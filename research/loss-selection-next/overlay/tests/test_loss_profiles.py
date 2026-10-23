"""Prepared LOSS00 contracts. No execution during authoring.

Run only from a fully materialized isolated CP1 package with these six overlays.
Ten pure/constructor methods and six tiny-real methods (nine tiny fits), no API
or public data. No assertion claims a quality gain for a loss profile.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import numpy as np
import pandas as pd
from automl.contracts.messages import (ExperimentRequest,LOSS_PROFILES,
    loss_profile_catalog,resolve_loss_profile,validate_loss_profiles)
from automl.execution.model_adapters.registry import CAPABILITIES,effective_parameters,make_model
from automl.execution.model_adapters.lightgbm import create_model,fit_options,loss_profile_fit_receipt
from automl.execution import worker
from automl.search.policy import normalize,signature


def recipe(profile=None,**params):
    values=dict(iterations=20,min_child_samples=5,num_leaves=15,seed=42,early_metric='primary')
    values.update(params)
    if profile is not None:values['loss_profile_id']=profile
    return dict(engine='lightgbm',params=values,feature_code='')


class NoNetwork(unittest.TestCase):
    def setUp(self):
        self.network_attempts=[]
        def blocked(*args,**kwargs):
            self.network_attempts.append(True);raise AssertionError('LOSS00 network is forbidden')
        self.patches=[patch.object(socket,name,side_effect=blocked) for name in ['create_connection','getaddrinfo']]
        self.patches += [patch.object(socket.socket,name,side_effect=blocked) for name in ['connect','connect_ex','sendto']]
        for item in self.patches:item.start()
    def tearDown(self):
        for item in reversed(self.patches):item.stop()
        self.assertEqual(self.network_attempts,[])


class LossContractTests(NoNetwork):
    def test_catalog_fixed_regression_only_and_returned_metadata_independent(self):
        profiles=loss_profile_catalog('lightgbm','regression')
        self.assertEqual([p['loss_profile_id'] for p in profiles],['lgbm_l2_v1','lgbm_l1_v1','lgbm_huber_a09_v1'])
        self.assertEqual(loss_profile_catalog('lightgbm','classification'),())
        self.assertEqual(loss_profile_catalog('xgboost','regression'),())
        profiles[0]['objective']='untrusted mutation'
        self.assertEqual(loss_profile_catalog()[0]['objective'],'regression')
        with self.assertRaises(FrozenInstanceError):LOSS_PROFILES[0].objective='huber'

    def test_normalization_effective_parameters_and_signature_retain_typed_ID(self):
        signatures=[]
        for profile in LOSS_PROFILES:
            value=normalize(recipe(profile.loss_profile_id));signatures.append(signature(value))
            self.assertEqual(value['params']['loss_profile_id'],profile.loss_profile_id)
            self.assertEqual(effective_parameters('lightgbm',value['params'])['loss_profile_id'],profile.loss_profile_id)
        self.assertEqual(len(set(signatures)),3)
        self.assertNotIn(signature(normalize(recipe())),signatures)
        first=recipe('lgbm_l1_v1');second=deepcopy(first);second['hypothesis']='different narrative'
        self.assertEqual(signature(first),signature(second))

    def test_unknown_incompatible_and_misplaced_profile_reject_before_filter(self):
        for profile in ['typo','lgbm_softmax_v1',None,True,{'objective':'huber'}]:
            raw=recipe();raw['params']['loss_profile_id']=profile
            with self.subTest(profile=profile),self.assertRaises(ValueError):normalize(raw)
            with self.subTest(profile=profile),self.assertRaises(ValueError):effective_parameters('lightgbm',raw['params'])
        for engine in ['catboost','xgboost','extra_trees','linear_text']:
            raw=recipe('lgbm_l1_v1');raw['engine']=engine
            with self.subTest(engine=engine),self.assertRaises(ValueError):normalize(raw)
            with self.subTest(engine=engine),self.assertRaises(ValueError):effective_parameters(engine,raw['params'])
        raw=recipe();raw['loss_profile_id']='lgbm_l1_v1'
        with self.assertRaises(ValueError):normalize(raw)
        with self.assertRaises(ValueError):signature(raw)

    def test_raw_alias_conflicts_and_inherited_profile_reject_without_mutation(self):
        best=normalize(recipe('lgbm_huber_a09_v1'));before=deepcopy(best)
        for alias in ['objective','objective_type','application','app','loss','alpha']:
            raw=recipe('lgbm_huber_a09_v1',**{alias:.9})
            with self.subTest(alias=alias),self.assertRaises(ValueError):normalize(raw)
            with self.subTest(inherited=alias),self.assertRaises(ValueError):
                normalize(dict(engine='lightgbm',params={alias:.9}),best)
        self.assertEqual(best,before)

    def test_process_contract_rejects_bad_profile_in_any_ensemble_child(self):
        good=recipe('lgbm_l1_v1')
        ExperimentRequest('loss','out','split.npz',good,1).validate()
        bad=deepcopy(good);bad['params']['loss_profile_id']='typo'
        with self.assertRaises(ValueError):ExperimentRequest('loss','out','split.npz',bad,1).validate()
        parent=dict(engine='ensemble',params={},components=[good,bad],weights=[.5,.5])
        with self.assertRaises(ValueError):ExperimentRequest('loss','out','split.npz',parent,1).validate()
        with self.assertRaises(ValueError):validate_loss_profiles(good,'classification')

    def test_ordinary_advertised_capabilities_equal_frozen_CP1(self):
        expected=json.loads((ROOT/'tests/fixtures/cp1_capabilities.json').read_text('utf-8'))
        self.assertEqual(CAPABILITIES,expected)
        self.assertNotIn('loss_profile_id',CAPABILITIES['lightgbm']['parameters'])

    def test_nonprimary_early_stopping_and_direct_classification_are_rejected(self):
        spec=dict(kind='regression',metric='rmse',greater_is_better=False)
        raw=recipe('lgbm_l1_v1',early_metric='loss')
        with self.assertRaises(ValueError):normalize(raw)
        with self.assertRaises(ValueError):create_model(raw,'regression',1,20)
        with self.assertRaises(ValueError):fit_options(spec,raw,None,None,None,[],False)
        with self.assertRaises(ValueError):make_model(recipe('lgbm_l2_v1'),'classification',1,20)
        self.assertIsNone(resolve_loss_profile('lightgbm',{},'classification'))

    def test_telemetry_requires_actual_fitted_booster_not_constructor_claim(self):
        raw=recipe('lgbm_huber_a09_v1')
        for actual in [None,{},dict(objective='regression',alpha=.9),dict(objective='huber'),dict(objective='huber',alpha=float('nan'),metric='None'),dict(objective='huber',alpha=.9,metric=[]),dict(objective='huber',alpha=.9,metric='l1'),dict(objective='huber',alpha=.9,metric={'bad':'None'})]:
            model=SimpleNamespace(booster_=SimpleNamespace(params=actual),get_params=lambda:dict(objective='huber',alpha=.9))
            with self.subTest(actual=actual),self.assertRaises(ValueError):loss_profile_fit_receipt(raw,'regression',model)
        model=SimpleNamespace(booster_=SimpleNamespace(params=dict(objective='huber',alpha=.9,metric=['None'])))
        proof=loss_profile_fit_receipt(raw,'regression',model)
        self.assertTrue(proof['verified']);self.assertEqual(proof['evidence_source'],'fitted_booster.params')
        self.assertEqual(proof['effective_metric'],['None']);self.assertEqual(proof['requested_metric'],'None')
        self.assertIsNone(loss_profile_fit_receipt(recipe(),'regression',SimpleNamespace()))

    def test_worker_rejects_wrong_kind_before_IO_or_any_ensemble_child(self):
        raw=recipe('lgbm_l1_v1')
        with patch.object(worker,'read_input_table',side_effect=AssertionError('Unexpected IO')):
            with self.assertRaises(ValueError):worker.run(dict(spec={'kind':'classification'},recipe=raw))
        parent=dict(engine='ensemble',params={},components=[recipe(),raw],weights=[.5,.5])
        with patch.object(worker,'run_ensemble',side_effect=AssertionError('Unexpected child')):
            with self.assertRaises(ValueError):worker.run(dict(spec={'kind':'classification'},recipe=parent))

    def test_legacy_constructor_and_fit_options_equal_exact_CP1_fixture(self):
        path=ROOT/'tests/fixtures/cp1_lightgbm.py'
        expected=json.loads((ROOT/'tests/fixtures/cp1_fixture_sha.json').read_text('utf-8'))['lightgbm']
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),expected)
        spec=importlib.util.spec_from_file_location('_CP1_loss_fixture',path)
        old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
        for kind in ['regression','classification']:
            value=recipe(class_weight_power=.5)
            self.assertEqual(create_model(value,kind,1,20).get_params(),old.create_model(value,kind,1,20).get_params())
        frame=pd.DataFrame({'x':[0.,1.,2.]});y=pd.Series([1.,2.,3.]);task=dict(kind='regression',metric='rmse',greater_is_better=False)
        new=fit_options(task,recipe(),frame,y,np.array([2]),[],True)
        before=old.fit_options(task,recipe(),frame,y,np.array([2]),[],True)
        self.assertEqual(set(new),set(before))
        values=np.log1p([2.,3.]);pred=np.log1p([1.,4.])
        self.assertEqual(new['eval_metric'](values,pred),before['eval_metric'](values,pred))


class LossRealEstimatorTests(NoNetwork):
    def data(self):
        x=pd.DataFrame({'x':np.arange(80,dtype=float)/10,'z':np.arange(80,dtype=float)%7})
        y=pd.Series(1+2*x['x']+.1*x['z']);y.iloc[3]+=20
        return x,y
    def fit_one(self,profile):
        x,y=self.data();value=recipe(profile);model=make_model(value,'regression',1,20);model.fit(x,y)
        proof=loss_profile_fit_receipt(value,'regression',model)
        self.assertEqual(proof['effective_objective'],resolve_loss_profile('lightgbm',value['params']).objective)
        self.assertTrue(np.isfinite(model.predict(x)).all());self.assertTrue(proof['verified'])
        values=proof['effective_metric'] if isinstance(proof['effective_metric'],list) else [proof['effective_metric']]
        self.assertTrue(all(v.lower() in {'none','na','null','custom'} for v in values))
        return model,proof
    def test_real_l2_booster_parameters_and_finite_outputs(self):self.fit_one('lgbm_l2_v1')
    def test_real_l1_booster_parameters_and_finite_outputs(self):self.fit_one('lgbm_l1_v1')
    def test_real_huber_booster_parameters_and_fixed_alpha(self):
        _,proof=self.fit_one('lgbm_huber_a09_v1');self.assertEqual(proof['effective_alpha'],.9)
    def test_real_explicit_l2_matches_implicit_legacy_loss(self):
        x,y=self.data();legacy=make_model(recipe(),'regression',1,20);explicit=make_model(recipe('lgbm_l2_v1'),'regression',1,20)
        legacy.fit(x,y);explicit.fit(x,y)
        np.testing.assert_allclose(legacy.predict(x),explicit.predict(x),rtol=0,atol=1e-12)
    def test_real_huber_stops_only_on_unchanged_original_scale_RMSE(self):
        x,y=self.data();raw=recipe('lgbm_huber_a09_v1');model=make_model(raw,'regression',1,20)
        spec=dict(kind='regression',metric='rmse',greater_is_better=False);target=np.log1p(y)
        options=fit_options(spec,raw,x,target,np.arange(60,80),[],True)
        self.assertEqual(model.get_params()['metric'],'None')
        _,value,direction=options['eval_metric'](np.log1p([1.,3.]),np.log1p([2.,1.]))
        self.assertAlmostEqual(value,np.sqrt((1+4)/2));self.assertFalse(direction)
        model.fit(x.iloc[:60],target.iloc[:60],**options)
        self.assertEqual(set(model.evals_result_['valid_0']),{'rmse'})
        proof=loss_profile_fit_receipt(raw,'regression',model)
        self.assertTrue(proof['verified']);self.assertEqual(proof['requested_metric'],'None')
        values=proof['effective_metric'] if isinstance(proof['effective_metric'],list) else [proof['effective_metric']]
        self.assertTrue(all(v.lower() in {'none','na','null','custom'} for v in values))
    def test_tiny_worker_nested_and_full_refit_record_actual_booster_scopes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);x,y=self.data();train=x.copy();train.insert(0,'id',np.arange(80));train['target']=y
            test=pd.DataFrame({'id':[101,102,103],'x':[1.,2.,3.],'z':[2.,3.,4.]})
            sample=pd.DataFrame({'id':[103,101,102],'target':[0.,0.,0.]})
            for name,frame in [('train',train),('test',test),('sample_submission',sample)]:frame.to_csv(root/(name+'.csv'),index=False)
            tr=np.arange(60);va=np.arange(60,80)[::-1];np.savez(root/'split.npz',train=tr,validation=va)
            spec=dict(kind='regression',metric='rmse',greater_is_better=False,target='target',id='id',features=['x','z'],
                paths={'train':str(root/'train.csv'),'test':str(root/'test.csv'),'sample_submission':str(root/'sample_submission.csv')},
                prediction_type='value',output_columns=['target'],sample_test_positions=[2,0,1],text_features=[],classes=[],validation_strategy='legacy')
            for full in [False,True]:
                out=root/('full' if full else 'nested');out.mkdir()
                raw=recipe('lgbm_huber_a09_v1',iterations=30,min_iterations=10,nested_stopping=True,log_target=True)
                worker.run(dict(spec=spec,recipe=raw,output_dir=str(out),split_path=str(root/'split.npz'),threads=1,full_fit=full))
                record=json.loads((out/'result.json').read_text('utf-8'));proofs=[v['loss_profile'] for v in record['data_policy_runs']]
                self.assertEqual(record['loss_profile_id'],'lgbm_huber_a09_v1')
                self.assertEqual(record['effective_loss_profile'],proofs[-1])
                self.assertEqual(len(proofs),1 if full else 2)
                self.assertTrue(all(p['verified'] and p['target_scale']=='log1p' and p['effective_alpha']==.9 for p in proofs))
                self.assertEqual(proofs[-1]['model_scope'],'full_refit' if full else 'outer_fitting')
                actual=pd.read_csv(out/'submission.csv');self.assertEqual(actual['id'].tolist(),sample['id'].tolist())
                self.assertTrue(np.isfinite(actual['target']).all())
                if not full:
                    validation=pd.read_csv(out/'validation_predictions.csv');np.testing.assert_array_equal(validation['row_position'],va)
                    self.assertAlmostEqual(record['metrics']['rmse'],float(np.sqrt(np.mean((y.iloc[va].to_numpy()-validation['y_pred'].to_numpy())**2))),places=9)
                    self.assertEqual(record['early_stopping_source'],'inner_training_holdout')


if __name__=='__main__':unittest.main(verbosity=2)
