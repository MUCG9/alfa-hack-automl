"""Contract and real-fit integration checks for opt-in causal history features."""
from pathlib import Path
import contextlib,io,json,sys,tempfile,unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tests'))
import numpy as np
import pandas as pd
from agent_policy import normalize,signature
from agent_core import discover
from automl.execution import worker


def fixture(root):
    train=pd.DataFrame({'id':np.arange(240),'period':np.repeat(np.arange(1,7),40),
                        'segment':np.tile(['a','b'],120),'measure':np.tile(np.arange(40),6)})
    train['target']=train.measure*.7+train.period*2+np.sin(train.measure)
    test=train.iloc[:12].drop(columns='target').copy();test['period']=7;test['id']+=1000
    sample=pd.DataFrame({'id':test.id,'target':0.})
    train.to_csv(root/'train.csv',index=False);test.to_csv(root/'test.csv',index=False)
    sample.to_csv(root/'sample_submission.csv',index=False)
    pd.DataFrame({'feature':train.columns,'role':['id','feature','feature','feature','target']}).to_csv(root/'data_dictionary.csv',index=False)
    task=root/'task.md';task.write_text('Regression. Target: target. Metric: RMSE. train.csv test.csv data_dictionary.csv sample_submission.csv')
    spec,*_=discover(task)
    spec.update(validation_strategy='time',time_column='period',time_candidate={'column':'period','split_mode':'period'})
    np.savez(root/'split.npz',train=np.arange(200),validation=np.arange(200,240))
    return spec,train


class HistoryWorkerTests(unittest.TestCase):
    def test_flag_is_preserved_in_signature_and_invalid_recipes_rejected(self):
        base={'engine':'lightgbm','params':{'target_encoding':True,'target_encoding_groups':[['segment','measure']]}}
        control=normalize(base)
        candidate=normalize({'engine':'lightgbm','params':{'history_asof':True}},control)
        self.assertTrue(candidate['params']['history_asof'])
        self.assertNotEqual(signature(control),signature(candidate))
        for params in [{'history_asof':'yes'},{'history_asof':True},{'history_asof':True,'target_encoding':True}]:
            with self.subTest(params=params),self.assertRaises(ValueError):normalize({'engine':'lightgbm','params':params})

    def test_real_worker_export_and_outer_label_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);spec,train=fixture(root)
            recipe=normalize({'engine':'lightgbm','params':{'iterations':35,'min_iterations':10,
                'num_leaves':15,'target_encoding':True,'target_encoding_groups':[['segment','measure']],
                'history_asof':True}})
            outputs=[]
            for number in range(2):
                out=root/str(number);out.mkdir()
                with contextlib.redirect_stdout(io.StringIO()):
                    worker.run({'spec':spec,'recipe':recipe,'output_dir':str(out),'split_path':str(root/'split.npz'),'threads':1})
                record=json.loads((out/'result.json').read_text())
                self.assertIn('__history_last_0',record['feature_names'])
                self.assertIn('__history_trend_0',record['feature_names'])
                self.assertEqual(record['early_stopping_source'],'inner_training_holdout')
                self.assertTrue(np.isfinite(pd.read_csv(out/'submission.csv').target).all())
                outputs.append((out/'submission.csv').read_bytes())
                train.loc[200:,'target']=100000.;train.to_csv(spec['paths']['train'],index=False)
            self.assertEqual(outputs[0],outputs[1])

    def test_real_full_fit_has_history_features_and_valid_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);spec,_=fixture(root);out=root/'full';out.mkdir()
            recipe=normalize({'engine':'lightgbm','params':{'iterations':30,'target_encoding':True,
                'target_encoding_groups':[['segment','measure']],'history_asof':True}})
            with contextlib.redirect_stdout(io.StringIO()):
                worker.run({'spec':spec,'recipe':recipe,'output_dir':str(out),'split_path':str(root/'split.npz'),'threads':1,'full_fit':True})
            record=json.loads((out/'result.json').read_text())
            self.assertEqual(record['early_stopping_source'],'full_refit')
            self.assertIn('__history_last_0',record['feature_names'])
            self.assertEqual(len(pd.read_csv(out/'submission.csv')),12)

    def test_unsupported_worker_kind_and_engine_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);spec,_=fixture(root)
            params={'history_asof':True,'target_encoding':True,'target_encoding_groups':[['segment','measure']]}
            for engine,kind in [('lightgbm','classification'),('linear_text','regression')]:
                invalid=dict(spec,kind=kind)
                job={'spec':invalid,'recipe':{'engine':engine,'params':params},
                     'output_dir':str(root/'invalid'),'split_path':str(root/'split.npz'),'threads':1}
                with self.subTest(engine=engine,kind=kind),self.assertRaises(ValueError):worker.run(job)


if __name__=='__main__':unittest.main(verbosity=2)
