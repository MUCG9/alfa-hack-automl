"""Trusted feature compilation: schema, quoted columns and real row invariants."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
sys.path.insert(0, str(ROOT/'src'))
import numpy as np
import pandas as pd
from propose_feature_dsl import compile_features
from automl.execution.feature_engineering.transforms import feature_transform


class FeatureDSLTests(unittest.TestCase):
    def test_unknown_operations_columns_and_calendar_constants_are_rejected(self):
        for plan in [[{'op': '__import__', 'columns': ['x']}],
                     [{'op': 'ratio', 'columns': ['x', 'target']}],
                     [{'op': 'difference', 'columns': ['x', 'y'], 'year': 2020}],
                     [{'op': 'signed_log', 'columns': 'x'}], []]:
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                compile_features(plan, ['x', 'y'])

    def test_all_operations_keep_original_columns_rows_and_rowwise_values(self):
        train = pd.DataFrame({'x': [0., -2., np.nan, 359., 1.]*4,
                              'y': [0., 3., 1., 1., np.nan]*4}, index=np.arange(100, 120))
        plan = [{'op': op, 'columns': ['x'] if op in {'missing', 'signed_log'} else ['x', 'y']}
                for op in ['signed_log', 'difference', 'product', 'ratio', 'log_ratio', 'missing', 'angle_delta']]
        code = compile_features(plan, list(train))
        first, second = feature_transform(code, train, train.iloc[:3], ('id', 'target'))
        pd.testing.assert_frame_equal(first[list(train)], train)
        self.assertEqual(len(first.columns), 9)
        self.assertTrue(first.index.equals(train.index))
        self.assertFalse(np.isinf(first.select_dtypes('number').to_numpy()).any())
        self.assertAlmostEqual(first.loc[103, '__dsl_feature_06'], -2*np.pi/180)
        pd.testing.assert_frame_equal(second, first.iloc[:3])
        infinite=pd.DataFrame({'x':[np.inf,-np.inf],'y':[1.,2.]})
        with np.errstate(invalid='ignore'):
            transformed,_=feature_transform(code,infinite,infinite)
        self.assertFalse(np.isinf(transformed.iloc[:,2:].to_numpy()).any())

    def test_quoted_source_names_cannot_inject_python(self):
        name = "x'); __import__('os').system('false'); #"
        train = pd.DataFrame({name: [1., 2., 3.]})
        code = compile_features([{'op': 'signed_log', 'columns': [name]}], [name])
        first, _ = feature_transform(code, train, train.iloc[:1])
        np.testing.assert_allclose(first['__dsl_feature_00'], np.log1p([1., 2., 3.]))

    def test_limits_duplicates_and_original_name_collisions_fail_closed(self):
        item = {'op': 'product', 'columns': ['x', 'y']}
        for plan, columns in [([item]*13, ['x', 'y']),
                              ([item, {'op': 'product', 'columns': ['y', 'x']}], ['x', 'y']),
                              ([item], ['x', 'y', '__dsl_feature_00'])]:
            with self.subTest(plan=plan), self.assertRaises(ValueError): compile_features(plan, columns)
        with self.assertRaises(ValueError): compile_features([item],['x','y'],['x','y','__dsl_feature_00'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
