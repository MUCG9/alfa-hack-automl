"""Prepared no-fit runtime contracts: all Popen/process/resource activity is mocked."""
from contextlib import ExitStack, contextmanager, nullcontext
from pathlib import Path
from types import SimpleNamespace
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from automl.search import runner
from automl.infrastructure.processes import ProcessCleanupError,ProcessObservationError


@contextmanager
def worker_case(*,strict=True,terminal_after=1,exit_code=0,construct_delay=0.,
                refresh_delay=0.,cleanup_delay=0.,artifact_delay=0.,setup_delay=0.,
                inspect_error=None,refresh_error=None,cleanup_error=None,constructor_error=None,
                terminal_during_inspection=False,recipe=None):
    """Small file artifacts plus inert handles; never starts a process or model."""
    with tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
        root=Path(directory); output=root/'worker'; ticks=[0.]; alive=[True]; polls=[0]
        process=Mock(pid=101,returncode=exit_code)
        def poll():
            polls[0]+=1
            if polls[0]>=terminal_after:alive[0]=False
            return None if alive[0] else exit_code
        process.poll.side_effect=poll
        process.terminate.side_effect=lambda:alive.__setitem__(0,False)
        process.kill.side_effect=lambda:alive.__setitem__(0,False)
        process.wait.side_effect=lambda **kwargs:exit_code
        tree=Mock();tree.members={(101,1.):Mock()}
        def refresh():
            ticks[0]+=refresh_delay
            if refresh_error is not None:raise refresh_error
        def terminate():
            ticks[0]+=cleanup_delay;alive[0]=False
            if cleanup_error is not None:raise cleanup_error
        tree.refresh.side_effect=refresh;tree.terminate.side_effect=terminate
        def make_tree(*args,**kwargs):
            ticks[0]+=construct_delay
            if constructor_error is not None:raise constructor_error
            return tree
        budget=Mock()
        def inspect(*args):
            if terminal_during_inspection:alive[0]=False
            if inspect_error is not None:raise inspect_error
            return None,1,2
        budget.inspect.side_effect=inspect
        def artifacts(*args):ticks[0]+=artifact_delay;return 0
        budget.inspect_artifacts.side_effect=artifacts
        def popen(command,**kwargs):
            target=Path(command[-1]).parent/'result.json'
            target.write_text(json.dumps({'status':'ok','metrics':{'rmse':1.}}),'utf-8')
            return process
        write=runner.atomic_json
        def atomic(path,value):write(path,value);ticks[0]+=setup_delay
        popen_mock=stack.enter_context(patch.object(runner.subprocess,'Popen',side_effect=popen))
        tree_mock=stack.enter_context(patch.object(runner,'ProcessTree',side_effect=make_tree))
        stack.enter_context(patch.object(runner,'ResourceBudget',return_value=budget))
        stack.enter_context(patch.object(runner,'atomic_json',side_effect=atomic))
        stack.enter_context(patch.object(runner,'worker_entrypoint',return_value=root/'inert_worker.py'))
        stack.enter_context(patch.object(runner.time,'monotonic',side_effect=lambda:ticks[0]))
        stack.enter_context(patch.object(runner.time,'sleep',side_effect=lambda n:ticks.__setitem__(0,ticks[0]+n)))
        token=runner._STRICT_RUNTIME.set(strict);stack.callback(runner._STRICT_RUNTIME.reset,token)
        yield SimpleNamespace(root=root,output=output,ticks=ticks,process=process,tree=tree,
            budget=budget,popen=popen_mock,tree_factory=tree_mock,
            spec={'root':str(root),'metric':'rmse','greater_is_better':False},
            recipe=recipe or {'engine':'lightgbm','params':{},'feature_code':'','hypothesis':'inert'},
            call=lambda timeout=2,**kwargs:runner.run_worker({'root':str(root)},
                recipe or {'engine':'lightgbm','params':{},'feature_code':'','hypothesis':'inert'},
                output,root/'split.npz',timeout,**kwargs))


class RuntimeOptInTests(unittest.TestCase):
    def test_trusted_cli_scope_applies_and_restores_on_success_and_failure(self):
        for enabled in (False,True):
            for failure in (False,True):
                with self.subTest(enabled=enabled,failure=failure):
                    expected=ValueError('fixture')
                    observed=[]
                    def solver(*args):
                        observed.append(runner._STRICT_RUNTIME.get())
                        if failure:raise expected
                        return 'inert'
                    argv=['solution.py','task.md','--offline']+(['--strict-runtime'] if enabled else [])
                    with patch.object(sys,'argv',argv),patch.object(runner,'RunBudget',return_value=nullcontext()),\
                         patch.object(runner,'load_inputs',return_value=object()),\
                         patch.object(runner,'discover',return_value=object()),\
                         patch.object(runner,'solve_single',side_effect=solver):
                        if failure:
                            with self.assertRaises(ValueError) as caught:runner._main()
                            self.assertIs(caught.exception,expected)
                        else:self.assertEqual(runner._main(),'inert')
                    self.assertEqual(observed,[enabled]);self.assertFalse(runner._STRICT_RUNTIME.get())

    def test_task_recipe_or_environment_cannot_enable_strict_runtime(self):
        recipe={'engine':'lightgbm','params':{'strict_runtime':True},'strict_runtime':True}
        with patch.dict(os.environ,{'AUTOML_STRICT_RUNTIME':'1'}),\
             worker_case(strict=False,recipe=recipe) as f,\
             patch.object(runner,'_run_worker_strict',side_effect=AssertionError('untrusted opt-in')):
            result=f.call()
            self.assertEqual(result['status'],'ok')
            f.tree_factory.assert_called_once_with(f.process)
            self.assertNotIn('strict_runtime',result)

    def test_legacy_off_retains_resource_denial_compatibility(self):
        with worker_case(strict=False,terminal_after=2,inspect_error=runner.psutil.AccessDenied(101)) as f:
            result=f.call();self.assertEqual(result['status'],'ok')
            self.assertEqual(result['metrics'],{'rmse':1.})
            f.tree_factory.assert_called_once_with(f.process)
            f.tree.terminate.assert_called_once();f.budget.inspect.assert_called_once()

    def test_strict_success_uses_same_job_and_sanitized_environment(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'inert-sensitive','SOME_TOKEN':'inert-sensitive'}),\
             worker_case() as f:
            result=f.call(full_fit=True,fit_iterations=[31,47])
            self.assertEqual(result['status'],'ok');self.assertTrue(result['strict_runtime'])
            f.tree_factory.assert_called_once_with(f.process,strict_observation=True)
            f.tree.terminate.assert_called_once()
            job=json.loads((f.output/'job.json').read_text('utf-8'))
            self.assertTrue(job['full_fit']);self.assertEqual(job['fit_iterations'],[31,47])
            self.assertEqual(job['threads'],runner.THREADS)
            self.assertNotIn('strict_runtime',job)
            env=f.popen.call_args.kwargs['env']
            self.assertNotIn('OPENAI_API_KEY',env);self.assertNotIn('SOME_TOKEN',env)

    def test_raw_resource_denial_remains_fatal_after_owned_cleanup(self):
        with worker_case(terminal_after=100,inspect_error=runner.psutil.AccessDenied(101)) as f:
            with self.assertRaises(ProcessObservationError) as caught:f.call()
            f.tree.terminate.assert_called_once()
            entry=caught.exception.receipt['unresolved'][0]
            self.assertEqual(entry,dict(pid=101,create_time=1.,action='inspect_resources',error='AccessDenied'))
            self.assertNotIn('argv',str(caught.exception))

    def test_tree_observation_error_is_not_an_ordinary_model_failure(self):
        failure=ProcessObservationError({'status':'observation_unconfirmed','unresolved':[],'actions':[]})
        with worker_case(refresh_error=failure) as f:
            with self.assertRaises(ProcessObservationError) as caught:f.call()
            self.assertIs(caught.exception,failure);f.tree.terminate.assert_called_once()
            f.budget.inspect.assert_not_called()

    def test_cleanup_uncertainty_is_fatal_and_retains_prior_failure_type(self):
        cleanup=ProcessCleanupError({'status':'cleanup_unconfirmed','unresolved':[{'pid':101}],'actions':[]})
        for denial in (None,runner.psutil.AccessDenied(101)):
            with self.subTest(denial=denial is not None),worker_case(
                    terminal_after=1 if denial is None else 100,inspect_error=denial,cleanup_error=cleanup) as f:
                with self.assertRaises(ProcessCleanupError) as caught:f.call()
                if denial is not None:
                    self.assertEqual(caught.exception.receipt['prior_failure_type'],'ProcessObservationError')
                    self.assertIsInstance(caught.exception.__cause__,ProcessObservationError)
                else:self.assertIs(caught.exception,cleanup)
        with worker_case(construct_delay=2.,cleanup_error=cleanup) as f:
            with self.assertRaises(ProcessCleanupError) as caught:f.call()
            self.assertEqual(caught.exception.receipt['prior_failure_type'],'TimeoutExpired')
            self.assertIsInstance(caught.exception.__cause__,runner.subprocess.TimeoutExpired)
        with worker_case(cleanup_error=PermissionError('inert-sensitive-text')) as f:
            with self.assertRaises(ProcessCleanupError) as caught:f.call()
            self.assertEqual(caught.exception.receipt['unresolved'][0]['error'],'PermissionError')
            self.assertNotIn('inert-sensitive-text',str(caught.exception))
        with worker_case() as f:
            f.budget.inspect_artifacts.side_effect=PermissionError('inert')
            with self.assertRaises(ProcessObservationError) as caught:f.call()
            self.assertEqual(caught.exception.receipt['unresolved'][0]['action'],'inspect_artifacts')
            f.tree.terminate.assert_called_once()

    def test_constructor_failure_cleans_only_popen_root_and_stays_unqualified(self):
        with worker_case(terminal_after=100,constructor_error=RuntimeError('inert')) as f:
            with self.assertRaises(ProcessObservationError) as caught:f.call()
            f.process.terminate.assert_called_once();f.process.wait.assert_called_once()
            f.tree.terminate.assert_not_called()
            self.assertEqual(caught.exception.receipt['unresolved'][0]['action'],'construct_owned_tree')
            self.assertIsNone(caught.exception.receipt['unresolved'][0]['create_time'])

    def test_initial_construction_and_prelaunch_setup_use_same_deadline(self):
        with worker_case(construct_delay=2.) as f:
            result=f.call();self.assertEqual(result['status'],'timeout');self.assertNotIn('metrics',result)
            f.tree.terminate.assert_called_once()
        with worker_case(setup_delay=2.) as f:
            result=f.call();self.assertEqual(result['status'],'timeout')
            f.popen.assert_not_called();f.tree_factory.assert_not_called()

    def test_terminal_at_deadline_is_timeout_without_minimum_one_second_extension(self):
        for elapsed,timeout,expected in [(1.9,2,'ok'),(2.,2,'timeout'),(2.1,2,'timeout'),(.25,.2,'timeout')]:
            with self.subTest(elapsed=elapsed,timeout=timeout),worker_case(refresh_delay=elapsed) as f:
                result=f.call(timeout);self.assertEqual(result['status'],expected)
                if expected=='timeout':self.assertNotIn('metrics',result)
        for invalid in (True,0,-1,float('inf'),float('nan')):
            with self.subTest(invalid=invalid),worker_case() as f:
                with self.assertRaises(ValueError):f.call(invalid)
                f.popen.assert_not_called()

    def test_cleanup_and_result_inspection_cannot_extend_success(self):
        for cleanup,artifact in [(2.,0.),(0.,2.)]:
            with self.subTest(cleanup=cleanup,artifact=artifact),worker_case(
                    cleanup_delay=cleanup,artifact_delay=artifact) as f:
                result=f.call();self.assertEqual(result['status'],'timeout');self.assertNotIn('metrics',result)
                f.tree.terminate.assert_called_once()
        with worker_case() as f:
            after_cleanup=iter([1.9,2.1])
            def advancing_clock():
                return next(after_cleanup) if f.tree.terminate.called else 0.
            with patch.object(runner.time,'monotonic',side_effect=advancing_clock):
                result=f.call()
            self.assertEqual(result['status'],'ok')
            self.assertEqual(result['wall_seconds'],1.9)
            self.assertLessEqual(result['wall_seconds'],2.)

    def test_uncertain_resource_snapshot_is_fatal_unless_root_already_terminal(self):
        with worker_case(terminal_after=100,inspect_error=runner.psutil.NoSuchProcess(202)) as f:
            with self.assertRaises(ProcessObservationError) as caught:f.call()
            self.assertEqual(caught.exception.receipt['unresolved'][0]['error'],'NoSuchProcessWithLiveRoot')
            f.tree.terminate.assert_called_once()
        with worker_case(terminal_after=100,inspect_error=runner.psutil.NoSuchProcess(202),
                terminal_during_inspection=True) as f:
            result=f.call();self.assertEqual(result['status'],'ok');f.tree.terminate.assert_called_once()

    def test_nonzero_child_remains_an_ordinary_failed_candidate(self):
        with worker_case(exit_code=7) as f:
            result=f.call();self.assertEqual(result['status'],'error');self.assertEqual(result['exit_code'],7)
            self.assertEqual(runner.ordered([result],f.spec),[])
            f.tree.terminate.assert_called_once()

    def test_blend_generic_catch_propagates_strict_cleanup_but_preserves_off_failure(self):
        import numpy as np
        import pandas as pd
        failure=ProcessCleanupError({'status':'cleanup_unconfirmed','unresolved':[],'actions':[]})
        for strict in (False,True):
            with self.subTest(strict=strict),tempfile.TemporaryDirectory() as directory,ExitStack() as stack:
                root=Path(directory)
                spec={'root':str(root),'task_path':str(root/'task.md'),'paths':{},'target':'y','id':'identifier',
                    'features':['x'],'kind':'regression','metric':'rmse','greater_is_better':False,
                    'prediction_type':'value','output_columns':['y'],'classes':None,'text_features':[]}
                train=pd.DataFrame({'x':range(8),'y':range(8)});test=pd.DataFrame({'x':[8,9],'identifier':['u','v']})
                sample=pd.DataFrame({'identifier':['u','v'],'y':[0.,0.]})
                recipes=[{'engine':'lightgbm','params':{'num_leaves':n},'feature_code':'','hypothesis':'inert'} for n in (31,47)]
                args=SimpleNamespace(task=root/'task.md',time_budget=2000,run_name='inert',max_experiments=2,
                    max_planner_calls=0,offline=True,hpo_trials=0,feature_selection_top_k=0,
                    protect_original_features=False,four_stage=False,validation_strategy='legacy')
                def worker(s,r,output,*unused,**kwargs):
                    return dict(status='ok',recipe=r,output_dir=str(output),submission=str(root/'inert.csv'),
                        metrics={'rmse':1. if r['params']['num_leaves']==31 else 2.},fit_iterations=100)
                patches=[patch.object(runner.time,'monotonic',return_value=0.),
                    patch.object(runner,'choose_validation',side_effect=lambda s,*a:s),
                    patch.object(runner,'file_fingerprints',return_value={}),
                    patch.object(runner,'make_split',return_value=(np.arange(4),np.arange(4,8),{})),
                    patch.object(runner,'evaluate',return_value={'rmse':10.}),
                    patch.object(runner,'portfolio',return_value=recipes),
                    patch.object(runner,'run_worker',side_effect=worker),patch.object(runner,'checkpoint'),
                    patch.object(runner,'journal'),patch.object(runner,'read_cache',return_value=object()),
                    patch.object(runner,'combine',return_value=({'rmse':0.},None)),
                    patch.object(runner,'materialize',side_effect=failure),
                    patch.object(runner,'request_json',side_effect=AssertionError('no API'))]
                for item in patches:stack.enter_context(item)
                token=runner._STRICT_RUNTIME.set(strict);stack.callback(runner._STRICT_RUNTIME.reset,token)
                data=(spec,{},train,test,sample,'',np.arange(8))
                if strict:
                    with self.assertRaises(ProcessCleanupError) as caught:runner.solve_single(args,data)
                    self.assertIs(caught.exception,failure)
                else:
                    report=runner.solve_single(args,data)
                    self.assertEqual(report['blend_trials'][-1]['exception_type'],'ProcessCleanupError')


if __name__=='__main__':unittest.main()
