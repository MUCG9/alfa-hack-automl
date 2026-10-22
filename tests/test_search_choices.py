"""Evidence-backed portfolio changes remain optional and task-specific."""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from automl.search.policy import portfolio,signature


class SearchChoiceTests(unittest.TestCase):
    def spec(self,kind='classification',metric='macro_f1'):
        return {'kind':kind,'metric':metric,'text_features':[]}

    def test_macro_f1_keeps_both_xgboost_control_and_calibration(self):
        candidates=[r for r in portfolio(self.spec()) if r['engine']=='xgboost']
        self.assertEqual(len(candidates),2)
        first,second=candidates; params=dict(second['params']); self.assertTrue(params.pop('calibrate'))
        self.assertEqual(params,first['params']); self.assertEqual(first['feature_code'],second['feature_code'])
        self.assertNotEqual(signature(first),signature(second))

    def test_other_classification_metrics_do_not_add_an_ignored_trial(self):
        for metric in ['roc_auc','log_loss','accuracy','balanced_accuracy','weighted_f1']:
            candidates=[r for r in portfolio(self.spec(metric=metric)) if r['engine']=='xgboost']
            self.assertEqual(len(candidates),1); self.assertFalse(candidates[0]['params'].get('calibrate',False))

    def test_regression_portfolio_is_not_changed_by_class_calibration(self):
        candidates=portfolio(self.spec('regression','rmse'))
        self.assertEqual(len(candidates),6)
        self.assertEqual([r['engine'] for r in candidates],['lightgbm','lightgbm','xgboost','catboost','xgboost','xgboost'])
        self.assertTrue(all(not r['params'].get('calibrate') for r in candidates))

    def test_optional_trial_has_independent_parameter_state(self):
        candidates=[r for r in portfolio(self.spec()) if r['engine']=='xgboost']
        candidates[1]['params']['class_weight_power']=1.
        self.assertEqual(candidates[0]['params']['class_weight_power'],.5)


if __name__=='__main__': unittest.main(verbosity=2)
