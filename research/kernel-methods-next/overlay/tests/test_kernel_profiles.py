"""Prepared technical contracts only; no author execution/public data/API.

The future tests include tiny fitting, not a quality comparison. Full source,
flat import-only adaptation and real saved-artifact screens remain separate.
"""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import numpy as np
import pandas as pd
from automl.contracts.messages import ExperimentRequest
from automl.contracts.representations import representation_catalog,resolve_representation_profile,validate_representation_recipe
from automl.execution.model_adapters.kernel_tabular import BoundedTabularModel,matrix_budget,tabular_representation_fit
from automl.execution.model_adapters.registry import CAPABILITIES,effective_parameters
from automl.execution.weighting.classes import sample_weights as original_weights
from automl.execution import worker
from automl.search.policy import normalize,signature


LINEAR='tabular_linear_bounded_v1'
RBF='tabular_rbf128_invdim_v1'


def recipe(profile=RBF):
    return {'engine':'linear_text','params':{'representation_profile':profile,'generic_features':'none'},'feature_code':''}


def spec(kind='regression'):
    return dict(kind=kind,metric='rmse' if kind=='regression' else 'macro_f1',greater_is_better=kind=='classification',
        text_features=[],features=['x','empty','group'],target='target',id='id',classes=[] if kind=='regression' else ['zeta','alpha','middle'],
        prediction_type='value' if kind=='regression' else 'label',output_columns=['target'])


def data():
    x=pd.DataFrame({'x':np.arange(72,dtype=float)/10,'empty':np.full(72,np.nan),'group':['a','b','c']*24})
    return x,pd.Series(1+2*x['x'])


class KernelProfileContracts(unittest.TestCase):
    def setUp(self):
        self.network_attempts=[]
        def blocked(*args,**kwargs):self.network_attempts.append(True);raise AssertionError('Network forbidden')
        self.network=[patch.object(socket,n,side_effect=blocked) for n in ['create_connection','getaddrinfo']]
        self.network += [patch.object(socket.socket,n,side_effect=blocked) for n in ['connect','connect_ex','sendto']]
        for item in self.network:item.start()
    def tearDown(self):
        for item in reversed(self.network):item.stop()
        self.assertEqual(self.network_attempts,[])

    def test_fixed_catalog_has_only_matched_identity_and_RBF128(self):
        cards=representation_catalog()
        self.assertEqual([c['representation_profile'] for c in cards],[LINEAR,RBF])
        self.assertEqual(cards[1]['components'],128)
        self.assertEqual(cards[1]['gamma_rule'],'1/prepared_fitting_dimension')
        self.assertEqual(cards[1]['matrix_limit_bytes'],128_000_000)
        self.assertEqual(cards[0]['ridge_alpha'],cards[1]['ridge_alpha'])
        cards[0]['ridge_alpha']=1000
        self.assertEqual(representation_catalog()[0]['ridge_alpha'],10.)

    def test_raw_validation_before_filter_dedup_and_no_ordinary_advertising(self):
        before=recipe();frozen=deepcopy(before)
        normal=normalize(before)
        self.assertEqual(normal['params']['representation_profile'],RBF)
        self.assertFalse(normal['params']['nested_stopping'])
        self.assertEqual(before,frozen)
        self.assertNotEqual(signature(normal),signature(normalize(recipe(LINEAR))))
        expected=json.loads((ROOT/'tests/fixtures/cp1_capabilities.json').read_text('utf-8'))
        self.assertEqual(CAPABILITIES,expected)
        self.assertNotIn('representation_profile',CAPABILITIES['linear_text']['parameters'])
        for profile in ['typo',None,True,{'components':128}]:
            raw=recipe();raw['params']['representation_profile']=profile
            with self.subTest(profile=profile),self.assertRaises(ValueError):normalize(raw)
        for engine in ['lightgbm','catboost','extra_trees','xgboost']:
            with self.subTest(engine=engine),self.assertRaises(ValueError):effective_parameters(engine,recipe()['params'])
        for name,value in [('gamma',.1),('seed',43),('text_C',2),('class_weights',True),('class_weights',False),('class_weight_power',1.),('log_target',True),('nested_stopping',True)]:
            raw=recipe();raw['params'][name]=value
            with self.subTest(name=name),self.assertRaises(ValueError):normalize(raw)
        with self.assertRaises(ValueError):normalize({'engine':'linear_text','params':{'text_C':2}},normal)

    def test_process_and_worker_reject_incompatible_task_before_IO(self):
        bad=recipe();bad['params']['representation_profile']='typo'
        with self.assertRaises(ValueError):ExperimentRequest('kernel','out','split',bad,1).validate()
        for task in [dict(spec(),text_features=['x']),dict(spec(),metric='mae'),dict(spec(),task_family='pointwise_ranking')]:
            with patch.object(worker,'read_input_table',side_effect=AssertionError('Unexpected IO')):
                with self.subTest(task=task),self.assertRaises(ValueError):worker.run(dict(spec=task,recipe=recipe()))
        parent={'engine':'ensemble','params':{},'components':[recipe(),bad]}
        with self.assertRaises(ValueError):validate_representation_recipe(parent,spec())

    def test_memory_and_shape_admission_precedes_any_processor_fit(self):
        profile=resolve_representation_profile('linear_text',recipe()['params'])
        for values in [(200001,1,0),(72,65,0),(200000,64,0)]:
            with self.subTest(values=values),self.assertRaises(ValueError):matrix_budget(profile,*values)
        x,y=data();model=BoundedTabularModel(spec(),recipe(),1)
        model.profile=replace(model.profile,matrix_limit_bytes=1)
        with patch('sklearn.compose.ColumnTransformer.fit_transform',side_effect=AssertionError('Unexpected fit')):
            with self.assertRaisesRegex(ValueError,'budget'):model.fit(x,y)
            wide_vocabulary=x.iloc[:1].loc[x.index[:1].repeat(4097)].reset_index(drop=True)
            wide_vocabulary['group']=['category'+str(i) for i in range(4097)]
            with self.assertRaisesRegex(ValueError,'vocabulary'):
                BoundedTabularModel(spec(),recipe(),1).fit(wide_vocabulary,pd.Series(np.arange(4097,dtype=float)))
        with self.assertRaises(ValueError):BoundedTabularModel(spec(),recipe(),3)

    def test_missing_classes_nonfinite_targets_and_target_ID_reject_before_fit(self):
        x,y=data()
        with patch('sklearn.compose.ColumnTransformer.fit_transform',side_effect=AssertionError('Unexpected fit')):
            with self.assertRaisesRegex(ValueError,'classes'):
                BoundedTabularModel(spec('classification'),recipe(),1).fit(x,pd.Series(['alpha','middle']*36))
            damaged=y.copy();damaged.iloc[0]=np.inf
            with self.assertRaisesRegex(ValueError,'targets'):BoundedTabularModel(spec(),recipe(),1).fit(x,damaged)
            for forbidden in ['id','target']:
                raw=x.copy();raw[forbidden]=1
                with self.subTest(forbidden=forbidden),self.assertRaisesRegex(ValueError,'Target/ID'):
                    BoundedTabularModel(spec(),recipe(),1).fit(raw,y)
        with patch.object(BoundedTabularModel,'fit',side_effect=AssertionError('Unexpected fit')):
            for tr,va in [(np.array([0.,1.]),np.array([2,3])),(np.array([0,1]),np.array([1,2])),(np.array([0,0]),np.array([2,3]))]:
                with self.subTest(tr=tr),self.assertRaises(ValueError):
                    tabular_representation_fit(spec(),recipe(),x,x.iloc[:2],y,tr,va,False,1,{})

    def test_matched_control_and_kernel_have_same_fitted_preprocessing(self):
        x,y=data();x['group']=['a']*30+['b']*30+['rare'+str(i) for i in range(12)]
        a=BoundedTabularModel(spec(),recipe(LINEAR),1).fit(x,y)
        b=BoundedTabularModel(spec(),recipe(RBF),1).fit(x,y)
        for name in ['numeric','category']:
            left=a.processor_.named_transformers_[name];right=b.processor_.named_transformers_[name]
            if name=='numeric':
                np.testing.assert_array_equal(left.steps[0][1].statistics_,right.steps[0][1].statistics_)
                np.testing.assert_array_equal(left.steps[1][1].scale_,right.steps[1][1].scale_)
            else:
                for p,q in zip(left.categories_,right.categories_):np.testing.assert_array_equal(p,q)
                self.assertEqual(len(left.get_feature_names_out()),3)
                self.assertEqual(len(left.infrequent_categories_[0]),12)
        self.assertEqual(a.diagnostics_['estimator'],b.diagnostics_['estimator'])
        self.assertEqual(b.diagnostics_['representation_columns'],128)
        self.assertEqual(b.diagnostics_['gamma'],1/b.diagnostics_['prepared_columns'])
        self.assertTrue(np.isfinite(a.predict(x)).all());self.assertTrue(np.isfinite(b.predict(x)).all())

    def test_outer_poisoned_features_labels_do_not_change_fitted_state_or_test_predictions(self):
        x,y=data();tr=np.arange(54);va=np.arange(54,72);test=x.iloc[:5].copy()
        poison=x.copy();poison['x']=poison['x'].astype(object);poison.loc[va,'x']='outer-only-string'
        poison.loc[va,'group']='outer-only-category';other_y=y.copy();other_y.iloc[va]+=10000
        diagnostics_a={};diagnostics_b={}
        before=x.copy(deep=True);ybefore=y.copy(deep=True)
        a=tabular_representation_fit(spec(),recipe(),x,test,y,tr,va,False,1,diagnostics_a)
        b=tabular_representation_fit(spec(),recipe(),poison,test,other_y,tr,va,False,1,diagnostics_b)
        self.assertEqual(diagnostics_a['fitting_state_sha256'],diagnostics_b['fitting_state_sha256'])
        self.assertEqual(diagnostics_a['fitting_row_order_sha256'],diagnostics_b['fitting_row_order_sha256'])
        np.testing.assert_allclose(a[0],b[0],rtol=0,atol=1e-12)
        self.assertNotEqual(a[2]['rmse'],b[2]['rmse'])
        pd.testing.assert_frame_equal(x,before);pd.testing.assert_series_equal(y,ybefore)

    def test_unknown_categories_all_missing_numeric_and_batch_invariance(self):
        x,y=data();model=BoundedTabularModel(spec(),recipe(),1).fit(x,y)
        unseen=pd.concat([x.iloc[:1]]*1100,ignore_index=True);unseen['group']='unseen';unseen['x']=np.inf
        whole=model.predict(unseen);parts=np.concatenate([model.predict(unseen.iloc[i:i+13]) for i in range(0,len(unseen),13)])
        self.assertTrue(np.isfinite(whole).all());np.testing.assert_allclose(whole,parts,rtol=0,atol=1e-12)
        with self.assertRaisesRegex(ValueError,'schema'):model.predict(unseen[['group','x','empty']])

    def test_canonical_class_probability_order_and_requested_output_columns(self):
        x,_=data();y=pd.Series(['alpha','middle','zeta']*24);task=spec('classification')
        model=BoundedTabularModel(task,recipe(),1).fit(x,y);prob=model.predict_proba(x.iloc[:5])
        self.assertEqual(model.classes_.tolist(),['zeta','alpha','middle'])
        self.assertEqual(model.estimator_.classes_.tolist(),['alpha','middle','zeta'])
        direct=model.estimator_.predict_proba(next(model._batches(x.iloc[:5])))[:,[2,0,1]]
        np.testing.assert_allclose(prob,direct,rtol=0,atol=1e-12)
        np.testing.assert_array_equal(model.predict(x.iloc[:5]),model.classes_[prob.argmax(axis=1)])
        np.testing.assert_allclose(prob.sum(axis=1),1.,atol=1e-8)
        task=dict(task,prediction_type='probability_matrix',output_columns=['middle','zeta','alpha'])
        returned=tabular_representation_fit(task,recipe(),x,x.iloc[:5],y,np.arange(54),np.arange(54,72),False,1,{})
        np.testing.assert_allclose(returned[0],returned[3][:,[2,0,1]],rtol=0,atol=1e-12)

    def test_binary_string_labels_and_fitting_only_class_weights(self):
        x,_=data();y=pd.Series(['right']*36+['left']*36);task=dict(spec('classification'),classes=['right','left'])
        rows=np.r_[np.arange(18),np.arange(36,54)];outside=np.setdiff1d(np.arange(72),rows)
        altered=y.copy();altered.iloc[outside]=['left','right']*18;seen=[]
        def weights(labels,params):seen.append((labels.tolist(),dict(params)));return original_weights(labels,params)
        with patch('automl.execution.model_adapters.kernel_tabular.sample_weights',side_effect=weights):
            a=tabular_representation_fit(task,recipe(),x,x.iloc[:3],y,rows,outside,False,1,{})
            b=tabular_representation_fit(task,recipe(),x,x.iloc[:3],altered,rows,outside,False,1,{})
        self.assertEqual(seen,[(y.iloc[rows].tolist(),{'class_weight_power':.5})]*2)
        np.testing.assert_allclose(a[3],b[3],rtol=0,atol=1e-12)
        self.assertEqual(a[5].tolist(),['right','left'])

    def test_worker_primary_RMSE_row_order_and_full_refit_CSV(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);x,y=data();train=x.copy();train.insert(0,'id',np.arange(len(x)));train['target']=y
            test=x.iloc[:3].copy();test.insert(0,'id',[101,102,103]);sample=pd.DataFrame({'id':[103,101,102],'target':[0.,0.,0.]})
            for name,frame in [('train',train),('test',test),('sample_submission',sample)]:frame.to_csv(root/(name+'.csv'),index=False)
            tr=np.arange(54);va=np.arange(54,72)[::-1];np.savez(root/'split.npz',train=tr,validation=va)
            task=dict(spec(),paths={n:str(root/(n+'.csv')) for n in ['train','test','sample_submission']},sample_test_positions=[2,0,1])
            for full in [False,True]:
                out=root/('full' if full else 'holdout');out.mkdir()
                worker.run(dict(spec=task,recipe=normalize(recipe()),output_dir=str(out),split_path=str(root/'split.npz'),threads=1,full_fit=full))
                record=json.loads((out/'result.json').read_text('utf-8'));actual=pd.read_csv(out/'submission.csv')
                self.assertEqual(record['representation']['fitting_rows'],72 if full else 54)
                self.assertEqual(actual['id'].tolist(),sample['id'].tolist());self.assertTrue(np.isfinite(actual['target']).all())
                if full:self.assertIsNone(record['metrics'])
                else:
                    validation=pd.read_csv(out/'validation_predictions.csv');np.testing.assert_array_equal(validation['row_position'],va)
                    expected=float(np.sqrt(np.mean((y.iloc[va].to_numpy()-validation['y_pred'].to_numpy())**2)))
                    self.assertAlmostEqual(record['metrics']['rmse'],expected,places=9)

    def test_no_profile_worker_keeps_existing_linear_dispatch_and_no_extra_receipt(self):
        # A no-fit dispatch fixture: checks the unchanged branch independently
        # of its learner; it does not claim prediction parity to a fitted baseline.
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);x,y=data();train=x.copy();train['id']=np.arange(72);train['target']=y
            test=x.iloc[:2].copy();test['id']=[101,102];sample=pd.DataFrame({'id':[101,102],'target':[0.,0.]})
            task=dict(spec(),paths={'train':'train','test':'test','sample_submission':'sample'})
            np.savez(root/'split.npz',train=np.arange(54),validation=np.arange(54,72))
            def table(path):return train.copy() if path=='train' else test.copy()
            expected=(np.array([1.,2.]),None,None,None,None,None)
            with patch.object(worker,'read_input_table',side_effect=table),patch.object(worker,'read_task_sample',return_value=sample),patch.object(worker,'linear_text_fit',return_value=expected) as old,patch('automl.execution.model_adapters.kernel_tabular.tabular_representation_fit',side_effect=AssertionError('Profile path used')):
                worker.run(dict(spec=task,recipe={'engine':'linear_text','params':{},'feature_code':''},output_dir=str(root),split_path=str(root/'split.npz'),threads=1,full_fit=True))
            self.assertEqual(old.call_count,1)
            self.assertNotIn('representation',json.loads((root/'result.json').read_text('utf-8')))


if __name__=='__main__':unittest.main(verbosity=2)
