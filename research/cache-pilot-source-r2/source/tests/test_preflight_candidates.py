"""Fitting-X preflight and mocked code-only repair; no API calls or ML fits."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tools'))

import numpy as np
import pandas as pd

from preflight_candidates import fitting_sample, lint_feature_code, preflight_candidates


BAD = '''def transform(df):
    out = df.copy()
    upper = ['high_a', 'high_b']
    lower = ['low_a', 'low_b']
    out['spread'] = (out[upper] - out[lower]).mean(axis=1)
    return out
'''
GOOD = BAD.replace('out[lower]', 'out[lower].set_axis(upper, axis=1)')


def fixture():
    x = np.arange(30, dtype=float)
    return pd.DataFrame({'high_a': x + 5, 'high_b': x + 8, 'low_a': x, 'low_b': x / 2},
                        index=np.arange(30) + 100)


def candidates():
    recipe = {'engine': 'lightgbm', 'params': {'num_leaves': 31}, 'feature_code': '', 'hypothesis': 'fixed'}
    control = {'name': 'control', 'recipe': recipe}
    bad = deepcopy(control)
    bad['name'] = 'feature-proposal'
    bad['recipe']['feature_code'] = BAD
    return [control, bad]


class PreflightTests(unittest.TestCase):
    def test_alignment_bug_is_all_missing_and_positional_repair_is_usable(self):
        x = fixture()
        bad = lint_feature_code(BAD, x, ('target', 'record_id'))
        self.assertTrue(bad['contract_passed'])
        self.assertEqual(bad['status'], 'repairable_defect')
        self.assertEqual(bad['all_missing_features'], ['spread'])
        self.assertEqual(bad['features'][0]['finite_count'], 0)
        good = lint_feature_code(GOOD, x)
        self.assertEqual(good['status'], 'ok')
        self.assertEqual(good['features'][0]['nonmissing_count'], len(x))
        self.assertGreater(good['features'][0]['unique_nonmissing'], 1)

    def test_constants_are_descriptive_and_never_trigger_repair_by_themselves(self):
        code = "def transform(df):\n    out=df.copy()\n    out['constant']=1.\n    return out"
        result = lint_feature_code(code, fixture())
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['constant_features'], ['constant'])
        self.assertEqual(result['all_missing_features'], [])

    def test_targets_ids_and_raw_schema_mutations_fail_closed(self):
        for code in ["def transform(df):\n    out=df.copy()\n    out['f']=out['target']\n    return out",
                     "def transform(df):\n    out=df.copy()\n    out['record_id']=1\n    return out",
                     "def transform(df):\n    out=df.copy()\n    out['high_a']=0\n    return out"]:
            with self.subTest(code=code):
                result = lint_feature_code(code, fixture(), ('target', 'record_id'))
                self.assertEqual(result['status'], 'rejected')
                self.assertFalse(result['contract_passed'])
        x = fixture().assign(target=42)
        self.assertEqual(lint_feature_code('', x, ('target',))['status'], 'rejected')

    def test_sample_never_contains_outer_rows_and_is_bounded_and_reproducible(self):
        train = pd.DataFrame({'safe_feature': np.arange(5000), 'target': -np.arange(5000)})
        spec = {'features': ['safe_feature'], 'target': 'target', 'id': None}
        fitting = np.arange(4000)
        with patch('preflight_candidates.choose_validation', side_effect=lambda spec, *args: spec), \
             patch('preflight_candidates.make_split', return_value=(fitting, np.arange(4000, 5000), {'split_sha256': 'fixed'})):
            _, first, rows, metadata = fitting_sample(spec, train, np.arange(5000))
            train.loc[4000:, 'safe_feature'] = -999999
            _, second, second_rows, second_metadata = fitting_sample(spec, train, np.arange(5000))
        self.assertEqual(len(first), 2048)
        self.assertTrue(set(rows) <= set(fitting))
        self.assertNotIn('target', first)
        self.assertTrue((first.safe_feature >= 0).all())
        pd.testing.assert_frame_equal(first, second)
        np.testing.assert_array_equal(rows, second_rows)
        self.assertEqual(metadata, second_metadata)

    def test_default_has_no_api_calls_and_preserves_original_bad_proposal(self):
        original, x = candidates(), fixture()
        before = deepcopy(original)
        requester = Mock(side_effect=AssertionError('No API allowed'))
        result = preflight_candidates(original, x, requester=requester)
        requester.assert_not_called()
        self.assertEqual(result['original_candidates'], before)
        self.assertEqual(result['validated_candidates'], before[:1])
        self.assertEqual(result['repaired_candidates'], before[:1])
        self.assertEqual(result['receipts'][1]['status'], 'invalid_original_preserved')
        self.assertEqual(original, before)

    def test_repair_keeps_hyperparameters_and_uses_only_schema_code_diagnostics(self):
        original, x = candidates(), fixture()
        before, before_x = deepcopy(original), x.copy(deep=True)
        requester = Mock(return_value=(json.dumps({'feature_code': GOOD, 'reason': 'Positional pairing'}),
                                       {'status': 'ok', 'attempts': 1}))
        result = preflight_candidates(original, x, ('target',), repair=True, requester=requester)
        self.assertEqual(result['repair_calls'], 1)
        self.assertEqual(result['receipts'][1]['status'], 'repaired')
        self.assertEqual(result['repaired_candidates'][0], before[0])
        repaired = result['repaired_candidates'][1]
        self.assertEqual(repaired['recipe']['params'], before[1]['recipe']['params'])
        self.assertEqual(repaired['recipe']['feature_code'], GOOD)
        self.assertNotEqual(result['receipts'][1]['code_before_sha256'], result['receipts'][1]['code_after_sha256'])
        context = requester.call_args.args[1]
        self.assertEqual(set(context), {'original_code', 'schema', 'diagnostics'})
        self.assertEqual(context['schema'], {column: 'float64' for column in x})
        self.assertNotIn('target', context['schema'])
        self.assertNotIn('rows', context)
        self.assertEqual(original, before)
        pd.testing.assert_frame_equal(x, before_x)

    def test_repair_cannot_drop_features_or_change_recipe_fields(self):
        for reply in [{'feature_code': 'def transform(df): return df.copy()', 'reason': 'Delete feature'},
                      {'feature_code': GOOD, 'reason': 'Also change params', 'params': {'num_leaves': 127}}]:
            requester = Mock(return_value=(json.dumps(reply), {'status': 'ok'}))
            result = preflight_candidates(candidates(), fixture(), repair=True, requester=requester)
            self.assertEqual(result['receipts'][1]['status'], 'unrepaired')
            self.assertEqual(len(result['repaired_candidates']), 1)
            self.assertEqual(result['repair_calls'], 1)

    def test_call_cap_is_per_file_and_invalid_limits_are_rejected(self):
        items = candidates()
        items.append(deepcopy(items[1]))
        requester = Mock(return_value=(json.dumps({'feature_code': GOOD, 'reason': 'Fix pairing'}), {'status': 'ok'}))
        result = preflight_candidates(items, fixture(), repair=True, max_repairs=1, requester=requester)
        self.assertEqual(requester.call_count, 1)
        self.assertEqual(result['repair_calls'], 1)
        for invalid in [-1, 3, True, '1']:
            with self.subTest(limit=invalid), self.assertRaisesRegex(ValueError, 'max_repairs'):
                preflight_candidates(items, fixture(), max_repairs=invalid)


if __name__ == '__main__':
    unittest.main(verbosity=2)
