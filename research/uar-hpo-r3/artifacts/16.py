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


def _anchor_parameters(recipe):
    """Match the adapters' effective control values, including sparse recipes.

    These constructor defaults/ranges are checked against actual model
    constructors without fitting. Search-space bounds remain independent: a
    valid control outside them must be rejected, never clipped into the study.
    """
    params = recipe.get('params', {})
    controls = {
        'lightgbm': {'num_leaves': (31, 15, 255, True),
                     'reg_lambda': (3., 0., 100., False),
                     'colsample_bytree': (.9, .5, 1., False)},
        'xgboost': {'max_depth': (params.get('depth', 8), 3, 12, True),
                    'min_child_weight': (3., 1., 50., False),
                    'reg_lambda': (8., 0., 100., False)},
        'catboost': {'depth': (6, 4, 10, True),
                     'l2_leaf_reg': (5., 1., 100., False),
                     'random_strength': (1., 0., 10., False)},
    }
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
    phases = {name: {'attempted': 0, 'completed': 0, 'failed': 0}
              for name in ('anchor', 'startup', 'guided', 'random')}
    for entry in entries:
        counts = phases[entry['sampling_phase']]
        counts['attempted'] += 1
        counts['completed' if entry.get('objective_valid', False) else 'failed'] += 1
    completed = sum(p['completed'] for p in phases.values())
    report.update(planned_trials=report['maximum_trials'], attempted_trials=len(entries),
                  completed_trials=completed, failed_trials=len(entries)-completed,
                  duplicate_trials=sum(e['status'] == 'duplicate' for e in entries),
                  unattempted_trials=report['maximum_trials']-len(entries),
                  sampler_startup_trials=report['startup_trials'] if report['sampler'] == 'tpe' else 0,
                  phase_counts=phases, guided_attempts=phases['guided']['attempted'],
                  guided_successful_trials=phases['guided']['completed'])


def optimize_recipe(spec, train, hashes, fitting_rows, recipe, output, worker,
                    deadline, trials=8, seed=137, sampler='tpe', worker_timeout=600, fair_reserve=None):
    """Return a recipe chosen by inner values, never outer labels or predictions.

    worker has run_worker's signature. It must implement time/memory guards and
    receive no credentials. A timeout is a failed trial, not a numeric objective.
    """
    if fair_reserve is not None:
        if fair_reserve != HPO_FAIR_RESERVE_MODE:
            raise ValueError('Unknown trusted HPO scheduling policy')
        return _optimize_recipe_fair_reserve(spec, train, hashes, fitting_rows, recipe, output,
            worker, deadline, trials, seed, sampler, worker_timeout)
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
        _update_trial_counts(report)
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
    anchor = _anchor_parameters(recipe)
    report['anchor_params'] = anchor
    if any(not lo <= anchor[k] <= hi for k, (_, lo, hi) in space.items()):
        report['anchor_error'] = 'Control outside predeclared search space'
        return finish('control_outside_search_space', deepcopy(recipe))
    study.enqueue_trial(anchor)
    selected, best_value, seen = deepcopy(recipe), None, set()
    for number in range(trials):
        remaining = deadline-time.monotonic()
        if remaining < 5:
            break
        completed_before = sum(t.state == optuna.trial.TrialState.COMPLETE for t in study.trials)
        phase = ('anchor' if number == 0 else 'random' if sampler == 'random'
                 else 'startup' if completed_before < report['startup_trials'] else 'guided')
        trial = study.ask()
        params = {}
        for name, (kind, low, high) in space.items():
            params[name] = (trial.suggest_int(name, low, high) if kind == 'int'
                            else trial.suggest_float(name, low, high, log=kind == 'log'))
        candidate = normalize(dict(deepcopy(recipe), params=dict(recipe.get('params', {}), **params)))
        fingerprint = signature(candidate)
        entry = {'number': number, 'params': params, 'recipe_sha256': fingerprint,
                 'recipe': candidate, 'sampling_phase': phase,
                 'completed_before_sampling': completed_before, 'objective_valid': False}
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
                         objective_valid=valid,
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
        _update_trial_counts(report)
        atomic_json(path, report)
    return finish('ok' if best_value is not None else 'no_successful_trials', selected)


# Research scheduling authority is caller/CLI-only; never a recipe parameter.
HPO_FAIR_RESERVE_MODE = 'hpo_fair_reserve_v1'
FAIR_OVERHEAD_SECONDS = 45.
FAIR_MINIMUM_SECONDS = 5.


class HPOFairReserveStop(RuntimeError):
    """A typed unqualified stop, never a completed/valid synthetic trial."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def validate_fair_reserve_configuration(*, phase_seconds, trials, worker_timeout,
                                        strict_runtime, kind=None, sampler='tpe'):
    if (strict_runtime is not True or type(trials) is not int or trials != 8
            or type(phase_seconds) not in (int, float) or not math.isfinite(phase_seconds)
            or phase_seconds != 900 or type(worker_timeout) not in (int, float)
            or not math.isfinite(worker_timeout) or worker_timeout != 600 or sampler != 'tpe'):
        raise ValueError('HPO fair reserve requires strict runtime, CLASS900, eight TPE trials and unchanged anchor600')
    if kind is not None and kind != 'classification':
        raise ValueError('HPO fair reserve pilot is classification only; regression stays OFF')
    required = worker_timeout + (trials - 1) * FAIR_MINIMUM_SECONDS + FAIR_OVERHEAD_SECONDS
    if phase_seconds < required:
        raise HPOFairReserveStop('fair_reserve_infeasible_anchor_and_remaining_slots')
    return required


def _fair_share(deadline, observed, remaining_slots, worker_timeout=600., anchor=False):
    if (type(deadline) not in (int, float) or type(observed) not in (int, float)
            or not math.isfinite(deadline) or not math.isfinite(observed)
            or type(remaining_slots) is not int or not 1 <= remaining_slots <= 8
            or type(worker_timeout) not in (int, float) or not math.isfinite(worker_timeout)
            or worker_timeout != 600 or type(anchor) is not bool):
        raise HPOFairReserveStop('fair_reserve_invalid_original_allocation')
    remaining = deadline - observed
    required = ((worker_timeout + (remaining_slots - 1) * FAIR_MINIMUM_SECONDS)
                if anchor else remaining_slots * FAIR_MINIMUM_SECONDS) + FAIR_OVERHEAD_SECONDS
    if remaining < required:
        raise HPOFairReserveStop('fair_reserve_remaining_slots_unattempted')
    return worker_timeout if anchor else min(worker_timeout,
        (remaining - FAIR_OVERHEAD_SECONDS) / remaining_slots)


class _FairReserveClock:
    """Observe the existing deadline; no replacement clock or time allowance."""
    def __init__(self, deadline):
        self.deadline, self.last, self.failure = deadline, None, None

    def observe(self):
        if self.failure is not None:
            raise self.failure
        try:
            now = time.monotonic()
            if (type(now) not in (int, float) or not math.isfinite(now)
                    or type(self.deadline) not in (int, float) or not math.isfinite(self.deadline)
                    or (self.last is not None and now < self.last)):
                raise HPOFairReserveStop('fair_reserve_original_clock_invalid_or_rollback')
            if now >= self.deadline:
                raise HPOFairReserveStop('fair_reserve_original_deadline_exhausted')
            self.last = now
            return now
        except Exception as exc:
            self.failure = exc
            raise

    def allocation(self, remaining_slots, anchor=False):
        try:
            observed = self.observe()
            return observed, _fair_share(self.deadline, observed, remaining_slots, anchor=anchor)
        except Exception as exc:
            self.failure = exc
            raise


def _fair_technical_result(result):
    if type(result) is not dict or result.get('strict_runtime') is not True:
        return 'fair_reserve_strict_worker_return_unconfirmed'
    origin = result.get('hpo_fair_reserve_provenance')
    fields = {'schema', 'cleanup_confirmed', 'coordinator_killed',
              'primary_exception_type', 'prior_result_status'}
    if (type(origin) is not dict or set(origin) != fields
            or origin.get('schema') != 'hpo-fair-reserve-worker-origin-v1'
            or origin.get('cleanup_confirmed') is not True
            or type(origin.get('prior_result_status')) is not str
            or not origin['prior_result_status']
            or (origin.get('coordinator_killed') is not None
                and (type(origin['coordinator_killed']) is not str or not origin['coordinator_killed']))
            or (origin.get('primary_exception_type') is not None
                and (type(origin['primary_exception_type']) is not str or not origin['primary_exception_type']))):
        return 'fair_reserve_parent_failure_provenance_unconfirmed'
    if origin['primary_exception_type'] is not None:
        return 'fair_reserve_parent_technical_exception'
    if origin['coordinator_killed'] not in (None, 'timeout'):
        return 'fair_reserve_worker_resource_or_observation_failure'
    if origin['prior_result_status'] not in {'ok', 'error', 'timeout'}:
        return 'fair_reserve_worker_resource_or_observation_failure'
    if type(result.get('status')) is not str or result['status'] not in {'ok', 'error', 'timeout'}:
        return 'fair_reserve_worker_resource_or_observation_failure'
    # A returned exception type without parent attribution is still unknown;
    # do not turn it into an ordinary failed objective.
    if result.get('exception_type') is not None:
        return 'fair_reserve_unknown_worker_exception'
    if result.get('cleanup_confirmed') is False:
        return 'fair_reserve_worker_cleanup_unconfirmed'
    observation = result.get('cleanup_observation')
    if type(observation) is dict and (observation.get('denial_count', 0)
                                     or observation.get('unresolved', [])):
        return 'fair_reserve_worker_cleanup_unconfirmed'
    return None


def _optimize_recipe_fair_reserve(spec, train, hashes, fitting_rows, recipe, output,
                                 worker, deadline, trials, seed, sampler, worker_timeout):
    if spec.get('kind') != 'classification':
        raise ValueError('HPO fair reserve pilot is classification only; regression stays OFF')
    validate_fair_reserve_configuration(phase_seconds=900, trials=trials,
        worker_timeout=worker_timeout, strict_runtime=True, kind=spec.get('kind'), sampler=sampler)
    if not math.isfinite(deadline):
        raise ValueError('Invalid original HPO deadline')
    space = search_space(recipe['engine'])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()  # Existing elapsed accounting only; deadline is caller-owned.
    clock = _FairReserveClock(deadline)
    policy = {'mode': HPO_FAIR_RESERVE_MODE, 'phase_seconds': 900,
        'original_deadline_monotonic': deadline, 'overhead_reserve_seconds': FAIR_OVERHEAD_SECONDS,
        'minimum_slice_seconds': FAIR_MINIMUM_SECONDS, 'allocations': [],
        'worker_callback_invocations': 0, 'actual_model_process_launches': None,
        'actual_recursive_learner_fits': None,
        'count_scope': 'Callback invocations are not process-start or recursive-fit attestations.',
        'soft_reservations_not_wall_guarantees': True}
    report = {'status': 'pending', 'sampler': sampler, 'seed': seed,
        'maximum_trials': trials, 'startup_trials': min(3, trials),
        'search_space': space, 'trials': [], 'control_recipe': deepcopy(recipe),
        'scope': 'inner fitting holdout; not outer/private/official score',
        'fair_reserve': policy}
    path = output / 'hpo.json'
    selected, best_value, seen = deepcopy(recipe), None, set()

    def finish(status):
        _update_trial_counts(report)
        report.update(status=status, selected_recipe=selected,
                      seconds=round(time.monotonic() - start, 3))
        atomic_json(path, report)
        return selected, report

    try:
        clock.observe()
        if deadline - clock.last > 900:
            raise HPOFairReserveStop('fair_reserve_original_phase_exceeds900')
        # Full untouched anchor maximum plus all later minimum slots, before any fit.
        clock.allocation(trials, anchor=True)
        try:
            import optuna
        except ImportError:
            return finish('optional_dependency_unavailable')
        try:
            tr, va, split_info = nested_partition(spec, train, hashes, fitting_rows, seed)
        except ValueError as exc:
            report['split_error'] = str(exc)[:300]
            return finish('inner_split_unavailable')
        split = output / 'split.npz'
        np.savez(split, train=tr, validation=va)
        report.update(split=split_info, optuna_version=optuna.__version__)
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        chooser = optuna.samplers.TPESampler(seed=seed, n_startup_trials=min(3, trials))
        study = optuna.create_study(direction='maximize' if spec['greater_is_better'] else 'minimize',
                                    sampler=chooser)
        anchor = _anchor_parameters(recipe)
        report['anchor_params'] = anchor
        if any(not lo <= anchor[k] <= hi for k, (_, lo, hi) in space.items()):
            report['anchor_error'] = 'Control outside predeclared search space'
            return finish('control_outside_search_space')
        study.enqueue_trial(anchor)
        for number in range(trials):
            k = trials - number
            clock.allocation(k, anchor=number == 0)
            completed_before = sum(t.state == optuna.trial.TrialState.COMPLETE for t in study.trials)
            phase = ('anchor' if number == 0 else 'startup'
                     if completed_before < report['startup_trials'] else 'guided')
            trial = study.ask()
            params = {}
            for name, (kind, low, high) in space.items():
                params[name] = (trial.suggest_int(name, low, high) if kind == 'int'
                    else trial.suggest_float(name, low, high, log=kind == 'log'))
            candidate = normalize(dict(deepcopy(recipe), params=dict(recipe.get('params', {}), **params)))
            fingerprint = signature(candidate)
            entry = {'number': number, 'params': params, 'recipe_sha256': fingerprint,
                'recipe': candidate, 'sampling_phase': phase,
                'completed_before_sampling': completed_before, 'objective_valid': False}
            allocation = {'number': number, 'recipe_sha256': fingerprint, 'sampling_phase': phase,
                'remaining_slots_including_current': k, 'proposal_sampled': True,
                'worker_callback_invoked': False, 'actual_model_process_launched': None,
                'status': 'proposal_prepared', 'original_deadline_monotonic': deadline,
                'overhead_reserve_seconds': FAIR_OVERHEAD_SECONDS}
            policy['allocations'].append(allocation)
            if fingerprint in seen:
                entry.update(status='duplicate', value=None)
                allocation['status'] = 'duplicate_no_worker'
                report['trials'].append(entry)
                study.tell(trial, state=optuna.trial.TrialState.FAIL)
            else:
                # Persist proposal/intent only. It grants no worker launch or fixed share.
                prepared, preview = clock.allocation(k, anchor=number == 0)
                allocation.update(prepared_monotonic=prepared, preview_timeout_seconds=preview)
                atomic_json(path, report)
                # Fresh clock AFTER ask/normalize/signature/persist, immediately before callback.
                admitted, timeout = clock.allocation(k, anchor=number == 0)
                allocation.update(admitted_monotonic=admitted, passed_timeout_seconds=timeout,
                    worker_callback_invoked=True, status='worker_callback_entered')
                seen.add(fingerprint)
                policy['worker_callback_invocations'] += 1
                try:
                    result = worker(spec, candidate, output / f'trial-{number:02d}', split, timeout)
                except BaseException as exc:
                    entry.update(status='error', value=None, exception_type=type(exc).__name__)
                    allocation.update(status='worker_callback_raised', exception_type=type(exc).__name__)
                    report['trials'].append(entry)
                    # Preserve the actual callback and primary exception even if telling
                    # the sampler also fails; no retry or replacement objective.
                    try:
                        study.tell(trial, state=optuna.trial.TrialState.FAIL)
                    except BaseException as tell_error:
                        allocation['sampler_failure_type'] = type(tell_error).__name__
                    raise
                allocation.update(status='worker_callback_returned',
                    returned_monotonic=time.monotonic(), returned_status=result.get('status') if type(result) is dict else None)
                fatal = _fair_technical_result(result)
                value = ((result.get('metrics') or {}).get(spec['metric'])
                         if type(result) is dict and fatal is None else None)
                valid = (fatal is None and result.get('status') == 'ok'
                         and isinstance(value, (int, float)) and math.isfinite(value))
                entry.update(status=result.get('status', 'error') if type(result) is dict else 'error',
                    value=value if valid else None, objective_valid=valid,
                    seconds=result.get('wall_seconds') if type(result) is dict else None,
                    fit_iterations=result.get('fit_iterations') if type(result) is dict else None)
                if fatal is not None:
                    entry['technical_stop_reason'] = fatal
                report['trials'].append(entry)
                if valid:
                    study.tell(trial, float(value))
                    if best_value is None or (value > best_value if spec['greater_is_better'] else value < best_value):
                        selected, best_value = candidate, float(value)
                else:
                    study.tell(trial, state=optuna.trial.TrialState.FAIL)
                report.update(best_inner_value=best_value, selected_recipe=selected)
                _update_trial_counts(report)
                atomic_json(path, report)
                if fatal is not None:
                    raise HPOFairReserveStop(fatal)
                # All actual callback/cleanup overrun is charged; later shares are not guaranteed.
                clock.observe()
                continue
            report.update(best_inner_value=best_value, selected_recipe=selected)
            _update_trial_counts(report)
            atomic_json(path, report)
            clock.observe()
        clock.observe()
        answer = finish('ok' if best_value is not None else 'no_successful_trials')
        clock.observe()  # Saving cannot grant time beyond the original phase.
        return answer
    except BaseException as exc:
        policy['stop_reason'] = exc.code if isinstance(exc, HPOFairReserveStop) else 'fair_reserve_technical_failure'
        policy['stop_exception_type'] = type(exc).__name__
        finish('fair_reserve_stopped')
        raise
