"""Bounded serial no-fit contracts for the isolated heartbeat repair."""
from pathlib import Path
import hashlib,importlib.util,json,os,subprocess,sys,time,psutil
W=Path(__file__).resolve().parent;OUT=W/'supervision-contracts-r2'
start=time.monotonic();wall=time.time();end=start+60
def read(p):return json.loads(p.read_text('utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,r):p.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n',encoding='utf-8')
source=W/'lean-supervision-next-dev/run_lean_mvp_r1.py'
test=W/'lean-supervision-next-dev/tests/test_cooperative_heartbeat.py'
assert sha(source)=='975796bee5dcd470b1f3ed1822d2d4396402b6bbdd4f2ce156c7a00a94442aa3'
assert sha(test)=='3901539a60fb8c8e2060e4e67f6ce2431adadda389cf2dc633651210df771f94'
assert not OUT.exists()
prior=read(W/'t6-independent-classification-r1/root-closure.json')
for row in prior['owned_identities']+prior['closure_preparer_identities']:
    try:assert psutil.Process(row['pid']).create_time()!=row['create_time']
    except psutil.NoSuchProcess:pass
spec=importlib.util.spec_from_file_location('_no_fit_lock',W/'alfa-hack-automl/tools/research_lock.py')
lockmodule=importlib.util.module_from_spec(spec);spec.loader.exec_module(lockmodule)
OUT.mkdir();root=psutil.Process();known=set();child=None;peak=0
r=dict(status='starting',common_cap_seconds=60,memory_cap_mib=512,threads=1,
    owned_root=dict(pid=root.pid,create_time=root.create_time()),bootstrap_identities=[],
    source_sha256=sha(source),test_sha256=sha(test),new_fits=0,API_calls=0,Power_API_calls=0,
    primary_T6_status='FAIL',errors=[],cleanup_confirmed=False,tests_expected=2)
p=root.parent()
while p and any(Path(v).resolve()==Path(__file__).resolve() for v in p.cmdline()):
    r['bootstrap_identities'].append(dict(pid=p.pid,create_time=p.create_time()));p=p.parent()
payload="""import sys,runpy
def audit(event,args):
    if event=='import' and str(args[0]).split('.')[0] in {'numpy','pandas','sklearn','lightgbm','catboost','xgboost','optuna','torch'}:raise RuntimeError('model_or_numeric_import_forbidden')
    if event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.posix_spawn'}:raise RuntimeError('network_or_child_process_forbidden')
sys.addaudithook(audit)
path=sys.argv[1];sys.argv=[path];runpy.run_path(path,run_name='__main__')
"""
def alive():
    result={}
    for p,b in list(known):
        try:
            q=psutil.Process(p)
            if q.create_time()!=b:continue
            result[(p,b)]=q
            for sub in q.children(recursive=True):known.add((sub.pid,sub.create_time()))
        except psutil.NoSuchProcess:pass
    return result
try:
    with lockmodule.ResearchLock(W/'alfa-hack-automl/test-runs/.owned-research.lock'):
        env={k:v for k,v in os.environ.items() if k.upper() in {'PATH','PATHEXT','SYSTEMROOT','WINDIR','COMSPEC','LOCALAPPDATA'}}
        env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
        with (OUT/'test.log').open('x',encoding='utf-8') as log:
            child=subprocess.Popen([sys.executable,'-B','-X','utf8','-c',payload,str(test)],cwd=W,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
        q=psutil.Process(child.pid);known.add((q.pid,q.create_time()))
        while child.poll() is None:
            live=alive();rss=root.memory_info().rss
            for (pid,birth),q in live.items():
                try:
                    if q.create_time()==birth:rss+=q.memory_info().rss
                except psutil.NoSuchProcess:pass
            peak=max(peak,rss);assert rss<512*2**20,'memory_limit'
            assert time.monotonic()<end-5 and time.time()<wall+55,'deadline'
            time.sleep(.05)
        assert child.returncode==0,'test_failed'
        log=(OUT/'test.log').read_text('utf-8');assert 'Ran 2 tests' in log and '\nOK\n' in log
        assert sha(source)==r['source_sha256'] and sha(test)==r['test_sha256']
        r.update(status='passed',actual_child_exit_code=0,tests_passed=2,source_unchanged=True)
except BaseException as exc:r.update(status='failed');r['errors'].append(type(exc).__name__+':'+str(exc))
finally:
    for key,q in alive().items():
        if psutil.Process(key[0]).create_time()==key[1]:q.kill()
    if child is not None:child.wait(timeout=3)
    r.update(cleanup_confirmed=not alive(),owned_process_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],
        elapsed_seconds=time.monotonic()-start,peak_tree_rss_mib=peak/2**20,finished_unix=time.time())
    if r['elapsed_seconds']>=60:r['status']='failed';r['errors'].append('terminal_over_cap')
    write(OUT/'receipt.json',r)
print(json.dumps(r))
raise SystemExit(0 if r['status']=='passed' and r['cleanup_confirmed'] else 1)
