"""Prospective root audit: own60 inside the same original6000; no fitting."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, math, os, time

PACKET=Path(__file__).resolve().parent
WORK=PACKET.parents[1]
OUT=WORK/'brq3'
LAUNCHER_PATH=WORK/'venv/Scripts/python.exe'
LAUNCHER_SHA='d59c9a894b319828d023f3aa83d9a3488d2339f9e27e60e49b02abb0d53cf538'

def need(value,code):
    if not value:raise RuntimeError(code)

def load(path):return json.loads(Path(path).read_text('utf-8'))

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value);return value

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
    for key in ('manifest','manifest-sha256','self-sha256','driver-sha256','campaign-sha256','actual-tool-evidence'):
        p.add_argument('--'+key,required=True)
    p.add_argument('--actual-exec-session',type=int,default=None)
    p.add_argument('--actual-exit-code',type=int,required=True)
    p.add_argument('--launch-parent-pid',type=int,required=True,help='Actual declared PowerShell shell PID, direct or one pinned venv launcher above')
    p.add_argument('--launch-parent-create-time',type=float,required=True,help='Actual declared shell Unix birth, invariant float serialization')
    a=p.parse_args();own_unix,own_mono=time.time(),time.monotonic()
    import psutil
    # Capture this actual helper/bootstrap before source, manifest or campaign validation.
    preparers,parent_observation=capture(psutil,a.launch_parent_pid,a.launch_parent_create_time)
    early=OUT/'root-preparer-identity.json'
    need(OUT.is_dir() and not early.exists(),'exclusive_actual_root_preparer_receipt')
    with early.open('x',encoding='utf-8') as stream:json.dump(dict(identities=preparers,launch_parent_observation=parent_observation),stream,indent=2,allow_nan=False)
    need(parent_observation['verified'] is True,'root_explicit_direct_launch_parent_unconfirmed')
    need(__debug__ and Path(a.manifest).is_absolute() and sha(__file__)==a.self_sha256,'root_source_or_absolute_manifest_required')
    driver=PACKET/'run_controller.py';need(sha(driver)==a.driver_sha256,'root_driver_source_changed')
    c=imported('_brq_root_source',driver)
    campaign=OUT/'campaign.json';need(sha(campaign)==a.campaign_sha256,'actual_terminal_campaign_changed')
    state=load(campaign);wall=state['absolute_deadline_unix'];end=state['common_deadline_monotonic']
    need(wall==state['start_unix']+6000 and end==state['start_monotonic']+6000,'same_assigned_original6000_required')
    need(own_mono+60<=end and own_unix+60<=wall,'full_root60_inside_original_common_required')
    cfg=c.config(a.manifest,a.manifest_sha256,a.driver_sha256)
    need(cfg['immutable_files'].get(str(Path(__file__).resolve()))==a.self_sha256,'new_root_auditor_must_be_frozen')
    modules={}
    for key,(relative,h) in c.HELPERS.items():
        need(sha(WORK/relative)==h,'root_trusted_helper_changed');modules[key]=c.imported('_brq_root_'+key,WORK/relative)
    owner=modules['owner'];statistics={};pulse=c.guard(own_mono,min(own_mono+60,end),min(own_unix+60,wall),owner,preparers,statistics)
    bad=[];uncertain=list(state.get('cleanup_uncertainty',[]));known=set();audit=None;release=None;awake=None;lease=None
    expected={str(campaign):a.campaign_sha256,str(early):sha(early),str(Path(a.manifest)):a.manifest_sha256}
    def check(force=False):pulse(force=force)
    def failure(exc,phase):
        bad.append(dict(phase=phase,exception_type=type(exc).__name__,code=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__))
    try:
        check(True);known=c.predecessor(cfg,check)
        known|=c.ids(state.get('owned_process_identities',[]))
        known|=c.ids([state['owned_root']]+state.get('coordinator_bootstrap_identities',[]))
        for item in state.get('supervisors',[]):
            path=Path(item['path']);path=path if path.is_absolute() else WORK/path
            need(c.sha(path,check)==item['sha256'],'root_saved_supervisor_changed')
            actual=c.read(path);expected[str(path)]=item['sha256']
            expected[str(path.with_suffix('.log'))]=c.sha(path.with_suffix('.log'),check)
            known|=c.ids(actual.get('owned_process_identities',[]))
            if actual.get('owned_root'):known|=c.ids([actual['owned_root']])
            ob=actual.get('cleanup_observation',{})
            if actual.get('cleanup_confirmed') is not True or ob.get('unresolved')!=[] or ob.get('denial_count')!=0:
                uncertain.append(dict(scope='saved_supervisor',path=str(path),observation=ob))
        c.absent(owner,known,check)
        lease=modules['lock'].ResearchLock(cfg['lock']);lease.__enter__();lease.write_identity(preparers[0])
        c.absent(owner,known,check);awake=modules['awake'].PowerRequestGuard('br-fixed-standard-root-audit')
        awake.__enter__();statistics['_awake']=awake;check(True)
        expected.update(cfg['immutable_files'])
        expected[str(OUT/'preparer-identity.json')]=c.sha(OUT/'preparer-identity.json',check)
        if state.get('pretruth_barrier'):
            ref=state['pretruth_barrier'];expected[ref['path']]=ref['sha256']
        for entry in state.get('tasks',[]):
            ref=entry['seal'];need(c.sha(ref['path'],check)==ref['sha256'],'root_core_seal_changed')
            expected[ref['path']]=ref['sha256'];expected.update(c.read(ref['path'])['files_sha256'])
            sup=entry['supervisor'];need(c.sha(sup['path'],check)==sup['sha256'] and c.read(sup['path'])==sup['record'],'root_task_terminal_mismatch')
        if state.get('independent_audit'):
            ref=state['independent_audit'];need(c.sha(ref['path'],check)==ref['sha256'],'root_independent_audit_changed')
            expected[ref['path']]=ref['sha256'];audit=c.read(ref['path'])
            sup=ref['supervisor'];need(c.read(sup['path'])==sup['record'] and c.sha(sup['path'],check)==sup['sha256'],
                'root_audit_saved_terminal_mismatch')
        for path,h in expected.items():need(c.sha(path,check)==h,'root_immutable_or_core_posthash_changed')
        temp=state.get('temporary_root')
        if temp:
            temp=Path(temp);need(temp.is_relative_to((WORK/'t').resolve()) and temp.name.startswith('bq-') and not temp.exists(),
                'owned_shallow_temp_not_removed')
        c.absent(owner,known,check);check(True)
    except BaseException as exc:failure(exc,'root_audit')
    finally:
        try:
            if awake is not None:awake.close();release=awake.record
            check(True)
            need(release is not None and release.get('release_API_verified') is True,'root_power_release_unconfirmed')
        except BaseException as exc:failure(exc,'root_power_release')
        if lease is not None:lease.__exit__(None,None,None)
    cleanup=(state.get('cleanup_confirmed') is True and state.get('temporary_cleanup_confirmed') is True
        and not uncertain and state.get('active_supervisor') is None and not bad)
    passed=(a.actual_exit_code==0 and state.get('status')=='completed_pending_root' and not state.get('error_history')
        and state.get('artifact_procedure_passed') is True and state.get('source_unchanged') is True
        and state.get('awake_guard',{}).get('release_API_verified') is True and cleanup
        and len(state.get('tasks',[]))==2 and len(state.get('contracts',[]))==7
        and audit is not None and audit.get('artifact_procedure_passed') is True
        and audit.get('manifest_sha256')==a.manifest_sha256 and audit.get('audit_within_original_common_clock') is True)
    result=dict(schema='br-standard-qualification-root-closure-v1',technical_procedure_passed=bool(passed),
        actual_exec_session=a.actual_exec_session,actual_exec_exit_code_observed_by_root=a.actual_exit_code,
        actual_tool_evidence=a.actual_tool_evidence,cleanup_confirmed=bool(cleanup),source_unchanged=not bad and state.get('source_unchanged') is True,
        active_owned_processes=[],uncertain_owned=uncertain,changed_source_or_core=bad,
        owned_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],closure_preparer_identities=preparers,
        early_preparer_receipt_sha256=expected[str(early)],original_common_seconds=6000,
        original_start_unix=state['start_unix'],original_deadline_unix=wall,original_start_monotonic=state['start_monotonic'],original_end_monotonic=end,
        raw_parent_elapsed_seconds=state.get('elapsed_common_seconds'),first_failure=state.get('first_failure'),
        error_history=state.get('error_history',[]),root_errors=bad,independent_audit=state.get('independent_audit'),
        qualified_ML_metrics=audit.get('quality_metric') if passed else None,manifest_sha256=a.manifest_sha256,
        archive_sha256=c.ARCHIVE_SHA,immutable_and_core_refs_rehashed=len(expected),root_resource_observation={k:v for k,v in statistics.items() if not k.startswith('_')},
        awake_guard=release,root_seconds_reserved_inside_cleanup300=60,official_hidden_test_score=None,promotion=False,submit=False,
        own_actual_exec_exit_and_fresh_preparer_absence_required=True)
    output=OUT/'terminal-root-closure.json';need(not output.exists(),'exclusive_new_root_output')
    try:
        check(True);c.save(output,result);check(True)
    except BaseException as exc:
        failure(exc,'root_terminal_save');result.update(technical_procedure_passed=False,cleanup_confirmed=False,source_unchanged=False,qualified_ML_metrics=None)
        c.save(output,result);passed=False
    print(json.dumps(dict(technical_procedure_passed=bool(passed),qualified_ML_metrics=result['qualified_ML_metrics']),allow_nan=False))
    return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
