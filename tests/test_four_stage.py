"""Pure four-stage recipe scheduling; no API requests or model fits."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from automl.search.policy import normalize, signature
from automl.search.stages import (choose_hpo_anchor, initial_assessment_status,
                                 prepare_four_stage_recipes)


def spec(kind='classification'):
    return {'kind': kind, 'metric': 'macro_f1' if kind == 'classification' else 'rmse',
            'features': ['unfamiliar_first', 'unfamiliar_second', 'reading'],
            'categorical_features': ['unfamiliar_first', 'unfamiliar_second'], 'text_features': []}


def recipe(engine='lightgbm', name='baseline', **params):
    return {'engine': engine, 'hypothesis': name, 'params': params, 'feature_code': ''}


def baselines():
    return [recipe(name='ordinary'), recipe(name='second ordinary', num_leaves=73),
            recipe(name='semantic anchor', feature_views='categorical_te_pair', calibrate=True),
            recipe('xgboost', 'histogram'), recipe('catboost', 'native categories'),
            recipe('extra_trees', 'randomized trees')]


class FourStageTests(unittest.TestCase):
    def test_initial_assessment_timeout_is_attempted_but_not_validated(self):
        status=initial_assessment_status(None,{'status':'error','exception_type':'TimeoutError'})
        self.assertTrue(status['attempted'])
        self.assertEqual(status['status'],'call_failed')
        self.assertEqual(status['call_status'],'error')
        self.assertFalse(status['assessment_valid'])

    def test_initial_assessment_requires_valid_terminal_json_and_object(self):
        for content in (None,'','not json','{"data_assessment":',json.dumps([])):
            with self.subTest(content=content):
                status=initial_assessment_status(content,{'status':'ok'})
                self.assertFalse(status['assessment_valid'])
                self.assertIn(status['status'],{'invalid_json','invalid_assessment'})
        for assessment in (None,'Generic EDA',[],True):
            with self.subTest(assessment=assessment):
                status=initial_assessment_status(json.dumps({'data_assessment':assessment}),{'status':'ok'})
                self.assertEqual(status['status'],'invalid_assessment')

    def test_missing_or_empty_assessment_does_not_discard_valid_model_recipes(self):
        candidate=recipe(name='usable independent recipe',num_leaves=43)
        content=json.dumps({'candidates':[candidate]})
        status=initial_assessment_status(content,{'status':'ok'})
        self.assertFalse(status['assessment_valid'])
        from automl.search.policy import parse_plans
        plans=parse_plans(content)
        self.assertEqual(plans[0]['params']['num_leaves'],43)

    def test_each_assessment_field_must_be_present_and_nonempty(self):
        good={'validation_risks':['Group identities must stay disjoint'],
              'feature_hypotheses':'Test bounded row-local interactions',
              'model_priorities':['LightGBM','CatBoost']}
        for field in good:
            for invalid in (None,'','   ',[],[''],['good','  '],['good',1],{},True):
                payload=dict(good,**{field:invalid})
                status=initial_assessment_status(json.dumps({'data_assessment':payload}),{'status':'ok'})
                with self.subTest(field=field,invalid=invalid):
                    self.assertFalse(status['assessment_valid'])
                    self.assertIn(field,status['error'])
            payload=dict(good)
            del payload[field]
            self.assertFalse(initial_assessment_status(json.dumps({'data_assessment':payload}),
                                                       {'status':'ok'})['assessment_valid'])

    def test_complete_assessment_succeeds_without_mutating_inputs_or_parsing_recipes(self):
        payload={'data_assessment':{'validation_risks':['No group leakage'],
                  'feature_hypotheses':'Check missingness flags',
                  'model_priorities':['LightGBM','CatBoost']},
                 'candidates':[{'engine':'unsupported-on-purpose'}]}
        call={'status':'ok'}
        before=deepcopy((payload,call))
        status=initial_assessment_status(json.dumps(payload),call)
        self.assertEqual(status,{'status':'ok','attempted':True,'call_status':'ok',
                                 'assessment_valid':True,'error':None})
        self.assertEqual((payload,call),before)

    def test_failed_call_cannot_be_relabelled_success_by_a_valid_payload(self):
        content=json.dumps({'data_assessment':{'validation_risks':'risk',
                    'feature_hypotheses':'feature','model_priorities':'model'}})
        self.assertFalse(initial_assessment_status(content,{'status':'error'})['assessment_valid'])

    def test_hpo_anchor_skips_best_extra_trees_and_failed_supported_records(self):
        records=[{'status':'ok','recipe':recipe('extra_trees')},
                 {'status':'timeout','recipe':recipe('catboost')},
                 {'status':'ok','recipe':recipe('lightgbm')},
                 {'status':'ok','recipe':recipe('xgboost')}]
        before=deepcopy(records)
        self.assertIs(choose_hpo_anchor(records),records[2])
        self.assertEqual(records,before)

    def test_hpo_anchor_is_none_when_no_successful_supported_recipe_exists(self):
        for records in ([],[{'status':'ok','recipe':recipe('extra_trees')}],
                        [{'status':'ok','recipe':recipe('linear_text')},
                         {'status':'error','recipe':recipe('lightgbm')}]):
            with self.subTest(records=records):
                before=deepcopy(records)
                self.assertIsNone(choose_hpo_anchor(records))
                self.assertEqual(records,before)

    def test_semantic_anchor_precedes_qwen_and_model_families_survive(self):
        planned = [recipe(name='qwen first', num_leaves=23), recipe(name='qwen second', num_leaves=43)]
        queue, receipts = prepare_four_stage_recipes(spec(), baselines(), planned, 5)
        self.assertEqual(queue[0]['hypothesis'], 'semantic anchor')
        self.assertEqual(queue[1]['hypothesis'], 'qwen first')
        self.assertEqual({item['engine'] for item in queue}, {'lightgbm', 'xgboost', 'catboost', 'extra_trees'})
        self.assertEqual(len(queue), 5)
        self.assertTrue(any(item['status'] == 'omitted' and 'Family' in item['reason'] for item in receipts))
        self.assertTrue(all(item['params']['generic_features'] == 'broad' for item in queue))

    def test_two_diverse_qwen_proposals_fit_before_missing_baseline_family(self):
        planned = [recipe('xgboost', 'qwen histogram', max_depth=4),
                   recipe('catboost', 'qwen native', depth=5),
                   recipe('extra_trees', 'third qwen', max_depth=20)]
        queue, receipts = prepare_four_stage_recipes(spec(), baselines(), planned, 5)
        self.assertEqual([item['hypothesis'] for item in queue[:3]],
                         ['semantic anchor', 'qwen histogram', 'qwen native'])
        self.assertIn('extra_trees', {item['engine'] for item in queue})
        self.assertNotIn('third qwen', [item['hypothesis'] for item in queue])
        self.assertTrue(any('Two-proposal' in item['reason'] for item in receipts))

    def test_temporal_history_is_anchor_even_after_several_plain_recipes(self):
        base = [recipe('catboost', 'first'), recipe('xgboost', 'second'),
                recipe(name='history anchor', history_asof=True, target_encoding=True,
                       target_encoding_auto_groups=True, history_min_periods=3)]
        queue, _ = prepare_four_stage_recipes(spec('regression'), base, [], 1)
        self.assertEqual(len(queue), 1)
        self.assertTrue(queue[0]['params']['history_asof'])
        self.assertEqual(queue[0]['hypothesis'], 'history anchor')

    def test_dedup_uses_normalized_signature_after_broad_override(self):
        base = [recipe(name='first', generic_features='none'), recipe(name='same', generic_features='missing')]
        queue, receipts = prepare_four_stage_recipes(spec(), base,
            [recipe(name='qwen duplicate', generic_features='skew'), recipe(name='distinct', num_leaves=91)], 9)
        self.assertEqual(len(queue), 2)
        self.assertEqual(len({signature(item) for item in queue}), 2)
        self.assertEqual(sum(item['status'] == 'duplicate' for item in receipts), 2)

    def test_invalid_recipes_have_receipts_and_are_not_silently_repaired(self):
        base = [recipe(name='working baseline')]
        planned = [recipe(name='typo mode', generic_features='broadd'),
                   recipe('unavailable_engine'),
                   dict(recipe(name='conflict', feature_views='categorical_te_pair', calibrate=True),
                        feature_code='def transform(df): return df')]
        queue, receipts = prepare_four_stage_recipes(spec(), base, planned)
        self.assertEqual([item['hypothesis'] for item in queue], ['working baseline'])
        self.assertEqual([item['index'] for item in receipts], [0, 1, 2])
        self.assertTrue(all(item['source'] == 'qwen' and item['status'] == 'rejected' for item in receipts))
        self.assertTrue(all(set(item) == {'source', 'index', 'engine', 'status', 'reason'} for item in receipts))
        with self.assertRaisesRegex(ValueError, 'No valid'):
            prepare_four_stage_recipes(spec(), [], [recipe('unavailable_engine')])

    def test_inputs_are_not_mutated_or_aliased_and_code_is_preserved(self):
        base = [recipe(name='encoded', target_encoding=True,
                       target_encoding_groups=[['unfamiliar_first', 'unfamiliar_second']])]
        code = 'def transform(df):\n    return df.copy()\n'
        planned = [dict(recipe('catboost', 'qwen code', depth=7), feature_code=code)]
        originals = deepcopy((base, planned))
        queue, _ = prepare_four_stage_recipes(spec(), base, planned)
        self.assertEqual((base, planned), originals)
        self.assertEqual(queue[1]['feature_code'], code)
        self.assertEqual(queue[1]['params']['depth'], 7)
        queue[0]['params']['target_encoding_groups'][0][0] = 'modified result'
        self.assertEqual((base, planned), originals)

    def test_text_portfolio_keeps_tfidf_settings_without_broad_or_selector(self):
        actual = dict(spec(), text_features=['text_input'])
        base = [recipe('linear_text', 'word baseline', text_alpha=3e-5),
                recipe('linear_text', 'char baseline', text_char_features=True)]
        queue, _ = prepare_four_stage_recipes(actual, base, [], 5)
        self.assertEqual(len(queue), 2)
        for item in queue:
            self.assertEqual(item['engine'], 'linear_text')
            self.assertNotIn('generic_features', item['params'])
            self.assertNotIn('feature_selection_top_k', item['params'])
        self.assertEqual(queue[0]['params']['text_alpha'], 3e-5)
        self.assertTrue(queue[1]['params']['text_char_features'])

    def test_caps_and_types_are_validated_and_baseline_defaults_stay_unchanged(self):
        base = baselines()
        before = [normalize(deepcopy(item)) for item in base]
        for cap in [0, -1, True, 1.5, '5', None]:
            with self.subTest(cap=cap), self.assertRaisesRegex(ValueError, 'positive integer'):
                prepare_four_stage_recipes(spec(), base, [], cap)
        for cap in [1, 2, 3, 9]:
            queue, _ = prepare_four_stage_recipes(spec(), base, [], cap)
            self.assertLessEqual(len(queue), cap)
            self.assertEqual(queue[0]['hypothesis'], 'semantic anchor')
        self.assertEqual([normalize(deepcopy(item)) for item in base], before)
        self.assertTrue(all('generic_features' not in item['params'] for item in before))


if __name__ == '__main__':
    unittest.main(verbosity=2)
