"""Fresh independent lean MVP:10800s includes gates, both tasks and R4 audit.
No old clock/output is resumed. Root prepares m4packet and private launch env.
Inputs: existing coordinator/archive/registry/tasks/gates/final_audit/plan schema;
also immutable exact t5 closure, CatBoost fixture, awake guard and R4 auditor.
Only9 outer experiments, protected exact controls,2planner/4gateway,8HPO trials.
Qualification remains pending root-observed exec and fresh terminal closure.
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
WORK = Path(__file__).resolve().parent.parent
RESOURCE_SAMPLER = 'verified-resource-sampling-next-dev/verified_sampling.py'
RESOURCE_SAMPLER_SHA = 'd65ee39eb80c9fc4590cbbf474ee6c09e84cb65abe2d2c367ebcfa415a390cf0'
COMMON, FINAL, TASK_AUDIT, CLEANUP = 10800, 300, 60, 30
CLASS_MIN, CLASS_MAX, REG_PARENT = 6000, 8200, 2100
PRIOR = 'm2packet/t5-terminal-closure.json'
PRIOR_SHA = '0e959a6d35963d30025799805544a35f732bb1b6c52a9bc0c2d345d6f4ecfb09'
FIXTURE = 'catboost-weight-metric-next/fixture-supervisor.json'
FIXTURE_SHA = '845d54a1a7785e0944f32a9b7fd74125617498752b6d034a47abd38cffec7a2a'
AWAKE = 'awake-next-dev/awake_guard.py'
AWAKE_SHA = '9a0bae0acb6ddb37e638420c52ad1e587a9180fbd7ef68ebc6e1a3c43e4bfc9b'
AUDITOR = 'repaired-mvp-r1-dev/evaluator_r4.py'
AUDITOR_SHA = 'c08e9f0be13a708d67b3266518381d6f1be3b0f43c384ef6425634160d7e2783'
TERMINAL_PREDECESSORS = {'m3packet/terminal-root-closure.json': 'ca4796c602ac213a2c48a652fcbb8461ddceadd51b4aa0b8f661ad59931b344a', 't6-independent-classification-r1/root-closure.json': 'cdd587b0ab7f93f9af5cbc835267a15bd008d85b3241fb162032ced3a91168f4', 't7-predecessor-root-closure.json': '1c7dea8a72738cee399597d5aef3afb34d220cd9719715fec4525c1dec48caae'}
LIBS = {
    'owner': 'support_component_coordinator.py',
    'processes': 'alfa-hack-automl/src/automl/infrastructure/processes.py',
    'lock': 'alfa-hack-automl/tools/research_lock.py'}

class TechnicalFailure(RuntimeError):
    pass

def need(value, code):
    if not value:
        raise TechnicalFailure(code)

def sha(path, checkpoint=None):
    # Cooperative progress does not reset clocks or excuse an actual blocked read.
    if checkpoint is not None: checkpoint()
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            if checkpoint is not None: checkpoint()
            chunk = stream.read(2**20)
            if not chunk: break
            h.update(chunk)
            if checkpoint is not None: checkpoint()
    if checkpoint is not None: checkpoint()
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

def guard(manifest, manifest_path, manifest_sha, deployment, checkpoint=None):
    if checkpoint is not None: checkpoint()
    need(sha(manifest_path, checkpoint) == manifest_sha, 'manifest_changed')
    need(sha(__file__, checkpoint) == manifest['coordinator_sha256'], 'coordinator_source_changed')
    for name in [*LIBS.values(), PRIOR, FIXTURE, AWAKE, AUDITOR]:
        need(name in manifest['immutable_files'], 'unbound_runtime_dependency')
    for ref in manifest.get('extra_predecessor_receipts', []):
        need(manifest['immutable_files'].get(ref['path']) == ref['sha256'], 'unbound_extra_predecessor')
    need(manifest['immutable_files'][PRIOR] == PRIOR_SHA and manifest['immutable_files'][FIXTURE] == FIXTURE_SHA
         and manifest['immutable_files'][AWAKE] == AWAKE_SHA and manifest['immutable_files'][AUDITOR] == AUDITOR_SHA
         and manifest['verification_plan_template']['verifier_source_sha256'] == AUDITOR_SHA, 'mandatory_proof_or_R4_binding_changed')
    terminal_refs = manifest.get('terminal_predecessor_receipts', [])
    need({r['path']: r['sha256'] for r in terminal_refs} == TERMINAL_PREDECESSORS
         and len(terminal_refs) == len(TERMINAL_PREDECESSORS), 'exact_terminal_predecessors_required')
    for name, digest in TERMINAL_PREDECESSORS.items():
        need(manifest['immutable_files'].get(name) == digest, 'unbound_terminal_predecessor')
    launcher = manifest.get('launcher')
    if launcher is not None:
        need(manifest['immutable_files'].get(launcher) == manifest['launcher_sha256'],
             'unbound_bootstrap_launcher')
    for name, expected in manifest['immutable_files'].items():
        need(sha(local(name), checkpoint) == expected, 'immutable_source_or_input_changed')
    for name, expected in deployment.items():
        need(sha(local(name), checkpoint) == expected, 'deployed_source_or_input_changed')
    source = local(manifest['source_root'])
    need(source == WORK/'m3dev', 'unexpected_candidate_source_root')
    expected = {n for n in manifest['immutable_files'] if n.endswith('.py')
                and any(local(n).is_relative_to(source/p) for p in ['src', 'tools', 'tests'])}
    actual = {relative(p) for folder in ['src', 'tools', 'tests']
              for p in (source/folder).rglob('*.py')}
    need(expected == actual, 'candidate_python_inventory_changed')
    need(sha(local(manifest['archive']), checkpoint) == manifest['archive_sha256'], 'archive_changed')
    # Rebind manifest/coordinator after the complete guarded inventory walk.
    need(sha(manifest_path, checkpoint) == manifest_sha, 'manifest_changed')
    need(sha(__file__, checkpoint) == manifest['coordinator_sha256'], 'coordinator_source_changed')
    if checkpoint is not None: checkpoint()

def clock(deadline, unix):
    need(abs((deadline-time.monotonic())-(unix-time.time())) <= 5, 'wall_monotonic_clock_disagreement')
    need(time.monotonic() < deadline and time.time() < unix, 'original_common_deadline_exhausted')

def predecessor(owner, additional=(), extra_receipts=(), terminal_receipts=()):
    need(sha(local(PRIOR)) == PRIOR_SHA and sha(local(FIXTURE)) == FIXTURE_SHA, 'closed_predecessor_proof_changed')
    prior, fixture = load(local(PRIOR)), load(local(FIXTURE))
    need(prior.get('cleanup_confirmed') is True and prior.get('source_unchanged') is True
         and prior.get('active_owned_processes') == [] and len(prior['owned_identities']) == 2805,
         't5_fresh_terminal_absence_required')
    need(fixture.get('status') == 'passed' and fixture.get('exit_code') == 0
         and fixture.get('cleanup_confirmed') is True and fixture.get('source_unchanged') is True,
         'fixture_terminal_cleanup_required')
    known = (identities(prior['owned_identities']) | identities(prior['closure_preparer_identities'])
             | identities([fixture['owned_root']]) | identities(fixture['bootstrap_identities'])
             | identities(fixture['owned_process_identities']) | set(additional))
    for ref in extra_receipts:
        need(sha(local(ref['path'])) == ref['sha256'], 'extra_predecessor_receipt_changed')
        proof = load(local(ref['path']))
        need(proof.get('cleanup_confirmed') is True and proof.get('source_unchanged') is True
             and proof.get('exit_code') == 0, 'extra_predecessor_cleanup_unknown')
        known |= (identities([proof['owned_root']]) | identities(proof['bootstrap_identities'])
                  | identities(proof['owned_process_identities']))
    need({r['path']: r['sha256'] for r in terminal_receipts} == TERMINAL_PREDECESSORS
         and len(terminal_receipts) == len(TERMINAL_PREDECESSORS), 'terminal_predecessor_set_changed')
    for ref in terminal_receipts:
        need(sha(local(ref['path'])) == ref['sha256'], 'terminal_predecessor_proof_changed')
        proof = load(local(ref['path']))
        need(proof.get('cleanup_confirmed') is True and proof.get('source_unchanged') is True
             and not proof.get('active_owned_processes', []) and not proof.get('uncertain_owned', []),
             'terminal_predecessor_cleanup_or_source_unknown')
        known |= identities(proof['owned_identities']) | identities(proof['closure_preparer_identities'])
    observer = owner.StrictOwnedObserver(); observer.remember(known)
    need(not observer.observe() and not observer.denials and not observer.final_check()['unresolved'],
         'exact_closed_predecessor_still_live_or_denied')
    return [dict(pid=p, create_time=c) for p, c in sorted(known)]

def pulse(awake):
    # heartbeat measures the real previous sample BEFORE updating it. Never reset
    # its history to excuse slow work, and retain the first bad sample on failure.
    sample = awake.heartbeat()
    if sample['scheduling_gap_exceeded']:
        awake.record.setdefault('first_exceeded_heartbeat', dict(sample))
    need(not sample['scheduling_gap_exceeded'], 'host_supervisor_heartbeat_gap_over10s')


def cooperative_checkpoint(awake, deadline, unix, parent_deadline=None,
                           parent_code='parent_cap_exhausted'):
    pulse(awake)
    clock(deadline, unix)
    if parent_deadline is not None:
        need(time.monotonic() < parent_deadline, parent_code)

def error(record, code, phase, exc=None):
    entry = dict(code=code, phase=phase, unix=time.time(), monotonic=time.monotonic(),
        exception_type=type(exc).__name__ if exc else None, errno=getattr(exc,'errno',None),
        winerror=getattr(exc,'winerror',None))
    record.setdefault('error_history', []).append(entry)
    record.setdefault('first_failure', entry); record.setdefault('failure_code', code)

def child_errors(state, receipt):
    for item in receipt.get('error_history', []):
        entry = dict(item, child_kind=receipt['kind'])
        state['error_history'].append(entry)
        state.setdefault('first_failure', entry); state.setdefault('failure_code', entry['code'])

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
    def resource_checkpoint():
        # Existing caller observation history/common/parent clocks, never reset.
        state['_pulse'](); clock(deadline, unix)
        need(time.monotonic() < end, 'parent_cap_exhausted')
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
        frozen(end, 'parent_cap_exhausted'); clock(deadline, unix)
        need(sha(local(RESOURCE_SAMPLER), resource_checkpoint) == RESOURCE_SAMPLER_SHA,
             'verified_resource_sampler_source_changed')
        sampling = imported('_verified_supervision_sampling', local(RESOURCE_SAMPLER))
        resource_sampler = sampling.VerifiedResourceSampler()
        me = psutil.Process(); self_identity = (me.pid, me.create_time())
        bootstrap_identities = identities(bootstraps)
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
                state['_pulse']()
                live = observer.observe(); tree.members.update(live)
                need(not observer.denials, 'owned_identity_or_traversal_denied')
                sample = resource_sampler.sample(set(live) | bootstrap_identities | {self_identity},
                    required=[self_identity], checkpoint=resource_checkpoint)
                stable_rss = {(row['pid'], row['create_time']): row['rss_bytes'] for row in sample['sampled']}
                parents, memory, roles = {}, {i:stable_rss[i] for i in live if i in stable_rss}, {}
                for identity, process in live.items():
                    if identity not in stable_rss: continue  # Explicit freshly confirmed departed identity.
                    try:
                        resource_checkpoint()
                        need(process.create_time() == identity[1], 'owned_identity_changed')
                        parents[identity[0]] = process.ppid()
                        argv = process.cmdline()  # Only exact owned processes; never saved.
                        need(process.create_time() == identity[1], 'owned_identity_changed')
                        resource_checkpoint()
                        if any(Path(x).name in {'automl_worker.py', 'agent_worker.py'} for x in argv):
                            job = Path(argv[-1]).resolve()
                            need(job.is_relative_to(WORK), 'owned_worker_job_outside_work')
                            roles[identity] = job
                    except psutil.NoSuchProcess:
                        resource_sampler.confirm_departed(identity, checkpoint=resource_checkpoint)
                        # Keep already verified RSS/PPID conservatively, as the original loop did.
                        continue
                record['verified_resource_sample'] = sample
                record['departed_known_resource_identities'] = list(resource_sampler.departed)
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
                # Preserve the original conservative self + tree + bootstrap sum,
                # including any overlap; departed rows are provenance, never invented RSS0.
                total = stable_rss[self_identity]+sum(memory.values())
                for identity in bootstrap_identities:
                    if identity in stable_rss: total += stable_rss[identity]
                need(total <= 2*2**30, 'whole_owned_tree_memory_limit')
                record['peak_owned_tree_rss_mib'] = max(record['peak_owned_tree_rss_mib'], total/2**20)
                now = time.monotonic(); clock(deadline, unix)
                need(now < end, 'parent_cap_exhausted')
                if now >= child_start+child_seconds:
                    record.update(status='timeout'); error(record, 'local_child_watchdog', 'child_watchdog'); break
                if child.poll() is not None:
                    record.update(status='ok' if child.returncode == 0 else 'child_failed', exit_code=child.returncode)
                    if child.returncode != 0: error(record, 'child_nonzero_exit', 'child_exit')
                    break
                if now-last_guard >= 30:
                    frozen(end, 'parent_cap_exhausted'); last_guard = time.monotonic()
                if now-last >= 2:
                    record.update(heartbeat_unix=time.time(), owned_process_identities=[
                        dict(pid=p, create_time=c) for p, c in sorted(observer.seen)])
                    save(receipt, record); persist(); last = time.monotonic()
                time.sleep(.1)
    except BaseException as exc:
        error(record, str(exc) if isinstance(exc, TechnicalFailure) else 'supervisor_operation_failed', 'supervisor', exc)
        record.update(status='technical_failure', exception_type=type(exc).__name__,
            os_errno=getattr(exc, 'errno', None), os_winerror=getattr(exc, 'winerror', None),
            failure_file=Path(exc.filename).name if getattr(exc, 'filename', None) else None)
    finally:
        record.update(owner.cleanup_owned(child, tree, observer, verified, processes.ProcessTree))
        record['exit_code'] = child.poll() if child is not None else None
        try:
            need(record['cleanup_confirmed'], 'cleanup_not_confirmed')
            frozen(end, 'parent_cleanup_source_guard_over_cap'); clock(deadline, unix)
            need(time.monotonic() < end, 'parent_cleanup_source_guard_over_cap')
        except BaseException as exc:
            error(record, str(exc) if isinstance(exc, TechnicalFailure) else 'terminal_supervision_failed', 'supervisor_terminal', exc)
            record.update(status='technical_failure', terminal_exception=type(exc).__name__)
        record.update(seconds=time.monotonic()-parent_start, end_unix=time.time())
        save(receipt, record)
        if time.monotonic() >= end or time.monotonic() >= deadline or time.time() >= unix:
            error(record, 'terminal_parent_receipt_over_cap', 'supervisor_receipt'); record.update(status='technical_failure')
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

def task_proof(directory, checkpoint=None):
    if checkpoint is not None: checkpoint()
    report = directory/'automl_runs/repair4/report.json'
    submission = directory/'submission.csv'
    if not report.is_file() or not submission.is_file():
        return dict(report_path=relative(report), submission_path=relative(submission),
                    artifacts_complete=False, final_fit_status=None, integrity_ok=None)
    data = load(report)
    if checkpoint is not None: checkpoint()
    return dict(report_path=relative(report), report_sha256=sha(report, checkpoint), submission_path=relative(submission),
        submission_sha256=sha(submission, checkpoint), artifacts_complete=True,
        final_fit_status=data.get('final_fit_status'), integrity_ok=data.get('integrity_ok'),
        solver_report_seconds=data.get('elapsed_seconds'), hpo_reported=data.get('hpo'),
        stage_report=data.get('pipeline'),
        scope='Parent metadata only; independent saved-artifact verifier decides stage/quality qualification.')

def core_seal(directory, checkpoint=None):
    if checkpoint is not None: checkpoint()
    # The API run-budget sibling is deliberately outside this core-artifact
    # seal. It is never retried or inferred from core prediction integrity.
    files = {}
    root = directory/'automl_runs/repair4'
    if root.exists():
        for parent, dirs, names in os.walk(root):
            if checkpoint is not None: checkpoint()
            need(not any((Path(parent)/n).is_symlink() for n in [*dirs, *names]), 'artifact_symlink')
            for name in names:
                if checkpoint is not None: checkpoint()
                p = Path(parent)/name
                need(not name.endswith(('.tmp', '.pending')), 'unfinished_core_artifact')
                files[relative(p)] = sha(p, checkpoint)
    if (directory/'submission.csv').exists(): files[relative(directory/'submission.csv')] = sha(directory/'submission.csv', checkpoint)
    if checkpoint is not None: checkpoint()
    return files

def invalidate(state):
    state.update(status='technical_failure', qualification='FAIL', qualified_four_stage_both_tasks=False,
        quality_gain=None, promotion=False)
    if isinstance(state.get('independent_audit'), dict):
        state['independent_audit'].update(explicitly_unqualified=True, qualified_result=None)
    for task in state['tasks']: task['qualified'] = False

def run(args, manifest, path, manifest_sha, awake):
    import psutil
    output = WORK/'t7'
    need(not output.exists(), 'new_attempt_output_required_no_resume')
    need(args.common_start_unix is not None and args.deadline_unix is not None
         and math.isfinite(args.common_start_unix) and math.isfinite(args.deadline_unix)
         and abs(args.deadline_unix-args.common_start_unix-COMMON) <= 1e-6
         and 0 <= time.time()-args.common_start_unix <= 30, 'one_fresh_independent10800_clock_required')
    deadline = time.monotonic()+args.deadline_unix-time.time()
    deployment = {}
    def frozen(parent_deadline=None, parent_code='parent_cap_exhausted'):
        check = lambda: cooperative_checkpoint(awake, deadline, args.deadline_unix,
                                               parent_deadline, parent_code)
        check()
        guard(manifest, path, manifest_sha, deployment, checkpoint=check)
        check()
    frozen()
    modules = {k: imported('_repair4_'+k, local(v)) for k, v in LIBS.items()}
    owner, processes = modules['owner'], modules['processes']
    previous_extras = manifest.get('extra_predecessor_receipts', [])
    previous_terminal = manifest['terminal_predecessor_receipts']
    predecessor(owner, extra_receipts=previous_extras, terminal_receipts=previous_terminal)
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
        new_common_limit_seconds=COMMON, independent_new_campaign=True, previous_t5_failure_preserved=True,
        repaired_harness_classification_min_parent_seconds=CLASS_MIN, owned_root=dict(pid=os.getpid(), create_time=psutil.Process().create_time()),
        coordinator_bootstrap_identities=bootstraps, tasks=[], gates=[], supervisors=[], active_supervisor=None,
        cleanup_confirmed=False, source_unchanged=False, qualification=None,
        qualified_four_stage_both_tasks=False, independent_audit=None, quality_gain=None,
        promotion=False, submit=False, root_actual_exec_qualification='pending', awake_guard=awake.record,
        error_history=[], _manifest=manifest,
        _pulse=lambda: cooperative_checkpoint(awake, deadline, args.deadline_unix), _deployment=deployment)
    def persist(): save(output/'campaign.json', {k: v for k, v in state.items() if not k.startswith('_')})
    finished = set()
    final_deadline = None
    with modules['lock'].ResearchLock(WORK/'alfa-hack-automl/test-runs/.owned-research.lock') as lock:
        lock.write_identity(state['owned_root']); predecessor(owner, extra_receipts=previous_extras, terminal_receipts=previous_terminal); frozen(); clock(deadline, args.deadline_unix)
        output.mkdir(); (output/'g').mkdir()
        plan = copy.deepcopy(manifest['verification_plan_template'])
        plan.update(execution_manifest_sha256=manifest_sha, original_absolute_deadline_unix=args.deadline_unix)
        save(output/'verification-plan.json', plan, True)
        state['verification_plan_sha256'] = sha(output/'verification-plan.json')
        deployment['t7/verification-plan.json'] = state['verification_plan_sha256']
        substitutions = dict(python=sys.executable, work=str(WORK), output=str(output),
            manifest=relative(path), deadline_unix=repr(args.deadline_unix), verification_plan='t7/verification-plan.json')
        def interrupted(signum, frame): raise SystemExit(128+signum)
        previous = {s: signal.signal(s, interrupted) for s in [signal.SIGINT, signal.SIGTERM]}
        persist()
        try:
            need([g['name'] for g in manifest['gates']] == ['source', 'exact'], 'required_gate_order_changed')
            for index, cfg in enumerate(manifest['gates']):
                tick = time.monotonic(); cap = [600, 180][index]
                reserve = sum([600, 180][index:])+REG_PARENT+CLASS_MIN+FINAL
                predecessor(owner, finished, previous_extras, previous_terminal)
                sup = supervise(command(cfg, substitutions), local(cfg['cwd']), output/'g'/(cfg['name']+'-supervisor.json'),
                    cfg['name'], tick, cap, cap-CLEANUP, deadline, args.deadline_unix, reserve,
                    state, persist, frozen, owner, processes, bootstraps)
                child_errors(state, sup)
                need(sup['status'] == 'ok' and sup['cleanup_confirmed'], 'mandatory_technical_gate_failed')
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
                state['gates'].append(dict(name=cfg['name'], supervisor=sup, fresh_changed_adapter_gate=True, result_sha256=sha(local(cfg['result']))))
                persist(); need(time.monotonic() < tick+cap, 'gate_terminal_parent_over_cap')
            need([(t['kind'], t['code']) for t in manifest['tasks']]
                 == [('regression', 'r'), ('classification', 'c')], 'two_task_order_and_paths_required')
            need(type(manifest.get('maximum_experiments')) is int and manifest['maximum_experiments'] == 9, 'exact9_outer_experiments_required')
            state['status'] = 'running'; persist()
            for index, task in enumerate(manifest['tasks']):
                tick = time.monotonic(); clock(deadline, args.deadline_unix)
                reserve = CLASS_MIN+FINAL if index == 0 else FINAL
                cap = REG_PARENT if index == 0 else min(CLASS_MAX, int(deadline-tick-FINAL-2))
                need(cap >= (REG_PARENT if index == 0 else CLASS_MIN), 'minimum_task_allocation_unavailable')
                need(deadline-tick >= cap+reserve, 'task_common_reservation_unavailable')
                predecessor(owner, finished, previous_extras, previous_terminal)
                directory = output/task['code']; materialize(task, directory, manifest, deployment)
                seconds = cap-TASK_AUDIT-CLEANUP
                hpo = 900 if index == 0 else 2100
                argv = [sys.executable, '-B', '-X', 'utf8', '-u', 'solution.py', 'task.md',
                    '--four-stage', '--preserve-anchor', '--protect-original-features',
                    '--control-recipe', 'protected_control.json',
                    '--max-experiments', '9',
                    '--max-planner-calls', '2', '--max-llm-calls', '4', '--hpo-trials', '8',
                    '--hpo-budget', str(hpo), '--feature-selection-top-k', '32', '--planner-mode', 'staged',
                    '--run-name', 'repair4', '--time-budget', str(seconds)]
                sup = supervise(argv, directory, directory/'supervisor.json', task['kind'], tick,
                    cap-TASK_AUDIT, seconds, deadline, args.deadline_unix, cap+reserve,
                    state, persist, frozen, owner, processes, bootstraps, seconds, hpo)
                child_errors(state, sup)
                finished |= identities(sup['owned_process_identities'])
                need(sup['status'] != 'technical_failure' and sup['cleanup_confirmed'], 'task_technical_failure')
                task_check = lambda: cooperative_checkpoint(awake, deadline, args.deadline_unix,
                    tick+cap, 'task_metadata_seal_over_parent_cap')
                frozen(tick+cap, 'task_metadata_seal_over_parent_cap')
                proof = task_proof(directory, checkpoint=task_check)
                sealed = core_seal(directory, checkpoint=task_check)
                seal_path = output/(task['code']+'-seal.json')
                task_check()
                save(seal_path, dict(files_sha256=sealed, cleanup_confirmed=True, source_unchanged=True), True)
                task_check()
                entry = dict(sup, kind=task['kind'], code=task['code'], allocated_parent_seconds=cap,
                    solver_budget_seconds=seconds, proof=proof, qualified=False,
                    supervisor_path=relative(directory/'supervisor.json'), supervisor_sha256=sha(directory/'supervisor.json', task_check),
                    seal=dict(path=relative(seal_path), sha256=sha(seal_path, task_check)), seconds_including_verification=time.monotonic()-tick)
                state['tasks'].append(entry); frozen(tick+cap, 'task_metadata_seal_over_parent_cap'); persist(); task_check()
                need(time.monotonic() < tick+cap, 'task_metadata_seal_over_parent_cap')
            tick = time.monotonic()
            final_deadline = tick+FINAL
            need(deadline-tick >= FINAL, 'final_independent_audit_reserve_unavailable')
            frozen(); predecessor(owner, finished, previous_extras, previous_terminal)
            state.update(status='verifying', cleanup_confirmed=True, source_unchanged=True)
            persist()
            cfg = manifest['final_audit']
            sup = supervise(command(cfg, substitutions), local(cfg.get('cwd', '.')), output/'final-audit-supervisor.json',
                'final-audit', tick, FINAL, FINAL-CLEANUP, deadline, args.deadline_unix, FINAL,
                state, persist, frozen, owner, processes, bootstraps)
            child_errors(state, sup)
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
            invalidate(state); error(state, str(exc) if isinstance(exc, TechnicalFailure) else 'coordinator_operation_failed', 'coordinator', exc)
            state.update(exception_type=type(exc).__name__,
                os_errno=getattr(exc, 'errno', None), os_winerror=getattr(exc, 'winerror', None),
                failure_file=Path(exc.filename).name if getattr(exc, 'filename', None) else None)
        finally:
            try:
                frozen(); predecessor(owner, finished, previous_extras, previous_terminal)
                for entry in state['tasks']:
                    receipt = local(entry['seal']['path'])
                    need(sha(receipt) == entry['seal']['sha256'], 'late_seal_receipt_changed')
                    final_check = lambda: cooperative_checkpoint(awake, deadline, args.deadline_unix,
                        final_deadline, 'final_audit_terminal_cleanup_over_cap')
                    need(load(receipt)['files_sha256'] == core_seal(output/entry['code'], checkpoint=final_check), 'late_core_artifact_changed')
                need(all(r['cleanup_confirmed'] is True for r in state['supervisors']),
                     'prior_supervisor_cleanup_unknown')
                state.update(cleanup_confirmed=True, source_unchanged=True)
                clock(deadline, args.deadline_unix)
                need(final_deadline is None or time.monotonic() < final_deadline,
                     'final_audit_terminal_cleanup_over_cap')
            except BaseException as exc:
                invalidate(state); error(state, str(exc) if isinstance(exc, TechnicalFailure) else 'terminal_cleanup_or_source_failed', 'coordinator_terminal', exc)
                state.update(cleanup_confirmed=False, source_unchanged=False, terminal_exception=type(exc).__name__)
            state.update(finished_unix=time.time(), finished_monotonic=time.monotonic(),
                elapsed_common_seconds=time.monotonic()-(deadline-COMMON))
            persist()
            if time.monotonic() >= deadline or time.time() >= args.deadline_unix or (
                    final_deadline is not None and time.monotonic() >= final_deadline):
                invalidate(state); error(state, 'terminal_campaign_write_over_common_cap', 'campaign_write'); persist()
            for sig, handler in previous.items(): signal.signal(sig, handler)
    state['_final_deadline'] = final_deadline
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
    need(path == WORK/'m4packet/manifest.json' and sha(path) == args.manifest_sha256, 'explicit_m3_manifest_sha_required')
    manifest = load(path)
    if not args.launch:
        print(json.dumps(dict(status='inspect_only', clock_assigned=False, fits=0, API_calls=0)))
        return
    need(sha(local(AWAKE)) == AWAKE_SHA and manifest['immutable_files'].get(AWAKE) == AWAKE_SHA, 'awake_guard_not_bound')
    awake = imported('_lean_awake', local(AWAKE)).PowerRequestGuard('Alfa AutoML t7 supervised research pid'+str(os.getpid()), 10)
    result = None
    try:
        with awake:
            result = run(args, manifest, path, args.manifest_sha256, awake)
    except BaseException as exc:
        if result is None:
            raise
        invalidate(result); error(result, 'power_request_release_failed', 'power_guard_terminal', exc)
    if result is not None:
        result['awake_guard'] = awake.record
        try:
            need(awake.record.get('release_API_verified') is True, 'power_request_release_unverified')
            def post_release_check():
                last_sample = awake.record['last_heartbeat']
                need(max(time.time()-last_sample['unix'], time.monotonic()-last_sample['monotonic']) <= 10,
                     'terminal_host_heartbeat_gap_over10s')
                clock(result['common_deadline_monotonic'], args.deadline_unix)
                need(result['_final_deadline'] is None or time.monotonic() < result['_final_deadline'],
                     'final_audit_power_release_over_cap')
            guard(manifest, path, args.manifest_sha256, result['_deployment'], checkpoint=post_release_check)
            last = awake.record['last_heartbeat']
            result['terminal_power_heartbeat_gap'] = dict(wall_seconds=time.time()-last['unix'],
                monotonic_seconds=time.monotonic()-last['monotonic'])
            need(max(result['terminal_power_heartbeat_gap'].values()) <= 10, 'terminal_host_heartbeat_gap_over10s')
            clock(result['common_deadline_monotonic'], args.deadline_unix)
            need(result['_final_deadline'] is None or time.monotonic() < result['_final_deadline'], 'final_audit_power_release_over_cap')
        except BaseException as exc:
            invalidate(result); error(result, str(exc) if isinstance(exc, TechnicalFailure) else 'post_power_source_or_clock_failed', 'after_power_release', exc)
        result.update(finished_unix=time.time(), finished_monotonic=time.monotonic(),
            elapsed_common_seconds=time.time()-args.common_start_unix)
        destination=WORK/'t7/campaign.json'
        save(destination, {k:v for k,v in result.items() if not k.startswith('_')})
        if time.time() >= args.deadline_unix or (result['_final_deadline'] is not None and time.monotonic() >= result['_final_deadline']):
            invalidate(result); error(result, 'terminal_power_receipt_over_cap', 'power_receipt')
            save(destination, {k:v for k,v in result.items() if not k.startswith('_')})
    print(json.dumps({k: result[k] for k in ['status', 'qualification', 'cleanup_confirmed', 'elapsed_common_seconds']}))
    raise SystemExit(0 if result['status'] == 'completed_repaired_MVP' and result['cleanup_confirmed'] else 1)

if __name__ == '__main__':
    main()
