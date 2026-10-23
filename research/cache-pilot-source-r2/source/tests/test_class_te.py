"""Multiclass encoding isolation and real worker coverage for feature-view research."""
from pathlib import Path
import contextlib,io,json,sys,tempfile,unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'))
import numpy as np
import pandas as pd
from automl.execution.preprocessing.target_encoding import target_encode_frames
from automl.execution import worker
from agent_core import discover
from agent_policy import normalize


class MulticlassEncodingTests(unittest.TestCase):
    def test_own_feature_group_and_outer_labels_do_not_enter_encoding(self):
        rows=np.arange(24)
        group_index=np.arange(28)//2
        x=pd.DataFrame({'segment':np.asarray(['a','b','c','d'])[group_index%4],
                        'channel':np.asarray(['q','r'])[group_index%2],'measure':group_index})
        test=pd.DataFrame({'segment':['a','unseen'],'channel':['q','unseen'],'measure':[100,101]})
        y=pd.Series(np.tile(['Z','A','M','A'],7));classes=['Z','M','A']
        hashes=np.arange(28)//2
        original=x.copy(deep=True);original_test=test.copy(deep=True)
        options=dict(classes=classes,smoothing=20.,groups=[['segment','channel']])
        first,first_test=target_encode_frames(x,test,y,rows,hashes,**options)
        changed=y.copy();changed.iloc[24:]='held-out-poison'
        second,second_test=target_encode_frames(x,test,changed,rows,hashes,**options)
        pd.testing.assert_frame_equal(first,second);pd.testing.assert_frame_equal(first_test,second_test)
        changed=y.copy();changed.iloc[:2]='M'
        third,_=target_encode_frames(x,test,changed,rows,hashes,**options)
        columns=[c for c in first if c.startswith('__te_')]
        self.assertEqual(len(columns),9)
        np.testing.assert_array_equal(first.loc[:1,columns],third.loc[:1,columns])
        pd.testing.assert_frame_equal(x,original);pd.testing.assert_frame_equal(test,original_test)

    def test_unseen_context_prior_channels_follow_explicit_class_order(self):
        x=pd.DataFrame({'segment':['a']*4+['b']*4+['held']*2,
                        'channel':['q']*4+['r']*4+['held']*2,'measure':np.arange(10)})
        y=pd.Series(['Z','Z','Z','M','A','A','A','A','held-out','held-out'])
        test=pd.DataFrame({'segment':['unseen','a'],'channel':['unseen','r'],'measure':[100,101]})
        classes=['M','A','Z'];rows=np.arange(8)
        _,encoded=target_encode_frames(x,test,y,rows,np.arange(10),classes=classes,
                                        groups=[['segment','channel']],smoothing=20.)
        prior=np.array([1/8,4/8,3/8])
        for number in range(3):
            np.testing.assert_allclose(encoded.loc[0,[f'__te_{number}_{i}' for i in range(3)]].to_numpy(dtype=float),prior)
        np.testing.assert_allclose(encoded.loc[1,[f'__te_2_{i}' for i in range(3)]].to_numpy(dtype=float),prior)

    def test_real_calibrated_worker_keeps_outer_labels_out_of_pair_statistics(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);n=300
            train=pd.DataFrame({'record':np.arange(n),'measure':np.arange(n,dtype=float),
                                'segment':np.tile(['a','b','c'],100),
                                'channel':np.tile(['q','r'],150)})
            train['answer']=np.tile(['A','M','Z'],100)
            test=train.iloc[:12].drop(columns='answer').copy();test['record']+=1000
            train.to_csv(root/'train.csv',index=False);test.to_csv(root/'test.csv',index=False)
            pd.DataFrame({'record':test.record,'answer':'A'}).to_csv(root/'sample_submission.csv',index=False)
            pd.DataFrame({'feature':train.columns,'role':['id','feature','feature','feature','target']}).to_csv(root/'data_dictionary.csv',index=False)
            path=root/'task.md';path.write_text('Classification. Target: answer. Metric: Macro F1. train.csv test.csv data_dictionary.csv sample_submission.csv')
            spec,*_=discover(path);np.savez(root/'split.npz',train=np.arange(240),validation=np.arange(240,300))
            recipe=normalize({'engine':'lightgbm','params':{'iterations':30,'min_iterations':10,'num_leaves':7,
                'calibrate':True,'target_encoding':True,'target_encoding_groups':[['segment','channel']],
                'target_encoding_smoothing':20}})
            outputs=[]
            for number in range(2):
                out=root/str(number);out.mkdir()
                with contextlib.redirect_stdout(io.StringIO()):
                    worker.run({'spec':spec,'recipe':recipe,'output_dir':str(out),'split_path':str(root/'split.npz'),'threads':1})
                record=json.loads((out/'result.json').read_text())
                self.assertEqual(record['calibration_status'],'inner_training_holdout_matching_iterations')
                self.assertIn('__te_2_2',record['feature_names'])
                with np.load(out/'test_probabilities.npz') as stored:
                    self.assertEqual(stored['classes'].astype(str).tolist(),spec['classes'])
                    self.assertTrue(np.isfinite(stored['probabilities']).all())
                    np.testing.assert_allclose(stored['probabilities'].sum(axis=1),1)
                outputs.append((out/'submission.csv').read_bytes())
                train.loc[240:,'answer']=np.tile(['M','Z','A'],20)
                train.to_csv(spec['paths']['train'],index=False)
            self.assertEqual(outputs[0],outputs[1])


if __name__=='__main__':unittest.main(verbosity=2)
