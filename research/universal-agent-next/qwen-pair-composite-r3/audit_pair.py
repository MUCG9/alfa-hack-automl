"""Independent sealed four-slot UAR audit. No fitting, API, candidate import or promotion.
Numerical/R4 imports and all truth reads follow verification of ALL FOUR seals.
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


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(2**20),b''):h.update(block)
    return h.hexdigest()


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


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['work-root','pair-root','manifest','manifest-sha256','plan','plan-sha256','self-sha256','output']:p.add_argument('--'+n,required=True)
    args=p.parse_args();need(__debug__,'nonoptimized_python_required');work=Path(args.work_root).resolve()
    def local(n):
        q=(work/n).resolve();need(not Path(n).is_absolute() and q.is_relative_to(work),'audit_reference_outside_work');return q
    root,output=local(args.pair_root),local(args.output)
    need(root==work/'uq1' and output==root/'independent-audit.json' and not output.exists(),'exclusive_new_pair_output_required')
    need(digest(__file__)==args.self_sha256 and digest(local(args.manifest))==args.manifest_sha256
         and digest(local(args.plan))==args.plan_sha256,'explicit_audit_pins_required')
    manifest,plan,campaign=load(local(args.manifest)),load(local(args.plan)),load(root/'campaign.json')
    need(manifest['schema']=='UAR-Qwen-pair-v1' and manifest['caps']==CAPS and manifest['common_seconds']==10800
         and plan['common_seconds']==10800 and manifest['order']==plan['pair_order']==[a+c for a,k,c in ORDER], 'same_four_slot_plan_required')
    need(plan['verifier_source_sha256']==args.self_sha256 and plan['execution_manifest_sha256']==args.manifest_sha256
         and plan['manual_metric_verifier_path']==R4 and plan['manual_metric_verifier_sha256']==R4_SHA
         and digest(local(R4))==R4_SHA and plan['r4_adapter_sha256']==manifest['r4_adapter_sha256']
         and digest(local(plan['r4_adapter_path']))==plan['r4_adapter_sha256'],'frozen_original_R4_and_reviewed_adapter_required')
    need(campaign['manifest_sha256']==args.manifest_sha256 and campaign['verification_plan_sha256']==args.plan_sha256
         and campaign['absolute_deadline_unix']==plan['original_absolute_deadline_unix']==campaign['start_unix']+10800
         and campaign['common_deadline_monotonic']==campaign['start_monotonic']+10800
         and campaign['start_unix']==plan['original_common_start_unix'] and campaign['status']=='verifying'
         and campaign['cleanup_confirmed'] is True and campaign['source_unchanged'] is True and not campaign['error_history'],
         'all_four_terminal_clean_original_clock_required')
    def clock():need(time.time()<campaign['absolute_deadline_unix'] and time.monotonic()<campaign['common_deadline_monotonic'],'original_audit_clock_exhausted')
    def frozen():
        clock()
        need(digest(__file__)==args.self_sha256 and digest(local(args.manifest))==args.manifest_sha256
             and digest(local(args.plan))==args.plan_sha256,'audit_authority_changed')
        for n,h in manifest['immutable_files'].items():need(digest(local(n))==h,'frozen_source_or_input_changed');clock()
    entries={v['slot']:v for v in campaign['arms']}
    need(len(campaign['arms'])==4 and set(entries)==set(manifest['order']),'all_four_unique_slots_required')
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
         'checkpoint_must_precede_all4_actual_solver_processes_under_same_setup_clock')
    for code in ['r','c']:
        need(manifest['slots']['B'+code]['argv']==manifest['slots']['A'+code]['argv']+['--strict-task-contract'],
             'only_B_strict_task_flag_may_differ')
    for arm,kind,code in ORDER:
        key=arm+code;entry=entries[key];cfg=CAPS[kind];directory=root/arm/code;meta=manifest['arms'][arm]
        need(campaign['actual_arm_argv'][key]==manifest['slots'][key]['argv'],'actual_frozen_argv_changed')
        argv=manifest['slots'][key]['argv'];need('--strict-runtime' in argv and '--offline' not in argv,'real_API_and_strict_runtime_both_required')
        need(entry['task_allocation_seconds']==entry['parent_cap_seconds']==cfg['parent']
             and entry['child_cap_seconds']==cfg['child'] and entry['solver_budget_seconds']==cfg['solver']
             and entry['requested_hpo_budget_seconds']==cfg['hpo'],'same_declared_task_caps_required')
        need(digest(local(entry['supervisor_path']))==entry['supervisor_sha256'],'saved_supervisor_changed')
        terminal=load(local(entry['supervisor_path']))
        need(entry['kind']==kind and terminal['kind']==kind+'-'+arm,'semantic_kind_terminal_kind_arm_mapping_changed')
        need(all(terminal.get(k)==v for k,v in entry.items() if k in terminal and k!='kind'),'inline_saved_supervisor_changed')
        need(terminal['status']=='ok' and terminal['exit_code']==0 and terminal['cleanup_confirmed'] is True
             and terminal['cleanup_observation']['unresolved']==[],'all_four_actual_solver_terminal_success_required')
        need(digest(local(entry['seal']['path']))==entry['seal']['sha256'],'pretruth_seal_changed');seal=load(local(entry['seal']['path']))
        need(seal['slot']==key and seal['arm']==arm and seal['kind']==kind and seal['cleanup_confirmed'] is True
             and seal['source_unchanged'] is True and seal['sealed_before_independent_label_scoring'] is True,'pretruth_seal_contract_changed')
        actual={}
        for subtree in [directory/'automl_runs/repair4',*sorted((directory/'automl_runs').glob('run-budget-*'))]:
            need(subtree.is_dir() and not subtree.is_symlink(),'complete_core_and_closed_usage_subtree_required')
            for parent,dirs,files in os.walk(subtree):
                need(not any((Path(parent)/n).is_symlink() for n in [*dirs,*files]),'sealed_symlink')
                for name in files:
                    need(not name.endswith(('.tmp','.pending')),'unfinished_core');path=Path(parent)/name
                    actual[path.relative_to(work).as_posix()]=digest(path);clock()
        actual[(directory/'submission.csv').relative_to(work).as_posix()]=digest(directory/'submission.csv')
        actual[(directory/'authority-checkpoint.json').relative_to(work).as_posix()]=digest(directory/'authority-checkpoint.json')
        need(actual==seal['files_sha256'],'complete_core_and_strict_receipt_inventory_changed')
        need(meta['archive']==manifest['archive'] and meta['archive_sha256']==manifest['archive_sha256']
             and meta['compiled_sha256']==manifest['compiled_sha256'] and digest(local(meta['archive']))==meta['archive_sha256'],'same_archive_both_arms_required')
        with zipfile.ZipFile(local(meta['archive'])) as archive:
            need(len(archive.namelist())==len(set(archive.namelist()))==len(meta['compiled_sha256'])
                 and {n:hashlib.sha256(archive.read(n)).hexdigest() for n in archive.namelist()}==meta['compiled_sha256'],'archive_member_changed')
        # Repeat the existing posttruth deployment checks for ALL FOUR arms here.
        # Hash bytes only: no CSV/label parsing before the first R4 import.
        for name,h in manifest['compiled_sha256'].items():need(digest(directory/name)==h,'pretruth_flat_changed');clock()
        task=next(t for t in manifest['tasks'] if t['kind']==kind)
        for name,h in task['files'].items():
            need(digest(directory/name)==digest(local(task['source'])/name)==h,'pretruth_input_changed');clock()
        need(digest(directory/'retention.json')==digest(local(task['retention']['path']))==task['retention']['sha256']
             and digest(directory/'protected_control.json')==task['control_recipe']['sha256'],
             'pretruth_retention_or_control_changed')
        need(digest(directory/'authority-checkpoint.json')==checkpoint_ref['sha256'],'all4_checkpoint_bytes_must_match')
        authority=checkpoint['tasks'][kind]
        need(authority['task_sha256']==task['files']['task.md'] and authority['retention_sha256']==task['retention']['sha256']
             and authority['metric']['status']=='resolved' and authority['metric']['name']==('rmse' if kind=='regression' else 'macro_f1')
             and authority['feature_or_target_rows_parsed'] is False and authority['input_bytes_hashed'] is True,
             'checkpoint_task_metric_retention_binding_changed')
    frozen()
    # All FOUR complete code/source/core/usage seals validated before NumPy/R4/truth.
    spec=importlib.util.spec_from_file_location('_frozen_UAR_R4_adapter',local(plan['r4_adapter_path']))
    r4=importlib.util.module_from_spec(spec);spec.loader.exec_module(r4)
    r4.WORK,r4.REPO,r4.RUN_NAME=work,work/'alfa-hack-automl','repair4';rows={}
    for arm,kind,code in ORDER:
        key=arm+code;entry=entries[key];directory=root/arm/code;raw=None
        try:
            clock();r4.ROOT=root/arm;task=next(t for t in manifest['tasks'] if t['kind']==kind)
            report=load(directory/'automl_runs/repair4/report.json')
            raw=r4.verify_task(task,manifest['arms'][arm],plan,entry)
            need({'lightgbm','catboost','xgboost'}<=set(raw['successful_model_families']),'all_three_actual_families_required')
            need(Path(report['spec']['root']).resolve()==directory.resolve(),'spec_root_changed')
            retention=retention_proof(directory,task,report,raw,entry,r4,plan)
            caller=strict_proof(directory,arm,report,load(local(entry['seal']['path'])),work)
            # Exact lexical CSV ID comparison supplements the original R4 value/probability checks.
            identifier=report['spec']['id']
            def ids(path):
                with path.open('r',encoding='utf-8-sig',newline='') as stream:
                    reader=csv.DictReader(stream);return [row[identifier] for row in reader]
            need(ids(directory/'submission.csv')==ids(directory/'sample_submission.csv'),'final_lexical_ID_order_changed')
            rows[key]=dict(procedure_passed=raw['procedure_passed'],qualified_selected_cut_mean=raw['selected_cut_mean'] if raw['procedure_passed'] else None,
                errors=raw['errors'],raw_r4=raw,retention=retention,caller=caller,failed_metrics_zero_imputed=False)
        except Exception as exc:
            rows[key]=dict(procedure_passed=False,qualified_selected_cut_mean=None,errors=['R4_or_UAR_contract_failed'],
                exception_type=type(exc).__name__,contract_reason=str(exc) if isinstance(exc,AssertionError)
                    and re.fullmatch('[A-Za-z0-9_:+.-]{1,200}',str(exc)) else None,
                raw_r4=raw,failed_metrics_zero_imputed=False)
    passed=all(v['procedure_passed'] for v in rows.values());comparison=None
    if passed:
        comparison={kind:dict(A=rows['A'+code]['qualified_selected_cut_mean'],B=rows['B'+code]['qualified_selected_cut_mean'],
            delta_B_minus_A=rows['B'+code]['qualified_selected_cut_mean']-rows['A'+code]['qualified_selected_cut_mean'],
            higher_is_better=kind=='classification',historical_comparisons={a:rows[a+code]['raw_r4']['baseline_comparisons'] for a in ['A','B']})
            for kind,code in [('regression','r'),('classification','c')]}
    frozen()
    for arm,kind,code in ORDER:
        entry=entries[arm+code];directory=root/arm/code;seal=load(local(entry['seal']['path']))
        need(digest(local(entry['seal']['path']))==entry['seal']['sha256'] and digest(local(entry['supervisor_path']))==entry['supervisor_sha256'],'late_seal_or_supervisor_changed')
        for name,h in seal['files_sha256'].items():need(digest(local(name))==h,'late_core_changed');clock()
        for name,h in manifest['compiled_sha256'].items():need(digest(directory/name)==h,'late_flat_changed')
        task=next(t for t in manifest['tasks'] if t['kind']==kind)
        for name,h in task['files'].items():need(digest(directory/name)==digest(local(task['source'])/name)==h,'late_input_changed')
        need(digest(directory/'retention.json')==task['retention']['sha256']
             and digest(directory/'protected_control.json')==task['control_recipe']['sha256'],'late_retention_or_control_changed')
        need(digest(directory/'authority-checkpoint.json')==digest(local(checkpoint_ref['path']))==checkpoint_ref['sha256'],
             'late_authority_checkpoint_changed')
    clock();result=dict(schema='UAR-Qwen-pair-audit-v1',status='four_slots_verified_pending_root' if passed else 'four_slots_unqualified',
        slots=rows,artifact_procedure_checks_passed=passed,audit_within_original_common_clock=True,
        parent_exec_terminal_qualification_required=True,campaign_terminal_confirmed=False,
        manifest_sha256=args.manifest_sha256,verification_plan_sha256=args.plan_sha256,manual_metric_source_sha256=R4_SHA,
        r4_adapter_sha256=plan['r4_adapter_sha256'],comparison=comparison,descriptive_retention_win=None,
        quality_metric={k:v['qualified_selected_cut_mean'] for k,v in rows.items()} if passed else None,
        failed_metrics_zero_imputed=False,source_and_core_rechecked=True,new_model_fits=0,API_calls=0,tests_run=0,
        official_default_ready=False,promotion=False,submit=False,official_score=None,
        scope='Equal-budget genuine stochastic Qwen procedures. Same common strong retention; only strict caller differs. Reused public and full-training planner summaries remain limitations; no causal or release/default qualification.')
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False)
    clock();print(json.dumps(dict(status=result['status'],artifact_procedure_checks_passed=passed)))


if __name__=='__main__':main()

