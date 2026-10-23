"""Explicit objective evidence for UAR-v1; no inferred objective defaults."""
from dataclasses import asdict, dataclass
from typing import Optional, Tuple


DEFINITIONS = {
    'rmse': ('minimize', 'value'),
    'mae': ('minimize', 'value'),
    'mse': ('minimize', 'value'),
    'mape': ('minimize', 'value'),
    'rmsle': ('minimize', 'value'),
    'r2': ('maximize', 'value'),
    'ndcg': ('maximize', 'value'),
    'macro_f1': ('maximize', 'label'),
    'weighted_f1': ('maximize', 'label'),
    'accuracy': ('maximize', 'label'),
    'balanced_accuracy': ('maximize', 'label'),
    'roc_auc': ('maximize', 'probability'),
    'log_loss': ('minimize', 'probability'),
}


class UnresolvedMetricError(ValueError):
    """Measured search requires a supported, unambiguous objective."""


@dataclass(frozen=True)
class MetricSpec:
    name: Optional[str]
    direction: Optional[str]
    prediction_kind: Optional[str]
    status: str
    source: str
    evidence: Tuple[str, ...] = ()
    reason: str = ''

    def __post_init__(self):
        if self.status not in {'resolved', 'unknown', 'unsupported', 'ambiguous'}:
            raise ValueError('Invalid metric resolution status')
        if not isinstance(self.source, str) or not self.source:
            raise ValueError('Metric evidence source is required')
        if not isinstance(self.evidence, tuple) or any(
            not isinstance(item, str) or len(item.encode('utf-8')) > 1024
            for item in self.evidence
        ):
            raise ValueError('Metric evidence must be bounded text')
        if len(self.evidence) > 8:
            raise ValueError('Too many metric evidence entries')
        if self.status == 'resolved':
            if self.name not in DEFINITIONS:
                raise ValueError('Unsupported resolved objective')
            expected_direction, expected_prediction = DEFINITIONS[self.name]
            if self.direction != expected_direction:
                raise ValueError('Objective direction mismatch')
            allowed = {expected_prediction}
            if expected_prediction == 'probability':
                allowed.add('probability_matrix')
            if self.prediction_kind not in allowed:
                raise ValueError('Objective prediction kind mismatch')
        elif any(value is not None for value in
                 (self.name, self.direction, self.prediction_kind)):
            raise ValueError('Unresolved objective cannot carry an assumed metric')

    def require_resolved(self):
        if self.status != 'resolved':
            raise UnresolvedMetricError(self.reason or self.status)
        return self

    def to_dict(self):
        return asdict(self)
