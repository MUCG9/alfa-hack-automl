"""One append-only bounded synthetic run; never starts the actual observer."""
from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess
import sys
import time
import psutil

HERE=Path(__file__).resolve().parent
W=HERE.parent


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    with path.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
def require(value,code):
    if not value:raise RuntimeError(code)


def run():
    start=time.monotonic();started=time.time();deadline=start+120
    require(not (HERE/'pretest-manifest.json').exists(),'append_only_run_already_started')
    names=['terminal_identity_fence_r1.py','terminal-identity-fence-independent-review-r1.json',
           'terminal-identity-fence-synthetic-r2/tests.py','terminal-identity-fence-synthetic-r2/guard.py',
           'fullagent-cv-stage1-review-r4/stage0-terminal-ownership.json',
           'fullagent-cv-terminal-closure-blocked-r4.json','build_fullagent_cv_binding.py',
           'terminal-identity-fence-synthetic-r1/supervisor.json',
           'terminal-identity-fence-synthetic-r2/resource-contract-addendum.json',
           'fullagent-cv-launch-r4/ownership.py','close_cv_stage1_r4.py']
    refs={n:sha(W/n) for n in names}
    require(refs['terminal_identity_fence_r1.py']=='f6f112fc9eedce4e402e87a306dfae30bfedd75b457458b5ac5431f2f67757c8','proposal_changed')
    require(refs['terminal-identity-fence-independent-review-r1.json']=='d6dacce680e4bf57b979cb8cc7a4d07c196e52354dbfdc3d1b229d145d17b64c','review_changed')
    frozen=json.loads((W/'fullagent-cv-launch-r4/manifest.json').read_text('utf-8'))['immutable_files']
    def source_guard():
        for n,h in refs.items():require(sha(W/n)==h,'synthetic_source_or_evidence_changed')
        for n,h in frozen.items():require(sha(W/n)==h,'frozen_campaign_source_changed')
    source_guard()
    tree=ast.parse((HERE/'tests.py').read_text('utf-8'))
    cases=[n.name for c in tree.body if isinstance(c,ast.ClassDef) and c.name=='FenceTests'
           for n in c.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')]
    require(len(cases)==26,'declared_case_count_changed')
    pre={'status':'source_frozen_before_synthetic_execution','recorded_epoch':time.time(),
         'source_evidence_sha256':refs,'frozen_campaign_files':len(frozen),
         'tests_declared':cases,'limits':{'seconds':120,'whole_guard_and_child_rss_mib':512,'compute_threads_per_process':1,'native_OS_threads_per_process':8},
         'actual_observer_execution':False,'fits':0,'API_calls':0,'network_calls':0}
    write(HERE/'pretest-manifest.json',pre)
    env=dict(os.environ)
    env.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
               NUMEXPR_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1',PYTHONHASHSEED='0',
               PYTHONDONTWRITEBYTECODE='1')
    for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS']:
        os.environ[key]='1'
    own=psutil.Process();known={};peak=0;maxthreads=0;failure=None;signals=0
    with (HERE/'stdout.log').open('xb') as stream:
        proc=subprocess.Popen([sys.executable,'-X','utf8',str(HERE/'tests.py')],cwd=HERE,env=env,
                              stdout=stream,stderr=subprocess.STDOUT)
        root=psutil.Process(proc.pid);known[(root.pid,root.create_time())]=True
        while proc.poll() is None:
            observed=[own]
            for p,c in list(known):
                try:
                    cur=psutil.Process(p)
                    if cur.create_time()!=c:continue
                    observed.append(cur)
                    for child in cur.children(recursive=True):
                        key=(child.pid,child.create_time());known[key]=True;observed.append(child)
                except psutil.NoSuchProcess:pass
                except psutil.AccessDenied:failure='owned_identity_or_descendant_access_denied'
            unique={p.pid:p for p in observed};rss=0
            for cur in unique.values():
                try:
                    rss+=cur.memory_info().rss;maxthreads=max(maxthreads,cur.num_threads())
                except psutil.NoSuchProcess:pass
                except psutil.AccessDenied:failure='owned_resource_access_denied'
            peak=max(peak,rss/2**20)
            if time.monotonic()>=deadline:failure='synthetic_deadline'
            if peak>512:failure='synthetic_memory_limit'
            if maxthreads>8:failure='synthetic_native_OS_thread_limit'
            if failure:
                for (p,c) in sorted(known,reverse=True):
                    try:
                        cur=psutil.Process(p)
                        if cur.create_time()==c:cur.terminate();signals+=1
                    except psutil.NoSuchProcess:pass
                proc.wait(timeout=5);break
            time.sleep(.01)
        exitcode=proc.wait(timeout=5)
    unresolved=[]
    for p,c in sorted(known):
        try:
            cur=psutil.Process(p)
            if cur.create_time()==c and cur.status() not in {psutil.STATUS_DEAD,psutil.STATUS_ZOMBIE}:
                unresolved.append({'pid':p,'create_time':c,'reason':'same_identity_alive'})
        except psutil.NoSuchProcess:pass
        except psutil.AccessDenied:unresolved.append({'pid':p,'create_time':c,'reason':'AccessDenied'})
    source_guard()
    actual=json.loads((HERE/'results.json').read_text('utf-8')) if (HERE/'results.json').exists() else None
    passed=(exitcode==0 and not failure and not unresolved and actual and actual['status']=='PASS'
            and actual['tests_run']==26 and not actual['errors'] and not actual['failures']
            and actual['tripwire_counters']=={'network_calls':0,'forbidden_ml_imports':0}
            and actual['python_execution_threads']==1
            and all(v=='1' for v in actual['compute_thread_environment'].values()))
    receipt={'status':'PASS' if passed else 'FAIL','recorded_epoch':time.time(),
       'start_epoch':started,'seconds':time.monotonic()-start,'exit_code':exitcode,
       'pretest_manifest_sha256':sha(HERE/'pretest-manifest.json'),'source_evidence_sha256':refs,
       'raw_results_sha256':sha(HERE/'results.json') if actual else None,
       'raw_log_sha256':sha(HERE/'checks.log') if (HERE/'checks.log').exists() else None,
       'stdout_sha256':sha(HERE/'stdout.log'),'source_unchanged':True,
       'immutable_campaign_source_files_rehashed':len(frozen),'peak_guard_plus_child_rss_mib':peak,
       'maximum_native_OS_threads_per_observed_process':maxthreads,
       'compute_threads_cap':1,'python_execution_threads':actual.get('python_execution_threads') if actual else None,'failure':failure,
       'owned_child_identities':[{'pid':p,'create_time':c} for p,c in sorted(known)],
       'cleanup_confirmed':not unresolved,'unresolved':unresolved,'signals':signals,
       'unique_synthetic_tests':26,'actual_terminal_observer_executed':False,
       'new_actual_cleanup_certificate':False,'fits':0,'API_calls':0,'network_calls':0,
       'actual_heavy_jobs_started':0,'root_source_review_required_before_actual_use':True}
    write(HERE/'supervisor.json',receipt)
    print(json.dumps({'status':receipt['status'],'seconds':receipt['seconds'],
          'peak_rss_mib':peak,'cleanup_confirmed':not unresolved,
          'supervisor_sha256':sha(HERE/'supervisor.json'),'tests':26}))
    raise SystemExit(0 if passed else 1)


if __name__=='__main__':run()
