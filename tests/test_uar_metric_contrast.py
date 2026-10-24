"""Prepared strict objective contrast contracts; no learner or API fixtures."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from automl.contracts.metrics import UnresolvedMetricError
from automl.task_understanding.metric_contract import resolve_metric_spec
from automl.task_understanding.metrics import metric_from_text


class MetricContrastTests(unittest.TestCase):
    def test_russian_explicit_contrast(self):
        value = resolve_metric_spec('Основная метрика: Macro F1, а не Accuracy.',
                                    'multiclass')
        self.assertEqual((value.require_resolved().name, value.direction,
                          value.prediction_kind), ('macro_f1', 'maximize', 'label'))

    def test_english_direct_not(self):
        value = resolve_metric_spec('Primary metric: weighted F1, not Accuracy.',
                                    'classification')
        self.assertEqual(value.require_resolved().name, 'weighted_f1')

    def test_rather_than_regression(self):
        value = resolve_metric_spec('Primary metric: RMSE rather than MAE.',
                                    'regression')
        self.assertEqual((value.require_resolved().name, value.direction,
                          value.prediction_kind), ('rmse', 'minimize', 'value'))

    def test_instead_of_regression_alias(self):
        value = resolve_metric_spec('Main metric: mean absolute error instead of RMSE.',
                                    'regression')
        self.assertEqual(value.require_resolved().name, 'mae')

    def test_longest_metric_alias_spans_are_preserved(self):
        for text, kind, expected in [
            ('Primary metric: root mean squared error, not mean squared error.',
             'regression', 'rmse'),
            ('Primary metric: RMSE rather than root mean squared logarithmic error.',
             'regression', 'rmse'),
            ('Primary metric: balanced accuracy, not Accuracy.',
             'classification', 'balanced_accuracy'),
        ]:
            with self.subTest(text=text):
                self.assertEqual(resolve_metric_spec(text, kind).require_resolved().name,
                                 expected)

    def test_repeated_equivalent_primary_with_multiline_contrast(self):
        value = resolve_metric_spec(
            'Поэтому основной\nметрикой выбран Macro F1, а не Accuracy.\n'
            'Primary metric: Macro F1', 'multiclass')
        self.assertEqual(value.require_resolved().name, 'macro_f1')
        self.assertEqual(len(value.evidence), 2)

    def test_negation_only_never_creates_a_default(self):
        for text, kind in [
            ('Primary metric: not Accuracy', 'classification'),
            ('Primary metric: rather than MAE', 'regression'),
            ('Main metric: instead of RMSE', 'regression'),
            ('Основная метрика: а не Macro F1', 'multiclass'),
        ]:
            with self.subTest(text=text):
                value = resolve_metric_spec(text, kind)
                self.assertEqual(value.status, 'unsupported')
                self.assertIsNone(value.name)
                with self.assertRaises(UnresolvedMetricError):
                    value.require_resolved()

    def test_not_only_but_also_keeps_both_objectives(self):
        for text in [
            'Primary metric: not only Accuracy but also Macro F1',
            'Primary metric: not just Accuracy but also Macro F1',
            'Основная метрика: не только Accuracy, но и Macro F1',
        ]:
            with self.subTest(text=text):
                self.assertEqual(resolve_metric_spec(text, 'multiclass').status,
                                 'ambiguous')

    def test_ambiguous_objective_list_is_not_reinterpreted(self):
        for text in [
            'Primary metric: RMSE and MAE',
            'Primary metric: RMSE, not MAE or MSE',
            'Primary metric: RMSE rather than MAE and MSE',
        ]:
            with self.subTest(text=text):
                value = resolve_metric_spec(text, 'regression')
                self.assertEqual(value.status, 'ambiguous')
                with self.assertRaises(UnresolvedMetricError):
                    value.require_resolved()

    def test_independent_primary_sources_still_conflict(self):
        value = resolve_metric_spec(
            'Primary metric: Macro F1, not Accuracy\nMain metric: Accuracy',
            'classification')
        self.assertEqual(value.status, 'ambiguous')

    def test_affirmed_and_negated_same_name_stay_unresolved(self):
        for text in [
            'Primary metric: RMSE, not RMSE',
            'Primary metric: RMSE\nMain metric: MAE, not RMSE',
            'Primary metric: RMSE, not not MAE',
            'Primary metric: RMSE rather than instead of MAE',
        ]:
            with self.subTest(text=text):
                value = resolve_metric_spec(text, 'regression')
                self.assertEqual(value.status, 'ambiguous')
                self.assertIsNone(value.name)

    def test_unsupported_primary_does_not_use_negated_or_diagnostic_metric(self):
        for text, kind in [
            ('Primary metric: custom_cost rather than RMSE\nDiagnostic metric: MAE',
             'regression'),
            ('Primary metric: AUC, not Accuracy', 'binary'),
        ]:
            with self.subTest(text=text):
                value = resolve_metric_spec(text, kind)
                self.assertEqual(value.status, 'unsupported')
                with self.assertRaises(UnresolvedMetricError):
                    value.require_resolved()

    def test_nonprimary_contrast_is_not_new_authority(self):
        for text in ['Metric: RMSE, not MAE', 'RMSE rather than MAE']:
            with self.subTest(text=text):
                self.assertEqual(resolve_metric_spec(text, 'regression').status,
                                 'ambiguous')

    def test_legacy_parser_path_is_unchanged(self):
        self.assertEqual(metric_from_text('Primary metric: RMSE rather than MAE',
                                          'regression'), 'rmse')
        self.assertEqual(metric_from_text('Primary metric: Macro F1, а не Accuracy',
                                          'classification'), 'macro_f1')
        self.assertEqual(metric_from_text('Predict the target.', 'regression'),
                         'rmse')

    def test_probability_shape_and_direction_remain_typed(self):
        value = resolve_metric_spec('Primary metric: log loss instead of Accuracy',
                                    'multiclass', class_count=3)
        self.assertEqual((value.require_resolved().name, value.direction,
                          value.prediction_kind),
                         ('log_loss', 'minimize', 'probability_matrix'))
        unknown = resolve_metric_spec('Primary metric: log loss, not Accuracy',
                                      'classification')
        self.assertEqual(unknown.status, 'unknown')

    def test_existing_evidence_bound_is_not_removed(self):
        value = resolve_metric_spec('\n'.join(['Primary metric: RMSE, not MAE'] * 9),
                                    'regression')
        self.assertEqual(value.status, 'ambiguous')
        self.assertEqual(len(value.evidence), 8)


if __name__ == '__main__':
    unittest.main()
