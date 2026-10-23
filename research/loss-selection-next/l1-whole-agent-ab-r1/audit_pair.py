"""Future sealed four-slot R4 adapter; no model fits, API calls or default promotion."""
from pathlib import Path
import argparse,copy,hashlib,importlib.util,json,math,os,re,sys,time,zipfile
R4='repaired-mvp-r1-dev/evaluator_r4.py'
R4_SHA='c08e9f0be13a708d67b3266518381d6f1be3b0f43c384ef6425634160d7e2783'
CHAMPION_SHA='914880505ed751da9fd0a38d7f1724dd860c20d98456ff3efd16a195a0709ad4'
CHAMPION_SIGNATURE='959a9b8fed203d71bafbbd4770b6bfb5b6aa5da79d08ee568b93979d7f795421'
SEED_SHA='be704f101ae26938a786f4b8989b39dd2fe92258131a3e923b8fc48df4a9e2e5'
SEED_SIGNATURE='f06008802b5f6d3cfd130e4cd4c921781404560afac3cf3ddcbb58b1509295e4'
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


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['work-root','pair-root','manifest','manifest-sha256','plan','plan-sha256','self-sha256','output']:p.add_argument('--'+n,required=True)
    args=p.parse_args();need(__debug__,'nonoptimized_python_required');work=Path(args.work_root).resolve()
    def local(n):
        q=(work/n).resolve();need(not Path(n).is_absolute() and q.is_relative_to(work),'audit_reference_outside_work');return q
    root,output=local(args.pair_root),local(args.output)
    need(root==work/'la1' and output==root/'independent-audit.json' and not output.exists(),'exclusive_expected_output_required')
    need(digest(__file__)==args.self_sha256 and digest(local(args.manifest))==args.manifest_sha256
         and digest(local(args.plan))==args.plan_sha256,'explicit_audit_pins_required')
    manifest,plan,campaign=load(local(args.manifest)),load(local(args.plan)),load(root/'campaign.json')
    need(manifest['schema']=='L1-whole-agent-pair-v1' and manifest['caps']==CAPS and manifest['common_seconds']==10800
         and plan['common_seconds']==10800 and manifest['order']==plan['pair_order']==[a+c for a,k,c in ORDER], 'same_four_slot_plan_required')
    need(plan['verifier_source_sha256']==args.self_sha256 and plan['execution_manifest_sha256']==args.manifest_sha256
         and plan['manual_metric_verifier_path']==R4 and plan['manual_metric_verifier_sha256']==R4_SHA
         and digest(local(R4))==R4_SHA,'frozen_R4_required')
    need(campaign['manifest_sha256']==args.manifest_sha256 and campaign['verification_plan_sha256']==args.plan_sha256
         and campaign['absolute_deadline_unix']==plan['original_absolute_deadline_unix']
         and campaign['start_unix']==plan['original_common_start_unix']
         and abs(campaign['absolute_deadline_unix']-campaign['start_unix']-10800)<=1e-6
         and abs(campaign['common_deadline_monotonic']-campaign['start_monotonic']-10800)<=1e-6
         and campaign['status']=='verifying' and campaign['cleanup_confirmed'] is True and campaign['source_unchanged'] is True,
         'closed_four_slots_original_clock_required')
    def clock():need(time.time()<campaign['absolute_deadline_unix'] and time.monotonic()<campaign['common_deadline_monotonic'],'original_audit_clock_exhausted')
    def frozen():
        clock()
        need(digest(__file__)==args.self_sha256 and digest(local(args.manifest))==args.manifest_sha256
             and digest(local(args.plan))==args.plan_sha256,'audit_authority_changed')
        for n,h in manifest['immutable_files'].items():need(digest(local(n))==h,'frozen_source_or_input_changed');clock()
    entries={v['slot']:v for v in campaign['arms']}
    need(len(campaign['arms'])==4 and set(entries)==set(manifest['order']),'all_four_unique_slots_required')
    need(manifest['slots']['Br']['argv']==manifest['slots']['Ar']['argv']+['--loss-seed-l1']
         and manifest['slots']['Ac']['argv']==manifest['slots']['Bc']['argv'],'only_Breg_L1_flag_difference_required')
    for arm,kind,code in ORDER:
        key=arm+code;entry=entries[key];meta=manifest['arms'][arm];cfg=CAPS[kind];directory=root/arm/code
        need(campaign['actual_arm_argv'][key]==manifest['slots'][key]['argv'],'actual_frozen_argv_changed')
        need(entry['task_allocation_seconds']==cfg['parent'] and entry['parent_cap_seconds']==cfg['parent']
             and entry['child_cap_seconds']==cfg['child'] and entry['solver_budget_seconds']==cfg['solver']
             and entry['requested_hpo_budget_seconds']==cfg['hpo'],'same_declared_task_caps_required')
        need(digest(local(entry['supervisor_path']))==entry['supervisor_sha256'],'saved_supervisor_changed')
        terminal=load(local(entry['supervisor_path']))
        need(all(terminal.get(k)==v for k,v in entry.items() if k in terminal),'inline_saved_supervisor_changed')
        need(terminal['cleanup_confirmed'] is True and terminal['cleanup_observation']['unresolved']==[],'terminal_clean_required')
        need(digest(local(entry['seal']['path']))==entry['seal']['sha256'],'prelabel_seal_changed');seal=load(local(entry['seal']['path']))
        need(seal['slot']==key and seal['arm']==arm and seal['kind']==kind and seal['cleanup_confirmed'] is True
             and seal['source_unchanged'] is True and seal['sealed_before_independent_label_scoring'] is True,'prelabel_seal_contract_changed')
        actual={};runs=directory/'automl_runs/repair4'
        if runs.exists():
            for parent,dirs,files in os.walk(runs):
                need(not any((Path(parent)/n).is_symlink() for n in [*dirs,*files]),'sealed_symlink')
                for n in files:
                    need(not n.endswith(('.tmp','.pending')),'unfinished_core');q=Path(parent)/n;actual[q.relative_to(work).as_posix()]=digest(q)
        if (directory/'submission.csv').exists():actual[(directory/'submission.csv').relative_to(work).as_posix()]=digest(directory/'submission.csv')
        need(actual==seal['files_sha256'],'complete_core_inventory_changed')
        need(meta['archive']==manifest['archive'] and meta['archive_sha256']==manifest['archive_sha256']
             and meta['compiled_sha256']==manifest['compiled_sha256'] and digest(local(meta['archive']))==meta['archive_sha256'],'same_archive_both_arms_required')
        with zipfile.ZipFile(local(meta['archive'])) as z:
            need(len(z.namelist())==len(set(z.namelist()))==68
                 and {n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}==meta['compiled_sha256'],'archive_member_changed')
    frozen()
    # First numerical/data import and label parsing occurs only after ALL FOUR complete seals.
    spec=importlib.util.spec_from_file_location('_frozen_R4_L1_AB_library',local(R4));r4=importlib.util.module_from_spec(spec);spec.loader.exec_module(r4)
    r4.WORK,r4.REPO,r4.RUN_NAME=work,work/'alfa-hack-automl','repair4'
    rows={}
    for arm,kind,code in ORDER:
        key=arm+code;entry=entries[key];meta=manifest['arms'][arm];directory=root/arm/code;raw=None
        if entry.get('status')!='ok' or entry.get('exit_code')!=0:
            rows[key]=dict(procedure_passed=False,qualified_selected_cut_mean=None,errors=['whole_agent_nonzero_or_not_ok'],raw_r4=None)
            continue
        try:
            clock();r4.ROOT=root/arm;task=next(t for t in meta['tasks'] if t['kind']==kind)
            raw=r4.verify_task(task,meta,plan,entry);runs=directory/'automl_runs/repair4';report=load(runs/'report.json')
            need(Path(report['spec']['root']).resolve()==directory.resolve(),'spec_root_changed')
            need({'lightgbm','catboost','xgboost'}<=set(raw['successful_model_families']),'all_three_actual_families_required')
            hpo=load(runs/'inner-hpo/hpo.json');counts=hpo_counts(hpo)
            protected=load(local(plan['protected_control_recipes'][kind]['path']))
            need(hpo['control_recipe']==protected['components'][0],'exact_unprofiled_SINGLE_HPO_anchor_changed')
            cfg=CAPS[kind];reserve=min(1200,max(60,cfg['solver']*.2));remaining=entry.get('hpo_first_worker_remaining_lower_bound_seconds')
            need(entry.get('hpo_full_budget_observed') is True and type(remaining) in (int,float) and math.isfinite(remaining)
                 and remaining>=reserve+cfg['hpo']+30,'complete_HPO_window_not_independently_observed')
            need(len(report['experiments'])<=9,'max9_changed')
            train,test,sample=[r4.pd.read_csv(directory/n) for n in ['train.csv','test.csv','sample_submission.csv']]
            verifier=r4.TaskVerifier(directory,report,train,test,sample)
            champion_measurements=None;seed_measurements=None;loss_proofs=[]
            if kind=='regression':
                for phase in ['primary','confirmation']:
                    expected=plan['expected_regression_splits'][phase]
                    need(all(raw['cuts'][phase][k]==expected[k] for k in ['fitting_rows','validation_rows','positions_sha256',
                        'training_rows_canonical_sha256','split_file_sha256','validation_periods']),'fixed_regression_cut_changed')
                need(digest(directory/'champion_recipe_input.json')==CHAMPION_SHA==plan['expected_champion_input_sha256'],'champion_input_changed')
                champion=load(directory/'champion_recipe_input.json')
                need(report['champion_recipe']==champion==load(runs/'champion_recipe.json'),'champion_snapshot_changed')
                provenance=load(runs/'provenance.json')['sha256'];receipt=load(runs/'champion-seed.json')
                need(provenance['champion_recipe']==CHAMPION_SHA and provenance['champion_recipe_snapshot']==digest(runs/'champion_recipe.json')
                     and receipt['recipe_signature']==CHAMPION_SIGNATURE and report['pipeline']['champion_seed']['maximum_initial']==7,'champion_provenance_changed')
                admissions=[v for v in report['pipeline']['initial_queue_receipts'] if v.get('source')=='prior_champion']
                need(len(admissions)==1 and admissions[0]['status']=='scheduled' and admissions[0]['queue_index']==5
                     and admissions[0]['signature']==CHAMPION_SIGNATURE,'champion_required_slot5_missing')
                champion_measurements={}
                for phase,file in [('primary','split.npz'),('confirmation','confirmation_split.npz')]:
                    record=report['champion_measurements'][phase]
                    if phase=='primary':need(record is not None and record['status']=='ok' and record.get('experiment_index')==5,'actual_champion_primary_missing')
                    if record is not None:
                        need(record['recipe']==champion and record['status']=='ok','champion_measurement_changed')
                        champion_measurements[phase]=r4.diagnostics(verifier,record,runs/file,phase)
                    else:champion_measurements[phase]=None
                if arm=='B':
                    expected=copy.deepcopy(protected['components'][0]);expected['params']['loss_profile_id']='lgbm_l1_v1'
                    need(digest(local(manifest['fixed_L1']['path']))==SEED_SHA and load(local(manifest['fixed_L1']['path']))==expected,'fixed_raw_L1_package_changed')
                    need(report['loss_seed_recipe']==expected==load(runs/'loss_seed_recipe.json'),'L1_snapshot_or_report_changed')
                    seed=load(runs/'loss-seed.json');pipeline=report['pipeline']['loss_seed']
                    need(seed['loss_profile_id']=='lgbm_l1_v1' and seed['recipe_signature']==SEED_SIGNATURE
                         and seed['changed_parameters']==['loss_profile_id'] and seed['metric'] is None
                         and seed['snapshot_sha256']==provenance['loss_seed_recipe_snapshot']==digest(runs/'loss_seed_recipe.json')
                         and pipeline['recipe_signature']==SEED_SIGNATURE and pipeline['maximum_initial']==7
                         and pipeline['hpo_anchor_unchanged'] is True,'fixed_L1_constructor_provenance_changed')
                    admissions=[v for v in report['pipeline']['initial_queue_receipts'] if v.get('source')=='fixed_regression_loss_seed']
                    need(len(admissions)==1 and admissions[0]['status']=='scheduled' and admissions[0]['queue_index']==6
                         and admissions[0]['signature']==SEED_SIGNATURE,'fixed_L1_required_slot6_missing')
                    seed_measurements={}
                    for phase,file in [('primary','split.npz'),('confirmation','confirmation_split.npz')]:
                        record=report['loss_seed_measurements'][phase]
                        if phase=='primary':need(record is not None and record['status']=='ok' and record.get('experiment_index')==6,'successful_L1_primary_missing')
                        if record is not None:
                            need(record['recipe']==expected and record['status']=='ok','L1_measurement_reference_changed')
                            checked=r4.diagnostics(verifier,record,runs/file,phase)
                            checked['loss']=loss_telemetry(record,expected,verifier,r4,runs/file);seed_measurements[phase]=checked
                        else:seed_measurements[phase]=None
                else:
                    need('loss_seed_recipe' not in report and 'loss_seed' not in report['pipeline']
                         and not (runs/'loss-seed.json').exists(),'A_has_fixed_L1_treatment')
                for path in sorted(runs.rglob('result.json')):
                    record=load(path);recipe=record.get('recipe') or {}
                    if record.get('status')!='ok' or record.get('components') or not recipe.get('params',{}).get('loss_profile_id'):continue
                    parts=path.relative_to(runs).parts;full=record.get('full_fit') is True
                    partition=runs/('inner-hpo/split.npz' if parts[0]=='inner-hpo' else 'confirmation_split.npz' if parts[0].startswith('confirmation-') or parts[0]=='ensemble-confirmation' else 'split.npz')
                    phase='final' if full else 'inner' if parts[0]=='inner-hpo' else 'confirmation' if 'confirmation' in partition.name else 'primary'
                    verifier.verify(dict(record,output_dir=str(path.parent)),partition,phase,full,recipe)
                    loss_proofs.append(dict(path=path.relative_to(runs).as_posix(),proof=loss_telemetry(record,recipe,verifier,r4,partition)))
            else:
                need(not (directory/'champion_recipe_input.json').exists() and 'champion_recipe' not in report
                     and 'loss_seed_recipe' not in report and 'loss_seed' not in report['pipeline'],'classification_treatment_must_remain_OFF')
            rows[key]=dict(procedure_passed=raw['procedure_passed'],qualified_selected_cut_mean=raw['selected_cut_mean'] if raw['procedure_passed'] else None,
                errors=list(raw.get('errors',[])),raw_r4=raw,champion_measurements=champion_measurements,L1_seed_measurements=seed_measurements,
                loss_profile_fits=loss_proofs,HPO_accounting=counts,actual_HPO_call_monotonic=None,actual_effective_HPO_deadline=None,
                HPO_availability_scope='Conservative first observed HPO worker; actual optimize_recipe call/deadline not emitted by frozen source.',
                actual_initial_queue_receipts=report['pipeline']['initial_queue_receipts'],failed_metrics_zero_imputed=False)
        except Exception as exc:
            trace=exc.__traceback__
            while trace is not None and trace.tb_next is not None:trace=trace.tb_next
            reason=str(exc)
            rows[key]=dict(procedure_passed=False,qualified_selected_cut_mean=None,errors=['R4_or_L1_pair_contract_failed'],
                exception_type=type(exc).__name__,contract_reason=reason if isinstance(exc,AssertionError) and re.fullmatch('[A-Za-z0-9_:+.-]{1,200}',reason) else None,
                errno=getattr(exc,'errno',None),winerror=getattr(exc,'winerror',None),failure_source_basename=Path(trace.tb_frame.f_code.co_filename).name if trace else None,
                failure_source_line=trace.tb_lineno if trace else None,raw_r4=raw,failed_metrics_zero_imputed=False)
    passed=all(v['procedure_passed'] for v in rows.values());comparison=None;win=None
    if passed:
        comparison={};toler=plan['reproduction_absolute_tolerance']
        for kind,code in [('regression','r'),('classification','c')]:
            a,b=rows['A'+code]['raw_r4'],rows['B'+code]['raw_r4'];cuts=[]
            for phase in ['primary','confirmation']:
                av,bv=a['cuts'][phase]['value'],b['cuts'][phase]['value'];item=dict(phase=phase,A=av,B=bv,delta_B_minus_A=bv-av)
                need(all(type(v) in (int,float) and math.isfinite(v) for v in [av,bv]),'nonfinite_cut')
                if kind=='regression':
                    floor=plan['T5_cut_floors'][phase+'_rmse'];item.update(B_no_worse_than_A=bv<=av+toler,retained_CP1_T5_floor=floor,B_meets_retained_floor=bv<=floor+toler)
                else:
                    ac,bc=a['cuts'][phase],b['cuts'][phase]
                    need(ac['independent_fitting_groups']==bc['independent_fitting_groups'] and ac['rarest_fitting_class']==bc['rarest_fitting_class'],'matched_feature_group_support_changed')
                    deltas={c:bc['per_class_f1'][c]-ac['per_class_f1'][c] for c in ac['per_class_f1']};rare=ac['rarest_fitting_class']
                    item.update(per_class_delta=deltas,supported_losses_over_001=[c for c,d in deltas.items() if ac['independent_fitting_groups'][c]>=100 and d<-.01],
                                ex_rarest_delta=sum(d for c,d in deltas.items() if c!=rare)/(len(deltas)-1),B_no_worse_than_A=bv>=av-toler)
                cuts.append(item)
            comparison[kind]=dict(cuts=cuts,A_mean=a['selected_cut_mean'],B_mean=b['selected_cut_mean'],delta_B_minus_A=b['selected_cut_mean']-a['selected_cut_mean'])
        reg=comparison['regression'];win=reg['B_mean']<reg['A_mean'] and all(c['B_no_worse_than_A'] and c['B_meets_retained_floor'] for c in reg['cuts'])
    frozen()
    for arm,kind,code in ORDER:
        key=arm+code;entry=entries[key];directory=root/arm/code;seal=load(local(entry['seal']['path']))
        need(digest(local(entry['seal']['path']))==entry['seal']['sha256'] and digest(local(entry['supervisor_path']))==entry['supervisor_sha256'],'late_seal_or_supervisor_changed')
        for n,h in seal['files_sha256'].items():need(digest(local(n))==h,'late_core_changed');clock()
        for n,h in manifest['compiled_sha256'].items():need(digest(directory/n)==h,'late_flat_changed')
        task=next(t for t in manifest['tasks'] if t['kind']==kind)
        for n,h in task['files'].items():need(digest(directory/n)==digest(local(task['source'])/n)==h,'late_input_changed')
        need(digest(directory/'protected_control.json')==task['control_recipe']['sha256'],'late_control_changed')
        if kind=='regression':need(digest(directory/'champion_recipe_input.json')==CHAMPION_SHA,'late_champion_changed')
    clock()
    result=dict(status='four_slot_artifacts_verified_pending_parent_terminal' if passed else 'four_slot_artifacts_unqualified_pending_parent_terminal',
        slots=rows,artifact_procedure_checks_passed=passed,audit_within_original_common_clock=True,campaign_terminal_confirmed=False,
        parent_exec_terminal_qualification_required=True,actual_common_deadline_satisfied=None,manifest_sha256=args.manifest_sha256,
        verification_plan_sha256=args.plan_sha256,campaign_sha256=digest(root/'campaign.json'),manual_metric_source_sha256=R4_SHA,
        comparison=comparison,descriptive_retention_win=win,quality_metric={k:v['qualified_selected_cut_mean'] for k,v in rows.items()} if passed else None,
        failed_metrics_zero_imputed=False,source_and_core_rechecked=True,new_model_fits=0,API_calls=0,tests_run=0,
        official_default_ready=False,promotion=False,submit=False,official_score=None,
        scope='Four complete stochastic procedures on reused public; fixed L1 admission factor only. Separate source/ownership/clock closure and later standard-command qualification required.')
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False)
    clock();print(json.dumps(dict(status=result['status'],artifact_procedure_checks_passed=passed,descriptive_retention_win=win)))

if __name__=='__main__':main()
