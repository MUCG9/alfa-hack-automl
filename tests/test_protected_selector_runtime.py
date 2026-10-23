"""FE-02 runtime selection contract with mocked teachers; no model fits."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

import numpy as np
import pandas as pd
from automl.execution.feature_engineering.selection import select_features, validate_selection
from automl.execution.model_adapters.registry import effective_parameters
from automl.search.policy import normalize, signature

MODULE = 'automl.execution.feature_engineering.selection'


def fixture():
    train = pd.DataFrame({
        'raw_b': [1., 2., 3., 4.], 'derived_low': [4., 3., 2., 1.],
        'raw_a': [3., 1., 2., 4.], 'derived_high': [7., 8., 6., 9.],
        'derived_mid': [4., 8., 2., 6.]}, index=[9, 3, 8, 1])
    test = train.iloc[[2, 0]].copy()
    y = pd.Series(['low', 'high', 'low', 'high'], index=train.index, name='target')
    return train, test, y, np.array([3, 0]), np.array([.5, 1.5])


class ProtectedRuntimeTests(unittest.TestCase):
    def invoke(self, protect=True, protected=('raw_a', 'raw_b'), **overrides):
        train, test, y, rows, weights = fixture()
        params = dict(feature_selection_top_k=2, seed=19,
                      feature_selection_protect_original=protect, **overrides)
        before_train, before_test, before_y = train.copy(), test.copy(), y.copy()
        teacher = Mock(feature_importances_=np.array([0., 1., 0., 8., 5.]))
        with patch(MODULE+'.create_model', return_value=teacher) as create, \
             patch(MODULE+'.prepare_frames', return_value=(train.copy(), test.copy(), ['raw_a'])) as prepare:
            first, second, info = select_features(train, test, y, rows, 'classification',
                2, params, weights, protected_columns=protected)
        pd.testing.assert_frame_equal(train, before_train)
        pd.testing.assert_frame_equal(test, before_test)
        pd.testing.assert_series_equal(y, before_y)
        return first, second, info, teacher, create, prepare

    def test_union_preserves_originals_and_ordinary_ranked_features_in_input_order(self):
        train, test, *_ = fixture()
        first, second, info, *_ = self.invoke()
        columns = ['raw_b', 'raw_a', 'derived_high', 'derived_mid']
        pd.testing.assert_frame_equal(first, train[columns])
        pd.testing.assert_frame_equal(second, test[columns])
        self.assertEqual(info['protected_columns'], ['raw_b', 'raw_a'])
        self.assertEqual(info['teacher_selected_columns'], ['derived_high', 'derived_mid'])
        self.assertEqual(info['selected_columns'], columns)
        self.assertEqual(info['method'], 'union_original_top_k')
        self.assertTrue(info['teacher_fitted'])
        self.assertGreaterEqual(info['selector_seconds'], 0.)

    def test_teacher_receives_only_actual_fitting_rows_targets_and_identical_weights(self):
        train, _, y, rows, weights = fixture()
        _, _, info, teacher, create, prepare = self.invoke()
        arguments, kwargs = teacher.fit.call_args
        pd.testing.assert_frame_equal(arguments[0], train.iloc[rows])
        pd.testing.assert_series_equal(arguments[1], y.iloc[rows])
        np.testing.assert_array_equal(kwargs['sample_weight'], weights)
        self.assertEqual(kwargs['cat_features'], ['raw_a'])
        self.assertNotIn('target', arguments[0])
        self.assertEqual(info['fitting_rows'], len(rows))
        np.testing.assert_array_equal(prepare.call_args.args[-1], rows)
        self.assertEqual(create.call_args.args[1:], ('classification', 2, 100))
        self.assertEqual(create.call_args.args[0]['params']['depth'], 5)
        self.assertEqual(create.call_args.args[0]['params']['seed'], 19)

    def test_teacher_delegation_preserves_weight_object_identity(self):
        train, test, y, rows, weights = fixture()
        teacher = Mock(feature_importances_=np.arange(5))
        with patch(MODULE+'.create_model', return_value=teacher), \
             patch(MODULE+'.prepare_frames', return_value=(train, test, [])):
            select_features(train, test, y, rows, 'regression', 1,
                {'feature_selection_top_k': 2, 'feature_selection_protect_original': True},
                weights, protected_columns=['raw_a', 'raw_b'])
        self.assertIs(teacher.fit.call_args.kwargs['sample_weight'], weights)

    def test_default_and_explicit_false_keep_ordinary_top_k_algorithm(self):
        train, test, *_ = fixture()
        first, second, info, *_ = self.invoke(protect=False, protected=('missing_ignored',))
        pd.testing.assert_frame_equal(first, train[['derived_high', 'derived_mid']])
        pd.testing.assert_frame_equal(second, test[['derived_high', 'derived_mid']])
        self.assertEqual(info['method'], 'catboost_importance')
        self.assertNotIn('protected_columns', info)

    def test_all_original_view_skips_teacher_even_above_top_k(self):
        train, test, y, rows, weights = fixture()
        with patch(MODULE+'.create_model', side_effect=AssertionError('teacher created')), \
             patch(MODULE+'.prepare_frames', side_effect=AssertionError('teacher preparation')):
            first, second, info = select_features(train, test, y, rows, 'classification', 1,
                {'feature_selection_top_k': 2, 'feature_selection_protect_original': True},
                weights, protected_columns=list(train.columns))
        pd.testing.assert_frame_equal(first, train)
        pd.testing.assert_frame_equal(second, test)
        self.assertEqual(info['status'], 'all_original_protected')
        self.assertFalse(info['teacher_fitted'])

    def test_top_k_at_least_input_columns_skips_teacher_and_keeps_derived(self):
        train, test, y, rows, weights = fixture()
        with patch(MODULE+'.create_model', side_effect=AssertionError('teacher created')):
            first, second, info = select_features(train, test, y, rows, 'classification', 1,
                {'feature_selection_top_k': 5, 'feature_selection_protect_original': True},
                weights, protected_columns=['raw_a'])
        pd.testing.assert_frame_equal(first, train)
        pd.testing.assert_frame_equal(second, test)
        self.assertEqual(info['status'], 'unneeded')
        self.assertFalse(info['teacher_fitted'])

    def test_missing_protected_column_in_either_frame_fails_before_teacher(self):
        train, test, y, rows, weights = fixture()
        for missing_train in (False, True):
            with self.subTest(missing_train=missing_train), \
                 patch(MODULE+'.create_model', side_effect=AssertionError('teacher created')), \
                 self.assertRaisesRegex(ValueError, 'Protected original'):
                select_features(train.drop(columns=['raw_a']) if missing_train else train,
                    test if missing_train else test.drop(columns=['raw_a']), y, rows,
                    'classification', 1,
                    {'feature_selection_top_k': 2, 'feature_selection_protect_original': True},
                    weights, protected_columns=['raw_a'])

    def test_old_positional_caller_remains_valid_and_disabled_is_identity(self):
        train, test, y, rows, weights = fixture()
        with patch(MODULE+'.create_model', side_effect=AssertionError('teacher created')):
            first, second, info = select_features(train, test, y, rows, 'classification', 1, {}, weights)
        self.assertIs(first, train)
        self.assertIs(second, test)
        self.assertEqual(info['status'], 'disabled')
        self.assertFalse(info['teacher_fitted'])

    def test_flag_is_strict_boolean_and_requires_positive_top_k(self):
        for flag in (1, 0, 'true', None, [], {}):
            for validator in (validate_selection,
                              lambda params: normalize({'engine': 'lightgbm', 'params': params})):
                with self.subTest(flag=flag, validator=validator), self.assertRaises(ValueError):
                    validator({'feature_selection_top_k': 2,
                               'feature_selection_protect_original': flag})
        for validator in (validate_selection,
                          lambda params: normalize({'engine': 'lightgbm', 'params': params})):
            with self.assertRaisesRegex(ValueError, 'positive'):
                validator({'feature_selection_protect_original': True})

    def test_registry_retains_flag_and_recipe_signature_distinguishes_policy(self):
        original = {'feature_selection_top_k': 2, 'feature_selection_protect_original': True}
        for engine in ('lightgbm', 'catboost', 'xgboost', 'extra_trees'):
            self.assertEqual(effective_parameters(engine, original), original)
        recipe = normalize({'engine': 'lightgbm', 'params': original})
        self.assertTrue(recipe['params']['feature_selection_protect_original'])
        ordinary = normalize({'engine': 'lightgbm', 'params': {'feature_selection_top_k': 2}})
        self.assertNotEqual(signature(recipe), signature(ordinary))
        self.assertNotIn('feature_selection_protect_original', ordinary['params'])

    def test_inheritance_preserves_policy_and_rejects_disabling_only_top_k(self):
        best = normalize({'engine': 'lightgbm', 'params': {
            'feature_selection_top_k': 2, 'feature_selection_protect_original': True}})
        inherited = normalize({'engine': 'lightgbm', 'params': {'num_leaves': 40}}, best)
        self.assertTrue(inherited['params']['feature_selection_protect_original'])
        with self.assertRaisesRegex(ValueError, 'positive'):
            normalize({'engine': 'lightgbm', 'params': {'feature_selection_top_k': 0}}, best)
        disabled = normalize({'engine': 'lightgbm', 'params': {
            'feature_selection_top_k': 0, 'feature_selection_protect_original': False}}, best)
        self.assertFalse(disabled['params']['feature_selection_protect_original'])

    def test_generic_feature_modes_are_validated_before_runtime(self):
        for mode in ('none', 'missing', 'skew', 'both', 'broad'):
            self.assertEqual(normalize({'engine': 'lightgbm', 'params': {
                'generic_features': mode}})['params']['generic_features'], mode)
        for mode in ('all', 'Broad', '', None, True, [], {}):
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'generic_features'):
                normalize({'engine': 'lightgbm', 'params': {'generic_features': mode}})
        invalid_best = {'engine': 'lightgbm', 'params': {'generic_features': 'unknown'}}
        with self.assertRaisesRegex(ValueError, 'generic_features'):
            normalize({'engine': 'lightgbm', 'params': {}}, invalid_best)


if __name__ == '__main__':
    unittest.main(verbosity=2)
