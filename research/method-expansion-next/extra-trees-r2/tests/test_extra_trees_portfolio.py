"""Prepared no-fit scheduler contracts; not executed in this source-only packet.

Run only after applying the two source overlays to a complete isolated source
tree. The exact baseline companion fixture lives under this tree, never beside
an unrelated development checkout. No model constructors or API calls are used.
"""
import ast
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from automl.search.policy import normalize,signature
from automl.search.stages import (extra_trees_method_recipe,
    prepare_preserved_four_stage_recipes,choose_hpo_anchor)
from automl.execution.api import CAPABILITIES


def task(kind='classification'):
    return {'kind':kind,'metric':'macro_f1' if kind=='classification' else 'rmse',
            'features':['category_a','category_b','measurement'],
            'categorical_features':['category_a','category_b'],'text_features':[]}


def recipe(engine='lightgbm',name='fixture',**params):
    return normalize({'engine':engine,'hypothesis':name,'params':params,'feature_code':''})


def setup_recipes():
    anchor=recipe(num_leaves=63,iterations=400)
    cat=recipe('catboost','native',depth=6)
    xgb=recipe('xgboost','histogram',max_depth=6)
    control={'engine':'ensemble','hypothesis':'complete fixed reference',
             'components':[deepcopy(anchor),deepcopy(cat)],'weights':[.6,.4]}
    return control,[anchor,cat,xgb]


def baseline_scheduler():
    path=ROOT/'tests/fixtures/meth01_baseline_stages.py'
    spec=importlib.util.spec_from_file_location('meth01_portable_baseline',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.prepare_preserved_four_stage_recipes


class ExtraTreesPortfolioContracts(unittest.TestCase):
    def test_default_off_matches_exact_portable_baseline(self):
        for kind in ['regression','classification']:
            control,base=setup_recipes()
            proposals=[recipe(name='novel',num_leaves=211),recipe('catboost','other',depth=7)]
            expected=baseline_scheduler()(task(kind),base,proposals,control,32,7)
            actual=prepare_preserved_four_stage_recipes(task(kind),base,proposals,control,32,7)
            self.assertEqual(actual,expected)

    def test_required_five_and_protected_single_are_exact_then_method_slot_five(self):
        control,base=setup_recipes()
        original,_,anchor=baseline_scheduler()(task(),base,[],control,32,7)
        method=extra_trees_method_recipe(task())
        queue,receipts,protected=prepare_preserved_four_stage_recipes(
            task(),base,[],control,32,7,method_recipe=method)
        self.assertEqual(queue[:5],original)
        self.assertEqual(queue[0],control)
        self.assertEqual(protected,anchor)
        self.assertEqual(queue[5],method)
        self.assertEqual(receipts[5]['source'],'explicit_method_portfolio')
        self.assertFalse(receipts[5]['selector_applied'])

    def test_fixed_cap_displaces_second_optional_proposal_with_receipt(self):
        control,base=setup_recipes()
        proposals=[recipe(name='first novel',num_leaves=211),
                   recipe('catboost','second novel',depth=7)]
        queue,receipts,_=prepare_preserved_four_stage_recipes(task(),base,proposals,control,
            maximum_initial=7,method_recipe=extra_trees_method_recipe(task()))
        self.assertEqual(len(queue),7)
        self.assertEqual(signature(queue[6]),signature(proposals[0]))
        self.assertNotIn(signature(proposals[1]),[signature(r) for r in queue])
        omitted=[r for r in receipts if r['source']=='qwen' and r['status']=='omitted']
        self.assertEqual(len(omitted),1)
        self.assertEqual(omitted[0]['index'],1)

    def test_semantic_dedup_does_not_consume_remaining_novel_slot_or_mutate_inputs(self):
        control,base=setup_recipes()
        method=extra_trees_method_recipe(task())
        duplicate=deepcopy(method)
        duplicate['hypothesis']='different wording is not different computation'
        duplicate['params']['iterations']=128.0
        proposals=[duplicate,recipe(name='novel',num_leaves=211)]
        before=deepcopy((control,base,proposals,method))
        queue,receipts,_=prepare_preserved_four_stage_recipes(task(),base,proposals,control,
            maximum_initial=7,method_recipe=method)
        self.assertEqual((control,base,proposals,method),before)
        self.assertEqual(len({signature(r) for r in queue}),len(queue))
        self.assertEqual(queue[6]['params']['num_leaves'],211)
        self.assertTrue(any(r['source']=='qwen' and r['status']=='duplicate' for r in receipts))
        queue[0]['components'][0]['params']['num_leaves']=999
        queue[5]['params']['max_depth']=40
        self.assertEqual((control,base,proposals,method),before)

    def test_ineligible_tasks_invalid_method_and_missing_family_fail_explicitly(self):
        for spec in [None,{},dict(task(),text_features=['sentence']),
                     dict(task(),task_family='pointwise_ranking'),dict(task(),kind='other')]:
            with self.subTest(spec=spec),self.assertRaises(ValueError):
                extra_trees_method_recipe(spec)
        control,base=setup_recipes()
        altered=extra_trees_method_recipe(task())
        altered['params']['iterations']=129
        with self.assertRaisesRegex(ValueError,'exact bounded'):
            prepare_preserved_four_stage_recipes(task(),base,[],control,method_recipe=altered)
        method=extra_trees_method_recipe(task())
        for cap in [True,5,5.5]:
            with self.subTest(cap=cap),self.assertRaises(ValueError):
                prepare_preserved_four_stage_recipes(task(),base,[],control,
                    maximum_initial=cap,method_recipe=method)
        with self.assertRaisesRegex(ValueError,'five distinct'):
            prepare_preserved_four_stage_recipes(task(),base[:-1],[],control,method_recipe=method)

    def test_hpo_anchor_and_supported_family_coverage_are_preserved(self):
        control,base=setup_recipes()
        queue,_,anchor=prepare_preserved_four_stage_recipes(task(),base,[],control,
            method_recipe=extra_trees_method_recipe(task()))
        self.assertEqual({r['engine'] for r in queue[:5] if r['engine']!='ensemble'},
                         {'lightgbm','catboost','xgboost'})
        records=[{'status':'ok','recipe':queue[5]},{'status':'ok','recipe':anchor}]
        self.assertIs(choose_hpo_anchor(records),records[1])
        self.assertEqual(signature(anchor),signature(control['components'][0]))

    def test_factory_is_bounded_task_generic_and_uses_existing_non_stopping_path(self):
        reg=extra_trees_method_recipe(task('regression'))
        cls=extra_trees_method_recipe(task('classification'))
        self.assertEqual((reg['engine'],cls['engine']),('extra_trees','extra_trees'))
        for candidate in [reg,cls]:
            params=candidate['params']
            self.assertEqual((params['iterations'],params['max_depth'],params['min_samples_leaf'],
                              params['max_features'],params['seed']),(128,16,4,.9,42))
            self.assertEqual(params['generic_features'],'none')
            self.assertEqual(candidate['feature_code'],'')
            for field in ['calibrate','feature_views','target_encoding','history_asof',
                          'feature_selection_top_k','log_target']:
                self.assertFalse(params.get(field,False))
        self.assertNotIn('class_weight_power',reg['params'])
        self.assertEqual(cls['params']['class_weight_power'],.5)
        self.assertFalse(CAPABILITIES['extra_trees']['nested_stopping'])
        self.assertEqual(CAPABILITIES['extra_trees']['category_strategy'],'frequency')

    def test_runner_opt_in_has_no_default_switch_and_preflights_before_artifacts(self):
        tree=ast.parse((ROOT/'src/automl/search/runner.py').read_text(encoding='utf-8'))
        cli=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_main')
        flags=[n for n in ast.walk(cli) if isinstance(n,ast.Call)
               and any(isinstance(a,ast.Constant) and a.value=='--extra-trees-portfolio' for a in n.args)]
        self.assertEqual(len(flags),1)
        kwargs={k.arg:ast.literal_eval(k.value) for k in flags[0].keywords}
        self.assertEqual(kwargs['action'],'store_true')
        self.assertNotIn('default',kwargs)
        solve=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='solve_single')
        preflight=next(n for n in solve.body if isinstance(n,ast.If)
                       and 'extra_trees_portfolio' in ast.unparse(n.test))
        task_contract=next(n for n in solve.body if 'TaskSpec.from_legacy' in ast.unparse(n))
        self.assertLess(preflight.lineno,task_contract.lineno)
        self.assertIn('extra_trees_method_recipe(spec)',ast.unparse(preflight))
        self.assertTrue(any(isinstance(n,ast.Raise) for n in ast.walk(preflight)))


if __name__=='__main__':
    unittest.main(verbosity=2)
