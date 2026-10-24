"""Prepared bounded declaration contracts; no model, worker or API calls."""
from dataclasses import replace
from pathlib import Path
import builtins
import csv
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from automl.task_understanding.early_declaration import (
    DeclarationLimits, EarlyDeclarationError, bootstrap_early_declaration,
)
from automl.task_understanding.early_output import prepare_early_output


class EarlyDeclarationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.task = self.root / 'instructions.txt'
        self.paths = {'train': 'unrelated-a.csv', 'test': 'unrelated-b.csv',
                      'sample_submission': 'layout-c.csv'}
        self.calls = 0

    def checkpoint(self):
        self.calls += 1

    def table(self, name, rows, delimiter=','):
        with (self.root / name).open('w', encoding='utf-8', newline='') as stream:
            csv.writer(stream, delimiter=delimiter).writerows(rows)

    def fixture(self, dictionary=True, kind='regression', extra=''):
        self.table(self.paths['train'], [['identity', 'input', 'outcome'],
                   ['01', 'opaque feature', '0'], ['02', 'opaque feature', '2']])
        self.table(self.paths['test'], [['identity', 'input'], ['001', 'ignored'], ['NA', 'ignored']])
        self.table(self.paths['sample_submission'], [['identity', 'outcome'], ['NA', ''], ['001', '']])
        self.table('roles.csv', [['feature', 'role'], ['outcome', 'target'], ['identity', 'id']])
        fields = [f'{role}: `{path}`' for role, path in self.paths.items()]
        fields += [f'Task kind: {kind}', 'Output kind: value']
        fields += ['Data dictionary: roles.csv'] if dictionary else ['Target: outcome', 'ID column: identity']
        self.task.write_text('\n'.join(fields) + '\n' + extra, encoding='utf-8')

    def call(self, **kwargs):
        return bootstrap_early_declaration(self.task,
            checkpoint=kwargs.pop('checkpoint', self.checkpoint), **kwargs)

    def test_renamed_explicit_tables_and_dictionary_roles_resolve_without_name_aliases(self):
        self.fixture()
        with patch.object(Path, 'rglob', side_effect=AssertionError('catalog scan forbidden')):
            result = self.call()
        self.assertTrue(result.ready_for_projection)
        self.assertEqual(result.paths, self.paths)
        self.assertEqual(result.declaration.target, 'outcome')
        self.assertEqual(result.declaration.identifier, 'identity')
        self.assertEqual(result.declaration.kind, 'regression')
        self.assertFalse(result.receipt['feature_rows_loaded'])
        self.assertFalse(result.receipt['target_rows_loaded'])

    def test_explicit_no_ID_single_column_semicolon_schema_composes_with_IO02(self):
        self.table('odd-one.csv', [['column', 'result'], ['text', '0'], ['other', '10']], ';')
        self.table('odd-two.csv', [['column'], ['unused']], ';')
        self.table('odd-three.csv', [['result'], ['']], ';')
        self.task.write_text('Train file: odd-one.csv\nTest file: odd-two.csv\n'
            'Sample submission: odd-three.csv\nTarget column: result\nTask kind: regression\n'
            'ID policy: none\nOutput kind: value\nMetric: MAE\n', encoding='utf-8')
        result = self.call()
        self.assertTrue(result.ready_for_projection)
        self.assertEqual(result.declaration.id_policy, 'none')
        early = prepare_early_output(self.root, result.paths, result.declaration,
            result.task_text, checkpoint=self.checkpoint)
        self.assertTrue(early.ready_for_publication)
        self.assertEqual(early.metric_spec.name, 'mae')
        self.assertEqual(early.test_ids.columns.tolist(), [])

    def test_unknown_metric_is_not_guessed_and_known_format_remains_separate(self):
        self.fixture(extra='Primary metric: cost_not_supported\n')
        result = self.call()
        self.assertTrue(result.ready_for_projection)
        self.assertEqual(result.receipt['metric_resolution'], 'deferred_to_IO02_strict_MetricSpec')
        early = prepare_early_output(self.root, result.paths, result.declaration,
            result.task_text, checkpoint=self.checkpoint)
        self.assertTrue(early.ready_for_publication)
        self.assertFalse(early.objective_resolved)
        self.assertIsNone(early.writer_spec['metric'])
        self.assertTrue(early.receipt['format_only'])

    def test_basenames_prose_and_numeric_target_values_never_supply_missing_authority(self):
        self.fixture(dictionary=False)
        text = self.task.read_text('utf-8')
        for remove, reason in [('Target: outcome\n', 'explicit_target_required'),
                               ('Task kind: regression\n', 'explicit_supported_task_kind_required')]:
            self.task.write_text(text.replace(remove, '') + '\nWe may use classification or regression.\n',
                                 encoding='utf-8')
            with self.subTest(remove=remove):
                result = self.call()
                self.assertEqual(result.status, 'unknown')
                self.assertEqual(result.reason, reason)
                self.assertIsNone(result.declaration)
        self.task.write_text('A regression example uses train.csv, test.csv and sample_submission.csv.\n',
                             encoding='utf-8')
        self.assertEqual(self.call().reason, 'explicit_file_roles_required')

    def test_missing_ID_is_unknown_and_explicit_no_ID_conflicting_with_dictionary_is_ambiguous(self):
        self.fixture(dictionary=False)
        text = self.task.read_text('utf-8').replace('ID column: identity\n', '')
        self.task.write_text(text, encoding='utf-8')
        self.assertEqual(self.call().reason, 'explicit_ID_policy_required')
        self.fixture(extra='ID policy: none\n')
        result = self.call()
        self.assertEqual(result.status, 'ambiguous')
        self.assertEqual(result.reason, 'conflicting_ID_policy')

    def test_conflicting_repeated_fields_and_dictionary_sources_are_not_silently_overridden(self):
        for extra, dictionary, reason in [('Train file: unrelated-b.csv\n', True,
                  'conflicting_explicit_task_fields'), ('Target: alternate\n', True,
                  'target_authority_conflict'), ('ID column: alternate\n', True,
                  'ID_authority_conflict')]:
            self.fixture(dictionary=dictionary, extra=extra)
            with self.subTest(reason=reason):
                result = self.call()
                self.assertEqual(result.status, 'ambiguous')
                self.assertEqual(result.reason, reason)
        self.fixture(extra='ID column: identity\nID policy: column\n')
        self.assertTrue(self.call().ready_for_projection)

    def test_explicit_multitarget_is_retained_as_unsupported_branch(self):
        self.fixture(dictionary=False)
        text = self.task.read_text('utf-8').replace('Target: outcome', 'Targets: ["outcome", "another"]')
        self.task.write_text(text, encoding='utf-8')
        self.assertEqual(self.call().status, 'multitarget')
        self.fixture()
        self.table('roles.csv', [['feature', 'role'], ['outcome', 'target'], ['another', 'target'],
                                ['identity', 'id']])
        result = self.call()
        self.assertEqual(result.status, 'multitarget')
        self.assertIsNone(result.paths)
        self.assertIsNone(result.declaration)

    def test_scalar_probability_needs_explicit_positive_and_output_header_authority(self):
        self.fixture(kind='binary')
        text = self.task.read_text('utf-8').replace('Output kind: value', 'Output kind: probability')
        self.task.write_text(text, encoding='utf-8')
        self.assertEqual(self.call().reason, 'explicit_positive_class_required')
        self.task.write_text(text + 'Positive class: 001\nOutput columns: ["outcome"]\n', encoding='utf-8')
        result = self.call()
        self.assertTrue(result.ready_for_projection)
        self.assertEqual(result.declaration.positive_class, '001')
        self.task.write_text(text + 'Positive class: 001\nOutput columns: ["wrong"]\n', encoding='utf-8')
        self.assertEqual(self.call().reason, 'explicit_output_header_conflict')
        self.fixture(kind='regression', extra='Positive class: 001\n')
        self.assertEqual(self.call().reason, 'positive_class_in_regression')

    def test_target_ID_and_output_header_conflicts_fail_before_IO02(self):
        self.fixture()
        self.table(self.paths['test'], [['identity', 'input', 'outcome']])
        self.assertEqual(self.call().reason, 'target_header_conflict')
        self.fixture()
        self.table(self.paths['sample_submission'], [['other_ID', 'outcome']])
        self.assertEqual(self.call().reason, 'ID_header_conflict')
        self.fixture()
        self.table(self.paths['sample_submission'], [['identity', 'outcome', 'extra']])
        self.assertEqual(self.call().reason, 'regression_output_header_conflict')

    def test_task_text_header_metadata_row_and_field_bounds_use_original_checkpoint(self):
        for options in (dict(max_task_bytes=16), dict(max_task_lines=2), dict(max_line_bytes=8),
                        dict(max_header_bytes=5), dict(max_columns=1), dict(max_metadata_bytes=16),
                        dict(max_metadata_rows=1), dict(max_metadata_columns=1), dict(max_field_bytes=2)):
            self.fixture()
            with self.subTest(options=options), self.assertRaises(EarlyDeclarationError):
                self.call(limits=replace(DeclarationLimits(), **options))
        self.fixture()
        (self.root / self.paths['train']).write_bytes(b'identity,input,outcome,outcome\n')
        with self.assertRaisesRegex(EarlyDeclarationError, 'invalid_CSV_header'):
            self.call()
        for kwargs in ({'max_task_bytes':65537}, {'max_metadata_rows':True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                DeclarationLimits(**kwargs)

    def test_checkpoint_expiry_propagates_before_IO_and_falsey_callable_is_not_replaced(self):
        self.fixture()
        def expired():
            raise TimeoutError('original preparation deadline')
        with patch.object(Path, 'open', side_effect=AssertionError('IO after expiry')):
            with self.assertRaises(TimeoutError):
                self.call(checkpoint=expired)
        calls = []
        class FalseyCheckpoint:
            def __bool__(self): return False
            def __call__(self): calls.append(True)
        result = self.call(checkpoint=FalseyCheckpoint())
        self.assertTrue(result.ready_for_projection)
        self.assertGreater(len(calls), 10)
        self.assertFalse(result.receipt['new_clock_created'])
        with self.assertRaises(ValueError):
            self.call(checkpoint=None)

    def test_path_escape_symlink_reused_files_and_dictionary_alias_are_rejected(self):
        self.fixture()
        text = self.task.read_text('utf-8')
        for path in ('../outside.csv', 'C:/outside.csv'):
            self.task.write_text(text.replace(self.paths['train'], path), encoding='utf-8')
            with self.subTest(path=path), self.assertRaises(EarlyDeclarationError):
                self.call()
        self.task.write_text(text.replace(self.paths['train'], self.paths['test']), encoding='utf-8')
        self.assertEqual(self.call().reason, 'file_roles_not_distinct')
        self.task.write_text(text.replace('roles.csv', self.paths['train']), encoding='utf-8')
        self.assertEqual(self.call().reason, 'dictionary_reuses_input_table')
        self.fixture()
        original = Path.is_symlink
        with patch.object(Path, 'is_symlink', lambda p: p.name == self.paths['train'] or original(p)):
            with self.assertRaisesRegex(EarlyDeclarationError, 'input_symlink'):
                self.call()

    def test_headers_only_ignore_unread_invalid_feature_target_and_placeholder_rows(self):
        self.fixture()
        for name in self.paths.values():
            path = self.root / name
            header = path.read_bytes().splitlines(keepends=True)[0]
            path.write_bytes(header + b'\xff invalid opaque feature and target cells\n')
        original_import = builtins.__import__
        def no_models_or_API(name, *args, **kwargs):
            if name.startswith(('automl.task_understanding.service', 'automl.infrastructure.llm_gateway',
                                'lightgbm', 'xgboost', 'catboost', 'sklearn')):
                raise AssertionError('Full loader/model/API import: ' + name)
            return original_import(name, *args, **kwargs)
        with patch.object(builtins, '__import__', no_models_or_API):
            result = self.call()
        self.assertTrue(result.ready_for_projection)
        self.assertFalse(result.receipt['feature_rows_loaded'])
        self.assertFalse(result.receipt['target_rows_loaded'])
        self.assertFalse((self.root / 'submission.csv').exists())

    def test_fenced_examples_and_malformed_lists_cannot_manufacture_declarations(self):
        self.fixture(dictionary=False)
        text = self.task.read_text('utf-8')
        self.task.write_text('Example only:\n```text\n' + text + '```\n', encoding='utf-8')
        self.assertEqual(self.call().reason, 'explicit_file_roles_required')
        for value in ('["outcome", "outcome"]', '[true]', '["outcome",', '[]', '[["outcome"]]'):
            self.task.write_text(text.replace('Target: outcome', 'Targets: ' + value), encoding='utf-8')
            with self.subTest(value=value), self.assertRaises(EarlyDeclarationError):
                self.call()


if __name__ == '__main__':
    unittest.main()
