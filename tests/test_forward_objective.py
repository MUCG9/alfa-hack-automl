"""Nested temporal prefixes/aggregation must never depend on outer labels."""
from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from benchmark_forward_objective import forward_folds,aggregate


class ForwardObjectiveTests(unittest.TestCase):
    def test_inner_periods_are_inside_fitting_prefix_and_ignore_outer_label_poisoning(self):
        train=pd.DataFrame({'period':np.repeat([1,2,3,4,5],3),'x':np.arange(15),'y':np.arange(15,dtype=float)})
        spec={'kind':'regression','features':['period','x'],'target':'y','validation_strategy':'time','time_column':'period'}
        outer=np.arange(12);groups=np.arange(15,dtype='uint64')
        left,_=forward_folds(spec,train,groups,outer);poison=train.copy();poison.loc[12:,'y']=1e30
        right,_=forward_folds(spec,poison,groups,outer)
        self.assertEqual(len(left),2)
        for a,b in zip(left,right):
            self.assertTrue(np.array_equal(a[0],b[0]));self.assertTrue(np.array_equal(a[1],b[1]))
            self.assertTrue(set(a[0])|set(a[1])<=set(outer))
            self.assertLess(train.period.iloc[a[0]].max(),train.period.iloc[a[1]].min())

    def test_short_prefix_uses_only_available_period_and_reports_missing_fold(self):
        train=pd.DataFrame({'period':[1,1,2,2,3,3],'y':[1,2,3,4,5,6]})
        spec={'kind':'regression','features':['period'],'target':'y','validation_strategy':'time','time_column':'period'}
        folds,missing=forward_folds(spec,train,np.arange(6,dtype='uint64'),np.arange(4))
        self.assertEqual(len(folds),1);self.assertEqual(missing[0]['offset'],1)
        with self.assertRaises(ValueError):forward_folds(spec,train,np.arange(6,dtype='uint64'),np.arange(2))

    def test_mean_and_worst_are_fold_aggregates_not_pooled_predictions(self):
        self.assertEqual(aggregate([3.,5.],'FORWARD_MEAN'),4.)
        self.assertEqual(aggregate([3.,5.],'FORWARD_WORST'),5.)
        for values in [[],[np.inf],[np.nan]]:
            with self.assertRaises(ValueError):aggregate(values,'FORWARD_MEAN')
        with self.assertRaises(ValueError):aggregate([1.],'unknown')


if __name__=='__main__':unittest.main()
