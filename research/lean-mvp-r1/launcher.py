"""Launch one separately declared lean MVP; preserve failed t5 and start a fresh clock."""
from pathlib import Path
import argparse,ctypes,hashlib,json,os,runpy,subprocess,sys,time
import psutil
W=Path(__file__).resolve().parent
P=W/'m3packet'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x,exclusive=False):
    raw=json.dumps(x,ensure_ascii=False,indent=2)+'\n'
    if exclusive:
        with p.open('x',encoding='utf-8') as f:f.write(raw)
    else:
        t=p.with_name(p.name+'.pending');t.write_text(raw,encoding='utf-8')
        for attempt in range(21):
            try:
                t.replace(p);break
            except PermissionError:
                if attempt==20:raise
                time.sleep(.05)
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
assert a.manifest_sha256 and sha(P/'manifest.json')==a.manifest_sha256
m=json.loads((P/'manifest.json').read_text('utf-8'))
assert sha(Path(__file__))==m['launcher_sha256']
assert sha(W/'run_lean_mvp_r1.py')==m['coordinator_sha256']
git=['git','-c','safe.directory='+(W/'alfa-hack-automl').as_posix(),'-C',str(W/'alfa-hack-automl')]
head=subprocess.check_output(git+['rev-parse','HEAD'],text=True).strip()
assert head==a.expected_commit
for public,local in [('launcher.py',Path(__file__)),('coordinator.py',W/'run_lean_mvp_r1.py'),
    ('evaluator.py',W/'repaired-mvp-r1-dev/evaluator_r4.py'),('lean-source.zip',P/'lean-source.zip')]:
    assert hashlib.sha256(subprocess.check_output(git+['show','HEAD:research/lean-mvp-r1/'+public])).hexdigest()==sha(local)
assert not (P/'launch.json').exists() and not (W/'t6').exists()
os.environ.update(OPENAI_API_KEY=key,OPENAI_BASE_URL=str(base),OPENAI_MODEL=m['requested_model'],
    AUTOML_REASONING_EFFORT=m['reasoning_effort'],PYTHONDONTWRITEBYTECODE='1')
del cfg,key
me=psutil.Process();ids=[{'pid':me.pid,'create_time':me.create_time()}]
parent=me.parent()
while parent is not None:
    birth=parent.create_time()
    if not any(Path(v).resolve()==Path(__file__).resolve() for v in parent.cmdline() if not v.startswith('-')):break
    assert parent.create_time()==birth
    ids.append({'pid':parent.pid,'create_time':birth});parent=parent.parent()
start=time.time();deadline=start+10800
r={'status':'launching_new_lean_campaign','continuation_started_unix':time.time(),'start_unix':start,'absolute_deadline_unix':deadline,'common_seconds':10800,
    'launcher_identities':ids,'manifest_sha256':a.manifest_sha256,'git_commit':head,'promotion':False}
write(P/'launch.json',r,True)
state_path=W/'SESSION_STATE.json';s=json.loads(state_path.read_text('utf-8'))
s.setdefault('lean_mvp',{}).update(status='launched_fresh_independent_campaign',clock_assigned=True,common_start_unix=start,
    absolute_deadline_unix=deadline,launcher_identities=ids,manifest_sha256=a.manifest_sha256,
    campaign='work/t6/campaign.json',previous_failed_campaign='work/t5/campaign.json',launch_receipt='work/m3packet/launch.json',publication_commit=head)
s['next'][0]='t6 is the sole heavy queue. Observe actual receipts and fresh exact identities; source+manifest frozen. Do not rerun launcher/reset clock. Poll actual exec and independent audit after terminal.'
s['updated_epoch']=time.time();write(state_path,s)
try:
    r.update(status='coordinator_running');write(P/'launch.json',r)
    sys.argv=[str(W/'run_lean_mvp_r1.py'),'--manifest',str(P/'manifest.json'),
        '--manifest-sha256',a.manifest_sha256,'--launch','--common-start-unix',repr(start),'--deadline-unix',repr(deadline)]
    runpy.run_path(str(W/'run_lean_mvp_r1.py'),run_name='__main__')
    r.update(status='coordinator_completed',coordinator_exit_code=0)
except BaseException as exc:
    code=exc.code if isinstance(exc,SystemExit) else 1
    r.update(status='coordinator_completed' if code==0 else 'coordinator_failed',
        coordinator_exit_code=code,exception_type=type(exc).__name__)
    raise
finally:
    r.update(finished_unix=time.time(),elapsed_common_seconds=time.time()-start)
    if time.time()>=deadline:
        r.update(status='unqualified_common_deadline_exceeded',coordinator_exit_code=1)
    write(P/'launch.json',r)
    if time.time()>=deadline:
        r.update(status='unqualified_terminal_write_over_common_deadline',coordinator_exit_code=1)
        write(P/'launch.json',r)
        raise SystemExit(1)
print(json.dumps({'status':r['status'],'coordinator_exit_code':r['coordinator_exit_code'],
    'elapsed_common_seconds':r['elapsed_common_seconds']}))
