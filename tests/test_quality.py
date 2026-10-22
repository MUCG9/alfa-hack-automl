"""Regression checks for process ownership and nested fit isolation."""
from pathlib import Path
import json,os,subprocess,sys,tempfile,time,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src')); sys.path.insert(0,str(ROOT/'tests'))
import numpy as np
import pandas as pd
import psutil
from automl.infrastructure.processes import wait_owned
from automl.execution import worker
from test_resilience import task
from agent_core import discover,make_split
from automl.evaluation.api import make_folds
from automl.execution.preprocessing.frames import prepare_frames


class QualityTests(unittest.TestCase):
    def test_xgboost_class_search_changes_effective_capacity_without_weight_drift(self):
        from agent_policy import fallback,normalize,signature
        from automl.execution.model_adapters.xgboost import create_model
        best=normalize({'engine':'xgboost','params':{'max_depth':6,'min_child_weight':3,'reg_lambda':8,'class_weight_power':.5}})
        before=signature(best); effective=[]
        for number in range(4,8):
            recipe=fallback({'kind':'classification'},number,best)
            self.assertEqual(recipe['params']['class_weight_power'],.5)
            model=create_model(recipe,'classification',1,30)
            effective.append(tuple(model.params[k] for k in ['max_depth','min_child_weight','reg_lambda']))
        self.assertEqual(len(set(effective)),4)
        self.assertNotIn((6,3,8),effective)
        self.assertEqual(signature(best),before)
        for depth in [3,12]:
            boundary=normalize({'engine':'xgboost','params':{'max_depth':depth,'min_child_weight':50,'reg_lambda':100}})
            for number in range(4,8):
                model=create_model(fallback({'kind':'classification'},number,boundary),'classification',1,30)
                self.assertTrue(3<=model.params['max_depth']<=12)
                self.assertTrue(1<=model.params['min_child_weight']<=50)
                self.assertTrue(0<=model.params['reg_lambda']<=100)

    def test_future_class_absent_from_history_keeps_a_working_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); n=240
            train=pd.DataFrame({'record':np.arange(n),'window':np.repeat([1,2,3],80),
                                'measure':np.tile(np.arange(80),3),'segment':['a','b']*120})
            train['answer']=np.where(train.window==3,'new',train.segment)
            test=train.iloc[:12].drop(columns='answer').copy();test['record']+=10000;test['window']=4
            train.to_csv(root/'train.csv',index=False);test.to_csv(root/'test.csv',index=False)
            pd.DataFrame({'record':test.record,'answer':'a'}).to_csv(root/'sample_submission.csv',index=False)
            pd.DataFrame({'feature':train.columns,'role':['id','feature','feature','feature','target'],
                          'description_ru':['','Порядковый код периода наблюдения','','','']}).to_csv(root/'data_dictionary.csv',index=False)
            path=root/'task.md';path.write_text('Classification. Metric Macro F1. train.csv test.csv data_dictionary.csv sample_submission.csv')
            env={k:v for k,v in os.environ.items() if not k.startswith('OPENAI_')};env['AUTOML_THREADS']='1'
            p=subprocess.run([sys.executable,str(ROOT/'solution.py'),str(path),'--offline','--max-experiments','1','--time-budget','300','--run-name','unavailable-time'],env=env,capture_output=True,text=True,timeout=120)
            self.assertEqual(p.returncode,0,p.stderr[-2000:])
            report=json.loads((root/'automl_runs/unavailable-time/report.json').read_text())
            self.assertIn('Forward split unavailable',report['spec']['validation_warning'])
            self.assertNotEqual(report['spec'].get('validation_strategy'),'time')
            self.assertEqual(report['final_fit_status'],'ok')

    def test_default_cli_detects_future_period_and_exports_refit(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); n=240
            train=pd.DataFrame({'record':np.arange(n),'window':np.repeat([1,2,3],80),
                                'measure':np.tile(np.arange(80),3),'segment':['a','b']*120})
            train['answer']=train['measure']*.3+train['window']
            test=train.iloc[:12].drop(columns='answer').copy();test['record']+=10000;test['window']=4
            sample=pd.DataFrame({'record':test.record,'answer':0.})
            train.to_csv(root/'train.csv',index=False);test.to_csv(root/'test.csv',index=False);sample.to_csv(root/'sample_submission.csv',index=False)
            pd.DataFrame({'feature':train.columns,'role':['id','feature','feature','feature','target'],
                          'dtype':['numeric','numeric','numeric','category','numeric'],
                          'description_ru':['','Порядковый код периода наблюдения','','','']}).to_csv(root/'data_dictionary.csv',index=False)
            path=root/'task.md';path.write_text('Regression. Metric RMSE. train.csv test.csv data_dictionary.csv sample_submission.csv')
            env={k:v for k,v in os.environ.items() if not k.startswith('OPENAI_')}; env['AUTOML_THREADS']='1'
            r=subprocess.run([sys.executable,str(ROOT/'solution.py'),str(path),'--offline','--max-experiments','1','--time-budget','300','--run-name','time-test'],env=env,capture_output=True,text=True,timeout=120)
            self.assertEqual(r.returncode,0,r.stderr[-2000:])
            report=json.loads((root/'automl_runs/time-test/report.json').read_text())
            self.assertEqual(report['spec']['validation_strategy'],'time')
            self.assertEqual(report['split']['cut'],3.)
            self.assertTrue(report['selected_recipe']['params']['target_encoding_auto_groups'])
            self.assertEqual(report['final_fit_status'],'ok')
            self.assertTrue(report['integrity_ok'])
            result=pd.read_csv(root/'submission.csv')
            self.assertEqual(result.record.tolist(),test.record.tolist())
            self.assertTrue(np.isfinite(result.answer).all())

    def test_pair_specialists_keep_class_order_and_valid_probabilities(self):
        from automl.execution.model_adapters.lightgbm import create_model
        x=pd.DataFrame({'x':np.zeros(360)})
        y=np.asarray(['major']*300+['rare-a']*30+['rare-b']*30)
        model=create_model({'params':{'pair_refinement':True}},'classification',1,30)
        model.fit(x,y)
        self.assertTrue(1<=len(model.specialist_pairs_)<=3)
        self.assertEqual(model.classes_.tolist(),['major','rare-a','rare-b'])
        p=model.predict_proba(x.iloc[:5])
        self.assertEqual(p.shape,(5,3)); self.assertTrue(np.isfinite(p).all())
        np.testing.assert_allclose(p.sum(axis=1),1.)
        self.assertTrue(set(model.predict(x.iloc[:5]))<=set(y))

    def test_encoding_group_switches_override_inherited_alternative(self):
        from agent_policy import normalize
        auto=normalize({'engine':'lightgbm','params':{'target_encoding_auto_groups':True}})
        manual=normalize({'engine':'lightgbm','params':{'target_encoding_groups':[['a','b']]}},auto)
        self.assertTrue(manual['params']['target_encoding'])
        self.assertFalse(manual['params']['target_encoding_auto_groups'])
        restored=normalize({'engine':'lightgbm','params':{'target_encoding_auto_groups':True}},manual)
        self.assertNotIn('target_encoding_groups',restored['params'])
        with self.assertRaises(ValueError): normalize({'engine':'lightgbm','params':{'target_encoding_groups':'a,b'}})

    def test_history_group_discovery_is_train_only_and_name_independent(self):
        from automl.execution.preprocessing.target_encoding import infer_history_groups
        x=pd.DataFrame({'window':np.repeat([1,2,3],50),'category':['a','b']*75,'measure':np.tile(np.arange(50),3)})
        rows=np.arange(100)
        groups=infer_history_groups(x,rows,'window',['category'])
        self.assertEqual(groups,[['category','measure']])
        self.assertEqual(groups,infer_history_groups(x,rows,'window',[]))
        changed=x.copy();changed.loc[100:,'measure']=99999
        self.assertEqual(groups,infer_history_groups(changed,rows,'window',['category']))

    def test_future_period_detection_and_forward_backtests(self):
        from automl.task_understanding.service import infer_time_candidate
        from automl.evaluation.api import make_time_split
        x=pd.DataFrame({'window_code':np.repeat([1,2,3,4,5],3),'y':np.arange(15)})
        test=pd.DataFrame({'window_code':[6,6]})
        dictionary=pd.DataFrame({'feature':['window_code'],'description_ru':['Порядковый код периода наблюдения']})
        candidate=infer_time_candidate(dictionary,x,test,['window_code'])
        self.assertEqual(candidate['column'],'window_code')
        spec={'kind':'regression','target':'y','features':['window_code'],'time_candidate':candidate,'validation_strategy':'time'}
        for offset,cut in [(0,5),(1,4)]:
            tr,va,info=make_time_split(spec,x,offset)
            self.assertTrue((x.window_code.iloc[tr]<cut).all())
            self.assertTrue((x.window_code.iloc[va]==cut).all())
            self.assertEqual(info['excluded_future_rows'],offset*3)
        with self.assertRaises(ValueError): make_folds(spec,x,np.arange(15))
        dictionary['description_ru']='Год постройки'; dictionary['feature']='construction_year'
        self.assertIsNone(infer_time_candidate(dictionary,x.rename(columns={'window_code':'construction_year'}),test.rename(columns={'window_code':'construction_year'}),['construction_year']))

    def test_oof_calibration_does_not_read_outer_validation_labels(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); path=task(root,metric='Macro F1')
            spec,_,train,_,_,_,hashes=discover(path)
            tr,va,_=make_split(spec,train,hashes); np.savez(root/'split.npz',train=tr,validation=va)
            recipe={'engine':'lightgbm','params':{'iterations':35,'min_iterations':10,'nested_stopping':True,'calibrate':True,'calibration_folds':3}}
            records=[]; submissions=[]
            for number in range(2):
                out=root/str(number); out.mkdir()
                worker.run({'spec':spec,'recipe':recipe,'output_dir':str(out),'split_path':str(root/'split.npz'),'threads':1})
                records.append(json.loads((out/'result.json').read_text())); submissions.append((out/'submission.csv').read_bytes())
                train.loc[va,'answer']=train.loc[va,'answer'].map({'c0':'c1','c1':'c0'})
                train.to_csv(spec['paths']['train'],index=False)
            self.assertEqual(records[0]['calibration_status'],'training_oof_matching_iterations')
            self.assertEqual(len(records[0]['calibration_folds']),3)
            self.assertEqual(records[0]['class_factors'],records[1]['class_factors'])
            self.assertEqual(submissions[0],submissions[1])

    def test_target_encoding_excludes_own_group_and_outer_labels(self):
        from automl.execution.preprocessing.target_encoding import target_encode_frames
        x=pd.DataFrame({'cat':['same']*14,'context':np.repeat(np.arange(7),2)})
        groups=np.repeat(np.arange(7),2); rows=np.arange(12)
        y=pd.Series(np.arange(14,dtype=float))
        options={'groups':[['cat','context']],'add_counts':True,'half_life':1,'time_column':'context'}
        first,test=target_encode_frames(x,x.iloc[:1],y,rows,groups,**options)
        changed=y.copy(); changed.iloc[:2]=10000
        second,_=target_encode_frames(x,x.iloc[:1],changed,rows,groups,**options)
        np.testing.assert_allclose(first['__te_0_0'].iloc[:2],second['__te_0_0'].iloc[:2])
        changed=y.copy(); changed.iloc[12:]=10000
        third,test3=target_encode_frames(x,x.iloc[:1],changed,rows,groups,**options)
        pd.testing.assert_frame_equal(first,third); pd.testing.assert_frame_equal(test,test3)

    def test_lsa_logistic_supports_tiny_vocabulary_and_probability_output(self):
        from automl.execution.model_adapters.linear_text import linear_text_fit
        x=pd.DataFrame({'review':['bright pleasant excellent','dark broken awful']*20})
        y=pd.Series(['positive','negative']*20)
        spec={'kind':'classification','metric':'roc_auc','text_features':['review'],'prediction_type':'probability'}
        output,_,metrics,probabilities,_,classes=linear_text_fit(spec,{'params':{'text_classifier':'logistic','text_svd_components':64}},x.copy(),x.iloc[:4].copy(),y,np.arange(30),np.arange(30,40),False,1)
        self.assertEqual(output.shape,(4,)); self.assertEqual(probabilities.shape,(4,2))
        self.assertAlmostEqual(metrics['roc_auc'],1.)
        np.testing.assert_allclose(output,probabilities[:,1])

    def test_flat_release_nested_in_checkout_uses_its_own_worker(self):
        from automl.infrastructure import runtime
        with tempfile.TemporaryDirectory(prefix='nested-release-',dir=ROOT) as folder:
            base=Path(folder)
            for name in ['solution.py','automl_worker.py','automl_runtime.py']: (base/name).touch()
            with patch.object(runtime,'__file__',str(base/'automl_runtime.py')):
                self.assertEqual(runtime.project_root(),base)
                self.assertEqual(runtime.worker_entrypoint(),base/'automl_worker.py')

    def test_grouped_oof_has_unique_coverage_and_no_group_overlap(self):
        groups=np.repeat(np.arange(30),3)
        train=pd.DataFrame({'y':np.repeat(np.arange(30)%3,3)})
        folds=make_folds({'kind':'classification','target':'y'},train,groups,5)
        coverage=np.zeros(len(train),int)
        for tr,va,info in folds:
            coverage[va]+=1
            self.assertFalse(set(groups[tr])&set(groups[va]))
            self.assertEqual(set(train.y.iloc[tr]),{0,1,2})
            self.assertEqual(info['validation_missing_classes'],sorted(map(str,{0,1,2}-set(train.y.iloc[va]))))
        np.testing.assert_array_equal(coverage,np.ones(len(train)))

    def test_frequency_and_median_ignore_validation_values(self):
        train=pd.DataFrame({'category':['a','a','b','other'],'x':[1.,3.,np.nan,100.]})
        first,_,_=prepare_frames(train,train.iloc[:1],'extra_trees',[0,1])
        changed=train.copy(); changed.loc[2:,'x']=90000; changed.loc[2:,'category']='new'
        second,_,_=prepare_frames(changed,changed.iloc[:1],'extra_trees',[0,1])
        pd.testing.assert_frame_equal(first.iloc[:2],second.iloc[:2])
        self.assertEqual(first.loc[2,'x'],2.)
        self.assertEqual(first.loc[2,'category'],0.)

    def test_ova_produces_finite_probability_matrix(self):
        from automl.execution.model_adapters.lightgbm import create_model
        from automl.evaluation.api import adjusted_probabilities
        x=pd.DataFrame({'x':np.arange(90)})
        y=np.asarray(['a','b','c']*30)
        m=create_model({'params':{'multiclass_strategy':'ova','min_child_samples':5}},'classification',1,30)
        m.fit(x,y)
        values=adjusted_probabilities(m.predict_proba(x),m.classes_,{})
        self.assertEqual(values.shape,(90,3)); self.assertTrue(np.isfinite(values).all())
        np.testing.assert_allclose(values.sum(axis=1),1.)

    def test_watchdog_owns_detached_worker_and_grandchild(self):
        with tempfile.TemporaryDirectory() as folder:
            marker=Path(folder)/'pids.json'
            child="import subprocess,sys,time,os,json; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],start_new_session=True); open(sys.argv[1],'w').write(json.dumps([os.getpid(),p.pid])); time.sleep(60)"
            parent="import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]],start_new_session=True); time.sleep(60)"
            p=subprocess.Popen([sys.executable,'-c',parent,child,str(marker)],start_new_session=True)
            with self.assertRaises(subprocess.TimeoutExpired): wait_owned(p,2)
            self.assertTrue(marker.exists())
            for pid in json.loads(marker.read_text()):
                if psutil.pid_exists(pid): self.assertEqual(psutil.Process(pid).status(),psutil.STATUS_ZOMBIE)

    def test_inner_preprocessing_fits_only_inner_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); path=task(root,metric='Macro F1')
            spec,_,train,_,_,_,hashes=discover(path)
            tr,va,_=make_split(spec,train,hashes); np.savez(root/'split.npz',train=tr,validation=va)
            seen=[]
            original=worker.prepare_frames
            def capture(x,test,engine,rows):
                seen.append(set(rows)); return original(x,test,engine,rows)
            recipe={'engine':'lightgbm','params':{'iterations':35,'min_iterations':10,'nested_stopping':True},'feature_code':''}
            with patch.object(worker,'prepare_frames',side_effect=capture):
                worker.run({'spec':spec,'recipe':recipe,'output_dir':str(root),'split_path':str(root/'split.npz'),'threads':1})
            self.assertEqual(len(seen),2)
            self.assertLess(len(seen[0]),len(tr)); self.assertTrue(seen[0]<set(tr))
            self.assertEqual(seen[1],set(tr))

    def test_inner_fit_error_is_not_reported_as_rare_class_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); path=task(root,metric='Macro F1')
            spec,_,train,_,_,_,hashes=discover(path)
            tr,va,_=make_split(spec,train,hashes); np.savez(root/'split.npz',train=tr,validation=va)
            with patch.object(worker,'fit_options',side_effect=ValueError('adapter defect')):
                with self.assertRaisesRegex(ValueError,'adapter defect'):
                    worker.run({'spec':spec,'recipe':{'engine':'lightgbm','params':{'iterations':30,'nested_stopping':True}},'output_dir':str(root),'split_path':str(root/'split.npz'),'threads':1})


if __name__=='__main__': unittest.main(verbosity=2)
