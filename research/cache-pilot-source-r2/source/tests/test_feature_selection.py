"""Real selector fits: inner/full scopes, outer-label isolation, valid output."""
from pathlib import Path
import contextlib
import io
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tests'))
import numpy as np
import pandas as pd
from automl.execution import worker
from automl.search.policy import normalize, signature
from automl.search.runner import coordinator_selection
from test_feature_views import fixture


class SelectionTests(unittest.TestCase):
    def test_worker_split_closes_before_model_construction_and_on_missing_key(self):
        for missing_key in [False, True]:
            with self.subTest(missing_key=missing_key), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                spec, _ = fixture(root)
                if missing_key:
                    np.savez(root/'split.npz', train=np.arange(288))
                opened = []
                original_load = np.load
                def tracked_load(*args, **kwargs):
                    value = original_load(*args, **kwargs)
                    opened.append(value)
                    return value
                recipe = normalize({'engine': 'lightgbm', 'params': {}})
                with patch.object(worker.np, 'load', side_effect=tracked_load), \
                     patch.object(worker, 'make_model', side_effect=RuntimeError('stop before any model fit')) as create:
                    with self.assertRaises(KeyError if missing_key else RuntimeError):
                        worker.run({'spec': spec, 'recipe': recipe, 'output_dir': str(root/'output'),
                                    'split_path': str(root/'split.npz'), 'threads': 1})
                self.assertEqual(len(opened), 1)
                self.assertTrue(all(value.zip is None for value in opened))
                if missing_key:
                    create.assert_not_called()
                else:
                    create.assert_called_once()

    def test_invalid_sizes_and_text_selection_fail_closed(self):
        for size in [-1, True, 2.5, 513, '32']:
            with self.subTest(size=size), self.assertRaises(ValueError):
                normalize({'engine': 'lightgbm', 'params': {'feature_selection_top_k': size}})
        with self.assertRaises(ValueError):
            normalize({'engine': 'linear_text', 'params': {'feature_selection_top_k': 2}})

    def test_selection_signature_and_omitted_default_are_distinct(self):
        first = normalize({'engine': 'lightgbm', 'params': {}})
        second = normalize({'engine': 'lightgbm', 'params': {'feature_selection_top_k': 2}})
        self.assertNotEqual(signature(first), signature(second))
        self.assertNotIn('feature_selection_top_k', first['params'])

    def test_explicit_coordinator_choice_overrides_planner_and_leaves_default_untouched(self):
        recipe=normalize({'engine':'catboost','params':{'feature_selection_top_k':50}})
        plain=normalize({'engine':'catboost','params':{}})
        self.assertIs(coordinator_selection(plain,0),plain)
        self.assertNotIn('feature_selection_top_k',coordinator_selection(recipe,0)['params'])
        selected=coordinator_selection(recipe,32)
        self.assertEqual(selected['params']['feature_selection_top_k'],32)
        self.assertEqual(recipe['params']['feature_selection_top_k'],50)
        with self.assertRaises(ValueError): coordinator_selection(normalize({'engine':'linear_text'}),32)

    def test_real_nested_and_full_refit_with_outer_label_poisoning(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            spec, train = fixture(root)
            recipe = normalize({'engine': 'lightgbm', 'params': {'iterations': 35, 'min_iterations': 10,
                'num_leaves': 7, 'feature_selection_top_k': 2, 'calibrate': True}})
            outputs = []
            for name, full in [('first', False), ('poisoned', False), ('full', True)]:
                out = root/name
                out.mkdir()
                with contextlib.redirect_stdout(io.StringIO()):
                    worker.run({'spec': spec, 'recipe': recipe, 'output_dir': str(out),
                        'split_path': str(root/'split.npz'), 'threads': 1, 'full_fit': full})
                result = json.loads((out/'result.json').read_text())
                scopes = [r['feature_selection'] for r in result['data_policy_runs']]
                self.assertTrue(all(s['status'] == 'selected' for s in scopes))
                self.assertEqual(result['feature_count'], 2)
                self.assertEqual(scopes[-1]['fitting_rows'], 360 if full else 288)
                if not full:
                    self.assertLess(scopes[0]['fitting_rows'], 288)
                    outputs.append((out/'submission.csv').read_bytes())
                else:
                    self.assertEqual(result['early_stopping_source'], 'full_refit')
                # Permute held-out labels while preserving the declared class set.
                train.loc[288:, 'answer'] = np.roll(train.answer.iloc[288:].to_numpy(), 1)
                train.to_csv(spec['paths']['train'], index=False)
            self.assertEqual(outputs[0], outputs[1])


if __name__ == '__main__':
    unittest.main(verbosity=2)
