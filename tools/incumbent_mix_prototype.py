"""Development implementation for PIPE-02; no fits or source mutations on import.

Move the tested implementation into canonical search only after frozen CV ends.
Fitting is intentionally not exposed as a standalone CLI during that freeze.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import numpy as np
import pandas as pd
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.run_budget import budget_metadata
from automl.evaluation.api import make_split, make_time_split
from automl.execution.api import read_cache, combine, materialize
from automl.publishing.api import checkpoint, save_submission, read_submission_values, positive_class_index
from automl.search.policy import portfolio, normalize, signature
from automl.search.hpo import optimize_recipe
from automl.search.runner import run_worker, median_iterations, file_fingerprints, journal

CLASS_AUGMENTATION_QUALIFIED = False  # Change only following the ongoing CV gate.


def profile_recipes(spec, allow_class_augmentation=False):
    """Data-agnostic priors from existing portfolio capabilities, no task keys."""
    if spec.get('text_features') or spec.get('task_family') == 'pointwise_ranking':
        return None
    candidates = portfolio(spec)
    if spec['kind'] == 'regression' and spec['metric'] == 'rmse':
        base = next((r for r in candidates if r['params'].get('history_asof')), None)
        native = next((r for r in candidates if r['engine'] == 'catboost'), None)
        if base is None or native is None or spec.get('validation_strategy') != 'time':
            return None
        return {'control': {'engine': 'ensemble', 'params': {},
                            'hypothesis': 'Fixed qualified history/native control',
                            'components': [deepcopy(base), deepcopy(native)], 'weights': [.9, 1-.9]},
                'augmentation': deepcopy(base), 'adaptive': True}
    if spec['kind'] == 'classification' and spec['metric'] == 'macro_f1':
        base = next((r for r in candidates if r['params'].get('feature_views')), None)
        independent = next((r for r in candidates if r['engine'] == 'xgboost' and r['params'].get('calibrate')), None)
        if base is None or independent is None:
            return None
        alternate = normalize(dict(deepcopy(base), params=dict(base['params'], seed=48)))
        control = {'engine': 'ensemble', 'params': {}, 'hypothesis': 'Fixed qualified categorical control',
                   'components': [deepcopy(base), alternate, deepcopy(independent)], 'weights': [1/3]*3}
        augmentation = normalize(dict(deepcopy(base), params=dict(base['params'],
            seed=53, class_weight_power=1., feature_selection_top_k=32))) if allow_class_augmentation else None
        return {'control': control, 'augmentation': augmentation, 'adaptive': False}
    return None


def paired_passes(spec, control, candidate, support=None):
    gain = (candidate[spec['metric']]-control[spec['metric']])*(1 if spec['greater_is_better'] else -1)
    if not np.isfinite(gain) or gain <= 0:
        return False
    if spec['kind'] != 'classification':
        return True
    if not support or len(spec['classes']) < 2:
        return False
    delta = {c: candidate['per_class_f1'][c]-control['per_class_f1'][c] for c in spec['classes']}
    rarest = min(spec['classes'], key=lambda c: support[c])
    return (not any(delta[c] < -.01-1e-12 for c in spec['classes'] if support[c] >= 100)
            and np.mean([v for c, v in delta.items() if c != rarest]) > 0)


def study_iterations(report):
    """Transfer iterations only from the selected successful full-study trial."""
    selected = signature(report['selected_recipe'])
    for trial in report.get('trials', []):
        if trial.get('value') is not None and signature(trial['recipe']) == selected:
            value = trial.get('fit_iterations')
            if type(value) is int and 1 <= value <= 3000:
                return value
    raise ValueError('Selected full study has no valid iteration provenance')


def full_output(spec, records, weights, directory, sample, test):
    """Mix actual full-fit outputs; never execute a nested model recipe."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    arrays = []
    for record in records:
        if record.get('status') != 'ok' or not record.get('full_fit'):
            raise ValueError('Only successful full-fit outputs can be mixed')
        if spec['kind'] == 'classification':
            with np.load(Path(record['submission']).parent/'test_probabilities.npz', allow_pickle=False) as saved:
                classes = saved['classes'].astype(str).tolist()
                if len(set(classes)) != len(classes) or set(classes) != set(spec['classes']):
                    raise ValueError('Full probability class schema differs')
                values = saved['probabilities'][:, [classes.index(c) for c in spec['classes']]]
            if (values.shape != (len(test), len(spec['classes'])) or not np.isfinite(values).all()
                    or (values < 0).any() or (values > 1).any()
                    or not np.allclose(values.sum(axis=1), 1, atol=1e-7, rtol=1e-7)):
                raise ValueError('Invalid full probabilities')
        else:
            values = np.asarray(read_submission_values(spec, record['submission']), dtype=float)
            if values.shape != (len(test),) or not np.isfinite(values).all():
                raise ValueError('Invalid full regression predictions')
        arrays.append(values)
    weights = np.asarray(weights, dtype=float)
    if len(weights) != len(arrays) or not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError('Invalid full mixture weights')
    weights = weights/weights.sum()
    mixed = sum(w*x for w, x in zip(weights, arrays))
    if spec['kind'] == 'classification':
        classes = np.asarray(spec['classes'])
        np.savez_compressed(directory/'test_probabilities.npz', probabilities=mixed, classes=classes)
        if spec['prediction_type'] == 'probability_matrix':
            values = mixed[:, [list(classes).index(c) for c in spec['output_columns']]]
        elif spec['prediction_type'] == 'probability':
            values = mixed[:, positive_class_index(spec, classes)]
        else:
            values = classes[mixed.argmax(axis=1)]
    else:
        values = mixed
    save_submission(spec, sample, test, values, directory/'submission.csv')
    recipe = records[0]['recipe'] if len(records) == 1 else {
        'engine': 'ensemble', 'params': {}, 'hypothesis': 'Fixed incumbent-plus-augmentation procedure',
        'components': [r['recipe'] for r in records], 'weights': weights.tolist()}
    result = {'status': 'ok', 'full_fit': True, 'recipe': recipe, 'metrics': None,
        'fit_iterations': records[0]['fit_iterations'] if len(records) == 1 else [r['fit_iterations'] for r in records],
        'feature_count': sum(r.get('feature_count', 0) for r in records),
        'submission': str(directory/'submission.csv'), 'output_dir': str(directory),
        'components': records, 'full_training_outputs_reused': True}
    atomic_json(directory/'result.json', result)
    return result


def solve_profile(args, task_data, runs, root, primary, protected_paths, fingerprints,
                  started, deadline, worker=None, optimizer=None,
                  allow_class_augmentation=CLASS_AUGMENTATION_QUALIFIED):
    """PIPE-02 execution; caller prepared immutable primary split and fallback."""
    spec, profile, train, test, sample, text, hashes = task_data
    plan = profile_recipes(spec, allow_class_augmentation)
    if plan is None:
        return None
    worker = worker or run_worker
    optimizer = optimizer or optimize_recipe
    runs, root = Path(runs), Path(root)
    output = root/'submission.csv'
    reserve = min(args.time_budget*.4, 3600 if plan['adaptive'] else 1800)
    controls, augmentations, chosen_records, gates, studies, scores = [], [], [], [], [], []
    all_augmentation_valid = plan['augmentation'] is not None
    phase_complete = False
    final_status = 'not_reached'
    final = None
    selected_ensemble = None
    failure = None

    def fit(recipe, where, split, timeout=900, full_fit=False, fit_iterations=None, stage_reserve=None):
        remaining = deadline-time.monotonic()-(stage_reserve if stage_reserve is not None else 5 if full_fit else reserve)
        if remaining < 5:
            return {'status': 'deadline', 'recipe': recipe, 'output_dir': str(where)}
        return worker(spec, recipe, where, split, min(timeout, remaining), full_fit=full_fit,
                      fit_iterations=fit_iterations, memory_limit=1536*2**20)

    def study(rows, where, full=False):
        stop = deadline-(900 if full else reserve)
        return optimizer(spec, train, hashes, rows, plan['augmentation'], where,
            lambda s, r, d, p, t: fit(r, d, p, t, stage_reserve=900 if full else reserve),
            min(stop, time.monotonic()+1800),
            trials=8, seed=137, sampler='tpe', worker_timeout=600)

    def load(record, expected_rows):
        cache = read_cache(spec, record, train)
        if not np.array_equal(cache['rows'], expected_rows):
            raise ValueError('Profile prediction row order differs from saved partition')
        for key in ['validation', 'test']:
            values = np.asarray(cache[key])
            if not np.isfinite(values).all():
                raise ValueError('Nonfinite profile predictions')
            if spec['kind'] == 'classification' and ((values < 0).any() or (values > 1).any()
                    or not np.allclose(values.sum(axis=1), 1, atol=1e-7, rtol=1e-7)):
                raise ValueError('Invalid profile probabilities')
        return cache

    try:
        for cut in range(2):
            tr, va, info = primary if cut == 0 else (make_time_split(spec, train, offset=1)
                if plan['adaptive'] else make_split(spec, train, hashes, seed=43))
            split = runs/('split.npz' if cut == 0 else 'confirmation_split.npz')
            if cut:
                np.savez(split, train=tr, validation=va)
                atomic_json(runs/'confirmation_split.json', info)
            control = fit(plan['control'], runs/f'control-{cut}', split)
            controls.append(control)
            journal(runs, 'profile_control', control, spec['metric'], 'fixed_complete_control')
            if control['status'] != 'ok':
                break
            checkpoint(control, output)
            control_cache = load(control, va)
            control_metrics = combine(spec, [control_cache], [1.])[0]
            control['metrics'] = control_metrics  # Source truth, not worker-reported scores.
            chosen = control
            candidate_metrics, cut_gate, reason = None, False, 'augmentation_disabled_or_prior_failure'
            if all_augmentation_valid:
                recipe = plan['augmentation']
                if plan['adaptive']:
                    recipe, report = study(tr, runs/f'inner-study-{cut}')
                    studies.append(report)
                    if report['status'] != 'ok':
                        all_augmentation_valid = False
                        reason = 'inner_study_'+report['status']
                if all_augmentation_valid:
                    augmentation = fit(recipe, runs/f'augmentation-{cut}', split, 600 if plan['adaptive'] else 900)
                    augmentations.append(augmentation)
                    journal(runs, 'profile_augmentation', augmentation, spec['metric'], 'fixed_marginal_candidate')
                    if augmentation['status'] == 'ok':
                        mixed = materialize(spec, [control_cache, load(augmentation, va)], [.9, .1],
                                            runs/f'profile-mixture-{cut}', sample, test)
                        support = None
                        if spec['kind'] == 'classification':
                            labels = train[spec['target']].astype(str).to_numpy()
                            support = {c: len(np.unique(np.asarray(hashes)[tr][labels[tr] == c])) for c in spec['classes']}
                        passed = paired_passes(spec, control_metrics, mixed['metrics'], support)
                        candidate_metrics, cut_gate = mixed['metrics'], passed
                        reason = 'passed' if passed else 'paired_gate_failed'
                        gates.append(passed)
                        all_augmentation_valid = passed
                        if passed:
                            chosen = mixed
                    else:
                        all_augmentation_valid = False
                        reason = 'augmentation_'+augmentation['status']
            chosen_records.append(chosen)
            scores.append({'cut': cut, 'control': control_metrics,
                           'candidate': candidate_metrics, 'augmentation_gate': cut_gate, 'reason': reason})
        phase_complete = len(controls) == 2 and all(r['status'] == 'ok' for r in controls)
        use_augmentation = (phase_complete and all_augmentation_valid and len(gates) == 2 and all(gates)
                            and len(augmentations) == 2 and all(r['status'] == 'ok' for r in augmentations))
        if not use_augmentation:
            chosen_records = controls if phase_complete else [r for r in controls if r['status'] == 'ok']
        if phase_complete:
            control_iterations = median_iterations(controls[0]['fit_iterations'], controls[1]['fit_iterations'])
            full_control = fit(plan['control'], runs/'full-control', runs/'split.npz', full_fit=True,
                               fit_iterations=control_iterations)
            if full_control['status'] == 'ok':
                checkpoint(full_control, output)
                full_records, weights = [full_control], [1.]
                if use_augmentation:
                    recipe = plan['augmentation']
                    if plan['adaptive']:
                        recipe, report = study(np.arange(len(train)), runs/'full-inner-study', full=True)
                        studies.append(report)
                        if report['status'] != 'ok':
                            raise RuntimeError('Full-training inner study unavailable')
                        iterations = study_iterations(report)
                    else:
                        iterations = median_iterations(augmentations[0]['fit_iterations'], augmentations[1]['fit_iterations'])
                    extra = fit(recipe, runs/'full-augmentation', runs/'split.npz', full_fit=True, fit_iterations=iterations)
                    if extra['status'] != 'ok':
                        raise RuntimeError('Full augmentation refit unavailable')
                    full_records.append(extra)
                    weights = [.9, .1]
                final = full_output(spec, full_records, weights, runs/'final-fit', sample, test)
                checkpoint(final, output)
                final_status = 'ok'
                if use_augmentation:
                    selected_ensemble = {'primary': chosen_records[0], 'confirmation': chosen_records[1],
                        'mean': float(np.mean([r['metrics'][spec['metric']] for r in chosen_records]))}
            else:
                final_status = full_control['status']
    except Exception as exc:
        failure = type(exc).__name__
        final_status = 'profile_incomplete'
    integrity = file_fingerprints(protected_paths) == fingerprints
    report = {'version': 'incumbent-mix-profile-v1', 'research_profile': 'incumbent_mix',
        'spec': spec, 'experiments': controls[:1]+augmentations[:1],
        'confirmations': controls[1:]+augmentations[1:], 'llm_calls': [], 'hpo_studies': studies,
        'profile_controls': controls, 'profile_augmentations': augmentations,
        'paired_gates': gates, 'profile_scores': scores, 'validation_complete': phase_complete,
        'augmentation_qualified': bool(selected_ensemble),
        'ensemble': selected_ensemble, 'selected_recipe': final['recipe'] if final else plan['control'],
        'best_validation': chosen_records[0]['metrics'] if chosen_records else None,
        'final_fit_iterations': final['fit_iterations'] if final else None,
        'final_fit_status': final_status, 'elapsed_seconds': round(time.monotonic()-started, 3),
        'submission_path': str(output), 'submission_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'integrity_ok': integrity, 'provenance_path': str(runs/'provenance.json'),
        'full_iteration_policy': 'control/ fixed class arm: median2; adaptive arm: selected full-study inner fit',
        'score_scope': 'Fixed learned profile on reused public cuts; not replay of the initial Qwen search or private/official score',
        **budget_metadata()}
    if failure:
        report['exception_type'] = failure
    atomic_json(runs/'report.json', report)
    if not integrity:
        raise RuntimeError('Protected profile source or inputs changed')
    return report
