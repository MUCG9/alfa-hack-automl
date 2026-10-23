"""Optional nested HPO. Workers and their deadlines stay owned by the coordinator."""
from copy import deepcopy
from pathlib import Path
import hashlib
import math
import time

import numpy as np

from automl.evaluation.api import make_split
from automl.infrastructure.atomic import atomic_json
from automl.search.policy import normalize, signature


def nested_partition(spec, train, hashes, fitting_rows, seed=137):
    rows = np.asarray(fitting_rows, dtype=np.int64)
    if rows.ndim != 1 or len(rows) != len(np.unique(rows)) or not len(rows):
        raise ValueError('HPO requires unique fitting row positions')
    if rows.min() < 0 or rows.max() >= len(train):
        raise ValueError('HPO fitting row outside input')
    subset = train.iloc[rows].reset_index(drop=True)
    tr, va, info = make_split(spec, subset, np.asarray(hashes)[rows], seed=seed)
    tr, va = rows[tr], rows[va]
    if set(tr) & set(va) or not (set(tr) | set(va)) <= set(rows):
        raise ValueError('HPO partition escaped outer fitting rows')
    if spec.get('validation_strategy') != 'time':
        # Do not accept the legacy rare-group row fallback in a nested study.
        if set(np.asarray(hashes)[tr]) & set(np.asarray(hashes)[va]):
            raise ValueError('HPO requires disjoint feature groups')
    info = dict(info, local_split_sha256=info['split_sha256'],
                split_sha256=hashlib.sha256(tr.astype('<i8').tobytes()+va.astype('<i8').tobytes()).hexdigest(),
                scope='inside_outer_fitting_rows_only')
    return tr, va, info


def search_space(engine):
    # Deliberately leave class weights, calibration, seeds, features and target
    # transforms untouched. Rejected leaf10 is not searched again.
    if engine == 'lightgbm':
        return {'num_leaves': ('int', 31, 127),
                'reg_lambda': ('log', 2., 20.),
                'colsample_bytree': ('float', .75, 1.)}
    if engine == 'catboost':
        return {'depth': ('int', 4, 8), 'l2_leaf_reg': ('log', 1., 30.),
                'random_strength': ('float', 0., 3.)}
    if engine == 'xgboost':
        return {'max_depth': ('int', 4, 10), 'min_child_weight': ('log', 1., 12.),
                'reg_lambda': ('log', 2., 20.)}
    raise ValueError('HPO supports lightgbm, catboost and xgboost recipes')


def optimize_recipe(spec, train, hashes, fitting_rows, recipe, output, worker,
                    deadline, trials=8, seed=137, sampler='tpe', worker_timeout=600):
    """Return a recipe chosen by inner values, never outer labels or predictions.

    worker has run_worker's signature. It must implement time/memory guards and
    receive no credentials. A timeout is a failed trial, not a numeric objective.
    """
    if type(trials) is not int or not 1 <= trials <= 32:
        raise ValueError('HPO requires 1..32 trials')
    if sampler not in {'tpe', 'random'}:
        raise ValueError('Unknown HPO sampler')
    if not math.isfinite(deadline) or worker_timeout <= 0:
        raise ValueError('Invalid HPO deadline')
    space = search_space(recipe['engine'])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    report = {'status': 'pending', 'sampler': sampler, 'seed': seed,
              'maximum_trials': trials, 'startup_trials': min(3, trials),
              'search_space': space, 'trials': [], 'control_recipe': deepcopy(recipe),
              'scope': 'inner fitting holdout; not outer/private/official score'}
    path = output/'hpo.json'
    start = time.monotonic()

    def finish(status, selected):
        report.update(status=status, selected_recipe=selected,
                      seconds=round(time.monotonic()-start, 3))
        atomic_json(path, report)
        return selected, report

    if deadline-time.monotonic() < 5:
        return finish('deadline_before_start', deepcopy(recipe))
    try:
        import optuna
    except ImportError:
        return finish('optional_dependency_unavailable', deepcopy(recipe))
    try:
        tr, va, split_info = nested_partition(spec, train, hashes, fitting_rows, seed)
    except ValueError as exc:
        report['split_error'] = str(exc)[:300]
        return finish('inner_split_unavailable', deepcopy(recipe))
    split = output/'split.npz'
    np.savez(split, train=tr, validation=va)
    report.update(split=split_info, optuna_version=optuna.__version__)
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    chooser = (optuna.samplers.TPESampler(seed=seed, n_startup_trials=min(3, trials))
               if sampler == 'tpe' else optuna.samplers.RandomSampler(seed=seed))
    study = optuna.create_study(direction='maximize' if spec['greater_is_better'] else 'minimize',
                                sampler=chooser)
    # The unchanged anchor must construct the same model as the adapters.
    # Defaults differ by engine; XGBoost also accepts the legacy depth alias.
    defaults = {
        'lightgbm': {'num_leaves': 31, 'reg_lambda': 3., 'colsample_bytree': .9},
        'catboost': {'depth': 6, 'l2_leaf_reg': 5., 'random_strength': 1.},
        'xgboost': {'max_depth': recipe.get('params', {}).get('depth', 8),
                    'min_child_weight': 3., 'reg_lambda': 8.},
    }[recipe['engine']]
    anchor = {k: recipe.get('params', {}).get(k, defaults[k]) for k in space}
    if any(not lo <= anchor[k] <= hi for k, (_, lo, hi) in space.items()):
        report['anchor_error'] = 'Control outside predeclared search space'
        return finish('control_outside_search_space', deepcopy(recipe))
    study.enqueue_trial(anchor)
    selected, best_value, seen = deepcopy(recipe), None, set()
    for number in range(trials):
        remaining = deadline-time.monotonic()
        if remaining < 5:
            break
        trial = study.ask()
        params = {}
        for name, (kind, low, high) in space.items():
            params[name] = (trial.suggest_int(name, low, high) if kind == 'int'
                            else trial.suggest_float(name, low, high, log=kind == 'log'))
        candidate = normalize(dict(deepcopy(recipe), params=dict(recipe.get('params', {}), **params)))
        fingerprint = signature(candidate)
        entry = {'number': number, 'params': params, 'recipe_sha256': fingerprint,
                 'recipe': candidate}
        if fingerprint in seen:
            entry['status'] = 'duplicate'
            study.tell(trial, state=optuna.trial.TrialState.FAIL)
        else:
            seen.add(fingerprint)
            result = worker(spec, candidate, output/f'trial-{number:02d}', split,
                            min(worker_timeout, max(1, deadline-time.monotonic())))
            value = (result.get('metrics') or {}).get(spec['metric'])
            valid = result.get('status') == 'ok' and isinstance(value, (int, float)) and math.isfinite(value)
            entry.update(status=result.get('status', 'error'), value=value if valid else None,
                         seconds=result.get('wall_seconds'),
                         fit_iterations=result.get('fit_iterations'))
            if valid:
                study.tell(trial, float(value))
                if best_value is None or (value > best_value if spec['greater_is_better'] else value < best_value):
                    selected, best_value = candidate, float(value)
            else:
                study.tell(trial, state=optuna.trial.TrialState.FAIL)
        report['trials'].append(entry)
        report.update(best_inner_value=best_value, selected_recipe=selected)
        atomic_json(path, report)
    report['completed_trials'] = sum(t.state == optuna.trial.TrialState.COMPLETE for t in study.trials)
    return finish('ok' if best_value is not None else 'no_successful_trials', selected)
