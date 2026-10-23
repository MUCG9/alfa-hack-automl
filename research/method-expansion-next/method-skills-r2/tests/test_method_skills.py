"""Prepared pure contracts; no application model, API or training data."""
import importlib.util,json,math
from pathlib import Path
import unittest
p=Path(__file__).resolve().parents[1]/'src/automl/search/method_skills.py'
s=importlib.util.spec_from_file_location('pure_method_skills',p)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class MethodSkillContracts(unittest.TestCase):
    def test_only_implemented_tools_are_exposed(self):
        packet,_=m.select_method_skills({'kind':'classification'}, {'lightgbm':{'kinds':['classification']}},600,120)
        self.assertEqual(packet['implemented_tools'],['lightgbm'])
        self.assertEqual([c['id'] for c in packet['selected_cards']],['boosting','feature_preparation','validation_and_budget'])
    def test_extra_trees_and_text_follow_task_properties(self):
        caps={n:{'kinds':['classification','regression']} for n in ['extra_trees','linear_text']}
        plain,_=m.select_method_skills({'kind':'regression','text_features':[]},caps,600,120)
        text,_=m.select_method_skills({'kind':'regression','text_features':['body']},caps,600,120)
        self.assertIn('extra_trees',[c['id'] for c in plain['selected_cards']])
        self.assertNotIn('linear_text',[c['id'] for c in plain['selected_cards']])
        self.assertIn('linear_tabular',[c['id'] for c in plain['selected_cards']])
        self.assertIn('linear_text',[c['id'] for c in text['selected_cards']])
        self.assertNotIn('extra_trees',[c['id'] for c in text['selected_cards']])
    def test_adds_one_field_without_changing_inherited_context(self):
        before={'feedback_read_first':[],'remaining_seconds':400}
        after,receipt=m.attach_method_skills(before,{'kind':'regression'},{},400,120)
        self.assertEqual(before,{'feedback_read_first':[],'remaining_seconds':400})
        after.pop('method_skills');self.assertEqual(after,before)
        self.assertIsNone(receipt['quality_metric'])
    def test_invalid_or_exhausted_budget_is_explicit(self):
        for bad in [float('nan'),float('inf'),-1,True]:
            with self.subTest(value=str(bad)),self.assertRaises(ValueError):
                m.select_method_skills({'kind':'regression'},{},bad,100)
        packet,_=m.select_method_skills({'kind':'regression'},{},10,100)
        self.assertEqual(packet['usable_search_seconds'],0)
    def test_packet_is_bounded_and_does_not_claim_planned_tools_ready(self):
        caps={n:{'kinds':['classification']} for n in ['lightgbm','xgboost','catboost','extra_trees','linear_text','ridge','logistic']}
        packet,receipt=m.select_method_skills({'kind':'classification'},caps,600,120)
        self.assertLessEqual(receipt['packet_UTF8_bytes'],8192)
        self.assertNotIn('ridge',packet['implemented_tools']);self.assertNotIn('logistic',packet['implemented_tools'])
    def test_no_double_injection_or_unimplemented_task_contract(self):
        with self.assertRaises(ValueError):m.attach_method_skills({'method_skills':{}},{'kind':'regression'},{},600,120)
        with self.assertRaises(ValueError):m.select_method_skills({'kind':'regression','task_family':'pointwise_ranking'},{},600,120)

if __name__=='__main__':unittest.main(verbosity=2)
