"""Input-role and delimiter robustness without network or public datasets."""
from pathlib import Path
import sys,tempfile,unittest
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from automl.task_understanding.api import discover
from automl.task_understanding.inputs import resolve_inputs
from automl.infrastructure.tables import read_input_table


class TaskInputTests(unittest.TestCase):
    def make_task(self,root,names=('train.csv','test.csv','sample_submission.csv','data_dictionary.csv'),delimiter=',',dictionary=True):
        n=100
        train=pd.DataFrame({'record':range(n),'x':np.arange(n)*.1,'answer':np.arange(n)*2.+1})
        test=pd.DataFrame({'record':[500,501,502],'x':[1.,2.,3.]})
        sample=pd.DataFrame({'record':test.record,'answer':0.})
        schema=pd.DataFrame({'feature':train.columns,'role':['id','feature','target']})
        for frame,name in zip([train,test,sample,schema],names):
            if not dictionary and name==names[-1]: continue
            path=root/name; path.parent.mkdir(parents=True,exist_ok=True)
            frame.to_csv(path,index=False,sep=delimiter)
        text='Regression. Primary metric: RMSE. Files: '+' '.join(names[:4 if dictionary else 3])
        (root/'task.md').write_text(text)
        return root/'task.md'

    def test_canonical_roles_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path=self.make_task(Path(directory)); spec,*_=discover(path)
            self.assertEqual(spec['features'],['x']); self.assertEqual(spec['target'],'answer')
            self.assertEqual(set(spec['paths']),{'train','test','sample_submission','data_dictionary'})

    def test_alternate_names_and_missing_dictionary(self):
        for dictionary in [False,True]:
            with tempfile.TemporaryDirectory() as directory:
                path=self.make_task(Path(directory),('fitting.csv','evaluation.csv','example.csv','schema.csv'),dictionary=dictionary)
                spec,profile,*_=discover(path)
                self.assertEqual(spec['target'],'answer'); self.assertEqual(spec['id'],'record')
                self.assertEqual(spec['features'],['x']); self.assertEqual('data_dictionary' in spec['paths'],dictionary)

    def test_tsv_and_semicolon_csv_reach_the_same_schema(self):
        for names,delimiter in [(('train.tsv','test.tsv','sample.tsv','schema.tsv'),'\t'),(('train.csv','test.csv','sample_submission.csv','schema.csv'),';')]:
            with tempfile.TemporaryDirectory() as directory:
                path=self.make_task(Path(directory),names,delimiter)
                spec,_,train,test,*_=discover(path)
                self.assertEqual(spec['n_features'],1); self.assertEqual(train.answer.iloc[-1],199.)
                self.assertEqual(test.record.tolist(),[500,501,502])

    def test_documented_nested_path_wins_over_other_folders(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path=self.make_task(root,tuple('actual/'+n for n in ('train.csv','test.csv','sample_submission.csv','data_dictionary.csv')))
            other=root/'backup'; other.mkdir(); pd.DataFrame({'bad':[1]}).to_csv(other/'train.csv',index=False)
            path.write_text('Regression. RMSE. '+ ' '.join('`actual/'+n+'`' for n in ('train.csv','test.csv','sample_submission.csv','data_dictionary.csv')))
            self.assertEqual(Path(discover(path)[0]['paths']['train']),root/'actual/train.csv')

    def test_ambiguous_aliases_are_not_guessed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); self.make_task(root,('fitting.csv','evaluation.csv','example.csv','schema.csv'))
            pd.DataFrame({'x':[1]}).to_csv(root/'training.csv',index=False)
            with self.assertRaisesRegex(ValueError,'Ambiguous'):
                resolve_inputs(root,'Regression. RMSE.')

    def test_symlink_outside_task_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory); root=base/'task'; root.mkdir()
            (base/'outside.csv').write_text('x\n1\n'); (root/'train.csv').symlink_to(base/'outside.csv')
            with self.assertRaisesRegex(ValueError,'leaves task directory'):
                resolve_inputs(root,'train.csv')

    def test_duplicate_headers_are_rejected_before_pandas_mangling(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'train.csv'; path.write_text('x,x\n1,2\n')
            with self.assertRaisesRegex(ValueError,'Duplicate input column'):
                read_input_table(path)

    def test_partial_probe_does_not_change_semicolon_separator(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'train.csv'
            expected=pd.DataFrame({'first':range(1000),'second':['long variable cell '+str(i)*5 for i in range(1000)]})
            expected.to_csv(path,index=False,sep=';')
            pd.testing.assert_frame_equal(read_input_table(path),expected)


if __name__=='__main__': unittest.main(verbosity=2)
