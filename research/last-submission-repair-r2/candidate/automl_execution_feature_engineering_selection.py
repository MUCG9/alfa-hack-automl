"""Optional CatBoost feature importance selection, refitted for each fitting scope."""
import time
import numpy as np
from automl_model_catboost import create_model
from automl_frames import prepare_frames

def validate_selection(params):
    top_k = params.get('feature_selection_top_k', 0)
    if type(top_k) is not int or not 0 <= top_k <= 512:
        raise ValueError('feature_selection_top_k must be an integer from0to512')
    protect = params.get('feature_selection_protect_original', False)
    if type(protect) is not bool:
        raise ValueError('feature_selection_protect_original must be a boolean')
    if protect and (not top_k):
        raise ValueError('Protected original selection requires positive feature_selection_top_k')
    return top_k

def select_features(train_x, test_x, y, rows, kind, threads, params, weights=None, protected_columns=()):
    tick = time.monotonic()
    top_k = validate_selection(params)
    protect = params.get('feature_selection_protect_original', False)
    protected = set(protected_columns) if protect else set()
    if not protected <= set(train_x) or not protected <= set(test_x):
        raise ValueError('Protected original feature absent from prepared frames')
    protected_order = [name for name in train_x if name in protected]
    if protect and set(train_x) <= protected:
        return (train_x.copy(), test_x.copy(), {'status': 'all_original_protected', 'method': 'union_original_top_k', 'input_columns': len(train_x.columns), 'fitting_rows': len(rows), 'protected_columns': protected_order, 'selected_columns': list(train_x), 'teacher_fitted': False, 'selector_seconds': round(time.monotonic() - tick, 6)})
    if not top_k or len(train_x.columns) <= top_k:
        info = {'status': 'disabled' if not top_k else 'unneeded', 'input_columns': len(train_x.columns), 'teacher_fitted': False, 'selector_seconds': round(time.monotonic() - tick, 6)}
        if protect:
            info.update(method='union_original_top_k', protected_columns=protected_order, teacher_selected_columns=list(train_x), selected_columns=list(train_x))
        return (train_x, test_x, info)
    selector_x, _, categorical = prepare_frames(train_x, test_x, 'catboost', rows)
    selector = create_model({'params': {'depth': 5, 'learning_rate': 0.08, 'seed': params.get('seed', 42), 'early_metric': 'default'}, 'metric': 'rmse' if kind == 'regression' else 'macro_f1'}, kind, threads, 100)
    selector.fit(selector_x.iloc[rows], y.iloc[rows], cat_features=categorical, sample_weight=weights)
    importance = np.asarray(selector.feature_importances_, dtype=float)
    if importance.shape != (len(train_x.columns),) or not np.isfinite(importance).all():
        raise ValueError('Invalid selector importance')
    ranked = np.argsort(-importance, kind='stable')[:top_k]
    selected = set(ranked.tolist())
    teacher_columns = [name for index, name in enumerate(train_x.columns) if index in selected]
    selected.update((index for index, name in enumerate(train_x.columns) if name in protected))
    columns = [name for index, name in enumerate(train_x.columns) if index in selected]
    info = {'status': 'selected', 'method': 'catboost_importance', 'iterations': 100, 'fitting_rows': len(rows), 'input_columns': len(train_x.columns), 'selected_columns': columns, 'teacher_fitted': True, 'selector_seconds': round(time.monotonic() - tick, 6)}
    if protect:
        info.update(method='union_original_top_k', teacher_selected_columns=teacher_columns, protected_columns=protected_order)
    return (train_x[columns].copy(), test_x[columns].copy(), info)
