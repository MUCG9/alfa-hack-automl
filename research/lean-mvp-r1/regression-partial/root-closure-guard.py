"""Root-observed exit0 closure for a partial no-fit audit, never T6 terminal."""
from pathlib import Path
import hashlib,json,time
import psutil
W=Path(__file__).resolve().parent; O=W.parent/'outputs'
def load(p): return json.loads(p.read_text('utf-8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,value,exclusive=False):
    raw=json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if exclusive:
        with p.open('x',encoding='utf-8') as stream: stream.write(raw)
    else:
        tmp=p.with_name(p.name+'.pending');tmp.write_text(raw,encoding='utf-8')
        for attempt in range(21):
            try:tmp.replace(p);break
            except PermissionError:
                if attempt==20:raise
                time.sleep(.05)

directory=W/'t6-independent-regression-r1'
sup=load(directory/'supervisor.json'); audit=load(directory/'audit.json')
assert sha(directory/'audit.json')==sup['audit_sha256']=='09cd760943277860f97d495302ff77f374ba448d3cf754c26aea3ef162778655'
assert sup['status']=='child_audit_ok_pending_root_wrapper_exec' and sup['child_exit_code']==0
assert sup['cleanup_confirmed'] is True and sup['source_unchanged'] is True and sup['regression_core_unchanged'] is True
known=[sup['owned_root'],*sup['bootstrap_identities'],*sup['owned_process_identities']]
for row in known:
    try:assert psutil.Process(row['pid']).create_time()!=row['create_time'],'owned_audit_process_still_live'
    except psutil.NoSuchProcess:pass
manifest_path=W/'m3packet/manifest.json'
assert sha(manifest_path)=='4b987c652864179465dc754e90e3d1c8c9ed7c0a2144db5c3339e4c8a607d07e'
m=load(manifest_path)
assert all(sha(W/n)==h for n,h in m['immutable_files'].items())
campaign=load(W/'t6/campaign.json')
assert time.time()<campaign['absolute_deadline_unix'] and time.monotonic()<campaign['common_deadline_monotonic']
entry=next(t for t in campaign['tasks'] if t['kind']=='regression')
assert sha(W/entry['seal']['path'])==entry['seal']['sha256']
seal=load(W/entry['seal']['path'])
assert all(sha(W/n)==h for n,h in seal['files_sha256'].items())
assert audit['artifact_procedure_checks_passed'] is True and audit['audit_within_original_common_clock'] is True
task=audit['tasks']['regression']; assert task['procedure_passed'] is True
scores=task['matched_control_comparison']['cuts']
mean=sum(c['current'] for c in scores)/len(scores)
control=sum(c['protected_control'] for c in scores)/len(scores)
assert abs(mean-task['selected_cut_mean'])<1e-12
old=load(O/'repaired-mvp-final.json')['regression']['verified_two_cut_mean']
closure={
    'status':'root_confirmed_partial_audit_exec0_and_fresh_owned_absence',
    'actual_wrapper_exit_code_observed_by_root':0,'actual_tool_chunk_id':'07567e',
    'recorded_epoch':time.time(),'cleanup_confirmed':True,'source_unchanged':True,
    'regression_sealed_files_rehashed':len(seal['files_sha256']),
    'immutable_refs_rehashed':len(m['immutable_files']),
    'owned_identities':known,'active_owned_processes':[],
    'auditor_supervisor_sha256':sha(directory/'supervisor.json'),
    'audit_sha256':sha(directory/'audit.json'),
    'does_not_confirm_parent_T6_terminal':True,'new_fits':0,'ML_API_calls':0,'promotion':False}
save(directory/'root-closure.json',closure,True)
result={
    'status':'independently_verified_regression_task_T6_campaign_still_active',
    'metric':'rmse','direction':'lower','cuts':scores,'two_cut_mean':mean,
    'matched_fresh_V16_control_mean':control,
    'delta_vs_V16':mean-control,'relative_reduction_vs_V16_percent':100*(control-mean)/control,
    'previous_verified_T5_regression_mean':old,'delta_vs_previous_best_T5':mean-old,
    'both_cuts_better_than_V16':task['matched_control_comparison']['each_cut_primary_gate_passed'],
    'successful_model_families':task['successful_model_families'],
    'HPO_completed':task['hpo_completed'],'HPO_guided_successful':task['hpo_guided_successful'],
    'closed_API_ledger':task['api'],'full_refit_CSV_integrity_verified':True,
    'whole_campaign_terminal':False,'whole_campaign_deadline_met':None,
    'scope':'Reused-public search cuts; regression HPO inner overlaps confirmation. Independent numeric integrity, not blind validation.',
    'control_limit':'Control recipe rerun on matching two cuts; only selected candidate final full refit audited.',
    'audit':'work/t6-independent-regression-r1/audit.json','audit_sha256':sha(directory/'audit.json'),
    'root_closure':'work/t6-independent-regression-r1/root-closure.json',
    'root_closure_sha256':sha(directory/'root-closure.json'),
    'decision':'Retain previous T5 regression candidate and complete V11/V16; T6 regression improves V16 but is worse than previous verified partial best. Classification pending.',
    'official_score':None,'promotion':False,'submit':False}
save(O/'lean-regression-results.json',result)
(O/'lean-regression-results.txt').write_text(
    f'T6, регрессия: независимый пересчёт завершён. Средний RMSE {mean:.8f} против {control:.8f} у V16 ({100*(control-mean)/control:.4f}% ниже).\n'
    f'Срезы: {scores[0]["current"]:.8f} / {scores[1]["current"]:.8f}; оба лучше V16.\n'
    f'Но хуже прежнего проверенного T5 {old:.8f} на {mean-old:.8f}. Прежний кандидат сохранён.\n'
    'Проверены refit, CSV, row order, исходные labels, chronology и source hashes; Optuna8/8, guided5; LightGBM/XGBoost/CatBoost.\n'
    'Частичный аудит: actual exec0 и свежая проверка отсутствия всех его процессов. Классификация и весь T6 ещё выполняются.\n'
    'Срезы public повторно использованы, HPO inner совпадает с confirmation; это не blind test и не официальный score.\n'
    'Основная версия V11/V16 сохранена, продвижения и сабмита нет.\n',encoding='utf-8')
s=load(W/'SESSION_STATE.json')
s['lean_mvp']['regression_verified_partial']=result
s['lean_mvp'].setdefault('additional_owned_receipts',[]).append({
    'path':'work/t6-independent-regression-r1/supervisor.json',
    'sha256':sha(directory/'supervisor.json'),
    'root_closure':'work/t6-independent-regression-r1/root-closure.json',
    'root_closure_sha256':sha(directory/'root-closure.json')})
s['github_latest_verified']='6d9c98ea7c568b43c87e76ebb6e6eab28130ea17'
s['updated_epoch']=time.time();save(W/'SESSION_STATE.json',s)
print(json.dumps({'root_observed_actual_exit_code':0,'fresh_audit_owned_absence':True,
    'RMSE':mean,'V16':control,'previous_T5':old,'delta_vs_previous_T5':mean-old,
    'classification_and_parent_T6_pending':True,'fits':0,'API_calls':0}))
