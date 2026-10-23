"""Exactly-once coverage and pooled-score semantics without model fitting."""
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from verify_blend_cv import check_coverage, measured


class BlendCVTests(unittest.TestCase):
    def test_require_exactly_once_validation_and_complement_fitting(self):
        splits = [(np.array([1, 2]), np.array([0])),
                  (np.array([0, 2]), np.array([1])),
                  (np.array([0, 1]), np.array([2]))]
        check_coverage(splits, 3)
        with self.assertRaisesRegex(ValueError, 'exactly once'):
            check_coverage([splits[0], splits[1], splits[1]], 3)
        with self.assertRaisesRegex(ValueError, 'complement'):
            check_coverage([(np.array([1]), np.array([0]))], 3)

    def test_fold_mean_is_not_pooled_macro_f1(self):
        truth = [['a'], ['b'], ['a', 'a', 'b', 'b']]
        predictions = [['a'], ['b'], ['a', 'a', 'a', 'a']]
        scores = [measured(y, p, ['a', 'b'])['value'] for y, p in zip(truth, predictions)]
        pooled = measured(sum(truth, []), sum(predictions, []), ['a', 'b'])['value']
        self.assertNotAlmostEqual(float(np.mean(scores)), pooled)


if __name__ == '__main__':
    unittest.main(verbosity=2)
