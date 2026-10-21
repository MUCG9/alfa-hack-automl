from pathlib import Path
import re,json,hashlib
import numpy as np
import pandas as pd
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

