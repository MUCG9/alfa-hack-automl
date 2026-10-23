"""Prepared METH02 tiny REAL-adapter fixtures; not executed during preparation.

Future execution is charged inside the same setup900/common10800 clock.  These
are tool contracts, not public quality results.  No public data or API is used.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import socket
import sys
import unittest
from unittest import mock

sys.dont_write_bytecode = True
WORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK / 'm3dev' / 'src'))

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge, LogisticRegression
from automl.execution.model_adapters.linear_text import linear_text_fit


REG = dict(engine='linear_text', feature_code='', params=dict(generic_features='none'))
CLF = dict(engine='linear_text', feature_code='', params=dict(generic_features='none',
    text_classifier='logistic', text_C=1, class_weight_power=.5))
FITTING_CALLBACKS = []


class TabularLinearContracts(unittest.TestCase):
    def setUp(self):
        self.network_calls = []
        def forbidden(*args, **kwargs):
            self.network_calls.append(True)
            raise AssertionError('No network is allowed in synthetic tool fixtures')
        self.network_patches = [mock.patch.object(socket, name, side_effect=forbidden)
            for name in ['create_connection', 'getaddrinfo']]
        self.network_patches += [mock.patch.object(socket.socket, name, side_effect=forbidden)
            for name in ['connect', 'connect_ex', 'sendto']]
        for patch in self.network_patches: patch.start()

    def tearDown(self):
        for patch in reversed(self.network_patches): patch.stop()
        self.assertEqual(self.network_calls, [])

    def frames(self):
        # Only 0..11 fit.  The outside category and magnitudes are deliberate.
        fitting = pd.DataFrame({'number': np.arange(12, dtype=float),
            'empty': np.full(12, np.nan), 'category': ['left']*6+['right']*6})
        outside = pd.DataFrame({'number': [1e6, -1e6, np.inf],
            'empty': [99., -99., 45.], 'category': ['outside']*3})
        train = pd.concat([fitting, outside], ignore_index=True)
        test = pd.DataFrame({'number': [1., 9., 4.], 'empty': [np.nan]*3,
            'category': ['never-seen', 'right', 'left']})
        return train, test, np.arange(12), np.array([14, 12, 13])

    def run_adapter(self, kind, train=None, test=None, y=None, spec_extra=None):
        raw, raw_test, tr, va = self.frames()
        train = raw if train is None else train
        test = raw_test if test is None else test
        if y is None:
            y = pd.Series(np.arange(15, dtype=float)*2) if kind=='regression' else pd.Series(
                ['zeta']*6+['alpha']*3+['middle']*3+['alpha','middle','zeta'])
        spec = dict(kind=kind, metric='rmse' if kind=='regression' else 'macro_f1',
            text_features=[], prediction_type='label')
        spec.update(spec_extra or {})
        seen = dict(processors=[], estimators=[], fitting_frames=[], fitting_labels=[])
        class RecordingProcessor(ColumnTransformer):
            def fit_transform(self, x, y=None, **params):
                FITTING_CALLBACKS.append(True)
                seen['processors'].append(self)
                seen['fitting_frames'].append(x.copy(deep=True))
                seen['fitting_labels'].append(np.asarray(y).copy())
                return super().fit_transform(x, y, **params)
        def ridge(**params):
            value = Ridge(**params); seen['estimators'].append(value); return value
        def logistic(**params):
            value = LogisticRegression(**params); seen['estimators'].append(value); return value
        with mock.patch('sklearn.compose.ColumnTransformer', RecordingProcessor), \
             mock.patch('sklearn.linear_model.Ridge', side_effect=ridge), \
             mock.patch('sklearn.linear_model.LogisticRegression', side_effect=logistic):
            result = linear_text_fit(spec, copy.deepcopy(REG if kind=='regression' else CLF),
                train.copy(deep=True), test.copy(deep=True), y.copy(), tr, va, False, 1)
        self.assertEqual(len(seen['processors']), 1)
        self.assertEqual(len(seen['estimators']), 1)
        self.assertEqual(seen['fitting_frames'][0].index.tolist(), tr.tolist())
        np.testing.assert_array_equal(seen['fitting_labels'][0], y.iloc[tr].to_numpy())
        return result, seen

    def test_no_text_regression_uses_fixed_ridge_and_keeps_empty_numeric(self):
        result, seen = self.run_adapter('regression')
        processor, estimator = seen['processors'][0], seen['estimators'][0]
        self.assertEqual((estimator.alpha, estimator.solver), (10, 'lsqr'))
        self.assertEqual([name for name, _, _ in processor.transformers], ['numeric', 'category'])
        numeric = processor.named_transformers_['numeric']
        np.testing.assert_allclose(numeric.steps[0][1].statistics_, [5.5, 0.])
        self.assertEqual(numeric.steps[0][1].keep_empty_features, True)
        self.assertFalse(numeric.steps[1][1].with_mean)
        self.assertTrue(np.isfinite(result[0]).all())
        self.assertTrue(np.isfinite(result[1]).all())
        self.assertIsNone(result[3]); self.assertIsNone(result[4]); self.assertIsNone(result[5])

    def test_heldout_poison_cannot_change_fitted_preprocessing_or_coefficients(self):
        train, test, _, _ = self.frames()
        _, first = self.run_adapter('regression', train, test)
        train.loc[12:, 'number'] = [-2e12, 7e12, 3e12]
        train.loc[12:, 'category'] = ['poison-a', 'poison-b', 'poison-c']
        test['category'] = ['poison-test']*3
        _, second = self.run_adapter('regression', train, test)
        for a,b in zip(first['processors'], second['processors']):
            np.testing.assert_array_equal(a.named_transformers_['numeric'].steps[0][1].statistics_,
                b.named_transformers_['numeric'].steps[0][1].statistics_)
            np.testing.assert_array_equal(a.named_transformers_['category'].categories_[0],
                b.named_transformers_['category'].categories_[0])
        np.testing.assert_allclose(first['estimators'][0].coef_, second['estimators'][0].coef_, rtol=0, atol=0)

    def test_unknown_category_sparse_width_and_row_order(self):
        train, test, tr, _ = self.frames()
        result, seen = self.run_adapter('regression', train, test)
        processor = seen['processors'][0]
        transformed = processor.transform(test)
        self.assertTrue(sparse.issparse(transformed))
        self.assertEqual(transformed.shape[1], processor.transform(train.iloc[tr]).shape[1])
        self.assertNotIn('never-seen', processor.named_transformers_['category'].categories_[0])
        np.testing.assert_allclose(seen['estimators'][0].predict(transformed), result[0], atol=1e-12)
        order = [2, 0, 1]
        reordered = processor.transform(test.iloc[order])
        np.testing.assert_allclose(reordered.toarray(), transformed.toarray()[order], atol=0)

    def test_infrequent_vocabulary_is_fitted_only_and_stays_sparse(self):
        train, test, tr, _ = self.frames()
        train.loc[:11, 'category'] = ['frequent']*9+['rare-a','rare-b','rare-c']
        test['category'] = ['rare-a','never-seen','frequent']
        _, seen = self.run_adapter('regression', train, test)
        encoder = seen['processors'][0].named_transformers_['category']
        self.assertEqual(encoder.min_frequency, 3)
        self.assertEqual(encoder.handle_unknown, 'ignore')
        self.assertEqual(set(encoder.infrequent_categories_[0]), {'rare-a','rare-b','rare-c'})
        self.assertNotIn('outside', encoder.categories_[0])
        self.assertEqual(encoder.transform(test[['category']]).shape, (3, 2))
        self.assertTrue(sparse.issparse(encoder.transform(train.iloc[tr][['category']])))

    def test_multiclass_declared_probability_columns_and_validation_rows(self):
        columns = ['zeta','middle','alpha']
        result, seen = self.run_adapter('classification', spec_extra=dict(
            prediction_type='probability_matrix', output_columns=columns, classes=columns))
        pred, val_pred, metrics, test_p, val_p, classes = result
        self.assertEqual(list(classes), ['alpha','middle','zeta'])
        np.testing.assert_allclose(pred, test_p[:, [list(classes).index(c) for c in columns]], atol=1e-12)
        for probability, rows in [(test_p,3), (val_p,3)]:
            self.assertEqual(probability.shape, (rows,3))
            self.assertTrue(np.isfinite(probability).all())
            self.assertTrue((probability>=0).all())
            np.testing.assert_allclose(probability.sum(axis=1), 1, atol=1e-12)
        np.testing.assert_array_equal(val_pred, np.asarray(classes)[val_p.argmax(axis=1)])
        for name in ['macro_f1','weighted_f1','accuracy']:
            self.assertTrue(np.isfinite(metrics[name]))
        estimator = seen['estimators'][0]
        self.assertEqual(estimator.C,1); self.assertEqual(estimator.random_state,42)
        self.assertIsNone(estimator.class_weight)

    def test_binary_probability_uses_declared_positive_class(self):
        y=pd.Series(['no']*8+['yes']*4+['yes','no','yes'])
        result,_=self.run_adapter('classification', y=y, spec_extra=dict(
            prediction_type='probability', classes=['yes','no'], positive_class='yes'))
        pred,_,_,raw,_,classes=result
        np.testing.assert_allclose(pred, raw[:,list(classes).index('yes')], atol=1e-12)
        self.assertEqual(pred.shape,(3,))

    def test_class_weight_power_uses_only_fitting_labels_and_no_double_balance(self):
        y=pd.Series(['zeta']*6+['alpha']*3+['middle']*3+['alpha','middle','zeta'])
        weights=[]
        original=LogisticRegression.fit
        def recording(estimator,x,target,sample_weight=None):
            weights.append(np.asarray(sample_weight).copy())
            return original(estimator,x,target,sample_weight=sample_weight)
        with mock.patch.object(LogisticRegression,'fit',recording):
            _,a=self.run_adapter('classification',y=y)
            y.iloc[12:]=['zeta','alpha','middle']
            _,b=self.run_adapter('classification',y=y)
        np.testing.assert_array_equal(weights[0],weights[1])
        self.assertAlmostEqual(float(weights[0].mean()),1.)
        self.assertLess(float(weights[0][0]),float(weights[0][6]))
        self.assertIsNone(a['estimators'][0].class_weight)
        np.testing.assert_allclose(a['estimators'][0].coef_,b['estimators'][0].coef_,rtol=0,atol=0)

    def test_absent_declared_fitting_class_is_explicit_never_fabricated(self):
        # The adapter must reject an impossible declared probability column.
        # Public worker/split validation remains authoritative; no class is dropped.
        y=pd.Series(['left']*6+['right']*6+['unfitted','left','right'])
        with self.assertRaisesRegex(ValueError, "'unfitted'.*not in list"):
            self.run_adapter('classification',y=y,spec_extra=dict(prediction_type='probability_matrix',
                output_columns=['left','right','unfitted'],classes=['left','right','unfitted']))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--self-sha256',required=True)
    args=parser.parse_args()
    output=Path(args.output).resolve()
    assert __debug__ and output==WORK/'meth02b/g/linear-contracts.json' and not output.exists()
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.self_sha256
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(TabularLinearContracts)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    receipt=dict(status='passed' if result.wasSuccessful() else 'failed',tests_run=result.testsRun,
        errors=len(result.errors),failures=len(result.failures),skipped=len(result.skipped),
        tiny_fitting_callbacks=len(FITTING_CALLBACKS),fixture_source_sha256=args.self_sha256,
        public_data_used=False,API_calls=0,public_quality_metric=None,
        scope='Synthetic existing-adapter contracts only; charged inside same setup/common clock')
    with output.open('x',encoding='utf-8') as stream:
        json.dump(receipt,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    raise SystemExit(0 if result.wasSuccessful() and result.testsRun==8 and not result.skipped else 1)
