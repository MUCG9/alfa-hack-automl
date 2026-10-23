"""Optional CatBoost feature importance selection, refitted for each fitting scope."""
import time

import numpy as np

from automl.execution.model_adapters.catboost import create_model
from automl.execution.preprocessing.frames import prepare_frames


def validate_selection(params):
    top_k = params.get('feature_selection_top_k', 0)
    if type(top_k) is not int or not 0 <= top_k <= 512:
        raise ValueError('feature_selection_top_k must be an integer from0to512')
    protect = params.get('feature_selection_protect_original', False)
    if type(protect) is not bool:
        raise ValueError('feature_selection_protect_original must be a boolean')
    if protect and not top_k:
        raise ValueError('Protected original selection requires positive feature_selection_top_k')
    return top_k


def select_features(train_x, test_x, y, rows, kind, threads, params, weights=None,
                    protected_columns=(), importance_cache=None, cache_scope=None,
                    importance_probe=None):
    tick = time.monotonic()
    top_k = validate_selection(params)
    protect = params.get('feature_selection_protect_original', False)
    protected = set(protected_columns) if protect else set()
    if not protected <= set(train_x) or not protected <= set(test_x):
        raise ValueError('Protected original feature absent from prepared frames')
    protected_order = [name for name in train_x if name in protected]
    if protect and set(train_x) <= protected:
        return train_x.copy(), test_x.copy(), {
            'status': 'all_original_protected', 'method': 'union_original_top_k',
            'input_columns': len(train_x.columns), 'fitting_rows': len(rows),
            'protected_columns': protected_order, 'selected_columns': list(train_x),
            'teacher_fitted': False, 'selector_seconds': round(time.monotonic()-tick, 6)}
    if not top_k or len(train_x.columns) <= top_k:
        info = {'status': 'disabled' if not top_k else 'unneeded',
                'input_columns': len(train_x.columns), 'teacher_fitted': False,
                'selector_seconds': round(time.monotonic()-tick, 6)}
        if protect:
            info.update(method='union_original_top_k', protected_columns=protected_order,
                        teacher_selected_columns=list(train_x), selected_columns=list(train_x))
        return train_x, test_x, info
    selector_x, _, categorical = prepare_frames(train_x, test_x, 'catboost', rows)
    teacher_recipe = {'params': {'depth': 5, 'learning_rate': .08,
                                'seed': params.get('seed', 42), 'early_metric': 'default'},
                      'metric': 'rmse' if kind == 'regression' else 'macro_f1'}
    importance, cache_key, cache_record = None, None, None
    context = None
    probe_record = None
    if importance_probe is not None:
        context = dict(fitting_x=selector_x.iloc[rows], fitting_y=y.iloc[rows],
            rows=np.asarray(rows), weights=weights, teacher_recipe=teacher_recipe,
            kind=kind, threads=threads, categorical=categorical,
            selection={'top_k': top_k, 'protect_original': protect,
                'protected_columns': protected_order, 'fitting_scope': cache_scope})
        probe_record = importance_probe.begin(**context)
    teacher_fitted = True
    if importance_cache is not None:
        if importance_cache.enabled and (type(cache_scope) is not str or not cache_scope):
            raise ValueError('Enabled teacher cache requires an explicit fitting scope')
        lookup_context = context if context is not None else dict(
            fitting_x=selector_x.iloc[rows], fitting_y=y.iloc[rows], rows=np.asarray(rows),
            weights=weights, teacher_recipe=teacher_recipe, kind=kind, threads=threads,
            categorical=categorical, selection={'top_k': top_k, 'protect_original': protect,
                'protected_columns': protected_order, 'fitting_scope': cache_scope})
        cache_key, importance, cache_record = importance_cache.lookup(**lookup_context)
        teacher_fitted = importance is None
    if teacher_fitted:
        teacher_tick = time.monotonic() if cache_record is not None or probe_record is not None else None
        selector = create_model(teacher_recipe, kind, threads, 100)
        constructed = time.monotonic() if probe_record is not None else None
        if probe_record is not None:
            # Hash and fit consume the exact same prepared objects. iloc/materialization
            # is outside pure .fit timing; the inclusive selector clock still pays it.
            fitting_x, fitting_y = context['fitting_x'], context['fitting_y']
            fit_tick = time.monotonic()
            selector.fit(fitting_x, fitting_y, cat_features=categorical, sample_weight=weights)
        else:
            selector.fit(selector_x.iloc[rows], y.iloc[rows], cat_features=categorical,
                         sample_weight=weights)
        fitted = time.monotonic() if probe_record is not None else None
        importance = np.asarray(selector.feature_importances_, dtype=float)
        extracted = time.monotonic() if probe_record is not None else None
        if cache_record is not None:
            cache_record['teacher_fit_seconds'] = time.monotonic()-teacher_tick
    elif cache_record is not None:
        cache_record['teacher_fit_seconds'] = 0.
    if importance.shape != (len(train_x.columns),) or not np.isfinite(importance).all():
        raise ValueError('Invalid selector importance')
    store_invoked = teacher_fitted and cache_record is not None
    store_tick = time.monotonic() if probe_record is not None and store_invoked else None
    if store_invoked:
        cache_record['stored'] = importance_cache.store(cache_key, list(train_x), importance)
    store_seconds = time.monotonic()-store_tick if store_tick is not None else 0.
    ranked = np.argsort(-importance, kind='stable')[:top_k]
    selected = set(ranked.tolist())
    teacher_columns = [name for index, name in enumerate(train_x.columns) if index in selected]
    selected.update(index for index, name in enumerate(train_x.columns) if name in protected)
    columns = [name for index, name in enumerate(train_x.columns) if index in selected]
    info = {
        'status': 'selected', 'method': 'catboost_importance', 'iterations': 100,
        'fitting_rows': len(rows), 'input_columns': len(train_x.columns),
        'selected_columns': columns, 'teacher_fitted': teacher_fitted,
        'selector_seconds': round(time.monotonic()-tick, 6)}
    if cache_record is not None:
        info['importance_cache'] = cache_record
    if protect:
        info.update(method='union_original_top_k', teacher_selected_columns=teacher_columns,
                    protected_columns=protected_order)
    if probe_record is not None:
        copy_tick = time.monotonic()
        selected_train, selected_test = train_x[columns].copy(), test_x[columns].copy()
        copy_seconds = time.monotonic()-copy_tick
        # Parameter collection is diagnostics, outside the constructor/fit/importance timer.
        teacher_params, parameter_probe_seconds = None, 0.
        if teacher_fitted:
            param_tick = time.monotonic()
            teacher_params = selector.get_params()
            parameter_probe_seconds = time.monotonic()-param_tick
        timings = {
            'teacher_constructor': constructed-teacher_tick if teacher_fitted else 0.,
            'teacher_fit_argument_preparation': fit_tick-constructed if teacher_fitted else 0.,
            'teacher_pure_fit': fitted-fit_tick if teacher_fitted else 0.,
            'teacher_importance_extraction': extracted-fitted if teacher_fitted else 0.,
            'teacher_constructor_fit_importance_inclusive': extracted-teacher_tick if teacher_fitted else 0.,
            'teacher_parameter_probe': parameter_probe_seconds,
            'cache_key_lookup': None if cache_record is None else cache_record.get('hash_seconds'),
            'cache_store_invoked': store_invoked, 'cache_store': store_seconds,
            'output_frame_copy': copy_seconds}
        info['teacher_diagnostics'] = importance_probe.finish(probe_record, importance,
            list(train_x), columns, ranked, teacher_params, timings, cache_record, importance_cache,
            selector_started=tick)
        # Pilot selector clock includes common digests, cache, params, ranking and trace.
        info['selector_seconds'] = round(time.monotonic()-tick, 6)
        return selected_train, selected_test, info
    return train_x[columns].copy(), test_x[columns].copy(), info
