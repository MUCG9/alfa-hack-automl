"""Atomic repair closer+fresh: same original6000/final240/actual closer birth60."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,math,os,re,subprocess,sys,time

PACKET=Path(__file__).resolve().parent
WORK=PACKET.parent
OUT=WORK/'rq5'
BASE=WORK/'br-standard-release-qualification-next-dev/controller-r5/run_controller.py'
BASE_SHA='d5f41cad6de2168cd520e442223428285dd3714854079d9305dd1b34938abd7d'
LAUNCHER_PATH=WORK/'venv/Scripts/python.exe'
LAUNCHER_SHA='d59c9a894b319828d023f3aa83d9a3488d2339f9e27e60e49b02abb0d53cf538'

def need(value,code):
    if not value:raise RuntimeError(code)
def read(path):return json.loads(Path(path).read_text('utf-8-sig'))
def sha(path,check=lambda:None):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            check();block=stream.read(2**20)
            if not block:break
            h.update(block)
    check();return h.hexdigest()
def save(path,value):
    path=Path(path);pending=path.with_name(path.name+'.pending')
    with pending.open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2,allow_nan=False)
    os.replace(pending,path)
def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

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

def bounds(state,wrapper_wall,wrapper_mono,closer_birth=None):
    start,begin=state['start_unix'],state['start_monotonic']
    wall,end=state['absolute_deadline_unix'],state['common_deadline_monotonic']
    values=(start,begin,wall,end,wrapper_wall,wrapper_mono,state['final_deadline_monotonic'])
    need(all(type(v) in (int,float) and math.isfinite(v) for v in values),'finite_original_clocks_required')
    need(wall==start+6000 and end==begin+6000,'same_original6000_assignment_required')
    final=state['final_deadline_monotonic'];final_wall=start+(final-begin)
    # The wrapper additionally keeps its own enclosing60. No later child birth
    # grants a replacement60; every bound can only tighten the old allocation.
    limits=[wrapper_wall+60,min(end,wrapper_mono+60,final)]
    limits[0]=min(limits[0],wall,final_wall)
    if closer_birth is not None:
        need(type(closer_birth) in (int,float) and math.isfinite(closer_birth)
            and closer_birth>=wrapper_wall,'actual_closer_birth_required')
        limits=[min(limits[0],closer_birth+60),min(limits[1],begin+(closer_birth-start)+60)]
    return tuple(limits)

def child_command(cfg,actual,shell_receipt):
    fields=('powershell','python','closer','manifest')
    need(all(Path(cfg[k]['path']).is_absolute() for k in fields)
        and Path(shell_receipt).is_absolute(),'absolute_fixed_child_paths_required')
    need(type(actual['exit_code']) is int and type(actual['tool']) is str
        and re.fullmatch('[A-Za-z0-9_-]{1,80}',actual['tool'])
        and (actual['session'] is None or type(actual['session']) is int and actual['session']>0),'typed_actual_driver_evidence_required')
    result=[cfg['powershell']['path'],'-NoProfile','-NonInteractive',
        '-File',str(PACKET/'close_child.ps1'),'-Python',cfg['python']['path'],'-Closer',cfg['closer']['path'],
        '-Manifest',cfg['manifest']['path'],'-ManifestSha',cfg['manifest']['sha256'],
        '-CloserSha',cfg['closer']['sha256'],'-DriverSha',cfg['driver']['sha256'],
        '-CampaignSha',cfg['campaign']['sha256'],'-ActualTool',actual['tool'],
        '-ActualExit',str(actual['exit_code']),'-ExitReceipt',str(shell_receipt)]
    if actual['session'] is not None:result+=['-ActualSession',str(actual['session'])]
    return result

def native_shell_verified(native,early,captured_shell):
    chain=early['launch_parent_observation']
    need(chain.get('verified') is True and chain.get('observed_shell')==captured_shell,
        'exact_observed_child_shell_identity_required')
    # Get-Process transports the declared birth; capture already validated its
    # bounded serialization difference and preserved the exact psutil identity.
    need(native.get('shell')==chain.get('declared'),'native_declared_shell_transport_required')

def postexit(shell_exit,native_exit,save_exit,fresh,check):
    # This source-owned sequence removes the human intertool gap: publish actual
    # exit evidence FIRST, then fresh observation, with unchanged clock checks.
    save_exit();check()
    need(type(shell_exit) is int and type(native_exit) is int
        and shell_exit==native_exit==0,'actual_closer_or_shell_failed')
    answer=fresh();check();return answer

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('binding','binding-sha256','self-sha256','actual-tool-evidence'):p.add_argument('--'+key,required=True)
    p.add_argument('--actual-exit-code',type=int,required=True);p.add_argument('--actual-exec-session',type=int,default=None)
    p.add_argument('--launch-parent-pid',type=int,required=True);p.add_argument('--launch-parent-create-time',type=float,required=True)
    a=p.parse_args();entry_wall,entry_mono=time.time(),time.monotonic()
    import psutil
    preparers,chain=capture(psutil,a.launch_parent_pid,a.launch_parent_create_time)
    need(OUT.is_dir() and not (OUT/'atomic-root-preparer-identity.json').exists(),'exclusive_new_repair_only')
    save(OUT/'atomic-root-preparer-identity.json',dict(identities=preparers,launch_parent_observation=chain))
    need(chain.get('verified') is True,'actual_wrapper_chain_unconfirmed')
    need(__debug__ and Path(a.binding).is_absolute() and sha(__file__)==a.self_sha256
        and sha(a.binding)==a.binding_sha256,'frozen_wrapper_binding_required')
    cfg=read(a.binding);need(cfg.get('schema')=='standard-repair-atomic-root-private-v1'
        and cfg.get('readiness')=='READY_REVIEWED_FROZEN' and cfg.get('missing_bindings')==[],'NOT_READY')
    pins=cfg['immutable_files'];need(type(pins) is dict and 1<=len(pins)<=4096
        and pins.get(str(Path(__file__).resolve()))==a.self_sha256
        and pins.get(str(PACKET/'close_child.ps1'))==cfg['child_script_sha256']
        and cfg['output']==str(OUT),'exact_wrapper_script_output_pins_required')
    for key in ('driver','closer','manifest','campaign','python','powershell','independent_source_review','qualification_source_review'):
        ref=cfg[key];need(Path(ref['path']).is_absolute() and pins.get(ref['path'])==ref['sha256'],'exact_fixed_child_reference_required')
        need(sha(ref['path'])==ref['sha256'],'fixed_child_reference_changed')
    need(cfg['python']==dict(path=str(LAUNCHER_PATH),sha256=LAUNCHER_SHA)
        and pins.get(str(BASE))==BASE_SHA and sha(BASE)==BASE_SHA,'qualified_base_interpreter_required')
    state=read(cfg['campaign']['path']);wall,end=bounds(state,entry_wall,entry_mono)
    need(state.get('status')=='completed_pending_root' and state.get('cleanup_confirmed') is True
        and state.get('source_unchanged') is True and state.get('temporary_cleanup_confirmed') is True,
        'actual_clean_terminal_driver_required')
    need(entry_mono+60<=state['common_deadline_monotonic'] and entry_wall+60<=state['absolute_deadline_unix']
        and entry_mono+60<=state['final_deadline_monotonic'],'full_enclosing60_original_reserve_required')
    c=imported('_atomic_future_cache_driver',cfg['driver']['path'])
    need(c.OUT==OUT and Path(cfg['closer']['path']).parent==Path(cfg['driver']['path']).parent,'fixed_repair_literal_binding_required')
    driver_cfg=c.config(cfg['manifest']['path'],cfg['manifest']['sha256'],cfg['driver']['sha256'])
    base=imported('_atomic_root_C5',BASE);modules={}
    for key,(relative,h) in base.HELPERS.items():
        need(pins.get(str(WORK/relative))==h and sha(WORK/relative)==h,'qualified_atomic_helper_changed')
        modules[key]=imported('_atomic_root_'+key,WORK/relative)
    owner=modules['owner'];stats={};pulse=base.guard(entry_mono,end,wall,owner,preparers,stats)
    joint_sampler=modules['sampling'].VerifiedResourceSampler();joint_last=entry_mono;joint_sticky=None
    required=(preparers[0]['pid'],preparers[0]['create_time'])
    def window_clock():
        if joint_sticky is not None:raise RuntimeError(joint_sticky)
        stats['_resource_checkpoint']()
        need(time.monotonic()-joint_last<=10,'atomic_joint_observation_gap10')
        need(time.monotonic()<end and time.time()<wall,'atomic_original_root_window_expired')
    def check(force=False):
        nonlocal joint_last,joint_sticky
        try:
            window_clock();pulse(force=force)
            if not force and time.monotonic()-joint_last<.25:return
            ob=stats.get('_root_observer');known=base.ids(preparers)
            if ob is not None:known|=set(ob.seen)
            record=joint_sampler.sample(known,required=[required],checkpoint=window_clock)
            need(sum(row['rss_bytes'] for row in record['sampled'])<=2048*2**20,'atomic_whole_owned_memory_limit')
            window_clock();joint_last=time.monotonic();stats['verified_atomic_joint_resource_sample']=record
        except BaseException as exc:
            joint_sticky=str(exc) if isinstance(exc,RuntimeError) else 'atomic_joint_resource_unconfirmed'
            raise
    def frozen():
        for path,h in {**driver_cfg['immutable_files'],**pins,str(Path(a.binding)):a.binding_sha256}.items():
            need(sha(path,check)==h,'atomic_source_input_core_changed')
    need(time.monotonic()-entry_mono<=10,'bootstrap_gap10_before_first_resource_observation')
    check(True);frozen();awake=modules['awake'].PowerRequestGuard('CLASS-cache-atomic-root');awake.__enter__();stats['_awake']=awake
    child=tree=None;observer=owner.StrictOwnedObserver();verified=False;child_identity=None;child_cleanup=None;errors=[];confirmation=None;lease=None
    stats['_root_observer']=observer
    early=OUT/'root-preparer-identity.json';root_path=OUT/'terminal-root-closure.json';native_path=OUT/'atomic-native-exit.json';exit_path=OUT/'atomic-child-exit.json'
    actual=dict(session=a.actual_exec_session,exit_code=a.actual_exit_code,tool=a.actual_tool_evidence)
    try:
        need(not any(x.exists() for x in (early,root_path,native_path,exit_path,OUT/'root-confirmation.json')),'new_root_no_rerun_required')
        allowed={'PATH','PATHEXT','SYSTEMROOT','WINDIR','COMSPEC','LOCALAPPDATA'}
        env={k:v for k,v in os.environ.items() if k.upper() in allowed}
        env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',AUTOML_THREADS='1',
            OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
        with (OUT/'atomic-root-child.log').open('x',encoding='utf-8') as log:
            try:
                check(True);child=subprocess.Popen(child_command(cfg,actual,native_path),cwd=WORK,env=env,
                    stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                process=psutil.Process(child.pid);birth=process.create_time()
                need(process.create_time()==birth,'actual_child_shell_birth_unconfirmed')
                child_identity=dict(pid=child.pid,create_time=birth);observer.remember([(child.pid,birth)]);verified=True
                tree=modules['processes'].ProcessTree(child)
                seen_early=None
                while True:
                    check();observer.observe();need(not observer.denials,'child_shell_observation_denied')
                    if early.exists() and seen_early is None:
                        row=read(early);need(row['launch_parent_observation'].get('verified') is True
                            and row['launch_parent_observation']['observed_shell']==child_identity,'closer_actual_child_shell_binding_required')
                        seen_early=row;wall,end=bounds(state,entry_wall,entry_mono,row['identities'][0]['create_time']);check(True)
                    # Deadline is checked BEFORE accepting terminal poll.
                    if child.poll() is not None:break
                    time.sleep(.05)
                need(seen_early is not None,'actual_early_closer_identity_required')
            finally:
                child_cleanup=owner.cleanup_owned(child,tree,observer,verified,modules['processes'].ProcessTree)
        check(True);need(child_cleanup['cleanup_confirmed'] is True,'actual_child_chain_cleanup_unconfirmed')
        native=read(native_path);need(native.get('schema')=='standard-repair-actual-native-closer-exit-v1','actual_native_exit_schema_required')
        native_shell_verified(native,seen_early,child_identity)
        def save_exit():
            save(exit_path,dict(schema='standard-repair-atomic-child-exit-v1',actual_shell_exit=child.returncode,
                actual_closer_exit=native['actual_native_exit_code'],child_shell=child_identity,
                closer_preparers=seen_early['identities'],child_cleanup=child_cleanup,actual_driver=actual,
                observed_unix=time.time(),observed_monotonic=time.monotonic()))
        def fresh():
            nonlocal lease
            root=read(root_path);need(root.get('schema')=='standard-repair-qualification-root-closure-v1'
                and root.get('technical_procedure_passed') is True and root.get('cleanup_confirmed') is True
                and root.get('source_unchanged') is True and root.get('temporary_cleanup_confirmed') is True
                and root.get('uncertain_owned')==[] and root.get('changed_source_or_core')==[]
                and root.get('actual_exec_session')==actual['session']
                and root.get('actual_exec_exit_code_observed_by_root')==actual['exit_code']
                and root.get('actual_tool_evidence')==actual['tool'],'exact_positive_actual_driver_root_required')
            known=base.ids(root['owned_identities']+root['closure_preparer_identities'])
            known|=base.ids(child_cleanup['owned_process_identities'])|base.ids([child_identity])
            need(not (known & base.ids(preparers)),'no_live_observer_exclusion_from_closer_preparers')
            base.absent(owner,known,check);lease=modules['lock'].ResearchLock(driver_cfg['lock']);lease.__enter__();lease.write_identity(preparers[0])
            base.absent(owner,known,check);frozen()
            temp=state.get('temporary_root');need(temp is None or not Path(temp).exists(),'driver_owned_temp_not_removed')
            need(sha(cfg['campaign']['path'],check)==cfg['campaign']['sha256'],'closed_driver_changed')
            base.absent(owner,known,check);check(True)
            return dict(schema='standard-repair-atomic-root-confirmation-v1',technical_procedure_passed=True,
                root_sha256=sha(root_path,check),actual_driver=actual,actual_closer_exit=0,
                child_exit_receipt_sha256=sha(exit_path,check),closer_preparer_receipt_sha256=sha(early,check),
                actual_closer_birth=seen_early['identities'][0]['create_time'],
                known_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],known_count=len(known),
                known_exact_live=[],uncertain=[],source_unchanged=True,current_temporary_absent=True,
                current_cleanup_confirmed=True,wrapper_preparer_identities=preparers,
                wrapper_actual_exit_and_fresh_preparer_absence_still_required=True,
                original6000_not_reset=True,
                fixture_learner_fits=None,external_API_calls=None,public_experiment_fits=0,promotion=False,submit=False)
        confirmation=postexit(child.returncode,native['actual_native_exit_code'],save_exit,fresh,check)
    except BaseException as exc:errors.append(dict(exception_type=type(exc).__name__,code=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__))
    finally:
        try:
            awake.close();check(True);need(awake.record.get('release_API_verified') is True,'atomic_power_release_unconfirmed')
        except BaseException as exc:errors.append(dict(exception_type=type(exc).__name__,phase='power_release'))
        if lease is not None:lease.__exit__(None,None,None)
    result=confirmation or dict(schema='standard-repair-atomic-root-confirmation-v1',technical_procedure_passed=False,
        wrapper_preparer_identities=preparers,fixture_learner_fits=None,external_API_calls=None,public_experiment_fits=0,promotion=False,submit=False)
    result.update(errors=errors,resource_observation={k:v for k,v in stats.items() if not k.startswith('_')})
    try:
        check(True);need(not errors,'atomic_root_failed');result.update(finished_unix=time.time(),finished_monotonic=time.monotonic(),
            inside_actual_closer_birth60=True,inside_original6000=True,inside_existing_driver_final240=True)
        save(OUT/'root-confirmation.json',result);check(True)
    except BaseException as exc:
        errors.append(dict(phase='terminal_save',exception_type=type(exc).__name__))
        result.update(technical_procedure_passed=False,errors=errors)
        save(OUT/'root-confirmation.json',result)
    print(json.dumps(dict(technical_procedure_passed=result['technical_procedure_passed'],promotion=False)))
    return 0 if result['technical_procedure_passed'] else 1

if __name__=='__main__':raise SystemExit(main())
