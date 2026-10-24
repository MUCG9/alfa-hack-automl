"""Entry-specific CLASS preparation supervision; no numerical imports/heartbeat.

The main thread observes the owned child tree. Delegation carries those real
observations, never advances a child's own successful-resource timestamp.
"""
from contextvars import ContextVar
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import traceback
import psutil
from automl_atomic import atomic_json
from automl_infrastructure_processes import ProcessTree, ProcessCleanupError
from automl_verified_resource_sampling import VerifiedResourceSampler

MIB = 2**20
WORKER_CAP = 1536 * MIB
WHOLE_CAP = 2048 * MIB
_DELEGATION = ContextVar('owned_class_resource_delegation', default=None)


def safe_failure(error):
    frames = traceback.extract_tb(error.__traceback__)
    last = frames[-1] if frames else None
    return dict(type=type(error).__name__, location=(dict(module=Path(last.filename).name,
        function=last.name, line=last.lineno) if last else None))


def bounded_json(path, maximum=262144):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= maximum:
        raise RuntimeError('delegation_bounded_regular_file_required')
    with path.open('rb') as stream: raw = stream.read(maximum + 1)
    if len(raw) > maximum: raise RuntimeError('delegation_receipt_size')
    return json.loads(raw.decode('utf-8'))


def file_sha(path, check):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(2**20), b''):
            check(); value.update(chunk)
    check(); return value.hexdigest()


def source_hashes(check):
    root = Path(__file__).resolve().parent
    paths = sorted(root.glob('*.py')) + [root / 'requirements.txt']
    return {path.name: file_sha(path, check) for path in paths}


def identity(process):
    return (process.pid, process.create_time())


def exact_process(expected):
    if (type(expected) is not list or len(expected) != 2 or type(expected[0]) is not int
            or type(expected[1]) not in (float, int) or not math.isfinite(expected[1])):
        raise RuntimeError('delegation_typed_identity_required')
    process = psutil.Process(expected[0])
    if identity(process) != tuple(expected): raise RuntimeError('delegation_birth_changed')
    return process


class ParentObservationClock:
    def __init__(self, origin, seconds, root):
        if (type(origin) is not tuple or len(origin) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in origin)
                or type(seconds) not in (int, float) or not 30 <= seconds <= 9900):
            raise ValueError('original_release_clock_required')
        self.start_unix, self.start_monotonic = origin
        self.seconds = seconds
        self.end_unix = origin[0] + seconds; self.end_monotonic = origin[1] + seconds
        self.previous = self.last = origin[1]
        self.root = Path(root); self.failure = None; self.samples = 0; self.max_gap = 0.
        self.peak_worker = self.peak_whole = 0; self.sequence = 0
        self.check()
        self.own = identity(psutil.Process(os.getpid())); self.check()
        self.sampler = VerifiedResourceSampler(); self.last_sample = None

    def check(self):
        if self.failure is not None: raise self.failure
        try:
            now = time.monotonic(); wall = time.time()
            if not math.isfinite(now) or not math.isfinite(wall) or now < self.previous or wall < self.start_unix:
                raise RuntimeError('parent_clock_rollback_or_nonfinite')
            self.previous = now
            if now - self.last > 10: raise RuntimeError('parent_observation_gap_over10s')
            if now >= self.end_monotonic or wall >= self.end_unix: raise RuntimeError('parent_original_deadline')
            if abs((self.end_unix - wall) - (self.end_monotonic - now)) > 5:
                raise RuntimeError('parent_wall_monotonic_disagreement')
            return now, wall
        except BaseException as error:
            self.failure = error; raise

    def observe(self, tree=None, force=False):
        try:return self._observe(tree,force)
        except BaseException as error:
            if self.failure is None:self.failure=error
            raise

    def _observe(self, tree=None, force=False):
        now, _ = self.check()
        if not force and self.samples and now - self.last < .25: return self.last_sample
        known = [self.own]
        if tree is not None:
            tree.refresh(); self.check(); known.extend(tree.members)
            roots = [item for item in tree.members if item[0] == tree.process.pid]
            if tree.process.poll() is None and len(roots) != 1:
                raise RuntimeError('parent_owned_root_identity_unconfirmed')
            if roots: self.sampler.discover_owned_tree(roots[0], checkpoint=self.check)
        self.sampler.remember(known)
        sample = self.sampler.sample(list(self.sampler.known), required=[self.own], checkpoint=self.check)
        rows = {(row['pid'], row['create_time']): row['rss_bytes'] for row in sample['sampled']}
        if tree is not None and tree.process.poll() is None:
            roots = [item for item in tree.members if item[0] == tree.process.pid]
            if len(roots)!=1 or roots[0] not in rows:
                raise RuntimeError('parent_resource_root_absent_with_live_handle')
        whole = sum(rows.values()); worker = sum(v for key, v in rows.items() if key != self.own)
        self.peak_worker = max(self.peak_worker, worker); self.peak_whole = max(self.peak_whole, whole)
        if worker > WORKER_CAP: raise RuntimeError('parent_worker_tree_memory_limit')
        if whole > WHOLE_CAP: raise RuntimeError('parent_whole_memory_limit')
        after, _ = self.check()
        self.max_gap = max(self.max_gap, after - self.last)
        self.last = after; self.samples += 1; self.sequence += 1
        self.last_sample = dict(sequence=self.sequence, successful_sample_monotonic=after,
            sampled=sample['sampled'], departed=sample['departed'], worker_tree_rss_bytes=worker,
            whole_rss_bytes=whole, maximum_observation_gap_seconds=self.max_gap,
            actual_successful_samples=self.samples, failure=None)
        return self.last_sample


class DelegatedResourceAuthority:
    """Owned-pipe/bootstrap authority, checked afresh; not an OS sandbox."""
    def __init__(self, manifest, *, directory):
        if (type(manifest) is not dict or manifest.get('schema') != 'owned-class-parent-authority-v1'
                or manifest.get('worker_cap') != WORKER_CAP or manifest.get('whole_cap') != WHOLE_CAP):
            raise RuntimeError('delegation_schema_or_caps')
        required = {'schema','session','parent_identity','child_identity','launch_identity',
            'launch_executable','launch_executable_sha256','start_unix','start_monotonic',
            'global_deadline_unix','global_deadline_monotonic','declared_seconds',
            'execution_deadline_unix','execution_deadline_monotonic','observation_path',
            'source_sha256','worker_cap','whole_cap'}
        if set(manifest) != required: raise RuntimeError('delegation_manifest_fields')
        times = [manifest[k] for k in ('start_unix','start_monotonic','global_deadline_unix',
            'global_deadline_monotonic','execution_deadline_unix','execution_deadline_monotonic','declared_seconds')]
        if (any(type(v) not in (int,float) or not math.isfinite(v) for v in times)
                or not 60 <= manifest['declared_seconds'] <= 9900
                or manifest['global_deadline_unix'] != manifest['start_unix'] + manifest['declared_seconds']
                or manifest['global_deadline_monotonic'] != manifest['start_monotonic'] + manifest['declared_seconds']
                or manifest['execution_deadline_unix'] != manifest['global_deadline_unix'] - 30
                or manifest['execution_deadline_monotonic'] != manifest['global_deadline_monotonic'] - 30
                or Path(manifest['observation_path']).resolve() != Path(directory).resolve()/'observation.json'
                or not isinstance(manifest['session'],str) or len(manifest['session'])!=32
                or not all(c in '0123456789abcdef' for c in manifest['session'])
                or not isinstance(manifest['source_sha256'],dict) or not manifest['source_sha256']):
            raise RuntimeError('delegation_original_bounds_or_paths')
        self.manifest = manifest; self.failure = None; self.last_sequence = 0
        self.start_unix = manifest['start_unix']; self.start_monotonic = manifest['start_monotonic']
        self.deadline_unix = manifest['execution_deadline_unix']
        self.deadline_monotonic = manifest['execution_deadline_monotonic']
        self.previous = self.start_monotonic
        self.check()
        if source_hashes(self.check) != manifest['source_sha256']:
            raise RuntimeError('delegation_source_changed')

    def check(self):
        if self.failure is not None: raise self.failure
        try:
            m = self.manifest
            now = time.monotonic(); wall = time.time()
            if (not math.isfinite(now) or not math.isfinite(wall) or now < self.previous
                    or wall < self.start_unix or now >= self.deadline_monotonic or wall >= self.deadline_unix
                    or abs((self.deadline_unix - wall) - (self.deadline_monotonic - now)) > 5):
                raise RuntimeError('delegation_original_clock_invalid')
            self.previous = now
            own = exact_process(m['child_identity']); parent = exact_process(m['parent_identity'])
            if own.pid != os.getpid(): raise RuntimeError('delegation_wrong_child')
            launch = m['launch_identity']
            if tuple(launch) == identity(own):
                if own.ppid() != parent.pid: raise RuntimeError('delegation_wrong_direct_parent')
            else:
                intermediate = exact_process(launch)
                if own.ppid() != intermediate.pid or intermediate.ppid() != parent.pid:
                    raise RuntimeError('delegation_extra_hop_or_reparented')
                executable = Path(intermediate.exe()).resolve()
                if (str(executable) != m['launch_executable']
                        or file_sha(executable, lambda: None) != m['launch_executable_sha256']):
                    raise RuntimeError('delegation_interpreter_changed')
            receipt = bounded_json(m['observation_path'])
            after = time.monotonic(); wall_after = time.time()
            if (receipt.get('schema') != 'owned-class-parent-observation-v1'
                    or receipt.get('session') != m['session'] or receipt.get('parent_identity') != m['parent_identity']
                    or receipt.get('child_identity') != m['child_identity']
                    or receipt.get('start_unix') != self.start_unix
                    or receipt.get('start_monotonic') != self.start_monotonic
                    or receipt.get('execution_deadline_unix') != self.deadline_unix
                    or receipt.get('execution_deadline_monotonic') != self.deadline_monotonic):
                raise RuntimeError('delegation_receipt_binding')
            sample = receipt['observation']
            moment = sample['successful_sample_monotonic']
            rows=sample['sampled']
            if (type(rows) is not list or not 2 <= len(rows) <= 30000
                    or any(type(row) is not dict or type(row.get('pid')) is not int or row['pid']<=0
                        or type(row.get('create_time')) not in (int,float) or not math.isfinite(row['create_time'])
                        or row['create_time']<=0 or type(row.get('rss_bytes')) is not int or row['rss_bytes']<0 for row in rows)):
                raise RuntimeError('delegation_sample_rows_untyped')
            identities = {(r['pid'], r['create_time']) for r in rows}
            if (len(identities)!=len(rows) or sum(r['rss_bytes'] for r in rows)!=sample['whole_rss_bytes']
                    or sum(r['rss_bytes'] for r in rows if (r['pid'],r['create_time'])!=tuple(m['parent_identity']))!=sample['worker_tree_rss_bytes']):
                raise RuntimeError('delegation_sample_sum_or_identity_changed')
            if (type(sample['sequence']) is not int or sample['sequence'] < self.last_sequence
                    or sample['sequence'] < 1 or sample.get('failure') is not None
                    or type(moment) not in (int,float) or not math.isfinite(moment)
                    or not self.start_monotonic <= moment <= after
                    or type(sample['maximum_observation_gap_seconds']) not in (int,float)
                    or not math.isfinite(sample['maximum_observation_gap_seconds'])
                    or not 0 <= sample['maximum_observation_gap_seconds'] <= 10
                    or sample['actual_successful_samples'] != sample['sequence']
                    or after - moment > 10
                    or tuple(m['parent_identity']) not in identities or tuple(m['child_identity']) not in identities
                    or type(sample['worker_tree_rss_bytes']) is not int or not 0 <= sample['worker_tree_rss_bytes'] <= WORKER_CAP
                    or type(sample['whole_rss_bytes']) is not int or not 0 <= sample['whole_rss_bytes'] <= WHOLE_CAP
                    or after >= self.deadline_monotonic or wall_after >= self.deadline_unix):
                raise RuntimeError('delegation_observation_stale_or_unqualified')
            self.last_sequence = sample['sequence']; self.previous = after
            return after, wall_after
        except BaseException as error:
            self.failure = error; raise


def current_delegation(): return _DELEGATION.get()


def write_observation(path, manifest, observation):
    keys = ('session', 'parent_identity', 'child_identity', 'start_unix', 'start_monotonic',
            'execution_deadline_unix', 'execution_deadline_monotonic')
    atomic_json(path, dict(schema='owned-class-parent-observation-v1',
        **{key: manifest[key] for key in keys}, observation=observation))


def supervise_class(task, origin, seconds):
    if seconds < 60: raise ValueError('class_release_needs_original_cleanup_reserve')
    clock = ParentObservationClock(origin, seconds, Path(task).parent)
    output = Path(task).parent / 'automl_runs'; output.mkdir(exist_ok=True)
    session = secrets.token_hex(16)
    directory = output / ('class-supervision-' + session); directory.mkdir()
    result_path = directory / 'supervision.json'
    process = tree = None; primary = None; secondary = []; cleanup = False; child_diagnostic = None
    report = dict(schema='owned-class-supervision-v1', status='running', session=session,
        start_unix=origin[0], start_monotonic=origin[1], global_deadline_unix=clock.end_unix,
        global_deadline_monotonic=clock.end_monotonic, worker_cap=WORKER_CAP, whole_cap=WHOLE_CAP,
        first_failure=None, secondary_failures=[], child_failure=None, cleanup_confirmed=False,
        qualified=False, new_metric=None, API_calls=0)
    try:
        clock.observe(force=True)
        before = source_hashes(lambda: clock.observe())
        executable = str(Path(sys.executable).resolve())
        executable_sha = file_sha(executable, lambda: clock.observe())
        phase_end_mono = clock.end_monotonic - 30; phase_end_wall = clock.end_unix - 30
        command = [sys.executable, '-u', str(Path(__file__).with_name('automl_release_class_child.py')),
                   str(task), str(directory), session, str(origin[0]), str(origin[1]),
                   str(phase_end_wall), str(phase_end_mono)]
        env = {k: v for k, v in os.environ.items() if not any(s in k.upper()
               for s in ('KEY', 'TOKEN', 'SECRET', 'PROXY', 'PASSWORD', 'PASSWD', 'AUTH'))}
        env.update(AUTOML_THREADS='2', PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
        for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS',
                     'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS'): env[name] = '2'
        with (directory / 'child.log').open('w', encoding='utf-8') as log:
            clock.observe(force=True)
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                cwd=Path(task).parent, env=env, start_new_session=True)
            tree = ProcessTree(process, strict_observation=True)
            roots = [item for item in tree.members if item[0] == process.pid]
            if len(roots) != 1: raise RuntimeError('owned_launch_identity_required')
            launch = roots[0]
            hello_path = directory / 'hello.json'
            while not hello_path.exists():
                clock.observe(tree)
                if process.poll() is not None: raise RuntimeError('child_failed_before_authority')
                if time.monotonic() >= min(phase_end_mono, clock.start_monotonic + 60):
                    raise RuntimeError('child_bootstrap_not_ready')
                time.sleep(.05)
            hello = bounded_json(hello_path)
            clock.observe(tree, force=True)
            child = hello.get('child_identity')
            if (hello.get('schema') != 'owned-class-child-hello-v1' or hello.get('session') != session
                    or type(child) is not list or tuple(child) not in clock.sampler.known):
                raise RuntimeError('child_hello_not_owned')
            manifest = dict(schema='owned-class-parent-authority-v1', session=session,
                parent_identity=list(clock.own), child_identity=child, launch_identity=list(launch),
                launch_executable=executable, launch_executable_sha256=executable_sha,
                start_unix=origin[0], start_monotonic=origin[1],
                global_deadline_unix=clock.end_unix, global_deadline_monotonic=clock.end_monotonic,
                declared_seconds=clock.seconds,
                execution_deadline_unix=phase_end_wall, execution_deadline_monotonic=phase_end_mono,
                observation_path=str(directory / 'observation.json'), source_sha256=before,
                worker_cap=WORKER_CAP, whole_cap=WHOLE_CAP)
            write_observation(Path(manifest['observation_path']), manifest, clock.observe(tree, force=True))
            atomic_json(directory / 'authority.json', manifest)
            while True:
                observation = clock.observe(tree)
                write_observation(Path(manifest['observation_path']), manifest, observation)
                if time.monotonic() >= phase_end_mono or time.time() >= phase_end_wall:
                    raise RuntimeError('child_phase_original_deadline')
                if process.poll() is not None: break
                time.sleep(.05)
            clock.observe(tree, force=True)
            report['actual_child_exit_code'] = process.returncode
            diagnostic = directory / 'child-diagnostic.json'
            if diagnostic.exists(): child_diagnostic = bounded_json(diagnostic)
            if process.returncode != 0: raise RuntimeError('class_child_nonzero_exit')
            if not child_diagnostic or child_diagnostic.get('status') != 'completed':
                raise RuntimeError('class_child_completion_receipt_missing')
    except BaseException as error:
        primary = error
    finally:
        if tree is not None:
            try:
                for known in clock.sampler.known:
                    if known != clock.own: tree.members.setdefault(known, None)
                tree.terminate(); cleanup = True
            except BaseException as error:
                if primary is None: primary = error
                else: secondary.append(safe_failure(error))
        elif process is not None:
            try:
                if process.poll() is None: process.kill()
                process.wait(timeout=max(.001, min(3, clock.end_monotonic - time.monotonic())))
            except BaseException as error: secondary.append(safe_failure(error))
        if primary is None:
            try:
                clock.observe(tree, force=True)
                if source_hashes(lambda: clock.observe(tree)) != before:
                    raise RuntimeError('release_source_changed')
                clock.observe(tree, force=True)
            except BaseException as error: primary = error
        if child_diagnostic is None and (directory/'child.log').is_file():
            try:
                log=(directory/'child.log')
                with log.open('rb') as stream:
                    stream.seek(max(0,log.stat().st_size-262144));tail=stream.read(262144).decode('utf-8',errors='replace')
                for line in reversed(tail.splitlines()):
                    try: value=json.loads(line)
                    except (ValueError,TypeError): continue
                    if (type(value) is dict and value.get('schema')=='owned-class-child-early-failure-v1'
                            and value.get('session')==session): child_diagnostic=value;break
            except BaseException as error: secondary.append(safe_failure(error))
        report.update(status='failed' if primary is not None else 'completed_pending_independent_qualification',
            first_failure=safe_failure(primary) if primary else None,
            secondary_failures=secondary, child_failure=child_diagnostic,
            cleanup_confirmed=cleanup, qualified=False,
            actual_successful_resource_samples=clock.samples, maximum_observation_gap_seconds=clock.max_gap,
            observed_worker_tree_peak_bytes=clock.peak_worker, observed_whole_peak_bytes=clock.peak_whole)
        try:
            atomic_json(result_path, report)
            if primary is None: clock.check()
        except BaseException as error:
            if primary is None: primary = error
            else: secondary.append(safe_failure(error))
        if primary is not None:
            print(json.dumps(dict(status='failed', phase='class_supervision', first_failure=safe_failure(primary),
                secondary_failures=secondary, cleanup_confirmed=cleanup)), flush=True)
    if primary is not None: raise primary
    return 0
