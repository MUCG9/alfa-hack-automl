"""Root confirms the actual no-fit audit exit; never relabel T6 as successful."""
from pathlib import Path
import hashlib,json,time,psutil
W=Path(__file__).resolve().parent;D=W/'t6-independent-classification-r1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text('utf-8'))
def write(p,r):
    with p.open('x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
sup=read(D/'supervisor.json');audit=read(D/'audit.json');c=read(W/'t6/campaign.json')
assert sha(D/'audit.json')=='831582b935dbfeabd5b6438d3133ab8fffcb8252708062f86057a5ac64d343b7'
assert sup['status']=='child_audit_ok_pending_root_wrapper_exec' and sup['cleanup_confirmed'] and sup['source_unchanged']
proof=read(W/'m3packet/terminal-root-closure.json')
rows=proof['owned_identities']+proof['closure_preparer_identities']+[sup['owned_root']]+sup['bootstrap_identities']+sup['owned_process_identities']
known={(r['pid'],r['create_time']) for r in rows};reused=0
for p,b in known:
    try:
        if psutil.Process(p).create_time()==b:raise RuntimeError('owned_identity_still_live')
        reused+=1
    except psutil.NoSuchProcess:pass
m=read(W/'m3packet/manifest.json')
assert all(sha(W/n)==h for n,h in m['immutable_files'].items())
assert sha(W/'t6/campaign.json')=='d8004d3c0c5daf2c3f5e599bc7db849f603e6679e59a7559462d0d5bfc53a973'
seal=read(W/'t6/c-seal.json');base=W/'t6/c/automl_runs/repair4'
files={p.relative_to(W).as_posix():sha(p) for p in base.rglob('*') if p.is_file()}
files['t6/c/submission.csv']=sha(W/'t6/c/submission.csv')
assert files==seal['files_sha256']
assert time.time()<c['absolute_deadline_unix'] and time.monotonic()<c['common_deadline_monotonic']
t=audit['tasks']['classification'];controls=t['protected_control_measurements']
metrics=dict(metric='macro_f1',direction='higher',two_cut_mean=t['selected_cut_mean'],
    matched_fresh_control_mean=sum(r['value'] for r in controls.values())/2,
    historical_V11_V16_mean=.6593178433614652,
    delta_vs_historical_V11_V16=t['selected_cut_mean']-.6593178433614652,
    matched_gates=t['matched_control_comparison'],historical_gates=t['baseline_comparisons']['v16-mean1'],
    hpo_completed=t['hpo_completed'],hpo_guided_successful=t['hpo_guided_successful'],
    successful_model_families=t['successful_model_families'],API_ledger=t['api'],
    selected_full_refit_CSV_integrity_verified=True,matched_control_full_refit=False,
    decision='Do not promote: below retained V11/V16 and supported-class/ex-rarest gates fail on primary',
    primary_T6_status='FAIL',scope='postfailure independently verified saved task artifacts, reused-public',
    official_score=None,promotion=False,submit=False)
r=dict(status='root_verified_postfailure_classification_artifacts',actual_exec_session=43087,
    actual_exec_exit_code=0,actual_tool_chunk='56aeef',observed_unix=time.time(),
    supervisor_sha256=sha(D/'supervisor.json'),audit_sha256=sha(D/'audit.json'),
    cleanup_confirmed=True,source_unchanged=True,immutable_refs_rehashed=718,
    owned_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],
    reused_PID_exclusions=reused,metrics=metrics,primary_T6_qualification='FAIL',
    primary_T6_actual_exit_code=1,whole_T6_success=False,new_fits=0,API_calls=0,
    closure_preparer_identities=[dict(pid=psutil.Process().pid,create_time=psutil.Process().create_time())],
    preparer_terminal_requires_fresh_confirmation=True)
parent=psutil.Process().parent()
while parent is not None:
    birth=parent.create_time()
    if not any(Path(v).resolve()==Path(__file__).resolve() for v in parent.cmdline()):break
    assert parent.create_time()==birth
    r['closure_preparer_identities'].append(dict(pid=parent.pid,create_time=birth));parent=parent.parent()
write(D/'root-closure.json',r)
for name in ['lean-classification-results.json']:
    write(W.parent/'outputs'/name,metrics)
s=read(W/'SESSION_STATE.json');s['lean_mvp']['classification_verified_postfailure']=metrics
s['lean_mvp']['additional_owned_receipts'].append(dict(path='work/t6-independent-classification-r1/supervisor.json',
    sha256=sha(D/'supervisor.json'),root_closure='work/t6-independent-classification-r1/root-closure.json',
    root_closure_sha256=sha(D/'root-closure.json')))
s['updated_epoch']=time.time()
(W/'SESSION_STATE.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(status=r['status'],mean=metrics['two_cut_mean'],
    fresh_control=metrics['matched_fresh_control_mean'],historical_control=metrics['historical_V11_V16_mean'],
    class_gates_passed=metrics['matched_gates']['class_each_cut_gate_passed'],T6_still_failed=True)))
