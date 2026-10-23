"""Prepare a frozen 20-study campaign; launch only with a reviewed SHA/deadline.

This is a developer supervisor, not contest runtime. Preparation has no child
processes, model fitting, API requests, lock acquisition or assigned deadline.
The reviewed component benchmark remains the sole public-data fit entry point.
"""
from pathlib import Path
import argparse
import ast
import hashlib
import importlib.util
import json
import math
import os
import signal
from statistics import median
import subprocess
import sys
import time
import zipfile

sys.dont_write_bytecode = True
TOTAL_SECONDS = 46800
FINAL_RESERVE = 120
MODEL_AUDIT_RESERVE = 120
MEMORY_BYTES = 2 * 2**30


class IntegrityError(RuntimeError):
    pass


def configure(work):
    global WORK, DEV, CANON, PLAN, BUNDLE, OUTPUT, PROTOCOL
    WORK = Path(work).expanduser().resolve()
    DEV, CANON = WORK / 'iteration3-dev', WORK / 'alfa-hack-automl'
    PLAN, BUNDLE = WORK / 'iteration3-campaign-plan-r1', WORK / 'hpo-campaign-launch-r2'
    OUTPUT = DEV / 'test-runs/h31'
    PROTOCOL = DEV / 'docs/experiments/hpo_admission_b_protocol_20261023-r2.json'
    if not all(path.is_dir() for path in [DEV / 'src/automl', CANON / 'src/automl', PLAN]):
        raise ValueError('Use --work-root pointing to the prepared task work directory')
    sys.path[:0] = [str(DEV / 'src'), str(DEV / 'tools')]


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


def resolved(name):
    path = (WORK / name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to(WORK):
        raise IntegrityError('Manifest path escapes task work')
    return path


def write(path, value, exclusive=False):
    content = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    if exclusive:
        with Path(path).open('xb') as stream:
            stream.write(content)
    else:
        temporary = Path(path).with_name(Path(path).name + '.pending')
        temporary.write_bytes(content)
        os.replace(temporary, path)


def module(name, path):
    definition = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(definition)
    definition.loader.exec_module(loaded)
    return loaded


def finite(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def python_inventory():
    return sorted(relative(p) for folder in ['src', 'tools', 'tests'] for p in (DEV / folder).rglob('*.py'))


def source_files():
    files = [p for folder in ['src', 'tools', 'tests'] for p in (DEV / folder).rglob('*')
             if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
    files += [DEV / 'requirements.txt', WORK / 'native2e-completion-ownership.json', CANON / 'tools/research_lock.py',
              CANON / 'src/automl/infrastructure/processes.py']
    for root in [PLAN, WORK / 'iteration3-review-packet']:
        files += [p for p in root.rglob('*') if p.is_file()]
    files += list((DEV / 'docs/experiments').glob('hpo_admission_b_protocol_20261023*'))
    for entry in load(PLAN / 'public-inputs.json')['copied_or_verified']:
        for name in ['source', 'path']:
            path = resolved(entry[name].removeprefix('work/'))
            if digest(path) != entry['sha256'] or path.stat().st_size != entry['bytes']:
                raise IntegrityError('Pristine public file differs')
            files.append(path)
    return {relative(p): digest(p) for p in files}


def path_audit():
    # Enumerate known deepest public-worker paths; reserve random fixture names.
    examples = [OUTPUT / 'c43m/cut-43/tpe/trial-07/component-1/validation_probabilities.npz',
                OUTPUT / 'c43m/cut-43/outer-control/component-1/validation_predictions.csv',
                OUTPUT / 'g/s/test_hpo_qualification.py.log',
                WORK / 't/ck-xxxxxxxx/tmpxxxxxxxx/automl_runs/multi-target-xxxxxxxxxxxxxxxx/target-1-second/automl_runs/run-xxxxxxxxxxxxxxxx/trial-000/validation_predictions.csv']
    rows = [{'path': relative(p), 'absolute_characters': len(str(p.resolve()))} for p in examples]
    maximum = max(r['absolute_characters'] for r in rows)
    if os.name == 'nt' and maximum >= 260:
        raise IntegrityError('Known Windows artifact/fixture path can reach MAX_PATH; choose a shorter task work root')
    return {'short_output_alias': 'test-runs/hb1 -> test-runs/h31', 'work_root_characters': len(str(WORK)),
            'examples': rows, 'maximum_known_absolute_characters': maximum,
            'windows_limit_checked': 260, 'coverage': 'Known nested HPO/component and conservative shallow-fixture paths; not a proof for arbitrary future files'}


def prepare():
    if BUNDLE.exists():
        raise FileExistsError('Preserve the existing preparation; make an explicit new revision')
    plan, protocol = load(PLAN / 'coordinator-plan.json'), load(PROTOCOL)
    if plan['budget']['new_common_seconds'] != TOTAL_SECONDS or sum(j['cap_seconds'] for j in plan['jobs']) != 45420:
        raise IntegrityError('Predeclared campaign budget differs')
    if digest(PROTOCOL) != plan['reviewed_protocol_sha256']:
        raise IntegrityError('Reviewed protocol differs')
    packet_path = WORK / 'iteration3-review-packet/manifest.json'
    if digest(packet_path) != plan['review_packet_manifest_sha256']:
        raise IntegrityError('Review packet manifest differs')
    packet = load(packet_path)
    for item in packet['files']:
        if digest(DEV / item['path']) != item['sha256']:
            raise IntegrityError('Reviewed source3 bytes differ: ' + item['path'])
    for name, expected in protocol['qualification']['expected_harness_sha256'].items():
        if digest(DEV / name) != expected:
            raise IntegrityError('Qualification harness differs')
    registry_tree = ast.parse((DEV / 'tools/run_checks.py').read_text(encoding='utf-8'))
    registry = next(ast.literal_eval(n.value) for n in registry_tree.body
                    if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'CHECKS' for t in n.targets))
    if sum(registry.values()) != 472 or len(registry) != 48:
        raise IntegrityError('Expected source472/48 registry differs')
    builder = module('_hpo_preparation_builder', DEV / 'tools/build_submission.py')
    compiled = builder.build_files()  # AST compilation only; no runtime imports/fits.
    compiled_sha = {name: hashlib.sha256(content).hexdigest() for name, content in compiled.items()}
    if compiled_sha != protocol['qualification']['expected_source_sha256']:
        raise IntegrityError('Compiled source differs from qualification protocol')
    frozen = source_files()
    BUNDLE.mkdir()
    archive = BUNDLE / 'evaluator-source.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as packed:
        for name, content in sorted(compiled.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            packed.writestr(info, content)
    frozen[relative(archive)] = digest(archive)
    # Output alias changes only receipt locations, never cut/control/order/budgets.
    jobs = json.loads(json.dumps(plan['jobs']).replace('test-runs/hb1', 'test-runs/h31'))
    manifest = {'status': 'prepared_not_launched', 'plan': relative(PLAN / 'coordinator-plan.json'),
        'protocol': relative(PROTOCOL), 'output': relative(OUTPUT), 'jobs': jobs, 'pairs': plan['pairs'],
        'path_audit': path_audit(),
        'coordinator_sha256': digest(__file__), 'immutable_files': frozen,
        'python_inventory': python_inventory(), 'compiled_sha256': compiled_sha,
        'archive': relative(archive), 'archive_sha256': digest(archive),
        'limits': {'common_seconds': TOTAL_SECONDS, 'job_caps_sum_seconds': 45420,
                   'invocation_external_seconds': 4200, 'invocation_process_seconds': 4080,
                   'invocation_verification_reserve_seconds': MODEL_AUDIT_RESERVE,
                   'final_verification_reserve_seconds': FINAL_RESERVE,
                   'additional_common_reserve_seconds': FINAL_RESERVE,
                   'minimum_initial_remaining_seconds': 45420 + FINAL_RESERVE + 5,
                   'supervisor_tree_memory_gib': 2, 'worker_memory_gib': 1.5,
                   'worker_seconds': 600, 'worker_threads': 2, 'study_initial_seconds': 900},
        'lock': 'alfa-hack-automl/test-runs/.owned-research.lock',
        'predecessors': ['alfa-hack-automl/test-runs/2e/queue.json', 'alfa-hack-automl/test-runs/sc1/coordinator.json'],
        'mandatory_sc1_completion_ownership': 'sc1-completion-ownership.json',
        'sc1_completion_contract': 'After SC1, root saves status=completed,cleanup_confirmed=true,active_owned_processes=[],launcher_identities and tracked_identities including launcher+owned worker roots,component_receipt_sha256. This file is not assigned/created during preparation.',
        'launch_started_unix': None, 'absolute_deadline_unix': None,
        'gates': {'source': 'pending472unique0skips', 'exact_unpacked': 'pending'},
        'tests_run': 0, 'model_fits': 0, 'api_calls': 0, 'child_processes': 0,
        'promotion': False, 'root_review_required_before_launch': True,
        'audit_limit': 'Prediction metrics are recomputed. Admission is a chronological saved-evidence replay; no independent physical witness for every internal trial clock.'}
    write(BUNDLE / 'manifest.json', manifest, exclusive=True)
    print(json.dumps({'status': manifest['status'], 'manifest_sha256': digest(BUNDLE / 'manifest.json'),
                      'archive_sha256': manifest['archive_sha256'], 'deadline_assigned': False, 'child_processes': 0}))


def guard(bundle):
    if digest(__file__) != bundle['coordinator_sha256'] or python_inventory() != bundle['python_inventory']:
        raise IntegrityError('Executing helper or source inventory changed')
    for name, expected in bundle['immutable_files'].items():
        if digest(resolved(name)) != expected:
            raise IntegrityError('Frozen source/input/harness changed: ' + name)


def process_identity(value):
    if (type(value.get('pid')) is not int or value['pid'] <= 0 or
            not finite(value.get('create_time')) or value['create_time'] <= 0):
        raise IntegrityError('Invalid owned process identity')
    return value['pid'], float(value['create_time'])


def predecessor_check(bundle):
    import psutil
    roots, receipts = set(), []
    completed_2e = load(WORK / 'native2e-completion-ownership.json')
    if completed_2e.get('cleanup_confirmed') is not True or completed_2e.get('active_owned_processes') != []:
        raise IntegrityError('2e terminal ownership proof is incomplete')
    roots.update(process_identity(v) for v in completed_2e['tracked_identities'])
    sc1_path = resolved(bundle['mandatory_sc1_completion_ownership'])
    sc1 = load(sc1_path)
    if (sc1.get('status') != 'completed' or sc1.get('cleanup_confirmed') is not True or
            sc1.get('active_owned_processes') != [] or not sc1.get('launcher_identities')):
        raise IntegrityError('Mandatory SC1 launcher completion/ownership proof is incomplete')
    sc1_tracked = {process_identity(v) for v in sc1['tracked_identities']}
    if not {process_identity(v) for v in sc1['launcher_identities']} <= sc1_tracked:
        raise IntegrityError('SC1 launcher identities absent from completion tracking')
    roots.update(sc1_tracked)
    receipts.append({'path': relative(sc1_path), 'sha256': digest(sc1_path), 'status': 'completed'})
    for name in bundle['predecessors']:
        path = resolved(name)
        if not path.exists():
            raise IntegrityError('Predecessor receipt missing')
        report = load(path)
        is_2e = '/2e/' in name
        terminal = (report.get('status', '').startswith(('completed', 'budget_exhausted')) if is_2e else
                    report.get('status') in {'complete_verified_component_screen', 'incomplete_component_screen',
                        'supervisor_stopped_with_saved_artifacts', 'verification_failed'})
        if not terminal or report.get('cleanup_confirmed') is not True:
            raise IntegrityError('Predecessor is active or cleanup is unconfirmed')
        if is_2e and report.get('source_unchanged') is not True:
            raise IntegrityError('Predecessor source integrity is unconfirmed')
        if not is_2e:
            if digest(path) != sc1['component_receipt_sha256'] or process_identity(report['owned_root']) not in sc1_tracked:
                raise IntegrityError('SC1 completion does not bind the actual terminal component/worker')
        pending = [report, *report.get('jobs', [])]
        for item in pending:
            if item.get('owned_root'):
                roots.add(process_identity(item['owned_root']))
            for key in ['owned_process_identities', 'owned_identities', 'predecessor_tracked']:
                roots.update(process_identity(v) for v in item.get(key, []))
        for v in report.get('predecessor_terminal_proof', {}).get('tracked', []):
            roots.add(process_identity(v))
        receipts.append({'path': name, 'sha256': digest(path), 'status': report['status'],
                         'original_deadline_unix': report.get('deadline_unix', report.get('common_deadline_unix'))})
    live = set()
    for identity in list(roots):
        try:
            p = psutil.Process(identity[0])
            if p.create_time() != identity[1]:
                continue
            if p.status() not in {psutil.STATUS_DEAD, psutil.STATUS_ZOMBIE}:
                live.add(identity)
                for child in p.children(recursive=True):
                    roots.add((child.pid, child.create_time()))
                    live.add((child.pid, child.create_time()))
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            raise IntegrityError('Predecessor identity/descendants unverifiable') from None
    # Read-only orphan discovery. A reused parent PID never establishes ownership.
    processes = list(psutil.process_iter(['pid', 'ppid', 'create_time', 'status']))
    changed = True
    while changed:
        changed = False
        for p in processes:
            info = p.info
            if info['create_time'] is None or info['status'] in {psutil.STATUS_DEAD, psutil.STATUS_ZOMBIE}:
                continue
            key = info['pid'], info['create_time']
            if key in roots:
                continue
            for pid, created in tuple(roots):
                if info['ppid'] != pid or info['create_time'] < created:
                    continue
                try:
                    parent = psutil.Process(pid)
                    actual = parent.create_time()
                    if actual != created and info['create_time'] >= actual:
                        continue
                except psutil.NoSuchProcess:
                    pass
                except psutil.AccessDenied:
                    raise IntegrityError('Orphan ancestry unverifiable') from None
                roots.add(key)
                live.add(key)
                changed = True
                break
    if live:
        raise IntegrityError('An owned predecessor or descendant remains active')
    return {'receipts': receipts, 'tracked_identities': [{'pid': p, 'create_time': c} for p, c in sorted(roots)],
            'active': [], 'no_predecessor_was_signalled': True}


def clean_environment(threads):
    env = {k: v for k, v in os.environ.items() if not any(s in k.upper() for s in
        ['KEY', 'TOKEN', 'SECRET', 'PROXY', 'PASSWORD', 'AUTH']) and not k.upper().startswith(('OPENAI_', 'DASHSCOPE_'))}
    env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1', AUTOML_THREADS=str(threads))
    for key in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
        env[key] = str(threads)
    return env


def clock_guard(deadline, utc_deadline):
    if abs((deadline - time.monotonic()) - (utc_deadline - time.time())) > 5:
        raise IntegrityError('UTC and monotonic common clocks differ by more than5seconds')
    if time.monotonic() >= deadline:
        raise TimeoutError('Common campaign deadline reached')


def strict_refresh(tree, child, identities):
    """Fresh verified identity/descendants only; never trust cached PID objects."""
    import psutil
    for key in list(tree.members):
        if key[0] == child.pid and child.poll() is not None:
            continue
        try:
            current = psutil.Process(key[0])
            if current.create_time() != key[1]:
                tree.members.pop(key, None)
                continue
            for descendant in current.children(recursive=True):
                try:
                    fresh = psutil.Process(descendant.pid)
                    if fresh.create_time() == descendant.create_time():
                        tree.members[(fresh.pid, fresh.create_time())] = fresh
                except psutil.NoSuchProcess:
                    continue
        except psutil.NoSuchProcess:
            tree.members.pop(key, None)
        except psutil.AccessDenied:
            failure = IntegrityError('Owned descendant identity or traversal denied')
            failure.denial = {'pid': key[0], 'create_time': key[1], 'action': 'strict_identity_or_descendant_traversal'}
            raise failure from None
    identities.update(tree.members)


def confirm_gone(child, identities):
    import psutil
    if child.poll() is None:
        raise IntegrityError('Owned root handle is still running after cleanup')
    for pid, created in identities:
        if pid == child.pid:
            continue  # Exited Popen handle is authoritative; never address a reused root PID.
        try:
            current = psutil.Process(pid)
            if current.create_time() != created:
                continue
            if current.is_running() and current.status() not in {psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD}:
                raise IntegrityError('A fresh verified owned descendant survives cleanup')
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied:
            raise IntegrityError('Fresh owned-descendant cleanup proof denied') from None


def owned_job(job, bundle, deadline, utc_deadline):
    import psutil
    processes = module('_hpo_canonical_processes', CANON / 'src/automl/infrastructure/processes.py')
    tick, utc = time.monotonic(), time.time()
    cap = min(job['cap_seconds'], deadline - tick - FINAL_RESERVE)
    if cap < job['cap_seconds'] - .01:
        raise TimeoutError('A full declared job cap cannot fit; no clipped launch')
    model = job['kind'] == 'paired_hpo_benchmark'
    process_deadline = tick + cap - (MODEL_AUDIT_RESERVE if model else 5)
    command = [sys.executable, *job['argv'][1:]]
    report = {'name': job['name'], 'kind': job['kind'], 'start_monotonic': tick, 'start_unix': utc,
              'declared_cap_seconds': job['cap_seconds'], 'allocated_cap_seconds': cap,
              'cleanup_confirmed': False, 'status': 'starting', 'metrics': None}
    child, tree, tracker_verified = None, None, False
    identities, denied, last_guard, last_heartbeat = set(), False, tick, tick
    report['ownership_denials'] = []
    def absorb_tree():
        nonlocal denied
        if tree is None:
            return
        for key in [*tree.members, *getattr(tree, '_pending_cleanup', {})]:
            if finite(key[1]):
                identities.add(key)
        for entry in getattr(tree, 'cleanup_errors', []):
            if entry not in report['ownership_denials']:
                report['ownership_denials'].append(entry)
        denied = denied or bool(report['ownership_denials'])
    def remember_denial(exc):
        nonlocal denied
        denied = True
        entry = getattr(exc, 'denial', {'action': 'strict_observation_unverifiable'})
        if entry not in report['ownership_denials']:
            report['ownership_denials'].append(entry)
    receipt_path = OUTPUT / (job['name'] + '.supervisor.json')
    write(receipt_path, report, exclusive=True)
    try:
        clock_guard(deadline, utc_deadline)
        with (OUTPUT / (job['name'] + '.log')).open('x', encoding='utf-8') as log:
            child = subprocess.Popen(command, cwd=DEV, env=clean_environment(2 if model else 1),
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            root = psutil.Process(child.pid)
            root_key = root.pid, root.create_time()
            identities.add(root_key)
            report['owned_root'] = {'pid': root_key[0], 'create_time': root_key[1]}
            report['status'] = 'running'
            report['owned_process_identities'] = [{'pid': root_key[0], 'create_time': root_key[1]}]
            write(receipt_path, report)
            tree = processes.ProcessTree(child)
            absorb_tree()
            if root_key not in tree.members:
                raise IntegrityError('Tracker did not observe exact owned root identity')
            tracker_verified = True
            while child.poll() is None:
                try:
                    strict_refresh(tree, child, identities)
                except IntegrityError as exc:
                    remember_denial(exc)
                    raise
                absorb_tree()
                if denied:
                    raise IntegrityError('Persistent process tracker denial observed')
                rss = psutil.Process().memory_info().rss
                for key in list(tree.members):
                    try:
                        fresh = psutil.Process(key[0])
                        if fresh.create_time() == key[1]:
                            rss += fresh.memory_info().rss
                    except psutil.NoSuchProcess:
                        pass
                    except psutil.AccessDenied:
                        denied = True
                        report['ownership_denials'].append({'pid': key[0], 'create_time': key[1], 'action': 'memory_observation'})
                        raise IntegrityError('Owned memory observation denied') from None
                if rss > MEMORY_BYTES:
                    raise MemoryError('Supervisor whole-tree2GiB allowance exceeded')
                clock_guard(deadline, utc_deadline)
                if time.monotonic() >= process_deadline:
                    raise TimeoutError('Declared process allocation exhausted; verification reserve retained')
                if time.monotonic() - last_guard >= 30:
                    guard(bundle)
                    last_guard = time.monotonic()
                if time.monotonic() - last_heartbeat >= 2:
                    report.update(heartbeat_monotonic=time.monotonic(), heartbeat_unix=time.time(),
                        owned_process_identities=[{'pid': p, 'create_time': c} for p, c in sorted(identities)])
                    write(receipt_path, report)
                    last_heartbeat = time.monotonic()
                time.sleep(.1)
            report.update(status='ok' if child.returncode == 0 else 'failed', exit_code=child.returncode)
    except (MemoryError, TimeoutError) as exc:
        report.update(status=type(exc).__name__, exception_type=type(exc).__name__)
    except BaseException as exc:
        report.update(status='stopped', exception_type=type(exc).__name__)
        raise
    finally:
        try:
            cleanup_exception = None
            if child is not None and not tracker_verified:
                # Preserve this uncertainty even if a retry can observe the root.
                # Known descendants still receive a best-effort owned cleanup.
                denied = True
                report['ownership_denials'].append({'pid': child.pid,
                    'create_time': report.get('owned_root', {}).get('create_time'),
                    'action': 'initial_tracking_unverified'})
                try:
                    if tree is None:
                        tree = processes.ProcessTree(child)
                    absorb_tree()
                    root = report.get('owned_root', {})
                    if (root.get('pid'), root.get('create_time')) not in tree.members:
                        raise IntegrityError('Retry did not observe exact root')
                except BaseException as exc:
                    report['cleanup_tracker_retry_exception_type'] = type(exc).__name__
            if tree is not None:
                try:
                    strict_refresh(tree, child, identities)
                except IntegrityError as exc:
                    remember_denial(exc)
                absorb_tree()
                try:
                    tree.terminate()
                except BaseException as exc:
                    cleanup_exception = exc
                    report['tree_cleanup_exception_type'] = type(exc).__name__
                finally:
                    # terminate may discover new members and/or record a denial;
                    # its final wait return is never sufficient cleanup proof.
                    absorb_tree()
                try:
                    strict_refresh(tree, child, identities)
                except IntegrityError as exc:
                    remember_denial(exc)
                absorb_tree()
            if child is not None:
                # Even a tracker failure must attempt the exact owned root
                # handle; an exited/reused root PID is never signalled.
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=3)
                confirm_gone(child, identities)
            if cleanup_exception is not None:
                raise IntegrityError('Owned tree cleanup raised; fresh identities retained') from None
            if denied:
                raise IntegrityError('Ownership uncertainty or AccessDenied; cleanup remains unconfirmed')
            report['cleanup_confirmed'] = True
            if child is not None:
                report['exit_code'] = child.poll()
        finally:
            report.update(end_monotonic=time.monotonic(), end_unix=time.time(),
                elapsed_seconds=time.monotonic() - tick,
                owned_process_identities=[{'pid': p, 'create_time': c} for p, c in sorted(identities)])
            write(receipt_path, report)
    log = (OUTPUT / (job['name'] + '.log')).read_text(encoding='utf-8', errors='replace')
    if 'ProcessCleanupError' in log or 'cleanup_unconfirmed' in log:
        raise IntegrityError('Child reported an owned cleanup failure')
    guard(bundle)
    clock_guard(deadline, utc_deadline)
    return report, tick + cap


def admission_audit(study, policy):
    entries, decisions = study['trials'], study['admission_decisions']
    if [r['number'] for r in entries] != list(range(len(entries))):
        raise IntegrityError('Nonchronological trial sequence')
    durations = []
    for trial in entries:
        if trial.get('objective_valid'):
            if trial.get('status') != 'ok' or not finite(trial.get('value')):
                raise IntegrityError('Invalid successful trial')
        elif trial.get('value') is not None:
            raise IntegrityError('Failed trial has a numeric objective')
    for index, decision in enumerate(decisions):
        if decision['next_trial'] != index:
            raise IntegrityError('Nonchronological admission decision')
        past = [r for r in entries if r['number'] < index]
        durations = [r['admission_observed_worker_seconds'] for r in past if r.get('objective_valid')
                     and finite(r.get('admission_observed_worker_seconds')) and r['admission_observed_worker_seconds'] > 0]
        remaining = decision.get('remaining_seconds')
        if not finite(remaining):
            raise IntegrityError('Nonfinite saved admission clock')
        if remaining < 5:
            if decision.get('admitted') is not False or decision.get('reason') != 'legacy_minimum_remaining':
                raise IntegrityError('Minimum-remaining refusal differs')
            continue
        expected = (1.5 * median(durations) if durations else 600.) if policy == 'measured' and index else None
        actual = decision.get('estimated_seconds')
        if actual != expected or decision.get('past_successful_duration_count') != (len(durations) if policy == 'measured' else 0):
            raise IntegrityError('Admission estimate used a different observation prefix')
        enough = expected is None or remaining >= expected
        if decision.get('sampled_but_not_started'):
            launch_remaining = decision.get('pre_worker_remaining_seconds')
            if (not finite(launch_remaining) or launch_remaining >= 5 and
                    (expected is None or launch_remaining >= expected)):
                raise IntegrityError('Unjustified sampled-but-unstarted refusal')
            if any(r['number'] == index for r in entries):
                raise IntegrityError('Unstarted sampled work counted as a trial')
        elif decision.get('admitted') is not enough:
            raise IntegrityError('Admission outcome differs from saved remaining/estimate')
        if policy == 'measured' and decision.get('admitted') and any(r['number'] == index and r.get('status') != 'duplicate' for r in entries):
            launch_remaining = decision.get('pre_worker_remaining_seconds')
            if not finite(launch_remaining) or launch_remaining < 5 or expected is not None and launch_remaining < expected:
                raise IntegrityError('Worker launched below admission estimate')
    observed = [r['admission_observed_worker_seconds'] for r in entries if r.get('objective_valid')
                and finite(r.get('admission_observed_worker_seconds')) and r['admission_observed_worker_seconds'] > 0]
    if policy == 'measured' and study['successful_worker_durations'] != observed:
        raise IntegrityError('Final successful-duration ledger differs')
    if len(decisions) < len(entries) or len(decisions) > len(entries) + 1:
        raise IntegrityError('Admission/trial accounting differs')
    completed = 0
    for trial in entries:
        phase = 'anchor' if trial['number'] == 0 else 'random' if study['sampler'] == 'random' else 'startup' if completed < study['startup_trials'] else 'guided'
        if trial['sampling_phase'] != phase or trial['completed_before_sampling'] != completed:
            raise IntegrityError('Startup/guided sampling chronology differs')
        completed += bool(trial.get('objective_valid'))
    return {'decisions': len(decisions), 'trials': len(entries), 'saved_prefix_consistent': True,
            'independent_physical_internal_clock_witness': False}


def audit_benchmark(job, bundle, limit, supervisor):
    import numpy as np
    import pandas as pd
    def check():
        if time.monotonic() >= limit:
            raise TimeoutError('Reserved independent verification allocation exhausted')
    folder = OUTPUT / job['name']
    path = folder / 'results.json'
    if not path.exists():
        return {'status': 'missing_benchmark_receipt', 'metrics': None, 'valid': False}
    report, protocol = load(path), load(PROTOCOL)
    if report['source_sha256'] != bundle['compiled_sha256']:
        raise IntegrityError('Actual benchmark source differs')
    integrity_complete = all(report.get(key) is True for key in ['source_unchanged', 'inputs_unchanged', 'task_unchanged', 'harness_unchanged'])
    if not integrity_complete:
        explicit_failure = any(report.get(key) is False for key in ['source_unchanged', 'inputs_unchanged', 'task_unchanged', 'harness_unchanged'])
        if not explicit_failure and report.get('status') != 'completed' and supervisor['status'] != 'ok':
            # The independent frozen-file guard is still required. An ordinary
            # interrupted lifecycle is never a certificate or numeric result,
            # but it must not erase the remaining predeclared policy arms.
            guard(bundle)
            return {'status': 'unfinalized_interrupted_benchmark', 'valid': False, 'metrics': None,
                    'saved_integrity_certified': False, 'current_frozen_files_verified': True,
                    'external_stop': supervisor['status'], 'failed_metric_substitution': False, 'promotion': False}
        raise IntegrityError('Completed benchmark integrity fields missing or not true')
    limits = report['limits']
    for name, expected in [('mode', 'hpo'), ('admission', job['admission']), ('trials', 8),
            ('study_seconds', 900), ('worker_seconds', 600), ('memory_mb', 1536), ('worker_threads', 2), ('time_budget', 4000)]:
        actual = report.get(name) if name == 'mode' else limits.get(name)
        if actual != expected or isinstance(actual, bool):
            raise IntegrityError('Actual benchmark invocation protocol differs: ' + name)
    if limits.get('cuts') != [job['cut']]:
        raise IntegrityError('Actual invocation cuts differ')
    from automl.task_understanding.api import discover
    from automl.evaluation.api import choose_validation, make_split, make_time_split
    import automl.infrastructure.llm_gateway as gateway
    import automl.task_understanding.semantic_inputs as semantic
    def no_api(*args, **kwargs):
        raise IntegrityError('API access forbidden in independent HPO audit')
    gateway.request_json = semantic.request_json = no_api
    task = DEV / protocol['controls'][job['task']]['task_path_from_dev']
    spec, _, train, test, sample, _, hashes = discover(task)
    spec = choose_validation(spec, train, 'auto')
    if report['spec'] != spec or spec['target'] in spec['features'] or spec.get('id') in spec['features']:
        raise IntegrityError('Pristine task contract differs')
    tr, va, info = (make_time_split(spec, train, offset=job['cut']) if spec.get('validation_strategy') == 'time'
                    else make_split(spec, train, hashes, seed=job['cut']))
    metric = 'rmse' if job['task'] == 'regression' else 'macro_f1'
    records, admissions = [], []
    saved_sequential_seconds = 0.
    def rows_from(path):
        with np.load(path, allow_pickle=False) as saved:
            a, b = saved['train'], saved['validation']
        for rows in [a, b]:
            if rows.ndim != 1 or not len(rows) or not np.issubdtype(rows.dtype, np.integer) or len(np.unique(rows)) != len(rows) or rows.min() < 0 or rows.max() >= len(train):
                raise IntegrityError('Invalid saved partition')
        if np.intersect1d(a, b).size:
            raise IntegrityError('Saved partition overlap')
        return a, b
    def verify(directory, expected_rows, result, recipe, split):
        check()
        saved_job, saved_result = load(directory / 'job.json'), load(directory / 'result.json')
        if (saved_job['spec'] != spec or saved_job['recipe'] != recipe or saved_result['recipe'] != recipe or
                saved_job['threads'] != 2 or saved_job['full_fit'] is not False or saved_result['full_fit'] is not False or
                saved_result['status'] != 'ok' or Path(saved_job['split_path']).resolve() != split.resolve() or
                Path(saved_job['output_dir']).resolve() != directory.resolve()):
            raise IntegrityError('Saved worker job/result differs')
        frame = pd.read_csv(directory / 'validation_predictions.csv')
        if not np.array_equal(frame.row_position.to_numpy(), expected_rows):
            raise IntegrityError('Prediction rows differ from saved fitting scope')
        truth = train[spec['target']].iloc[expected_rows].to_numpy()
        if metric == 'rmse':
            truth, predicted = truth.astype(float), frame.y_pred.to_numpy(dtype=float)
            if not np.isfinite(predicted).all() or not np.allclose(frame.y_true.to_numpy(dtype=float), truth, rtol=0, atol=1e-12):
                raise IntegrityError('Pristine regression truth/prediction differs')
            value = float(np.sqrt(np.mean((truth - predicted)**2)))
            per_class = None
        else:
            classes = list(spec['classes'])
            truth = truth.astype(str)
            with np.load(directory / 'validation_probabilities.npz', allow_pickle=False) as saved:
                order = list(saved['classes'].astype(str))
                if len(order) != len(classes) or set(order) != set(classes) or not np.array_equal(saved['row_position'], expected_rows):
                    raise IntegrityError('Validation probability inventory/rows differ')
                probabilities = saved['probabilities'][:, [order.index(c) for c in classes]]
            if (probabilities.shape != (len(expected_rows), len(classes)) or not np.isfinite(probabilities).all() or
                    (probabilities < 0).any() or (probabilities > 1).any() or not np.allclose(probabilities.sum(axis=1), 1., atol=1e-6)):
                raise IntegrityError('Invalid validation probabilities')
            predicted = np.asarray(classes)[probabilities.argmax(axis=1)]
            if not np.array_equal(frame.y_true.astype(str), truth) or not np.array_equal(frame.y_pred.astype(str), predicted):
                raise IntegrityError('Pristine class truth/prediction differs')
            per_class = {}
            for label in classes:
                actual, guess = truth == label, predicted == label
                denominator = int(actual.sum() + guess.sum())
                per_class[label] = float(2 * np.sum(actual & guess) / denominator) if denominator else 0.
            value = float(np.mean(list(per_class.values())))
        for values in [result.get('metrics'), saved_result.get('metrics')]:
            reported = (values or {}).get(metric)
            if not finite(reported) or not math.isclose(value, reported, rel_tol=1e-10, abs_tol=1e-10):
                raise IntegrityError('Primary metric does not independently reproduce')
        submission = pd.read_csv(directory / 'submission.csv')
        if list(submission) != list(sample) or len(submission) != len(sample) or submission.isna().any().any():
            raise IntegrityError('Submission schema/rows/nonmissing contract differs')
        if spec.get('id') is not None and not submission[spec['id']].equals(sample[spec['id']]):
            raise IntegrityError('Submission sample IDs/order differ')
        if metric == 'rmse':
            if not np.isfinite(submission[spec['output_columns'][0]].to_numpy(dtype=float)).all():
                raise IntegrityError('Nonfinite regression test prediction')
        else:
            with np.load(directory / 'test_probabilities.npz', allow_pickle=False) as saved:
                order = list(saved['classes'].astype(str))
                if len(order) != len(classes) or set(order) != set(classes):
                    raise IntegrityError('Test class inventory differs')
                probabilities = saved['probabilities'][:, [order.index(c) for c in classes]]
            if (probabilities.shape != (len(test), len(classes)) or not np.isfinite(probabilities).all() or
                    (probabilities < 0).any() or (probabilities > 1).any() or not np.allclose(probabilities.sum(axis=1), 1., atol=1e-6)):
                raise IntegrityError('Invalid test probabilities')
            positions = np.asarray(spec.get('sample_test_positions', np.arange(len(test))))
            prediction = np.asarray(classes)[probabilities.argmax(axis=1)][positions]
            if not np.array_equal(submission[spec['output_columns'][0]].astype(str), prediction):
                raise IntegrityError('Submission and probability order differ')
        check()
        return {'directory': relative(directory), 'status': 'verified_ok', 'metrics': {metric: value},
                'per_class_f1': per_class, 'validation_predictions_sha256': digest(directory / 'validation_predictions.csv')}
    for row in report['cuts']:
        check()
        if row['cut'] != job['cut']:
            raise IntegrityError('Unexpected actual outer cut')
        cut_dir = folder / ('cut-' + str(row['cut']))
        a, b = rows_from(cut_dir / 'outer-split.npz')
        if not np.array_equal(a, tr) or not np.array_equal(b, va) or row['split'] != info:
            raise IntegrityError('Outer split differs from independent pristine reconstruction')
        for sampler in ['random', 'tpe']:
            if sampler not in row:
                continue
            study = row[sampler]
            if not finite(study.get('seconds')) or study['seconds'] < 0:
                raise IntegrityError('Invalid saved study duration')
            saved_sequential_seconds += study['seconds']
            allocation = row['study_allocations'][sampler]
            if (allocation.get('requested_seconds') != 900 or not finite(allocation.get('allocated_seconds')) or
                    not math.isclose(allocation['allocated_seconds'], 900., abs_tol=1e-6, rel_tol=0) or
                    allocation.get('clipped_by_common_deadline') is not False):
                raise IntegrityError('Study did not receive its full initial900-second allocation')
            if (study.get('sampler') != sampler or study.get('admission_policy') != job['admission'] or
                    study.get('seed') != 137 or study.get('startup_trials') != 3 or study.get('maximum_trials') != 8):
                raise IntegrityError('Actual study protocol differs')
            admissions.append({'sampler': sampler, **admission_audit(study, job['admission'])})
            inner_tr, inner_va = rows_from(cut_dir / sampler / 'split.npz')
            local_tr, local_va, _ = make_split(spec, train.iloc[tr].reset_index(drop=True), hashes[tr], seed=137)
            if not np.array_equal(inner_tr, tr[local_tr]) or not np.array_equal(inner_va, tr[local_va]):
                raise IntegrityError('Inner split differs from independent pristine reconstruction')
            if not (set(inner_tr) | set(inner_va)) <= set(tr):
                raise IntegrityError('Inner partition escaped fitting rows')
            if spec['kind'] == 'classification' and np.intersect1d(hashes[inner_tr], hashes[inner_va]).size:
                raise IntegrityError('Inner feature-group leakage')
            for trial in study['trials']:
                if trial.get('objective_valid'):
                    directory = cut_dir / sampler / ('trial-' + str(trial['number']).zfill(2))
                    result = load(directory / 'result.json')
                    record = verify(directory, inner_va, result, trial['recipe'], cut_dir / sampler / 'split.npz')
                    if not math.isclose(record['metrics'][metric], trial['value'], rel_tol=1e-10, abs_tol=1e-10):
                        raise IntegrityError('Trial objective differs from independent metric')
                    records.append(record)
                else:
                    records.append({'directory': relative(cut_dir / sampler / ('trial-' + str(trial['number']).zfill(2))), 'status': trial['status'], 'metrics': None})
        for name, result in row['outcomes'].items():
            if not finite(result.get('wall_seconds')) or result['wall_seconds'] < 0:
                raise IntegrityError('Invalid saved outer duration')
            saved_sequential_seconds += result['wall_seconds']
            if result.get('status') == 'ok':
                records.append(verify(cut_dir / ('outer-' + name), va, result, result['recipe'], cut_dir / 'outer-split.npz'))
            else:
                records.append({'directory': relative(cut_dir / ('outer-' + name)), 'status': result.get('status'), 'metrics': None})
    complete = report['status'] == 'completed' and len(report['cuts']) == 1 and set(report['cuts'][0]['outcomes']) == {'control', 'random', 'tpe'}
    complete = complete and all(r.get('status') == 'ok' for r in report['cuts'][0]['outcomes'].values())
    if (not finite(report.get('seconds')) or saved_sequential_seconds > report['seconds'] + .1 or
            report['seconds'] > supervisor['elapsed_seconds'] + .1):
        raise IntegrityError('Saved sequential study/outer durations exceed their enclosing external clock')
    check()
    return {'status': 'verified_saved_metrics' if complete else 'incomplete_saved_artifacts', 'valid': complete,
        'records': records, 'admission_prefix_replays': admissions, 'report_sha256': digest(path),
        'saved_sequential_seconds': saved_sequential_seconds, 'externally_observed_process_seconds': supervisor['elapsed_seconds'],
        'failed_metric_substitution': False, 'promotion': False,
        'limitations': ['Admission replays saved durations; no physical internal-clock witness.',
                        'Public component evidence only; no whole-agent/private/official-score qualification.']}


def gate_result(job, bundle, supervisor):
    if supervisor['status'] != 'ok':
        raise IntegrityError('Technical gate process failed: ' + job['name'])
    if job['name'] == 'freeze':
        if digest(OUTPUT / 'runtime.zip') != bundle['archive_sha256']:
            raise IntegrityError('Actual frozen archive differs from prepared bytes')
    elif job['name'] == 'source472':
        result = load(OUTPUT / 'g/s/results.json')
        if (result.get('passed') is not True or result.get('unique_checks_passed') != 472 or
                result.get('unique_checks_skipped') != 0 or result.get('source_unchanged') is not True or
                result.get('fixture_cleanup_confirmed') is not True or result['source_sha256'] != bundle['compiled_sha256']):
            raise IntegrityError('Source472/no-skips/exact-source/cleanup gate failed')
    elif job['name'] == 'unpacked':
        result = load(OUTPUT / 'g/u.json')
        if result.get('passed') is not True or result.get('matches_current_source') is not True or result['sha256'] != bundle['archive_sha256']:
            raise IntegrityError('Exact-unpacked archive gate failed')


def scoped_awake(enable):
    if os.name != 'nt':
        return None
    try:
        import ctypes
        return bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | (0x1 if enable else 0)))
    except Exception:
        return False


def launch(args):
    import psutil
    path = BUNDLE / 'manifest.json'
    if not args.manifest_sha256 or digest(path) != args.manifest_sha256:
        raise ValueError('Explicit root-reviewed manifest SHA required')
    started, utc = time.monotonic(), time.time()
    remaining = args.deadline_unix - utc if finite(args.deadline_unix) else None
    if remaining is None or not 45420 + FINAL_RESERVE + 5 <= remaining <= TOTAL_SECONDS:
        raise ValueError('Root must assign one future absolute deadline within13h leaving all full declared caps')
    deadline = started + remaining
    bundle = load(path)
    guard(bundle)
    path_audit()
    predecessor_check(bundle)
    locks = module('_hpo_canonical_lock', CANON / 'tools/research_lock.py')
    # One central lock for all source trees, never an isolated-tree local lock.
    with locks.ResearchLock(resolved(bundle['lock'])) as lock:
        lock.write_identity({'pid': os.getpid(), 'create_time': psutil.Process().create_time()})
        predecessors = predecessor_check(bundle)
        guard(bundle)
        if OUTPUT.exists():
            raise FileExistsError('Never overwrite or silently resume a previous campaign')
        OUTPUT.mkdir(parents=True)
        report = {'status': 'running', 'manifest_sha256': args.manifest_sha256,
            'coordinator_sha256': digest(__file__), 'launch_started_unix': utc, 'launch_started_monotonic': started,
            'absolute_deadline_unix': args.deadline_unix, 'common_deadline_monotonic': deadline,
            'initial_remaining_seconds': remaining, 'common_budget_seconds': TOTAL_SECONDS,
            'owned_root': {'pid': os.getpid(), 'create_time': psutil.Process().create_time()},
            'predecessor_terminal_proof': predecessors, 'jobs': [], 'cleanup_confirmed': False,
            'source_unchanged': False, 'promotion': False, 'new_api_calls': 0,
            'windows_awake_requested': scoped_awake(True), 'paired_protocol_modified': False}
        def save():
            write(OUTPUT / 'campaign.json', report)
        def interrupted(signum, frame):
            raise SystemExit(128 + signum)
        previous = {sig: signal.signal(sig, interrupted) for sig in [signal.SIGINT, signal.SIGTERM]}
        save()
        try:
            for index, job in enumerate(bundle['jobs']):
                guard(bundle)
                clock_guard(deadline, args.deadline_unix)
                required = sum(j['cap_seconds'] for j in bundle['jobs'][index:]) + FINAL_RESERVE
                if deadline - time.monotonic() < required:
                    report['status'] = 'budget_exhausted_before_full_pair_or_job'
                    break
                if job['kind'] == 'coordinator_read_only_summary':
                    report['clock_audit'] = {'all_sequential': all(a['end_monotonic'] <= b['start_monotonic'] for a, b in zip(report['jobs'], report['jobs'][1:])),
                        'all_jobs_within_declared_caps': all(j['elapsed_seconds'] <= j['declared_cap_seconds'] + 1 for j in report['jobs']),
                        'all_owned_cleanup_confirmed': all(j['cleanup_confirmed'] for j in report['jobs']),
                        'saved_internal_clock_witness_limit': 'No independent physical timestamp per inner worker; admission replay checks saved prefix consistency only'}
                    if not all(report['clock_audit'][k] for k in ['all_sequential', 'all_jobs_within_declared_caps', 'all_owned_cleanup_confirmed']):
                        raise IntegrityError('Independent external common-clock audit failed')
                    break
                report['current_job'] = job['name']
                save()
                supervisor, verification_deadline = owned_job(job, bundle, deadline, args.deadline_unix)
                report['jobs'].append(supervisor)
                save()
                if job['kind'] in {'technical_gate', 'static_preflight_and_archive'}:
                    gate_result(job, bundle, supervisor)
                elif job['kind'] == 'paired_hpo_benchmark':
                    supervisor['independent_audit'] = audit_benchmark(job, bundle, verification_deadline, supervisor)
                    write(OUTPUT / (job['name'] + '.audit.json'), supervisor['independent_audit'], exclusive=True)
                    supervisor['end_monotonic'], supervisor['end_unix'] = time.monotonic(), time.time()
                    supervisor['elapsed_seconds'] = supervisor['end_monotonic'] - supervisor['start_monotonic']
                    if supervisor['elapsed_seconds'] > job['cap_seconds']:
                        raise IntegrityError('Verification exceeded reserved invocation cap')
                elif job['kind'] == 'read_only_validity_gate':
                    name = 'q-regression.json' if job['name'].endswith('regression') else 'q-classification.json'
                    result = load(OUTPUT / name) if (OUTPUT / name).exists() else {'valid_equal_budget_screen': False, 'metrics': None}
                    supervisor['valid_equal_budget_screen'] = result.get('valid_equal_budget_screen') is True
                guard(bundle)
                save()
            else:
                raise IntegrityError('Missing declared final audit job')
            if report['status'] == 'running':
                model_jobs = [j for j in report['jobs'] if j['kind'] == 'paired_hpo_benchmark']
                qualifiers = [j for j in report['jobs'] if j['kind'] == 'read_only_validity_gate']
                valid = (len(model_jobs) == 10 and len(qualifiers) == 2 and
                         all(j.get('valid_equal_budget_screen') for j in qualifiers) and
                         all(j.get('status') == 'ok' and j.get('independent_audit', {}).get('valid') for j in model_jobs))
                report['status'] = 'completed_valid_component_screen' if valid else 'completed_invalid_or_incomplete_component_screen'
                report['valid_equal_budget_component_screen'] = valid
        except BaseException as exc:
            report.update(status='stopped', exception_type=type(exc).__name__, valid_equal_budget_component_screen=False)
            raise
        finally:
            try:
                report['cleanup_confirmed'] = all(j.get('cleanup_confirmed') is True for j in report['jobs'])
                # A job may have failed before returning; retain its truthful supervisor receipt.
                for receipt in OUTPUT.glob('*.supervisor.json'):
                    if load(receipt).get('cleanup_confirmed') is not True:
                        report['cleanup_confirmed'] = False
                guard(bundle)
                report['source_unchanged'] = True
            except BaseException as exc:
                report.update(status='stopped', final_integrity_exception_type=type(exc).__name__, source_unchanged=False)
                raise
            finally:
                report.update(finished_unix=time.time(), finished_monotonic=time.monotonic(),
                    elapsed_common_seconds=time.monotonic() - started, windows_awake_released=scoped_awake(False))
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
                save()
        if report['status'] != 'completed_valid_component_screen' or not report['cleanup_confirmed']:
            raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, default=Path(__file__).resolve().parent,
                        help='Explicit task work directory for a byte-identical published copy')
    parser.add_argument('--launch', action='store_true', help='Requires separate root review and released predecessor resources')
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--deadline-unix', type=float)
    args = parser.parse_args()
    configure(args.work_root)
    if args.launch:
        launch(args)
    else:
        if args.manifest_sha256 is not None or args.deadline_unix is not None:
            parser.error('Deadline and reviewed SHA are accepted only by explicit --launch')
        prepare()


if __name__ == '__main__':
    main()
