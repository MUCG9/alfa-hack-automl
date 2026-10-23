"""Reject false equivalence and incomplete full fitting without running models."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from verify_profile_campaign import full_leaves, same_recipe


class ProfileVerificationTests(unittest.TestCase):
    def test_recipe_equivalence_ignores_prose_but_preserves_nested_policy(self):
        leaf = {'engine': 'lightgbm', 'params': {'num_leaves': 63}, 'hypothesis': 'first'}
        recipe = {'engine': 'ensemble', 'components': [leaf, deepcopy(leaf)], 'weights': [.9, .1]}
        changed = deepcopy(recipe); changed['components'][0]['hypothesis'] = 'different prose'
        self.assertTrue(same_recipe(recipe, changed))
        changed['components'][0]['params']['feature_selection_top_k'] = 32
        self.assertFalse(same_recipe(recipe, changed))
        changed = deepcopy(recipe); changed['weights'] = [.8, .2]
        self.assertFalse(same_recipe(recipe, changed))

    def test_full_lineage_requires_every_original_row_in_every_final_leaf(self):
        count = 12
        leaf = {'status': 'ok', 'full_fit': True, 'early_stopping_source': 'full_refit',
                'data_policy_runs': [{'source_rows': count,
                    'source_parent_sha256': hashlib.sha256(json.dumps(list(range(count)), separators=(',', ':')).encode()).hexdigest()}]}
        full = {'status': 'ok', 'full_fit': True, 'components': [deepcopy(leaf), deepcopy(leaf)]}
        self.assertEqual(full_leaves(full, count), 2)
        for key, value in [('source_rows', 11), ('source_parent_sha256', 'wrong')]:
            bad = deepcopy(full); bad['components'][1]['data_policy_runs'][-1][key] = value
            with self.assertRaisesRegex(ValueError, 'original training rows'):
                full_leaves(bad, count)
        bad = deepcopy(full); bad['components'][1]['full_fit'] = False
        with self.assertRaisesRegex(ValueError, 'non-full'):
            full_leaves(bad, count)


if __name__ == '__main__':
    unittest.main(verbosity=2)
