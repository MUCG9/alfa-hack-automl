"""One separately declared no-fit R4 audit, only after every primary owner closes.
Preserve original parent exit/failure and original clock. No model/API imports.
Only the auditor child tree may receive bounded exact-identity cleanup signals.
"""
from pathlib import Path
import argparse,hashlib,json,math,os,subprocess,sys,time
import psutil
W=Path(__file__).resolve().parent;OUT=W/'t5-independent-all-r4'
START=1792750977.2275486;DEADLINE=1792761777.2275486
SOURCE='c08e9f0be13a708d67b3266518381d6f1be3b0f43c384ef6425634160d7e2783'
MANIFEST='ac28e6da826809e3fe334a6096229ad6410500d7f91a65071987f37ac80ce716'
ARCHIVE='cfd5ff3b44f77227b15b130c16762e6c8349ac53f02a53462883680aad436459'
def need(v,msg):
    if not v:raise RuntimeError(msg)
def load(p):return json.loads(p.read_text('utf-8'))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def local(v):
    p=(W/v).resolve();need(p.is_relative_to(W),'path_outside_work');return p
def rel(p):return p.relative_to(W).as_posix()
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
    result=True
    for p,b in known:
        try:
            if psutil.Process(p).create_time()==b:result=False
        except psutil.NoSuchProcess:pass
    return result
def primary():
    cp=W/'t5/campaign.json';lp=W/'m2packet/continuation3-launch.json';c,l=load(cp),load(lp)
    need(c['start_unix']==l['start_unix']==START and c['absolute_deadline_unix']==l['absolute_deadline_unix']==DEADLINE
         and c['manifest_sha256']==l['manifest_sha256']==MANIFEST,'primary_clock_changed')
    if l.get('status') not in {'coordinator_completed','coordinator_failed','coordinator_failed_late'} or 'coordinator_exit_code' not in l:return None
    if c.get('status') in {'starting','running','verifying'}:return None
    need(c.get('cleanup_confirmed') is True and c.get('source_unchanged') is True
         and c.get('active_supervisor') is None,'primary_terminal_cleanup_unknown')
    known=ids(l['launcher_identities'])|ids([c['owned_root']])|ids(c['coordinator_bootstrap_identities'])
    files={rel(cp):sha(cp),rel(lp):sha(lp)}
    refs={r['path']:r for r in c.get('supervisors',[])}
    for name in ['t5/r/supervisor.json','t5/c/supervisor.json','t5/final-audit-supervisor.json']:
        if local(name).exists():refs.setdefault(name,None)
    need('t5/r/supervisor.json' in refs and 't5/c/supervisor.json' in refs,'both_task_supervisors_required')
    for name,ref in refs.items():
        p=local(name);need(p.is_relative_to(W/'t5'),'supervisor_outside_primary');s=load(p);h=sha(p)
        if ref is not None:need(ref['cleanup_confirmed'] is True and h==ref['sha256'],'supervisor_reference_changed')
        need(s.get('cleanup_confirmed') is True,'primary_supervisor_cleanup_unknown')
        known|=ids(s['owned_process_identities']);files[name]=h
    for task in c.get('tasks',[]):known|=ids(task.get('owned_process_identities',[]))
    if not absent(known):return None
    return c,l,known,files
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ['self','source','plan','declaration']:ap.add_argument('--'+n+'-sha256',required=True)
    a=ap.parse_args();refs={Path(__file__).resolve():a.self_sha256,W/'repaired-mvp-r1-dev/evaluator_r4.py':a.source_sha256,
        OUT/'plan.json':a.plan_sha256,OUT/'declaration.json':a.declaration_sha256,
        W/'m2packet/manifest-continuation-r3.json':MANIFEST,W/'m2packet/repaired-source.zip':ARCHIVE}
    need(a.source_sha256==SOURCE,'wrong_R4_source');need(not (OUT/'audit.json').exists(),'no_audit_retry')
    def frozen():
        for p,h in refs.items():need(sha(p)==h,'frozen_reference_changed:'+rel(p))
    frozen();plan=load(OUT/'plan.json');decl=load(OUT/'declaration.json')
    need(plan['verifier_source_sha256']==SOURCE and plan['execution_manifest_sha256']==MANIFEST
         and plan['original_absolute_deadline_unix']==DEADLINE,'plan_clock_or_source_changed')
    need(decl['watcher_source_sha256']==a.self_sha256 and decl['plan_sha256']==a.plan_sha256,'declaration_binding_changed')
    r=dict(status='waiting_primary_terminal',started_unix=time.time(),original_absolute_deadline_unix=DEADLINE,
        clock_reset=False,attempts=0,metrics=None,cleanup_confirmed=True,source_sha256=a.source_sha256,
        plan_sha256=a.plan_sha256,declaration_sha256=a.declaration_sha256,waiter_memory_cap_mib=64,
        auditor_whole_memory_cap_mib=512,root_actual_exec_qualification='pending',promotion=False,submit=False,
        scope='Separate saved-artifact R4 verification; primary failure/result remains unchanged')
    save(OUT/'watcher.json',r,True);child=None;root_identity=None;known=set();denied=[];bootstrap=[];end=None
    def own():
        live={};todo=list(known)
        while todo:
            key=todo.pop()
            if key in live:continue
            try:
                q=psutil.Process(key[0])
                if q.create_time()!=key[1]:continue
                live[key]=q
                for c in q.children():new=(c.pid,c.create_time());known.add(new);todo.append(new)
            except psutil.NoSuchProcess:pass
            except psutil.AccessDenied:denied.append(key)
        return live
    def memory(live):
        total=psutil.Process().memory_info().rss
        for pid,birth in set(live)|set(bootstrap):
            try:
                q=psutil.Process(pid)
                if q.create_time()==birth:total+=q.memory_info().rss
            except psutil.NoSuchProcess:pass
        return total
    def signal_own(key,kill=False):
        try:
            q=psutil.Process(key[0])
            if q.create_time()==key[1]:(q.kill if kill else q.terminate)()
        except psutil.NoSuchProcess:pass
        except psutil.AccessDenied:denied.append(key)
    try:
        parent=psutil.Process().parent()
        while parent is not None:
            b=parent.create_time()
            if not any(Path(v).resolve()==Path(__file__).resolve() for v in parent.cmdline()):break
            need(parent.create_time()==b,'bootstrap_identity_changed');bootstrap.append((parent.pid,b));parent=parent.parent()
        while True:
            need(time.time()<DEADLINE-10,'original_deadline_no_audit_window');need(memory({})<=64*2**20,'waiter_memory_limit')
            frozen();closed=primary()
            if closed is not None:break
            save(OUT/'watcher.json',r);time.sleep(1)
        c,l,primary_ids,protected=closed
        r.update(primary_status=c['status'],primary_exit_code=l['coordinator_exit_code'],
            primary_passed=c['status']=='completed_repaired_MVP' and l['coordinator_exit_code']==0,
            primary_result_replaced=False,primary_terminal_sha256=protected,
            primary_owned_identities=[dict(pid=p,create_time=b) for p,b in sorted(primary_ids)])
        cap=min(180.,DEADLINE-time.time()-10);need(cap>=1,'no_audit_window');frozen()
        env={k:v for k,v in os.environ.items() if k.upper() in {'PATH','PATHEXT','SYSTEMROOT','WINDIR','COMSPEC','LOCALAPPDATA'}}
        env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',AUTOML_THREADS='1',
            OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
        argv=[sys.executable,'-B','-X','utf8',str(W/'repaired-mvp-r1-dev/evaluator_r4.py'),'--work-root',str(W),
            '--task-root','t5','--run-name','repair4','--task','all','--plan',rel(OUT/'plan.json'),
            '--manifest','m2packet/manifest-continuation-r3.json','--archive','m2packet/repaired-source.zip','--output',rel(OUT/'audit.json')]
        need(time.time()+cap+9<DEADLINE and absent(primary_ids),'primary_restart_or_late_audit')
        end=time.monotonic()+cap
        with (OUT/'auditor.log').open('x',encoding='utf-8') as log:
            child=subprocess.Popen(argv,cwd=W,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        q=psutil.Process(child.pid);root_identity=(q.pid,q.create_time());known.add(root_identity)
        r.update(status='auditing_once',attempts=1,cleanup_confirmed=False,child_cap_seconds=cap);save(OUT/'watcher.json',r)
        while True:
            live=own();need(not denied,'own_auditor_denied');need(memory(live)<=512*2**20,'whole_memory_limit')
            need(time.monotonic()<end and time.time()<DEADLINE-9,'own_auditor_timeout')
            if child.poll() is not None:break
            time.sleep(.1)
        need(child.returncode==0,'auditor_nonzero');frozen()
        need(all(sha(local(n))==h for n,h in protected.items()) and absent(primary_ids),'primary_terminal_changed')
        audit=load(OUT/'audit.json');r['audit_sha256']=sha(OUT/'audit.json')
        need(audit.get('artifact_procedure_checks_passed') is True and audit.get('audit_within_original_common_clock') is True,'artifact_checks_failed')
        r.update(status='independent_audit_finished',raw_R4_status=audit.get('status'),artifact_checks_passed=True,
            primary_result_replaced=False,root_actual_exec_qualification='pending')
    except BaseException as exc:r.update(status='failed_or_late',failure_type=type(exc).__name__,failure_code=str(exc),metrics=None)
    finally:
        cleanup=False
        try:
            for key in sorted(own(),key=lambda k:k[1],reverse=True):signal_own(key)
            if child is not None:
                try:child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    need(root_identity in known,'own_root_identity_unverified')
                    signal_own(root_identity,True);child.wait(timeout=3)
            for key in own():signal_own(key,True)
            until=time.monotonic()+2
            while own() and time.monotonic()<until:time.sleep(.05)
            cleanup=not own() and not denied
        except BaseException as exc:r['cleanup_failure_type']=type(exc).__name__
        r.update(cleanup_confirmed=cleanup,finished_unix=time.time(),
            auditor_owned_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)])
        if time.time()>=DEADLINE or (end is not None and time.monotonic()>=end) or not r['cleanup_confirmed']:r.update(status='failed_or_late',metrics=None)
        r['audit_qualified_separately']=r['status']=='independent_audit_finished';save(OUT/'watcher.json',r)
        if time.time()>=DEADLINE or (end is not None and time.monotonic()>=end):r.update(status='failed_or_late',metrics=None,audit_qualified_separately=False);save(OUT/'watcher.json',r)
    return 0 if r['status']=='independent_audit_finished' else 1
if __name__=='__main__':raise SystemExit(main())
