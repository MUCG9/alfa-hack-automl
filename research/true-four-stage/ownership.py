"""Prepare by default. Explicit reviewed launch supervises one frozen six-worker screen.

No alternative learner, API client, promotion, source modification or automatic
continuation of 2e. The only fit entry point is the existing benchmark tool.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import signal
import subprocess
import sys
import time
import zipfile

WORK = Path(__file__).resolve().parent
REPO = WORK / 'alfa-hack-automl'
PLAN = WORK / 'support-context-component-plan'
BUNDLE = WORK / 'support-component-launch'
OUTPUT = REPO / 'test-runs/sc1'
QUEUE = REPO / 'test-runs/2e/queue.json'
QUEUE_MANIFEST = REPO / 'test-runs/native-screen-plan/execution-ready-native-iteration2e/manifest.json'
PREDECESSORS = [{'pid': 6412, 'create_time': 1792718706.779424},
                {'pid': 24700, 'create_time': 1792718706.768474}]
TOTAL_SECONDS, VERIFICATION_RESERVE = 4200, 600
WORKER_SECONDS, THREADS, WORKER_MEMORY_GIB = 600, 2, 1.5
SUPERVISOR_MEMORY_BYTES = 2 * 2**30  # Same benchmark-parent allowance as 2e; each worker remains1.5GiB.
sys.dont_write_bytecode = True


def configure_work_root(path):
    """Allow an identical published copy under research/ to use explicit task work."""
    global WORK, REPO, PLAN, BUNDLE, OUTPUT, QUEUE, QUEUE_MANIFEST
    WORK = Path(path).expanduser().resolve()
    REPO = WORK / 'alfa-hack-automl'
    PLAN = WORK / 'support-context-component-plan'
    BUNDLE = WORK / 'support-component-launch'
    OUTPUT = REPO / 'test-runs/sc1'
    QUEUE = REPO / 'test-runs/2e/queue.json'
    QUEUE_MANIFEST = REPO / 'test-runs/native-screen-plan/execution-ready-native-iteration2e/manifest.json'
    if not (REPO / 'src/automl').is_dir() or not PLAN.is_dir():
        raise ValueError('Use --work-root pointing to task work with repository and frozen component plan')
    sys.path[:0] = [str(REPO / 'src'), str(REPO / 'tools')]


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            value.update(block)
    return value.hexdigest()


def relative(path):
    return Path(path).resolve().relative_to(WORK).as_posix()


def write(path, value, exclusive=False):
    with Path(path).open('x' if exclusive else 'w', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def identity(value):
    pid, created = value['pid'], value['create_time']
    if type(pid) is not int or pid <= 0 or isinstance(created, bool) or not math.isfinite(created) or created <= 0:
        raise ValueError('Unverifiable predecessor identity')
    return pid, float(created)


class StrictOwnedObserver:
    """Observe exact owned identities without signalling; remember any denial.

    ProcessTree remains the cleanup implementation. This independent observation
    layer covers its swallowed descendant-enumeration errors and final alive set.
    """
    def __init__(self):
        self.seen = set()
        self.denials = []

    def denied(self, pid, created, action, reason):
        if type(pid) is not int or pid <= 0:
            pid = None
        if (not isinstance(created, (int, float)) or isinstance(created, bool)
                or not math.isfinite(created) or created <= 0):
            created = None
        item = {'pid': pid, 'create_time': created, 'action': action, 'reason': reason}
        if item not in self.denials:
            self.denials.append(item)

    def remember(self, identities):
        for pid, created in identities:
            if type(pid) is int and pid > 0 and isinstance(created, (int, float)) and not isinstance(created, bool) and math.isfinite(created) and created > 0:
                self.seen.add((pid, float(created)))
            else:
                self.denied(pid, created, 'remember_identity', 'birth_time_unverified')

    def observe(self):
        import psutil
        live, pending, visited = {}, list(self.seen), set()
        while pending:
            expected = pending.pop()
            if expected in visited:
                continue
            visited.add(expected)
            pid, created = expected
            try:
                current = psutil.Process(pid)
                if current.create_time() != created:
                    continue  # A new unrelated process is never signalled.
                if current.status() in {psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD}:
                    continue
                live[expected] = current
            except psutil.NoSuchProcess:
                continue
            except psutil.AccessDenied:
                self.denied(pid, created, 'verify_identity', 'AccessDenied')
                continue
            try:
                descendants = current.children(recursive=True)
            except psutil.NoSuchProcess:
                continue
            except psutil.AccessDenied:
                self.denied(pid, created, 'enumerate_descendants', 'AccessDenied')
                continue
            for child in descendants:
                try:
                    actual = child.pid, child.create_time()
                    self.remember([actual])
                    if actual not in visited:
                        pending.append(actual)
                except psutil.NoSuchProcess:
                    continue
                except psutil.AccessDenied:
                    self.denied(child.pid, None, 'discover_descendant_identity', 'AccessDenied')
        return live

    def final_check(self):
        live = self.observe()
        unresolved = list(self.denials)
        for pid, created in sorted(live):
            unresolved.append({'pid': pid, 'create_time': created,
                               'action': 'final_fresh_identity_recheck', 'reason': 'same_identity_alive'})
        return {'observed_count': len(self.seen), 'denial_count': len(self.denials),
                'unresolved': unresolved}


def cleanup_owned(child, tree, observer, initially_verified, tree_factory):
    """Always attempt known-owned cleanup, then independently certify absence."""
    if child is None:
        return {'cleanup_confirmed': True, 'owned_process_identities': [],
                'cleanup_observation': {'observed_count': 0, 'denial_count': 0, 'unresolved': []}}
    before = set(observer.seen)
    if not initially_verified:
        observer.denied(child.pid, None, 'initial_process_tracking', 'initial_identity_not_verified')
        if tree is None:
            try:
                tree = tree_factory(child)
            except BaseException as exc:
                observer.denied(child.pid, None, 'retry_process_tracking', type(exc).__name__)
    def remember_tree(stage):
        if tree is not None:
            try:
                observer.remember(list(tree.members))
                observer.remember(list(getattr(tree, '_pending_cleanup', {})))
            except BaseException as exc:
                observer.denied(child.pid, None, stage, type(exc).__name__)
    remember_tree('pre_cleanup_tracker_inventory')
    # Strict observer errors never prevent canonical known-owned/root cleanup.
    try:
        fresh = observer.observe()
        if tree is not None:
            tree.members.update(fresh)
    except BaseException as exc:
        observer.denied(child.pid, None, 'pre_cleanup_observation', type(exc).__name__)
    if tree is not None:
        before.update(observer.seen)
        try:
            tree.terminate()
        except BaseException as exc:
            observer.denied(child.pid, None, 'canonical_tree_cleanup', type(exc).__name__)
        remember_tree('post_cleanup_tracker_inventory')
        try:
            for item in getattr(tree, 'cleanup_errors', []):
                observer.denied(item.get('pid'), item.get('create_time'),
                                'canonical_' + item.get('action', 'cleanup'), item.get('error', 'unverified'))
        except BaseException as exc:
            observer.denied(child.pid, None, 'post_cleanup_tracker_errors', type(exc).__name__)
    # Popen owns this exact root handle, even if identity discovery failed.
    try:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=3)
    except BaseException as exc:
        observer.denied(child.pid, None, 'exact_root_handle_cleanup', type(exc).__name__)
    observer.remember(before)
    try:
        final = observer.final_check()
    except BaseException as exc:
        observer.denied(child.pid, None, 'final_fresh_observation', type(exc).__name__)
        final = {'observed_count': len(observer.seen), 'denial_count': len(observer.denials),
                 'unresolved': list(observer.denials)}
    if child.poll() is None:
        final['unresolved'].append({'pid': child.pid, 'create_time': None,
                                    'action': 'final_root_handle_recheck', 'reason': 'root_still_running'})
    return {'cleanup_confirmed': not final['unresolved'], 'benchmark_exit_code': child.poll(),
            'owned_process_identities': [{'pid': p, 'create_time': c} for p, c in sorted(observer.seen)],
            'cleanup_observation': dict(final, tracked_before_cleanup_count=len(before),
                                        tracked_after_cleanup_count=len(tree.members) if tree is not None else 0)}


def predecessor_snapshot(known=()):
    """Read only: never signal a predecessor or a PID with a changed birth time.

    Include all queue-declared job roots and recursively observed descendants.
    An orphan PPID scan also conservatively blocks descendants of exited roots;
    terminal source-supervisor cleanup telemetry remains mandatory at launch.
    """
    import psutil
    queue = load(QUEUE)
    members = {identity(value) for value in [*PREDECESSORS, *known]}
    for job in queue.get('jobs', []):
        if job.get('owned_root'):
            members.add(identity(job['owned_root']))
    live = {}
    for expected in list(members):
        try:
            process = psutil.Process(expected[0])
            if process.create_time() != expected[1]:
                continue
            if process.status() in {psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD}:
                continue
            live[expected] = process
            for child in process.children(recursive=True):
                actual = child.pid, child.create_time()
                members.add(actual)
                if child.status() not in {psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD}:
                    live[actual] = child
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            raise RuntimeError('Predecessor identity or descendants cannot be verified') from None
    # Windows retains an orphan's parent PID. Only read identity fields, never argv/env.
    processes = []
    for process in psutil.process_iter(['pid', 'ppid', 'create_time', 'status']):
        try:
            info = process.info
            if info['ppid'] is not None and info['create_time'] is not None:
                processes.append((process, info))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    changed = True
    while changed:
        changed = False
        for process, info in processes:
            actual = info['pid'], info['create_time']
            if actual in members or info['status'] in {psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD}:
                continue
            for parent_pid, parent_created in tuple(members):
                if info['ppid'] != parent_pid or info['create_time'] < parent_created:
                    continue
                try:
                    current_parent = psutil.Process(parent_pid)
                    parent_now = current_parent.create_time()
                    if parent_now != parent_created and info['create_time'] >= parent_now:
                        continue  # Child of a reused, unrelated PID.
                except psutil.NoSuchProcess:
                    pass
                except psutil.AccessDenied:
                    raise RuntimeError('Orphan-parent identity cannot be verified') from None
                members.add(actual)
                live[actual] = process
                changed = True
                break
    return {'tracked': [{'pid': p, 'create_time': c} for p, c in sorted(members)],
            'active': [{'pid': p, 'create_time': c} for p, c in sorted(live)],
            'queue_status': queue['status'], 'cleanup_confirmed': queue.get('cleanup_confirmed'),
            'queue_source_unchanged': queue.get('source_unchanged')}


def technical_gates():
    queue, manifest = load(QUEUE), load(QUEUE_MANIFEST)
    protocol = load(PLAN / 'protocol.json')
    if queue['archive_sha256'] != protocol['evaluator_archive_sha256'] or queue['frozen_fingerprints']['compiled_files'] != protocol['evaluator_compiled_sha256']:
        raise ValueError('2e compiled runtime differs from frozen component runtime')
    if digest(QUEUE_MANIFEST) != queue['execution_manifest_sha256']:
        raise ValueError('2e execution manifest changed')
    jobs = {job['name']: job for job in queue['jobs']}
    for name in ['source-checks', 'exact-unpacked', 'live-four-stage']:
        if jobs.get(name, {}).get('status') != 'ok':
            raise ValueError('Reusable exact technical gate not passed: ' + name)
    paths = [REPO / 'test-runs/2e/gates/source-checks/results.json',
             REPO / 'test-runs/2e/gates/exact-unpacked.json',
             REPO / 'test-runs/2e/gates/live-four-stage/live-summary.json']
    source, release, live = map(load, paths)
    if (source.get('passed') is not True or source.get('source_unchanged') is not True
            or source.get('unique_checks_passed') != manifest['expected_source_checks']
            or source.get('unique_checks_skipped') != 0
            or source['source_sha256'] != protocol['evaluator_compiled_sha256']):
        raise ValueError('Source gate does not certify this exact source')
    if release.get('passed') is not True or release['sha256'] != protocol['evaluator_archive_sha256']:
        raise ValueError('Exact archive gate differs')
    if (live.get('passed') is not True or live['archive_sha256'] != protocol['evaluator_archive_sha256']
            or live.get('four_stage_pipeline', {}).get('initial_data_assessment_before_fitting') is not True):
        raise ValueError('Live four-stage gate differs')
    # Every current canonical source/test/tool byte must match the gate's own frozen inventory.
    for path, expected in queue['frozen_fingerprints']['files'].items():
        if digest(path) != expected:
            raise ValueError('2e frozen source/input/harness changed')
    current_python = {str(path.resolve()) for name in ['src', 'tools', 'tests'] for path in (REPO / name).rglob('*.py')}
    saved_python = {str(Path(path).resolve()) for path in queue['frozen_fingerprints']['files']
                    if Path(path).suffix == '.py' and any(Path(path).resolve().is_relative_to(REPO / name) for name in ['src', 'tools', 'tests'])}
    if current_python != saved_python:
        raise ValueError('2e canonical source inventory changed')
    return {relative(path): digest(path) for path in paths}


def prepare():
    if BUNDLE.exists():
        raise FileExistsError('Preserve existing launch manifest; do not overwrite')
    protocol = load(PLAN / 'protocol.json')
    if digest(PLAN / 'candidates.json') != protocol['candidates_file_sha256']:
        raise ValueError('Frozen candidate file changed')
    if digest(PLAN / 'evaluator-source.zip') != protocol['evaluator_archive_sha256']:
        raise ValueError('Frozen archive bytes changed')
    with zipfile.ZipFile(PLAN / 'evaluator-source.zip') as packed:
        compiled = {name: hashlib.sha256(packed.read(name)).hexdigest() for name in packed.namelist()}
    if compiled != protocol['evaluator_compiled_sha256']:
        raise ValueError('Frozen archive inventory changed')
    for name, expected in protocol['packet_sha256'].items():
        if digest(PLAN / 'generation-packet' / name) != expected:
            raise ValueError('Frozen generation packet changed')
    for seed in [42, 43]:
        if digest(PLAN / 'splits' / f'group-{seed}.npz') != protocol['splits'][str(seed)]['split_file_sha256']:
            raise ValueError('Frozen partition bytes changed')
    gate_hashes = technical_gates()
    queue = load(QUEUE)
    frozen = {relative(Path(path)): expected for path, expected in queue['frozen_fingerprints']['files'].items()}
    for path in PLAN.rglob('*'):
        if path.is_file():
            frozen[relative(path)] = digest(path)
    frozen.update(gate_hashes)
    frozen[relative(QUEUE_MANIFEST)] = digest(QUEUE_MANIFEST)
    frozen[relative(Path(__file__))] = digest(__file__)
    for name, expected in protocol['evaluator_harness_sha256'].items():
        if digest(WORK / name) != expected:
            raise ValueError('Prepared component harness no longer matches')
    bundle = {'status': 'prepared_not_launched', 'new_model_fits': 0, 'new_api_calls': 0,
        'output': relative(OUTPUT), 'task': 'evaluation/multiclass/task.md',
        'protocol_sha256': digest(PLAN / 'protocol.json'), 'immutable_files': frozen,
        'coordinator_sha256': digest(__file__),
        'canonical_python_inventory': sorted(relative(path) for name in ['src', 'tools', 'tests'] for path in (REPO / name).rglob('*.py')),
        'reused_technical_gates': gate_hashes, 'predecessor_initial_snapshot': predecessor_snapshot(),
        'source_archive_sha256': protocol['evaluator_archive_sha256'],
        'worker_limits': {'seconds': 600, 'threads': 2, 'memory_gib': 1.5, 'sequential_workers': 6},
        'coordinator_limits': {'total_seconds': 4200, 'verification_reserve_seconds': 600,
            'supervisor_tree_memory_gib': 2, 'scope': 'Same parent allowance as 2e; worker cap unchanged'},
        'deadline': 'Not assigned in preparation. Root must supply an absolute Unix deadline only at a reviewed launch after2e has released all resources.',
        'promotion': False}
    BUNDLE.mkdir()
    write(BUNDLE / 'manifest.json', bundle, exclusive=True)
    print(json.dumps({'status': bundle['status'], 'manifest_sha256': digest(BUNDLE / 'manifest.json'),
                      'active_predecessors': len(bundle['predecessor_initial_snapshot']['active']),
                      'fits': 0, 'api_calls': 0}))


def guard(bundle):
    if digest(__file__) != bundle['coordinator_sha256']:
        raise ValueError('Executing coordinator differs from reviewed source bytes')
    inventory = sorted(relative(path) for name in ['src', 'tools', 'tests'] for path in (REPO / name).rglob('*.py'))
    if inventory != bundle['canonical_python_inventory']:
        raise ValueError('Immutable canonical source inventory changed')
    for name, expected in bundle['immutable_files'].items():
        path = (WORK / name).resolve()
        if not path.is_relative_to(WORK) or digest(path) != expected:
            raise ValueError('Immutable source/input/packet changed: ' + name)


def require_free(bundle):
    state = predecessor_snapshot(bundle['predecessor_initial_snapshot']['tracked'])
    terminal = state['queue_status'].startswith('completed') or state['queue_status'].startswith('budget_exhausted')
    if state['active'] or not terminal or state['cleanup_confirmed'] is not True or state['queue_source_unchanged'] is not True:
        raise RuntimeError('2e or an owned descendant is active/unverifiable, or terminal cleanup is unconfirmed')
    return state


def context_and_splits(bundle):
    import numpy as np
    from automl.task_understanding.api import discover
    from automl.evaluation.api import choose_validation, make_split
    # Discovery is deterministic on the already-verified ordinary named CSV inputs.
    import automl.infrastructure.llm_gateway as gateway
    import automl.task_understanding.semantic_inputs as semantic_inputs
    def forbidden_request(*args, **kwargs):
        raise RuntimeError('API access forbidden in component preflight')
    gateway.request_json = forbidden_request
    semantic_inputs.request_json = forbidden_request
    spec, _, train, test, sample, _, hashes = discover(WORK / bundle['task'])
    spec = choose_validation(spec, train, 'auto')
    if (spec['kind'] != 'classification' or spec['metric'] != 'macro_f1'
            or spec['target'] in spec['features'] or spec.get('id') in spec['features']):
        raise ValueError('Unexpected feature/target contract')
    protocol = load(PLAN / 'protocol.json')
    for filename, receipt in protocol['task_input_sha256'].items():
        if digest((WORK / bundle['task']).parent / filename) != receipt['sha256']:
            raise ValueError('Pristine task input changed')
    splits = {}
    for seed in [42, 43]:
        tr, va, metadata = make_split(spec, train, hashes, seed=seed)
        path = PLAN / 'splits' / f'group-{seed}.npz'
        if digest(path) != protocol['splits'][str(seed)]['split_file_sha256']:
            raise ValueError('Frozen split bytes changed')
        with np.load(path, allow_pickle=False) as saved:
            if not np.array_equal(tr, saved['train']) or not np.array_equal(va, saved['validation']):
                raise ValueError('Prelaunch saved-array equality failed')
        if np.intersect1d(hashes[tr], hashes[va]).size:
            raise ValueError('Feature groups overlap')
        splits[seed] = tr, va, metadata
    return spec, train, test, sample, hashes, splits


def audit_results(bundle, context, output, deadline):
    import numpy as np
    import pandas as pd
    spec, train, test, sample, hashes, splits = context
    manifest = load(output / 'results.json')
    protocol, candidates = load(PLAN / 'protocol.json'), load(PLAN / 'candidates.json')
    names = {item['name']: item['recipe'] for item in candidates}
    if manifest['source'] != protocol['evaluator_compiled_sha256'] or manifest['spec'] != spec or manifest['candidates'] != candidates:
        raise ValueError('Actual evaluator source/spec/candidates differ')
    with zipfile.ZipFile(PLAN / 'evaluator-source.zip') as archive:
        for name in archive.namelist():
            if (output / 'sources' / name).read_bytes() != archive.read(name):
                raise ValueError('Actual copied evaluator source differs')
    for name, expected in manifest['harness'].items():
        if digest(REPO / name) != expected or expected != bundle['immutable_files'].get(relative(REPO / name)):
            raise ValueError('Actual evaluator harness differs')
    for role, location in spec['paths'].items():
        if digest(location) != manifest['inputs'][role]:
            raise ValueError('Actual evaluator input differs')
    truth, classes = train[spec['target']].astype(str).to_numpy(), list(spec['classes'])
    if set(classes) != set(truth):
        raise ValueError('Pristine class inventory differs')
    rows, verified, seen = [], {}, set()
    for item in manifest['results']:
        if time.time() >= deadline:
            raise TimeoutError('Absolute deadline reached during verification')
        key = item['name'], item['seed']
        if key in seen or key[0] not in names or key[1] not in splits:
            raise ValueError('Unexpected or duplicate actual worker')
        seen.add(key)
        status = item['status']
        if status != 'ok' or item.get('exit_code') != 0:
            rows.append({'candidate': key[0], 'seed': key[1], 'status': status, 'metrics': None})
            continue
        folder = Path(item['directory']).resolve()
        if folder != (output / key[0] / f'seed-{key[1]}').resolve():
            raise ValueError('Actual artifact directory differs')
        job, result = load(folder / 'job.json'), load(folder / 'result.json')
        if (job['spec'] != spec or job['recipe'] != names[key[0]] or job['threads'] != 2
                or job['full_fit'] is not False or result['status'] != 'ok'
                or result['recipe'] != job['recipe'] or result['full_fit'] is not False
                or Path(job['split_path']).resolve() != folder / 'split.npz'):
            raise ValueError('Actual worker job/result contract differs')
        tr, va, metadata = splits[key[1]]
        with np.load(folder / 'split.npz', allow_pickle=False) as stored:
            if not np.array_equal(tr, stored['train']) or not np.array_equal(va, stored['validation']):
                raise ValueError('Postrun frozen-array equality failed')
        if item['split'] != metadata:
            raise ValueError('Actual split metadata differs')
        frame = pd.read_csv(folder / 'validation_predictions.csv')
        with np.load(folder / 'validation_probabilities.npz', allow_pickle=False) as stored:
            stored_classes = list(stored['classes'].astype(str))
            if len(stored_classes) != len(classes) or set(stored_classes) != set(classes) or not np.array_equal(stored['row_position'], va):
                raise ValueError('Validation classes/positions differ')
            probabilities = stored['probabilities'][:, [stored_classes.index(c) for c in classes]]
        if (probabilities.shape != (len(va), len(classes)) or not np.isfinite(probabilities).all()
                or (probabilities < 0).any() or (probabilities > 1).any()
                or not np.allclose(probabilities.sum(axis=1), 1., atol=1e-6)):
            raise ValueError('Invalid validation probabilities')
        predicted = np.asarray(classes)[probabilities.argmax(axis=1)]
        if (not np.array_equal(frame.row_position, va) or not np.array_equal(frame.y_true.astype(str), truth[va])
                or not np.array_equal(frame.y_pred.astype(str), predicted)):
            raise ValueError('Pristine label / row order / prediction mismatch')
        per_class = {}
        for label in classes:
            actual, guess = truth[va] == label, predicted == label
            tp = int(np.sum(actual & guess))
            denominator = int(np.sum(actual) + np.sum(guess))
            per_class[label] = 2. * tp / denominator if denominator else 0.
        macro = float(np.mean(list(per_class.values())))
        for reported in [item.get('metrics'), result.get('metrics')]:
            value = (reported or {}).get('macro_f1')
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value - macro) > 1e-12:
                raise ValueError('Saved MacroF1 does not reproduce')
        support = {c: int(len(np.unique(hashes[tr][truth[tr] == c]))) for c in classes}
        expected_support = protocol['splits'][str(key[1])]['support']
        rarest = min(classes, key=lambda c: support[c])
        if support != expected_support['independent_fitting_feature_groups_per_class'] or rarest != expected_support['rarest_fitting_class']:
            raise ValueError('Pristine fitting-group support differs')
        with np.load(folder / 'test_probabilities.npz', allow_pickle=False) as stored:
            order = list(stored['classes'].astype(str))
            if len(order) != len(classes) or set(order) != set(classes):
                raise ValueError('Test class inventory differs')
            test_probability = stored['probabilities'][:, [order.index(c) for c in classes]]
        if (test_probability.shape != (len(test), len(classes)) or not np.isfinite(test_probability).all()
                or (test_probability < 0).any() or (test_probability > 1).any()
                or not np.allclose(test_probability.sum(axis=1), 1., atol=1e-6)):
            raise ValueError('Invalid test probabilities')
        csv = pd.read_csv(folder / 'submission.csv')
        positions = np.asarray(spec.get('sample_test_positions', np.arange(len(test))))
        expected_prediction = np.asarray(classes)[test_probability.argmax(axis=1)][positions]
        if list(csv) != list(sample) or len(csv) != len(sample) or csv.isna().any().any():
            raise ValueError('Actual submission schema differs')
        if spec.get('id') is not None and not csv[spec['id']].equals(sample[spec['id']]):
            raise ValueError('Pristine sample IDs/order differ')
        if not np.array_equal(csv[spec['output_columns'][0]].astype(str), expected_prediction):
            raise ValueError('Actual CSV and test probability order differ')
        record = {'candidate': key[0], 'seed': key[1], 'status': 'verified_ok',
            'metrics': {'macro_f1': macro, 'per_class_f1': per_class,
                'ex_rarest_macro_f1': float(np.mean([per_class[c] for c in classes if c != rarest]))},
            'fitting_independent_groups': support, 'rarest_class': rarest,
            'supported_classes': [c for c in classes if support[c] >= 100],
            'artifact_sha256': {path.relative_to(folder).as_posix(): digest(path) for path in folder.rglob('*')
                if path.is_file() and path.suffix in {'.json', '.csv', '.npz'}}}
        rows.append(record)
        verified[key] = record
    expected = {(name, seed) for name in names for seed in [42, 43]}
    complete = set(verified) == expected and seen == expected
    comparisons = []
    if complete:
        control, old, support = [v['name'] for v in candidates]
        for base, candidate in [(control, old), (control, support), (old, support)]:
            cuts = []
            for seed in [42, 43]:
                a, b = verified[(base, seed)], verified[(candidate, seed)]
                deltas = {c: b['metrics']['per_class_f1'][c] - a['metrics']['per_class_f1'][c] for c in classes}
                cuts.append({'seed': seed, 'macro_f1_delta': b['metrics']['macro_f1'] - a['metrics']['macro_f1'],
                    'ex_rarest_delta': b['metrics']['ex_rarest_macro_f1'] - a['metrics']['ex_rarest_macro_f1'],
                    'per_class_f1_delta': deltas,
                    'supported_class_gate': all(deltas[c] >= -.01 for c in a['supported_classes'])})
            comparisons.append({'control': base, 'candidate': candidate, 'cuts': cuts,
                'component_gate_passed': all(c['macro_f1_delta'] > 0 and c['ex_rarest_delta'] > 0 and c['supported_class_gate'] for c in cuts)})
    return {'status': 'complete_verified_component_screen' if complete else 'incomplete_component_screen',
        'complete_six_workers': complete, 'workers': rows, 'comparisons': comparisons,
        'missing_workers': [{'candidate': name, 'seed': seed, 'metrics': None} for name, seed in sorted(expected - seen)],
        'actual_results_sha256': digest(output / 'results.json'), 'failed_metrics_zero_imputed': False,
        'ex_rarest_definition': 'Mean original per-class F1 excluding predeclared rarest label; all validation rows retained',
        'promotion': False, 'quality_generalization_claim': False,
        'scope': 'One frozen fixed-recipe reused-public component screen; no official score or whole-agent qualification'}


def launch(args):
    import psutil
    from research_lock import ResearchLock
    from automl.infrastructure.processes import ProcessTree
    path = BUNDLE / 'manifest.json'
    if not args.manifest_sha256 or digest(path) != args.manifest_sha256:
        raise ValueError('Explicit reviewed manifest SHA is required')
    if args.deadline_unix is None or not math.isfinite(args.deadline_unix):
        raise ValueError('Explicit finite absolute root-assigned deadline required')
    launch_started_unix = time.time()
    remaining = args.deadline_unix - launch_started_unix
    if not VERIFICATION_RESERVE + 10 < remaining <= TOTAL_SECONDS:
        raise ValueError('Deadline must leave verification reserve and be within4200s; never reset an active budget')
    bundle = load(path)
    guard(bundle)
    require_free(bundle)  # Refuse active2e; do not wait under a fresh clock.
    with ResearchLock(REPO / 'test-runs/.owned-research.lock') as lock:
        lock.write_identity({'pid': os.getpid(), 'create_time': psutil.Process().create_time()})
        predecessor = require_free(bundle)
        guard(bundle)
        technical_gates()
        context = context_and_splits(bundle)  # Mandatory saved-array equality BEFORE any fit.
        if OUTPUT.exists():
            raise FileExistsError('Do not overwrite a previous component attempt')
        OUTPUT.mkdir()
        report = {'status': 'preflight_verified', 'absolute_deadline_unix': args.deadline_unix,
            'launch_started_unix': launch_started_unix, 'initial_remaining_seconds': remaining,
            'manifest_sha256': args.manifest_sha256, 'protocol_sha256': bundle['protocol_sha256'],
            'predecessor_terminal_proof': predecessor, 'predecessor_final_queue_sha256': digest(QUEUE),
            'reused_technical_gates': bundle['reused_technical_gates'], 'new_api_calls': 0,
            'cleanup_confirmed': False, 'promotion': False}
        write(OUTPUT / 'coordinator.json', report)
        command = [sys.executable, '-u', str(REPO / 'tools/benchmark_candidates.py'),
            '--task', str(WORK / bundle['task']), '--candidates', str(PLAN / 'candidates.json'),
            '--output', str(OUTPUT / 'b'), '--archive', str(PLAN / 'evaluator-source.zip'),
            '--validation-strategy', 'auto', '--seeds', '42', '43', '--threads', '2', '--timeout', '600', '--memory-gb', '1.5']
        env = {key: value for key, value in os.environ.items() if not any(marker in key.upper()
               for marker in ['KEY', 'TOKEN', 'SECRET', 'AUTH', 'PASSWORD', 'PROXY']) and not key.upper().startswith(('OPENAI_', 'DASHSCOPE_'))}
        env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', AUTOML_THREADS='2')
        for key in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
            env[key] = '2'
        child, tree, tracking_verified = None, None, False
        observer = StrictOwnedObserver()
        started = time.monotonic()
        fit_deadline = started + max(0., args.deadline_unix - time.time() - VERIFICATION_RESERVE)
        last_guard = 0.
        def interrupted(signum, frame):
            raise SystemExit(128 + signum)
        previous = {sig: signal.signal(sig, interrupted) for sig in [signal.SIGINT, signal.SIGTERM]}
        try:
            if args.deadline_unix - time.time() <= VERIFICATION_RESERVE + 5:
                raise TimeoutError('Preflight consumed fit allocation; no process launched')
            with (OUTPUT / 'benchmark.log').open('x', encoding='utf-8') as log:
                child = subprocess.Popen(command, cwd=REPO, env=env, stdin=subprocess.DEVNULL,
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    report['owned_root'] = {'pid': child.pid, 'create_time': psutil.Process(child.pid).create_time()}
                except psutil.NoSuchProcess:
                    report['owned_root'] = {'pid': child.pid, 'create_time': None}
                root = report['owned_root']
                observer.remember([(root['pid'], root['create_time'])])
                tree = ProcessTree(child)
                if root['create_time'] is None or (root['pid'], root['create_time']) not in tree.members:
                    raise RuntimeError('Initial root ownership was not observed by process tracker')
                tracking_verified = True
                report['status'] = 'running_component'
                observer.remember(list(tree.members))
                report['owned_process_identities'] = [{'pid': p, 'create_time': c} for p, c in sorted(observer.seen)]
                report['heartbeat_unix'] = time.time()
                write(OUTPUT / 'coordinator.json', report)
                while child.poll() is None:
                    tree.refresh()
                    observer.remember(list(tree.members))
                    observer.remember(list(getattr(tree, '_pending_cleanup', {})))
                    fresh = observer.observe()
                    tree.members.update(fresh)
                    if observer.denials:
                        raise RuntimeError('Owned process identity or descendant enumeration was denied')
                    rss = psutil.Process().memory_info().rss
                    for member in fresh.values():
                        try:
                            rss += member.memory_info().rss
                        except psutil.NoSuchProcess:
                            pass
                    if rss > SUPERVISOR_MEMORY_BYTES:
                        raise MemoryError('Supervisor tree allowance exceeded')
                    now = time.monotonic()
                    if now >= fit_deadline or time.time() >= args.deadline_unix - VERIFICATION_RESERVE:
                        raise TimeoutError('Fit phase exhausted; preserve verification reserve')
                    if now - last_guard >= 10:
                        guard(bundle)
                        require_free(bundle)
                        last_guard = now
                        report['heartbeat_unix'] = time.time()
                        report['owned_process_identities'] = [{'pid': p, 'create_time': c} for p, c in sorted(observer.seen)]
                        report['process_observation'] = {'observed_count': len(observer.seen),
                            'tracked_count': len(tree.members), 'denial_count': len(observer.denials)}
                        write(OUTPUT / 'coordinator.json', report)
                    time.sleep(.1)
                report['benchmark_exit_code'] = child.returncode
        except BaseException as exc:
            report.update(status='component_stopped', exception_type=type(exc).__name__)
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                report['interrupted'] = True
        finally:
            try:
                report.update(cleanup_owned(child, tree, observer, tracking_verified, ProcessTree))
                report['heartbeat_unix'] = time.time()
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
                write(OUTPUT / 'coordinator.json', report)
        if not report['cleanup_confirmed']:
            raise RuntimeError('Owned component cleanup unconfirmed')
        try:
            guard(bundle)
            if time.time() >= args.deadline_unix:
                raise TimeoutError('No verification time remains')
            report['audit'] = audit_results(bundle, context, OUTPUT / 'b', args.deadline_unix)
            report['status'] = (report['audit']['status'] if report.get('benchmark_exit_code') == 0
                                and not report.get('exception_type') else 'supervisor_stopped_with_saved_artifacts')
            report['source_input_packet_unchanged'] = True
            guard(bundle)
        except Exception as exc:
            report.update(status='verification_failed', verification_exception_type=type(exc).__name__)
            report['audit'] = {'complete_six_workers': False, 'metrics': None, 'promotion': False}
        report['elapsed_fit_and_verification_seconds'] = round(time.monotonic() - started, 3)
        report['total_launch_elapsed_seconds'] = round(time.time() - launch_started_unix, 3)
        write(OUTPUT / 'coordinator.json', report)
        if (report.get('benchmark_exit_code') != 0 or not report['audit']['complete_six_workers']
                or report['status'] != 'complete_verified_component_screen'):
            raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launch', action='store_true', help='Requires explicit root review, terminal2e and absolute deadline')
    parser.add_argument('--work-root', type=Path, default=Path(__file__).resolve().parent,
                        help='Task work directory; supply explicitly when running the published research copy')
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--deadline-unix', type=float)
    args = parser.parse_args()
    configure_work_root(args.work_root)
    if args.launch:
        launch(args)
    else:
        if args.manifest_sha256 or args.deadline_unix:
            parser.error('Deadline/reviewed SHA belong only to an explicit --launch')
        prepare()


if __name__ == '__main__':
    main()
