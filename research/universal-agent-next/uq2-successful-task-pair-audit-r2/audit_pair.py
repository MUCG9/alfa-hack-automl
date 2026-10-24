"""Separate preregistered UQ2 complete-task-pair audit. No fits, API or promotion.
ALL4 closed byte seals precede selected-pair numerical/R4 imports and truth reads.
"""
from pathlib import Path
import argparse,copy,csv,hashlib,importlib.util,json,math,os,re,sys,time,zipfile
R4='repaired-mvp-r1-dev/evaluator_r4.py'
R4_SHA='c08e9f0be13a708d67b3266518381d6f1be3b0f43c384ef6425634160d7e2783'
ORDER=[('A','regression','r'),('B','regression','r'),('A','classification','c'),('B','classification','c')]
CAPS={'regression':dict(parent=900,child=870,solver=810,hpo=300),'classification':dict(parent=3600,child=3570,solver=3510,hpo=900)}

def need(value,code):
    if not value:raise AssertionError(code)


def load(path):return json.loads(Path(path).read_text('utf-8'))


DIGEST_CHECKPOINT=lambda:None

def digest(path):
    DIGEST_CHECKPOINT()
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(2**20),b''):DIGEST_CHECKPOINT();h.update(block)
    DIGEST_CHECKPOINT();return h.hexdigest()


def hpo_counts(hpo):
    trials=hpo['trials'];need(len(trials)==8 and [v['number'] for v in trials]==list(range(8)),'all_eight_actual_HPO_attempts_required')
    phases={k:dict(attempted=0,completed=0,failed=0) for k in ['anchor','startup','guided','random']}
    for v in trials:
        need(type(v.get('objective_valid')) is bool,'trial_objective_valid_bool_required')
        p=phases[v['sampling_phase']];p['attempted']+=1;p['completed' if v['objective_valid'] else 'failed']+=1
        if not v['objective_valid']:need(v.get('value') is None,'failed_HPO_value_must_be_null')
    done=sum(v['completed'] for v in phases.values())
    expected=dict(planned_trials=8,attempted_trials=8,completed_trials=done,failed_trials=8-done,
        duplicate_trials=sum(v['status']=='duplicate' for v in trials),unattempted_trials=0,
        sampler_startup_trials=3,phase_counts=phases,guided_attempts=phases['guided']['attempted'],
        guided_successful_trials=phases['guided']['completed'])
    need(all(hpo.get(k)==v for k,v in expected.items()),'independently_replayed_HPO_accounting_mismatch')
    return expected


def loss_telemetry(record,recipe,verifier,r4,partition):
    """Same fixed LOSS backend proof extended only to full-refit fitting rows."""
    profile=recipe.get('params',{}).get('loss_profile_id')
    catalog={'lgbm_l2_v1':('regression',None),'lgbm_l1_v1':('regression_l1',None),'lgbm_huber_a09_v1':('huber',.9)}
    need(profile in catalog and verifier.spec['kind']=='regression','known_regression_loss_only')
    objective,alpha=catalog[profile];full=record.get('full_fit') is True
    tr,_=r4.split(partition,len(verifier.train))
    if full:parents=[r4.np.arange(len(verifier.train),dtype=r4.np.int64)];scopes=['full_refit'];stops=[False]
    else:
        need(record.get('early_stopping_source')=='inner_training_holdout' and record.get('inner_split_error') is None,'nested_loss_stopping_required')
        spec=verifier.spec;column=spec['time_column'];need(spec.get('validation_strategy')=='time'
            and (spec.get('time_candidate') or {}).get('split_mode')=='period','same_period_scope_required')
        values=r4.pd.to_numeric(verifier.train[column],errors='raise').to_numpy(dtype=float);local=values[tr]
        latest=r4.np.unique(local)[-1];inner=tr[r4.np.flatnonzero(local<latest)]
        parents=[inner,tr];scopes=['inner_fitting','outer_fitting'];stops=[True,False]
    rows=record.get('data_policy_runs');need(type(rows) is list and len(rows)==len(parents),'actual_loss_fit_receipts_required')
    proofs=[]
    for index,(row,parent,scope,stopping) in enumerate(zip(rows,parents,scopes,stops),1):
        proof=row.get('loss_profile');target=verifier.train[verifier.spec['target']].iloc[parent].to_numpy(dtype=float)
        scale='log1p' if recipe['params'].get('log_target',False) and target.min()>=0 else 'original'
        need(row.get('source_rows')==len(parent) and row.get('output_rows')==len(parent)
            and row.get('source_parent_sha256')==r4.canonical(parent.tolist()) and row.get('synthetic_rows')==0,
            'loss_fitting_parent_lineage_changed')
        need(isinstance(proof,dict) and proof.get('loss_profile_id')==profile and proof.get('requested_objective')==objective
            and proof.get('effective_objective')==objective and proof.get('requested_alpha')==alpha
            and (alpha is None or proof.get('effective_alpha')==alpha) and proof.get('requested_metric')=='None'
            and proof.get('verified') is True and proof.get('evidence_source')=='fitted_booster.params'
            and proof.get('library')=='lightgbm' and proof.get('library_version')=='4.6.0' and proof.get('fit_index')==index
            and proof.get('model_scope')==scope and proof.get('validation_used_for_stopping') is stopping
            and proof.get('primary_metric')=='rmse' and proof.get('target_scale')==scale,'actual_booster_loss_proof_changed')
        metric=proof.get('effective_metric');metric=[metric] if isinstance(metric,str) else metric
        need(type(metric) is list and metric and all(type(v) is str and v.lower() in {'none','na','null','custom'} for v in metric),
             'actual_default_loss_metric_not_disabled')
        proofs.append(proof)
    need(record.get('loss_profile_id')==profile and record.get('effective_loss_profile')==proofs[-1],'effective_loss_receipt_mismatch')
    return dict(profile_id=profile,actual_postfit_receipts=proofs,full_fit=full)


def raw_records(report,recipe):
    result={}
    for phase,field in [('primary','experiments'),('confirmation','confirmations')]:
        found=[r for r in report[field] if r.get('status')=='ok' and r.get('recipe')==recipe]
        need(len(found)==1,'retained_recipe_requires_unique_actual_success_both_cuts')
        result[phase]=found[0]
    return result


def retention_proof(directory,task,report,raw,entry,r4,plan):
    runs=directory/'automl_runs/repair4';packet=load(directory/'retention.json')
    ref=task['retention'];kind=task['kind'];ret=report['research_retention']
    need(digest(directory/'retention.json')==ref['sha256']==ret['input_sha256']==ret['input_fingerprint'],
         'retention_input_byte_pin_or_runtime_receipt_changed')
    need(packet['schema']=='uar-strong-retention-v1' and packet['mode']==ret['mode']==
         ('l1_composite' if kind=='regression' else 'control'),'same_fixed_policy_mode_required')
    control=packet['control'];need(report['protected_control_recipe']==control['recipe']
        and ret['control_signature']==control['recipe_signature'],'typed_complete_control_changed')
    snapshot=load(runs/'strong-retention-recipes.json');prov=load(runs/'provenance.json')['sha256']
    need(snapshot['control']==control['recipe'] and snapshot['receipt']['input_sha256']==ref['sha256']
         and prov['strong_retention_input']==ref['sha256']
         and prov['strong_retention_snapshot']==digest(runs/'strong-retention-recipes.json'),
         'exact_raw_control_snapshot_and_provenance_required')
    sources=['protected_complete_control','unprofiled_hpo_single','isolated_feature_engineering','required_catboost','required_xgboost']
    if kind=='regression':sources+=['prior_champion','fixed_l1_composite']
    receipts=report['pipeline']['initial_queue_receipts'];required=ret['required_primary_statuses']
    need(len(required)==len(sources) and [v['source'] for v in required]==sources
         and [v['queue_index'] for v in required]==list(range(len(sources))), 'REG7_CLASS5_required_matrix_changed')
    for index,source in enumerate(sources):
        slot=[v for v in receipts if v.get('source')==source]
        need(len(slot)==1 and slot[0]['status']=='scheduled' and slot[0]['queue_index']==index
             and slot[0]['signature']==required[index]['signature'],'protected_slot_or_signature_changed')
        need(len(report['experiments'])>index and report['experiments'][index].get('experiment_index')==index,
             'required_primary_attempt_missing')
        need(report['experiments'][index]['status']==required[index]['status'],'required_attempt_status_mismatch')
    need(report['experiments'][0]['recipe']==control['recipe']
         and report['experiments'][1]['recipe']==control['recipe']['components'][0], 'first_control_and_raw_HPO_SINGLE_changed')
    anchor_signature=required[1]['signature']
    need(ret['hpo_anchor_signature']==report['pipeline']['hpo_single_anchor_signature']==anchor_signature,
         'raw_unprofiled_HPO_signature_changed')
    hpo=report['hpo'];need(hpo['control_recipe']==control['recipe']['components'][0]
        and not hpo['control_recipe']['params'].get('loss_profile_id'),'HPO_anchor_must_remain_unprofiled_raw_SINGLE')
    admission=ret['hpo_admission'];cfg=CAPS[kind];reserve=min(1200,max(60,cfg['solver']*.2))
    need(admission==load(runs/'retention-hpo-admission.json') and admission['configured_seconds']==cfg['hpo']
         and admission['requested_attempts']==8 and admission['anchor_signature']==anchor_signature
         and admission['reserve_seconds']==reserve
         and admission['deadline_monotonic']==admission['admitted_at_monotonic']+cfg['hpo']
         and admission['task_deadline_monotonic']-admission['admitted_at_monotonic']>=reserve+cfg['hpo']+30,
         'actual_full_HPO_call_window_and_reserve_required')
    need(ret['maximum_initial']==7 and ret['maximum_experiments']==9 and ret['isolated_selector'] is True
         and len(report['experiments'])<=9,'max9_or_matrix_policy_changed')
    train,test,sample=[r4.pd.read_csv(directory/n,converters={report['spec']['id']:str}) for n in ['train.csv','test.csv','sample_submission.csv']]
    verifier=r4.TaskVerifier(directory,report,train,test,sample);retained_metrics=None
    if kind=='regression':
        champion=packet['champion']['recipe'];seed=copy.deepcopy(control['recipe']['components'][0])
        seed['params']['loss_profile_id']='lgbm_l1_v1'
        retained=dict(engine='ensemble',params={},hypothesis='Fixed retained L1 SINGLE and prior champion; no weight search',components=[seed,copy.deepcopy(champion)],weights=[.75,.25])
        need(report['experiments'][5]['recipe']==champion and report['experiments'][6]['recipe']==retained
             and snapshot['champion']==champion and snapshot['retained']==report['retained_recipe']==retained
             and ret['retained_signature']==packet['retained_signature']==required[6]['signature'],
             'raw_CP1_and_fixed_75L1_25CP1_retention_changed')
        retained_metrics={}
        for phase,record in raw_records(report,retained).items():
            retained_metrics[phase]=r4.diagnostics(verifier,record,runs/('split.npz' if phase=='primary' else 'confirmation_split.npz'),phase)
        for phase in ['primary','confirmation']:
            expected=plan['expected_regression_splits'][phase]
            need(all(raw['cuts'][phase][k]==expected[k] for k in ['fitting_rows','validation_rows','positions_sha256',
                'training_rows_canonical_sha256','split_file_sha256','validation_periods']),'fixed_regression_cut_changed')
    else:
        need(snapshot['champion'] is None and snapshot['retained'] is None and report['retained_recipe'] is None
             and ret['retained_signature'] is None,'classification_control_only_changed')
    loss=[]
    for path in sorted(runs.rglob('result.json')):
        record=load(path);recipe=record.get('recipe') or {}
        if record.get('status')!='ok' or record.get('components') or not recipe.get('params',{}).get('loss_profile_id'):continue
        parts=path.relative_to(runs).parts;full=record.get('full_fit') is True
        partition=runs/('inner-hpo/split.npz' if parts[0]=='inner-hpo' else 'confirmation_split.npz' if parts[0].startswith('confirmation-') or parts[0]=='ensemble-confirmation' else 'split.npz')
        phase='final' if full else 'inner' if parts[0]=='inner-hpo' else 'confirmation' if 'confirmation' in partition.name else 'primary'
        verifier.verify(dict(record,output_dir=str(path.parent)),partition,phase,full,recipe)
        loss.append(dict(path=path.relative_to(runs).as_posix(),proof=loss_telemetry(record,recipe,verifier,r4,partition)))
    leaf_fit_receipts=[]
    for path in sorted(runs.rglob('result.json')):
        record=load(path)
        if record.get('components'):continue
        receipts=record.get('data_policy_runs')
        leaf_fit_receipts.append(dict(path=path.relative_to(runs).as_posix(),status=record.get('status'),
            completed_fitting_callbacks=len(receipts) if type(receipts) is list else None))
    return dict(required_matrix=required,actual_HPO_admission=admission,actual_HPO_accounting=hpo_counts(hpo),
        retained_composite_both_cut_measurements=retained_metrics,loss_profile_fits=loss,
        leaf_fit_receipts=leaf_fit_receipts,actual_total_learner_fits=None,
        fit_count_scope='One row per unique saved leaf, excludes copied parent components; failed/interrupted fits can be unknown. Callback receipts are not a certified total fit counter.',
        candidate_fit_costs_are_not_free=True,whole_training_planner_statistics_are_not_fitting_only=True)


def strict_proof(directory,arm,report,seal,work):
    spec=report['spec'];ledger_path=Path(report['run_budget_trace']).resolve()
    need(ledger_path.is_relative_to(directory/'automl_runs') and ledger_path.name=='report.json'
         and ledger_path.parent.name.startswith('run-budget-'),'exact_local_closed_usage_trace_required')
    def sealed(path):
        name=path.relative_to(work).as_posix()
        need(seal['files_sha256'].get(name)==digest(path),'strict_or_API_evidence_not_pretruth_sealed')
        return load(path)
    ledger=sealed(ledger_path);need(ledger['status']=='completed' and ledger['gateway_call_limit']==4
        and 1<=ledger['gateway_calls_started']<=4 and ledger['usage_complete'] is True,'actual_complete_gateway_usage_required')
    initial=load(directory/'automl_runs/repair4/initial-data-assessment.json');call=initial['call']
    need(call.get('status')=='ok' and type(call.get('attempts')) is int and call['attempts']>=1,
         'genuine_initial_Qwen_HTTP_attempt_required_no_mock_or_cache_claim')
    need(ledger['http_attempts_reported']>=ledger['gateway_calls_started']
         and all(type(e.get('http_attempts_known')) is int and e['http_attempts_known']>=1
                 for e in ledger['events'] if e.get('reserved_gateway_call')),'HTTP_attempts_unknown_not_zero_or_certified')
    # Counts are actual provider-reported evidence, not imputed currency or effective reasoning guarantees.
    info=dict(gateway_calls=ledger['gateway_calls_started'],HTTP_attempts=ledger['http_attempts_reported'],
        prompt_tokens=ledger['prompt_tokens_reported'],completion_tokens=ledger['completion_tokens_reported'],usage_complete=True,
        followup_observed=len(report.get('llm_calls',[]))>=2,requested_reasoning_effort='off',effective_reasoning_effort_certified=False)
    if arm=='A':
        need('strict_task_contract' not in spec and not (ledger_path.parent/'task-contract.json').exists(),
             'A_strict_task_factor_must_be_absent')
        return dict(strict_task_contract=False,API=info)
    contract=sealed(ledger_path.parent/'task-contract.json');provenance=sealed(ledger_path.parent/'strict-input-provenance.json')
    need(contract['schema']=='strict-task-contract-v1' and contract['status']=='admitted'
         and contract['output_produced'] is True and contract['publication']=='validated_atomic_C01'
         and contract['objective_resolved'] is True and contract['full_input_provenance_verified'] is True
         and contract['full_load_lexical_projections_verified'] is True and contract['new_clock_created'] is False,
         'strict_caller_did_not_reach_qualified_pre_model_admission')
    metric=contract['metric_spec'];need(metric['status']=='resolved' and metric['name']==spec['metric']
        and metric['direction']==('minimize' if spec['kind']=='regression' else 'maximize'),'strict_objective_changed')
    need(spec['strict_task_contract']['metric_spec']==metric and spec['strict_task_contract']['full_input_provenance_verified'] is True,
         'strict_spec_report_field_mismatch')
    need(provenance['new_clock_created'] is False and provenance['sha256']['task']==digest(directory/'task.md'),
         'strict_task_source_changed')
    for role,name in [('train','train.csv'),('test','test.csv'),('sample_submission','sample_submission.csv')]:
        need(provenance['input_roles'][role]==name and provenance['sha256']['input:'+role]==digest(directory/name),
             'strict_full_input_role_or_byte_binding_changed')
    need(provenance['dictionary_path']=='data_dictionary.csv'
         and provenance['sha256']['input:data_dictionary']==digest(directory/'data_dictionary.csv'),'strict_dictionary_binding_changed')
    for key,value in provenance['sha256'].items():
        if key.startswith('source:'):
            need(digest(directory/key.split(':',2)[2])==value,'strict_runtime_source_inventory_changed')
    return dict(strict_task_contract=True,contract_receipt_sha256=digest(ledger_path.parent/'task-contract.json'),
        provenance_sha256=digest(ledger_path.parent/'strict-input-provenance.json'),API=info,
        format_and_lexical_receipt_verified=True,planner_full_train_statistics_not_fitting_only=True)


ORIGINAL_AUDIT_SHA='d004d777670807d59d8998c6bc7c4c84cf5a177c68144cdc71aceebaa937bd22'
ADAPTER_SHA='823d9629119bcd03560cafb62e8b240af8dea5b3f3ba63b4d196b96a62a518cd'
PREREGISTRATION_SHA='5e826ec22f0291d5b204b9bc2594db16e0320e14adc20f08c90ac86ae77ecc22'
ORIGIN=(1792826068.8239975,85073.953,1792836868.8239975,95873.953)

def identity_set(rows):
    need(type(rows) is list and len(rows)<=20000,'bounded_known_identity_list_required')
    result=set()
    for row in rows:
        need(type(row) is dict and type(row.get('pid')) is int and row['pid']>0
             and type(row.get('create_time')) in (int,float) and math.isfinite(row['create_time'])
             and row['create_time']>0,'typed_exact_process_identity_required')
        result.add((row['pid'],row['create_time']))
    return result


def main():
    # This is a separately declared audit revision, not the frozen campaign auditor.
    begin=time.monotonic()
    p=argparse.ArgumentParser(description='Fixed UQ2 complete-task-pair saved-artifact audit; no fits/API')
    for n in ['work-root','manifest','manifest-sha256','plan','plan-sha256','self-sha256',
              'declaration','declaration-sha256','root-readiness','root-readiness-sha256']:
        p.add_argument('--'+n,required=True)
    args=p.parse_args();need(__debug__,'nonoptimized_python_required');work=Path(args.work_root).resolve()
    def local(n):
        q=(work/n).resolve();need(not Path(n).is_absolute() and q.is_relative_to(work),'audit_reference_outside_work');return q
    root=work/'uq2';outroot=work/'uq2-successful-task-pair-audit-r1'
    output=outroot/'audit.json';eligibility_output=outroot/'eligibility-pretruth.json'
    need(outroot.is_dir() and not outroot.is_symlink() and not output.exists()
         and not eligibility_output.exists(),'exclusive_new_audit_output_required')
    need(digest(__file__)==args.self_sha256 and digest(local(args.manifest))==args.manifest_sha256
         and digest(local(args.plan))==args.plan_sha256
         and digest(local(args.declaration))==args.declaration_sha256
         and digest(local(args.root_readiness))==args.root_readiness_sha256,'explicit_separate_audit_pins_required')
    declaration,ready=load(local(args.declaration)),load(local(args.root_readiness))
    need(declaration['schema']=='uq2-successful-task-pair-audit-declaration-v1'
         and declaration['auditor_sha256']==args.self_sha256
         and declaration['preregistration']['sha256']==PREREGISTRATION_SHA
         and digest(local(declaration['preregistration']['path']))==PREREGISTRATION_SHA
         and declaration['original_auditor_sha256']==ORIGINAL_AUDIT_SHA
         and digest(local(declaration['original_auditor_path']))==ORIGINAL_AUDIT_SHA,
         'published_preoutcome_rule_and_unchanged_original_auditor_required')
    need(ready['schema']=='uq2-successful-task-pair-audit-root-readiness-v1'
         and ready['status']=='READY_ROOT_CONFIRMED_SOURCE_REVIEWED'
         and ready['missing_bindings']==[]
         and ready['actual_campaign_session']==3588 and ready['actual_campaign_exit_code']==1
         and type(ready['actual_campaign_tool_evidence']) is str and ready['actual_campaign_tool_evidence'].strip()
         and ready['declaration_sha256']==args.declaration_sha256
         and ready['preregistration_sha256']==PREREGISTRATION_SHA
         and ready['original_global_failure_preserved'] is True
         and ready['original_full_procedure_passed'] is False,'actual_whole_terminal_failure_required_before_audit')
    need(ready['root_closure_actual_exit_code']==0
         and type(ready['root_closure_actual_tool_evidence']) is str
         and ready['root_closure_actual_tool_evidence'].strip(),'actual_root_closer_terminal_evidence_required')
    guard=ready['guard']
    need(type(guard['source_path']) is str and type(guard['source_sha256']) is str
         and re.fullmatch('[0-9a-f]{64}',guard['source_sha256'])
         and digest(local(guard['source_path']))==guard['source_sha256'],
         'source_reviewed_actual_bounded_caller_pin_required')
    need(ready['manifest']==dict(path=args.manifest,sha256=args.manifest_sha256)
         and ready['plan']==dict(path=args.plan,sha256=args.plan_sha256),'root_ready_original_plan_and_manifest_binding_required')
    manifest,plan,campaign=load(local(args.manifest)),load(local(args.plan)),load(root/'campaign.json')
    need(digest(root/'campaign.json')==ready['campaign_sha256'],'terminal_campaign_changed')
    ref=ready['root_closure'];need(digest(local(ref['path']))==ref['sha256'],'actual_root_closure_changed')
    closure=load(local(ref['path']))
    need(closure['actual_exec_session']==3588 and closure['actual_exec_exit_code_observed_by_root']==1
         and closure['actual_tool_evidence']==ready['actual_campaign_tool_evidence']
         and closure['technical_procedure_passed'] is False
         and closure['cleanup_confirmed'] is True and closure['source_unchanged'] is True
         and closure['active_owned_processes']==[] and closure['uncertain_owned']==[]
         and closure['changed_source_or_core']==[],'whole_FAIL_and_current_clean_known_scope_required')
    observation=ready['fresh_owned_observation']
    need(observation['known_exact_live']==[] and observation['uncertain']==[]
         and observation['all_root_and_preparer_identities_checked'] is True
         and ready['guard']['parent_seconds']==120 and ready['guard']['child_seconds']==90
         and ready['guard']['worker_mib']==1536 and ready['guard']['whole_mib']==2048
         and ready['guard']['threads']==1 and ready['guard']['API_environment_stripped'] is True
         and ready['guard']['canonical_lock_required'] is True,
         'fresh_known_scope_and_existing_supervisor120_90_required')
    for field in ['checked_unix','checked_monotonic']:
        need(type(observation[field]) in (int,float) and math.isfinite(observation[field]),'finite_fresh_observation_required')
    required=identity_set(closure['owned_identities']+closure['closure_preparer_identities'])
    need(required<=identity_set(observation['known_identities']),'current_observation_must_include_closure_preparers')
    need(manifest['schema']=='UAR-Qwen-pair-v1' and manifest['caps']==CAPS and manifest['common_seconds']==10800
         and plan['common_seconds']==10800 and manifest['order']==plan['pair_order']==[a+c for a,k,c in ORDER],
         'same_four_slot_plan_required')
    need(plan['verifier_source_sha256']==ORIGINAL_AUDIT_SHA
         and plan['execution_manifest_sha256']==args.manifest_sha256
         and plan['manual_metric_verifier_path']==R4 and plan['manual_metric_verifier_sha256']==R4_SHA
         and digest(local(R4))==R4_SHA and plan['r4_adapter_sha256']==manifest['r4_adapter_sha256']==ADAPTER_SHA
         and digest(local(plan['r4_adapter_path']))==ADAPTER_SHA,'unchanged_frozen_R4_adapter_and_original_plan_required')
    need(campaign['manifest_sha256']==args.manifest_sha256 and campaign['verification_plan_sha256']==args.plan_sha256
         and campaign['absolute_deadline_unix']==plan['original_absolute_deadline_unix']==campaign['start_unix']+10800
         and campaign['common_deadline_monotonic']==campaign['start_monotonic']+10800
         and campaign['start_unix']==plan['original_common_start_unix']
         and tuple(campaign[k] for k in ['start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic'])==ORIGIN
         and campaign['status'] not in {'starting','running','verifying'}
         and campaign['qualification']=='FAIL' and campaign['error_history']
         and campaign['cleanup_confirmed'] is True and campaign['source_unchanged'] is True
         and campaign['start_unix']<=campaign['finished_unix']<campaign['absolute_deadline_unix']
         and campaign['start_monotonic']<=campaign['finished_monotonic']<campaign['common_deadline_monotonic'],
         'actual_terminal_FAIL_and_original10800_required')
    # Charge every elapsed second since the original audit admission, including its
    # failed auditor, root closure, review and publication. No reclaimed old time.
    audit_ref=ready['original_audit_supervisor']
    need(digest(local(audit_ref['path']))==audit_ref['sha256']
         and any(v['path']==audit_ref['path'] and v['sha256']==audit_ref['sha256']
                 for v in campaign['supervisors']),'original_audit_admission_receipt_required')
    original_audit=load(local(audit_ref['path']))
    need(original_audit['kind']=='pair-audit' and original_audit['parent_cap_seconds']==600
         and original_audit['cleanup_confirmed'] is True
         and original_audit['cleanup_observation']['unresolved']==[]
         and original_audit['cleanup_observation']['denial_count']==0,'original_auditor_must_be_terminal_clean')
    budget_end=original_audit['start_monotonic']+600
    budget_unix=original_audit['start_unix']+600
    parent_start=ready['guard']['parent_start_monotonic'];parent_unix=ready['guard']['parent_start_unix']
    need(all(type(v) in (int,float) and math.isfinite(v) for v in [parent_start,parent_unix])
         and campaign['finished_monotonic']<=observation['checked_monotonic']<=parent_start<=begin
         and campaign['finished_unix']<=observation['checked_unix']<=parent_unix<=time.time()
         and parent_start+120+30<=min(budget_end,campaign['common_deadline_monotonic'])
         and parent_unix+120+30<=min(budget_unix,campaign['absolute_deadline_unix']),
         'new120_and_root30_must_fit_original_audit600_and_common10800')
    def clock():
        mono,unix=time.monotonic(),time.time()
        need(mono<min(begin+90,parent_start+120,budget_end,campaign['common_deadline_monotonic']-30)
             and unix<min(budget_unix,campaign['absolute_deadline_unix']-30),'original_or_separate_audit_clock_exhausted')
        need(abs((campaign['absolute_deadline_unix']-unix)-(campaign['common_deadline_monotonic']-mono))<=5,
             'original_clock_disagreement')
    global DIGEST_CHECKPOINT
    DIGEST_CHECKPOINT=clock
    def frozen():
        clock()
        for path,h in [(Path(__file__),args.self_sha256),(local(args.manifest),args.manifest_sha256),
                       (local(args.plan),args.plan_sha256),(local(args.declaration),args.declaration_sha256),
                       (local(args.root_readiness),args.root_readiness_sha256),(root/'campaign.json',ready['campaign_sha256']),
                       (local(ref['path']),ref['sha256']),(local(audit_ref['path']),audit_ref['sha256']),
                       (local(guard['source_path']),guard['source_sha256'])]:
            need(digest(path)==h,'audit_authority_or_terminal_evidence_changed')
        for n,h in {**manifest['immutable_files'],**declaration['source_pins']}.items():
            need(digest(local(n))==h,'frozen_source_or_input_changed')
    entries={v['slot']:v for v in campaign['arms']}
    need(len(campaign['arms'])==4 and set(entries)==set(manifest['order']),'ALL4_actual_unique_closed_slots_required')
    checkpoint_ref=manifest['authority_checkpoint']
    need(checkpoint_ref==plan['authority_checkpoint'] and digest(local(checkpoint_ref['path']))==checkpoint_ref['sha256'],
         'shared_prefirst_API_checkpoint_changed')
    checkpoint=load(local(checkpoint_ref['path']))
    need(checkpoint['schema']=='UAR-authority-checkpoint-v1' and checkpoint['status']=='validated_before_first_Qwen'
         and set(checkpoint['tasks'])==set(CAPS) and checkpoint['source_archive_sha256']==manifest['archive_sha256']
         and checkpoint['new_clock_created'] is False and checkpoint['shared_original_setup_budget'] is True
         and checkpoint['original_common_start_unix']==campaign['start_unix']
         and checkpoint['original_common_start_monotonic']==campaign['start_monotonic']
         and campaign['start_monotonic']<=checkpoint['validation_start_monotonic']<=checkpoint['validation_end_monotonic']
         <campaign['start_monotonic']+900
         and checkpoint['validation_end_monotonic']<=min(v['child_start_monotonic'] for v in entries.values()),
         'checkpoint_must_precede_ALL4_actual_solvers')
    for code in ['r','c']:
        need(manifest['slots']['B'+code]['argv']==manifest['slots']['A'+code]['argv']+['--strict-task-contract'],
             'only_B_strict_task_flag_may_differ')
    terminals,seals,preliminary={},{},{}
    for arm,kind,code in ORDER:
        key=arm+code;entry=entries[key];cfg=CAPS[kind];directory=root/arm/code;meta=manifest['arms'][arm]
        need(campaign['actual_arm_argv'][key]==manifest['slots'][key]['argv'],'actual_frozen_argv_changed')
        argv=manifest['slots'][key]['argv'];need('--strict-runtime' in argv and '--offline' not in argv,'original_Qwen_strict_runtime_required')
        need(entry['task_allocation_seconds']==entry['parent_cap_seconds']==cfg['parent']
             and entry['child_cap_seconds']==cfg['child'] and entry['solver_budget_seconds']==cfg['solver']
             and entry['requested_hpo_budget_seconds']==cfg['hpo'],'same_declared_task_caps_required')
        need(digest(local(entry['supervisor_path']))==entry['supervisor_sha256'],'saved_supervisor_changed')
        terminal=load(local(entry['supervisor_path']));terminals[key]=terminal
        need(entry['kind']==kind and terminal['kind']==kind+'-'+arm,'terminal_kind_arm_mapping_changed')
        need(all(terminal.get(k)==v for k,v in entry.items() if k in terminal and k!='kind'),'inline_saved_supervisor_changed')
        need(terminal['status'] in {'ok','child_failed'} and terminal['cleanup_confirmed'] is True
             and terminal['cleanup_observation']['unresolved']==[]
             and terminal['cleanup_observation']['denial_count']==0,'ALL4_closed_known_scope_required_including_failed_slot')
        need(digest(local(entry['seal']['path']))==entry['seal']['sha256'],'pretruth_seal_changed')
        seal=load(local(entry['seal']['path']));seals[key]=seal
        need(seal['slot']==key and seal['arm']==arm and seal['kind']==kind and seal['cleanup_confirmed'] is True
             and seal['source_unchanged'] is True and seal['sealed_before_independent_label_scoring'] is True,
             'ALL4_pretruth_seal_contract_required')
        # Exact existing inventory for failed slots; absence is failure evidence,
        # never a fabricated report/refit/CSV or a reason to omit that slot's seal.
        actual={};subtrees=[directory/'automl_runs/repair4',*sorted((directory/'automl_runs').glob('run-budget-*'))]
        for subtree in subtrees:
            if not subtree.exists():continue
            need(subtree.is_dir() and not subtree.is_symlink(),'core_or_usage_subtree_symlink')
            for parent,dirs,files in os.walk(subtree):
                need(not any((Path(parent)/n).is_symlink() for n in [*dirs,*files]),'sealed_symlink')
                for name in files:
                    need(not name.endswith(('.tmp','.pending')),'unfinished_core');path=Path(parent)/name
                    actual[path.relative_to(work).as_posix()]=digest(path)
        if (directory/'submission.csv').exists():
            actual[(directory/'submission.csv').relative_to(work).as_posix()]=digest(directory/'submission.csv')
        actual[(directory/'authority-checkpoint.json').relative_to(work).as_posix()]=digest(directory/'authority-checkpoint.json')
        need(actual==seal['files_sha256'],'ALL4_exact_complete_or_failed_partial_inventory_changed')
        need(meta['archive']==manifest['archive'] and meta['archive_sha256']==manifest['archive_sha256']
             and meta['compiled_sha256']==manifest['compiled_sha256']
             and digest(local(meta['archive']))==meta['archive_sha256'],'same_archive_both_arms_required')
        with zipfile.ZipFile(local(meta['archive'])) as archive:
            need(len(archive.namelist())==len(set(archive.namelist()))==len(meta['compiled_sha256'])
                 and {n:hashlib.sha256(archive.read(n)).hexdigest() for n in archive.namelist()}==meta['compiled_sha256'],
                 'archive_member_changed')
        for name,h in manifest['compiled_sha256'].items():need(digest(directory/name)==h,'ALL4_pretruth_flat_changed')
        task=next(t for t in manifest['tasks'] if t['kind']==kind)
        for name,h in task['files'].items():need(digest(directory/name)==digest(local(task['source'])/name)==h,'ALL4_pretruth_input_changed')
        need(digest(directory/'retention.json')==digest(local(task['retention']['path']))==task['retention']['sha256']
             and digest(directory/'protected_control.json')==task['control_recipe']['sha256'],'ALL4_pretruth_retention_or_control_changed')
        need(digest(directory/'authority-checkpoint.json')==checkpoint_ref['sha256'],'ALL4_checkpoint_bytes_must_match')
        authority=checkpoint['tasks'][kind]
        need(authority['task_sha256']==task['files']['task.md'] and authority['retention_sha256']==task['retention']['sha256']
             and authority['metric']['status']=='resolved' and authority['metric']['name']==('rmse' if kind=='regression' else 'macro_f1')
             and authority['feature_or_target_rows_parsed'] is False and authority['input_bytes_hashed'] is True,
             'checkpoint_task_metric_retention_binding_changed')
        reasons=[];accounting=None
        if terminal['status']!='ok' or terminal['exit_code']!=0:reasons.append('actual_solver_not_successful')
        if not (directory/'automl_runs/repair4/report.json').is_file() or not (directory/'submission.csv').is_file():
            reasons.append('complete_report_and_refit_CSV_required')
        if not reasons:
            try:
                report=load(directory/'automl_runs/repair4/report.json');pipeline=report.get('pipeline') or {}
                need(report.get('final_fit_status')=='ok' and report.get('integrity_ok') is True
                     and pipeline.get('mode')=='four_stage' and pipeline.get('initial_data_assessment_before_fitting') is True
                     and (directory/'automl_runs/repair4/final-fit/result.json').is_file(),
                     'successful_four_stages_and_actual_refit_required')
                hpo=load(directory/'automl_runs/repair4/inner-hpo/hpo.json')
                need(hpo==report['hpo'] and hpo['status']=='ok','saved_HPO_report_mismatch')
                accounting=hpo_counts(hpo)
                need(accounting['attempted_trials']==accounting['completed_trials']==8 and accounting['failed_trials']==0
                     and accounting['duplicate_trials']==0 and accounting['unattempted_trials']==0,
                     'eight_actual_valid_HPO_attempts_required')
            except Exception as exc:
                reasons.append(str(exc) if isinstance(exc,AssertionError) and re.fullmatch('[A-Za-z0-9_:+.-]{1,200}',str(exc))
                               else 'pretruth_procedure_metadata_unqualified')
        preliminary[key]=dict(eligible=not reasons,reasons=reasons,actual_HPO_accounting=accounting,
                              solver_status=terminal['status'],solver_exit_code=terminal.get('exit_code'))
    frozen()
    eligibility={kind:all(preliminary[a+code]['eligible'] for a in ['A','B'])
                 for kind,code in [('regression','r'),('classification','c')]}
    need(eligibility['regression'] is False and terminals['Br']['status']=='child_failed'
         and terminals['Br']['exit_code']!=0,'preregistered_Br_failure_must_remain_unqualified')
    pretruth=dict(schema='uq2-successful-task-pair-pretruth-eligibility-v1',preregistration_sha256=PREREGISTRATION_SHA,
        campaign_sha256=ready['campaign_sha256'],root_closure=ref,all4_seal_sha256={k:v['seal']['sha256'] for k,v in entries.items()},
        slots=preliminary,task_pair_eligibility=eligibility,metrics_read_for_selection=False,
        original_global_qualification='FAIL',new_common_clock=False)
    with eligibility_output.open('x',encoding='utf-8') as stream:json.dump(pretruth,stream,ensure_ascii=False,indent=2,allow_nan=False)
    clock();pretruth_sha=digest(eligibility_output)
    rows={key:dict(procedure_passed=False,qualified_selected_cut_mean=None,raw_r4=None,
        errors=preliminary[key]['reasons'] or ['paired_other_arm_not_eligible'],failed_metrics_zero_imputed=False)
        for key in entries}
    # ALL4 source/input/seal bytes and fixed technical eligibility precede every
    # numerical import and pristine-label read. Do not score an incomplete pair.
    if any(eligibility.values()):
        spec=importlib.util.spec_from_file_location('_frozen_UAR_R4_adapter',local(plan['r4_adapter_path']))
        r4=importlib.util.module_from_spec(spec);spec.loader.exec_module(r4)
        r4.WORK,r4.REPO,r4.RUN_NAME=work,work/'alfa-hack-automl','repair4'
        for arm,kind,code in ORDER:
            if not eligibility[kind]:continue
            key=arm+code;entry=entries[key];directory=root/arm/code;raw=None
            try:
                clock();r4.ROOT=root/arm;task=next(t for t in manifest['tasks'] if t['kind']==kind)
                report=load(directory/'automl_runs/repair4/report.json')
                raw=r4.verify_task(task,manifest['arms'][arm],plan,entry)
                need({'lightgbm','catboost','xgboost'}<=set(raw['successful_model_families']),'all_three_actual_families_required')
                need(Path(report['spec']['root']).resolve()==directory.resolve(),'spec_root_changed')
                retention=retention_proof(directory,task,report,raw,entry,r4,plan)
                need(retention['actual_HPO_accounting']==preliminary[key]['actual_HPO_accounting'],'late_HPO_accounting_changed')
                caller=strict_proof(directory,arm,report,seals[key],work)
                identifier=report['spec']['id']
                def ids(path):
                    with path.open('r',encoding='utf-8-sig',newline='') as stream:
                        reader=csv.DictReader(stream);return [row[identifier] for row in reader]
                need(ids(directory/'submission.csv')==ids(directory/'sample_submission.csv'),'final_lexical_ID_order_changed')
                rows[key]=dict(procedure_passed=raw['procedure_passed'],qualified_selected_cut_mean=None,
                    errors=raw['errors'],raw_r4=raw,retention=retention,caller=caller,failed_metrics_zero_imputed=False)
            except Exception as exc:
                rows[key]=dict(procedure_passed=False,qualified_selected_cut_mean=None,errors=['R4_or_UAR_contract_failed'],
                    exception_type=type(exc).__name__,contract_reason=str(exc) if isinstance(exc,AssertionError)
                        and re.fullmatch('[A-Za-z0-9_:+.-]{1,200}',str(exc)) else None,
                    raw_r4=raw,failed_metrics_zero_imputed=False)
    pair_passed={kind:eligibility[kind] and all(rows[a+code]['procedure_passed'] for a in ['A','B'])
                 for kind,code in [('regression','r'),('classification','c')]}
    comparison={kind:None for kind in CAPS}
    for kind,code in [('regression','r'),('classification','c')]:
        if not pair_passed[kind]:continue
        for arm in ['A','B']:rows[arm+code]['qualified_selected_cut_mean']=rows[arm+code]['raw_r4']['selected_cut_mean']
        values={a:rows[a+code]['qualified_selected_cut_mean'] for a in ['A','B']}
        need(all(type(v) in (int,float) and math.isfinite(v) for v in values.values()),'finite_independent_pair_metrics_required')
        comparison[kind]=dict(**values,delta_B_minus_A=values['B']-values['A'],higher_is_better=kind=='classification',
            historical_comparisons={a:rows[a+code]['raw_r4']['baseline_comparisons'] for a in ['A','B']})
    frozen()
    for arm,kind,code in ORDER:
        entry=entries[arm+code];directory=root/arm/code;seal=seals[arm+code]
        need(digest(local(entry['seal']['path']))==entry['seal']['sha256']
             and digest(local(entry['supervisor_path']))==entry['supervisor_sha256'],'late_seal_or_supervisor_changed')
        for name,h in seal['files_sha256'].items():need(digest(local(name))==h,'late_core_changed')
        for name,h in manifest['compiled_sha256'].items():need(digest(directory/name)==h,'late_flat_changed')
        task=next(t for t in manifest['tasks'] if t['kind']==kind)
        for name,h in task['files'].items():need(digest(directory/name)==digest(local(task['source'])/name)==h,'late_input_changed')
        need(digest(directory/'retention.json')==task['retention']['sha256']
             and digest(directory/'protected_control.json')==task['control_recipe']['sha256'],'late_retention_or_control_changed')
        need(digest(directory/'authority-checkpoint.json')==digest(local(checkpoint_ref['path']))==checkpoint_ref['sha256'],
             'late_authority_checkpoint_changed')
    need(digest(eligibility_output)==pretruth_sha,'pretruth_eligibility_changed');clock()
    result=dict(schema='uq2-successful-task-pair-audit-v1',
        status='separate_successful_task_pair_verified_pending_root' if any(pair_passed.values()) else 'all_task_pairs_unqualified',
        slots=rows,task_pair_pretruth_eligibility=eligibility,task_pair_procedure_passed=pair_passed,comparison=comparison,
        regression_quality_metric=None,classification_quality_metric=comparison['classification'],
        original_global_qualification='FAIL',original_full_procedure_passed=False,original_global_error_history=campaign['error_history'],
        original_first_failure=campaign['first_failure'],original_campaign_actual_session=3588,original_campaign_actual_exit_code=1,
        original_root_closure=ref,original_root_readiness_sha256=args.root_readiness_sha256,
        preregistration_sha256=PREREGISTRATION_SHA,declaration_sha256=args.declaration_sha256,
        manifest_sha256=args.manifest_sha256,original_verification_plan_sha256=args.plan_sha256,
        original_auditor_sha256=ORIGINAL_AUDIT_SHA,separate_auditor_sha256=args.self_sha256,
        manual_metric_source_sha256=R4_SHA,r4_adapter_sha256=ADAPTER_SHA,eligibility_pretruth_sha256=pretruth_sha,
        all4_source_input_and_core_rechecked=True,audit_within_original_common_clock=True,
        combined_audit_allocation_seconds=600,original_audit_start_monotonic=original_audit['start_monotonic'],
        new_audit_parent_cap_seconds=120,new_audit_child_cap_seconds=90,new_common_clock=False,
        separate_actual_exec_and_fresh_preparer_confirmation_required=True,actual_separate_exec_exit_code=None,
        new_model_fits=0,API_calls=0,tests_run=0,failed_metrics_zero_imputed=False,
        official_default_ready=False,promotion=False,submit=False,official_score=None,
        scope='Separately preregistered reused-public successful-task pair only. Whole UQ2 remains FAIL; no regression A/B, causal, blind, release/default or official qualification.')
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False)
    clock();print(json.dumps(dict(status=result['status'],task_pair_procedure_passed=pair_passed)))


if __name__=='__main__':main()
