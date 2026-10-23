"""Unexecuted prospective contracts: no models, API, subprocess or training data.

Apply the reviewed source patch to an isolated copy, then register this file in
its technical check inventory BEFORE a future root-authorized no-fit test run.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import os
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from automl.search.policy import normalize, signature
from automl.search.stages import (CHAMPION_RECIPE_MAX_BYTES, load_champion_recipe,
    prepare_preserved_four_stage_recipes, validate_champion_recipe)


def recipe(engine='lightgbm', **params):
    return normalize({'engine': engine, 'hypothesis': 'synthetic fixture',
                      'params': params, 'feature_code': ''})


def fixtures():
    spec = {'kind': 'regression', 'metric': 'rmse', 'features': ['a', 'b', 'x', 'period'],
            'categorical_features': ['a', 'b'], 'text_features': [], 'time_column': 'period'}
    single = recipe(reg_lambda=5, generic_features='missing')
    other = recipe('catboost')
    control = {'engine': 'ensemble', 'hypothesis': 'preserved fixture', 'params': {},
               'components': [single, other], 'weights': [.9, .1]}
    return spec, [single, other, recipe('xgboost')], control


class ChampionSeedContracts(unittest.TestCase):
    def test_default_omission_matches_none_and_keeps_two_qwen_slots(self):
        spec, base, control = fixtures()
        proposals = [recipe(reg_lambda=9), recipe(reg_lambda=11)]
        first = prepare_preserved_four_stage_recipes(spec, base, proposals, control)
        second = prepare_preserved_four_stage_recipes(spec, base, proposals, control, champion=None)
        self.assertEqual(first, second)
        self.assertEqual(len(first[0]), 7)
        self.assertEqual([r['source'] for r in first[1]],
            ['preserved_complete_control', 'preserved_single_anchor',
             'separate_feature_engineering', 'baseline_family', 'baseline_family', 'qwen', 'qwen'])

    def test_max9_reserves_required5_champion_one_qwen_then_hpo_followup(self):
        spec, base, control = fixtures(); champion = recipe(reg_lambda=9)
        queue, receipts, anchor = prepare_preserved_four_stage_recipes(
            spec, base, [recipe(reg_lambda=11), recipe(reg_lambda=13)], control,
            maximum_initial=7, champion=champion)
        self.assertEqual(len(queue), 7)
        self.assertEqual(queue[0], control)
        self.assertEqual(anchor, control['components'][0])
        self.assertEqual(signature(queue[1]), signature(anchor))
        self.assertEqual(signature(queue[5]), signature(champion))
        self.assertEqual({r['engine'] for r in queue[1:5]}, {'lightgbm', 'catboost', 'xgboost'})
        selected = [r for r in queue if r.get('params', {}).get('feature_selection_top_k')]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['params']['generic_features'], 'broad')
        self.assertTrue(selected[0]['params']['feature_selection_protect_original'])
        self.assertTrue(any(r['status'] == 'not_scheduled_initial_capacity' for r in receipts))
        self.assertEqual(9-len(queue), 2)  # Admission reservation, not proof a fit succeeds.

    def test_caller_objects_and_returned_control_anchor_stay_independent(self):
        spec, base, control = fixtures(); champion = recipe(reg_lambda=9)
        proposals = [recipe(reg_lambda=11)]; before = deepcopy((spec, base, control, champion, proposals))
        queue, _, anchor = prepare_preserved_four_stage_recipes(spec, base, proposals, control, champion=champion)
        queue[0]['components'][0]['params']['reg_lambda'] = 999
        queue[5]['params']['reg_lambda'] = 999
        anchor['params']['reg_lambda'] = 999
        self.assertEqual((spec, base, control, champion, proposals), before)

    def test_hypothesis_integer_float_noop_policy_deduplicate_to_required_anchor(self):
        spec, base, control = fixtures(); champion = deepcopy(base[0])
        champion['hypothesis'] = 'different narrative is not a different executable recipe'
        champion['params']['reg_lambda'] = 5.0; champion['data_policy'] = {}
        queue, receipts, anchor = prepare_preserved_four_stage_recipes(spec, base, [], control, champion=champion)
        self.assertEqual(len(queue), 5)
        self.assertEqual(sum(signature(r)==signature(anchor) for r in queue), 1)
        receipt = next(r for r in receipts if r['source']=='prior_champion')
        self.assertEqual(receipt['status'], 'duplicate'); self.assertEqual(receipt['queue_index'], 1)

    def test_duplicate_qwen_champion_does_not_consume_second_fit_or_slot(self):
        spec, base, control = fixtures(); champion = recipe(reg_lambda=9)
        same = deepcopy(champion); same['hypothesis'] = 'untrusted alternate narrative'
        queue, receipts, _ = prepare_preserved_four_stage_recipes(
            spec, base, [same, recipe(reg_lambda=11)], control, champion=champion)
        self.assertEqual(len(queue), 7)
        self.assertEqual(sum(signature(r)==signature(champion) for r in queue), 1)
        self.assertTrue(any(r['source']=='qwen' and r['status']=='duplicate' for r in receipts))

    def test_family_or_capacity_shortfall_fails_instead_of_weakening_control(self):
        spec, base, control = fixtures(); champion = recipe(reg_lambda=9); before=deepcopy(control)
        with self.assertRaises(ValueError):
            prepare_preserved_four_stage_recipes(spec, base, [], control, maximum_initial=5, champion=champion)
        with self.assertRaises(ValueError):
            prepare_preserved_four_stage_recipes(spec, base[:-1], [], control, champion=champion)
        self.assertEqual(control, before)

    def test_authority_unknown_params_selector_and_free_code_are_rejected(self):
        spec, _, _ = fixtures()
        bad = [dict(recipe(), control_recipe='replace.json'), recipe(feature_selection_top_k=32),
               dict(recipe(), feature_code='def transform(df): return df'),
               {'engine':'lightgbm','params':{'threads':99}},
               {'engine':'ensemble','params':{},'components':[],'weights':[]}]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_champion_recipe(value, spec)

    def test_generic_feature_and_task_specific_combinations_fail_explicitly(self):
        spec, _, _ = fixtures()
        with self.assertRaises(ValueError): validate_champion_recipe(recipe(generic_features='unbounded'), spec)
        with self.assertRaises(ValueError):
            validate_champion_recipe(recipe(feature_views='categorical_te_pair', calibrate=True), spec)
        cls=dict(spec, kind='classification', metric='macro_f1')
        history=recipe(history_asof=True, history_min_periods=3, target_encoding=True, target_encoding_auto_groups=True)
        with self.assertRaises(ValueError): validate_champion_recipe(history, cls)
        with self.assertRaises(ValueError): validate_champion_recipe(recipe(), dict(spec, text_features=['x']))
        self.assertEqual(validate_champion_recipe(history, spec), history)

    def test_loader_hashes_exact_bytes_without_changing_source_and_returns_no_metric(self):
        spec, _, _ = fixtures(); expected=recipe(reg_lambda=9)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'champion.json'; raw=json.dumps(expected, indent=2).encode('utf-8')
            path.write_bytes(raw); actual, receipt=load_champion_recipe(path, spec)
            self.assertEqual(actual, expected); self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(receipt['input_sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(receipt['input_bytes'], len(raw))
            self.assertEqual(receipt['recipe_signature'], signature(actual))
            self.assertIsNone(receipt['metric']); self.assertEqual(receipt['measurement_status'], 'not_run')

    def test_loader_rejects_oversize_duplicate_keys_nonfinite_and_missing_input(self):
        spec, _, _ = fixtures()
        cases=[b' '*(CHAMPION_RECIPE_MAX_BYTES+1),
               b'{"engine":"lightgbm","engine":"catboost","params":{}}',
               b'{"engine":"lightgbm","params":{"reg_lambda":NaN}}',
               b'{"engine":"lightgbm","params":{"reg_lambda":1e309}}']
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'champion.json'
            for raw in cases:
                path.write_bytes(raw)
                with self.subTest(raw_bytes=len(raw)), self.assertRaises(ValueError):load_champion_recipe(path, spec)
            with self.assertRaises(FileNotFoundError):load_champion_recipe(Path(tmp)/'absent.json', spec)

    def test_symlink_and_windows_reparse_are_rejected_without_following(self):
        spec, _, _ = fixtures()
        for info in [SimpleNamespace(st_mode=stat.S_IFLNK, st_file_attributes=0),
                     SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=1024)]:
            with patch.object(Path, 'lstat', return_value=info):
                with self.assertRaises(ValueError):load_champion_recipe('unfollowed.json', spec)

    def test_mutation_during_read_is_rejected_before_recipe_acceptance(self):
        spec, _, _ = fixtures()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'champion.json';path.write_text(json.dumps(recipe()), encoding='utf-8')
            actual=path.stat()
            altered=SimpleNamespace(st_dev=actual.st_dev,st_ino=actual.st_ino,
                st_size=actual.st_size,st_mtime_ns=actual.st_mtime_ns+1)
            with patch('automl.search.stages.os.fstat', side_effect=[actual, altered]):
                with self.assertRaises(ValueError):load_champion_recipe(path, spec)


if __name__ == '__main__': unittest.main(verbosity=2)
