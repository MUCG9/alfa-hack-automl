"""Frozen dev-only CPU procedure. Not a production adapter or contest module.

Dispatched by benchmark_candidates --worker-extension; ordinary controls run the
original compiled worker. Imports below resolve beside the frozen copied script.
"""
from pathlib import Path
import hashlib,importlib.metadata,json,random,resource,sys,time
import numpy as np
import pandas as pd

from automl_atomic import atomic_json
from automl_infrastructure_tables import read_input_table,read_task_sample
from automl_evaluation import make_split,evaluate
from automl_callbacks import tune_class_factors,adjusted_probabilities
from automl_publishing import save_submission
from automl_contracts_messages import SplitPlan,DataPolicy


def run(job):
    recipe=job['recipe']
    if recipe.get('engine')!='autogluon':
        from automl_worker import run as original
        return original(job)
    start=time.monotonic();spec=job['spec'];out=Path(job['output_dir'])
    if importlib.metadata.version('autogluon.tabular')!='1.3.1':
        raise ValueError('Research protocol requires pinned AutoGluon1.3.1')
    if (spec['kind']!='classification' or spec['metric']!='macro_f1'
            or spec.get('text_features') or spec.get('task_family')=='pointwise_ranking'):
        raise ValueError('Research protocol requires nontext MacroF1 classification')
    if recipe.get('feature_code') or not DataPolicy.parse(recipe.get('data_policy')).is_noop or set(recipe.get('params',{}))-{'seed'}:
        raise ValueError('No extra treatment parameters/feature code/data policy allowed')
    seed=recipe.get('params',{}).get('seed',42)
    if type(seed) is not int or seed!=42:raise ValueError('Frozen protocol seed42 required')
    if 'fit_iterations' in job:raise ValueError('This research procedure has no runtime iteration-tree contract')
    threads=job['threads']
    if type(threads) is not int or not 1<=threads<=8:raise ValueError('Invalid CPU count')
    random.seed(seed);np.random.seed(seed)
    train=read_input_table(spec['paths']['train']);test=read_input_table(spec['paths']['test'])
    sample=read_task_sample(spec);split=np.load(job['split_path'])
    tr,va=split['train'],split['validation'];SplitPlan(tuple(tr.tolist()),tuple(va.tolist())).validate(len(train))
    full=job.get('full_fit',False);rows=np.arange(len(train)) if full else tr
    fitting=train.iloc[rows].reset_index(drop=True)
    hashes=pd.util.hash_pandas_object(fitting[spec['features']],index=False).to_numpy(dtype='uint64')
    inner_tr,inner_va,inner_info=make_split(spec,fitting,hashes,seed=73)
    if set(hashes[inner_tr])&set(hashes[inner_va]):
        raise ValueError('Research calibration split has overlapping feature groups')
    if set(fitting[spec['target']].iloc[inner_tr].astype(str))!=set(spec['classes']):
        raise ValueError('Inner fitting rows do not support all declared classes')
    x=fitting[spec['features']].copy();queries=test[spec['features']].copy()
    outer=train[spec['features']].iloc[va].copy() if not full else None
    for column in spec.get('categorical_features',[]):
        for frame in [x,queries]+([outer] if outer is not None else []):
            frame[column]=frame[column].fillna('__MISSING__').astype(str)
    y=fitting[spec['target']].astype(str)
    labeled=x.copy();labeled[spec['target']]=y
    from autogluon.tabular import TabularPredictor
    from autogluon.features.generators import AutoMLPipelineFeatureGenerator
    # Pinned default learner concatenates train+tuning before feature generation.
    # An already-fitted generator takes its transform-only path instead.
    generator=AutoMLPipelineFeatureGenerator(enable_text_special_features=False,
        enable_text_ngram_features=False,enable_raw_text_features=False,enable_vision_features=False)
    generator.fit_transform(x.iloc[inner_tr].copy())
    if not generator.is_fit():raise ValueError('Feature generator did not complete fitting')
    predictor=TabularPredictor(label=spec['target'],
        problem_type='multiclass' if len(spec['classes'])>2 else 'binary',
        eval_metric='f1_macro',path=str(out/'ag-models'),verbosity=0,
        learner_kwargs={'label_count_threshold':1})
    hyperparameters={
        'GBM':{'num_boost_round':1200,'learning_rate':.04,'num_leaves':63,
            'min_data_in_leaf':25,'lambda_l2':5,'feature_fraction':.9,'seed':42},
        'CAT':{'iterations':600,'depth':6,'learning_rate':.07,'l2_leaf_reg':5,'random_seed':42}}
    predictor.fit(labeled.iloc[inner_tr],tuning_data=labeled.iloc[inner_va],
        hyperparameters=hyperparameters,feature_generator=generator,
        time_limit=450,num_bag_folds=0,num_stack_levels=0,
        fit_weighted_ensemble=True,dynamic_stacking=False,fit_strategy='sequential',
        num_cpus=threads,num_gpus=0,calibrate=False,calibrate_decision_threshold=False,
        raise_on_model_failure=True,refit_full=False)
    selected=predictor.model_best
    def aligned(frame,model):
        probabilities=predictor.predict_proba(frame,model=model,as_pandas=True)
        lookup={str(c):c for c in probabilities.columns}
        if set(lookup)!=set(spec['classes']):raise ValueError('AutoGluon class channels mismatch')
        values=probabilities[[lookup[c] for c in spec['classes']]].to_numpy(dtype=float)
        if not np.isfinite(values).all() or (values<0).any() or not np.allclose(values.sum(axis=1),1.,atol=1e-6):
            raise ValueError('Invalid AutoGluon probability output')
        return values
    inner_probabilities=aligned(x.iloc[inner_va],selected)
    factors=tune_class_factors(y.iloc[inner_va],inner_probabilities,spec['classes'])
    mapping=predictor.refit_full(model=selected,set_best_to_refit_full=False,
        num_cpus=threads,num_gpus=0,fit_strategy='sequential')
    if selected not in mapping:raise ValueError('Missing selected model full refit')
    refitted=mapping[selected]
    probabilities=adjusted_probabilities(aligned(queries,refitted),spec['classes'],factors)
    classes=np.asarray(spec['classes'])
    predictions=classes[probabilities.argmax(axis=1)]
    if spec.get('prediction_type')=='probability_matrix':
        predictions=probabilities[:,[list(classes).index(c) for c in spec['output_columns']]]
    elif spec.get('prediction_type','value')!='value':raise ValueError('Unsupported research publication type')
    save_submission(spec,sample,test,predictions,out/'submission.csv')
    np.savez_compressed(out/'test_probabilities.npz',probabilities=probabilities,classes=classes)
    metrics=None
    if not full:
        values=adjusted_probabilities(aligned(outer,refitted),classes,factors)
        val_pred=classes[values.argmax(axis=1)];truth=train[spec['target']].iloc[va].astype(str)
        metrics=evaluate(truth,val_pred,'classification','macro_f1',values,classes)
        pd.DataFrame({'row_position':va,'y_true':truth,'y_pred':val_pred}).to_csv(out/'validation_predictions.csv',index=False)
        np.savez_compressed(out/'validation_probabilities.npz',probabilities=values,classes=classes,row_position=va)
    models=predictor.model_names()
    record={'status':'ok','recipe':recipe,'metrics':metrics,'full_fit':full,
        'fit_iterations':{'selected':selected,'refit':refitted,'models':models},
        'feature_count':len(spec['features']),'class_factors':factors,'inner_split':inner_info,
        'inner_fit_rows_sha256':hashlib.sha256(np.asarray(rows[inner_tr],dtype='<i8').tobytes()).hexdigest(),
        'inner_calibration_rows_sha256':hashlib.sha256(np.asarray(rows[inner_va],dtype='<i8').tobytes()).hexdigest(),
        'calibration_status':'inner_holdout_before_full_refit_not_oof',
        'full_refit_map':mapping,'trained_model_artifact_count':len(models),
        'feature_generator_fit_scope':'inner_train_only_prefit_transform_elsewhere',
        'submission':str(out/'submission.csv'),'wall_seconds':round(time.monotonic()-start,3),
        'peak_rss_mb':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,1),
        'scope':'Dev-only complete alternative procedure, not runtime-integrated or unbiased private score'}
    atomic_json(out/'result.json',record)


if __name__=='__main__':
    job=json.loads(Path(sys.argv[1]).read_text())
    try:run(job)
    except Exception as exc:
        atomic_json(Path(job['output_dir'])/'result.json',{'status':'error','exception_type':type(exc).__name__})
        raise
