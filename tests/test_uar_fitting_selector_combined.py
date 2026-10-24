"""Prepared interaction mocks only; no real strict input, gateway, child or fit."""
import ast
from copy import deepcopy
import inspect
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from automl.contracts.metrics import MetricSpec
from automl.search import fit_context_gateway as G
from automl.search import runner as R
_STRICT_FLOW_SOURCE_FUNCTION=R._strict_task_flow


def actual_strict_scope(args,budget,solve):
    """Run the exact final strict-flow authority branch, mocking only its inputs.

    This is not a full-loader fixture: the separate26 extractor/native and14
    consumer contracts cover those boundaries. The compiled AST below is the
    original branch plus its existing OFF return, without rewriting its body.
    """
    flow=ast.parse(inspect.getsource(_STRICT_FLOW_SOURCE_FUNCTION)).body[0]
    index=next(i for i,n in enumerate(flow.body) if isinstance(n,ast.If) and any(
        isinstance(c,ast.Call) and isinstance(c.func,ast.Name) and c.func.id=='getattr'
        and len(c.args)>1 and isinstance(c.args[1],ast.Constant)
        and c.args[1].value=='fitting_context_initial' for c in ast.walk(n.test)))
    body=deepcopy(flow.body[index:])
    function=ast.FunctionDef(name='strict_scope',args=ast.arguments(posonlyargs=[],args=[],
        kwonlyargs=[],kw_defaults=[],defaults=[]),body=body,decorator_list=[])
    module=ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[]))
    metric=MetricSpec('rmse','minimize','value','resolved','synthetic explicit objective')
    frame=object();spec={'metric':'rmse','target':'response','features':['feature']}
    namespace=dict(R.__dict__,args=args,budget=budget,solve_single=solve,
        task_data=[spec,None,frame],spec=spec,declared=object(),
        early=SimpleNamespace(metric_spec=metric),check=Mock(),fingerprints={},paths={})
    exec(compile(module,'<exact-reviewed-strict-scope>','exec'),namespace)
    return namespace['strict_scope']()


class FittingSelectorInteractionContracts(unittest.TestCase):
    def test_four_independent_flag_combinations_use_real_scope_and_restore_after_exception(self):
        for context_on in [False,True]:
            for cache_on in [False,True]:
                for fail in [False,True]:
                    argv=['solution.py','explicit-task.md','--offline','--strict-runtime',
                          '--strict-task-contract','--four-stage']
                    if context_on:argv.append('--fitting-context-initial')
                    if cache_on:argv.append('--selector-importance-cache')
                    observations=[]
                    original_fitting=R._FITTING_INITIAL_AUTHORITY.get()
                    original_cache=R._SELECTOR_IMPORTANCE_CACHE.get()
                    budget=SimpleNamespace(started=1.,deadline=100.,clock=lambda:2.)
                    manager=Mock();manager.__enter__=Mock(return_value=budget);manager.__exit__=Mock(return_value=False)

                    def solve(args,task_data):
                        authority=R._FITTING_INITIAL_AUTHORITY.get()
                        observations.append((type(authority) is G.InitialFittingAuthority,
                                             R._SELECTOR_IMPORTANCE_CACHE.get()))
                        job=R._selector_cache_job({'recipe':{'engine':'lightgbm'}})
                        self.assertEqual(job.get('selector_importance_cache',False),cache_on)
                        if context_on:self.assertIs(authority.producer_budget,budget)
                        if fail:raise RuntimeError('synthetic-solver-failure')
                        return 'synthetic-result'

                    with self.subTest(context=context_on,cache=cache_on,fail=fail), \
                         patch.object(sys,'argv',argv),patch.object(R,'RunBudget',return_value=manager), \
                         patch.object(R,'_strict_task_flow',side_effect=lambda a,b:actual_strict_scope(a,b,solve)):
                        if fail:
                            with self.assertRaisesRegex(RuntimeError,'synthetic-solver-failure'):R._main()
                        else:self.assertEqual(R._main(),'synthetic-result')
                    self.assertEqual(observations,[(context_on,cache_on)])
                    self.assertIs(R._FITTING_INITIAL_AUTHORITY.get(),original_fitting)
                    self.assertIs(R._SELECTOR_IMPORTANCE_CACHE.get(),original_cache)

    def test_followup_feedback_is_unchanged_and_never_relabelled_fitting_only(self):
        spec=dict(metric='macro_f1',greater_is_better=True,features=['f'],target='label',id='identifier')
        profile=dict(target_summary={'all_training_rows':123},features=[{'feature':'f'}],dictionary=[])
        split=dict(validation_class_counts={'a':2,'b':1})
        record=dict(status='ok',recipe={'engine':'lightgbm','params':{}},
                    metrics={'macro_f1':.5,'per_class_f1':{'a':.6,'b':.4}},wall_seconds=2.)
        baseline=R.planner_context(spec,profile,'declared task',split,[record],record,120,2)
        for context_on in [False,True]:
            for cache_on in [False,True]:
                token=R._FITTING_INITIAL_AUTHORITY.set(object() if context_on else None)
                cache_token=R._SELECTOR_IMPORTANCE_CACHE.set(cache_on)
                try:actual=R.planner_context(spec,profile,'declared task',split,[record],record,120,2)
                finally:
                    R._SELECTOR_IMPORTANCE_CACHE.reset(cache_token)
                    R._FITTING_INITIAL_AUTHORITY.reset(token)
                self.assertEqual(json.dumps(actual,sort_keys=True),json.dumps(baseline,sort_keys=True))
                self.assertEqual(actual['feedback_read_first'][0]['value'],.5)
                self.assertEqual(actual['split'],split)
                self.assertEqual(actual['data_summary']['target_summary'],profile['target_summary'])
                self.assertNotIn('fitting_context',actual)


if __name__=='__main__':unittest.main(verbosity=2)
