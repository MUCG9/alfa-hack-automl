"""The first HPO trial must construct the same model as its unchanged recipe.

Real adapters and Optuna are used; the injected worker never fits a model.
"""
from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tests'))
from test_hpo import fixture
from automl.search.hpo import optimize_recipe, search_space
from automl.search.policy import normalize
from automl.execution.model_adapters import lightgbm, xgboost, catboost


def constructed_params(recipe):
    adapters = {'lightgbm': lightgbm, 'xgboost': xgboost, 'catboost': catboost}
    model = adapters[recipe['engine']].create_model(recipe, 'regression', 1, 5)
    return model.params if recipe['engine'] == 'xgboost' else model.get_params()


class HPOAnchorTests(unittest.TestCase):
    def compare_anchor(self, engine, params, normalized=True):
        spec, train, hashes, rows, _ = fixture()
        recipe = {'engine': engine, 'params': params, 'feature_code': ''}
        if normalized:
            recipe = normalize(recipe)
        before = constructed_params(recipe)
        observed = []
        def worker(spec, candidate, *args):
            observed.append(constructed_params(candidate))
            return {'status': 'ok', 'metrics': {'rmse': 1.}}
        with tempfile.TemporaryDirectory() as directory:
            _, report = optimize_recipe(spec, train, hashes, rows, recipe,
                Path(directory)/'study', worker, time.monotonic()+30, trials=1)
        self.assertEqual(report['completed_trials'], 1)
        self.assertEqual(len(observed), 1)
        for name in search_space(engine):
            self.assertEqual(observed[0][name], before[name], name)

    def test_sparse_recipes_preserve_adapter_defaults(self):
        for engine in ['lightgbm', 'xgboost', 'catboost']:
            with self.subTest(engine=engine):
                self.compare_anchor(engine, {})

    def test_xgboost_depth_alias_and_explicit_max_depth_precedence(self):
        for normalized in [False, True]:
            for params in [{'depth': 5}, {'depth': 5, 'max_depth': 9}]:
                with self.subTest(params=params, normalized=normalized):
                    self.compare_anchor('xgboost', params, normalized)

    def test_explicit_measured_controls_keep_their_parameters(self):
        for engine, params in [
            ('lightgbm', {'num_leaves': 63, 'reg_lambda': 5., 'colsample_bytree': .9}),
            ('xgboost', {'max_depth': 6, 'min_child_weight': 3., 'reg_lambda': 8.}),
            ('catboost', {'depth': 6, 'l2_leaf_reg': 5., 'random_strength': 1.})]:
            with self.subTest(engine=engine):
                self.compare_anchor(engine, params)


if __name__ == '__main__':
    unittest.main(verbosity=2)
