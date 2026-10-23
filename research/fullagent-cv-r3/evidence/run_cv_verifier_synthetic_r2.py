"""Bounded owner-side no-fit contract check runner; no model or API work."""
from pathlib import Path
import hashlib,importlib.util,json,os,subprocess,sys,time
import psutil
sys.dont_write_bytecode=True
WORK=Path(__file__).resolve().parent
OUTPUT=WORK/'cv-verifier-synthetic-r2'
SOURCE=WORK/'verify_fullagent_cv.py'
EXPECTED='33f98e1bdb44743b8b55e7e694459c2dc2c19dd5db8359c51747cc5c62274519'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
def main():
    assert sha(SOURCE)==EXPECTED
    owner_path=WORK/'support_component_coordinator.py';process_path=WORK/'alfa-hack-automl/src/automl/infrastructure/processes.py'
    assert sha(owner_path)=='8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8'
    owner=module('_cv_synthetic_owner',owner_path);processes=module('_cv_synthetic_processes',process_path)
    OUTPUT.mkdir(exist_ok=False)
    test=WORK/'test_cv_verifier_synthetic_r2.py'
    before={p.name:sha(p) for p in [SOURCE,test,owner_path,process_path]}
    allowed={'PATH','SystemRoot','SYSTEMROOT','WINDIR','COMSPEC','ComSpec','PATHEXT','PROCESSOR_ARCHITECTURE','NUMBER_OF_PROCESSORS'}
    env={k:v for k,v in os.environ.items() if k in allowed}
    for n in ['tmp','mpl']:(OUTPUT/n).mkdir()
    env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',
        TMPDIR=str(OUTPUT/'tmp'),TMP=str(OUTPUT/'tmp'),TEMP=str(OUTPUT/'tmp'),MPLCONFIGDIR=str(OUTPUT/'mpl'))
    for n in ['AUTOML_THREADS','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:env[n]='1'
    child=tree=None;verified=False;observer=owner.StrictOwnedObserver();tick=time.monotonic();peak=0.;status='starting'
    receipt={'status':status,'source_sha256':EXPECTED,'test_sha256':sha(test),'max_seconds':300,'max_memory_mib':512,'threads':1,'cleanup_confirmed':False}
    try:
        with (OUTPUT/'checks.log').open('x',encoding='utf-8') as log:
            child=subprocess.Popen([sys.executable,'-B',str(test)],cwd=WORK,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,stdin=subprocess.DEVNULL)
            tree=processes.ProcessTree(child);observer.remember(tree.members);verified=any(pid==child.pid for pid,_ in tree.members)
            if not verified:raise RuntimeError('Initial owned root missing')
            while child.poll() is None:
                live=observer.observe();tree.members.update(live)
                if observer.denials:raise RuntimeError('Owned identity observation denied')
                rss=0
                for identity in live:
                    try:
                        p=psutil.Process(identity[0])
                        if p.create_time()==identity[1]:rss+=p.memory_info().rss
                    except psutil.NoSuchProcess:pass
                peak=max(peak,rss/2**20)
                if rss>512*2**20:raise MemoryError('Synthetic contract memory cap')
                if time.monotonic()-tick>300:raise TimeoutError('Synthetic contract wall cap')
                time.sleep(.05)
            status='PASS' if child.returncode==0 else 'FAIL';receipt['exit_code']=child.returncode
    except BaseException as exc:receipt['exception_type']=type(exc).__name__;status='FAIL'
    finally:
        receipt.update(owner.cleanup_owned(child,tree,observer,verified,processes.ProcessTree))
        receipt.update(status=status,seconds=time.monotonic()-tick,peak_owned_rss_mib=peak,
            source_unchanged=before=={p.name:sha(p) for p in [SOURCE,test,owner_path,process_path]},
            fits=0,API_calls=0,real_CV_outcomes_read=False,scoped_contract_only=True)
        if not receipt['cleanup_confirmed'] or not receipt['source_unchanged']:receipt['status']='FAIL'
        (OUTPUT/'supervisor.json').write_bytes((json.dumps(receipt,indent=2,allow_nan=False)+'\n').encode('utf-8'))
    print(json.dumps(receipt,indent=2))
    raise SystemExit(0 if receipt['status']=='PASS' else 1)
if __name__=='__main__':main()
