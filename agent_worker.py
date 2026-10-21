"""Isolated, bounded training worker. No API credentials enter this process."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from threadpoolctl import threadpool_limits

from agent_core import atomic_json, evaluate, save_submission, make_split
from model_utils import make_model, sample_weights, lgbm_metric, generic_features, tune_class_factors, adjusted_probabilities


def feature_transform(code, train_x, test_x, forbidden_columns=()):
    if not code or not code.strip():
        return train_x.copy(),test_x.copy()
    tree=ast.parse(code)
    banned_names={'open','eval','exec','compile','__import__','getattr','setattr','globals','locals','vars','input','breakpoint'}
    banned_attrs={'to_csv','to_pickle','to_parquet','to_sql','to_json','read_csv','read_pickle','read_parquet','read_sql','load','save','system','popen'}
    numpy_functions={'abs','arctan2','clip','cos','deg2rad','e','exp','expm1','finfo','float32','float64','full','hypot',
        'int8','int16','int32','int64','isfinite','isnan','log','log1p','maximum','minimum','nan','nan_to_num',
        'pi','radians','select','sign','sin','sqrt','square','tanh','where','zeros','ones'}
    pandas_functions={'DataFrame','Series','to_numeric','isna','notna','NA','Timestamp','to_datetime','cut','qcut'}
    for node in ast.walk(tree):
        if isinstance(node,ast.Constant) and isinstance(node.value,str) and node.value in forbidden_columns:
            raise ValueError('Feature code references an unavailable target/ID column; use params.log_target for regression target transformations')
        if isinstance(node,(ast.Import,ast.ImportFrom,ast.Global,ast.Nonlocal,ast.ClassDef,ast.AsyncFunctionDef)):
            raise ValueError('Feature code may only define a synchronous transform function without imports')
        if isinstance(node,ast.Name) and (node.id in banned_names or node.id.startswith('__')):
            raise ValueError('Disallowed feature-code name')
        if isinstance(node,ast.Attribute):
            safe_pandas_conversion=isinstance(node.value,ast.Name) and node.value.id=='pd' and node.attr in pandas_functions
            if node.attr.startswith('_') or node.attr in banned_attrs|{'eval','query','fromfile','memmap','loadtxt','genfromtxt','savetxt','dump','dumps','write','writelines'} or node.attr.startswith('read_') or (node.attr.startswith('to_') and not safe_pandas_conversion):
                raise ValueError('Disallowed feature-code attribute')
            if isinstance(node.value,ast.Name) and node.value.id in {'np','pd'}:
                allowed=numpy_functions if node.value.id=='np' else pandas_functions
                if node.attr not in allowed: raise ValueError('Unsupported module function in feature code')
    scope={'pd':pd,'np':np,'__builtins__':{'len':len,'str':str,'float':float,'int':int,
           'list':list,'dict':dict,'range':range,'enumerate':enumerate,'zip':zip,
           'min':min,'max':max,'abs':abs,'isinstance':isinstance,'sum':sum,'sorted':sorted}}
    exec(compile(tree,'<qwen_feature_code>','exec'),scope)
    if not callable(scope.get('transform')):
        raise ValueError('Feature code must define transform(df)')
    transformed=[]
    for source in [train_x,test_x]:
        value=scope['transform'](source.copy())
        if not isinstance(value,pd.DataFrame) or len(value)!=len(source) or not value.index.equals(source.index):
            raise ValueError('Feature code changed row count/order/index')
        if value.columns.duplicated().any() or len(value.columns)>len(source.columns)+32:
            raise ValueError('Feature code created duplicate or too many columns')
        transformed.append(value)
    if list(transformed[0].columns)!=list(transformed[1].columns):
        raise ValueError('Feature schemas differ between train and test')
    # Reject transformations depending on validation/other-row statistics.
    if len(train_x)>8:
        subset=train_x.iloc[::2].copy()
        check=scope['transform'](subset)
        try:
            pd.testing.assert_frame_equal(check,transformed[0].loc[subset.index],check_dtype=False,check_exact=False,rtol=1e-6,atol=1e-8)
        except (AssertionError,TypeError,ValueError) as exc:
            raise ValueError('Feature code depends on other rows; fitting/statistics must stay inside training split') from exc
    return transformed


def prepare_frames(train_x,test_x,engine,fit_rows=None):
    train_x=train_x.copy()
    test_x=test_x.copy()
    cat_cols=[]
    for c in train_x:
        if not pd.api.types.is_numeric_dtype(train_x[c]) or not pd.api.types.is_numeric_dtype(test_x[c]):
            cat_cols.append(c)
            for frame in [train_x,test_x]:
                frame[c]=frame[c].fillna('__MISSING__').astype(str)
            if engine in {'lightgbm','xgboost'}:
                categories=sorted(set(train_x[c].iloc[fit_rows] if fit_rows is not None else train_x[c]))
                for frame in [train_x,test_x]:
                    frame[c]=pd.Categorical(frame[c],categories=categories)
            elif engine=='extra_trees':
                fit=train_x[c].iloc[fit_rows] if fit_rows is not None else train_x[c]
                frequencies=fit.value_counts(normalize=True)
                for frame in [train_x,test_x]: frame[c]=frame[c].map(frequencies).fillna(0).astype('float32')
        else:
            for frame in [train_x,test_x]:
                frame[c]=pd.to_numeric(frame[c],errors='coerce').replace([np.inf,-np.inf],np.nan).astype('float32')
            if engine=='extra_trees':
                fit=train_x[c].iloc[fit_rows] if fit_rows is not None else train_x[c]
                median=float(fit.median()) if fit.notna().any() else 0.
                for frame in [train_x,test_x]: frame[c]=frame[c].fillna(median)
    return train_x,test_x,cat_cols


def legacy_make_model(recipe,kind,threads,iterations):
    params=recipe.get('params',{})
    depth=int(np.clip(params.get('depth',6),4,9))
    learning_rate=float(np.clip(params.get('learning_rate',.06),.02,.2))
    weighted=bool(params.get('class_weights',False)) and kind=='classification'
    if recipe['engine']=='catboost':
        from catboost import CatBoostClassifier,CatBoostRegressor
        common=dict(iterations=iterations,depth=depth,learning_rate=learning_rate,
                    thread_count=threads,random_seed=42,verbose=False,allow_writing_files=False,
                    l2_leaf_reg=float(np.clip(params.get('l2_leaf_reg',5),1,30)))
        if kind=='regression':
            return CatBoostRegressor(loss_function='RMSE',**common)
        return CatBoostClassifier(loss_function='MultiClass',auto_class_weights='Balanced' if weighted else None,**common)
    if recipe['engine']=='lightgbm':
        from lightgbm import LGBMClassifier,LGBMRegressor
        common=dict(n_estimators=iterations,learning_rate=learning_rate,
                    num_leaves=int(np.clip(params.get('num_leaves',31),15,63)),
                    max_depth=-1,reg_lambda=float(params.get('reg_lambda',3)),
                    n_jobs=threads,random_state=42,verbosity=-1,
                    colsample_bytree=.9,subsample=.9,
                    min_child_samples=int(np.clip(params.get('min_child_samples',30),10,100)))
        return LGBMRegressor(**common) if kind=='regression' else LGBMClassifier(class_weight='balanced' if weighted else None,**common)
    raise ValueError('Unknown recipe engine')


def linear_text_fit(spec,recipe,train_x,test_x,y,tr,va,full,threads):
    from sklearn.compose import ColumnTransformer
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge,SGDClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import OneHotEncoder,StandardScaler
    text_columns=[c for c in spec.get('text_features',[]) if c in train_x]
    numeric=[c for c in train_x if pd.api.types.is_numeric_dtype(train_x[c]) and c not in text_columns]
    categorical=[c for c in train_x if c not in text_columns+numeric]
    for frame in [train_x,test_x]:
        for column in text_columns+categorical:
            frame[column]=frame[column].fillna('').astype(str)
        for column in numeric:
            frame[column]=pd.to_numeric(frame[column],errors='coerce').replace([np.inf,-np.inf],np.nan)
    transforms=[]
    if numeric:
        transforms.append(('numeric',make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),StandardScaler(with_mean=False)),numeric))
    if categorical:
        transforms.append(('category',OneHotEncoder(handle_unknown='ignore',min_frequency=3,sparse_output=True),categorical))
    for index,column in enumerate(text_columns):
        transforms.append((f'text{index}',TfidfVectorizer(max_features=30000,ngram_range=(1,2),min_df=1,sublinear_tf=True),column))
        if recipe.get('params',{}).get('text_char_features',False):
            transforms.append((f'char{index}',TfidfVectorizer(analyzer='char_wb',max_features=15000,ngram_range=(3,5),min_df=2,sublinear_tf=True),column))
    processor=ColumnTransformer(transforms,sparse_threshold=1.0)
    params=recipe.get('params',{})
    if spec['kind']=='classification':
        estimator=SGDClassifier(loss='log_loss',alpha=float(np.clip(params.get('text_alpha',1e-5),1e-7,1e-2)),max_iter=1000,tol=1e-4,
                                random_state=42,class_weight='balanced' if params.get('class_weights') else None,n_jobs=threads)
    else:
        estimator=Ridge(alpha=10,solver='lsqr')
    model=make_pipeline(processor,estimator)
    rows=np.arange(len(train_x)) if full else tr
    with threadpool_limits(limits=threads):
        kwargs={}
        weights=sample_weights(y.iloc[rows],params) if spec['kind']=='classification' else None
        if weights is not None: kwargs[model.steps[-1][0]+'__sample_weight']=weights
        model.fit(train_x.iloc[rows],y.iloc[rows],**kwargs)
        predictions=model.predict(test_x)
        metrics=None
        val_pred=None; proba=None
        if not full:
            val_pred=model.predict(train_x.iloc[va])
            proba=model.predict_proba(train_x.iloc[va]) if spec['kind']=='classification' else None
            metrics=evaluate(y.iloc[va],val_pred,spec['kind'],spec['metric'],proba,getattr(model,'classes_',None))
    if spec.get('prediction_type')=='probability_matrix':
        indices=[list(map(str,model.classes_)).index(str(c)) for c in spec['output_columns']]
        predictions=model.predict_proba(test_x)[:,indices]
    elif spec.get('prediction_type')=='probability':
        predictions=model.predict_proba(test_x)[:,1]
    return predictions,val_pred,metrics,model.predict_proba(test_x) if spec['kind']=='classification' else None,proba,getattr(model,'classes_',None)


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
        records.append(json.loads((directory/'result.json').read_text()))
    train=pd.read_csv(spec['paths']['train']); test=pd.read_csv(spec['paths']['test'])
    sample=pd.read_csv(spec['paths']['sample_submission']); full=job.get('full_fit',False)
    va=np.load(job['split_path'])['validation']
    combined=None; val_combined=None
    for index,weight in enumerate(weights):
        directory=output/f'component-{index}'
        if spec['kind']=='classification':
            stored=np.load(directory/'test_probabilities.npz')
            classes=stored['classes'].astype(str)
            order=[list(classes).index(c) for c in spec['classes']]
            predictions=stored['probabilities'][:,order]
            if not full:
                stored_val=np.load(directory/'validation_probabilities.npz')
                assert np.array_equal(stored_val['row_position'],va)
                val_predictions=stored_val['probabilities'][:,order]
        else:
            predictions=pd.read_csv(directory/'submission.csv')[spec.get('output_columns',[spec['target']])[0]].to_numpy()
            if not full: val_predictions=pd.read_csv(directory/'validation_predictions.csv')['y_pred'].to_numpy()
        combined=weight*predictions if combined is None else combined+weight*predictions
        if not full: val_combined=weight*val_predictions if val_combined is None else val_combined+weight*val_predictions
    if spec['kind']=='classification':
        classes=np.asarray(spec['classes'])
        np.savez_compressed(output/'test_probabilities.npz',probabilities=combined,classes=classes)
        if not full: np.savez_compressed(output/'validation_probabilities.npz',probabilities=val_combined,classes=classes,row_position=va)
        if spec.get('prediction_type')=='probability_matrix':
            predictions=combined[:,[list(classes).index(str(c)) for c in spec['output_columns']]]
        elif spec.get('prediction_type')=='probability': predictions=combined[:,1]
        else: predictions=classes[combined.argmax(axis=1)]
        val_pred=classes[val_combined.argmax(axis=1)] if not full else None
    else:
        predictions=combined; val_pred=val_combined
    save_submission(spec,sample,test,predictions,output/'submission.csv')
    metrics=None
    if not full:
        truth=train[spec['target']].iloc[va]
        if spec['kind']=='classification': truth=truth.astype(str)
        metrics=evaluate(truth,val_pred,spec['kind'],spec['metric'],val_combined if spec['kind']=='classification' else None,spec['classes'])
        pd.DataFrame({'row_position':va,'y_true':truth.to_numpy(),'y_pred':val_pred}).to_csv(output/'validation_predictions.csv',index=False)
    atomic_json(output/'result.json',{'status':'ok','recipe':recipe,'metrics':metrics,'full_fit':full,
        'fit_iterations':[r['fit_iterations'] for r in records],'feature_count':sum(r['feature_count'] for r in records),
        'wall_seconds':round(time.monotonic()-start,3),'peak_rss_mb':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,1),
        'submission':str(output/'submission.csv'),'components':records})


def run(job):
    start=time.monotonic()
    spec=job['spec']
    recipe=job['recipe']
    if recipe['engine']=='ensemble':
        return run_ensemble(job)
    train=pd.read_csv(spec['paths']['train'])
    test=pd.read_csv(spec['paths']['test'])
    sample=pd.read_csv(spec['paths']['sample_submission'])
    y=train[spec['target']]
    if spec['kind']=='classification':
        y=y.astype(str)
    train_x,test_x=feature_transform(recipe.get('feature_code',''),train[spec['features']],test[spec['features']],(spec['target'],spec['id']))
    # Numeric target and IDs are never passed into generated code.
    if spec['target'] in train_x or spec['id'] in train_x:
        raise ValueError('Feature code reintroduced target or ID')
    split=np.load(job['split_path'])
    tr,va=split['train'],split['validation']
    full=job.get('full_fit',False)
    if recipe['engine']=='linear_text':
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
                'peak_rss_mb':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,1),
                'submission':str(output_dir/'submission.csv')}
        atomic_json(output_dir/'result.json',record)
        print(json.dumps({'status':'ok','metrics':metrics,'wall_seconds':record['wall_seconds']}),flush=True)
        return
    fit_tr=np.arange(len(train)) if full else tr
    train_x,test_x=generic_features(train_x,test_x,fit_tr,recipe.get('params',{}).get('generic_features','none'))
    train_x,test_x,categorical=prepare_frames(train_x,test_x,recipe['engine'],fit_tr)
    iterations=int(np.clip(job.get('fit_iterations',recipe.get('params',{}).get('iterations',800)),30,3000))
    model=make_model(dict(recipe,metric=spec['metric']),spec['kind'],job['threads'],iterations)
    target_log=bool(recipe.get('params',{}).get('log_target',False)) and spec['kind']=='regression' and float(y.iloc[fit_tr].min())>=0
    fit_y=np.log1p(y) if target_log else y
    def fit_on_rows(estimator,rows,validation_rows=None):
        kwargs={}
        if spec['kind']=='classification':
            weights=sample_weights(y.iloc[rows],recipe.get('params',{}))
            if weights is not None: kwargs['sample_weight']=weights
        if recipe['engine']=='catboost':
            kwargs['cat_features']=categorical
            if validation_rows is not None:
                kwargs.update(eval_set=(train_x.iloc[validation_rows],fit_y.iloc[validation_rows]),early_stopping_rounds=100)
        elif recipe['engine']=='lightgbm' and validation_rows is not None:
            from lightgbm import early_stopping,log_evaluation
            kwargs.update(eval_set=[(train_x.iloc[validation_rows],fit_y.iloc[validation_rows])],
                callbacks=[early_stopping(100,first_metric_only=True,verbose=False),log_evaluation(0)])
            if recipe.get('params',{}).get('early_metric','primary')=='primary':
                kwargs['eval_metric']=lgbm_metric(spec,target_log)
        elif recipe['engine']=='xgboost' and validation_rows is not None:
            evaluator=lgbm_metric(spec,target_log)
            def primary_loss(truth,predictions):
                _,value,higher=evaluator(truth,predictions)
                return 1-value if higher else value
            kwargs.update(eval_set=[(train_x.iloc[validation_rows],fit_y.iloc[validation_rows])],eval_metric=primary_loss)
        estimator.fit(train_x.iloc[rows],fit_y.iloc[rows],**kwargs)
        return estimator
    class_factors={}
    calibration_status='disabled'
    nested=bool(recipe.get('params',{}).get('nested_stopping',False)) and not full and recipe['engine'] in {'lightgbm','catboost','xgboost'}
    calibrate=spec['kind']=='classification' and spec['metric']=='macro_f1' and recipe['engine']=='lightgbm' and recipe.get('params',{}).get('calibrate',False)
    early_stopping_source='full_refit' if full else 'outer_search_holdout'
    inner_split=None
    if nested or calibrate:
        # Neither stopping nor calibration sees the outer validation labels.
        inner_train=train.iloc[fit_tr].reset_index(drop=True)
        inner_hashes=pd.util.hash_pandas_object(inner_train[spec['features']],index=False).to_numpy(dtype='uint64')
        try:
            inner_tr,inner_va,inner_split=make_split(spec,inner_train,inner_hashes,seed=73)
            inner_tr=fit_tr[inner_tr]; inner_va=fit_tr[inner_va]
            inner_model=make_model(dict(recipe,metric=spec['metric']),spec['kind'],job['threads'],iterations)
            with threadpool_limits(limits=job['threads']):
                fit_on_rows(inner_model,inner_tr,inner_va if nested else None)
            if nested:
                selected=getattr(inner_model,'tree_count_',None) if recipe['engine']=='catboost' else getattr(inner_model,'best_iteration_',None)
                if selected and selected>0:
                    floor=int(np.clip(recipe.get('params',{}).get('min_iterations',1),1,iterations))
                    iterations=max(floor,int(selected))
                model=make_model(dict(recipe,metric=spec['metric']),spec['kind'],job['threads'],iterations)
                early_stopping_source='inner_training_holdout'
            if calibrate:
                with threadpool_limits(limits=job['threads']):
                    if nested and selected and int(selected)!=iterations:
                        inner_model=make_model(dict(recipe,metric=spec['metric']),spec['kind'],job['threads'],iterations)
                        fit_on_rows(inner_model,inner_tr,None)
                    class_factors=tune_class_factors(y.iloc[inner_va],inner_model.predict_proba(train_x.iloc[inner_va]),inner_model.classes_)
                    calibration_status='inner_training_holdout_matching_iterations'
        except ValueError:
            calibration_status='skipped_rare_classes' if calibrate else 'disabled'
            if nested: early_stopping_source='fixed_iterations_rare_class_fallback'
    with threadpool_limits(limits=job['threads']):
        fit_on_rows(model,fit_tr,None if full or nested else va)
        pred=np.asarray(model.predict(test_x)).reshape(-1)
        if target_log:
            pred=np.expm1(pred)
        if spec['kind']=='classification':
            probabilities=adjusted_probabilities(model.predict_proba(test_x),model.classes_,class_factors)
            pred=np.asarray(model.classes_)[np.argmax(probabilities,axis=1)]
            if spec.get('prediction_type')=='probability_matrix':
                indices=[list(map(str,model.classes_)).index(str(c)) for c in spec['output_columns']]
                pred=probabilities[:,indices]
            elif spec['metric'] in {'roc_auc','log_loss'} and len(model.classes_)==2:
                pred=probabilities[:,1]
        metrics=None
        if not full:
            val_pred=np.asarray(model.predict(train_x.iloc[va])).reshape(-1)
            if target_log:
                val_pred=np.expm1(val_pred)
            proba=adjusted_probabilities(model.predict_proba(train_x.iloc[va]),model.classes_,class_factors) if spec['kind']=='classification' else None
            if proba is not None: val_pred=np.asarray(model.classes_)[np.argmax(proba,axis=1)]
            metrics=evaluate(y.iloc[va],val_pred,spec['kind'],spec['metric'],proba,getattr(model,'classes_',None))
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
    best_iteration=getattr(model,'tree_count_',None) if recipe['engine']=='catboost' else getattr(model,'best_iteration_',None)
    if best_iteration is None or best_iteration<=0:
        best_iteration=getattr(model,'tree_count_',iterations)
    else:
        best_iteration=int(best_iteration)
    importance=getattr(model,'feature_importances_',None)
    important_features=sorted(zip(map(str,train_x.columns),map(float,importance)),key=lambda p:p[1],reverse=True)[:15] if importance is not None else []
    record={'status':'ok','recipe':recipe,'metrics':metrics,'full_fit':full,
            'calibration_status':calibration_status,'class_factors':class_factors,
            'early_stopping_source':early_stopping_source,'inner_split':inner_split,
            'important_features':important_features,
            'fit_iterations':int(best_iteration),'feature_count':len(train_x.columns),
            'feature_names':list(train_x.columns),'wall_seconds':round(time.monotonic()-start,3),
            'peak_rss_mb':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,1),
            'validation_predictions':str(validation_path) if validation_path else None,
            'submission':str(output_dir/'submission.csv')}
    atomic_json(output_dir/'result.json',record)
    print(json.dumps({k:v for k,v in record.items() if k not in {'recipe','feature_names'}},ensure_ascii=False),flush=True)


if __name__=='__main__':
    job=json.loads(Path(sys.argv[1]).read_text())
    try:
        run(job)
    except Exception as exc:
        atomic_json(Path(job['output_dir'])/'result.json',{'status':'error','error':f'{type(exc).__name__}: {exc}'})
        raise
