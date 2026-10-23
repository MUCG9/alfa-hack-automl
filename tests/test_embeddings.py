"""Experimental Torch CPU contracts and small real fitting/refitting fixtures."""
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from automl.contracts.messages import TaskSpec
from automl.contracts.embeddings import EmbeddingRequest
from automl.execution.embeddings_api import fit_predict_embeddings
from automl.execution.model_adapters.embeddings import Encoder
from automl.publishing.api import save_submission


def fixture(kind):
    rng=np.random.default_rng(154)
    frame=pd.DataFrame({'x':rng.normal(size=600),'color':np.where(np.arange(600)%2,'red','blue')})
    frame.loc[np.arange(0,600,11),'x']=np.nan
    frame['target']=np.where(frame.color=='red','a','b') if kind=='classification' else 10+frame.x.fillna(0)*2
    test=pd.DataFrame({'x':[np.nan,1.,2.],'color':['unseen','red',None]})
    task=TaskSpec(kind=kind,target='target',identifier=None,features=('x','color'),
                  metric='macro_f1' if kind=='classification' else 'rmse',greater_is_better=kind=='classification')
    req=EmbeddingRequest(task,('color',),('b','a') if kind=='classification' else (),tuple(range(450)),
                         tuple(range(350)),tuple(range(350,450)),tuple(range(450,600)),seconds=60,epochs=3,threads=1)
    return req,frame,test


class EmbeddingTests(unittest.TestCase):
    def check_export(self,request,test,predictions):
        test=test.assign(record=[101,102,103])
        sample=pd.DataFrame({'record':[103,101,102],'target':[0.,0.,0.]})
        spec={'kind':request.task.kind,'metric':request.task.metric,'target':'target','id':'record',
              'sample_test_positions':[2,0,1],'classes':list(request.classes),'output_columns':['target']}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'submission.csv';save_submission(spec,sample,test,predictions,path)
            output=pd.read_csv(path)
        self.assertEqual(output.record.tolist(),sample.record.tolist())
        self.assertFalse(output.isna().any().any())
        expected=np.asarray(predictions)[[2,0,1]]
        if request.task.kind=='classification':np.testing.assert_array_equal(output.target.to_numpy(),expected)
        else:np.testing.assert_allclose(output.target.to_numpy(),expected,rtol=1e-7,atol=1e-7)

    def test_contract_rejects_overlap(self):
        req,_,_=fixture('regression')
        with self.assertRaises(ValueError):replace(req,evaluation_rows=(1,))
        with self.assertRaises(ValueError):replace(req,inner_validation_rows=(1,))

    def test_contract_rejects_invalid_resources(self):
        req,_,_=fixture('regression')
        for params in ({'seconds':float('nan')},{'epochs':21},{'threads':True},{'fitting_rows':(True,)}):
            with self.subTest(params=params),self.assertRaises(ValueError):replace(req,**params)

    def test_encoder_fitting_only_and_oov(self):
        frame=pd.DataFrame({'x':[1.,3.,10000.],'color':['red','red','new']})
        encoder=Encoder(('x','color'),('color',)).fit(frame.iloc[:2])
        self.assertEqual(encoder.median['x'],2.)
        self.assertNotIn('new',encoder.vocab['color'])
        numeric,categories=encoder.transform(frame.iloc[2:])
        self.assertEqual(categories[0,0],0)
        self.assertEqual(numeric[0,0],10.)

    def test_encoder_all_categorical(self):
        frame=pd.DataFrame({'c':['a',None,'b']})
        encoder=Encoder(('c',),('c',)).fit(frame)
        a,b=encoder.transform(frame)
        self.assertEqual(a.shape,(3,0));self.assertEqual(b.shape,(3,1))

    def test_classification_real_refit_and_probability_order(self):
        req,frame,test=fixture('classification')
        result=fit_predict_embeddings(req,frame,test)
        self.assertTrue(result.full_fit_ok)
        self.assertEqual(result.classes,('b','a'))
        self.assertEqual(result.evaluation_probabilities.shape,(150,2))
        self.assertTrue(np.allclose(result.test_probabilities.sum(axis=1),1.))
        np.testing.assert_array_equal(result.test_prediction,np.asarray(req.classes)[result.test_probabilities.argmax(axis=1)])
        self.assertFalse(result.metadata['pretrained'])
        self.check_export(req,test,result.test_prediction)

    def test_regression_real_refit_and_local_statistics(self):
        req,frame,test=fixture('regression')
        result=fit_predict_embeddings(req,frame,test)
        self.assertTrue(result.full_fit_ok)
        self.assertTrue(np.isfinite(result.test_prediction).all())
        self.assertIsNone(result.test_probabilities)
        self.assertAlmostEqual(result.metadata['target_center'],float(frame.target.iloc[:450].to_numpy(dtype=np.float32).mean()),places=5)
        self.assertEqual(result.metadata['stopping_source'],'inner_fitting_only')
        self.check_export(req,test,result.test_prediction)

    def test_outer_target_values_do_not_change_fit(self):
        req,frame,test=fixture('regression')
        first=fit_predict_embeddings(req,frame,test)
        changed=frame.copy();changed.loc[450:,'target']=999999.
        second=fit_predict_embeddings(req,changed,test)
        np.testing.assert_allclose(first.test_prediction,second.test_prediction,rtol=0,atol=0)


if __name__=='__main__':unittest.main()
