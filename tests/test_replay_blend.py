"""Adversarial alignment checks for the no-fit probability replay."""
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from replay_blend01 import aligned_probabilities


class BlendReplayTests(unittest.TestCase):
    def write(self, path, probabilities, rows=(2, 0)):
        np.savez(path/'validation_probabilities.npz', probabilities=probabilities,
                 classes=np.array(['b', 'a']), row_position=np.array(rows))
        pd.DataFrame({'row_position': [2, 0], 'y_pred': ['a', 'b']}).to_csv(
            path/'validation_predictions.csv', index=False)

    def test_align_class_columns_and_require_saved_row_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.write(path, np.array([[.1, .9], [.8, .2]]))
            actual = aligned_probabilities(path, np.array([2, 0]), ['a', 'b'])
            np.testing.assert_array_equal(actual, [[.9, .1], [.2, .8]])
            with self.assertRaisesRegex(ValueError, 'row order'):
                aligned_probabilities(path, np.array([0, 2]), ['a', 'b'])

    def test_reject_nonfinite_or_unnormalized_probabilities(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for values in [[[np.nan, .9], [.8, .2]], [[.5, .9], [.8, .2]]]:
                self.write(path, np.array(values))
                with self.assertRaisesRegex(ValueError, 'normalized probabilities'):
                    aligned_probabilities(path, np.array([2, 0]), ['a', 'b'])

    def test_reject_disagreement_with_actual_saved_predictions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.write(path, np.array([[.9, .1], [.8, .2]]))
            with self.assertRaisesRegex(ValueError, 'CSV predictions'):
                aligned_probabilities(path, np.array([2, 0]), ['a', 'b'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
