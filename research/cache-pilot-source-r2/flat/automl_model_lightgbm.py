import numpy as np
from automl_evaluation_api import lgbm_metric
from automl_weights import number

def fit_options(spec, recipe, x, y, validation_rows, categorical, target_log):
    if validation_rows is None:
        return {}
    from lightgbm import early_stopping, log_evaluation
    options = {'eval_set': [(x.iloc[validation_rows], y.iloc[validation_rows])], 'callbacks': [early_stopping(100, first_metric_only=True, verbose=False), log_evaluation(0)]}
    if recipe.get('params', {}).get('early_metric', 'primary') == 'primary':
        options['eval_metric'] = lgbm_metric(spec, target_log)
    return options

def create_model(recipe, kind, threads, iterations):
    params = recipe.get('params', {})
    depth = number(params, 'depth', 6, 4, 10, True)
    learning_rate = number(params, 'learning_rate', 0.06, 0.01, 0.2)
    weighted = bool(params.get('class_weights', False)) and 'class_weight_power' not in params and (kind == 'classification')
    seed = number(params, 'seed', 42, 0, 2 ** 31 - 1, True)
    from lightgbm import LGBMClassifier, LGBMRegressor
    max_depth = int(params.get('max_depth', params.get('depth', -1)))
    max_depth = -1 if max_depth <= 0 else int(np.clip(max_depth, 3, 14))
    subsample = number(params, 'subsample', 1, 0.5, 1)
    common = dict(n_estimators=iterations, learning_rate=learning_rate, num_leaves=number(params, 'num_leaves', 31, 15, 255, True), max_depth=max_depth, reg_lambda=number(params, 'reg_lambda', 3, 0, 100), reg_alpha=number(params, 'reg_alpha', 0, 0, 20), n_jobs=threads, random_state=seed, verbosity=-1, colsample_bytree=number(params, 'colsample_bytree', 0.9, 0.5, 1), subsample=subsample, subsample_freq=int(params.get('subsample_freq', 1 if subsample < 1 else 0)), min_child_samples=number(params, 'min_child_samples', 30, 5, 150, True))
    if params.get('early_metric', 'primary') == 'primary':
        common['metric'] = 'None'
    if kind == 'regression':
        return LGBMRegressor(**common)
    strategy = params.get('multiclass_strategy', 'softmax')
    if strategy not in {'softmax', 'ova'}:
        raise ValueError('Unsupported multiclass strategy')
    if strategy == 'ova' and recipe.get('n_classes', 3) > 2:
        common['objective'] = 'multiclassova'
    model = LGBMClassifier(class_weight='balanced' if weighted else None, **common)
    if params.get('pair_refinement', False):
        from automl_execution_model_adapters_specialists import PairSpecialists
        model = PairSpecialists(model)
    return model
