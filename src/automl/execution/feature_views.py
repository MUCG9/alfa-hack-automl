"""Bounded two-view learner contract, distinct from the global ensemble."""
from copy import deepcopy
from itertools import combinations
import numbers

from automl.contracts.messages import DataPolicy

METHOD = 'categorical_te_pair'


def validate_feature_view(recipe, spec=None):
    params = recipe.get('params', {})
    if 'feature_views' not in params:
        return None
    if params['feature_views'] != METHOD or recipe.get('engine') != 'lightgbm':
        raise ValueError('Unsupported feature-view learner')
    if recipe.get('feature_code') or not DataPolicy.parse(recipe.get('data_policy')).is_noop:
        raise ValueError('Feature views require unchanged features and noop data policy')
    if any(k.startswith('target_encoding') or k.startswith('history_') for k in params):
        raise ValueError('Feature views cannot combine explicit encoding/history options')
    if params.get('generic_features', 'none') not in {'none','broad'} or params.get('log_target', False):
        raise ValueError('Feature views cannot combine generic or target transformations')
    if params.get('calibrate') is not True or params.get('calibration_folds', 1) != 1:
        raise ValueError('Feature views require existing inner-holdout calibration')
    if params.get('multiclass_strategy', 'softmax') != 'softmax' or params.get('pair_refinement', False):
        raise ValueError('Feature views require the ordinary softmax learner')
    if spec is None:
        return []
    if (spec.get('kind') != 'classification' or spec.get('metric') != 'macro_f1'
            or spec.get('text_features') or spec.get('task_family') == 'pointwise_ranking'):
        raise ValueError('Feature views require nontext Macro F1 classification')
    declared = set(spec.get('categorical_features') or [])
    categories = [c for c in spec['features'] if c in declared][:3]
    if len(categories) < 2:
        raise ValueError('Feature views require two schema-declared categorical features')
    return [list(pair) for pair in combinations(categories, 2)]


def feature_view_components(recipe, spec):
    groups = validate_feature_view(recipe, spec)
    if groups is None:
        raise ValueError('Missing feature-view method')
    plain = deepcopy(recipe)
    plain['params'].pop('feature_views')
    encoded = deepcopy(plain)
    encoded['params'].update(target_encoding=True, target_encoding_groups=groups,
                             target_encoding_smoothing=20.)
    plain['hypothesis'] = 'Fixed feature view: original categorical features'
    encoded['hypothesis'] = 'Fixed feature view: fitting-cross-fitted categorical statistics'
    return [plain, encoded]


def validate_fit_iterations(recipe, value):
    """Preserve the full tree; never silently zip/drop a second view at refit."""
    if value is None:
        return
    if recipe.get('engine') == 'ensemble':
        children = recipe.get('components', [])
        if not isinstance(value, list) or len(value) != len(children):
            raise ValueError('Global ensemble iteration tree does not match components')
        for child, selected in zip(children, value):
            validate_fit_iterations(child, selected)
    elif 'feature_views' in recipe.get('params', {}):
        if not isinstance(value, list) or len(value) != 2:
            raise ValueError('Feature-view iterations require exactly two leaves')
        for leaf in value:
            _iteration_leaf(leaf)
    else:
        _iteration_leaf(value)


def _iteration_leaf(value):
    if isinstance(value, bool) or not isinstance(value, numbers.Integral) or not 1 <= value <= 3000:
        raise ValueError('Fit iteration leaf must be an integer from1to3000')
