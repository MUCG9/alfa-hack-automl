"""Small artifact-level checks for the development-only diversity diagnostic."""
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, mean_squared_error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.analyze_diversity import analyze, main


class BenchmarkFixture:
    """Write the public benchmark's actual on-disk interchange format."""

    def __init__(self, root, kind='classification', classes=None):
        self.root = Path(root)
        self.classes = ['a', 'b'] if classes is None else classes
        self.kind = kind
        self.path = self.root / 'results.json'
        digest = hashlib.sha256(b'frozen fixture').hexdigest()
        self.manifest = {
            'source': {'solution.py': digest}, 'harness': {'benchmark.py': digest},
            'inputs': {'train': digest}, 'task_sha256': digest,
            'spec': {'kind': kind, 'metric': 'macro_f1' if kind == 'classification' else 'rmse',
                     'greater_is_better': kind == 'classification',
                     'classes': self.classes if kind == 'classification' else None},
            'candidates': [], 'results': [],
        }

    def save(self):
        self.path.write_text(json.dumps(self.manifest))
        return self.path

    def write_artifacts(self, directory, recipe, truth, predicted=None, probabilities=None,
                        classes=None, rows=None, training=None):
        directory = Path(directory)
        directory.mkdir(parents=True)
        truth = np.asarray(truth)
        rows = np.arange(len(truth)) if rows is None else np.asarray(rows)
        training = np.arange(len(truth), len(truth) + 3) if training is None else np.asarray(training)
        if self.kind == 'classification':
            classes = self.classes if classes is None else classes
            probabilities = np.asarray(probabilities, dtype=float)
            predicted = np.asarray(classes)[probabilities.argmax(axis=1)]
            primary = f1_score(truth, predicted, labels=self.classes, average='macro', zero_division=0)
            np.savez(directory / 'validation_probabilities.npz', classes=classes,
                     probabilities=probabilities, row_position=rows)
        else:
            predicted = np.asarray(predicted, dtype=float)
            primary = mean_squared_error(truth, predicted) ** .5
        np.savez(directory / 'split.npz', train=training, validation=rows)
        pd.DataFrame({'row_position': rows, 'y_true': truth, 'y_pred': predicted}).to_csv(
            directory / 'validation_predictions.csv', index=False)
        metrics = {self.manifest['spec']['metric']: float(primary)}
        (directory / 'result.json').write_text(json.dumps({
            'status': 'ok', 'full_fit': False, 'recipe': recipe, 'metrics': metrics}))
        signature = hashlib.sha256(np.asarray(training, dtype='<i8').tobytes()
                                   + np.asarray(rows, dtype='<i8').tobytes()).hexdigest()
        return metrics, {'split_sha256': signature, 'train_rows': len(training),
                         'validation_rows': len(rows), 'method': 'fixture_holdout'}

    def add(self, name, truth, predicted=None, probabilities=None, seed=42,
            classes=None, rows=None, training=None, fold=None, n_splits=2, recipe=None):
        recipe = recipe or {'engine': 'synthetic', 'params': {'name': name}}
        if not any(c['name'] == name for c in self.manifest['candidates']):
            self.manifest['candidates'].append({'name': name, 'recipe': recipe})
        directory = self.root / name / f'seed-{seed}'
        metrics, split = self.write_artifacts(directory, recipe, truth, predicted, probabilities,
                                              classes, rows, training)
        if fold is not None:
            split.update(fold=fold, n_splits=n_splits, method='KFold')
        self.manifest['results'].append({'name': name, 'seed': seed, 'status': 'ok',
                                        'exit_code': 0, 'directory': str(directory),
                                        'split': split, 'metrics': metrics})
        self.save()
        return directory

    def paired_classification(self):
        truth = ['a', 'a', 'b', 'b']
        a = self.add('control', truth, probabilities=[[.9, .1], [.4, .6], [.6, .4], [.1, .9]])
        b = self.add('candidate', truth, probabilities=[[.4, .6], [.9, .1], [.7, .3], [.2, .8]])
        return a, b


class DiversityTests(unittest.TestCase):
    def test_classification_corrections_double_fault_and_fixed_blend(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = BenchmarkFixture(folder)
            fixture.paired_classification()
            report = analyze(fixture.path, 'control', ['candidate'])
            fold = report['comparisons'][0]['folds'][0]
            errors = fold['diversity']
            self.assertEqual(errors['both_wrong_count'], 1)
            self.assertEqual(errors['double_fault_rate'], .25)
            self.assertEqual(errors['shared_error_rate'], .25)
            self.assertEqual(errors['candidate_correct_given_control_wrong'],
                             {'numerator': 1, 'denominator': 2, 'rate': .5})
            self.assertEqual(errors['per_class']['a']['support'], 2)
            self.assertEqual(errors['per_class']['a']['candidate_correct_given_control_wrong']['rate'], 1.)
            self.assertEqual(errors['per_class']['b']['candidate_correct_given_control_wrong']['rate'], 0.)
            self.assertEqual(fold['primary_metric']['control'], .5)
            self.assertAlmostEqual(fold['primary_metric']['fixed_blend'], 11 / 15)
            self.assertEqual(report['provenance']['inputs'], fixture.manifest['inputs'])
            self.assertEqual(fold['alignment']['matched_rows'], 4)
            encoded = json.dumps(report, allow_nan=False)
            self.assertNotIn('y_true', encoded)
            self.assertNotIn('y_pred', encoded)
            self.assertNotIn('"row_position":', encoded)
            self.assertFalse(report['fixed_blend']['weights_fitted'])

    def test_zero_denominators_and_absent_class_have_explicit_support(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = BenchmarkFixture(folder, classes=['a', 'b', 'c'])
            for name in ['control', 'candidate']:
                fixture.add(name, ['a', 'b'], probabilities=[[1., 0., 0.], [0., 1., 0.]])
            errors = analyze(fixture.path, 'control')['comparisons'][0]['folds'][0]['diversity']
            self.assertEqual(errors['candidate_correct_given_control_wrong'],
                             {'numerator': 0, 'denominator': 0, 'rate': None})
            self.assertEqual(errors['per_class']['c']['support'], 0)
            self.assertIsNone(errors['per_class']['c']['double_fault_rate'])

    def test_probability_columns_reorder_by_classes(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = BenchmarkFixture(folder)
            a, b = fixture.paired_classification()
            baseline = analyze(fixture.path, 'control')['comparisons'][0]
            path = b / 'validation_probabilities.npz'
            with np.load(path) as stored:
                values = stored['probabilities'][:, ::-1].copy()
                rows = stored['row_position'].copy()
            np.savez(path, classes=['b', 'a'], probabilities=values, row_position=rows)
            reordered = analyze(fixture.path, 'control')['comparisons'][0]
            self.assertEqual(baseline['folds'][0]['metrics'], reordered['folds'][0]['metrics'])
            self.assertEqual(baseline['folds'][0]['diversity'], reordered['folds'][0]['diversity'])

    def test_csv_and_probability_row_order_mismatch_fail(self):
        for artifact in ['csv', 'probabilities']:
            with self.subTest(artifact=artifact), tempfile.TemporaryDirectory() as folder:
                fixture = BenchmarkFixture(folder)
                _, directory = fixture.paired_classification()
                if artifact == 'csv':
                    path = directory / 'validation_predictions.csv'
                    frame = pd.read_csv(path)
                    frame.iloc[::-1].to_csv(path, index=False)
                else:
                    path = directory / 'validation_probabilities.npz'
                    with np.load(path) as stored:
                        values = stored['probabilities'][::-1].copy()
                        rows = stored['row_position'][::-1].copy()
                    np.savez(path, classes=['a', 'b'], probabilities=values, row_position=rows)
                with self.assertRaisesRegex(ValueError, 'row order'):
                    analyze(fixture.path, 'control')

    def test_split_manifest_and_actual_training_mismatch_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = BenchmarkFixture(folder)
            _, directory = fixture.paired_classification()
            np.savez(directory / 'split.npz', train=[8, 9, 10], validation=[0, 1, 2, 3])
            with self.assertRaisesRegex(ValueError, 'Split SHA'):
                analyze(fixture.path, 'control')
            entry = fixture.manifest['results'][1]
            entry['split']['split_sha256'] = hashlib.sha256(
                np.asarray([8, 9, 10, 0, 1, 2, 3], dtype='<i8').tobytes()).hexdigest()
            fixture.save()
            with self.assertRaisesRegex(ValueError, 'split SHA'):
                analyze(fixture.path, 'control')

    def test_missing_duplicate_or_unknown_probability_classes_fail(self):
        for classes in [['a'], ['a', 'a'], ['a', 'z']]:
            with self.subTest(classes=classes), tempfile.TemporaryDirectory() as folder:
                fixture = BenchmarkFixture(folder)
                _, directory = fixture.paired_classification()
                np.savez(directory / 'validation_probabilities.npz', classes=classes,
                         probabilities=np.full((4, len(classes)), .5), row_position=np.arange(4))
                with self.assertRaisesRegex(ValueError, 'class set'):
                    analyze(fixture.path, 'control')

    def test_duplicate_manifest_entries_and_positions_fail(self):
        for duplicate in ['candidate', 'result', 'position']:
            with self.subTest(duplicate=duplicate), tempfile.TemporaryDirectory() as folder:
                fixture = BenchmarkFixture(folder)
                _, directory = fixture.paired_classification()
                if duplicate == 'candidate':
                    fixture.manifest['candidates'].append(fixture.manifest['candidates'][0])
                elif duplicate == 'result':
                    fixture.manifest['results'].append(fixture.manifest['results'][0])
                else:
                    path = directory / 'validation_predictions.csv'
                    frame = pd.read_csv(path)
                    frame.loc[1, 'row_position'] = 0
                    frame.to_csv(path, index=False)
                fixture.save()
                with self.assertRaisesRegex(ValueError, '[Dd]uplicate'):
                    analyze(fixture.path, 'control')

    def test_invalid_probability_values_fail_closed(self):
        for value in [np.nan, np.inf, -.1, 1.1, 0.]:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as folder:
                fixture = BenchmarkFixture(folder)
                _, directory = fixture.paired_classification()
                probabilities = np.full((4, 2), .5)
                probabilities[0] = value
                np.savez(directory / 'validation_probabilities.npz', classes=['a', 'b'],
                         probabilities=probabilities, row_position=np.arange(4))
                with self.assertRaisesRegex(ValueError, 'Probabilit'):
                    analyze(fixture.path, 'control')

    def test_missing_failed_or_incomplete_artifacts_fail_closed(self):
        for issue in ['missing', 'failed', 'folds', 'truth', 'decision']:
            with self.subTest(issue=issue), tempfile.TemporaryDirectory() as folder:
                fixture = BenchmarkFixture(folder)
                _, directory = fixture.paired_classification()
                if issue == 'missing':
                    (directory / 'validation_probabilities.npz').unlink()
                elif issue == 'failed':
                    fixture.manifest['results'][1]['status'] = 'timeout'
                elif issue == 'folds':
                    fixture.manifest['results'][1]['seed'] = 43
                else:
                    path = directory / 'validation_predictions.csv'
                    frame = pd.read_csv(path)
                    frame.loc[0, 'y_true' if issue == 'truth' else 'y_pred'] = 'b' if issue == 'truth' else 'a'
                    frame.to_csv(path, index=False)
                fixture.save()
                with self.assertRaises(ValueError):
                    analyze(fixture.path, 'control')

    def test_regression_constant_residuals_and_fixed_blend(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = BenchmarkFixture(folder, 'regression')
            fixture.add('control', [0., 1., 2., 3.], predicted=[1., 2., 3., 4.])
            fixture.add('candidate', [0., 1., 2., 3.], predicted=[-1., 0., 1., 2.])
            fold = analyze(fixture.path, 'control')['comparisons'][0]['folds'][0]
            self.assertIsNone(fold['diversity']['residual_correlation'])
            self.assertTrue(fold['diversity']['residual_correlation_undefined'])
            self.assertEqual(fold['metrics']['control']['mae'], 1.)
            self.assertEqual(fold['metrics']['fixed_blend']['mae'], 0.)
            self.assertEqual(fold['primary_metric']['fixed_blend'], 0.)

    def test_regression_residual_correlation(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = BenchmarkFixture(folder, 'regression')
            fixture.add('control', [0., 1., 2., 3.], predicted=[1., 0., 4., 1.])
            fixture.add('candidate', [0., 1., 2., 3.], predicted=[-1., 2., 0., 5.])
            fold = analyze(fixture.path, 'control')['comparisons'][0]['folds'][0]
            self.assertAlmostEqual(fold['diversity']['residual_correlation'], -1.)
            self.assertAlmostEqual(fold['metrics']['control']['rmse'], 2.5 ** .5)
            self.assertEqual(fold['metrics']['fixed_blend']['rmse'], 0.)

    def test_regression_nonfinite_truth_or_predictions_fail_closed(self):
        for column in ['y_true', 'y_pred']:
            with self.subTest(column=column), tempfile.TemporaryDirectory() as folder:
                fixture = BenchmarkFixture(folder, 'regression')
                fixture.add('control', [0., 1.], predicted=[0., 1.])
                directory = fixture.add('candidate', [0., 1.], predicted=[0., 1.])
                path = directory / 'validation_predictions.csv'
                frame = pd.read_csv(path)
                frame.loc[0, column] = np.inf
                frame.to_csv(path, index=False)
                with self.assertRaisesRegex(ValueError, 'must be finite'):
                    analyze(fixture.path, 'control')

    def test_complete_oof_separates_fold_mean_and_pooled_metrics(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = BenchmarkFixture(folder, 'regression')
            for name in ['control', 'candidate']:
                fixture.add(name, [0., 0.], predicted=[2., 0.], rows=[0, 1],
                            training=[2, 3, 4], seed=0, fold=0)
                fixture.add(name, [0., 0., 0.], predicted=[0., 0., 0.], rows=[2, 3, 4],
                            training=[0, 1], seed=1, fold=1)
            comparison = analyze(fixture.path, 'control')['comparisons'][0]
            self.assertAlmostEqual(comparison['fold_mean']['primary_metric']['control'], 2 ** .5 / 2)
            self.assertAlmostEqual(comparison['pooled_oof']['primary_metric']['control'], .8 ** .5)
            self.assertEqual(comparison['pooled_oof']['coverage'], 'exactly_once')
            self.assertEqual(comparison['pooled_oof']['matched_rows'], 5)

    def test_overlapping_holdouts_are_never_pooled(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = BenchmarkFixture(folder, 'regression')
            for name in ['control', 'candidate']:
                fixture.add(name, [0., 1.], predicted=[0., 1.], seed=42)
                fixture.add(name, [1., 2.], predicted=[1., 2.], rows=[1, 2], training=[0, 3, 4], seed=43)
            comparison = analyze(fixture.path, 'control')['comparisons'][0]
            self.assertEqual(comparison['fold_mean']['fold_count'], 2)
            self.assertEqual(comparison['pooled_oof']['status'], 'omitted')

    def test_incomplete_declared_oof_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = BenchmarkFixture(folder, 'regression')
            for name in ['control', 'candidate']:
                fixture.add(name, [0., 1.], predicted=[0., 1.], rows=[0, 1],
                            training=[2, 3, 4], seed=0, fold=0)
            with self.assertRaisesRegex(ValueError, 'OOF folds'):
                analyze(fixture.path, 'control')

    def test_expand_ensemble_components_uses_parent_split(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = BenchmarkFixture(folder)
            components = [{'engine': 'synthetic', 'params': {'number': n}} for n in range(2)]
            truth, probabilities = ['a', 'b'], [[.8, .2], [.2, .8]]
            fixture.add('control', truth, probabilities=probabilities)
            parent = fixture.add('ensemble', truth, probabilities=probabilities,
                                 recipe={'engine': 'ensemble', 'components': components})
            for number, recipe in enumerate(components):
                child = parent / f'component-{number}'
                fixture.write_artifacts(child, recipe, truth, probabilities=probabilities)
                (child / 'split.npz').unlink()
            report = analyze(fixture.path, 'control', expand_components=True)
            self.assertEqual([c['candidate'] for c in report['comparisons']],
                             ['ensemble', 'ensemble::component-0', 'ensemble::component-1'])
            self.assertTrue(all(c['folds'][0]['primary_metric']['fixed_blend'] == 1.
                                for c in report['comparisons']))

    def test_recomputed_primary_metric_must_match_record(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = BenchmarkFixture(folder)
            fixture.paired_classification()
            fixture.manifest['results'][1]['metrics']['macro_f1'] = .99
            fixture.save()
            with self.assertRaisesRegex(ValueError, 'recorded metric'):
                analyze(fixture.path, 'control')

    def test_class_labels_keep_leading_zero_and_na_strings(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = BenchmarkFixture(folder, classes=['01', 'NA'])
            for name in ['control', 'candidate']:
                fixture.add(name, ['01', 'NA'], probabilities=[[.8, .2], [.2, .8]])
            fold = analyze(fixture.path, 'control')['comparisons'][0]['folds'][0]
            self.assertEqual(fold['primary_metric']['control'], 1.)
            self.assertEqual(fold['alignment']['classes'], ['01', 'NA'])

    def test_cli_deterministic_outputs_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = BenchmarkFixture(folder)
            fixture.paired_classification()
            outputs = [Path(folder) / f'diagnostics-{i}.json' for i in range(2)]
            for output in outputs:
                with redirect_stdout(io.StringIO()):
                    main(['--results', folder, '--control', 'control', '--candidate', 'candidate',
                          '--output', str(output)])
            self.assertEqual(outputs[0].read_bytes(), outputs[1].read_bytes())
            with self.assertRaisesRegex(ValueError, 'new output path'):
                main(['--results', folder, '--control', 'control', '--output', str(outputs[0])])


if __name__ == '__main__':
    unittest.main()
