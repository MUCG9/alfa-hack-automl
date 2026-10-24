"""SOURCE metadata finalization only; no controller/test/candidate import or run."""
from pathlib import Path
import ast,hashlib,json
P=Path(__file__).resolve().parent;W=P.parent
AD=W/'rq6-no-fit-audit-repair-next-dev'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text('utf-8'))
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def methods(path):return {c.name+'.'+n.name:hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest() for c in ast.parse(path.read_text('utf-8-sig')).body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')}
assert not (P/'source-handoff.json').exists()
assert sha(AD/'source-handoff.json')=='9d71e51c509eb9119381c22500b5b0470e4d2703616f1271deac6df9c6eddfdc'
peer=W/'rq6-no-fit-audit-repair-fm-independent-review-r1.json'
assert sha(peer)=='d50cdc35a956269542745d0212f2ccab1d4e667b61e4c6127db353a2f5339ef7'
main=P/'run_audit.py';source=main.read_text('utf-8')
source=source.replace('AUDITOR_SHA=None',"AUDITOR_SHA='39530e417e5504f416c4e833d1c25ede6f6fc6a5a4a7aed7d73193bf896a9093'")
source=source.replace('AUDITOR_TEST_SHA=None',"AUDITOR_TEST_SHA='024642ae96640b5641c72cd6c485d5c28b9dfa0bf5f6cadcd01df5ec37320745'")
source=source.replace('AUDITOR_TEST_METHODS={}','AUDITOR_TEST_METHODS='+repr(methods(AD/'test_saved_terminal_bridge.py')))
main.write_text(source,encoding='utf-8',newline='\n')
tree=ast.parse(source)
origins=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ORIGINAL_REFS' for t in n.targets)))
assert set(origins)=={'manifest','campaign','root','negative','post','barrier','regression_seal','classification_seal','old_auditor'}
for rel,h in origins.values():assert sha(W/rel)==h
rq6={k:dict(path=rel,sha256=h) for k,(rel,h) in origins.items()}
runtime=read(W/origins['manifest'][0])['executor']['members_sha256']['automl_release_runtime.py']
contracts=[dict(path=str(path.relative_to(W)).replace('\\','/'),sha256=sha(path),methods=methods(path),count=len(methods(path)),parent=60,child=45)
    for path in (AD/'test_saved_terminal_bridge.py',P/'test_caller.py',P/'test_atomic_root.py')]
assert [r['count'] for r in contracts]==[12,4,6]
payload=dict(schema='rq6-saved-terminal-audit-repair-private-v1',clock=None,output='ra1/independent-artifact-audit.json',
    original_manifest=rq6['manifest'],original_campaign=rq6['campaign'],original_root=rq6['root'],original_auditor=rq6['old_auditor'],
    current_negative=rq6['negative'],post_tool_confirmation=rq6['post'],executor_runtime_sha256=runtime,
    actual_current_negative_observer=dict(exit_code=0,tool='b449e3'),actual_post_tool_observer=dict(exit_code=0,tool='317ee6'))
cfg=dict(schema='postfailure-standard-artifact-qualification-private-v1',readiness='NOT_READY',
    missing_bindings=['Root ABS operational binding and complete immutable old/new source/input/core map.','Independent caller source/private review, publication and actual finite current absence.','One NEW600 clock at actual main entry, MIN inherited RQ6 original6000.'],
    output=None,python=None,lock=None,immutable_files=None,common_seconds=600,caps=dict(setup=180,audit=[120,90],final=240,root=60),
    rq6=rq6,negative_actual=dict(exit_code=0,tool='b449e3'),post_actual=dict(exit_code=0,tool='317ee6'),
    launch_preparer_receipts=[],auditor=dict(path='rq6-no-fit-audit-repair-next-dev/artifact_audit.py',sha256=sha(AD/'artifact_audit.py')),
    auditor_handoff=dict(path='rq6-no-fit-audit-repair-next-dev/source-handoff.json',sha256=sha(AD/'source-handoff.json')),
    auditor_source_review=dict(path=peer.name,sha256=sha(peer)),counts=dict(path='uar-count-parser-next-dev/counts.py',sha256='bc320fd4723476c8a73404ed17a7bdec0cd4c69b1b1d41b321e370549c8cf4d3'),
    contracts=contracts,repair_payload=payload,caller_source_review=None,actual_clock=None,actual_metrics=None,promotion=False,submit=False)
save(P/'binding.template.NOT_READY.json',cfg)
atomic=dict(schema='postfailure-standard-artifact-atomic-root-private-v1',readiness='NOT_READY',missing_bindings=['Actual RA1 main exit before root.','Root hosted ABS binding/source pins/terminal campaign SHA/current source peers.'],output=None,immutable_files={},
    child_script_sha256=sha(P/'close_child.ps1'),
    **{role:dict(path=P.name+'/'+name,sha256=sha(P/name)) for role,name in [('driver','run_audit.py'),('closer','close_audit.py'),('post_tool','confirm_post_tool.py')]},
    **{role:dict(path=None,sha256=None) for role in ['manifest','campaign','python','powershell','independent_source_review','qualification_source_review']})
save(P/'atomic-binding.template.NOT_READY.json',atomic)
protocol=dict(schema='RA1-prospective-no-fit-protocol-v1',status='SOURCE_ONLY_NOT_READY',common600=True,inherited_original_RQ6_common6000_also_required=True,
    setup180=True,audit_parent120_child90=True,final300_driver240_root60=True,post_own30_no_extension=True,
    changed_contract_counts=[12,4,6],prepared_executions=22,setup_serial_parent_maxima180=True,
    old119_not_replayed=True,old_two_models_not_repeated=True,new_model_fits=0,API_calls=0,
    root_schema='postfailure-standard-artifact-qualification-root-v1',fresh_schema='postfailure-standard-artifact-atomic-root-confirmation-v1',
    post_schema='postfailure-standard-artifact-actual-wrapper-exit-confirmation-v1',old_RQ6_FAIL_preserved=True,
    original_RQ6_procedure_requalified=False,actual_clocks=None,actual_metrics=None)
save(P/'protocol.json',protocol)
# Independent mechanical evidence, never a candidate/test execution.
cx=ast.parse((W/'class-xgb-cx2-next-dev/run_audit.py').read_text('utf-8'))
new=ast.parse(source)
def fn(tree,name):return next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
def dump(node):return ast.dump(node,include_attributes=False)
assert dump(fn(cx,'capture'))==dump(fn(new,'capture'))
fence=ast.parse(ast.unparse(fn(new,'temporary_fence')).replace("'ra-'","'cx-'")).body[0]
assert dump(fence)==dump(fn(cx,'temporary_fence'))
qh=ast.parse((W/'qwen-three-hour-outer-next-dev-r5/run_root.py').read_text('utf-8'))
newatomic=ast.parse((P/'run_root.py').read_text('utf-8'))
assert dump(fn(qh,'capture'))==dump(fn(newatomic,'capture'))
proof=dict(schema='RA1-thin-caller-source-proof-v1',status='SOURCE_ONLY_NOT_EXECUTED',
    qualified_CX2_main_lifecycle_source_sha256=sha(W/'class-xgb-cx2-next-dev/run_audit.py'),
    qualified_QH_R5_atomic_post_source_handoff_sha256=sha(W/'qwen-three-hour-outer-next-dev-r5/source-handoff.json'),
    capture_whole_AST_exact_CX2_and_QH=True,temp_fence_inverse_prefix_only_whole_AST_exact=True,
    changed_boundaries=['Exact RQ6 clean-negative admission and original nine role refs; no old positive PASS requirement.',
        'Fixed saved-artifact adapter/context/results instead of CLASS factor comparison.',
        'MIN new600/originalRQ6common6000 for parent,root,atomic,post and active phases; new clocks never replace old.',
        'New explicit RA1 root/fresh/post schemas; original failure refs and original model/core facts preserved.'],
    methods={r['path']:r['methods'] for r in contracts},prepared_counts=[12,4,6],prepared_executions22=True,
    contracts_executed=0,model_fits=0,API_calls=0,author_data_or_PID_reads=0,actual_clock=None)
save(P/'source-proof.json',proof)
(P/'README.txt').write_text('''SOURCE ONLY / NOT_READY. RA1 saved-standard-artifact audit, no models/API/119 replay.
Common NEW600=setup180+audit120+final300(driver240/root60); every phase also MIN original RQ6common6000. Source guarded before any numerical/truth import.
22 prepared changed contracts (adapter12/caller4/atomic6), three60/45 slots inside setup180; author executed0.

Root hosted binding: set output=ABS WORK/ra1, python=ABS pinned venv launcher, canonical ABS ResearchLock. Normalize every typed ref path and contracts[].path to ABS, all rq6 refs and repair_payload refs/output. Keep payload.clock=None; actual main assigns8-key new600/audit120 clock.
immutable_files starts exact prior RQ6private1017 map, plus all packet/auditor/helper/peer/count source hashes and nine rq6 refs. Both core-seal inventories are independently read+rehash guarded before setup/auditor, without regenerating any artifact. Never re-pin an existing value.
Hosted writer creates no native preparer identities: launch_preparer_receipts may be[]. Optional later actual native metadata preparers require exact captured {path,sha256,actual_tool:{exit_code:0,tool:ACTUAL}}. Main capture3 and whole child/root/atomic/post union remain mandatory.

Metadata preflight BEFORE assigning unitclock: import ONLY reviewed run_audit.py (stdlib top level), cfg=config(ABS_manifest,rawSHA,selfSHA), known=predecessor(cfg,lambda:None). These functions do not create a clock, scan PIDs, import candidate/models or open numerical data. predecessor loads hash-qualified C5 only for ids(). A native preflight process, if used, must have its actual capture/exit accounted by root; no fabricated identities for hosted writes.

Main CLI: python -B -X utf8 run_audit.py --launch --manifest ABS --manifest-sha256 SHA --self-sha256 SHA --launch-parent-pid ACTUAL_PS_PID --launch-parent-create-time ACTUAL_PS_BIRTH.
After actual main exit, root hosted-writes atomic-binding from template: all operational refs ABS, outputABSra1, immutable map full superset, terminal campaign SHA, source peer refs, no local writer/binder receipt.
Atomic CLI: run_root.py --binding ABS --binding-sha256 SHA --self-sha256 SHA --actual-exit-code ACTUAL --actual-tool-evidence ACTUAL_MAIN_TOOL [--actual-exec-session ACTUAL_HANDLE] --launch-parent-pid PID --launch-parent-create-time BIRTH.
After actual wrapper toolEXIT0 IMMEDIATELY: confirm_post_tool.py --binding ABS --binding-sha256 SHA --self-sha256 SHA --wrapper-tool ACTUAL_WRAPPER_TOOL --wrapper-exit-code0 --launch-parent-pid NEW_PS_PID --launch-parent-create-time BIRTH. Use '--wrapper-exit-code 0' as separate argv tokens.
Native childexit is saved before fresh; finitepost keeps full known/root/closer/wrapper scope and records currentobserverpreparers; actual own tool exit is separately required. Same actualcloserbirth60, savedfinal240, new600 and old6000; no new60/reset.

Original RQ6main49569/dbc6a1EXIT1 and closerfb3841EXIT1/rootf9e remain FAIL. RA1 result/root is a distinct saved-artifact qualification. No source/campaign/report mutation or fake RQ6positive schema. Finalactualmetrics/READY/publication/clock/root admission remain root-owned.
''',encoding='utf-8',newline='\n')
external={rel:h for rel,h in origins.values()}
for folder,filename in [(AD,'source-handoff.json'),(W/'class-xgb-cx2-next-dev','source-handoff.json'),(W/'qwen-three-hour-outer-next-dev-r5','source-handoff.json')]:
    h=read(folder/filename);external[folder.name+'/'+filename]=sha(folder/filename)
    for rel,digest in h['files_sha256'].items():external[folder.name+'/'+rel]=digest
external[peer.name]=sha(peer)
for rel in ['rq6-current-negative-audit-next-dev/source-handoff.json','rq6-current-negative-post-tool-next-dev/source-handoff.json',
            'rq6-current-negative-fm-independent-source-review-r1.json','br-standard-release-qualification-next-dev/controller-r5/run_controller.py',
            'verified-supervision-next-dev-r2/coordinator.py','verified-resource-sampling-next-dev/verified_sampling.py','uar-count-parser-next-dev/counts.py']:
    external[rel]=sha(W/rel)
for rel,h in external.items():assert sha(W/rel)==h,rel
for p in P.glob('*.py'):compile(p.read_text('utf-8'),str(p),'exec')
files={p.relative_to(P).as_posix():sha(p) for p in P.iterdir() if p.is_file() and p.name!='source-handoff.json'}
save(P/'source-handoff.json',dict(schema='RA1-saved-standard-artifact-qualification-source-handoff-v1',status='FROZEN_SOURCE_ONLY_NOT_READY_PENDING_PEER',
    files_sha256=files,external_refs_sha256=external,prepared_contract_executions=22,actual_contract_executions=0,
    actual_models=0,actual_API=0,actual_clock=None,actual_metrics=None,approval=None,original_RQ6_FAIL_preserved=True))
print(json.dumps(dict(handoff_sha256=sha(P/'source-handoff.json'),local=len(files),external=len(external),prepared=22,executed=0)))
