"""One bounded 60s/512MiB import-only diagnostic; no data or verifier execution."""
from pathlib import Path
import hashlib, importlib.util, json, os, subprocess, sys, time
import psutil
sys.dont_write_bytecode = True
D=Path(__file__).resolve().parent;W=D.parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
def module(n,p):
    s=importlib.util.spec_from_file_location(n,p);v=importlib.util.module_from_spec(s);s.loader.exec_module(v);return v
def require(v,c):
    if not v:raise RuntimeError(c)
def ids(v):
    if isinstance(v,dict):
        out={(v['pid'],v['create_time'])} if type(v.get('pid')) is int and type(v.get('create_time')) in (int,float) else set()
        for k in ['owned_root','owned_process_identities','launcher_identities','tracked_identities','closure_preparer_identities']:out|=ids(v.get(k))
        return out
    if isinstance(v,list):
        out=set()
        for x in v:out|=ids(x)
        return out
    return set()
require(not (D/'supervisor.json').exists(),'exclusive_diagnostic_only')
start,tick=time.time(),time.monotonic();deadline=tick+60
m=load(D/'pretest-manifest.json')
def guard():
    require(time.monotonic()<deadline,'diagnostic_parent_deadline')
    for n,h in m['source_sha256'].items():require(sha(W/n)==h,'diagnostic_source_changed')
guard()
owner=module('_importdiag_owner',W/'fullagent-cv-launch-r4/ownership.py')
processes=module('_importdiag_processes',W/'alfa-hack-automl/src/automl/infrastructure/processes.py')
locks=module('_importdiag_lock',W/'fullagent-cv-launch-r4/research_lock.py')
fence=module('_importdiag_fence',W/'terminal_identity_fence_r1.py')
known=ids(load(W/'fullagent-cv-stage1-terminal-ownership-fenced-r1.json'))|ids(load(W/'p0/parent-receipt.json'))
known=[{'pid':p,'create_time':c} for p,c in sorted(known)]
fenceproof=W/'fullagent-cv-stage1-review-r4/stage0-terminal-ownership.json'
child=None;tree=None;verified=False;observer=owner.StrictOwnedObserver()
result={'scope':'bootstrap_import_context_only_no_data_no_verifier','status':'starting','start_unix':start,'parent_seconds':60,'child_seconds':40,'memory_mib':512,'threads':1,'metrics':None,'fits':0,'API_calls':0,'original_p0_clock_resumed':False}
me=psutil.Process();launchers=[{'pid':me.pid,'create_time':me.create_time()}];parent=me.parent()
while parent is not None and parent.name().lower() in {'python.exe','pythonw.exe'}:
    if str(Path(__file__).resolve()) not in parent.cmdline():break
    launchers.append({'pid':parent.pid,'create_time':parent.create_time()});parent=parent.parent()
result['launcher_identities']=launchers
with locks.ResearchLock(W/'alfa-hack-automl/test-runs/.owned-research.lock') as lock:
    lock.write_identity(launchers[0]);guard()
    result['prior_fenced_observation']=fence.strict_orphan_check_with_one_fence(owner,known,fenceproof)
    try:
        env={k:os.environ[k] for k in ['SYSTEMROOT','WINDIR','COMSPEC','PATH','TEMP','TMP'] if k in os.environ}
        env.update(PYTHONIOENCODING='utf-8',PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',BLIS_NUM_THREADS='1')
        guard();child_deadline=min(time.monotonic()+40,deadline-15)
        with (D/'child.log').open('xb') as log:
            child=subprocess.Popen([sys.executable,'-X','utf8','-u',str(D/'child.py')],cwd=D,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            root=psutil.Process(child.pid);ident=(root.pid,root.create_time());observer.remember([ident]);result['owned_root']={'pid':ident[0],'create_time':ident[1]}
            tree=processes.ProcessTree(child);observer.remember(tree.members);verified=ident in tree.members;require(verified,'child_identity_unverified')
            while child.poll() is None:
                live=observer.observe();tree.members.update(live);require(not observer.denials,'owned_observer_denied')
                rss=psutil.Process().memory_info().rss
                for proc in live.values():
                    try:rss+=proc.memory_info().rss
                    except psutil.NoSuchProcess:pass
                result['peak_parent_and_owned_rss_mib']=max(result.get('peak_parent_and_owned_rss_mib',0),rss/2**20)
                require(rss<=512*2**20,'memory_limit');require(time.monotonic()<child_deadline,'child_deadline');time.sleep(.1)
        result.update(status='import_context_completed',child_exit_code=child.returncode)
    except BaseException as exc:result.update(status='technical_failure',exception_type=type(exc).__name__)
    finally:result.update(owner.cleanup_owned(child,tree,observer,verified,processes.ProcessTree))
    try:
        require(result['cleanup_confirmed'],'cleanup_unconfirmed');guard()
        result['terminal_fenced_observation']=fence.strict_orphan_check_with_one_fence(owner,known+result.get('owned_process_identities',[]),fenceproof)
        result['source_unchanged']=True
    except BaseException as exc:result.update(status='technical_failure',exception_type=type(exc).__name__,source_unchanged=None)
    result.update(seconds=time.monotonic()-tick,end_unix=time.time());save(D/'supervisor.json',result)
    guard()
print(json.dumps({k:result.get(k) for k in ['status','child_exit_code','cleanup_confirmed','source_unchanged','seconds','peak_parent_and_owned_rss_mib']}))
