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

from agent_core import atomic_json, evaluate, save_submission


def feature_transform(code, train_x, test_x):
    if not code or not code.strip():
        return train_x.copy(),test_x.copy()
    tree=ast.parse(code)
    banned_names={'open','eval','exec','compile','__import__','getattr','setattr','globals','locals','vars','input','breakpoint'}
    banned_attrs={'to_csv','to_pickle','to_parquet','to_sql','to_json','read_csv','read_pickle','read_parquet','read_sql','load','save','system','popen'}
    for node in ast.walk(tree):
        if isinstance(node,(ast.Import,ast.ImportFrom,ast.Global,ast.Nonlocal,ast.ClassDef,ast.AsyncFunctionDef)):
            raise ValueError('Feature code may only define a synchronous transform function without imports')
        if isinstance(node,ast.Name) and (node.id in banned_names or node.id.startswith('__')):
            raise ValueError('Disallowed feature-code name')
        if isinstance(node,ast.Attribute) and (node.attr.startswith('_') or node.attr in banned_attrs or node.attr.startswith('read_') or node.attr.startswith('to_')):
            raise ValueError('Disallowed feature-code attribute')
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
    return transformed


def prepare_frames(train_x,test_x,engine):
    train_x=train_x.copy()
    test_x=test_x.copy()
    cat_cols=[]
    for c in train_x:
        if not pd.api.types.is_numeric_dtype(train_x[c]) or not pd.api.types.is_numeric_dtype(test_x[c]):
            cat_cols.append(c)
            for frame in [train_x,test_x]:
                frame[c]=frame[c].fillna('__MISSING__').astype(str)
            if engine=='lightgbm':
                categories=sorted(set(train_x[c]))
                for frame in [train_x,test_x]:
                    frame[c]=pd.Categorical(frame[c],categories=categories)
        else:
            for frame in [train_x,test_x]:
                frame[c]=pd.to_numeric(frame[c],errors='coerce').replace([np.inf,-np.inf],np.nan).astype('float32')
    return train_x,test_x,cat_cols


def make_model(recipe,kind,threads,iterations):
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
    processor=ColumnTransformer(transforms,sparse_threshold=1.0)
    params=recipe.get('params',{})
    if spec['kind']=='classification':
        estimator=SGDClassifier(loss='log_loss',alpha=1e-5,max_iter=1000,tol=1e-4,
                                random_state=42,class_weight='balanced' if params.get('class_weights') else None,n_jobs=threads)
    else:
        estimator=Ridge(alpha=10,solver='lsqr')
    model=make_pipeline(processor,estimator)
    rows=np.arange(len(train_x)) if full else tr
    with threadpool_limits(limits=threads):
        model.fit(train_x.iloc[rows],y.iloc[rows])
        predictions=model.predict(test_x)
        metrics=None
        val_pred=None
        if not full:
            val_pred=model.predict(train_x.iloc[va])
            proba=model.predict_proba(train_x.iloc[va]) if spec['kind']=='classification' else None
            metrics=evaluate(y.iloc[va],val_pred,spec['kind'],spec['metric'],proba,getattr(model,'classes_',None))
    return predictions,val_pred,metrics


def run(job):
    start=time.monotonic()
    spec=job['spec']
    recipe=job['recipe']
    train=pd.read_csv(spec['paths']['train'])
    test=pd.read_csv(spec['paths']['test'])
    sample=pd.read_csv(spec['paths']['sample_submission'])
    y=train[spec['target']]
    if spec['kind']=='classification':
        y=y.astype(str)
    train_x,test_x=feature_transform(recipe.get('feature_code',''),train[spec['features']],test[spec['features']])
    # Numeric target and IDs are never passed into generated code.
    if spec['target'] in train_x or spec['id'] in train_x:
        raise ValueError('Feature code reintroduced target or ID')
    split=np.load(job['split_path'])
    tr,va=split['train'],split['validation']
    full=job.get('full_fit',False)
    if recipe['engine']=='linear_text':
        predictions,val_pred,metrics=linear_text_fit(spec,recipe,train_x,test_x,y,tr,va,full,job['threads'])
        output_dir=Path(job['output_dir'])
        save_submission(spec,sample,test,predictions,output_dir/'submission.csv')
        if val_pred is not None:
            pd.DataFrame({'row_position':va,'y_true':y.iloc[va].to_numpy(),'y_pred':val_pred}).to_csv(output_dir/'validation_predictions.csv',index=False)
        record={'status':'ok','recipe':recipe,'metrics':metrics,'full_fit':full,'fit_iterations':1,
                'feature_count':len(train_x.columns),'feature_names':list(train_x.columns),
                'wall_seconds':round(time.monotonic()-start,3),
                'peak_rss_mb':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,1),
                'submission':str(output_dir/'submission.csv')}
        atomic_json(output_dir/'result.json',record)
        print(json.dumps({'status':'ok','metrics':metrics,'wall_seconds':record['wall_seconds']}),flush=True)
        return
    train_x,test_x,categorical=prepare_frames(train_x,test_x,recipe['engine'])
    iterations=int(np.clip(job.get('fit_iterations',recipe.get('params',{}).get('iterations',400)),30,1600))
    model=make_model(recipe,spec['kind'],job['threads'],iterations)
    target_log=bool(recipe.get('params',{}).get('log_target',False)) and spec['kind']=='regression' and float(y.min())>=0
    fit_y=np.log1p(y) if target_log else y
    fit_tr=np.arange(len(train)) if full else tr
    fit_kwargs={}
    if recipe['engine']=='catboost':
        fit_kwargs['cat_features']=categorical
        if not full:
            fit_kwargs.update(eval_set=(train_x.iloc[va],fit_y.iloc[va]),early_stopping_rounds=60)
    elif not full:
        from lightgbm import early_stopping,log_evaluation
        fit_kwargs.update(eval_set=[(train_x.iloc[va],fit_y.iloc[va])],callbacks=[early_stopping(60,verbose=False),log_evaluation(0)])
    with threadpool_limits(limits=job['threads']):
        model.fit(train_x.iloc[fit_tr],fit_y.iloc[fit_tr],**fit_kwargs)
        pred=np.asarray(model.predict(test_x)).reshape(-1)
        if target_log:
            pred=np.expm1(pred)
        if spec['kind']=='classification':
            if spec['metric']=='roc_auc' and len(model.classes_)==2:
                pred=model.predict_proba(test_x)[:,1]
            elif spec['metric']=='log_loss':
                raise ValueError('One-column probability submission for log_loss requires an explicit contract')
        metrics=None
        if not full:
            val_pred=np.asarray(model.predict(train_x.iloc[va])).reshape(-1)
            if target_log:
                val_pred=np.expm1(val_pred)
            proba=model.predict_proba(train_x.iloc[va]) if spec['kind']=='classification' else None
            metrics=evaluate(y.iloc[va],val_pred,spec['kind'],spec['metric'],proba,getattr(model,'classes_',None))
    output_dir=Path(job['output_dir'])
    save_submission(spec,sample,test,pred,output_dir/'submission.csv')
    validation_path=None
    if not full:
        validation_path=output_dir/'validation_predictions.csv'
        validation_frame=pd.DataFrame({'row_position':va,'y_true':y.iloc[va].to_numpy(),'y_pred':val_pred})
        validation_frame.to_csv(validation_path,index=False)
    best_iteration=getattr(model,'tree_count_',None) if recipe['engine']=='catboost' else getattr(model,'best_iteration_',None)
    if best_iteration is None or best_iteration<=0:
        best_iteration=getattr(model,'tree_count_',iterations)
    else:
        best_iteration=int(best_iteration)
    record={'status':'ok','recipe':recipe,'metrics':metrics,'full_fit':full,
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
