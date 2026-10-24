"""Exact stdlib-only metadata signature closure; no model imports. Generated SOURCE."""
from dataclasses import dataclass,asdict
import math,hashlib,json
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

COMMON_PARAMETERS = {'iterations', 'learning_rate', 'seed', 'class_weight_power', 'class_weights', 'generic_features', 'log_target', 'early_metric', 'nested_stopping', 'min_iterations', 'categorical_from_dictionary', 'calibrate', 'calibration_folds', 'target_encoding', 'target_encoding_groups', 'target_encoding_smoothing', 'target_encoding_auto_groups', 'target_encoding_refine_groups', 'target_encoding_counts', 'target_encoding_half_life', 'target_encoding_hierarchical', 'history_asof', 'history_min_periods', 'decision_optimizer', 'target_smearing', 'target_smearing_method', 'feature_selection_top_k', 'feature_selection_protect_original'}

MODEL_PARAMETERS = {'lightgbm': {'max_depth', 'depth', 'num_leaves', 'min_child_samples', 'reg_lambda', 'reg_alpha', 'subsample', 'subsample_freq', 'colsample_bytree', 'calibrate', 'multiclass_strategy', 'pair_refinement', 'feature_views', 'loss_profile_id'}, 'xgboost': {'depth', 'max_depth', 'min_child_weight', 'subsample', 'colsample_bytree', 'reg_lambda', 'reg_alpha', 'gamma', 'max_bin'}, 'catboost': {'depth', 'l2_leaf_reg', 'random_strength'}, 'extra_trees': {'max_depth', 'min_samples_leaf', 'max_features'}, 'linear_text': {'text_alpha', 'text_char_features', 'text_svd_components', 'text_classifier', 'text_C'}}

def effective_parameters(engine, params):
    resolve_loss_profile(engine, params)
    result = {k: v for k, v in params.items() if k in COMMON_PARAMETERS | MODEL_PARAMETERS[engine]}
    if result.get('target_smearing') is True and result.get('target_smearing_method') == 'duan':
        result.pop('target_smearing_method')
    if engine in {'lightgbm', 'xgboost'}:
        if 'depth' in result and 'max_depth' not in result:
            result['max_depth'] = result['depth']
        result.pop('depth', None)
    if engine == 'lightgbm' and 'subsample' in result and ('subsample_freq' not in result):
        result['subsample_freq'] = int(float(result['subsample']) < 1)
    return result

def signature(recipe):
    validate_loss_profiles(recipe)
    actual = {k: recipe.get(k) for k in ['engine', 'params', 'feature_code', 'components', 'weights', 'data_policy'] if k in recipe}
    if recipe.get('engine') in CAPABILITIES:
        actual['params'] = effective_parameters(recipe['engine'], recipe.get('params', {}))
    policy = DataPolicy.parse(recipe.get('data_policy'))
    if policy.is_noop:
        actual.pop('data_policy', None)
    else:
        actual['data_policy'] = policy.to_dict()
    return hashlib.sha256(json.dumps(actual, sort_keys=True, default=str).encode()).hexdigest()

CAPABILITIES={'catboost': None, 'extra_trees': None, 'lightgbm': None, 'linear_text': None, 'xgboost': None}
