"""Root proof for one cache audit: own60 INSIDE the same original600."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,math,os,time

PACKET=Path(__file__).resolve().parent;WORK=PACKET.parent;OUT=WORK/'cx2'
LAUNCHER_PATH=WORK/'venv/Scripts/python.exe'
LAUNCHER_SHA='d59c9a894b319828d023f3aa83d9a3488d2339f9e27e60e49b02abb0d53cf538'
def need(value,code):
    if not value:raise RuntimeError(code)
def read(p):return json.loads(Path(p).read_text('utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

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

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('manifest','manifest-sha256','self-sha256','driver-sha256','campaign-sha256','actual-tool-evidence'):p.add_argument('--'+k,required=True)
    p.add_argument('--actual-exec-session',type=int,default=None);p.add_argument('--actual-exit-code',type=int,required=True)
    p.add_argument('--launch-parent-pid',type=int,required=True);p.add_argument('--launch-parent-create-time',type=float,required=True)
    a=p.parse_args();own_unix,own_mono=time.time(),time.monotonic()
    import psutil
    preparers,parent=capture(psutil,a.launch_parent_pid,a.launch_parent_create_time)
    early=OUT/'root-preparer-identity.json';need(OUT.is_dir() and not early.exists(),'exclusive_root_preparer_receipt')
    with early.open('x',encoding='utf-8') as stream:json.dump(dict(identities=preparers,launch_parent_observation=parent),stream,indent=2,allow_nan=False)
    need(parent.get('verified') is True,'exact_root_launch_parent_unconfirmed')
    driver=PACKET/'run_audit.py';need(__debug__ and Path(a.manifest).is_absolute()
        and sha(__file__)==a.self_sha256 and sha(driver)==a.driver_sha256,'root_frozen_self_driver_and_absolute_manifest')
    c=imported('_cx_root_caller',driver);campaign=OUT/'campaign.json';need(sha(campaign)==a.campaign_sha256,'closed_campaign_changed')
    state=read(campaign);end,wall=state['common_deadline_monotonic'],state['absolute_deadline_unix']
    need(end==state['start_monotonic']+600 and wall==state['start_unix']+600,'same_assigned_original600_required')
    need(own_mono+60<=end and own_unix+60<=wall,'whole_root60_original_reserve_required')
    cfg=c.config(a.manifest,a.manifest_sha256,a.driver_sha256)
    need(cfg['immutable_files'].get(str(Path(__file__).resolve()))==a.self_sha256,'frozen_actual_root_source_required')
    need(c.sha(c.BASE_PATH)==c.BASE_SHA,'qualified_base_changed');base=c.imported('_cx_root_base',c.BASE_PATH)
    modules={}
    for key,(relative,h) in base.HELPERS.items():
        need(cfg['immutable_files'].get(str(WORK/relative))==h and c.sha(WORK/relative)==h,'root_helper_changed')
        modules[key]=c.imported('_cx_root_'+key,WORK/relative)
    owner=modules['owner'];stats={};pulse=base.guard(own_mono,min(own_mono+60,end),min(own_unix+60,wall),owner,preparers,stats)
    known=set();bad=[];uncertain=list(state.get('cleanup_uncertainty',[]));audit=None;awake=lease=None;release=None
    expected={str(campaign):a.campaign_sha256,str(early):sha(early),str(Path(a.manifest)):a.manifest_sha256,**cfg['immutable_files']}
    def check(force=False):pulse(force=force)
    def failure(exc,phase):bad.append(dict(phase=phase,exception_type=type(exc).__name__,code=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__))
    try:
        check(True);docs={k:c.read(cfg['brq3'][k]['path']) for k in ('root','fresh','timing')};c.predecessor_documents(**docs)
        known=base.ids(docs['fresh']['known_identities'])|base.ids(state.get('owned_process_identities',[]))
        known|=base.ids([state['owned_root']]+state.get('coordinator_bootstrap_identities',[]))
        for ref in cfg.get('additional_preparer_receipts',[]):known|=base.ids(c.read(ref['path'])['identities'])
        for item in state.get('supervisors',[]):
            path=Path(item['path']);path=path if path.is_absolute() else WORK/path
            need(c.sha(path,check)==item['sha256'],'saved_terminal_supervisor_changed');actual=c.read(path)
            expected[str(path)]=item['sha256'];expected[str(path.with_suffix('.log'))]=c.sha(path.with_suffix('.log'),check)
            known|=base.ids(actual.get('owned_process_identities',[]))
            if actual.get('owned_root'):known|=base.ids([actual['owned_root']])
            ob=actual.get('cleanup_observation',{})
            if actual.get('cleanup_confirmed') is not True or ob.get('unresolved')!=[] or ob.get('denial_count')!=0:
                uncertain.append(dict(scope='saved_supervisor',path=str(path),observation=ob))
        base.absent(owner,known,check);lease=modules['lock'].ResearchLock(cfg['lock']);lease.__enter__();lease.write_identity(preparers[0])
        base.absent(owner,known,check);awake=modules['awake'].PowerRequestGuard('CLASS-XGB-CONTRIBUTION-01-root');awake.__enter__();stats['_awake']=awake
        check(True);expected[str(OUT/'preparer-identity.json')]=c.sha(OUT/'preparer-identity.json',check)
        if state.get('audit_binding'):
            ref=state['audit_binding'];expected[ref['path']]=ref['sha256']
        if state.get('independent_audit'):
            ref=state['independent_audit'];need(c.sha(ref['path'],check)==ref['sha256'],'independent_comparison_changed')
            expected[ref['path']]=ref['sha256'];audit=c.read(ref['path']);sup=ref['supervisor']
            need(c.sha(sup['path'],check)==sup['sha256'] and c.read(sup['path'])==sup['record'],'inline_terminal_mismatch')
        for path,h in expected.items():need(c.sha(path,check)==h,'root_source_input_core_changed')
        temp=state.get('temporary_root')
        if temp:
            temp=Path(temp);need(temp.parent==(WORK/'t').resolve() and temp.name.startswith('cx-') and not temp.exists(),'owned_temp_not_removed')
        base.absent(owner,known,check);check(True)
    except BaseException as exc:failure(exc,'root_audit')
    finally:
        try:
            if awake is not None:awake.close();release=awake.record
            check(True);need(release is not None and release.get('release_API_verified') is True,'root_power_release_unconfirmed')
        except BaseException as exc:failure(exc,'root_power_release')
        if lease is not None:lease.__exit__(None,None,None)
    cleanup=(state.get('cleanup_confirmed') is True and state.get('temporary_cleanup_confirmed') is True
        and not uncertain and state.get('active_supervisor') is None and not bad)
    passed=(a.actual_exit_code==0 and state.get('status')=='completed_pending_root' and not state.get('error_history')
        and state.get('comparison_procedure_passed') is True and state.get('source_unchanged') is True and cleanup
        and len(state.get('contracts',[]))==3 and state.get('awake_guard',{}).get('release_API_verified') is True
        and audit is not None and c.result_qualified(audit,state.get('audit_binding',{}).get('sha256'),cfg['audit_payload']['expected_inventory']['sha256']))
    result=dict(schema='class-xgb-cache-root-closure-v1',technical_procedure_passed=bool(passed),
        actual_exec_session=a.actual_exec_session,actual_exec_exit_code_observed_by_root=a.actual_exit_code,actual_tool_evidence=a.actual_tool_evidence,
        cleanup_confirmed=bool(cleanup),source_unchanged=not bad and state.get('source_unchanged') is True,
        temporary_cleanup_confirmed=bool(cleanup),active_owned_processes=[],uncertain_owned=uncertain,changed_source_or_core=bad,
        owned_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],closure_preparer_identities=preparers,
        original_common_seconds=600,original_start_unix=state['start_unix'],original_start_monotonic=state['start_monotonic'],original_deadline_unix=wall,original_end_monotonic=end,
        first_failure=state.get('first_failure'),error_history=state.get('error_history',[]),root_errors=bad,
        independent_audit=state.get('independent_audit'),qualified_comparison=audit.get('comparison') if passed else None,
        quality_gate_passed=audit.get('quality_gate_passed') if passed else None,model_fits=0,API_calls=0,
        manifest_sha256=a.manifest_sha256,source_and_core_refs_rehashed=len(expected),root_resource_observation={k:v for k,v in stats.items() if not k.startswith('_')},
        awake_guard=release,promotion=False,submit=False,archive_build_or_release_qualification=False,
        own_actual_exit_and_fresh_complete_preparer_absence_required=True)
    output=OUT/'terminal-root-closure.json';need(not output.exists(),'exclusive_root_output')
    try:check(True);c.save(output,result);check(True)
    except BaseException as exc:
        failure(exc,'root_terminal_save');result.update(technical_procedure_passed=False,cleanup_confirmed=False,source_unchanged=False,qualified_comparison=None,quality_gate_passed=None)
        c.save(output,result);passed=False
    print(json.dumps(dict(technical_procedure_passed=bool(passed),quality_gate_passed=result['quality_gate_passed'],promotion=False),allow_nan=False))
    return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
