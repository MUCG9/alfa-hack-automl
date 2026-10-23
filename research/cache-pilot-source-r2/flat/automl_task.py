from pathlib import Path
import re, json, hashlib
import numpy as np
import pandas as pd
from automl_task_understanding_metrics import metric_from_text, LOWER_IS_BETTER
from automl_task_understanding_inputs import find_input, resolve_inputs
from automl_infrastructure_tables import read_input_table
from automl_infrastructure_observation_time import observation_values
from automl_task_understanding_probabilities import infer_positive_class

def infer_static_numeric(dictionary, train, features):
    """Schema-described construction attributes can refine recurring contexts."""
    result = []
    for row in dictionary.to_dict(orient='records'):
        column = row.get('feature')
        description = ' '.join((str(row.get(k, '')) for k in ['feature', 'description', 'description_ru'])).lower()
        if column in features and pd.api.types.is_numeric_dtype(train[column]) and re.search('built|construction|построй', description):
            result.append(column)
    return result

def infer_time_candidate(dictionary, train, test, features):
    """Conservative observation-period detection, without dataset-specific names."""
    candidates = []
    for row in dictionary.to_dict(orient='records'):
        column = row.get('feature')
        if column not in features:
            continue
        description = ' '.join((str(row.get(k, '')) for k in ['feature', 'role', 'dtype', 'description_ru', 'description'])).lower()
        if not re.search('year|period|timestamp|date|период|год.*наблюд|времен', description):
            continue
        if re.search('built|construction|построй|возраст|\\bage\\b|birth|duration|длитель', description):
            continue
        if not len(test):
            continue
        try:
            a, representation = observation_values(train[column])
            b, test_representation = observation_values(test[column])
        except ValueError:
            continue
        if representation != test_representation:
            continue
        if a.nunique() >= 3 and b.min() > a.max():
            candidates.append({'column': column, 'reason': 'Documented observation period; entire test range follows training range', 'representation': representation, 'split_mode': 'chronological_block' if representation == 'datetime' or a.nunique() > 100 else 'period', 'train_min': float(a.min()), 'train_max': float(a.max()), 'test_min': float(b.min()), 'test_max': float(b.max())})
    return candidates[0] if len(candidates) == 1 else None

class MultipleTargets(ValueError):

    def __init__(self, targets):
        self.targets = tuple(targets)
        super().__init__('Expected one target, got ' + repr(list(targets)))

def _read_tables(paths):
    train = read_input_table(paths['train'])
    test = read_input_table(paths['test'])
    sample = read_input_table(paths['sample_submission'])
    dictionary = read_input_table(paths['data_dictionary']) if 'data_dictionary' in paths else pd.DataFrame(columns=['feature', 'role'])
    return {'train': train, 'test': test, 'sample': sample, 'dictionary': dictionary}

def load_inputs(task_path: Path, allow_llm=False):
    root = task_path.resolve().parent
    text = task_path.read_text(encoding='utf-8-sig')
    resolution = {}
    accepted = {}

    def validate(paths):
        from automl_task_understanding_role_validation import validate_role_tables
        tables = _read_tables(paths)
        validate_role_tables(tables)
        accepted.update(tables)
    paths = resolve_inputs(root, text, allow_llm=allow_llm, resolution=resolution, validate=validate)
    tables = accepted or _read_tables(paths)
    return {'root': root, 'task_path': task_path.resolve(), 'text': text, 'paths': paths, **tables, 'file_role_resolution': resolution}

def discover(task_path: Path, target_override=None, loaded=None, allow_llm=False):
    loaded = load_inputs(task_path, allow_llm=allow_llm) if loaded is None else loaded
    if loaded['task_path'] != task_path.resolve():
        raise ValueError('Cached inputs belong to a different task')
    root, text, paths = (loaded[k] for k in ['root', 'text', 'paths'])
    train, test, sample, dictionary = (loaded[k] for k in ['train', 'test', 'sample', 'dictionary'])
    if train.columns.duplicated().any() or test.columns.duplicated().any():
        raise ValueError('Duplicate column names are unsupported')
    roles = dictionary['role'].astype(str).str.strip().str.lower() if 'role' in dictionary else pd.Series(dtype=str)
    groups = dictionary.loc[roles.isin(['group', 'group_id', 'validation_group', 'query', 'query_id']), 'feature'].tolist() if len(roles) else []
    groups = [c for c in groups if c in train and c in test]
    targets = dictionary.loc[roles.eq('target'), 'feature'].tolist() if len(roles) else []
    if not targets or any((c not in train for c in targets)):
        targets = [c for c in train if c not in test]
    if len(targets) > 1 and target_override is None:
        raise MultipleTargets(targets)
    if target_override is not None:
        if target_override not in targets:
            raise ValueError('Requested target is not declared in training data')
        target = target_override
    elif len(targets) == 1:
        target = targets[0]
    else:
        raise ValueError(f'Expected one target, got {targets}')
    all_ids = dictionary.loc[roles.eq('id'), 'feature'].tolist() if len(roles) else []
    ids = list(all_ids)
    ids = [c for c in ids if c in sample and c in test and (c not in targets)]
    if not ids:
        ids = [c for c in sample if c in test and c not in targets]
    if len(ids) > 1:
        raise ValueError('Ambiguous sample ID columns')
    identifier = ids[0] if ids else None
    if train[target].isna().any():
        raise ValueError('Training target contains missing values')
    if len(sample) != len(test):
        raise ValueError('Sample/test row counts differ')
    sample_positions = None
    if identifier is not None:
        if test[identifier].isna().any() or test[identifier].duplicated().any():
            raise ValueError('Test IDs are missing or duplicated')
        if sample[identifier].isna().any() or sample[identifier].duplicated().any():
            raise ValueError('Sample IDs are missing or duplicated')
        positions = pd.Index(test[identifier]).get_indexer(sample[identifier])
        if (positions < 0).any():
            raise ValueError('Sample/test ID values differ')
        if not np.array_equal(positions, np.arange(len(test))):
            sample_positions = positions.tolist()
    if len(targets) > 1:
        if target not in sample:
            raise ValueError('Multi-target output columns must match declared target names')
        sample = sample[[c for c in sample if c == identifier or c == target]].copy()
    features = [c for c in test if c not in set(all_ids + [identifier] + targets) and c in train]
    if not features:
        raise ValueError('No common features')
    ranking = bool(re.search('\\bndcg\\b|learning.to.rank|\\branking\\b|ранжирован', text.lower()))
    classification = bool(re.search('классификац|classification', text.lower()))
    regression = bool(re.search('регресси|regression', text.lower()))
    if ranking:
        kind = 'regression'
    elif regression and (not classification):
        kind = 'regression'
    elif classification and (not regression):
        kind = 'classification'
    elif not pd.api.types.is_numeric_dtype(train[target]):
        kind = 'classification'
    else:
        kind = 'classification' if train[target].nunique() <= min(20, max(2, len(train) // 100)) else 'regression'
    metric = metric_from_text(text, kind)
    ranking_parameters = {}
    if ranking:
        if metric != 'ndcg':
            raise ValueError('Only NDCG score-output ranking is implemented')
        if len(targets) > 1:
            raise ValueError('Multi-target ranking is not implemented')
        if len(groups) != 1:
            raise ValueError('Ranking requires one explicit query/group role in the dictionary')
        if not pd.api.types.is_numeric_dtype(train[target]) or (train[target] < 0).any():
            raise ValueError('Ranking relevance must be numeric and non-negative')
        match = re.search('ndcg\\s*@\\s*(\\d+)', text, re.I)
        cutoff = int(match.group(1)) if match else None
        if cutoff is not None and cutoff < 1:
            raise ValueError('NDCG top-k must be positive')
        gain = 'exponential' if re.search('2\\s*(?:\\*\\*|\\^)\\s*(?:relevance|label|rel|y)|exponential\\s+gain|экспоненциальн', text, re.I) else 'linear'
        features = [c for c in features if c != groups[0]]
        if not features:
            raise ValueError('Ranking has no non-query input features')
        ranking_parameters = {'task_family': 'pointwise_ranking', 'group_column': groups[0], 'ranking_k': cutoff, 'ranking_gain': gain, 'ranking_metric_definition': 'mean_query_ndcg_ties_averaged_' + gain, 'ranking_training_objective': 'pointwise regression surrogate, not LambdaRank'}
    classes = sorted(train[target].astype(str).unique().tolist()) if kind == 'classification' else None
    output_columns = [c for c in sample if c != identifier]
    if len(output_columns) > 1:
        if kind != 'classification' or set(map(str, output_columns)) != set(classes):
            raise ValueError('Multiple output columns require class-named probability columns')
        prediction_type = 'probability_matrix'
    elif len(output_columns) == 1:
        prediction_type = 'probability' if kind == 'classification' and metric in {'roc_auc', 'log_loss'} else 'value'
        if prediction_type == 'probability' and len(classes) != 2:
            raise ValueError('Multiclass probabilities require one sample column per class')
    else:
        raise ValueError('No prediction columns in sample_submission')
    hashes = pd.util.hash_pandas_object(train[features], index=False).to_numpy(dtype='uint64')
    dup_rate = float(pd.Series(hashes).duplicated().mean())
    text_features = [c for c in features if not pd.api.types.is_numeric_dtype(train[c]) and float(train[c].dropna().astype(str).str.len().mean()) > 50 and (train[c].nunique() > min(100, len(train) * 0.1))]
    spec = {'root': str(root), 'task_path': str(task_path.resolve()), 'paths': {k: str(v) for k, v in paths.items()}, 'target': target, 'id': identifier, 'features': features, 'kind': kind, 'metric': metric, 'greater_is_better': metric not in LOWER_IS_BETTER, 'n_train': len(train), 'n_test': len(test), 'n_features': len(features), 'duplicate_feature_rate': dup_rate, 'text_features': text_features, 'classes': classes, 'prediction_type': prediction_type, 'output_columns': output_columns, 'categorical_features': [str(row['feature']) for row in dictionary.to_dict(orient='records') if str(row.get('dtype', '')).lower() in {'category', 'categorical'} and row['feature'] in features], 'time_candidate': infer_time_candidate(dictionary, train, test, features), 'static_numeric_features': infer_static_numeric(dictionary, train, features), 'group_candidate': {'column': groups[0], 'reason': 'Explicit group role in the data dictionary'} if len(groups) == 1 else None}
    if sample_positions is not None:
        spec['sample_test_positions'] = sample_positions
    spec.update(ranking_parameters)
    if loaded.get('file_role_resolution'):
        spec['file_role_resolution'] = dict(loaded['file_role_resolution'])
    if prediction_type == 'probability':
        spec['positive_class'], spec['positive_class_source'] = infer_positive_class(text, classes, pd.api.types.is_numeric_dtype(train[target]))
    if len(targets) > 1:
        spec['sample_columns'] = list(sample.columns)
        spec['all_targets'] = list(targets)
    profile = {'kind': kind, 'metric': metric, 'rows': len(train), 'test_rows': len(test), 'feature_count': len(features), 'features': [{'name': c, 'dtype': str(train[c].dtype), 'unique': int(train[c].nunique()), 'missing_rate': round(float(train[c].isna().mean()), 4)} for c in features], 'target_summary': train[target].describe().astype(str).to_dict(), 'class_counts': train[target].value_counts().to_dict() if kind == 'classification' else None, 'duplicate_feature_rate': dup_rate, 'text_features': text_features, 'dictionary': dictionary.to_dict(orient='records')}
    return (spec, profile, train, test, sample, text, hashes)
