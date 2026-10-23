"""One no-fit classification-verifier contract probe, separate 30-second clock."""
from pathlib import Path
import hashlib,importlib.util,json,os,subprocess,sys,time
import psutil
W=Path(__file__).resolve().parent;D=W/'r4-contract-probe'
assert not D.exists();D.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text('utf-8'))
def mod(n,p):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def save(p,r):
    with p.open('x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,indent=2);f.write('\n')
assert sha(W/'m2packet/t5-terminal-closure.json')=='0e959a6d35963d30025799805544a35f732bb1b6c52a9bc0c2d345d6f4ecfb09'
assert sha(W/'r4-class-contract-probe.py')=='ff75a5b69570e1367cae98666d86e17ede4dd9a9fb53d3660b699796273b56cd'
assert sha(W/'r4-class-contract-probe-plan.json')=='4eeeaa41f5c5abb4642a2ed49ff7967182eccde756c23dbd4a6e5eaac4e681f7'
manifest=load(W/'m2packet/manifest-continuation-r3.json');closure=load(W/'m2packet/t5-terminal-closure.json')
assert closure['cleanup_confirmed'] and closure['source_unchanged']
def frozen():
    for n,h in manifest['immutable_files'].items():assert sha(W/n)==h,n
def prior_absent():
    fixture=load(W/'catboost-weight-metric-next/fixture-supervisor.json')
    assert fixture['status']=='passed' and fixture['cleanup_confirmed']
    for v in closure['owned_identities']+closure['closure_preparer_identities']+[fixture['owned_root']]+fixture['bootstrap_identities']+fixture['owned_process_identities']:
        try:assert psutil.Process(v['pid']).create_time()!=v['create_time'],'prior_owned_still_alive'
        except psutil.NoSuchProcess:pass
owner=mod('_fixture_owner',W/'support_component_coordinator.py')
processes=mod('_fixture_processes',W/'alfa-hack-automl/src/automl/infrastructure/processes.py')
locking=mod('_fixture_lock',W/'alfa-hack-automl/tools/research_lock.py')
assert not (D/'fixture-result.json').exists() and not (D/'fixture-supervisor.json').exists()
parent=psutil.Process();own_root={'pid':parent.pid,'create_time':parent.create_time()};boot=[]
p=parent.parent()
while p is not None:
    birth=p.create_time()
    if not any(Path(a).name==Path(__file__).name for a in p.cmdline()):break
    assert p.create_time()==birth;boot.append({'pid':p.pid,'create_time':birth});p=p.parent()
with locking.ResearchLock(W/'alfa-hack-automl/test-runs/.owned-research.lock') as lock:
    lock.write_identity(own_root);prior_absent();frozen()
    start=time.monotonic();end=start+30;child=None;tree=None;verified=False;peak=0
    observer=owner.StrictOwnedObserver();r={'status':'starting','parent_cap_seconds':30,'child_cap_seconds':25,
        'whole_memory_cap_mib':512,'threads':1,'maximum_fixture_fits':0,'API':0,
        'scope':'New technical fixture after failed MVP; original MVP status/clock is not changed',
        'owned_root':own_root,'bootstrap_identities':boot,'promotion':False}
    try:
        env={k:v for k,v in os.environ.items() if k.upper() in {'PATH','PATHEXT','SYSTEMROOT','WINDIR','COMSPEC','LOCALAPPDATA','TEMP','TMP'}}
        env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
        argv=[sys.executable,'-B','-X','utf8',str(W/'r4-class-contract-probe.py'),'--plan','r4-class-contract-probe-plan.json','--output','r4-contract-probe/fixture-result.json','--deadline-monotonic',str(end-5)]
        with (D/'fixture.log').open('x',encoding='utf-8') as log:
            child=subprocess.Popen(argv,cwd=W,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
        q=psutil.Process(child.pid);key=q.pid,q.create_time();observer.remember([key])
        tree=processes.ProcessTree(child);observer.remember(tree.members);verified=key in tree.members
        assert verified
        while True:
            live=observer.observe();tree.members.update(live);assert not observer.denials
            memory=psutil.Process().memory_info().rss
            for q in live.values():
                try:memory+=q.memory_info().rss
                except psutil.NoSuchProcess:pass
            peak=max(peak,memory);assert peak<=512*2**20,'fixture_memory_limit'
            assert time.monotonic()<end-5,'fixture_child_timeout'
            if child.poll() is not None:break
            time.sleep(.05)
        assert child.returncode==0,'fixture_nonzero'
        v=load(D/'fixture-result.json');assert v['status']=='classification_worker_contract_probe_passed' and v['model_fits']==0
        r['status']='passed'
    except BaseException as exc:
        r.update(status='failed',failure_type=type(exc).__name__,failure_code=str(exc)[:200])
    finally:
        r.update(owner.cleanup_owned(child,tree,observer,verified,processes.ProcessTree))
        try:frozen();prior_absent();r['source_unchanged']=True
        except BaseException:r.update(source_unchanged=False,status='failed')
        r.update(exit_code=child.poll() if child else None,seconds=time.monotonic()-start,
            peak_owned_tree_rss_mib=peak/2**20)
        if not r['cleanup_confirmed'] or time.monotonic()>=end:r['status']='failed'
        save(D/'fixture-supervisor.json',r)
print(json.dumps({k:r[k] for k in ['status','exit_code','cleanup_confirmed','source_unchanged','seconds']}))
raise SystemExit(0 if r['status']=='passed' and time.monotonic()<end else 1)
