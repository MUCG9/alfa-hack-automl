"""Scientific and export invariants of PIPE-02, without model fitting."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tools'))
import numpy as np
import pandas as pd
import incumbent_mix_prototype as profile


def fixture():
    train = pd.DataFrame({'key': range(100), 'x': np.arange(100), 'period': np.repeat(range(5), 20),
                          'y': np.arange(100, dtype=float)})
    test = pd.DataFrame({'key': [100, 101], 'x': [100, 101], 'period': [5, 5]})
    sample = pd.DataFrame({'key': [101, 100], 'y': 0.})
    spec = {'kind': 'regression', 'metric': 'rmse', 'greater_is_better': False,
            'features': ['x', 'period'], 'target': 'y', 'id': 'key', 'text_features': [],
            'validation_strategy': 'time', 'time_column': 'period', 'static_numeric_features': ['x'],
            'prediction_type': 'value', 'output_columns': ['y'], 'sample_test_positions': [1, 0], 'classes': []}
    return spec, train, test, sample


class IncumbentMixTests(unittest.TestCase):
    def test_profile_priors_match_execution_contract_and_unsupported_tasks_fallback(self):
        spec, *_ = fixture()
        plan = profile.profile_recipes(spec)
        self.assertEqual([r['engine'] for r in plan['control']['components']], ['lightgbm', 'catboost'])
        self.assertTrue(plan['augmentation']['params']['history_asof'])
        self.assertTrue(plan['augmentation']['params']['log_target'])
        for changes in [{'text_features': ['x']}, {'metric': 'mae'}, {'validation_strategy': 'legacy'},
                        {'task_family': 'pointwise_ranking'}]:
            self.assertIsNone(profile.profile_recipes(dict(spec, **changes)))
        classification = dict(spec, kind='classification', metric='macro_f1', greater_is_better=True,
                              categorical_features=['x', 'period'])
        plan = profile.profile_recipes(classification, True)
        self.assertEqual(len(plan['control']['components']), 3)
        self.assertEqual(plan['control']['components'][1]['params']['seed'], 48)
        self.assertEqual(plan['augmentation']['params']['seed'], 53)
        self.assertEqual(plan['augmentation']['params']['feature_selection_top_k'], 32)
        self.assertIsNone(profile.profile_recipes(classification, False)['augmentation'])

    def test_class_gate_uses_fitting_group_support_and_gain_beyond_rarest(self):
        spec = {'kind': 'classification', 'metric': 'macro_f1', 'greater_is_better': True,
                'classes': ['a', 'b', 'rare']}
        control = {'macro_f1': .5, 'per_class_f1': {'a': .5, 'b': .5, 'rare': .5}}
        candidate = {'macro_f1': .6, 'per_class_f1': {'a': .48, 'b': .52, 'rare': .8}}
        self.assertFalse(profile.paired_passes(spec, control, candidate, {'a': 100, 'b': 120, 'rare': 4}))
        candidate['per_class_f1'] = {'a': .5, 'b': .5, 'rare': .8}
        self.assertFalse(profile.paired_passes(spec, control, candidate, {'a': 100, 'b': 120, 'rare': 4}))
        candidate['per_class_f1']['a'] = .51
        self.assertTrue(profile.paired_passes(spec, control, candidate, {'a': 100, 'b': 120, 'rare': 4}))

    def controller(self, augmentation_error):
        spec, train, test, sample = fixture()
        calls, scopes = [], []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); runs = root/'runs'; runs.mkdir()
            primary = (np.arange(80), np.arange(80, 100), {'method': 'time'})
            np.savez(runs/'split.npz', train=primary[0], validation=primary[1])
            pd.DataFrame({'key': sample.key, 'y': 0.}).to_csv(root/'submission.csv', index=False)
            def worker(spec, recipe, where, split, timeout, full_fit=False, fit_iterations=None, **kwargs):
                where = Path(where); where.mkdir()
                calls.append((where.name, full_fit, fit_iterations, kwargs['memory_limit']))
                self.assertLessEqual(timeout, 900)
                result = {'status': 'ok', 'recipe': deepcopy(recipe), 'full_fit': full_fit,
                          'fit_iterations': fit_iterations if full_fit else [40, 60] if recipe['engine'] == 'ensemble' else 50,
                          'metrics': {'rmse': 0.}, 'submission': str(where/'submission.csv')}
                profile.save_submission(spec, sample, test, [100., 101.], Path(result['submission']))
                if not full_fit:
                    with np.load(split) as saved:
                        rows = saved['validation']
                    error = 1. if recipe['engine'] == 'ensemble' else augmentation_error
                    pd.DataFrame({'row_position': rows, 'y_true': train.y.iloc[rows],
                                  'y_pred': train.y.iloc[rows]+error}).to_csv(where/'validation_predictions.csv', index=False)
                return result
            def optimizer(spec, train, hashes, rows, recipe, where, worker, deadline, **kwargs):
                scopes.append(np.asarray(rows).copy())
                chosen = deepcopy(recipe); chosen['params']['num_leaves'] = 70+len(scopes)
                return chosen, {'status': 'ok', 'selected_recipe': chosen, 'completed_trials': 8,
                                'trials': [{'recipe': chosen, 'value': 1., 'fit_iterations': 77}]}
            with patch.object(profile, 'make_time_split', return_value=(np.arange(60), np.arange(60, 80), {'method': 'time'})):
                result = profile.solve_profile(SimpleNamespace(time_budget=7200),
                    (spec, {}, train, test, sample, '', np.arange(100)), runs, root, primary,
                    {}, {}, time.monotonic(), time.monotonic()+7200, worker, optimizer)
            self.assertEqual(result['final_fit_status'], 'ok', result)
            self.assertTrue(result['integrity_ok'])
            self.assertTrue(all(c[3] == 1536*2**20 for c in calls))
            self.assertEqual(pd.read_csv(root/'submission.csv').key.tolist(), [101, 100])
            return result, calls, scopes

    def test_nested_scope_full_refit_iterations_and_source_truth(self):
        result, calls, scopes = self.controller(.5)
        for observed, expected in zip(scopes, [np.arange(80), np.arange(60), np.arange(100)]):
            np.testing.assert_array_equal(observed, expected)
        self.assertEqual(len(scopes), 3)
        self.assertTrue(result['augmentation_qualified'])
        self.assertAlmostEqual(result['profile_scores'][0]['control']['rmse'], 1.)
        self.assertAlmostEqual(result['profile_scores'][0]['candidate']['rmse'], .95)
        self.assertEqual([c[2] for c in calls if c[1]], [[40, 60], 77])

    def test_futile_augmentation_preserves_negative_score_and_full_control(self):
        result, calls, scopes = self.controller(5.)
        self.assertEqual(len(scopes), 1)
        self.assertFalse(result['augmentation_qualified'])
        self.assertAlmostEqual(result['profile_scores'][0]['candidate']['rmse'], 1.4)
        self.assertIsNone(result['profile_scores'][1]['candidate'])
        self.assertEqual([c[0] for c in calls if c[1]], ['full-control'])
        self.assertEqual(result['selected_recipe']['engine'], 'ensemble')
        self.assertEqual(len(result['selected_recipe']['components']), 2)

    def test_selected_trial_provenance_and_class_export_validation(self):
        recipe = {'engine': 'lightgbm', 'params': {'num_leaves': 31}}
        report = {'selected_recipe': recipe, 'trials': [{'recipe': recipe, 'value': None, 'fit_iterations': 42}]}
        with self.assertRaisesRegex(ValueError, 'provenance'):
            profile.study_iterations(report)
        report['trials'].append({'recipe': recipe, 'value': 1., 'fit_iterations': 77})
        self.assertEqual(profile.study_iterations(report), 77)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); arm = root/'arm'; arm.mkdir()
            spec = {'kind': 'classification', 'classes': ['a', 'b'], 'id': 'key', 'prediction_type': 'label',
                    'output_columns': ['y'], 'target': 'y', 'sample_test_positions': [1, 0]}
            test = pd.DataFrame({'key': [10, 11]}); sample = pd.DataFrame({'key': [11, 10], 'y': ['a', 'b']})
            record = {'status': 'ok', 'full_fit': True, 'recipe': recipe, 'fit_iterations': 77,
                      'submission': str(arm/'submission.csv')}
            np.savez(arm/'test_probabilities.npz', classes=['b', 'a'], probabilities=[[.9, .1], [.2, .8]])
            result = profile.full_output(spec, [record], [1.], root/'valid', sample, test)
            self.assertEqual(pd.read_csv(result['submission']).y.tolist(), ['a', 'b'])
            np.savez(arm/'test_probabilities.npz', classes=['b', 'a'], probabilities=[[.9, .9], [.2, .8]])
            with self.assertRaisesRegex(ValueError, 'probabilities'):
                profile.full_output(spec, [record], [1.], root/'bad', sample, test)


if __name__ == '__main__':
    unittest.main(verbosity=2)
