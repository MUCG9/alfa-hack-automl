"""Task discovery, immutable validation and submission contracts.

All modules deliberately live at ZIP root, as required by the platform.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, f1_score, log_loss, mean_absolute_error,
    mean_squared_error, r2_score, roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold, train_test_split


def atomic_json(path: Path, value) -> None:
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    temp.replace(path)


def find_input(root: Path, name: str, text: str) -> Path:
    matches = re.findall(r'`([^`\n]*' + re.escape(name) + r')`', text)
    for match in matches:
        candidate = (root / match).resolve()
        if candidate.is_relative_to(root) and candidate.is_file():
            return candidate
    direct = root / name
    if direct.is_file():
        return direct
    candidates = sorted(root.rglob(name))
    if len(candidates) != 1:
        raise ValueError(f'Expected one {name} under task directory, found {len(candidates)}')
    return candidates[0]


def metric_from_text(text: str, kind: str) -> str:
    text = text.lower()
    if kind == 'regression':
        if re.search(r'\brmse\b|root.mean.square|среднеквадрат', text):
            return 'rmse'
        if re.search(r'\bmae\b|mean.absolute.error', text):
            return 'mae'
        if re.search(r'\br2\b|r\^2|r²', text):
            return 'r2'
        return 'rmse'
    if re.search(r'macro[\s_-]*f1|f1[^\n]{0,30}macro', text):
        return 'macro_f1'
    if 'roc' in text and 'auc' in text:
        return 'roc_auc'
    if 'logloss' in text or 'log loss' in text or 'log_loss' in text:
        return 'log_loss'
    if re.search(r'weighted[\s_-]*f1', text):
        return 'weighted_f1'
    if 'accuracy' in text:
        return 'accuracy'
    return 'macro_f1'


def discover(task_path: Path):
    root = task_path.resolve().parent
    text = task_path.read_text(encoding='utf-8-sig')
    paths = {name: find_input(root, name + '.csv', text) for name in
             ['train', 'test', 'data_dictionary', 'sample_submission']}
    train = pd.read_csv(paths['train'])
    test = pd.read_csv(paths['test'])
    sample = pd.read_csv(paths['sample_submission'])
    dictionary = pd.read_csv(paths['data_dictionary'])
    if train.columns.duplicated().any() or test.columns.duplicated().any():
        raise ValueError('Duplicate column names are unsupported')
    roles = dictionary['role'].astype(str).str.lower() if 'role' in dictionary else pd.Series(dtype=str)
    targets = dictionary.loc[roles.eq('target'), 'feature'].tolist() if len(roles) else []
    if len(targets) != 1:
        targets = [c for c in train if c not in test]
    if len(targets) != 1:
        raise ValueError(f'Expected one target, got {targets}')
    target = targets[0]
    all_ids = dictionary.loc[roles.eq('id'), 'feature'].tolist() if len(roles) else []
    ids = list(all_ids)
    ids = [c for c in ids if c in sample and c != target]
    if not ids:
        ids = [c for c in sample if c in test and c != target]
    if len(ids) != 1:
        raise ValueError('Expected one sample ID column')
    identifier = ids[0]
    if train[target].isna().any():
        raise ValueError('Training target contains missing values')
    if test[identifier].isna().any() or test[identifier].duplicated().any():
        raise ValueError('Test IDs are missing or duplicated')
    if sample[identifier].tolist() != test[identifier].tolist():
        raise ValueError('Sample/test ID values or order differ')
    features = [c for c in test if c not in set(all_ids+[identifier,target]) and c in train]
    if not features:
        raise ValueError('No common features')
    classification = bool(re.search(r'классификац|classification', text.lower()))
    regression = bool(re.search(r'регресси|regression', text.lower()))
    if regression and not classification:
        kind = 'regression'
    elif classification and not regression:
        kind = 'classification'
    elif not pd.api.types.is_numeric_dtype(train[target]):
        kind = 'classification'
    else:
        kind = 'classification' if train[target].nunique() <= min(20, max(2, len(train)//100)) else 'regression'
    metric = metric_from_text(text, kind)
    classes=sorted(train[target].astype(str).unique().tolist()) if kind=='classification' else None
    output_columns=[c for c in sample if c!=identifier]
    if len(output_columns)>1:
        if kind!='classification' or set(map(str,output_columns))!=set(classes):
            raise ValueError('Multiple output columns require class-named probability columns')
        prediction_type='probability_matrix'
    elif len(output_columns)==1:
        prediction_type='probability' if kind=='classification' and metric in {'roc_auc','log_loss'} else 'value'
        if prediction_type=='probability' and len(classes)!=2:
            raise ValueError('Multiclass probabilities require one sample column per class')
    else:
        raise ValueError('No prediction columns in sample_submission')
    hashes = pd.util.hash_pandas_object(train[features], index=False).to_numpy(dtype='uint64')
    dup_rate = float(pd.Series(hashes).duplicated().mean())
    text_features=[c for c in features if not pd.api.types.is_numeric_dtype(train[c])
                   and float(train[c].dropna().astype(str).str.len().mean())>50
                   and train[c].nunique()>min(100,len(train)*.1)]
    spec = {
        'root': str(root), 'task_path': str(task_path.resolve()),
        'paths': {k: str(v) for k, v in paths.items()},
        'target': target, 'id': identifier, 'features': features,
        'kind': kind, 'metric': metric, 'greater_is_better': metric not in {'rmse','mae','log_loss'},
        'n_train': len(train), 'n_test': len(test), 'n_features': len(features),
        'duplicate_feature_rate': dup_rate,
        'text_features': text_features,
        'classes': classes, 'prediction_type':prediction_type,'output_columns':output_columns,
    }
    profile = {
        'kind': kind, 'metric': metric, 'rows': len(train), 'test_rows': len(test),
        'feature_count':len(features), 'features': [
            {'name': c, 'dtype': str(train[c].dtype), 'unique': int(train[c].nunique()),
             'missing_rate': round(float(train[c].isna().mean()),4)} for c in features
        ],
        'target_summary': train[target].describe().astype(str).to_dict(),
        'class_counts': train[target].value_counts().to_dict() if kind=='classification' else None,
        'duplicate_feature_rate': dup_rate,
        'text_features': text_features,
        'dictionary': dictionary.to_dict(orient='records'),
    }
    return spec, profile, train, test, sample, text, hashes


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


def save_submission(spec, sample, test, predictions, path):
    result=sample.copy()
    if len(predictions)!=len(test):
        raise ValueError('Wrong prediction length')
    prediction_type=spec.get('prediction_type','value')
    output_columns=spec.get('output_columns',[spec['target']])
    if prediction_type=='probability_matrix':
        values=np.asarray(predictions,dtype=float)
        if values.shape!=(len(test),len(output_columns)) or not np.isfinite(values).all() or (values<0).any() or (values>1).any() or not np.allclose(values.sum(axis=1),1,atol=1e-5):
            raise ValueError('Invalid probability matrix')
        result[output_columns]=values
    else:
        result[output_columns[0]]=np.asarray(predictions).reshape(-1)
    if result.isna().any().any():
        raise ValueError('Null submission values')
    if spec['kind']=='regression' and not np.isfinite(pd.to_numeric(result[output_columns[0]],errors='coerce')).all():
        raise ValueError('Non-finite regression predictions')
    if spec['kind']=='classification':
        if prediction_type=='probability':
            values=pd.to_numeric(result[output_columns[0]],errors='coerce').to_numpy(dtype=float)
            if not np.isfinite(values).all() or (values<0).any() or (values>1).any():
                raise ValueError('Invalid probability predictions')
        elif prediction_type=='value' and spec.get('classes') and set(result[output_columns[0]].astype(str))-set(spec['classes']):
            raise ValueError('Unknown predicted classification labels')
    if list(result.columns)!=list(sample.columns) or result[spec['id']].tolist()!=test[spec['id']].tolist():
        raise ValueError('Submission contract violation')
    temp=path.with_suffix('.csv.tmp')
    result.to_csv(temp,index=False,encoding='utf-8')
    temp.replace(path)


def dummy_predictions(spec, train, n):
    y=train[spec['target']]
    if spec.get('prediction_type')=='probability':
        return np.repeat(float((y.astype(str)==spec['classes'][1]).mean()),n)
    if spec.get('prediction_type')=='probability_matrix':
        frequencies=y.astype(str).value_counts(normalize=True)
        return np.tile([frequencies.get(str(c),0) for c in spec['output_columns']],(n,1))
    value=float(y.mean()) if spec['kind']=='regression' else y.mode().iloc[0]
    return np.repeat(value,n)
