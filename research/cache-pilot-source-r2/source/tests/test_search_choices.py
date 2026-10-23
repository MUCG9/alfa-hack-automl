"""Evidence-backed portfolio changes remain optional and task-specific."""
from pathlib import Path
from copy import deepcopy
import sys,unittest
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from automl.search.policy import portfolio,signature,normalize


class SearchChoiceTests(unittest.TestCase):
    def spec(self,kind='classification',metric='macro_f1'):
        return {'kind':kind,'metric':metric,'text_features':[]}

    def history_spec(self):
        return dict(self.spec('regression','rmse'),validation_strategy='time',time_column='period',
                    time_candidate={'representation':'numeric','split_mode':'period'},static_numeric_features=['built'])

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

    def test_asof_history_is_one_three_period_clone_immediately_after_semantic(self):
        candidates=portfolio(self.history_spec())
        indices=[i for i,r in enumerate(candidates) if r['params'].get('history_asof')]
        self.assertEqual(indices,[3])
        semantic,asof=candidates[2:4]
        self.assertTrue(semantic['params']['target_encoding_hierarchical'])
        params=dict(asof['params'])
        self.assertIs(params.pop('history_asof'),True)
        self.assertEqual(params.pop('history_min_periods'),3)
        self.assertEqual(params,semantic['params'])
        self.assertTrue(params['log_target']); self.assertEqual(params['target_encoding_smoothing'],2.)
        self.assertEqual(asof['engine'],semantic['engine'])
        self.assertEqual(asof['feature_code'],semantic['feature_code'])
        self.assertNotEqual(signature(asof),signature(semantic))

    def test_asof_history_eligibility_excludes_other_tasks_and_time_representations(self):
        cases=[{'validation_strategy':'group'}, {'static_numeric_features':[]},
               {'static_numeric_features':None}, {'time_candidate':{'representation':'datetime','split_mode':'period'}},
               {'time_candidate':{'representation':'numeric','split_mode':'continuous'}},
               {'kind':'classification','metric':'macro_f1'}, {'task_family':'pointwise_ranking'},
               {'text_features':['review']}]
        for change in cases:
            spec=dict(self.history_spec(),**change)
            with self.subTest(change=change):
                self.assertFalse(any(r['params'].get('history_asof') for r in portfolio(spec)))
        legacy_numeric=self.history_spec(); legacy_numeric.pop('time_candidate')
        self.assertEqual(sum(bool(r['params'].get('history_asof')) for r in portfolio(legacy_numeric)),1)

    def test_asof_preserves_existing_recipe_values_order_and_class_text_policies(self):
        spec=self.history_spec(); candidates=portfolio(spec)
        old_time=portfolio(dict(spec,static_numeric_features=[]))
        semantic=normalize(dict(old_time[1],params=dict(old_time[1]['params'],target_encoding_hierarchical=True),
                                hypothesis='Refine recurring contexts with categorical attributes and schema-described static properties'))
        expected=old_time[:2]+[semantic]+old_time[2:]
        self.assertEqual([r for r in candidates if not r['params'].get('history_asof')],expected)
        self.assertEqual(candidates[5:],portfolio(self.spec('regression','rmse')))
        self.assertEqual(portfolio(dict(spec,task_family='pointwise_ranking')),expected)
        for metric in ['macro_f1','roc_auc','log_loss','accuracy']:
            plain=self.spec(metric=metric)
            self.assertEqual(portfolio(dict(spec,**plain)),portfolio(plain))
        for kind,metric in [('classification','macro_f1'),('regression','rmse')]:
            plain=dict(self.spec(kind,metric),text_features=['review'])
            self.assertEqual(portfolio(dict(spec,**plain)),portfolio(plain))

    def test_asof_clone_and_portfolio_calls_have_independent_parameter_state(self):
        spec=self.history_spec(); candidates=portfolio(spec); original=deepcopy(candidates)
        asof=candidates[3]
        for number,recipe in enumerate(candidates):
            if number!=3: self.assertIsNot(asof['params'],recipe['params'])
        asof['params']['target_encoding_smoothing']=99.
        asof['params']['num_leaves']=1
        asof['feature_code']='train_x["added"]=1'
        self.assertEqual(candidates[:3]+candidates[4:],original[:3]+original[4:])
        candidates[2]['params']['target_encoding_hierarchical']=False
        self.assertIs(asof['params']['target_encoding_hierarchical'],True)
        self.assertEqual(portfolio(spec),original)


if __name__=='__main__': unittest.main(verbosity=2)
