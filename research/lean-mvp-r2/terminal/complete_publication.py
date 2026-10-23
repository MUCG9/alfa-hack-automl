"""Complete report export after a literal-marker false positive; no ML work."""
from pathlib import Path
import hashlib,json,re,time,psutil
w=Path(__file__).resolve().parent;o=w.parent/'outputs'
def read(p):return json.loads(p.read_text('utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
root=w/'m4packet/terminal-root-closure.json';r=read(root)
assert r['actual_exec_exit_code_observed_by_root']==0 and r['parent_terminal_procedure_qualified']
old=w/'t7-final-export-root-closure.json';prior=read(old)
known=prior['owned_identities']+prior['closure_preparer_identities'];live=[];uncertain=[]
for item in known:
    try:
        if psutil.Process(item['pid']).create_time()==item['create_time']:live.append(item)
    except psutil.NoSuchProcess:pass
    except (psutil.AccessDenied,OSError):uncertain.append(item)
assert not live and not uncertain
me=psutil.Process();preparers=[dict(pid=me.pid,create_time=me.create_time())];parent=me.parent()
while parent is not None:
    birth=parent.create_time()
    if not any(Path(x).resolve()==Path(__file__).resolve() for x in parent.cmdline() if x and not x.startswith('-')):break
    assert parent.create_time()==birth;preparers.append(dict(pid=parent.pid,create_time=birth));parent=parent.parent()
proof=dict(status='T7_report_export_R2_fresh_closure',cleanup_confirmed=True,source_unchanged=True,
    active_owned_processes=[],uncertain_owned=[],owned_identities=known,closure_preparer_identities=preparers,
    actual_exec_session=65008,actual_exec_exit_code_observed_by_root=0,
    actual_T7_terminal_tool='56d091',actual_root_closure_tool='c3c9c6',
    failed_export_attempt=dict(source='finalize_t7_report_r1.py',actual_exit_code=1,tool_chunk='6fb328',
        reason='Generic literal credential markers in exporter source triggered its own prefix-only guard; raw audit/closure/summary contained neither workspace basename nor credential marker. Core T7 status unaffected.'),
    prior_export_proof_sha256=sha(old),original_T7_root_closure_sha256=sha(root),
    fits=0,API_calls=0,recorded_unix=time.time(),exporter_actual_terminal_confirmation_required=True)
dest=w/'t7-report-publication-closure-r2.json';assert not dest.exists();write(dest,proof)
summary=read(o/'supervision-retry-terminal-results.json')
public=w/'alfa-hack-automl/research/lean-mvp-r2/terminal';assert public.is_dir()
files={'audit.json':w/r['audit_reference'],'root-closure.json':root,
    'export-root-closure.json':old,'publication-closure-r2.json':dest,
    'terminal-results.json':o/'supervision-retry-terminal-results.json',
    'terminal-results.txt':o/'supervision-retry-terminal-results.txt',
    'export_results.py':w/'finalize_t7_report_r1.py','complete_publication.py':Path(__file__).resolve()}
for name,p in files.items():
    b=p.read_bytes()
    assert w.parent.name.encode('utf-8') not in b
    assert re.search(rb'ghp_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{12,}',b) is None
    q=public/name
    if q.exists():assert q.read_bytes()==b,'Do not replace published evidence with changed bytes'
    else:q.write_bytes(b)
write(public/'export-attempts.json',dict(R1=proof['failed_export_attempt'],R2=dict(status='publication_completed_pending_root_actual_exec',
    source_sha256=sha(Path(__file__).resolve()),closure_sha256=sha(dest),fits=0,API_calls=0)))
state=w/'SESSION_STATE.json';s=read(state)
s['supervision_retry_mvp'].update(status='terminal_procedure_verified_quality_not_promoted',
    actual_exec_exit_code=0,actual_terminal_tool_chunk='56d091',root_terminal_qualification='PASS_technical_only',
    terminal_result='outputs/supervision-retry-terminal-results.json',terminal_result_sha256=sha(o/'supervision-retry-terminal-results.json'),
    final_metrics=summary['task_means'],all_quality_gates_improved=False,
    root_export_closure='work/t7-report-publication-closure-r2.json',root_export_closure_sha256=sha(dest),
    root_export_R1_failure=proof['failed_export_attempt'],root_export_R2_actual_exec='pending_root_observation',
    original_elapsed_seconds=r['parent_elapsed_common_seconds'],promotion=False,submit=False)
s['active_queue']=None
s['active_priority']='User method experiments registered; resume automatic research. T7 terminal verified, preserve best quality. Review/publish new champion Stage0 then actual bounded serial900s technical gate after fresh exporter/preparer absence.'
s['next'][0]='T7 actual65008 exit0 tool56d091, root R3closure c3c9c6, finalmetricsRMSE34.9236892957/classF1.6569242333, no qualitypromotion. Fresh t7-report-publication-closure-r2.json exporterIDs absent before nextheavy. Review+publish champion-stage0-next-dev/run_stage0.py SHA3fdeff5dd225bf02bc8d806a5a0616a5949b7a1d3b2ce5363339d96bd4cd311f, then new900sStage0, prepared-manifestSHA5160562be127dc6130a1f3349a21b552c8aac526ead484048982716b037aa1c1, exactT7terminalrootSHA and --extra-terminal-receipt t7-report-publication-closure-r2.json=SHA. No old launch/reset; no MLgain from source-only. Full model A/B remains later.'
s['method_expansion_program']=dict(queue='work/method-expansion-program/queue.json',user_deliverable='outputs/method-expansion-experiments.txt',
    experiments=['METH-01','METH-02','METH-03','METH-04','METH-05','METH-06'],started=0,
    correction='Existing linear_text already supports numeric/category-only Ridge/LogReg/SGD; admit/test it rather than invent missing adapter.',
    method_guidance_overlay='work/method-skills-next-dev-r2',source_only=True)
s['updated_epoch']=time.time();t=state.with_suffix('.pending');write(t,s);t.replace(state)
with (w/'research-terminal-events.jsonl').open('a',encoding='utf-8') as stream:
    for event in [dict(event='T7_report_export_R1_failure',**proof['failed_export_attempt']),dict(event='T7_terminal_verified',**summary)]:
        stream.write(json.dumps(event,ensure_ascii=False,allow_nan=False)+'\n')
print(json.dumps({'T7_technical_pass':True,'quality_promoted':False,'metrics':summary['task_means'],
    'publication_closure_sha256':sha(dest),'closure_preparer_identities':preparers}))
