"""Class diagnostics and confidence bins; decision scores are explicitly labelled."""
import numpy as np

from automl.error_analysis.artifacts import score


def describe(task, value, groups, high_confidence):
    metrics = score(task, value.truth, value.predicted, value.probabilities, value.classes)
    matrix = np.asarray(metrics['confusion_matrix']['counts'])
    pairs = [(int(matrix[i, j]), value.classes[i], value.classes[j])
             for i in range(len(value.classes)) for j in range(len(value.classes)) if i != j and matrix[i, j]]
    result = {'metrics': metrics, 'rows': len(value.rows), 'probability_kind': value.probability_kind,
              'most_common_confusions': [{'count': n, 'true_class': a, 'predicted_class': b}
                                        for n, a, b in sorted(pairs, reverse=True)[:10]]}
    if len(value.training):
        result['independent_fitting_groups_per_class'] = {
            label: int(len(np.unique(groups['groups'][value.training][groups['truth'][value.training] == label])))
            for label in value.classes}
    if value.probabilities is None:
        result['confidence_diagnostics'] = {'status': 'unavailable', 'reason': 'No probability artifact'}
        return result
    confidence = value.probabilities.max(axis=1)
    correct = value.predicted == value.truth
    bins = []
    for i in range(10):
        mask = (confidence >= i / 10) & ((confidence < (i + 1) / 10) if i < 9 else (confidence <= 1))
        bins.append({'lower': i / 10, 'upper': (i + 1) / 10, 'rows': int(mask.sum()),
                     'mean_confidence': float(confidence[mask].mean()) if mask.any() else None,
                     'accuracy': float(correct[mask].mean()) if mask.any() else None})
    target = np.asarray(value.classes)[None, :] == value.truth[:, None]
    result['confidence_diagnostics'] = {
        'status': 'complete', 'threshold': high_confidence,
        'high_confidence_wrong_rows': int(((confidence >= high_confidence) & ~correct).sum()),
        'multiclass_brier_score': float(np.mean(np.sum((value.probabilities - target) ** 2, axis=1))),
        'bins': bins, 'interpretation': 'Descriptive only; decision-adjusted scores do not establish probability calibration.'}
    return result
