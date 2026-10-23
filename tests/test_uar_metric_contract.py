"""Prepared UAR-v1 objective contracts; no learner or LLM required."""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from automl.contracts.metrics import MetricSpec, UnresolvedMetricError
from automl.task_understanding.metric_contract import resolve_metric_spec


class MetricContractTests(unittest.TestCase):
    def test_no_missing_metric_default(self):
        for kind in ['regression', 'classification']:
            value = resolve_metric_spec('Predict the target.', kind)
            self.assertEqual(value.status, 'unknown')
            self.assertIsNone(value.name)
            with self.assertRaises(UnresolvedMetricError):
                value.require_resolved()

    def test_primary_overrides_diagnostics(self):
        value = resolve_metric_spec('Primary metric: RMSE\nDiagnostic metric: MAE', 'regression')
        self.assertEqual(value.require_resolved().name, 'rmse')

    def test_conflicting_primary_objectives(self):
        value = resolve_metric_spec('Primary metric: RMSE\nMain metric: MAE', 'regression')
        self.assertEqual(value.status, 'ambiguous')

    def test_explicit_unknown_does_not_use_diagnostic(self):
        value = resolve_metric_spec('Primary metric: custom_cost\nDiagnostic RMSE', 'regression')
        self.assertEqual(value.status, 'unsupported')
        for objective in ['PR AUC', 'precision recall AUC', 'AUC']:
            self.assertEqual(resolve_metric_spec('Metric: ' + objective,
                                                'binary').status, 'unsupported')

    def test_diagnostics_alone_are_not_a_primary(self):
        value = resolve_metric_spec('Diagnostic metric: RMSE', 'regression')
        self.assertEqual(value.status, 'unknown')

    def test_metric_direction_and_metric_input(self):
        regression = resolve_metric_spec('Метрика: MAE', 'regression')
        self.assertEqual((regression.name, regression.direction, regression.prediction_kind),
                         ('mae', 'minimize', 'value'))
        labels = resolve_metric_spec('Macro F1', 'multiclass', class_count=3)
        self.assertEqual((labels.name, labels.prediction_kind), ('macro_f1', 'label'))
        self.assertEqual(resolve_metric_spec('Metric: balanced accuracy',
                                            'classification').name, 'balanced_accuracy')
        for alias in ['Root-Mean-Squared-Error', 'root_mean_squared_error']:
            self.assertEqual(resolve_metric_spec('Metric: ' + alias,
                                                'regression').name, 'rmse')
        for alias in ['root mean squared logarithmic error',
                      'root_mean_squared_logarithmic_error']:
            self.assertEqual(resolve_metric_spec('Metric: ' + alias,
                                                'regression').name, 'rmsle')

    def test_binary_vs_multiclass_probability_inputs(self):
        binary = resolve_metric_spec('Metric: logloss', 'binary', class_count=2)
        multiclass = resolve_metric_spec('Metric: logloss', 'multiclass', class_count=3)
        self.assertEqual(binary.prediction_kind, 'probability')
        self.assertEqual(multiclass.prediction_kind, 'probability_matrix')
        self.assertEqual(resolve_metric_spec('Metric: log loss',
                                             'multiclass').prediction_kind,
                         'probability_matrix')
        self.assertEqual(resolve_metric_spec('Metric: log loss',
                                             'classification').status, 'unknown')
        with self.assertRaises(ValueError):
            resolve_metric_spec('Metric: log loss', 'binary', class_count=3)

    def test_ambiguous_named_metrics(self):
        self.assertEqual(resolve_metric_spec('RMSE and MAE', 'regression').status, 'ambiguous')
        self.assertEqual(resolve_metric_spec('balanced accuracy and accuracy',
                                             'classification').status, 'ambiguous')

    def test_unresolved_cannot_smuggle_a_default(self):
        with self.assertRaises(ValueError):
            MetricSpec('rmse', 'minimize', 'value', 'unknown', 'test')

    def test_resolved_direction_cannot_be_changed(self):
        with self.assertRaises(ValueError):
            MetricSpec('rmse', 'maximize', 'value', 'resolved', 'test')

    def test_task_kind_does_not_come_from_target_name(self):
        self.assertEqual(resolve_metric_spec('Metric: MAE', 'regression').name, 'mae')
        with self.assertRaises(ValueError):
            resolve_metric_spec('RMSE', 'arbitrary_target_name')

    def test_json_metadata_keeps_unknown_unknown(self):
        value = resolve_metric_spec('', 'classification').to_dict()
        self.assertEqual(value['status'], 'unknown')
        self.assertIsNone(value['name'])


if __name__ == '__main__':
    unittest.main()
