"""Isolated, bounded training worker. No API credentials enter this process."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from threadpoolctl import threadpool_limits

from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.resources import peak_rss_mb
from automl.infrastructure.tables import read_input_table,read_task_sample
from automl.evaluation.api import evaluate,make_split,make_folds,metric_context
from automl.publishing.api import save_submission,read_submission_values,positive_class_index
from automl.execution.model_adapters.registry import make_model,fit_options,selected_iterations,CAPABILITIES,loss_profile_fit_receipt
from automl.execution.weighting.classes import sample_weights,number
from automl.evaluation.api import lgbm_metric,tune_class_factors,adjusted_probabilities
from automl.execution.feature_engineering.transforms import feature_transform,generic_features
from automl.execution.feature_engineering.selection import select_features,validate_selection
from automl.execution.preprocessing.frames import prepare_frames
from automl.execution.preprocessing.target_encoding import target_encode_frames,infer_history_groups
from automl.execution.preprocessing.history import add_history_features,validate_history_groups
from automl.execution.model_adapters.linear_text import linear_text_fit
from automl.contracts.messages import DataPolicy,SplitPlan,PredictionBundle,resolve_loss_profile,validate_loss_profiles
from dataclasses import asdict
from automl.execution.sampling.policies import prepare_training
from automl.execution.feature_views import validate_feature_view,feature_view_components,validate_fit_iterations
from automl.evaluation.api import calibrate_class_factors,validate_decision_optimizer
from automl.execution.postprocessing.targets import validate_target_smearing,fit_smearing,inverse_log_predictions














def run_ensemble(job):
    start=time.monotonic()
    recipe=job['recipe']; spec=job['spec']; output=Path(job['output_dir'])
    components=recipe.get('components',[])
    if not 2<=len(components)<=3 or any(c.get('engine')=='ensemble' for c in components):
        raise ValueError('Ensemble must contain two or three non-nested recipes')
    weights=np.asarray(recipe.get('weights',[1]*len(components)),dtype=float)
    if len(weights)!=len(components) or not np.isfinite(weights).all() or (weights<=0).any():
        raise ValueError('Invalid ensemble weights')
    weights=weights/weights.sum()
    records=[]
    for index,component in enumerate(components):
        directory=output/f'component-{index}'
        directory.mkdir(parents=True,exist_ok=True)
        child=dict(job,recipe=component,output_dir=str(directory))
        if isinstance(job.get('fit_iterations'),list): child['fit_iterations']=job['fit_iterations'][index]
        else: child.pop('fit_iterations',None)
        run(child)
        records.append(json.loads((directory/'result.json').read_text(encoding='utf-8')))
    train=read_input_table(spec['paths']['train']); test=read_input_table(spec['paths']['test'])
    sample=read_task_sample(spec); full=job.get('full_fit',False)
    with np.load(job['split_path']) as split:
        va=split['validation'].copy()
    combined=None; val_combined=None
    for index,weight in enumerate(weights):
        directory=output/f'component-{index}'
        if spec['kind']=='classification':
            with np.load(directory/'test_probabilities.npz') as stored:
                classes=stored['classes'].astype(str)
                order=[list(classes).index(c) for c in spec['classes']]
                predictions=stored['probabilities'][:,order]
            if not full:
                with np.load(directory/'validation_probabilities.npz') as stored_val:
                    assert np.array_equal(stored_val['row_position'],va)
                    val_predictions=stored_val['probabilities'][:,order]
        else:
            predictions=read_submission_values(spec,directory/'submission.csv')
            if not full: val_predictions=pd.read_csv(directory/'validation_predictions.csv')['y_pred'].to_numpy()
        combined=weight*predictions if combined is None else combined+weight*predictions
        if not full: val_combined=weight*val_predictions if val_combined is None else val_combined+weight*val_predictions
    if spec['kind']=='classification':
        classes=np.asarray(spec['classes'])
        np.savez_compressed(output/'test_probabilities.npz',probabilities=combined,classes=classes)
        if not full: np.savez_compressed(output/'validation_probabilities.npz',probabilities=val_combined,classes=classes,row_position=va)
        if spec.get('prediction_type')=='probability_matrix':
            predictions=combined[:,[list(classes).index(str(c)) for c in spec['output_columns']]]
        elif spec.get('prediction_type')=='probability': predictions=combined[:,positive_class_index(spec,classes)]
        else: predictions=classes[combined.argmax(axis=1)]
        val_pred=classes[val_combined.argmax(axis=1)] if not full else None
    else:
        predictions=combined; val_pred=val_combined
    save_submission(spec,sample,test,predictions,output/'submission.csv')
    metrics=None
    if not full:
        truth=train[spec['target']].iloc[va]
        if spec['kind']=='classification': truth=truth.astype(str)
        metrics=evaluate(truth,val_pred,spec['kind'],spec['metric'],val_combined if spec['kind']=='classification' else None,spec['classes'],**metric_context(spec,train,va))
        pd.DataFrame({'row_position':va,'y_true':truth.to_numpy(),'y_pred':val_pred}).to_csv(output/'validation_predictions.csv',index=False)
    atomic_json(output/'result.json',{'status':'ok','recipe':recipe,'metrics':metrics,'full_fit':full,
        'fit_iterations':[r['fit_iterations'] for r in records],'feature_count':sum(r['feature_count'] for r in records),
        'wall_seconds':round(time.monotonic()-start,3),'peak_rss_mb':round(peak_rss_mb(),1),
        'submission':str(output/'submission.csv'),'components':records})


def run_feature_views(job):
    recipe=job['recipe']
    validate_selection(recipe.get('params',{}))
    components=feature_view_components(recipe,job['spec'])
    internal=dict(recipe,engine='ensemble',params={},components=components,weights=[.5,.5])
    run_ensemble(dict(job,recipe=internal))
    path=Path(job['output_dir'])/'result.json'
    record=json.loads(path.read_text(encoding='utf-8'))
    record['recipe']=recipe
    record['feature_views']={'method':'categorical_te_pair','weights':[.5,.5],
        'groups':components[1]['params']['target_encoding_groups'],
        'iteration_tree':record['fit_iterations']}
    atomic_json(path,record)


def run(job):
    start=time.monotonic()
    spec=job['spec']
    recipe=job['recipe']
    validate_loss_profiles(recipe,spec['kind'])
    loss_profile=resolve_loss_profile(recipe.get('engine'),recipe.get('params',{}),spec['kind'])
    selection_size=validate_selection(recipe.get('params',{}))
    if selection_size and recipe['engine']=='linear_text':
        raise ValueError('Feature selection is unsupported for text recipes')
    validate_fit_iterations(recipe,job.get('fit_iterations'))
    decision_optimizer=validate_decision_optimizer(recipe,spec)
    target_smearing=validate_target_smearing(recipe,spec)
    if 'feature_views' in recipe.get('params',{}):
        validate_feature_view(recipe,spec)
        return run_feature_views(job)
    data_policy=DataPolicy.parse(recipe.get('data_policy'))
    if recipe['engine']=='ensemble':
        return run_ensemble(job)
    train=read_input_table(spec['paths']['train'])
    test=read_input_table(spec['paths']['test'])
    sample=read_task_sample(spec)
    y=train[spec['target']]
    if spec['kind']=='classification':
        y=y.astype(str)
    train_x,test_x=train[spec['features']].copy(),test[spec['features']].copy()
    if recipe.get('params',{}).get('categorical_from_dictionary',False):
        for column in spec.get('categorical_features',[]):
            for frame in [train_x,test_x]:
                frame[column]=frame[column].fillna('__MISSING__').astype(str)
    forbidden=tuple(spec.get('all_targets',[spec['target']]))+(spec['id'],)
    if spec.get('task_family')=='pointwise_ranking': forbidden+=(spec['group_column'],)
    train_x,test_x=feature_transform(recipe.get('feature_code',''),train_x,test_x,forbidden)
    # Numeric target and IDs are never passed into generated code.
    if any(column in train_x for column in forbidden):
        raise ValueError('Feature code reintroduced target or ID')
    with np.load(job['split_path']) as split:
        tr,va=split['train'].copy(),split['validation'].copy()
    SplitPlan(tuple(tr.tolist()),tuple(va.tolist())).validate(len(train))
    full=job.get('full_fit',False)
    history_asof=recipe.get('params',{}).get('history_asof',False)
    history_time=spec.get('time_column') or (spec.get('time_candidate') or {}).get('column')
    if not isinstance(history_asof,bool): raise ValueError('history_asof must be a boolean')
    history_minimum=recipe.get('params',{}).get('history_min_periods',2)
    if type(history_minimum) is not int or not 2<=history_minimum<=10: raise ValueError('history_min_periods must be an integer from2to10')
    if 'history_min_periods' in recipe.get('params',{}) and not history_asof: raise ValueError('Minimum history requires history_asof')
    if history_asof and (spec['kind']!='regression' or spec.get('task_family')=='pointwise_ranking' or history_time not in spec['features'] or not recipe.get('params',{}).get('target_encoding') or not (recipe['params'].get('target_encoding_auto_groups') or recipe['params'].get('target_encoding_groups'))):
        raise ValueError('As-of history requires regression, observation periods and context encoding')
    if history_asof:
        for transformed,original in [(train_x,train),(test_x,test)]:
            if history_time not in transformed: raise ValueError('As-of history requires an unmodified observation period')
            before=pd.to_numeric(original[history_time],errors='raise').to_numpy(dtype=float)
            after=pd.to_numeric(transformed[history_time],errors='raise').to_numpy(dtype=float)
            if not np.array_equal(before,after,equal_nan=True): raise ValueError('As-of history requires an unmodified observation period')
    if history_asof and recipe['engine']=='linear_text': raise ValueError('As-of history is not supported for text recipes')
    if CAPABILITIES[recipe['engine']].get('mode')=='text':
        if spec.get('task_family')=='pointwise_ranking': raise ValueError('Text ranking adapter is not implemented')
        if not data_policy.is_noop: raise ValueError('Data-policy support for text is not implemented; use explicit noop')
        predictions,val_pred,metrics,test_proba,val_proba,classes=linear_text_fit(spec,recipe,train_x,test_x,y,tr,va,full,job['threads'])
        output_dir=Path(job['output_dir'])
        save_submission(spec,sample,test,predictions,output_dir/'submission.csv')
        if val_pred is not None:
            pd.DataFrame({'row_position':va,'y_true':y.iloc[va].to_numpy(),'y_pred':val_pred}).to_csv(output_dir/'validation_predictions.csv',index=False)
        if test_proba is not None:
            np.savez_compressed(output_dir/'test_probabilities.npz',probabilities=test_proba,classes=np.asarray(classes,dtype=str))
            if val_proba is not None: np.savez_compressed(output_dir/'validation_probabilities.npz',probabilities=val_proba,classes=np.asarray(classes,dtype=str),row_position=va)
        record={'status':'ok','recipe':recipe,'metrics':metrics,'full_fit':full,'fit_iterations':1,
                'feature_count':len(train_x.columns),'feature_names':list(train_x.columns),
                'wall_seconds':round(time.monotonic()-start,3),
                'peak_rss_mb':round(peak_rss_mb(),1),
                'submission':str(output_dir/'submission.csv')}
        atomic_json(output_dir/'result.json',record)
        print(json.dumps({'status':'ok','metrics':metrics,'wall_seconds':record['wall_seconds']}),flush=True)
        return
    fit_tr=np.arange(len(train)) if full else tr
    raw_train_x,raw_test_x=train_x,test_x
    iterations=int(np.clip(job.get('fit_iterations',recipe.get('params',{}).get('iterations',800)),30,3000))
    model_recipe=dict(recipe,metric=spec['metric'],n_classes=len(spec.get('classes') or []))
    model=make_model(model_recipe,spec['kind'],job['threads'],iterations)
    target_log=bool(recipe.get('params',{}).get('log_target',False)) and spec['kind']=='regression' and float(y.iloc[fit_tr].min())>=0
    if target_smearing and not target_log:raise ValueError('Smearing requires nonnegative fitting targets')
    fit_y=np.log1p(y) if target_log else y
    policy_records=[]
    source_hashes=pd.util.hash_pandas_object(train[spec['features']],index=False).to_numpy(dtype='uint64')
    def fit_on_rows(estimator,rows,validation_rows=None):
        # Refit all learned preprocessing for this partition, including inner fits.
        prepared_x,prepared_test=generic_features(raw_train_x,raw_test_x,rows,recipe.get('params',{}).get('generic_features','none'))
        encoding_groups=None
        if recipe.get('params',{}).get('target_encoding',False):
            encoding_params=recipe.get('params',{})
            encoding_groups=encoding_params.get('target_encoding_groups')
            if encoding_params.get('target_encoding_auto_groups',False):
                if encoding_groups: raise ValueError('Choose explicit groups or automatic history groups, not both')
                encoding_groups=infer_history_groups(prepared_x[spec['features']],rows,spec.get('time_column') or (spec.get('time_candidate') or {}).get('column'),
                                                     spec.get('categorical_features',[]),refine=encoding_params.get('target_encoding_refine_groups',False),
                                                     static_numeric=spec.get('static_numeric_features',[]) if encoding_params.get('target_encoding_hierarchical',False) else None)
            prepared_x,prepared_test=target_encode_frames(prepared_x,prepared_test,y,rows,source_hashes,spec.get('classes'),
                smoothing=number(encoding_params,'target_encoding_smoothing',20,.5,100),groups=encoding_groups,add_counts=encoding_params.get('target_encoding_counts',False),
                half_life=number(encoding_params,'target_encoding_half_life',0,0,10),time_column=spec.get('time_column') or (spec.get('time_candidate') or {}).get('column'))
        history_state=None
        if history_asof:
            validate_history_groups(prepared_x,prepared_test,history_time,encoding_groups or [])
            periods=pd.to_numeric(raw_train_x[history_time].iloc[rows],errors='raise').to_numpy(dtype=float)
            if not np.isfinite(periods).all(): raise ValueError('History fitting periods must be finite')
            period_count=len(np.unique(periods))
            enabled=period_count>=history_minimum and bool(encoding_groups)
            history_state={'fitting_periods':period_count,'minimum_periods':history_minimum,
                           'enabled':enabled,'contexts':len(encoding_groups or []),
                           'reason':'enabled' if enabled else 'insufficient_periods' if period_count<history_minimum else 'no_supported_contexts'}
            if enabled: prepared_x,prepared_test=add_history_features(prepared_x,prepared_test,y,rows,history_time,encoding_groups)
        selector_weights=sample_weights(y.iloc[rows],recipe.get('params',{})) if spec['kind']=='classification' else None
        selection_record=None
        if recipe.get('params',{}).get('feature_selection_top_k',0):
            selection_options=({'protected_columns':spec['features']}
                if recipe['params'].get('feature_selection_protect_original',False) else {})
            prepared_x,prepared_test,selection_record=select_features(prepared_x,prepared_test,fit_y,rows,
                spec['kind'],job['threads'],recipe.get('params',{}),selector_weights,**selection_options)
        prepared_x,prepared_test,categorical=prepare_frames(prepared_x,prepared_test,recipe['engine'],rows)
        kwargs={}
        weights=None
        if spec['kind']=='classification':
            weights=sample_weights(y.iloc[rows],recipe.get('params',{}))
        fit_x,targets,weights,parents,policy_record=prepare_training(
            prepared_x.iloc[rows],fit_y.iloc[rows],y.iloc[rows],weights,source_hashes[rows],rows,
            recipe.get('data_policy'),spec['kind'],recipe['engine'])
        policy_records.append(policy_record)
        if selection_record is not None: policy_record['feature_selection']=selection_record
        if history_state is not None: policy_record['history_asof']=history_state
        if encoding_groups is not None: policy_record['target_encoding_groups']=encoding_groups
        if not data_policy.is_noop:
            provenance_path=Path(job['output_dir'])/f'fit-parents-{len(policy_records)}.npz'
            np.savez_compressed(provenance_path,parent_rows=parents)
            policy_record['parent_rows_artifact']=str(provenance_path)
        if validation_rows is not None and set(parents)&set(validation_rows): raise ValueError('Augmentation parent crosses validation boundary')
        if weights is not None: kwargs['sample_weight']=weights
        kwargs.update(fit_options(recipe['engine'],spec,recipe,prepared_x,fit_y,validation_rows,categorical,target_log))
        if spec.get('task_family')=='pointwise_ranking' and validation_rows is not None and recipe['engine'] in {'lightgbm','xgboost'}:
            evaluator=lgbm_metric(spec,target_log,**metric_context(spec,train,validation_rows))
            if recipe['engine']=='lightgbm': kwargs['eval_metric']=evaluator
            else:
                def ranking_loss(truth,predictions): return 1-evaluator(truth,predictions)[1]
                kwargs['eval_metric']=ranking_loss
        estimator.fit(fit_x,targets,**kwargs)
        if loss_profile is not None:
            receipt=loss_profile_fit_receipt(recipe,spec['kind'],estimator)
            receipt.update(fit_index=len(policy_records),model_scope='full_refit' if full and estimator is model
                else 'outer_fitting' if estimator is model else 'inner_fitting',
                validation_used_for_stopping=validation_rows is not None,
                primary_metric=spec['metric'],target_scale='log1p' if target_log else 'original')
            policy_record['loss_profile']=receipt
        return prepared_x,prepared_test
    class_factors={}
    decision_diagnostics=None
    smearing={'requested':target_smearing,'factor':1.,'status':'pending' if target_smearing else 'disabled',
        'method':recipe.get('params',{}).get('target_smearing_method','duan') if target_smearing else None}
    calibration_status='disabled'
    nested=bool(recipe.get('params',{}).get('nested_stopping',False)) and not full and CAPABILITIES[recipe['engine']]['nested_stopping']
    calibrate=spec['kind']=='classification' and spec['metric']=='macro_f1' and CAPABILITIES[recipe['engine']]['macro_f1_calibration'] and recipe.get('params',{}).get('calibrate',False)
    early_stopping_source='full_refit' if full else 'outer_search_holdout'
    inner_split=None
    inner_split_error=None
    calibration_folds=[]
    if nested or calibrate or target_smearing:
        # Neither stopping nor calibration sees the outer validation labels.
        inner_train=train.iloc[fit_tr].reset_index(drop=True)
        inner_hashes=pd.util.hash_pandas_object(inner_train[spec['features']],index=False).to_numpy(dtype='uint64')
        try:
            inner_tr,inner_va,inner_split=make_split(spec,inner_train,inner_hashes,seed=73)
        except ValueError as exc:
            # Only a split failure can trigger this fallback; fit errors propagate.
            inner_split_error=str(exc)[:300]
            calibration_status='skipped_unavailable_inner_split' if calibrate else 'disabled'
            if target_smearing:smearing['status']='skipped_unavailable_inner_split'
            if nested: early_stopping_source='fixed_iterations_split_fallback'
        else:
            inner_tr=fit_tr[inner_tr]; inner_va=fit_tr[inner_va]
            inner_model=make_model(model_recipe,spec['kind'],job['threads'],iterations)
            with threadpool_limits(limits=job['threads']):
                inner_x,_=fit_on_rows(inner_model,inner_tr,inner_va if nested else None)
            if nested:
                selected=selected_iterations(recipe['engine'],inner_model)
                if selected and selected>0:
                    floor=int(np.clip(recipe.get('params',{}).get('min_iterations',1),1,iterations))
                    iterations=max(floor,int(selected))
                model=make_model(model_recipe,spec['kind'],job['threads'],iterations)
                early_stopping_source='inner_training_holdout'
            smearing_ready=False
            if target_smearing:
                history_state=policy_records[-1].get('history_asof')
                smearing_ready=(not history_asof or bool(history_state and history_state['enabled'])) and len(inner_va)>=20
                smearing.update(status='pending' if smearing_ready else 'skipped_history_support' if history_asof and not (history_state and history_state['enabled']) else 'skipped_insufficient_calibration_rows',
                    calibration_rows=len(inner_va),history_support=history_state)
            if calibrate or smearing_ready:
                with threadpool_limits(limits=job['threads']):
                    if nested and selected and int(selected)!=iterations:
                        inner_model=make_model(model_recipe,spec['kind'],job['threads'],iterations)
                        inner_x,_=fit_on_rows(inner_model,inner_tr,None)
                    if calibrate:
                        class_factors,decision_diagnostics=calibrate_class_factors(y.iloc[inner_va],inner_model.predict_proba(inner_x.iloc[inner_va]),inner_model.classes_,decision_optimizer)
                        calibration_status='inner_training_holdout_matching_iterations'
                    if smearing_ready:
                        smearing.update(fit_smearing(y.iloc[inner_va],np.asarray(inner_model.predict(inner_x.iloc[inner_va])).reshape(-1),
                            recipe.get('params',{}).get('target_smearing_method','duan')),
                            matching_iterations=iterations,source='inner_training_holdout_matching_iterations')
    if calibrate and int(recipe.get('params',{}).get('calibration_folds',1))>1:
        fit_frame=train.iloc[fit_tr].reset_index(drop=True)
        try:
            folds=make_folds(spec,fit_frame,source_hashes[fit_tr],int(np.clip(recipe['params']['calibration_folds'],2,3)),73)
        except ValueError:
            folds=[]
        if folds:
            probabilities=np.zeros((len(fit_tr),len(spec['classes'])))
            for local_tr,local_va,info in folds:
                local_model=make_model(model_recipe,spec['kind'],job['threads'],iterations)
                with threadpool_limits(limits=job['threads']):
                    local_x,_=fit_on_rows(local_model,fit_tr[local_tr],None)
                    order=[list(map(str,local_model.classes_)).index(c) for c in spec['classes']]
                    probabilities[local_va]=local_model.predict_proba(local_x.iloc[fit_tr[local_va]])[:,order]
                calibration_folds.append(info)
            class_factors,decision_diagnostics=calibrate_class_factors(y.iloc[fit_tr],probabilities,spec['classes'],decision_optimizer)
            calibration_status='training_oof_matching_iterations'
    with threadpool_limits(limits=job['threads']):
        train_x,test_x=fit_on_rows(model,fit_tr,None if full or nested else va)
        pred=np.asarray(model.predict(test_x)).reshape(-1)
        if target_log:
            pred=inverse_log_predictions(pred,smearing['factor']) if target_smearing else np.expm1(pred)
        if spec['kind']=='classification':
            probabilities=adjusted_probabilities(model.predict_proba(test_x),model.classes_,class_factors)
            pred=np.asarray(model.classes_)[np.argmax(probabilities,axis=1)]
            if spec.get('prediction_type')=='probability_matrix':
                indices=[list(map(str,model.classes_)).index(str(c)) for c in spec['output_columns']]
                pred=probabilities[:,indices]
            elif spec.get('prediction_type')=='probability':
                pred=probabilities[:,positive_class_index(spec,model.classes_)]
        metrics=None
        if not full:
            val_pred=np.asarray(model.predict(train_x.iloc[va])).reshape(-1)
            if target_log:
                val_pred=inverse_log_predictions(val_pred,smearing['factor']) if target_smearing else np.expm1(val_pred)
            proba=adjusted_probabilities(model.predict_proba(train_x.iloc[va]),model.classes_,class_factors) if spec['kind']=='classification' else None
            if proba is not None: val_pred=np.asarray(model.classes_)[np.argmax(proba,axis=1)]
            metrics=evaluate(y.iloc[va],val_pred,spec['kind'],spec['metric'],proba,getattr(model,'classes_',None),**metric_context(spec,train,va))
    output_dir=Path(job['output_dir'])
    save_submission(spec,sample,test,pred,output_dir/'submission.csv')
    validation_path=None
    if spec['kind']=='classification':
        np.savez_compressed(output_dir/'test_probabilities.npz',probabilities=probabilities,classes=np.asarray(model.classes_,dtype=str))
    if not full:
        validation_path=output_dir/'validation_predictions.csv'
        validation_frame=pd.DataFrame({'row_position':va,'y_true':y.iloc[va].to_numpy(),'y_pred':val_pred})
        validation_frame.to_csv(validation_path,index=False)
        if spec['kind']=='classification':
            np.savez_compressed(output_dir/'validation_probabilities.npz',probabilities=proba,classes=np.asarray(model.classes_,dtype=str),row_position=va)
    best_iteration=selected_iterations(recipe['engine'],model)
    if best_iteration is None or best_iteration<=0:
        best_iteration=getattr(model,'tree_count_',iterations)
    else:
        best_iteration=int(best_iteration)
    importance=getattr(model,'feature_importances_',None)
    important_features=sorted(zip(map(str,train_x.columns),map(float,importance)),key=lambda p:p[1],reverse=True)[:15] if importance is not None else []
    record={'status':'ok','recipe':recipe,'metrics':metrics,'full_fit':full,
            'data_policy_runs':policy_records,
            'prediction_bundle':asdict(PredictionBundle(str(output_dir/'submission.csv'),len(test),tuple(sample.columns),tuple(spec.get('classes') or []))),
            'calibration_status':calibration_status,'class_factors':class_factors,
            'decision_optimizer':decision_diagnostics,
            'target_smearing':smearing,
            'calibration_folds':calibration_folds,
            'specialist_pairs':getattr(model,'specialist_pairs_',[]),
            'early_stopping_source':early_stopping_source,'inner_split':inner_split,'inner_split_error':inner_split_error,
            'important_features':important_features,
            'fit_iterations':int(best_iteration),'feature_count':len(train_x.columns),
            'feature_names':list(train_x.columns),'wall_seconds':round(time.monotonic()-start,3),
            'peak_rss_mb':round(peak_rss_mb(),1),
            'validation_predictions':str(validation_path) if validation_path else None,
            'submission':str(output_dir/'submission.csv')}
    if loss_profile is not None:
        record['loss_profile_id']=loss_profile.loss_profile_id
        record['effective_loss_profile']=policy_records[-1]['loss_profile']
    atomic_json(output_dir/'result.json',record)
    print(json.dumps({k:v for k,v in record.items() if k not in {'recipe','feature_names'}},ensure_ascii=False),flush=True)


if __name__=='__main__':
    job=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    try:
        run(job)
    except Exception as exc:
        atomic_json(Path(job['output_dir'])/'result.json',{'status':'error','error':f'{type(exc).__name__}: {exc}'})
        raise
