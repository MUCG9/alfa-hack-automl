"""Prepared projection/publication contracts; no estimator, worker or API calls."""
from dataclasses import replace
from pathlib import Path
import csv
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from automl.publishing.service import dummy_predictions, save_submission
from automl.task_understanding.early_output import (
    DeclaredOutput, EarlyOutputError, ProjectionLimits, prepare_early_output,
)


class EarlyOutputTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.paths = {'train': 'unfamiliar-learning.csv', 'test': 'future-features.csv',
                      'sample_submission': 'answer-layout.csv'}
        self.checks = 0

    def checkpoint(self):
        self.checks += 1

    def table(self, role, rows, delimiter=','):
        with (self.root / self.paths[role]).open('w', encoding='utf-8', newline='') as stream:
            csv.writer(stream, delimiter=delimiter).writerows(rows)

    def fixture(self, labels=('0', '0', '90')):
        self.table('train', [['id', 'x', 'answer'], *[[str(i), 'not-retained', y]
                    for i, y in enumerate(labels)]])
        self.table('test', [['id', 'x'], ['001', 'unused'], ['1', 'unused'], ['NA', 'unused']])
        self.table('sample_submission', [['id', 'answer'], ['NA', ''], ['001', ''], ['1', '']])

    def declaration(self, **updates):
        return replace(DeclaredOutput(target='answer', kind='regression', id_policy='column',
            identifier='id', evidence=('Declared task/dictionary roles',)), **updates)

    def prepare(self, declaration=None, text='Metric: RMSE', **kwargs):
        return prepare_early_output(self.root, self.paths, declaration or self.declaration(),
            text, checkpoint=kwargs.pop('checkpoint', self.checkpoint), **kwargs)

    def publish(self, result):
        self.assertTrue(result.ready_for_publication)
        path = self.root / 'output.csv'
        values = dummy_predictions(result.writer_spec, result.target_frame, len(result.test_ids))
        save_submission(result.writer_spec, result.sample, result.test_ids, values, path)
        with path.open(encoding='utf-8', newline='') as stream:
            return list(csv.reader(stream))

    def test_known_RMSE_and_MAE_publish_mean_or_median_with_sample_order(self):
        self.fixture()
        for text, expected in [('Metric: RMSE', 30.), ('Metric: MAE', 0.)]:
            with self.subTest(text=text):
                result = self.prepare(text=text)
                self.assertTrue(result.objective_resolved)
                self.assertEqual(result.writer_spec['sample_test_positions'], [2, 0, 1])
                rows = self.publish(result)
                self.assertEqual([r[0] for r in rows[1:]], ['NA', '001', '1'])
                self.assertEqual([float(r[1]) for r in rows[1:]], [expected] * 3)

    def test_lexical_labels_and_IDs_preserve_leading_zero_and_literal_NA(self):
        self.fixture(('001', 'NA', '001'))
        result = self.prepare(self.declaration(kind='classification'), 'Metric: Macro F1')
        self.assertEqual(result.target_frame['answer'].tolist(), ['001', 'NA', '001'])
        self.assertEqual(result.test_ids['id'].tolist(), ['001', '1', 'NA'])
        self.assertEqual(result.writer_spec['classes'], ['001', 'NA'])
        self.assertEqual(result.receipt['target_scope'],
                         'entire_training_target_for_output_only_not_fitting_analysis')
        self.assertEqual([r[1] for r in self.publish(result)[1:]], ['001'] * 3)

    def test_binary_probability_uses_explicit_first_positive_class(self):
        self.fixture(('alpha', 'alpha', 'omega', 'alpha'))
        result = self.prepare(self.declaration(kind='binary', output_kind='probability',
            positive_class='alpha'), 'Metric: log loss')
        self.assertEqual(result.writer_spec['classes'], ['alpha', 'omega'])
        self.assertEqual([float(r[1]) for r in self.publish(result)[1:]], [.75] * 3)

    def test_probability_matrix_follows_sample_class_columns_and_row_mapping(self):
        self.fixture(('alpha', 'alpha', 'omega', 'alpha'))
        self.table('sample_submission', [['id', 'omega', 'alpha'], ['NA', '', ''],
                    ['001', '', ''], ['1', '', '']])
        result = self.prepare(self.declaration(kind='classification'), 'Metric: Macro F1')
        self.assertEqual(result.writer_spec['output_columns'], ['omega', 'alpha'])
        rows = self.publish(result)
        self.assertEqual(rows[0], ['id', 'omega', 'alpha'])
        self.assertEqual([[float(v) for v in row[1:]] for row in rows[1:]], [[.25, .75]] * 3)

    def test_unknown_or_unsupported_metric_can_only_be_format_only(self):
        self.fixture()
        for text, status in [('Predict answer.', 'unknown'), ('Primary metric: custom_cost', 'unsupported')]:
            with self.subTest(text=text):
                result = self.prepare(text=text)
                self.assertEqual(result.metric_spec.status, status)
                self.assertIsNone(result.writer_spec['metric'])
                self.assertIsNone(result.writer_spec['greater_is_better'])
                self.assertTrue(result.receipt['format_only'])
                self.assertFalse(result.objective_resolved)
                self.assertEqual(len(self.publish(result)), 4)

    def test_unresolved_declared_roles_do_not_open_or_guess_files(self):
        for declaration in (DeclaredOutput(), self.declaration(target=None),
                            self.declaration(kind=None), self.declaration(id_policy='unknown'),
                            self.declaration(evidence=())):
            with self.subTest(declaration=declaration), patch.object(Path, 'open',
                    side_effect=AssertionError('IO before role contract')):
                result = self.prepare(declaration)
                self.assertEqual(result.status, 'unknown')
                self.assertFalse(result.ready_for_publication)
                self.assertIsNone(result.writer_spec)

    def test_conflicting_target_ID_or_file_roles_are_explicitly_ambiguous(self):
        self.fixture()
        result = self.prepare(self.declaration(identifier='answer'))
        self.assertEqual(result.status, 'ambiguous')
        result = prepare_early_output(self.root, dict(self.paths, test=self.paths['train']),
            self.declaration(), 'Metric: RMSE', checkpoint=self.checkpoint)
        self.assertEqual(result.status, 'ambiguous')
        self.table('test', [['id', 'answer'], ['001', ''], ['1', ''], ['NA', '']])
        self.assertEqual(self.prepare().reason, 'target_role_schema_conflict')

    def test_classification_placeholder_cannot_decide_unknown_format_or_positive_label(self):
        self.fixture(('left', 'right', 'left'))
        result = self.prepare(self.declaration(kind='classification'), 'Predict answer.')
        self.assertEqual(result.status, 'unknown')
        self.assertEqual(result.reason, 'output_format_not_declared')
        for positive in (None, 'absent'):
            result = self.prepare(self.declaration(kind='binary', output_kind='probability',
                positive_class=positive), 'Metric: ROC AUC')
            self.assertFalse(result.ready_for_publication)
            self.assertEqual(result.reason, 'explicit_positive_class_required')

    def test_bad_ID_bijection_or_row_count_cannot_publish(self):
        for rows in ([['001', ''], ['001', ''], ['NA', '']],
                     [['001', ''], ['absent', ''], ['NA', '']],
                     [['001', ''], ['1', '']]):
            self.fixture()
            self.table('sample_submission', [['id', 'answer'], *rows])
            with self.subTest(rows=rows), self.assertRaises(EarlyOutputError):
                self.prepare()
        self.assertFalse((self.root / 'output.csv').exists())

    def test_bad_headers_width_targets_and_RMSLE_domain_reject(self):
        for content in ('id,x,answer,answer\n1,a,1,2\n', 'id,x,answer\n1,a\n',
                        'id,x,answer\n1,a,inf\n', 'id,x,answer\n1,a,\n'):
            self.fixture()
            (self.root / self.paths['train']).write_text(content, encoding='utf-8')
            with self.subTest(content=content), self.assertRaises(EarlyOutputError):
                self.prepare()
        self.fixture(('-1', '0', '1'))
        with self.assertRaisesRegex(EarlyOutputError, 'negative_RMSLE_target'):
            self.prepare(text='Metric: RMSLE')

    def test_changed_header_between_validation_and_projection_cannot_publish(self):
        original_open = Path.open
        for role in self.paths:
            self.fixture()
            changed_path = self.root / self.paths[role]
            read_count = 0

            def drift(path, *args, **kwargs):
                nonlocal read_count
                if path == changed_path and args and args[0] == 'r':
                    read_count += 1
                    if read_count == 2:
                        with original_open(path, encoding='utf-8', newline='') as stream:
                            rows = list(csv.reader(stream))
                        rows[0].append('extra_output')
                        for row in rows[1:]:
                            row.append('must_not_publish')
                        with original_open(path, 'w', encoding='utf-8', newline='') as stream:
                            csv.writer(stream).writerows(rows)
                return original_open(path, *args, **kwargs)

            with self.subTest(role=role), patch.object(Path, 'open', drift):
                with self.assertRaisesRegex(EarlyOutputError, 'input_schema_changed:' + role):
                    self.prepare()
            self.assertEqual(read_count, 2)
            self.assertFalse((self.root / 'output.csv').exists())

    def test_hard_projection_row_header_field_prediction_and_source_bounds(self):
        cases = [dict(max_rows=2), dict(max_header_bytes=5), dict(max_field_bytes=3),
                 dict(max_projection_bytes=100), dict(max_prediction_bytes=8),
                 dict(max_source_bytes=10)]
        for options in cases:
            self.fixture()
            with self.subTest(options=options), self.assertRaises(EarlyOutputError):
                self.prepare(limits=replace(ProjectionLimits(), **options))
        self.fixture(('a', 'b', 'c'))
        with self.assertRaisesRegex(EarlyOutputError, 'class_count_bound'):
            self.prepare(self.declaration(kind='classification'), 'Metric: Macro F1',
                         limits=replace(ProjectionLimits(), max_classes=2))
        self.fixture(('z' * 100, 'z' * 100, 'other'))
        with self.assertRaisesRegex(EarlyOutputError, 'prediction_bytes_bound'):
            self.prepare(self.declaration(kind='classification'), 'Metric: Macro F1',
                         limits=replace(ProjectionLimits(), max_prediction_bytes=64))

    def test_caller_checkpoint_failure_propagates_and_no_fresh_clock_is_created(self):
        self.fixture()
        def expired():
            raise TimeoutError('original preparation deadline')
        with patch.object(Path, 'open', side_effect=AssertionError('IO after timeout')):
            with self.assertRaises(TimeoutError):
                self.prepare(checkpoint=expired)
        calls = []
        class FalseyCheckpoint:
            def __bool__(self): return False
            def __call__(self): calls.append(True)
        result = self.prepare(checkpoint=FalseyCheckpoint())
        self.assertGreater(len(calls), 10)
        self.assertFalse(result.receipt['new_clock_created'])
        with self.assertRaises(ValueError):
            self.prepare(checkpoint=None)

    def test_path_escape_symlink_and_malformed_declaration_reject(self):
        self.fixture()
        with self.assertRaises(EarlyOutputError):
            prepare_early_output(self.root, dict(self.paths, train='../outside.csv'),
                self.declaration(), 'Metric: RMSE', checkpoint=self.checkpoint)
        with patch.object(Path, 'is_symlink', return_value=True), self.assertRaises(EarlyOutputError):
            self.prepare()
        for updates in ({'target': True}, {'kind': 'named_dataset'}, {'evidence': ['not tuple']},
                        {'output_kind': 'arbitrary'}, {'positive_class': 'x' * 257}):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                self.declaration(**updates)

    def test_no_ID_renamed_semicolon_tables_retain_only_output_projections(self):
        self.table('train', [['unused', 'new_target'], ['large feature', '0'],
                           ['different feature', '0'], ['third feature', '90']], delimiter=';')
        self.table('test', [['unused'], ['ignored'], ['ignored again']], delimiter=';')
        self.table('sample_submission', [['new_target'], [''], ['']], delimiter=';')
        result = self.prepare(DeclaredOutput(target='new_target', kind='regression',
            id_policy='none', evidence=('Explicit no-ID task format',)), 'Metric: MAE')
        self.assertEqual(result.target_frame.columns.tolist(), ['new_target'])
        self.assertEqual(result.test_ids.columns.tolist(), [])
        self.assertEqual(len(result.test_ids), 2)
        self.assertFalse(result.receipt['feature_profiling'])
        self.assertTrue(result.receipt['full_input_provenance_pending'])
        self.assertEqual([float(r[0]) for r in self.publish(result)[1:]], [0., 0.])


if __name__ == '__main__':
    unittest.main()
