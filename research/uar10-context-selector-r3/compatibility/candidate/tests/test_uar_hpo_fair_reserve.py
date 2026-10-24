"""Prepared synthetic HPO scheduling contracts. No learner/process/API execution.

The future root lease must use a merged authoritative source tree. The one
modular AST proof is excluded from flat mapping; every other method is portable.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from automl.search import hpo, runner


class FakeClock:
    def __init__(self):
        self.now = 0.

    def __call__(self):
        return self.now


class Trial:
    def __init__(self, params):
        self.params, self.state = params, None

    def suggest_int(self, name, low, high):
        assert low <= self.params[name] <= high
        return self.params[name]

    def suggest_float(self, name, low, high, **unused):
        assert low <= self.params[name] <= high
        return self.params[name]


class Study:
    def __init__(self, duplicate=False):
        self.trials, self.anchor, self.duplicate = [], None, duplicate

    def enqueue_trial(self, params):
        self.anchor = copy.deepcopy(params)

    def ask(self):
        number = len(self.trials)
        identity = 2 if self.duplicate and number == 3 else number
        params = copy.deepcopy(self.anchor)
        params['reg_lambda'] += identity * .125
        trial = Trial(params)
        self.trials.append(trial)
        return trial

    def tell(self, trial, *value, state=None):
        trial.state = 'complete' if value else state


def origin(prior='ok', killed=None, primary=None):
    return dict(schema='hpo-fair-reserve-worker-origin-v1', cleanup_confirmed=True,
        coordinator_killed=killed, primary_exception_type=primary, prior_result_status=prior)


def _composed_runner_off(tree):
    """Normalize exact reviewed independent layers before the OLD golden proof.

    Work on a private AST; validate every consumed shape/count before returning.
    A modified same-name helper/If/args/hook cannot be silently discarded.
    Unrelated nodes remain for the unchanged independent old witness to reject.
    """
    markers={'_fitting_context_initial_options', 'prepared_fitting', '_selector_cache_job', '_SELECTOR_IMPORTANCE_CACHE', '_FITTING_INITIAL_AUTHORITY'}
    def names(node):
        return {v for n in ast.walk(node) for v in ([n.id] if isinstance(n,ast.Name)
            else [n.name] if isinstance(n,(ast.FunctionDef,ast.ClassDef,ast.alias))
            else [n.arg] if isinstance(n,(ast.arg,ast.keyword)) else [])}
    if not names(tree)&markers:return tree
    class _Recorded(ast.NodeTransformer):
        def __init__(self):self.consumed={}
        def record(self,node):
            key=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
            self.consumed[key]=self.consumed.get(key,0)+1
        def visit(self,node):
            before=ast.parse(ast.unparse(node)).body[0] if isinstance(node,ast.stmt) else node
            key=hashlib.sha256(ast.dump(before,include_attributes=False).encode()).hexdigest()
            result=super().visit(node)
            if result is None or type(result) is list:self.consumed[key]=self.consumed.get(key,0)+1
            return result

    class _Selector(_Recorded):
        def visit_FunctionDef(self,node):
            if node.name=='_selector_cache_job':return None
            return self.generic_visit(node)
        def visit_Assign(self,node):
            if any(isinstance(n,ast.Name) and n.id in {'_SELECTOR_IMPORTANCE_CACHE','cache_token'} for n in node.targets):return None
            return self.generic_visit(node)
        def visit_Expr(self,node):
            call=node.value
            if isinstance(call,ast.Call):
                if isinstance(call.func,ast.Name) and call.func.id=='_selector_cache_job':return None
                if isinstance(call.func,ast.Attribute):
                    if isinstance(call.func.value,ast.Name) and call.func.value.id=='_SELECTOR_IMPORTANCE_CACHE' and call.func.attr=='reset':return None
                    if call.func.attr=='add_argument' and call.args and isinstance(call.args[0],ast.Constant) and call.args[0].value=='--selector-importance-cache':return None
            return self.generic_visit(node)

    class ContextOff(ast.NodeTransformer):
        def visit_FunctionDef(self,node):
            if node.name=='_fitting_context_initial_options':return None
            return self.generic_visit(node)
        def visit_Assign(self,node):
            if any(isinstance(n,ast.Name) and n.id in ('_FITTING_INITIAL_AUTHORITY','prepared_fitting') for n in node.targets):return None
            return node
        def visit_Expr(self,node):
            call=node.value
            if isinstance(call,ast.Call):
                if isinstance(call.func,ast.Name) and call.func.id=='_fitting_context_initial_options':return None
                if isinstance(call.func,ast.Attribute) and call.func.attr=='add_argument' and call.args and isinstance(call.args[0],ast.Constant) and call.args[0].value=='--fitting-context-initial':return None
            return node
        def visit_If(self,node):
            if any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='getattr' and len(n.args)>1 and isinstance(n.args[1],ast.Constant) and n.args[1].value=='fitting_context_initial' for n in ast.walk(node.test)):
                return [self.visit(n) for n in node.orelse]
            if isinstance(node.test,ast.Compare) and isinstance(node.test.left,ast.Name) and node.test.left.id=='prepared_fitting':
                if isinstance(node.test.ops[0],ast.Is):return [self.visit(n) for n in node.body]
                if isinstance(node.test.ops[0],ast.IsNot):return []
            return self.generic_visit(node)
    class _Context(_Recorded,ContextOff):pass

    result=ast.parse(ast.unparse(tree))
    selector=_Selector();result=selector.visit(result)
    context=_Context();result=context.visit(result);counts={'selector':selector.consumed,'context':context.consumed}
    if counts!={'selector': {'469f844e78e10a2563cc642e8e95179a5ccca0c8c3d5f6f84715bd4e9cc9dc36': 1, '1e2e4465e1fc5c4223257471ac24ec7c88ce76bad3828ce7147022ec428d6cb0': 1, '0c487b8d34d9688e6d3f2b58caf56ef46d37af4a7af41f0813c112a806001006': 2, 'dda23977686372768ca2ae9aadcc33c0b727c07efd59131eab009972ed78cfda': 1, '1a6833e0bc8f60acc7c1a75877e157e0a79f4cec86518c4d2057af3b9518b238': 1, 'e02b9e009b9bf386a0b022df7b80959bda000665fa00aa2ab18f02114e59e0cb': 1}, 'context': {'2bbaa9c0c97981a8d370af665fceac0f28a3f42781cef6c365dfca88f52592ae': 1, 'e65eb4b219b8ced3009c12f0d05063a1acfe14c997f8e8ba25bcc0c5c9cc4354': 1, 'cfad4af02bdaef8b3dcf735a88733355404ff4dfb164c864811660c78cd9e431': 1, '2c98c34812cfd885f481b7f3e76780b8053fb971c59f6462e06734bc5c716d16': 1, 'e80036dce796ae0eaba42ba35fd4609fbef85cc2caf5aab262d92cd1fe891320': 1, '2314fa1c2eaae4ed80b9d9d0365e953f68f79d70af3208e463dcb448deba863f': 1, 'a74fcd0fe2f9af231b7ea0496d79bb4c7850e8d6e025349e425f0f092a91ee4d': 1, '56e9f2cd2b672f9a1be920ea3ee01a5f1388899e8025ba305588c9a976b645b5': 1, '3a6a9301d09c75e87f657fa8b4fa49671495f258fe206c4cb1c54eb4b9c6ec5c': 1, '088a3a867f35a73244b09820b749372f26c6e6b29b29c0923816a1ff433e5a46': 2}}:raise ValueError('reviewed_composed_AST_shape_or_count_changed')
    if names(result)&markers:raise ValueError('unreviewed_or_duplicate_composed_AST_scaffold')
    return result


def projected_ast(text, is_runner):
    tree = ast.parse(text)
    if is_runner:tree = _composed_runner_off(tree)
    hpo_new = {'HPOFairReserveStop', 'validate_fair_reserve_configuration', '_fair_share',
        '_FairReserveClock', '_fair_technical_result', '_optimize_recipe_fair_reserve'}
    runner_new = {'_hpo_fair_reserve_options', '_run_hpo_fair_reserve_worker'}
    constants = ({'_HPO_FAIR_RESERVE_PROVENANCE'} if is_runner else
        {'HPO_FAIR_RESERVE_MODE', 'FAIR_OVERHEAD_SECONDS', 'FAIR_MINIMUM_SECONDS'})

    class Project(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            if node.name in (runner_new if is_runner else hpo_new):
                return None
            if not is_runner and node.name == 'optimize_recipe':
                assert node.args.args[-1].arg == 'fair_reserve'
                node.args.args.pop()
                node.args.defaults.pop()
                assert ast.unparse(node.body[1].test) == 'fair_reserve is not None'
                node.body.pop(1)
            return self.generic_visit(node)

        def visit_ClassDef(self, node):
            if node.name in hpo_new and not is_runner:
                return None
            return self.generic_visit(node)

        def visit_Assign(self, node):
            if any(isinstance(n, ast.Name) and n.id in constants for n in node.targets):
                return None
            return self.generic_visit(node)

        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call):
                call = node.value
                if isinstance(call.func, ast.Name) and call.func.id == '_hpo_fair_reserve_options':
                    return None
                if isinstance(call.func, ast.Attribute) and call.func.attr == 'add_argument' and any(
                        isinstance(a, ast.Constant) and a.value == '--hpo-fair-reserve' for a in call.args):
                    return None
            return self.generic_visit(node)

        def visit_If(self, node):
            text = ast.unparse(node.test)
            if is_runner and text == "getattr(args, 'hpo_fair_reserve', False)":
                return [self.visit(n) for n in node.orelse]
            if is_runner and text == '_HPO_FAIR_RESERVE_PROVENANCE.get()':
                return None
            return self.generic_visit(node)
    return ast.dump(Project().visit(tree), include_attributes=False)


class FairReserveTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.clock = FakeClock()
        self.study = Study()
        self.saved, self.calls = [], []
        self.persist_hook = None
        self.spec = dict(kind='classification', metric='macro_f1', greater_is_better=True)
        self.recipe = dict(hypothesis='Generic fixed unprofiled control', engine='lightgbm',
            params=dict(iterations=1200, learning_rate=.04, num_leaves=63,
                reg_lambda=5., colsample_bytree=.9, class_weight_power=.5,
                calibrate=True, min_iterations=100, feature_views='categorical_te_pair',
                nested_stopping=True, early_metric='primary'), feature_code='')
        fake = SimpleNamespace(__version__='synthetic', logging=SimpleNamespace(WARNING=0,
            set_verbosity=lambda *a:None), samplers=SimpleNamespace(TPESampler=lambda **k:object()),
            trial=SimpleNamespace(TrialState=SimpleNamespace(COMPLETE='complete', FAIL='fail')),
            create_study=lambda **k:self.study)
        for patcher in [patch.dict(sys.modules, optuna=fake),
                patch.object(hpo.time, 'monotonic', self.clock),
                patch.object(hpo, 'nested_partition', return_value=([0], [1], {'scope':'inside_outer_fitting_rows_only'})),
                patch.object(hpo.np, 'savez', return_value=None),
                patch.object(hpo, 'atomic_json', side_effect=self.persist),
                patch.object(runner.subprocess, 'Popen', side_effect=AssertionError('unmocked_process_forbidden')),
                patch.object(runner, 'request_json', side_effect=AssertionError('API_forbidden'))]:
            patcher.start()
            self.addCleanup(patcher.stop)

    def persist(self, path, report):
        self.saved.append(copy.deepcopy(report))
        if self.persist_hook:
            self.persist_hook(report)

    def worker(self, spec, recipe, output, split, timeout):
        self.calls.append(dict(recipe=copy.deepcopy(recipe), timeout=timeout))
        self.clock.now += 40.
        return dict(status='ok', strict_runtime=True, metrics={'macro_f1':.5},
            wall_seconds=40., fit_iterations=[100,100], hpo_fair_reserve_provenance=origin())

    def optimize(self, worker=None, **kwargs):
        deadline=kwargs.pop('original_deadline',900.)
        output=kwargs.pop('original_output',Path(self.directory.name)/'study')
        options = dict(trials=8, fair_reserve=hpo.HPO_FAIR_RESERVE_MODE)
        options.update(kwargs)
        return hpo.optimize_recipe(self.spec, None, None, [0], self.recipe,
            output, worker or self.worker, deadline, **options)

    def test_numerical_REG300_and_missing_strict_reject_before_discovery_or_API(self):
        for extra in [['--hpo-budget','300','--strict-runtime'], ['--hpo-budget','900']]:
            with self.subTest(extra=extra), patch.object(sys,'argv',['solution.py',
                    '--hpo-fair-reserve','--hpo-trials','8',*extra]), \
                    patch.object(runner,'RunBudget',side_effect=AssertionError('new_run_forbidden')), \
                    patch.object(runner,'load_inputs',side_effect=AssertionError('discovery_forbidden')):
                with self.assertRaises(ValueError):
                    runner._main()
        args = SimpleNamespace(hpo_fair_reserve=True,hpo_budget=900,hpo_trials=8,
            strict_runtime=True,hpo_sampler='tpe')
        for kind in ['regression', None]:
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                runner._hpo_fair_reserve_options(args, {'kind':kind})

    def test_exact_anchor_feasibility_and_soft_equal_share_arithmetic(self):
        self.assertEqual(hpo._fair_share(900.,220.,8,anchor=True),600.)
        with self.assertRaises(hpo.HPOFairReserveStop):
            hpo._fair_share(900.,220.001,8,anchor=True)
        self.assertAlmostEqual(hpo._fair_share(900.,80.,7),(900.-80.-45.)/7)
        self.assertEqual(hpo._fair_share(900.,850.,1),5.)
        with self.assertRaises(hpo.HPOFairReserveStop):
            hpo._fair_share(900.,850.001,1)
        for allocation in [(float('nan'),0.,7),(900.,0.,True),(True,0.,7)]:
            with self.subTest(allocation=allocation), self.assertRaises(hpo.HPOFairReserveStop):
                hpo._fair_share(*allocation)
        # Include the requested decimal and a true false-rejection witness.
        # Both preserve EXACT endpoint=start+900, without epsilon or reset.
        for index,start in enumerate([65452.093,65535.00000000002]):
            self.clock.now=start
            self.study=Study()
            self.calls.clear()
            end=start+900.
            if index==1:
                self.assertGreater(end-start,900.)
            _, report=self.optimize(original_deadline=end,
                original_output=Path(self.directory.name)/('exact-assignment-'+str(index)))
            self.assertEqual(report['fair_reserve']['original_deadline_monotonic'],end)
            self.assertEqual(report['attempted_trials'],8)
            self.assertEqual(self.calls[0]['timeout'],600.)
            self.clock.now=start
            calls_before=len(self.calls)
            with self.assertRaisesRegex(hpo.HPOFairReserveStop,'original_phase_exceeds900'):
                hpo.optimize_recipe(self.spec,None,None,[0],self.recipe,
                    Path(self.directory.name)/('too-long-'+str(index)),self.worker,end+.0001,
                    trials=8,fair_reserve=hpo.HPO_FAIR_RESERVE_MODE)
            self.assertEqual(len(self.calls),calls_before)

    def test_original_clock_invalid_rollback_and_deadline_remain_sticky(self):
        for bad in [float('nan'), float('inf'), -1., 100.]:
            self.clock.now = 1.
            guard = hpo._FairReserveClock(100.)
            self.assertEqual(guard.observe(),1.)
            self.clock.now = bad
            with self.assertRaises(hpo.HPOFairReserveStop) as first:
                guard.observe()
            self.clock.now = 2.
            with self.assertRaises(hpo.HPOFairReserveStop) as second:
                guard.observe()
            self.assertIs(first.exception,second.exception)
            self.assertEqual(guard.deadline,100.)
        self.clock.now=800.
        guard=hpo._FairReserveClock(900.)
        with self.assertRaises(hpo.HPOFairReserveStop) as first:
            guard.allocation(8,anchor=True)
        self.clock.now=0.
        with self.assertRaises(hpo.HPOFairReserveStop) as second:
            guard.allocation(1)
        self.assertIs(first.exception,second.exception)

    def test_late_anchor_setup_stops_without_callback_or_fake_trial(self):
        def slow_split(*args, **kwargs):
            self.clock.now = 250.
            return [0],[1],{'scope':'inside_outer_fitting_rows_only'}
        with patch.object(hpo,'nested_partition',side_effect=slow_split), self.assertRaises(hpo.HPOFairReserveStop):
            self.optimize()
        self.assertEqual(self.calls,[])
        self.assertEqual(self.saved[-1]['trials'],[])
        self.assertEqual(self.saved[-1]['unattempted_trials'],8)

    def test_share_recomputed_after_persist_does_not_launch_stale_proposal(self):
        def slow_save(report):
            alloc = report['fair_reserve']['allocations']
            if alloc and alloc[-1]['number']==1 and alloc[-1]['status']=='proposal_prepared':
                self.clock.now = 850.
        self.persist_hook = slow_save
        with self.assertRaises(hpo.HPOFairReserveStop):
            self.optimize()
        self.assertEqual(len(self.calls),1)
        final = self.saved[-1]
        self.assertEqual(final['attempted_trials'],1)
        self.assertEqual(final['unattempted_trials'],7)
        self.assertFalse(final['fair_reserve']['allocations'][-1]['worker_callback_invoked'])

    def test_eight_actual_callbacks_preserve_anchor_template_space_and_truthful_phases(self):
        _, report = self.optimize()
        self.assertEqual(len(self.calls),8)
        self.assertEqual(self.calls[0]['timeout'],600.)
        self.assertEqual(self.calls[0]['recipe']['params']['iterations'],1200)
        self.assertEqual(report['control_recipe'],self.recipe)
        self.assertEqual(report['search_space'],{'num_leaves':('int',31,127),
            'reg_lambda':('log',2.,20.),'colsample_bytree':('float',.75,1.)})
        self.assertEqual([t['sampling_phase'] for t in report['trials']],
            ['anchor','startup','startup','guided','guided','guided','guided','guided'])
        self.assertEqual((report['attempted_trials'],report['completed_trials'],report['failed_trials']), (8,8,0))
        self.assertEqual(report['fair_reserve']['worker_callback_invocations'],8)
        self.assertIsNone(report['fair_reserve']['actual_model_process_launches'])
        self.assertIsNone(report['fair_reserve']['actual_recursive_learner_fits'])

    def test_ordinary_confirmed_timeout_is_null_consumes_slot_and_continues(self):
        def worker(*args):
            result=self.worker(*args)
            if len(self.calls)==2:
                result.update(status='timeout',metrics={'macro_f1':999.},fit_iterations=None,
                    hpo_fair_reserve_provenance=origin('timeout','timeout'))
            return result
        _, report=self.optimize(worker)
        self.assertEqual(len(self.calls),8)
        self.assertEqual((report['completed_trials'],report['failed_trials']),(7,1))
        self.assertIsNone(report['trials'][1]['value'])
        self.assertFalse(report['trials'][1]['objective_valid'])
        self.assertEqual(report['trials'][3]['sampling_phase'],'startup')

    def test_actual_cleanup_overrun_stops_later_slots_without_reset_or_retry(self):
        def worker(*args):
            result=self.worker(*args)
            if len(self.calls)==2:
                self.clock.now=870.
                result.update(status='timeout',metrics=None,hpo_fair_reserve_provenance=origin('timeout','timeout'))
            return result
        with self.assertRaises(hpo.HPOFairReserveStop):
            self.optimize(worker)
        final=self.saved[-1]
        self.assertEqual((len(self.calls),final['attempted_trials'],final['unattempted_trials']),(2,2,6))
        self.assertEqual(final['trials'][1]['status'],'timeout')
        self.assertIsNone(final['trials'][1]['value'])
        self.assertEqual(final['fair_reserve']['original_deadline_monotonic'],900.)

    def strict_return(self, killed=None, provenance=True, cleanup_exception=None):
        directory=Path(self.directory.name)/('worker-'+str(len(list(Path(self.directory.name).iterdir()))))
        class Process:
            pid=123
            returncode=0
            def poll(self):
                return None if killed is not None else 0
        def popen(*args, **kwargs):
            (directory/'result.json').write_text(json.dumps({'status':'ok'}),encoding='utf-8')
            return Process()
        def cleanup(*args):
            if cleanup_exception is not None:
                raise cleanup_exception
            self.clock.now=2.
        budget=SimpleNamespace(inspect=lambda *a:(killed,1,1),inspect_artifacts=lambda *a:0)
        tree=SimpleNamespace(refresh=lambda:None)
        self.clock.now=0.
        token=runner._HPO_FAIR_RESERVE_PROVENANCE.set(provenance)
        try:
            with patch.object(runner.subprocess,'Popen',side_effect=popen), \
                    patch.object(runner,'ProcessTree',return_value=tree), \
                    patch.object(runner,'ResourceBudget',return_value=budget), \
                    patch.object(runner,'ExperimentRequest',return_value=SimpleNamespace(validate=lambda:None)), \
                    patch.object(runner,'atomic_json',return_value=None), \
                    patch.object(runner,'worker_entrypoint',return_value=Path('mock_worker.py')), \
                    patch.object(runner,'_strict_worker_cleanup',side_effect=cleanup):
                return runner._run_worker_strict({'root':self.directory.name},self.recipe,directory,'split.npz',1.)
        finally:
            runner._HPO_FAIR_RESERVE_PROVENANCE.reset(token)

    def test_resource_kill_late_cleanup_stays_timeout_but_parent_origin_forces_STOP(self):
        for killed in ['memory_limit','disk_space_limit']:
            with self.subTest(killed=killed):
                result=self.strict_return(killed)
                self.assertEqual(result['status'],'timeout')
                self.assertEqual(result['hpo_fair_reserve_provenance']['coordinator_killed'],killed)
                self.assertEqual(result['hpo_fair_reserve_provenance']['prior_result_status'],killed)
                self.assertIsNotNone(hpo._fair_technical_result(result))

    def test_ordinary_late_clean_result_has_complete_nonresource_origin(self):
        result=self.strict_return()
        self.assertEqual(result['status'],'timeout')
        self.assertEqual(result['hpo_fair_reserve_provenance'],origin('ok'))
        self.assertIsNone(hpo._fair_technical_result(result))

    def test_original_cleanup_exception_propagates_and_trusted_scope_restores(self):
        error=runner.ProcessObservationError({'status':'observation_unconfirmed','unresolved':[]})
        with self.assertRaises(runner.ProcessObservationError) as caught:
            self.strict_return(cleanup_exception=error)
        self.assertIs(caught.exception,error)
        def failed(*args,**kwargs):
            self.assertTrue(runner._HPO_FAIR_RESERVE_PROVENANCE.get())
            raise error
        with patch.object(runner,'run_worker',side_effect=failed), self.assertRaises(runner.ProcessObservationError):
            runner._run_hpo_fair_reserve_worker()
        self.assertFalse(runner._HPO_FAIR_RESERVE_PROVENANCE.get())
        def raised_callback(*args):
            self.calls.append({'callback_entered':True})
            raise error
        with self.assertRaises(runner.ProcessObservationError) as caught:
            self.optimize(raised_callback)
        self.assertIs(caught.exception,error)
        self.assertEqual(len(self.calls),1)
        self.assertFalse(self.saved[-1]['trials'][0]['objective_valid'])
        self.assertIsNone(self.saved[-1]['trials'][0]['value'])
        # A secondary diagnostic IO failure cannot mask the primary uncertainty.
        # Use a separate output tree; no retry/continuation of the stopped study.
        self.clock.now=0.
        before=len(self.calls)
        save_failure=PermissionError('synthetic private path must never be exported')
        def diagnostics_unavailable(report):
            if report['status']=='fair_reserve_stopped':
                raise save_failure
        self.persist_hook=diagnostics_unavailable
        with patch('builtins.print') as diagnostics:
            try:
                hpo.optimize_recipe(self.spec,None,None,[0],self.recipe,
                    Path(self.directory.name)/'secondary-save',raised_callback,900.,
                    trials=8,fair_reserve=hpo.HPO_FAIR_RESERVE_MODE)
            except runner.ProcessObservationError as retained:
                self.assertIs(retained,error)
                traceback=retained.__traceback__
                names=[]
                while traceback is not None:
                    names.append(traceback.tb_frame.f_code.co_name)
                    traceback=traceback.tb_next
                self.assertIn('raised_callback',names)
            else:
                self.fail('primary observation uncertainty was not re-raised')
        payload=json.loads(diagnostics.call_args.args[0])
        self.assertEqual(payload,{'hpo_fair_reserve_failure_types':{
            'primary_exception_type':'ProcessObservationError',
            'diagnostic_save_exception_type':'PermissionError'}})
        self.assertEqual(len(self.calls),before+1)
        self.assertEqual(error.hpo_fair_reserve_failure_types,{
            'primary_exception_type':'ProcessObservationError',
            'diagnostic_save_exception_type':'PermissionError'})
        self.assertNotIn('synthetic private path',str(error.hpo_fair_reserve_failure_types))

    def test_missing_or_incomplete_parent_receipt_is_technical_STOP(self):
        for receipt in [None,{},dict(schema='hpo-fair-reserve-worker-origin-v1'),
                        dict(origin(),cleanup_confirmed=False)]:
            with self.subTest(receipt=receipt):
                result=dict(status='timeout',strict_runtime=True,hpo_fair_reserve_provenance=receipt)
                self.assertIsNotNone(hpo._fair_technical_result(result))
        def worker(*args):
            result=self.worker(*args)
            result.pop('hpo_fair_reserve_provenance')
            return result
        with self.assertRaises(hpo.HPOFairReserveStop):
            self.optimize(worker)
        self.assertEqual(len(self.calls),1)
        self.assertIsNone(self.saved[-1]['trials'][0]['value'])

    def test_resource_or_unknown_technical_origin_STOPs_without_extra_draw(self):
        for change in [dict(hpo_fair_reserve_provenance=origin('timeout','memory_limit')),
                       dict(hpo_fair_reserve_provenance=origin('error',primary='RuntimeError')),
                       dict(exception_type='ProcessObservationError'),dict(exception_type='UnknownParentError')]:
            result=dict(status='timeout',strict_runtime=True,hpo_fair_reserve_provenance=origin())
            result.update(change)
            with self.subTest(change=change):
                self.assertIsNotNone(hpo._fair_technical_result(result))
        def worker(*args):
            result=self.worker(*args)
            result.update(status='timeout',hpo_fair_reserve_provenance=origin('memory_limit','memory_limit'))
            return result
        with self.assertRaises(hpo.HPOFairReserveStop):
            self.optimize(worker)
        self.assertEqual((len(self.calls),len(self.study.trials)),(1,1))

    def test_duplicate_proposal_is_not_callback_or_valid_or_padding(self):
        self.study.duplicate=True
        _, report=self.optimize()
        self.assertEqual(len(self.study.trials),8)
        self.assertEqual((len(self.calls),report['duplicate_trials'],report['completed_trials']),(7,1,7))
        self.assertEqual(report['fair_reserve']['worker_callback_invocations'],7)
        self.assertEqual(report['fair_reserve']['allocations'][3]['status'],'duplicate_no_worker')
        self.assertFalse(report['fair_reserve']['allocations'][3]['worker_callback_invoked'])
        self.assertIsNone(report['trials'][3]['value'])

    def test_final_save_crossing_original_deadline_cannot_return_ok(self):
        def final_cost(report):
            if report['status']=='ok':
                self.clock.now=901.
        self.persist_hook=final_cost
        with self.assertRaises(hpo.HPOFairReserveStop):
            self.optimize()
        self.assertEqual(self.saved[-1]['status'],'fair_reserve_stopped')
        self.assertEqual(len(self.calls),8)

    def test_trusted_flag_cannot_be_enabled_by_recipe_context_and_scope_is_local(self):
        # An arbitrary recipe key cannot select the argparse attribute.
        runner._hpo_fair_reserve_options(SimpleNamespace(recipe={'hpo_fair_reserve':True}))
        observed=[]
        def callback(*args,**kwargs):
            observed.append(runner._HPO_FAIR_RESERVE_PROVENANCE.get())
            return 'same result'
        with patch.object(runner,'run_worker',side_effect=callback):
            self.assertEqual(runner._run_hpo_fair_reserve_worker(),'same result')
        self.assertEqual(observed,[True])
        self.assertFalse(runner._HPO_FAIR_RESERVE_PROVENANCE.get())

    def test_OFF_strict_worker_late_classification_does_not_add_provenance(self):
        result=self.strict_return('memory_limit',provenance=False)
        self.assertEqual(result['status'],'timeout')
        self.assertNotIn('hpo_fair_reserve_provenance',result)

    def test_default_OFF_whole_module_ASTs_match_independent_original_bases(self):
        expected={'hpo.py':'b03466060e2eed6886b89b8c3706afbb51eac9364f855b955c3b90f47bddbe96','runner.py':'877b5cd74b661d921cb1a12bca0b0b554caf943ee1c2e9b80adcb5e467097f7c'}
        for name,witness in expected.items():
            text=(ROOT/'src/automl/search'/name).read_text('utf-8')
            actual=hashlib.sha256(projected_ast(text,name=='runner.py').encode()).hexdigest()
            self.assertEqual(actual,witness)


if __name__=='__main__':
    unittest.main()
