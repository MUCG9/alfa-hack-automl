"""METH02 saved component artifacts: frozen R4.TaskVerifier/diagnostics, no fits.

All ten closed cores are sealed and rehashed BEFORE pristine labels are parsed.
An ordinary failed worker has a null metric; it is never dropped or zero-imputed.
This component screen cannot qualify a whole agent, refit, blend or release.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
import time
import zipfile

R4 = ('repaired-mvp-r1-dev/evaluator_r4.py','c08e9f0be13a708d67b3266518381d6f1be3b0f43c384ef6425634160d7e2783')
BASE_SHA = '8faf33cd81c0e864bcf338828c34447000111eda85bc719b8f43312d2babae9a'
ARCHIVE_SHA = '16120391716fe43b7f0ec2b36f35eaea7511a08cba4f4108da01cd81dea314d0'
ORDER = ['regression0-control','regression0-candidate','regression1-control','regression1-candidate',
    'regression2-control','regression2-candidate','classification42-control','classification42-candidate',
    'classification43-control','classification43-candidate']
FIXED = dict(engine='linear_text',feature_code='',params=dict(generic_features='none'))
FIXTURES = ('method-linear-recovery-dev/test_tabular_linear_contracts.py', '827fcc5bab907ddeb71248456425a4ba8c31f7ff306cceebee69aa802fb9af34')
FAILED_CAMPAIGN = ('meth02/campaign.json', 'fbc2844806b1ebda4912aa038f5b407931eff8c8a38c7fcf5f8722e11930e2f3')
FAILED_PROOF = ('meth02/terminal-root-closure.json', '220e7c93f56eaa4a9c2e09ce70aa3ba406d864686cc68520bf69eace4ed75361')
METH01_PROOF = ('meth01/terminal-root-closure.json', '2c67361da8f95875b35d124ac6c19d6cccba28c899f1e20dada88f3bec4ea283')
CUT_SHA = {('regression',0):'5c72db2a788262cfe52ba9c0c51a8b3a20e90875279e39cb96101c052cc40c84',
    ('regression',1):'e877869cb58f530a7bc73ad1e4cbc7d941fbb8bf6e7b42415f1a73608378fc8b',
    ('regression',2):'60ccdf913bfda8c1d7feaed8cd18c104d785caa2a40b8c5372f447d179a53fcc',
    ('classification',42):'e16a563499871e19227ba700425045bc14eb853615c420defd6277d0a963b2a0',
    ('classification',43):'d4d278eebfeebba90e3441854a4342def29ad57d704bdaff8dd226b66aa206df'}


def need(value, code):
    if not value: raise AssertionError(code)


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(2**20),b''): h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text('utf-8'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['work-root','manifest','manifest-sha256','plan','plan-sha256','self-sha256','output']:
        p.add_argument('--'+name,required=True)
    args=p.parse_args();need(__debug__,'nonoptimized_python_required');work=Path(args.work_root).resolve()
    def local(name):
        path=(work/name).resolve();need(not Path(name).is_absolute() and path.is_relative_to(work),'audit_reference_outside_work');return path
    root=work/'meth02b';output=local(args.output)
    need(output==root/'independent-audit.json' and not output.exists(),'exclusive_expected_component_output_required')
    need(digest(__file__)==args.self_sha256 and digest(local(args.manifest))==args.manifest_sha256
         and digest(local(args.plan))==args.plan_sha256,'explicit_component_audit_pin_failed')
    manifest,plan,campaign=load(local(args.manifest)),load(local(args.plan)),load(root/'campaign.json')
    need(manifest['schema']=='METH02-component-v1' and manifest['common_seconds']==10800
         and plan['schema']=='METH02-component-audit-v1' and plan['common_seconds']==10800
         and plan['ordered_jobs']==ORDER,'registered_component_contract_changed')
    need(plan['quality_gate_policy']==dict(regression='strict_RMSE_improvement_on_all_three_cuts',
        classification='both_MacroF1_improve_and_supported_class_and_ex_rarest_gates',supported_independent_groups_min=100,
        maximum_supported_class_drop=.01,class_drop_tolerance=1e-12,ex_rarest_gain_strictly_positive=True,
        failed_or_null_cut_gate=False,full_refit_or_promotion=False),'registered_component_quality_gates_changed')
    need(plan['verifier_source_sha256']==args.self_sha256 and plan['execution_manifest_sha256']==args.manifest_sha256
         and plan['manual_metric_verifier_path']==R4[0] and plan['manual_metric_verifier_sha256']==R4[1]
         and digest(local(R4[0]))==R4[1],'frozen_R4_manual_metric_source_required')
    need(campaign['manifest_sha256']==args.manifest_sha256 and campaign['verification_plan_sha256']==args.plan_sha256
         and campaign['start_unix']==plan['original_common_start_unix']
         and campaign['absolute_deadline_unix']==plan['original_absolute_deadline_unix']
         and abs(campaign['absolute_deadline_unix']-campaign['start_unix']-10800)<=1e-6
         and abs(campaign['common_deadline_monotonic']-campaign['start_monotonic']-10800)<=1e-6,
         'original_component_clock_binding_failed')
    need(campaign['status']=='verifying' and campaign['cleanup_confirmed'] is True
         and campaign['source_unchanged'] is True and campaign.get('finished_unix') is None,'closed_workers_before_live_parent_audit_required')
    original=load(local(FAILED_CAMPAIGN[0]));failed=load(local(FAILED_PROOF[0]))
    need(digest(local(FAILED_CAMPAIGN[0]))==FAILED_CAMPAIGN[1] and digest(local(FAILED_PROOF[0]))==FAILED_PROOF[1]
         and original['status']=='technical_failure' and original['workers']==[]
         and campaign['start_unix']==original['start_unix'] and campaign['start_monotonic']==original['start_monotonic']
         and campaign['absolute_deadline_unix']==original['absolute_deadline_unix']
         and campaign['common_deadline_monotonic']==original['common_deadline_monotonic']
         and failed['actual_exec_session'] is None and failed['actual_exec_exit_code_observed_by_root']==1
         and failed['cleanup_confirmed'] is True and failed['source_unchanged'] is True
         and manifest['original_failed_attempt']==campaign['original_failed_attempt']
         and campaign['original_failed_attempt']['original_status']=='FAILED_preserved',
         'recovery_must_inherit_actual_failed_original_common_clock')
    def clock():
        need(time.time()<campaign['absolute_deadline_unix'] and time.monotonic()<campaign['common_deadline_monotonic'],
             'original_component_audit_clock_exhausted')
    def frozen():
        clock()
        need(digest(__file__)==args.self_sha256 and digest(local(args.manifest))==args.manifest_sha256
             and digest(local(args.plan))==args.plan_sha256,'component_audit_authority_changed')
        for name,h in {**manifest['immutable_files'],**manifest['setup_deployment_sha256']}.items():
            need(digest(local(name))==h,'component_frozen_source_input_spec_job_split_changed');clock()
    frozen()
    need(manifest['immutable_files']['m4packet/manifest.json']==BASE_SHA,'exact_native_no_text_linear_base_required')
    base=load(local('m4packet/manifest.json'))
    need(manifest['archive_sha256']==ARCHIVE_SHA==base['archive_sha256'] and manifest['archive']==base['archive']
         and manifest['compiled_sha256']==base['compiled_sha256'] and digest(local(manifest['archive']))==ARCHIVE_SHA,
         'unchanged_native_no_text_linear_archive_required')
    with zipfile.ZipFile(local(manifest['archive'])) as z:
        need(len(z.namelist())==68 and len(set(z.namelist()))==68 and all(Path(n).name==n for n in z.namelist()),'flat_archive_inventory_changed')
        need({n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}==manifest['compiled_sha256'],'compiled_archive_changed')
    need(manifest['per_worker_parent_seconds']==600 and manifest['per_worker_child_seconds']==570
         and manifest['threads']==2 and manifest['BLAS_threads']==1 and manifest['worker_memory_gib']==1.5
         and manifest['whole_tree_memory_gib']==2 and manifest['refit'] is False,'registered_resource_contract_changed')
    jobs=manifest['jobs'];entries=campaign['workers']
    need([j['key'] for j in jobs]==ORDER and [e['key'] for e in entries]==ORDER,'complete_registered_order_required')
    gates={r['name']:r for r in campaign['gates']}
    need(set(gates)=={'source','exact','linear_contracts'},'source_exact_and_linear_contracts_required')
    for name in ['source','exact']:
        gate=gates[name]
        need(gate.get('evidence_mode')=='REUSED_T7_UNCHANGED_SOURCE_NOT_EXECUTED_AGAIN','reused_gate_evidence_scope_required')
        need(digest(local(gate['supervisor_path']))==gate['supervisor_sha256']
             and load(local(gate['supervisor_path']))==gate['supervisor'],'gate_inline_differs_from_saved_terminal')
        need(gate['supervisor']['status']=='ok' and gate['supervisor']['exit_code']==0
             and gate['supervisor']['cleanup_confirmed'] is True and digest(local(gate['result_path']))==gate['result_sha256'],
             'reused_gate_terminal_contract_failed')
    gate=gates['linear_contracts']
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
    old_campaign=load(local('t7/campaign.json'));old_root=load(local('m4packet/terminal-root-closure.json'))
    need(old_campaign['manifest_sha256']==BASE_SHA and old_root['actual_exec_session']==65008
         and old_root['actual_exec_exit_code_observed_by_root']==0 and old_root['cleanup_confirmed'] is True
         and old_root['source_unchanged'] is True,'actual_closed_T7_gate_lineage_required')
    source=load(local(gates['source']['result_path']));exact=load(local(gates['exact']['result_path']))
    need(source.get('passed') is True and source.get('source_unchanged') is True and source.get('fixture_cleanup_confirmed') is True
         and source['unique_checks_passed']==458 and source['unique_checks_skipped']==0
         and source['source_sha256']==manifest['compiled_sha256'],'source458_no_skip_required')
    registry={r['script']:r for r in source['checks']}
    need(set(registry)==set(manifest['registry']) and all(registry[n]['passed'] is True and registry[n]['observed_checks']==c
         and registry[n]['skipped_checks']==0 for n,c in manifest['registry'].items()),'reused_source_registry_coverage_changed')
    need(exact.get('passed') is True and exact.get('matches_current_source') is True and exact['sha256']==ARCHIVE_SHA
         and [r['script'] for r in exact['checks']]==['test_v2.py','test_resilience.py','smoke.py'],'reused_exact23_archive_coverage_changed')
    for row in exact['checks']:
        text=row.get('stdout','')+'\n'+row.get('stderr','')
        need(row['exit_code']==0 and not re.search(r'\bskipped\s*=\s*[1-9]',text),'reused_exact_failed_or_skipped')
        if row['script']=='smoke.py':
            cases=json.loads(row['stdout']);need(len(cases)==5 and all(v['status']=='passed' for v in cases),'reused_exact_smoke_incomplete')
        else:
            counts=re.findall(r'Ran (\d+) tests? in ',text);need(counts and int(counts[-1])==manifest['registry'][row['script']],'reused_exact_count_changed')
    # Bind every seal, saved terminal supervisor and exact ordered job before
    # importing NumPy/Pandas or parsing any pristine fitting/validation labels.
    cores={}
    for kind,meta in manifest['tasks'].items():
        original=next(v for v in base['tasks'] if v['kind']==kind)
        need(meta['files']==original['files'] and set(meta['files'])=={'task.md','train.csv','test.csv','data_dictionary.csv','sample_submission.csv'},
             'five_pristine_component_inputs_required')
        for name,h in meta['files'].items():
            need(digest(root/meta['code']/name)==digest(local(original['source'])/name)==h,'direct_pristine_source_and_copy_binding_failed')
            clock()
    for job,entry in zip(jobs,entries):
        kind,arm=job['kind'],job['arm'];meta=manifest['tasks'][kind]
        need(arm in {'control','candidate'} and job['key']==f"{kind}{job['cut']}-{arm}",'component_key_arm_cut_mismatch')
        original=next(v for v in base['tasks'] if v['kind']==kind)
        need(meta['files']==original['files'] and meta['control_recipe']==original['control_recipe'],'protected_pristine_or_control_reference_changed')
        control=load(local(meta['control_recipe']['path']))['components'][0]
        need(meta['component_control']==control,'exact_first_SINGLE_control_required')
        candidate=copy.deepcopy(FIXED)
        if kind=='classification':candidate['params'].update(text_classifier='logistic',text_C=1,class_weight_power=.5)
        need(job['recipe']==(control if arm=='control' else candidate),'fixed_component_recipe_changed')
        expected_cut=CUT_SHA[(kind,job['cut'])]
        original_split=f"alfa-hack-automl/test-runs/2e/fe-{kind}/control_historical/seed-{job['cut']}/split.npz"
        need(job['split_sha256']==expected_cut==manifest['immutable_files'][original_split]
             and digest(local(original_split))==expected_cut,'exact_existing_ordered_cut_required')
        need(digest(local(job['job_path']))==job['job_sha256'] and digest(local(job['split_path']))==job['split_sha256'],'frozen_component_job_or_split_changed')
        actual_job=load(local(job['job_path']));spec=load(local(meta['spec_path']))
        need(actual_job==dict(spec=spec,recipe=job['recipe'],output_dir=str(local(job['output_dir'])),
             split_path=str(local(job['split_path'])),threads=2,full_fit=False),'exact_worker_dispatch_contract_changed')
        need(digest(local(meta['spec_path']))==meta['spec_sha256'],'frozen_rebound_spec_changed')
        need(digest(local(entry['supervisor_path']))==entry['supervisor_sha256'],'closed_component_supervisor_changed')
        terminal=load(local(entry['supervisor_path']))
        for key in ['status','exit_code','cleanup_confirmed','solver_budget_seconds','parent_cap_seconds','child_cap_seconds',
                    'owned_root','owned_process_identities','cleanup_observation','kind','first_failure','error_history']:
            need(terminal.get(key)==entry.get(key),'inline_component_differs_from_saved_supervisor:'+key)
        need(terminal['cleanup_confirmed'] is True and terminal['cleanup_observation']['unresolved']==[]
             and terminal['parent_cap_seconds']==600 and terminal['child_cap_seconds']==570
             and terminal['solver_budget_seconds'] is None and 0<=entry['seconds_including_seal']<600,
             'component_closed_parent_contract_failed')
        local_oom=(terminal.get('status')=='technical_failure' and terminal.get('error_history')
            and all(r.get('code')=='worker_subtree_memory_limit' for r in terminal['error_history']))
        need(terminal['status'] in {'ok','child_failed','timeout'} or local_oom,'systemic_component_failure_cannot_be_scored')
        need(digest(local(entry['seal']['path']))==entry['seal']['sha256'],'component_prelabel_seal_changed')
        seal=load(local(entry['seal']['path']));need(seal['key']==job['key'] and seal['cleanup_confirmed'] is True
             and seal['source_unchanged'] is True and seal['sealed_before_independent_label_scoring'] is True,'prelabel_seal_contract_failed')
        actual={}
        for parent,dirs,files in os.walk(local(job['output_dir'])):
            need(not any((Path(parent)/n).is_symlink() for n in [*dirs,*files]),'sealed_component_symlink')
            for name in files:
                need(not name.endswith(('.tmp','.pending')),'unfinished_component_core')
                path=Path(parent)/name;actual[path.relative_to(work).as_posix()]=digest(path);clock()
        need(actual==seal['files_sha256'],'sealed_component_inventory_or_bytes_changed');cores[job['key']]=actual
    for a,b in zip(jobs[::2],jobs[1::2]):
        need(a['kind']==b['kind'] and a['cut']==b['cut'] and a['split_path']==b['split_path']
             and a['split_sha256']==b['split_sha256'],'paired_fitting_validation_rows_must_be_identical')
    spec=importlib.util.spec_from_file_location('_frozen_R4_component_library',local(R4[0]))
    r4=importlib.util.module_from_spec(spec);spec.loader.exec_module(r4)
    verifiers={}
    for kind,meta in manifest['tasks'].items():
        directory=root/meta['code'];specification=load(local(meta['spec_path']))
        source_spec=load(local('t7/'+meta['code']+'/automl_runs/repair4/task_spec.json'))
        expected=copy.deepcopy(source_spec);expected.update(root=str(directory),task_path=str(directory/'task.md'),
            paths={key:str(directory/Path(value).name) for key,value in source_spec['paths'].items()})
        need(specification==expected,'rebound_spec_changed_beyond_paths')
        train,test,sample=[r4.pd.read_csv(directory/name) for name in ['train.csv','test.csv','sample_submission.csv']]
        verifiers[kind]=r4.TaskVerifier(directory,dict(spec=specification,experiments=[],confirmations=[]),train,test,sample)
    rows=[]
    for job,entry in zip(jobs,entries):
        clock();row=dict(key=job['key'],kind=job['kind'],cut=job['cut'],arm=job['arm'],status=entry['status'],
            exit_code=entry.get('exit_code'),metric=None,diagnostics=None,integrity_passed=None,
            failed_metric_zero_imputed=False,artifact_hashes=cores[job['key']])
        if entry['status']!='ok' or entry.get('exit_code')!=0:
            row.update(measurement_status='worker_failure_preserved_null',failure=entry.get('first_failure'),integrity_passed=True)
        else:
            try:
                stored=load(local(job['output_dir'])/'result.json')
                record=dict(stored,output_dir=str(local(job['output_dir'])))
                verifier=verifiers[job['kind']]
                checked=verifier.verify(record,local(job['split_path']),job['key'],False,job['recipe'])
                diagnostic=r4.diagnostics(verifier,record,local(job['split_path']),job['key'])
                need(math.isfinite(checked['value']),'nonfinite_component_metric')
                row.update(metric=checked['value'],diagnostics=diagnostic,integrity_passed=True,measurement_status='independent_component_metric')
            except Exception as exc:
                trace=exc.__traceback__
                while trace is not None and trace.tb_next is not None:trace=trace.tb_next
                reason=str(exc)
                row.update(integrity_passed=False,measurement_status='saved_artifact_unqualified',exception_type=type(exc).__name__,
                    contract_reason=reason if isinstance(exc,AssertionError) and re.fullmatch('[A-Za-z0-9_:+.-]{1,200}',reason) else None,
                    errno=getattr(exc,'errno',None),winerror=getattr(exc,'winerror',None),
                    failure_source_basename=Path(trace.tb_frame.f_code.co_filename).name if trace else None,
                    failure_source_line=trace.tb_lineno if trace else None)
        rows.append(row)
    all_succeeded=all(r['status']=='ok' and r['exit_code']==0 and r['integrity_passed'] is True for r in rows)
    integrity=all(r['integrity_passed'] is True for r in rows)
    comparisons=[]
    for a,b in zip(rows[::2],rows[1::2]):
        complete=a['metric'] is not None and b['metric'] is not None
        comparisons.append(dict(kind=a['kind'],cut=a['cut'],control=a['metric'],candidate=b['metric'],
            delta_candidate_minus_control=b['metric']-a['metric'] if complete else None,
            complete=complete,greater_is_better=a['kind']=='classification'))
    quality={}
    for kind,count in [('regression',3),('classification',2)]:
        group=[v for v in comparisons if v['kind']==kind]
        complete=len(group)==count and all(v['complete'] for v in group)
        quality[kind]=dict(metric='rmse' if kind=='regression' else 'macro_f1',required_cuts=count,
            complete=complete,control_mean=sum(v['control'] for v in group)/count if complete else None,
            candidate_mean=sum(v['candidate'] for v in group)/count if complete else None)
    regression_gates=[dict(cut=v['cut'],strict_RMSE_improvement=v['complete'] and v['delta_candidate_minus_control']<0)
        for v in comparisons if v['kind']=='regression']
    class_rows={r['key']:r for r in rows if r['kind']=='classification'}
    class_complete=all(class_rows[f'classification{cut}-{arm}']['diagnostics'] is not None
        for cut in [42,43] for arm in ['control','candidate'])
    class_gates=dict(cuts=[],each_cut_MacroF1_improves=False,each_cut_supported_class_and_ex_rarest_gates_passed=False)
    if class_complete:
        aliases={'primary':42,'confirmation':43}
        candidate={phase:class_rows[f'classification{cut}-candidate']['diagnostics'] for phase,cut in aliases.items()}
        control={phase:class_rows[f'classification{cut}-control']['diagnostics'] for phase,cut in aliases.items()}
        matched=r4.matched_control_comparison(candidate,control,'classification')
        class_gates.update(cuts=[dict(row,cut_alias='group_seed_'+str(aliases[row['phase']]),
            cut=aliases[row['phase']]) for row in matched['cuts']],
            each_cut_MacroF1_improves=matched['each_cut_primary_gate_passed'],
            each_cut_supported_class_and_ex_rarest_gates_passed=matched['class_each_cut_gate_passed'])
    else:
        class_gates['cuts']=[dict(cut=cut,cut_alias='group_seed_'+str(cut),primary_improves=False,
            all_class_gates_passed=False,reason='missing_or_unqualified_control_or_candidate_cut') for cut in [42,43]]
    regression_pass=len(regression_gates)==3 and all(v['strict_RMSE_improvement'] for v in regression_gates)
    class_pass=class_gates['each_cut_MacroF1_improves'] and class_gates['each_cut_supported_class_and_ex_rarest_gates_passed']
    decisions=dict(regression_all_three_strict_RMSE_improvement=regression_pass,regression_cuts=regression_gates,
        classification=class_gates,component_quality_gates_passed=regression_pass and class_pass,
        negative_standalone_artifacts_retained_for_separate_METH03=True,full_refit_or_promotion=False,
        scope='Registered standalone component gates only; class primary/confirmation names are aliases for group seeds42/43, not whole-agent phases')
    frozen()
    linear_gate=gates['linear_contracts']
    need(digest(local(linear_gate['result_path']))==linear_gate['result_sha256']
         and digest(local(linear_gate['supervisor_path']))==linear_gate['supervisor_sha256'],
         'late_linear_tool_contract_receipt_changed')
    for job,entry in zip(jobs,entries):
        need(digest(local(entry['supervisor_path']))==entry['supervisor_sha256']
             and digest(local(entry['seal']['path']))==entry['seal']['sha256'],'late_component_receipt_changed')
        for name,h in cores[job['key']].items():need(digest(local(name))==h,'late_component_core_changed');clock()
    clock()
    result=dict(status='component_artifacts_verified_pending_parent_terminal' if integrity else 'component_artifacts_partial_unqualified_pending_parent_terminal',
        rows=rows,comparisons=comparisons,quality_metric=quality,all_workers_succeeded=all_succeeded,
        component_quality_gates_passed=decisions['component_quality_gates_passed'],registered_component_decisions=decisions,
        artifact_integrity_checks_passed=integrity,audit_within_original_common_clock=True,
        campaign_terminal_confirmed=False,parent_exec_terminal_qualification_required=True,actual_common_deadline_satisfied=None,
        manifest_sha256=args.manifest_sha256,verification_plan_sha256=args.plan_sha256,campaign_sha256=digest(root/'campaign.json'),
        manual_metric_source_sha256=R4[1],source_and_core_rechecked=True,
        failed_metrics_zero_imputed=False,new_model_fits=0,API_calls=0,tests_run=0,
        full_refit=False,promotion=False,submit=False,official_score=None,
        scope='Fixed component screen only on reused public forward/group cuts; weak standalone results retained for future separately declared diversity analysis. Not whole-agent or blind/private gain.')
    with output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    clock();print(json.dumps({k:result[k] for k in ['status','all_workers_succeeded','artifact_integrity_checks_passed']}))


if __name__=='__main__':main()
