import numpy as np
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, r2_score, mean_absolute_percentage_error, mean_squared_log_error
from automl_evaluation_ranking import NDCGByQuery

def lgbm_metric(spec, log_target=False, groups=None, top_k=None, gain='linear'):
    """sklearn wrapper supplies encoded class labels; do not confuse loss and F1."""
    metric = spec['metric']
    ranker = NDCGByQuery(groups, top_k, gain) if metric == 'ndcg' and groups is not None else None

    def evaluate(y_true, pred):
        y_true = np.asarray(y_true)
        pred = np.asarray(pred)
        if metric == 'ndcg':
            if ranker is None:
                raise ValueError('NDCG callback requires query groups')
            if log_target:
                y_true = np.expm1(y_true)
                pred = np.expm1(pred)
            value = ranker(y_true, pred)
        elif spec['kind'] == 'regression':
            if log_target:
                y_true = np.expm1(y_true)
                pred = np.expm1(pred)
            if metric == 'mae':
                value = np.abs(y_true - pred).mean()
            elif metric == 'r2':
                value = r2_score(y_true, pred)
            elif metric == 'mse':
                value = np.square(y_true - pred).mean()
            elif metric == 'mape':
                value = mean_absolute_percentage_error(y_true, pred)
            elif metric == 'rmsle':
                value = mean_squared_log_error(y_true, np.maximum(pred, 0)) ** 0.5
            else:
                value = np.sqrt(np.square(y_true - pred).mean())
        elif metric in {'macro_f1', 'weighted_f1', 'accuracy', 'balanced_accuracy'}:
            labels = pred.argmax(axis=1) if pred.ndim == 2 else (pred >= 0.5).astype(int)
            if metric == 'accuracy':
                value = accuracy_score(y_true, labels)
            elif metric == 'balanced_accuracy':
                value = balanced_accuracy_score(y_true, labels)
            else:
                classes = np.arange(pred.shape[1]) if pred.ndim == 2 else np.array([0, 1])
                value = f1_score(y_true, labels, labels=classes, average='macro' if metric == 'macro_f1' else 'weighted', zero_division=0)
        else:
            from sklearn.metrics import log_loss, roc_auc_score
            if metric == 'roc_auc':
                value = roc_auc_score(y_true, pred, multi_class='ovr', average='macro', labels=np.arange(pred.shape[1])) if pred.ndim == 2 and pred.shape[1] > 2 else roc_auc_score(y_true, pred[:, 1] if pred.ndim == 2 else pred)
            else:
                value = log_loss(y_true, pred, labels=np.arange(pred.shape[1]) if pred.ndim == 2 else [0, 1])
        return (metric, float(value), spec['greater_is_better'])
    return evaluate

def tune_class_factors(y, probabilities, classes):
    """Conservative decision-rule tuning, called only on an inner training holdout."""
    y = np.asarray(y, dtype=str)
    classes = np.asarray(classes, dtype=str)
    factors = np.ones(len(classes))

    def objective(values):
        pred = classes[np.argmax(probabilities * values, axis=1)]
        score = f1_score(y, pred, labels=classes, average='macro', zero_division=0)
        return score - 0.004 * float(np.square(np.log(values)).mean())
    best = objective(factors)
    for _ in range(2):
        changed = False
        for column in range(len(classes)):
            chosen = factors.copy()
            chosen_score = best
            for multiplier in [0.7, 0.85, 1.15, 1.4]:
                trial = factors.copy()
                trial[column] = np.clip(trial[column] * multiplier, 0.4, 2.5)
                score = objective(trial)
                if score > chosen_score + 0.0005:
                    chosen = trial
                    chosen_score = score
            if chosen_score > best + 0.0005:
                factors = chosen
                best = chosen_score
                changed = True
        if not changed:
            break
    return {str(c): float(v) for c, v in zip(classes, factors)}

def adjusted_probabilities(probabilities, classes, factors):
    values = np.asarray(probabilities, dtype=float) * np.asarray([factors.get(str(c), 1.0) for c in classes])
    return values / np.maximum(values.sum(axis=1, keepdims=True), 1e-15)
