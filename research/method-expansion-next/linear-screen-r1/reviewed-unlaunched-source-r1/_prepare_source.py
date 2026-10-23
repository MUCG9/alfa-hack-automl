"""One-shot stdlib source preparation; never import/execute candidate sources."""
from pathlib import Path
import ast
import copy
import difflib
import hashlib
import json

HERE=Path(__file__).resolve().parent
WORK=HERE.parent
BASE=WORK/'method-component-next-dev'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,value):
    p=HERE/name
    assert not p.exists(),name
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def source(name,value):
    p=HERE/name
    assert not p.exists(),name
    p.write_text(value,encoding='utf-8',newline='\n')
def change(text,old,new):
    assert text.count(old)==1,(text.count(old),old[:100])
    return text.replace(old,new)

expected={'run_components.py':'672479b4aa444242369c28aef179454e1ab3c6470e3b00052676f255d4281379',
    'audit_components.py':'bf3526023c265fd102531426a2c35472686be84104500e703eb82d18f9456973',
    'protocol.json':'d21a32cabd475756f18426760d61a960e92c202978f3d5b324edcd4c57c13ad3',
    'static-proof.json':'a734fccb1416b3f1b5d82d06322577ab7a80dc5323ebf864ac89db32ed67ee26'}
assert all(sha(BASE/name)==digest for name,digest in expected.items())
old_closer=WORK/'close_method_components_r1.py'
assert sha(old_closer)=='7a6ef1331c49699a6fdd8cb10353b6b051594761856ba9f2d1c17bf38c3ed9d7'
closer=old_closer.read_text('utf-8').replace('METH01','METH02').replace('meth01','meth02').replace('6600','10800')
closer=closer.replace('w=Path(__file__).resolve().parent\n','w=Path(__file__).resolve().parents[1]\n')
closer=closer.replace('method-component-results','method-linear-results').replace("s['method_component_screen']", "s['method_linear_component_screen']")
closer=change(closer,"s['next'][0]='METH02 terminal: read actual exit/audit/rootclosure and fresh helper-preparer absence. Preserve every cut/negative/timeout. Strong CP1/B and V11/V16 retained. Next registered fixed90/10 component blend METH03 uses only closed aligned caches, no fits; then METH02 existing no-text linear tool separately.'",
    "s['next'][0]='METH02 terminal: read actual exit/audit/rootclosure and fresh helper-preparer absence. Preserve every cut/negative/timeout and prior METH01/METH03 evidence. Strong CP1/B and V11/V16 retained; no automatic model promotion. Future linear blend or whole-agent admission requires a separately declared protocol.'")
source('close_linear_components.py',closer)
closure=('meth01/terminal-root-closure.json','2c67361da8f95875b35d124ac6c19d6cccba28c899f1e20dada88f3bec4ea283')
assert sha(WORK/closure[0])==closure[1]  # bytes only, no outcome parsing
fixture=('method-linear-next-dev/test_tabular_linear_contracts.py',sha(HERE/'test_tabular_linear_contracts.py'))
queue=WORK/'method-expansion-program/queue.json'
registration=dict(source_path='method-expansion-program/queue.json',source_sha256=sha(queue),
    registered_entry=next(v for v in json.loads(queue.read_text('utf-8'))['experiments'] if v['id']=='METH-02'),
    boundary='Copied registration metadata; original mutable queue is not runtime authority. No job/clock/outcome read.')
write('registered-METH02.json',registration)
registration_sha=sha(HERE/'registered-METH02.json')

protocol=json.loads((BASE/'protocol.json').read_text('utf-8'))
protocol.update(status='source_prepared_not_executed_not_a_metric',experiment_id='METH-02',
    scope='Fixed admission of existing linear_text no-text Ridge/LogisticRegression versus protected first SINGLE; no model/agent change',
    registration=dict(path='method-linear-next-dev/registered-METH02.json',sha256=registration_sha),
    output_root='meth02',driver='method-linear-next-dev/run_components.py',auditor='method-linear-next-dev/audit_components.py')
protocol['clock']['common_seconds']=10800
protocol['allocations_seconds']=dict(setup_source_evidence_materialization_and_contracts=900,
    ten_parent_envelopes=6000,per_parent=600,per_child=570,cleanup_guard_seal_persist_within_each_parent=30,
    independent_audit_parent=600,audit_child=570,final_cleanup_export=300,unused_spare_not_reinvested=3000,arithmetic_total=10800)
protocol['setup_amendment_before_outcomes']='Reuse exact unchanged T7 source458/exact23 receipts with fresh hashes. NEW eight tiny synthetic existing-linear contracts must run successfully under a300parent/270child envelope WITHIN setup900; not yet executed. No broader source registry change; no saved/spare time reinvestment.'
protocol['lineage']['actual_METH01_required']=dict(path=closure[0],sha256=closure[1],actual_exec_session=3417,
    exit_code='explicit CLI must match actual root receipt; no requirement of ML/quality success',
    campaign='meth01/campaign.json, actual terminal bytes pinned during future setup',
    fresh_union='owned_identities plus closure_preparer_identities merged before/under lock/between children')
protocol['lineage']['after_intervening_blend']='Root supplies any intervening actual closed METH03 launcher/auditor/helper union via --extra-terminal-receipt PATH=SHA before METH02 launch. No invented future receipt or clock.'
protocol['candidate']=dict(engine='linear_text',feature_code='',params=dict(generic_features='none'),
    regression_effective=dict(estimator='Ridge',alpha=10,solver='lsqr'),
    classification_only_params=dict(text_classifier='logistic',text_C=1,class_weight_power=.5),
    classification_effective=dict(estimator='LogisticRegression',C=1,max_iter=1000,random_state=42,class_weight=None),
    weight_scope='Fixed inherited power.5 matches all3 strong control components; no tuning or simultaneous balanced class_weight',
    not_effective_here=['text_alpha is not Ridge alpha','tree iterations/early stopping','tree generic features/selector','target encoding/history/log_target/calibration'],
    preprocessing='Existing fitting-only numeric median keep_empty/scaling and sparse OHE min_frequency3/unknown ignore. Raw numeric finite/string cleanup is row-local on supplied schemas.')
protocol['factor_boundary']='Complete supported recipe/package comparison: no-text linear_text generic_features=none differs from rich history/target-encoding control preprocessing. Not a pure causal linear-versus-boosting family effect.'
protocol['candidate_failure_policy']='All parameters fixed before outcomes. No postscore recipe repairs, alternate regularization, retries, candidate replacement, spare reinvestment or silently dropped failures. Negative standalone artifacts remain useful only for a separately declared fixed blend.'
protocol['lineage']['actual_METH01_required']['actual_exec_exit_code_observed_by_root']=0
protocol['tool_contracts']=dict(path=fixture[0],sha256=fixture[1],prepared_methods=8,actual_tests_run=0,
    future_parent_seconds=300,future_child_seconds=270,inside_setup900=True,threads=1,
    actual_fits_now=0,expected_tiny_fitting_callbacks_if_all_methods_reached=10,
    future_tiny_fits_are_charged=True,no_public_data_or_API=True,
    cases=['fixed Ridge numeric/category/all-missing numeric','heldout poison cannot change fitted median/vocabulary/coef',
        'unknown category sparse width and row ordering','infrequent OHE fitted vocabulary',
        'multiclass probability output/class/row alignment','binary declared positive string class',
        'fitting-only power.5 weights without double balance','absent declared fitting class explicitly rejects probability output'])
protocol['resource_contract']['technical_fixture_threads']=1
protocol['worker_cli']='PYTHON -B -X utf8 -u meth02/sources/automl_worker.py ABS_JOB.json'
protocol['saved_split_bindings']='Same exact five old2e NPZ bytes as METH01; no regeneration. SHA map in source-evidence.json; worker pairs share the same copied split.'
protocol['post_exec_root_closer']=dict(path='method-linear-next-dev/close_linear_components.py',sha256=sha(HERE/'close_linear_components.py'),
    external_after_parent_exec=True,actual_exec_and_fresh_preparer_absence_required=True,
    candidate_gates_source='audit.registered_component_decisions',technical_success_does_not_imply_quality_success=True,
    authority='Root-use source copy only; not invoked by driver or during preparation. Root owns any future output/STATE write.')
write('protocol.json',protocol)
protocol_sha=sha(HERE/'protocol.json')

driver=(BASE/'run_components.py').read_text('utf-8')
driver=driver.replace('METH01','METH02').replace('meth01','meth02').replace('6600','10800')
driver=change(driver,"REGISTRATION = ('method-portfolio-next-dev-r2/registered-METH02.json', 'ac359bfc16ac43a044ff08f346b05514c1dfe719dea7844256cb382b91331d4d')",f"REGISTRATION = ('method-linear-next-dev/registered-METH02.json', '{registration_sha}')")
driver=change(driver,"PROTOCOL = ('method-portfolio-next-dev-r2/METH02-protocol.json', '5d8d384555bf92ab452a9552e8eb270bf8a3a13a7709272f9dbccc282af1ca61')",f"PROTOCOL = ('method-linear-next-dev/protocol.json', '{protocol_sha}')")
driver=driver.replace("AUDITOR = 'method-component-next-dev/audit_components.py'","AUDITOR = 'method-linear-next-dev/audit_components.py'")
driver=change(driver,'COMMON, SETUP, PARENT, CHILD, AUDIT, CLEANUP = 10800, 900, 480, 450, 600, 300',
    'COMMON, SETUP, PARENT, CHILD, AUDIT, CLEANUP, SPARE = 10800, 900, 600, 570, 600, 300, 3000')
driver=change(driver,"FIXED = dict(engine='extra_trees', feature_code='', params=dict(iterations=128,\n    max_depth=16, min_samples_leaf=4, max_features=.9, seed=42, generic_features='none'))",
    "FIXED = dict(engine='linear_text', feature_code='', params=dict(generic_features='none'))\n"+
    f"FIXTURES = {fixture!r}\nMETH01_PROOF = {closure!r}")
driver=change(driver,"for name in ['self-sha256', 'auditor-sha256', 'pair-root-closure', 'pair-root-closure-sha256']:",
    "for name in ['self-sha256', 'auditor-sha256', 'pair-root-closure', 'pair-root-closure-sha256',\n                 'method01-root-closure', 'method01-root-closure-sha256']:")
driver=change(driver,"    p.add_argument('--pair-exit-code', type=int, required=True)",
    "    p.add_argument('--pair-exit-code', type=int, required=True)\n    p.add_argument('--method01-exec-session', type=int, required=True)\n    p.add_argument('--method01-exit-code', type=int, required=True)")
driver=change(driver,'allocations=dict(setup_source_exact=SETUP, ten_workers=10*PARENT, independent_audit=AUDIT, cleanup_export=CLEANUP),',
    'allocations=dict(setup_source_exact_and_contracts=SETUP, ten_workers=10*PARENT, independent_audit=AUDIT, cleanup_export=CLEANUP, unused_spare_not_reinvested=SPARE),')
driver=change(driver,'explicit = dict([BASE, COOR, R4, REGISTRATION, PROTOCOL, *SPECS.values()])',
    'explicit = dict([BASE, COOR, R4, REGISTRATION, PROTOCOL, FIXTURES, *SPECS.values()])')
driver=driver.replace('unchanged_native_ET_source_required','unchanged_native_no_text_linear_source_required')
anchor="            merge(name,digest)\n        frozen(setup_end,'component_setup_cap_exhausted')\n        owner = imported"
new="""            merge(name,digest)
        need((args.method01_root_closure,args.method01_root_closure_sha256)==METH01_PROOF
             and args.method01_exec_session==3417,'actual_METH01_terminal_reference_required')
        need(sha(local(args.method01_root_closure),check)==args.method01_root_closure_sha256,'actual_METH01_terminal_proof_pin_failed')
        proof=load(local(args.method01_root_closure))
        need(proof.get('cleanup_confirmed') is True and proof.get('source_unchanged') is True
             and proof.get('active_owned_processes')==[] and proof.get('uncertain_owned')==[]
             and proof.get('owned_identities') and proof.get('closure_preparer_identities')
             and proof.get('actual_exec_session')==args.method01_exec_session
             and proof.get('actual_exec_exit_code_observed_by_root')==args.method01_exit_code
             and proof.get('original_common_seconds')==6600,'actual_METH01_terminal_cleanup_lineage_required')
        prior_path='meth01/campaign.json';prior=load(local(prior_path))
        need(prior.get('finished_unix') is not None and prior.get('finished_monotonic') is not None
             and prior['finished_unix']<=start_unix and prior['finished_monotonic']<=start_mono
             and prior['start_unix']==proof['original_start_unix']
             and prior['absolute_deadline_unix']==proof['original_deadline_unix']
             and prior['elapsed_common_seconds']==proof['raw_parent_elapsed_seconds']
             and prior['cleanup_confirmed'] is True and prior['source_unchanged'] is True,
             'actual_METH01_terminal_campaign_binding_required')
        known.update(coor.identities(proof['owned_identities']))
        known.update(coor.identities(proof['closure_preparer_identities']))
        merge(args.method01_root_closure,args.method01_root_closure_sha256);merge(prior_path,sha(local(prior_path),check))
        prior_reference=dict(path=args.method01_root_closure,sha256=args.method01_root_closure_sha256,
            campaign_path=prior_path,campaign_sha256=pins[prior_path],actual_exec_session=args.method01_exec_session,
            actual_exec_exit_code_observed_by_root=args.method01_exit_code,quality_success_required=False)
        state['completed_METH01_predecessor']=prior_reference
        frozen(setup_end,'component_setup_cap_exhausted')
        owner = imported"""
driver=change(driver,anchor,new)
driver=change(driver,"if arm=='candidate' and kind=='classification': recipe['params']['class_weight_power']=.5",
    "if arm=='candidate' and kind=='classification': recipe['params'].update(text_classifier='logistic',text_C=1,class_weight_power=.5)")
driver=change(driver,"compiled_sha256=base['compiled_sha256'],registry=base['registry'],tasks=tasks,jobs=jobs,",
    "compiled_sha256=base['compiled_sha256'],registry=base['registry'],tasks=tasks,jobs=jobs,\n                    completed_METH01_predecessor=prior_reference,tool_contract_source=dict(path=FIXTURES[0],sha256=FIXTURES[1]),")
anchor="                    state['technical_checks_newly_executed']=0\n                    state['technical_gate_evidence']='Reused actual T7 source458/exact23 plus actual65008/exit0 root closure; all bytes freshly rehashed'\n"
new="""                    # New tiny tool contracts consume a fixed300 parent WITHIN setup900.
                    tick=time.monotonic();need(setup_end-tick>=300,'linear_contract_full_setup_allocation_unavailable')
                    absence();result=ROOT/'g/linear-contracts.json';receipt=ROOT/'g/linear-contracts-supervisor.json'
                    command=[sys.executable,'-B','-X','utf8',str(local(FIXTURES[0])),
                        '--self-sha256',FIXTURES[1],'--output',str(result)]
                    sup=coor.supervise(command,WORK,receipt,'linear-contracts',tick,300,270,deadline,unix,
                        300+10*PARENT+AUDIT+CLEANUP,state,persist,frozen,owner,processes,
                        state['coordinator_bootstrap_identities'],solver_seconds=None)
                    coor.child_errors(state,sup);finished.update(coor.identities(sup.get('owned_process_identities',[])))
                    need(sup.get('status')=='ok' and sup.get('exit_code')==0 and sup.get('cleanup_confirmed') is True,
                         'linear_contract_process_failed')
                    check_contract=lambda:checkpoint(min(tick+300,setup_end),'linear_contract_setup_parent_exhausted')
                    data=load(result)
                    need(data.get('status')=='passed' and data.get('tests_run')==8 and data.get('errors')==0
                         and data.get('failures')==0 and data.get('skipped')==0 and data.get('tiny_fitting_callbacks')==10
                         and data.get('fixture_source_sha256')==FIXTURES[1] and data.get('public_data_used') is False
                         and data.get('API_calls')==0,'linear_tool_contracts_incomplete_or_failed')
                    need(start_unix<=sup['start_unix']<=sup['end_unix']<start_unix+SETUP
                         and start_mono<=sup['start_monotonic']
                         and sup['start_monotonic']+sup['seconds']<setup_end,'linear_contract_original_setup_clock_binding_failed')
                    state['gates'].append(dict(name='linear_contracts',evidence_mode='NEW_SYNTHETIC_LINEAR_TOOL_CONTRACTS',
                        result_path=coor.relative(result),result_sha256=sha(result,check_contract),
                        supervisor_path=coor.relative(receipt),supervisor_sha256=sha(receipt,check_contract),supervisor=sup))
                    deployment[coor.relative(result)]=sha(result,check_contract)
                    deployment[coor.relative(receipt)]=sha(receipt,check_contract);check_contract();persist()
                    state['technical_checks_newly_executed']=8
                    state['technical_gate_evidence']='Reused actual T7 source458/exact23; NEW8tiny linear contracts within setup900; all original bytes rehashed'
"""
driver=change(driver,anchor,new)
driver=driver.replace('component_cleanup_seal_over480','component_cleanup_seal_over600')
source('run_components.py',driver)

auditor=(BASE/'audit_components.py').read_text('utf-8')
auditor=auditor.replace('METH01','METH02').replace('meth01','meth02').replace('6600','10800')
auditor=change(auditor,"FIXED = dict(engine='extra_trees',feature_code='',params=dict(iterations=128,max_depth=16,\n    min_samples_leaf=4,max_features=.9,seed=42,generic_features='none'))",
    "FIXED = dict(engine='linear_text',feature_code='',params=dict(generic_features='none'))\n"+
    f"FIXTURES = {fixture!r}\nMETH01_PROOF = {closure!r}")
auditor=auditor.replace('exact_native_ET_base_required','exact_native_no_text_linear_base_required').replace('unchanged_native_ET_archive_required','unchanged_native_no_text_linear_archive_required')
auditor=auditor.replace("manifest['per_worker_parent_seconds']==480 and manifest['per_worker_child_seconds']==450",
    "manifest['per_worker_parent_seconds']==600 and manifest['per_worker_child_seconds']==570")
auditor=auditor.replace("terminal['parent_cap_seconds']==480 and terminal['child_cap_seconds']==450",
    "terminal['parent_cap_seconds']==600 and terminal['child_cap_seconds']==570")
auditor=auditor.replace("0<=entry['seconds_including_seal']<480","0<=entry['seconds_including_seal']<600")
auditor=change(auditor,"need(set(gates)=={'source','exact'},'fresh_source_exact_gates_required')\n    for gate in gates.values():",
    "need(set(gates)=={'source','exact','linear_contracts'},'source_exact_and_linear_contracts_required')\n    for name in ['source','exact']:\n        gate=gates[name]")
anchor="    old_campaign=load(local('t7/campaign.json'));old_root=load(local('m4packet/terminal-root-closure.json'))"
new="""    gate=gates['linear_contracts']
    need(gate['evidence_mode']=='NEW_SYNTHETIC_LINEAR_TOOL_CONTRACTS'
         and digest(local(gate['supervisor_path']))==gate['supervisor_sha256']
         and load(local(gate['supervisor_path']))==gate['supervisor']
         and gate['supervisor']['status']=='ok' and gate['supervisor']['exit_code']==0
         and gate['supervisor']['cleanup_confirmed'] is True
         and gate['supervisor']['parent_cap_seconds']==300 and gate['supervisor']['child_cap_seconds']==270
         and gate['supervisor']['solver_budget_seconds'] is None
         and campaign['start_unix']<=gate['supervisor']['start_unix']<=gate['supervisor']['end_unix']<campaign['start_unix']+900
         and campaign['start_monotonic']<=gate['supervisor']['start_monotonic']
         and gate['supervisor']['start_monotonic']+gate['supervisor']['seconds']<campaign['start_monotonic']+900
         and 0<=campaign['setup_seconds']<900
         and digest(local(gate['result_path']))==gate['result_sha256'],'new_linear_contract_receipt_required')
    checks=load(local(gate['result_path']))
    need(checks.get('status')=='passed' and checks.get('tests_run')==8 and checks.get('errors')==0
         and checks.get('failures')==0 and checks.get('skipped')==0 and checks.get('tiny_fitting_callbacks')==10
         and checks.get('fixture_source_sha256')==FIXTURES[1] and checks.get('public_data_used') is False
         and checks.get('API_calls')==0 and digest(local(FIXTURES[0]))==FIXTURES[1],
         'new_linear_synthetic_tool_contracts_failed')
    prior_ref=manifest['completed_METH01_predecessor']
    need((prior_ref['path'],prior_ref['sha256'])==METH01_PROOF and prior_ref['actual_exec_session']==3417
         and prior_ref['quality_success_required'] is False
         and digest(local(prior_ref['path']))==prior_ref['sha256']
         and digest(local(prior_ref['campaign_path']))==prior_ref['campaign_sha256'],'actual_METH01_predecessor_binding_changed')
    prior=load(local(prior_ref['path']))
    need(prior.get('cleanup_confirmed') is True and prior.get('source_unchanged') is True
         and prior.get('actual_exec_session')==prior_ref['actual_exec_session']
         and prior.get('actual_exec_exit_code_observed_by_root')==prior_ref['actual_exec_exit_code_observed_by_root'],
         'actual_METH01_predecessor_cleanup_changed')
    old_campaign=load(local('t7/campaign.json'));old_root=load(local('m4packet/terminal-root-closure.json'))"""
auditor=change(auditor,anchor,new)
auditor=change(auditor,"if kind=='classification':candidate['params']['class_weight_power']=.5",
    "if kind=='classification':candidate['params'].update(text_classifier='logistic',text_C=1,class_weight_power=.5)")
source('audit_components.py',auditor)

refs={f'method-component-next-dev/{n}':d for n,d in expected.items()}
refs.update(json.loads((BASE/'reuse-review.json').read_text('utf-8'))['inputs_sha256'])
refs={n:d for n,d in refs.items() if 'registered-METH01' not in n and 'METH01-protocol' not in n}
for name in ['m3dev/src/automl/execution/model_adapters/linear_text.py',
             'm3dev/src/automl/execution/model_adapters/registry.py',
             'm3dev/src/automl/execution/weighting/classes.py',
             'm3dev/src/automl/publishing/service.py','close_method_components_r1.py',closure[0]]:
    refs[name]=sha(WORK/name)
assert all(sha(WORK/n)==h for n,h in refs.items())
write('source-evidence.json',dict(status='source_only_exact_reuse_no_runtime_imports',inputs_sha256=refs,
    native_adapter='Existing no-text route before tree preparation; no model source/flat archive change',
    class_weight='Power.5 only, no simultaneous class_weights balanced. Existing fitting-row weights normalized to mean1',
    linear_effective_parameters='Ridge alpha10/lsqr hardcoded; logistic C1/max_iter1000/random_state42. No text_alpha/Ridge fiction.',
    class_probability_order='NPZ retains model.classes_; frozen R4 independently aligns declared class/CSV order',
    invalid_fitting_class='Explicit missing class outcome, never synthesize/dismiss missing column',
    fixture_actual_tests_run=0,fixture_actual_fits=0,metrics=None))
patch=''
for name in ['run_components.py','audit_components.py']:
    patch+=''.join(difflib.unified_diff((BASE/name).read_text('utf-8').splitlines(True),
        (HERE/name).read_text('utf-8').splitlines(True),fromfile='METH01/'+name,tofile='METH02/'+name))
source('meth01-to-meth02.patch',patch)
source('README.txt', '''METH02 source-only existing no-text linear component screen

This is a minimal adaptation of reviewed METH01 driver/auditor, using the same
immutable68-member m3 archive, five old NPZ cuts, first protected SINGLE controls,
R4 TaskVerifier/diagnostics and unchanged null/quality gates. No new adapter,
portfolio/Qwen/HPO, selector, calibration, target encoding or target transform.
This compares complete supported packages: the no-text generic_features=none
candidate has different preprocessing from rich history/TE controls. It cannot
identify a pure causal linear-versus-boosting family effect.

Regression is existing Ridge(alpha=10,solver=lsqr). text_alpha does not control
Ridge and is omitted. Classification is existing logistic(text_C=1), with fixed
inherited class_weight_power=.5 and NO class_weights=true. This fixed weight was
declared before outcomes, not tuned. Preprocessing is fitted on current fit rows.
No postscore model/regularization repair, new setting, retry or spare reinvestment.

One future10800 clock = setup900 +10*600 parents +audit600 +cleanup300 +spare3000.
Each parent600 includes570 child and30 cleanup/source/seal. Spare is not usable
for extra models, retries, extending stages or tuning. All jobs fail/null honestly.
Within setup900 a NEW300parent/270child synthetic8-method fixture must pass.
These fixtures intentionally exercise10 tiny actual fits in a FUTURE run, charged
to setup/common time. No fixture/test/model import or fit has been executed now.
Unchanged T7 source458/exact23 is freshly hash-checked and labelled REUSED; these
8 outside-runtime methods do not imply a new source466/exact run or registry edit.

Root supplies --launch --self-sha256 SHA --auditor-sha256 SHA, retained exact CP1
--pair-root-closure cp1/terminal-root-closure.json --pair-root-closure-sha256
96f5d956fa235cfd0904d55f67aeeaae8c93a083391fe8b370836f6e39ba309d
--pair-exec-session43472 --pair-exit-code0 (flags and values must be separate),
and --method01-root-closure meth01/terminal-root-closure.json
--method01-root-closure-sha2562c67361da8f95875b35d124ac6c19d6cccba28c899f1e20dada88f3bec4ea283
--method01-exec-session3417 --method01-exit-code ACTUAL_ROOT_OBSERVED_CODE.
The explicit METH01 exit must match the real receipt; a quality win is not needed.
Use the exact flag/value argv array from source-handoff.json, not this prose.
Any intervening actual METH03 roots/helpers require their real pinned terminal
receipt through --extra-terminal-receipt PATH=SHA. Before/under lock and between
children the existing strict known owned+bootstrap+preparer unions must be absent.
No old PPID orphan adoption or invented receipt, quality-positive or API gate.

Not launch-ready: source peer review/publication, actual synthetic contract gate,
root-owned launch/actual clock, intervening closure and a distinct METH02 terminal
root-closer review are still pending. No command has been run and no actual
input/job/split/clock was generated. Do not invoke the old METH01 closer for METH02.
The separately copied close_linear_components.py is root-use post-exit source;
root owns its future actual-exec input and output/STATE writes. It has not run.
No full refit, whole-agent qualification, promotion, submission or official score.
''')

asts={}
for name in ['run_components.py','audit_components.py','test_tabular_linear_contracts.py','close_linear_components.py']:
    text=(HERE/name).read_text('utf-8');asts[name]=ast.parse(text);compile(text,str(HERE/name),'exec')
methods=[n.name for n in ast.walk(asts['test_tabular_linear_contracts.py']) if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')]
assert len(methods)==8
assert all(sha(BASE/n)==d for n,d in expected.items())
assert ast.literal_eval(next(n.value for n in asts['run_components.py'].body if isinstance(n,ast.Assign)
    and any(isinstance(t,ast.Tuple) and t.elts[0].id=='COMMON' for t in n.targets)))==(10800,900,600,570,600,300,3000)
files={p.name:sha(p) for p in HERE.iterdir() if p.is_file() and p.name not in {'source-handoff.json','static-proof.json'}}
write('static-proof.json',dict(status='AST_compile_and_hash_only_no_candidate_execution',files_sha256=files,
    base_frozen_unchanged_sha256=expected,contract_methods=methods,prepared_contract_methods=8,actual_tests_run=0,
    arithmetic='10800=900+10*600+600+300+3000;600=570+30; new300contractgate inside900',
    source_delta='Harness recipe/paths/budgets/new contract gate/METH01 terminal binding only; runtime/adapter/archive unchanged',
    inherited_preserved=['five oldsplit pins','exact SINGLE control recipes','CP1/T7/history/T5/T6 closure union',
        'R4 metrics and perclass gates','seals before labels','null failures','late error clears live quality'],
    expected_reused_registry=458,expected_reused_exact=23,extra_source_registry_methods_added=0,
    actual_driver_invocations=0,actual_auditor_invocations=0,actual_application_imports=0,actual_tests=0,
    actual_fits=0,actual_API_calls=0,actual_data_or_prediction_reads=0,actual_generated_jobs=0,actual_clocks=0,
    qualification='Static only. No measured runtime/quality or execution-readiness claim.',ML_metric=None,promotion=False))
files={p.name:sha(p) for p in HERE.iterdir() if p.is_file() and p.name!='source-handoff.json'}
write('source-handoff.json',dict(status='source_frozen_unexecuted_peer_review_pending',files_sha256=files,
    unchanged_archive_sha256='16120391716fe43b7f0ec2b36f35eaea7511a08cba4f4108da01cd81dea314d0',
    exact_METH01_closure=dict(path=closure[0],sha256=closure[1],actual_exec_session=3417,
        exit_code='provided by root CLI and matched to real receipt, no positive quality required'),
    launch_argv_template=['work/venv/Scripts/python.exe','-B','-X','utf8','-u','work/method-linear-next-dev/run_components.py',
        '--launch','--self-sha256',files['run_components.py'],'--auditor-sha256',files['audit_components.py'],
        '--pair-root-closure','cp1/terminal-root-closure.json','--pair-root-closure-sha256',
        '96f5d956fa235cfd0904d55f67aeeaae8c93a083391fe8b370836f6e39ba309d','--pair-exec-session','43472','--pair-exit-code','0',
        '--method01-root-closure',closure[0],'--method01-root-closure-sha256',closure[1],
        '--method01-exec-session','3417','--method01-exit-code','0',
        '--extra-terminal-receipt','ACTUAL_INTERVENING_CLOSURE_PATH=SHA'],
    changed_sources=['run_components.py','audit_components.py'],new_contract_source='test_tabular_linear_contracts.py',
    actual_tests_run=0,prepared_tests=8,actual_fits=0,actual_API_calls=0,actual_runtime_imports=0,
    actual_jobs_or_clock_generated=False,launch_ready=False,ML_metric=None,promotion=False,
    root_checkpoints=['source peer review/publication','actual synthetic contracts within future setup900',
        'real terminal closure of any intervening METH03 and fresh exact identities underlock',
        'root owns actual clock/launch/exec observation','METH02 terminal root-closer source review']))
print(json.dumps(dict(status='source_only_prepared_no_tests_imports_fits_API',files_sha256=files,
    handoff_sha256=sha(HERE/'source-handoff.json')),indent=2))
