"""Root metadata only: bind actual closed CX2 campaign to reviewed atomic caller."""
from pathlib import Path
import argparse
import hashlib
import json
import time

W=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return dict(path=str(p),sha256=sha(p))
p=argparse.ArgumentParser()
p.add_argument('--actual-exit-code',required=True,type=int)
p.add_argument('--actual-tool-evidence',required=True)
p.add_argument('--actual-exec-session',required=True,type=int)
a=p.parse_args()
assert a.actual_exit_code==0 and a.actual_tool_evidence and a.actual_exec_session>0
manifest=W/'private/cx2-manifest.r2.ready.json'
assert sha(manifest)=='16c87369fcbcd8cd3bc1690b6f0ea63248db001da6e3370a135be539ba0165ae'
driver=read(manifest);campaign=W/'cx2/campaign.json';state=read(campaign)
assert state['status']=='completed_pending_root'
assert all(state[k] is True for k in ('cleanup_confirmed','source_unchanged','temporary_cleanup_confirmed'))
assert time.monotonic()+60<state['common_deadline_monotonic']
assert time.monotonic()+60<state['final_deadline_monotonic']
packet=W/'class-cache-atomic-root-next-dev-r2'
cfg=read(packet/'binding.template.NOT_READY.json')
cfg.update(readiness='READY_REVIEWED_FROZEN',missing_bindings=[],output=str(W/'cx2'))
paths=dict(driver=W/'class-xgb-cx2-next-dev/run_audit.py',
    closer=W/'class-xgb-cx2-next-dev/close_audit.py',manifest=manifest,campaign=campaign,
    python=W/'venv/Scripts/python.exe',
    independent_source_review=W/'class-cache-atomic-root-independent-review-r2.json',
    future_CX2_literal_rebind_review=W/'class-xgb-cx2-independent-review-r1.json')
ps=read(W/'private/class-cache-ps-policy-preflight-r1.json')
paths['powershell']=Path(ps['executable'])
assert sha(paths['powershell'])==ps['executable_sha256']=='362a356ce7f0940ec74f73a8fc2c990a2cc24a38a11c90bbd8eca947110ad139'
pins=dict(driver['immutable_files'])
for key,path in paths.items():
    current=sha(path)
    if key=='manifest':
        assert current=='16c87369fcbcd8cd3bc1690b6f0ea63248db001da6e3370a135be539ba0165ae'
    elif key=='powershell':
        assert current==ps['executable_sha256']=='362a356ce7f0940ec74f73a8fc2c990a2cc24a38a11c90bbd8eca947110ad139'
    elif key!='campaign':
        assert pins.get(str(path))==current, 'reviewed_fixed_reference_changed'
    cfg[key]=dict(path=str(path),sha256=current)
    pins[str(path)]=current
for name in ('run_root.py','close_child.ps1','source-handoff.json','binding.template.NOT_READY.json'):
    path=packet/name
    assert pins.get(str(path))==sha(path), 'reviewed_atomic_source_changed'
pins[str(Path(__file__).resolve())]=sha(__file__)
cfg['immutable_files']=pins
cfg['actual_driver_execution']=dict(session=a.actual_exec_session,exit_code=a.actual_exit_code,tool=a.actual_tool_evidence)
for path,h in pins.items():assert sha(path)==h
target=W/'private/cx2-atomic.ready.json'
with target.open('x',encoding='utf-8') as f:json.dump(cfg,f,indent=2);f.write('\n')
print(json.dumps(dict(binding_sha256=sha(target),pins=len(pins),new_clock=False)))
