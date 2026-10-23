"""Tiny-array tests only: no worker, model fit or API calls."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from automl.search.selection import select_third


class MarginalSelectionTests(unittest.TestCase):
    def setUp(self):
        self.ids = ['a', 'b', 'redundant', 'complementary']
        self.truth = np.array(['0', '1', '0', '1'])
        self.matrices = {k: {'rows': np.arange(4), 'classes': ('0', '1'),
                            'values': np.tile([.6, .4], (4, 1))} for k in self.ids}
        self.matrices['complementary']['values'] = np.eye(2)[self.truth.astype(int)]

    def choose(self, **kwargs):
        return select_third(self.ids, self.matrices, self.truth, kind='classification',
                            metric='macro_f1', greater_is_better=True, classes=('0', '1'), **kwargs)

    def test_complementary_third_wins_and_leaders_preserved(self):
        result = self.choose()
        self.assertEqual(result['selected_ids'], ['a', 'b', 'complementary'])
        self.assertEqual(result['third_slot']['fixed_thirds_score'], 1.)
        self.assertGreater(result['third_slot']['directional_gain'], 0)
        self.assertFalse(result['runtime_enabled'])
        self.assertFalse(result['weights_fitted'])

    def test_original_candidate_order_breaks_ties(self):
        self.matrices['redundant']['values'] = self.matrices['complementary']['values'].copy()
        self.assertEqual(self.choose()['selected_ids'][-1], 'redundant')

    def test_regression_minimizes_metric_not_individual_error(self):
        truth = np.arange(1., 5.)
        values = {k: {'rows': np.arange(4), 'values': truth + 2} for k in self.ids}
        values['complementary']['values'] = truth - 4
        result = select_third(self.ids, values, truth, kind='regression', metric='rmse', greater_is_better=False)
        self.assertEqual(result['selected_ids'][-1], 'complementary')
        self.assertAlmostEqual(result['third_slot']['fixed_thirds_score'], 0.)
        self.assertAlmostEqual(result['third_slot']['directional_gain'], 2.)

    def test_all_harmful_still_preserves_three_slot_rule(self):
        truth = np.arange(1., 5.)
        values = {k: {'rows': np.arange(4), 'values': truth.copy()} for k in self.ids}
        values['redundant']['values'] += 1
        values['complementary']['values'] += 2
        result = select_third(self.ids, values, truth, kind='regression', metric='rmse', greater_is_better=False)
        self.assertEqual(result['selected_ids'], ['a', 'b', 'redundant'])
        self.assertLess(result['third_slot']['directional_gain'], 0)

    def test_inputs_are_not_mutated(self):
        before = deepcopy(self.matrices)
        self.choose()
        for k in self.ids:
            np.testing.assert_array_equal(before[k]['values'], self.matrices[k]['values'])
            np.testing.assert_array_equal(before[k]['rows'], self.matrices[k]['rows'])

    def test_class_order_mismatch_rejected(self):
        self.matrices['redundant']['classes'] = ('1', '0')
        with self.assertRaises(ValueError): self.choose()

    def test_row_order_mismatch_rejected(self):
        self.matrices['redundant']['rows'] = np.arange(4)[::-1]
        with self.assertRaises(ValueError): self.choose()

    def test_duplicate_rows_rejected(self):
        self.matrices['a']['rows'] = np.array([0, 0, 1, 2])
        with self.assertRaises(ValueError): self.choose()

    def test_nonfinite_matrix_rejected(self):
        self.matrices['a']['values'][0, 0] = np.nan
        with self.assertRaises(ValueError): self.choose()

    def test_negative_probability_rejected(self):
        self.matrices['a']['values'][0] = [-.1, 1.1]
        with self.assertRaises(ValueError): self.choose()

    def test_zero_probability_mass_rejected(self):
        self.matrices['a']['values'][0] = 0
        with self.assertRaises(ValueError): self.choose()

    def test_duplicate_candidate_ids_rejected(self):
        self.ids[-1] = self.ids[0]
        with self.assertRaises(ValueError): self.choose()

    def test_too_few_candidates_rejected(self):
        self.ids = self.ids[:2]
        with self.assertRaises(ValueError): self.choose()

    def test_scope_must_be_explicit_supported_declaration(self):
        with self.assertRaises(ValueError): self.choose(scope='independent_private')
        self.assertEqual(self.choose(scope='inner_oof')['scope'], 'inner_oof')

    def test_unknown_truth_class_rejected(self):
        self.truth[0] = '3'
        with self.assertRaises(ValueError): self.choose()


if __name__ == '__main__':
    unittest.main(verbosity=2)
