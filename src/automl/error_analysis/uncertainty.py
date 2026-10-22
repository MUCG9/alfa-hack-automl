"""Conditional paired cluster bootstrap; no retraining uncertainty is claimed."""
import numpy as np

from automl.error_analysis.comparisons import pool


def _scorer(task, value):
    if task.kind == 'regression':
        # The first implementation supports RMSE/MSE/MAE bootstrap explicitly.
        error = value.predicted - value.truth
        loss = np.abs(error) if task.metric == 'mae' else error ** 2
        def regression_score(weights):
            mean = np.average(loss, weights=weights)
            return float(mean ** .5 if task.metric == 'rmse' else mean)
        return regression_score
    classes = list(value.classes)
    actual = np.array([classes.index(v) for v in value.truth])
    predicted = np.array([classes.index(v) for v in value.predicted])
    codes = actual * len(classes) + predicted
    def classification_score(weights):
        matrix = np.bincount(codes, weights=weights, minlength=len(classes)**2).reshape(len(classes), len(classes))
        denom = matrix.sum(axis=0) + matrix.sum(axis=1)
        return float(np.divide(2 * matrix.diagonal(), denom, out=np.zeros(len(classes)), where=denom > 0).mean())
    return classification_score


def paired_bootstrap(task, a, b, groups, protocol, guard):
    unique, inverse = np.unique(groups, return_inverse=True)
    if len(unique) < protocol.min_bootstrap_groups:
        return {'status': 'unavailable', 'reason': 'Too few independent resampling units', 'units': len(unique)}
    rng = np.random.default_rng(protocol.bootstrap_seed)
    score_a, score_b = _scorer(task, a), _scorer(task, b)
    deltas, control, candidate = [], [], []
    for _ in range(protocol.bootstrap_replicates):
        guard.check()
        draws = rng.multinomial(len(unique), np.full(len(unique), 1 / len(unique)))
        weights = draws[inverse]
        first, second = score_a(weights), score_b(weights)
        control.append(first)
        candidate.append(second)
        deltas.append(second - first)
    return {'status': 'complete', 'replicates': protocol.bootstrap_replicates, 'units': len(unique),
            'delta_candidate_minus_control': b.metrics[task.metric] - a.metrics[task.metric],
            'paired_percentile_95': np.percentile(deltas, [2.5, 97.5]).tolist(),
            'control_percentile_95': np.percentile(control, [2.5, 97.5]).tolist(),
            'candidate_percentile_95': np.percentile(candidate, [2.5, 97.5]).tolist(),
            'fraction_favorable_resamples': float(np.mean(np.array(deltas) > 0 if task.greater_is_better else np.array(deltas) < 0)),
            'interpretation': 'Conditional on fixed predictions; exploratory, unadjusted for multiple comparisons; not refit/private uncertainty or a probability the hypothesis is true.'}


def profiles(data, guard):
    task, protocol = data.request.task, data.protocol
    supported = task.metric == 'macro_f1' if task.kind == 'classification' else task.metric in ('rmse', 'mse', 'mae')
    if not supported or protocol.bootstrap_replicates == 0:
        return None, 'Bootstrap disabled or unsupported for the requested metric'
    comparisons = []
    control = data.request.control_model_id
    candidates = [m for m in data.alignment['models'] if m != control]
    units = data.times if data.request.prediction_scope == 'forward' else data.groups
    for model in candidates:
        for fold in data.alignment['folds']:
            a, b = data.predictions[(control, fold)], data.predictions[(model, fold)]
            comparisons.append({'candidate': model, 'fold': fold,
                                **paired_bootstrap(task, a, b, units[a.rows], protocol, guard)})
        if data.request.prediction_scope == 'oof':
            a, b = pool(data, control), pool(data, model)
            comparisons.append({'candidate': model, 'fold': 'pooled_oof',
                                **paired_bootstrap(task, a, b, units[a.rows], protocol, guard)})
    if not any(c['status'] == 'complete' for c in comparisons):
        return None, 'No paired comparison has enough independent groups/temporal blocks'
    return {'unit': 'observation_period_block' if data.request.prediction_scope == 'forward' else data.alignment['independence_unit'],
            'seed': protocol.bootstrap_seed, 'comparisons': comparisons, 'model_refits': 0}, None
