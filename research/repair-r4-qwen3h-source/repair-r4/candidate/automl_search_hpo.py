"""Optional nested HPO. Workers and their deadlines stay owned by the coordinator."""
from copy import deepcopy
from pathlib import Path
import hashlib
import math
import time
import numpy as np
from automl_evaluation_api import make_split
from automl_atomic import atomic_json
from automl_policy import normalize, signature

def nested_partition(spec, train, hashes, fitting_rows, seed=137):
    rows = np.asarray(fitting_rows, dtype=np.int64)
    if rows.ndim != 1 or len(rows) != len(np.unique(rows)) or (not len(rows)):
        raise ValueError('HPO requires unique fitting row positions')
    if rows.min() < 0 or rows.max() >= len(train):
        raise ValueError('HPO fitting row outside input')
    subset = train.iloc[rows].reset_index(drop=True)
    tr, va, info = make_split(spec, subset, np.asarray(hashes)[rows], seed=seed)
    tr, va = (rows[tr], rows[va])
    if set(tr) & set(va) or not set(tr) | set(va) <= set(rows):
        raise ValueError('HPO partition escaped outer fitting rows')
    if spec.get('validation_strategy') != 'time':
        if set(np.asarray(hashes)[tr]) & set(np.asarray(hashes)[va]):
            raise ValueError('HPO requires disjoint feature groups')
    info = dict(info, local_split_sha256=info['split_sha256'], split_sha256=hashlib.sha256(tr.astype('<i8').tobytes() + va.astype('<i8').tobytes()).hexdigest(), scope='inside_outer_fitting_rows_only')
    return (tr, va, info)

def search_space(engine):
    if engine == 'lightgbm':
        return {'num_leaves': ('int', 31, 127), 'reg_lambda': ('log', 2.0, 20.0), 'colsample_bytree': ('float', 0.75, 1.0)}
    if engine == 'catboost':
        return {'depth': ('int', 4, 8), 'l2_leaf_reg': ('log', 1.0, 30.0), 'random_strength': ('float', 0.0, 3.0)}
    if engine == 'xgboost':
        return {'max_depth': ('int', 4, 10), 'min_child_weight': ('log', 1.0, 12.0), 'reg_lambda': ('log', 2.0, 20.0)}
    raise ValueError('HPO supports lightgbm, catboost and xgboost recipes')

def _anchor_parameters(recipe):
    """Match the adapters' effective control values, including sparse recipes.

    These constructor defaults/ranges are checked against actual model
    constructors without fitting. Search-space bounds remain independent: a
    valid control outside them must be rejected, never clipped into the study.
    """
    params = recipe.get('params', {})
    controls = {'lightgbm': {'num_leaves': (31, 15, 255, True), 'reg_lambda': (3.0, 0.0, 100.0, False), 'colsample_bytree': (0.9, 0.5, 1.0, False)}, 'xgboost': {'max_depth': (params.get('depth', 8), 3, 12, True), 'min_child_weight': (3.0, 1.0, 50.0, False), 'reg_lambda': (8.0, 0.0, 100.0, False)}, 'catboost': {'depth': (6, 4, 10, True), 'l2_leaf_reg': (5.0, 1.0, 100.0, False), 'random_strength': (1.0, 0.0, 10.0, False)}}
    anchor = {}
    for name, (default, low, high, integer) in controls[recipe['engine']].items():
        value = float(params.get(name, default))
        if not math.isfinite(value):
            raise ValueError(f'Non-finite parameter: {name}')
        value = float(np.clip(value, low, high))
        anchor[name] = int(value) if integer else value
    return anchor

def _update_trial_counts(report):
    """Describe actual work; a TPE label alone does not imply guided search."""
    entries = report['trials']
    phases = {name: {'attempted': 0, 'completed': 0, 'failed': 0} for name in ('anchor', 'startup', 'guided', 'random')}
    for entry in entries:
        counts = phases[entry['sampling_phase']]
        counts['attempted'] += 1
        counts['completed' if entry.get('objective_valid', False) else 'failed'] += 1
    completed = sum((p['completed'] for p in phases.values()))
    report.update(planned_trials=report['maximum_trials'], attempted_trials=len(entries), completed_trials=completed, failed_trials=len(entries) - completed, duplicate_trials=sum((e['status'] == 'duplicate' for e in entries)), unattempted_trials=report['maximum_trials'] - len(entries), sampler_startup_trials=report['startup_trials'] if report['sampler'] == 'tpe' else 0, phase_counts=phases, guided_attempts=phases['guided']['attempted'], guided_successful_trials=phases['guided']['completed'])

def optimize_recipe(spec, train, hashes, fitting_rows, recipe, output, worker, deadline, trials=8, seed=137, sampler='tpe', worker_timeout=600):
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
    report = {'status': 'pending', 'sampler': sampler, 'seed': seed, 'maximum_trials': trials, 'startup_trials': min(3, trials), 'search_space': space, 'trials': [], 'control_recipe': deepcopy(recipe), 'scope': 'inner fitting holdout; not outer/private/official score'}
    path = output / 'hpo.json'
    start = time.monotonic()

    def finish(status, selected):
        _update_trial_counts(report)
        report.update(status=status, selected_recipe=selected, seconds=round(time.monotonic() - start, 3))
        atomic_json(path, report)
        return (selected, report)
    if deadline - time.monotonic() < 5:
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
    split = output / 'split.npz'
    np.savez(split, train=tr, validation=va)
    report.update(split=split_info, optuna_version=optuna.__version__)
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    chooser = optuna.samplers.TPESampler(seed=seed, n_startup_trials=min(3, trials)) if sampler == 'tpe' else optuna.samplers.RandomSampler(seed=seed)
    study = optuna.create_study(direction='maximize' if spec['greater_is_better'] else 'minimize', sampler=chooser)
    anchor = _anchor_parameters(recipe)
    report['anchor_params'] = anchor
    if any((not lo <= anchor[k] <= hi for k, (_, lo, hi) in space.items())):
        report['anchor_error'] = 'Control outside predeclared search space'
        return finish('control_outside_search_space', deepcopy(recipe))
    study.enqueue_trial(anchor)
    selected, best_value, seen = (deepcopy(recipe), None, set())
    for number in range(trials):
        remaining = deadline - time.monotonic()
        if remaining < 5:
            break
        completed_before = sum((t.state == optuna.trial.TrialState.COMPLETE for t in study.trials))
        phase = 'anchor' if number == 0 else 'random' if sampler == 'random' else 'startup' if completed_before < report['startup_trials'] else 'guided'
        trial = study.ask()
        params = {}
        for name, (kind, low, high) in space.items():
            params[name] = trial.suggest_int(name, low, high) if kind == 'int' else trial.suggest_float(name, low, high, log=kind == 'log')
        candidate = normalize(dict(deepcopy(recipe), params=dict(recipe.get('params', {}), **params)))
        fingerprint = signature(candidate)
        entry = {'number': number, 'params': params, 'recipe_sha256': fingerprint, 'recipe': candidate, 'sampling_phase': phase, 'completed_before_sampling': completed_before, 'objective_valid': False}
        if fingerprint in seen:
            entry['status'] = 'duplicate'
            study.tell(trial, state=optuna.trial.TrialState.FAIL)
        else:
            seen.add(fingerprint)
            result = worker(spec, candidate, output / f'trial-{number:02d}', split, min(worker_timeout, max(1, deadline - time.monotonic())))
            value = (result.get('metrics') or {}).get(spec['metric'])
            valid = result.get('status') == 'ok' and isinstance(value, (int, float)) and math.isfinite(value)
            entry.update(status=result.get('status', 'error'), value=value if valid else None, objective_valid=valid, seconds=result.get('wall_seconds'), fit_iterations=result.get('fit_iterations'))
            if valid:
                study.tell(trial, float(value))
                if best_value is None or (value > best_value if spec['greater_is_better'] else value < best_value):
                    selected, best_value = (candidate, float(value))
            else:
                study.tell(trial, state=optuna.trial.TrialState.FAIL)
        report['trials'].append(entry)
        report.update(best_inner_value=best_value, selected_recipe=selected)
        _update_trial_counts(report)
        atomic_json(path, report)
    return finish('ok' if best_value is not None else 'no_successful_trials', selected)
