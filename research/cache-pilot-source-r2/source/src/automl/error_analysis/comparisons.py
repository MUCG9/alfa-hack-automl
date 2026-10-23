"""Paired errors, fixed blends and leave-one-member-out diagnostics."""
from dataclasses import replace
import itertools
import numpy as np
from scipy.stats import rankdata

from automl.error_analysis.artifacts import score
from automl.error_analysis.regression import describe as describe_regression
from automl.error_analysis.classification import describe as describe_classification


def correlation(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if len(a) < 2 or np.ptp(a) == 0 or np.ptp(b) == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def combine(task, values, weights, name):
    weights = np.asarray(weights, dtype=float)
    weights = weights / weights.sum()
    first = values[0]
    if any(not np.array_equal(v.rows, first.rows) or not np.array_equal(v.truth, first.truth) for v in values):
        raise ValueError('Cannot blend misaligned predictions')
    if task.kind == 'classification':
        if any(v.probabilities is None for v in values):
            return None
        probabilities = sum(w * v.probabilities for w, v in zip(weights, values))
        predicted = np.asarray(first.classes)[probabilities.argmax(axis=1)]
    else:
        probabilities = None
        predicted = sum(w * v.predicted for w, v in zip(weights, values))
    return replace(first, model_id=name, probabilities=probabilities, predicted=predicted,
                   probability_kind='raw' if all(v.probability_kind == 'raw' for v in values) else 'decision_adjusted',
                   metrics=score(task, first.truth, predicted, probabilities, first.classes))


def error_overlap(truth, a, b):
    wa, wb = a != truth, b != truth
    both_correct = int((~wa & ~wb).sum())
    both_wrong = int((wa & wb).sum())
    correct_a = int((~wa & wb).sum())
    correct_b = int((wa & ~wb).sum())
    denom = both_correct * both_wrong + correct_a * correct_b
    return {'rows': len(truth), 'both_wrong': both_wrong, 'double_fault_rate': both_wrong / len(truth),
            'disagreement_rate': float((a != b).mean()), 'error_indicator_correlation': correlation(wa, wb),
            'candidate_correct_control_wrong': correct_b, 'control_correct_candidate_wrong': correct_a,
            'q_statistic': (both_correct * both_wrong - correct_a * correct_b) / denom if denom else None}


def paired(task, a, b):
    primary = task.metric
    result = {'control': a.metrics[primary], 'candidate': b.metrics[primary],
              'candidate_minus_control': b.metrics[primary] - a.metrics[primary]}
    blend = combine(task, [a, b], [.5, .5], 'fixed-half')
    result['fixed_half_blend'] = blend.metrics[primary] if blend else None
    if task.kind == 'classification':
        result['errors'] = error_overlap(a.truth, a.predicted, b.predicted)
        result['per_class_errors'] = {}
        for label in a.classes:
            mask = a.truth == label
            result['per_class_errors'][label] = error_overlap(a.truth[mask], a.predicted[mask], b.predicted[mask]) if mask.any() else None
        result['per_class_f1_delta'] = {label: b.metrics['per_class_f1'][label] - a.metrics['per_class_f1'][label] for label in a.classes}
        result['probability_correlation'] = correlation(a.probabilities.ravel(), b.probabilities.ravel()) if a.probabilities is not None and b.probabilities is not None else None
    else:
        ea, eb = a.predicted - a.truth, b.predicted - b.truth
        result['residuals'] = {'pearson': correlation(ea, eb), 'spearman': correlation(rankdata(ea), rankdata(eb)),
            'covariance': float(np.mean((ea - ea.mean()) * (eb - eb.mean()))),
            'mean_product': float(np.mean(ea * eb)), 'control_bias': float(ea.mean()), 'candidate_bias': float(eb.mean()),
            'candidate_smaller_absolute_error_fraction': float((np.abs(eb) < np.abs(ea)).mean())}
    return result


def pool(data, model):
    values = [v for (name, _), v in sorted(data.predictions.items()) if name == model]
    order = np.argsort(np.concatenate([v.rows for v in values]))
    rows = np.concatenate([v.rows for v in values])[order]
    truth = np.concatenate([v.truth for v in values])[order]
    predicted = np.concatenate([v.predicted for v in values])[order]
    probabilities = np.concatenate([v.probabilities for v in values])[order] if all(v.probabilities is not None for v in values) else None
    first = values[0]
    return replace(first, fold_id='pooled_oof', training=np.array([], dtype=np.int64), rows=rows, truth=truth,
                   predicted=predicted, probabilities=probabilities,
                   metrics=score(data.request.task, truth, predicted, probabilities, first.classes))


def model_profiles(data, guard):
    task = data.request.task
    result = {}
    group_info = {'groups': data.groups, 'truth': data.dataset[task.target].to_numpy(dtype=str)}
    for model in data.alignment['models']:
        summaries = {}
        for fold in data.alignment['folds']:
            guard.check()
            value = data.predictions[(model, fold)]
            summaries[fold] = (describe_regression(task, value) if task.kind == 'regression' else
                               describe_classification(task, value, group_info, data.protocol.high_confidence))
        result[model] = {'folds': summaries, 'fold_mean': {task.metric: float(np.mean([s['metrics'][task.metric] for s in summaries.values()]))}}
        if data.request.prediction_scope == 'oof':
            pooled = pool(data, model)
            result[model]['pooled_oof'] = (describe_regression(task, pooled) if task.kind == 'regression' else
                                         describe_classification(task, pooled, group_info, data.protocol.high_confidence))
        else:
            result[model]['pooled_oof'] = {'status': 'unavailable', 'reason': 'Not exactly-once OOF'}
    if task.kind == 'classification':
        import pandas as pd
        grouped = pd.DataFrame({'group': data.groups, 'label': group_info['truth']}).groupby('group').label.nunique()
        conflicts = set(grouped[grouped > 1].index)
        conflict_summary = {'groups_with_conflicting_labels': len(conflicts),
                            'rows_in_conflicting_groups': int(np.isin(data.groups, list(conflicts)).sum()),
                            'interpretation': 'Conflicts under the declared grouping; not an irreducible Macro F1 bound.'}
    else:
        conflict_summary = None
    return {'models': result, 'label_conflicts': conflict_summary}


def comparison_profiles(data, guard):
    models = [data.request.control_model_id] + [m for m in data.alignment['models'] if m != data.request.control_model_id]
    pair_count = len(models) * (len(models) - 1) // 2
    pairs = itertools.islice(itertools.combinations(models, 2), data.protocol.max_pairs)
    result = []
    for a, b in pairs:
        folds = {}
        for fold in data.alignment['folds']:
            guard.check()
            folds[fold] = paired(data.request.task, data.predictions[(a, fold)], data.predictions[(b, fold)])
        record = {'models': [a, b], 'folds': folds,
                  'fold_mean_delta': float(np.mean([f['candidate_minus_control'] for f in folds.values()]))}
        if data.request.prediction_scope == 'oof':
            record['pooled_oof'] = paired(data.request.task, pool(data, a), pool(data, b))
        result.append(record)
    declared = []
    for blend in data.protocol.blends:
        rows = {}
        for fold in data.alignment['folds']:
            guard.check()
            values = [data.predictions[(model, fold)] for model in blend.models]
            mixed = combine(data.request.task, values, blend.weights, blend.name)
            if mixed is None:
                rows[fold] = {'status': 'unavailable', 'reason': 'Missing probabilities'}
                continue
            ablations = []
            for i, model in enumerate(blend.models):
                reduced = combine(data.request.task, values[:i] + values[i+1:], blend.weights[:i] + blend.weights[i+1:], 'without-' + model)
                ablations.append({'removed': model, 'metrics': reduced.metrics,
                                  'delta_without_minus_full': reduced.metrics[data.request.task.metric] - mixed.metrics[data.request.task.metric]})
            rows[fold] = {'status': 'complete', 'metrics': mixed.metrics, 'ablations': ablations}
        declared.append({'name': blend.name, 'models': list(blend.models), 'weights': list(blend.weights), 'folds': rows,
                         'weights_fitted': False, 'ablation_semantics': 'Renormalized fixed remaining weights; no refit or reoptimization.'})
    return {'pairs': result, 'pairs_omitted_by_protocol_cap': max(0, pair_count - data.protocol.max_pairs),
            'declared_blends': declared, 'selection_performed': False}
