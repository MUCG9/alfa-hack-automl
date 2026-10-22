"""Output identity and row alignment, including cached ensemble input order."""
from pathlib import Path
import sys,tempfile,unittest
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from automl.task_understanding.api import discover
from automl.publishing.api import save_submission,read_submission_values
from automl.execution.api import read_cache,combine
from automl.contracts.messages import TaskSpec


class OutputContractTests(unittest.TestCase):
    def task(self,root,no_id=False,reorder=False):
        train=pd.DataFrame({'key':range(100),'x':np.arange(100)*.1,'y':np.arange(100)+1.})
        test=pd.DataFrame({'key':[503,501,502],'x':[3.,1.,2.]})
        sample=pd.DataFrame({'key':test.key,'prediction':[0.]*3})
        if reorder: sample=sample.iloc[[2,0,1]].reset_index(drop=True)
        if no_id: sample=sample[['prediction']]
        for name,frame in [('train',train),('test',test),('sample_submission',sample),('data_dictionary',pd.DataFrame({'feature':train.columns,'role':['id','feature','target']}))]:
            frame.to_csv(root/(name+'.csv'),index=False)
        path=root/'task.md'; path.write_text('Regression. Metric RMSE. train.csv test.csv sample_submission.csv data_dictionary.csv')
        return discover(path)

    def test_no_id_output_uses_row_order_without_adding_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); spec,_,_,test,sample,*_=self.task(root,no_id=True)
            self.assertIsNone(spec['id']); self.assertEqual(spec['features'],['x'])
            TaskSpec.from_legacy(spec)
            save_submission(spec,sample,test,[30.,10.,20.],root/'out.csv')
            actual=pd.read_csv(root/'out.csv')
            self.assertEqual(actual.columns.tolist(),['prediction']); self.assertEqual(actual.prediction.tolist(),[30,10,20])

    def test_reordered_sample_is_aligned_by_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); spec,_,_,test,sample,*_=self.task(root,reorder=True)
            self.assertEqual(spec['sample_test_positions'],[2,0,1])
            save_submission(spec,sample,test,[30.,10.,20.],root/'out.csv')
            actual=pd.read_csv(root/'out.csv')
            self.assertEqual(actual.key.tolist(),sample.key.tolist()); self.assertEqual(actual.prediction.tolist(),[20,30,10])
            self.assertEqual(read_submission_values(spec,root/'out.csv').tolist(),[30,10,20])

    def test_probability_matrices_keep_rows_and_class_column_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            spec={'id':'key','target':'y','kind':'classification','classes':['a','b'],'prediction_type':'probability_matrix','output_columns':['b','a'],'sample_test_positions':[2,0,1]}
            test=pd.DataFrame({'key':[10,11,12]}); sample=pd.DataFrame({'key':[12,10,11],'b':0.,'a':0.})
            values=np.array([[.8,.2],[.3,.7],[.4,.6]])
            save_submission(spec,sample,test,values,root/'out.csv')
            self.assertTrue(np.allclose(pd.read_csv(root/'out.csv')[['b','a']],values[[2,0,1]]))
            self.assertTrue(np.allclose(read_submission_values(spec,root/'out.csv'),values))

    def test_invalid_mapping_and_unmatched_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); spec,_,_,test,sample,*_=self.task(root)
            for mapping in [[0,0,2],[0,1,3],[0.,1.,2.],[0,1]]:
                with self.assertRaises(ValueError): save_submission(dict(spec,sample_test_positions=mapping),sample,test,[1,2,3],root/'bad.csv')
            sample.loc[0,'key']=999; sample.to_csv(root/'sample_submission.csv',index=False)
            with self.assertRaisesRegex(ValueError,'ID values differ'): discover(root/'task.md')

    def test_duplicate_sample_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); spec,_,_,test,sample,*_=self.task(root)
            sample.loc[0,'key']=sample.loc[1,'key']; sample.to_csv(root/'sample_submission.csv',index=False)
            with self.assertRaisesRegex(ValueError,'Sample IDs'): discover(root/'task.md')

    def test_cached_regression_blend_does_not_apply_permutation_twice(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); spec,_,train,test,sample,*_=self.task(root,reorder=True)
            caches=[]
            for number,predictions in enumerate([[30.,10.,20.],[60.,20.,40.]]):
                folder=root/str(number); folder.mkdir()
                save_submission(spec,sample,test,predictions,folder/'submission.csv')
                pd.DataFrame({'row_position':[0,1],'y_pred':[1.,2.]}).to_csv(folder/'validation_predictions.csv',index=False)
                caches.append(read_cache(spec,{'submission':str(folder/'submission.csv')},train))
            _,_,test_values,_=combine(spec,caches,[.5,.5])
            self.assertTrue(np.allclose(test_values,[45,15,30]))
            save_submission(spec,sample,test,test_values,root/'blend.csv')
            self.assertEqual(pd.read_csv(root/'blend.csv').prediction.tolist(),[30,45,15])


if __name__=='__main__': unittest.main(verbosity=2)
