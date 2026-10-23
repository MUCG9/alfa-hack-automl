"""Bounded no-fit audit of the closed regression task while classification runs."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time
import psutil
W=Path(__file__).resolve().parent
def load(p):return json.loads(p.read_text('utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
manifest=W/'m2packet/manifest-continuation-r3.json'
assert sha(manifest)=='ac28e6da826809e3fe334a6096229ad6410500d7f91a65071987f37ac80ce716'
assert sha(W/'repaired-mvp-r1-dev/evaluator_r4.py')=='c08e9f0be13a708d67b3266518381d6f1be3b0f43c384ef6425634160d7e2783'
assert sha(W/'t5-independent-r4/plan.json')=='8bf46de828b502ba5b7bb1d0af503ccef609812a4eac510c39a4a79edc009eed'
m=load(manifest)
for n,h in m['immutable_files'].items():assert sha(W/n)==h
sup=load(W/'t5/r/supervisor.json')
assert sup['status']=='ok' and sup['exit_code']==0 and sup['cleanup_confirmed'] is True
assert not (W/'t5-independent-r4/audit.json').exists()
assert not (W/'t5-independent-r4/supervisor.json').exists()
assert 1792761777.2275486-time.time()>10
end=min(time.monotonic()+60,time.monotonic()+1792761777.2275486-time.time()-10)
env={k:v for k,v in os.environ.items() if k.upper() in {'PATH','PATHEXT','SYSTEMROOT','WINDIR','COMSPEC','LOCALAPPDATA','TEMP','TMP'}}
env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',
 OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
argv=[sys.executable,'-B','-X','utf8',str(W/'repaired-mvp-r1-dev/evaluator_r4.py'),
 '--work-root',str(W),'--task-root','t5','--run-name','repair4','--task','regression',
 '--plan','t5-independent-r4/plan.json','--manifest','m2packet/manifest-continuation-r3.json',
 '--archive','m2packet/repaired-source.zip','--output','t5-independent-r4/audit.json']
known={};denials=set();child=None;started=time.monotonic();status='starting';peak=0
def observe():
    global peak
    live={}
    for (pid,birth) in list(known):
        try:
            p=psutil.Process(pid)
            if p.create_time()!=birth or not p.is_running():continue
            live[pid,birth]=p
            for c in p.children(recursive=True):
                key=c.pid,c.create_time();known[key]=True;live[key]=c
        except psutil.NoSuchProcess:pass
        except (psutil.AccessDenied,OSError):denials.add(pid)
    memory=psutil.Process().memory_info().rss
    for p in live.values():
        try:memory+=p.memory_info().rss
        except psutil.NoSuchProcess:pass
        except (psutil.AccessDenied,OSError):denials.add(p.pid)
    peak=max(peak,memory)
    return live
try:
    with (W/'t5-independent-r4/audit.log').open('x',encoding='utf-8') as log:
        child=subprocess.Popen(argv,cwd=W,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
        p=psutil.Process(child.pid);known[p.pid,p.create_time()]=True
        while True:
            observe()
            if peak>512*2**20:raise RuntimeError('owned_audit_memory_limit')
            if denials:raise RuntimeError('owned_audit_observation_denied')
            if time.monotonic()>=end or time.time()>=1792761777.2275486:raise RuntimeError('owned_audit_timeout')
            if child.poll() is not None:break
            time.sleep(.1)
        status='ok' if child.returncode==0 else 'child_failed'
except BaseException as exc:
    status='technical_failure';error=type(exc).__name__
finally:
    live=observe()
    for key,p in reversed(list(live.items())):
        try:
            if psutil.Process(key[0]).create_time()==key[1]:psutil.Process(key[0]).terminate()
        except psutil.NoSuchProcess:pass
        except (psutil.AccessDenied,OSError):denials.add(key[0])
    if child is not None:
        try:child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            for key,p in observe().items():
                try:
                    if psutil.Process(key[0]).create_time()==key[1]:psutil.Process(key[0]).kill()
                except psutil.NoSuchProcess:pass
                except (psutil.AccessDenied,OSError):denials.add(key[0])
            child.wait(timeout=2)
    live=observe()
    source_ok=all(sha(W/n)==h for n,h in m['immutable_files'].items())
    if live or denials or not source_ok or time.monotonic()>=end or time.time()>=1792761777.2275486:status='technical_failure'
    result={'status':status,'exit_code':child.returncode if child else None,
     'cleanup_confirmed':not live and not denials,'observation_denial_count':len(denials),'source_unchanged':source_ok,
     'owned_process_identities':[{'pid':p,'create_time':c} for p,c in sorted(known)],
     'seconds':time.monotonic()-started,'peak_owned_tree_rss_mib':peak/2**20,
     'fits':0,'API':0,'original_deadline_unix':1792761777.2275486,'promotion':False}
    receipt=W/'t5-independent-r4/supervisor.json'
    write(receipt,result)
    if time.monotonic()>=end or time.time()>=1792761777.2275486:
        result.update(status='technical_failure',failure_code='terminal_receipt_over_cap');status='technical_failure'
        pending=receipt.with_name(receipt.name+'.pending')
        write(pending,result)
        for attempt in range(21):
            try:pending.replace(receipt);break
            except PermissionError:
                if attempt==20:raise
                time.sleep(.05)
print(json.dumps(result))
raise SystemExit(0 if status=='ok' and result['cleanup_confirmed'] and source_ok and time.monotonic()<end else 1)
