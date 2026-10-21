"""Regression tests for effective parameters, isolation and probability contracts."""
from pathlib import Path
import json,sys,tempfile,unittest
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from agent_core import discover,save_submission,dummy_predictions
from agent_policy import normalize,parse_plans,signature
from agent_worker import feature_transform,prepare_frames
from model_utils import make_model,lgbm_metric,sample_weights,tune_class_factors
from agent_runner import file_fingerprints,journal,run_worker,planner_context

class V2Tests(unittest.TestCase):
    def test_xgboost_preserves_string_labels_and_categories(self):
        frame=pd.DataFrame({'x':np.arange(40,dtype=float),'category':pd.Categorical(['a','b']*20)})
        labels=np.array(['z-label','a-label']*20)
        model=make_model({'engine':'xgboost','params':{'max_depth':4}},'classification',1,30)
        model.fit(frame,labels)
        self.assertEqual(model.classes_.tolist(),['a-label','z-label'])
        self.assertTrue(set(model.predict(frame))<=set(labels))
        self.assertTrue(np.allclose(model.predict_proba(frame).sum(axis=1),1))

    def test_feedback_context_is_first_and_keeps_incumbent_code(self):
        recipe=normalize({'engine':'lightgbm','params':{},'feature_code':'def transform(df): return df.copy()'})
        record={'status':'ok','recipe':recipe,'metrics':{'rmse':1.2}}
        context=planner_context({'metric':'rmse','greater_is_better':False,'features':['x'],'target':'answer','id':'key'},
            {'features':[{'name':'x'}],'dictionary':[]},'task',{},[record],record,500,2)
        self.assertLess(list(context).index('feedback_read_first'),list(context).index('features'))
        self.assertEqual(context['best_recipe']['feature_code'],recipe['feature_code'])
        self.assertEqual(context['feedback_read_first'][0]['value'],1.2)

    def test_effective_depth_and_bagging(self):
        model=make_model({'engine':'lightgbm','params':{'depth':6,'subsample':.8}},'regression',2,100)
        self.assertEqual(model.get_params()['max_depth'],6)
        self.assertEqual(model.get_params()['subsample_freq'],1)

    def test_inheritance_does_not_hide_requested_changes(self):
        best=normalize({'engine':'lightgbm','params':{'max_depth':-1,'subsample':1,'class_weight_power':.5},'feature_code':'def transform(df): return df.copy()'})
        changed=normalize({'engine':'lightgbm','params':{'depth':5,'subsample':.8,'class_weights':True}},best)
        self.assertEqual(changed['params']['max_depth'],5)
        self.assertEqual(changed['params']['subsample_freq'],1)
        self.assertEqual(changed['params']['class_weight_power'],1)
        self.assertEqual(changed['feature_code'],best['feature_code'])
        self.assertNotEqual(signature(changed),signature(best))

    def test_planner_json_fences_and_invalid_engine(self):
        plans=parse_plans('```json\n{"candidates":[{"engine":"lightgbm","params":{}}]}\n```')
        self.assertTrue(plans[0]['params']['nested_stopping'])
        with self.assertRaises(ValueError): parse_plans('{"engine":"download_models"}')
        with self.assertRaises(ValueError): parse_plans('{"candidates":[')

    def test_metric_alignment(self):
        metric=lgbm_metric({'kind':'classification','metric':'macro_f1','greater_is_better':True})
        name,value,direction=metric(np.array([0,1,2]),np.eye(3)*.8+.2/3)
        self.assertEqual(name,'macro_f1'); self.assertEqual(value,1); self.assertTrue(direction)
        auc=lgbm_metric({'kind':'classification','metric':'roc_auc','greater_is_better':True})
        self.assertEqual(auc(np.array([0,1,2]),np.eye(3)*.8+.2/3)[1],1)

    def test_provenance_journal_and_stale_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); source=root/'fixed.txt'; source.write_text('fixed')
            before=file_fingerprints({'fixed':source})
            source.write_text('changed')
            self.assertNotEqual(before,file_fingerprints({'fixed':source}))
            recipe=normalize({'engine':'lightgbm','params':{}})
            record={'recipe':recipe,'status':'ok','metrics':{'rmse':1.2}}
            journal(root,'search',record,'rmse','keep_search_incumbent')
            self.assertIn('keep_search_incumbent',(root/'results.tsv').read_text())
            (root/'result.json').write_text('{"status":"ok"}')
            stale=run_worker({},recipe,root,'absent.npz',1)
            self.assertEqual(stale['status'],'error')

    def test_weights_normalized(self):
        weights=sample_weights(pd.Series(['a']*8+['b']*2),{'class_weight_power':.5})
        self.assertAlmostEqual(weights.mean(),1)
        self.assertGreater(weights[-1],weights[0])

    def test_generated_statistics_rejected(self):
        train=pd.DataFrame({'x':np.arange(20,dtype=float)})
        with self.assertRaises(ValueError):
            feature_transform('def transform(df):\n out=df.copy()\n out["x"]=out["x"]-out["x"].mean()\n return out',train,train)
        good,_=feature_transform('def transform(df):\n out=df.copy()\n out["log"]=np.log1p(out["x"])\n return out',train,train)
        self.assertIn('log',good)
        for expression in ['np.fromfile("private")','np.loadtxt("private")','pd.ExcelFile("private")','pd.eval("1+1")']:
            with self.assertRaises(ValueError):
                feature_transform('def transform(df):\n '+expression+'\n return df.copy()',train,train)
        good,_=feature_transform('def transform(df):\n out=df.copy()\n out["number"]=pd.to_numeric(out["x"],errors="coerce")\n return out',train,train)
        self.assertIn('number',good)
        with self.assertRaisesRegex(ValueError,'target/ID'):
            feature_transform('def transform(df):\n if "answer" in df: df["answer"]=np.log1p(df["answer"])\n return df',train,train,('answer','id'))

    def test_unknown_categories_not_fit_on_validation(self):
        train=pd.DataFrame({'cat':['a','a','validation_only'],'x':[1.,np.nan,999.]})
        x,t,_=prepare_frames(train,train.iloc[:1].copy(),'lightgbm',np.array([0,1]))
        self.assertTrue(pd.isna(x['cat'].iloc[2]))
        x,t,_=prepare_frames(train,train.iloc[:1].copy(),'extra_trees',np.array([0,1]))
        self.assertFalse(x.isna().any().any())

    def test_binary_and_multiclass_probability_contracts(self):
        for classes,metric in [(2,'ROC AUC'),(3,'Log loss')]:
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory); n=90
                train=pd.DataFrame({'key':np.arange(n),'x':np.arange(n),'answer':[f'c{i%classes}' for i in range(n)]})
                test=pd.DataFrame({'key':[1001,1002],'x':[1,2]})
                sample=pd.DataFrame({'key':test['key'],'answer':[.5,.5]}) if classes==2 else pd.DataFrame({'key':test['key'],**{f'c{i}':[1/classes]*2 for i in range(classes)}})
                train.to_csv(root/'train.csv',index=False); test.to_csv(root/'test.csv',index=False); sample.to_csv(root/'sample_submission.csv',index=False)
                pd.DataFrame({'feature':train.columns,'role':['id','feature','target']}).to_csv(root/'data_dictionary.csv',index=False)
                (root/'task.md').write_text(f'Classification. Metric {metric}. train.csv test.csv data_dictionary.csv sample_submission.csv')
                spec,_,tr,te,sa,_,_=discover(root/'task.md')
                pred=dummy_predictions(spec,tr,len(te))
                save_submission(spec,sa,te,pred,root/'submission.csv')
                self.assertEqual(pd.read_csv(root/'submission.csv').columns.tolist(),sample.columns.tolist())
                with self.assertRaises(ValueError): save_submission(spec,sa,te,np.full_like(pred,2.),root/'bad.csv')

if __name__=='__main__': unittest.main(verbosity=2)
