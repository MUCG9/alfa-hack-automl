"""Bounded retransformation math and real fitting-only history calibration."""
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
import contextlib,io,json,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tests'))
import numpy as np
from automl.execution.postprocessing.targets import fit_smearing,inverse_log_predictions,validate_target_smearing
from automl.execution import worker
from automl.search.policy import normalize,signature,portfolio
from test_history_worker import fixture


def recipe(smear=True):
    params={'iterations':40,'min_iterations':10,'num_leaves':15,
        'log_target':True,'target_encoding':True,'target_encoding_groups':[['segment','measure']],
        'history_asof':True,'history_min_periods':3}
    if smear:params['target_smearing']=True
    return normalize({'engine':'lightgbm','params':params})


def run(root,spec,selected,name,**options):
    output=root/name;output.mkdir()
    with contextlib.redirect_stdout(io.StringIO()):
        worker.run(dict(spec=spec,recipe=selected,output_dir=str(output),
            split_path=str(root/'split.npz'),threads=1,**options))
    return output,json.loads((output/'result.json').read_text())


class TargetSmearingTests(unittest.TestCase):
    def test_empirical_residual_factor_and_correct_inverse(self):
        logged=np.linspace(1,3,30);truth=np.exp(logged)*1.1-1
        state=fit_smearing(truth,logged)
        self.assertAlmostEqual(state['factor'],1.1,places=14)
        self.assertEqual(state['status'],'fitted')
        np.testing.assert_allclose(inverse_log_predictions(logged,state['factor']),truth)

    def test_bound_and_invalid_target_contracts(self):
        logged=np.ones(30)
        self.assertEqual(fit_smearing(np.exp(logged)*4-1,logged)['factor'],1.25)
        self.assertEqual(fit_smearing(np.exp(logged)*.5-1,logged)['factor'],.8)
        for y,pred in [(np.ones(29),logged),(np.ones((30,1)),logged),
                       (-np.ones(30),logged),(np.full(30,np.nan),logged),
                       (np.ones(30),np.full(30,np.inf))]:
            with self.subTest(shapes=(np.shape(y),np.shape(pred))),self.assertRaises(ValueError):fit_smearing(y,pred)

    def test_sparse_or_overflowing_moments_preserve_identity(self):
        self.assertEqual(fit_smearing(np.ones(19),np.ones(19))['factor'],1.)
        state=fit_smearing(np.ones(30),np.full(30,-1000.))
        self.assertEqual(state['factor'],1.)
        self.assertEqual(state['status'],'skipped_nonfinite_residual_moment')

    def test_identity_preserves_existing_dtype_and_exact_values(self):
        values=np.linspace(-1,5,30,dtype='float32')
        actual=inverse_log_predictions(values,1.)
        np.testing.assert_array_equal(actual,np.expm1(values));self.assertEqual(actual.dtype,values.dtype)
        for factor in [True,'1',np.nan,.7,1.3]:
            with self.subTest(factor=factor),self.assertRaises(ValueError):inverse_log_predictions(values,factor)

    def test_flag_contract_signature_and_explicit_disable(self):
        selected=recipe();base=recipe(False)
        self.assertNotEqual(signature(selected),signature(base))
        disabled=normalize({'engine':'lightgbm','params':{'target_smearing':False}},selected)
        self.assertNotIn('target_smearing',disabled['params'])
        self.assertEqual(signature(disabled),signature(base))
        for value in [None,0,1,'true']:
            invalid=deepcopy(selected);invalid['params']['target_smearing']=value
            with self.subTest(value=value),self.assertRaises(ValueError):normalize(invalid)
        for invalid in [dict(selected,engine='linear_text'),
                        dict(selected,params=dict(selected['params'],log_target=False)),
                        dict(selected,data_policy={'augmentation':'mask'})]:
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):normalize(invalid)
        for spec in [{'kind':'classification','metric':'macro_f1'},
                     {'kind':'regression','metric':'mae'},
                     {'kind':'regression','metric':'rmse','task_family':'pointwise_ranking'},
                     {'kind':'regression','metric':'rmse','text_features':['review']}]:
            with self.subTest(spec=spec),self.assertRaises(ValueError):validate_target_smearing(selected,spec)

    def test_no_unmeasured_default_candidate_is_added(self):
        for spec in [{'kind':'classification','metric':'macro_f1','text_features':[]},
                     {'kind':'regression','metric':'rmse','text_features':[]},
                     {'kind':'regression','metric':'rmse','text_features':[],
                      'validation_strategy':'time','time_column':'period','static_numeric_features':['built']}]:
            self.assertFalse(any(r['params'].get('target_smearing') for r in portfolio(spec)))

    def test_real_worker_outer_labels_do_not_enter_factor_or_predictions(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);spec,train=fixture(root);exports=[];states=[]
            for number in range(2):
                output,record=run(root,spec,recipe(),str(number))
                state=record['target_smearing'];states.append(state)
                self.assertIn(state['status'],['fitted','bounded'])
                self.assertTrue(state['history_support']['enabled'])
                self.assertGreaterEqual(state['calibration_rows'],20)
                exports.append((output/'submission.csv').read_bytes())
                train.loc[200:,'target']=1000000.;train.to_csv(spec['paths']['train'],index=False)
            self.assertEqual(states[0],states[1]);self.assertEqual(exports[0],exports[1])

    def test_real_full_refit_calibrates_at_fixed_selected_iterations(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);spec,_=fixture(root)
            output,record=run(root,spec,recipe(),'full',full_fit=True,fit_iterations=35)
            self.assertEqual(record['fit_iterations'],35)
            self.assertEqual(record['target_smearing']['matching_iterations'],35)
            self.assertEqual(record['early_stopping_source'],'full_refit')
            values=__import__('pandas').read_csv(output/'submission.csv')
            self.assertEqual(values.id.tolist(),list(range(1000,1012)))
            self.assertTrue(np.isfinite(values.target).all())

    def test_real_insufficient_inner_history_is_byte_identical_to_control(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);spec,_=fixture(root)
            np.savez(root/'split.npz',train=np.arange(80),validation=np.arange(80,120))
            first,control=run(root,spec,recipe(False),'control')
            second,candidate=run(root,spec,recipe(),'gated')
            self.assertEqual(candidate['target_smearing']['status'],'skipped_history_support')
            self.assertEqual(candidate['target_smearing']['factor'],1.)
            for name in ['validation_predictions.csv','submission.csv']:
                self.assertEqual((first/name).read_bytes(),(second/name).read_bytes())

    def test_real_matching_floor_refits_calibration_model_before_prediction(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);spec,_=fixture(root);predicted=[];fitted=[]
            original=worker.make_model
            class Proxy:
                def __init__(self,model):self.model=model
                def __getattr__(self,name):return getattr(self.model,name)
                def fit(self,*args,**kwargs):
                    fitted.append(self.model.n_estimators);self.model.fit(*args,**kwargs);return self
                def predict(self,*args,**kwargs):
                    predicted.append(self.model.n_estimators);return self.model.predict(*args,**kwargs)
            def make(*args,**kwargs):return Proxy(original(*args,**kwargs))
            selected=recipe();selected['params']['min_iterations']=30
            with patch.object(worker,'make_model',side_effect=make),patch.object(worker,'selected_iterations',side_effect=[1,None]):
                _,record=run(root,spec,selected,'floor')
            self.assertEqual(fitted,[40,30,30])
            self.assertEqual(predicted,[30,30,30])
            self.assertEqual(record['target_smearing']['matching_iterations'],30)


if __name__=='__main__':unittest.main(verbosity=2)
