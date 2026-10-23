"""Export actual closed T7 evidence and freshly check its closure preparers."""
from pathlib import Path
import hashlib,json,time,psutil
w=Path(__file__).resolve().parent;o=w.parent/'outputs'
def read(p):return json.loads(p.read_text('utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
root=w/'m4packet/terminal-root-closure.json';r=read(root)
assert r['actual_exec_session']==65008 and r['actual_exec_exit_code_observed_by_root']==0
assert r['parent_terminal_procedure_qualified'] and r['cleanup_confirmed'] and r['source_unchanged']
assert not r['all_declared_quality_gates_better_than_V16']
known=r['owned_identities']+r['closure_preparer_identities'];live=[];uncertain=[]
for row in known:
    try:
        if psutil.Process(row['pid']).create_time()==row['create_time']:live.append(row)
    except psutil.NoSuchProcess:pass
    except (psutil.AccessDenied,OSError):uncertain.append(row)
assert not live and not uncertain,'Terminal owned or root closure preparer still active/uncertain'
audit=w/r['audit_reference'];assert sha(audit)==r['audit_sha256'];a=read(audit)
assert a['artifact_procedure_checks_passed'] and a['audit_within_original_common_clock']
assert set(a['tasks'])=={'regression','classification'}
me=psutil.Process();preparers=[dict(pid=me.pid,create_time=me.create_time())];parent=me.parent()
while parent is not None:
    birth=parent.create_time()
    if not any(Path(x).resolve()==Path(__file__).resolve() for x in parent.cmdline() if x and not x.startswith('-')):break
    assert parent.create_time()==birth;preparers.append(dict(pid=parent.pid,create_time=birth));parent=parent.parent()
proof=dict(status='T7_terminal_report_export_owned_fresh_closure',actual_exec_session=65008,
    actual_exec_exit_code_observed_by_root=0,actual_exec_evidence='write_stdin tool56d091 exit0',
    actual_root_closure_exec_evidence='close_lean_mvp_r3 toolc3c9c6 exit0',
    cleanup_confirmed=True,source_unchanged=True,active_owned_processes=[],uncertain_owned=[],
    owned_identities=known,closure_preparer_identities=preparers,
    prior_root_closure_sha256=sha(root),final_R4_audit_sha256=sha(audit),
    recorded_unix=time.time(),root_exporter_actual_exec_confirmation_required=True,
    fits=0,API_calls=0,official_score=None,promotion=False)
dest=w/'t7-final-export-root-closure.json';assert not dest.exists();write(dest,proof)
summary=dict(experiment='T7',status='technical_procedure_pass_quality_not_promoted',
    actual_exec_session=65008,actual_exec_exit_code=0,actual_exec_tool_chunk='56d091',
    common_seconds=10800,elapsed_seconds=r['parent_elapsed_common_seconds'],
    root_confirmation_within_original_clock=r['root_confirmation_within_clock'],
    technical_source_unique=458,source_skipped=0,exact_default_repeated=23,
    fresh_owned_and_root_closure_preparers_absent=True,
    root_closure_sha256=sha(root),final_audit_sha256=sha(audit),exporter_proof_sha256=sha(dest),
    task_means=r['independently_audited_task_means'],fresh_control_means=r['matched_fresh_control_means'],
    preserved_control_means={'regression':35.44723155783769,'classification':0.6593178433614652},
    previous_T6_means={'regression':35.21107809690049,'classification':0.657105733603337},
    previous_best_T5_regression=34.86622087872278,
    matched_control_gates=r['matched_control_gates'],preserved_V16_gates=r['preserved_V16_gates'],
    mandatory_stage_proofs={k:dict(successful_model_families=t['successful_model_families'],
        hpo_completed=t['hpo_completed'],hpo_guided_successful=t['hpo_guided_successful'],
        procedure_passed=t['procedure_passed'],errors=t['errors'],api=t['api']) for k,t in a['tasks'].items()},
    decision='Retain strong V11/V16 and best T5 regression component. Both T7 tasks full refit/CSV and independent artifact audit qualified; quality gates did not improve. No submit.',
    scope='Reused public cuts; regression HPO inner overlaps confirmation; current classification protected control repeats T6fresh result but does not reproduce historical V11/V16. No blind/private/official score.',
    official_score=None,promotion=False,submit=False)
write(o/'supervision-retry-terminal-results.json',summary)
text='''T7 завершён технически успешно: actual exec65008 exit0, elapsed3786.214с при общем лимите10800с.
Четыре стадии обеих задач,8HPO/5guided каждой, refit/CSV/integrity и независимый R4-аудит проверены. Source458 unique/0skips; exact23 repeated. Процессы и root-closure preparers завершены.
Регрессия RMSE34.92368930 против V1635.44723156; primary37.78330937 лучше38.90280373, confirmation32.06406922 хуже31.99165938. Лучший прежний T5=34.86622088 сохраняется.
Классификация MacroF1=0.65692423 против исторического V11/V160.65931784; оба среза хуже исторического контроля. По сравнению со свежим контролем0.65300490 среднее выше, но primary Analysis(-0.01888),Backdoor(-0.01093) и ex-rarest(-0.001289) не проходят gates. Свежий контроль совпал с T6; причина отличия от исторического всё ещё не установлена.
Итог: техническая ошибка supervision исправлена, подтверждённого улучшения полной процедуры нет. V11/V16 и лучший T5 regression сохранены. Сабмит не выполнен. Метрики reused-public, не официальный score.
Детальные per-cut/per-class, API/стадии и SHA: supervision-retry-terminal-results.json.
'''
(o/'supervision-retry-terminal-results.txt').write_text(text,encoding='utf-8')
public=w/'alfa-hack-automl/research/lean-mvp-r2/terminal';assert not public.exists();public.mkdir()
files={
    'audit.json':audit,'root-closure.json':root,'export-root-closure.json':dest,
    'terminal-results.json':o/'supervision-retry-terminal-results.json',
    'terminal-results.txt':o/'supervision-retry-terminal-results.txt',
    'export_results.py':Path(__file__).resolve()}
for name,p in files.items():
    b=p.read_bytes();assert w.parent.name.encode('utf-8') not in b and b'ghp_' not in b and b'sk-C_' not in b
    (public/name).write_bytes(b)
state=w/'SESSION_STATE.json';s=read(state)
s['supervision_retry_mvp'].update(status='terminal_procedure_verified_quality_not_promoted',
    actual_exec_exit_code=0,actual_terminal_tool_chunk='56d091',root_terminal_qualification='PASS_technical_only',
    terminal_result='outputs/supervision-retry-terminal-results.json',terminal_result_sha256=sha(o/'supervision-retry-terminal-results.json'),
    final_metrics=summary['task_means'],all_quality_gates_improved=False,
    root_export_closure='work/t7-final-export-root-closure.json',root_export_closure_sha256=sha(dest),
    original_deadline_unix=r.get('original_deadline_unix',1792780615.4813344),
    original_elapsed_seconds=r['parent_elapsed_common_seconds'],promotion=False,submit=False)
s['active_queue']=None
s['active_priority']='T7 terminal verified. User method-expansion experiments registered. After fresh exporter/helper absence and source review/publication, start new bounded sequential champion Stage0; preserve all T5/T6/T7 quality outcomes.'
s['next'][0]='T7 actual exec65008 exit0 tool56d091; terminal verified by rootR3 c3c9c6. Never relaunch/reset. Read final terminal results. Freshly prove t7-final-export-root-closure.json preparer identities absent, review+publish champion-stage0-next-dev/run_stage0.py SHA3fdeff5dd225bf02bc8d806a5a0616a5949b7a1d3b2ce5363339d96bd4cd311f, then new900s technical Stage0 with prepared-manifestSHA5160562be127dc6130a1f3349a21b552c8aac526ead484048982716b037aa1c1 and exactT7terminalrootSHA plus --extra-terminal-receipt t7-final-export-root-closure.json=SHA. No duplicate heavy fits; source-only proposals are not model results.'
s['method_expansion_program']=dict(queue='work/method-expansion-program/queue.json',user_deliverable='outputs/method-expansion-experiments.txt',
    experiments=['METH-01','METH-02','METH-03','METH-04','METH-05','METH-06'],started=0,
    correction='Existing linear_text already supports numeric/category-only Ridge/LogReg/SGD; admission/test it rather than invent missing adapter.',
    method_guidance_overlay='work/method-skills-next-dev-r2',source_only=True)
s['updated_epoch']=time.time();t=state.with_suffix('.pending');write(t,s);t.replace(state)
with (w/'research-terminal-events.jsonl').open('a',encoding='utf-8') as stream:stream.write(json.dumps(dict(event='T7_terminal_verified',**summary),ensure_ascii=False,allow_nan=False)+'\n')
print(json.dumps({'T7_technical_pass':True,'quality_promoted':False,'metrics':summary['task_means'],
    'exporter_proof_sha256':sha(dest),'closure_preparer_identities':preparers}))
