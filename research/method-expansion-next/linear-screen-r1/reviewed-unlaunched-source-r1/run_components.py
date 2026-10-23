"""METH02: ten fixed component jobs on five existing cuts, one future10800s clock.

No model/pipeline source change; reuse archive1612039 and standalone43be supervisor.
Source preparation does not create jobs, parse fitting data, or assign a clock.
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
import sys
import time
import zipfile

sys.dont_write_bytecode = True
WORK = Path(__file__).resolve().parents[1]
ROOT = WORK/'meth02'
BASE = ('m4packet/manifest.json', '8faf33cd81c0e864bcf338828c34447000111eda85bc719b8f43312d2babae9a')
COOR = ('run_lean_mvp_r2.py', '43be86ece6c453641afdcc6f8eccef02d713986e2ac8bf3314756f0bb78e0818')
R4 = ('repaired-mvp-r1-dev/evaluator_r4.py', 'c08e9f0be13a708d67b3266518381d6f1be3b0f43c384ef6425634160d7e2783')
REGISTRATION = ('method-linear-next-dev/registered-METH02.json', '9573629c1decf7ad3c29d879f3489778ce70d471ca0a57b065c360b9b78a045e')
PROTOCOL = ('method-linear-next-dev/protocol.json', '07e29fa8c3e3adb43fac51a3204ea6b7b94bdaeb427f261bfc9fb4e16630b56e')
AUDITOR = 'method-linear-next-dev/audit_components.py'
SPECS = {'regression': ('t7/r/automl_runs/repair4/task_spec.json', 'e8306fe48200d2cfbdf040e68159bd1ceeb505c61363a4302639b9c637368f4f'),
         'classification': ('t7/c/automl_runs/repair4/task_spec.json', '76a50236a9a8b8733c69e3bba3922448bd8b19b19a24e1aafdec6a7daab53b50')}
CUTS = [
    ('regression', 0, '5c72db2a788262cfe52ba9c0c51a8b3a20e90875279e39cb96101c052cc40c84'),
    ('regression', 1, 'e877869cb58f530a7bc73ad1e4cbc7d941fbb8bf6e7b42415f1a73608378fc8b'),
    ('regression', 2, '60ccdf913bfda8c1d7feaed8cd18c104d785caa2a40b8c5372f447d179a53fcc'),
    ('classification', 42, 'e16a563499871e19227ba700425045bc14eb853615c420defd6277d0a963b2a0'),
    ('classification', 43, 'd4d278eebfeebba90e3441854a4342def29ad57d704bdaff8dd226b66aa206df')]
COMMON, SETUP, PARENT, CHILD, AUDIT, CLEANUP, SPARE = 10800, 900, 600, 570, 600, 300, 3000
FIXED = dict(engine='linear_text', feature_code='', params=dict(generic_features='none'))
FIXTURES = ('method-linear-next-dev/test_tabular_linear_contracts.py', 'b6a7e541fbf6cad97956846d23b9ce8ce7b62a56a4509d3e2a5bc76e97ebe814')
METH01_PROOF = ('meth01/terminal-root-closure.json', '2c67361da8f95875b35d124ac6c19d6cccba28c899f1e20dada88f3bec4ea283')
FAILURE = RuntimeError
PAIR_PROOF = ('cp1/terminal-root-closure.json','96f5d956fa235cfd0904d55f67aeeaae8c93a083391fe8b370836f6e39ba309d')
T7_PROOF = ('m4packet/terminal-root-closure.json','d19648a53253c0b070fe12068d6eafef5569e2d51332d9b212ef44cc828b9ddc')
HISTORY_PROOF = ('method-update-publication-closure-r1.json','93bd05d3ff741eadf9bfc8858c875e8c130ec2aadc216c77e9480283b2692030')
REUSED_GATES = {
    't7/g/source/results.json':'dc5d07a7b5961685fe5a5f54f076a93e5965d1976279dea489f82f193f5897f0',
    't7/g/exact.json':'92c9a550a5945ff58b98356cafa9068dbbc54cc5ee8e4429c15355586df2eca2',
    't7/g/source-supervisor.json':'bc39180bd4c2a7be32db4f3cbc7c9b85f6117b6d97a126201d1d973f2b436a12',
    't7/g/exact-supervisor.json':'268ef32bb2bf36d2c124181d7f2246bae82cb4885690d514c16c4a1ed02a0d54',
    't7/campaign.json':'f72e7dc8b7094b8689e5ac37c1dbc77a2ed9963eada470f5be95da3e3a89e6b1'}


def need(value, code):
    if not value: raise FAILURE(code)


def local(name):
    p = (WORK/name).resolve()
    need(not Path(name).is_absolute() and p.is_relative_to(WORK), 'reference_outside_work')
    return p


def sha(path, check=None):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            if check is not None: check()
            block = stream.read(2**20)
            if not block: break
            h.update(block)
    if check is not None: check()
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text('utf-8'))


def imported(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def split_source(kind, cut):
    return f'alfa-hack-automl/test-runs/2e/fe-{kind}/control_historical/seed-{cut}/split.npz'


def main():
    global FAILURE
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--launch', action='store_true', required=True)
    for name in ['self-sha256', 'auditor-sha256', 'pair-root-closure', 'pair-root-closure-sha256',
                 'method01-root-closure', 'method01-root-closure-sha256']:
        p.add_argument('--'+name, required=True)
    p.add_argument('--pair-exec-session', type=int, required=True)
    p.add_argument('--pair-exit-code', type=int, required=True)
    p.add_argument('--method01-exec-session', type=int, required=True)
    p.add_argument('--method01-exit-code', type=int, required=True)
    p.add_argument('--bootstrap-launcher'); p.add_argument('--bootstrap-launcher-sha256')
    p.add_argument('--extra-terminal-receipt', action='append', default=[], metavar='WORK_REL_PATH=SHA256')
    args = p.parse_args()
    need(__debug__ and not ROOT.exists(), 'new_nonoptimized_component_run_required_no_retry')
    start_unix, start_mono = time.time(), time.monotonic()
    unix, deadline = start_unix+COMMON, start_mono+COMMON
    ROOT.mkdir()
    import psutil
    state = dict(status='starting', start_unix=start_unix, start_monotonic=start_mono,
        absolute_deadline_unix=unix, common_deadline_monotonic=deadline, common_seconds=COMMON,
        allocations=dict(setup_source_exact_and_contracts=SETUP, ten_workers=10*PARENT, independent_audit=AUDIT, cleanup_export=CLEANUP, unused_spare_not_reinvested=SPARE),
        owned_root=dict(pid=os.getpid(), create_time=psutil.Process().create_time()),
        coordinator_bootstrap_identities=[], supervisors=[], active_supervisor=None,
        gates=[], workers=[], error_history=[], cleanup_confirmed=False, source_unchanged=False,
        component_procedure_passed=False, component_quality_gates_passed=None, quality_metric=None, independent_audit=None,
        root_actual_exec_qualification='pending_root_observed_actual_exec_and_fresh_closure',
        promotion=False, submit=False, official_score=None,
        scope='Fixed component screen on five reused public cuts; no full refit, tuning, blend or whole-agent promotion')
    coor = owner = awake = None
    pins, deployment, known, finished = {}, {}, set(), set()
    manifest_path, plan_path = ROOT/'manifest.json', ROOT/'verification-plan.json'
    def persist():
        data = {k:v for k,v in state.items() if not k.startswith('_')}
        if coor is None:
            with (ROOT/'campaign.json').open('x', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
        else: coor.save(ROOT/'campaign.json', data)
    def error(exc, phase):
        message = str(exc)
        row = dict(code=message if isinstance(exc, RuntimeError) and re.fullmatch('[A-Za-z0-9_:+.-]{1,200}', message)
            else 'component_'+type(exc).__name__, phase=phase, exception_type=type(exc).__name__,
            unix=time.time(), monotonic=time.monotonic(), errno=getattr(exc,'errno',None), winerror=getattr(exc,'winerror',None))
        state.setdefault('first_failure', row); state['error_history'].append(row)
        state.update(status='technical_failure', component_procedure_passed=False, component_quality_gates_passed=None, quality_metric=None)
    def checkpoint(end=None, code='component_parent_cap_exhausted'):
        if awake is not None and awake.handle is not None:
            coor.cooperative_checkpoint(awake, deadline, unix, end, code)
        else:
            need(time.monotonic() < deadline and time.time() < unix, 'component_common_clock_exhausted')
            need(abs((deadline-time.monotonic())-(unix-time.time())) <= 5, 'wall_monotonic_clock_disagreement')
            if end is not None: need(time.monotonic() < end, code)
            if awake is not None and awake.record.get('last_heartbeat'):
                last=awake.record['last_heartbeat']
                need(max(time.time()-last['unix'],time.monotonic()-last['monotonic'])<=10,'terminal_host_heartbeat_gap_over10s')
        rss = psutil.Process().memory_info().rss
        for saved in state['coordinator_bootstrap_identities']:
            try:
                proc = psutil.Process(saved['pid'])
                if proc.create_time() == saved['create_time']: rss += proc.memory_info().rss
            except psutil.NoSuchProcess: pass
        need(rss <= 2*2**30, 'component_parent_bootstrap_memory_limit')
    def frozen(end=None, code='component_parent_cap_exhausted'):
        check = lambda: checkpoint(end, code)
        for name, digest in {**pins, **deployment}.items():
            need(sha(local(name), check) == digest, 'frozen_source_input_job_split_or_core_changed')
        check()
    def merge(name, digest):
        local(name)
        need(isinstance(digest,str) and re.fullmatch('[0-9a-f]{64}', digest), 'invalid_sha256')
        need(name not in pins or pins[name] == digest, 'conflicting_pin')
        pins[name] = digest
    def absence():
        history = coor.predecessor(owner, finished, base.get('extra_predecessor_receipts', []), base['terminal_predecessor_receipts'])
        known.update(coor.identities(history))
        observer = owner.StrictOwnedObserver(); observer.remember(known | finished)
        need(not observer.observe() and not observer.denials and not observer.final_check()['unresolved'],
             'closed_predecessor_or_prior_worker_live_or_denied')
        state['fresh_predecessor_identity_count'] = len(observer.seen)
    def seal(directory, check):
        result = {}
        for parent, dirs, files in os.walk(directory):
            need(not any((Path(parent)/n).is_symlink() for n in [*dirs,*files]), 'worker_core_symlink')
            for name in files:
                need(not name.endswith(('.pending','.tmp')), 'unfinished_worker_core')
                path = Path(parent)/name; result[path.relative_to(WORK).as_posix()] = sha(path, check)
        return result
    final_end = None
    try:
        setup_end = start_mono+SETUP
        check = lambda: checkpoint(setup_end, 'component_setup_cap_exhausted')
        explicit = dict([BASE, COOR, R4, REGISTRATION, PROTOCOL, FIXTURES, *SPECS.values()])
        explicit[Path(__file__).resolve().relative_to(WORK).as_posix()] = args.self_sha256
        explicit[AUDITOR] = args.auditor_sha256
        for name, digest in explicit.items():
            need(sha(local(name), check) == digest, 'explicit_component_source_pin_failed'); merge(name,digest)
        coor = imported('_component_proven_coordinator', local(COOR[0])); FAILURE = coor.TechnicalFailure
        base = load(local(BASE[0]))
        need(base['source_root'] == 'm3dev' and base['archive_sha256'] == '16120391716fe43b7f0ec2b36f35eaea7511a08cba4f4108da01cd81dea314d0'
             and len(base['compiled_sha256']) == 68 and sum(base['registry'].values()) == 458, 'unchanged_native_no_text_linear_source_required')
        for name, digest in base['immutable_files'].items(): merge(name,digest)
        for name in [*coor.LIBS.values(), coor.AWAKE]: need(name in pins, 'runtime_helper_unbound')
        need(bool(args.bootstrap_launcher) == bool(args.bootstrap_launcher_sha256), 'paired_bootstrap_pin_required')
        if args.bootstrap_launcher: merge(args.bootstrap_launcher, args.bootstrap_launcher_sha256)
        for kind, cut, digest in CUTS: merge(split_source(kind,cut),digest)
        for name,digest in REUSED_GATES.items():merge(name,digest)
        refs = [(args.pair_root_closure,args.pair_root_closure_sha256),T7_PROOF,HISTORY_PROOF]
        refs += [tuple(v.rsplit('=',1)) for v in args.extra_terminal_receipt]
        need((args.pair_root_closure,args.pair_root_closure_sha256)==PAIR_PROOF
             and args.pair_exec_session==43472 and args.pair_exit_code==0, 'actual_pair_root_closure_required')
        for index,(name,digest) in enumerate(refs):
            need(sha(local(name),check) == digest, 'terminal_proof_pin_failed'); proof = load(local(name))
            need(proof.get('cleanup_confirmed') is True and proof.get('source_unchanged') is True
                 and proof.get('active_owned_processes',[]) == [] and proof.get('uncertain_owned',[]) == []
                 and proof.get('owned_identities') and proof.get('closure_preparer_identities'), 'terminal_cleanup_source_unknown')
            if index == 0:
                need(proof.get('actual_exec_session') == args.pair_exec_session
                     and proof.get('actual_exec_exit_code_observed_by_root') == args.pair_exit_code
                     and proof.get('original_common_seconds') == 5400, 'actual_pair_terminal_exec_binding_failed')
            known.update(coor.identities(proof['owned_identities'])); known.update(coor.identities(proof['closure_preparer_identities']))
            merge(name,digest)
        need((args.method01_root_closure,args.method01_root_closure_sha256)==METH01_PROOF
             and args.method01_exec_session==3417,'actual_METH01_terminal_reference_required')
        need(sha(local(args.method01_root_closure),check)==args.method01_root_closure_sha256,'actual_METH01_terminal_proof_pin_failed')
        proof=load(local(args.method01_root_closure))
        need(proof.get('cleanup_confirmed') is True and proof.get('source_unchanged') is True
             and proof.get('active_owned_processes')==[] and proof.get('uncertain_owned')==[]
             and proof.get('owned_identities') and proof.get('closure_preparer_identities')
             and proof.get('actual_exec_session')==args.method01_exec_session
             and proof.get('actual_exec_exit_code_observed_by_root')==args.method01_exit_code
             and proof.get('original_common_seconds')==6600,'actual_METH01_terminal_cleanup_lineage_required')
        prior_path='meth01/campaign.json';prior=load(local(prior_path))
        need(prior.get('finished_unix') is not None and prior.get('finished_monotonic') is not None
             and prior['finished_unix']<=start_unix and prior['finished_monotonic']<=start_mono
             and prior['start_unix']==proof['original_start_unix']
             and prior['absolute_deadline_unix']==proof['original_deadline_unix']
             and prior['elapsed_common_seconds']==proof['raw_parent_elapsed_seconds']
             and prior['cleanup_confirmed'] is True and prior['source_unchanged'] is True,
             'actual_METH01_terminal_campaign_binding_required')
        known.update(coor.identities(proof['owned_identities']))
        known.update(coor.identities(proof['closure_preparer_identities']))
        merge(args.method01_root_closure,args.method01_root_closure_sha256);merge(prior_path,sha(local(prior_path),check))
        prior_reference=dict(path=args.method01_root_closure,sha256=args.method01_root_closure_sha256,
            campaign_path=prior_path,campaign_sha256=pins[prior_path],actual_exec_session=args.method01_exec_session,
            actual_exec_exit_code_observed_by_root=args.method01_exit_code,quality_success_required=False)
        state['completed_METH01_predecessor']=prior_reference
        frozen(setup_end,'component_setup_cap_exhausted')
        owner = imported('_component_owner',local(coor.LIBS['owner']))
        processes = imported('_component_processes',local(coor.LIBS['processes']))
        locker = imported('_component_lock',local(coor.LIBS['lock']))
        awake = imported('_component_awake',local(coor.AWAKE)).PowerRequestGuard('Alfa METH02 pid'+str(os.getpid()),10)
        parent = psutil.Process().parent(); own_paths = {Path(__file__).resolve()}
        if args.bootstrap_launcher: own_paths.add(local(args.bootstrap_launcher))
        while parent is not None:
            birth = parent.create_time()
            if not any(Path(v).resolve() in own_paths for v in parent.cmdline() if not v.startswith('-')): break
            need(parent.create_time() == birth,'bootstrap_identity_changed')
            state['coordinator_bootstrap_identities'].append(dict(pid=parent.pid,create_time=birth)); parent=parent.parent()
        state.update(_manifest=base,_pulse=lambda:checkpoint(),awake_guard=awake.record)
        state['completed_pair_predecessor']=dict(path=PAIR_PROOF[0],sha256=PAIR_PROOF[1],actual_exec_session=43472,
            actual_exec_exit_code_observed_by_root=0)
        with awake:
            absence(); frozen(setup_end,'component_setup_cap_exhausted')
            with locker.ResearchLock(WORK/'alfa-hack-automl/test-runs/.owned-research.lock') as lock:
                lock.write_identity(state['owned_root']); absence()
                (ROOT/'g').mkdir(); (ROOT/'sources').mkdir(); (ROOT/'supervisors').mkdir()
                with zipfile.ZipFile(local(base['archive'])) as z:
                    need(len(z.namelist()) == 68 and set(z.namelist()) == set(base['compiled_sha256']), 'exact_flat_archive_inventory_required')
                    for name,digest in base['compiled_sha256'].items():
                        need(Path(name).name == name,'flat_archive_required')
                        target=ROOT/'sources'/name; target.write_bytes(z.read(name))
                        need(sha(target,check) == digest,'flat_archive_copy_changed'); deployment[coor.relative(target)]=digest
                tasks, jobs = {}, []
                for task in base['tasks']:
                    kind, code = task['kind'], task['code']; directory=ROOT/code; directory.mkdir()
                    for name,digest in task['files'].items():
                        target=directory/name; shutil.copyfile(local(task['source'])/name,target)
                        need(sha(target,check) == digest,'pristine_copy_changed'); deployment[coor.relative(target)]=digest
                    original=load(local(SPECS[kind][0])); spec=copy.deepcopy(original)
                    spec.update(root=str(directory),task_path=str(directory/'task.md'),
                        paths={key:str(directory/Path(value).name) for key,value in original['paths'].items()})
                    need(spec['kind'] == kind and not spec.get('text_features') and spec['metric'] == ('rmse' if code=='r' else 'macro_f1'), 'ordinary_component_task_required')
                    control=load(local(task['control_recipe']['path']))['components'][0]
                    path=directory/'task_spec.json';coor.save(path,spec,True);deployment[coor.relative(path)]=sha(path,check)
                    tasks[kind]=dict(task,spec_path=coor.relative(path),spec_sha256=deployment[coor.relative(path)],component_control=control)
                for kind,cut,digest in CUTS:
                    code=tasks[kind]['code']; partition=ROOT/code/f'split-{cut}.npz'
                    shutil.copyfile(local(split_source(kind,cut)),partition)
                    need(sha(partition,check)==digest,'existing_ordered_split_copy_changed');deployment[coor.relative(partition)]=digest
                    for arm in ['control','candidate']:
                        key=f'{kind}{cut}-{arm}'; directory=ROOT/code/key;directory.mkdir()
                        recipe=copy.deepcopy(tasks[kind]['component_control'] if arm=='control' else FIXED)
                        if arm=='candidate' and kind=='classification': recipe['params'].update(text_classifier='logistic',text_C=1,class_weight_power=.5)
                        job=dict(spec=load(local(tasks[kind]['spec_path'])),recipe=recipe,output_dir=str(directory),
                            split_path=str(partition),threads=2,full_fit=False)
                        path=directory/'job.json';coor.save(path,job,True);digest_job=sha(path,check);deployment[coor.relative(path)]=digest_job
                        jobs.append(dict(key=key,kind=kind,cut=cut,arm=arm,job_path=coor.relative(path),job_sha256=digest_job,
                            output_dir=coor.relative(directory),split_path=coor.relative(partition),split_sha256=digest,recipe=recipe))
                manifest=dict(schema='METH02-component-v1',common_seconds=COMMON,immutable_files=dict(pins),
                    setup_deployment_sha256=dict(deployment),source_root='m3dev',archive=base['archive'],archive_sha256=base['archive_sha256'],
                    compiled_sha256=base['compiled_sha256'],registry=base['registry'],tasks=tasks,jobs=jobs,
                    completed_METH01_predecessor=prior_reference,tool_contract_source=dict(path=FIXTURES[0],sha256=FIXTURES[1]),
                    per_worker_parent_seconds=PARENT,per_worker_child_seconds=CHILD,threads=2,BLAS_threads=1,
                    worker_memory_gib=1.5,whole_tree_memory_gib=2,refit=False,API_calls=0,
                    interpreter_path=sys.executable,interpreter_sha256=sha(sys.executable,check),interpreter_version=sys.version)
                coor.save(manifest_path,manifest,True);state['manifest_sha256']=sha(manifest_path,check)
                plan=dict(schema='METH02-component-audit-v1',verifier_source_sha256=args.auditor_sha256,
                    manual_metric_verifier_path=R4[0],manual_metric_verifier_sha256=R4[1],
                    execution_manifest_sha256=state['manifest_sha256'],original_common_start_unix=start_unix,
                    original_absolute_deadline_unix=unix,common_seconds=COMMON,ordered_jobs=[j['key'] for j in jobs],
                    reproduction_absolute_tolerance=1e-10,failed_metrics_zero_imputed=False,promotion=False,
                    quality_gate_policy=dict(regression='strict_RMSE_improvement_on_all_three_cuts',
                        classification='both_MacroF1_improve_and_supported_class_and_ex_rarest_gates',
                        supported_independent_groups_min=100,maximum_supported_class_drop=.01,
                        class_drop_tolerance=1e-12,ex_rarest_gain_strictly_positive=True,
                        failed_or_null_cut_gate=False,full_refit_or_promotion=False))
                coor.save(plan_path,plan,True);state['verification_plan_sha256']=sha(plan_path,check)
                deployment[coor.relative(manifest_path)]=state['manifest_sha256'];deployment[coor.relative(plan_path)]=state['verification_plan_sha256']
                previous={s:signal.signal(s,lambda n,f:(_ for _ in ()).throw(SystemExit(128+n))) for s in [signal.SIGINT,signal.SIGTERM]}
                persist()
                try:
                    historical=load(local('t7/campaign.json'));t7=load(local(T7_PROOF[0]))
                    need(historical['manifest_sha256']==BASE[1] and historical['cleanup_confirmed'] is True
                         and historical['source_unchanged'] is True and t7['actual_exec_session']==65008
                         and t7['actual_exec_exit_code_observed_by_root']==0,'reused_T7_gate_terminal_lineage_required')
                    for index,name in enumerate(['source','exact']):
                        receipt=local('t7/g/'+name+'-supervisor.json');sup=load(receipt)
                        need(sup.get('status')=='ok' and sup.get('exit_code')==0 and sup.get('cleanup_confirmed') is True,'reused_gate_not_clean')
                        saved=next(g for g in historical['gates'] if g['name']==name)
                        need(saved['supervisor']==sup,'reused_gate_campaign_supervisor_changed')
                        result=local('t7/g/'+('source/results.json' if name=='source' else 'exact.json'));data=load(result)
                        need(sha(result,check)==saved['result_sha256'],'reused_gate_campaign_result_changed')
                        if index==0:
                            need(data.get('passed') is True and data.get('source_unchanged') is True and data.get('fixture_cleanup_confirmed') is True
                                 and data.get('unique_checks_passed')==458 and data.get('unique_checks_skipped')==0
                                 and data.get('source_sha256')==base['compiled_sha256'],'source458_no_skip_required')
                            rows={r['script']:r for r in data['checks']}
                            need(set(rows)==set(base['registry']) and all(rows[n]['passed'] is True and rows[n]['observed_checks']==c
                                 and rows[n]['skipped_checks']==0 for n,c in base['registry'].items()),'source_registry_coverage_changed')
                        else:
                            need(data.get('passed') is True and data.get('matches_current_source') is True and data.get('sha256')==base['archive_sha256'],'exact_archive_gate_failed')
                            rows=data['checks'];need([r['script'] for r in rows]==['test_v2.py','test_resilience.py','smoke.py'],'exact23_coverage_changed')
                            for row in rows:
                                text=row.get('stdout','')+'\n'+row.get('stderr','');need(row['exit_code']==0 and not re.search(r'\bskipped\s*=\s*[1-9]',text),'exact_failed_or_skipped')
                                if row['script']=='smoke.py':
                                    cases=json.loads(row['stdout']);need(len(cases)==5 and all(r['status']=='passed' for r in cases),'exact_smoke_incomplete')
                                else:
                                    counts=re.findall(r'Ran (\d+) tests? in ',text);need(counts and int(counts[-1])==base['registry'][row['script']],'exact_count_changed')
                        state['gates'].append(dict(name=name,evidence_mode='REUSED_T7_UNCHANGED_SOURCE_NOT_EXECUTED_AGAIN',
                            result_path=coor.relative(result),result_sha256=sha(result,check),supervisor_path=coor.relative(receipt),
                            supervisor_sha256=sha(receipt,check),supervisor=sup));persist()
                    # New tiny tool contracts consume a fixed300 parent WITHIN setup900.
                    tick=time.monotonic();need(setup_end-tick>=300,'linear_contract_full_setup_allocation_unavailable')
                    absence();result=ROOT/'g/linear-contracts.json';receipt=ROOT/'g/linear-contracts-supervisor.json'
                    command=[sys.executable,'-B','-X','utf8',str(local(FIXTURES[0])),
                        '--self-sha256',FIXTURES[1],'--output',str(result)]
                    sup=coor.supervise(command,WORK,receipt,'linear-contracts',tick,300,270,deadline,unix,
                        300+10*PARENT+AUDIT+CLEANUP,state,persist,frozen,owner,processes,
                        state['coordinator_bootstrap_identities'],solver_seconds=None)
                    coor.child_errors(state,sup);finished.update(coor.identities(sup.get('owned_process_identities',[])))
                    need(sup.get('status')=='ok' and sup.get('exit_code')==0 and sup.get('cleanup_confirmed') is True,
                         'linear_contract_process_failed')
                    check_contract=lambda:checkpoint(min(tick+300,setup_end),'linear_contract_setup_parent_exhausted')
                    data=load(result)
                    need(data.get('status')=='passed' and data.get('tests_run')==8 and data.get('errors')==0
                         and data.get('failures')==0 and data.get('skipped')==0 and data.get('tiny_fitting_callbacks')==10
                         and data.get('fixture_source_sha256')==FIXTURES[1] and data.get('public_data_used') is False
                         and data.get('API_calls')==0,'linear_tool_contracts_incomplete_or_failed')
                    need(start_unix<=sup['start_unix']<=sup['end_unix']<start_unix+SETUP
                         and start_mono<=sup['start_monotonic']
                         and sup['start_monotonic']+sup['seconds']<setup_end,'linear_contract_original_setup_clock_binding_failed')
                    state['gates'].append(dict(name='linear_contracts',evidence_mode='NEW_SYNTHETIC_LINEAR_TOOL_CONTRACTS',
                        result_path=coor.relative(result),result_sha256=sha(result,check_contract),
                        supervisor_path=coor.relative(receipt),supervisor_sha256=sha(receipt,check_contract),supervisor=sup))
                    deployment[coor.relative(result)]=sha(result,check_contract)
                    deployment[coor.relative(receipt)]=sha(receipt,check_contract);check_contract();persist()
                    state['technical_checks_newly_executed']=8
                    state['technical_gate_evidence']='Reused actual T7 source458/exact23; NEW8tiny linear contracts within setup900; all original bytes rehashed'
                    frozen(setup_end,'component_setup_cap_exhausted');state['setup_seconds']=time.monotonic()-start_mono
                    for index,job in enumerate(jobs):
                        tick=time.monotonic();future=(len(jobs)-index-1)*PARENT+AUDIT+CLEANUP
                        need(deadline-tick>=PARENT+future,'fixed_remaining_component_allocations_unavailable');absence()
                        state.update(status='running',active_job=job['key']);persist()
                        receipt=ROOT/'supervisors'/(job['key']+'.json')
                        command=[sys.executable,'-B','-X','utf8','-u',str(ROOT/'sources/automl_worker.py'),str(local(job['job_path']))]
                        sup=coor.supervise(command,ROOT/'sources',receipt,job['key'],tick,PARENT,CHILD,deadline,unix,PARENT+future,
                            state,persist,frozen,owner,processes,state['coordinator_bootstrap_identities'],solver_seconds=None)
                        coor.child_errors(state,sup)
                        finished.update(coor.identities(sup.get('owned_process_identities',[])))
                        need(sup.get('cleanup_confirmed') is True,'component_worker_cleanup_unknown')
                        ordinary={'ok','child_failed','timeout'}
                        local_oom=(sup.get('status')=='technical_failure' and sup.get('error_history')
                            and all(r.get('code')=='worker_subtree_memory_limit' for r in sup['error_history']))
                        need(sup.get('status') in ordinary or local_oom,'component_systemic_supervisor_failure')
                        check_job=lambda:checkpoint(tick+PARENT,'component_cleanup_seal_over600')
                        frozen(tick+PARENT,'component_cleanup_seal_over600');files=seal(local(job['output_dir']),check_job)
                        seal_path=ROOT/'supervisors'/(job['key']+'-seal.json')
                        coor.save(seal_path,dict(key=job['key'],files_sha256=files,cleanup_confirmed=True,source_unchanged=True,
                            sealed_before_independent_label_scoring=True),True)
                        entry=dict(sup,key=job['key'],supervisor_path=coor.relative(receipt),supervisor_sha256=sha(receipt,check_job),
                            seal=dict(path=coor.relative(seal_path),sha256=sha(seal_path,check_job)),metric=None,
                            measurement_status='pending_independent_component_audit',seconds_including_seal=time.monotonic()-tick)
                        deployment.update(files);deployment[entry['seal']['path']]=entry['seal']['sha256'];deployment[entry['supervisor_path']]=entry['supervisor_sha256']
                        state['workers'].append(entry);state['active_job']=None;persist();check_job()
                    tick=time.monotonic();need(deadline-tick>=AUDIT+CLEANUP,'component_audit_cleanup_reserve_unavailable');absence();frozen()
                    state.update(status='verifying',cleanup_confirmed=True,source_unchanged=True);persist()
                    command=[sys.executable,'-B','-X','utf8',str(local(AUDITOR)),'--work-root',str(WORK),
                        '--manifest','meth02/manifest.json','--manifest-sha256',state['manifest_sha256'],
                        '--plan','meth02/verification-plan.json','--plan-sha256',state['verification_plan_sha256'],
                        '--self-sha256',args.auditor_sha256,'--output','meth02/independent-audit.json']
                    sup=coor.supervise(command,WORK,ROOT/'audit-supervisor.json','component-audit',tick,AUDIT,AUDIT-30,
                        deadline,unix,AUDIT+CLEANUP,state,persist,frozen,owner,processes,state['coordinator_bootstrap_identities'])
                    coor.child_errors(state,sup)
                    finished.update(coor.identities(sup.get('owned_process_identities',[])))
                    need(sup.get('status')=='ok' and sup.get('exit_code')==0 and sup.get('cleanup_confirmed') is True,'component_auditor_process_failed')
                    audit=load(ROOT/'independent-audit.json');state['independent_audit']=dict(path='meth02/independent-audit.json',sha256=sha(ROOT/'independent-audit.json'),raw_result=audit)
                    need(audit.get('artifact_integrity_checks_passed') is True and audit.get('audit_within_original_common_clock') is True
                         and audit.get('parent_exec_terminal_qualification_required') is True,'component_saved_artifact_contract_failed')
                    state.update(status='completed_component_screen_pending_root_exec_and_closure',
                        component_procedure_passed=audit['all_workers_succeeded'],component_quality_gates_passed=audit['component_quality_gates_passed'],
                        quality_metric=audit['quality_metric'])
                except BaseException as exc: error(exc,'component_procedure')
                finally:
                    final_end=min(deadline-10,time.monotonic()+CLEANUP)
                    try:
                        frozen(final_end,'component_final_cleanup_over_cap');absence()
                        need(all(r['cleanup_confirmed'] is True for r in state['supervisors']),'prior_cleanup_unknown')
                        state.update(cleanup_confirmed=True,source_unchanged=True)
                    except BaseException as exc:
                        error(exc,'component_terminal');state.update(cleanup_confirmed=False,source_unchanged=False)
                    for sig,handler in previous.items():signal.signal(sig,handler)
        need(awake.record.get('release_API_verified') is True,'power_release_unverified')
        last=awake.record['last_heartbeat'];need(max(time.time()-last['unix'],time.monotonic()-last['monotonic'])<=10,'terminal_host_heartbeat_gap_over10s')
        frozen(final_end,'component_terminal_source_over_cap')
    except BaseException as exc: error(exc,'component_setup_or_power_terminal')
    finally:
        state.update(finished_unix=time.time(),finished_monotonic=time.monotonic(),elapsed_common_seconds=time.monotonic()-start_mono,
            owned_process_identities=[dict(pid=p,create_time=c) for p,c in sorted(finished)])
        if time.monotonic()>=min(deadline-10,final_end if final_end is not None else deadline) or time.time()>=unix-10:
            error(RuntimeError('component_terminal_export_over_cap'),'component_export')
        persist()
        try:checkpoint(final_end,'component_terminal_receipt_over_cap')
        except BaseException as exc:error(exc,'component_terminal_receipt');persist()
        if time.monotonic()>=min(deadline-10,final_end if final_end is not None else deadline):
            error(RuntimeError('component_terminal_receipt_write_over_cap'),'component_export');persist()
    print(json.dumps({k:state[k] for k in ['status','component_procedure_passed','cleanup_confirmed','source_unchanged','elapsed_common_seconds']}))
    raise SystemExit(0 if state['component_procedure_passed'] and state['cleanup_confirmed'] and state['source_unchanged'] and not state['error_history'] else 1)


if __name__ == '__main__': main()
