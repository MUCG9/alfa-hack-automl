"""Same-process bounded continuation; the first failed launch clock is retained."""
from pathlib import Path
import argparse,ctypes,hashlib,json,os,runpy,subprocess,sys,time
import psutil
W=Path(__file__).resolve().parent
P=W/'m2packet'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x,exclusive=False):
    raw=json.dumps(x,ensure_ascii=False,indent=2)+'\n'
    if exclusive:
        with p.open('x',encoding='utf-8') as f:f.write(raw)
    else:
        t=p.with_name(p.name+'.pending');t.write_text(raw,encoding='utf-8');t.replace(p)
pa=argparse.ArgumentParser();pa.add_argument('--manifest-sha256');pa.add_argument('--expected-commit')
pa.add_argument('--preflight-env',action='store_true');a=pa.parse_args()
# Use already-authorized credentials without emitting any values or passing argv secrets.
cfg=json.loads((W/'private/qwen.json').read_text('utf-8'))
key=next((cfg[n] for n in ['api_key','key','token','OPENAI_API_KEY'] if cfg.get(n)),None)
base=next((cfg[n] for n in ['base_url','api_base','OPENAI_BASE_URL'] if cfg.get(n)),
    'https://changellenge.up.railway.app/v1')
if not isinstance(key,str) or not key or str(base).rstrip('/')!='https://changellenge.up.railway.app/v1':
    raise RuntimeError('Authorized private environment is unavailable')
if a.preflight_env:
    print(json.dumps({'authorized_private_environment_ready':True,'API_calls':0}));raise SystemExit(0)
assert a.manifest_sha256 and sha(P/'manifest-continuation-r1.json')==a.manifest_sha256
m=json.loads((P/'manifest-continuation-r1.json').read_text('utf-8'))
assert sha(Path(__file__))==m['launcher_sha256']
assert sha(W/'run_repaired_mvp_r2.py')==m['coordinator_sha256']
git=['git','-c','safe.directory='+(W/'alfa-hack-automl').as_posix(),'-C',str(W/'alfa-hack-automl')]
head=subprocess.check_output(git+['rev-parse','HEAD'],text=True).strip()
assert head==a.expected_commit
for public,local in [('repair/launcher.py',Path(__file__)),('repair/coordinator.py',W/'run_repaired_mvp_r2.py'),
    ('evaluator.py',W/'repaired-mvp-r1-dev/evaluator_r2.py'),('repaired-source.zip',P/'repaired-source.zip')]:
    assert hashlib.sha256(subprocess.check_output(git+['show','HEAD:research/repaired-mvp-r1/'+public])).hexdigest()==sha(local)
assert not (P/'continuation-launch.json').exists() and not (W/'t3').exists()
os.environ.update(OPENAI_API_KEY=key,OPENAI_BASE_URL=str(base),OPENAI_MODEL=m['requested_model'],
    AUTOML_REASONING_EFFORT=m['reasoning_effort'],PYTHONDONTWRITEBYTECODE='1')
del cfg,key
failed_path=P/'launch.json'
assert sha(failed_path)=='55c357c4c8ada13565cfe06dd6b03be5bee005ebc31937ae98c728593454d627'
failed=json.loads(failed_path.read_text('utf-8'))
assert failed['status']=='coordinator_failed' and failed['coordinator_exit_code']==1
assert failed['common_seconds']==10800
start=failed['start_unix'];deadline=failed['absolute_deadline_unix']
assert deadline-start==10800 and time.time()<deadline

me=psutil.Process();ids=[{'pid':me.pid,'create_time':me.create_time()}]
parent=me.parent()
while parent is not None:
    birth=parent.create_time()
    if not any(Path(v).resolve()==Path(__file__).resolve() for v in parent.cmdline() if not v.startswith('-')):break
    assert parent.create_time()==birth
    ids.append({'pid':parent.pid,'create_time':birth});parent=parent.parent()
r={'status':'continuation_launching','continuation_started_unix':time.time(),'start_unix':start,'absolute_deadline_unix':deadline,'common_seconds':10800,
    'launcher_identities':ids,'manifest_sha256':a.manifest_sha256,'git_commit':head,'promotion':False}
write(P/'continuation-launch.json',r,True)
state_path=W/'SESSION_STATE.json';s=json.loads(state_path.read_text('utf-8'))
s['repaired_mvp'].update(status='continuation_launched_under_original_clock',clock_assigned=True,common_start_unix=start,
    absolute_deadline_unix=deadline,launcher_identities=ids,manifest_sha256=a.manifest_sha256,
    campaign='work/t3/campaign.json',original_failed_launch='work/m2packet/launch.json',launch_receipt='work/m2packet/continuation-launch.json',publication_commit=head)
s['next'][0]='t3 is the sole heavy queue. Observe actual receipts and fresh exact identities; source+manifest frozen. Do not rerun launcher/reset clock. Poll actual exec and independent audit after terminal.'
s['updated_epoch']=time.time();write(state_path,s)
awake=False
try:
    if os.name=='nt':awake=bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000001))
    r.update(status='coordinator_running',windows_awake_requested=awake);write(P/'continuation-launch.json',r)
    sys.argv=[str(W/'run_repaired_mvp_r2.py'),'--manifest',str(P/'manifest-continuation-r1.json'),
        '--manifest-sha256',a.manifest_sha256,'--launch','--common-start-unix',repr(start),'--deadline-unix',repr(deadline)]
    runpy.run_path(str(W/'run_repaired_mvp_r2.py'),run_name='__main__')
    r.update(status='coordinator_completed',coordinator_exit_code=0)
except BaseException as exc:
    code=exc.code if isinstance(exc,SystemExit) else 1
    r.update(status='coordinator_completed' if code==0 else 'coordinator_failed',
        coordinator_exit_code=code,exception_type=type(exc).__name__)
    raise
finally:
    r.update(finished_unix=time.time(),elapsed_common_seconds=time.time()-start)
    if os.name=='nt':r['windows_awake_released']=bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000000))
    if time.time()>=deadline:
        r.update(status='unqualified_common_deadline_exceeded',coordinator_exit_code=1)
    write(P/'continuation-launch.json',r)
    if time.time()>=deadline:
        r.update(status='unqualified_terminal_write_over_common_deadline',coordinator_exit_code=1)
        write(P/'continuation-launch.json',r)
        raise SystemExit(1)
print(json.dumps({'status':r['status'],'coordinator_exit_code':r['coordinator_exit_code'],
    'elapsed_common_seconds':r['elapsed_common_seconds']}))
