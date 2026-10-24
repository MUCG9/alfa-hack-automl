"""Independent saved-artifact evaluator for a NEW prospective four-stage MVP.

Reuses tm1's manual NumPy/Pandas metric/CSV/recursive checks. No sklearn, model,
runtime, network or process imports/calls are needed. The existing parent owns
time/memory/terminal-process guards; this file adds no audit tripwire.
"""
from copy import deepcopy
from itertools import combinations
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import math
import time
import zipfile

import numpy as np
import pandas as pd

WORK = Path(__file__).resolve().parents[1]
REPO = WORK / 'alfa-hack-automl'
ROOT = None
RUN_NAME = 'repair4'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            result.update(block)
    return result.hexdigest()


def close(a, b):
    return (not isinstance(b, bool) and isinstance(b, (int, float))
            and math.isfinite(b) and math.isclose(a, b, abs_tol=1e-10, rel_tol=1e-10))


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def index_sha(tr, va):
    return hashlib.sha256(tr.astype('<i8').tobytes()+va.astype('<i8').tobytes()).hexdigest()


def split(path, n):
    with np.load(path, allow_pickle=False) as saved:
        tr, va = saved['train'].copy(), saved['validation'].copy()
    for rows in [tr, va]:
        assert rows.ndim == 1 and rows.dtype.kind in 'iu' and len(rows)
        assert rows.min() >= 0 and rows.max() < n and len(np.unique(rows)) == len(rows)
    assert not np.intersect1d(tr, va).size
    return tr, va


def f1(truth, prediction, classes):
    mapping = {name: i for i, name in enumerate(classes)}
    assert set(truth) <= set(classes) and set(prediction) <= set(classes)
    counts = np.zeros((len(classes), len(classes)), dtype=np.int64)
    np.add.at(counts, ([mapping[v] for v in truth], [mapping[v] for v in prediction]), 1)
    return f1_counts(counts, classes)


def f1_counts(counts, classes):
    denominator = counts.sum(axis=0)+counts.sum(axis=1)
    values = np.divide(2*np.diag(counts), denominator,
        out=np.zeros(len(classes)), where=denominator > 0)
    return float(values.mean()), dict(zip(classes, map(float, values)))


def probability(path, positions, classes):
    with np.load(path, allow_pickle=False) as saved:
        order = saved['classes'].astype(str).tolist()
        values = saved['probabilities'].copy()
        if positions is not None:
            assert np.array_equal(saved['row_position'], positions)
    assert len(order) == len(set(order)) == len(classes) and set(order) == set(classes)
    assert values.ndim == 2 and values.shape[1] == len(classes) and np.isfinite(values).all()
    if positions is not None:
        assert len(values) == len(positions)
    assert (values >= 0).all() and (values <= 1).all()
    assert np.allclose(values.sum(axis=1), 1., rtol=1e-10, atol=1e-10)
    return values[:, [order.index(c) for c in classes]]


def selected_records(report):
    selected = report['selected_recipe']
    if report.get('ensemble'):
        a, b = report['ensemble']['primary'], report['ensemble']['confirmation']
        assert a['recipe'] == b['recipe'] == selected
        return {'primary': a, 'confirmation': b}
    if report.get('protected_control_recipe') == selected:
        result = report['protected_control']
        assert set(result) == {'primary', 'confirmation'}
        assert all(r['recipe'] == selected for r in result.values())
        return result
    result = {}
    for phase, field in [('primary', 'experiments'), ('confirmation', 'confirmations')]:
        found = [r for r in report.get(field, []) if r.get('status') == 'ok' and r['recipe'] == selected]
        assert len(found) == 1, 'The selected recipe must identify one successful outcome per cut'
        result[phase] = found[0]
    return result


def child_feature_views(recipe, spec):
    plain = deepcopy(recipe)
    plain['params'].pop('feature_views')
    encoded = deepcopy(plain)
    categorical = [c for c in spec['features'] if c in set(spec['categorical_features'])][:3]
    encoded['params'].update(target_encoding=True,
        target_encoding_groups=[list(v) for v in combinations(categorical, 2)],
        target_encoding_smoothing=20.)
    plain['hypothesis'] = 'Fixed feature view: original categorical features'
    encoded['hypothesis'] = 'Fixed feature view: fitting-cross-fitted categorical statistics'
    return [plain, encoded]


def value_output_contract(spec, train, test, sample):
    """Canonical parser enum: one-column MacroF1/RMSE predictions use value."""
    assert spec['kind'] in {'classification', 'regression'}
    assert spec['metric'] == ('macro_f1' if spec['kind'] == 'classification' else 'rmse')
    assert spec.get('prediction_type') == 'value', 'Canonical prediction_type must be value'
    assert spec.get('output_columns') == [spec['target']]
    assert spec['target'] in train and spec['target'] not in test
    assert spec['target'] not in spec['features'] and spec.get('id') not in spec['features']
    assert len(spec['features']) == len(set(spec['features']))
    assert all(name in train and name in test for name in spec['features'])
    assert len(train) == spec['n_train'] and len(test) == spec['n_test'] == len(sample)
    assert not train[spec['target']].isna().any()
    assert list(sample) == ([spec['id']] if spec.get('id') is not None else []) + [spec['target']]
    positions = np.asarray(spec.get('sample_test_positions', np.arange(len(test))))
    assert positions.ndim == 1 and positions.dtype.kind in 'iu' and len(positions) == len(test)
    assert np.array_equal(np.sort(positions), np.arange(len(test))), 'Sample positions must be a permutation'
    if spec.get('id') is not None:
        assert spec['id'] in test and not test[spec['id']].isna().any() and not sample[spec['id']].isna().any()
        assert test[spec['id']].iloc[positions].reset_index(drop=True).equals(sample[spec['id']].reset_index(drop=True))
    if spec['kind'] == 'classification':
        classes = spec.get('classes')
        assert isinstance(classes, list) and classes and all(isinstance(c, str) for c in classes)
        assert classes == sorted(set(train[spec['target']].astype(str)))
    else:
        assert np.isfinite(pd.to_numeric(train[spec['target']], errors='raise').to_numpy(dtype=float)).all()
    return positions


def median_iterations(first, second):
    if isinstance(first, list) or isinstance(second, list):
        assert isinstance(first, list) and isinstance(second, list) and len(first) == len(second)
        return [median_iterations(a, b) for a, b in zip(first, second)]
    assert type(first) is int and type(second) is int and 1 <= first <= 3000 and 1 <= second <= 3000
    return max(30, int(np.median([first, second])))


def learner_families(recipe):
    if recipe['engine'] == 'ensemble':
        return set().union(*(learner_families(child) for child in recipe['components']))
    return {recipe['engine']}


def matched_control_comparison(cuts, control, kind):
    rows = []
    for phase in ['primary', 'confirmation']:
        actual, reference = cuts[phase], control[phase]
        assert actual['positions_sha256'] == reference['positions_sha256']
        delta = actual['value'] - reference['value']
        row = {'phase': phase, 'current': actual['value'], 'protected_control': reference['value'],
               'delta_current_minus_control': delta,
               'primary_improves': delta > 0 if kind == 'classification' else delta < 0}
        if kind == 'classification':
            assert actual['independent_fitting_groups'] == reference['independent_fitting_groups']
            assert actual['rarest_fitting_class'] == reference['rarest_fitting_class']
            support, rarest = actual['independent_fitting_groups'], actual['rarest_fitting_class']
            deltas = {c: actual['per_class_f1'][c] - reference['per_class_f1'][c] for c in support}
            losses = {c: value for c, value in deltas.items() if support[c] >= 100 and value < -.01-1e-12}
            ex_rarest = float(np.mean([v for c, v in deltas.items() if c != rarest]))
            row.update(per_class_f1_delta=deltas, supported_class_losses_over_001=losses,
                       ex_rarest_macro_f1_delta=ex_rarest,
                       all_class_gates_passed=row['primary_improves'] and not losses and ex_rarest > 0)
        rows.append(row)
    return {'cuts': rows, 'each_cut_primary_gate_passed': all(r['primary_improves'] for r in rows),
            'class_each_cut_gate_passed': all(r.get('all_class_gates_passed', True) for r in rows),
            'matched_saved_primary_and_confirmation_independently_recomputed': True,
            'fresh_protected_control_full_refit': False,
            'scope': 'Exact preserved control recipe rerun on the same two fitting/validation partitions; final refit audited only for the selected procedure'}


class TaskVerifier:
    def __init__(self, directory, report, train, test, sample):
        self.directory, self.report = directory, report
        self.spec, self.train, self.test, self.sample = report['spec'], train, test, sample
        self.classes, self.records = list(self.spec.get('classes') or []), {}
        self.sample_positions = value_output_contract(self.spec, train, test, sample)
        self.hashes = pd.util.hash_pandas_object(train[self.spec['features']], index=False).to_numpy(dtype='uint64')

    def folder(self, record):
        path = Path(record.get('output_dir') or Path(record['submission']).parent).resolve()
        assert path.is_relative_to(self.directory)
        return path

    def verify(self, record, partition, phase, full=False, expected_recipe=None):
        folder = self.folder(record)
        key = (str(folder), phase, full)
        if key in self.records:
            return self.records[key]
        recipe = record['recipe']
        if expected_recipe is not None:
            assert recipe == expected_recipe
        assert record['status'] == 'ok'
        stored = load(folder / 'result.json')
        assert stored['status'] == 'ok' and stored['recipe'] == recipe and stored['full_fit'] is full
        assert stored['fit_iterations'] == record['fit_iterations']
        job_path = folder / 'job.json'
        if job_path.exists():
            job = load(job_path)
            assert job['spec'] == self.spec and job['recipe'] == recipe and job['threads'] == 2
            assert job['full_fit'] is full and Path(job['output_dir']).resolve() == folder
            assert Path(job['split_path']).resolve() == partition.resolve()
            if full:
                assert job.get('fit_iterations') == stored['fit_iterations']
        elif stored.get('training_reused') is True:
            assert recipe['engine'] == 'ensemble' and not full
        else:
            # Recursive leaf calls write their result and probability files,
            # while the invoking top-level job carries the dispatch contract.
            assert expected_recipe is not None
        tr, va = split(partition, len(self.train))
        prediction = pd.read_csv(folder / 'submission.csv', converters={self.spec['id']: str})
        assert list(prediction) == list(self.sample) and len(prediction) == len(self.sample)
        assert not prediction.isna().any().any()
        if self.spec.get('id') is not None:
            assert prediction[self.spec['id']].equals(self.sample[self.spec['id']])
        output = self.spec['output_columns'][0]
        returned = {'folder': folder, 'recipe': recipe, 'test': None, 'validation': None,
            'value': None, 'per_class_f1': None}
        if self.spec['kind'] == 'classification':
            test_probability = probability(folder / 'test_probabilities.npz', None, self.classes)
            assert len(test_probability) == len(self.test)
            positions = self.sample_positions
            assert np.array_equal(prediction[output].astype(str),
                np.asarray(self.classes)[test_probability.argmax(axis=1)][positions])
            returned['test'] = test_probability
        else:
            returned['test'] = prediction[output].to_numpy(dtype=float)
            assert np.isfinite(returned['test']).all()
        if not full:
            frame = pd.read_csv(folder / 'validation_predictions.csv')
            assert frame.row_position.dtype.kind in 'iu' and np.array_equal(frame.row_position, va)
            truth = self.train[self.spec['target']].iloc[va].to_numpy()
            if self.spec['kind'] == 'classification':
                val_probability = probability(folder / 'validation_probabilities.npz', va, self.classes)
                predicted = np.asarray(self.classes)[val_probability.argmax(axis=1)]
                assert np.array_equal(frame.y_true.astype(str), truth.astype(str))
                assert np.array_equal(frame.y_pred.astype(str), predicted)
                value, per_class = f1(truth.astype(str), predicted, self.classes)
                returned.update(validation=val_probability, value=value, per_class_f1=per_class)
            else:
                values = frame.y_pred.to_numpy(dtype=float)
                assert np.isfinite(values).all()
                assert np.allclose(frame.y_true.to_numpy(dtype=float), truth.astype(float), atol=1e-12, rtol=0)
                value = float(np.sqrt(np.mean((truth.astype(float)-values)**2)))
                returned.update(validation=values, value=value)
            assert close(value, record['metrics'][self.spec['metric']])
            assert close(value, stored['metrics'][self.spec['metric']])
        children, weights = [], None
        if recipe['engine'] == 'ensemble':
            weights = np.asarray(recipe['weights'], dtype=float)
            assert len(weights) == len(recipe['components']) and np.isfinite(weights).all()
            assert (weights >= 0).all() and weights.sum() > 0
            weights = weights / weights.sum()
            for i, child_recipe in enumerate(recipe['components']):
                if job_path.exists():
                    child = load(folder / f'component-{i}/result.json')
                    child = dict(child, output_dir=str(folder / f'component-{i}'))
                else:
                    field = 'experiments' if phase == 'primary' else 'confirmations'
                    matches = [r for r in self.report[field] if r.get('status') == 'ok' and r['recipe'] == child_recipe]
                    assert len(matches) == 1
                    child = matches[0]
                children.append(self.verify(child, partition, phase, full, child_recipe))
        elif recipe.get('params', {}).get('feature_views'):
            assert recipe['params']['feature_views'] == 'categorical_te_pair'
            weights = np.asarray([.5, .5])
            for i, child_recipe in enumerate(child_feature_views(recipe, self.spec)):
                child = load(folder / f'component-{i}/result.json')
                children.append(self.verify(dict(child, output_dir=str(folder / f'component-{i}')),
                    partition, phase, full, child_recipe))
        if children:
            for field in ['test'] + ([] if full else ['validation']):
                expected = sum(weight*child[field] for weight, child in zip(weights, children))
                assert np.allclose(returned[field], expected, atol=1e-10, rtol=1e-10)
        returned['mixture_children'] = len(children)
        self.records[key] = returned
        return returned


def expected_partition(task, spec, train, phase, plan):
    if task['kind'] == 'classification':
        frozen = plan['expected_classification_splits'][phase]
        path = work_path(frozen['path'])
        assert digest(path) == frozen['sha256']
        return split(path, len(train))
    values = pd.to_numeric(train[spec['time_column']], errors='raise')
    assert values.notna().all()
    offset = 0 if phase == 'primary' else 1
    cut = np.sort(values.unique())[-1-offset]
    return np.flatnonzero(values.to_numpy() < cut), np.flatnonzero(values.to_numpy() == cut)


def diagnostics(verifier, record, partition, phase):
    verified = verifier.verify(record, partition, phase)
    tr, va = split(partition, len(verifier.train))
    value = {'phase': phase, 'metric': verifier.spec['metric'], 'value': verified['value'],
        'fitting_rows': len(tr), 'validation_rows': len(va), 'positions_sha256': index_sha(tr, va),
        'training_rows_canonical_sha256': canonical(tr.tolist()),
        'split_file_sha256': digest(partition), 'prediction_sha256': digest(verified['folder'] / 'validation_predictions.csv'),
        'mixture_children': verified['mixture_children']}
    if verifier.spec['kind'] == 'classification':
        assert not np.intersect1d(verifier.hashes[tr], verifier.hashes[va]).size
        fitting_y = verifier.train[verifier.spec['target']].iloc[tr].astype(str).to_numpy()
        support = {c: len(np.unique(verifier.hashes[tr][fitting_y == c])) for c in verifier.classes}
        rarest = min(verifier.classes, key=lambda c: support[c])
        value.update(per_class_f1=verified['per_class_f1'], independent_fitting_groups=support,
            rarest_fitting_class=rarest, ex_rarest_macro_f1=float(np.mean([
                v for c, v in verified['per_class_f1'].items() if c != rarest])), feature_groups_disjoint=True)
    else:
        times = pd.to_numeric(verifier.train[verifier.spec['time_column']], errors='raise')
        assert times.iloc[tr].max() < times.iloc[va].min()
        value.update(forward_chronology_verified=True,
            validation_periods=sorted(map(float, times.iloc[va].unique())))
    return value


def baseline_comparison(report, cuts, baseline, baseline_path, train):
    assert baseline['final_fit_status'] == 'ok' and baseline['integrity_ok'] is True
    assert baseline['split']['split_sha256'] == cuts['primary']['positions_sha256']
    assert baseline['spec']['features'] == report['spec']['features']
    assert baseline['spec']['target'] == report['spec']['target']
    records = selected_records(baseline)
    confirmation_fit_hash = cuts['confirmation']['training_rows_canonical_sha256']
    def fitting_receipts(record):
        for row in record.get('data_policy_runs', []):
            yield row
        for child in record.get('components', []):
            yield from fitting_receipts(child)
    selected_components = (baseline['selected_recipe']['components'] if baseline['selected_recipe']['engine'] == 'ensemble'
        else [baseline['selected_recipe']])
    confirmation_component_training_matches = []
    for recipe in selected_components:
        candidates = [r for r in baseline.get('confirmations', []) if r.get('status') == 'ok' and r['recipe'] == recipe]
        assert len(candidates) == 1
        confirmation_component_training_matches.append(any(
            r.get('source_rows') == cuts['confirmation']['fitting_rows'] and
            r.get('source_parent_sha256') == confirmation_fit_hash for r in fitting_receipts(candidates[0])))
    comparable = all(confirmation_component_training_matches)
    metric = report['spec']['metric']
    rows = []
    for phase in ['primary', 'confirmation']:
        old = records[phase]['metrics']
        reference = old[metric]
        assert close(reference, reference)
        delta = cuts[phase]['value']-reference
        entry = {'phase': phase, 'current': cuts[phase]['value'], 'preserved_control': reference,
            'delta_current_minus_control': delta,
            'primary_improves': (delta > 0 if report['spec']['greater_is_better'] else delta < 0) if comparable else False}
        if report['spec']['kind'] == 'classification':
            classes = list(report['spec']['classes'])
            matrix = old.get('confusion_matrix')
            if matrix:
                order = matrix['classes']
                assert set(order) == set(classes) and len(order) == len(classes)
                counts = np.asarray(matrix['counts'], dtype=np.int64)
                score, per_class = f1_counts(counts, order)
                assert close(score, reference)
                assert all(close(per_class[c], old['per_class_f1'][c]) for c in classes)
            support = cuts[phase]['independent_fitting_groups']
            rarest = cuts[phase]['rarest_fitting_class']
            deltas = {c: cuts[phase]['per_class_f1'][c]-old['per_class_f1'][c] for c in classes}
            losses = {c: v for c, v in deltas.items() if support[c] >= 100 and v < -.01-1e-12}
            ex_rarest = float(np.mean([v for c, v in deltas.items() if c != rarest]))
            entry.update(per_class_f1_delta=deltas, supported_class_losses_over_001=losses,
                ex_rarest_macro_f1_delta=ex_rarest,
                all_class_gates_passed=entry['primary_improves'] and not losses and ex_rarest > 0)
        rows.append(entry)
    actual_mean = float(np.mean([cuts[p]['value'] for p in ['primary', 'confirmation']]))
    control_mean = float(np.mean([r['preserved_control'] for r in rows]))
    if baseline.get('ensemble'):
        assert close(control_mean, baseline['ensemble']['mean'])
    return {'baseline_report_sha256': digest(baseline_path), 'cuts': rows,
        'cut_comparable_by_preserved_protocol_and_matching_training_row_hashes': comparable,
        'historical_confirmation_training_rows_rechecked': comparable,
        'historical_confirmation_component_training_hash_matches': confirmation_component_training_matches,
        'actual_selected_two_cut_mean': actual_mean, 'preserved_selected_two_cut_mean': control_mean,
        'mean_delta_current_minus_control': actual_mean-control_mean,
        'each_cut_primary_gate_passed': all(r['primary_improves'] for r in rows),
        'class_each_cut_gate_passed': all(r.get('all_class_gates_passed', True) for r in rows),
        'fresh_control_refit': False, 'historical_control_raw_predictions_recomputed': False,
        'historical_confirmation_raw_partition_rechecked': False,
        'scope': 'Saved qualified full-procedure V11/V16 control; primary partition fingerprint matches, confirmation follows preserved two-cut protocol. Not a prospective matched rerun.'}


def verify_task(task, manifest, plan, campaign_task):
    directory = ROOT / task['code']
    runs = directory / 'automl_runs' / RUN_NAME
    report_path = runs / 'report.json'
    if not report_path.exists():
        return {'kind': task['kind'], 'status': 'missing_report', 'selected_cut_mean': None,
            'procedure_passed': False}
    report, supervisor = load(report_path), load(directory / 'supervisor.json')
    errors = []
    assert set(task['files']) == {'task.md', 'train.csv', 'test.csv', 'sample_submission.csv', 'data_dictionary.csv'}
    for name, sha in task['files'].items():
        assert digest(directory / name) == digest(WORK / task['source'] / name) == sha
    for name, sha in manifest['compiled_sha256'].items():
        assert digest(directory / name) == sha
    spec = report['spec']
    assert spec['kind'] == task['kind'] and spec['target'] not in spec['features'] and spec.get('id') not in spec['features']
    train, test, sample = [pd.read_csv(directory / name, converters={spec['id']: str}) for name in ['train.csv', 'test.csv', 'sample_submission.csv']]
    verifier = TaskVerifier(directory, report, train, test, sample)
    control_ref = plan['protected_control_recipes'][task['kind']]
    control_path = work_path(control_ref['path'])
    assert digest(control_path) == digest(directory / 'protected_control.json') == control_ref['sha256']
    protected_recipe = load(control_path)
    assert report['protected_control_recipe'] == protected_recipe
    control_records = report['protected_control']
    assert set(control_records) == {'primary', 'confirmation'}
    assert all(r['status'] == 'ok' and r['recipe'] == protected_recipe for r in control_records.values())
    signature = control_ref['signature']
    assert isinstance(signature, str) and len(signature) == 64
    assert report['research_retention']['control_signature'] == signature
    records = selected_records(report)
    cuts, control_cuts = {}, {}
    for phase, file in [('primary', 'split.npz'), ('confirmation', 'confirmation_split.npz')]:
        path = runs / file
        actual = split(path, len(train))
        expected = expected_partition(task, spec, train, phase, plan)
        assert all(np.array_equal(a, b) for a, b in zip(actual, expected))
        cuts[phase] = diagnostics(verifier, records[phase], path, phase)
        control_cuts[phase] = diagnostics(verifier, control_records[phase], path, phase)
    selected_mean = float(np.mean([cuts[p]['value'] for p in ['primary', 'confirmation']]))
    if report.get('ensemble'):
        assert close(selected_mean, report['ensemble']['mean'])
    elif report['selected_recipe'] != protected_recipe:
        selected = [r for r in report.get('selection', []) if r['recipe'] == report['selected_recipe']]
        assert len(selected) == 1 and close(selected_mean, selected[0]['mean'])
    assert close(cuts['primary']['value'], report['best_validation'][spec['metric']])
    initial_path = runs / 'initial-data-assessment.json'
    initial = load(initial_path)
    terminal = json.loads(initial['terminal_response'])
    assessment = terminal.get('data_assessment')
    assert isinstance(assessment, dict)
    for field in ['validation_risks', 'feature_hypotheses', 'model_priorities']:
        value = assessment.get(field)
        assert (isinstance(value, str) and bool(value.strip())) or (isinstance(value, list) and bool(value)
            and all(isinstance(v, str) and bool(v.strip()) for v in value))
    assert initial['context']['feedback_read_first'] == [] and initial['context']['best_recipe'] is None
    assert initial['context']['stage'] == 'initial_data_assessment_before_any_model_fit'
    assert initial['assessment']['assessment_valid'] is True
    assert supervisor['initial_assessment_valid_at_first_worker'] is True
    assert supervisor['initial_assessment_sha256_at_first_worker'] == digest(initial_path)
    pipeline = report.get('pipeline') or {}
    assert pipeline.get('mode') == 'four_stage' and pipeline.get('initial_data_assessment_before_fitting') is True
    assert pipeline.get('trusted_feature_family') == 'broad' and pipeline.get('maximum_added_broad_features') == 128
    assert pipeline.get('catboost_top_k') == 32 and pipeline.get('protected_originals') is True
    assert pipeline.get('preserved_control') is True
    assert pipeline.get('exploratory_selector_scope') == 'separate_candidates_only'
    families = sorted(set().union(*(learner_families(r['recipe'])
        for r in report['experiments'] if r.get('status') == 'ok')))
    if len(families) < 2:
        errors.append('fewer_than_two_successful_student_families')
    exploratory = [r for r in report['experiments'] if r.get('status') == 'ok'
        and r['recipe'].get('params', {}).get('generic_features') == 'broad'
        and r['recipe']['params'].get('feature_selection_top_k') == 32
        and r['recipe']['params'].get('feature_selection_protect_original') is True]
    assert exploratory, 'At least one successful separate broad/protected-CatBoost32 candidate is mandatory'
    for record in exploratory:
        verifier.verify(record, runs / 'split.npz', 'primary')
    job_hashes = {}
    teachers = []
    for path in sorted(runs.rglob('job.json')):
        job = load(path)
        assert job['spec'] == spec and job['threads'] == 2
        assert Path(job['output_dir']).resolve() == path.parent.resolve()
        job_hashes[path.relative_to(runs).as_posix()] = digest(path)
    for path in sorted(runs.rglob('result.json')):
        value = load(path)
        if value.get('components'):
            continue  # Saved parent copies would otherwise duplicate leaf receipts.
        for row in value.get('data_policy_runs', []):
            selection = row.get('feature_selection') or {}
            if selection.get('teacher_fitted') is True:
                assert selection['status'] == 'selected' and selection['iterations'] == 100
                assert selection.get('method') == 'union_original_top_k'
                assert len(selection['teacher_selected_columns']) == 32 and selection['fitting_rows'] > 0
                assert set(spec['features']) <= set(selection['protected_columns']) <= set(selection['selected_columns'])
                assert set(selection['teacher_selected_columns']) <= set(selection['selected_columns'])
                assert set(selection['selected_columns']) == set(selection['teacher_selected_columns']) | set(selection['protected_columns'])
                if value.get('status') == 'ok':
                    assert set(spec['features']) <= set(value['feature_names'])
                teachers.append({'stage': path.relative_to(runs).parts[0], 'input_columns': selection['input_columns'],
                    'fitting_rows': selection['fitting_rows'], 'retained_broad_columns': sum(str(c).startswith('__broad_')
                        for c in selection['selected_columns']), 'selector_seconds': selection.get('selector_seconds'),
                    'successful_leaf': value.get('status') == 'ok',
                    'in_successful_exploratory_candidate': any(path.is_relative_to(verifier.folder(r)) for r in exploratory)})
    assert teachers and max(t['input_columns'] for t in teachers) > len(spec['features'])
    assert any(t['successful_leaf'] and t['in_successful_exploratory_candidate'] for t in teachers)
    hpo = load(runs / 'inner-hpo/hpo.json')
    assert hpo == report['hpo'] and hpo['status'] == 'ok' and hpo['maximum_trials'] == 8
    assert hpo['sampler'] == 'tpe' and hpo['seed'] == 137 and hpo['startup_trials'] == 3
    requested_hpo = plan['hpo_requested_budget_seconds'][task['kind']]
    assert type(requested_hpo) is int and requested_hpo >= 5
    solver_budget = supervisor['solver_budget_seconds']
    reserve = min(1200, max(60, solver_budget * .2))
    lower_bound = supervisor.get('hpo_first_worker_remaining_lower_bound_seconds')
    if (supervisor.get('hpo_full_budget_observed') is not True or
            not isinstance(lower_bound, (int, float)) or isinstance(lower_bound, bool) or
            not math.isfinite(lower_bound) or lower_bound < reserve + requested_hpo + 30):
        errors.append('full_requested_HPO_allocation_not_independently_observed')
    assert not hpo['control_recipe'].get('params', {}).get('feature_selection_top_k')
    preserved_single = protected_recipe['components'][0]
    assert not preserved_single.get('params', {}).get('feature_selection_top_k')
    expected_generic = preserved_single.get('params', {}).get('generic_features', 'none')
    assert expected_generic != 'broad'
    assert hpo['control_recipe'].get('params', {}).get('generic_features', 'none') == expected_generic
    outer_tr, _ = split(runs / 'split.npz', len(train))
    inner_tr, inner_va = split(runs / 'inner-hpo/split.npz', len(train))
    assert (set(inner_tr) | set(inner_va)) <= set(outer_tr)
    assert hpo['split']['split_sha256'] == index_sha(inner_tr, inner_va)
    assert hpo['split']['scope'] == 'inside_outer_fitting_rows_only'
    if task['kind'] == 'classification':
        assert not np.intersect1d(verifier.hashes[inner_tr], verifier.hashes[inner_va]).size
    else:
        time_values = pd.to_numeric(train[spec['time_column']], errors='raise')
        assert time_values.iloc[inner_tr].max() < time_values.iloc[inner_va].min()
    hpo_rows, completed = [], 0
    for number, trial in enumerate(hpo['trials']):
        assert trial['number'] == number
        phase = 'anchor' if number == 0 else 'startup' if completed < hpo['startup_trials'] else 'guided'
        assert trial['sampling_phase'] == phase and trial['completed_before_sampling'] == completed
        if trial.get('objective_valid'):
            path = runs / 'inner-hpo' / f'trial-{number:02d}'
            record = load(path / 'result.json')
            checked = verifier.verify(dict(record, output_dir=str(path)), runs / 'inner-hpo/split.npz', 'inner')
            assert close(checked['value'], trial['value'])
            completed += 1
            hpo_rows.append({'number': number, 'phase': phase, 'status': 'verified_ok', 'value': checked['value']})
        else:
            assert trial.get('value') is None
            hpo_rows.append({'number': number, 'phase': phase, 'status': trial['status'], 'value': None})
    assert completed > 0
    final_path = runs / 'final-fit/result.json'
    if report.get('final_fit_status') != 'ok' or not final_path.exists():
        errors.append('final_full_refit_missing_or_failed')
    else:
        final = load(final_path)
        expected_iterations = median_iterations(records['primary']['fit_iterations'], records['confirmation']['fit_iterations'])
        assert report['final_fit_iterations'] == final['fit_iterations'] == expected_iterations
        verifier.verify(dict(final, output_dir=str(final_path.parent)), runs / 'split.npz', 'final',
            full=True, expected_recipe=report['selected_recipe'])
        assert digest(directory / 'submission.csv') == digest(final_path.parent / 'submission.csv') == report['submission_sha256']
    if report.get('integrity_ok') is not True or supervisor.get('cleanup_confirmed') is not True:
        errors.append('runtime_integrity_or_owned_cleanup_not_confirmed')
    trace_path = Path(report['run_budget_trace']).resolve()
    assert trace_path.is_relative_to(directory)
    try:
        budget = load(trace_path)
        api_hash = digest(trace_path)
        assert budget['gateway_call_limit'] == 4 and budget['gateway_calls_started'] <= 4
        if budget['status'] != 'completed' or budget['usage_complete'] is not True:
            errors.append('api_usage_incomplete')
        api = {'independently_read_closed_ledger': True, 'gateway_calls': budget['gateway_calls_started'],
            'http_attempts_reported': budget.get('http_attempts_reported'),
            'prompt_tokens_reported': budget.get('prompt_tokens_reported'),
            'completion_tokens_reported': budget.get('completion_tokens_reported'),
            'usage_complete': budget.get('usage_complete')}
    except PermissionError as exc:
        errors.append('closed_api_ledger_independently_unavailable_permission_denied')
        api_hash = None
        api = {'independently_read_closed_ledger': False, 'gateway_calls': None,
            'http_attempts_reported': None, 'prompt_tokens_reported': None,
            'completion_tokens_reported': None, 'usage_complete': None,
            'unavailable_reason': 'PermissionError', 'winerror': getattr(exc, 'winerror', None),
            'acl_bypass_attempted': False,
            'parent_supervisor_reported_usage': {k: campaign_task.get('proof', {}).get(k) for k in
                ['gateway_calls', 'gateway_calls_reported', 'http_attempts_reported', 'usage_complete',
                 'prompt_tokens_reported', 'completion_tokens_reported']},
            'parent_report_is_independent_ledger_read': False}
    comparisons = {}
    for name, frozen in plan['baseline_reports'][task['kind']].items():
        path = WORK / frozen['path']
        assert digest(path) == frozen['sha256']
        comparisons[name] = baseline_comparison(report, cuts, load(path), path, train)
    artifacts = {p.relative_to(runs).as_posix(): digest(p) for p in runs.rglob('*')
        if p.is_file() and p.suffix in {'.json', '.csv', '.npz'}}
    return {'kind': task['kind'], 'status': 'verified_saved_artifacts' if not errors else 'verified_saved_artifacts_unqualified',
        'procedure_passed': not errors and campaign_task.get('status') == 'ok' and campaign_task.get('exit_code') == 0 and campaign_task.get('cleanup_confirmed') is True,
        'errors': errors, 'cuts': cuts, 'selected_cut_mean': selected_mean,
        'mean_definition': 'Arithmetic mean of independently verified selected primary and selected confirmation; never proof.metrics/best_validation treated as a mean',
        'baseline_comparisons': comparisons, 'protected_control_measurements': control_cuts,
        'protected_control_recipe_sha256': control_ref['sha256'],
        'matched_control_comparison': matched_control_comparison(cuts, control_cuts, task['kind']),
        'successful_model_families': families, 'actual_teacher_receipts': teachers,
        'hpo_trials': hpo_rows, 'hpo_completed': completed,
        'hpo_guided_successful': sum(r['phase'] == 'guided' and r['status'] == 'verified_ok' for r in hpo_rows),
        'job_sha256': job_hashes, 'actual_artifact_sha256': artifacts,
        'stage_hashes': {'report': digest(report_path), 'initial_assessment': digest(initial_path),
            'supervisor': digest(directory / 'supervisor.json'), 'hpo': digest(runs / 'inner-hpo/hpo.json'),
            'api_ledger': api_hash},
        'api': api, 'promotion': False}


def work_path(value):
    path = Path(value)
    path = path.resolve() if path.is_absolute() else (WORK / path).resolve()
    assert path.is_relative_to(WORK), 'Expected an artifact inside the explicit work root'
    return path


def main():
    global WORK, REPO, ROOT, RUN_NAME
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight-only', action='store_true', help='Import real NumPy/Pandas only; no data or saved reports read')
    parser.add_argument('--work-root', type=Path)
    parser.add_argument('--task-root', help='New campaign directory, e.g. t3, relative to work root')
    parser.add_argument('--plan', help='SHA-bound prospective independent-verification plan')
    parser.add_argument('--manifest', help='Prospective execution manifest')
    parser.add_argument('--archive', help='Exact flat runtime archive')
    parser.add_argument('--run-name', default='repair4')
    parser.add_argument('--output', help='New exclusive output JSON, relative to work root')
    parser.add_argument('--task', choices=['all', 'regression', 'classification'], default='all')
    args = parser.parse_args()
    if args.preflight_only:
        print(json.dumps({'status': 'numpy_pandas_import_preflight_passed',
            'numpy': np.__version__, 'pandas': pd.__version__,
            'classification_prediction_type': 'value', 'sklearn_import_required': False,
            'model_runtime_imports': False, 'data_read': False, 'fits': 0, 'api_calls': 0}))
        return
    assert all([args.work_root, args.task_root, args.plan, args.manifest, args.archive, args.output])
    assert __debug__, 'Do not disable evaluator assertions'
    WORK = args.work_root.resolve()
    REPO = WORK / 'alfa-hack-automl'
    ROOT = work_path(args.task_root)
    RUN_NAME = args.run_name
    assert ROOT != REPO / 'test-runs/tm1', 'Historical tm1 is not a new prospective campaign'
    assert ROOT.parent == WORK and ROOT != WORK and ROOT.is_dir()
    assert RUN_NAME and Path(RUN_NAME).name == RUN_NAME
    plan_path, manifest_path = work_path(args.plan), work_path(args.manifest)
    archive_path, output = work_path(args.archive), work_path(args.output)
    assert not output.exists()
    plan = load(plan_path)
    assert digest(__file__) == plan['verifier_source_sha256']
    assert digest(manifest_path) == plan['execution_manifest_sha256']
    manifest = load(manifest_path)
    for name, expected in manifest['immutable_files'].items():
        assert digest(work_path(name)) == expected
    campaign_path = ROOT / 'campaign.json'
    campaign = load(campaign_path)
    terminal_clock_fields_present = all(campaign.get(k) is not None for k in ['finished_monotonic', 'finished_unix'])
    if args.task == 'all':
        assert campaign['cleanup_confirmed'] is True and campaign['source_unchanged'] is True
        if terminal_clock_fields_present:
            assert campaign['status'] not in {'starting', 'running', 'verifying'}
        else:
            assert campaign['status'] == 'verifying', 'All task artifacts may be audited before the campaign parent terminates'
    audit_clock_ok = (time.monotonic() <= campaign['common_deadline_monotonic']
                      and time.time() <= campaign['absolute_deadline_unix'])
    assert audit_clock_ok, 'Independent audit must remain inside the original common clock'
    assert campaign['manifest_sha256'] == plan['execution_manifest_sha256']
    assert campaign['absolute_deadline_unix'] == plan['original_absolute_deadline_unix']
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names)) and all(Path(n).name == n and (n.endswith('.py') or n == 'requirements.txt') for n in names)
        compiled = {n: hashlib.sha256(archive.read(n)).hexdigest() for n in names}
        assert compiled.get('requirements.txt') == '9173b0388532fbd2a709e4f4b3029e3b9ccab685fce43a85261ffa1ba95efbe6'
    assert compiled == manifest['compiled_sha256'] and len(compiled) > 0
    assert digest(archive_path) == manifest['archive_sha256']
    rows = {}
    for task in manifest['tasks']:
        if args.task != 'all' and task['kind'] != args.task:
            continue
        saved = next((r for r in campaign.get('tasks', []) if r['kind'] == task['kind']), {})
        terminal = load(ROOT / task['code'] / 'supervisor.json')
        assert terminal['status'] == 'ok' and terminal['exit_code'] == 0 and terminal['cleanup_confirmed'] is True
        rows[task['kind']] = verify_task(task, manifest, plan, saved)
    assert set(rows) == ({'regression', 'classification'} if args.task == 'all' else {args.task})
    # Recheck protected inputs/source after scoring; late drift cannot certify a result.
    for name, expected in manifest['immutable_files'].items():
        assert digest(work_path(name)) == expected
    for task in manifest['tasks']:
        if task['kind'] in rows:
            for name, expected in task['files'].items():
                assert digest(ROOT / task['code'] / name) == digest(work_path(task['source']) / name) == expected
    deadline_ok = (campaign['finished_monotonic'] <= campaign['common_deadline_monotonic']
        and campaign['finished_unix'] <= campaign['absolute_deadline_unix']) if terminal_clock_fields_present else None
    artifact_procedure_passed = all(r['procedure_passed'] for r in rows.values())
    audit_clock_ok = (time.monotonic() <= campaign['common_deadline_monotonic']
                      and time.time() <= campaign['absolute_deadline_unix'])
    assert audit_clock_ok
    if args.task != 'all':
        status = 'independently_verified_terminal_task_of_active_campaign'
    elif not terminal_clock_fields_present:
        status = ('independently_verified_task_artifacts_pending_campaign_terminal' if artifact_procedure_passed
                  else 'independently_verified_partial_or_unqualified_task_artifacts_pending_campaign_terminal')
    else:
        status = ('independently_verified_complete_new_four_stage_mvp' if deadline_ok and artifact_procedure_passed
                  else 'independently_verified_partial_or_unqualified_new_four_stage_mvp')
    report = {'status': status,
        'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'tasks': rows,
        'manifest_sha256': plan['execution_manifest_sha256'], 'campaign_sha256': digest(campaign_path),
        'runtime_archive_sha256': manifest['archive_sha256'], 'pristine_input_source_hashes_verified': True,
        'actual_common_deadline_satisfied': deadline_ok, 'actual_elapsed_common_seconds': campaign.get('elapsed_common_seconds'),
        'artifact_procedure_checks_passed': artifact_procedure_passed,
        'audit_within_original_common_clock': audit_clock_ok,
        'campaign_terminal_confirmed': terminal_clock_fields_present,
        'parent_exec_terminal_qualification_required': not terminal_clock_fields_present,
        'campaign_still_active_at_task_only_verification': campaign['status'] == 'running',
        'new_model_fits': 0, 'api_calls': 0, 'tests_run': 0, 'canonical_runtime_results_changed': False,
        'official_score': None, 'official_score_estimated': False,
        'failed_metrics_zero_imputed': False, 'promotion': False,
        'scope': 'New prospective saved-artifact audit on reused public cuts; independent quality gates are separate from stage completion and API completeness',
        'historical_baseline_limit': 'V11/V16 preserved report metrics/confusion matrices are saved-control evidence. Raw historical confirmation predictions are not independently reverified.'}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'output': output.name, 'status': report['status'],
        'selected_two_cut_means': {k: v.get('selected_cut_mean') for k, v in rows.items()}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
