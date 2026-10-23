"""Fixed-grid replay helpers on tiny deterministic arrays; no public reads/fits."""
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from replay_marginal_selection import fixed_grid


class MarginalReplayTests(unittest.TestCase):
    def data(self, fold):
        truth = np.arange(4.)
        task = NS(kind='regression', metric='rmse', greater_is_better=False)
        request = NS(task=task, predictions=[NS(fold_id=fold)])
        predictions = {(name, fold): NS(truth=truth, predicted=truth + delta,
                         probabilities=None, classes=()) for name, delta in [('a', 1.), ('b', -1.), ('c', 4.)]}
        return NS(request=request, predictions=predictions)

    def test_unchanged_pair_grid_can_reject_harmful_third(self):
        result = fixed_grid(self.data('search'), self.data('confirmation'), ['a', 'b', 'c'])
        self.assertEqual(result['ids'], ['a', 'b'])
        self.assertEqual(result['weights'], [.5, .5])
        self.assertEqual(result['mean'], 0.)
        self.assertEqual(result['search'], result['confirmation'])

    def test_three_distinct_slots_are_required(self):
        for ids in [['a', 'b'], ['a', 'b', 'b']]:
            with self.assertRaises(ValueError): fixed_grid(self.data('search'), self.data('confirmation'), ids)

    def test_helper_does_not_modify_prediction_arrays(self):
        a, b = self.data('search'), self.data('confirmation')
        before = a.predictions[('a', 'search')].predicted.copy()
        fixed_grid(a, b, ['a', 'b', 'c'])
        np.testing.assert_array_equal(a.predictions[('a', 'search')].predicted, before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
