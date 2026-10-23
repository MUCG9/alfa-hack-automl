"""Reject repeated/semantically incompatible DSL expressions before execution."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from propose_residual_features import validate
from benchmark_feature_hpo import feature_only
from verify_feature_hpo import feature_contract


class ResidualFeatureTests(unittest.TestCase):
    def test_negative_expression_and_time_scales_are_rejected(self):
        old=[{'op':'signed_log','columns':['area']}]
        for feature in [old[0],{'op':'difference','columns':['Year_Factor','year_built']}]:
            with self.assertRaises(ValueError):validate([feature],['area','Year_Factor','year_built'],['area'],old)

    def test_direction_units_and_small_feature_cap(self):
        with self.assertRaises(ValueError):validate([{'op':'angle_delta','columns':['area','heat']}],['area','heat'],['area','heat'],[])
        code=validate([{'op':'ratio','columns':['area','heat']}],['area','heat'],['area','heat'],[])
        self.assertIn('np.where',code)
        with self.assertRaises(ValueError):validate([{'op':'missing','columns':['area']}]*5,['area'],['area'],[])

    def test_feature_intervention_cannot_change_model_or_target_policy(self):
        base={'engine':'lightgbm','params':{'log_target':True},'feature_code':'','hypothesis':'old'}
        candidate=dict(base,feature_code='def transform(df): return df.copy()',hypothesis='new')
        for check in [feature_only,feature_contract]:
            check(base,candidate)
            for bad in [dict(candidate,params={'log_target':False}),dict(candidate,engine='catboost')]:
                with self.assertRaises(ValueError):check(base,bad)


if __name__=='__main__':unittest.main()
