"""Independent saved-artifact checks; no learner, gateway or solver imports.

audit_arm must not read verifier truth. audit_pair reads it only after the
coordinator has sealed both complete arms. No function launches a process.
"""
from copy import deepcopy
from itertools import combinations
from pathlib import Path
import hashlib
import json
import math
import time


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_time(deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError('Protected independent verification clock exhausted')


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_deployment(directory, fold, arm, task_files):
    expected = {**arm['compiled_sha256'], **fold['solver_inputs_sha256']}
    actual = {p.name for p in directory.iterdir() if p.is_file()}
    require(actual == set(expected), 'Unexpected solver-visible file/schema')
    require(set(fold['solver_inputs_sha256']) == set(task_files), 'Five-file task allowlist differs')
    for name, value in expected.items():
        require(digest(directory / name) == value, 'Deployed source/task input SHA differs')


def probabilities(path, classes, count, rows=None):
    import numpy as np
    with np.load(path, allow_pickle=False) as saved:
        order = saved['classes'].astype(str).tolist()
        require(len(order) == len(classes) and set(order) == set(classes), 'Probability class order/schema differs')
        value = saved['probabilities'][:, [order.index(c) for c in classes]].copy()
        if rows is not None:
            require('row_position' in saved and np.array_equal(saved['row_position'], rows), 'Validation probability row positions differ')
    require(value.shape == (count, len(classes)), 'Probability shape differs')
    require(np.isfinite(value).all() and (value >= 0).all() and (value <= 1).all(), 'Invalid/nonfinite probability')
    require(np.allclose(value.sum(axis=1), 1., rtol=0, atol=1e-6), 'Probability normalization differs')
    return value


def iteration_tree(value, expected=None):
    if expected is not None:
        require(value == expected, 'Refit selected iteration tree differs')
    if isinstance(value, list):
        require(bool(value), 'Empty iteration subtree')
        for child in value:
            iteration_tree(child)
    else:
        require(type(value) is int and 1 <= value <= 3000, 'Invalid scalar refit iteration')


def feature_children(recipe, spec):
    method = recipe['params']['feature_views']
    require(method in ['categorical_te_pair', 'categorical_te_capacity_pair'], 'Unknown feature-view subtype')
    categories = [c for c in spec['features'] if c in set(spec['categorical_features'])][:3]
    require(len(categories) >= 2, 'Feature-view schema eligibility lost')
    plain = deepcopy(recipe)
    plain['params'].pop('feature_views')
    encoded = deepcopy(plain)
    encoded['params'].update(target_encoding=True,
        target_encoding_groups=[list(p) for p in combinations(categories, 2)], target_encoding_smoothing=20.)
    plain['hypothesis'] = 'Fixed feature view: original categorical features'
    encoded['hypothesis'] = 'Fixed feature view: fitting-cross-fitted categorical statistics'
    children = [plain, encoded]
    if method == 'categorical_te_capacity_pair':
        require(recipe['params']['num_leaves'] == 63, 'Fixed subtype base capacity differs')
        extra = deepcopy(children)
        for child in extra:
            child['params']['num_leaves'] = 98
        children.extend(extra)
    return children, [.25] * 4 if len(children) == 4 else [.5] * 2


def contains_fixed(recipe):
    return (recipe.get('params', {}).get('feature_views') == 'categorical_te_capacity_pair'
            or any(contains_fixed(r) for r in recipe.get('components', [])))


def audit_final_tree(folder, recipe, selected_iterations, spec, sample, deadline):
    import numpy as np
    import pandas as pd
    check_time(deadline)
    result = load(folder / 'result.json')
    require(result.get('status') == 'ok' and result.get('full_fit') is True, 'Fresh full-fit node not successful')
    require(result.get('recipe') == recipe, 'Fresh full-fit recipe differs')
    iteration_tree(result.get('fit_iterations'), selected_iterations)
    classes = spec['classes']
    value = probabilities(folder / 'test_probabilities.npz', classes, len(sample))
    csv = pd.read_csv(folder / 'submission.csv')
    require(csv.columns.tolist() == sample.columns.tolist() and len(csv) == len(sample)
            and not csv.isna().any().any(), 'Full-fit node CSV schema/nonmissing failed')
    require(csv[spec['id']].equals(sample[spec['id']]), 'Full-fit node CSV ID/order failed')
    require(np.array_equal(csv[spec['output_columns'][0]].astype(str), np.asarray(classes)[value.argmax(axis=1)]), 'Full-fit node CSV argmax differs')
    params = recipe.get('params', {})
    if 'feature_views' in params:
        children, weights = feature_children(recipe, spec)
        view = result.get('feature_views', {})
        require(view.get('method') == params['feature_views'] and view.get('weights') == weights
                and view.get('iteration_tree') == selected_iterations, 'Feature-view metadata differs')
    elif recipe.get('engine') == 'ensemble':
        children = recipe['components']
        require(2 <= len(children) <= 3, 'Ordinary global ensemble width changed')
        weights = recipe['weights']
        require(len(weights) == len(children) and all(isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v) and v > 0 for v in weights), 'Global blend weights invalid')
        weights = np.asarray(weights, dtype=float) / sum(weights)
    else:
        children, weights = [], []
        if params.get('calibrate'):
            require(result.get('calibration_status') == 'inner_training_holdout_matching_iterations', 'Leaf inner calibration scope/matching iterations not proven')
        for record in result.get('data_policy_runs', []):
            selection = record.get('feature_selection') or {}
            require(not selection.get('teacher_fitted'), 'Unexpected selector fit')
        require(spec['target'] not in result.get('feature_names', []) and spec['id'] not in result.get('feature_names', []), 'Target/ID entered leaf features')
    leaves = 0
    if children:
        require(isinstance(selected_iterations, list) and len(selected_iterations) == len(children), 'Full child iteration tree shape differs')
        require(len(result.get('components', [])) == len(children), 'Full-fit child result count differs')
        mixture = np.zeros_like(value)
        for i, (child, weight) in enumerate(zip(children, weights)):
            child_value, count = audit_final_tree(folder / ('component-' + str(i)), child,
                selected_iterations[i], spec, sample, deadline)
            require(result['components'][i] == load(folder / ('component-' + str(i)) / 'result.json'), 'Embedded/actual full child result differs')
            mixture += weight * child_value
            leaves += count
        require(np.allclose(value, mixture, rtol=1e-12, atol=1e-12), 'Saved parent probability differs from actual child mixture')
    else:
        require(type(selected_iterations) is int, 'Leaf received a nested iteration list')
        leaves = 1
    return value, leaves


def audit_arm(directory, fold, arm, deadline):
    import numpy as np
    import pandas as pd
    check_time(deadline)
    runs = directory / 'automl_runs/run-v2'
    report_path = runs / 'report.json'
    report = load(report_path)
    spec = report['spec']
    require(report.get('integrity_ok') is True and report.get('final_fit_status') == 'ok', 'Complete agent integrity/refit failed')
    require(spec['kind'] == 'classification' and spec['metric'] == 'macro_f1'
            and not spec.get('text_features'), 'Task contract changed')
    require(report.get('llm_calls') == [] and not report.get('pipeline') and not report.get('hpo')
            and not report.get('feature_selection_top_k'), 'Unexpected planner/fourstage/HPO/selector factor')
    budget = report.get('run_budget') or {}
    require(budget.get('wall_limit_seconds') == 9900 and budget.get('gateway_call_limit') == 0
            and budget.get('gateway_calls_started') == 0 and budget.get('http_attempts_reported') == 0
            and budget.get('events') == [], 'Offline zero-cap controller provenance invalid')
    expected_inputs = {**arm['compiled_sha256'], **fold['solver_inputs_sha256']}
    for name, expected in expected_inputs.items():
        require(digest(directory / name) == expected, 'Runtime/task source differs after fitting')
    for role, value in spec['paths'].items():
        require(Path(value).resolve().parent == directory.resolve()
                and Path(value).name in fold['solver_inputs_sha256'], 'Report input path escapes deployed task')
    require(Path(spec['root']).resolve() == directory.resolve() and Path(spec['task_path']).resolve() == directory / 'task.md', 'Report task root differs')
    provenance = load(runs / 'provenance.json')['sha256']
    require(bool(provenance), 'Protected-source provenance missing')
    for label, expected in provenance.items():
        path = label.split(':', 1)[1] if label.startswith('source:') else spec['paths'].get(label[6:]) if label.startswith('input:') else spec['task_path'] if label == 'task' else None
        require(path is not None and Path(path).resolve().parent == directory.resolve()
                and digest(path) == expected, 'Protected provenance fingerprint does not reproduce')
    job = load(runs / 'final-fit/job.json')
    require(job.get('recipe') == report['selected_recipe'] and job.get('full_fit') is True
            and job.get('threads') == 2 and job.get('fit_iterations') == report['final_fit_iterations'], 'Actual final job differs from selected procedure')
    require(job.get('spec') == spec, 'Final full-fit task spec differs')
    sample = pd.read_csv(directory / 'sample_submission.csv')
    final_value, leaves = audit_final_tree(runs / 'final-fit', report['selected_recipe'],
        report['final_fit_iterations'], spec, sample, deadline)
    final_csv = directory / 'submission.csv'
    require(digest(final_csv) == report['submission_sha256']
            and digest(final_csv) == digest(runs / 'final-fit/submission.csv'), 'Final export does not match fresh full-fit CSV')
    experiments = report.get('experiments', [])
    require(len(experiments) <= 12 and len({r['experiment_index'] for r in experiments}) == len(experiments), 'Default search slot/identity limit differs')
    for record in experiments:
        require(record['experiment_index'] in range(12), 'Unexpected search slot')
        params = record['recipe'].get('params', {})
        require(params.get('generic_features', 'none') == 'none' and not params.get('feature_selection_top_k', 0)
                and not params.get('selector_importance_cache', False), 'Unexpected broad/selector/cache factor')
    check_time(deadline)
    return {'status': 'complete_source_refit_artifacts_verified_outer_unscored',
        'report_sha256': digest(report_path), 'final_csv_sha256': digest(final_csv),
        'final_probabilities_sha256': digest(runs / 'final-fit/test_probabilities.npz'),
        'actual_final_leaf_count': leaves, 'final_fit_iterations': report['final_fit_iterations'],
        'fixed_component_reached': any(contains_fixed(r['recipe']) for r in experiments),
        'fixed_component_selected': contains_fixed(report['selected_recipe']),
        'API_limit': 0, 'gateway_calls_source_controller_reported': 0,
        'independent_private_ledger_closed': None, 'outer_metrics': None,
        'boundary': 'No outer truth read; actual CLI/source/controller report proves offline cap0, not private-ledger independent closure'}

# Outer truth and pair/OOF metrics belong to the separately owned independent verifier.
