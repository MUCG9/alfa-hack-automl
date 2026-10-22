from pathlib import Path
import re,json,hashlib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score,balanced_accuracy_score,f1_score,log_loss,mean_absolute_error,mean_absolute_percentage_error,mean_squared_error,mean_squared_log_error,r2_score,roc_auc_score,precision_recall_fscore_support,confusion_matrix
from sklearn.model_selection import StratifiedGroupKFold,StratifiedKFold,GroupKFold,KFold,train_test_split


def make_folds(spec,train,hashes,n_splits=5,seed=42):
    """Explicit full-CV mode; legacy make_split and its hashes remain unchanged."""
    if spec.get('validation_strategy')=='time': raise ValueError('Time tasks require forward backtests, not exact-coverage random OOF')
    if not 2<=n_splits<=5: raise ValueError('CV requires 2..5 folds')
    y=train[spec['target']]; positions=np.arange(len(train))
    grouped=pd.Series(hashes).duplicated().any()
    if spec['kind']=='classification':
        counts=pd.DataFrame({'y':y.to_numpy(),'h':hashes}).groupby('y')['h'].nunique() if grouped else y.value_counts()
        n_splits=min(n_splits,int(counts.min()))
        if n_splits<2: raise ValueError('Too few independent groups per class for full CV')
        splitter=StratifiedGroupKFold(n_splits=n_splits,shuffle=True,random_state=seed) if grouped else StratifiedKFold(n_splits=n_splits,shuffle=True,random_state=seed)
    else:
        n_splits=min(n_splits,len(np.unique(hashes)))
        if n_splits<2: raise ValueError('Too few groups for full CV')
        splitter=GroupKFold(n_splits=n_splits) if grouped else KFold(n_splits=n_splits,shuffle=True,random_state=seed)
    folds=[]; coverage=np.zeros(len(train),dtype=int)
    for fold,(tr,va) in enumerate(splitter.split(positions,y,groups=hashes if grouped else None)):
        if grouped and set(hashes[tr])&set(hashes[va]): raise ValueError('CV group overlap')
        if spec['kind']=='classification' and set(y.iloc[tr])!=set(y): raise ValueError('CV training fold missing classes')
        coverage[va]+=1
        info={'method':type(splitter).__name__,'fold':fold,'n_splits':n_splits,'seed':seed,
              'train_rows':len(tr),'validation_rows':len(va),'shared_feature_hashes':len(set(hashes[tr])&set(hashes[va])),
              'split_sha256':hashlib.sha256(np.asarray(tr,dtype='<i8').tobytes()+np.asarray(va,dtype='<i8').tobytes()).hexdigest(),
              'validation_class_counts':y.iloc[va].value_counts().to_dict() if spec['kind']=='classification' else None}
        if spec['kind']=='classification':
            info['validation_missing_classes']=sorted(map(str,set(y)-set(y.iloc[va])))
        folds.append((tr,va,info))
    if not np.all(coverage==1): raise ValueError('OOF coverage must be exactly once')
    return folds

def make_time_split(spec,train,offset=0):
    column=spec.get('time_column') or (spec.get('time_candidate') or {}).get('column')
    if column not in spec['features']: raise ValueError('Time column must be an input feature')
    values=pd.to_numeric(train[column],errors='coerce')
    if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
        raise ValueError('Time split requires complete finite numeric observation periods')
    periods=np.sort(values.unique())
    if not 0<=offset<len(periods)-1: raise ValueError('Insufficient history for requested backtest')
    cut=periods[-1-offset]
    tr=np.flatnonzero((values<cut).to_numpy()); va=np.flatnonzero((values==cut).to_numpy())
    if spec['kind']=='classification' and set(train[spec['target']].iloc[va])-set(train[spec['target']].iloc[tr]):
        raise ValueError('Time validation contains a class absent from history')
    signature=hashlib.sha256(np.asarray(tr,dtype='<i8').tobytes()+np.asarray(va,dtype='<i8').tobytes()).hexdigest()
    return tr,va,{'method':'forward_observation_period','time_column':column,'cut':float(cut),'offset':offset,
                 'train_rows':len(tr),'validation_rows':len(va),'excluded_future_rows':int((values>cut).sum()),'split_sha256':signature}


def make_split(spec, train, hashes, seed=42):
    if spec.get('validation_strategy')=='time': return make_time_split(spec,train)
    positions = np.arange(len(train))
    kind = spec['kind']
    y = train[spec['target']]
    method = 'random_holdout_20pct'
    if kind == 'classification' and spec['duplicate_feature_rate'] > .05:
        groups_per_class = pd.DataFrame({'y':y,'g':hashes}).groupby('y')['g'].nunique()
        n_splits = min(5, int(groups_per_class.min()))
        if n_splits >= 2:
            splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
            tr, va = next(splitter.split(positions, y, groups=hashes))
            method = f'stratified_group_feature_hash_{n_splits}fold_fold0'
        else:
            tr, va = train_test_split(positions,test_size=.2,random_state=seed,
                                     stratify=y if y.value_counts().min()>=2 else None)
            method = 'stratified_holdout_20pct_rare_group_fallback'
    else:
        tr, va = train_test_split(positions, test_size=.2, random_state=seed,
                                 stratify=y if kind=='classification' and y.value_counts().min()>=2 else None)
        if kind=='classification':
            method='stratified_holdout_20pct'
    if kind=='classification' and set(y.iloc[va])-set(y.iloc[tr]):
        raise ValueError('Validation contains classes absent in training')
    signature=hashlib.sha256(np.asarray(tr,dtype='<i8').tobytes()+np.asarray(va,dtype='<i8').tobytes()).hexdigest()
    overlap=len(set(hashes[tr])&set(hashes[va]))
    return np.asarray(tr),np.asarray(va),{
        'method':method,'seed':seed,'train_rows':len(tr),'validation_rows':len(va),
        'split_sha256':signature,'shared_feature_hashes':overlap,
        'validation_class_counts': y.iloc[va].value_counts().to_dict() if kind=='classification' else None,
    }


def evaluate(y, pred, kind, metric, proba=None, classes=None):
    if kind=='regression':
        values={'rmse':float(mean_squared_error(y,pred)**.5),
                'mae':float(mean_absolute_error(y,pred)), 'r2':float(r2_score(y,pred))}
        if metric=='mse': values['mse']=float(mean_squared_error(y,pred))
        if metric=='mape': values['mape']=float(mean_absolute_percentage_error(y,pred))
        if metric=='rmsle':
            if (np.asarray(y)<0).any(): raise ValueError('RMSLE requires non-negative targets')
            values['rmsle']=float(mean_squared_log_error(y,np.maximum(pred,0))**.5)
    else:
        labels=np.asarray(classes) if classes is not None else np.unique(np.concatenate([np.asarray(y),np.asarray(pred)]))
        values={'macro_f1':float(f1_score(y,pred,labels=labels,average='macro',zero_division=0)),
                'weighted_f1':float(f1_score(y,pred,labels=labels,average='weighted',zero_division=0)),
                'accuracy':float(accuracy_score(y,pred)),
                'per_class_f1':{str(c):float(v) for c,v in zip(
                    labels,f1_score(y,pred,labels=labels,average=None,zero_division=0))}}
        if metric=='balanced_accuracy': values['balanced_accuracy']=float(balanced_accuracy_score(y,pred))
        precision,recall,_,support=precision_recall_fscore_support(y,pred,labels=labels,zero_division=0)
        values['per_class_diagnostics']={str(c):{'precision':float(p),'recall':float(r),'support':int(n)} for c,p,r,n in zip(labels,precision,recall,support)}
        values['confusion_matrix']={'classes':list(map(str,labels)),'counts':confusion_matrix(y,pred,labels=labels).tolist()}
        if proba is not None:
            try:
                values['log_loss']=float(log_loss(y,proba,labels=classes))
                if len(classes)==2:
                    values['roc_auc']=float(roc_auc_score((np.asarray(y)==classes[1]).astype(int),proba[:,1]))
                else:
                    values['roc_auc']=float(roc_auc_score(y,proba,labels=classes,multi_class='ovr',average='macro'))
            except ValueError:
                pass
    if metric not in values:
        raise ValueError(f'Cannot evaluate requested metric {metric}')
    return values
