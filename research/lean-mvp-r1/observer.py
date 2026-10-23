"""Read-only t6 observation by default; optional narrowly merged status writes.
Never fits, calls a model/API, signals processes, acquires a lock, adopts old
PPID edges or claims actual exec completion. Only known exact owners and their
freshly proved current descendants are inspected. Root confirms terminal exec.
"""
from pathlib import Path
import argparse,copy,hashlib,json,math,os,sys,time
import psutil

W=Path(__file__).resolve().parent
MANIFEST='4b987c652864179465dc754e90e3d1c8c9ed7c0a2144db5c3339e4c8a607d07e'
COMMIT='7215b97cdc6cc7c322c5b11f2cb0f539a163cda0'
R4='c08e9f0be13a708d67b3266518381d6f1be3b0f43c384ef6425634160d7e2783'
BEGUN=time.monotonic()
def need(v,reason):
    if not v:raise RuntimeError(reason)
def bound():need(time.monotonic()-BEGUN<30,'observer_30s_bound')
def local(v):
    p=(W/v).resolve();need(p.is_relative_to(W),'reference_outside_work');return p
def relative(p):return p.relative_to(W).as_posix()
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def load(p):return json.loads(p.read_text('utf-8'))
def finite(value):
    if isinstance(value,float) and not math.isfinite(value):return None
    if isinstance(value,dict):return {str(k):finite(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [finite(v) for v in value]
    return value
def identity(row):
    p,b=row['pid'],row['create_time']
    need(type(p) is int and p>0 and type(b) in (int,float) and math.isfinite(b) and b>0,'invalid_known_identity')
    return p,float(b)
def atomic(path,raw,before_replace=None):
    pending=path.with_name(path.name+'.observer-pending')
    for attempt in range(21):
        try:
            pending.write_bytes(raw)
            if before_replace is not None:before_replace()
            os.replace(pending,path);return
        except PermissionError:
            if attempt==20:raise
            time.sleep(.05)
def json_bytes(value):return (json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')
def observe(args):
    report=dict(status='observing',recorded_epoch=time.time(),exec_session=args.exec_session,
        actual_exec_exit_code=None,root_actual_exec_qualification='pending_root_confirmation_and_fresh_closure',
        no_fits=True,ML_API_calls=0,signals_sent=0,locks_acquired=0,official_score=None,promotion=False,
        source_manifest_sha256=MANIFEST,source_checks={},tasks={},current_experiments=[],metrics=None)
    known=set();supervisors={};manifest_path=W/'m3packet/manifest.json'
    try:
        need(args.exec_session==88656,'wrong_t6_exec_session');need(sha(Path(__file__))==args.self_sha256,'observer_source_changed')
        need(sha(manifest_path)==MANIFEST,'manifest_changed');m=load(manifest_path)
        need(len(m['immutable_files'])==718,'immutable_inventory_not718')
        verified=0
        for name,expected in m['immutable_files'].items():
            bound();need(sha(local(name))==expected,'immutable_ref_changed:'+name);verified+=1
        report['immutable_refs_verified']=verified
        l=load(W/'m3packet/launch.json');c=load(W/'t6/campaign.json')
        need(l['manifest_sha256']==c['manifest_sha256']==MANIFEST and l['git_commit']==COMMIT,'launch_or_campaign_binding_changed')
        start,deadline=l['start_unix'],l['absolute_deadline_unix']
        need(type(start) in (int,float) and type(deadline) in (int,float) and math.isfinite(start) and math.isfinite(deadline)
             and abs(deadline-start-10800)<=1e-6 and c['start_unix']==start and c['absolute_deadline_unix']==deadline
             and abs(c['common_deadline_monotonic']-c['start_monotonic']-10800)<=1e-6,'fresh10800_clock_binding_changed')
        skew=(c['common_deadline_monotonic']-time.monotonic())-(deadline-time.time())
        need(abs(skew)<=5,'wall_monotonic_disagreement')
        report.update(status=c['status'],launch_status=l['status'],parent_reported_exit_code=l.get('coordinator_exit_code'),
            start_unix=start,absolute_deadline_unix=deadline,elapsed_seconds=max(0,time.time()-start),
            remaining_seconds=max(0,deadline-time.time()),wall_monotonic_skew_seconds=skew,
            active_supervisor=c.get('active_supervisor'),campaign_cleanup_claim=c.get('cleanup_confirmed'),
            campaign_source_claim=c.get('source_unchanged'),first_failure=c.get('first_failure'),
            terminal_error=(c.get('error_history') or [None])[-1],awake_guard=c.get('awake_guard'),
            completed_gates=[g['name'] for g in c.get('gates',[])],completed_tasks=[t['kind'] for t in c.get('tasks',[])])
        known|={identity(r) for r in l['launcher_identities']+c['coordinator_bootstrap_identities']+[c['owned_root']]}
        refs={r['path']:r for r in c.get('supervisors',[])}
        if c.get('active_supervisor'):refs.setdefault(c['active_supervisor'],None)
        for name in ['t6/g/source-supervisor.json','t6/g/exact-supervisor.json','t6/r/supervisor.json','t6/c/supervisor.json','t6/final-audit-supervisor.json']:
            if local(name).is_file():refs.setdefault(name,None)
        for name,ref in refs.items():
            p=local(name);need(p.is_relative_to(W/'t6'),'supervisor_outside_t6');s=load(p)
            if ref is not None:need(sha(p)==ref['sha256'],'closed_supervisor_changed')
            for row in s.get('owned_process_identities',[])+s.get('observed_worker_roots',[]):known.add(identity(row))
            if s.get('owned_root'):known.add(identity(s['owned_root']))
            supervisors[name]={k:s.get(k) for k in ['status','exit_code','cleanup_confirmed','heartbeat_unix','first_failure','failure_code']}
        report['supervisors']=supervisors
        for name in ['source/results.json','source/progress.json']:
            p=W/'t6/g'/name
            if p.is_file():
                d=load(p);rows=d.get('checks',[])
                report['source_checks']=dict(expected=sum(m['registry'].values()),
                    passed_so_far=sum(r.get('observed_checks',0) or 0 for r in rows if r.get('passed') is True),
                    skipped=sum(r.get('skipped_checks',0) or 0 for r in rows),scripts_observed=len(rows),
                    all_scripts_reported_passed=d.get('passed'),scope='Saved primary technical-gate metadata')
                break
        for code,kind in [('r','regression'),('c','classification')]:
            p=W/'t6'/code/'automl_runs/repair4/progress.json'
            if not p.is_file():continue
            progress=load(p);rows=progress.get('experiments',[])
            report['tasks'][kind]=dict(completed_experiments=len(rows),
                last_completed_experiment=rows[-1].get('experiment_index') if rows else None,
                last_status=rows[-1].get('status') if rows else None,planner_calls=len(progress.get('calls',[])),
                metric_scope='Parent-reported progress only; metrics withheld pending actual R4 audit')
            # This frozen progress ABI has no process identities; do not invent
            # a new ownership grant from arbitrary nested metric/result fields.
            need(not progress.get('owned_process_identities'),'unexpected_progress_ownership_records')
        live,absent,reused,uncertain=[],0,0,[];todo=list(known);visited=set()
        while todo:
            bound();key=todo.pop()
            if key in visited:continue
            visited.add(key)
            try:
                q=psutil.Process(key[0])
                if q.create_time()!=key[1]:reused+=1;continue
                row=dict(pid=key[0],create_time=key[1],ppid=q.ppid(),rss_mib=q.memory_info().rss/2**20)
                for child in q.children():
                    birth=child.create_time();fresh=psutil.Process(child.pid)
                    if fresh.create_time()!=birth or fresh.ppid()!=key[0] or birth<key[1]:continue
                    if psutil.Process(key[0]).create_time()!=key[1]:continue
                    child_key=(child.pid,birth);known.add(child_key);todo.append(child_key)
                argv=q.cmdline()  # Exact owned process only; argv is never emitted.
                if any(Path(v).name in {'automl_worker.py','agent_worker.py'} for v in argv):
                    job=Path(argv[-1]).resolve()
                    if job.is_relative_to(W/'t6/r') or job.is_relative_to(W/'t6/c'):
                        report['current_experiments'].append(dict(pid=key[0],create_time=key[1],job=relative(job)))
                live.append(row)
            except psutil.NoSuchProcess:absent+=1
            except psutil.AccessDenied:uncertain.append(dict(pid=key[0],create_time=key[1],reason='AccessDenied'))
        report.update(known_identity_count=len(known),fresh_known_active=live,fresh_absent_count=absent,
            reused_PID_exclusions=reused,fresh_uncertain=uncertain)
        audit_ref=c.get('independent_audit')
        if audit_ref and audit_ref.get('path') and audit_ref.get('sha256'):
            p=local(audit_ref['path']);need(sha(p)==audit_ref['sha256'],'R4_audit_receipt_changed')
            plan=load(W/'t6/verification-plan.json');audit=load(p)
            need(plan['verifier_source_sha256']==R4 and audit['manifest_sha256']==MANIFEST,'audit_revision_changed')
            if audit.get('artifact_procedure_checks_passed') is True and audit.get('audit_within_original_common_clock') is True:
                report['metrics']={k:v.get('selected_cut_mean') for k,v in audit.get('tasks',{}).items()}
                report['metric_scope']='Actual frozen R4 saved-artifact audit; terminal root qualification still pending'
        need(sha(manifest_path)==MANIFEST and sha(Path(__file__))==args.self_sha256,'observer_or_manifest_changed_during_read')
        report['source_check_status']='718_verified'
    except BaseException as exc:
        report.update(status='observation_failed',observer_failure=dict(type=type(exc).__name__,reason=str(exc)),metrics=None)
    report['observer_seconds']=time.monotonic()-BEGUN
    return finite(report)
def write_status(report):
    target=W/'SESSION_STATE.json';before=target.read_bytes();old=json.loads(before.decode('utf-8'));updated=copy.deepcopy(old)
    updated.setdefault('lean_mvp',{}).update(observed_status=report['status'],last_observer=report,observer_recorded_epoch=report['recorded_epoch'])
    if report.get('first_failure') or report.get('observer_failure'):
        updated['lean_mvp'].setdefault('observer_first_failure',report.get('first_failure') or report['observer_failure'])
    updated['heartbeat_last']=report
    need({k:v for k,v in old.items() if k not in {'lean_mvp','heartbeat_last'}}==
         {k:v for k,v in updated.items() if k not in {'lean_mvp','heartbeat_last'}},'unrelated_state_mutation')
    def unchanged():need(target.read_bytes()==before,'concurrent_state_change_abort')
    atomic(target,json_bytes(updated),unchanged)
    output=W.parent/'outputs/lean-mvp-status.txt'
    # Existing task deliverables normally live at workspace/outputs, not work/.
    output.parent.mkdir(parents=True,exist_ok=True)
    text=(f"Lean MVP t6: {report['status']}\nExec session: {report['exec_session']} (root terminal confirmation pending)\n"
          f"Source: {report.get('source_check_status','not confirmed')}\nRemaining seconds: {report.get('remaining_seconds')}\n"
          f"Progress: {json.dumps(report.get('tasks',{}),ensure_ascii=False,allow_nan=False)}\n"
          f"Current workers: {json.dumps(report.get('current_experiments',[]),ensure_ascii=False,allow_nan=False)}\n"
          f"Metrics: {json.dumps(report.get('metrics'),ensure_ascii=False,allow_nan=False)}\nOfficial score: null\n")
    atomic(output,text.encode('utf-8'))
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--self-sha256',required=True)
    p.add_argument('--exec-session',type=int,required=True);p.add_argument('--write-status',action='store_true');a=p.parse_args()
    report=observe(a)
    if a.write_status:write_status(report)
    print(json.dumps(report,ensure_ascii=False,allow_nan=False,separators=(',',':')))
    return 1 if report['status']=='observation_failed' else 0
if __name__=='__main__':raise SystemExit(main())
