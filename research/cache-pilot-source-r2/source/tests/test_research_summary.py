"""Artifact alignment and metric gates, without fitting models."""
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from summarize_research import paired_gate, partition, verify_predictions


class ResearchSummaryTests(unittest.TestCase):
    def test_saved_row_order_and_source_labels_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            spec = {'kind': 'regression', 'metric': 'rmse', 'target': 'y'}
            source = pd.DataFrame({'y': [10., 20., 30.]})
            frame = pd.DataFrame({'row_position': [2, 0], 'y_true': [30., 10.], 'y_pred': [29., 11.]})
            path = directory/'validation_predictions.csv'
            frame.to_csv(path, index=False)
            record = {'metrics': {'rmse': 1.}}
            self.assertEqual(verify_predictions(record, directory, spec, source, np.array([2, 0]))['value'], 1.)
            with self.assertRaisesRegex(ValueError, 'row order'):
                verify_predictions(record, directory, spec, source, np.array([0, 2]))
            frame.loc[0, 'y_true'] = 31.
            frame.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, 'source regression'):
                verify_predictions(record, directory, spec, source, np.array([2, 0]))

    def test_saved_partition_rejects_group_leakage_and_future_fitting(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'split.npz'
            np.savez(path, train=np.array([0, 1]), validation=np.array([2]))
            with self.assertRaisesRegex(ValueError, 'feature groups overlap'):
                partition(path, 3, hashes=np.array([1, 2, 1]))
            with self.assertRaisesRegex(ValueError, 'chronology'):
                partition(path, 3, periods=np.array([1, 3, 2]))
            tr, va = partition(path, 3, periods=np.array([1, 1, 2]))
            self.assertEqual(tr.tolist(), [0, 1])
            self.assertEqual(va.tolist(), [2])

    def test_primary_gain_does_not_override_supported_class_loss(self):
        spec = {'kind': 'classification', 'classes': ['common', 'rare', 'other'], 'greater_is_better': True}
        control = {'value': .5, 'per_class_f1': dict(common=.5, rare=.5, other=.5)}
        candidate = {'value': .56, 'per_class_f1': dict(common=.48, rare=.6, other=.6)}
        result = paired_gate(control, candidate, spec, dict(common=100, rare=10, other=200))
        self.assertTrue(result['primary_improved'])
        self.assertGreater(result['gain_without_rarest_class'], 0)
        self.assertFalse(result['passed'])
        self.assertIn('common', result['supported_class_violations'])

    def test_rarest_only_gain_is_insufficient_and_rmse_direction_is_correct(self):
        spec = {'kind': 'classification', 'classes': ['common', 'rare'], 'greater_is_better': True}
        control = {'value': .5, 'per_class_f1': dict(common=.5, rare=.5)}
        candidate = {'value': .6, 'per_class_f1': dict(common=.5, rare=.7)}
        self.assertFalse(paired_gate(control, candidate, spec, dict(common=100, rare=10))['passed'])
        self.assertTrue(paired_gate({'value': 3.}, {'value': 2.}, {'kind': 'regression', 'greater_is_better': False})['passed'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
