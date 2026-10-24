"""Versioned process-boundary messages. No model, data-frame or API imports."""
from dataclasses import dataclass, field, asdict
import hashlib, json, math
SCHEMA_VERSION = '1.0'

@dataclass(frozen=True)
class LossProfile:
    """Fixed backend profile metadata; never a changed evaluation metric."""
    loss_profile_id: str
    engine: str
    kind: str
    objective: str
    alpha: float | None = None

    def parameters(self):
        result = {'objective': self.objective}
        if self.alpha is not None:
            result['alpha'] = self.alpha
        return result

    def to_dict(self):
        return asdict(self)
LOSS_PROFILES = (LossProfile('lgbm_l2_v1', 'lightgbm', 'regression', 'regression'), LossProfile('lgbm_l1_v1', 'lightgbm', 'regression', 'regression_l1'), LossProfile('lgbm_huber_a09_v1', 'lightgbm', 'regression', 'huber', 0.9))

def loss_profile_catalog(engine=None, kind=None):
    """Separate opt-in backend catalog; legacy planner capabilities stay unchanged."""
    return tuple((profile.to_dict() for profile in LOSS_PROFILES if (engine is None or profile.engine == engine) and (kind is None or profile.kind == kind)))

def resolve_loss_profile(engine, params, kind=None):
    if 'loss_profile_id' not in params:
        return None
    value = params['loss_profile_id']
    if not isinstance(value, str):
        raise ValueError('loss_profile_id must be a supported string ID')
    profile = next((profile for profile in LOSS_PROFILES if profile.loss_profile_id == value), None)
    if profile is None:
        raise ValueError('Unsupported loss_profile_id')
    if engine != profile.engine or (kind is not None and kind != profile.kind):
        raise ValueError('Loss profile is incompatible with the learner or task kind')
    if any((key in params for key in ('objective', 'objective_type', 'application', 'app', 'loss', 'alpha'))):
        raise ValueError('Fixed loss profile cannot combine raw objective/loss/alpha aliases')
    if params.get('early_metric', 'primary') != 'primary':
        raise ValueError('Loss profile requires unchanged primary-metric early stopping')
    return profile

def validate_loss_profiles(recipe, kind=None):
    """Validate before filtering and before any child model fit; no model imports."""
    if 'loss_profile_id' in recipe:
        raise ValueError('loss_profile_id belongs in recipe.params')
    resolve_loss_profile(recipe.get('engine'), recipe.get('params', {}), kind)
    if recipe.get('engine') == 'ensemble':
        for child in recipe.get('components', []):
            validate_loss_profiles(child, kind)

@dataclass(frozen=True)
class DataPolicy:
    schema_version: str = SCHEMA_VERSION
    sampling: str = 'identity'
    factor: float = 1.5
    majority_fraction: float = 0.85
    duplicate_beta: float = 0.0
    class_weight_cap: float | None = None
    augmentation: str = 'noop'
    copy_fraction: float = 0.15
    mask_probability: float = 0.1
    synthetic_weight: float = 0.5
    max_added_fraction: float = 0.25
    seed: int = 2026

    def __post_init__(self):
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError('Unsupported data-policy version')
        if self.sampling not in {'identity', 'compress', 'over', 'under'}:
            raise ValueError('Unsupported sampling policy')
        if self.augmentation not in {'noop', 'mask'}:
            raise ValueError('Unsupported augmentation')
        for name, low, high in [('factor', 1, 2), ('majority_fraction', 0.5, 1), ('duplicate_beta', 0, 1), ('copy_fraction', 0, 0.25), ('mask_probability', 0, 0.3), ('synthetic_weight', 0.1, 1), ('max_added_fraction', 0, 0.25)]:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or (not math.isfinite(value)) or (not low <= value <= high):
                raise ValueError('Invalid policy parameter: ' + name)
        if self.class_weight_cap is not None and (not math.isfinite(self.class_weight_cap) or not 1 <= self.class_weight_cap <= 50):
            raise ValueError('Invalid class weight cap')
        if not isinstance(self.seed, int) or not 0 <= self.seed < 2 ** 31:
            raise ValueError('Invalid seed')

    @classmethod
    def parse(cls, value=None):
        if value is None:
            return cls()
        if not isinstance(value, dict):
            raise ValueError('Data policy must be an object')
        unknown = set(value) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError('Unknown data-policy fields: ' + ','.join(sorted(unknown)))
        return cls(**value)

    def to_dict(self):
        return asdict(self)

    @property
    def is_noop(self):
        return self.sampling == 'identity' and self.augmentation == 'noop' and (self.duplicate_beta == 0) and (self.class_weight_cap is None)

@dataclass(frozen=True)
class DatasetRef:
    path: str
    sha256: str
    rows: int
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        if self.schema_version != SCHEMA_VERSION or self.rows < 0 or len(self.sha256) != 64 or any((c not in '0123456789abcdef' for c in self.sha256)):
            raise ValueError('Invalid DatasetRef')

@dataclass(frozen=True)
class TaskSpec:
    kind: str
    target: str
    identifier: str | None
    features: tuple[str, ...]
    metric: str
    greater_is_better: bool
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def from_legacy(cls, spec):
        result = cls(spec['kind'], spec['target'], spec['id'], tuple(spec['features']), spec['metric'], spec['greater_is_better'])
        if result.kind not in {'regression', 'classification'} or not result.features:
            raise ValueError('Unsupported task contract')
        if result.target in result.features or result.identifier in result.features:
            raise ValueError('Target/ID cannot be model features')
        return result

@dataclass(frozen=True)
class SplitPlan:
    train: tuple[int, ...]
    validation: tuple[int, ...]
    schema_version: str = SCHEMA_VERSION

    def validate(self, n):
        a, b = (set(self.train), set(self.validation))
        if self.schema_version != SCHEMA_VERSION or not a or (not b) or a & b:
            raise ValueError('Invalid split partition')
        if len(a) != len(self.train) or len(b) != len(self.validation) or min(a | b) < 0 or (max(a | b) >= n):
            raise ValueError('Invalid split row IDs')

@dataclass(frozen=True)
class ExperimentRequest:
    experiment_id: str
    output_dir: str
    split_path: str
    recipe: dict
    threads: int
    schema_version: str = SCHEMA_VERSION

    def validate(self):
        if self.schema_version != SCHEMA_VERSION or not 1 <= self.threads <= 8 or (not self.experiment_id):
            raise ValueError('Invalid experiment request')
        if self.recipe.get('engine') != 'ensemble':
            DataPolicy.parse(self.recipe.get('data_policy'))
        validate_loss_profiles(self.recipe)

@dataclass(frozen=True)
class EvaluationResult:
    metric: str
    value: float
    split_sha256: str
    greater_is_better: bool
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        if self.schema_version != SCHEMA_VERSION or not math.isfinite(self.value):
            raise ValueError('Invalid evaluation result')

@dataclass(frozen=True)
class SelectionPlan:
    recipe_hashes: tuple[str, ...]
    weights: tuple[float, ...]
    schema_version: str = SCHEMA_VERSION

    def validate(self):
        if self.schema_version != SCHEMA_VERSION or len(self.recipe_hashes) != len(self.weights) or (not self.weights):
            raise ValueError('Invalid selection plan')
        if not all((math.isfinite(v) and v > 0 for v in self.weights)):
            raise ValueError('Invalid selection weights')

@dataclass(frozen=True)
class PredictionBundle:
    path: str
    rows: int
    columns: tuple[str, ...]
    classes: tuple[str, ...] = ()
    split_sha256: str = ''
    schema_version: str = SCHEMA_VERSION

    def validate(self, rows, columns, split_sha256=''):
        if self.schema_version != SCHEMA_VERSION or self.rows != rows or self.columns != tuple(columns):
            raise ValueError('Prediction shape/order mismatch')
        if split_sha256 and self.split_sha256 != split_sha256:
            raise ValueError('Prediction split mismatch')
        if len(set(self.classes)) != len(self.classes):
            raise ValueError('Duplicate prediction classes')

def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
