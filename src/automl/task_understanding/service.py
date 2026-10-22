from pathlib import Path
import re,json,hashlib
import numpy as np
import pandas as pd
from automl.task_understanding.metrics import metric_from_text,LOWER_IS_BETTER
from automl.task_understanding.inputs import find_input,resolve_inputs
from automl.infrastructure.tables import read_input_table


def infer_static_numeric(dictionary,train,features):
    """Schema-described construction attributes can refine recurring contexts."""
    result=[]
    for row in dictionary.to_dict(orient='records'):
        column=row.get('feature')
        description=' '.join(str(row.get(k,'')) for k in ['feature','description','description_ru']).lower()
        if column in features and pd.api.types.is_numeric_dtype(train[column]) and re.search(r'built|construction|построй',description):
            result.append(column)
    return result


def infer_time_candidate(dictionary,train,test,features):
    """Conservative observation-period detection, without dataset-specific names."""
    candidates=[]
    for row in dictionary.to_dict(orient='records'):
        column=row.get('feature')
        if column not in features: continue
        description=' '.join(str(row.get(k,'')) for k in ['feature','role','dtype','description_ru','description']).lower()
        if not re.search(r'year|period|timestamp|date|период|год.*наблюд|времен',description): continue
        if re.search(r'built|construction|построй|возраст|duration|длитель',description): continue
        a=pd.to_numeric(train[column],errors='coerce'); b=pd.to_numeric(test[column],errors='coerce')
        if a.isna().any() or b.isna().any() or not len(b): continue
        if not np.isfinite(a.to_numpy(dtype=float)).all() or not np.isfinite(b.to_numpy(dtype=float)).all(): continue
        if 3<=a.nunique()<=100 and b.min()>a.max():
            candidates.append({'column':column,'reason':'Documented observation period; entire test range follows training range',
                               'train_min':float(a.min()),'train_max':float(a.max()),'test_min':float(b.min()),'test_max':float(b.max())})
    return candidates[0] if len(candidates)==1 else None
def discover(task_path: Path):
    root = task_path.resolve().parent
    text = task_path.read_text(encoding='utf-8-sig')
    paths = resolve_inputs(root,text)
    train = read_input_table(paths['train'])
    test = read_input_table(paths['test'])
    sample = read_input_table(paths['sample_submission'])
    dictionary = read_input_table(paths['data_dictionary']) if 'data_dictionary' in paths else pd.DataFrame(columns=['feature','role'])
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
        'kind': kind, 'metric': metric, 'greater_is_better': metric not in LOWER_IS_BETTER,
        'n_train': len(train), 'n_test': len(test), 'n_features': len(features),
        'duplicate_feature_rate': dup_rate,
        'text_features': text_features,
        'classes': classes, 'prediction_type':prediction_type,'output_columns':output_columns,
        'categorical_features': [str(row['feature']) for row in dictionary.to_dict(orient='records')
                                 if str(row.get('dtype','')).lower() in {'category','categorical'} and row['feature'] in features],
        'time_candidate':infer_time_candidate(dictionary,train,test,features),
        'static_numeric_features':infer_static_numeric(dictionary,train,features),
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
