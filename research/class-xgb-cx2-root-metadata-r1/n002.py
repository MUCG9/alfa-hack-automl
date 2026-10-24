"""Post-tool finite known closure: root window is checked from saved timestamps."""
from pathlib import Path
import argparse
import hashlib
import json
import time
import psutil

W=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    check();result=hashlib.sha256(Path(p).read_bytes()).hexdigest();check();return result
p=argparse.ArgumentParser();p.add_argument('--actual-wrapper-exit-code',required=True,type=int)
p.add_argument('--actual-wrapper-tool',required=True);a=p.parse_args()
assert a.actual_wrapper_exit_code==0
begin=time.monotonic();last=begin
def check():
    global last
    now=time.monotonic();assert now-begin<30 and now-last<10;last=now
confirmation=W/'cx2/root-confirmation.json';r=read(confirmation)
assert r['technical_procedure_passed'] is True and r['errors']==[]
assert all(r[k] is True for k in ('inside_actual_closer_birth60','inside_original600','inside_existing_driver_final240'))
assert r['finished_unix']-r['actual_closer_birth']<=60
s=read(W/'cx2/campaign.json')
assert r['finished_monotonic']<=min(s['common_deadline_monotonic'],s['final_deadline_monotonic'])
known={(int(x['pid']),float(x['create_time'])) for x in r['known_identities']+r['wrapper_preparer_identities']}
alive=[];uncertain=[]
for pid,birth in sorted(known):
    check()
    try:
        process=psutil.Process(pid);actual=process.create_time();assert process.create_time()==actual
        if actual==birth and process.is_running():alive.append(dict(pid=pid,create_time=birth))
    except psutil.NoSuchProcess:pass
    except (psutil.AccessDenied,psutil.Error):uncertain.append(dict(pid=pid,create_time=birth))
assert not alive and not uncertain
cfg=read(W/'private/cx2-atomic.ready.json')
for path,h in cfg['immutable_files'].items():check();assert sha(path)==h
q=dict(schema='class-cache-CX2-actual-wrapper-exit-confirmed-v1',
    actual_wrapper=dict(exit_code=a.actual_wrapper_exit_code,tool=a.actual_wrapper_tool),
    root_confirmation_sha256=sha(confirmation),known_count=len(known),known_exact_live=alive,uncertain=uncertain,
    source_unchanged=True,source_pins=len(cfg['immutable_files']),
    original_root_window_saved_and_verified=True,no_new_root60=True,
    elapsed_metadata_seconds=time.monotonic()-begin,original_CX1_status='FAIL_ROOT_FRESH60_MISSED')
target=W/'cx2/actual-wrapper-exit-confirmation.json'
try:
    check();q['post_tool_confirmed']=True
    with target.open('x',encoding='utf-8') as f:json.dump(q,f,indent=2);f.write('\n')
    check();receipt_hash=sha(target);check()
except BaseException as exc:
    failure=dict(schema='class-cache-CX2-wrapper-exit-confirmation-failure-v1',
        post_tool_confirmed=False,exception_type=type(exc).__name__,
        positive_receipt_unqualified_even_if_present=True)
    with (W/'cx2/actual-wrapper-exit-confirmation-failure.json').open('x',encoding='utf-8') as f:
        json.dump(failure,f,indent=2);f.write('\n')
    raise
print(json.dumps(dict(confirmed=True,known=len(known),alive=len(alive),uncertain=len(uncertain),
    receipt_sha256=receipt_hash)))
