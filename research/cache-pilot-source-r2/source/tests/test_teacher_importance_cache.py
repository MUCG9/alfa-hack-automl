"""Teacher cache contracts using synthetic frames and mocked models; no ML fits."""
from copy import deepcopy
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tests'))

import numpy as np
import pandas as pd
from automl.execution.feature_engineering.importance_cache import TeacherImportanceCache
from automl.execution.feature_engineering.selection import select_features

MODULE = 'automl.execution.feature_engineering.selection'


def fixture():
    x = pd.DataFrame({'a': [1., 2., np.nan, 4., 5., 6.],
        'b': [7., 5., 3., 2., 1., 8.], 'cat': ['x', 'y', 'x', 'z', 'w', 'q'],
        'c': [8., 9., 5., 6., 1., 2.], 'd': [3., 1., 9., 7., 2., 4.]}, index=[11, 9, 2, 7, 3, 8])
    return dict(train_x=x, test_x=x.iloc[[5, 1]].copy(),
        y=pd.Series(['p', 'q', 'p', 'q', 'p', 'q'], index=x.index, name='label'),
        rows=np.array([3, 0, 2]), kind='classification', threads=2,
        params={'feature_selection_top_k': 2, 'seed': 17}, weights=np.array([.5, 1.5, 2.]))


def cache(**kwargs):
    instance = TeacherImportanceCache(enabled=True, **kwargs)
    instance.libraries = {'python': 'fixture', 'numpy': 'fixture', 'pandas': 'fixture', 'catboost': 'fixture'}
    return instance


def teacher():
    return Mock(feature_importances_=np.array([0., 2., 1., 8., 5.]))


class TeacherCacheTests(unittest.TestCase):
    def test_default_off_fits_normally_and_does_not_compute_keys(self):
        data = fixture()
        model = teacher()
        with patch(MODULE+'.create_model', return_value=model) as create, \
             patch('automl.execution.feature_engineering.importance_cache.teacher_key', side_effect=AssertionError('key requested')):
            a = select_features(**data)
            b = select_features(**data)
        self.assertEqual(create.call_count, 2)
        self.assertEqual(model.fit.call_count, 2)
        self.assertTrue(a[2]['teacher_fitted'])
        self.assertNotIn('importance_cache', a[2])
        pd.testing.assert_frame_equal(a[0], b[0])
        self.assertIs(model.fit.call_args.kwargs['sample_weight'], data['weights'])

    def test_identical_actual_teacher_context_reuses_importances_and_preserves_outputs(self):
        data, instance, model = fixture(), cache(), teacher()
        before = deepcopy(data)
        with patch(MODULE+'.create_model', return_value=model) as create:
            first = select_features(**data, importance_cache=instance, cache_scope='inner')
            second = select_features(**data, importance_cache=instance, cache_scope='inner')
        self.assertEqual(create.call_count, 1)
        self.assertEqual(model.fit.call_count, 1)
        self.assertEqual(first[2]['importance_cache']['status'], 'miss')
        self.assertEqual(second[2]['importance_cache']['status'], 'hit')
        self.assertFalse(second[2]['teacher_fitted'])
        self.assertEqual(second[2]['importance_cache']['teacher_fit_seconds'], 0.)
        pd.testing.assert_frame_equal(first[0], second[0])
        pd.testing.assert_frame_equal(first[1], second[1])
        pd.testing.assert_frame_equal(data['train_x'], before['train_x'])
        pd.testing.assert_series_equal(data['y'], before['y'])
        self.assertEqual(instance.snapshot()['hits'], 1)

    def test_nonfitting_values_labels_and_test_values_cannot_affect_key(self):
        data, instance, model = fixture(), cache(), teacher()
        changed = deepcopy(data)
        changed['train_x'].iloc[[1, 4, 5], 0] = [1e12, -1e12, 6e9]
        changed['train_x'].iloc[[1, 4, 5], 2] = ['outer1', 'outer2', 'outer3']
        changed['y'].iloc[[1, 4, 5]] = ['poison', 'other', 'unused']
        changed['test_x'].iloc[:, 0] = [1e10, -1e10]
        changed['test_x'].iloc[:, 2] = ['unseen_test_a', 'unseen_test_b']
        with patch(MODULE+'.create_model', return_value=model):
            a = select_features(**data, importance_cache=instance, cache_scope='inner')
            b = select_features(**changed, importance_cache=instance, cache_scope='inner')
        self.assertEqual(model.fit.call_count, 1)
        self.assertEqual(a[2]['importance_cache']['key_sha256'], b[2]['importance_cache']['key_sha256'])
        self.assertEqual(a[2]['selected_columns'], b[2]['selected_columns'])

    def test_each_teacher_input_or_scope_change_is_a_miss(self):
        mutations = {
            'fitting_numeric_value': lambda d: d['train_x'].__setitem__('a', d['train_x']['a'].where(d['train_x'].index != 7, 41.)),
            'fitting_category_value': lambda d: d['train_x'].iloc.__setitem__((3, 2), 'new'),
            'fitting_missingness': lambda d: d['train_x'].iloc.__setitem__((2, 0), 2.),
            'fitting_label': lambda d: d['y'].iloc.__setitem__(3, 'p'),
            'actual_weight': lambda d: d['weights'].__setitem__(0, .75),
            'row_order': lambda d: d.__setitem__('rows', d['rows'][::-1].copy()),
            'row_scope_same_content': lambda d: d.__setitem__('rows', np.array([3, 0, 1])),
            'column_order': lambda d: (d.__setitem__('train_x', d['train_x'].iloc[:, ::-1]), d.__setitem__('test_x', d['test_x'].iloc[:, ::-1])),
            'column_schema': lambda d: (d['train_x'].rename(columns={'a': 'renamed'}, inplace=True), d['test_x'].rename(columns={'a': 'renamed'}, inplace=True)),
            'seed': lambda d: d['params'].__setitem__('seed', 18),
            'threads': lambda d: d.__setitem__('threads', 1),
            'selection_top_k': lambda d: d['params'].__setitem__('feature_selection_top_k', 3),
            'selection_protected': lambda d: (d['params'].__setitem__('feature_selection_protect_original', True), d.__setitem__('protected_columns', ['a'])),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                data, instance, model = fixture(), cache(), teacher()
                changed = deepcopy(data)
                mutate(changed)
                with patch(MODULE+'.create_model', return_value=model):
                    select_features(**data, importance_cache=instance, cache_scope='inner')
                    second = select_features(**changed, importance_cache=instance, cache_scope='inner')
                self.assertEqual(model.fit.call_count, 2)
                self.assertEqual(second[2]['importance_cache']['status'], 'miss')

    def test_library_identity_and_inner_outer_phase_cannot_share(self):
        data, instance, model = fixture(), cache(), teacher()
        with patch(MODULE+'.create_model', return_value=model):
            select_features(**data, importance_cache=instance, cache_scope='inner')
            outer = select_features(**data, importance_cache=instance, cache_scope='outer')
            instance.libraries['catboost'] = 'different'
            other = select_features(**data, importance_cache=instance, cache_scope='inner')
        self.assertEqual(model.fit.call_count, 3)
        self.assertEqual(outer[2]['importance_cache']['status'], 'miss')
        self.assertEqual(other[2]['importance_cache']['status'], 'miss')

    def test_fresh_worker_cache_cannot_reuse_another_worker(self):
        data, first, second, model = fixture(), cache(), cache(), teacher()
        with patch(MODULE+'.create_model', return_value=model):
            a = select_features(**data, importance_cache=first, cache_scope='inner')
            b = select_features(**data, importance_cache=second, cache_scope='inner')
        self.assertEqual(model.fit.call_count, 2)
        self.assertNotEqual(a[2]['importance_cache']['worker_cache_identity'], b[2]['importance_cache']['worker_cache_identity'])

    def test_duplicate_content_on_different_row_positions_is_not_same_scope(self):
        data, instance, model = fixture(), cache(), teacher()
        data['train_x'].iloc[1] = data['train_x'].iloc[2].to_numpy()
        data['y'].iloc[1] = data['y'].iloc[2]
        other = deepcopy(data)
        other['rows'] = np.array([3, 0, 1])
        with patch(MODULE+'.create_model', return_value=model):
            select_features(**data, importance_cache=instance, cache_scope='inner')
            result = select_features(**other, importance_cache=instance, cache_scope='inner')
        self.assertEqual(model.fit.call_count, 2)
        self.assertEqual(result[2]['importance_cache']['status'], 'miss')

    def test_only_importance_and_column_metadata_are_retained_and_copies_are_defensive(self):
        data, instance, model = fixture(), cache(), teacher()
        with patch(MODULE+'.create_model', return_value=model):
            info = select_features(**data, importance_cache=instance, cache_scope='inner')[2]
        key = info['importance_cache']['key_sha256']
        values, columns, size = instance.entries[key]
        self.assertEqual(columns, tuple(data['train_x'].columns))
        self.assertEqual(values.shape, (5,))
        model.feature_importances_[:] = 0.
        self.assertEqual(values.tolist(), [0., 2., 1., 8., 5.])
        with patch('automl.execution.feature_engineering.importance_cache.teacher_key', return_value=key):
            _, copy, _ = instance.lookup()
            copy[:] = -999.
        self.assertEqual(values.tolist(), [0., 2., 1., 8., 5.])
        self.assertTrue(all(not isinstance(x, (pd.DataFrame, pd.Series)) for x in instance.__dict__.values()))
        with patch(MODULE+'.create_model', side_effect=AssertionError('cache miss')):
            result = select_features(**data, importance_cache=instance, cache_scope='inner')
        self.assertEqual(result[2]['selected_columns'], ['c', 'd'])
        self.assertGreaterEqual(size, values.nbytes)

    def test_unsupported_exact_key_type_bypasses_without_changing_fit_behavior(self):
        data, instance, model = fixture(), cache(), teacher()
        data['y'].name = pd.Timestamp('2020-01-01')
        with patch(MODULE+'.create_model', return_value=model):
            a = select_features(**data, importance_cache=instance, cache_scope='inner')
            b = select_features(**data, importance_cache=instance, cache_scope='inner')
        self.assertEqual(model.fit.call_count, 2)
        self.assertEqual(a[2]['importance_cache']['status'], 'bypass')
        self.assertEqual(b[2]['importance_cache']['status'], 'bypass')
        self.assertEqual(instance.snapshot()['entries'], 0)
        self.assertEqual(a[2]['selected_columns'], b[2]['selected_columns'])

    def test_lru_entry_and_byte_bounds_and_nonfinite_rejection(self):
        instance = cache(maximum_entries=2, maximum_bytes=4096)
        self.assertTrue(instance.store('a'*64, ['a', 'b'], [1., 2.]))
        self.assertTrue(instance.store('b'*64, ['a', 'b'], [3., 4.]))
        self.assertTrue(instance.store('c'*64, ['a', 'b'], [5., 6.]))
        self.assertNotIn('a'*64, instance.entries)
        self.assertLessEqual(len(instance.entries), 2)
        self.assertLessEqual(instance.bytes, 4096)
        with self.assertRaises(ValueError):
            instance.store('d'*64, ['a', 'b'], [np.nan, 1.])
        tiny = cache(maximum_bytes=1)
        self.assertFalse(tiny.store('e'*64, ['a'], [1.]))
        self.assertEqual(tiny.bytes, 0)

    def test_opt_in_requires_explicit_scope_and_invalid_job_flag_fails_before_io(self):
        from automl.execution.worker import run
        with patch(MODULE+'.create_model', side_effect=AssertionError('fit')), self.assertRaisesRegex(ValueError, 'explicit fitting scope'):
            select_features(**fixture(), importance_cache=cache())
        for invalid in [0, 1, 'true', None, [], {}]:
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, 'selector_importance_cache'):
                run({'selector_importance_cache': invalid})

    def test_leaf_worker_matching_inner_refit_hits_but_outer_refit_does_not(self):
        from automl.execution import worker
        from automl.search.policy import normalize
        from test_feature_views import fixture as worker_fixture

        class Student:
            classes_ = np.array(['A', 'M', 'Z'])
            feature_importances_ = None

            def fit(self, x, y, **kwargs):
                return self  # Mock student; no learner or optimiser is called.

            def predict_proba(self, x):
                return np.tile([.2, .5, .3], (len(x), 1))

            def predict(self, x):
                return np.full(len(x), 'M')

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec, _ = worker_fixture(root)
            recipe = normalize({'engine': 'lightgbm', 'params': {
                'iterations': 35, 'min_iterations': 10, 'calibrate': True,
                'feature_selection_top_k': 2}})
            outputs = []
            teachers_per_job, snapshots = [], []
            for enabled in [False, True, True]:
                out = root/('job-' + str(len(outputs)))
                out.mkdir()
                model = Mock(feature_importances_=np.array([0., 2., 1.]))
                with patch(MODULE+'.create_model', return_value=model), \
                     patch('automl.execution.feature_engineering.importance_cache.library_identity', return_value={'catboost': 'mock'}), \
                     patch.object(worker, 'make_model', side_effect=lambda *a: Student()), \
                     patch.object(worker, 'fit_options', return_value={}), \
                     patch.object(worker, 'selected_iterations', return_value=5), \
                     patch.object(worker, 'calibrate_class_factors', return_value=({}, {})), \
                     contextlib.redirect_stdout(io.StringIO()):
                    worker.run(dict(spec=spec, recipe=recipe, output_dir=str(out),
                        split_path=str(root/'split.npz'), threads=1,
                        selector_importance_cache=enabled))
                record = json.loads((out/'result.json').read_text(encoding='utf-8'))
                outputs.append((out/'submission.csv').read_bytes())
                teachers_per_job.append(model.fit.call_count)
                snapshots.append(record.get('selector_importance_cache'))
                scopes = [r['feature_selection'] for r in record['data_policy_runs']]
                self.assertEqual(len(scopes), 3)
                if enabled:
                    self.assertEqual([r['teacher_fitted'] for r in scopes], [True, False, True])
                    self.assertEqual([r['importance_cache']['status'] for r in scopes], ['miss', 'hit', 'miss'])
                    self.assertEqual(record['selector_importance_cache']['hits'], 1)
                    self.assertEqual(record['selector_importance_cache']['misses'], 2)
                else:
                    self.assertTrue(all(r['teacher_fitted'] for r in scopes))
                    self.assertNotIn('selector_importance_cache', record)
            self.assertEqual(teachers_per_job, [3, 2, 2])
            self.assertEqual(outputs[0], outputs[1])
            self.assertEqual(outputs[1], outputs[2])
            self.assertNotEqual(snapshots[1]['worker_cache_identity'], snapshots[2]['worker_cache_identity'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
