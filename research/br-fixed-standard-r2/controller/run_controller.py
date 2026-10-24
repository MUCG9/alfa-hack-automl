"""Prospective two-standard-call qualification; SOURCE ONLY / NOT_READY."""
from pathlib import Path
from contextlib import contextmanager
import argparse, ast, hashlib, importlib.util, json, math, os, re, shutil, sys, tempfile, time, zipfile

PACKET=Path(__file__).resolve().parent
WORK=PACKET.parents[1]
OUT=WORK/'brq1'
COMMON,SETUP,AUDIT,FINAL,ROOT_CLOSE=6000,600,600,240,60
CAPS={'regression':(900,870),'classification':(3600,3570)}
HELPERS={
 'coordinator':('run_lean_mvp_r2.py','43be86ece6c453641afdcc6f8eccef02d713986e2ac8bf3314756f0bb78e0818'),
 'owner':('support_component_coordinator.py','8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8'),
 'processes':('historical-runtime-support/fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d.py','fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d'),
 'lock':('alfa-hack-automl/tools/research_lock.py','78a0441bb3b9ea60197e9a1a6e1087f6e4cd0886593ec54bcfc4e41c9abe5a45'),
 'awake':('awake-next-dev/awake_guard.py','9a0bae0acb6ddb37e638420c52ad1e587a9180fbd7ef68ebc6e1a3c43e4bfc9b')}
EXECUTOR_HANDOFF_SHA='64fcf54a8bd987ea38b2fc921a1d06eadd834b56e2f09c6e4fd0fa333bce8b09'
ARCHIVE_SHA='6af5374a8fac2ba7d0286580e6b8c588e8bd50552a7d942fccdc2081e634699a'
COUNTS_SHA='bc320fd4723476c8a73404ed17a7bdec0cd4c69b1b1d41b321e370549c8cf4d3'
LAUNCHER_PATH=WORK/'venv/Scripts/python.exe'
LAUNCHER_SHA='d59c9a894b319828d023f3aa83d9a3488d2339f9e27e60e49b02abb0d53cf538'

def need(value,code):
    if not value:raise RuntimeError(code)

def read(path):return json.loads(Path(path).read_text('utf-8'))

def save(path,value):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.pending')
    with temporary.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    os.replace(temporary,path)

def sha(path,check=lambda:None):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            check();block=stream.read(2**20)
            if not block:break
            h.update(block)
    check();return h.hexdigest()

def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module

def methods(path):
    tree=ast.parse(Path(path).read_text('utf-8-sig'));result={}
    for cls in tree.body:
        if isinstance(cls,ast.ClassDef):
            for node in cls.body:
                if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name.startswith('test_'):
                    key=cls.name+'.'+node.name;need(key not in result,'duplicate_test_method')
                    result[key]=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
    return result

def ids(rows):
    need(type(rows) is list and len(rows)<=30000,'bounded_saved_identities_required')
    need(all(type(v) is dict and type(v.get('pid')) is int and v['pid']>0
        and type(v.get('create_time')) in (int,float) and math.isfinite(v['create_time'])
        and v['create_time']>0 for v in rows),'typed_PID_create_time_required')
    return {(v['pid'],v['create_time']) for v in rows}

def capture(psutil,parent_pid,parent_birth):
    """Observe self/direct/shell; allow only direct or ONE pinned venv launcher.

    One microsecond absolute tolerance is ONLY for Get-Process ticks/Unix float
    transport. Saved identities always contain the exact observed psutil birth.
    Shell PID and fresh bounded OS relationships must match independently.
    """
    transported=parent_birth if type(parent_birth) in (int,float) and math.isfinite(parent_birth) else None
    rows=[];record=dict(declared=dict(pid=parent_pid,create_time=transported),
        declared_birth_invalid=transported is None,
        observed_parent=None,observed_shell=None,verified=False,transport_absolute_tolerance_seconds=1e-6)
    try:
        me=psutil.Process();own_birth=me.create_time();rows.append(dict(pid=me.pid,create_time=own_birth))
        parent=me.parent();need(parent is not None,'direct_launch_parent_missing')
        birth=parent.create_time();observed=dict(pid=parent.pid,create_time=birth);record['observed_parent']=observed
        need(type(parent_pid) is int and parent_pid>0 and type(parent_birth) in (int,float)
            and math.isfinite(parent_birth) and parent_birth>0,'typed_launch_parent_required')
        shell=parent;record['mode']='direct_declared_shell'
        if parent.pid!=parent_pid:
            exe=Path(parent.exe())
            need(not exe.is_symlink() and os.path.normcase(os.path.abspath(exe))==os.path.normcase(os.path.abspath(LAUNCHER_PATH))
                and sha(exe)==LAUNCHER_SHA,'exact_pinned_venv_launcher_required')
            shell=parent.parent();need(shell is not None,'declared_shell_missing_after_one_launcher')
            record['mode']='one_pinned_venv_launcher';record['launcher_executable_sha256']=LAUNCHER_SHA
        shell_birth=shell.create_time();shell_row=dict(pid=shell.pid,create_time=shell_birth);record['observed_shell']=shell_row
        need(shell.pid==parent_pid and abs(shell_birth-parent_birth)<=1e-6,'declared_shell_transport_or_extra_hop_mismatch')
        need(me.ppid()==parent.pid and me.create_time()==own_birth and parent.create_time()==birth,
            'direct_launch_parent_relationship_or_identity_changed')
        if shell.pid!=parent.pid:
            need(parent.ppid()==shell.pid and shell.create_time()==shell_birth,'launcher_shell_relationship_or_identity_changed')
        else:need(shell.create_time()==shell_birth,'declared_shell_identity_changed')
        rows.append(observed)
        if shell.pid!=parent.pid:rows.append(shell_row)
        record['verified']=True
    except BaseException as exc:
        record['error']=str(exc) if isinstance(exc,RuntimeError) else 'launch_parent_observation_unconfirmed'
        record['exception_type']=type(exc).__name__
    return rows,record

def guard(begin,deadline,wall,owner,preparers,state,awake=None):
    ob=owner.StrictOwnedObserver();ob.remember(ids(preparers));last=begin;previous=begin;sticky=None
    def pulse(force=False):
        nonlocal last,previous,sticky
        if sticky is not None:raise RuntimeError(sticky)
        try:
            now=time.monotonic();w=time.time()
            need(math.isfinite(now) and math.isfinite(w) and now>=previous,'clock_nonfinite_or_rollback')
            previous=now;state['maximum_observed_gap_seconds']=max(state.get('maximum_observed_gap_seconds',0),now-last)
            need(now-last<=10,'actual_observation_gap10')
            need(now<deadline and w<wall,'original_common_or_phase_deadline')
            need(abs((deadline-now)-(wall-w))<=5,'wall_monotonic_disagreement')
            if not force and now-last<.25:return
            live=ob.observe();need(not ob.denials,'self_bootstrap_resource_denied')
            need((preparers[0]['pid'],preparers[0]['create_time']) in live,'self_identity_unconfirmed')
            rss=0
            for identity,obj in live.items():
                need(obj.create_time()==identity[1],'resource_identity_reused');rss+=obj.memory_info().rss
                need(obj.create_time()==identity[1],'resource_identity_reused')
            need(rss<=2048*2**20,'parent_bootstrap_memory_limit')
            state['peak_parent_bootstrap_mib']=max(state.get('peak_parent_bootstrap_mib',0),rss/2**20)
            after=time.monotonic();need(after-last<=10 and after<deadline and time.time()<wall,'late_resource_observation')
            current_awake=state.get('_awake',awake)
            if current_awake is not None and current_awake.handle is not None:
                sample=current_awake.heartbeat();need(not sample['scheduling_gap_exceeded'],'power_observation_gap10')
            after=time.monotonic();need(after-last<=10 and after<deadline and time.time()<wall,'late_power_or_resource_observation')
            last=after;state['actual_resource_samples']=state.get('actual_resource_samples',0)+1
        except BaseException as exc:
            sticky=str(exc) if isinstance(exc,RuntimeError) else 'resource_observation_unconfirmed'
            state['guard_sticky_error']=sticky;raise
    return pulse

def config(path,expected,self_sha):
    need(__debug__ and Path(path).is_absolute() and Path(path).stat().st_size<=2**20 and sha(path)==expected,'private_manifest_changed')
    cfg=read(path)
    need(cfg.get('schema')=='br-standard-qualification-private-v1'
        and cfg.get('readiness')=='READY_REVIEWED_FROZEN' and cfg.get('missing_bindings')==[], 'NOT_READY')
    need(type(EXECUTOR_HANDOFF_SHA) is str and cfg['executor']['handoff']['sha256']==EXECUTOR_HANDOFF_SHA,
        'NOT_READY_final_reviewed_executor_source_required')
    pins=cfg['immutable_files']
    need(type(pins) is dict and 1<=len(pins)<=4096 and all(Path(p).is_absolute()
        and type(h) is str and re.fullmatch('[0-9a-f]{64}',h) for p,h in pins.items()),'typed_absolute_immutable_pins')
    need(pins.get(str(Path(__file__).resolve()))==self_sha and sha(__file__)==self_sha,'controller_changed')
    need(cfg['output']==str(OUT) and cfg['common_seconds']==COMMON
        and cfg['caps']==dict(setup=SETUP,regression=[900,870],classification=[3600,3570],audit=[600,570],final=FINAL,root=ROOT_CLOSE),
        'fixed_output_and_prospective_caps_required')
    need(Path(cfg['python']).resolve()==Path(sys.executable).resolve() and cfg['python'] in pins,'interpreter_pin_required')
    need(pins.get(str(LAUNCHER_PATH))==LAUNCHER_SHA,'pinned_expected_venv_launcher_required')
    need(cfg['lock']==str(WORK/'alfa-hack-automl/test-runs/.owned-research.lock'),'canonical_lock_required')
    executor=cfg['executor'];need(executor['archive']['sha256']==ARCHIVE_SHA
        and len(executor['members_sha256'])==73 and executor['test_count']==18
        and len(executor['test_methods'])==18 and methods(executor['test'])==executor['test_methods'],
        'exact_R2_archive_and_18_contract_methods_required')
    handoff=read(executor['handoff']['path'])
    need(sha(executor['handoff']['path'])==EXECUTOR_HANDOFF_SHA
        and handoff['archive']['sha256']==ARCHIVE_SHA
        and {Path(k).name:h for k,h in handoff['files_sha256'].items() if k.startswith('candidate/')}==executor['members_sha256'],
        'exact_frozen_R2_member_binding_required')
    executor_root=WORK/'br-standard-release-next-dev-r2'
    for key,relative in [('handoff','source-handoff.json'),('archive','solution-br-fixed-candidate.zip')]:
        need(executor[key]['path']==str(executor_root/relative),'fixed_reviewed_executor_reference_required')
    for key,relative in [('test','tests/test_fixed_release.py'),('recipe_fixture','tests/fixtures/recipes.json'),('base_inventory','base-inventory.json')]:
        need(executor[key]==str(executor_root/relative) and pins.get(executor[key])==handoff['files_sha256'][relative],
            'byte_exact_reviewed_executor_contract_required')
    need(cfg['counts']==dict(path=str(WORK/'uar-count-parser-next-dev/counts.py'),sha256=COUNTS_SHA)
        and pins.get(cfg['counts']['path'])==COUNTS_SHA
        and cfg['caller_contract_count']==10 and len(cfg['caller_test_methods'])==10
        and methods(PACKET/'test_controller_contracts.py')==cfg['caller_test_methods'], 'fixed_caller_and_count_contracts_required')
    for ref in (executor['handoff'],executor['archive'],cfg['candidate_source_review'],cfg['uq3']['root'],cfg['uq3']['fresh']):
        need(type(ref) is dict and Path(ref['path']).is_absolute() and pins.get(ref['path'])==ref['sha256'],'mandatory_reference_pin_required')
    for path in (executor['test'],executor['recipe_fixture'],executor['base_inventory'],
                 str(PACKET/'artifact_audit.py'),str(PACKET/'close_controller.py'),str(PACKET/'test_controller_contracts.py')):
        need(path in pins,'mandatory_contract_or_audit_pin_required')
    for key,(relative,h) in HELPERS.items():
        need(cfg['helpers'][key]==dict(path=str(WORK/relative),sha256=h) and pins.get(str(WORK/relative))==h,'proven_helper_changed')
    need([t['kind'] for t in cfg['tasks']]==['regression','classification'],'exact_two_task_order')
    for task in cfg['tasks']:
        need(Path(task['source']).is_absolute() and set(task['files'])==
            {'task.md','train.csv','test.csv','sample_submission.csv','data_dictionary.csv'},'five_original_task_files')
        need(all(pins.get(str(Path(task['source'])/n))==h for n,h in task['files'].items()),'task_source_pins_required')
    recipes=read(executor['recipe_fixture'])
    need(all(task['expected_recipe']==recipes[task['kind']] for task in cfg['tasks']),'frozen_embedded_recipe_metadata_required')
    for ref in cfg['verification_plan']['expected_classification_splits'].values():
        need(pins.get(str(WORK/ref['path']))==ref['sha256'],'frozen_classification_row_reference_required')
    need(cfg['tasks'][0]['reference_mean']==34.155023394837 and cfg['tasks'][1]['reference_mean']==0.6593178433614652,
        'fixed_historical_references_no_outcome_selection')
    return cfg

def predecessor(cfg,check):
    ref=cfg['uq3']['root'];fresh=cfg['uq3']['fresh'];execution=cfg['uq3']['actual_execution']
    need(type(execution['exit_code']) is int and execution['session']==18415 and bool(execution['tool']),'actual_UQ3_exit_required')
    need(sha(ref['path'],check)==ref['sha256'] and sha(fresh['path'],check)==fresh['sha256'],'UQ3_root_or_fresh_changed')
    proof,confirmation=read(ref['path']),read(fresh['path'])
    need(proof.get('actual_exec_session')==18415 and proof.get('actual_exec_exit_code_observed_by_root')==execution['exit_code']
        and proof.get('actual_tool_evidence')==execution['tool'] and proof.get('cleanup_confirmed') is True
        and proof.get('source_unchanged') is True and proof.get('active_owned_processes')==[]
        and proof.get('uncertain_owned')==[] and proof.get('changed_source_or_core')==[], 'UQ3_known_cleanup_or_source_unqualified')
    need(confirmation.get('schema')=='br-release-predecessor-current-observation-v1'
        and confirmation.get('predecessor_root_sha256')==ref['sha256']
        and confirmation.get('predecessor_actual_execution')==execution
        and confirmation.get('root_actual_execution')==cfg['uq3']['root_actual_execution']
        and type(confirmation['root_actual_execution']['exit_code']) is int
        and bool(confirmation['root_actual_execution']['tool'])
        and confirmation.get('known_exact_live')==[] and confirmation.get('uncertain')==[]
        and confirmation.get('root_and_preparer_union_included') is True
        and confirmation.get('source_unchanged') is True and confirmation.get('cleanup_confirmed') is True,
        'actual_UQ3_closer_and_complete_current_observation_required')
    known=ids(confirmation['known_identities'])
    need(len(known)==len(confirmation['known_identities'])==confirmation['known_count']
        and ids(proof['owned_identities']+proof['closure_preparer_identities'])<=known,'complete_UQ3_known_union_required')
    return known

def absent(owner,known,check=lambda:None):
    check();ob=owner.StrictOwnedObserver();ob.remember(known)
    need(not ob.observe() and not ob.denials and not ob.final_check()['unresolved'],'known_owned_live_or_unconfirmed');check()

def frozen(cfg,check):
    for path,h in cfg['immutable_files'].items():need(sha(path,check)==h,'immutable_source_input_or_dependency_changed')

def seal(directory,check):
    result={}
    for parent,dirs,files in os.walk(directory):
        need(not any((Path(parent)/n).is_symlink() for n in dirs+files),'sealed_tree_symlink')
        for name in files:
            need(not name.endswith(('.pending','.tmp')),'unfinished_artifact')
            path=Path(parent)/name;result[str(path.resolve())]=sha(path,check)
            need(len(result)<=20000,'bounded_core_inventory')
    return result

def archive(cfg,directory,check):
    ref=cfg['executor']['archive'];need(sha(ref['path'],check)==ref['sha256'],'candidate_archive_changed')
    with zipfile.ZipFile(ref['path']) as z:
        need(len(z.namelist())==len(set(z.namelist()))==len(cfg['executor']['members_sha256'])
            and set(z.namelist())==set(cfg['executor']['members_sha256']),'exact_flat_member_inventory')
        for n,h in cfg['executor']['members_sha256'].items():
            need(Path(n).name==n and n.endswith(('.py','.txt')),'flat_code_only_archive_required')
            raw=z.read(n);check();need(hashlib.sha256(raw).hexdigest()==h,'flat_member_changed')
            (directory/n).write_bytes(raw)

@contextmanager
def two_learner_threads(coor):
    original=coor.environment
    def facade(directory,model,manifest):
        need(model is False,'no_model_API_environment_allowed')
        raw=original(directory,False,manifest)
        need(not any(any(s in k.upper() for s in ('KEY','TOKEN','SECRET','AUTH','PASSWORD','PROXY')) for k in raw),'API_scrub_failed')
        env=dict(raw);env['AUTOML_THREADS']='2';return env
    coor.environment=facade
    try:yield
    finally:coor.environment=original

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--launch',action='store_true',required=True)
    for n in ('manifest','manifest-sha256','self-sha256'):p.add_argument('--'+n,required=True)
    p.add_argument('--launch-parent-pid',type=int,required=True,help='Actual declared PowerShell shell PID, direct or one pinned venv launcher above')
    p.add_argument('--launch-parent-create-time',type=float,required=True,help='Actual declared shell Unix birth, invariant float serialization')
    args=p.parse_args();start,begin=time.time(),time.monotonic();wall,end=start+COMMON,begin+COMMON
    import psutil
    preparers,parent_observation=capture(psutil,args.launch_parent_pid,args.launch_parent_create_time)
    need(not OUT.exists(),'exclusive_output_no_retry');OUT.mkdir()
    save(OUT/'preparer-identity.json',dict(schema=2,identities=preparers,launch_parent_observation=parent_observation))
    state=dict(schema='br-standard-qualification-campaign-v1',status='starting',start_unix=start,start_monotonic=begin,
        absolute_deadline_unix=wall,common_deadline_monotonic=end,common_seconds=COMMON,
        owned_root=preparers[0] if preparers else None,coordinator_bootstrap_identities=preparers[1:],supervisors=[],active_supervisor=None,
        launch_parent_observation=parent_observation,
        tasks=[],contracts=[],error_history=[],cleanup_uncertainty=[],cleanup_confirmed=False,source_unchanged=False,temporary_cleanup_confirmed=False,
        artifact_procedure_passed=False,quality_metric=None,root_actual_exec_pending=True,promotion=False,submit=False,_manifest={})
    cfg=None;coor=owner=awake=lease=None;tmp=None;pulse=lambda **kwargs:None;known=set();cores={};deployment={}
    def persist():save(OUT/'campaign.json',{k:v for k,v in state.items() if not k.startswith('_')})
    def fail(exc,phase):
        row=dict(code=str(exc) if isinstance(exc,RuntimeError) and re.fullmatch('[A-Za-z0-9_:+.-]{1,200}',str(exc))
            else type(exc).__name__,phase=phase,exception_type=type(exc).__name__,errno=getattr(exc,'errno',None),winerror=getattr(exc,'winerror',None))
        state.setdefault('first_failure',row);state['error_history'].append(row)
        state.update(status='failed',artifact_procedure_passed=False,quality_metric=None)
    def check(phase_end=None,code='phase_cap'):
        pulse();need(time.monotonic()<end and time.time()<wall,'original6000_exhausted')
        if phase_end is not None:need(time.monotonic()<phase_end,code)
    def all_frozen(phase_end=None,code='source_over_cap'):
        callback=lambda:check(phase_end,code);frozen(cfg,callback)
        for path,h in {**deployment,**cores}.items():need(sha(path,callback)==h,'deployment_or_sealed_core_changed')
    def run(argv,cwd,name,parent,child,reserve,model=False):
        tick=time.monotonic();need(min(end-tick,wall-time.time())>=reserve,'remaining_reserved_phases_unavailable')
        receipt=tmp/(name+'.json')
        try:
            if model:
                with two_learner_threads(coor):sup=coor.supervise(argv,cwd,receipt,name,tick,parent,child,end,wall,reserve,
                    state,persist,all_frozen,owner,modules['processes'],preparers[1:],solver_seconds=None)
            else:sup=coor.supervise(argv,cwd,receipt,name,tick,parent,child,end,wall,reserve,
                    state,persist,all_frozen,owner,modules['processes'],preparers[1:],solver_seconds=None)
        finally:
            if receipt.exists():
                observed=read(receipt);known.update(ids(observed.get('owned_process_identities',[])))
                if observed.get('owned_root'):known.update(ids([observed['owned_root']]))
                ob=observed.get('cleanup_observation',{})
                if observed.get('cleanup_confirmed') is not True or ob.get('unresolved')!=[] or ob.get('denial_count')!=0:
                    state['cleanup_uncertainty'].append(dict(scope=name,receipt=dict(path=str(receipt),sha256=sha(receipt)),observation=ob))
            else:state['cleanup_uncertainty'].append(dict(scope=name,reason='missing_actual_supervisor_receipt'))
        coor.child_errors(state,sup);known.update(ids(sup.get('owned_process_identities',[])))
        if sup.get('owned_root'):known.update(ids([sup['owned_root']]))
        target=OUT/'supervisors';target.mkdir(exist_ok=True)
        for ext in ('.json','.log'):
            src=receipt.with_suffix(ext);dest=target/(name+ext);shutil.copyfile(src,dest)
            cores[str(dest)]=sha(dest,check);need(sha(src,check)==cores[str(dest)],'terminal_receipt_copy_changed')
        state['supervisors'][-1]['path']=coor.relative(target/(name+'.json'));persist()
        need(sup.get('status')=='ok' and sup.get('exit_code')==0 and sup.get('cleanup_confirmed') is True
            and not sup.get('error_history'),'mandatory_child_failed')
        return dict(path=str(target/(name+'.json')),sha256=cores[str(target/(name+'.json'))],record=sup)
    try:
        need(parent_observation['verified'] is True,'explicit_direct_launch_parent_unconfirmed')
        cfg=config(str(Path(args.manifest).resolve()),args.manifest_sha256,args.self_sha256)
        modules={}
        for key,(relative,h) in HELPERS.items():
            need(sha(WORK/relative)==h,'trusted_helper_changed');modules[key]=imported('_brq_'+key,WORK/relative)
        coor,owner=modules['coordinator'],modules['owner']
        pulse=guard(begin,end,wall,owner,preparers,state);state['_pulse']=pulse;check()
        known=predecessor(cfg,check);absent(owner,known,check)
        lease=modules['lock'].ResearchLock(cfg['lock']);lease.__enter__();lease.write_identity(preparers[0])
        absent(owner,known,check);awake=modules['awake'].PowerRequestGuard('br-fixed-standard-qualification')
        awake.__enter__();state['_awake']=awake;check()
        # All setup, tests and copies are inside the same original origin.
        setup_end=begin+SETUP;state.update(manifest_sha256=args.manifest_sha256,status='setup');persist()
        all_frozen(setup_end);(WORK/'t').mkdir(exist_ok=True);tmp=Path(tempfile.mkdtemp(prefix='bq-',dir=WORK/'t')).resolve()
        state['temporary_root']=str(tmp)
        # Final reviewed executor tests are repeated unchanged against source and unpacked bytes.
        flat=tmp/'contracts-flat';(flat/'candidate').mkdir(parents=True);(flat/'tests/fixtures').mkdir(parents=True)
        archive(cfg,flat/'candidate',lambda:check(setup_end))
        for source,dest in [(cfg['executor']['test'],flat/'tests/test_fixed_release.py'),
            (cfg['executor']['recipe_fixture'],flat/'tests/fixtures/recipes.json'),
            (cfg['executor']['base_inventory'],flat/'base-inventory.json')]:shutil.copyfile(source,dest)
        deployment.update(seal(flat,lambda:check(setup_end)))
        counter=imported('_brq_counts',cfg['counts']['path'])
        for name,test,parent,child,count in [('source-contracts',Path(cfg['executor']['test']),150,120,cfg['executor']['test_count']),
            ('flat-contracts',flat/'tests/test_fixed_release.py',150,120,cfg['executor']['test_count']),
            ('caller-contracts',PACKET/'test_controller_contracts.py',60,45,cfg['caller_contract_count'])]:
            check(setup_end);need(setup_end-time.monotonic()>=parent,'setup_full_contract_slot_unavailable')
            ref=run([cfg['python'],'-B','-X','utf8',str(test),'-v'],test.parent,name,parent,child,
                parent+4500+AUDIT+300)
            log=Path(ref['path']).with_suffix('.log').read_text('utf-8');need(counter.counts(log,count),'contract_count_or_skip_failed')
            state['contracts'].append(dict(name=name,expected=count,supervisor=ref));persist();check(setup_end)
        for index,task in enumerate(cfg['tasks']):
            directory=OUT/task['kind'];directory.mkdir();archive(cfg,directory,check)
            for n,h in task['files'].items():
                shutil.copyfile(Path(task['source'])/n,directory/n);need(sha(directory/n,check)==h,'pristine_copy_changed')
            deployment.update(seal(directory,check));kind=task['kind'];parent,child=CAPS[kind]
            ref=run([cfg['python'],'-B','-X','utf8','solution.py','task.md'],directory,kind,parent,child,
                parent+(3600 if index==0 else 0)+AUDIT+300,model=True)
            reports=list((directory/'automl_runs').glob('fixed-release-*/report.json'))
            need(len(reports)==1,'exact_one_fresh_fixed_report_required')
            # Seal complete data/code/cut/refit inventory before any pristine labels are opened by audit.
            sealed=seal(directory,check);core_ref=OUT/(kind+'-core-seal.json');save(core_ref,dict(files_sha256=sealed))
            cores.update(sealed);cores[str(core_ref)]=sha(core_ref,check)
            state['tasks'].append(dict(kind=kind,directory=str(directory),report=str(reports[0]),
                supervisor=ref,seal=dict(path=str(core_ref),sha256=cores[str(core_ref)])));persist()
        need(len(state['tasks'])==2,'both_complete_tasks_required_before_truth')
        state['status']='verifying';save(OUT/'pretruth-barrier.json',dict(tasks=state['tasks'],manifest_sha256=args.manifest_sha256,
            clock={k:state[k] for k in ('start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic')}))
        cores[str(OUT/'pretruth-barrier.json')]=sha(OUT/'pretruth-barrier.json',check);persist()
        state['pretruth_barrier']=dict(path=str(OUT/'pretruth-barrier.json'),sha256=cores[str(OUT/'pretruth-barrier.json')]);persist()
        audit=run([cfg['python'],'-B','-X','utf8',str(PACKET/'artifact_audit.py'),'--manifest',str(Path(args.manifest).resolve()),
            '--manifest-sha256',args.manifest_sha256,'--self-sha256',cfg['immutable_files'][str(PACKET/'artifact_audit.py')]],
            WORK,'independent-audit',600,570,AUDIT+300)
        result=read(OUT/'independent-audit.json');need(result.get('artifact_procedure_passed') is True,'independent_artifacts_unqualified')
        state.update(independent_audit=dict(path=str(OUT/'independent-audit.json'),sha256=sha(OUT/'independent-audit.json',check),supervisor=audit),
            artifact_procedure_passed=True,quality_metric=result['quality_metric'],status='completed_pending_root')
    except BaseException as exc:fail(exc,'qualification')
    finally:
        final_begin=time.monotonic();state['final_start_monotonic']=final_begin
        state['final_deadline_monotonic']=min(final_begin+FINAL,end-ROOT_CLOSE)
        try:
            check(state['final_deadline_monotonic']);need(owner is not None and cfg is not None,'final_authority_unavailable')
            absent(owner,known,check);all_frozen(state['final_deadline_monotonic'])
            need(state['active_supervisor'] is None and not state['cleanup_uncertainty']
                and all(r.get('cleanup_confirmed') is True for r in state['supervisors']),'sticky_child_cleanup_unconfirmed')
            if tmp is not None:
                need(tmp.is_relative_to((WORK/'t').resolve()) and tmp.name.startswith('bq-') and not tmp.is_symlink(),'owned_temp_fence')
                state['temporary_pins_verified_before_removal']=dict(files=deployment,
                    checked_monotonic=time.monotonic(),scope='Source/flat projection verified inside common; deleted paths are not later live pins')
                shutil.rmtree(tmp);check(state['final_deadline_monotonic']);need(not tmp.exists(),'temporary_cleanup_unconfirmed')
            state.update(cleanup_confirmed=True,temporary_cleanup_confirmed=True,source_unchanged=True)
        except BaseException as exc:fail(exc,'final_cleanup');state['cleanup_confirmed']=False
        try:
            if awake is not None:awake.close();state['awake_guard']=awake.record
            pulse(force=True);need(state.get('awake_guard',{}).get('release_API_verified') is True,'power_release_unconfirmed')
        except BaseException as exc:fail(exc,'power_release')
        state['owned_process_identities']=[dict(pid=p,create_time=b) for p,b in sorted(known)]
        state.update(finished_unix=time.time(),finished_monotonic=time.monotonic(),elapsed_common_seconds=time.monotonic()-begin)
        try:persist();pulse(force=True);check(state['final_deadline_monotonic'])
        except BaseException as exc:fail(exc,'terminal_save');persist()
        finally:
            if lease is not None:lease.__exit__(None,None,None)
        try:
            check(state['final_deadline_monotonic'],'final_phase_after_lease_over_cap')
            state.update(finished_unix=time.time(),finished_monotonic=time.monotonic(),elapsed_common_seconds=time.monotonic()-begin)
            persist();check(state['final_deadline_monotonic'],'terminal_save_after_lease_over_cap')
        except BaseException as exc:fail(exc,'postlease');persist()
    passed=state.get('status')=='completed_pending_root' and not state['error_history'] and state['cleanup_confirmed']
    print(json.dumps(dict(status=state['status'],artifact_procedure_passed=bool(passed),quality_metric=state['quality_metric']),allow_nan=False))
    return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
