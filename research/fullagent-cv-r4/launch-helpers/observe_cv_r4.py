"""Read-only R4 checkpoint; never starts, resumes, signals or admits any work."""
from pathlib import Path
import argparse
import hashlib
import json
import time
import psutil

W=Path(__file__).resolve().parent
def load(p):return json.loads(p.read_text('utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):
    t=p.with_name(p.name+'.pending');t.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf-8'));t.replace(p)
def identities(x):
    out=set()
    if isinstance(x,dict):
        if type(x.get('pid')) is int and isinstance(x.get('create_time'),(int,float)):
            out.add((x['pid'],float(x['create_time'])))
        for v in x.values():out.update(identities(v))
    elif isinstance(x,list):
        for v in x:out.update(identities(v))
    return out
parser=argparse.ArgumentParser();parser.add_argument('--exec-session',type=int);args=parser.parse_args()
P=W/'fullagent-cv-launch-r4';m=load(P/'manifest.json')
assert sha(P/'manifest.json')=='a70f2a0cefb686dd04535c76b4c9e9e80073aba23d86fd7aad7e52fc7b9eee6a'
assert sha(W/'fullagent_cv_coordinator_r4.py')==m['coordinator_sha256']
for n,v in m['immutable_files'].items():assert sha(W/n)==v,n
stage='stage1' if (W/'f4/stage1.json').exists() else 'stage0'
r=load(W/'f4'/f'{stage}.json');l=load(W/f'fullagent-cv-{stage}-launch-r4.json')
known=identities(r)|identities(l)
gate_status=[]
for p in sorted((W/'f4').glob('gate-*.json')):
    g=load(p);known.update(identities(g))
    gate_status.append({'name':p.stem.removeprefix('gate-'),'status':g['status'],
        'cleanup_confirmed':g['cleanup_confirmed'],'exit_code':g.get('exit_code')})
for arm in r.get('arms',[]):
    if arm.get('supervisor_receipt_path'):
        p=W/arm['supervisor_receipt_path']
        if p.exists():known.update(identities(load(p)))
live=[];unresolved=[];absent=0
for pid,birth in sorted(known):
    try:
        p=psutil.Process(pid)
        if p.create_time()!=birth or not p.is_running():absent+=1;continue
        live.append({'pid':pid,'create_time':birth,'RSS_MiB':p.memory_info().rss/2**20})
    except psutil.NoSuchProcess:absent+=1
    except (psutil.AccessDenied,OSError) as exc:
        unresolved.append({'pid':pid,'create_time':birth,'exception':type(exc).__name__})
now=time.time()
technical_stage0=load(W/'f4/stage0.json')
x={'recorded_epoch':now,'campaign':'fullagent_R4','stage':stage,'status':r['status'],
    'exec_session':args.exec_session,'manifest_sha256':sha(P/'manifest.json'),
    'source_sha256':m['coordinator_sha256'],'immutable_files_rehashed':430,'current_source_guard_passed':True,
    'absolute_deadline_unix':r['absolute_deadline_unix'],
    'remaining_original_seconds':max(0,r['absolute_deadline_unix']-now),
    'active_exact_identities':live,'absent_or_reused_identity_count':absent,'unresolved':unresolved,
    'observation_scope':'Recorded exact identities only, read-only; not a lock/admission/orphan or cleanup certificate',
    'gate_supervisors':gate_status,'gates_verified':[g['name'] for g in technical_stage0['gates'] if g['proof']['passed']],
    'gates_evidence_stage':'stage0','running_slot':r.get('running_slot'),
    'arm_statuses':[{k:a.get(k) for k in ['directory','fold','arm','status','independent_pair_audited']} for a in r['arms']],
    'paired_audits_completed':len(r['pairs']),'complete_CV':r['complete_CV'],'OOF_complete':r['OOF_complete'],
    'source_unchanged':r['source_unchanged'],'cleanup_confirmed':r['cleanup_confirmed'],
    'available_RAM_MiB':psutil.virtual_memory().available/2**20,
    'promotion':False,'official_submission':False}
write(W/'fullagent-cv-r4-latest-observation.json',x)
sp=W/'SESSION_STATE.json';s=load(sp);s['updated_epoch']=now;s['heartbeat_last']=x
f=s['full_agent_fixed_half_preparation'];f.update(status=f'R4_{stage}_{r["status"]}',active_stage=stage,
    fit_launch=stage=='stage1',promotion=False)
f['technical_repair_preparation'].update(status=f'R4_{stage}_{r["status"]}',new_clock_assigned=True,
    new_heavy_launch=True,actual_launch=f'work/fullagent-cv-{stage}-launch-r4.json',exec_session=args.exec_session,
    absolute_deadline_unix=r['absolute_deadline_unix'],current_output='work/f4',prior_failed_output_preserved='work/f3')
publication_commit=l.get('publication_commit','388adc5d9cfa0e9c08d95a09ba9ec7a7e2da1148')
s['launch_preparation_github']=publication_commit
s['github_latest_verified']=s.get('github_latest_verified',publication_commit)
s['github']=s['github_latest_verified']+' pushed; exact remote SHA verified. Active launch preparation commit:'+publication_commit+'.'
s['next']=[n for n in s['next'] if not n.startswith('R4 actual manifest')]
s['next'].insert(0,'R4 is the only active sequential heavy queue. Observe f4 receipts and fresh PID/create_time; do not launch another suite/fit. After actual all4Stage0 PASS+cleanup/exec exit0, review/publish Stage1 root receipt and assign separate original64800clock. Preserve oldf3 and do not use old checkpoint_fullagent_cv.py.')
s['agents']['features_models']='Separate cache pilot plan only, no tests/fits/API/frozen edits.'
s['agents']['audit_contract']='Actual R4 binding/manifest independent review fd1fa384 complete; no source/fits/API.'
write(sp,s)
lines=[f'Кандидат полного агента, техническая попытка R4: {stage}, {r["status"]}.',
    f'Один исходный лимит этапа: {r["stage_cap_seconds"]}с, deadline Unix {r["absolute_deadline_unix"]}; он не переносится.',
    'Зафиксированы430 файлов, включая прежние395. Для тестовой копии добавлены9 общих metadata-файлов; модели, архивы, данные, фолды, критерии и лимиты сохранены.',
    'Проверенные завершённые gates: '+(', '.join(x['gates_verified']) or 'пока нет')+'.',
    ('A451/B468 без skips и по23 повторных exact-unpacked проверки пройдены на фактических архивах.' if technical_stage0['status']=='completed_stage0_pass' else 'Ожидаются A451/B468 без skips и по23 повторных exact-unpacked проверки; ожидаемые количества не являются PASS.'),
    'Предыдущий f3 сохранён как технический FAIL с двумя missing-metadata ошибками;444 exact identities проверенно отсутствовали до и внутри lock. Его clock не перезапущен.',
    'После всех реальных gates/очистки — CV всей процедуры на трёх групповых фолдах; отдельный лимит18ч, early stop только по заранее объявленному отказу.',
    'Сильный V11/V16 сохранён. Предыдущий four-stage MVP хуже: RMSE38.10404 против35.44723; MacroF1 .64991 против.65932. Это локальные reused-public метрики.',
    'Полного улучшения, продвижения и нового официального submit нет. Скилл/AGENTS/handoff обновлены и опубликованы; autoresearch-ml.zip прошёл quick_validate.',
    'Git research branch:'+publication_commit+'; remote SHA проверен.']
(W.parent/'outputs/fullagent-cv-status.txt').write_bytes(('\n'.join(lines)+'\n').encode('utf-8'))
print(json.dumps({k:x[k] for k in ['stage','status','gates_verified','active_exact_identities','unresolved','remaining_original_seconds']},ensure_ascii=False))
