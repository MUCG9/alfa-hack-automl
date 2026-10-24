"""Prepared synthetic contracts only: zero model fits/API calls. NOT executed.
Run only under root's future bounded technical lease after source review.
"""
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout
import io
import csv
import hashlib
import json
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'candidate'))
import numpy as np
import pandas as pd
import automl_fixed_release as release
import automl_release_recipes as recipes
import automl_release_runtime as runtime
import automl_infrastructure_tables as tables


class FixedReleaseContracts(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name)
        self.network=patch('socket.create_connection',side_effect=AssertionError('No network in contracts'))
        self.process=patch('subprocess.Popen',side_effect=AssertionError('No actual learners in contracts'))
        self.network.start();self.process.start();self.addCleanup(self.network.stop);self.addCleanup(self.process.stop)
    def write(self,name,text):
        path=self.root/name;path.write_text(text,encoding='utf-8');return path
    def clock(self):
        class Caller:
            def check(self,force=False):pass
            def remaining(self):return 9900.
            def receipt(self):return {'test_clock':True}
        return Caller()
    def fixture(self,role='target'):
        self.write('fit-renamed.csv','ticket,sensor,answer\n001,2,1.5\nNA,3,2.5\n')
        self.write('future-renamed.csv','ticket,sensor\n001,4\nNA,5\n')
        self.write('format-renamed.csv','ticket,answer\nNA,0\n001,0\n')
        self.write('roles-renamed.csv',f'feature,role\nticket,id\nsensor,feature\nanswer,{role}\n')
        task=self.write('instructions-renamed.md','Regression task. Primary metric: RMSE')
        paths={'train':self.root/'fit-renamed.csv','test':self.root/'future-renamed.csv',
            'sample_submission':self.root/'format-renamed.csv','data_dictionary':self.root/'roles-renamed.csv'}
        return task,paths

    def test_exact_embedded_raw_recipes_and_outer_component_geometry(self):
        expected=json.loads((ROOT/'tests/fixtures/recipes.json').read_text('utf-8'))
        self.assertEqual(recipes.REGRESSION_RECIPE,expected['regression'])
        self.assertEqual(recipes.CLASSIFICATION_RECIPE,expected['classification'])
        self.assertEqual(recipes.REGRESSION_RECIPE['weights'],[.75,.25])
        self.assertEqual([c['engine'] for c in recipes.REGRESSION_RECIPE['components']],['lightgbm','lightgbm'])
        self.assertEqual(len(recipes.CLASSIFICATION_RECIPE['components']),3)
        self.assertEqual([c['params'].get('feature_views') for c in recipes.CLASSIFICATION_RECIPE['components'][:2]],['categorical_te_pair']*2)
        self.assertTrue(all(c['engine']!='ensemble' for r in expected.values() for c in r['components']))

    def test_routing_uses_only_supported_kind_metric_not_schema_names(self):
        for arbitrary_name in ['unseen_renamed_problem','001','NA']:
            self.assertEqual(recipes.fixed_recipe('regression','rmse'),recipes.REGRESSION_RECIPE)
            self.assertEqual(recipes.fixed_recipe('classification','macro_f1'),recipes.CLASSIFICATION_RECIPE)
            self.assertNotIn(arbitrary_name,{'regression','classification'})

    def test_unknown_incompatible_metric_and_text_do_not_get_wrong_recipe(self):
        for kind,metric in [('regression','mae'),('classification','accuracy'),('regression',None),('unknown','rmse')]:
            with self.subTest(kind=kind,metric=metric),self.assertRaises(ValueError):recipes.fixed_recipe(kind,metric)
        with self.assertRaises(ValueError):recipes.fixed_recipe('regression','rmse',text_features=['free_text'])

    def test_fixed_recipe_returns_independent_copies(self):
        first=recipes.fixed_recipe('regression','rmse');first['components'][0]['params']['iterations']=1
        self.assertEqual(recipes.fixed_recipe('regression','rmse')['components'][0]['params']['iterations'],1600)

    def test_actual_cut_iterations_not_historical_tree_feed_only_full_refit(self):
        task,paths=self.fixture();loaded={'paths':paths,'declared_target':'answer','declared_identifier':'ticket',
            'train':pd.DataFrame({'sensor':range(9),'answer':range(9)}),
            'test':pd.DataFrame({'ticket':['001','NA'],'sensor':[1,2]}),'sample':pd.DataFrame({'ticket':['NA','001'],'answer':[0,0]})}
        spec={'root':str(self.root),'paths':{k:str(v) for k,v in paths.items()},'target':'answer','id':'ticket',
            'features':['sensor'],'kind':'regression','metric':'rmse','greater_is_better':False,
            'n_train':9,'n_test':2,'text_features':[],'prediction_type':'value','output_columns':['answer']}
        calls=[]
        def worker(spec,recipe,directory,split,timeout,**kwargs):
            calls.append(kwargs)
            return dict(status='ok',cleanup_confirmed=True,output_dir=str(directory),full_fit=kwargs.get('full_fit',False),
                fit_iterations=[50,70] if len(calls)==1 else [70,90])
        captured_stdout=io.StringIO()
        with redirect_stdout(captured_stdout),patch.object(release,'ReleaseClock',return_value=self.clock()),patch.object(release,'load_fixed_inputs',return_value=loaded),\
             patch.object(release,'discover',return_value=(spec,{},loaded['train'],loaded['test'],loaded['sample'],'',np.arange(9))),\
             patch.object(release,'choose_validation',side_effect=lambda s,*a:s),patch.object(release,'source_files',return_value=[]),\
             patch.object(release,'fingerprints',side_effect=lambda paths,check:{k:'bound' for k in paths}),\
             patch.object(release,'make_split',return_value=(np.arange(6),np.arange(6,9),{'test':True})),\
             patch.object(release,'run_release_worker',side_effect=worker),patch.object(release,'publish_fresh_result'):
            self.assertEqual(release.execute(task),0)
            for replacement in [dict(spec,target='wrong_target'),dict(spec,id='wrong_id')]:
                with patch.object(release,'discover',return_value=(replacement,{},loaded['train'],loaded['test'],loaded['sample'],'',np.arange(9))),\
                     self.assertRaises(ValueError):release.execute(task)
            with patch.object(release,'validate_output_identity',side_effect=ValueError('protected output alias')),\
                 self.assertRaises(ValueError):release.execute(task)
        self.assertEqual(json.loads(captured_stdout.getvalue()),{
            'status':'completed_pending_independent_qualification',
            'policy':'fixed_typed_recipe_two_cut_median_full_refit','quality_metric':None,
            'actual_primary_and_confirmation':2,'actual_full_refit':1,'Qwen_calls':0,'API_calls':0})
        self.assertEqual(len(calls),3)
        self.assertNotIn('fit_iterations',calls[0]);self.assertNotIn('fit_iterations',calls[1])
        self.assertEqual(calls[2]['fit_iterations'],[60,80]);self.assertTrue(calls[2]['full_fit'])
        self.assertNotEqual(calls[2]['fit_iterations'],recipes.HISTORICAL_DEPLOYMENT_ITERATIONS['regression'])

    def test_recursive_actual_median_and_malformed_trees(self):
        self.assertEqual(release.median_iterations([[100,111],[100,138],339],[[100,121],[100,148],341]),[[100,116],[100,143],340])
        for first,second in [([1],[1,2]),(True,2),(0,10),(float('nan'),2),('100',100)]:
            with self.subTest(first=first),self.assertRaises(ValueError):release.median_iterations(first,second)

    def test_lexical_ID_preserves_numeric_regression_target_and_predictor_parsing(self):
        p=self.write('arbitrary.csv','key,value,label\n001,,1.25\nNA,4,2.5\n')
        frame=tables.read_input_table(p,lexical_columns=['key']);baseline=pd.read_csv(p)
        self.assertEqual(frame['key'].tolist(),['001','NA'])
        pd.testing.assert_series_equal(frame['value'],baseline['value'])
        pd.testing.assert_series_equal(frame['label'],baseline['label'])
        self.assertTrue(pd.api.types.is_numeric_dtype(frame['label']))

    def test_worker_lexical_class_labels_and_sample_IDs(self):
        p=self.write('class-fit.csv','key,value,label\n001,2,NA\nNA,3,001\n')
        sample=self.write('class-format.csv','key,label\nNA,0\n001,0\n')
        spec={'paths':{'train':str(p),'sample_submission':str(sample)},'kind':'classification','id':'key','target':'label'}
        frame=tables.read_worker_table(spec,'train')
        self.assertEqual(frame['label'].tolist(),['NA','001'])
        self.assertEqual(frame['key'].tolist(),['001','NA'])
        self.assertEqual(tables.read_task_sample(spec)['key'].tolist(),['NA','001'])

    def test_missing_declared_target_role_stops_before_discovery_or_fit(self):
        task,paths=self.fixture(role='not_target')
        with patch.object(release,'resolve_inputs',return_value=paths),self.assertRaises(ValueError):
            release.load_fixed_inputs(task,'regression',self.clock())
        task,paths=self.fixture()
        for dictionary in ['feature,role\nticket,id\nsensor,feature\nghost,target\n',
                           'feature,role\nmissing_key,id\nsensor,feature\nanswer,target\n',
                           'feature,role\nticket,id\nsensor,feature\n,target\n']:
            paths['data_dictionary'].write_text(dictionary,encoding='utf-8')
            with patch.object(release,'resolve_inputs',return_value=paths),\
                 patch.object(release,'validate_role_tables',side_effect=AssertionError('Legacy guessing must not run')),\
                 self.assertRaises(ValueError):
                release.load_fixed_inputs(task,'regression',self.clock())

    def test_renamed_paths_and_lexical_sample_order_use_declared_roles(self):
        task,paths=self.fixture()
        with patch.object(release,'resolve_inputs',return_value=paths):loaded=release.load_fixed_inputs(task,'regression',self.clock())
        self.assertEqual(loaded['test']['ticket'].tolist(),['001','NA'])
        self.assertEqual(loaded['sample']['ticket'].tolist(),['NA','001'])
        self.assertEqual(loaded['train']['answer'].tolist(),[1.5,2.5])

    def test_strict_original_metric_contrast_unknown_and_conflicts(self):
        self.assertEqual(release.resolved_policy('Поэтому основной\nметрикой выбран Macro F1, а не Accuracy.')[0],'classification')
        self.assertEqual(release.resolved_policy('Primary metric: RMSE')[0],'regression')
        for text in ['No objective declared','Primary metric: novel_score','Primary metric: Macro F1 and Accuracy']:
            with self.subTest(text=text),self.assertRaises(ValueError):release.resolved_policy(text)

    def test_publication_preserves_lexical_IDs_canonical_labels_and_sample_order(self):
        run=self.root/'run';folder=run/'final-fit';folder.mkdir(parents=True)
        np.savez(folder/'test_probabilities.npz',classes=np.asarray(['NA','left']),probabilities=[[.8,.2],[.1,.9]])
        spec={'kind':'classification','id':'key','classes':['NA','left'],'prediction_type':'value',
            'target':'out','output_columns':['out'],'sample_test_positions':[1,0]}
        loaded={'test':pd.DataFrame({'key':['001','NA']}),'sample':pd.DataFrame({'key':['NA','001'],'out':['','']}),
            'protected_files':{'task':self.write('task.md','classification')}}
        output=self.root/'submission.csv'
        release.publish_fresh_result(spec,loaded,{'status':'ok','full_fit':True,'output_dir':str(folder)},output,run,self.clock())
        with output.open(newline='') as stream:rows=list(csv.DictReader(stream))
        self.assertEqual(rows,[{'key':'NA','out':'left'},{'key':'001','out':'NA'}])

    def test_bad_probability_order_and_nonfinite_values_cannot_publish(self):
        run=self.root/'run';folder=run/'final-fit';folder.mkdir(parents=True)
        spec={'kind':'classification','id':None,'classes':['a','b'],'prediction_type':'value','output_columns':['out']}
        loaded={'test':pd.DataFrame({'x':[1]}),'sample':pd.DataFrame({'out':['']}),
            'protected_files':{'task':self.write('task.md','classification')}}
        for classes,probs in [(['b','a'],[[.3,.7]]),(['a','b'],[[float('nan'),.7]])]:
            np.savez(folder/'test_probabilities.npz',classes=np.asarray(classes),probabilities=probs)
            with self.assertRaises(ValueError):release.publish_fresh_result(spec,loaded,{'status':'ok','full_fit':True,'output_dir':str(folder)},self.root/'submission.csv',run,self.clock())
            self.assertFalse((self.root/'submission.csv').exists())

    def test_strict_adapter_preserves_primary_failure_and_restores_caller_scope(self):
        error=runtime.ProcessObservationError({'status':'unconfirmed','unresolved':[],'actions':[]})
        with patch.object(runtime,'_run_worker_strict',side_effect=error):
            with self.assertRaises(runtime.ProcessObservationError) as caught:
                runtime.run_release_worker({}, {},self.root,'unused',100,clock=self.clock())
        self.assertIs(caught.exception,error);self.assertIsNone(runtime._CALLER_CLOCK.get())

    def test_clock_actual_sample_cadence_and_sticky_denial(self):
        now=[0.];calls=[]
        class Resources:
            memory_limit=runtime.WHOLE_MEMORY_LIMIT_BYTES
            def inspect(self,*args):calls.append(now[0]);return None,1,2
        with patch.object(runtime.time,'monotonic',side_effect=lambda:now[0]),\
             patch.object(runtime.time,'time',side_effect=lambda:1000+now[0]),\
             patch.object(runtime,'ResourceBudget',return_value=Resources()):
            clock=runtime.ReleaseClock(60,self.root)
            now[0]=.1;clock.check();self.assertEqual(len(calls),1)
            now[0]=.25;clock.check();self.assertEqual(len(calls),2)
            now[0]=11
            with self.assertRaisesRegex(RuntimeError,'gap'):clock.check()
            now[0]=.3
            with self.assertRaises(RuntimeError):clock.check()
            now[0]=0.
            fresh=runtime.ReleaseClock(60,self.root)
            denied=runtime.psutil.AccessDenied(pid=123)
            with patch.object(fresh.resources,'inspect',side_effect=denied):
                now[0]=.25
                with self.assertRaises(runtime.psutil.AccessDenied) as caught:fresh.check()
                self.assertIs(caught.exception,denied)
            now[0]=.5
            with self.assertRaises(runtime.psutil.AccessDenied) as caught:fresh.check()
            self.assertIs(caught.exception,denied)
            now[0]=0.
            parent=runtime.ReleaseClock(60,self.root)
            with patch.object(parent.resources,'inspect',return_value=(None,1,runtime.WHOLE_MEMORY_LIMIT_BYTES)):
                now[0]=.25;parent.check()
            with patch.object(parent.resources,'inspect',return_value=(None,1,runtime.WHOLE_MEMORY_LIMIT_BYTES+1)):
                now[0]=.5
                with self.assertRaisesRegex(RuntimeError,'whole_memory'):parent.check()
            self.assertEqual(parent.receipt()['last_actual_resource_observation']['conservative_combined_bytes'],runtime.WHOLE_MEMORY_LIMIT_BYTES+1)

    def test_terminal_memory_caps_boundary_and_denial_are_not_success(self):
        worker_cap=1536*2**20;whole_cap=2048*2**20
        for index,(rss,total,expected) in enumerate([
            (worker_cap,whole_cap,'ok'),(worker_cap+1,whole_cap,'worker_memory_limit'),
            (worker_cap,whole_cap+1,'whole_memory_limit')]):
            with self.subTest(rss=rss,total=total):
                directory=self.root/('worker-'+str(index))
                process=unittest.mock.Mock(pid=123,returncode=0);process.poll.return_value=0
                tree=unittest.mock.Mock();tree.members={(123,1.):object()}
                budget=unittest.mock.Mock();budget.inspect.return_value=(None,rss,total);budget.inspect_artifacts.return_value=0
                def spawned(*args,**kwargs):
                    (directory/'result.json').write_text(json.dumps({'status':'ok'}),encoding='utf-8');return process
                with patch.object(runtime.subprocess,'Popen',side_effect=spawned),\
                     patch.object(runtime,'ProcessTree',return_value=tree),\
                     patch.object(runtime,'ResourceBudget',return_value=budget) as constructor,\
                     patch.object(runtime.time,'monotonic',return_value=0.):
                    result=runtime.run_release_worker({'root':str(self.root)},recipes.REGRESSION_RECIPE,
                        directory,'unused',100,clock=self.clock())
                self.assertEqual(result['status'],expected)
                self.assertEqual(result['observed_worker_tree_peak_bytes'],rss)
                self.assertEqual(result['observed_combined_peak_bytes'],total)
                self.assertEqual(result['worker_memory_limit_bytes'],worker_cap)
                self.assertEqual(result['whole_memory_limit_bytes'],whole_cap)
                self.assertEqual(result['terminal_resource_observation']['status'],'sampled_before_terminal_acceptance')
                constructor.assert_called_once_with(memory_limit=whole_cap);tree.terminate.assert_called_once()
        directory=self.root/'terminal-denial';process=unittest.mock.Mock(pid=123,returncode=0);process.poll.return_value=0
        tree=unittest.mock.Mock();tree.members={(123,1.):object()}
        budget=unittest.mock.Mock();budget.inspect.side_effect=runtime.psutil.AccessDenied(pid=123)
        with patch.object(runtime.subprocess,'Popen',return_value=process),\
             patch.object(runtime,'ProcessTree',return_value=tree),patch.object(runtime,'ResourceBudget',return_value=budget):
            with self.assertRaises(runtime.ProcessObservationError):
                runtime.run_release_worker({'root':str(self.root)},recipes.REGRESSION_RECIPE,
                    directory,'unused',100,clock=self.clock())
        tree.terminate.assert_called_once()

    def test_publication_alias_preflight_preserves_protected_files(self):
        output=self.write('submission.csv','immutable source bytes')
        with self.assertRaises(ValueError):release.validate_output_identity(output,{'sample':output})
        self.assertEqual(output.read_text(),'immutable source bytes')
        other=self.write('task.md','task bytes')
        with patch.object(Path,'samefile',return_value=True),self.assertRaises(ValueError):
            release.validate_output_identity(output,{'task':other})
        with patch.object(Path,'is_symlink',return_value=True),self.assertRaises(ValueError):
            release.validate_output_identity(output,{'task':other})
        release.validate_output_identity(output,{'task':other})
        self.assertEqual(other.read_text(),'task bytes');self.assertEqual(output.read_text(),'immutable source bytes')

    def test_source_base_requirements_and_numerical_adapter_bytes_preserved(self):
        inventory=json.loads((ROOT/'base-inventory.json').read_text('utf-8'))['members_sha256']
        for name in ['requirements.txt','automl_model_lightgbm.py','automl_model_xgboost.py','automl_model_catboost.py',
                     'automl_execution_feature_views.py','automl_execution_preprocessing_history.py',
                     'automl_execution_preprocessing_target_encoding.py','automl_frames.py']:
            self.assertEqual(hashlib.sha256((ROOT/'candidate'/name).read_bytes()).hexdigest(),inventory[name])


if __name__=='__main__':unittest.main()
