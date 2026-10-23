"""Pinned optimizer and inner-forward contracts; fake objectives, no ML fits."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import time
import unittest
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import isolated_hpo as hpo


class IsolatedHPOTests(unittest.TestCase):
    def setUp(self):
        self.recipe={'engine':'lightgbm','feature_code':'','params':{'num_leaves':127,'reg_lambda':8.,'colsample_bytree':.9,'log_target':True,'seed':42}}

    def test_strict_metrics(self):
        for value in (True,False,None,'1',float('nan'),float('inf')):self.assertFalse(hpo.valid_metric(value))
        self.assertTrue(hpo.valid_metric(1.))

    def test_effective_anchor_not_clipped(self):
        self.assertEqual(hpo.effective_anchor(self.recipe),{'num_leaves':127,'reg_lambda':8.,'colsample_bytree':.9})
        recipe=deepcopy(self.recipe);recipe['params']['reg_lambda']=25
        with self.assertRaises(ValueError):hpo.effective_anchor(recipe)

    def test_forward_inside_outer_fitting(self):
        train=pd.DataFrame({'period':np.repeat(np.arange(1,7),5),'x':np.arange(30),'y':np.arange(30)})
        spec={'features':['period','x'],'kind':'regression','target':'y','time_column':'period'}
        fitting=np.arange(20)
        a,b,info=hpo.forward_inside(spec,train,np.arange(30),fitting)
        self.assertLess(train.period.iloc[a].max(),train.period.iloc[b].min())
        self.assertTrue(set(a)|set(b)<=set(fitting))
        self.assertEqual(info['scope'],'inside_outer_fitting_only')

    def test_bad_fitting_rows_rejected(self):
        train=pd.DataFrame({'period':[1,2,3],'x':[0,1,2]})
        for rows in ([0,0,1],[.1,1.],[-1,2]):
            with self.subTest(rows=rows),self.assertRaises(ValueError):hpo.forward_inside({},train,np.arange(3),rows)

    def test_real_tpe_guided_and_unchanged_other_params(self):
        calls=[]
        def fake(spec,recipe,out,split,timeout):
            calls.append(recipe)
            self.assertEqual(recipe['params']['log_target'],True)
            self.assertEqual(recipe['params']['seed'],42)
            self.assertLessEqual(timeout,60)
            return {'status':'ok','metrics':{'rmse':abs(recipe['params']['num_leaves']-90.)+1},'wall_seconds':0.,'fit_iterations':50,'data_policy_runs':[{},{}]}
        with tempfile.TemporaryDirectory() as tmp:
            result=hpo.optimize({},self.recipe,Path('not-read'),Path(tmp),fake,time.monotonic()+60,'tpe')
        self.assertEqual(len(calls),12)
        self.assertEqual(result['guided_successful'],9)
        self.assertTrue(result['anchor_valid'])

    def test_failed_anchor_stops_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=hpo.optimize({},self.recipe,Path('unused'),Path(tmp),lambda *a:{'status':'ok','metrics':{'rmse':True}},time.monotonic()+60,'random')
        self.assertEqual(result['attempted_trials'],1)
        self.assertFalse(result['anchor_valid'])
        self.assertIsNone(result['selected_recipe'])

    def test_expired_deadline_never_calls_worker(self):
        def no_call(*a):raise AssertionError('must not start')
        with tempfile.TemporaryDirectory() as tmp:
            result=hpo.optimize({},self.recipe,Path('unused'),Path(tmp),no_call,time.monotonic()-1,'tpe')
        self.assertEqual(result['attempted_trials'],0)
        self.assertEqual(result['unattempted_trials'],12)


if __name__=='__main__':unittest.main()
