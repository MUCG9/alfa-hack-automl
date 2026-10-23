"""A scalar probability must refer to the requested label, not sorted column 1."""
from pathlib import Path
import os,subprocess,sys,tempfile,unittest
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src')); sys.path.insert(0,str(ROOT/'tools'))
from build_submission import build_files
from automl.task_understanding.probabilities import infer_positive_class
from automl.publishing.api import dummy_predictions,positive_class_index
from automl.execution.api import materialize
from automl.execution.model_adapters.linear_text import linear_text_fit


class BinaryProbabilityTests(unittest.TestCase):
    def test_literal_zero_overrides_sorted_last_label(self):
        for text in ['Positive class: 0.','positive_label = `0`','Output probability of class 0.','{"positive_class": "0"}']:
            self.assertEqual(infer_positive_class(text,['0','1'])[0],'0')

    def test_quoted_labels_russian_and_literal_domain_label(self):
        for text,classes,expected in [('positive_class = "not spam"',['not spam','spam'],'not spam'),
            ('Вероятность класса `нет`.',['да','нет'],'нет'),('Output probability of fraud.',['fraud','normal'],'fraud')]:
            self.assertEqual(infer_positive_class(text,classes)[0],expected)

    def test_default_casefold_and_numeric_metadata(self):
        self.assertEqual(infer_positive_class('Classification. ROC AUC.',['a','z']),('z','legacy_last_class_default'))
        self.assertEqual(infer_positive_class('Positive class: YES',['No','Yes'])[0],'Yes')
        self.assertEqual(infer_positive_class('Positive class: 0',['0.0','1.0'],True)[0],'0.0')

    def test_conflicting_or_unknown_explicit_classes_are_rejected(self):
        for text in ['Positive class: missing','Positive class: 0. Output probability of class 1.']:
            with self.assertRaises(ValueError): infer_positive_class(text,['0','1'])
        self.assertEqual(infer_positive_class('Output probability of class 0. Do not output probability of class 1.',['0','1'])[0],'0')

    def test_dummy_prior_and_model_class_order_follow_positive_label(self):
        spec={'target':'y','classes':['0','1'],'positive_class':'0','prediction_type':'probability'}
        self.assertTrue(np.allclose(dummy_predictions(spec,pd.DataFrame({'y':[0,0,0,1]}),3),.75))
        self.assertEqual(positive_class_index(spec,['1','0']),1)
        with self.assertRaises(ValueError): positive_class_index(spec,['1','other'])

    def test_cached_materialization_projects_positive_column_and_sample_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); classes=['0','1']; truth=np.array(['0','1','0','1']); rows=np.arange(4)
            spec={'kind':'classification','metric':'roc_auc','target':'y','id':'key','classes':classes,'positive_class':'0',
                  'prediction_type':'probability','output_columns':['prob'],'sample_test_positions':[2,0,1]}
            validation=np.array([[.8,.2],[.2,.8],[.7,.3],[.3,.7]]); test=np.array([[.9,.1],[.2,.8],[.4,.6]])
            caches=[{'rows':rows,'truth':truth,'validation':validation,'test':test,'record':{'recipe':{'engine':'lightgbm','params':{}},'fit_iterations':30}} for _ in range(2)]
            sample=pd.DataFrame({'key':[12,10,11],'prob':.5}); frame=pd.DataFrame({'key':[10,11,12]})
            result=materialize(spec,caches,[.5,.5],root/'blend',sample,frame)
            actual=pd.read_csv(result['submission'])
            self.assertTrue(np.allclose(actual.prob,[.4,.9,.2]))

    def test_text_adapter_projects_the_same_requested_class(self):
        frame=pd.DataFrame({'body':['alpha clean reliable message']*20+['beta fraud unreliable message']*20})
        test=pd.DataFrame({'body':['alpha clean reliable message','beta fraud unreliable message']})
        y=pd.Series(['a']*20+['z']*20)
        spec={'kind':'classification','metric':'roc_auc','classes':['a','z'],'positive_class':'a','prediction_type':'probability','output_columns':['prob'],'text_features':['body']}
        recipe={'params':{'text_classifier':'logistic','text_C':1.}}
        tr=np.r_[np.arange(15),np.arange(20,35)]; va=np.r_[np.arange(15,20),np.arange(35,40)]
        pred,_,_,raw,_,classes=linear_text_fit(spec,recipe,frame.copy(),test.copy(),y,tr,va,False,1)
        self.assertTrue(np.allclose(pred,raw[:,list(classes).index('a')]))

    def cli(self,string_labels=False,no_id=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); rng=np.random.default_rng(71); x=rng.normal(size=180)
            train=pd.DataFrame({'key':range(180),'x':x,'label':np.where(x>0,'accept','reject') if string_labels else np.where(x>0,0,1)})
            test=pd.DataFrame({'key':range(600,604),'x':[1.5,.8,-1.5,-.8]}); sample=pd.DataFrame({'key':test.key,'prob':.5})
            if no_id: sample=sample[['prob']]
            else: sample=sample.iloc[::-1].reset_index(drop=True)
            for name,frame in [('train',train),('test',test),('sample_submission',sample)]: frame.to_csv(root/(name+'.csv'),index=False)
            pd.DataFrame({'feature':train.columns,'role':['id','feature','target']}).to_csv(root/'data_dictionary.csv',index=False)
            positive='accept' if string_labels else '0'
            (root/'task.md').write_text(f'Classification. Primary metric: ROC AUC. Positive class: {positive}. Output probability of class {positive}. Files: train.csv test.csv sample_submission.csv data_dictionary.csv')
            for name,data in build_files().items(): (root/name).write_bytes(data)
            env={k:v for k,v in os.environ.items() if not k.startswith('OPENAI_')}; env.update(AUTOML_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
            result=subprocess.run([sys.executable,'solution.py','task.md','--offline','--max-experiments','1','--time-budget','300'],cwd=root,env=env,capture_output=True,text=True,timeout=120)
            self.assertEqual(result.returncode,0,result.stderr[-2200:]+'\n'+result.stdout[-1000:])
            output=pd.read_csv(root/'submission.csv')
            self.assertEqual(output.columns.tolist(),sample.columns.tolist())
            if no_id: self.assertGreater(output.prob.iloc[0],output.prob.iloc[2])
            else:
                self.assertEqual(output.key.tolist(),sample.key.tolist())
                by_id=output.set_index('key').prob; self.assertGreater(by_id.loc[600],by_id.loc[602])
            self.assertTrue(((output.prob>=0)&(output.prob<=1)).all())

    def test_flat_cli_numeric_positive_zero(self): self.cli()
    def test_flat_cli_string_positive_first_without_id(self): self.cli(True,True)


if __name__=='__main__': unittest.main(verbosity=2)
