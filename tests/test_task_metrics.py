"""Objective semantics, including exact alignment of search and inner callbacks."""
from pathlib import Path
import sys,unittest
import numpy as np
from sklearn.metrics import balanced_accuracy_score,mean_absolute_percentage_error,mean_squared_log_error
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from automl.task_understanding.api import metric_from_text
from automl.evaluation.api import evaluate,lgbm_metric


class TaskMetricTests(unittest.TestCase):
    def test_new_objectives_are_not_legacy_defaults(self):
        for text,kind,expected in [
            ('Regression. Metric MAPE (mean absolute percentage error).','regression','mape'),
            ('Regression. Metric: MSE.','regression','mse'),
            ('Regression. Metric RMSLE.','regression','rmsle'),
            ('Classification. Metric: balanced accuracy.','classification','balanced_accuracy'),
        ]:
            self.assertEqual(metric_from_text(text,kind),expected)

    def test_primary_overrides_earlier_diagnostics(self):
        self.assertEqual(metric_from_text('RMSE is diagnostic. Primary metric: MAPE; RMSE is secondary.','regression'),'mape')
        self.assertEqual(metric_from_text('Accuracy and Weighted F1 are diagnostic. Основная метрика — **Macro F1**.','classification'),'macro_f1')
        self.assertEqual(metric_from_text('Macro F1 is diagnostic. Primary metric: balanced accuracy.','classification'),'balanced_accuracy')

    def test_legacy_objectives_remain_supported(self):
        for kind,metrics in [('regression',['RMSE','MAE','R2']),('classification',['Macro F1','ROC AUC','Log loss','Weighted F1','Accuracy'])]:
            for metric in metrics:
                self.assertEqual(metric_from_text('Metric: '+metric,kind),metric.lower().replace(' ','_'))

    def test_unsupported_explicit_objective_is_not_silently_changed(self):
        with self.assertRaisesRegex(ValueError,'supported objective'):
            metric_from_text('Regression. Metric: pinball loss.','regression')
        with self.assertRaises(ValueError):
            metric_from_text('RMSE is diagnostic. Primary metric: pinball loss.','regression')
        self.assertEqual(metric_from_text('Regression. Predict demand.','regression'),'rmse')

    def test_regression_callbacks_match_outer_metrics_including_log_target(self):
        y=np.array([1.,2.,4.,8.]); pred=np.array([1.5,1.,5.,6.])
        for metric in ['rmse','mae','r2','mse','mape','rmsle']:
            expected=evaluate(y,pred,'regression',metric)[metric]
            spec={'kind':'regression','metric':metric,'greater_is_better':metric=='r2'}
            for logged in [False,True]:
                result=lgbm_metric(spec,logged)(np.log1p(y) if logged else y,np.log1p(pred) if logged else pred)
                self.assertAlmostEqual(result[1],expected)
                self.assertEqual(result[2],metric=='r2')

    def test_mape_matches_pinned_sklearn_zero_semantics(self):
        y=[0.,1.,2.]; pred=[.1,1.1,1.9]
        result=evaluate(y,pred,'regression','mape')['mape']
        self.assertTrue(np.isfinite(result))
        self.assertEqual(result,float(mean_absolute_percentage_error(y,pred)))

    def test_rmsle_clips_predictions_but_rejects_negative_truth(self):
        self.assertAlmostEqual(evaluate([0,1],[-1,2],'regression','rmsle')['rmsle'],mean_squared_log_error([0,1],[0,2])**.5)
        with self.assertRaises(ValueError): evaluate([-1,1],[0,1],'regression','rmsle')

    def test_balanced_accuracy_differs_from_accuracy_and_matches_callback(self):
        y=np.array([0]*9+[1]); pred=np.array([0]*10)
        proba=np.column_stack([np.ones(10)*.8,np.ones(10)*.2])
        result=evaluate(y,pred,'classification','balanced_accuracy',classes=[0,1])
        self.assertEqual(result['accuracy'],.9)
        self.assertEqual(result['balanced_accuracy'],.5)
        callback=lgbm_metric({'kind':'classification','metric':'balanced_accuracy','greater_is_better':True})
        self.assertEqual(callback(y,proba),('balanced_accuracy',balanced_accuracy_score(y,pred),True))


if __name__=='__main__': unittest.main(verbosity=2)
