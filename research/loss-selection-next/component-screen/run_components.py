"""LOSS01: nine fixed loss-only jobs on three existing cuts, one future7200s clock.

No new model/pipeline source change; reuse qualified LOSSarchive037f88 and standalone43be supervisor.
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
ROOT = WORK/'loss01'
BASE = ('m4packet/manifest.json', '8faf33cd81c0e864bcf338828c34447000111eda85bc719b8f43312d2babae9a')
COOR = ('run_lean_mvp_r2.py', '43be86ece6c453641afdcc6f8eccef02d713986e2ac8bf3314756f0bb78e0818')
R4 = ('repaired-mvp-r1-dev/evaluator_r4.py', 'c08e9f0be13a708d67b3266518381d6f1be3b0f43c384ef6425634160d7e2783')
REGISTRATION = ('loss-selection-program/experiments.json','71f72c906e22a3d754e460b8cc5bbb6d4902650cb9c4e1de73e701207ff2f59e')
PROTOCOL = ('loss-components-next-dev/protocol.json','47ab4a7d21274c97797994a864f7403c675b17e40193d698207aded5747c1671')
AUDITOR = 'loss-components-next-dev/audit_components.py'
SPECS = {'regression': ('t7/r/automl_runs/repair4/task_spec.json','e8306fe48200d2cfbdf040e68159bd1ceeb505c61363a4302639b9c637368f4f')}
CUTS = [('regression',0,'5c72db2a788262cfe52ba9c0c51a8b3a20e90875279e39cb96101c052cc40c84'),
        ('regression',1,'e877869cb58f530a7bc73ad1e4cbc7d941fbb8bf6e7b42415f1a73608378fc8b'),
        ('regression',2,'60ccdf913bfda8c1d7feaed8cd18c104d785caa2a40b8c5372f447d179a53fcc')]
PROFILES=['lgbm_l2_v1','lgbm_l1_v1','lgbm_huber_a09_v1']
COMMON,SETUP,PARENT,CHILD,AUDIT,CLEANUP=7200,900,600,570,600,300
FAILURE=RuntimeError
LOSS_BASE=('loss-stage0-packet/manifest.json','319d6035162f46e6a1272a833d5f8668c731294b443eeae2dd8fc8c897dabfdc')
ARCHIVE_SHA='037f88de1d547a18ff63e300c81b4ecd9e36935d2ddc32a0ba3fe304b105439d'
LOSS00=('loss0/terminal-root-closure.json','c4916f2e7c7bd38e394bcb2ab33a51daf7a472a2aec8e08ff4b8a79a8fd5ba69')
HISTORY={
 'queue-checks/terminal-root-closure.json':('4006102127dd971c97843642754a748fc97199e20505c037f1688a80b8e12d27',None,1),
 'queue-checks-r2/terminal-root-closure.json':('887a4b82614ca18d4589102a9f385d513e96ff5562dcb56ca3d2f95b6a186c34',None,0),
 'meth03l/terminal-root-closure.json':('e02fd31162f1db27342895901ebb52764b140d59f9cd7651c9be447283bd3b9d',63424,0),
 'meth02b/terminal-root-closure.json':('fe00067cb099fdd4fdcd036861f5c3d55cd1c9ee0ee75bcddf488cfc035fe7f7',38041,0),
 'meth02/terminal-root-closure.json':('220e7c93f56eaa4a9c2e09ce70aa3ba406d864686cc68520bf69eace4ed75361',None,1),
 'meth03/terminal-root-closure.json':('901f3c928d95d992800aef808ff70f84768a456bc23235e0ae63fd539fe159bf',33253,0),
 'meth01/terminal-root-closure.json':('2c67361da8f95875b35d124ac6c19d6cccba28c899f1e20dada88f3bec4ea283',3417,0),
 'cp1/terminal-root-closure.json':('96f5d956fa235cfd0904d55f67aeeaae8c93a083391fe8b370836f6e39ba309d',43472,0),
 'cs0/terminal-root-closure.json':('06d20ce5b1bfd51ceefc924f8d09eb06b4022e9998bcef4d36343cb58669fba8',79591,0),
 'm4packet/terminal-root-closure.json':('d19648a53253c0b070fe12068d6eafef5569e2d51332d9b212ef44cc828b9ddc',65008,0)}
PUBLICATION={
 't7-report-publication-closure-r2.json':'154eca18b219f8c62ec79ec391da2b09fa59c891fcb444e96732e1c2f1afed20',
 'method-update-publication-closure-r1.json':'93bd05d3ff741eadf9bfc8858c875e8c130ec2aadc216c77e9480283b2692030'}


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
    for name in ['self-sha256','auditor-sha256','loss00-root-closure','loss00-root-closure-sha256']:
        p.add_argument('--'+name, required=True)
    p.add_argument('--loss00-exec-session',type=int,required=True)
    p.add_argument('--loss00-exit-code',type=int,required=True)
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
        allocations=dict(setup_reused_readiness=SETUP, nine_workers=9*PARENT, independent_audit=AUDIT, cleanup_export=CLEANUP),
        owned_root=dict(pid=os.getpid(), create_time=psutil.Process().create_time()),
        coordinator_bootstrap_identities=[], supervisors=[], active_supervisor=None,
        gates=[], workers=[], error_history=[], cleanup_confirmed=False, source_unchanged=False,
        component_procedure_passed=False, component_quality_gates_passed=None, quality_metric=None, independent_audit=None,
        root_actual_exec_qualification='pending_root_observed_actual_exec_and_fresh_closure',
        promotion=False, submit=False, official_score=None,
        scope='Fixed loss-only SINGLE regression9jobs on three reused public forwardcuts; no full refit, HPO, LLM or whole-agent promotion')
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
        explicit = dict([BASE,COOR,R4,REGISTRATION,PROTOCOL,LOSS_BASE,*SPECS.values()])
        explicit[Path(__file__).resolve().relative_to(WORK).as_posix()] = args.self_sha256
        explicit[AUDITOR] = args.auditor_sha256
        for name, digest in explicit.items():
            need(sha(local(name), check) == digest, 'explicit_component_source_pin_failed'); merge(name,digest)
        coor = imported('_component_proven_coordinator', local(COOR[0])); FAILURE = coor.TechnicalFailure
        base = load(local(BASE[0]))
        loss_base=load(local(LOSS_BASE[0]))
        need(loss_base['source_root']=='loss00' and loss_base['archive_sha256']==ARCHIVE_SHA
             and len(loss_base['compiled_sha256'])==68 and sum(loss_base['registry'].values())==487,
             'actual_LOSS00_unchanged_source_required')
        for name,digest in loss_base['source_files_sha256'].items():merge('loss00/'+name,digest)
        merge(loss_base['archive'],ARCHIVE_SHA)
        for name, digest in base['immutable_files'].items(): merge(name,digest)
        for name in [*coor.LIBS.values(), coor.AWAKE]: need(name in pins, 'runtime_helper_unbound')
        need(bool(args.bootstrap_launcher) == bool(args.bootstrap_launcher_sha256), 'paired_bootstrap_pin_required')
        if args.bootstrap_launcher: merge(args.bootstrap_launcher, args.bootstrap_launcher_sha256)
        for kind, cut, digest in CUTS: merge(split_source(kind,cut),digest)
        need((args.loss00_root_closure,args.loss00_root_closure_sha256)==LOSS00
             and args.loss00_exec_session==99080 and args.loss00_exit_code==0,
             'actual_LOSS00_root_proof_required')
        refs=[(LOSS00[0],LOSS00[1],99080,0)]
        refs += [(name,digest,session,exitcode) for name,(digest,session,exitcode) in HISTORY.items()]
        refs += [(name,digest,'not_checked','not_checked') for name,digest in PUBLICATION.items()]
        refs += [(name,digest,'not_checked','not_checked') for name,digest in
                 (v.rsplit('=',1) for v in args.extra_terminal_receipt)]
        for index,(name,digest,session,exitcode) in enumerate(refs):
            need(sha(local(name),check)==digest,'terminal_proof_pin_failed');proof=load(local(name))
            need(proof.get('cleanup_confirmed') is True and proof.get('source_unchanged') is True
                 and proof.get('active_owned_processes',[])==[] and proof.get('uncertain_owned',[])==[]
                 and proof.get('owned_identities') and proof.get('closure_preparer_identities'),
                 'terminal_cleanup_source_unknown')
            if session!='not_checked':
                need(proof.get('actual_exec_session')==session
                     and proof.get('actual_exec_exit_code_observed_by_root')==exitcode,'actual_predecessor_exec_binding_failed')
            if index==0:
                need(proof.get('technical_procedure_passed') is True and proof.get('source_checks')==487
                     and proof.get('exact_default_repeated')==23 and proof.get('exact_flat_same_LOSS_contracts')==16
                     and proof.get('prepared_manifest_sha256')==LOSS_BASE[1],'actual_LOSS00_full_readiness_required')
            known.update(coor.identities(proof['owned_identities']));known.update(coor.identities(proof['closure_preparer_identities']))
            merge(name,digest)
        historical=load(local('loss0/campaign.json'));rootproof=load(local(LOSS00[0]))
        need(historical['prepared_manifest_sha256']==LOSS_BASE[1]
             and historical['start_unix']==rootproof['original_start_unix']
             and historical['absolute_deadline_unix']==rootproof['original_deadline_unix']
             and historical['elapsed_common_seconds']==rootproof['raw_parent_elapsed_seconds']
             and historical['status']==rootproof['raw_parent_status']
             and historical['technical_checks_passed'] is True and historical['cleanup_confirmed'] is True
             and historical['source_unchanged'] is True and not historical['error_history'],
             'reused_LOSS00_terminal_lineage_required')
        merge('loss0/campaign.json',sha(local('loss0/campaign.json'),check))
        expected={'source':(487,'source','source/results.json'),
                  'exact-default':(23,'exact','exact.json'),
                  'exact-optin':(16,'exact-optin','exact-optin-supervisor.log')}
        need({g['name'] for g in historical['gates']}==set(expected),'full_LOSS00_gate_inventory_required')
        for name,(count,supname,filename) in expected.items():
            saved=next(g for g in historical['gates'] if g['name']==name)
            result='loss0/'+filename;supervisor='loss0/'+supname+'-supervisor.json'
            ref=next(r for r in historical['supervisors'] if r['path']==supervisor)
            need(saved['checks']==count and saved['passed'] is True
                 and sha(local(result),check)==saved['sha256']
                 and sha(local(supervisor),check)==ref['sha256'],'reused_LOSS00_gate_ref_changed')
            sup=load(local(supervisor))
            need(sup['status']=='ok' and sup['exit_code']==0 and sup['cleanup_confirmed'] is True,
                 'reused_LOSS00_gate_not_terminal_clean')
            merge(result,saved['sha256']);merge(supervisor,ref['sha256'])
            state['gates'].append(dict(name=name,checks=count,
                evidence_mode='REUSED_LOSS00_UNCHANGED_SOURCE_NOT_EXECUTED_AGAIN',
                result_path=result,result_sha256=saved['sha256'],supervisor_path=supervisor,
                supervisor_sha256=ref['sha256'],supervisor=sup))
        state['technical_checks_newly_executed']=0
        state['technical_gate_evidence']='Actual LOSS00 source487/exact23/flat16 reused; exactsource freshly rehashed'
        frozen(setup_end,'component_setup_cap_exhausted')
        owner = imported('_component_owner',local(coor.LIBS['owner']))
        processes = imported('_component_processes',local(coor.LIBS['processes']))
        locker = imported('_component_lock',local(coor.LIBS['lock']))
        awake = imported('_component_awake',local(coor.AWAKE)).PowerRequestGuard('Alfa LOSS01 pid'+str(os.getpid()),10)
        parent = psutil.Process().parent(); own_paths = {Path(__file__).resolve()}
        if args.bootstrap_launcher: own_paths.add(local(args.bootstrap_launcher))
        while parent is not None:
            birth = parent.create_time()
            if not any(Path(v).resolve() in own_paths for v in parent.cmdline() if not v.startswith('-')): break
            need(parent.create_time() == birth,'bootstrap_identity_changed')
            state['coordinator_bootstrap_identities'].append(dict(pid=parent.pid,create_time=birth)); parent=parent.parent()
        state.update(_manifest=base,_pulse=lambda:checkpoint(),awake_guard=awake.record)
        state['completed_LOSS00_predecessor']=dict(path=LOSS00[0],sha256=LOSS00[1],actual_exec_session=99080,
            actual_exec_exit_code_observed_by_root=0)
        with awake:
            absence(); frozen(setup_end,'component_setup_cap_exhausted')
            with locker.ResearchLock(WORK/'alfa-hack-automl/test-runs/.owned-research.lock') as lock:
                lock.write_identity(state['owned_root']); absence()
                (ROOT/'g').mkdir(); (ROOT/'sources').mkdir(); (ROOT/'supervisors').mkdir()
                with zipfile.ZipFile(local(loss_base['archive'])) as z:
                    need(len(z.namelist()) == 68 and set(z.namelist()) == set(loss_base['compiled_sha256']), 'exact_flat_archive_inventory_required')
                    for name,digest in loss_base['compiled_sha256'].items():
                        need(Path(name).name == name,'flat_archive_required')
                        target=ROOT/'sources'/name; target.write_bytes(z.read(name))
                        need(sha(target,check) == digest,'flat_archive_copy_changed'); deployment[coor.relative(target)]=digest
                tasks, jobs = {}, []
                for task in base['tasks']:
                    if task['kind']!='regression':continue
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
                    for arm in PROFILES:
                        key=f'{kind}{cut}-{arm}'; directory=ROOT/code/key;directory.mkdir()
                        recipe=copy.deepcopy(tasks[kind]['component_control'])
                        need(recipe['engine']=='lightgbm' and recipe['params'].get('early_metric')=='primary'
                             and recipe['params'].get('nested_stopping') is True and 'loss_profile_id' not in recipe['params'],
                             'unchanged_nested_primary_SINGLE_required')
                        recipe['params']['loss_profile_id']=arm
                        job=dict(spec=load(local(tasks[kind]['spec_path'])),recipe=recipe,output_dir=str(directory),
                            split_path=str(partition),threads=2,full_fit=False)
                        path=directory/'job.json';coor.save(path,job,True);digest_job=sha(path,check);deployment[coor.relative(path)]=digest_job
                        jobs.append(dict(key=key,kind=kind,cut=cut,arm=arm,profile_id=arm,job_path=coor.relative(path),job_sha256=digest_job,
                            output_dir=coor.relative(directory),split_path=coor.relative(partition),split_sha256=digest,recipe=recipe))
                manifest=dict(schema='LOSS01-component-v1',common_seconds=COMMON,immutable_files=dict(pins),
                    setup_deployment_sha256=dict(deployment),source_root='loss00',archive=loss_base['archive'],archive_sha256=ARCHIVE_SHA,
                    compiled_sha256=loss_base['compiled_sha256'],registry=loss_base['registry'],tasks=tasks,jobs=jobs,profiles=PROFILES,
                    loss_prepared_manifest=dict(path=LOSS_BASE[0],sha256=LOSS_BASE[1]),
                    loss00_predecessor=state['completed_LOSS00_predecessor'],
                    per_worker_parent_seconds=PARENT,per_worker_child_seconds=CHILD,threads=2,BLAS_threads=1,
                    worker_memory_gib=1.5,whole_tree_memory_gib=2,refit=False,API_calls=0,
                    interpreter_path=sys.executable,interpreter_sha256=sha(sys.executable,check),interpreter_version=sys.version)
                coor.save(manifest_path,manifest,True);state['manifest_sha256']=sha(manifest_path,check)
                plan=dict(schema='LOSS01-component-audit-v1',verifier_source_sha256=args.auditor_sha256,
                    manual_metric_verifier_path=R4[0],manual_metric_verifier_sha256=R4[1],
                    execution_manifest_sha256=state['manifest_sha256'],original_common_start_unix=start_unix,
                    original_absolute_deadline_unix=unix,common_seconds=COMMON,ordered_jobs=[j['key'] for j in jobs],
                    reproduction_absolute_tolerance=1e-10,failed_metrics_zero_imputed=False,promotion=False,
                    profiles=PROFILES,quality_gate_policy=dict(
                        regression='each_non_L2_profile_strict_RMSE_improvement_on_all_three_cuts_vs_fresh_L2',
                        failed_or_null_cut_gate=False,full_refit_or_promotion=False,
                        legacy_SINGLE='additional_parity_reference_only'))
                coor.save(plan_path,plan,True);state['verification_plan_sha256']=sha(plan_path,check)
                deployment[coor.relative(manifest_path)]=state['manifest_sha256'];deployment[coor.relative(plan_path)]=state['verification_plan_sha256']
                previous={s:signal.signal(s,lambda n,f:(_ for _ in ()).throw(SystemExit(128+n))) for s in [signal.SIGINT,signal.SIGTERM]}
                persist()
                try:
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
                        '--manifest','loss01/manifest.json','--manifest-sha256',state['manifest_sha256'],
                        '--plan','loss01/verification-plan.json','--plan-sha256',state['verification_plan_sha256'],
                        '--self-sha256',args.auditor_sha256,'--output','loss01/independent-audit.json']
                    sup=coor.supervise(command,WORK,ROOT/'audit-supervisor.json','component-audit',tick,AUDIT,AUDIT-30,
                        deadline,unix,AUDIT+CLEANUP,state,persist,frozen,owner,processes,state['coordinator_bootstrap_identities'])
                    coor.child_errors(state,sup)
                    finished.update(coor.identities(sup.get('owned_process_identities',[])))
                    need(sup.get('status')=='ok' and sup.get('exit_code')==0 and sup.get('cleanup_confirmed') is True,'component_auditor_process_failed')
                    audit=load(ROOT/'independent-audit.json');state['independent_audit']=dict(path='loss01/independent-audit.json',sha256=sha(ROOT/'independent-audit.json'),raw_result=audit)
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
