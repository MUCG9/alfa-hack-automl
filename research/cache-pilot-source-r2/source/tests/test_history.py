"""Causal contracts for fitting-only, strictly earlier-period regression history."""
from pathlib import Path
import sys,unittest
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from automl.execution.preprocessing.history import add_history_features


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.train=pd.DataFrame({'period':[1.,1.,3.,3.,6.,6.,10.,10.],
                                 'segment':['a']*8,'size':[7]*8},index=[40,10,80,30,90,20,70,60])
        self.test=pd.DataFrame({'period':[0.,1.,2.,3.,4.,6.,7.,10.],
                                'segment':['a']*8,'size':[7]*8},index=[9,8,7,6,5,4,3,2])
        self.y=pd.Series([2.,6.,10.,14.,28.,32.,1000.,2000.],index=self.train.index)
        self.rows=np.array([5,0,2,1,4,3])
        self.groups=[['segment','size']]

    def run_history(self,train=None,test=None,y=None,rows=None,groups=None):
        return add_history_features(self.train if train is None else train,self.test if test is None else test,
                                    self.y if y is None else y,self.rows if rows is None else rows,'period',
                                    self.groups if groups is None else groups)

    def test_duplicate_period_means_and_nonuniform_period_trends(self):
        train,test=self.run_history()
        np.testing.assert_allclose(train['__history_last_0'],[np.nan,np.nan,4,4,12,12,30,30],equal_nan=True)
        np.testing.assert_allclose(train['__history_trend_0'],[np.nan,np.nan,np.nan,np.nan,4,4,6,6],equal_nan=True)
        np.testing.assert_allclose(test['__history_last_0'],[np.nan,np.nan,4,4,12,12,30,30],equal_nan=True)
        np.testing.assert_allclose(test['__history_trend_0'],[np.nan,np.nan,np.nan,np.nan,4,4,6,6],equal_nan=True)

    def test_same_period_and_future_fitting_labels_do_not_change_earlier_features(self):
        original_train,original_test=self.run_history()
        for period,positions in [(3,[2,3]),(6,[4,5])]:
            changed=self.y.copy(); changed.iloc[positions]=[10000.,20000.]
            train,test=self.run_history(y=changed)
            pd.testing.assert_frame_equal(original_train.loc[self.train.period<=period],train.loc[self.train.period<=period])
            pd.testing.assert_frame_equal(original_test.loc[self.test.period<=period],test.loc[self.test.period<=period])
            later_position=6 if period==6 else 4
            self.assertNotEqual(original_test['__history_last_0'].iloc[later_position],test['__history_last_0'].iloc[later_position])

    def test_only_selected_fitting_targets_are_read_and_raw_scale_is_preserved(self):
        class FittingTargetsOnly:
            def __len__(inner): return len(self.y)
            def __getitem__(inner,position):
                self.assertIn(position,set(self.rows))
                return self.y.iloc[position]
        first=self.run_history()
        guarded=self.run_history(y=FittingTargetsOnly())
        for expected,actual in zip(first,guarded): pd.testing.assert_frame_equal(expected,actual)
        changed=self.y.astype(object); changed.iloc[[6,7]]=['held-out target',object()]
        for expected,actual in zip(first,self.run_history(y=changed)):
            pd.testing.assert_frame_equal(expected,actual)
        self.assertEqual(first[1]['__history_last_0'].iloc[-1],30.)

    def test_a_smaller_inner_fit_rebuilds_history(self):
        _,test=self.run_history(rows=np.array([0,1]))
        np.testing.assert_allclose(test['__history_last_0'],[np.nan,np.nan,4,4,4,4,4,4],equal_nan=True)
        self.assertTrue(test['__history_trend_0'].isna().all())

    def test_contexts_with_missing_values_categories_and_unseen_values(self):
        train=pd.DataFrame({'period':[1.,1.,2.,2.,1.,2.],
                            'segment':pd.Categorical([None,'__MISSING__',None,'__MISSING__','b','b']),
                            'size':pd.Series([np.nan,np.nan,np.nan,np.nan,2.,2.],dtype='Float64')})
        test=pd.DataFrame({'period':[3.,3.,3.,3.,3.],
                           'segment':pd.Categorical([None,'__MISSING__','b','unseen','b']),
                           'size':pd.Series([np.nan,np.nan,2.,2.,np.nan],dtype='Float64')})
        _,output=add_history_features(train,test,pd.Series([2.,10.,4.,14.,20.,26.]),np.arange(6),'period',self.groups)
        np.testing.assert_allclose(output['__history_last_0'],[4,14,26,np.nan,np.nan],equal_nan=True)
        np.testing.assert_allclose(output['__history_trend_0'],[2,4,6,np.nan,np.nan],equal_nan=True)

    def test_independent_groups_use_only_their_matching_context(self):
        train=self.train.copy(); test=self.test.copy()
        train['segment']=['a','b']*4
        test['segment']=['a','b']*4
        _,output=self.run_history(train=train,test=test,groups=[['segment'],['size']])
        self.assertEqual(output['__history_last_0'].iloc[-2],28.)
        self.assertEqual(output['__history_last_0'].iloc[-1],32.)
        self.assertEqual(output['__history_last_1'].iloc[-2],30.)
        self.assertEqual(output['__history_last_1'].iloc[-1],30.)
        self.assertEqual(list(output.columns[-4:]),['__history_last_0','__history_trend_0','__history_last_1','__history_trend_1'])

    def test_nonfinite_and_nonnumeric_query_times_have_no_history(self):
        train=self.train.copy(); test=self.test.copy()
        train.iloc[6,train.columns.get_loc('period')]=np.nan
        test['period']=pd.Series([np.nan,np.inf,-np.inf,'unknown',4.,6.,7.,10.],index=test.index)
        output,query=self.run_history(train=train,test=test)
        self.assertTrue(output.filter(like='__history_').iloc[6].isna().all())
        self.assertTrue(query.filter(like='__history_').iloc[:4].isna().all().all())
        self.assertEqual(query['__history_last_0'].iloc[4],12.)

    def test_overflowing_trend_retains_last_value_and_uses_nan_instead_of_infinity(self):
        train=pd.DataFrame({'period':[0.,1e-300],'segment':['a','a']})
        test=pd.DataFrame({'period':[2e-300],'segment':['a']})
        with np.errstate(all='raise'):
            _,output=add_history_features(train,test,pd.Series([-1e300,1e300]),[0,1],'period',[['segment']])
        self.assertEqual(output['__history_last_0'].iloc[0],1e300)
        self.assertTrue(np.isnan(output['__history_trend_0'].iloc[0]))

    def test_renaming_and_duplicate_index_labels_preserve_positional_order_without_mutation(self):
        train=self.train.copy(); test=self.test.copy(); y=self.y.copy()
        train.index=[4,4,3,3,2,2,1,1]; y.index=train.index; test.index=[1]*len(test)
        before_train=train.copy(deep=True); before_test=test.copy(deep=True); before_y=y.copy(deep=True)
        first,second=self.run_history(train=train,test=test,y=y)
        pd.testing.assert_frame_equal(first[self.train.columns],before_train)
        pd.testing.assert_frame_equal(second[self.test.columns],before_test)
        pd.testing.assert_frame_equal(train,before_train); pd.testing.assert_frame_equal(test,before_test)
        pd.testing.assert_series_equal(y,before_y)
        mapping={'period':'observation_code','segment':'context_a','size':'context_b'}
        renamed=add_history_features(train.rename(columns=mapping),test.rename(columns=mapping),y,self.rows,
                                     'observation_code',[['context_a','context_b']])
        for expected,actual in zip([first,second],renamed):
            pd.testing.assert_frame_equal(expected.rename(columns=mapping),actual)

    def test_empty_groups_return_independent_copies_with_no_new_columns(self):
        train,test=self.run_history(groups=[])
        pd.testing.assert_frame_equal(train,self.train); pd.testing.assert_frame_equal(test,self.test)
        self.assertIsNot(train,self.train); self.assertIsNot(test,self.test)

    def test_feature_collisions_and_missing_columns_are_rejected_in_either_frame(self):
        for name in ['__history_last_0','__history_trend_0']:
            for frame in ['train','test']:
                changed=getattr(self,frame).copy(); changed[name]=0.
                with self.subTest(name=name,frame=frame),self.assertRaisesRegex(ValueError,'collision'):
                    self.run_history(**{frame:changed})
        for column in ['period','segment','size']:
            for frame in ['train','test']:
                with self.subTest(column=column,frame=frame),self.assertRaisesRegex(ValueError,'columns'):
                    self.run_history(**{frame:getattr(self,frame).drop(columns=column)})
        duplicate=self.train.copy(); duplicate.columns=['period','segment','segment']
        with self.assertRaisesRegex(ValueError,'unique input columns'): self.run_history(train=duplicate)

    def test_group_and_fitting_row_contracts(self):
        bad_groups=[None,(),[['segment']]*4,[[]],[['segment','segment']],[['period']],
                    [['segment'],['segment']],['segment'],[['segment']*7],[[object()]]]
        for groups in bad_groups:
            with self.subTest(groups=groups),self.assertRaises(ValueError):
                add_history_features(self.train,self.test,self.y,self.rows,'period',groups)
        for rows in [[],[0,0],[-1],[len(self.train)],[0.,1.],[[0,1]],[True,False]]:
            with self.subTest(rows=rows),self.assertRaisesRegex(ValueError,'fitting rows'):
                self.run_history(rows=rows)

    def test_target_alignment_and_nonfinite_fitting_values_fail(self):
        for target in [self.y.reset_index(drop=True),self.y.iloc[:-1],np.arange(7.),np.zeros((8,2)),self.y.to_frame()]:
            with self.subTest(target_type=type(target)),self.assertRaises(ValueError): self.run_history(y=target)
        for value in [np.nan,np.inf,-np.inf,'invalid']:
            changed=self.y.astype(object); changed.iloc[0]=value
            with self.subTest(target=value),self.assertRaisesRegex(ValueError,'fitting targets'):
                self.run_history(y=changed)
            changed_train=self.train.astype({'period':'object'}); changed_train.iloc[0,0]=value
            with self.subTest(period=value),self.assertRaisesRegex(ValueError,'fitting periods'):
                self.run_history(train=changed_train)


if __name__=='__main__': unittest.main(verbosity=2)
