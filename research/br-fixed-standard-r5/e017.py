"""Descriptive residual statistics; no inverse correction or weight fitting."""
import math
import numpy as np
from automl_error_analysis_artifacts import score

def describe(task, value):
    residual = value.predicted - value.truth
    squared = residual ** 2
    mse = float(squared.mean())
    tail = {}
    for fraction in (0.01, 0.05):
        count = max(1, math.ceil(len(residual) * fraction))
        tail[str(fraction)] = {'rows': count, 'squared_error_share': float(np.sort(squared)[-count:].sum() / squared.sum()) if squared.sum() else 0.0}
    return {'metrics': score(task, value.truth, value.predicted), 'rows': len(residual), 'bias': float(residual.mean()), 'residual_std': float(residual.std()), 'mse': mse, 'bias_squared': float(residual.mean() ** 2), 'residual_variance': float(residual.var()), 'residual_quantiles': {str(q): float(np.quantile(residual, q)) for q in (0, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 1)}, 'overprediction_fraction': float((residual > 0).mean()), 'underprediction_fraction': float((residual < 0).mean()), 'largest_error_concentration': tail}
