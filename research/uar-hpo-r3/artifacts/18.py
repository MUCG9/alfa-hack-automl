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


def projected_ast(text, is_runner):
    tree = ast.parse(text)
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
        options = dict(trials=8, fair_reserve=hpo.HPO_FAIR_RESERVE_MODE)
        options.update(kwargs)
        return hpo.optimize_recipe(self.spec, None, None, [0], self.recipe,
            Path(self.directory.name)/'study', worker or self.worker, 900., **options)

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
