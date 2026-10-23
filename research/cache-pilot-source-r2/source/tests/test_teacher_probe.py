"""Fitting-only diagnostics contracts with mock teachers/students; no ML fits."""
from copy import deepcopy
import ast
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tests')]

import numpy as np
import pandas as pd
from automl.execution.feature_engineering import importance_cache as cache_module
from automl.execution.feature_engineering import teacher_probe as probe_module
from automl.execution.feature_engineering.selection import select_features
from automl.execution.feature_engineering.teacher_probe import TeacherImportanceProbe, json_digest
from test_teacher_importance_cache import fixture, cache, teacher, MODULE


def probe(instance=None, context=None):
    return TeacherImportanceProbe(context=context, libraries=(instance.libraries if instance else
        {'python': 'fixture', 'numpy': 'fixture', 'pandas': 'fixture', 'catboost': 'fixture'}))


def model():
    result = teacher()
    result.get_params.return_value = {'iterations': 100, 'depth': 5, 'thread_count': 2,
                                      'random_seed': 17, 'allow_writing_files': False}
    return result


class TeacherProbeTests(unittest.TestCase):
    def test_default_path_has_no_probe_or_keys_and_keeps_original_outputs(self):
        data, learner = fixture(), model()
        source = ROOT/'tests/fixtures/teacher_selector_default_off.py'
        import hashlib
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
            '46005426777b60358549dc7dcecc559631b9012a9b3c6c90df24d4a2ffeb7008')
        spec = importlib.util.spec_from_file_location('frozen_selector_default_off', source)
        frozen = importlib.util.module_from_spec(spec); spec.loader.exec_module(frozen)
        with patch(MODULE+'.create_model', return_value=learner), \
             patch.object(frozen, 'create_model', return_value=learner), \
             patch.object(probe_module, 'teacher_key', side_effect=AssertionError('probe hash')), \
             patch.object(cache_module, 'teacher_key', side_effect=AssertionError('cache hash')), \
             patch.object(TeacherImportanceProbe, '__init__', side_effect=AssertionError('probe created')):
            first = select_features(**data)
            second = select_features(**data, importance_cache=None, importance_probe=None)
            original = frozen.select_features(**data)
        self.assertEqual(learner.fit.call_count, 3)
        self.assertEqual(learner.get_params.call_count, 0)
        self.assertNotIn('teacher_diagnostics', first[2])
        self.assertNotIn('importance_cache', first[2])
        pd.testing.assert_frame_equal(first[0], second[0])
        pd.testing.assert_frame_equal(first[0], original[0])
        pd.testing.assert_frame_equal(first[1], original[1])
        for args in learner.fit.call_args_list[1:]:
            pd.testing.assert_frame_equal(learner.fit.call_args_list[0].args[0], args.args[0])
            pd.testing.assert_series_equal(learner.fit.call_args_list[0].args[1], args.args[1])
            self.assertIs(args.kwargs['sample_weight'], data['weights'])
        self.assertEqual(first[2]['selected_columns'], second[2]['selected_columns'])

    def test_common_hashes_match_both_arms_without_supplying_free_cache_key(self):
        data, instance, learner = fixture(), cache(), model()
        off, on = probe(instance), probe(instance)
        original = cache_module.teacher_key
        with patch(MODULE+'.create_model', return_value=learner), \
             patch.object(probe_module, 'teacher_key', wraps=original) as common, \
             patch.object(cache_module, 'teacher_key', wraps=original) as lookup:
            off_values = [select_features(**data, importance_probe=off, cache_scope='inner') for _ in range(2)]
            on_values = [select_features(**data, importance_probe=on, importance_cache=instance,
                                         cache_scope='inner') for _ in range(2)]
        self.assertEqual(common.call_count, 4)
        self.assertEqual(lookup.call_count, 2)  # ON pays another full key on miss AND hit.
        self.assertEqual(learner.fit.call_count, 3)
        self.assertEqual([r['cache_status'] for r in off.records], ['disabled', 'disabled'])
        self.assertEqual([r['cache_status'] for r in on.records], ['miss', 'hit'])
        self.assertEqual(on.records[1]['source_miss_request'], 0)
        for i in range(2):
            self.assertEqual(off.records[i]['key_sha256'], on.records[i]['key_sha256'])
            self.assertEqual(off.records[i]['components'], on.records[i]['components'])
            self.assertEqual(off.records[i]['effective_teacher_params_sha256'], on.records[i]['effective_teacher_params_sha256'])
            pd.testing.assert_frame_equal(off_values[i][0], on_values[i][0])
        self.assertEqual(on.records[1]['timings_seconds']['teacher_pure_fit'], 0.)
        for record in off.records+[on.records[1]]:
            self.assertFalse(record['timings_seconds']['cache_store_invoked'])
            self.assertEqual(record['timings_seconds']['cache_store'], 0.)

    def test_actual_fitting_values_log_target_weights_and_history_context_are_distinct(self):
        data, learner = fixture(), model()
        base = deepcopy(data)
        base['y'] = pd.Series(np.log1p(np.arange(6.)+1), index=base['train_x'].index, name='label')
        base['kind'] = 'regression'
        outside = deepcopy(base)
        outside['train_x'].iloc[[1, 4, 5], 0] = [-999., 8e12, 123.]
        outside['y'].iloc[[1, 4, 5]] = [222., 333., 444.]
        outside['test_x'].iloc[:, 2] = ['outside', 'poison']
        first, same = probe(context={'history_min_periods': 2}), probe(context={'history_min_periods': 2})
        with patch(MODULE+'.create_model', return_value=learner):
            select_features(**base, importance_probe=first, cache_scope='inner')
            fitted_target = learner.fit.call_args.args[1].copy()
            select_features(**outside, importance_probe=same, cache_scope='inner')
        pd.testing.assert_series_equal(fitted_target, base['y'].iloc[base['rows']])
        self.assertEqual(first.records[0]['components'], same.records[0]['components'])
        for component, mutate in [
            ('X_values', lambda x: x['train_x'].iloc.__setitem__((3, 0), 17.)),
            ('y', lambda x: x['y'].iloc.__setitem__(3, 91.)),
            ('weights', lambda x: x['weights'].__setitem__(0, .125)),
            ('rows', lambda x: x.__setitem__('rows', x['rows'][::-1].copy())),
            ('X_schema', lambda x: (x['train_x'].rename(columns={'a':'other'}, inplace=True),
                                   x['test_x'].rename(columns={'a':'other'}, inplace=True)))]:
            with self.subTest(component=component):
                changed, other = deepcopy(base), probe(context={'history_min_periods': 2})
                mutate(changed)
                with patch(MODULE+'.create_model', return_value=learner):
                    select_features(**changed, importance_probe=other, cache_scope='inner')
                self.assertNotEqual(first.records[0]['components'][component], other.records[0]['components'][component])
                self.assertNotEqual(first.records[0]['key_sha256'], other.records[0]['key_sha256'])
        history = probe(context={'history_min_periods': 3})
        self.assertNotEqual(first.context_sha256, history.context_sha256)
        self.assertNotIn('history_minimum_periods', first.snapshot()['context'])

    def test_scopes_fresh_leaf_and_bounded_lru_trace_keep_no_fitting_values(self):
        data, instance, learner = fixture(), cache(maximum_entries=1), model()
        measured = probe(instance)
        with patch(MODULE+'.create_model', return_value=learner):
            for scope in ['inner', 'inner', 'outer', 'inner']:
                select_features(**data, importance_probe=measured, importance_cache=instance, cache_scope=scope)
        self.assertEqual([r['cache_status'] for r in measured.records], ['miss', 'hit', 'miss', 'miss'])
        self.assertEqual(measured.records[1]['source_miss_request'], 0)
        self.assertNotEqual(measured.records[0]['key_sha256'], measured.records[2]['key_sha256'])
        self.assertEqual(instance.snapshot()['evictions'], 2)
        for record in measured.records:
            trace = record['cache_trace']
            self.assertLessEqual(len(trace['resident_keys_lru']), 1)
            self.assertEqual(sum(trace['resident_payload_bytes_lru'].values()), trace['snapshot']['metadata_and_importance_bytes'])
        self.assertNotEqual(measured.identity, probe(instance).identity)
        def assert_compact(value):
            self.assertNotIsInstance(value, (pd.DataFrame, pd.Series, np.ndarray))
            if isinstance(value, dict):
                for item in value.values(): assert_compact(item)
            elif isinstance(value, (list, tuple)):
                for item in value: assert_compact(item)
        assert_compact(measured.__dict__)
        copy = measured.snapshot()
        copy['requests'][0]['components'].clear()
        self.assertTrue(measured.records[0]['components'])

    def test_fake_clock_separates_actual_fit_from_constructor_and_importance(self):
        clock = [0.]
        class TimedTeacher:
            def __init__(self): clock[0] += 2
            def fit(self, *args, **kwargs): clock[0] += 5
            @property
            def feature_importances_(self):
                clock[0] += 3
                return np.array([0., 2., 1., 8., 5.])
            def get_params(self):
                clock[0] += 7
                return {'iterations':100}
        instance = cache(); measured = probe(instance)
        with patch(MODULE+'.create_model', side_effect=lambda *args: TimedTeacher()), \
             patch('time.monotonic', side_effect=lambda: clock[0]):
            info = select_features(**fixture(), importance_cache=instance,
                importance_probe=measured, cache_scope='inner')[2]
        timing = measured.records[0]['timings_seconds']
        self.assertEqual(timing['teacher_constructor'], 2)
        self.assertEqual(timing['teacher_pure_fit'], 5)
        self.assertEqual(timing['teacher_importance_extraction'], 3)
        self.assertEqual(timing['teacher_constructor_fit_importance_inclusive'], 10)
        self.assertEqual(info['importance_cache']['teacher_fit_seconds'], 10)
        self.assertEqual(timing['teacher_parameter_probe'], 7)
        self.assertGreaterEqual(info['selector_seconds'], 17)

    def test_mock_worker_probe_has_same_inner_keys_outer_miss_and_exact_csv(self):
        from automl.execution import worker
        from automl.search.policy import normalize
        from test_feature_views import fixture as worker_fixture
        class Student:
            classes_ = np.array(['A', 'M', 'Z'])
            feature_importances_ = None
            def fit(self, x, y, **kwargs): return self
            def predict_proba(self, x): return np.tile([.2, .5, .3], (len(x), 1))
            def predict(self, x): return np.full(len(x), 'M')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); spec, _ = worker_fixture(root)
            recipe = normalize({'engine':'lightgbm','params':{'iterations':35,
                'min_iterations':10,'calibrate':True,'feature_selection_top_k':2}})
            records, csvs, counts = [], [], []
            for on in [False, True]:
                out = root/('on' if on else 'off'); out.mkdir()
                learner = Mock(feature_importances_=np.array([0., 2., 1.]))
                learner.get_params.return_value = {'iterations':100,'random_seed':42}
                versions = {'catboost':'mock'}
                with patch(MODULE+'.create_model', return_value=learner), \
                     patch.object(cache_module,'library_identity',return_value=versions), \
                     patch.object(probe_module,'library_identity',return_value=versions), \
                     patch.object(worker,'make_model',side_effect=lambda *args:Student()), \
                     patch.object(worker,'fit_options',return_value={}), \
                     patch.object(worker,'selected_iterations',return_value=5), \
                     patch.object(worker,'calibrate_class_factors',return_value=({},{})), \
                     contextlib.redirect_stdout(io.StringIO()):
                    worker.run(dict(spec=spec,recipe=recipe,output_dir=str(out),
                        split_path=str(root/'split.npz'),threads=1,
                        selector_importance_cache=on,selector_importance_diagnostics=True))
                result = json.loads((out/'result.json').read_text(encoding='utf-8'))
                sidecar = out/'teacher-diagnostics.json'
                import hashlib
                self.assertEqual(result['teacher_diagnostics']['sha256'], hashlib.sha256(sidecar.read_bytes()).hexdigest())
                records.append(json.loads(sidecar.read_text(encoding='utf-8')))
                csvs.append((out/'submission.csv').read_bytes()); counts.append(learner.fit.call_count)
            self.assertEqual(csvs[0], csvs[1]); self.assertEqual(counts, [3,2])
            for item in records:
                self.assertEqual([r['scope'] for r in item['requests']], ['inner','inner','outer'])
                self.assertEqual(item['context']['history_min_periods'], 2)
            self.assertEqual([r['key_sha256'] for r in records[0]['requests']], [r['key_sha256'] for r in records[1]['requests']])
            self.assertEqual([r['cache_status'] for r in records[1]['requests']], ['miss','hit','miss'])

    def test_uncacheable_types_and_invalid_flags_keep_fit_or_fail_before_io(self):
        from automl.execution.worker import run
        for invalid in [0,1,'true',None,[],{}]:
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError,'selector_importance_diagnostics'):
                run({'selector_importance_diagnostics':invalid})
        with patch(MODULE+'.create_model',side_effect=AssertionError('fit')), self.assertRaisesRegex(ValueError,'explicit fitting scope'):
            select_features(**fixture(),importance_probe=probe())
        data, learner, measured = fixture(), model(), probe()
        data['y'].name = pd.Timestamp('2020-01-01')
        with patch(MODULE+'.create_model',return_value=learner):
            select_features(**data,importance_probe=measured,cache_scope='inner')
        self.assertEqual(learner.fit.call_count, 1)
        self.assertEqual(measured.records[0]['status'], 'uncacheable')
        self.assertIsNone(measured.records[0]['key_sha256'])
        # Unsupported column metadata must describe an unavailable diagnostic,
        # not turn ordinary fitting/cache bypass into a serialization failure.
        renamed, other = fixture(), probe()
        names = {name:pd.Timestamp('2020-01-01')+pd.Timedelta(days=i)
                 for i,name in enumerate(renamed['train_x'].columns)}
        renamed['train_x'].rename(columns=names,inplace=True)
        renamed['test_x'].rename(columns=names,inplace=True)
        with patch(MODULE+'.create_model',return_value=learner):
            select_features(**renamed,importance_probe=other,cache_scope='inner')
        self.assertEqual(other.records[0]['column_metadata_status'], 'unsupported_JSON_metadata')
        self.assertFalse(other.records[0]['store_eligibility']['eligible_if_enabled'])
        self.assertIsNone(other.records[0]['columns'])
        json.dumps(other.snapshot(),allow_nan=False)

    def test_flat_build_maps_probe_and_keeps_registered_method_counts(self):
        source = ROOT/'tools/build_submission.py'
        spec = importlib.util.spec_from_file_location('probe_flat_build',source)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        files = module.build_files()  # AST compile only; no runtime import or fits.
        self.assertIn('automl_execution_feature_engineering_teacher_probe.py',files)
        self.assertIn('automl_execution_feature_engineering_importance_cache.py',files)
        text = files['automl_worker.py'].decode()
        self.assertIn('selector_importance_diagnostics',text)
        self.assertTrue(any(isinstance(n,ast.If) and isinstance(n.test,ast.Compare)
                            and '__main__' in ast.unparse(n.test) for n in ast.parse(text).body))
        tree = ast.parse((ROOT/'tools/run_checks.py').read_text(encoding='utf-8'))
        checks = ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign)
            and any(isinstance(t,ast.Name) and t.id=='CHECKS' for t in n.targets)))
        self.assertEqual(checks['test_teacher_importance_cache.py'],12)
        self.assertEqual(checks['test_teacher_probe.py'],8)
        self.assertEqual(sum(checks.values()),471); self.assertEqual(len(checks),48)


if __name__ == '__main__':
    unittest.main(verbosity=2)
