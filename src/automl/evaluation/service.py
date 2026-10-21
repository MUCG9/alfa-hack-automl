from pathlib import Path
import re,json,hashlib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score,f1_score,log_loss,mean_absolute_error,mean_squared_error,r2_score,roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold,train_test_split
def make_split(spec, train, hashes, seed=42):
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
    else:
        labels=np.asarray(classes) if classes is not None else np.unique(np.concatenate([np.asarray(y),np.asarray(pred)]))
        values={'macro_f1':float(f1_score(y,pred,labels=labels,average='macro',zero_division=0)),
                'weighted_f1':float(f1_score(y,pred,labels=labels,average='weighted',zero_division=0)),
                'accuracy':float(accuracy_score(y,pred)),
                'per_class_f1':{str(c):float(v) for c,v in zip(
                    labels,f1_score(y,pred,labels=labels,average=None,zero_division=0))}}
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

