"""Root confirms actual no-fit audit exit, fresh exact owners and sealed core."""
from pathlib import Path
import json,hashlib,psutil,time
W=Path(__file__).resolve().parent;D=W/'t7-independent-regression-r1'
def read(p):return json.loads(p.read_text('utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,r,exclusive=True):
    with p.open('x' if exclusive else 'w',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
sup=read(D/'supervisor.json');audit=read(D/'audit.json');c=read(W/'t7/campaign.json')
assert sha(D/'audit.json')=='57ac0844a186fd36e40eafb3ee83a6888dc34a496abfe9cd054680fccef5224f'
assert sup['status']=='child_audit_ok_pending_root_wrapper_exec' and sup['cleanup_confirmed'] and sup['source_unchanged']
known={(r['pid'],r['create_time']) for r in [sup['owned_root']]+sup['bootstrap_identities']+sup['owned_process_identities']}
for p,b in known:
    try:assert psutil.Process(p).create_time()!=b,'audit_owned_process_still_live'
    except psutil.NoSuchProcess:pass
m=read(W/'m4packet/manifest.json')
assert sha(W/'m4packet/manifest.json')=='8faf33cd81c0e864bcf338828c34447000111eda85bc719b8f43312d2babae9a'
assert sha(W/'t7/verification-plan.json')=='1a506dc89c6001668bfcc72aebab842151164cf1c67dcc43909c5a87e5236277'
assert all(sha(W/n)==h for n,h in m['immutable_files'].items())
entry=next(t for t in c['tasks'] if t['kind']=='regression')
assert sha(W/entry['supervisor_path'])==entry['supervisor_sha256']
assert sha(W/entry['seal']['path'])==entry['seal']['sha256']
seal=read(W/entry['seal']['path']);base=W/'t7/r/automl_runs/repair4'
inventory={p.relative_to(W).as_posix():sha(p) for p in base.rglob('*') if p.is_file()}
inventory['t7/r/submission.csv']=sha(W/'t7/r/submission.csv')
assert inventory==seal['files_sha256']
assert time.time()<c['absolute_deadline_unix'] and time.monotonic()<c['common_deadline_monotonic']
t=audit['tasks']['regression'];control=sum(v['value'] for v in t['protected_control_measurements'].values())/2
metrics=dict(status='independently_verified_regression_task_T7_still_active',metric='rmse',direction='lower',
    cuts=t['matched_control_comparison']['cuts'],two_cut_mean=t['selected_cut_mean'],
    matched_fresh_V16_mean=control,delta_vs_V16=t['selected_cut_mean']-control,
    previous_T5_mean=34.86622087872278,delta_vs_T5=t['selected_cut_mean']-34.86622087872278,
    previous_T6_mean=35.21107809690049,delta_vs_T6=t['selected_cut_mean']-35.21107809690049,
    HPO_completed=t['hpo_completed'],HPO_guided_successful=t['hpo_guided_successful'],
    model_families=t['successful_model_families'],api=t['api'],full_refit_CSV_integrity_verified=True,
    both_cuts_better_than_V16=t['matched_control_comparison']['each_cut_primary_gate_passed'],
    preserved_V16_gates=t['baseline_comparisons']['v16-mean1'],
    scope='Reused public; HPO inner overlaps confirmation. Independent numeric integrity, not blind score.',
    whole_T7_terminal=False,official_score=None,promotion=False,submit=False,
    control_limit='Matched control rerun on two cuts; no fresh full control refit')
me=psutil.Process();preparers=[dict(pid=me.pid,create_time=me.create_time())];p=me.parent()
while p and any(Path(v).resolve()==Path(__file__).resolve() for v in p.cmdline()):
    preparers.append(dict(pid=p.pid,create_time=p.create_time()));p=p.parent()
r=dict(status='root_verified_partial_regression_audit',actual_exec_exit_code=0,actual_tool_chunk='dd3245',
    audit_sha256=sha(D/'audit.json'),supervisor_sha256=sha(D/'supervisor.json'),recorded_unix=time.time(),
    cleanup_confirmed=True,source_unchanged=True,source_refs_rehashed=733,regression_core_unchanged=True,
    owned_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],closure_preparer_identities=preparers,
    closure_preparer_actual_exit_and_fresh_absence_required=True,whole_T7_terminal=False,new_fits=0,API_calls=0)
write(D/'root-closure.json',r)
write(W.parent/'outputs/supervision-retry-regression-results.json',metrics)
(W.parent/'outputs/supervision-retry-regression-results.txt').write_text(
    'T7 regression RMSE '+format(t['selected_cut_mean'],'.10f')+'; V16 '+format(control,'.10f')
    +'; прежний T5 34.8662208787; прежний T6 35.2110780969.\n'
    +'Оба среза лучшеV16: '+str(metrics['both_cuts_better_than_V16'])+'. Full refit/CSV/integrity проверены.\n'
    +'Классификация и whole-T7 terminal pending. Reused-public, не слепая проверка/official score; продвижения нет.\n',encoding='utf-8')
s=read(W/'SESSION_STATE.json');s['supervision_retry_mvp']['regression_verified_partial']=metrics
s['supervision_retry_mvp'].setdefault('additional_owned_receipts',[]).append(dict(
    path='work/t7-independent-regression-r1/supervisor.json',sha256=sha(D/'supervisor.json'),
    root_closure='work/t7-independent-regression-r1/root-closure.json',root_closure_sha256=sha(D/'root-closure.json')))
s['updated_epoch']=time.time();write(W/'SESSION_STATE.json',s,False)
print(json.dumps(dict(status=r['status'],mean=metrics['two_cut_mean'],V16=control,
    T5=metrics['previous_T5_mean'],both_cuts_improve=metrics['both_cuts_better_than_V16'],whole_T7_terminal=False)))
