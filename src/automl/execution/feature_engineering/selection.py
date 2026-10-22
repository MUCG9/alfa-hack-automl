"""Optional CatBoost feature importance selection, refitted for each fitting scope."""
import numpy as np

from automl.execution.model_adapters.catboost import create_model
from automl.execution.preprocessing.frames import prepare_frames


def validate_selection(params):
    top_k = params.get('feature_selection_top_k', 0)
    if type(top_k) is not int or not 0 <= top_k <= 512:
        raise ValueError('feature_selection_top_k must be an integer from0to512')
    return top_k


def select_features(train_x, test_x, y, rows, kind, threads, params, weights=None):
    top_k = validate_selection(params)
    if not top_k or len(train_x.columns) <= top_k:
        return train_x, test_x, {'status': 'disabled' if not top_k else 'unneeded',
                                 'input_columns': len(train_x.columns)}
    selector_x, _, categorical = prepare_frames(train_x, test_x, 'catboost', rows)
    selector = create_model({'params': {'depth': 5, 'learning_rate': .08,
                                       'seed': params.get('seed', 42), 'early_metric': 'default'},
                             'metric': 'rmse' if kind == 'regression' else 'macro_f1'},
                            kind, threads, 100)
    selector.fit(selector_x.iloc[rows], y.iloc[rows], cat_features=categorical,
                 sample_weight=weights)
    importance = np.asarray(selector.feature_importances_, dtype=float)
    if importance.shape != (len(train_x.columns),) or not np.isfinite(importance).all():
        raise ValueError('Invalid selector importance')
    ranked = np.argsort(-importance, kind='stable')[:top_k]
    selected = set(ranked.tolist())
    columns = [name for index, name in enumerate(train_x.columns) if index in selected]
    return train_x[columns].copy(), test_x[columns].copy(), {
        'status': 'selected', 'method': 'catboost_importance', 'iterations': 100,
        'fitting_rows': len(rows), 'input_columns': len(train_x.columns),
        'selected_columns': columns}
