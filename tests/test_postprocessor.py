"""Bounded decision optimizer contracts; outer labels never used for fitting."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import builtins
import sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tests'))
import numpy as np
from sklearn.metrics import f1_score
from automl.evaluation.postprocessor import MacroF1ThresholdOptimizer,calibrate_class_factors,validate_decision_optimizer
from automl.evaluation.callbacks import tune_class_factors
from automl.search.policy import normalize,signature
from test_feature_views import fixture,run,recipe as view_recipe


def probabilities():
    rng=np.random.default_rng(97)
    p=rng.dirichlet([4.,1.,.7],size=90)
    y=rng.choice(['Z','M','A'],size=90,p=[.65,.25,.1])
    return p,y,np.array(['Z','M','A'])


class PostprocessorTests(unittest.TestCase):
    def test_coordinate_rule_exactly_preserves_existing_factors(self):
        p,y,c=probabilities();expected=tune_class_factors(y,p,c)
        fitted=MacroF1ThresholdOptimizer(3).fit(p,y,c)
        self.assertEqual(fitted.factors_,expected)
        self.assertEqual(calibrate_class_factors(y,p,c)[0],expected)

    def test_bounded_numeric_refinement_never_loses_inner_objective(self):
        p,y,c=probabilities();fitted=MacroF1ThresholdOptimizer(3,'nelder_mead').fit(p,y,c)
        self.assertTrue(np.isfinite(fitted.weights).all())
        self.assertTrue(((fitted.weights>=.4)&(fitted.weights<=2.5)).all())
        self.assertGreaterEqual(fitted.diagnostics_['final_objective']+1e-12,fitted.diagnostics_['initial_objective'])
        self.assertLessEqual(fitted.diagnostics_['optimizer_nfev'],400)
        score=f1_score(y,fitted.predict_labels(p),labels=c,average='macro',zero_division=0)
        objective=score-.004*np.square(np.log(fitted.weights)).mean()
        self.assertAlmostEqual(objective,fitted.diagnostics_['final_objective'],places=14)

    def test_optimizer_exception_preserves_coordinate_warm_start(self):
        p,y,c=probabilities();expected=tune_class_factors(y,p,c)
        with patch('scipy.optimize.minimize',side_effect=RuntimeError('fixture failure')):
            fitted=MacroF1ThresholdOptimizer(3,'nelder_mead').fit(p,y,c)
        self.assertEqual(fitted.factors_,expected)
        self.assertEqual(fitted.diagnostics_['exception_type'],'RuntimeError')
        self.assertEqual(fitted.diagnostics_['status'],'preserved_coordinate_on_optimizer_error')

    def test_invalid_optimizer_result_cannot_publish_nonfinite_factors(self):
        p,y,c=probabilities();expected=tune_class_factors(y,p,c)
        for values in [[np.nan,0.,0.],[100.,100.,100.],[0.,0.]]:
            with self.subTest(values=values),patch('scipy.optimize.minimize',return_value=SimpleNamespace(x=np.array(values),nfev=10,success=False)):
                fitted=MacroF1ThresholdOptimizer(3,'nelder_mead').fit(p,y,c)
                self.assertEqual(fitted.factors_,expected)

    def test_unavailable_optional_optimizer_preserves_legacy_factors(self):
        p,y,c=probabilities();expected=tune_class_factors(y,p,c)
        original=builtins.__import__
        def guarded(name,*args,**kwargs):
            if name=='scipy.optimize':raise ImportError('fixture unavailable')
            return original(name,*args,**kwargs)
        with patch('builtins.__import__',side_effect=guarded):
            fitted=MacroF1ThresholdOptimizer(3,'nelder_mead').fit(p,y,c)
        self.assertEqual(fitted.factors_,expected)
        self.assertEqual(fitted.diagnostics_['exception_type'],'ImportError')

    def test_probability_label_class_shape_and_range_contracts(self):
        p,y,c=probabilities()
        invalid=[(p[:,:2],y,c),(p[:-1],y,c),(np.zeros_like(p),y,c),
            (p*2,y,c),(np.full_like(p,np.nan),y,c),(p,np.repeat('unknown',len(y)),c),
            (p,y,['Z','M','M']),(p,y,['Z','M']),(p[:0],y[:0],c)]
        for values in invalid:
            with self.subTest(shapes=[np.shape(v) for v in values]),self.assertRaises(ValueError):
                MacroF1ThresholdOptimizer(3).fit(*values)
        for n in [True,1,2.5,'3']:
            with self.subTest(n=n),self.assertRaises(ValueError):MacroF1ThresholdOptimizer(n)

    def test_fitted_api_default_integer_channels(self):
        p,y,c=probabilities();fitted=MacroF1ThresholdOptimizer(3)
        with self.assertRaises(ValueError):fitted.predict(p)
        lookup={label:i for i,label in enumerate(c)}
        fitted.fit(p,np.array([lookup[label] for label in y]))
        self.assertEqual(fitted.predict(p).dtype.kind,'i')
        np.testing.assert_allclose(fitted.predict_proba(p).sum(axis=1),1.)
        self.assertTrue(set(fitted.predict_labels(p))<=set(['0','1','2']))

    def test_explicit_class_order_and_probability_projection(self):
        p,y,c=probabilities();fitted=MacroF1ThresholdOptimizer(3).fit(p,y,c)
        expected=p*np.array([fitted.factors_[label] for label in c])
        expected/=expected.sum(axis=1,keepdims=True)
        np.testing.assert_allclose(fitted.predict_proba(p),expected)
        np.testing.assert_array_equal(fitted.predict_labels(p),c[expected.argmax(axis=1)])

    def test_normalizer_rejects_ignored_or_conflicting_optimizer_flags(self):
        for params in [{'decision_optimizer':'bad','calibrate':True},
                       {'decision_optimizer':[],'calibrate':True},
                       {'decision_optimizer':'nelder_mead'},
                       {'decision_optimizer':'nelder_mead','calibrate':True,'calibration_folds':3}]:
            with self.subTest(params=params),self.assertRaises(ValueError):normalize({'engine':'lightgbm','params':params})
        for engine in ['linear_text']:
            with self.assertRaises(ValueError):normalize({'engine':engine,'params':{'calibrate':True,'decision_optimizer':'nelder_mead'}})
        selected=normalize({'engine':'lightgbm','params':{'calibrate':True,'decision_optimizer':'nelder_mead'}})
        for spec in [{'kind':'regression','metric':'rmse'},{'kind':'classification','metric':'accuracy'}]:
            with self.subTest(spec=spec),self.assertRaises(ValueError):validate_decision_optimizer(selected,spec)
        combined=view_recipe();combined['params']['decision_optimizer']='nelder_mead'
        with self.assertRaises(ValueError):normalize(combined)

    def test_planner_can_explicitly_leave_a_typed_view_before_feature_hypothesis(self):
        original=view_recipe()
        cleared=normalize({'engine':'lightgbm','params':{'feature_views':None},
            'feature_code':'def transform(df): return df'},original)
        self.assertNotIn('feature_views',cleared['params'])
        self.assertIn('feature_views',original['params'])

    def test_real_worker_optimizer_does_not_see_outer_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);spec,train=fixture(root);exports=[];factors=[]
            selected=normalize({'engine':'lightgbm','params':{'iterations':35,'min_iterations':10,
                'calibrate':True,'decision_optimizer':'nelder_mead','class_weight_power':.5}})
            for number in range(2):
                out,record=run(root,spec,selected,str(number))
                self.assertEqual(record['decision_optimizer']['method'],'nelder_mead')
                self.assertLessEqual(record['decision_optimizer']['optimizer_nfev'],400)
                exports.append((out/'submission.csv').read_bytes());factors.append(record['class_factors'])
                train.loc[288:,'answer']=np.tile(['A','M','Z'],24)
                train.to_csv(spec['paths']['train'],index=False)
            self.assertEqual(exports[0],exports[1]);self.assertEqual(factors[0],factors[1])

    def test_method_is_an_effective_signature_not_an_ignored_parameter(self):
        base=normalize({'engine':'lightgbm','params':{'calibrate':True}})
        changed=normalize({'engine':'lightgbm','params':{'decision_optimizer':'nelder_mead'}},base)
        self.assertNotEqual(signature(base),signature(changed))
        self.assertEqual(validate_decision_optimizer(base),'coordinate')

    def test_legacy_calibration_is_called_once_not_once_per_class(self):
        p,y,c=probabilities()
        with patch('automl.evaluation.postprocessor.tune_class_factors',wraps=tune_class_factors) as legacy:
            MacroF1ThresholdOptimizer(3).fit(p,y,c)
            self.assertEqual(legacy.call_count,1)


if __name__=='__main__':unittest.main(verbosity=2)
