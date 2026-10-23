"""FE-02 treatment contract without model fitting or a frozen-worker import."""
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from protected_selection_worker import protected_union


class ProtectedSelectionTests(unittest.TestCase):
    def test_original_only_view_skips_teacher_without_changing_rows(self):
        frame = pd.DataFrame({'raw': [1, 2]}, index=[9, 4])
        def forbidden_teacher(*args):
            raise AssertionError('No ranking needed when every feature is protected')
        first, second, record = protected_union(forbidden_teacher, ['raw'], frame, frame,
            pd.Series([0, 1]), np.array([0]), 'classification', 1, {'feature_selection_top_k': 32})
        pd.testing.assert_frame_equal(first, frame)
        pd.testing.assert_frame_equal(second, frame)
        self.assertFalse(record['teacher_fitted'])

    def test_union_keeps_raw_and_ranked_generated_features_in_input_order(self):
        train = pd.DataFrame({'raw': [1., 2., 3.], 'drop': [4., 5., 6.], 'keep': [7., 8., 9.]}, index=[8, 1, 6])
        test = train.iloc[:1].copy()
        labels = pd.Series(['a', 'a', 'b'])
        rows = np.array([0, 2]); weights = np.array([.5, 1.5])
        def teacher(x, queries, y, fit_rows, kind, threads, params, passed_weights):
            self.assertIs(fit_rows, rows)
            self.assertIs(passed_weights, weights)
            self.assertIs(y, labels)
            return x[['keep']], queries[['keep']], {'status': 'selected', 'input_columns': 3}
        first, second, record = protected_union(teacher, ['raw'], train, test, labels, rows,
            'classification', 1, {'feature_selection_top_k': 32}, weights)
        pd.testing.assert_frame_equal(first, train[['raw', 'keep']])
        pd.testing.assert_frame_equal(second, test[['raw', 'keep']])
        self.assertEqual(record['teacher_selected_columns'], ['keep'])
        self.assertTrue(record['teacher_fitted'])

    def test_missing_original_feature_fails_before_teacher(self):
        frame = pd.DataFrame({'derived': [1.]})
        with self.assertRaisesRegex(ValueError, 'Protected original'):
            protected_union(None, ['raw'], frame, frame, None, np.array([0]),
                            'classification', 1, {'feature_selection_top_k': 32})


if __name__ == '__main__':
    unittest.main(verbosity=2)
