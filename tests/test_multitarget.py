"""Independent-target contracts, failure isolation and standalone small CLI checks."""
from argparse import Namespace
from pathlib import Path
import hashlib,json,os,subprocess,sys,tempfile,unittest
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src')); sys.path.insert(0,str(ROOT/'tools'))
from build_submission import build_files
from automl.task_understanding.api import discover,load_inputs,MultipleTargets
from automl.search.multitarget import solve_many
from automl.publishing.api import save_submission,publish_targets


class MultiTargetTests(unittest.TestCase):
    def task(self,root,classification=False,no_id=False,reorder=False):
        rng=np.random.default_rng(27); x=rng.normal(size=180)
        train=pd.DataFrame({'x':x,'first':np.where(x>0,'a','b') if classification else x*2+3,
                            'second':np.where(x>1,'red',np.where(x<-.5,'blue','green')) if classification else x*x+1})
        test=pd.DataFrame({'x':[-1.,-.2,0.,.4,1.3,2.]})
        sample=pd.DataFrame({'first':['a']*6 if classification else [0.]*6,
                             'second':['red']*6 if classification else [0.]*6})
        if not no_id:
            train.insert(0,'key',range(180)); test.insert(0,'key',range(500,506)); sample.insert(0,'key',test.key)
        if reorder: sample=sample.iloc[[2,0,5,1,3,4]].reset_index(drop=True)
        for name,frame in [('train',train),('test',test),('sample_submission',sample)]: frame.to_csv(root/(name+'.csv'),index=False)
        pd.DataFrame({'feature':train.columns,'role':['target' if c in {'first','second'} else 'id' if c=='key' else 'feature' for c in train]}).to_csv(root/'data_dictionary.csv',index=False)
        path=root/'task.md'; path.write_text(('Classification. Metric: Macro F1.' if classification else 'Regression. Metric: RMSE.')+' Predict both first and second. Files: train.csv test.csv data_dictionary.csv sample_submission.csv')
        return path,train,test,sample

    def args(self,path,budget=400):
        return Namespace(task=path,time_budget=budget,max_experiments=1,max_planner_calls=4,offline=True,validation_strategy='auto',run_name='run-v2')

    def test_multiple_target_detection_is_structured(self):
        with tempfile.TemporaryDirectory() as directory:
            path,*_=self.task(Path(directory))
            with self.assertRaises(MultipleTargets) as caught: discover(path)
            self.assertEqual(caught.exception.targets,('first','second'))

    def test_projection_shares_inputs_without_mutating_the_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            path,_,_,sample=self.task(Path(directory)); loaded=load_inputs(path)
            first=discover(path,'first',loaded); second=discover(path,'second',loaded)
            self.assertIs(first[2],second[2]); self.assertIs(first[2],loaded['train'])
            self.assertEqual(first[4].columns.tolist(),['key','first']); self.assertEqual(second[4].columns.tolist(),['key','second'])
            self.assertEqual(loaded['sample'].columns.tolist(),sample.columns.tolist())
            self.assertEqual(first[0]['features'],['x']); self.assertEqual(second[0]['features'],['x'])

    def test_unmapped_output_names_fail_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path,_,_,sample=self.task(root)
            sample.rename(columns={'second':'unknown'}).to_csv(root/'sample_submission.csv',index=False)
            with self.assertRaisesRegex(ValueError,'must match declared target names'): discover(path,'second')

    def test_other_declared_target_is_never_an_input_feature(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path,_,test,_=self.task(root)
            test['first']=np.nan; test.to_csv(root/'test.csv',index=False)
            for target in ['first','second']:
                spec=discover(path,target)[0]
                self.assertEqual(spec['features'],['x']); self.assertEqual(spec['all_targets'],['first','second'])

    def test_one_failed_target_preserves_all_baselines_and_other_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path,train,test,sample=self.task(root,reorder=True)
            def solver(args,task_data,output_root):
                spec,_,tr,te,sa,*_=task_data
                if spec['target']=='first': raise RuntimeError('fixture failure')
                save_submission(spec,sa,te,np.full(len(te),9.),output_root/'submission.csv')
                return {'best_validation':{'rmse':1.},'final_fit_status':'ok'}
            report=solve_many(self.args(path),('first','second'),solver)
            actual=pd.read_csv(root/'submission.csv')
            self.assertEqual(actual.key.tolist(),sample.key.tolist())
            self.assertTrue(np.allclose(actual['first'],train['first'].mean())); self.assertTrue(np.allclose(actual.second,9.))
            self.assertEqual(report['children'][0]['status'],'error_preserve_checkpoint'); self.assertTrue(report['integrity_ok'])

    def test_invalid_child_publication_reverts_only_that_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path,train,*_=self.task(root)
            def solver(args,task_data,output_root):
                (output_root/'submission.csv').write_text('bad\n1\n')
                return {'best_validation':{'rmse':1.},'final_fit_status':'ok'}
            report=solve_many(self.args(path),('first','second'),solver)
            actual=pd.read_csv(root/'submission.csv')
            for child in report['children']:
                self.assertEqual(child['status'],'invalid_publication_baseline'); self.assertFalse(child['trained'])
            self.assertTrue(np.allclose(actual['first'],train['first'].mean()))

    def test_short_budget_exports_all_targets_without_starting_search(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path,*_=self.task(root,no_id=True)
            def forbidden(*args,**kwargs): raise AssertionError('Search should not start')
            report=solve_many(self.args(path,1),('first','second'),forbidden)
            self.assertTrue(all(c['status']=='budget_skipped_baseline' for c in report['children']))
            self.assertEqual(pd.read_csv(root/'submission.csv').columns.tolist(),['first','second'])

    def test_time_and_planner_budgets_are_shared_not_multiplied(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path,*_=self.task(root); calls=[]
            def solver(args,task_data,output_root):
                calls.append((args.time_budget,args.max_planner_calls,output_root))
                return {'best_validation':None,'final_fit_status':'fallback_or_search_checkpoint'}
            solve_many(self.args(path),('first','second'),solver)
            self.assertEqual(len(calls),2); self.assertLessEqual(sum(c[1] for c in calls),4)
            self.assertTrue(all(c[0]<400 for c in calls)); self.assertNotEqual(calls[0][2],calls[1][2])

    def test_combiner_rejects_a_reordered_child_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path,train,test,sample=self.task(root); parts=[]
            for target in ['first','second']:
                data=discover(path,target); spec=data[0]; destination=root/(target+'.csv')
                save_submission(spec,data[4],test,np.ones(len(test)),destination); parts.append((spec,destination))
            frame=pd.read_csv(parts[0][1]); frame.iloc[::-1].to_csv(parts[0][1],index=False)
            with self.assertRaisesRegex(ValueError,'ID order'): publish_targets(parts,sample,root/'bad.csv')

    def cli(self,classification=False,no_id=False,reorder=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path,train,test,sample=self.task(root,classification,no_id,reorder)
            before=hashlib.sha256((root/'train.csv').read_bytes()).hexdigest()
            for name,data in build_files().items(): (root/name).write_bytes(data)
            env={k:v for k,v in os.environ.items() if not k.startswith('OPENAI_')}; env.update(AUTOML_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
            result=subprocess.run([sys.executable,'solution.py','task.md','--offline','--max-experiments','1','--time-budget','400'],cwd=root,env=env,capture_output=True,text=True,timeout=180)
            self.assertEqual(result.returncode,0,result.stderr[-3000:]+'\n'+result.stdout[-1500:])
            report=json.loads(next((root/'automl_runs').glob('multi-target-*/report.json')).read_text())
            self.assertEqual(len(report['children']),2); self.assertTrue(report['integrity_ok'])
            self.assertTrue(all(c['final_fit_status']=='ok' and c['trained'] for c in report['children']))
            actual=pd.read_csv(root/'submission.csv'); self.assertEqual(actual.columns.tolist(),sample.columns.tolist())
            self.assertFalse(actual.isna().any().any()); self.assertEqual(len(actual),len(test))
            if not no_id: self.assertEqual(actual.key.tolist(),sample.key.tolist())
            if classification:
                for column in ['first','second']: self.assertTrue(set(actual[column])<=set(train[column]))
            self.assertEqual(hashlib.sha256((root/'train.csv').read_bytes()).hexdigest(),before)

    def test_flat_cli_two_regression_targets_and_reordered_ids(self): self.cli(reorder=True)
    def test_flat_cli_two_regression_targets_without_id(self): self.cli(no_id=True)
    def test_flat_cli_two_classification_targets(self): self.cli(classification=True)


if __name__=='__main__': unittest.main(verbosity=2)
