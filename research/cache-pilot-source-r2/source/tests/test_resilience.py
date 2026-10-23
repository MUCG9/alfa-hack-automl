"""Offline end-to-end probability and failure-path tests. No real API calls."""
from pathlib import Path
import contextlib,io,json,os,subprocess,sys,tempfile,unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import agent_runner
from agent_core import discover,save_submission,atomic_json,make_split
from agent_policy import normalize,portfolio,fallback
from ensemble_cache import read_cache,combine,materialize

def task(root,classes=2,metric='ROC AUC'):
    rng=np.random.default_rng(590); x=rng.normal(size=240)
    labels=np.arange(len(x))%classes
    train=pd.DataFrame({'record':np.arange(len(x)),'x':x,'signal':labels+rng.normal(size=len(x))*.05,'answer':[f'c{i}' for i in labels]})
    test=pd.DataFrame({'record':np.arange(24)+10000,'x':rng.normal(size=24),'signal':np.arange(24)%classes})
    sample=pd.DataFrame({'record':test.record,'answer':.5}) if classes==2 else pd.DataFrame({'record':test.record,**{f'c{i}':1/classes for i in reversed(range(classes))}})
    train.to_csv(root/'train.csv',index=False); test.to_csv(root/'test.csv',index=False); sample.to_csv(root/'sample_submission.csv',index=False)
    pd.DataFrame({'feature':train.columns,'role':['id','feature','feature','target']}).to_csv(root/'data_dictionary.csv',index=False)
    (root/'task.md').write_text(f'Classification. Metric: {metric}. train.csv test.csv data_dictionary.csv sample_submission.csv')
    return root/'task.md'

class ResilienceTests(unittest.TestCase):
    def test_production_recipes_enforce_inner_stopping(self):
        for kind in ['regression','classification']:
            spec={'kind':kind,'text_features':[]}
            for recipe in portfolio(spec):
                self.assertTrue(recipe['params']['nested_stopping'])
                self.assertTrue(fallback(spec,3,recipe)['params']['nested_stopping'])
            changed=normalize({'engine':'lightgbm','params':{'nested_stopping':False}})
            self.assertTrue(changed['params']['nested_stopping'])

    def test_api_timeout_is_recoverable(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'dummy-not-a-real-key','OPENAI_BASE_URL':'https://invalid.example/v1'}):
            with patch('openai.OpenAI') as client:
                client.return_value.chat.completions.create.side_effect=TimeoutError('simulated')
                plans,call=agent_runner.llm_plan({'best_recipe':None},Path('.'),timeout=1)
        self.assertEqual(plans,[]); self.assertEqual(call['status'],'error')
        self.assertEqual(call['exception_type'],'TimeoutError')

    def test_failed_refit_preserves_working_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path=task(root,metric='Macro F1')
            def worker(spec,recipe,run_dir,split_path,timeout,full_fit=False,fit_iterations=None):
                run_dir.mkdir(parents=True,exist_ok=True)
                if full_fit: return {'status':'timeout','recipe':recipe,'output_dir':str(run_dir)}
                test=pd.read_csv(spec['paths']['test']); sample=pd.read_csv(spec['paths']['sample_submission'])
                save_submission(spec,sample,test,np.repeat('c1',len(test)),run_dir/'submission.csv')
                return {'status':'ok','recipe':recipe,'metrics':{'macro_f1':.4},'output_dir':str(run_dir),'submission':str(run_dir/'submission.csv'),'fit_iterations':100}
            arguments=['solution.py',str(path),'--offline','--max-experiments','1','--time-budget','300','--run-name','failure-test']
            with patch.object(sys,'argv',arguments),patch.object(agent_runner,'run_worker',side_effect=worker),contextlib.redirect_stdout(io.StringIO()):
                agent_runner.main()
            report=json.loads((root/'automl_runs/failure-test/report.json').read_text())
            self.assertEqual(report['final_fit_status'],'timeout'); self.assertTrue(report['integrity_ok'])
            self.assertEqual(set(pd.read_csv(root/'submission.csv').answer),{'c1'})

    def test_actual_cli_binary_and_multiclass_probabilities(self):
        for count,metric in [(2,'ROC AUC'),(3,'Log loss')]:
            with self.subTest(classes=count),tempfile.TemporaryDirectory() as directory:
                root=Path(directory); path=task(root,count,metric)
                env={k:v for k,v in os.environ.items() if not k.startswith('OPENAI_')}; env['AUTOML_THREADS']='1'
                process=subprocess.run([sys.executable,str(ROOT/'solution.py'),str(path),'--offline','--max-experiments','1','--time-budget','300','--run-name','probability'],env=env,capture_output=True,text=True,timeout=120)
                self.assertEqual(process.returncode,0,process.stderr[-3000:])
                report=json.loads((root/'automl_runs/probability/report.json').read_text())
                self.assertEqual(report['final_fit_status'],'ok'); self.assertTrue(report['integrity_ok'])
                expected=pd.read_csv(root/'sample_submission.csv'); result=pd.read_csv(root/'submission.csv')
                self.assertEqual(result.columns.tolist(),expected.columns.tolist()); self.assertEqual(result.record.tolist(),expected.record.tolist())
                probabilities=result.drop(columns='record').to_numpy()
                self.assertTrue(np.isfinite(probabilities).all()); self.assertTrue(((probabilities>=0)&(probabilities<=1)).all())
                if count>2: self.assertTrue(np.allclose(probabilities.sum(axis=1),1))
                self.assertIn('roc_auc' if count==2 else 'log_loss',report['best_validation'])

    def test_ensemble_matches_unsorted_sample_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path=task(root,3,'Log loss')
            spec,_,train,test,sample,_,hashes=discover(path)
            tr,va,_=make_split(spec,train,hashes); np.savez(root/'split.npz',train=tr,validation=va)
            component=normalize({'engine':'lightgbm','params':{'iterations':100,'min_iterations':30}})
            recipe={'engine':'ensemble','hypothesis':'alignment test','params':{},'components':[component,component],'weights':[.5,.5]}
            result=agent_runner.run_worker(spec,recipe,root/'ensemble',root/'split.npz',120)
            self.assertEqual(result['status'],'ok',result)
            with np.load(root/'ensemble/test_probabilities.npz') as stored:
                positions=[list(stored['classes']).index(c) for c in spec['output_columns']]
                exported=pd.read_csv(root/'ensemble/submission.csv')[spec['output_columns']].to_numpy()
                self.assertTrue(np.allclose(exported,stored['probabilities'][:,positions]))
            components=json.loads((root/'ensemble/result.json').read_text())['components']
            caches=[read_cache(spec,component,train) for component in components]
            cached=materialize(spec,caches,[.5,.5],root/'cached-blend',sample,test)
            self.assertTrue(np.allclose(pd.read_csv(cached['submission'])[spec['output_columns']],exported))
            self.assertAlmostEqual(cached['metrics']['log_loss'],result['metrics']['log_loss'],places=10)

    def test_xgboost_worker_probability_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path=task(root,3,'Log loss')
            spec,_,train,test,sample,_,hashes=discover(path)
            tr,va,_=make_split(spec,train,hashes); np.savez(root/'split.npz',train=tr,validation=va)
            recipe=normalize({'engine':'xgboost','params':{'iterations':100,'max_depth':4,'min_iterations':30}})
            result=agent_runner.run_worker(spec,recipe,root/'xgboost',root/'split.npz',120)
            self.assertEqual(result['status'],'ok',result)
            exported=pd.read_csv(result['submission'])
            self.assertEqual(exported.columns.tolist(),sample.columns.tolist())
            self.assertTrue(np.allclose(exported[spec['output_columns']].sum(axis=1),1))
            self.assertEqual(result['early_stopping_source'],'inner_training_holdout')

    def test_outer_labels_do_not_choose_regression_log_transform(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path=task(root)
            train=pd.read_csv(root/'train.csv'); train['answer']=10+train.x*2
            train.to_csv(root/'train.csv',index=False)
            pd.DataFrame({'record':[10000,10001],'x':[1.,2.],'signal':[0.,1.]}).to_csv(root/'test.csv',index=False)
            pd.DataFrame({'record':[10000,10001],'answer':[0.,0.]}).to_csv(root/'sample_submission.csv',index=False)
            path.write_text('Regression. RMSE. train.csv test.csv data_dictionary.csv sample_submission.csv')
            spec,_,train,_,_,_,hashes=discover(path); tr,va,_=make_split(spec,train,hashes)
            np.savez(root/'split.npz',train=tr,validation=va)
            recipe=normalize({'engine':'lightgbm','params':{'iterations':100,'min_iterations':30,'log_target':True}})
            first=agent_runner.run_worker(spec,recipe,root/'first',root/'split.npz',120)
            train.loc[va,'answer']=-.5; train.to_csv(root/'train.csv',index=False)
            second=agent_runner.run_worker(spec,recipe,root/'second',root/'split.npz',120)
            self.assertEqual(first['status'],'ok',first); self.assertEqual(second['status'],'ok',second)
            self.assertEqual(first['fit_iterations'],second['fit_iterations'])
            self.assertTrue(np.allclose(pd.read_csv(root/'first/submission.csv').answer,pd.read_csv(root/'second/submission.csv').answer))

if __name__=='__main__': unittest.main(verbosity=2)
