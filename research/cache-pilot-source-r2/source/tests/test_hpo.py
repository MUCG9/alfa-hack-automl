"""Nested objective isolation, failed trials, deadline and real Optuna samplers."""
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
from automl.search.hpo import nested_partition, optimize_recipe
from automl.search.policy import normalize
from automl.search.runner import llm_plan


def fixture():
    train = pd.DataFrame({'x': np.arange(180), 'answer': np.sin(np.arange(180))})
    spec = {'kind': 'regression', 'metric': 'rmse', 'target': 'answer',
            'features': ['x'], 'greater_is_better': False, 'duplicate_feature_rate': 0.}
    recipe = normalize({'engine': 'lightgbm', 'params': {'num_leaves': 63, 'reg_lambda': 5.,
                      'colsample_bytree': .9, 'iterations': 35}})
    return spec, train, np.arange(len(train)), np.arange(140), recipe


class HPOTests(unittest.TestCase):
    def test_absolute_inner_positions_exclude_outer_rows_and_preserve_time(self):
        spec, train, hashes, _, _ = fixture()
        rows = np.arange(0, 140, 2)
        tr, va, info = nested_partition(spec, train, hashes, rows)
        self.assertTrue(set(tr) | set(va) <= set(rows))
        self.assertFalse(set(tr) & set(va))
        self.assertNotEqual(info['local_split_sha256'], info['split_sha256'])
        train['period'] = np.repeat(np.arange(6), 30)
        spec.update(validation_strategy='time', time_column='period', features=['x', 'period'])
        tr, va, _ = nested_partition(spec, train, hashes, np.arange(150))
        self.assertLess(train.period.iloc[tr].max(), train.period.iloc[va].min())
        self.assertTrue(set(va) <= set(range(150)))

    def test_duplicate_or_invalid_fitting_rows_fail_before_training(self):
        spec, train, hashes, _, _ = fixture()
        for rows in [[0, 0, 1], [-1, 2], [0, 190], []]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                nested_partition(spec, train, hashes, rows)

    def test_poisoning_outer_labels_cannot_change_study_or_selected_recipe(self):
        spec, train, hashes, rows, recipe = fixture()
        traces = []
        for sampler in ['random', 'tpe']:
            chosen = []
            for poison in [False, True]:
                data = train.copy()
                if poison:
                    data.loc[140:, 'answer'] = 1e20
                with tempfile.TemporaryDirectory() as directory:
                    def worker(spec, candidate, out, split, timeout):
                        with np.load(split) as stored:
                            self.assertLess(max(stored['train'].max(), stored['validation'].max()), 140)
                            value = abs(data.answer.iloc[stored['validation']].mean())+candidate['params']['num_leaves']/1000
                        return {'status': 'ok', 'metrics': {'rmse': float(value)}}
                    selected, report = optimize_recipe(spec, data, hashes, rows, recipe,
                        Path(directory)/'study', worker, time.monotonic()+30, trials=6, sampler=sampler)
                    chosen.append((selected, [(t['params'], t['value']) for t in report['trials']]))
                    self.assertEqual(report['completed_trials'], 6)
                    self.assertEqual(report['trials'][0]['params'],
                                     {'num_leaves': 63, 'reg_lambda': 5., 'colsample_bytree': .9})
            self.assertEqual(chosen[0], chosen[1])

    def test_failures_are_not_optimized_as_zero_rmse(self):
        spec, train, hashes, rows, recipe = fixture()
        with tempfile.TemporaryDirectory() as directory:
            count = [0]
            def worker(*args):
                count[0] += 1
                return {'status': 'timeout'} if count[0] != 2 else {'status': 'ok', 'metrics': {'rmse': 7.}}
            selected, report = optimize_recipe(spec, train, hashes, rows, recipe,
                Path(directory)/'study', worker, time.monotonic()+30, trials=4)
            self.assertEqual(report['completed_trials'], 1)
            self.assertEqual(report['best_inner_value'], 7.)
            self.assertEqual(selected, report['trials'][1]['recipe'])

    def test_all_failed_trials_preserve_control(self):
        spec, train, hashes, rows, recipe = fixture()
        with tempfile.TemporaryDirectory() as directory:
            selected, report = optimize_recipe(spec, train, hashes, rows, recipe,
                Path(directory)/'study', lambda *a: {'status': 'ok', 'metrics': {'rmse': float('nan')}},
                time.monotonic()+30, trials=2)
            self.assertEqual(selected, recipe)
            self.assertEqual(report['status'], 'no_successful_trials')

    def test_deadline_prevents_worker_start_and_bounds_each_timeout(self):
        spec, train, hashes, rows, recipe = fixture()
        with tempfile.TemporaryDirectory() as directory:
            selected, report = optimize_recipe(spec, train, hashes, rows, recipe,
                Path(directory)/'expired', lambda *a: self.fail('worker after deadline'),
                time.monotonic()-1)
            self.assertEqual(report['status'], 'deadline_before_start')
            def worker(*args):
                self.assertLessEqual(args[-1], 2)
                return {'status': 'timeout'}
            optimize_recipe(spec, train, hashes, rows, recipe, Path(directory)/'bounded', worker,
                            time.monotonic()+30, trials=2, worker_timeout=2)

    def test_staged_prompt_uses_same_recipe_contract(self):
        response = json.dumps({'data_assessment': 'fixture', 'candidates': [
            {'engine': 'catboost', 'params': {'depth': 5}, 'hypothesis': 'fixture'}]})
        with patch('automl.search.runner.request_json', return_value=(response, {'status': 'ok'})) as request:
            candidates, call = llm_plan({'best_recipe': None}, Path('.'), prompt_mode='staged')
        self.assertEqual(candidates[0]['engine'], 'catboost')
        self.assertIn('failure_diagnosis', request.call_args.args[0])


if __name__ == '__main__':
    unittest.main(verbosity=2)
