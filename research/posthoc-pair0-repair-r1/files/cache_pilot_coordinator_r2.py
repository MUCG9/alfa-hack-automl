"""One reviewed 7200-second sequential cache pilot. Inspect manifest by default.

--launch requires exact manifest/root review/publication and a fresh immutable
root-assigned clock. No retry/resume, private API/config access or promotion.
Common runtime/probe is identical in OFF and ON; only the strict cache flag differs.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import zipfile

sys.dont_write_bytecode = True
TOTAL = 7200
FINAL_RESERVE = 600


class TechnicalFailure(RuntimeError):
    pass


def require(condition, code):
    if not condition:
        raise TechnicalFailure(code)


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value, exclusive=False):
    payload = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    if exclusive:
        with Path(path).open('xb') as stream:
            stream.write(payload)
    else:
        tmp = Path(path).with_suffix(Path(path).suffix + '.pending')
        tmp.write_bytes(payload)
        os.replace(tmp, path)


def relative(work, value):
    return Path(value).resolve().relative_to(work).as_posix()


def resolve(work, name):
    p = (work / name).resolve()
    require(not Path(name).is_absolute() and p.is_relative_to(work), 'unsafe_reference')
    return p


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def identities(value):
    result = set()
    if isinstance(value, dict):
        if 'pid' in value and 'create_time' in value:
            p, c = value['pid'], value['create_time']
            require(type(p) is int and p > 0 and type(c) in (int, float) and math.isfinite(c) and c > 0,
                    'unverifiable_identity')
            result.add((p, float(c)))
        for key, child in value.items():
            if key not in {'excluded_impossible_parent_edges', 'terminal_excluded_impossible_parent_edges'}:
                result.update(identities(child))
    elif isinstance(value, list):
        for child in value:
            result.update(identities(child))
    return result


def clock(deadline, unix):
    require(abs((deadline - time.monotonic()) - (unix - time.time())) <= 5, 'clock_disagreement')
    require(time.monotonic() < deadline and time.time() < unix, 'common_deadline_exhausted')


def guard(work, manifest, deployment=None):
    for field in ['_manifest_binding', '_root_review_binding']:
        if field in manifest:
            ref = manifest[field]
            require(digest(resolve(work, ref['path'])) == ref['sha256'], 'manifest_or_root_review_changed')
    for n, sha in manifest['immutable_files'].items():
        require(digest(resolve(work, n)) == sha, 'immutable_source_or_input_changed')
    require(digest(sys.executable) == manifest['python_sha256'], 'interpreter_changed')
    prep = module('_cache_guard_preparation', work / 'prepare_cache_pilot_r2.py')
    require(prep.dependencies() == manifest['dependencies'], 'dependency_inventory_changed')
    for root_name, entries in (deployment or {}).items():
        root = resolve(work, root_name)
        for n, sha in entries.items():
            require(digest(resolve(work, root_name + '/' + n)) == sha, 'deployed_source_or_input_changed')
        expected_python = {n for n in entries if n.endswith('.py')}
        actual_python = {p.relative_to(root).as_posix() for p in root.rglob('*.py')}
        require(expected_python == actual_python, 'deployed_python_inventory_changed')


def predecessor(work, manifest, owner, strict, additional=()):
    binding = load(resolve(work, manifest['predecessor_binding']))
    require(binding.get('root_reviewed') is True and binding.get('scope_complete') is True
            and binding.get('cleanup_confirmed') is True and binding.get('source_unchanged') is True,
            'predecessor_proof_incomplete')
    known = identities(binding['owned_identities']) | set(additional)
    for n, sha in binding['files_sha256'].items():
        p = resolve(work, n)
        require(digest(p) == sha, 'predecessor_receipt_changed')
        if n not in binding['owned_receipt_paths']:
            continue  # Analysis inventories are evidence, never ownership grants.
        value = load(p)
        known |= identities(value)
        if 'cleanup_confirmed' in value:
            require(value['cleanup_confirmed'] is True, 'predecessor_cleanup_uncertain')
        if 'source_unchanged' in value:
            require(value['source_unchanged'] is True, 'predecessor_integrity_uncertain')
        require(not str(value.get('status', '')).startswith('running'), 'predecessor_active')
    fresh = strict.strict_orphan_check_with_one_fence(owner,
        [dict(pid=p, create_time=c) for p, c in sorted(known)],
        work / 'fullagent-cv-stage1-review-r4/stage0-terminal-ownership.json')
    return {'cleanup_confirmed': True, 'active': [], 'no_predecessor_signalled': True,
            'tracked': fresh['tracked_identities'], 'lifetime_fence': fresh['fence'],
            'excluded_impossible_parent_edges': fresh['excluded_impossible_parent_edges'],
            'binding_sha256': digest(resolve(work, manifest['predecessor_binding']))}


def environment(directory, threads):
    allowed = {'PATH', 'SystemRoot', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'ComSpec',
               'PATHEXT', 'PROCESSOR_ARCHITECTURE', 'NUMBER_OF_PROCESSORS'}
    env = {k: v for k, v in os.environ.items() if k in allowed}
    directory.mkdir(parents=True)
    (directory / 't').mkdir()
    (directory / 'm').mkdir()
    env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1',
        AUTOML_THREADS=str(threads), OMP_NUM_THREADS=str(threads), OPENBLAS_NUM_THREADS=str(threads),
        MKL_NUM_THREADS=str(threads), NUMEXPR_NUM_THREADS=str(threads),
        TMPDIR=str(directory / 't'), TEMP=str(directory / 't'), TMP=str(directory / 't'),
        MPLCONFIGDIR=str(directory / 'm'))
    return env


def supervise(work, manifest, output, name, command, cwd, parent_start, parent_cap,
              child_cap, deadline, unix, reserve, libs, deployment, report, persist,
              worker_job=None, memory_bytes=None):
    """Child watchdog is separate from complete parent cap, with fixed cleanup reserve.

    The calling slot's timer starts before job creation. This function's receipt
    is saved before the caller seals artifacts and records its complete parent
    elapsed time. All those later actions remain inside the same parent cap.
    """
    import psutil
    owner, processes, strict = libs
    child = tree = None
    observer = owner.StrictOwnedObserver()
    verified = False
    path = output / (name + '-supervisor.json')
    parent_deadline = parent_start + parent_cap
    result = {'status': 'starting', 'start_unix': time.time(), 'parent_start_monotonic': parent_start,
        'parent_cap_seconds': parent_cap, 'child_cap_seconds': child_cap,
        'owned_process_identities': [], 'cleanup_confirmed': False, 'maximum_logical_jobs': 0,
        'peak_owned_tree_RSS_MiB': 0., 'API_limit': 0}
    save(path, result, True)
    report['active_supervisor'] = {'path': relative(work, path), 'name': name}
    last_heartbeat = last_guard = time.monotonic()
    child_deadline = None
    try:
        clock(deadline, unix)
        guard(work, manifest, deployment)
        env = environment(output / 'e' / name, 2 if worker_job else 1)
        require(deadline - time.monotonic() >= reserve, 'full_remaining_reserve_not_available')
        require(parent_deadline - time.monotonic() >= child_cap, 'setup_consumed_full_child_allocation')
        with (output / (name + '.log')).open('x', encoding='utf-8') as log:
            clock(deadline, unix)
            require(deadline - time.monotonic() >= reserve and
                    parent_deadline - time.monotonic() >= child_cap, 'prePopen_full_allocation_unavailable')
            child = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            child_tick = time.monotonic()
            child_deadline = child_tick + child_cap
            root = psutil.Process(child.pid)
            root_identity = root.pid, root.create_time()
            observer.remember([root_identity])
            tree = processes.ProcessTree(child)
            observer.remember(tree.members)
            verified = root_identity in tree.members
            require(verified, 'initial_child_identity_unverified')
            result.update(status='running', owned_root=dict(pid=root_identity[0], create_time=root_identity[1]),
                child_start_monotonic=child_tick, child_deadline_monotonic=child_deadline)
            save(path, result)
            persist()
            while True:
                live = observer.observe()
                tree.members.update(live)
                require(not observer.denials, 'identity_or_traversal_denied')
                parents, roles, memory = {}, {}, {}
                for identity in live:
                    try:
                        current = psutil.Process(identity[0])
                        if current.create_time() != identity[1]:
                            continue
                        parents[identity[0]] = current.ppid()
                        memory[identity] = current.memory_info().rss
                        argv = current.cmdline()  # Exact owned identities only; never saved.
                        if any(Path(a).name in {'automl_worker.py', 'agent_worker.py'} for a in argv):
                            job = Path(argv[-1]).resolve()
                            require(job.is_relative_to(output) and job.name == 'job.json', 'unowned_worker_job_path')
                            require(worker_job is None or job == worker_job.resolve(), 'unexpected_callback_worker')
                            roles[identity] = job
                    except psutil.NoSuchProcess:
                        continue
                    except psutil.AccessDenied:
                        observer.denied(*identity, 'role_or_memory', 'AccessDenied')
                        raise TechnicalFailure('role_or_memory_denied') from None
                top = []
                for identity, job in roles.items():
                    cursor, ancestors = parents.get(identity[0]), set()
                    while cursor is not None and cursor not in ancestors:
                        ancestors.add(cursor)
                        cursor = parents.get(cursor)
                    if not ancestors & {i[0] for i in roles}:
                        top.append((identity, job))
                require(len(top) <= 1, 'multiple_logical_jobs')
                result['maximum_logical_jobs'] = max(result['maximum_logical_jobs'], len(top))
                for identity, job in top:
                    subtree = 0
                    for member, rss in memory.items():
                        cursor, ancestors = member[0], set()
                        while cursor is not None and cursor not in ancestors:
                            ancestors.add(cursor)
                            cursor = parents.get(cursor)
                        if identity[0] in ancestors:
                            subtree += rss
                    require(subtree <= manifest['worker_memory_bytes'], 'worker_subtree_memory_limit')
                    if worker_job:
                        actual = load(job)
                        require(actual.get('threads') == 2 and actual.get('full_fit') is False, 'worker_contract_drift')
                total = psutil.Process().memory_info().rss + sum(memory.values())
                for bootstrap in report.get('coordinator_bootstrap_identities', []):
                    try:
                        parent = psutil.Process(bootstrap['pid'])
                        require(parent.create_time() == bootstrap['create_time'], 'coordinator_bootstrap_identity_changed')
                        total += parent.memory_info().rss
                    except psutil.NoSuchProcess:
                        continue
                    except psutil.AccessDenied:
                        raise TechnicalFailure('coordinator_bootstrap_memory_denied') from None
                bound = memory_bytes if memory_bytes is not None else manifest['whole_memory_bytes']
                require(total <= bound, 'whole_owned_tree_memory_limit')
                result['peak_owned_tree_RSS_MiB'] = max(result['peak_owned_tree_RSS_MiB'], total / 2**20)
                now = time.monotonic()
                clock(deadline, unix)
                require(now < parent_deadline, 'parent_cap_exhausted')
                if now >= child_deadline:
                    result.update(status='worker_timeout' if worker_job else 'technical_failure',
                        failure_code='local_child_watchdog', child_seconds=now - child_tick)
                    break
                if child.poll() is not None:
                    result.update(status='ok' if child.returncode == 0 else 'worker_failed', exit_code=child.returncode,
                                  child_seconds=now - child_tick)
                    break
                if now - last_guard >= 30:
                    guard(work, manifest, deployment)
                    last_guard = time.monotonic()
                if now - last_heartbeat >= 2:
                    result.update(heartbeat_unix=time.time(), owned_process_identities=[
                        dict(pid=p, create_time=c) for p, c in sorted(observer.seen)])
                    save(path, result)
                    persist()
                    last_heartbeat = time.monotonic()
                time.sleep(.1)
    except BaseException as exc:
        result.update(status='technical_failure', exception_type=type(exc).__name__,
            failure_code=str(exc) if isinstance(exc, TechnicalFailure) else 'supervisor_exception')
    finally:
        result.update(owner.cleanup_owned(child, tree, observer, verified, processes.ProcessTree))
        # Cleanup telemetry uses benchmark_exit_code; preserve truthful local
        # watchdog classification even when its owned child was terminated.
        if result.get('exit_code') is None:
            result['exit_code'] = child.poll() if child is not None else None
        try:
            require(result['cleanup_confirmed'], 'cleanup_not_confirmed')
            guard(work, manifest, deployment)
            clock(deadline, unix)
            require(time.monotonic() < parent_deadline, 'parent_cleanup_or_guard_over_cap')
        except BaseException as exc:
            result.update(status='technical_failure', terminal_exception_type=type(exc).__name__,
                failure_code=str(exc) if isinstance(exc, TechnicalFailure) else 'terminal_guard_exception')
        result.update(seconds=time.monotonic() - parent_start, end_unix=time.time())
        save(path, result)
        if time.monotonic() >= parent_deadline or time.monotonic() >= deadline or time.time() >= unix:
            result.update(status='technical_failure', failure_code='supervisor_terminal_write_over_cap')
            save(path, result)
        persist()
        report['supervisors'].append({'path': relative(work, path), 'sha256': digest(path), 'status': result['status']})
        report['active_supervisor'] = None
        persist()
    return result, path


def seal(root):
    result = {}
    for parent, dirs, names in os.walk(root):
        require(not any((Path(parent) / n).is_symlink() for n in [*dirs, *names]), 'artifact_symlink')
        for n in names:
            p = Path(parent) / n
            require(not n.endswith(('.pending', '.tmp')), 'unfinished_atomic_artifact')
            result[p.relative_to(root).as_posix()] = digest(p)
    return result


def ordinary_model_failure(directory):
    """Only positively identified learner errors may continue the fixed matrix.

    The worker catches contract/probe/resource errors as well as model errors.
    An arbitrary exit1 or ValueError therefore cannot certify an ordinary fit
    failure. Unknown error types and every explicit resource marker fail closed.
    """
    p = directory / 'result.json'
    require(p.is_file(), 'worker_failure_without_result_contract')
    value = load(p)
    require(value.get('status') == 'error' and isinstance(value.get('error'), str), 'worker_failure_result_contract_invalid')
    error = value['error']
    require(not re.search(r'memory|allocat|out.of.memory|\boom\b|resource|thread|bad_alloc', error, re.I),
            'worker_reported_resource_failure')
    require(error.startswith(('LightGBMError:', 'CatBoostError:', 'XGBoostError:')),
            'worker_unknown_or_key_scope_contract_failure')
    return {'classification': 'positively_identified_ordinary_learner_error',
            'error_type': error.split(':', 1)[0], 'result_sha256': digest(p)}


def verify_saved_seals(work, output, slots):
    for slot in slots:
        if slot.get('seal'):
            ref = slot['seal']
            p = resolve(work, ref['path'])
            require(digest(p) == ref['sha256'], 'late_seal_receipt_changed')
            value = load(p)
            require(value['files_sha256'] == seal(output / slot['id']), 'late_sealed_artifact_changed')


def deploy_sources(work, output, manifest):
    deployment = {}
    for name, short in [('baseline', 'a'), ('candidate', 'b')]:
        arm = manifest['arms'][name]
        root = output / short
        root.mkdir()
        for n, sha in arm['source_files_sha256'].items():
            target = resolve(work, relative(work, root) + '/' + n)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(resolve(work, arm['source_refs'][n]), target)
            require(digest(target) == sha, 'source_deployment_changed_bytes')
        deployment[relative(work, root)] = arm['source_files_sha256']
    return deployment


def shared_inputs(work, output, manifest, deployment):
    for kind, task in manifest['input_fingerprints']['tasks'].items():
        root = output / 'd' / kind
        root.mkdir(parents=True)
        entries = {}
        for n, sha in task['expected_files_sha256'].items():
            shutil.copyfile(resolve(work, task['pristine_source'] + '/' + n), root / n)
            require(digest(root / n) == sha, 'shared_input_copy_changed')
            entries[n] = sha
        split = manifest['input_fingerprints']['splits'][kind]
        shutil.copyfile(resolve(work, split['source_path']), root / 'split.npz')
        require(digest(root / 'split.npz') == split['file_sha256'], 'shared_split_copy_changed')
        entries['split.npz'] = split['file_sha256']
        deployment[relative(work, root)] = entries
    flat = output / 'flat'
    flat.mkdir()
    arm = manifest['arms']['candidate']
    with zipfile.ZipFile(resolve(work, arm['archive'])) as z:
        require(set(z.namelist()) == set(arm['compiled_sha256']), 'runtime_archive_inventory_changed')
        for n, sha in arm['compiled_sha256'].items():
            require(Path(n).name == n, 'runtime_archive_escape')
            (flat / n).write_bytes(z.read(n))
            require(digest(flat / n) == sha, 'flat_runtime_copy_changed')
    deployment[relative(work, flat)] = arm['compiled_sha256']


def materialize(work, output, manifest, slot):
    anchor = next(a for a in manifest['anchors'] if a['id'] == slot['anchor'])
    job = copy.deepcopy(load(resolve(work, anchor['source_job'])))
    directory = output / slot['id']
    directory.mkdir()
    inputs = output / 'd' / slot['anchor'][0]
    job['output_dir'] = str(directory)
    job['split_path'] = str(inputs / 'split.npz')
    job['spec']['root'] = str(inputs)
    job['spec']['task_path'] = str(inputs / 'task.md')
    for key, original in job['spec']['paths'].items():
        name = Path(original).name
        require(name in manifest['input_fingerprints']['tasks'][slot['anchor'][0]]['expected_files_sha256'],
                'undeclared_input_basename')
        job['spec']['paths'][key] = str(inputs / name)
    job['selector_importance_cache'] = slot['enabled']
    job['selector_importance_diagnostics'] = True
    save(directory / 'job.json', job, True)
    return directory


def invalidate(report):
    report.update(qualification='FAIL', complete_six=False, mechanism_pass=False,
        positive_descriptive_time_label=False, total_parent_delta_OFF_minus_ON=None,
        measured_savings=None, quality_gain=None, full_agent_gain=None)
    for slot in report['slots']:
        slot.update(qualified=False, paired_speedup=None, mechanism_pass=False)
    if isinstance(report.get('audit'), dict):
        report['audit']['explicitly_unqualified_after_late_technical_failure'] = True
        report['audit']['qualified_result'] = None


def run(work, packet, manifest, args):
    import psutil
    output = resolve(work, manifest['output'])
    require(not output.exists(), 'attempt_already_exists_no_resume')
    review = load(packet / 'review.json')
    require(review.get('root_launch_reviewed') is True and review.get('manifest_sha256') == args.manifest_sha256
            and review.get('source_sha256') == digest(__file__)
            and review.get('publication_remote_sha_verified') is True
            and review.get('source_and_verifier_reviewed') is True, 'root_exact_review_missing')
    manifest['_manifest_binding'] = {'path': relative(work, packet / 'manifest.json'), 'sha256': args.manifest_sha256}
    manifest['_root_review_binding'] = {'path': relative(work, packet / 'review.json'), 'sha256': digest(packet / 'review.json')}
    require(type(args.common_start_unix) in (int, float) and type(args.deadline_unix) in (int, float)
            and math.isfinite(args.common_start_unix) and math.isfinite(args.deadline_unix)
            and abs(args.deadline_unix - args.common_start_unix - TOTAL) <= 1e-6
            and 0 <= time.time() - args.common_start_unix <= 30, 'fresh_7200_root_clock_required')
    deadline = time.monotonic() + args.deadline_unix - time.time()
    guard(work, manifest)  # Verify imported source bytes before executing libraries.
    owner = module('_cache_owned_library', work / 'support_component_coordinator.py')
    processes = module('_cache_process_library', work / 'alfa-hack-automl/src/automl/infrastructure/processes.py')
    strict = module('_cache_strict_orphans', work / 'terminal_identity_fence_r1.py')
    lockmod = module('_cache_lock', work / 'alfa-hack-automl/tools/research_lock.py')
    awake = module('_cache_awake', work / 'hpo_campaign_coordinator.py')
    gate = module('_cache_gate_audits', work / 'fullagent_cv_coordinator_r4.py')
    libs = owner, processes, strict
    predecessor(work, manifest, owner, strict)
    guard(work, manifest)
    bootstraps = []
    parent = psutil.Process().parent()
    while parent is not None:
        # Venv redirectors run this exact reviewed script. Other ancestors are
        # outside this owned Python supervisor and are not adopted or signalled.
        created = parent.create_time()
        argv = parent.cmdline()
        if not any(Path(a).resolve() == Path(__file__).resolve() for a in argv if not a.startswith('-')):
            break
        require(parent.create_time() == created, 'coordinator_bootstrap_birth_changed')
        bootstraps.append(dict(pid=parent.pid, create_time=created))
        parent = parent.parent()
    report = {'status': 'starting', 'manifest_sha256': args.manifest_sha256,
        'root_review': manifest['_root_review_binding'],
        'source_sha256': digest(__file__), 'common_start_unix': args.common_start_unix,
        'common_start_monotonic': deadline - TOTAL, 'common_deadline_unix': args.deadline_unix,
        'common_deadline_monotonic': deadline, 'common_seconds': TOTAL,
        'owned_root': dict(pid=os.getpid(), create_time=psutil.Process().create_time()),
        'coordinator_bootstrap_identities': bootstraps,
        'slots': copy.deepcopy(manifest['slots']), 'gates': [], 'supervisors': [],
        'cleanup_confirmed': False, 'source_unchanged': False, 'audit': None,
        'API_limit': 0, 'fits': None, 'promotion': False, 'default_change': False,
        'full_agent_qualification': False, 'submit': False, 'qualification': None,
        'complete_six': False, 'mechanism_pass': False, 'positive_descriptive_time_label': False,
        'measured_savings': None, 'quality_gain': None, 'full_agent_gain': None}
    deployment, owned_finished = {}, set()
    campaign = output / 'campaign.json'
    def persist():
        save(campaign, report)
    def interrupted(signum, frame):
        raise SystemExit(128 + signum)
    old_signals = {}
    with lockmod.ResearchLock(work / 'alfa-hack-automl/test-runs/.owned-research.lock') as lock:
        lock.write_identity(report['owned_root'])
        report['predecessor'] = predecessor(work, manifest, owner, strict)
        guard(work, manifest)
        clock(deadline, args.deadline_unix)
        output.mkdir()
        report.update(status='running_technical_gates', scoped_awake_requested=awake.scoped_awake(True))
        old_signals = {sig: signal.signal(sig, interrupted) for sig in [signal.SIGINT, signal.SIGTERM]}
        persist()
        try:
            deployment.update(deploy_sources(work, output, manifest))
            for i, (name, cap) in enumerate(manifest['gates']):
                tick = time.monotonic()
                reserve = sum(c for _, c in manifest['gates'][i:]) + sum(s['parent_cap'] for s in report['slots']) + FINAL_RESERVE
                clock(deadline, args.deadline_unix)
                require(deadline - tick >= reserve, 'gate_remaining_full_reserve_unavailable')
                predecessor(work, manifest, owner, strict, owned_finished)
                out = output / 'g' / name
                out.parent.mkdir(exist_ok=True)
                if name == 'nofit':
                    out.mkdir()
                    command = [sys.executable, '-B', str(work / 'cache-pilot-dev/evidence/run_focused_mock_checks.py'),
                        '--freeze', str(work / 'cache-pilot-dev/evidence/pretest-manifest-r2.json'), '--output', str(out)]
                    cwd = work / 'cache-pilot-dev'
                else:
                    arm_name, kind = name.split('_')
                    arm = manifest['arms'][arm_name]
                    cwd = output / ('a' if arm_name == 'baseline' else 'b')
                    if kind == 'source':
                        command = [sys.executable, '-B', str(cwd / 'tools/run_checks.py'), '--output', str(out)]
                    else:
                        command = [sys.executable, '-B', str(cwd / 'tools/verify_release.py'),
                            '--archive', str(resolve(work, arm['archive'])), '--output', str(out.with_suffix('.json')),
                            '--timeout', '150', '--memory-gb', '1.5']
                sup, ref = supervise(work, manifest, output, name, command, cwd, tick, cap, cap - 20,
                    deadline, args.deadline_unix, reserve, libs, deployment, report, persist,
                    memory_bytes=512 * 2**20 if name == 'nofit' else None)
                owned_finished |= identities(sup)
                require(sup['status'] == 'ok' and sup['cleanup_confirmed'], 'technical_gate_process_failed')
                if name == 'nofit':
                    result = load(out / 'results.json')
                    require(result.get('status') == 'passed' and result['tests_run'] == 20
                        and result['source_unchanged'] is True and result['skips'] == 0
                        and result['failures'] == result['errors'] == 0 and
                        all(result[k] == 0 for k in ['forbidden_real_fit_attempts', 'forbidden_API_attempts', 'forbidden_network_attempts']),
                        'fresh_nofit_contract_failed')
                    proof = {'passed': True, 'checks': 20, 'result_sha256': digest(out / 'results.json')}
                elif kind == 'source':
                    proof = gate.source_gate(sup, arm, out)
                else:
                    proof = gate.exact_gate(sup, arm, out.with_suffix('.json'))
                guard(work, manifest, deployment)
                require(time.monotonic() < tick + cap, 'technical_gate_parent_proof_over_cap')
                report['gates'].append({'name': name, 'supervisor': {'path': relative(work, ref),
                    'sha256': digest(ref)}, 'proof': proof, 'parent_seconds': time.monotonic() - tick, 'parent_cap': cap})
                persist()
                require(time.monotonic() < tick + cap, 'technical_gate_terminal_parent_write_over_cap')
            shared_inputs(work, output, manifest, deployment)
            guard(work, manifest, deployment)
            report['status'] = 'running_six_fixed_callbacks'
            persist()
            for i, slot in enumerate(report['slots']):
                tick = time.monotonic()  # Before setup/job/env/guard/admission I/O.
                reserve = sum(s['parent_cap'] for s in report['slots'][i:]) + FINAL_RESERVE
                require(deadline - tick >= reserve, 'callback_remaining_full_reserve_unavailable')
                predecessor(work, manifest, owner, strict, owned_finished)
                directory = materialize(work, output, manifest, slot)
                slot.update(status='running', job_sha256=digest(directory / 'job.json'))
                persist()
                command = [sys.executable, '-B', str(output / 'flat/automl_worker.py'), str(directory / 'job.json')]
                sup, ref = supervise(work, manifest, output, slot['id'], command, output / 'flat',
                    tick, slot['parent_cap'], slot['worker_cap'], deadline, args.deadline_unix, reserve,
                    libs, deployment, report, persist, worker_job=directory / 'job.json')
                owned_finished |= identities(sup)
                slot['supervisor'] = {'path': relative(work, ref), 'sha256': digest(ref), 'object': sup}
                require(sup['status'] != 'technical_failure' and sup['cleanup_confirmed'], 'callback_technical_failure')
                require(sup['maximum_logical_jobs'] == 1, 'callback_logical_worker_not_proved')
                if sup['status'] == 'worker_failed':
                    slot['ordinary_failure_audit'] = ordinary_model_failure(directory)
                else:
                    require(sup['status'] in {'ok', 'worker_timeout'}, 'unknown_callback_status')
                guard(work, manifest, deployment)
                seal_path = output / (slot['id'] + '-seal.json')
                save(seal_path, {'root': relative(work, directory), 'files_sha256': seal(directory),
                    'source_unchanged': True, 'cleanup_confirmed': True, 'supervisor_sha256': digest(ref),
                    'job_sha256': slot['job_sha256']}, True)
                slot['seal'] = {'path': relative(work, seal_path), 'sha256': digest(seal_path)}
                # Parent receipt is already saved. Seal and all source/input
                # checks are included in this primary external elapsed timer.
                parent_seconds = time.monotonic() - tick
                require(parent_seconds < slot['parent_cap'], 'callback_parent_seal_over_cap')
                slot['timing'] = {'parent_seconds': parent_seconds, 'worker_supervisor_seconds': sup['seconds'],
                    'child_seconds': sup.get('child_seconds'), 'timer_start_monotonic': tick,
                    'timer_end_monotonic': tick + parent_seconds,
                    'boundary': 'Before setup through cleanup, guard, seal and saved supervisor receipt.'}
                slot['status'] = 'sealed_complete' if sup['status'] == 'ok' else sup['status']
                slot['metrics'] = None
                persist()
                require(time.monotonic() < tick + slot['parent_cap'], 'callback_terminal_parent_write_over_cap')
                clock(deadline, args.deadline_unix)
            report.update(status='auditing_fixed_matrix', cleanup_confirmed=True, source_unchanged=True)
            report['pre_audit_owned_closure'] = predecessor(work, manifest, owner, strict, owned_finished)
            persist()
            tick = time.monotonic()
            require(deadline - tick >= FINAL_RESERVE, 'full_final_audit_reserve_unavailable')
            # Final audit parent includes source guards, child, cleanup and final
            # qualification write; child has580s inside the600s fixed envelope.
            audit_deadline = min(tick + FINAL_RESERVE, deadline)
            command = [sys.executable, '-B', str(work / 'verify_cache_pilot_r2.py'),
                '--work-root', str(work), '--manifest', str(packet / 'manifest.json'),
                '--campaign', str(campaign), '--output', str(output / 'independent-audit.json'),
                '--deadline-monotonic', str(audit_deadline - 15)]
            sup, ref = supervise(work, manifest, output, 'final-audit', command, work, tick,
                FINAL_RESERVE, FINAL_RESERVE - 20, deadline, args.deadline_unix, FINAL_RESERVE,
                libs, deployment, report, persist)
            owned_finished |= identities(sup)
            require(sup['status'] == 'ok' and sup['cleanup_confirmed'], 'final_audit_process_failed')
            result = load(output / 'independent-audit.json')
            require(result['status'] != 'technical_audit_failure', 'independent_parity_or_mechanism_rejected')
            report['audit'] = {'path': relative(work, output / 'independent-audit.json'),
                'sha256': digest(output / 'independent-audit.json'), 'qualified_result': result}
            report.update(status='completed_fixed_matrix', complete_six=result['complete_six'],
                qualification='PASS' if result['complete_six'] else 'INCOMPLETE',
                mechanism_pass=result['mechanism_pass'], positive_descriptive_time_label=result['positive_descriptive_time_label'],
                total_parent_delta_OFF_minus_ON=result['total_parent_delta_OFF_minus_ON'])
            report['final_audit_deadline_monotonic'] = audit_deadline
            require(time.monotonic() < audit_deadline, 'final_audit_parent_over_cap')
        except BaseException as exc:
            report.update(status='technical_failure', exception_type=type(exc).__name__,
                failure_code=str(exc) if isinstance(exc, TechnicalFailure) else 'coordinator_exception')
            invalidate(report)
        finally:
            try:
                guard(work, manifest, deployment)
                verify_saved_seals(work, output, report['slots'])
                report['source_unchanged'] = True
            except BaseException as exc:
                report.update(status='technical_failure', source_unchanged=False, integrity_exception=type(exc).__name__)
                invalidate(report)
            try:
                supervisors = [load(p) for p in output.glob('*-supervisor.json')]
                union = set().union(*(identities(s) for s in supervisors)) if supervisors else set()
                report['final_owned_closure'] = predecessor(work, manifest, owner, strict, union)
                report['cleanup_confirmed'] = all(s.get('cleanup_confirmed') is True for s in supervisors)
            except BaseException as exc:
                report.update(cleanup_confirmed=False, cleanup_exception=type(exc).__name__)
            if not report['cleanup_confirmed']:
                report['status'] = 'fatal_cleanup_failure'
                invalidate(report)
            try:
                clock(deadline, args.deadline_unix)
                require('final_audit_deadline_monotonic' not in report or
                        time.monotonic() < report['final_audit_deadline_monotonic'], 'final_audit_terminal_over_cap')
            except BaseException as exc:
                report.update(status='technical_failure', clock_exception=type(exc).__name__)
                invalidate(report)
            report.update(end_unix=time.time(), seconds=time.monotonic() - (deadline - TOTAL),
                scoped_awake_released=awake.scoped_awake(False))
            if report['status'] in {'technical_failure', 'fatal_cleanup_failure'}:
                rejection = output / 'technical-rejection.json'
                save(rejection, {'status': report['status'], 'failure_code': report.get('failure_code'),
                    'exception_type': report.get('exception_type'), 'source_unchanged': report['source_unchanged'],
                    'cleanup_confirmed': report['cleanup_confirmed'], 'common_deadline_unix': args.deadline_unix,
                    'slots': [{k: s.get(k) for k in ['id', 'status', 'timing', 'supervisor', 'seal']} for s in report['slots']],
                    'metrics': None, 'measured_savings': None, 'promotion': False}, True)
                decisive = {'path': relative(work, rejection), 'sha256': digest(rejection)}
                for s in report['slots']:
                    if s['status'] in {'not_attempted', 'running'}:
                        s.update(status='not_attempted_due_technical_failure' if s['status'] == 'not_attempted'
                            else 'technical_failure', decisive_audit=decisive, metrics=None, paired_speedup=None)
            persist()
            if time.monotonic() >= deadline or time.time() >= args.deadline_unix or (
                    'final_audit_deadline_monotonic' in report and time.monotonic() >= report['final_audit_deadline_monotonic']):
                report.update(status='technical_failure', failure_code='terminal_campaign_write_over_cap')
                invalidate(report)
                persist()
            for sig, previous in old_signals.items():
                signal.signal(sig, previous)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work-root', type=Path, default=Path(__file__).resolve().parent)
    p.add_argument('--packet', default='cache-pilot-launch-r1')
    p.add_argument('--manifest-sha256', required=True)
    p.add_argument('--launch', action='store_true')
    p.add_argument('--common-start-unix', type=float)
    p.add_argument('--deadline-unix', type=float)
    a = p.parse_args()
    work = a.work_root.resolve()
    packet = resolve(work, a.packet)
    require(digest(packet / 'manifest.json') == a.manifest_sha256, 'manifest_exact_SHA_required')
    manifest = load(packet / 'manifest.json')
    require(manifest['total_seconds'] == TOTAL and manifest['final_audit_seconds'] == FINAL_RESERVE,
            'frozen_budget_changed')
    if not a.launch:
        print(json.dumps({'status': 'inspect_only_no_launch', 'manifest_sha256': a.manifest_sha256,
            'deadline_assigned': False, 'jobs_materialized': 0, 'tests_run': 0, 'fits': 0, 'API_calls': 0}))
        return
    report = run(work, packet, manifest, a)
    print(json.dumps({k: report[k] for k in ['status', 'qualification', 'complete_six',
        'mechanism_pass', 'positive_descriptive_time_label', 'seconds', 'promotion']}))
    raise SystemExit(0 if report['status'] == 'completed_fixed_matrix' else 1)


if __name__ == '__main__':
    main()
