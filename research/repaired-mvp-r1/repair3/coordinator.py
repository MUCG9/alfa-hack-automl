"""Owned repaired MVP continuation: original10800 clock, gates and two tasks.

Prepare the data manifest separately; this file never creates an authorization
layer. Manifest: coordinator_sha256, immutable_files, source_root=m2dev,
archive, archive_sha256, compiled_sha256, registry,
tasks[{kind,code,source,files,control_recipe:{path,sha256,signature}}],
gates[{name:source|exact,command,cwd,result,required}], final_audit with the same
command/cwd/result/required fields, and verification_plan_template.
Commands are argv lists; supported placeholders: python,work,output,manifest,
deadline_unix,verification_plan. No shell. Root supplies credentials only in its
existing launch environment, plus the fresh common start/deadline CLI values.
Default is inspect-only. Only the SHA-pinned failed pre-gate clock may continue; no clock reset, old task output or private ledger is resumed.
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
WORK = Path(__file__).resolve().parent
COMMON, FINAL, TASK_AUDIT, CLEANUP = 10800, 300, 60, 30
CLASS_MIN, CLASS_MAX, REG_PARENT = 6000, 8200, 2100
PREVIOUS_CAMPAIGN = 't3/campaign.json'
PREVIOUS_CAMPAIGN_SHA = '0557c4576b55af8cc17e51d6e71b327be4b544d69586078a51cdcfadab18c33c'
FAILED_LAUNCH = 'm2packet/launch.json'
FAILED_LAUNCH_SHA = '55c357c4c8ada13565cfe06dd6b03be5bee005ebc31937ae98c728593454d627'
ORIGINAL_START = 1792750977.2275486
ORIGINAL_DEADLINE = 1792761777.2275486
PRIOR = 'cache-pilot-k1-terminal-closure.json'
PRIOR_SHA = 'a42d2fedb4156158d8876134e238c7b86863d70506fcb59697c28efb096f939e'
LIBS = {
    'owner': 'support_component_coordinator.py',
    'processes': 'alfa-hack-automl/src/automl/infrastructure/processes.py',
    'lock': 'alfa-hack-automl/tools/research_lock.py',
    'strict': 'terminal_identity_fence_k1_r1.py'}


class TechnicalFailure(RuntimeError):
    pass


def need(value, code):
    if not value:
        raise TechnicalFailure(code)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(2**20), b''):
            h.update(chunk)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value, exclusive=False):
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf-8')
    if exclusive:
        with Path(path).open('xb') as stream:
            stream.write(raw)
    else:
        pending = Path(path).with_name(Path(path).name+'.pending')
        pending.write_bytes(raw)
        for attempt in range(21):
            try:
                os.replace(pending, path)
                break
            except PermissionError:
                if attempt == 20:
                    raise
                time.sleep(.05)


def local(name):
    p = (WORK/name).resolve()
    need(not Path(name).is_absolute() and p.is_relative_to(WORK), 'reference_outside_work')
    return p


def relative(path):
    return Path(path).resolve().relative_to(WORK).as_posix()


def imported(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def identities(items):
    result = set()
    for item in items:
        p, c = item['pid'], item['create_time']
        need(type(p) is int and p > 0 and type(c) in (int, float)
             and math.isfinite(c) and c > 0, 'invalid_owned_identity')
        result.add((p, float(c)))
    return result


def guard(manifest, manifest_path, manifest_sha, deployment):
    need(sha(manifest_path) == manifest_sha, 'manifest_changed')
    need(sha(__file__) == manifest['coordinator_sha256'], 'coordinator_source_changed')
    need(sha(local(FAILED_LAUNCH)) == FAILED_LAUNCH_SHA, 'original_failed_launch_changed')
    previous_failed_campaign_identities(manifest)
    for name in [*LIBS.values(), PRIOR, FAILED_LAUNCH, PREVIOUS_CAMPAIGN]:
        need(name in manifest['immutable_files'], 'unbound_runtime_dependency')
    launcher = manifest.get('launcher')
    if launcher is not None:
        need(manifest['immutable_files'].get(launcher) == manifest['launcher_sha256'],
             'unbound_bootstrap_launcher')
    for name, expected in manifest['immutable_files'].items():
        need(sha(local(name)) == expected, 'immutable_source_or_input_changed')
    for name, expected in deployment.items():
        need(sha(local(name)) == expected, 'deployed_source_or_input_changed')
    source = local(manifest['source_root'])
    need(source == WORK/'m2dev', 'unexpected_candidate_source_root')
    expected = {n for n in manifest['immutable_files'] if n.endswith('.py')
                and any(local(n).is_relative_to(source/p) for p in ['src', 'tools', 'tests'])}
    actual = {relative(p) for folder in ['src', 'tools', 'tests']
              for p in (source/folder).rglob('*.py')}
    need(expected == actual, 'candidate_python_inventory_changed')
    need(sha(local(manifest['archive'])) == manifest['archive_sha256'], 'archive_changed')


def clock(deadline, unix):
    need(abs((deadline-time.monotonic())-(unix-time.time())) <= 5, 'wall_monotonic_clock_disagreement')
    need(time.monotonic() < deadline and time.time() < unix, 'original_common_deadline_exhausted')


def previous_failed_campaign_identities(manifest=None):
    need(sha(local(PREVIOUS_CAMPAIGN)) == PREVIOUS_CAMPAIGN_SHA, 'failed_t3_campaign_changed')
    prior = load(local(PREVIOUS_CAMPAIGN))
    need(prior.get('status') == 'technical_failure' and prior.get('cleanup_confirmed') is True
         and prior.get('source_unchanged') is True and prior.get('active_supervisor') is None
         and prior.get('tasks') == [] and prior.get('start_unix') == ORIGINAL_START
         and prior.get('absolute_deadline_unix') == ORIGINAL_DEADLINE,
         'failed_t3_terminal_pre_task_proof_incomplete')
    result = identities([prior['owned_root']]) | identities(prior['coordinator_bootstrap_identities'])
    need(len(prior['supervisors']) == 1, 'failed_t3_supervisor_inventory_changed')
    for ref in prior['supervisors']:
        need(ref['path'] == 't3/g/source-supervisor.json' and ref['cleanup_confirmed'] is True
             and sha(local(ref['path'])) == ref['sha256'], 'failed_t3_source_supervisor_changed')
        if manifest is not None:
            need(manifest['immutable_files'].get(ref['path']) == ref['sha256'], 'failed_t3_supervisor_unbound')
        saved = load(local(ref['path']))
        need(saved.get('cleanup_confirmed') is True and saved.get('status') == 'child_failed'
             and saved.get('exit_code') == 1, 'failed_t3_source_cleanup_unknown')
        result |= identities(saved['owned_process_identities'])
    closure = load(local('m2packet/t4-terminal-closure.json'))
    need(closure['cleanup_confirmed'] is True and closure['source_unchanged'] is True
         and closure['actual_exec_exit_code_observed_by_root'] == 1
         and closure['original_absolute_deadline_unix'] == ORIGINAL_DEADLINE,
         't4_terminal_closure_required')
    result |= identities(closure['owned_identities']) | identities(closure['closure_preparer_identities'])
    return result


def predecessor(owner, strict, additional=()):
    need(sha(local(PRIOR)) == PRIOR_SHA, 'root_certified_k1_closure_changed')
    proof = load(local(PRIOR))
    need(proof.get('status') == 'root_certified_k1_terminal'
         and proof.get('cleanup_confirmed') is True and proof.get('source_unchanged') is True
         and proof.get('active_owned_processes') == []
         and proof.get('actual_exec_exit_code_observed_by_root') == 0,
         'predecessor_terminal_cleanup_unknown')
    # Only real ownership lists grant identities; analytical excluded edges and
    # nested historical receipts are never recursively adopted.
    need(sha(local(FAILED_LAUNCH)) == FAILED_LAUNCH_SHA, 'original_failed_launch_changed')
    failed = load(local(FAILED_LAUNCH))
    known = (identities(proof['owned_identities']) | identities(proof['closure_preparer_identities'])
             | identities(failed['launcher_identities']) | previous_failed_campaign_identities() | set(additional))
    return strict.strict_orphan_check_with_one_fence(owner,
        [dict(pid=p, create_time=c) for p, c in sorted(known)],
        WORK/'fullagent-cv-stage1-review-r4/stage0-terminal-ownership.json')


def environment(directory, model, manifest):
    allowed = {'PATH', 'PATHEXT', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'LOCALAPPDATA'}
    env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
    directory.mkdir(parents=True)
    for name in ['t', 'm']:
        (directory/name).mkdir()
    threads = '2' if model else '1'
    env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1',
        AUTOML_THREADS=threads, OMP_NUM_THREADS=threads, OPENBLAS_NUM_THREADS=threads,
        MKL_NUM_THREADS=threads, NUMEXPR_NUM_THREADS=threads,
        TEMP=str(directory/'t'), TMP=str(directory/'t'), TMPDIR=str(directory/'t'),
        MPLCONFIGDIR=str(directory/'m'))
    if model:
        need(os.environ.get('OPENAI_API_KEY') and os.environ.get('OPENAI_BASE_URL', '').rstrip('/')
             == 'https://changellenge.up.railway.app/v1', 'authorized_API_environment_missing')
        for key in ['OPENAI_API_KEY', 'OPENAI_BASE_URL']:
            env[key] = os.environ[key]
        env['OPENAI_MODEL'] = manifest.get('requested_model', 'qwen/qwen3.8-27b')
        env['AUTOML_REASONING_EFFORT'] = manifest.get('reasoning_effort', 'off')
    return env


def supervise(command, cwd, receipt, name, parent_start, parent_seconds, child_seconds,
              deadline, unix, reserve, state, persist, frozen, owner, processes,
              bootstraps, solver_seconds=None, requested_hpo=None):
    import psutil
    child = tree = None
    observer = owner.StrictOwnedObserver()
    verified = False
    end = parent_start+parent_seconds
    record = dict(status='starting', kind=name, start_unix=time.time(),
        start_monotonic=parent_start, parent_cap_seconds=parent_seconds,
        solver_budget_seconds=solver_seconds, child_cap_seconds=child_seconds,
        owned_process_identities=[], observed_worker_roots=[], cleanup_confirmed=False,
        peak_owned_tree_rss_mib=0., maximum_observed_concurrent_worker_jobs=0,
        hpo_first_worker_remaining_lower_bound_seconds=None, hpo_full_budget_observed=False,
        initial_assessment_seen_at_first_worker=None,
        requested_hpo_budget_seconds=requested_hpo)
    save(receipt, record, True)
    state['active_supervisor'] = relative(receipt)
    last = last_guard = time.monotonic()
    try:
        frozen(); clock(deadline, unix)
        env = environment(receipt.parent/('env-'+name), solver_seconds is not None, state['_manifest'])
        need(deadline-time.monotonic() >= reserve-(time.monotonic()-parent_start),
             'full_remaining_common_reserve_unavailable')
        need(end-time.monotonic() >= child_seconds, 'setup_consumed_complete_child_allocation')
        with receipt.with_suffix('.log').open('x', encoding='utf-8') as log:
            clock(deadline, unix)
            need(deadline-time.monotonic() >= reserve-(time.monotonic()-parent_start)
                 and end-time.monotonic() >= child_seconds,
                 'prePopen_remaining_allocation_unavailable')
            child = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            child_start = time.monotonic()
            p = psutil.Process(child.pid)
            root = p.pid, p.create_time()
            observer.remember([root]); tree = processes.ProcessTree(child)
            observer.remember(tree.members); verified = root in tree.members
            need(verified, 'initial_child_identity_unknown')
            record.update(status='running', owned_root=dict(pid=root[0], create_time=root[1]),
                child_start_monotonic=child_start)
            save(receipt, record); persist()
            worker_seen = set()
            while True:
                live = observer.observe(); tree.members.update(live)
                need(not observer.denials, 'owned_identity_or_traversal_denied')
                parents, memory, roles = {}, {}, {}
                for identity, process in live.items():
                    try:
                        need(process.create_time() == identity[1], 'owned_identity_changed')
                        memory[identity] = process.memory_info().rss
                        parents[identity[0]] = process.ppid()
                        argv = process.cmdline()  # Only exact owned processes; never saved.
                        if any(Path(x).name in {'automl_worker.py', 'agent_worker.py'} for x in argv):
                            job = Path(argv[-1]).resolve()
                            need(job.is_relative_to(WORK), 'owned_worker_job_outside_work')
                            roles[identity] = job
                    except psutil.NoSuchProcess:
                        continue
                logical = []
                for identity, job in roles.items():
                    ancestors, cursor = set(), parents.get(identity[0])
                    while cursor is not None and cursor not in ancestors:
                        ancestors.add(cursor); cursor = parents.get(cursor)
                    if not ancestors & {i[0] for i in roles}:
                        logical.append((identity, job))
                need(len(logical) <= 1, 'multiple_logical_workers')
                record['maximum_observed_concurrent_worker_jobs'] = max(
                    record['maximum_observed_concurrent_worker_jobs'], len(logical))
                for identity, job in logical:
                    rss = 0
                    for member, amount in memory.items():
                        cursor, ancestors = member[0], set()
                        while cursor is not None and cursor not in ancestors:
                            ancestors.add(cursor); cursor = parents.get(cursor)
                        if identity[0] in ancestors: rss += amount
                    need(rss <= int(1.5*2**30), 'worker_subtree_memory_limit')
                    if solver_seconds is not None:
                        actual = load(job)
                        need(actual.get('threads') == 2, 'model_threads_changed')
                    if identity not in worker_seen:
                        worker_seen.add(identity)
                        record['observed_worker_roots'].append(dict(pid=identity[0], create_time=identity[1],
                            job=relative(job), observed_monotonic=time.monotonic()))
                        if solver_seconds is not None and record['initial_assessment_seen_at_first_worker'] is None:
                            assessment = cwd/'automl_runs/repair4/initial-data-assessment.json'
                            record['initial_assessment_seen_at_first_worker'] = assessment.is_file()
                            record['initial_assessment_sha256_at_first_worker'] = sha(assessment) if assessment.is_file() else None
                            value = load(assessment).get('assessment', {}) if assessment.is_file() else {}
                            record['initial_assessment_valid_at_first_worker'] = (
                                value.get('assessment_valid') is True and value.get('call_status') == 'ok')
                        if requested_hpo and 'inner-hpo' in job.parts and record['hpo_first_worker_remaining_lower_bound_seconds'] is None:
                            reserve_export = min(1200, max(60, solver_seconds*.2))
                            window = max(0., child_start+solver_seconds-time.monotonic())
                            record.update(hpo_first_worker_remaining_lower_bound_seconds=window,
                                hpo_full_budget_observed=window >= reserve_export+requested_hpo+30,
                                hpo_usable_remaining_lower_bound_seconds=max(0., window-reserve_export-30),
                                hpo_window_definition='Raw remaining solver clock at first observed HPO worker; compare with actual export reserve plus requested HPO plus30')
                total = psutil.Process().memory_info().rss+sum(memory.values())
                for saved in bootstraps:
                    try:
                        p = psutil.Process(saved['pid'])
                        if p.create_time() == saved['create_time']: total += p.memory_info().rss
                    except psutil.NoSuchProcess:
                        pass
                need(total <= 2*2**30, 'whole_owned_tree_memory_limit')
                record['peak_owned_tree_rss_mib'] = max(record['peak_owned_tree_rss_mib'], total/2**20)
                now = time.monotonic(); clock(deadline, unix)
                need(now < end, 'parent_cap_exhausted')
                if now >= child_start+child_seconds:
                    record.update(status='timeout', failure_code='local_child_watchdog'); break
                if child.poll() is not None:
                    record.update(status='ok' if child.returncode == 0 else 'child_failed', exit_code=child.returncode); break
                if now-last_guard >= 30:
                    frozen(); last_guard = time.monotonic()
                if now-last >= 2:
                    record.update(heartbeat_unix=time.time(), owned_process_identities=[
                        dict(pid=p, create_time=c) for p, c in sorted(observer.seen)])
                    save(receipt, record); persist(); last = time.monotonic()
                time.sleep(.1)
    except BaseException as exc:
        record.update(status='technical_failure', exception_type=type(exc).__name__,
            failure_code=str(exc) if isinstance(exc, TechnicalFailure) else 'supervisor_operation_failed',
            os_errno=getattr(exc, 'errno', None), os_winerror=getattr(exc, 'winerror', None),
            failure_file=Path(exc.filename).name if getattr(exc, 'filename', None) else None)
    finally:
        record.update(owner.cleanup_owned(child, tree, observer, verified, processes.ProcessTree))
        record['exit_code'] = child.poll() if child is not None else None
        try:
            need(record['cleanup_confirmed'], 'cleanup_not_confirmed')
            frozen(); clock(deadline, unix)
            need(time.monotonic() < end, 'parent_cleanup_source_guard_over_cap')
        except BaseException as exc:
            record.update(status='technical_failure', terminal_exception=type(exc).__name__)
        record.update(seconds=time.monotonic()-parent_start, end_unix=time.time())
        save(receipt, record)
        if time.monotonic() >= end or time.monotonic() >= deadline or time.time() >= unix:
            record.update(status='technical_failure', failure_code='terminal_parent_receipt_over_cap')
            save(receipt, record)
        state['active_supervisor'] = None
        state.setdefault('supervisors', []).append(dict(path=relative(receipt), sha256=sha(receipt),
            cleanup_confirmed=record['cleanup_confirmed'], status=record['status']))
        persist()
    return record


def required_result(cfg):
    data = load(local(cfg['result']))
    need(cfg.get('required'), 'result_contract_unspecified')
    for key, expected in cfg['required'].items():
        value = data
        for part in key.split('.'): value = value[part]
        need(value == expected and type(value) is type(expected), 'required_result_field_failed:'+key)
    return data


def command(cfg, substitutions):
    need(isinstance(cfg['command'], list) and cfg['command'], 'command_argv_required')
    return [str(x).format_map(substitutions) for x in cfg['command']]


def materialize(task, directory, manifest, deployment):
    directory.mkdir()
    with zipfile.ZipFile(local(manifest['archive'])) as z:
        need(set(z.namelist()) == set(manifest['compiled_sha256']) and len(z.namelist()) == len(set(z.namelist())), 'archive_inventory_changed')
        for name, expected in manifest['compiled_sha256'].items():
            need(Path(name).name == name, 'archive_not_flat')
            (directory/name).write_bytes(z.read(name))
            need(sha(directory/name) == expected, 'runtime_copy_changed')
            deployment[relative(directory/name)] = expected
    need(set(task['files']) == {'task.md', 'train.csv', 'test.csv', 'data_dictionary.csv', 'sample_submission.csv'}, 'five_named_inputs_required')
    for name, expected in task['files'].items():
        shutil.copyfile(local(task['source'])/name, directory/name)
        need(sha(directory/name) == expected, 'task_input_copy_changed')
        deployment[relative(directory/name)] = expected
    control = task['control_recipe']
    need(manifest['immutable_files'].get(control['path']) == control['sha256']
         and sha(local(control['path'])) == control['sha256'], 'protected_control_not_bound')
    shutil.copyfile(local(control['path']), directory/'protected_control.json')
    need(sha(directory/'protected_control.json') == control['sha256'], 'protected_control_copy_changed')
    deployment[relative(directory/'protected_control.json')] = control['sha256']


def task_proof(directory):
    report = directory/'automl_runs/repair4/report.json'
    submission = directory/'submission.csv'
    if not report.is_file() or not submission.is_file():
        return dict(report_path=relative(report), submission_path=relative(submission),
                    artifacts_complete=False, final_fit_status=None, integrity_ok=None)
    data = load(report)
    return dict(report_path=relative(report), report_sha256=sha(report), submission_path=relative(submission),
        submission_sha256=sha(submission), artifacts_complete=True,
        final_fit_status=data.get('final_fit_status'), integrity_ok=data.get('integrity_ok'),
        solver_report_seconds=data.get('elapsed_seconds'), hpo_reported=data.get('hpo'),
        stage_report=data.get('pipeline'),
        scope='Parent metadata only; independent saved-artifact verifier decides stage/quality qualification.')


def core_seal(directory):
    # The API run-budget sibling is deliberately outside this core-artifact
    # seal. It is never retried or inferred from core prediction integrity.
    files = {}
    root = directory/'automl_runs/repair4'
    if root.exists():
        for parent, dirs, names in os.walk(root):
            need(not any((Path(parent)/n).is_symlink() for n in [*dirs, *names]), 'artifact_symlink')
            for name in names:
                p = Path(parent)/name
                need(not name.endswith(('.tmp', '.pending')), 'unfinished_core_artifact')
                files[relative(p)] = sha(p)
    if (directory/'submission.csv').exists(): files[relative(directory/'submission.csv')] = sha(directory/'submission.csv')
    return files


def invalidate(state):
    state.update(status='technical_failure', qualification='FAIL', qualified_four_stage_both_tasks=False,
        quality_gain=None, promotion=False)
    if isinstance(state.get('independent_audit'), dict):
        state['independent_audit'].update(explicitly_unqualified=True, qualified_result=None)
    for task in state['tasks']: task['qualified'] = False


def run(args, manifest, path, manifest_sha):
    import psutil
    output = WORK/'t5'
    need(not output.exists(), 'new_attempt_output_required_no_resume')
    need(sha(local(FAILED_LAUNCH)) == FAILED_LAUNCH_SHA, 'original_failed_launch_changed')
    failed = load(local(FAILED_LAUNCH))
    need(failed.get('status') == 'coordinator_failed'
         and failed.get('coordinator_exit_code') == 1 and failed.get('exception_type') == 'Blocked'
         and failed.get('start_unix') == ORIGINAL_START
         and failed.get('absolute_deadline_unix') == ORIGINAL_DEADLINE
         and failed.get('finished_unix', float('inf')) < ORIGINAL_DEADLINE
         and args.common_start_unix == ORIGINAL_START and args.deadline_unix == ORIGINAL_DEADLINE
         and ORIGINAL_START <= time.time() < ORIGINAL_DEADLINE,
         'only_original_failed_launch_clock_continuation_permitted')
    deadline = time.monotonic()+args.deadline_unix-time.time()
    deployment = {}
    frozen = lambda: guard(manifest, path, manifest_sha, deployment)
    frozen()
    modules = {k: imported('_repair4_'+k, local(v)) for k, v in LIBS.items()}
    owner, processes, strict = modules['owner'], modules['processes'], modules['strict']
    predecessor(owner, strict)
    bootstraps = []
    owned_launcher_paths = {Path(__file__).resolve()}
    if manifest.get('launcher') is not None:
        owned_launcher_paths.add(local(manifest['launcher']))
    parent = psutil.Process().parent()
    while parent is not None:
        created = parent.create_time()
        if not any(Path(a).resolve() in owned_launcher_paths for a in parent.cmdline() if not a.startswith('-')): break
        need(parent.create_time() == created, 'bootstrap_identity_changed')
        bootstraps.append(dict(pid=parent.pid, create_time=created)); parent = parent.parent()
    state = dict(status='starting', manifest_sha256=manifest_sha, source_archive_sha256=manifest['archive_sha256'],
        start_unix=args.common_start_unix, start_monotonic=deadline-COMMON,
        absolute_deadline_unix=args.deadline_unix, common_deadline_monotonic=deadline,
        new_common_limit_seconds=COMMON, original_clock_continuation=True, failed_launch_sha256=FAILED_LAUNCH_SHA,
        failed_t3_campaign_sha256=PREVIOUS_CAMPAIGN_SHA,
        repaired_harness_classification_min_parent_seconds=CLASS_MIN, owned_root=dict(pid=os.getpid(), create_time=psutil.Process().create_time()),
        coordinator_bootstrap_identities=bootstraps, tasks=[], gates=[], supervisors=[], active_supervisor=None,
        cleanup_confirmed=False, source_unchanged=False, qualification=None,
        qualified_four_stage_both_tasks=False, independent_audit=None, quality_gain=None,
        promotion=False, submit=False, _manifest=manifest)
    def persist(): save(output/'campaign.json', {k: v for k, v in state.items() if not k.startswith('_')})
    finished = set()
    final_deadline = None
    with modules['lock'].ResearchLock(WORK/'alfa-hack-automl/test-runs/.owned-research.lock') as lock:
        lock.write_identity(state['owned_root']); predecessor(owner, strict); frozen(); clock(deadline, args.deadline_unix)
        output.mkdir(); (output/'g').mkdir()
        plan = copy.deepcopy(manifest['verification_plan_template'])
        plan.update(execution_manifest_sha256=manifest_sha, original_absolute_deadline_unix=args.deadline_unix)
        save(output/'verification-plan.json', plan, True)
        state['verification_plan_sha256'] = sha(output/'verification-plan.json')
        deployment['t5/verification-plan.json'] = state['verification_plan_sha256']
        substitutions = dict(python=sys.executable, work=str(WORK), output=str(output),
            manifest=relative(path), deadline_unix=repr(args.deadline_unix), verification_plan='t5/verification-plan.json')
        def interrupted(signum, frame): raise SystemExit(128+signum)
        previous = {s: signal.signal(s, interrupted) for s in [signal.SIGINT, signal.SIGTERM]}
        persist()
        try:
            need([g['name'] for g in manifest['gates']] == ['source', 'exact'], 'required_gate_order_changed')
            for index, cfg in enumerate(manifest['gates']):
                # Same compiled source, inputs and registry; completed actual gates are
                # reused from t4, with terminal pending record plus fresh root closure.
                predecessor(owner, strict, finished); frozen(); clock(deadline, args.deadline_unix)
                sup = load(local(cfg['reused_supervisor']))
                need(sup['status'] == 'ok' and sup['exit_code'] == 0
                     and sup['cleanup_confirmed'] is True, 'reused_gate_terminal_failed')
                finished |= identities(sup['owned_process_identities'])
                data = required_result(cfg)
                if cfg['name'] == 'source':
                    need(data.get('passed') is True and data.get('source_unchanged') is True
                         and data.get('fixture_cleanup_confirmed') is True
                         and data.get('unique_checks_passed') == sum(manifest['registry'].values())
                         and data.get('unique_checks_skipped') == 0
                         and data.get('source_sha256') == manifest['compiled_sha256'], 'source_registry_or_compilation_mismatch')
                    rows = {r['script']: r for r in data['checks']}
                    need(set(rows) == set(manifest['registry']), 'source_script_coverage_changed')
                    for name, count in manifest['registry'].items():
                        need(rows[name]['passed'] is True and rows[name]['observed_checks'] == count
                             and rows[name]['skipped_checks'] == 0, 'source_script_count_or_skip_failed')
                else:
                    need(data.get('passed') is True and data.get('matches_current_source') is True
                         and data.get('sha256') == manifest['archive_sha256'], 'exact_archive_mismatch')
                    rows = data.get('checks', [])
                    need([r['script'] for r in rows] == ['test_v2.py', 'test_resilience.py', 'smoke.py'], 'exact_script_coverage_missing')
                    for row in rows:
                        text = row.get('stdout', '')+'\n'+row.get('stderr', '')
                        need(row['exit_code'] == 0 and not re.search(r'\bskipped\s*=\s*[1-9]', text), 'exact_script_failed_or_skipped')
                        if row['script'] == 'smoke.py':
                            cases = json.loads(row['stdout']); need(len(cases) == 5 and all(c['status'] == 'passed' for c in cases), 'exact_smoke_incomplete')
                        else:
                            counts = re.findall(r'Ran (\d+) tests? in ', text)
                            need(counts and int(counts[-1]) == manifest['registry'][row['script']], 'exact_script_count_mismatch')
                state['gates'].append(dict(name=cfg['name'], supervisor=sup, reused_completed_t4_gate=True, result_sha256=sha(local(cfg['result']))))
                persist()
            need([(t['kind'], t['code']) for t in manifest['tasks']]
                 == [('regression', 'r'), ('classification', 'c')], 'two_task_order_and_paths_required')
            need(type(manifest.get('maximum_experiments', 14)) is int
                 and 7 <= manifest.get('maximum_experiments', 14) <= 14, 'invalid_maximum_experiments')
            state['status'] = 'running'; persist()
            for index, task in enumerate(manifest['tasks']):
                tick = time.monotonic(); clock(deadline, args.deadline_unix)
                reserve = CLASS_MIN+FINAL if index == 0 else FINAL
                cap = REG_PARENT if index == 0 else min(CLASS_MAX, int(deadline-tick-FINAL-2))
                need(cap >= (REG_PARENT if index == 0 else CLASS_MIN), 'minimum_task_allocation_unavailable')
                need(deadline-tick >= cap+reserve, 'task_common_reservation_unavailable')
                predecessor(owner, strict, finished)
                directory = output/task['code']; materialize(task, directory, manifest, deployment)
                seconds = cap-TASK_AUDIT-CLEANUP
                hpo = 900 if index == 0 else 2100
                argv = [sys.executable, '-B', '-X', 'utf8', '-u', 'solution.py', 'task.md',
                    '--four-stage', '--preserve-anchor', '--protect-original-features',
                    '--control-recipe', 'protected_control.json',
                    '--max-experiments', str(manifest.get('maximum_experiments', 14)),
                    '--max-planner-calls', '2', '--max-llm-calls', '4', '--hpo-trials', '8',
                    '--hpo-budget', str(hpo), '--feature-selection-top-k', '32', '--planner-mode', 'staged',
                    '--run-name', 'repair4', '--time-budget', str(seconds)]
                sup = supervise(argv, directory, directory/'supervisor.json', task['kind'], tick,
                    cap-TASK_AUDIT, seconds, deadline, args.deadline_unix, cap+reserve,
                    state, persist, frozen, owner, processes, bootstraps, seconds, hpo)
                finished |= identities(sup['owned_process_identities'])
                need(sup['status'] != 'technical_failure' and sup['cleanup_confirmed'], 'task_technical_failure')
                proof = task_proof(directory)
                sealed = core_seal(directory)
                seal_path = output/(task['code']+'-seal.json')
                save(seal_path, dict(files_sha256=sealed, cleanup_confirmed=True, source_unchanged=True), True)
                entry = dict(sup, kind=task['kind'], code=task['code'], allocated_parent_seconds=cap,
                    solver_budget_seconds=seconds, proof=proof, qualified=False,
                    supervisor_path=relative(directory/'supervisor.json'), supervisor_sha256=sha(directory/'supervisor.json'),
                    seal=dict(path=relative(seal_path), sha256=sha(seal_path)), seconds_including_verification=time.monotonic()-tick)
                state['tasks'].append(entry); frozen(); persist()
                need(time.monotonic() < tick+cap, 'task_metadata_seal_over_parent_cap')
            tick = time.monotonic()
            final_deadline = tick+FINAL
            need(deadline-tick >= FINAL, 'final_independent_audit_reserve_unavailable')
            frozen(); predecessor(owner, strict, finished)
            state.update(status='verifying', cleanup_confirmed=True, source_unchanged=True)
            persist()
            cfg = manifest['final_audit']
            sup = supervise(command(cfg, substitutions), local(cfg.get('cwd', '.')), output/'final-audit-supervisor.json',
                'final-audit', tick, FINAL, FINAL-CLEANUP, deadline, args.deadline_unix, FINAL,
                state, persist, frozen, owner, processes, bootstraps)
            finished |= identities(sup['owned_process_identities'])
            need(sup['status'] == 'ok' and sup['cleanup_confirmed'], 'independent_audit_process_failed')
            audit = required_result(cfg)
            need(audit.get('artifact_procedure_checks_passed') is True
                 and audit.get('audit_within_original_common_clock') is True
                 and audit.get('campaign_terminal_confirmed') is False
                 and audit.get('parent_exec_terminal_qualification_required') is True
                 and audit.get('actual_common_deadline_satisfied') is None,
                 'independent_pending_terminal_artifact_contract_failed')
            need(all(t['status'] == 'ok' and t['exit_code'] == 0 and t['cleanup_confirmed'] is True
                     for t in state['tasks']), 'successful_task_terminal_receipts_required')
            state.update(status='completed_repaired_MVP', qualification='PASS',
                qualified_four_stage_both_tasks=True,
                campaign_terminal_confirmed=False, parent_exec_terminal_qualification_required=True,
                independent_audit=dict(path=cfg['result'], sha256=sha(local(cfg['result'])), qualified_result=audit))
            need(time.monotonic() < tick+FINAL, 'independent_audit_terminal_parent_cap')
        except BaseException as exc:
            invalidate(state)
            state.update(exception_type=type(exc).__name__, failure_code=str(exc) if isinstance(exc, TechnicalFailure) else 'coordinator_operation_failed',
                os_errno=getattr(exc, 'errno', None), os_winerror=getattr(exc, 'winerror', None),
                failure_file=Path(exc.filename).name if getattr(exc, 'filename', None) else None)
        finally:
            try:
                frozen(); predecessor(owner, strict, finished)
                for entry in state['tasks']:
                    receipt = local(entry['seal']['path'])
                    need(sha(receipt) == entry['seal']['sha256'], 'late_seal_receipt_changed')
                    need(load(receipt)['files_sha256'] == core_seal(output/entry['code']), 'late_core_artifact_changed')
                need(all(r['cleanup_confirmed'] is True for r in state['supervisors']),
                     'prior_supervisor_cleanup_unknown')
                state.update(cleanup_confirmed=True, source_unchanged=True)
                clock(deadline, args.deadline_unix)
                need(final_deadline is None or time.monotonic() < final_deadline,
                     'final_audit_terminal_cleanup_over_cap')
            except BaseException as exc:
                invalidate(state); state.update(cleanup_confirmed=False, source_unchanged=False, terminal_exception=type(exc).__name__)
            state.update(finished_unix=time.time(), finished_monotonic=time.monotonic(),
                elapsed_common_seconds=time.monotonic()-(deadline-COMMON))
            persist()
            if time.monotonic() >= deadline or time.time() >= args.deadline_unix or (
                    final_deadline is not None and time.monotonic() >= final_deadline):
                invalidate(state); state['failure_code'] = 'terminal_campaign_write_over_common_cap'; persist()
            for sig, handler in previous.items(): signal.signal(sig, handler)
    return state


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--manifest-sha256', required=True)
    p.add_argument('--launch', action='store_true')
    p.add_argument('--common-start-unix', type=float)
    p.add_argument('--deadline-unix', type=float)
    args = p.parse_args()
    path = args.manifest.resolve()
    need(path.is_relative_to(WORK) and sha(path) == args.manifest_sha256, 'explicit_manifest_sha_required')
    manifest = load(path)
    if not args.launch:
        print(json.dumps(dict(status='inspect_only', clock_assigned=False, fits=0, API_calls=0)))
        return
    result = run(args, manifest, path, args.manifest_sha256)
    print(json.dumps({k: result[k] for k in ['status', 'qualification', 'cleanup_confirmed', 'elapsed_common_seconds']}))
    raise SystemExit(0 if result['status'] == 'completed_repaired_MVP' and result['cleanup_confirmed'] else 1)


if __name__ == '__main__':
    main()
