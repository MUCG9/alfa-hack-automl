from pathlib import Path
import re, json, hashlib, itertools
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, log_loss, mean_absolute_error, mean_absolute_percentage_error, mean_squared_error, mean_squared_log_error, r2_score, roc_auc_score, precision_recall_fscore_support, confusion_matrix
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold, GroupKFold, GroupShuffleSplit, KFold, train_test_split
from automl_infrastructure_observation_time import observation_values
from automl_evaluation_ranking import NDCGByQuery

def choose_validation(spec, train, mode='auto'):
    if mode == 'legacy' and spec.get('task_family') == 'pointwise_ranking':
        raise ValueError('Ranking requires held-out queries; legacy row validation is unsupported')
    if mode == 'legacy':
        return dict(spec, validation_strategy='legacy')
    if mode != 'auto':
        raise ValueError('Unknown validation selection mode')
    result = dict(spec)
    if spec.get('task_family') == 'pointwise_ranking':
        result.update(validation_strategy='group')
        semantic_group_hashes(result, train)
        if spec.get('time_candidate'):
            result['validation_warning'] = 'Ranking uses held-out queries; joint query/time validation is not implemented'
        return result
    if spec.get('time_candidate'):
        temporal = dict(result, validation_strategy='time', time_column=spec['time_candidate']['column'])
        try:
            make_time_split(temporal, train)
        except ValueError as exc:
            result['validation_warning'] = 'Forward split unavailable: ' + str(exc)[:250]
        else:
            if spec.get('group_candidate'):
                temporal['validation_warning'] = 'Both future-period and group hints exist; forward validation selected, joint unseen-group/forward validation is not implemented'
            return temporal
    if spec.get('group_candidate'):
        result.update(validation_strategy='group', group_column=spec['group_candidate']['column'])
        semantic_group_hashes(result, train)
    return result

def semantic_group_hashes(spec, train):
    column = spec.get('group_column')
    if column not in train or column == spec['target'] or train[column].isna().any():
        raise ValueError('Validation group must be a complete non-target input column')
    values = pd.util.hash_pandas_object(train[[column]], index=False).to_numpy(dtype='uint64')
    if len(np.unique(values)) < 2:
        raise ValueError('At least two independent groups are required')
    return values

def semantic_group_split(spec, train, feature_hashes, seed):
    groups = semantic_group_hashes(spec, train)
    y = train[spec['target']]
    positions = np.arange(len(train))
    stratified = iter(())
    if spec['kind'] == 'classification':
        independent = pd.DataFrame({'y': y.to_numpy(), 'g': groups}).groupby('y')['g'].nunique()
        folds = min(5, int(independent.min()))
        if folds >= 2:
            stratified = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed).split(positions, y, groups)
    options = itertools.chain(stratified, GroupShuffleSplit(n_splits=20, test_size=0.2, random_state=seed).split(positions, y, groups))
    for tr, va in options:
        if spec['kind'] == 'classification' and set(y.iloc[tr]) != set(y):
            continue
        if spec['kind'] == 'classification' and spec['metric'] == 'roc_auc' and (set(y.iloc[va]) != set(y)):
            continue
        overlap = len(set(groups[tr]) & set(groups[va]))
        if overlap:
            raise ValueError('Semantic validation group overlap')
        return (tr, va, {'method': 'explicit_semantic_group_holdout', 'group_column': spec['group_column'], 'seed': seed, 'train_rows': len(tr), 'validation_rows': len(va), 'shared_semantic_groups': overlap, 'shared_feature_hashes': len(set(feature_hashes[tr]) & set(feature_hashes[va])), 'split_sha256': hashlib.sha256(np.asarray(tr, dtype='<i8').tobytes() + np.asarray(va, dtype='<i8').tobytes()).hexdigest(), 'validation_class_counts': y.iloc[va].value_counts().to_dict() if spec['kind'] == 'classification' else None})
    raise ValueError('No group-safe split retains the required classes; row-wise fallback is forbidden')

def make_folds(spec, train, hashes, n_splits=5, seed=42):
    """Explicit full-CV mode; legacy make_split and its hashes remain unchanged."""
    if spec.get('validation_strategy') == 'time':
        raise ValueError('Time tasks require forward backtests, not exact-coverage random OOF')
    if not 2 <= n_splits <= 5:
        raise ValueError('CV requires 2..5 folds')
    y = train[spec['target']]
    positions = np.arange(len(train))
    if spec.get('validation_strategy') == 'group':
        hashes = semantic_group_hashes(spec, train)
    grouped = spec.get('validation_strategy') == 'group' or pd.Series(hashes).duplicated().any()
    if spec['kind'] == 'classification':
        counts = pd.DataFrame({'y': y.to_numpy(), 'h': hashes}).groupby('y')['h'].nunique() if grouped else y.value_counts()
        n_splits = min(n_splits, int(counts.min()))
        if n_splits < 2:
            raise ValueError('Too few independent groups per class for full CV')
        splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed) if grouped else StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    else:
        n_splits = min(n_splits, len(np.unique(hashes)))
        if n_splits < 2:
            raise ValueError('Too few groups for full CV')
        splitter = GroupKFold(n_splits=n_splits) if grouped else KFold(n_splits=n_splits, shuffle=True, random_state=seed)
    folds = []
    coverage = np.zeros(len(train), dtype=int)
    for fold, (tr, va) in enumerate(splitter.split(positions, y, groups=hashes if grouped else None)):
        if grouped and set(hashes[tr]) & set(hashes[va]):
            raise ValueError('CV group overlap')
        if spec['kind'] == 'classification' and set(y.iloc[tr]) != set(y):
            raise ValueError('CV training fold missing classes')
        coverage[va] += 1
        info = {'method': type(splitter).__name__, 'fold': fold, 'n_splits': n_splits, 'seed': seed, 'train_rows': len(tr), 'validation_rows': len(va), 'shared_feature_hashes': len(set(hashes[tr]) & set(hashes[va])), 'split_sha256': hashlib.sha256(np.asarray(tr, dtype='<i8').tobytes() + np.asarray(va, dtype='<i8').tobytes()).hexdigest(), 'validation_class_counts': y.iloc[va].value_counts().to_dict() if spec['kind'] == 'classification' else None}
        if spec['kind'] == 'classification':
            info['validation_missing_classes'] = sorted(map(str, set(y) - set(y.iloc[va])))
        folds.append((tr, va, info))
    if not np.all(coverage == 1):
        raise ValueError('OOF coverage must be exactly once')
    return folds

def make_time_split(spec, train, offset=0):
    column = spec.get('time_column') or (spec.get('time_candidate') or {}).get('column')
    if column not in spec['features']:
        raise ValueError('Time column must be an input feature')
    values, representation = observation_values(train[column])
    periods = np.sort(values.unique())
    if not 0 <= offset < len(periods) - 1:
        raise ValueError('Insufficient history for requested backtest')
    blocked = representation == 'datetime' or (spec.get('time_candidate') or {}).get('split_mode') == 'chronological_block'
    if blocked:
        width = max(1, len(periods) // 5)
        end = len(periods) - offset * width
        begin = max(1, end - width)
        if not 1 <= begin < end <= len(periods):
            raise ValueError('Insufficient history for requested forward block')
        cut = periods[begin]
        upper = periods[end - 1]
    else:
        cut = upper = periods[-1 - offset]
    tr = np.flatnonzero((values < cut).to_numpy())
    va = np.flatnonzero(((values >= cut) & (values <= upper)).to_numpy())
    if not len(tr) or not len(va):
        raise ValueError('Empty chronological partition')
    if spec['kind'] == 'classification' and set(train[spec['target']]) - set(train[spec['target']].iloc[tr]):
        raise ValueError('Time validation contains a class absent from history')
    signature = hashlib.sha256(np.asarray(tr, dtype='<i8').tobytes() + np.asarray(va, dtype='<i8').tobytes()).hexdigest()
    return (tr, va, {'method': 'forward_chronological_block' if blocked else 'forward_observation_period', 'time_column': column, 'cut': float(cut), 'offset': offset, 'train_rows': len(tr), 'validation_rows': len(va), 'excluded_future_rows': int((values > upper).sum()), 'split_sha256': signature})

def make_split(spec, train, hashes, seed=42):
    if spec.get('validation_strategy') == 'time':
        return make_time_split(spec, train)
    if spec.get('validation_strategy') == 'group':
        return semantic_group_split(spec, train, hashes, seed)
    positions = np.arange(len(train))
    kind = spec['kind']
    y = train[spec['target']]
    method = 'random_holdout_20pct'
    if kind == 'classification' and spec['duplicate_feature_rate'] > 0.05:
        groups_per_class = pd.DataFrame({'y': y, 'g': hashes}).groupby('y')['g'].nunique()
        n_splits = min(5, int(groups_per_class.min()))
        if n_splits >= 2:
            splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
            tr, va = next(splitter.split(positions, y, groups=hashes))
            method = f'stratified_group_feature_hash_{n_splits}fold_fold0'
        else:
            tr, va = train_test_split(positions, test_size=0.2, random_state=seed, stratify=y if y.value_counts().min() >= 2 else None)
            method = 'stratified_holdout_20pct_rare_group_fallback'
    else:
        tr, va = train_test_split(positions, test_size=0.2, random_state=seed, stratify=y if kind == 'classification' and y.value_counts().min() >= 2 else None)
        if kind == 'classification':
            method = 'stratified_holdout_20pct'
    if kind == 'classification' and set(y.iloc[va]) - set(y.iloc[tr]):
        raise ValueError('Validation contains classes absent in training')
    signature = hashlib.sha256(np.asarray(tr, dtype='<i8').tobytes() + np.asarray(va, dtype='<i8').tobytes()).hexdigest()
    overlap = len(set(hashes[tr]) & set(hashes[va]))
    return (np.asarray(tr), np.asarray(va), {'method': method, 'seed': seed, 'train_rows': len(tr), 'validation_rows': len(va), 'split_sha256': signature, 'shared_feature_hashes': overlap, 'validation_class_counts': y.iloc[va].value_counts().to_dict() if kind == 'classification' else None})

def evaluate(y, pred, kind, metric, proba=None, classes=None, groups=None, top_k=None, gain='linear'):
    if kind == 'regression':
        values = {'rmse': float(mean_squared_error(y, pred) ** 0.5), 'mae': float(mean_absolute_error(y, pred)), 'r2': float(r2_score(y, pred))}
        if metric == 'mse':
            values['mse'] = float(mean_squared_error(y, pred))
        if metric == 'ndcg':
            values['ndcg'] = NDCGByQuery(groups, top_k, gain)(y, pred)
        if metric == 'mape':
            values['mape'] = float(mean_absolute_percentage_error(y, pred))
        if metric == 'rmsle':
            if (np.asarray(y) < 0).any():
                raise ValueError('RMSLE requires non-negative targets')
            values['rmsle'] = float(mean_squared_log_error(y, np.maximum(pred, 0)) ** 0.5)
    else:
        labels = np.asarray(classes) if classes is not None else np.unique(np.concatenate([np.asarray(y), np.asarray(pred)]))
        values = {'macro_f1': float(f1_score(y, pred, labels=labels, average='macro', zero_division=0)), 'weighted_f1': float(f1_score(y, pred, labels=labels, average='weighted', zero_division=0)), 'accuracy': float(accuracy_score(y, pred)), 'per_class_f1': {str(c): float(v) for c, v in zip(labels, f1_score(y, pred, labels=labels, average=None, zero_division=0))}}
        if metric == 'balanced_accuracy':
            values['balanced_accuracy'] = float(balanced_accuracy_score(y, pred))
        precision, recall, _, support = precision_recall_fscore_support(y, pred, labels=labels, zero_division=0)
        values['per_class_diagnostics'] = {str(c): {'precision': float(p), 'recall': float(r), 'support': int(n)} for c, p, r, n in zip(labels, precision, recall, support)}
        values['confusion_matrix'] = {'classes': list(map(str, labels)), 'counts': confusion_matrix(y, pred, labels=labels).tolist()}
        if proba is not None:
            try:
                values['log_loss'] = float(log_loss(y, proba, labels=classes))
                if len(classes) == 2:
                    values['roc_auc'] = float(roc_auc_score((np.asarray(y) == classes[1]).astype(int), proba[:, 1]))
                else:
                    values['roc_auc'] = float(roc_auc_score(y, proba, labels=classes, multi_class='ovr', average='macro'))
            except ValueError:
                pass
    if metric not in values:
        raise ValueError(f'Cannot evaluate requested metric {metric}')
    return values
