"""FE-02 trusted development dispatcher, copied by benchmark_candidates.

Controls use the frozen canonical worker unchanged. The treatment changes only
the selector's output policy to union(original columns, ordinary top32).
"""
from copy import deepcopy
from pathlib import Path
import json
import sys
import time

ENGINE = 'lightgbm_union_original'


def protected_union(base, original_columns, train_x, test_x, y, rows,
                    kind, threads, params, weights=None):
    protected = set(original_columns)
    if not protected <= set(train_x) or not protected <= set(test_x):
        raise ValueError('Protected original feature absent from prepared frames')
    tick = time.monotonic()
    if set(train_x) <= protected:
        # Union would retain every column regardless of teacher ranking.
        return train_x.copy(), test_x.copy(), {
            'status': 'all_original_protected', 'method': 'union_original_top32',
            'input_columns': len(train_x.columns), 'fitting_rows': len(rows),
            'selected_columns': list(train_x.columns), 'teacher_fitted': False,
            'selector_seconds': round(time.monotonic()-tick, 6)}
    selected_x, _, info = base(train_x, test_x, y, rows, kind, threads, params, weights)
    selected = set(selected_x.columns) | protected
    columns = [column for column in train_x.columns if column in selected]
    return train_x[columns].copy(), test_x[columns].copy(), dict(info,
        method='union_original_top32', teacher_selected_columns=list(selected_x),
        protected_columns=[column for column in train_x if column in protected],
        selected_columns=columns, teacher_fitted=info.get('status') == 'selected',
        selector_seconds=round(time.monotonic()-tick, 6))


def run(job):
    import automl_worker as worker
    if job['recipe']['engine'] != ENGINE:
        return worker.run(job)
    spec, recipe = job['spec'], deepcopy(job['recipe'])
    if (spec['kind'] != 'classification' or spec['metric'] != 'macro_f1'
            or spec.get('text_features') or recipe.get('feature_code')
            or recipe.get('data_policy') or recipe['params'].get('feature_selection_top_k') != 32
            or recipe['params'].get('feature_views') != 'categorical_te_pair'):
        raise ValueError('FE-02 requires unchanged MacroF1 two-view recipe, selector32, noop policy')
    recipe['engine'] = 'lightgbm'
    original = worker.select_features
    def selector(*args, **kwargs):
        return protected_union(original, spec['features'], *args, **kwargs)
    worker.select_features = selector
    try:
        worker.run(dict(job, recipe=recipe))
    finally:
        worker.select_features = original
    path = Path(job['output_dir'])/'result.json'
    record = json.loads(path.read_text())
    record['research_intervention'] = {
        'name': 'FE-02 union original with ordinary CatBoost top32',
        'declared_engine': ENGINE, 'scope': 'Development-only, not runtime-integrated'}
    from automl_atomic import atomic_json
    atomic_json(path, record)


if __name__ == '__main__':
    job = json.loads(Path(sys.argv[1]).read_text())
    try:
        run(job)
    except Exception as exc:
        from automl_atomic import atomic_json
        atomic_json(Path(job['output_dir'])/'result.json', {
            'status': 'error', 'exception_type': type(exc).__name__})
        raise
