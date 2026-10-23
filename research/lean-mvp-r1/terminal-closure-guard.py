"""Certify actual T6 terminal observations without fitting or changing raw receipts.
Run ONLY after root observes actual exec88656 exit. Never signals processes.
Fresh closure and original raw cleanup flags are deliberately separate facts.
"""
from pathlib import Path
import argparse,hashlib,json,math,time
import psutil

W=Path(__file__).resolve().parent
M='4b987c652864179465dc754e90e3d1c8c9ed7c0a2144db5c3339e4c8a607d07e'
P='58e3364aa35c43c975ee0b8ade09210f6b058d41157b2a1fc4f4debdb6a35519'
R4='c08e9f0be13a708d67b3266518381d6f1be3b0f43c384ef6425634160d7e2783'
def read(path):return json.loads(path.read_text('utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def local(name):
    path=(W/name).resolve()
    if not path.is_relative_to(W):raise ValueError('Reference outside work')
    return path
def write(path,value,exclusive=False):
    raw=json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if exclusive:
        with path.open('x',encoding='utf-8') as stream:stream.write(raw)
        return
    pending=path.with_name(path.name+'.pending');pending.write_text(raw,encoding='utf-8')
    for attempt in range(21):
        try:pending.replace(path);return
        except PermissionError:
            if attempt==20:raise
            time.sleep(.05)
def add(known,rows):
    for row in rows:
        pid,birth=row['pid'],row['create_time']
        if type(pid) is not int or pid<1 or type(birth) not in (int,float) or not math.isfinite(birth) or birth<=0:
            raise ValueError('Invalid exact identity')
        known.add((pid,float(birth)))
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--self-sha256',required=True)
    ap.add_argument('--actual-exec-session',type=int,required=True)
    ap.add_argument('--actual-exit-code',type=int,required=True)
    ap.add_argument('--actual-tool-evidence',required=True)
    a=ap.parse_args();started=time.time();started_mono=time.monotonic()
    assert a.actual_exec_session==88656 and 0<len(a.actual_tool_evidence.strip())<=300
    assert W.parent.name not in a.actual_tool_evidence
    assert sha(Path(__file__))==a.self_sha256
    manifest_path=W/'m3packet/manifest.json';launch_path=W/'m3packet/launch.json';campaign_path=W/'t6/campaign.json'
    assert sha(manifest_path)==M and sha(W/'t6/verification-plan.json')==P
    m,l,c=read(manifest_path),read(launch_path),read(campaign_path)
    assert l['manifest_sha256']==c['manifest_sha256']==M
    assert l.get('coordinator_exit_code') is not None and l.get('finished_unix') is not None
    assert c.get('finished_unix') is not None and c.get('finished_monotonic') is not None
    assert c['status'] not in {'starting','running','verifying'},'Parent is still active'
    assert l['start_unix']==c['start_unix'] and l['absolute_deadline_unix']==c['absolute_deadline_unix']
    assert l['absolute_deadline_unix']-l['start_unix']==10800
    destination=W/'m3packet/terminal-root-closure.json'
    assert not destination.exists(),'Never overwrite a terminal closure'
    known=set();add(known,l['launcher_identities']);add(known,[c['owned_root']])
    add(known,c.get('coordinator_bootstrap_identities',[]))
    receipts={r['path']:r['sha256'] for r in c.get('supervisors',[])}
    for name in ['t6/g/source-supervisor.json','t6/g/exact-supervisor.json','t6/r/supervisor.json','t6/c/supervisor.json','t6/final-audit-supervisor.json']:
        if local(name).exists():receipts.setdefault(name,None)
    state=read(W/'SESSION_STATE.json')
    for item in state['lean_mvp'].get('additional_owned_receipts',[]):
        name=item['path'].removeprefix('work/')
        receipts[name]=item['sha256']
        proof=local(item['root_closure'].removeprefix('work/'))
        assert sha(proof)==item['root_closure_sha256']
        add(known,read(proof)['owned_identities'])
    for name,expected in receipts.items():
        path=local(name)
        if expected:assert sha(path)==expected,'Closed supervisor drifted'
        record=read(path)
        for field in ['owned_process_identities','observed_worker_roots','bootstrap_identities']:
            add(known,record.get(field,[]))
        if record.get('owned_root'):add(known,[record['owned_root']])
    live=[];uncertain=[];reused=0
    for pid,birth in sorted(known):
        try:
            if psutil.Process(pid).create_time()==birth:live.append(dict(pid=pid,create_time=birth))
            else:reused+=1
        except psutil.NoSuchProcess:pass
        except (psutil.AccessDenied,OSError) as exc:uncertain.append(dict(pid=pid,create_time=birth,error=type(exc).__name__))
    source_bad=[name for name,digest in m['immutable_files'].items() if sha(local(name))!=digest]
    deployed_bad=[];seal_bad=[]
    for task in m['tasks']:
        root=W/'t6'/task['code']
        if not root.exists():continue
        refs={**m['compiled_sha256'],**task['files'],'protected_control.json':task['control_recipe']['sha256']}
        for name,digest in refs.items():
            path=root/name
            if not path.is_file() or sha(path)!=digest:deployed_bad.append(task['code']+'/'+name)
    for task in c.get('tasks',[]):
        path=local(task['seal']['path'])
        if sha(path)!=task['seal']['sha256']:seal_bad.append(task['code']+':receipt');continue
        sealed=read(path)['files_sha256']
        runtime=W/'t6'/task['code']/'automl_runs/repair4'
        inventory={p.relative_to(W).as_posix() for p in runtime.rglob('*') if p.is_file()}
        inventory.add(f"t6/{task['code']}/submission.csv")
        if set(sealed)!=inventory:seal_bad.append(task['code']+':inventory')
        seal_bad.extend(name for name,digest in sealed.items() if not local(name).is_file() or sha(local(name))!=digest)
    original_terminal_clock=(l['finished_unix']<l['absolute_deadline_unix'] and c['finished_unix']<c['absolute_deadline_unix']
        and c['finished_monotonic']<c['common_deadline_monotonic'])
    clock_skew=(c['common_deadline_monotonic']-time.monotonic())-(c['absolute_deadline_unix']-time.time())
    root_confirmation_in_clock=(started<c['absolute_deadline_unix'] and time.time()<c['absolute_deadline_unix']
        and time.monotonic()<c['common_deadline_monotonic'] and abs(clock_skew)<=5)
    cleanup=not live and not uncertain
    source=not source_bad and not deployed_bad and not seal_bad
    audit=None
    if c.get('independent_audit'):
        ref=c['independent_audit'];path=local(ref['path'])
        assert sha(path)==ref['sha256']
        assert sha(W/'repaired-mvp-r1-dev/evaluator_r4.py')==R4
        audit=read(path);assert audit['manifest_sha256']==M
        assert audit['parent_exec_terminal_qualification_required'] is True
        assert audit['campaign_terminal_confirmed'] is False
    procedure=(a.actual_exit_code==0 and l['coordinator_exit_code']==0 and c['status']=='completed_repaired_MVP'
        and c['qualification']=='PASS' and c['cleanup_confirmed'] is True and c['source_unchanged'] is True
        and cleanup and source and original_terminal_clock and root_confirmation_in_clock
        and c.get('awake_guard',{}).get('release_API_verified') is True
        and audit is not None and audit.get('artifact_procedure_checks_passed') is True
        and audit.get('audit_within_original_common_clock') is True)
    metrics={k:v['selected_cut_mean'] for k,v in audit['tasks'].items()} if audit else {}
    quality=(procedure and set(metrics)=={'regression','classification'} and all(
        t['matched_control_comparison']['each_cut_primary_gate_passed']
        and t['matched_control_comparison']['class_each_cut_gate_passed'] for t in audit['tasks'].values()))
    preparers=[dict(pid=os_process.pid,create_time=os_process.create_time()) for os_process in [psutil.Process()]]
    parent=psutil.Process().parent()
    while parent is not None:
        birth=parent.create_time()
        if not any(Path(v).resolve()==Path(__file__).resolve() for v in parent.cmdline()):break
        assert parent.create_time()==birth
        preparers.append(dict(pid=parent.pid,create_time=birth));parent=parent.parent()
    controls={k:sum(vv['value'] for vv in t['protected_control_measurements'].values())/2
        for k,t in audit['tasks'].items()} if audit else {}
    task_gates={k:t['matched_control_comparison'] for k,t in audit['tasks'].items()} if audit else {}
    result=dict(status='terminal_procedure_verified' if procedure else 'terminal_procedure_failed_or_unqualified',
        actual_exec_session=88656,actual_exec_exit_code_observed_by_root=a.actual_exit_code,
        actual_tool_evidence=a.actual_tool_evidence,root_observation_unix=started,
        parent_elapsed_common_seconds=c['elapsed_common_seconds'],common_limit_seconds=10800,
        root_wall_monotonic_skew_seconds=clock_skew,
        original_terminal_clock_satisfied=original_terminal_clock,root_confirmation_within_clock=root_confirmation_in_clock,
        cleanup_confirmed=cleanup,source_unchanged=source,active_owned_processes=live,uncertain_owned=uncertain,
        owned_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],reused_PID_exclusions=reused,
        immutable_refs_rehashed=len(m['immutable_files']),source_drift=source_bad,deployed_drift=deployed_bad,seal_drift=seal_bad,
        raw_campaign_flags={k:c.get(k) for k in ['status','qualification','cleanup_confirmed','source_unchanged','first_failure','error_history']},
        parent_terminal_procedure_qualified=procedure,all_declared_quality_gates_better_than_V16=quality,
        independently_audited_task_means=metrics,matched_fresh_control_means=controls,matched_control_gates=task_gates,
        retained_best_T5_regression_mean=34.86622087872278,
        audit_reference=(c.get('independent_audit') or {}).get('path'),audit_sha256=(c.get('independent_audit') or {}).get('sha256'),
        validation_scope='Reused public; regression HPO inner equals confirmation; no blind/private score claim',
        closure_preparer_identities=preparers,preparer_actual_exec_terminal_confirmation_required=True,
        root_new_fits=0,root_ML_API_calls=0,official_score=None,promotion=False,submit=False)
    assert time.monotonic()-started_mono<30,'Root no-fit closure exceeded30s before export'
    write(destination,result,True)
    if (time.time()>=c['absolute_deadline_unix'] or time.monotonic()>=c['common_deadline_monotonic']) and result['root_confirmation_within_clock']:
        result.update(status='terminal_procedure_failed_or_unqualified',root_confirmation_within_clock=False,
            parent_terminal_procedure_qualified=False,all_declared_quality_gates_better_than_V16=False,
            root_terminal_write_after_deadline=True)
        procedure=quality=False
        write(destination,result)
    result['root_closure_sha256']=sha(destination)
    write(W.parent/'outputs/lean-mvp-final.json',result)
    def number(value):return 'нет проверенного значения' if value is None else format(value,'.8f')
    (W.parent/'outputs/lean-mvp-final.txt').write_text(
        'T6 завершён: '+result['status']+'\n'
        +'Фактический exec exit: '+str(a.actual_exit_code)+'; общий лимит10800с, elapsed '+str(c['elapsed_common_seconds'])+'с.\n'
        +'Регрессия RMSE: '+number(metrics.get('regression'))+'; свежий контроль '+number(controls.get('regression'))+'; сохранённый T5 '+number(34.86622087872278)+'.\n'
        +'Классификация MacroF1: '+number(metrics.get('classification'))+'; свежий контроль '+number(controls.get('classification'))+'.\n'
        +'Техническое выполнение/аудит: '+str(procedure)+'; улучшены все объявленные quality gates: '+str(quality)+'.\n'
        +'Детали срезов/классов/ошибок: lean-mvp-final.json. Метрики reused-public, не слепая проверка и не официальный score.\n'
        +'V11/V16 и лучший прежний T5 regression candidate сохранены. Продвижение и сабмит не выполнены.\n',encoding='utf-8')
    state['lean_mvp'].update(status=result['status'],actual_terminal_exec_exit_code=a.actual_exit_code,
        terminal_root_closure='work/m3packet/terminal-root-closure.json',terminal_root_closure_sha256=sha(destination),
        procedure_terminal_qualified=procedure,all_quality_gates_improved=quality,
        final_summary='outputs/lean-mvp-final.json')
    state['active_priority']='T6 terminal. Preserve all raw evidence; review metric gates and actual closure-preparer exit before any next heavy experiment.'
    state['next'][0]='T6 terminal; never relaunch old T6/T5 or reset clocks. Read terminal-root-closure and final outputs. Freshly prove closure-preparer IDs absent and canonical lock free, then prepare the next independently declared source/test/ML experiment under existing user authorization. If cleanup/source uncertain, resolve ownership/source first.'
    state['updated_epoch']=time.time();write(W/'SESSION_STATE.json',state)
    print(json.dumps({k:result[k] for k in ['status','actual_exec_exit_code_observed_by_root','cleanup_confirmed',
        'source_unchanged','parent_terminal_procedure_qualified','all_declared_quality_gates_better_than_V16','independently_audited_task_means']}))
    return 0 if cleanup and source else 1
if __name__=='__main__':raise SystemExit(main())
