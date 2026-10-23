"""Supported-class safety, rare-class exclusion, bounded learned factors."""
from pathlib import Path
import sys
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from joint_decision import fit_factors,safety,GRIDS
from verify_joint_calibration import audit_selection
from copy import deepcopy


class JointDecisionTests(unittest.TestCase):
    def test_supported_class_loss_and_rarest_only_gain_are_refused(self):
        self.assertFalse(safety([.5,.5,.5],[.7,.48,.5],[5,200,200])['passed'])
        self.assertFalse(safety([.5,.5,.5],[.7,.5,.5],[5,200,200])['passed'])
        self.assertTrue(safety([.5,.5,.5],[.5,.51,.51],[5,200,200])['passed'])

    def test_no_gain_preserves_identity_and_every_tested_factor_is_bounded(self):
        truth=np.array(['a','b','c']*10);probs=np.eye(3)[np.tile(np.arange(3),10)]*.8+.2/3
        result=fit_factors(truth,probs,['a','b','c'],{'a':5,'b':200,'c':200},'JOINT_NARROW')
        self.assertEqual(result['status'],'identity');self.assertEqual(list(result['factors'].values()),[1.,1.,1.])
        self.assertTrue(all(t['factor'] in GRIDS['JOINT_NARROW'] for s in result['history'] for t in s['candidates']))
        self.assertEqual(len(result['history']),3)

    def test_probability_schema_and_group_support_are_required(self):
        with self.assertRaises(ValueError):fit_factors(['a'],[[.2,.2]],['a','b'],{'a':1,'b':2},'JOINT_TIGHT')
        with self.assertRaises(ValueError):fit_factors(['a'],[[.5,.5]],['a','b'],{'a':1},'JOINT_TIGHT')

    def test_independent_trace_audit_refuses_changed_inner_metrics(self):
        classes=['a','b','c'];truth=np.array(classes*5);probs=np.eye(3)[np.tile(np.arange(3),5)]*.8+.2/3
        support={'a':5,'b':200,'c':200};spec={'kind':'classification','metric':'macro_f1','greater_is_better':True,'classes':classes}
        selection=fit_factors(truth,probs,classes,support,'JOINT_TIGHT')
        self.assertEqual(audit_selection(selection,truth,probs,classes,support,spec,GRIDS['JOINT_TIGHT'])['status'],'verified')
        tampered=deepcopy(selection);tampered['history'][0]['candidates'][0]['per_class_f1']['a']=0.
        with self.assertRaises(ValueError):audit_selection(tampered,truth,probs,classes,support,spec,GRIDS['JOINT_TIGHT'])


if __name__=='__main__':unittest.main()
