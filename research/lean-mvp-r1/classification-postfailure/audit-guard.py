"""One bounded post-failure saved-artifact audit of T6 classification.
T6 actualexec88656 exit1 and primary qualification FAIL remain authoritative.
No new ML/API jobs, no reset of the original T6 deadline. Root separately
confirms this wrapper actual exec and fresh closure; only a new audit folder is written.
"""
from pathlib import Path
import argparse,hashlib,json,math,os,subprocess,sys,time
import psutil
W=Path(__file__).resolve().parent;OUT=W/'t6-independent-classification-r1'
START=time.monotonic();START_WALL=time.time();END=START+300;END_WALL=START_WALL+300
MANIFEST_SHA='4b987c652864179465dc754e90e3d1c8c9ed7c0a2144db5c3339e4c8a607d07e'
PLAN_SHA='58e3364aa35c43c975ee0b8ade09210f6b058d41157b2a1fc4f4debdb6a35519'
AUDITOR_SHA='c08e9f0be13a708d67b3266518381d6f1be3b0f43c384ef6425634160d7e2783'
CLOSURE_SHA='ca4796c602ac213a2c48a652fcbb8461ddceadd51b4aa0b8f661ad59931b344a'
LAUNCH_SHA='808913336453f9fd8c37b10b08c770599ed73163cce048103b10ab75c6f7a61a'
CAMPAIGN_SHA='d8004d3c0c5daf2c3f5e599bc7db849f603e6679e59a7559462d0d5bfc53a973'
ORIGINAL_START=1792764087.858047
ORIGINAL_DEADLINE=1792774887.858047
def need(v,m):
    if not v:raise RuntimeError(m)
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def load(p):return json.loads(p.read_text('utf-8'))
def local(v):
    p=(W/v).resolve();need(p.is_relative_to(W),'path_outside_work');return p
def save(p,r,exclusive=False):
    raw=(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')
    if exclusive:
        with p.open('xb') as f:f.write(raw)
        return
    pending=p.with_name(p.name+'.pending')
    for attempt in range(21):
        try:pending.write_bytes(raw);os.replace(pending,p);return
        except PermissionError:
            if attempt==20:raise
            time.sleep(.05)
def ids(rows):
    result=set()
    for r in rows:
        p,b=r['pid'],r['create_time']
        need(type(p) is int and p>0 and type(b) in (int,float) and math.isfinite(b) and b>0,'invalid_identity')
        result.add((p,float(b)))
    return result
def absent(known):
    for pid,birth in known:
        try:
            if psutil.Process(pid).create_time()==birth:return False
        except psutil.NoSuchProcess:pass
    return True
def error(r,code,phase,exc=None):
    e=dict(code=code,phase=phase,unix=time.time(),exception_type=type(exc).__name__ if exc else None,
        errno=getattr(exc,'errno',None),winerror=getattr(exc,'winerror',None))
    r['error_history'].append(e);r.setdefault('first_failure',e);r['status']='technical_failure'
    r.update(artifact_procedure_checks_passed=False,qualified_salvage_artifacts=False,metrics=None)
def core():
    base=W/'t6/c/automl_runs/repair4';result={}
    need(base.is_dir(),'classification_core_missing')
    for parent,dirs,names in os.walk(base):
        for name in [*dirs,*names]:
            p=Path(parent)/name;need(not p.is_symlink() and not p.is_junction(),'core_link')
        for name in names:
            p=Path(parent)/name;need(not name.endswith(('.pending','.tmp')),'unfinished_core_file')
            result[p.relative_to(W).as_posix()]=sha(p)
    result['t6/c/submission.csv']=sha(W/'t6/c/submission.csv')
    return result
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--self-sha256',required=True);a=ap.parse_args()
    r=dict(status='preflight',parent_cap_seconds=300,whole_memory_cap_mib=512,compute_threads=1,
        started_unix=START_WALL,owned_root=dict(pid=os.getpid(),create_time=psutil.Process().create_time()),
        bootstrap_identities=[],owned_process_identities=[],cleanup_confirmed=True,source_unchanged=False,
        classification_core_unchanged=False,error_history=[],actual_wrapper_exec_code=None,
        root_actual_wrapper_exec_qualification='pending_root_observation_and_fresh_closure',metrics=None,
        fits=0,ML_API_calls=0,promotion=False,primary_campaign_modified=False,
        scope='postfailure_classification_saved_artifact_salvage_only',primary_exec_session=88656,
        primary_exec_exit_code_observed_by_root=1,primary_campaign_passed=False,
        primary_qualification='FAIL',whole_T6_success=False,qualified_salvage_artifacts=False,
        artifact_procedure_checks_passed=False,original_common_clock_extended=False)
    need(not OUT.exists(),'new_exclusive_audit_directory_required')
    manifest=W/'m3packet/manifest.json';plan=W/'t6/verification-plan.json';auditor=W/'repaired-mvp-r1-dev/evaluator_r4.py'
    campaign=W/'t6/campaign.json';launch=W/'m3packet/launch.json';closure=W/'m3packet/terminal-root-closure.json'
    need(sha(manifest)==MANIFEST_SHA and sha(plan)==PLAN_SHA and sha(auditor)==AUDITOR_SHA
         and sha(Path(__file__))==a.self_sha256 and sha(campaign)==CAMPAIGN_SHA
         and sha(launch)==LAUNCH_SHA and sha(closure)==CLOSURE_SHA,'fixed_source_or_plan_binding_failed')
    m=load(manifest);need(len(m['immutable_files'])==718,'expected718_source_refs')
    c=load(campaign);l=load(launch);proof=load(closure)
    deadline=c['absolute_deadline_unix'];mono=c['common_deadline_monotonic']
    need(c['status']=='technical_failure' and c['qualification']=='FAIL' and c['cleanup_confirmed'] is True
         and c['source_unchanged'] is True and c['active_supervisor'] is None
         and c['independent_audit'] is None and c['finished_unix']<=deadline
         and c['finished_monotonic']<=mono,'primary_failure_terminal_contract')
    need(l['status']=='coordinator_failed' and l['coordinator_exit_code']==1 and l['finished_unix']==c['finished_unix']
         and l['manifest_sha256']==MANIFEST_SHA and l['start_unix']==ORIGINAL_START
         and l['absolute_deadline_unix']==ORIGINAL_DEADLINE,'actual_failed_launch_binding')
    need(proof['actual_exec_session']==88656 and proof['actual_exec_exit_code_observed_by_root']==1
         and proof['cleanup_confirmed'] is True and proof['source_unchanged'] is True
         and proof['immutable_refs_rehashed']==718 and proof['active_owned_processes']==[]
         and proof['uncertain_owned']==[] and proof['parent_terminal_procedure_qualified'] is False
         and proof['raw_campaign_flags']['qualification']=='FAIL','root_terminal_closure_binding')
    prior=ids(proof['owned_identities'])|ids(proof['closure_preparer_identities'])
    need(len(proof['owned_identities'])==452 and len(proof['closure_preparer_identities'])==2
         and len(prior)==454 and absent(prior),'fresh_all454_closed_identities_required')
    need(c['manifest_sha256']==MANIFEST_SHA and c['verification_plan_sha256']==PLAN_SHA
         and deadline==ORIGINAL_DEADLINE and c['start_unix']==ORIGINAL_START
         and abs(deadline-c['start_unix']-10800)<=1e-6
         and abs(mono-c['start_monotonic']-10800)<=1e-6,'original_clock_binding_failed')
    need(deadline-time.time()>=330 and mono-time.monotonic()>=330,'minimum_original_budget330s_unavailable')
    entry=next((t for t in c['tasks'] if t['kind']=='classification'),None)
    need(entry is not None and entry['status']=='ok' and entry['exit_code']==0 and entry['cleanup_confirmed'] is True,'sealed_classification_entry_not_closed')
    reference={k:entry[k] for k in ['code','supervisor_path','supervisor_sha256','seal']}
    need(reference['code']=='c' and reference['supervisor_path']=='t6/c/supervisor.json'
         and reference['seal']['path']=='t6/c-seal.json','unexpected_classification_reference')
    sup=load(local(reference['supervisor_path']));closed=ids(sup['owned_process_identities'])
    if sup.get('owned_root'):closed|=ids([sup['owned_root']])
    closed|=ids(l['launcher_identities'])|ids([c['owned_root']])|ids(c['coordinator_bootstrap_identities'])
    need(closed<=prior and sup['status']=='ok' and sup['exit_code']==0 and sup['cleanup_confirmed'] is True
         and absent(closed),'classification_owned_processes_not_closed')
    r.update(primary_campaign_sha256=CAMPAIGN_SHA,primary_launch_sha256=LAUNCH_SHA,
        root_terminal_closure_sha256=CLOSURE_SHA,prior_closed_identity_count=len(prior),
        original_absolute_deadline_unix=deadline,original_common_deadline_monotonic=mono,
        original_start_unix=ORIGINAL_START)
    def clock():
        need(time.monotonic()<END and time.time()<END_WALL and time.monotonic()<mono and time.time()<deadline,'audit_parent_or_original_deadline')
        need(abs((mono-time.monotonic())-(deadline-time.time()))<=5,'clock_disagreement')
    def guard():
        clock();need(sha(manifest)==MANIFEST_SHA and sha(plan)==PLAN_SHA and sha(auditor)==AUDITOR_SHA
            and sha(Path(__file__))==a.self_sha256 and sha(campaign)==CAMPAIGN_SHA
            and sha(launch)==LAUNCH_SHA and sha(closure)==CLOSURE_SHA,'fixed_reference_changed')
        for n,h in m['immutable_files'].items():clock();need(sha(local(n))==h,'immutable_ref_changed:'+n)
        current=load(campaign);row=next((t for t in current['tasks'] if t['kind']=='classification'),None)
        need(row is not None and {k:row[k] for k in reference}==reference,'classification_seal_reference_changed')
        need(sha(local(reference['supervisor_path']))==reference['supervisor_sha256'],'classification_supervisor_changed')
        need(sha(local(reference['seal']['path']))==reference['seal']['sha256'],'classification_seal_receipt_changed')
        seal=load(local(reference['seal']['path']))
        need(seal['cleanup_confirmed'] is True and seal['source_unchanged'] is True
             and core()==seal['files_sha256'] and absent(prior),'classification_core_or_closure_changed')
        r.update(source_unchanged=True,classification_core_unchanged=True,immutable_refs_verified=718)
    guard();OUT.mkdir();save(OUT/'supervisor.json',r,True)
    child=None;child_root=None;known=set();denied=[];peak=0
    def own():
        live={};todo=list(known)
        while todo:
            key=todo.pop()
            if key in live:continue
            try:
                q=psutil.Process(key[0])
                if q.create_time()!=key[1]:continue
                live[key]=q
                for sub in q.children():
                    birth=sub.create_time();fresh=psutil.Process(sub.pid)
                    if fresh.create_time()==birth and fresh.ppid()==key[0] and birth>=key[1] and psutil.Process(key[0]).create_time()==key[1]:
                        new=(sub.pid,birth);known.add(new);todo.append(new)
            except psutil.NoSuchProcess:pass
            except psutil.AccessDenied:denied.append(key)
        return live
    def signal_own(key,kill=False):
        try:
            q=psutil.Process(key[0])
            if q.create_time()==key[1]:(q.kill if kill else q.terminate)()
        except psutil.NoSuchProcess:pass
        except psutil.AccessDenied:denied.append(key)
    try:
        parent=psutil.Process().parent()
        while parent is not None:
            birth=parent.create_time()
            if not any(Path(v).resolve()==Path(__file__).resolve() for v in parent.cmdline()):break
            need(parent.create_time()==birth,'bootstrap_identity_changed')
            r['bootstrap_identities'].append(dict(pid=parent.pid,create_time=birth));parent=parent.parent()
        env={k:v for k,v in os.environ.items() if k.upper() in {'PATH','PATHEXT','SYSTEMROOT','WINDIR','COMSPEC','LOCALAPPDATA'}}
        env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',AUTOML_THREADS='1',
            OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
        argv=[sys.executable,'-B','-X','utf8',str(auditor),'--work-root',str(W),'--task-root','t6','--run-name','repair4',
            '--task','classification','--plan','t6/verification-plan.json','--manifest','m3packet/manifest.json',
            '--archive','m3packet/lean-source.zip','--output','t6-independent-classification-r1/audit.json']
        guard();need(END-time.monotonic()>10,'cleanup_reserve_unavailable')
        need(deadline-time.time()>=330 and mono-time.monotonic()>=330,'minimum_original_budget330s_unavailable_before_child')
        child_end=END-15
        with (OUT/'auditor.log').open('x',encoding='utf-8') as log:
            child=subprocess.Popen(argv,cwd=W,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        q=psutil.Process(child.pid);child_root=(q.pid,q.create_time());known.add(child_root)
        r.update(status='running_auditor',cleanup_confirmed=False);save(OUT/'supervisor.json',r)
        while True:
            live=own();need(not denied,'own_observation_denied');rss=psutil.Process().memory_info().rss
            for pid,birth in set(live)|ids(r['bootstrap_identities']):
                try:
                    q=psutil.Process(pid)
                    if q.create_time()==birth:rss+=q.memory_info().rss
                except psutil.NoSuchProcess:pass
            peak=max(peak,rss);need(rss<=512*2**20,'whole_memory_limit');clock()
            need(time.monotonic()<child_end,'auditor_child_timeout')
            if child.poll() is not None:break
            time.sleep(.1)
        need(child.returncode==0,'auditor_nonzero_exit');guard()
        audit=load(OUT/'audit.json')
        row=audit.get('tasks',{}).get('classification',{})
        r.update(audit_sha256=sha(OUT/'audit.json'),raw_R4_status=audit.get('status'),
            raw_R4_status_is_not_whole_T6_success=True,raw_audit_preserved=True,
            raw_task_errors=row.get('errors'),raw_numeric_values_preserved_in_audit_file=True,
            missing_failed_values_zero_imputed=False,
            audit_scope_status='saved_artifacts_pass_pending_wrapper_terminal' if audit.get('artifact_procedure_checks_passed') is True
                else 'independent_audit_partial_unqualified')
        need(audit.get('artifact_procedure_checks_passed') is True and audit.get('audit_within_original_common_clock') is True,'R4_artifact_checks_failed')
        need(set(audit.get('tasks',{}))=={'classification'} and audit['tasks']['classification']['procedure_passed'] is True
             and audit.get('manifest_sha256')==MANIFEST_SHA and audit.get('campaign_sha256')==CAMPAIGN_SHA
             and audit.get('campaign_terminal_confirmed') is True and audit.get('new_model_fits')==0
             and audit.get('api_calls')==0,'R4_task_scope_or_lineage_failed')
        r.update(status='child_audit_ok_pending_root_wrapper_exec',child_exit_code=child.returncode,
            audit_sha256=sha(OUT/'audit.json'),raw_R4_status=audit.get('status'),
            raw_R4_status_is_not_whole_T6_success=True,artifact_procedure_checks_passed=True,
            qualified_salvage_artifacts=True)
    except BaseException as exc:error(r,str(exc) if type(exc) is RuntimeError else 'auditor_operation_failed','auditor',exc)
    finally:
        try:
            for key in sorted(own(),key=lambda k:k[1],reverse=True):signal_own(key)
            if child is not None:
                try:child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    need(child_root in known,'unverified_auditor_root');signal_own(child_root,True);child.wait(timeout=3)
            for key in own():signal_own(key,True)
            until=min(END,time.monotonic()+2)
            while own() and time.monotonic()<until:time.sleep(.05)
            r['cleanup_confirmed']=not own() and not denied
        except BaseException as exc:r['cleanup_confirmed']=False;error(r,'cleanup_failed','terminal_cleanup',exc)
        try:guard()
        except BaseException as exc:r.update(source_unchanged=False,classification_core_unchanged=False);error(r,str(exc) if type(exc) is RuntimeError else 'terminal_guard_operation_failed','terminal_guard',exc)
        r.update(owned_process_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],
            child_exit_code=child.returncode if child is not None else None,
            peak_owned_tree_rss_mib=peak/2**20,observation_denial_count=len(denied),finished_unix=time.time(),
            seconds=time.monotonic()-START,original_deadline_unix=deadline)
        if not r['cleanup_confirmed']:error(r,'cleanup_unconfirmed','terminal')
        if time.monotonic()>=END or time.time()>=END_WALL or time.time()>=deadline:error(r,'terminal_over_cap','terminal')
        save(OUT/'supervisor.json',r)
        if time.monotonic()>=END or time.time()>=END_WALL or time.time()>=deadline:
            error(r,'terminal_write_over_cap','terminal_write');save(OUT/'supervisor.json',r)
    print(json.dumps(r,ensure_ascii=False,allow_nan=False,separators=(',',':')))
    return 0 if r['status']=='child_audit_ok_pending_root_wrapper_exec' and r['cleanup_confirmed'] and r['source_unchanged'] and r['classification_core_unchanged'] else 1
if __name__=='__main__':raise SystemExit(main())
