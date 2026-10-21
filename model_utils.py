"""Bounded, task-independent model recipes and metric-aligned evaluation."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, r2_score


def number(params, name, default, low, high, integer=False):
    value=float(params.get(name,default))
    if not np.isfinite(value):
        raise ValueError(f'Non-finite parameter: {name}')
    value=float(np.clip(value,low,high))
    return int(value) if integer else value


def sample_weights(y, params):
    """Estimate imbalance weights on fitting rows only, never validation labels."""
    if 'class_weight_power' not in params:
        return None
    power=number(params,'class_weight_power',0,0,1)
    if not power:
        return None
    counts=pd.Series(np.asarray(y)).value_counts()
    weights=pd.Series(np.asarray(y)).map((len(y)/(len(counts)*counts))**power).to_numpy(dtype=float)
    return weights/weights.mean()

class CPUXGBoost:
    """Adapter preserving original string labels with the pinned XGBoost 2.1 API."""
    def __init__(self,kind,params):
        self.kind=kind; self.params=params; self.model=None; self.encoder=None

    def fit(self,x,y,sample_weight=None,eval_set=None,eval_metric=None):
        from xgboost import XGBClassifier,XGBRegressor
        from sklearn.preprocessing import LabelEncoder
        values=np.asarray(y)
        evaluation=eval_set
        if self.kind=='classification':
            self.encoder=LabelEncoder(); values=self.encoder.fit_transform(values.astype(str))
            if eval_set is not None:
                evaluation=[(frame,self.encoder.transform(np.asarray(target).astype(str))) for frame,target in eval_set]
        options=dict(self.params)
        if eval_set is not None:
            options['early_stopping_rounds']=100
            if eval_metric is not None: options['eval_metric']=eval_metric
        cls=XGBClassifier if self.kind=='classification' else XGBRegressor
        self.model=cls(**options)
        self.model.fit(x,values,sample_weight=sample_weight,eval_set=evaluation,verbose=False)
        return self

    def predict(self,x):
        values=self.model.predict(x)
        return self.encoder.inverse_transform(values.astype(int)) if self.encoder is not None else values

    def predict_proba(self,x): return self.model.predict_proba(x)

    @property
    def classes_(self):
        if self.encoder is None: raise AttributeError('Regression has no classes')
        return self.encoder.classes_

    @property
    def best_iteration_(self):
        try: return int(self.model.best_iteration)+1
        except AttributeError: return 0

    @property
    def feature_importances_(self): return self.model.feature_importances_


def make_model(recipe,kind,threads,iterations):
    params=recipe.get('params',{})
    depth=number(params,'depth',6,4,10,True)
    learning_rate=number(params,'learning_rate',.06,.01,.2)
    weighted=bool(params.get('class_weights',False)) and 'class_weight_power' not in params and kind=='classification'
    seed=number(params,'seed',42,0,2**31-1,True)
    if recipe['engine']=='xgboost':
        options=dict(n_estimators=iterations,learning_rate=learning_rate,
            max_depth=number(params,'max_depth',params.get('depth',8),3,12,True),
            min_child_weight=number(params,'min_child_weight',3,1,50),
            subsample=number(params,'subsample',.85,.5,1),colsample_bytree=number(params,'colsample_bytree',.9,.5,1),
            reg_lambda=number(params,'reg_lambda',8,0,100),reg_alpha=number(params,'reg_alpha',.1,0,20),
            gamma=number(params,'gamma',0,0,10),max_bin=number(params,'max_bin',256,64,512,True),
            tree_method='hist',device='cpu',enable_categorical=True,max_cat_to_onehot=8,
            n_jobs=threads,random_state=seed)
        return CPUXGBoost(kind,options)
    if recipe['engine']=='catboost':
        from catboost import CatBoostClassifier,CatBoostRegressor
        common=dict(iterations=iterations,depth=depth,learning_rate=learning_rate,
                    thread_count=threads,random_seed=seed,verbose=False,allow_writing_files=False,
                    l2_leaf_reg=number(params,'l2_leaf_reg',5,1,100),
                    random_strength=number(params,'random_strength',1,0,10))
        if kind=='regression':
            return CatBoostRegressor(loss_function='RMSE',**common)
        if params.get('early_metric','primary')=='primary':
            metric=recipe.get('metric','macro_f1')
            if metric=='macro_f1': common['eval_metric']='TotalF1:average=Macro;use_weights=false'
            elif metric=='accuracy': common['eval_metric']='Accuracy:use_weights=false'
        return CatBoostClassifier(loss_function='MultiClass',auto_class_weights='Balanced' if weighted else None,**common)
    if recipe['engine']=='lightgbm':
        from lightgbm import LGBMClassifier,LGBMRegressor
        max_depth=int(params.get('max_depth',params.get('depth',-1)))
        max_depth=-1 if max_depth<=0 else int(np.clip(max_depth,3,14))
        subsample=number(params,'subsample',1,.5,1)
        common=dict(n_estimators=iterations,learning_rate=learning_rate,
                    num_leaves=number(params,'num_leaves',31,15,255,True),max_depth=max_depth,
                    reg_lambda=number(params,'reg_lambda',3,0,100),reg_alpha=number(params,'reg_alpha',0,0,20),
                    n_jobs=threads,random_state=seed,verbosity=-1,
                    colsample_bytree=number(params,'colsample_bytree',.9,.5,1),subsample=subsample,
                    subsample_freq=int(params.get('subsample_freq',1 if subsample<1 else 0)),
                    min_child_samples=number(params,'min_child_samples',30,5,150,True))
        if params.get('early_metric','primary')=='primary':
            common['metric']='None'
        return LGBMRegressor(**common) if kind=='regression' else LGBMClassifier(class_weight='balanced' if weighted else None,**common)
    if recipe['engine']=='extra_trees':
        from sklearn.ensemble import ExtraTreesClassifier,ExtraTreesRegressor
        common=dict(n_estimators=min(iterations,500),n_jobs=threads,random_state=seed,
                    max_depth=number(params,'max_depth',24,6,40,True),
                    min_samples_leaf=number(params,'min_samples_leaf',2,1,20,True),
                    max_features=number(params,'max_features',.9,.4,1))
        return ExtraTreesRegressor(**common) if kind=='regression' else ExtraTreesClassifier(class_weight='balanced' if weighted else None,**common)
    raise ValueError('Unknown recipe engine')


def lgbm_metric(spec,log_target=False):
    """sklearn wrapper supplies encoded class labels; do not confuse loss and F1."""
    metric=spec['metric']
    def evaluate(y_true,pred):
        y_true=np.asarray(y_true)
        pred=np.asarray(pred)
        if spec['kind']=='regression':
            if log_target:
                y_true=np.expm1(y_true); pred=np.expm1(pred)
            if metric=='mae': value=np.abs(y_true-pred).mean()
            elif metric=='r2': value=r2_score(y_true,pred)
            else: value=np.sqrt(np.square(y_true-pred).mean())
        elif metric in {'macro_f1','weighted_f1','accuracy'}:
            labels=pred.argmax(axis=1) if pred.ndim==2 else (pred>=.5).astype(int)
            if metric=='accuracy': value=accuracy_score(y_true,labels)
            else:
                classes=np.arange(pred.shape[1]) if pred.ndim==2 else np.array([0,1])
                value=f1_score(y_true,labels,labels=classes,average='macro' if metric=='macro_f1' else 'weighted',zero_division=0)
        else:
            from sklearn.metrics import log_loss,roc_auc_score
            if metric=='roc_auc':
                value=roc_auc_score(y_true,pred,multi_class='ovr',average='macro',labels=np.arange(pred.shape[1])) if pred.ndim==2 and pred.shape[1]>2 else roc_auc_score(y_true,pred[:,1] if pred.ndim==2 else pred)
            else:
                value=log_loss(y_true,pred,labels=np.arange(pred.shape[1]) if pred.ndim==2 else [0,1])
        return metric,float(value),spec['greater_is_better']
    return evaluate


def generic_features(train_x,test_x,fit_rows,mode):
    """Feature choices learned on fitting rows only; all transforms are row-wise."""
    if mode not in {'missing','skew','both'}:
        return train_x,test_x
    train_x=train_x.copy(); test_x=test_x.copy()
    fit=train_x.iloc[fit_rows]
    numeric=[c for c in fit if pd.api.types.is_numeric_dtype(fit[c])]
    missing=sorted(numeric,key=lambda c:float(fit[c].isna().mean()),reverse=True)
    if mode in {'missing','both'}:
        for column in [c for c in missing if .01<float(fit[c].isna().mean())<.99][:12]:
            for frame in [train_x,test_x]: frame[f'__missing_{column}']=frame[column].isna().astype('int8')
    if mode in {'skew','both'}:
        skew=fit[numeric].skew().abs().sort_values(ascending=False)
        for column in skew[skew>2].head(12).index:
            for frame in [train_x,test_x]:
                values=pd.to_numeric(frame[column],errors='coerce')
                frame[f'__signed_log_{column}']=np.sign(values)*np.log1p(np.abs(values))
    return train_x,test_x


def tune_class_factors(y,probabilities,classes):
    """Conservative decision-rule tuning, called only on an inner training holdout."""
    y=np.asarray(y,dtype=str); classes=np.asarray(classes,dtype=str)
    factors=np.ones(len(classes))
    def objective(values):
        pred=classes[np.argmax(probabilities*values,axis=1)]
        score=f1_score(y,pred,labels=classes,average='macro',zero_division=0)
        return score-.004*float(np.square(np.log(values)).mean())
    best=objective(factors)
    for _ in range(2):
        changed=False
        for column in range(len(classes)):
            chosen=factors.copy(); chosen_score=best
            for multiplier in [.7,.85,1.15,1.4]:
                trial=factors.copy(); trial[column]=np.clip(trial[column]*multiplier,.4,2.5)
                score=objective(trial)
                if score>chosen_score+.0005:
                    chosen=trial; chosen_score=score
            if chosen_score>best+.0005:
                factors=chosen; best=chosen_score; changed=True
        if not changed: break
    return {str(c):float(v) for c,v in zip(classes,factors)}


def adjusted_probabilities(probabilities,classes,factors):
    values=np.asarray(probabilities,dtype=float)*np.asarray([factors.get(str(c),1.) for c in classes])
    return values/np.maximum(values.sum(axis=1,keepdims=True),1e-15)
