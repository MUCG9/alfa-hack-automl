"""Semantic groups and chronological evaluation, separate from legacy hash splits."""
from pathlib import Path
import sys,unittest
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from automl.task_understanding.service import infer_time_candidate
from automl.infrastructure.observation_time import observation_values
from automl.evaluation.api import make_split,make_folds,make_time_split,choose_validation


class ValidationContractTests(unittest.TestCase):
    def data(self):
        train=pd.DataFrame({'client':np.repeat(np.arange(20),10),'x':np.arange(200)*.1,'y':np.tile(['a','b'],100)})
        spec={'kind':'classification','target':'y','id':'row','features':['client','x'],
              'metric':'macro_f1','classes':['a','b'],'duplicate_feature_rate':0.,
              'group_candidate':{'column':'client'}}
        hashes=pd.util.hash_pandas_object(train[spec['features']],index=False).to_numpy(dtype='uint64')
        return spec,train,hashes

    def test_semantic_group_outer_and_inner_never_overlap(self):
        spec,train,hashes=self.data(); spec=choose_validation(spec,train)
        for seed in [42,43]:
            tr,va,info=make_split(spec,train,hashes,seed)
            self.assertFalse(set(train.client.iloc[tr])&set(train.client.iloc[va]))
            self.assertEqual(info['shared_semantic_groups'],0)
            inner=train.iloc[tr].reset_index(drop=True)
            a,b,_=make_split(spec,inner,hashes[tr],73)
            self.assertFalse(set(inner.client.iloc[a])&set(inner.client.iloc[b]))

    def test_semantic_group_cv_has_unique_coverage(self):
        spec,train,hashes=self.data(); spec=choose_validation(spec,train)
        coverage=np.zeros(len(train),dtype=int)
        for tr,va,_ in make_folds(spec,train,hashes,3):
            coverage[va]+=1; self.assertFalse(set(train.client.iloc[tr])&set(train.client.iloc[va]))
        self.assertTrue(np.all(coverage==1))

    def test_rare_group_retains_training_class_without_rowwise_fallback(self):
        spec,train,hashes=self.data(); train['y']='a'; train.loc[train.client==0,'y']='b'
        spec=choose_validation(spec,train)
        tr,va,info=make_split(spec,train,hashes)
        self.assertEqual(set(train.y.iloc[tr]),{'a','b'})
        self.assertNotIn(0,set(train.client.iloc[va])); self.assertEqual(info['shared_semantic_groups'],0)

    def test_impossible_group_split_fails_instead_of_leaking(self):
        spec,train,hashes=self.data(); train.client=np.repeat([0,1],100); train.y=np.repeat(['a','b'],100)
        spec=choose_validation(spec,train)
        with self.assertRaisesRegex(ValueError,'row-wise fallback is forbidden'):
            make_split(spec,train,hashes)

    def test_legacy_mode_explicitly_disables_semantic_group_hint(self):
        spec,train,hashes=self.data(); legacy=choose_validation(spec,train,'legacy')
        tr,va,info=make_split(legacy,train,hashes)
        self.assertEqual(legacy['validation_strategy'],'legacy')
        self.assertNotEqual(info['method'],'explicit_semantic_group_holdout')
        self.assertTrue(set(train.client.iloc[tr])&set(train.client.iloc[va]))

    def test_missing_group_values_are_not_invented(self):
        spec,train,_=self.data(); train.loc[0,'client']=np.nan
        with self.assertRaisesRegex(ValueError,'complete non-target'):
            choose_validation(spec,train)

    def test_iso_dates_get_forward_blocks_not_single_row_validation(self):
        train=pd.DataFrame({'when':pd.date_range('2024-01-01',periods=200).astype(str),'y':np.arange(200)})
        spec={'kind':'regression','target':'y','features':['when'],'time_column':'when','validation_strategy':'time'}
        for offset in [0,1]:
            tr,va,info=make_time_split(spec,train,offset)
            self.assertEqual(len(va),40)
            self.assertLess(train.when.iloc[tr].max(),train.when.iloc[va].min())
            self.assertEqual(info['excluded_future_rows'],offset*40)
            self.assertEqual(info['method'],'forward_chronological_block')

    def test_numeric_period_backtests_keep_the_original_partition(self):
        train=pd.DataFrame({'period':np.repeat(np.arange(1,6),10),'y':np.arange(50)})
        spec={'kind':'regression','target':'y','features':['period'],'time_column':'period'}
        tr,va,info=make_time_split(spec,train)
        self.assertEqual(tr.tolist(),list(range(40))); self.assertEqual(va.tolist(),list(range(40,50)))
        self.assertEqual(info['method'],'forward_observation_period')

    def test_dictionary_dates_detect_future_without_confusing_construction(self):
        train=pd.DataFrame({'observed':pd.date_range('2024-01-01',periods=200).astype(str),'built':np.arange(200)+1800})
        test=pd.DataFrame({'observed':pd.date_range('2025-01-01',periods=20).astype(str),'built':np.arange(20)+2100})
        dictionary=pd.DataFrame({'feature':['observed','built'],'description':['Observation date','Construction year']})
        hint=infer_time_candidate(dictionary,train,test,list(train.columns))
        self.assertEqual(hint['column'],'observed'); self.assertEqual(hint['representation'],'datetime')
        self.assertEqual(hint['split_mode'],'chronological_block')

    def test_high_cardinality_numeric_timestamps_use_blocks(self):
        train=pd.DataFrame({'timestamp':np.arange(200)}); test=pd.DataFrame({'timestamp':np.arange(200,220)})
        dictionary=pd.DataFrame({'feature':['timestamp'],'description':['Observation timestamp']})
        hint=infer_time_candidate(dictionary,train,test,['timestamp'])
        self.assertEqual(hint['representation'],'numeric'); self.assertEqual(hint['split_mode'],'chronological_block')

    def test_bad_dates_fail_and_timezone_dates_share_a_representation(self):
        with self.assertRaises(ValueError): observation_values(pd.Series(['2024-01-01','not a date']))
        values,kind=observation_values(pd.Series(['2024-01-01T03:00:00+03:00','2024-01-01T00:00:00Z']))
        self.assertEqual(kind,'datetime'); self.assertEqual(values.iloc[0],values.iloc[1])

    def test_joint_time_group_limitation_is_disclosed(self):
        spec,train,_=self.data(); train['period']=np.repeat(np.arange(1,6),40)
        spec['features'].append('period'); spec['time_candidate']={'column':'period'}
        result=choose_validation(spec,train)
        self.assertEqual(result['validation_strategy'],'time')
        self.assertIn('joint unseen-group/forward validation is not implemented',result['validation_warning'])


if __name__=='__main__': unittest.main(verbosity=2)
