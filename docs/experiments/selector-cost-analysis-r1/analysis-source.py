"""Read terminal cost/selector metadata only; no outer scoring or fitting."""
from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,math,statistics
import numpy as np

WORK=Path(__file__).resolve().parent
REPO=WORK/'alfa-hack-automl'
OUT=WORK/'hpo-selector-cost-audit-r1'
SOURCES={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p):return p.resolve().relative_to(WORK.resolve()).as_posix()
def load(p):
    SOURCES[rel(p)]=sha(p)
    return json.loads(p.read_text(encoding='utf-8'))
def canonical(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')).hexdigest()
def split_info(job,root):
    path=Path(job['split_path']).resolve()
    if not path.is_relative_to(root.resolve()):raise ValueError('Split outside authorized terminal root')
    SOURCES[rel(path)]=sha(path)
    with np.load(path,allow_pickle=False) as stored:
        rows=stored['train'].copy()
    return {'file':rel(path),'file_sha256':sha(path),'row_count':len(rows),'ordered_rows_canonical_sha256':canonical(rows.tolist())}
def leaves(root):
    for p in sorted(root.rglob('result.json')):
        if any(x.startswith('run-budget-') for x in p.parts):raise ValueError('Private ledger unexpectedly in allowed scope')
        result=load(p)
        if result.get('status')=='ok' and result.get('data_policy_runs'):
            yield p,result
def job_subset(job,result):
    p=result['recipe'].get('params',{})
    names=['generic_features','target_encoding','target_encoding_auto_groups','target_encoding_groups',
      'target_encoding_smoothing','target_encoding_counts','target_encoding_half_life','target_encoding_refine_groups',
      'target_encoding_hierarchical','log_target','class_weight_power','class_weight_cap','feature_selection_top_k',
      'feature_selection_protect_original','seed','history_asof','history_minimum_periods']
    return {'kind':job['spec']['kind'],'threads':job['threads'],'selector_importance_cache':job.get('selector_importance_cache',False),
      'selector_affecting_recipe_subset':{k:p[k] for k in names if k in p},
      'teacher_static_constructor_recipe':{'depth':5,'learning_rate':.08,'seed':p.get('seed',42),'early_metric':'default','iterations':100}}
def summarize_worker(root,top_job,parent_status,supervised_seconds,group):
    job=load(top_job);split=split_info(job,root.parent if group.startswith('tm1') else root)
    rows=[];leaf_stats=[]
    for p,result in leaves(root):
        fingerprint=job_subset(job,result)
        leaf_id=rel(p.parent)
        leaf_rows=[]
        for index,policy in enumerate(result['data_policy_runs']):
            selection=policy.get('feature_selection')
            if not selection:continue
            selected=selection.get('selected_columns',[])
            match=policy.get('source_parent_sha256')==split['ordered_rows_canonical_sha256']
            signature={'source_parent_sha256':policy.get('source_parent_sha256'),'source_rows':policy.get('source_rows'),
                'weights_source':policy.get('weights_source'),'effective_weight_sum':policy.get('effective_weight_sum'),
                'policy':policy.get('policy'),'target_encoding_groups':policy.get('target_encoding_groups'),
                'fitting_rows':selection.get('fitting_rows'),'input_columns':selection.get('input_columns'),
                'selected_columns_sha256':canonical(selected),'selected_columns_count':len(selected),
                'method':selection.get('method'),'teacher_iterations':selection.get('iterations'),
                'static_fingerprint':fingerprint}
            item={'leaf':leaf_id,'policy_index':index,'record_sha256':SOURCES[rel(p)],'parent_worker_status':parent_status,
                'teacher_fitted':selection.get('teacher_fitted'),'selector_seconds':selection.get('selector_seconds'),
                'metadata_signature_sha256':canonical(signature),'saved_scope':signature,
                'ordered_scope_verified_against_saved_job_train_rows':match,
                'actual_prepared_teacher_X_y_weights_key':None,'pure_teacher_fit_seconds':None}
            leaf_rows.append(item);rows.append(item)
        leaf_stats.append({'path':leaf_id,'result_sha256':SOURCES[rel(p)],'status':'ok','wall_seconds':result.get('wall_seconds'),
            'selector_calls':len(leaf_rows),'teacher_fitted_calls':sum(x['teacher_fitted'] is True for x in leaf_rows),
            'selector_seconds':round(sum(x['selector_seconds'] for x in leaf_rows if isinstance(x['selector_seconds'],(int,float))),6)})
    within=[]
    for leaf in leaf_stats:
        groups=defaultdict(list)
        for row in rows:
            if row['leaf']==leaf['path'] and row['teacher_fitted'] is True:groups[row['metadata_signature_sha256']].append(row)
        for key,items in groups.items():
            if len(items)>1:within.append({'leaf':leaf['path'],'metadata_signature_sha256':key,'calls':len(items),
                'policy_indices':[x['policy_index'] for x in items],
                'repeated_after_first_selector_seconds':round(sum(x['selector_seconds'] for x in items[1:]),6),
                'full_exact_teacher_input_equivalence':None})
    total=sum(x['selector_seconds'] for x in rows if isinstance(x['selector_seconds'],(int,float)))
    return {'worker':rel(root),'parent_status':parent_status,'supervised_or_reported_worker_seconds':supervised_seconds,
        'leaf_wall_seconds_sum':round(sum(x['wall_seconds'] for x in leaf_stats),6),'saved_job_train_scope':split,
        'selector_calls':len(rows),'teacher_fitted_calls':sum(x['teacher_fitted'] is True for x in rows),
        'selector_seconds_sum':round(total,6),'selector_fraction_of_supervised_or_reported_worker_seconds':total/supervised_seconds if supervised_seconds else None,
        'completed_leaf_records':leaf_stats,'within_leaf_metadata_repeats':within,'selector_records':rows}

def main():
    OUT.mkdir(exist_ok=False)
    hpo={};fe={}
    for task in ['r','c']:
        root=REPO/f'test-runs/tm1/{task}/automl_runs/true4/inner-hpo';ledger=load(root/'hpo.json')
        if ledger['status']!='ok':raise ValueError('Nonterminal HPO ledger')
        workers=[]
        for trial in ledger['trials']:
            directory=root/f"trial-{trial['number']:02d}"
            workers.append(summarize_worker(directory,directory/'job.json',trial['status'],trial.get('seconds'),'tm1_'+task))
        successful=[x for x in workers if x['parent_status']=='ok'];failed=[x for x in workers if x['parent_status']!='ok']
        hpo[task]={'hpo_json_sha256':SOURCES[rel(root/'hpo.json')],'hpo_terminal_status':ledger['status'],
            'sampler':ledger['sampler'],'maximum_trials':ledger['maximum_trials'],'startup_trials':ledger['startup_trials'],
            'whole_inner_hpo_seconds':ledger['seconds'],'trial_status_counts':dict(Counter(x['parent_status'] for x in workers)),
            'successful_trial_reported_seconds_sum':round(sum(x['supervised_or_reported_worker_seconds'] for x in successful),6),
            'all_attempted_trial_reported_seconds_sum':round(sum(x['supervised_or_reported_worker_seconds'] for x in workers),6),
            'successful_trial_teacher_calls':sum(x['teacher_fitted_calls'] for x in successful),
            'successful_trial_selector_seconds_sum':round(sum(x['selector_seconds_sum'] for x in successful),6),
            'failed_parent_completed_leaf_selector_seconds_sum':round(sum(x['selector_seconds_sum'] for x in failed),6),
            'successful_trial_selector_fraction':sum(x['selector_seconds_sum'] for x in successful)/sum(x['supervised_or_reported_worker_seconds'] for x in successful),
            'known_selector_seconds_fraction_of_whole_study':sum(x['selector_seconds_sum'] for x in workers)/ledger['seconds'],
            'failed_parent_selector_coverage':'Only already terminal successful child result records; interrupted/unsaved calls unknown, not zero.',
            'workers':workers}
    for task in ['regression','classification']:
        root=REPO/f'test-runs/2e/fe-{task}';ledger=load(root/'results.json');workers=[]
        for row in ledger['results']:
            directory=Path(row['directory']).resolve()
            if not directory.is_relative_to(root.resolve()):raise ValueError('FE worker outside terminal FE scope')
            if row['status'] not in ['ok','timeout','error','crash']:raise ValueError('Nonterminal FE worker')
            item=summarize_worker(directory,directory/'job.json',row['status'],row['seconds'],'fe_'+task)
            item.update(candidate=row['name'],cut=row['seed']);workers.append(item)
        fe[task]={'results_sha256':SOURCES[rel(root/'results.json')],'workers':workers,'candidate_totals':{}}
        for candidate in sorted({x['candidate'] for x in workers}):
            items=[x for x in workers if x['candidate']==candidate]
            seconds=sum(x['supervised_or_reported_worker_seconds'] for x in items);selector=sum(x['selector_seconds_sum'] for x in items)
            fe[task]['candidate_totals'][candidate]={'workers':len(items),'status_counts':dict(Counter(x['parent_status'] for x in items)),
                'supervised_worker_seconds_sum':round(seconds,6),'successful_leaf_wall_seconds_sum':round(sum(x['leaf_wall_seconds_sum'] for x in items),6),
                'teacher_fitted_calls':sum(x['teacher_fitted_calls'] for x in items),'selector_seconds_sum':round(selector,6),
                'selector_fraction_of_supervised_worker_seconds':selector/seconds,
                'within_leaf_metadata_repeat_groups':sum(len(x['within_leaf_metadata_repeats']) for x in items),
                'repeated_after_first_selector_seconds':round(sum(g['repeated_after_first_selector_seconds'] for x in items for g in x['within_leaf_metadata_repeats']),6)}
    all_workers=[x for value in hpo.values() for x in value['workers']]+[x for value in fe.values() for x in value['workers']]
    across={}
    for task,value in hpo.items():
        groups=defaultdict(list)
        for worker in value['workers']:
            if worker['parent_status']!='ok':continue
            for row in worker['selector_records']:
                if row['teacher_fitted'] is True:groups[row['metadata_signature_sha256']].append(row)
        repeated=[]
        for key,items in groups.items():
            if len({x['leaf'] for x in items})>1:
                repeated.append({'metadata_signature_sha256':key,'calls':len(items),'distinct_leaf_workers':len({x['leaf'] for x in items}),
                    'selector_seconds_sum':round(sum(x['selector_seconds'] for x in items),6),
                    'ordered_scope_verified_against_saved_job_train_rows':all(x['ordered_scope_verified_against_saved_job_train_rows'] for x in items),
                    'input_columns':items[0]['saved_scope']['input_columns'],'fitting_rows':items[0]['saved_scope']['fitting_rows'],
                    'selected_columns_sha256':items[0]['saved_scope']['selected_columns_sha256'],
                    'actual_prepared_teacher_equivalence':None,'cacheability_under_existing_worker_local_prototype':False})
        across[task]=repeated
    refs=['src/automl/execution/worker.py','src/automl/execution/feature_engineering/selection.py',
        'src/automl/execution/sampling/policies.py','src/automl/execution/model_adapters/catboost.py','src/automl/search/hpo.py']
    for name in refs:SOURCES[rel(REPO/name)]=sha(REPO/name)
    for name in ['selector-cache-prototype.json','selector-cache-card.md','selector-cache-mock-checks-r1/results.json',
       'iteration3-campaign-plan-r1/coordinator-plan.json','iteration3-campaign-plan-r1/future-selector-cache-card.json',
       'iteration3-dev/docs/experiments/hpo_admission_b_protocol_20261023-r2.json']:
        SOURCES[name]=sha(WORK/name)
    unchanged=all(sha(WORK/name)==expected for name,expected in SOURCES.items())
    if not unchanged:raise ValueError('Terminal evidence changed while reading')
    report={'status':'terminal_cost_metadata_analysis_only','tm1_hpo':hpo,'completed_2e_FE':fe,
      'across_successful_hpo_callbacks_metadata_repeats':across,'source_sha256':SOURCES,'all_read_evidence_unchanged':unchanged,
      'equality_boundary':{'proven':'Exact saved JSON field/signature equality. Where flagged, parent-row ordered canonical SHA matches actual saved job split train array.',
        'not_proven':['Complete actual CatBoost-prepared fitting X values/index/dtypes/category metadata/order','Fitting transformed y values/index','Ordered sample-weight vector','Actual effective CatBoost constructor/library identity receipt','Pure teacher.fit timing'],
        'actual_exact_teacher_input_groups':None,'cache_hits_proven':0,'measured_cache_savings_seconds':None,
        'same_parent_rows_and_selected_columns_are_insufficient':True},
      'timing_boundary':'selector_seconds times complete select_features call including preparation, teacher fit, ranking and slicing; not pure CatBoost cost. Sums do not establish avoidable time or actual cache savings. Failed/interrupted work remains unknown where no terminal receipt exists.',
      'fits':0,'API_calls':0,'network_calls':0,'tests_run':0,'current_outer_metrics_read_or_scored':False,'private_API_ledger_access':False,
      'canonical_or_frozen_edits':False,'promotion':False}
    (OUT/'observations.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8'))
    compact={'hpo':{k:{n:v[n] for n in ['whole_inner_hpo_seconds','trial_status_counts','successful_trial_teacher_calls','successful_trial_selector_seconds_sum','failed_parent_completed_leaf_selector_seconds_sum','successful_trial_selector_fraction','known_selector_seconds_fraction_of_whole_study']} for k,v in hpo.items()},
        'FE':{k:v['candidate_totals'] for k,v in fe.items()},'cross_hpo_metadata_repeat_groups':{k:len(v) for k,v in across.items()},
        'within_hpo_repeats':{k:[g for x in v['workers'] for g in x['within_leaf_metadata_repeats']] for k,v in hpo.items()},
        'report_sha256':sha(OUT/'observations.json'),'read_files':len(SOURCES)}
    print(json.dumps(compact,indent=2,allow_nan=False))
if __name__=='__main__':main()
