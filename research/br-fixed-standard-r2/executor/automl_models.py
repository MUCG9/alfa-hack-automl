"""Single registry; adapters hide library-specific constructors."""
import automl_model_lightgbm as lightgbm
import automl_model_xgboost as xgboost
import automl_model_catboost as catboost
import automl_model_extra_trees as extra_trees
from automl_weights import number
from automl_evaluation_api import lgbm_metric
from automl_contracts_messages import loss_profile_catalog, resolve_loss_profile, validate_loss_profiles
COMMON_PARAMETERS = {'iterations', 'learning_rate', 'seed', 'class_weight_power', 'class_weights', 'generic_features', 'log_target', 'early_metric', 'nested_stopping', 'min_iterations', 'categorical_from_dictionary', 'calibrate', 'calibration_folds', 'target_encoding', 'target_encoding_groups', 'target_encoding_smoothing', 'target_encoding_auto_groups', 'target_encoding_refine_groups', 'target_encoding_counts', 'target_encoding_half_life', 'target_encoding_hierarchical', 'history_asof', 'history_min_periods', 'decision_optimizer', 'target_smearing', 'target_smearing_method', 'feature_selection_top_k', 'feature_selection_protect_original'}
MODEL_PARAMETERS = {'lightgbm': {'max_depth', 'depth', 'num_leaves', 'min_child_samples', 'reg_lambda', 'reg_alpha', 'subsample', 'subsample_freq', 'colsample_bytree', 'calibrate', 'multiclass_strategy', 'pair_refinement', 'feature_views', 'loss_profile_id'}, 'xgboost': {'depth', 'max_depth', 'min_child_weight', 'subsample', 'colsample_bytree', 'reg_lambda', 'reg_alpha', 'gamma', 'max_bin'}, 'catboost': {'depth', 'l2_leaf_reg', 'random_strength'}, 'extra_trees': {'max_depth', 'min_samples_leaf', 'max_features'}, 'linear_text': {'text_alpha', 'text_char_features', 'text_svd_components', 'text_classifier', 'text_C'}}
ADAPTERS = {'lightgbm': lightgbm, 'xgboost': xgboost, 'catboost': catboost, 'extra_trees': extra_trees}
CAPABILITIES = {name: {'kinds': ['regression', 'classification'], 'nested_stopping': name != 'extra_trees'} for name in ADAPTERS}
CAPABILITIES['linear_text'] = {'kinds': ['regression', 'classification'], 'nested_stopping': False, 'mode': 'text'}
for name in CAPABILITIES:
    CAPABILITIES[name]['parameters'] = sorted((COMMON_PARAMETERS | MODEL_PARAMETERS[name]) - {'loss_profile_id'})
    CAPABILITIES[name]['category_strategy'] = 'pandas' if name in {'lightgbm', 'xgboost'} else 'frequency' if name == 'extra_trees' else 'native'
    CAPABILITIES[name]['macro_f1_calibration'] = name in ADAPTERS

def make_model(recipe, kind, threads, iterations):
    validate_loss_profiles(recipe, kind)
    try:
        adapter = ADAPTERS[recipe['engine']]
    except KeyError:
        raise ValueError('Unknown recipe engine')
    return adapter.create_model(recipe, kind, threads, iterations)

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

def fit_options(engine, spec, recipe, train_x, fit_y, validation_rows, categorical, target_log):
    return ADAPTERS[engine].fit_options(spec, recipe, train_x, fit_y, validation_rows, categorical, target_log)

def selected_iterations(engine, model):
    return getattr(model, 'tree_count_', None) if engine == 'catboost' else getattr(model, 'best_iteration_', None)

def loss_profile_fit_receipt(recipe, kind, model):
    profile = resolve_loss_profile(recipe.get('engine'), recipe.get('params', {}), kind)
    if profile is None:
        return None
    return lightgbm.loss_profile_fit_receipt(recipe, kind, model)
