"""KERN01 saved component artifacts: frozen R4.TaskVerifier/diagnostics, no fits.

All fifteen closed cores are sealed and rehashed BEFORE pristine labels are parsed.
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
KERN_BASE='kern-stage0-packet/manifest.json'
KERN_MANIFEST_SHA='8e9fb3c8e428df7e372dc53d0e3b11bc4c435bdf13c89426ebe5b0e45ebffa98'
ARCHIVE_SHA='ca8a0898af84a4ddb8039343f94edc73aa7360005f215125907a34427a3c6d5c'
ARMS=['strong','linear','rbf']
PROFILES={'linear':'tabular_linear_bounded_v1','rbf':'tabular_rbf128_invdim_v1'}
ORDER=[f'{kind}{cut}-{arm}' for kind,cut in [('regression',0),('regression',1),('regression',2),
    ('classification',42),('classification',43)] for arm in ARMS]
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


def representation_receipt(r4,verifier,record,job):
    profile=PROFILES[job['arm']];info=record.get('representation')
    need(isinstance(info,dict),'missing_fixed_representation_receipt')
    tr,va=r4.split(Path(job['_absolute_split']),len(verifier.train))
    ordered=r4.np.ascontiguousarray(tr,dtype=r4.np.int64)
    rowsha=hashlib.sha256(str(ordered.dtype).encode()+str(ordered.shape).encode()+ordered.tobytes()).hexdigest()
    numeric=[];category=[]
    import numbers
    for name in verifier.spec['features']:
        values=verifier.train[name].iloc[tr].dropna()
        is_numeric=all(isinstance(v,(numbers.Real,r4.np.number,bool)) for v in values)
        (numeric if is_numeric else category).append(name)
    prepared=info.get('prepared_columns');represented=info.get('representation_columns')
    need(type(prepared) is int and 1<=prepared<=4096 and 1<=len(numeric)+len(category)<=64,
         'bounded_prepared_schema_required')
    n=len(tr);width=len(numeric)+64*len(category);dimension=128 if job['arm']=='rbf' else width
    upper={'numeric_dense':n*len(numeric)*8,'category_codes':n*len(category)*8,
        'prepared_CSR_upper_bound':n*(len(numeric)+len(category))*12+(n+1)*4,
        'representation_dense':n*dimension*8 if job['arm']=='rbf' else 0,
        'random_projection':width*dimension*8 if job['arm']=='rbf' else 0}
    estimate=n*(len(numeric)*8*3+len(category)*16*3+(len(numeric)+len(category))*16*2)
    estimate+=n*dimension*8*2 if job['arm']=='rbf' else n*(len(numeric)+len(category))*16
    estimate+=upper['random_projection']+64*dimension*8
    budget=dict(fitting_rows=n,numeric_columns=len(numeric),categorical_columns=len(category),
        maximum_encoded_columns=width,estimated_live_matrix_bytes=estimate,matrix_limit_bytes=128000000,
        matrix_limit_scope='each_logical_matrix',matrix_bytes_upper_bounds=upper,process_RSS_requires_external_guard=True)
    need(1<=n<=200000 and width<=4096 and max(upper.values())<=128000000
         and info.get('budget')==budget,'fixed_representation_budget_or_fitting_schema_mismatch')
    need(info.get('representation_profile')==profile and info.get('fitting_rows')==n
         and info.get('fitting_row_order_sha256')==rowsha and info.get('seed')==42
         and info.get('numeric_columns')==len(numeric) and info.get('categorical_columns')==len(category)
         and info.get('threads')==2 and info.get('calibration')=='disabled' and info.get('log_target') is False
         and info.get('preprocessing_scope')=='fitting_rows_only' and info.get('representation_scope')=='fitting_rows_only'
         and isinstance(info.get('fitting_state_sha256'),str) and re.fullmatch('[0-9a-f]{64}',info['fitting_state_sha256']),
         'fixed_representation_scope_or_order_mismatch')
    for key in ['actual_prepared_matrix_bytes','actual_representation_matrix_bytes','projection_bytes']:
        need(type(info.get(key)) is int and 0<=info[key]<=128000000,'representation_matrix_byte_cap_mismatch')
    need(info['actual_prepared_matrix_bytes']>0 and info['actual_representation_matrix_bytes']>0,'empty_prepared_matrix')
    if job['arm']=='rbf':
        need(represented==128 and info.get('gamma')==1./prepared
             and info['actual_representation_matrix_bytes']==n*128*8
             and info['projection_bytes']==prepared*128*8+128*8,'fixed_RBF128_gamma_or_projection_mismatch')
    else:
        need(represented==prepared and info.get('gamma') is None and info['projection_bytes']==0
             and info['actual_representation_matrix_bytes']==info['actual_prepared_matrix_bytes'],
             'matched_identity_representation_mismatch')
    expected_estimator=dict(family='Ridge',alpha=10.,solver='lsqr') if job['kind']=='regression' else dict(
        family='LogisticRegression',C=1.,solver='lbfgs',class_weight_power=.5)
    need(info.get('estimator')==expected_estimator and info.get('classes')==list(verifier.spec.get('classes') or [])
         and record.get('fit_iterations')==1,'fixed_linear_head_class_order_or_fit_count_mismatch')
    return dict(verified=True,profile_id=profile,receipt=info,independent_order_and_schema_verified=True,
        no_auditor_preprocessor_refit=True,simultaneous_RSS_not_certified_by_single_matrix_cap=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['work-root','manifest','manifest-sha256','plan','plan-sha256','self-sha256','output']:
        p.add_argument('--'+name,required=True)
    args=p.parse_args();need(__debug__,'nonoptimized_python_required');work=Path(args.work_root).resolve()
    def local(name):
        path=(work/name).resolve();need(not Path(name).is_absolute() and path.is_relative_to(work),'audit_reference_outside_work');return path
    root=work/'kern01';output=local(args.output)
    need(output==root/'independent-audit.json' and not output.exists(),'exclusive_expected_component_output_required')
    need(digest(__file__)==args.self_sha256 and digest(local(args.manifest))==args.manifest_sha256
         and digest(local(args.plan))==args.plan_sha256,'explicit_component_audit_pin_failed')
    manifest,plan,campaign=load(local(args.manifest)),load(local(args.plan)),load(root/'campaign.json')
    need(manifest['schema']=='KERN01-component-v1' and manifest['common_seconds']==10800
         and plan['schema']=='KERN01-component-audit-v1' and plan['common_seconds']==10800
         and plan['ordered_jobs']==ORDER,'registered_component_contract_changed')
    need(plan['arms']==ARMS and manifest['arms']==ARMS and plan['profiles']==PROFILES and manifest['profiles']==PROFILES
         and plan['quality_gate_policy']==dict(
             regression='each_new_arm_strict_RMSE_improvement_all_three_cuts_vs_fresh_strong',
             classification='each_new_arm_both_MacroF1_improve_and_supported_class_and_ex_rarest_gates',
             supported_independent_groups_min=100,maximum_supported_class_drop=.01,class_drop_tolerance=1e-12,
             ex_rarest_gain_strictly_positive=True,failed_or_null_cut_gate=False,full_refit_or_promotion=False,
             matched_linear_contrast='RBF_minus_matchedlinear_separately_not_strong_control'),
         'registered_component_quality_gates_changed')
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
    need(manifest['immutable_files']['m4packet/manifest.json']==BASE_SHA,'pristine_metadata_base_required')
    base=load(local('m4packet/manifest.json'))
    prepared_ref=manifest['kernel_prepared_manifest']
    need(prepared_ref['path']==KERN_BASE and digest(local(KERN_BASE))==prepared_ref['sha256']==KERN_MANIFEST_SHA,
         'exact_qualified_KERN_source_manifest_required')
    kernel_base=load(local(KERN_BASE));archive_sha=kernel_base['archive_sha256']
    need(archive_sha==ARCHIVE_SHA and kernel_base['source_root']=='kern00' and kernel_base['source_expected_checks']==483
         and kernel_base['self_sha256']=='f749889a9a6eb29859169468c352345e05d41aa357579df132a1ff9cfb7520a8'
         and kernel_base['base_archive_sha256']=='52627ac5b9da5ee47d8d40951f84edf9b9dede28cca4b4f90504be6bb4e672b8'
         and kernel_base['overlay_handoff_sha256']=='3794521c315a93900d22df54472299fa6b71d2a36cda0e6b743784c31737fc55'
         and kernel_base['exact_flat_kernel_checks']==12 and kernel_base['source_skipped_expected']==0,
         'qualified_kernel_factor_required')
    need(len(kernel_base['source_files_sha256'])==694,'full_kernel_source_inventory_required')
    for name,h in kernel_base['source_files_sha256'].items():
        need(manifest['immutable_files'].get('kern00/'+name)==h and digest(local('kern00/'+name))==h,
             'direct_qualified_kernel_source_binding_failed');clock()
    need(manifest['archive_sha256']==archive_sha and manifest['archive']==kernel_base['archive']
         and manifest['compiled_sha256']==kernel_base['compiled_sha256'] and digest(local(manifest['archive']))==archive_sha,
         'unchanged_qualified_KERN_archive_required')
    with zipfile.ZipFile(local(manifest['archive'])) as z:
        need(len(z.namelist())==len(set(z.namelist()))==70 and all(Path(n).name==n for n in z.namelist()),'flat_archive_inventory_changed')
        need({n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}==manifest['compiled_sha256'],'compiled_archive_changed')
    need(manifest['per_worker_parent_seconds']==480 and manifest['per_worker_child_seconds']==450
         and manifest['threads']==2 and manifest['BLAS_threads']==1 and manifest['worker_memory_gib']==1.5
         and manifest['whole_tree_memory_gib']==2 and manifest['refit'] is False,'registered_resource_contract_changed')
    jobs=manifest['jobs'];entries=campaign['workers']
    need([j['key'] for j in jobs]==ORDER and [e['key'] for e in entries]==ORDER,'complete_registered_order_required')
    rootref=manifest['kernel00_predecessor']
    need(rootref==dict(path='kern0/terminal-root-closure.json',sha256=rootref['sha256'],actual_exec_session=rootref['actual_exec_session'],actual_exec_exit_code_observed_by_root=0) and type(rootref['actual_exec_session']) is int and rootref['actual_exec_session']==19035
         and digest(local(rootref['path']))==rootref['sha256'],'actual_KERN00_terminal_binding_required')
    prior=load(local(rootref['path']));old_campaign=load(local('kern0/campaign.json'))
    need(prior['original_common_seconds']==900 and prior['source_checks']==483 and prior['exact_default_repeated']==23 and prior['exact_flat_same_KERN_contracts']==12
         and prior['technical_procedure_passed'] is True and prior['cleanup_confirmed'] is True and prior['source_unchanged'] is True
         and prior['actual_exec_session']==rootref['actual_exec_session'] and prior['actual_exec_exit_code_observed_by_root']==0
         and prior['prepared_manifest_sha256']==prepared_ref['sha256']
         and old_campaign['prepared_manifest_sha256']==prepared_ref['sha256']
         and old_campaign['start_unix']==prior['original_start_unix']
         and old_campaign['absolute_deadline_unix']==prior['original_deadline_unix']
         and old_campaign['elapsed_common_seconds']==prior['raw_parent_elapsed_seconds'],
         'actual_full_KERN00_readiness_lineage_required')
    gates={r['name']:r for r in campaign['gates']}
    need(set(gates)=={'source','exact-default','exact-optin'},'full_reused_KERN00_gate_inventory_required')
    for name,gate in gates.items():
        expected=next(g for g in old_campaign['gates'] if g['name']==name)
        need(gate['evidence_mode']=='REUSED_KERN00_UNCHANGED_SOURCE_NOT_EXECUTED_AGAIN'
             and gate['checks']==expected['checks'] and gate['result_sha256']==expected['sha256']
             and digest(local(gate['result_path']))==gate['result_sha256']
             and digest(local(gate['supervisor_path']))==gate['supervisor_sha256']
             and load(local(gate['supervisor_path']))==gate['supervisor'],'reused_KERN00_gate_ref_changed')
        need(gate['supervisor']['status']=='ok' and gate['supervisor']['exit_code']==0
             and gate['supervisor']['cleanup_confirmed'] is True,'reused_KERN00_supervisor_not_terminal_clean')
    source=load(local(gates['source']['result_path']));exact=load(local(gates['exact-default']['result_path']))
    need(source['passed'] is True and source['source_unchanged'] is True and source['fixture_cleanup_confirmed'] is True
         and source['unique_checks_passed']==483 and source['unique_checks_skipped']==0
         and source['source_sha256']==manifest['compiled_sha256'],'actual_source483_no_skip_required')
    registry={r['script']:r for r in source['checks']}
    need(set(registry)==set(manifest['registry']) and sum(manifest['registry'].values())==483
         and all(registry[n]['passed'] is True and registry[n]['observed_checks']==count and registry[n]['skipped_checks']==0
                 for n,count in manifest['registry'].items()),'reused_source_registry_incomplete')
    need(exact['passed'] is True and exact['matches_current_source'] is True and exact['sha256']==archive_sha,
         'actual_exact_archive_readiness_required')
    counts={'test_v2.py':11,'test_resilience.py':7,'smoke.py':5}
    need([r['script'] for r in exact['checks']]==list(counts),'actual_exact23_inventory_required')
    for row in exact['checks']:
        text=row.get('stdout','')+'\n'+row.get('stderr','')
        need(row['exit_code']==0 and not re.search(r'\bskipped\s*=\s*[1-9]',text),'actual_exact_failed_or_skipped')
        observed=re.findall(r'Ran (\d+) tests? in ',text)
        if row['script']=='smoke.py':need(len(json.loads(row['stdout']))==5,'actual_exact_smoke5_required')
        else:need(observed and int(observed[-1])==counts[row['script']],'actual_exact_count_changed')
    text=local(gates['exact-optin']['result_path']).read_text('utf-8')
    need(gates['exact-optin']['checks']==12 and re.findall(r'Ran (\d+) tests? in ',text)==['12']
         and '\nOK\n' in text and 'skipped=' not in text,'actual_flat_KERN12_required')
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
        need(arm in set(ARMS) and job['key']==f"{kind}{job['cut']}-{arm}",'component_key_arm_cut_mismatch')
        original=next(v for v in base['tasks'] if v['kind']==kind)
        need(meta['files']==original['files'] and meta['control_recipe']==original['control_recipe'],'protected_pristine_or_control_reference_changed')
        control=load(local(meta['control_recipe']['path']))['components'][0]
        need(meta['component_control']==control,'exact_first_SINGLE_control_required')
        candidate=dict(engine='linear_text',feature_code='',params=dict(representation_profile=PROFILES[arm],generic_features='none')) if arm!='strong' else None
        need(job['recipe']==(control if arm=='strong' else candidate),'fixed_component_recipe_changed')
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
             and terminal['parent_cap_seconds']==480 and terminal['child_cap_seconds']==450
             and terminal['solver_budget_seconds'] is None and 0<=entry['seconds_including_seal']<480,
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
    for offset in range(0,len(jobs),3):
        group=jobs[offset:offset+3]
        need([j['arm'] for j in group]==ARMS and len({(j['kind'],j['cut'],j['split_path'],j['split_sha256']) for j in group})==1,
             'three_arms_fitting_validation_rows_must_be_identical')
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
                representation=representation_receipt(r4,verifier,record,dict(job,_absolute_split=str(local(job['split_path'])))) if job['arm']!='strong' else None
                need(math.isfinite(checked['value']),'nonfinite_component_metric')
                row.update(metric=checked['value'],diagnostics=diagnostic,representation_verification=representation,integrity_passed=True,measurement_status='independent_component_metric')
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
    lookup={r['key']:r for r in rows};comparisons=[];quality={};decisions={}
    pairs=[('linear','strong'),('rbf','strong'),('rbf','linear')]
    for arm,baseline in pairs:
        tag=arm+'_vs_'+baseline;comp=[];perkind={}
        for kind,cut in [('regression',0),('regression',1),('regression',2),('classification',42),('classification',43)]:
            a=lookup[f'{kind}{cut}-{baseline}'];b=lookup[f'{kind}{cut}-{arm}'];complete=a['metric'] is not None and b['metric'] is not None
            comp.append(dict(kind=kind,cut=cut,baseline_arm=baseline,arm=arm,baseline=a['metric'],candidate=b['metric'],
                delta_candidate_minus_baseline=b['metric']-a['metric'] if complete else None,complete=complete,
                greater_is_better=kind=='classification'))
        for kind,count in [('regression',3),('classification',2)]:
            group=[v for v in comp if v['kind']==kind];complete=len(group)==count and all(v['complete'] for v in group)
            perkind[kind]=dict(metric='rmse' if kind=='regression' else 'macro_f1',required_cuts=count,complete=complete,
                baseline_mean=sum(v['baseline'] for v in group)/count if complete else None,
                candidate_mean=sum(v['candidate'] for v in group)/count if complete else None)
        reg=[dict(cut=v['cut'],strict_RMSE_improvement=v['complete'] and v['delta_candidate_minus_baseline']<0)
            for v in comp if v['kind']=='regression']
        cls_complete=all(lookup[f'classification{cut}-{a}']['diagnostics'] is not None for cut in [42,43] for a in [arm,baseline])
        cls=dict(cuts=[],each_cut_MacroF1_improves=False,each_cut_supported_class_and_ex_rarest_gates_passed=False)
        if cls_complete:
            aliases={'primary':42,'confirmation':43}
            candidate={phase:lookup[f'classification{cut}-{arm}']['diagnostics'] for phase,cut in aliases.items()}
            control={phase:lookup[f'classification{cut}-{baseline}']['diagnostics'] for phase,cut in aliases.items()}
            matched=r4.matched_control_comparison(candidate,control,'classification')
            cls.update(cuts=[dict(v,cut=aliases[v['phase']],cut_alias='group_seed_'+str(aliases[v['phase']])) for v in matched['cuts']],
                each_cut_MacroF1_improves=matched['each_cut_primary_gate_passed'],
                each_cut_supported_class_and_ex_rarest_gates_passed=matched['class_each_cut_gate_passed'])
        else:cls['cuts']=[dict(cut=cut,primary_improves=False,all_class_gates_passed=False,reason='missing_or_unqualified_arm') for cut in [42,43]]
        decisions[tag]=dict(regression_all_three_strict_RMSE_improvement=len(reg)==3 and all(v['strict_RMSE_improvement'] for v in reg),
            regression_cuts=reg,classification=cls,classification_all_gates_passed=cls['each_cut_MacroF1_improves'] and cls['each_cut_supported_class_and_ex_rarest_gates_passed'],
            reference_scope='fresh_strong_SINGLE_package' if baseline=='strong' else 'matched_preparation_representation_contrast',
            qualified_for_promotion=False)
        comparisons.append(dict(contrast=tag,cuts=comp));quality[tag]=perkind
    gatespassed=all(decisions[tag]['regression_all_three_strict_RMSE_improvement'] and decisions[tag]['classification_all_gates_passed']
        for tag in ['linear_vs_strong','rbf_vs_strong']) and all_succeeded and integrity
    decisions=dict(contrasts=decisions,component_quality_gates_passed=gatespassed,full_refit_or_promotion=False,
        scope='Fixed component comparisons; strong-vs-new is whole recipe package, RBF-vs-linear isolates representation; reused public cuts, not wholeagent or unseen researcher holdout.')
    frozen()
    for job,entry in zip(jobs,entries):
        need(digest(local(entry['supervisor_path']))==entry['supervisor_sha256']
             and digest(local(entry['seal']['path']))==entry['seal']['sha256'],'late_component_receipt_changed')
        for name,h in cores[job['key']].items():need(digest(local(name))==h,'late_component_core_changed');clock()
    clock()
    result=dict(status='component_artifacts_verified_pending_parent_terminal' if integrity else 'component_artifacts_partial_unqualified_pending_parent_terminal',
        rows=rows,comparisons=comparisons,quality_metric=quality,all_workers_succeeded=all_succeeded,
        component_quality_gates_passed=gatespassed,registered_component_decisions=decisions,
        artifact_integrity_checks_passed=integrity,audit_within_original_common_clock=True,
        campaign_terminal_confirmed=False,parent_exec_terminal_qualification_required=True,actual_common_deadline_satisfied=None,
        manifest_sha256=args.manifest_sha256,verification_plan_sha256=args.plan_sha256,campaign_sha256=digest(root/'campaign.json'),
        manual_metric_source_sha256=R4[1],source_and_core_rechecked=True,
        failed_metrics_zero_imputed=False,new_model_fits=0,API_calls=0,tests_run=0,
        full_refit=False,promotion=False,submit=False,official_score=None,
        scope='Fixed component screen only on reused public forward/group cuts; all fixed arm results retained, including negative or null. Not whole-agent or blind/private gain.')
    with output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    clock();print(json.dumps({k:result[k] for k in ['status','all_workers_succeeded','artifact_integrity_checks_passed']}))


if __name__=='__main__':main()
