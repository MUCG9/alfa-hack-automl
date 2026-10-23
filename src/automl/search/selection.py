"""Pure fixed-third marginal selector. Not connected to the runtime search."""
import numpy as np
from automl.evaluation.api import evaluate


def select_third(ranked_ids, matrices, truth, *, kind, metric, greater_is_better,
                 classes=(), scope='diagnostic_reused_public'):
    """Keep first two slots, rank third by a fixed equal-thirds metric gain.

    Caller owns immutable split/input verification and fitting-only generation.
    A scope label is a declaration, not proof of isolation or independent quality.
    No weights, models, calibration or representations are fitted here.
    """
    ranked_ids = tuple(ranked_ids)
    if len(ranked_ids) < 3 or len(set(ranked_ids)) != len(ranked_ids):
        raise ValueError('Need at least three uniquely identified candidates')
    if kind not in {'classification', 'regression'}:
        raise ValueError('Unsupported prediction kind')
    if scope not in {'inner_oof', 'diagnostic_reused_public'}:
        raise ValueError('Declare fitting-inner or diagnostic-only scope')
    if type(greater_is_better) is not bool:
        raise ValueError('Explicit metric direction is required')
    values = []
    reference = None
    for identity in ranked_ids:
        entry = matrices[identity]
        rows = np.asarray(entry['rows'])
        if (rows.ndim != 1 or rows.dtype.kind not in 'iu' or not len(rows)
                or np.any(rows < 0) or len(np.unique(rows)) != len(rows)):
            raise ValueError('Invalid original-row positions')
        if reference is None:
            reference = rows
        if not np.array_equal(rows, reference):
            raise ValueError('Candidate row order differs')
        matrix = np.asarray(entry['values'], dtype=float)
        if not np.isfinite(matrix).all():
            raise ValueError('Nonfinite predictions')
        if kind == 'classification':
            if (len(classes) < 2 or len(set(classes)) != len(classes)
                    or tuple(entry.get('classes', ())) != tuple(classes)
                    or matrix.shape != (len(rows), len(classes))
                    or (matrix < 0).any() or (matrix > 1).any()
                    or not np.allclose(matrix.sum(axis=1), 1., atol=1e-6, rtol=0)):
                raise ValueError('Invalid or misaligned class probabilities')
        elif matrix.shape != (len(rows),):
            raise ValueError('Invalid regression prediction shape')
        values.append(matrix)
    truth = np.asarray(truth)
    if truth.ndim != 1 or len(truth) != len(reference):
        raise ValueError('Truth does not align with row positions')
    if kind == 'classification' and not set(truth).issubset(classes):
        raise ValueError('Truth contains an unknown class')
    if kind == 'regression' and not np.isfinite(truth.astype(float)).all():
        raise ValueError('Nonfinite regression truth')

    def score(matrix):
        predicted = np.asarray(classes)[matrix.argmax(axis=1)] if kind == 'classification' else matrix
        result = evaluate(truth, predicted, kind, metric,
                          matrix if kind == 'classification' else None,
                          list(classes) if kind == 'classification' else None)[metric]
        if not np.isfinite(result):
            raise ValueError('Nonfinite selection metric')
        return float(result)

    base = score(.5 * values[0] + .5 * values[1])
    candidates = []
    direction = 1 if greater_is_better else -1
    for identity, matrix in zip(ranked_ids[2:], values[2:]):
        measured = score(values[0] / 3 + values[1] / 3 + matrix / 3)
        candidates.append({'model_id': identity, 'fixed_thirds_score': measured,
                           'raw_delta': measured - base,
                           'directional_gain': direction * (measured - base)})
    # Python max preserves original frozen order for exact ties.
    winner = max(candidates, key=lambda row: row['directional_gain'])
    return {'selected_ids': list(ranked_ids[:2]) + [winner['model_id']],
            'first_two_preserved': True, 'fixed_half_base_score': base,
            'third_slot': winner, 'candidates': candidates, 'scope': scope,
            'criterion': 'fixed_equal_thirds_metric_gain',
            'weights_fitted': False, 'new_model_fits': 0,
            'runtime_enabled': False}
