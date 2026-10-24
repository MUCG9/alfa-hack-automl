"""12 prospective c7b source/synthetic/mock contracts; author executed zero.

Run only in a fresh guarded root-owned process after the active gate closes.
No model fits, learner subprocesses, network, organizer rows or prediction reuse.
Dependency import-time local metadata subprocesses are not model launches.
"""
from contextlib import ExitStack
import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parent
SOURCE = WORK / 'br-standard-release-next-dev-r5/candidate'
ARCHIVE = WORK.parent / 'outputs/solution-br-rmse34.15502.zip'
ARCHIVE_SHA = 'c7b54a8996e36dfaaf582b104d1f38ecca71d91d4f38362ed50775381f42f930'


class ClassRuntimeContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() == ARCHIVE_SHA
        with zipfile.ZipFile(ARCHIVE) as zipped:
            assert len(zipped.namelist()) == 74
            for name in zipped.namelist():
                assert zipped.read(name) == (SOURCE / name).read_bytes(), name
        sys.path.insert(0, str(SOURCE))
        # Exact source barrier above precedes all candidate/dependency imports.
        # Dependency initialization may perform local CPU metadata subprocesses;
        # the outer owned-process guard accounts for them. No learner is called
        # by these module imports. The blanket Popen tripwire remains active in
        # setUp BEFORE EVERY unchanged test method (including mocked workers).
        with patch('socket.create_connection', side_effect=AssertionError('No network')):
            cls.release = importlib.import_module('automl_fixed_release')
            cls.recipes = importlib.import_module('automl_release_recipes')
            cls.runtime = importlib.import_module('automl_release_runtime')
            cls.worker = importlib.import_module('automl_worker')
            cls.evaluation = importlib.import_module('automl_evaluation')
            cls.views = importlib.import_module('automl_execution_feature_views')
            cls.resources = importlib.import_module('automl_infrastructure_resources')
            cls.np = importlib.import_module('numpy')
            cls.pd = importlib.import_module('pandas')
        for module in (cls.release, cls.recipes, cls.runtime, cls.worker,
                       cls.evaluation, cls.views, cls.resources):
            assert Path(module.__file__).resolve().parent == SOURCE.resolve()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch('socket.create_connection', side_effect=AssertionError('No network')))
        self.stack.enter_context(patch('subprocess.Popen', side_effect=AssertionError('No learners')))

    def class_spec(self):
        return dict(kind='classification', metric='macro_f1', features=['left', 'right', 'sensor'],
                    categorical_features=['left', 'right'], text_features=[],
                    target='answer', id='ticket', classes=['A', 'B', 'C'],
                    prediction_type='value', output_columns=['answer'], root=str(self.root))

    def fake_clock(self, origin=(1000., 0.)):
        now = [0.]
        samples = []
        resources = SimpleNamespace(memory_limit=2048 * 2**20,
            inspect=lambda *args: (samples.append(now[0]) or (None, 1, 2)))
        own = SimpleNamespace(pid=991, create_time=lambda: 1.)
        self.stack.enter_context(patch.object(self.runtime.time, 'monotonic', side_effect=lambda: now[0]))
        self.stack.enter_context(patch.object(self.runtime.time, 'time', side_effect=lambda: 1000. + now[0]))
        self.stack.enter_context(patch.object(self.runtime, 'ResourceBudget', return_value=resources))
        self.stack.enter_context(patch.object(self.runtime.psutil, 'Process', return_value=own))
        clock = self.runtime.ReleaseClock(9900, self.root, origin=origin)
        return clock, now, samples

    def test_fixed_class_geometry_has_no_variable_oof_fold_tree(self):
        recipe = self.recipes.fixed_recipe('classification', 'macro_f1')
        self.assertEqual([c['engine'] for c in recipe['components']], ['lightgbm', 'lightgbm', 'xgboost'])
        self.assertTrue(all(c['params'].get('calibration_folds', 1) == 1 for c in recipe['components']))
        self.assertTrue(all(c['params']['nested_stopping'] is True for c in recipe['components']))
        self.assertEqual([c['params'].get('feature_views') for c in recipe['components']],
                         ['categorical_te_pair', 'categorical_te_pair', None])

    def test_valid_macro_f1_schema_with_fewer_than_two_declared_categories_is_rejected(self):
        recipe = self.recipes.CLASSIFICATION_RECIPE['components'][0]
        for categories in ([], ['left']):
            spec = self.class_spec(); spec['categorical_features'] = categories
            with self.subTest(categories=categories), self.assertRaisesRegex(ValueError, 'two schema-declared'):
                self.views.validate_feature_view(recipe, spec)
        self.assertEqual(self.views.validate_feature_view(recipe, self.class_spec()), [['left', 'right']])

    def test_small_ten_class_valid_table_cannot_use_current_twenty_percent_stratification(self):
        frame = self.pd.DataFrame({'answer': [str(i) for i in range(10) for _ in range(2)]})
        spec = dict(kind='classification', target='answer', duplicate_feature_rate=0.)
        with self.assertRaises(ValueError):
            self.evaluation.make_split(spec, frame, self.np.arange(len(frame), dtype='uint64'), seed=42)

    def test_singleton_class_in_validation_is_a_strict_failure_not_a_wrong_class_order(self):
        frame = self.pd.DataFrame({'answer': ['A', 'A', 'B']})
        spec = dict(kind='classification', target='answer', duplicate_feature_rate=0.)
        hashes = self.np.arange(3, dtype='uint64')
        with patch.object(self.evaluation, 'train_test_split', return_value=(self.np.array([0, 1]), self.np.array([2]))) as split:
            with self.assertRaisesRegex(ValueError, 'classes absent in training'):
                self.evaluation.make_split(spec, frame, hashes, seed=42)
        self.assertIsNone(split.call_args.kwargs['stratify'])
        with patch.object(self.evaluation, 'train_test_split', return_value=(self.np.array([0, 2]), self.np.array([1]))):
            tr, va, _ = self.evaluation.make_split(spec, frame, hashes, seed=42)
        self.assertEqual(tr.tolist(), [0, 2]); self.assertEqual(va.tolist(), [1])

    def test_calibration_diagnostic_lengths_do_not_change_two_view_iteration_geometry(self):
        spec = self.class_spec(); recipe = self.recipes.CLASSIFICATION_RECIPE['components'][0]
        output = self.root / 'views'; output.mkdir()
        def inert_ensemble(job):
            self.assertEqual(len(job['recipe']['components']), 2)
            record = dict(fit_iterations=[101, 202], components=[
                dict(calibration_folds=[]), dict(calibration_folds=[{}, {}, {}])])
            (output / 'result.json').write_text(json.dumps(record), encoding='utf-8')
        with patch.object(self.worker, 'run_ensemble', side_effect=inert_ensemble):
            self.worker.run_feature_views(dict(recipe=recipe, spec=spec, output_dir=str(output)))
        result = json.loads((output / 'result.json').read_text())
        self.assertEqual(result['fit_iterations'], [101, 202])
        self.assertEqual(result['feature_views']['iteration_tree'], [101, 202])
        self.views.validate_fit_iterations(recipe, result['fit_iterations'])

    def test_recursive_median_uses_fixed_model_tree_and_rejects_malformed_trees(self):
        recipe = self.recipes.CLASSIFICATION_RECIPE
        actual = self.release.median_iterations([[100, 120], [130, 140], 300],
                                                 [[110, 100], [150, 160], 340])
        self.assertEqual(actual, [[105, 110], [140, 150], 320])
        self.views.validate_fit_iterations(recipe, actual)
        for broken in ([[100], [100, 120], 300], [[100, 110], [120, 130]],
                       [[100, True], [120, 130], 200]):
            with self.subTest(tree=broken), self.assertRaises(ValueError):
                self.views.validate_fit_iterations(recipe, broken)
        with self.assertRaises(ValueError):
            self.release.median_iterations([[100, 120], [130, 140], 300], [[110], [150, 160], 340])

    def ensemble_case(self, missing=False):
        output = self.root / 'ensemble'; output.mkdir()
        split = self.root / 'split.npz'
        self.np.savez(split, train=self.np.array([0]), validation=self.np.array([1]))
        spec = self.class_spec(); captured = []
        canonical = self.np.array([[.1, .6, .3], [.8, .1, .1]])
        permutations = [['C', 'A', 'B'], ['B', 'C', 'A'], ['A', 'B', 'C']]
        def inert_child(job):
            index = int(Path(job['output_dir']).name.rsplit('-', 1)[1])
            classes = permutations[index]
            if missing and index == 1: classes = classes[:2]
            values = canonical[:, [spec['classes'].index(c) for c in classes]]
            directory = Path(job['output_dir'])
            self.np.savez(directory / 'test_probabilities.npz', classes=self.np.asarray(classes), probabilities=values)
            iterations = [[101, 102], [103, 104], 105][index]
            (directory / 'result.json').write_text(json.dumps(dict(fit_iterations=iterations, feature_count=1)), encoding='utf-8')
        with patch.object(self.worker, 'run', side_effect=inert_child), \
             patch.object(self.worker, 'read_worker_table', return_value=self.pd.DataFrame()), \
             patch.object(self.worker, 'read_task_sample', return_value=self.pd.DataFrame()), \
             patch.object(self.worker, 'save_submission', side_effect=lambda *args: captured.append(args[3])), \
             patch.object(self.worker, 'peak_rss_mb', return_value=0.):
            self.worker.run_ensemble(dict(recipe=self.recipes.CLASSIFICATION_RECIPE, spec=spec,
                output_dir=str(output), split_path=str(split), full_fit=True))
        return output, canonical, captured

    def test_child_probability_permutations_are_aligned_to_canonical_class_order(self):
        output, expected, captured = self.ensemble_case()
        with self.np.load(output / 'test_probabilities.npz', allow_pickle=False) as saved:
            self.assertEqual(saved['classes'].tolist(), ['A', 'B', 'C'])
            self.np.testing.assert_allclose(saved['probabilities'], expected)
        self.assertEqual(captured[0].tolist(), ['B', 'A'])

    def test_missing_class_artifact_stops_instead_of_silent_probability_padding(self):
        with self.assertRaises(ValueError): self.ensemble_case(missing=True)
        self.assertFalse((self.root / 'ensemble/result.json').exists())

    def test_more_than_ten_seconds_import_elapsed_rejects_before_first_os_observation(self):
        resources = SimpleNamespace(memory_limit=2048 * 2**20)
        with patch.object(self.runtime.time, 'monotonic', return_value=10.01), \
             patch.object(self.runtime.time, 'time', return_value=1010.01), \
             patch.object(self.runtime, 'ResourceBudget', return_value=resources), \
             patch.object(self.runtime.psutil, 'Process', side_effect=AssertionError('No OS observation')) as process:
            with self.assertRaisesRegex(RuntimeError, 'observation_gap_over10s'):
                self.runtime.ReleaseClock(9900, self.root, origin=(1000., 0.))
        process.assert_not_called()

    def test_slow_discovery_after_original_sample_causes_sticky_gap_before_any_worker(self):
        clock, now, samples = self.fake_clock()
        task = self.root / 'task.md'; task.write_text('Classification. Primary metric: Macro F1', encoding='utf-8')
        spec = self.class_spec()
        loaded = dict(declared_target='answer', declared_identifier='ticket')
        def slow_discover(*args, **kwargs):
            now[0] = 10.5
            return spec, None, None, None, None, None, None
        with patch.object(self.release, 'ReleaseClock', return_value=clock), \
             patch.object(self.release, 'load_fixed_inputs', return_value=loaded), \
             patch.object(self.release, 'discover', side_effect=slow_discover), \
             patch.object(self.release.TaskSpec, 'from_legacy'), \
             patch.object(self.release, 'choose_validation', side_effect=lambda value, *args: value), \
             patch.object(self.release, 'run_release_worker') as worker:
            with self.assertRaisesRegex(RuntimeError, 'observation_gap_over10s') as first:
                self.release.execute(task, origin=(1000., 0.))
        worker.assert_not_called(); self.assertEqual(samples, [0.])
        now[0] = 10.6
        with self.assertRaises(RuntimeError) as again: clock.check()
        self.assertIs(first.exception, again.exception)

    def test_class_terminal_worker_over_1536_mib_is_not_accepted_as_success(self):
        directory = self.root / 'terminal-class'
        process = Mock(pid=123, returncode=0); process.poll.return_value = 0
        tree = Mock(); tree.members = {(123, 1.): object()}
        budget = Mock(); budget.inspect.return_value = (None, 1536 * 2**20 + 1, 2048 * 2**20)
        budget.inspect_artifacts.return_value = 0
        caller = SimpleNamespace(check=lambda force=False: None, remaining=lambda: 9900., receipt=lambda: {})
        def spawned(*args, **kwargs):
            (directory / 'result.json').write_text(json.dumps(dict(status='ok')), encoding='utf-8')
            return process
        with patch.object(self.runtime.subprocess, 'Popen', side_effect=spawned), \
             patch.object(self.runtime, 'ProcessTree', return_value=tree), \
             patch.object(self.runtime, 'ResourceBudget', return_value=budget), \
             patch.object(self.runtime.psutil, 'Process', return_value=SimpleNamespace(pid=991, create_time=lambda: 1.)), \
             patch.object(self.runtime.time, 'monotonic', return_value=0.):
            result = self.runtime.run_release_worker(dict(root=str(self.root)), self.recipes.CLASSIFICATION_RECIPE,
                directory, 'unused', 100., clock=caller)
        self.assertEqual(result['status'], 'worker_memory_limit')
        self.assertEqual(result['observed_worker_tree_peak_bytes'], 1536 * 2**20 + 1)
        self.assertEqual(result['terminal_resource_observation']['status'], 'sampled_before_terminal_acceptance')
        tree.terminate.assert_called_once()

    def test_parent_inspect_self_conservatively_counts_self_twice(self):
        own = (991, 1.); rss = 1100 * 2**20
        sampler = SimpleNamespace(known={own}, remember=lambda *args: None, discover_owned_tree=lambda *args, **kwargs: None,
            sample=lambda *args, **kwargs: dict(sampled=[dict(pid=own[0], create_time=own[1], rss_bytes=rss)], departed=[]))
        budget = self.resources.ResourceBudget(memory_limit=2048 * 2**20)
        config = dict(sampler=sampler, checkpoint=lambda: None, self_identity=own, root_identity=own)
        limit, tree_rss, total = budget._inspect_verified(own[0], self.root, config)
        self.assertEqual(tree_rss, rss); self.assertEqual(total, 2 * rss)
        self.assertLess(tree_rss, budget.memory_limit); self.assertGreater(total, budget.memory_limit)
        self.assertEqual(limit, 'memory_limit')


if __name__ == '__main__':
    unittest.main(verbosity=2)
