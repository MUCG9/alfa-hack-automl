"""No model fitting: feature scope isolation, row semantics and resource bounds."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

import numpy as np
import pandas as pd

from automl.execution.feature_engineering.transforms import generic_features


def fixture():
    rng = np.random.default_rng(170)
    train = pd.DataFrame({
        'measurement': rng.normal(size=120),
        'quantity': rng.lognormal(1, 2, size=120),
        'category': np.tile(['north', 'south', None], 40),
        'description': np.tile(['a sentence with words', 'another longer observation', ''], 40),
    }, index=np.arange(120) * 3 + 8)
    train.loc[train.index[::9], 'measurement'] = np.nan
    test = train.iloc[-9:].copy()
    test.index = np.arange(9) + 5000
    return train, test, np.arange(90)


class BroadFeatureTests(unittest.TestCase):
    def test_broad_is_real_features_and_preserves_sources_and_schema(self):
        train, test, rows = fixture()
        before, test_before = train.copy(deep=True), test.copy(deep=True)
        transformed, query = generic_features(train, test, rows, 'broad')
        added = [column for column in transformed if column not in train]
        self.assertGreater(len(added), 2, 'broad must not silently act as the no-op')
        self.assertTrue(any(transformed[column].nunique() > 1 for column in added))
        self.assertTrue(any('product' in column for column in added))
        self.assertEqual(list(transformed), list(query))
        pd.testing.assert_frame_equal(transformed[list(train)], before)
        pd.testing.assert_frame_equal(query[list(test)], test_before)
        pd.testing.assert_frame_equal(train, before)
        pd.testing.assert_frame_equal(test, test_before)

    def test_outer_feature_poisoning_cannot_change_fitting_features_or_plan(self):
        train, test, rows = fixture()
        original, _ = generic_features(train, test, rows, 'broad')
        poison = train.copy()
        # Change full-column dtype using only values outside fitting rows.
        poison['measurement'] = poison.measurement.astype(object)
        poison['quantity'] = poison.quantity.astype(object)
        poison.iloc[90:, 0] = 'malformed external value'
        poison.iloc[90:, 1] = '-9999999999999999999999'
        poison.iloc[90:, 2] = 'never observed category'
        poison.iloc[90:, 3] = 'X' * 1000
        poisoned_test = test.copy()
        poisoned_test['description'] = ''
        transformed, _ = generic_features(poison, poisoned_test, rows, 'broad')
        added = [column for column in original if column not in train]
        self.assertEqual(list(original), list(transformed))
        pd.testing.assert_frame_equal(original.iloc[rows][added], transformed.iloc[rows][added])

    def test_query_batches_and_order_do_not_affect_any_derived_value(self):
        train, test, rows = fixture()
        _, all_rows = generic_features(train, test, rows, 'broad')
        order = [7, 1, 5]
        _, subset = generic_features(train, test.iloc[order], rows, 'broad')
        pd.testing.assert_frame_equal(all_rows.iloc[order], subset)
        _, empty = generic_features(train, test.iloc[:0], rows, 'broad')
        self.assertEqual(list(empty), list(all_rows))
        self.assertEqual(len(empty), 0)

    def test_derived_values_are_finite_for_extreme_and_missing_queries(self):
        train, test, rows = fixture()
        test['measurement'] = [np.inf, -np.inf, np.nan, 1e308, -1e308, 0, 1e-300, -1e-300, 3]
        test['quantity'] = [0, np.inf, np.nan, 1e308, -1e308, 0, 1e-300, -1e-300, 3]
        transformed, query = generic_features(train, test, rows, 'broad')
        added = [column for column in transformed if column not in train]
        for result in [transformed, query]:
            self.assertTrue(np.isfinite(result[added].to_numpy()).all())
            self.assertTrue(all(result[column].dtype == np.dtype('float32') for column in added))
        # Finite guarantees apply to derived columns; raw infinities survive.
        self.assertTrue(np.isinf(query.measurement.iloc[0]))

    def test_wide_inputs_remain_bounded_without_removing_raw_columns(self):
        rng = np.random.default_rng(12)
        train = pd.DataFrame(rng.normal(size=(60, 200)), columns=[f'column_{i}' for i in range(200)])
        train.iloc[::5, :20] = np.nan
        for number in range(4):
            train[f'words_{number}'] = 'several words in a long observation'
        query = train.iloc[:4].copy()
        transformed, test = generic_features(train, query, np.arange(45), 'broad')
        additions = len(transformed.columns) - len(train.columns)
        self.assertLessEqual(additions, 128)
        self.assertGreater(additions, 64)
        self.assertTrue(transformed.columns.is_unique)
        self.assertEqual(list(transformed), list(test))
        pd.testing.assert_frame_equal(transformed[list(train)], train)

    def test_name_collisions_fail_before_overwriting_any_original_values(self):
        train, test, rows = fixture()
        for mode, name in [('missing', '__missing_measurement'),
                           ('both', '__missing_measurement'),
                           ('skew', '__signed_log_quantity'),
                           ('broad', '__broad_row_missing_count')]:
            source, query = train.copy(), test.copy()
            # Guarantee a highly skewed fitting distribution for the legacy mode.
            source['quantity'] = 0.
            source.iloc[2, source.columns.get_loc('quantity')] = 1000000.
            source[name] = np.arange(len(source)) + 1000
            query[name] = np.arange(len(query)) + 2000
            before = source.copy(deep=True)
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'collision'):
                generic_features(source, query, rows, mode)
            pd.testing.assert_frame_equal(source, before)

    def test_unknown_modes_and_invalid_scopes_fail_closed(self):
        train, test, rows = fixture()
        for mode in ['broadd', '', None, [], 1]:
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'mode'):
                generic_features(train, test, rows, mode)
        for invalid in [[], [0, 0], [-1], [len(train)], [1.5], [True, False]]:
            with self.subTest(rows=invalid), self.assertRaisesRegex(ValueError, 'Fitting rows'):
                generic_features(train, test, invalid, 'broad')
        with self.assertRaisesRegex(ValueError, 'schema'):
            generic_features(train, test.rename(columns={'quantity': 'changed'}), rows, 'broad')

    def test_none_remains_identity_and_deterministic_repeats_match(self):
        train, test, rows = fixture()
        raw_train, raw_test = generic_features(train, test, rows, 'none')
        self.assertIs(raw_train, train)
        self.assertIs(raw_test, test)
        first = generic_features(train, test, rows, 'broad')
        second = generic_features(train, test, rows[::-1], 'broad')
        for a, b in zip(first, second):
            pd.testing.assert_frame_equal(a, b)


if __name__ == '__main__':
    unittest.main(verbosity=2)
