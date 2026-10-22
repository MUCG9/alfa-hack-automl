"""Recognize supported objectives without confusing diagnostic metrics with them."""
import re

REGRESSION = {
    'ndcg': r'\bndcg\b|normalized[\s_-]*discounted[\s_-]*cumulative[\s_-]*gain',
    'rmsle': r'\brmsle\b|root\s+mean\s+squared\s+logarithmic',
    'rmse': r'\brmse\b|root[\s_-]*mean[\s_-]*squared?|среднеквадрат',
    'mape': r'\bmape\b|mean[\s_-]*absolute[\s_-]*percentage',
    'mae': r'\bmae\b|mean[\s_-]*absolute[\s_-]*error',
    'mse': r'\bmse\b|(?<!root )mean[\s_-]*squared[\s_-]*error',
    'r2': r'\br2\b|r\^2|r²',
}
CLASSIFICATION = {
    'balanced_accuracy': r'balanced[\s_-]*accuracy|сбалансированн\w*\s+точност',
    'macro_f1': r'macro[\s_-]*f1|f1[^\n]{0,30}macro',
    'roc_auc': r'roc[\s_-]*auc|\bauc\b',
    'log_loss': r'log[\s_-]*loss|cross[\s_-]*entropy',
    'weighted_f1': r'weighted[\s_-]*f1|f1[^\n]{0,30}weighted',
    'accuracy': r'\baccuracy\b',
}
LOWER_IS_BETTER = frozenset({'rmse', 'mae', 'mse', 'mape', 'rmsle', 'log_loss'})


def metric_from_text(text, kind):
    patterns = REGRESSION if kind == 'regression' else CLASSIFICATION
    normalized = text.lower().replace('**', '').replace('`', '')
    # A declared primary objective overrides metrics mentioned as diagnostics.
    declarations = [
        r'(?:primary|main|основн\w*)\s+(?:metric|метрик\w*)\s*[:=—–-]?\s*',
        r'(?:metric|метрика(?:\s+оценки)?)\s*[:=—–-]\s*',
        r'\bmetric\s+(?=[a-z])',
    ]
    for declaration_number, declaration in enumerate(declarations):
        for match in re.finditer(declaration, normalized):
            clause = re.split(r'[\n;]|\.\s', normalized[match.end():], maxsplit=1)[0][:250]
            found = [(m.start(), order, name) for order, (name, pattern) in enumerate(patterns.items())
                     if (m := re.search(pattern, clause))]
            if found:
                return min(found)[2]
            if declaration_number < 2 and clause.strip():
                raise ValueError('No supported objective found in the explicit metric declaration')
    for name, pattern in patterns.items():
        if re.search(pattern, normalized):
            return name
    # Missing metadata retains the documented legacy fallback; an explicitly
    # unsupported objective must not silently become RMSE or Macro F1.
    if re.search(r'\bmetric\s*[:=—–-]?\s*\w|метрика\s*[:=—–-]\s*\w', normalized):
        raise ValueError('No supported objective found in the explicit metric declaration')
    return 'rmse' if kind == 'regression' else 'macro_f1'
