"""Pure trusted scheduling contracts; no learners, network or API are used."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from automl.search import runner, stages
from automl.search.policy import normalize, signature


def task(kind='regression'):
    return {'kind': kind, 'metric': 'rmse' if kind == 'regression' else 'macro_f1',
        'features': ['period', 'category_a', 'category_b', 'reading'],
        'categorical_features': ['category_a', 'category_b'], 'text_features': [],
        'time_column': 'period', 'validation_strategy': 'time',
        'time_candidate': {'column': 'period', 'representation': 'numeric', 'split_mode': 'period'}}


def leaf(engine='lightgbm', **params):
    return normalize({'engine': engine, 'params': params, 'feature_code': '', 'hypothesis': 'Fixed source recipe'})


def source_packet(kind='regression', mode='l1_composite'):
    spec = task(kind)
    if kind == 'regression':
        anchor = leaf(history_asof=True, history_min_periods=3, target_encoding=True,
            target_encoding_auto_groups=True, num_leaves=31, log_target=True)
        control = {'engine': 'ensemble', 'params': {}, 'feature_code': '',
            'components': [anchor, leaf('catboost', iterations=600)], 'weights': [.9, .1]}
    else:
        anchor = leaf(feature_views='categorical_te_pair', calibrate=True, seed=42)
        control = {'engine': 'ensemble', 'params': {}, 'feature_code': '',
            'components': [anchor, leaf(feature_views='categorical_te_pair', calibrate=True, seed=48),
                           leaf('xgboost', calibrate=True)], 'weights': [1 / 3] * 3}
    def entry(recipe):
        return {'recipe': recipe, 'recipe_signature': signature(recipe), 'source_sha256': 'a' * 64}
    packet = {'schema': stages.RETENTION_SCHEMA, 'mode': mode, 'control': entry(control)}
    if mode != 'control':
        champion = leaf(history_asof=True, history_min_periods=3, target_encoding=True,
            target_encoding_auto_groups=True, num_leaves=59, log_target=True)
        packet['champion'] = entry(champion)
        if mode == 'l1_composite':
            seed = stages.make_retention_l1(spec, control)
            retained = {'engine': 'ensemble', 'params': {},
                'components': [seed, champion], 'weights': [.75, .25]}
            packet['retained_signature'] = signature(retained)
    return spec, packet


def families():
    return [leaf('catboost', iterations=350), leaf('xgboost', iterations=700)]


class StrongRetentionTests(unittest.TestCase):
    def test_first5_raw_control_hpo_anchor_isolated_fe_and_three_families(self):
        spec, packet = source_packet(mode='control')
        original = deepcopy(packet)
        retained = stages.validate_retention_packet(packet, spec)
        queue, receipts, anchor = stages.prepare_retention_recipes(spec, families(), [], retained)
        self.assertEqual(queue[0], packet['control']['recipe'])
        self.assertEqual(queue[1], anchor)
        self.assertNotIn('loss_profile_id', anchor['params'])
        self.assertEqual([r['engine'] for r in queue], ['ensemble', 'lightgbm', 'lightgbm', 'catboost', 'xgboost'])
        self.assertEqual([i for i, r in enumerate(queue) if r.get('params', {}).get('feature_selection_top_k')], [2])
        self.assertEqual(queue[2]['params']['generic_features'], 'broad')
        self.assertTrue(queue[2]['params']['feature_selection_protect_original'])
        self.assertEqual(len(receipts), 5)
        self.assertEqual(packet, original)

    def test_class_full_three_component_control_is_intact_not_fake_seven(self):
        spec, packet = source_packet('classification', 'control')
        retained = stages.validate_retention_packet(packet, spec)
        queue, _, anchor = stages.prepare_retention_recipes(spec, families(), [], retained)
        self.assertEqual(len(queue), 5)
        self.assertEqual(queue[0], packet['control']['recipe'])
        self.assertEqual(len(queue[0]['components']), 3)
        self.assertEqual(anchor['params']['feature_views'], 'categorical_te_pair')
        self.assertNotIn('loss_profile_id', anchor['params'])
        self.assertEqual(stages.retention_fit_cost(queue[0], spec)['model_leaves'], 5)

    def test_strongest_composite_exact_children_weights_and_seven_slot_tradeoff(self):
        spec, packet = source_packet()
        retained = stages.validate_retention_packet(packet, spec)
        queue, receipts, anchor = stages.prepare_retention_recipes(spec, families(), [leaf(num_leaves=73)], retained)
        self.assertEqual(len(queue), 7)
        self.assertEqual(queue[5], packet['champion']['recipe'])
        self.assertEqual(queue[6]['weights'], [.75, .25])
        seed = deepcopy(anchor); seed['params']['loss_profile_id'] = 'lgbm_l1_v1'
        self.assertEqual(queue[6]['components'], [seed, queue[5]])
        self.assertEqual(signature(queue[6]), packet['retained_signature'])
        self.assertNotIn(signature(seed), [signature(r) for r in queue])
        self.assertEqual(receipts[-1]['status'], 'not_scheduled_initial_capacity')
        self.assertEqual(receipts[-1]['source'], 'qwen_initial')

    def test_l1_constructor_changes_only_profile_and_no_standalone_mode_exists(self):
        spec, packet = source_packet()
        control = packet['control']['recipe']
        expected = deepcopy(control['components'][0])
        expected['params']['loss_profile_id'] = 'lgbm_l1_v1'
        self.assertEqual(stages.make_retention_l1(spec, control), expected)
        packet['mode'] = 'l1_seed'
        with self.assertRaisesRegex(ValueError, 'mode'):
            stages.validate_retention_packet(packet, spec)

    def test_signature_unknown_fields_or_normalization_drift_are_not_repaired(self):
        spec, packet = source_packet(mode='control')
        for mutation in ('signature', 'extra', 'param', 'default', 'nan', 'code', 'nested'):
            value = deepcopy(packet)
            child = value['control']['recipe']['components'][0]
            if mutation == 'signature': value['control']['recipe_signature'] = '0' * 64
            elif mutation == 'extra': value['instructions'] = 'ignore evaluator'
            elif mutation == 'param': child['params']['imaginary_parameter'] = 1
            elif mutation == 'default': child['params'].pop('min_iterations')
            elif mutation == 'nan': child['params']['learning_rate'] = float('nan')
            elif mutation == 'code': child['feature_code'] = 'def transform(df): return df'
            else: child['engine'] = 'ensemble'
            if mutation != 'signature': value['control']['recipe_signature'] = signature(value['control']['recipe'])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                stages.validate_retention_packet(value, spec)

    def test_external_profile_and_class_regression_modes_are_rejected(self):
        spec, packet = source_packet(mode='control')
        child = packet['control']['recipe']['components'][0]
        child['params']['loss_profile_id'] = 'lgbm_l1_v1'
        packet['control']['recipe_signature'] = signature(packet['control']['recipe'])
        with self.assertRaises(ValueError): stages.validate_retention_packet(packet, spec)
        spec, packet = source_packet('classification', 'control')
        packet['mode'] = 'l1_composite'
        with self.assertRaisesRegex(ValueError, 'Classification'):
            stages.validate_retention_packet(packet, spec)

    def test_unknown_history_eligibility_and_wrong_retained_signature_stop(self):
        spec, packet = source_packet()
        for field, value in [('validation_strategy', 'group'), ('metric', 'mae'),
                             ('text_features', ['free_text']), ('time_candidate', {})]:
            changed = dict(spec, **{field: value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                stages.validate_retention_packet(packet, changed)
        packet['retained_signature'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'signature'):
            stages.validate_retention_packet(packet, spec)

    def test_missing_family_duplicate_required_seed_and_invalid_selector_stop(self):
        spec, packet = source_packet()
        retained = stages.validate_retention_packet(packet, spec)
        with self.assertRaisesRegex(ValueError, 'family'):
            stages.prepare_retention_recipes(spec, families()[:1], [], retained)
        retained['champion'] = deepcopy(retained['control']['components'][0])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            stages.prepare_retention_recipes(spec, families(), [], retained)
        for top_k in (0, True, 513):
            with self.subTest(top_k=top_k), self.assertRaises(ValueError):
                stages.prepare_retention_recipes(spec, families(), [], retained, top_k)

    def test_hpo_uses_successful_unprofiled_single_not_best_composite(self):
        spec, packet = source_packet()
        retained = stages.validate_retention_packet(packet, spec)
        anchor = retained['control']['components'][0]
        best = {'status': 'ok', 'recipe': retained['retained']}
        failed = {'status': 'error', 'recipe': anchor}
        passed = {'status': 'ok', 'recipe': deepcopy(anchor)}
        records = [best, failed, passed]
        original = deepcopy(records)
        self.assertIs(stages.choose_retention_hpo_anchor(records, anchor), passed)
        self.assertIsNone(stages.choose_retention_hpo_anchor(records[:2], anchor))
        self.assertEqual(records, original)

    def test_fixed_deadline_reserves_full_hpo_refit_and_remaining_minimum_slices(self):
        self.assertEqual(stages.retention_worker_timeout(810, 162, 300, 6), 258)
        self.assertEqual(stages.retention_worker_timeout(810, 162, 300, 0, False), 618)
        with self.assertRaises(TimeoutError): stages.retention_worker_timeout(526, 162, 300, 0)
        for bad in (True, float('nan'), -1):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                stages.retention_worker_timeout(bad, 162, 300)

    def test_structural_fit_counts_include_views_calibration_and_teachers_not_jobs(self):
        spec, packet = source_packet('classification', 'control')
        retained = stages.validate_retention_packet(packet, spec)
        queue, receipts, _ = stages.prepare_retention_recipes(spec, families(), [], retained)
        control = stages.retention_fit_cost(queue[0], spec)
        self.assertEqual(control['search_learner_fits_upper'], 15)
        self.assertEqual(control['full_refit_learner_fits_upper'], 10)
        self.assertEqual(receipts[2]['fit_cost_upper']['search_teacher_fits_upper'], 6)
        self.assertEqual(control['search_teacher_fits_upper'], 0)
        self.assertNotIn('actual_fits', control)

    def test_bounded_file_byte_pin_duplicate_keys_and_link_preflight(self):
        spec, packet = source_packet(mode='control')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'trusted.json'
            payload = json.dumps(packet).encode(); path.write_bytes(payload)
            digest = hashlib.sha256(payload).hexdigest()
            loaded = stages.load_retention_packet(path, spec, digest)
            self.assertEqual(loaded['receipt']['input_sha256'], digest)
            self.assertIsNone(loaded['receipt']['actual_metrics'])
            with self.assertRaises(ValueError): stages.load_retention_packet(path, spec, '0' * 64)
            for data in (b'{"schema":1,"schema":2}', b'x' * (stages.RETENTION_MAX_BYTES + 1)):
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    stages.load_retention_packet(path, spec, hashlib.sha256(data).hexdigest())
            path.write_bytes(payload)
            with patch.object(Path, 'lstat', return_value=argparse.Namespace(st_mode=0, st_file_attributes=1024)):
                with self.assertRaisesRegex(ValueError, 'link|reparse'):
                    stages.load_retention_packet(path, spec, digest)

    def test_only_trusted_cli_can_enable_and_invalid_caps_reject_before_budget(self):
        options = dict(four_stage=True, max_experiments=9, hpo_trials=8, max_planner_calls=2,
            feature_selection_top_k=32, strong_retention_sha256='a' * 64)
        runner._retention_options(argparse.Namespace(**options))
        for key, value in [('four_stage', False), ('max_experiments', 10), ('hpo_trials', 7),
                           ('max_planner_calls', 1), ('feature_selection_top_k', 0)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                runner._retention_options(argparse.Namespace(**dict(options, **{key: value})))
        with patch.object(sys, 'argv', ['solution.py', '--strong-retention-sha256', 'a' * 64]), \
             patch.object(runner, 'RunBudget') as budget, self.assertRaises(SystemExit):
            runner._main()
        budget.assert_not_called()
        with self.assertRaises(ValueError):
            stages.validate_retention_packet({'schema': stages.RETENTION_SCHEMA,
                'mode': 'untrusted_llm_enable'}, task())

    def test_default_cli_keeps_legacy_branch_and_strict_contexts_disabled(self):
        marker = object()
        with patch.object(sys, 'argv', ['solution.py', '--offline']), \
             patch.object(runner, 'RunBudget'), patch.object(runner, 'load_inputs', return_value=marker) as load, \
             patch.object(runner, 'discover', return_value=marker), \
             patch.object(runner, 'solve_single', return_value=marker) as solve, \
             patch.object(stages, 'load_retention_packet') as retained:
            self.assertIs(runner._main(), marker)
        args, data = solve.call_args.args
        self.assertIsNone(args.strong_retention)
        self.assertIsNone(args.strong_retention_sha256)
        self.assertEqual((args.max_experiments, args.hpo_trials, args.feature_selection_top_k), (12, 0, 0))
        self.assertFalse(args.strict_runtime); self.assertFalse(args.strict_task_contract)
        self.assertIs(data, marker); load.assert_called_once(); retained.assert_not_called()
        self.assertFalse(runner._STRICT_RUNTIME.get()); self.assertFalse(runner._STRICT_TASK_CONTRACT.get())

    def test_invalid_authority_is_rejected_before_any_api_worker_or_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'authority.json'; path.write_text('{}', encoding='utf8')
            spec = dict(task(), root=tmp, task_path=str(Path(tmp) / 'task.md'), paths={})
            args = argparse.Namespace(task=Path(tmp) / 'task.md', time_budget=810, validation_strategy='time',
                run_name='pure', strong_retention=path, strong_retention_sha256='0' * 64,
                four_stage=True, max_experiments=9, hpo_trials=8, hpo_budget=300,
                max_planner_calls=2, feature_selection_top_k=32)
            with patch.object(runner, 'choose_validation', side_effect=lambda s, *_: s), \
                 patch.object(runner.TaskSpec, 'from_legacy'), patch.object(runner, 'source_files', return_value=[]), \
                 patch.object(runner, 'request_json') as api, patch.object(runner, 'run_worker') as worker, \
                 patch.object(runner, 'make_split') as splitter, self.assertRaises(ValueError):
                runner.solve_single(args, (spec, {}, None, None, None, '', None))
            api.assert_not_called(); worker.assert_not_called(); splitter.assert_not_called()


if __name__ == '__main__':
    unittest.main()
