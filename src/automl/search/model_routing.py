"""Opt-in, metadata-only routing across existing adapters (not job admission).

No data, model, filesystem, optional-library or planner imports. Callers supply
trusted fitting-scope counts and independently verified capability facts. The
module is deliberately not imported by the current runner/default portfolio.
Memory figures are conservative buffer heuristics, not peak-RSS/fit-time proofs;
the existing worker watchdog and absolute export reserve remain authoritative.
"""
from dataclasses import asdict, dataclass


FAMILIES = ('lightgbm', 'catboost', 'xgboost', 'extra_trees', 'linear_text')
BOOSTING = FAMILIES[:3]
_MAX_COUNT = 2**31 - 1


def _integer(name, value, low=0, high=_MAX_COUNT):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Invalid ' + name)


@dataclass(frozen=True)
class TaskFingerprint:
    """Counts only: target/ID/column/file names and raw values are not inputs.

    categorical_levels is the total fitting-only category count across columns.
    text_nnz_upper_bound, if known, bounds total text nonzeros across these rows.
    sparse_preferred describes a representation preference, not a CSR input API:
    existing adapters still receive their ordinary DataFrame/worker contracts.
    """
    kind: str
    n_rows: int
    n_numeric: int
    n_categorical: int = 0
    n_text: int = 0
    n_classes: int | None = None
    categorical_levels: int | None = None
    text_nnz_upper_bound: int | None = None
    sparse_preferred: bool = False

    def __post_init__(self):
        if type(self.kind) is not str or self.kind not in ('regression', 'classification'):
            raise ValueError('Unsupported task kind')
        _integer('n_rows', self.n_rows, 1)
        for name in ('n_numeric', 'n_categorical', 'n_text'):
            _integer(name, getattr(self, name))
        if not self.n_features:
            raise ValueError('At least one feature is required')
        if type(self.sparse_preferred) is not bool:
            raise ValueError('sparse_preferred must be a boolean')
        if self.kind == 'classification':
            _integer('n_classes', self.n_classes, 2, 10000)
        elif self.n_classes is not None:
            raise ValueError('Regression does not have class counts')
        if self.categorical_levels is not None:
            _integer('categorical_levels', self.categorical_levels,
                     self.n_categorical, self.n_rows * self.n_categorical)
        if self.text_nnz_upper_bound is not None:
            _integer('text_nnz_upper_bound', self.text_nnz_upper_bound, 0,
                     self.n_rows * self.n_text * 30000)

    @property
    def n_features(self):
        return self.n_numeric + self.n_categorical + self.n_text


@dataclass(frozen=True)
class FamilyCapability:
    """Four distinct caller-attested facts; none means measured quality."""
    engine: str
    allowed: bool | None
    installed: bool | None
    adapter_implemented: bool | None
    source_verified: bool | None
    kinds: tuple[str, ...] = ('regression', 'classification')

    def __post_init__(self):
        if self.engine not in FAMILIES:
            raise ValueError('No existing adapter for this family')
        for name in ('allowed', 'installed', 'adapter_implemented', 'source_verified'):
            if getattr(self, name) is not None and type(getattr(self, name)) is not bool:
                raise ValueError(name + ' must be a boolean or unknown')
        if (type(self.kinds) is not tuple or not self.kinds or len(self.kinds) > 2
                or any(type(k) is not str or k not in ('regression', 'classification') for k in self.kinds)
                or len(set(self.kinds)) != len(self.kinds)):
            raise ValueError('Invalid supported task kinds')


@dataclass(frozen=True)
class RoutingBudget:
    max_families: int = 3
    matrix_bytes: int = 128 * 1024 * 1024
    research_seconds: int = 600
    minimum_probe_seconds: int = 30
    max_extra_trees_rows: int = 100000
    max_extra_trees_cells: int = 10000000

    def __post_init__(self):
        _integer('max_families', self.max_families, 2, 3)
        for name in ('matrix_bytes', 'minimum_probe_seconds',
                     'max_extra_trees_rows', 'max_extra_trees_cells'):
            _integer(name, getattr(self, name), 1, 2**63 - 1)
        _integer('research_seconds', self.research_seconds, 0, 10800)


@dataclass(frozen=True)
class RoutingDecision:
    families: tuple[str, ...]
    boosting_anchor: str | None
    status: str
    exclusions: tuple[dict, ...]
    estimates: tuple[dict, ...]
    rationale: tuple[str, ...]
    schema_version: str = 'uar-model-routing-v1'
    integration_default_enabled: bool = False
    worker_admission_required: bool = True

    def to_dict(self):
        return asdict(self)


def _buffer_estimate(fingerprint, engine):
    f = fingerprint
    if engine != 'linear_text':
        if f.n_text:
            return None, 'text_requires_existing_sparse_path'
        return f.n_rows * f.n_features * 8 * 3, 'three_dense_float64_buffers'
    if f.n_categorical and f.categorical_levels is None:
        return None, 'categorical_width_unknown'
    width = f.n_numeric + (f.categorical_levels or 0) + f.n_text * 30000
    text_nnz = f.text_nnz_upper_bound
    if text_nnz is None:
        text_nnz = f.n_rows * f.n_text * 30000
    nnz = f.n_rows * (f.n_numeric + f.n_categorical) + text_nnz
    # Existing default word TF-IDF/no-SVD/no-char path: CSR plus coefficient
    # storage. This is only a representation heuristic, not sklearn RSS bound.
    channels = f.n_classes if f.kind == 'classification' else 1
    return nnz * 16 + (f.n_rows + 1) * 8 + width * channels * 8, 'csr_and_head_buffers'


def route_families(fingerprint, capabilities, budget):
    """Choose up to 2–3 feasible existing families; return fewer if unavailable.

    Priority rules are explicit heuristics, never measured gain probabilities.
    A feasible strong boosting anchor is retained before exploration. This
    returns family names only: it cannot alter recipes, metric, split, HPO,
    protected anchors or the caller's resource/confirmation/refit admission.
    """
    if type(fingerprint) is not TaskFingerprint or type(budget) is not RoutingBudget:
        raise ValueError('Typed fingerprint and budget required')
    if type(capabilities) not in (tuple, list) or len(capabilities) > len(FAMILIES):
        raise ValueError('Bounded existing capability sequence required')
    observed = {}
    for cap in capabilities:
        if type(cap) is not FamilyCapability or cap.engine in observed:
            raise ValueError('Typed unique capability records required')
        observed[cap.engine] = cap
    excluded, estimates, eligible = [], [], []
    for engine in FAMILIES:
        cap = observed.get(engine)
        reasons = []
        if cap is None:
            reasons.append('capability_missing')
        else:
            reasons.extend(name + ('_unknown' if getattr(cap, name) is None else '_false') for name in
                           ('allowed', 'installed', 'adapter_implemented', 'source_verified')
                           if getattr(cap, name) is not True)
            if fingerprint.kind not in cap.kinds:
                reasons.append('kind_unsupported')
        size, basis = _buffer_estimate(fingerprint, engine)
        estimates.append({'engine': engine, 'representation_bytes_heuristic': size,
                          'basis': basis, 'measured_fit_seconds': None,
                          'peak_RSS_bytes': None})
        if size is None:
            reasons.append(basis)
        elif size > budget.matrix_bytes:
            reasons.append('representation_heuristic_exceeds_matrix_budget')
        if engine == 'extra_trees' and (
                fingerprint.n_rows > budget.max_extra_trees_rows or
                fingerprint.n_rows * fingerprint.n_features > budget.max_extra_trees_cells):
            reasons.append('forest_probe_size_guard')
        if reasons:
            excluded.append({'engine': engine, 'reasons': tuple(reasons)})
        else:
            eligible.append(engine)
    cap = min(budget.max_families,
              budget.research_seconds // budget.minimum_probe_seconds)
    anchor = next((e for e in BOOSTING if e in eligible), None)
    priorities, rationale = [], []
    if anchor:
        priorities.append(anchor)
        rationale.append('retain_available_strong_boosting_anchor')
    if fingerprint.n_text or fingerprint.sparse_preferred or (
            fingerprint.n_numeric >= max(32, fingerprint.n_rows // 2)):
        priorities.append('linear_text')
        rationale.append('sparse_or_wide_representation_heuristic')
    if fingerprint.n_categorical:
        priorities.append('catboost')
        rationale.append('native_categories_avoid_onehot_width')
    if not fingerprint.n_categorical and not fingerprint.n_text and fingerprint.n_rows <= 5000:
        priorities.append('extra_trees')
        rationale.append('small_numeric_randomized_tree_challenger')
    priorities.extend(('xgboost', 'catboost', 'lightgbm', 'linear_text', 'extra_trees'))
    selected = []
    for engine in priorities:
        if engine in eligible and engine not in selected and len(selected) < cap:
            selected.append(engine)
    if cap == 0:
        rationale.append('insufficient_search_budget_preserve_existing_submission')
    elif len(selected) < 2:
        rationale.append('fewer_than_two_feasible_families_no_fabricated_fallback')
    status = 'routed' if len(selected) >= 2 else 'partial' if selected else 'no_feasible_family'
    return RoutingDecision(tuple(selected), anchor if anchor in selected else None, status,
                           tuple(excluded), tuple(estimates), tuple(rationale))
