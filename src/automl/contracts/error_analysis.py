"""JSON process-boundary contracts for diagnostics; no artifact I/O or statistics."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, is_dataclass
import json
import math
import types
from typing import get_args, get_origin, get_type_hints

from automl.contracts.messages import DatasetRef, PredictionBundle, TaskSpec, canonical_hash

ERROR_ANALYSIS_SCHEMA_VERSION = '2.0'
PROFILE_SECTIONS = ('alignment', 'models', 'comparisons', 'slices', 'uncertainty')


def _text(value, label):
    if not isinstance(value, str) or not value.strip() or '\x00' in value:
        raise ValueError(f'{label}: expected nonempty text without NUL')


def _sha(value, label):
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError(f'{label}: expected lowercase SHA256')


def _strings(value, label, allow_empty=False):
    if not isinstance(value, tuple) or (not value and not allow_empty):
        raise ValueError(f'{label}: expected a tuple')
    for item in value:
        _text(item, label)
    if len(set(value)) != len(value):
        raise ValueError(f'{label}: duplicate entries')


def _dataset(value, label):
    if not isinstance(value, DatasetRef) or value.schema_version != '1.0':
        raise ValueError(f'{label}: expected DatasetRef v1.0')
    _text(value.path, label + '.path')
    _sha(value.sha256, label + '.sha256')
    if type(value.rows) is not int or value.rows < 1:
        raise ValueError(f'{label}: expected positive original row count')


def _finite_number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _decode(hint, value, label):
    """Decode only declared dataclass fields and JSON primitives, never imports."""
    origin = get_origin(hint)
    if origin is types.UnionType:
        for choice in get_args(hint):
            try:
                return _decode(choice, value, label)
            except ValueError:
                pass
        raise ValueError(f'{label}: incompatible optional value')
    if hint is type(None):
        if value is not None:
            raise ValueError(f'{label}: expected null')
        return None
    if origin is tuple:
        if not isinstance(value, (list, tuple)):
            raise ValueError(f'{label}: expected an array')
        item_type, repeat = get_args(hint)
        if repeat is not Ellipsis:
            raise ValueError(f'{label}: unsupported tuple contract')
        return tuple(_decode(item_type, item, f'{label}[{i}]') for i, item in enumerate(value))
    if is_dataclass(hint):
        if not isinstance(value, dict):
            raise ValueError(f'{label}: expected an object')
        declared = {f.name for f in fields(hint)}
        if set(value) - declared:
            raise ValueError(f'{label}: unknown fields')
        hints = get_type_hints(hint)
        decoded = {key: _decode(hints[key], item, f'{label}.{key}') for key, item in value.items()}
        try:
            return hint(**decoded)
        except TypeError as exc:
            raise ValueError(f'{label}: missing or invalid fields') from exc
    if hint is float:
        if not _finite_number(value):
            raise ValueError(f'{label}: expected a finite number')
        return float(value)
    if hint in (str, int, bool) and type(value) is hint:
        return value
    raise ValueError(f'{label}: invalid primitive type')


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON field: ' + key)
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError('Nonfinite JSON constant: ' + value)


class _Message:
    def to_dict(self):
        return json.loads(json.dumps(asdict(self), allow_nan=False))

    def to_json(self):
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False, allow_nan=False)

    @classmethod
    def from_dict(cls, value):
        return _decode(cls, value, cls.__name__)

    @classmethod
    def from_json(cls, value):
        return cls.from_dict(json.loads(value, object_pairs_hook=_object, parse_constant=_invalid_constant))

    def _version(self):
        if self.schema_version != ERROR_ANALYSIS_SCHEMA_VERSION:
            raise ValueError('Unsupported error-analysis schema version')


@dataclass(frozen=True)
class AnalysisArtifactRef(_Message):
    path: str
    sha256: str
    schema_version: str = ERROR_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self):
        self._version()
        _text(self.path, 'artifact.path')
        _sha(self.sha256, 'artifact.sha256')


@dataclass(frozen=True)
class AnalysisBudget(_Message):
    max_seconds: float = 60.0
    max_memory_mb: int = 512
    threads: int = 1
    schema_version: str = ERROR_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self):
        self._version()
        if not _finite_number(self.max_seconds) or not 0 < self.max_seconds <= 10800:
            raise ValueError('Analysis time budget must be finite and within task limit')
        object.__setattr__(self, 'max_seconds', float(self.max_seconds))
        if type(self.max_memory_mb) is not int or not 1 <= self.max_memory_mb <= 32768:
            raise ValueError('Invalid analysis memory budget')
        if type(self.threads) is not int or not 1 <= self.threads <= 8:
            raise ValueError('Invalid analysis thread budget')


@dataclass(frozen=True)
class ModelPredictionRef(_Message):
    model_id: str
    fold_id: str
    recipe_sha256: str
    source_sha256: str
    predictions: PredictionBundle
    predictions_sha256: str
    row_positions_sha256: str
    split: AnalysisArtifactRef
    probabilities: AnalysisArtifactRef | None = None
    probability_kind: str = 'none'
    recorded_result: AnalysisArtifactRef | None = None
    schema_version: str = ERROR_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self):
        self._version()
        _text(self.model_id, 'model_id')
        _text(self.fold_id, 'fold_id')
        for name in ('recipe_sha256', 'source_sha256', 'predictions_sha256', 'row_positions_sha256'):
            _sha(getattr(self, name), name)
        if not isinstance(self.predictions, PredictionBundle) or self.predictions.schema_version != '1.0':
            raise ValueError('Expected PredictionBundle v1.0')
        bundle = self.predictions
        _text(bundle.path, 'predictions.path')
        _sha(bundle.split_sha256, 'predictions.split_sha256')
        if type(bundle.rows) is not int or bundle.rows < 1:
            raise ValueError('Predictions require a positive row count')
        _strings(bundle.columns, 'prediction columns')
        _strings(bundle.classes, 'prediction classes', allow_empty=True)
        if not isinstance(self.split, AnalysisArtifactRef):
            raise ValueError('Expected split artifact reference')
        if self.probability_kind not in ('none', 'raw', 'decision_adjusted'):
            raise ValueError('Unknown probability kind')
        if self.probabilities is None:
            if self.probability_kind != 'none':
                raise ValueError('Probability kind requires an artifact')
        elif not isinstance(self.probabilities, AnalysisArtifactRef) or self.probability_kind == 'none' or not bundle.classes:
            raise ValueError('Probability artifact requires kind and class order')
        if self.recorded_result is not None and not isinstance(self.recorded_result, AnalysisArtifactRef):
            raise ValueError('Expected recorded-result artifact reference')


@dataclass(frozen=True)
class DiagnosticBlend(_Message):
    name: str
    models: tuple[str, ...]
    weights: tuple[float, ...]
    schema_version: str = ERROR_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self):
        self._version()
        _text(self.name, 'blend name')
        _strings(self.models, 'blend models')
        if len(self.models) < 2 or not isinstance(self.weights, tuple) or len(self.weights) != len(self.models):
            raise ValueError('Blend requires at least two models and matching weights')
        if any(not _finite_number(w) or w <= 0 for w in self.weights):
            raise ValueError('Diagnostic blend weights must be finite and positive')
        total = sum(self.weights)
        if not math.isfinite(total):
            raise ValueError('Invalid total blend weight')
        object.__setattr__(self, 'weights', tuple(float(w / total) for w in self.weights))


@dataclass(frozen=True)
class ErrorAnalysisProtocol(_Message):
    protocol_id: str
    numeric_features: tuple[str, ...] = ()
    categorical_features: tuple[str, ...] = ()
    context_groups: tuple[tuple[str, ...], ...] = ()
    period_column: str | None = None
    require_group_disjoint: bool = True
    quantile_bins: int = 4
    max_categories: int = 8
    min_slice_groups: int = 20
    rare_max_groups: int = 20
    high_confidence: float = .9
    bootstrap_replicates: int = 200
    bootstrap_seed: int = 2026
    min_bootstrap_groups: int = 20
    max_pairs: int = 66
    blends: tuple[DiagnosticBlend, ...] = ()
    evidence: tuple[AnalysisArtifactRef, ...] = ()
    schema_version: str = ERROR_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self):
        self._version()
        _text(self.protocol_id, 'protocol_id')
        for name in ('numeric_features', 'categorical_features'):
            _strings(getattr(self, name), name, allow_empty=True)
        if not isinstance(self.context_groups, tuple):
            raise ValueError('Expected context groups tuple')
        for group in self.context_groups:
            _strings(group, 'context group')
        if len(set(self.context_groups)) != len(self.context_groups):
            raise ValueError('Duplicate context groups')
        if self.period_column is not None:
            _text(self.period_column, 'period_column')
        if type(self.require_group_disjoint) is not bool:
            raise ValueError('Group-disjoint flag must be boolean')
        for name, low, high in (('quantile_bins', 2, 10), ('max_categories', 1, 50),
                                ('min_slice_groups', 2, 1000000), ('rare_max_groups', 1, 1000000),
                                ('bootstrap_replicates', 0, 5000), ('bootstrap_seed', 0, 2**31-1),
                                ('min_bootstrap_groups', 2, 1000000), ('max_pairs', 1, 1000)):
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError('Invalid protocol parameter: ' + name)
        if self.bootstrap_replicates != 0 and self.bootstrap_replicates < 100:
            raise ValueError('Use zero or at least 100 bootstrap replicates')
        if not _finite_number(self.high_confidence) or not .5 <= self.high_confidence <= 1:
            raise ValueError('Invalid confidence threshold')
        if not isinstance(self.blends, tuple) or any(not isinstance(b, DiagnosticBlend) for b in self.blends):
            raise ValueError('Invalid declared diagnostic blends')
        if len({b.name for b in self.blends}) != len(self.blends):
            raise ValueError('Duplicate blend names')
        if not isinstance(self.evidence, tuple) or any(not isinstance(r, AnalysisArtifactRef) for r in self.evidence):
            raise ValueError('Invalid protocol evidence')


@dataclass(frozen=True)
class ErrorAnalysisRequest(_Message):
    request_id: str
    task: TaskSpec
    dataset: DatasetRef
    control_model_id: str
    protocol_id: str
    protocol: AnalysisArtifactRef
    prediction_scope: str
    predictions: tuple[ModelPredictionRef, ...]
    output_dir: str
    budget: AnalysisBudget
    groups: DatasetRef | None = None
    observation_time: DatasetRef | None = None
    schema_version: str = ERROR_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self):
        self._version()
        for name in ('request_id', 'control_model_id', 'protocol_id', 'output_dir'):
            _text(getattr(self, name), name)
        task = self.task
        if not isinstance(task, TaskSpec) or task.schema_version != '1.0' or task.kind not in ('regression', 'classification'):
            raise ValueError('Expected supported TaskSpec v1.0')
        _strings(task.features, 'task features')
        _text(task.target, 'target')
        _text(task.metric, 'metric')
        if task.identifier is not None:
            _text(task.identifier, 'identifier')
        if type(task.greater_is_better) is not bool or task.target in task.features or task.identifier in task.features or task.target == task.identifier:
            raise ValueError('Invalid task roles or metric direction')
        _dataset(self.dataset, 'dataset')
        if not isinstance(self.protocol, AnalysisArtifactRef) or not isinstance(self.budget, AnalysisBudget):
            raise ValueError('Expected protocol artifact and analysis budget')
        if self.prediction_scope not in ('inner', 'search', 'confirmation', 'oof', 'forward'):
            raise ValueError('Unsupported prediction scope; test/full-fit predictions are not diagnostics')
        if not isinstance(self.predictions, tuple) or not self.predictions or any(not isinstance(p, ModelPredictionRef) for p in self.predictions):
            raise ValueError('Expected nonempty tuple of model predictions')
        keys = [(p.model_id, p.fold_id) for p in self.predictions]
        if len(set(keys)) != len(keys) or self.control_model_id not in {p.model_id for p in self.predictions}:
            raise ValueError('Duplicate model/fold or missing control')
        recipes = {}
        for prediction in self.predictions:
            provenance = (prediction.recipe_sha256, prediction.source_sha256)
            if recipes.setdefault(prediction.model_id, provenance) != provenance:
                raise ValueError('Model identity changes across folds')
            if prediction.predictions.rows > self.dataset.rows:
                raise ValueError('Prediction row count exceeds original dataset')
            if bool(prediction.predictions.classes) != (task.kind == 'classification'):
                raise ValueError('Prediction classes do not match task kind')
        for name in ('groups', 'observation_time'):
            value = getattr(self, name)
            if value is not None:
                _dataset(value, name)
                if value.rows != self.dataset.rows:
                    raise ValueError('Group/time metadata must describe original dataset rows')

    @property
    def sha256(self):
        return canonical_hash(self.to_dict())


@dataclass(frozen=True)
class ErrorProfileSection(_Message):
    name: str
    status: str
    result: AnalysisArtifactRef | None = None
    reason: str | None = None
    schema_version: str = ERROR_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self):
        self._version()
        if self.name not in PROFILE_SECTIONS or self.status not in ('complete', 'unavailable', 'failed'):
            raise ValueError('Unknown profile section or status')
        if self.status == 'complete':
            if not isinstance(self.result, AnalysisArtifactRef) or self.reason is not None:
                raise ValueError('Completed section requires an aggregate artifact and no failure reason')
        else:
            _text(self.reason, 'section reason')
            if self.result is not None:
                raise ValueError('Incomplete section cannot carry a successful result')


@dataclass(frozen=True)
class ErrorFinding(_Message):
    code: str
    summary: str
    evidence_sections: tuple[str, ...]
    schema_version: str = ERROR_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self):
        self._version()
        _text(self.code, 'finding code')
        _text(self.summary, 'finding summary')
        _strings(self.evidence_sections, 'finding evidence')
        if not set(self.evidence_sections) <= set(PROFILE_SECTIONS):
            raise ValueError('Unknown finding evidence section')


@dataclass(frozen=True)
class ErrorProfile(_Message):
    request: ErrorAnalysisRequest
    request_sha256: str
    analysis_source_sha256: str
    status: str
    sections: tuple[ErrorProfileSection, ...]
    limitations: tuple[str, ...]
    findings: tuple[ErrorFinding, ...] = ()
    diagnostic_only: bool = True
    schema_version: str = ERROR_ANALYSIS_SCHEMA_VERSION

    def __post_init__(self):
        self._version()
        if not isinstance(self.request, ErrorAnalysisRequest) or self.request_sha256 != self.request.sha256:
            raise ValueError('Profile request provenance mismatch')
        _sha(self.analysis_source_sha256, 'analysis_source_sha256')
        if self.diagnostic_only is not True:
            raise ValueError('An error profile is diagnostic evidence only')
        _strings(self.limitations, 'limitations')
        if not isinstance(self.sections, tuple) or any(not isinstance(s, ErrorProfileSection) for s in self.sections):
            raise ValueError('Expected profile sections')
        by_name = {s.name: s for s in self.sections}
        if len(by_name) != len(self.sections) or set(by_name) != set(PROFILE_SECTIONS):
            raise ValueError('All five profile sections must have explicit unique states')
        alignment = by_name['alignment'].status
        if alignment != 'complete' and any(s.status == 'complete' for s in self.sections):
            raise ValueError('Completed diagnostics require completed alignment')
        if alignment == 'unavailable' and any(s.status != 'unavailable' for s in self.sections):
            raise ValueError('Unavailable alignment requires unavailable diagnostics')
        expected = 'failed' if alignment != 'complete' else 'complete' if all(s.status == 'complete' for s in self.sections) else 'partial'
        if self.status != expected:
            raise ValueError('Profile status contradicts its sections')
        if not isinstance(self.findings, tuple) or any(not isinstance(f, ErrorFinding) for f in self.findings):
            raise ValueError('Expected diagnostic findings')
        if len({f.code for f in self.findings}) != len(self.findings):
            raise ValueError('Duplicate finding codes')
        for finding in self.findings:
            if any(by_name[name].status != 'complete' for name in finding.evidence_sections):
                raise ValueError('Finding cites incomplete evidence')
