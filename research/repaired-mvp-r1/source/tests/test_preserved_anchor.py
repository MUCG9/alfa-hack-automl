"""Prevent the two measured regressions: mutated controls and duplicate HPO fits."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from automl.search.policy import normalize,signature
from automl.search.stages import prepare_preserved_four_stage_recipes

def recipe(engine='lightgbm',**params):
    return normalize({'engine':engine,'hypothesis':'original','params':params,'feature_code':''})

def inputs():
    spec={'kind':'classification','metric':'macro_f1','features':['a','b','x'],
        'categorical_features':['a','b'],'text_features':[]}
    single=recipe(feature_views='categorical_te_pair',calibrate=True,reg_lambda=5)
    other=recipe('xgboost',calibrate=True)
    control={'engine':'ensemble','hypothesis':'saved control','params':{},
        'components':[single,other],'weights':[.75,.25]}
    base=[single,recipe('catboost'),other]
    return spec,base,control

class PreservedAnchorTests(unittest.TestCase):
    def test_integral_float_hpo_anchor_does_not_trigger_duplicate_fit(self):
        first=recipe(reg_lambda=5)
        second=deepcopy(first);second['params']['reg_lambda']=5.0
        self.assertEqual(first,second)
        self.assertEqual(signature(first),signature(second))

    def test_distinct_numeric_parameter_stays_distinct(self):
        self.assertNotEqual(signature(recipe(reg_lambda=5)),signature(recipe(reg_lambda=5.1)))

    def test_complete_control_and_single_anchor_are_preserved(self):
        spec,base,control=inputs();before=deepcopy((base,control))
        queue,_,anchor=prepare_preserved_four_stage_recipes(spec,base,[],control)
        self.assertEqual(queue[0],control)
        self.assertEqual(queue[1],control['components'][0])
        self.assertEqual(anchor,control['components'][0])
        queue[0]['components'][0]['params']['reg_lambda']=99
        self.assertEqual((base,control),before)

    def test_exactly_one_explicit_selector_branch_and_family_coverage(self):
        spec,base,control=inputs()
        queue,receipts,_=prepare_preserved_four_stage_recipes(spec,base,[],control)
        selected=[r for r in queue if r.get('params',{}).get('feature_selection_top_k')]
        self.assertEqual(len(selected),1)
        self.assertEqual(selected[0]['params']['feature_selection_top_k'],32)
        self.assertTrue(selected[0]['params']['feature_selection_protect_original'])
        self.assertEqual(selected[0]['params']['generic_features'],'broad')
        self.assertTrue({'lightgbm','catboost','xgboost'} <= {r['engine'] for r in queue})
        self.assertTrue(any(r['source']=='preserved_complete_control' for r in receipts))

    def test_qwen_cannot_enable_another_unrecorded_selector(self):
        spec,base,control=inputs()
        proposal=recipe(num_leaves=91,feature_selection_top_k=12)
        queue,_,_=prepare_preserved_four_stage_recipes(spec,base,[proposal],control)
        actual=next(r for r in queue if r.get('params',{}).get('num_leaves')==91)
        self.assertNotIn('feature_selection_top_k',actual['params'])
        self.assertEqual(len(queue),6)

    def test_invalid_control_cannot_silently_become_a_weak_reference(self):
        spec,base,control=inputs()
        for weights in ([1,0],[1,float('nan')],[1],[-1,2]):
            broken=deepcopy(control);broken['weights']=weights
            with self.subTest(weights=weights),self.assertRaises(ValueError):
                prepare_preserved_four_stage_recipes(spec,base,[],broken)

    def test_hpo_integer_float_equivalent_proposal_is_deduplicated(self):
        spec,base,control=inputs()
        proposal=deepcopy(base[0]);proposal['params']['reg_lambda']=5.0
        queue,_,_=prepare_preserved_four_stage_recipes(spec,base,[proposal],control)
        matches=[r for r in queue if signature(r)==signature(base[0])]
        self.assertEqual(len(matches),1)

if __name__=='__main__': unittest.main(verbosity=2)
