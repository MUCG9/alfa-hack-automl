"""Fixed BRQ2 current-negative source/temp audit; never qualifies original FAIL."""
import time
ENTRY_UNIX,ENTRY_MONO=time.time(),time.monotonic()
from pathlib import Path
import argparse, hashlib, importlib.util, json, math, os, shutil, stat

PACKET=Path(__file__).resolve().parent
WORK=PACKET.parent
OUT=WORK/'brq2-negative-closure-r1'
OLD=WORK/'brq2'
TEMP=WORK/'t/bq-vsv0eprp'
DRIVER=WORK/'br-standard-release-qualification-next-dev/controller-r4/run_controller.py'
DRIVER_SHA='975d28e52c62a0b00834e898edbfc46c35eedec683cbd9e1e9a5337ca5d26470'
MANIFEST_SHA='ce61c1dd2498fa162aa1b7d3089e4c5120e33070fe32cf2011a25aeb1610a74f'
LAUNCHER_PATH=WORK/'venv/Scripts/python.exe'
LAUNCHER_SHA='d59c9a894b319828d023f3aa83d9a3488d2339f9e27e60e49b02abb0d53cf538'
PINS={
 'brq2/campaign.json':'fd85c8317ff187ffc37986613ea5169c4dbd1e9512545e51127469750416ae24',
 'brq2/terminal-root-closure.json':'2d259e647a64f2f1e48d06e450f6fd877d4dc07bac3363df9743d78fecb890a0',
 'brq2/preparer-identity.json':'8b22ce8b267f07608ba9723eebd620b81888eec886c2f9099835d013de13f07a',
 'brq2/root-preparer-identity.json':'b93d8c27b6a22a70632e1d5e64cde20a15f44c43da050be880ce250812916d61',
 'brq2-post-failure-identities-r1.json':'2a4c861b17354efe007b72de31e10d57a2dbd6bc13f2febb104ad0fe2d9906af',
 't/bq-vsv0eprp/source-contracts.json':'0307ffaf89992535da470b947c1f45fc4538495fd458d3f9fec41a604e9c512b',
 't/bq-vsv0eprp/source-contracts.log':'475d65be1069ddbe3bc5e17a572699dfde09e4ee6f8a1deaa8d6b30f010b83bd'}

def need(value,code):
    if not value:raise RuntimeError(code)

def load(path):return json.loads(Path(path).read_text('utf-8'))

def sha(path,check=lambda:None):
    result=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(2**20),b''):check();result.update(block)
    check();return result.hexdigest()

def save(path,value):
    path=Path(path);pending=path.with_suffix(path.suffix+'.pending')
    with pending.open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2,ensure_ascii=False,allow_nan=False);stream.write('\n')
    os.replace(pending,path)

def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value);return value

def technical_environment():
    # Same allowlist as pinned coor.environment(model=False), without a child or
    # temporary env directory. Only this helper's inherited mapping is changed.
    allowed={'PATH','PATHEXT','SYSTEMROOT','WINDIR','COMSPEC','LOCALAPPDATA'}
    for name in list(os.environ):
        if name.upper() not in allowed:os.environ.pop(name,None)
    os.environ.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',AUTOML_THREADS='1')
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS'):
        os.environ[name]='1'

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

def regular(path,directory=False):
    row=os.lstat(path)
    need(not stat.S_ISLNK(row.st_mode) and not (getattr(row,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',1024)),
        'symlink_junction_or_reparse_denied')
    need(stat.S_ISDIR(row.st_mode) if directory else stat.S_ISREG(row.st_mode),'regular_owned_path_required')

def temp_inventory(check):
    regular(WORK,True);regular(WORK/'t',True);regular(TEMP,True)
    need(TEMP.parent==WORK/'t' and TEMP.name=='bq-vsv0eprp'
        and TEMP.resolve(strict=True)==TEMP.absolute() and TEMP.resolve(strict=True).is_relative_to((WORK/'t').resolve(strict=True)),
        'exact_receipt_owned_shallow_temp_fence')
    result={}
    for directory,dirs,files in os.walk(TEMP,followlinks=False):
        check();regular(Path(directory),True)
        for name in dirs:regular(Path(directory)/name,True);check()
        for name in files:
            path=Path(directory)/name;regular(path);result[str(path.relative_to(TEMP)).replace('\\','/')]=sha(path,check)
            need(len(result)<=20000,'bounded_temp_inventory_required')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',required=True);p.add_argument('--self-sha256',required=True)
    p.add_argument('--launch-parent-pid',type=int,required=True);p.add_argument('--launch-parent-create-time',type=float,required=True)
    a=p.parse_args()
    technical_environment()
    import psutil
    preparers,launch=capture(psutil,a.launch_parent_pid,a.launch_parent_create_time)
    need(not OUT.exists(),'exclusive_new_negative_audit_output');OUT.mkdir()
    save(OUT/'preparer-identity.json',dict(identities=preparers,launch_parent_observation=launch))
    need(launch['verified'] is True,'negative_audit_launch_chain_unconfirmed')
    need(__debug__ and Path(a.manifest).is_absolute() and sha(__file__)==a.self_sha256 and sha(DRIVER)==DRIVER_SHA,'frozen_new_auditor_and_original_driver_required')
    need(sha(a.manifest)==MANIFEST_SHA,'exact_original_private_manifest_required')
    state=load(OLD/'campaign.json');root=load(OLD/'terminal-root-closure.json');observation=load(WORK/'brq2-post-failure-identities-r1.json')
    end,wall=state['common_deadline_monotonic'],state['absolute_deadline_unix']
    need(end==state['start_monotonic']+6000 and wall==state['start_unix']+6000,'same_assigned_original_BRQ2_6000')
    need(ENTRY_MONO+90<=end and ENTRY_UNIX+90<=wall,'full_audit90_in_original_remaining_common_required')
    c=imported('_brq2_fixed_negative_controller',DRIVER)
    owner_path,owner_sha=c.HELPERS['owner'];need(sha(WORK/owner_path)==owner_sha,'proven_owner_changed')
    owner=imported('_brq2_negative_owner',WORK/owner_path);resource={}
    pulse=c.guard(ENTRY_MONO,ENTRY_MONO+60,ENTRY_UNIX+60,owner,preparers,resource)
    def check(force=False):
        pulse(force=force);need(time.monotonic()<end and time.time()<wall,'original_BRQ2_common_exhausted')
    bad=[];known=set();copies={};lease=awake=None;source_ok=temp_ok=absence_ok=False;before=None
    def failure(exc,phase):bad.append(dict(phase=phase,code=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__,exception_type=type(exc).__name__))
    try:
        check(True)
        for relative,h in PINS.items():need(sha(WORK/relative,check)==h,'fixed_failure_evidence_changed')
        need(state['status']=='failed' and state['tasks']==[] and state['contracts']==[] and state['active_supervisor'] is None
            and state['artifact_procedure_passed'] is False and state['quality_metric'] is None,'exact_pre_model_failed_campaign_required')
        need(all(state.get(k) is False for k in ('cleanup_confirmed','source_unchanged','temporary_cleanup_confirmed'))
            and root['technical_procedure_passed'] is root['cleanup_confirmed'] is root['source_unchanged'] is False,
            'original_false_flags_must_stay_false')
        need(root['actual_exec_session'] is None and root['actual_exec_exit_code_observed_by_root']==1
            and root['actual_tool_evidence']=='199da9' and root['qualified_ML_metrics'] is None,'exact_original_actual_failure_required')
        need(observation['schema']=='BRQ2-owned-identities-only-post-failure-observation-r1'
            and observation['root_sha256']==PINS['brq2/terminal-root-closure.json']
            and observation['actual_driver_execution']==dict(session=None,exit_code=1,tool='199da9')
            and observation['actual_root_execution']==dict(session=None,exit_code=1,tool='306e5d')
            and observation['known_exact_live']==observation['uncertain']==[],'typed_actual_current_identity_observation_required')
        cfg=c.config(a.manifest,MANIFEST_SHA,DRIVER_SHA);need(len(cfg['immutable_files'])==130,'original130pins_required')
        known=c.ids(observation['known_identities']);need(len(known)==observation['known_count']==7264,'exact_unique7264_scope')
        required=c.predecessor(cfg,check)|c.ids(state['owned_process_identities'])|c.ids([state['owned_root']]+state['coordinator_bootstrap_identities'])
        required|=c.ids(root['owned_identities']+root['closure_preparer_identities'])
        for name in ('preparer-identity.json','root-preparer-identity.json'):required|=c.ids(load(OLD/name)['identities'])
        supervisor=load(TEMP/'source-contracts.json');required|=c.ids(supervisor['owned_process_identities']+[supervisor['owned_root']])
        need(required<=known and supervisor['cleanup_confirmed'] is True and supervisor['exit_code']==0
            and supervisor['kind']=='source-contracts' and supervisor['parent_cap_seconds']==150 and supervisor['child_cap_seconds']==120
            and supervisor['status']=='technical_failure' and supervisor['cleanup_observation']['unresolved']==[]
            and supervisor['cleanup_observation']['denial_count']==0,'complete_actual_closed_owned_union_required')
        need(Path(state['temporary_root'])==TEMP and len(state['supervisors'])==1
            and state['supervisors'][0]['path']=='t/bq-vsv0eprp/source-contracts.json'
            and state['supervisors'][0]['sha256']==PINS['t/bq-vsv0eprp/source-contracts.json'],'exact_receipt_owned_temp_required')
        c.absent(owner,known,check)
        for key in ('lock','awake'):
            relative,h=c.HELPERS[key];need(sha(WORK/relative,check)==h,'proven_metadata_guard_changed')
        locker=imported('_brq2_negative_lock',WORK/c.HELPERS['lock'][0]);power=imported('_brq2_negative_power',WORK/c.HELPERS['awake'][0])
        lease=locker.ResearchLock(cfg['lock']);lease.__enter__();lease.write_identity(preparers[0]);c.absent(owner,known,check)
        awake=power.PowerRequestGuard('BRQ2-current-negative-source-temp-audit');awake.__enter__();resource['_awake']=awake;check(True)
        c.frozen(cfg,check)
        evidence=OUT/'evidence';evidence.mkdir()
        # Preserve every actual terminal/failure receipt BEFORE deleting its original owned temp.
        for relative,h in PINS.items():
            source=WORK/relative;regular(source);target=evidence/(relative.replace('/','__'))
            need(sha(source,check)==h,'failure_source_changed_before_copy');shutil.copyfile(source,target)
            need(sha(source,check)==sha(target,check)==h,'actual_failure_evidence_copy_changed');copies[relative]=dict(path=str(target.relative_to(WORK)).replace('\\','/'),sha256=h)
        before=temp_inventory(check);save(OUT/'temporary-inventory-before.json',dict(root='t/bq-vsv0eprp',files_sha256=before))
        c.absent(owner,known,check);need(temp_inventory(check)==before,'owned_temp_changed_during_current_audit')
        # Revalidate the exact explicit target immediately before its ONLY recursive deletion.
        regular(WORK/'t',True);regular(TEMP,True);need(TEMP.resolve(strict=True)==TEMP.absolute(),'temp_target_changed_before_cleanup')
        check(True);shutil.rmtree(TEMP);check(True);need(not TEMP.exists(),'explicit_owned_temp_cleanup_incomplete');temp_ok=True
        c.absent(owner,known,check);absence_ok=True;c.frozen(cfg,check)
        for relative,h in PINS.items():
            if not relative.startswith('t/'):
                need(sha(WORK/relative,check)==h,'original_failure_receipt_mutated')
            need(sha(WORK/copies[relative]['path'],check)==h,'preserved_failure_evidence_mutated')
        need(sha(__file__,check)==a.self_sha256 and sha(a.manifest,check)==MANIFEST_SHA,'new_auditor_or_original_manifest_changed')
        source_ok=True;check(True)
    except BaseException as exc:failure(exc,'current_negative_audit')
    finally:
        try:
            if awake is not None:awake.close()
            check(True);need(awake is not None and awake.record.get('release_API_verified') is True,'negative_audit_power_release_unconfirmed')
        except BaseException as exc:failure(exc,'release')
        if lease is not None:lease.__exit__(None,None,None)
    completed=source_ok and temp_ok and absence_ok and not bad
    result=dict(schema='brq2-current-negative-source-temp-closure-v1',technical_procedure_passed=False,qualified_ML_metrics=None,
        original_gate_remains_FAILED=True,original_driver_flags={k:state.get(k) for k in ('cleanup_confirmed','source_unchanged','temporary_cleanup_confirmed')},
        original_root_flags={k:root.get(k) for k in ('technical_procedure_passed','cleanup_confirmed','source_unchanged')},
        original_first_failure=state.get('first_failure'),original_error_history=state['error_history'],original_root_errors=root['root_errors'],
        original_driver_actual_execution=dict(session=None,exit_code=1,tool='199da9'),original_closer_actual_execution=dict(session=None,exit_code=1,tool='306e5d'),
        fixed_failure_refs=PINS,original_manifest_sha256=MANIFEST_SHA,original_source_pin_count=130,
        current_negative_audit_completed=bool(completed),cleanup_confirmed=bool(completed),source_unchanged=bool(completed),temporary_cleanup_confirmed=bool(temp_ok),
        active_owned_processes=[],uncertain_owned=[] if completed else bad,current_audit_errors=bad,
        owned_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],closure_preparer_identities=preparers,
        current_known_scope_only=True,current_observation_source_sha256=PINS['brq2-post-failure-identities-r1.json'],
        preserved_terminal_evidence=copies,explicit_removed_temp='t/bq-vsv0eprp',temporary_inventory_before_sha256=sha(OUT/'temporary-inventory-before.json') if (OUT/'temporary-inventory-before.json').is_file() else None,
        original_start_unix=state['start_unix'],original_start_monotonic=state['start_monotonic'],original_deadline_unix=wall,original_end_monotonic=end,
        original_common_seconds=6000,common_clock_reset=False,audit_parent_start_unix=ENTRY_UNIX,audit_parent_start_monotonic=ENTRY_MONO,
        audit_parent_deadline_unix=ENTRY_UNIX+90,audit_parent_end_monotonic=ENTRY_MONO+90,own_helper_cap_seconds=60,root_fresh_reserve_seconds=30,
        actual_helper_exit_and_fresh_full_preparer_absence_before_parent90_and_original_common_required=True,
        helper_source_sha256=a.self_sha256,resource_observation={k:v for k,v in resource.items() if not k.startswith('_')},awake_guard=awake.record if awake is not None else None,
        new_model_fits=0,API_calls=0,tests_run=0,official_default_ready=False,promotion=False,submit=False,
        scope='Separate current known ownership/source/temp audit ONLY; original source/runtime/test/ML procedure is not retroqualified.')
    target=OUT/'terminal-root-closure.json'
    try:check(True);save(target,result);check(True)
    except BaseException as exc:
        failure(exc,'terminal_save');result.update(current_negative_audit_completed=False,cleanup_confirmed=False,source_unchanged=False);save(target,result);completed=False
    print(json.dumps(dict(current_negative_audit_completed=bool(completed),technical_procedure_passed=False,qualified_ML_metrics=None)))
    return 0 if completed else 1

if __name__=='__main__':raise SystemExit(main())
