"""No-fit constructor parity and actual Optuna startup/guided accounting."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

import numpy as np
import pandas as pd
from automl.execution.model_adapters.registry import make_model
from automl.search.hpo import _anchor_parameters, optimize_recipe, search_space


def model_parameters(recipe):
    model = make_model(dict(recipe, metric='rmse'), 'regression', 1, 35)
    if recipe['engine'] == 'xgboost':
        # CPUXGBoost constructs its library estimator at fit time. Construct
        # that exact estimator here, without invoking either wrapper/library fit.
        from xgboost import XGBRegressor
        model = XGBRegressor(**model.params)
    return model.get_params()


def fixture(engine='lightgbm', params=None):
    train = pd.DataFrame({'x': np.arange(100), 'answer': np.arange(100)/10})
    spec = {'kind': 'regression', 'metric': 'rmse', 'target': 'answer',
            'features': ['x'], 'greater_is_better': False, 'duplicate_feature_rate': 0.}
    return spec, train, np.arange(100), np.arange(80), {
        'engine': engine, 'params': {} if params is None else params,
        'feature_code': '', 'hypothesis': 'Preserved constructor control'}


class HPOAnchorTests(unittest.TestCase):
    def run_study(self, recipe, worker, trials=1, sampler='tpe', expired=False):
        spec, train, hashes, rows, _ = fixture()
        with tempfile.TemporaryDirectory() as directory:
            selected, report = optimize_recipe(
                spec, train, hashes, rows, recipe, Path(directory)/'study', worker,
                time.monotonic()+(-1 if expired else 30), trials=trials, sampler=sampler)
            stored = json.loads((Path(directory)/'study/hpo.json').read_text())
            self.assertEqual(json.loads(json.dumps(report)), stored)
            return selected, report

    def assert_constructor_anchor(self, engine, params=None):
        recipe = fixture(engine, params)[-1]
        before = deepcopy(recipe)
        expected = model_parameters(recipe)
        seen = []
        def worker(spec, candidate, *args):
            seen.append(candidate)
            self.assertEqual(model_parameters(candidate), expected)
            return {'status': 'ok', 'metrics': {'rmse': 1.}}
        selected, report = self.run_study(recipe, worker)
        self.assertEqual(len(seen), 1)
        self.assertEqual(report['anchor_params'], _anchor_parameters(recipe))
        self.assertEqual(model_parameters(selected), expected)
        self.assertEqual(recipe, before)
        return report

    def test_sparse_lightgbm_preserves_actual_leaves31_lambda3(self):
        report = self.assert_constructor_anchor('lightgbm')
        self.assertEqual(report['anchor_params'],
                         {'num_leaves': 31, 'reg_lambda': 3., 'colsample_bytree': .9})

    def test_sparse_xgboost_preserves_actual_depth8_lambda8(self):
        report = self.assert_constructor_anchor('xgboost')
        self.assertEqual(report['anchor_params'],
                         {'max_depth': 8, 'min_child_weight': 3., 'reg_lambda': 8.})

    def test_sparse_catboost_preserves_actual_constructor_defaults(self):
        report = self.assert_constructor_anchor('catboost')
        self.assertEqual(report['anchor_params'],
                         {'depth': 6, 'l2_leaf_reg': 5., 'random_strength': 1.})

    def test_legacy_depth_alias_matches_real_xgboost_and_lightgbm(self):
        for engine in ('xgboost', 'lightgbm'):
            with self.subTest(engine=engine):
                self.assert_constructor_anchor(engine, {'depth': 5})

    def test_explicit_max_depth_takes_priority_over_legacy_alias(self):
        self.assert_constructor_anchor('xgboost', {'depth': 4, 'max_depth': 9})

    def test_explicit_tuned_and_untuned_settings_are_preserved(self):
        self.assert_constructor_anchor('lightgbm', {
            'num_leaves': 80, 'reg_lambda': 11., 'colsample_bytree': .8,
            'learning_rate': .04, 'min_child_samples': 42, 'subsample': .8, 'seed': 19})
        self.assert_constructor_anchor('catboost', {
            'depth': 7, 'l2_leaf_reg': 9., 'random_strength': .3, 'seed': 19})

    def test_adapter_clipping_is_used_without_clipping_to_search_space(self):
        self.assert_constructor_anchor('catboost', {'depth': 2})
        for recipe in (fixture('lightgbm', {'num_leaves': 2})[-1],
                       fixture('xgboost', {'depth': 30})[-1],
                       fixture('catboost', {'depth': 10})[-1]):
            with self.subTest(recipe=recipe):
                selected, report = self.run_study(
                    recipe, lambda *args: self.fail('Outside-space control reached worker'))
                self.assertEqual(selected, recipe)
                self.assertEqual(report['status'], 'control_outside_search_space')
                self.assertEqual(report['attempted_trials'], 0)

    def test_original_search_bounds_are_unchanged(self):
        self.assertEqual(search_space('lightgbm'), {
            'num_leaves': ('int', 31, 127), 'reg_lambda': ('log', 2., 20.),
            'colsample_bytree': ('float', .75, 1.)})
        self.assertEqual(search_space('xgboost'), {
            'max_depth': ('int', 4, 10), 'min_child_weight': ('log', 1., 12.),
            'reg_lambda': ('log', 2., 20.)})
        self.assertEqual(search_space('catboost'), {
            'depth': ('int', 4, 8), 'l2_leaf_reg': ('log', 1., 30.),
            'random_strength': ('float', 0., 3.)})

    def test_two_successes_below_startup3_are_not_guided_tpe(self):
        count = [0]
        def worker(*args):
            count[0] += 1
            return ({'status': 'ok', 'metrics': {'rmse': float(count[0])}}
                    if count[0] <= 2 else {'status': 'timeout'})
        selected, report = self.run_study(fixture()[-1], worker, trials=4)
        self.assertEqual(report['sampler_startup_trials'], 3)
        self.assertEqual(report['completed_trials'], 2)
        self.assertEqual(report['failed_trials'], 2)
        self.assertEqual(report['guided_attempts'], 0)
        self.assertEqual(report['guided_successful_trials'], 0)
        self.assertEqual([t['sampling_phase'] for t in report['trials']],
                         ['anchor', 'startup', 'startup', 'startup'])
        self.assertEqual(selected, report['trials'][0]['recipe'])

    def test_guided_attempts_start_only_after_three_completed_observations(self):
        def worker(*args):
            return {'status': 'ok', 'metrics': {'rmse': 1.}}
        _, report = self.run_study(fixture()[-1], worker, trials=5)
        self.assertEqual(report['planned_trials'], 5)
        self.assertEqual(report['attempted_trials'], 5)
        self.assertEqual(report['completed_trials'], 5)
        self.assertEqual(report['failed_trials'], 0)
        self.assertEqual(report['unattempted_trials'], 0)
        self.assertEqual(report['guided_attempts'], 2)
        self.assertEqual(report['guided_successful_trials'], 2)
        self.assertEqual(report['trials'][3]['completed_before_sampling'], 3)

    def test_random_sampler_never_reports_guided_tpe(self):
        _, report = self.run_study(fixture()[-1], lambda *args: {
            'status': 'ok', 'metrics': {'rmse': 1.}}, trials=4, sampler='random')
        self.assertEqual(report['sampler_startup_trials'], 0)
        self.assertEqual(report['guided_attempts'], 0)
        self.assertEqual(report['phase_counts']['random']['completed'], 3)

    def test_failed_guided_attempt_is_not_a_guided_success(self):
        count = [0]
        def worker(*args):
            count[0] += 1
            return ({'status': 'ok', 'metrics': {'rmse': 1.}}
                    if count[0] <= 3 else {'status': 'timeout'})
        _, report = self.run_study(fixture()[-1], worker, trials=4)
        self.assertEqual(report['guided_attempts'], 1)
        self.assertEqual(report['guided_successful_trials'], 0)
        self.assertEqual(report['failed_trials'], 1)

    def test_duplicate_proposals_are_failures_without_worker_calls(self):
        recipe = fixture()[-1]
        anchor = _anchor_parameters(recipe)
        count = [0]
        def worker(*args):
            count[0] += 1
            return {'status': 'ok', 'metrics': {'rmse': 1.}}
        with patch('optuna.samplers.TPESampler.sample_independent',
                   side_effect=lambda study, trial, name, distribution: anchor[name]):
            _, report = self.run_study(recipe, worker, trials=4)
        self.assertEqual(count[0], 1)
        self.assertEqual(report['completed_trials'], 1)
        self.assertEqual(report['duplicate_trials'], 3)
        self.assertEqual(report['failed_trials'], 3)
        self.assertEqual(report['guided_attempts'], 0)

    def test_expired_study_reports_planned_but_no_actual_work(self):
        _, report = self.run_study(fixture()[-1],
            lambda *args: self.fail('Expired study reached worker'), trials=8, expired=True)
        self.assertEqual(report['status'], 'deadline_before_start')
        self.assertEqual(report['planned_trials'], 8)
        self.assertEqual(report['attempted_trials'], 0)
        self.assertEqual(report['completed_trials'], 0)
        self.assertEqual(report['failed_trials'], 0)
        self.assertEqual(report['unattempted_trials'], 8)


if __name__ == '__main__':
    unittest.main(verbosity=2)
