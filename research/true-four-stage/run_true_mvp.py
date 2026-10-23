"""Prepare by default; root-reviewed launch of the actual four-stage public MVP.

Fresh 10800-second common campaign, regression then classification. No historical
MVP artifact is reused. Contest runtime, validation and metrics stay unchanged.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import time
import zipfile

sys.dont_write_bytecode = True
RUNTIME_SHA = '88dac47a9a815b98b5d00c44e5650518f84db5197c9eac56b79fb1ce465c92a0'
HPO_HELPER_SHA = '8d4bd4212867787552b7785e8ec6d33a8025ca315f018c1d2d4c39616982d27a'
COMMON_SECONDS, COMMON_RESERVE, TASK_AUDIT_RESERVE = 10800, 120, 60


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            value.update(block)
    return value.hexdigest()


def write(path, value, exclusive=False):
    content = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    if exclusive:
        with Path(path).open('xb') as stream:
            stream.write(content)
    else:
        temporary = Path(path).with_name(Path(path).name + '.pending')
        temporary.write_bytes(content)
        os.replace(temporary, path)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def configure(path):
    global WORK, REPO, BUNDLE, OUTPUT
    WORK = Path(path).expanduser().resolve()
    REPO, BUNDLE = WORK / 'alfa-hack-automl', WORK / 'true-four-stage-launch-r1'
    OUTPUT = REPO / 'test-runs/tm1'
    if not (REPO / 'src/automl').is_dir():
        raise ValueError('Use --work-root pointing to the task work directory')


def relative(path):
    return Path(path).resolve().relative_to(WORK).as_posix()


def resolve(name):
    path = (WORK / name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to(WORK):
        raise ValueError('Manifest path escapes task work')
    return path


def libraries(preparing=False):
    hpo = WORK / 'hpo_campaign_coordinator.py' if preparing else BUNDLE / 'prior_ownership.py'
    observer = WORK / 'support_component_coordinator.py' if preparing else BUNDLE / 'ownership.py'
    if digest(hpo) != HPO_HELPER_SHA:
        raise ValueError('Reviewed predecessor/clock library differs')
    prior = module('_true_mvp_prior', hpo)
    prior.WORK = WORK
    owner = module('_true_mvp_owner', observer)
    owner.configure_work_root(WORK)
    return prior, owner


def paths_audit():
    examples = [OUTPUT / 'c/automl_runs/true4/inner-hpo/trial-07/component-1/validation_probabilities.npz',
                OUTPUT / 'c/automl_runs/true4/final-fit/component-0/component-1/submission.csv.tmp',
                OUTPUT / 'c/automl_runs/true4/ensemble-confirmation/validation_probabilities.npz']
    result = [{'path': relative(p), 'absolute_characters': len(str(p))} for p in examples]
    if os.name == 'nt' and max(x['absolute_characters'] for x in result) >= 260:
        raise ValueError('Known Windows artifact path reaches MAX_PATH')
    return result


def prepare():
    if BUNDLE.exists():
        raise FileExistsError('Preserve previous preparation; make a new explicit revision')
    prior, owner = libraries(preparing=True)
    gates = owner.technical_gates()  # Existing exact2e receipts, read only.
    queue = load(REPO / 'test-runs/2e/queue.json')
    builder = module('_true_mvp_builder', REPO / 'tools/build_submission.py')
    files = builder.build_files()
    compiled = {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}
    if compiled != queue['frozen_fingerprints']['compiled_files']:
        raise ValueError('Current runtime differs from passed2e source')
    task_inputs = []
    for kind, folder in [('regression', 'regression'), ('classification', 'multiclass')]:
        source = WORK / 'evaluation' / folder
        task_inputs.append({'kind': kind, 'source': relative(source), 'code': 'r' if kind == 'regression' else 'c',
            'files': {name: digest(source / name) for name in ['task.md', 'train.csv', 'test.csv', 'data_dictionary.csv', 'sample_submission.csv']}})
    BUNDLE.mkdir()
    for source, name in [(WORK / 'hpo_campaign_coordinator.py', 'prior_ownership.py'),
                         (WORK / 'support_component_coordinator.py', 'ownership.py')]:
        (BUNDLE / name).write_bytes(source.read_bytes())
    archive = BUNDLE / 'evaluator-source.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as packed:
        for name, content in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            packed.writestr(info, content)
    if digest(archive) != RUNTIME_SHA:
        raise ValueError('Expected exact88dac runtime archive')
    immutable = {relative(Path(path)): sha for path, sha in queue['frozen_fingerprints']['files'].items()}
    immutable.update(gates)
    for task in task_inputs:
        immutable.update({task['source'] + '/' + name: sha for name, sha in task['files'].items()})
    for path in BUNDLE.iterdir():
        if path.is_file():
            immutable[relative(path)] = digest(path)
    immutable['native2e-completion-ownership.json'] = digest(WORK / 'native2e-completion-ownership.json')
    manifest = {'status': 'prepared_not_launched', 'coordinator_sha256': digest(__file__),
        'archive_sha256': RUNTIME_SHA, 'compiled_sha256': compiled, 'immutable_files': immutable,
        'canonical_python_inventory': sorted(relative(p) for f in ['src', 'tools', 'tests'] for p in (REPO / f).rglob('*.py')),
        'tasks': task_inputs, 'task_order': ['regression', 'classification'],
        'predecessors': ['alfa-hack-automl/test-runs/2e/queue.json', 'alfa-hack-automl/test-runs/sc1/coordinator.json'],
        'mandatory_sc1_completion_ownership': 'sc1-completion-ownership.json',
        'limits': {'new_common_seconds': COMMON_SECONDS, 'common_export_verification_reserve_seconds': COMMON_RESERVE,
            'regression_parent_cap_seconds': 2400, 'classification_minimum_reserved_seconds': 7200,
            'classification_parent_max_seconds': 9960, 'task_verification_reserve_seconds': TASK_AUDIT_RESERVE,
            'solver_startup_cleanup_allowance_seconds': 30, 'worker_memory_gib': 1.5,
            'supervisor_tree_memory_gib': 2, 'threads': 2,
            'maximum_experiments': 14, 'maximum_planner_calls_including_initial_eda': 2,
            'gateway_limit_per_task_including_roles': 4, 'maximum_campaign_gateway_calls': 8,
            'maximum_http_attempts_per_gateway_call_from_frozen_source': 3, 'maximum_campaign_http_attempts': 24,
            'hpo_trials_including_anchor': 8, 'hpo_requested_budget_seconds': 900, 'catboost_top_k': 32},
        'solver_arguments': ['solution.py', 'task.md', '--four-stage', '--max-experiments', '14',
            '--max-planner-calls', '2', '--max-llm-calls', '4', '--hpo-trials', '8', '--hpo-budget', '900',
            '--feature-selection-top-k', '32', '--planner-mode', 'staged', '--run-name', 'true4'],
        'protected_originals': False, 'reasoning_factor_changed': False,
        'requested_model': 'qwen/qwen3.8-27b', 'reasoning_effort': 'off',
        'reused_exact_technical_gates': gates, 'windows_paths': paths_audit(),
        'start_unix': None, 'absolute_deadline_unix': None,
        'historical_mvp_reused': False, 'historical_mvp_clock_reset': False,
        'resume': 'No automatic resume/overwrite. A reviewed continuation must retain this new original deadline, source/inputs and all attempt API ledgers; reuse only a complete qualified task after fresh ownership checks.',
        'new_api_calls': 0, 'new_fits': 0, 'child_processes': 0, 'promotion': False,
        'root_review_before_launch': True}
    write(BUNDLE / 'manifest.json', manifest, exclusive=True)
    print(json.dumps({'status': manifest['status'], 'manifest_sha256': digest(BUNDLE / 'manifest.json'),
                      'archive_sha256': RUNTIME_SHA, 'deadline_assigned': False, 'child_processes': 0}))


def guard(manifest):
    if digest(__file__) != manifest['coordinator_sha256']:
        raise RuntimeError('Executing coordinator differs from reviewed bytes')
    inventory = sorted(relative(p) for f in ['src', 'tools', 'tests'] for p in (REPO / f).rglob('*.py'))
    if inventory != manifest['canonical_python_inventory']:
        raise RuntimeError('Canonical source inventory changed')
    for name, expected in manifest['immutable_files'].items():
        if digest(resolve(name)) != expected:
            raise RuntimeError('Frozen source/input/harness changed: ' + name)


def clock_check(deadline, utc_deadline):
    if abs((deadline - time.monotonic()) - (utc_deadline - time.time())) > 5:
        raise RuntimeError('Common UTC/monotonic clocks disagree')
    if time.monotonic() >= deadline:
        raise TimeoutError('Original new common deadline exhausted')


def audit_task(task, directory, manifest, supervision, audit_deadline):
    import numpy as np
    import pandas as pd
    runs = directory / 'automl_runs/true4'
    traces = list((directory / 'automl_runs').glob('run-budget-*/report.json'))
    ledgers = [load(p) for p in traces]
    api_complete = len(ledgers) == 1 and all(t.get('status') == 'completed' and t.get('usage_complete') is True for t in ledgers)
    known_calls = sum(t['gateway_calls_started'] for t in ledgers)
    api_receipt = {'gateway_calls': known_calls if api_complete else None,
        'gateway_calls_reported': known_calls, 'gateway_calls_upper_bound': 4,
        'usage_complete': api_complete, 'prompt_tokens_reported': sum(t.get('prompt_tokens_reported', 0) for t in ledgers),
        'completion_tokens_reported': sum(t.get('completion_tokens_reported', 0) for t in ledgers)}
    api_receipt['http_attempts_reported'] = sum(t.get('http_attempts_reported', 0) for t in ledgers)
    api_receipt['logical_call_limit_is_not_http_attempt_limit'] = True
    path = runs / 'report.json'
    if not path.exists():
        return {'qualified_four_stage': False, 'metrics': None, 'reason': 'missing_report', **api_receipt}
    report = load(path)
    errors = []
    pipeline = report.get('pipeline') or {}
    initial_path = runs / 'initial-data-assessment.json'
    initial = load(initial_path) if initial_path.exists() else {}
    assessment = initial.get('assessment') or {}
    context = initial.get('context') or {}
    if (pipeline.get('mode') != 'four_stage' or pipeline.get('initial_data_assessment_before_fitting') is not True or
            assessment.get('attempted') is not True or assessment.get('assessment_valid') is not True or
            assessment.get('call_status') != 'ok' or context.get('stage') != 'initial_data_assessment_before_any_model_fit' or
            context.get('feedback_read_first') != [] or context.get('best_recipe') is not None or
            supervision.get('initial_assessment_valid_at_first_worker') is not True or
            supervision.get('initial_assessment_sha256_at_first_worker') != (digest(initial_path) if initial_path.exists() else None)):
        errors.append('Initial LLM data assessment before fitting not proven')
    if pipeline.get('trusted_feature_family') != 'broad' or pipeline.get('maximum_added_broad_features') != 128 or pipeline.get('catboost_top_k') != 32:
        errors.append('Declared actual broad128/CatBoost32 stage differs')
    experiments = report.get('experiments') or []
    successful = [r for r in experiments if r.get('status') == 'ok']
    families = sorted({r['recipe']['engine'] for r in successful})
    if len(families) < 2:
        errors.append('Fewer than two successful student model families')
    if not experiments or any(r['recipe'].get('params', {}).get('generic_features') != 'broad' or
            r['recipe'].get('params', {}).get('feature_selection_top_k') != 32 for r in experiments if r['recipe']['engine'] != 'linear_text'):
        errors.append('Actual trusted broad+CatBoost32 coordinator recipes not proven')
    selectors, actual_results = [], []
    for result_path in sorted(runs.rglob('result.json')):
        if time.monotonic() >= audit_deadline:
            raise TimeoutError('Task verification reserve exhausted')
        result = load(result_path)
        if result.get('status') == 'ok':
            actual_results.append(result_path)
            for row in result.get('data_policy_runs', []):
                selection = row.get('feature_selection') or {}
                if selection.get('teacher_fitted'):
                    selectors.append(selection)
    if not selectors or any(r.get('status') != 'selected' or r.get('iterations') != 100 or
            not r.get('fitting_rows') or not r.get('input_columns') for r in selectors):
        errors.append('Actual fitted CatBoost selector receipts missing/invalid')
    original_features = len(report['spec']['features'])
    if selectors and not any(r['input_columns'] > original_features for r in selectors):
        errors.append('No actual teacher input had additional features')
    hpo = report.get('hpo') or {}
    hpo_path = runs / 'inner-hpo/hpo.json'
    actual_hpo = load(hpo_path) if hpo_path.exists() else {}
    if (hpo.get('status') != 'ok' or actual_hpo != hpo or hpo.get('maximum_trials') != 8 or
            hpo.get('sampler') != 'tpe' or hpo.get('seed') != 137 or not hpo.get('trials')):
        errors.append('Actual inner Optuna stage not successfully reached')
    inner_successes, failed_trials = 0, 0
    for trial in hpo.get('trials', []):
        if trial.get('objective_valid'):
            if trial.get('status') != 'ok' or isinstance(trial.get('value'), bool) or not isinstance(trial.get('value'), (int, float)) or not math.isfinite(trial['value']):
                errors.append('Invalid successful inner objective')
            inner_successes += 1
        else:
            failed_trials += 1
            if trial.get('value') is not None:
                errors.append('Failed inner objective was numeric')
    if not inner_successes:
        errors.append('No successful inner Optuna objective')
    if supervision.get('hpo_full_budget_observed') is not True:
        errors.append('Full initial900-second HPO allocation not conservatively proven')
    if hpo.get('split', {}).get('scope') != 'inside_outer_fitting_rows_only':
        errors.append('Inner fitting-only scope not recorded')
    if (runs / 'split.npz').exists() and (runs / 'inner-hpo/split.npz').exists():
        with np.load(runs / 'split.npz', allow_pickle=False) as split:
            fitting = split['train']
        with np.load(runs / 'inner-hpo/split.npz', allow_pickle=False) as split:
            inner_tr, inner_va = split['train'], split['validation']
        for rows in [fitting, inner_tr, inner_va]:
            if (rows.ndim != 1 or not len(rows) or not np.issubdtype(rows.dtype, np.integer) or
                    len(np.unique(rows)) != len(rows) or rows.min() < 0 or rows.max() >= report['spec']['n_train']):
                errors.append('Invalid actual fitting/inner row positions')
        if np.intersect1d(inner_tr, inner_va).size or not (set(inner_tr) | set(inner_va)) <= set(fitting):
            errors.append('Actual inner split escapes primary fitting rows')
    else:
        errors.append('Missing actual outer or inner partition artifact')
    for trial in hpo.get('trials', []):
        if not trial.get('objective_valid'):
            continue
        folder = runs / 'inner-hpo' / ('trial-' + str(trial['number']).zfill(2))
        if not (folder / 'job.json').exists() or not (folder / 'result.json').exists():
            errors.append('Successful inner trial lacks actual job/result artifact')
            continue
        actual_job, actual_result = load(folder / 'job.json'), load(folder / 'result.json')
        value = (actual_result.get('metrics') or {}).get(report['spec']['metric'])
        if (actual_job.get('recipe') != trial['recipe'] or actual_result.get('recipe') != trial['recipe'] or
                actual_job.get('full_fit') is not False or actual_job.get('threads') != 2 or
                actual_result.get('full_fit') is not False or actual_result.get('status') != 'ok' or
                Path(actual_job['split_path']).resolve() != (runs / 'inner-hpo/split.npz').resolve() or
                value != trial['value']):
            errors.append('Actual successful Optuna worker/objective differs')
    final_path, final_job = runs / 'final-fit/result.json', runs / 'final-fit/job.json'
    final = load(final_path) if final_path.exists() else {}
    job = load(final_job) if final_job.exists() else {}
    if (report.get('final_fit_status') != 'ok' or final.get('status') != 'ok' or final.get('full_fit') is not True or
            job.get('full_fit') is not True or job.get('threads') != 2 or report.get('integrity_ok') is not True):
        errors.append('Completed full refit/integrity not proven')
    sample = pd.read_csv(directory / 'sample_submission.csv')
    prediction_path = directory / 'submission.csv'
    if not prediction_path.exists():
        errors.append('Missing final submission CSV')
    else:
        prediction = pd.read_csv(prediction_path)
        spec = report['spec']
        if list(prediction) != list(sample) or len(prediction) != len(sample) or prediction.isna().any().any():
            errors.append('CSV schema/row/nonmissing contract failed')
        if spec.get('id') is not None and not prediction[spec['id']].equals(sample[spec['id']]):
            errors.append('CSV sample ID/order contract failed')
        if task['kind'] == 'regression' and not np.isfinite(prediction[spec['output_columns'][0]].to_numpy(dtype=float)).all():
            errors.append('Nonfinite regression predictions')
        if task['kind'] == 'classification' and not set(prediction[spec['output_columns'][0]].astype(str)) <= set(spec['classes']):
            errors.append('Unexpected output class')
        if digest(prediction_path) != report.get('submission_sha256'):
            errors.append('Final CSV fingerprint differs')
    for name, expected in task['files'].items():
        if digest(directory / name) != expected:
            raise RuntimeError('Copied pristine task input changed')
    for name, expected in manifest['compiled_sha256'].items():
        if digest(directory / name) != expected:
            raise RuntimeError('Copied contest runtime changed')
    if known_calls > 4 or not api_complete:
        errors.append('Closed complete shared API ledger missing or limit exceeded')
    response_models = sorted({c.get('response_model') for c in report.get('llm_calls', []) if c.get('response_model')})
    if any(c.get('reasoning_effort_requested') != 'off' for c in report.get('llm_calls', [])):
        errors.append('Actual reasoning request differs from fixed fast baseline')
    if supervision['status'] != 'ok' or supervision.get('cleanup_confirmed') is not True:
        errors.append('Solver lifecycle/ownership incomplete')
    # Independently reproduce the selected primary/confirmation metrics. These
    # are reused research folds, never an unbiased or official score.
    diagnostics = []
    ensemble = report.get('ensemble') or {}
    primary = ensemble.get('primary') or next((r for r in experiments if r.get('recipe') == report.get('selected_recipe')), None)
    confirmation = ensemble.get('confirmation') or next((r for r in report.get('confirmations', [])
        if r.get('recipe') == report.get('selected_recipe') and r.get('status') == 'ok'), None)
    train = pd.read_csv(directory / 'train.csv')
    for label, record, split_path in [('primary', primary, runs / 'split.npz'),
                                      ('confirmation', confirmation, runs / 'confirmation_split.npz')]:
        if not record or not split_path.exists():
            errors.append('Selected primary/confirmation evidence missing: ' + label)
            continue
        folder = Path(record['submission']).resolve().parent
        if not folder.is_relative_to(directory):
            raise RuntimeError('Selected prediction artifact escapes owned task')
        with np.load(split_path, allow_pickle=False) as saved:
            fit_rows, val_rows = saved['train'], saved['validation']
        frame = pd.read_csv(folder / 'validation_predictions.csv')
        if not np.array_equal(frame.row_position, val_rows):
            raise RuntimeError('Selected validation row order differs')
        truth = train[report['spec']['target']].iloc[val_rows].to_numpy()
        metric = report['spec']['metric']
        if task['kind'] == 'regression':
            predicted = frame.y_pred.to_numpy(dtype=float)
            if not np.isfinite(predicted).all() or not np.allclose(frame.y_true.to_numpy(dtype=float), truth.astype(float), atol=1e-12, rtol=0):
                raise RuntimeError('Selected regression truth/predictions differ')
            value = float(np.sqrt(np.mean((truth.astype(float) - predicted)**2)))
            diagnostic = {'split': label, 'metrics': {'rmse': value}}
        else:
            classes = list(report['spec']['classes'])
            with np.load(folder / 'validation_probabilities.npz', allow_pickle=False) as saved:
                order = list(saved['classes'].astype(str))
                if set(order) != set(classes) or len(order) != len(classes) or not np.array_equal(saved['row_position'], val_rows):
                    raise RuntimeError('Selected probability classes/rows differ')
                probabilities = saved['probabilities'][:, [order.index(c) for c in classes]]
            if (probabilities.shape != (len(val_rows), len(classes)) or not np.isfinite(probabilities).all() or
                    (probabilities < 0).any() or (probabilities > 1).any() or not np.allclose(probabilities.sum(axis=1), 1., atol=1e-6)):
                raise RuntimeError('Selected validation probabilities invalid')
            predicted = np.asarray(classes)[probabilities.argmax(axis=1)]
            truth = truth.astype(str)
            if not np.array_equal(frame.y_true.astype(str), truth) or not np.array_equal(frame.y_pred.astype(str), predicted):
                raise RuntimeError('Selected class truth/predictions differ')
            per_class = {}
            for c in classes:
                actual, guess = truth == c, predicted == c
                denominator = int(actual.sum() + guess.sum())
                per_class[c] = float(2 * np.sum(actual & guess) / denominator) if denominator else 0.
            value = float(np.mean(list(per_class.values())))
            hashes = pd.util.hash_pandas_object(train[report['spec']['features']], index=False).to_numpy(dtype='uint64')
            if np.intersect1d(hashes[fit_rows], hashes[val_rows]).size:
                raise RuntimeError('Selected outer feature groups overlap')
            fitting_truth = train[report['spec']['target']].iloc[fit_rows].astype(str).to_numpy()
            support = {c: len(np.unique(hashes[fit_rows][fitting_truth == c])) for c in classes}
            rarest = min(classes, key=lambda c: support[c])
            diagnostic = {'split': label, 'metrics': {'macro_f1': value}, 'per_class_f1': per_class,
                'independent_fitting_groups': support, 'rarest_class': rarest,
                'ex_rarest_macro_f1': float(np.mean([per_class[c] for c in classes if c != rarest])),
                'supported_classes_at_least100groups': [c for c in classes if support[c] >= 100]}
        reported = (record.get('metrics') or {}).get(metric)
        if isinstance(reported, bool) or not isinstance(reported, (int, float)) or not math.isclose(value, reported, rel_tol=1e-10, abs_tol=1e-10):
            raise RuntimeError('Selected primary/confirmation metric does not independently reproduce')
        diagnostics.append(diagnostic)
        if time.monotonic() >= audit_deadline:
            raise TimeoutError('Selected metric verification exceeded protected reserve')
    qualified = not errors
    return {'qualified_four_stage': qualified, 'errors': errors, 'metrics': report.get('best_validation') if qualified else None,
        'scope': 'Reused public search/confirmation metrics; no private/official score',
        'successful_student_families': families, 'teacher_selection_calls': len(selectors),
        'maximum_teacher_input_columns': max((r['input_columns'] for r in selectors), default=0),
        'retained_broad_columns_per_selection': [sum(str(c).startswith('__broad_') for c in r.get('selected_columns', [])) for r in selectors],
        'successful_inner_trials': inner_successes, 'failed_inner_trials': failed_trials,
        'hpo_requested_trials': 8, 'hpo_requested_budget_seconds': 900, 'actual_hpo_seconds': hpo.get('seconds'),
        'hpo_full_requested_allocation_conservatively_observed': supervision.get('hpo_full_budget_observed', False),
        **api_receipt, 'requested_model': manifest['requested_model'], 'reasoning_effort': 'off',
        'reported_response_models': response_models, 'model_architecture_independently_verified': False,
        'reasoning_tokens_reported_per_planner_call': [c.get('reasoning_tokens_reported') for c in report.get('llm_calls', [])],
        'independently_recomputed_selected_metrics': diagnostics,
        'report_sha256': digest(path), 'submission_sha256': digest(prediction_path) if prediction_path.exists() else None,
        'promotion': False}


def supervise(task, directory, manifest, cap, deadline, utc_deadline, save_campaign):
    import psutil
    _, owner = libraries()
    processes = module('_true_mvp_processes', REPO / 'src/automl/infrastructure/processes.py')
    tick = time.monotonic()
    if cap + COMMON_RESERVE > deadline - tick:
        raise TimeoutError('Copied-input time consumed the protected common reserve')
    solver_seconds = int(cap - TASK_AUDIT_RESERVE - 30)
    process_deadline = tick + cap - TASK_AUDIT_RESERVE
    command = [sys.executable, '-u', *manifest['solver_arguments'], '--time-budget', str(solver_seconds)]
    env = os.environ.copy()  # Authorized API exists only in environment; never argv/manifest/logged env.
    env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1', AUTOML_THREADS='2')
    env.update(OPENAI_MODEL=manifest['requested_model'], AUTOML_REASONING_EFFORT=manifest['reasoning_effort'])
    for name in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
        env[name] = '2'
    for name in ['tmp', 'mpl']:
        (directory / name).mkdir()
    env.update(TMPDIR=str(directory / 'tmp'), MPLCONFIGDIR=str(directory / 'mpl'))
    result = {'kind': task['kind'], 'status': 'starting', 'allocated_parent_seconds': cap,
        'solver_budget_seconds': solver_seconds, 'start_monotonic': tick, 'start_unix': time.time(),
        'cleanup_confirmed': False, 'observed_worker_roots': [], 'initial_assessment_seen_at_first_worker': None}
    receipt = directory / 'supervisor.json'
    write(receipt, result, exclusive=True)
    observer = owner.StrictOwnedObserver()
    child, tree, verified = None, None, False
    last_guard, last_heartbeat = tick, tick
    try:
        clock_check(deadline, utc_deadline)
        if process_deadline - time.monotonic() < solver_seconds:
            raise TimeoutError('Prelaunch work consumed the protected task allocation')
        with (directory / 'process.log').open('x', encoding='utf-8') as log:
            child = subprocess.Popen(command, cwd=directory, env=env, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            fresh = psutil.Process(child.pid)
            identity = fresh.pid, fresh.create_time()
            result['owned_root'] = {'pid': identity[0], 'create_time': identity[1]}
            observer.remember([identity])
            tree = processes.ProcessTree(child)
            observer.remember(tree.members)
            verified = identity in tree.members
            if not verified:
                raise RuntimeError('Exact solver root was not observed')
            result['status'] = 'running'
            write(receipt, result)
            while child.poll() is None:
                live = observer.observe()
                tree.members.update(live)
                if observer.denials:
                    raise RuntimeError('Owned identity/descendant observation denied')
                total = psutil.Process().memory_info().rss
                active_worker_jobs = set()
                for key, process in live.items():
                    try:
                        current = psutil.Process(key[0])
                        if current.create_time() != key[1]:
                            continue
                        total += current.memory_info().rss
                        argv = current.cmdline()  # Only exact owned descendants; never persist argv.
                        if not any(Path(part).name in {'automl_worker.py', 'agent_worker.py'} for part in argv):
                            continue
                        job_path = Path(argv[-1]).resolve()
                        if not job_path.is_relative_to(directory) or job_path.name != 'job.json':
                            raise RuntimeError('Owned worker has an unexpected job path')
                        active_worker_jobs.add(str(job_path))
                        if key not in {(r['pid'], r['create_time']) for r in result['observed_worker_roots']}:
                            job = load(job_path)
                            if job.get('threads') != 2:
                                raise RuntimeError('Actual worker thread limit differs')
                            result['observed_worker_roots'].append({'pid': key[0], 'create_time': key[1],
                                'job': relative(job_path), 'observed_monotonic': time.monotonic(), 'full_fit': job.get('full_fit')})
                            initial = directory / 'automl_runs/true4/initial-data-assessment.json'
                            if result['initial_assessment_seen_at_first_worker'] is None:
                                result['initial_assessment_seen_at_first_worker'] = initial.exists()
                                result['initial_assessment_sha256_at_first_worker'] = digest(initial) if initial.exists() else None
                                first_assessment = load(initial).get('assessment', {}) if initial.exists() else {}
                                result['initial_assessment_valid_at_first_worker'] = (first_assessment.get('assessment_valid') is True and first_assessment.get('call_status') == 'ok')
                            if '/inner-hpo/' in job_path.as_posix() and 'hpo_first_worker_remaining_lower_bound_seconds' not in result:
                                remaining = tick + solver_seconds - time.monotonic()
                                reserve = min(1200, max(60, solver_seconds * .2))
                                result['hpo_first_worker_remaining_lower_bound_seconds'] = remaining
                                result['hpo_full_budget_observed'] = remaining >= reserve + 930
                        worker_rss = current.memory_info().rss
                        for descendant in current.children(recursive=True):
                            fresh = psutil.Process(descendant.pid)
                            created = fresh.create_time()
                            if created != descendant.create_time():
                                continue
                            observer.remember([(fresh.pid, created)])
                            worker_rss += fresh.memory_info().rss
                        if worker_rss > int(1.5 * 2**30):
                            raise MemoryError('Owned worker subtree exceeds1.5GiB')
                    except psutil.NoSuchProcess:
                        continue
                    except psutil.AccessDenied:
                        observer.denied(key[0], key[1], 'worker_memory_or_role', 'AccessDenied')
                        raise RuntimeError('Owned worker role/memory observation denied') from None
                # Windows venv redirector + actual Python share one job path;
                # distinct simultaneously live jobs would violate serial fits.
                result['maximum_observed_concurrent_worker_jobs'] = max(result.get('maximum_observed_concurrent_worker_jobs', 0), len(active_worker_jobs))
                if len(active_worker_jobs) > 1:
                    raise RuntimeError('More than one actual model worker job is live')
                if total > 2 * 2**30:
                    raise MemoryError('Parent plus owned process tree exceeds2GiB')
                clock_check(deadline, utc_deadline)
                if time.monotonic() >= process_deadline:
                    raise TimeoutError('Task process allocation exhausted; preserve verification reserve')
                if time.monotonic() - last_guard >= 30:
                    guard(manifest)
                    last_guard = time.monotonic()
                if time.monotonic() - last_heartbeat >= 2:
                    result.update(heartbeat_unix=time.time(), owned_process_identities=[{'pid': p, 'create_time': c} for p, c in sorted(observer.seen)])
                    write(receipt, result)
                    save_campaign()
                    last_heartbeat = time.monotonic()
                time.sleep(.1)
            result.update(status='ok' if child.returncode == 0 else 'failed', exit_code=child.returncode)
    except (MemoryError, TimeoutError) as exc:
        result.update(status=type(exc).__name__, exception_type=type(exc).__name__)
    except BaseException as exc:
        result.update(status='stopped', exception_type=type(exc).__name__)
        raise
    finally:
        result.update(owner.cleanup_owned(child, tree, observer, verified, processes.ProcessTree))
        result.update(end_monotonic=time.monotonic(), end_unix=time.time(), seconds=time.monotonic() - tick)
        write(receipt, result)
    if not result['cleanup_confirmed']:
        raise RuntimeError('Owned solver/worker cleanup unconfirmed; stop campaign')
    guard(manifest)
    result['proof'] = audit_task(task, directory, manifest, result, min(tick + cap, deadline - COMMON_RESERVE))
    clock_check(deadline, utc_deadline)
    write(directory / 'four-stage-proof.json', result['proof'], exclusive=True)
    result['seconds_including_verification'] = time.monotonic() - tick
    if result['seconds_including_verification'] > cap:
        raise TimeoutError('Task verification exceeded its reserved cap')
    write(receipt, result)
    return result


def launch(args):
    import psutil
    path = BUNDLE / 'manifest.json'
    if not args.manifest_sha256 or digest(path) != args.manifest_sha256:
        raise ValueError('Explicit root-reviewed manifest SHA required')
    utc, tick = time.time(), time.monotonic()
    if args.deadline_unix is None or not math.isfinite(args.deadline_unix):
        raise ValueError('Root must assign a fresh finite absolute common deadline')
    remaining = args.deadline_unix - utc
    if not 10700 <= remaining <= COMMON_SECONDS:
        raise ValueError('Fresh common deadline must leave10700..10800seconds; no old-MVP clock reuse')
    deadline = tick + remaining
    manifest = load(path)
    guard(manifest)
    paths_audit()
    prior, owner = libraries()
    predecessor = prior.predecessor_check(manifest)
    lock_module = module('_true_mvp_lock', REPO / 'tools/research_lock.py')
    with lock_module.ResearchLock(REPO / 'test-runs/.owned-research.lock') as lock:
        lock.write_identity({'pid': os.getpid(), 'create_time': psutil.Process().create_time()})
        predecessor = prior.predecessor_check(manifest)
        owner.technical_gates()
        guard(manifest)
        if OUTPUT.exists():
            raise FileExistsError('Preserve all prior attempts; automatic resume/overwrite forbidden')
        if not os.environ.get('OPENAI_API_KEY') or os.environ.get('OPENAI_BASE_URL', '').rstrip('/') != 'https://changellenge.up.railway.app/v1':
            raise ValueError('Authorized organizer API environment is required; never pass credentials in argv')
        OUTPUT.mkdir()
        report = {'status': 'running', 'manifest_sha256': args.manifest_sha256, 'source_archive_sha256': RUNTIME_SHA,
            'start_unix': utc, 'start_monotonic': tick, 'absolute_deadline_unix': args.deadline_unix,
            'common_deadline_monotonic': deadline, 'new_common_limit_seconds': COMMON_SECONDS,
            'owned_root': {'pid': os.getpid(), 'create_time': psutil.Process().create_time()},
            'predecessor_terminal_proof': predecessor, 'tasks': [], 'cleanup_confirmed': False,
            'source_unchanged': False, 'historical_mvp_reused': False, 'historical_clock_reset': False,
            'promotion': False, 'windows_awake_requested': prior.scoped_awake(True)}
        def save():
            write(OUTPUT / 'campaign.json', report)
        def interrupted(signum, frame):
            raise SystemExit(128 + signum)
        previous = {sig: signal.signal(sig, interrupted) for sig in [signal.SIGINT, signal.SIGTERM]}
        save()
        try:
            with zipfile.ZipFile(BUNDLE / 'evaluator-source.zip') as archive:
                files = {name: archive.read(name) for name in archive.namelist()}
            for index, task in enumerate(manifest['tasks']):
                guard(manifest)
                clock_check(deadline, args.deadline_unix)
                remaining = deadline - time.monotonic()
                if index == 0:
                    if remaining < 2400 + 7200 + COMMON_RESERVE:
                        raise TimeoutError('Cannot preserve classification allocation')
                    cap = 2400
                else:
                    cap = min(9960, int(remaining - COMMON_RESERVE))
                    if cap < 7200:
                        raise TimeoutError('Protected classification allocation unavailable')
                directory = OUTPUT / task['code']
                directory.mkdir()
                for name, data in files.items():
                    (directory / name).write_bytes(data)
                for name in task['files']:
                    shutil.copyfile(resolve(task['source']) / name, directory / name)
                remaining = deadline - time.monotonic()
                if index == 0:
                    if remaining < 2400 + 7200 + COMMON_RESERVE:
                        raise TimeoutError('Input copying consumed the classification reserve')
                    cap = 2400
                else:
                    cap = min(9960, int(remaining - COMMON_RESERVE - 1))
                    if cap < 7200:
                        raise TimeoutError('Input copying consumed the classification allocation')
                report['current_task'] = task['kind']
                save()
                result = supervise(task, directory, manifest, cap, deadline, args.deadline_unix, save)
                report['tasks'].append(result)
                save()
            calls_reported = sum(t.get('proof', {}).get('gateway_calls_reported', 0) for t in report['tasks'])
            calls_complete = all(t.get('proof', {}).get('usage_complete') is True for t in report['tasks'])
            complete = len(report['tasks']) == 2 and all(t.get('proof', {}).get('qualified_four_stage') for t in report['tasks'])
            if calls_reported > 8:
                raise RuntimeError('Aggregate campaign API limit exceeded')
            clock_check(deadline, args.deadline_unix)
            report.update(status='completed_qualified_four_stage_mvp' if complete else 'completed_unqualified_four_stage_mvp',
                actual_gateway_calls=calls_reported if calls_complete else None,
                gateway_calls_reported=calls_reported, gateway_calls_upper_bound=8,
                api_usage_complete=calls_complete, qualified_four_stage_both_tasks=complete)
        except BaseException as exc:
            report.update(status='stopped', exception_type=type(exc).__name__, qualified_four_stage_both_tasks=False)
            raise
        finally:
            try:
                receipts = [load(p) for p in OUTPUT.glob('*/supervisor.json')]
                report['cleanup_confirmed'] = bool(receipts) and all(r.get('cleanup_confirmed') is True for r in receipts)
                guard(manifest)
                report['source_unchanged'] = True
            except BaseException as exc:
                report.update(status='stopped', final_integrity_exception_type=type(exc).__name__, source_unchanged=False)
                raise
            finally:
                report.update(finished_unix=time.time(), finished_monotonic=time.monotonic(),
                    elapsed_common_seconds=time.monotonic() - tick, windows_awake_released=prior.scoped_awake(False))
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
                save()
        if report['status'] != 'completed_qualified_four_stage_mvp' or not report['cleanup_confirmed']:
            raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--launch', action='store_true')
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--deadline-unix', type=float)
    args = parser.parse_args()
    configure(args.work_root)
    if args.launch:
        launch(args)
    else:
        if args.manifest_sha256 is not None or args.deadline_unix is not None:
            parser.error('Deadline/reviewed SHA belong only to a separately reviewed --launch')
        prepare()


if __name__ == '__main__':
    main()
