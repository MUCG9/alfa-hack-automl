"""Prepared UAR loss-backend contracts; author execution remains zero.

Eleven pure/mock/constructor methods plus six tiny-real methods (nine learner fits
if complete). Synthetic fixtures only; no public data or API. No quality claim.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import ast
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


# Baseline provenance: Git 3ca3f7a63cd107527ab6b7b1ead2af651407d109 execution/api.py,
# plus ONLY approved same-object feature_view_components API export
# (architecture R2 handoff13aed9ec); all five other base AST pins unchanged.
DEFAULT_OFF_AST_SHA256={'src/automl/contracts/messages.py': '0b50cd6f2586376e111df718e872b6dd0dfc7b98842ef68b3b25b8faf7269f42', 'src/automl/execution/api.py': '2f5a5a753da784e3c2ea30c4629e0427ca41743ba86b16b591c7ad1e02317fab', 'src/automl/execution/worker.py': 'ea1ba7f6270ced919a4f04ef50b80725af86068722a38573ab3a61fb3b9b324e', 'src/automl/search/policy.py': 'e38eeb0f02fd1f7cb135f2fde0ecdb7783fa5ce7f83813d662bb1750fc851ba7', 'src/automl/execution/model_adapters/lightgbm.py': '4eada9d5b315883c3351aae43c49f7b03052b01a2211ded5610679d34aed9041', 'src/automl/execution/model_adapters/registry.py': 'eb22c05f60f80d7307d8507a8a42ebd607cd47656556044f6bd29af9cc3dd2d1'}
LEGACY_CAPABILITIES_SHA256='956827b308970db4f31a0827e203c4fd86c3ebbd24453d2f9f605d690a907249'

class LegacyOffProjection(ast.NodeTransformer):
    loss_names={'LossProfile','LOSS_PROFILES','loss_profile_catalog','resolve_loss_profile',
                'validate_loss_profiles','loss_profile_fit_receipt'}
    def visit_ImportFrom(self,node):
        node.names=[v for v in node.names if v.name not in self.loss_names]
        return node if node.names else None
    def visit_ClassDef(self,node):
        return None if node.name in self.loss_names else self.generic_visit(node)
    def visit_FunctionDef(self,node):
        return None if node.name in self.loss_names else self.generic_visit(node)
    def visit_Assign(self,node):
        if any(isinstance(v,ast.Name) and v.id in {'LOSS_PROFILES','loss_profile'} for v in node.targets):
            return None
        return self.generic_visit(node)
    def visit_Expr(self,node):
        value=node.value
        if isinstance(value,ast.Call):
            if isinstance(value.func,ast.Name) and value.func.id in self.loss_names:return None
            if (isinstance(value.func,ast.Attribute) and isinstance(value.func.value,ast.Name)
                    and value.func.value.id=='PARAMETERS' and value.func.attr=='add'
                    and len(value.args)==1 and isinstance(value.args[0],ast.Constant)
                    and value.args[0].value=='loss_profile_id'):return None
        return self.generic_visit(node)
    def visit_If(self,node):
        if any(isinstance(v,ast.Name) and v.id=='loss_profile' for v in ast.walk(node.test)):
            return None
        if any(isinstance(v,ast.Constant) and v.value=='loss_profile_id' for v in ast.walk(node.test)):
            return None
        return self.generic_visit(node)
    def visit_BinOp(self,node):
        if (isinstance(node.op,ast.Sub) and isinstance(node.right,ast.Set)
                and len(node.right.elts)==1 and isinstance(node.right.elts[0],ast.Constant)
                and node.right.elts[0].value=='loss_profile_id'):
            return self.visit(node.left)
        return self.generic_visit(node)
    def visit_Set(self,node):
        node.elts=[v for v in node.elts if not (isinstance(v,ast.Constant) and v.value=='loss_profile_id')]
        return self.generic_visit(node)


def recipe(profile=None,**params):
    values=dict(iterations=20,min_child_samples=5,num_leaves=15,seed=42,early_metric='primary')
    values.update(params)
    if profile is not None:values['loss_profile_id']=profile
    return dict(engine='lightgbm',params=values,feature_code='')


class NoNetwork(unittest.TestCase):
    def setUp(self):
        self.network_attempts=[]
        def blocked(*args,**kwargs):
            self.network_attempts.append(True);raise AssertionError('UAR loss contracts network is forbidden')
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

    def test_ordinary_advertised_capabilities_equal_base_UAR(self):
        actual=json.dumps(CAPABILITIES,sort_keys=True,separators=(',',':')).encode()
        self.assertEqual(hashlib.sha256(actual).hexdigest(),LEGACY_CAPABILITIES_SHA256)
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

    def test_default_OFF_all_six_modules_preserve_base_UAR_AST(self):
        from automl.execution import api as public_execution
        from automl.execution.feature_views import feature_view_components
        self.assertIs(public_execution.feature_view_components,feature_view_components)
        for path,expected in DEFAULT_OFF_AST_SHA256.items():
            with self.subTest(path=path):
                tree=LegacyOffProjection().visit(ast.parse((ROOT/path).read_text('utf-8')))
                actual=hashlib.sha256(ast.dump(tree,include_attributes=False).encode()).hexdigest()
                self.assertEqual(actual,expected)
        for kind in ['regression','classification']:
            model=create_model(recipe(class_weight_power=.5),kind,1,20)
            self.assertEqual(model.get_params()['metric'],'None')
            self.assertNotIn('loss_profile_id',model.get_params())
        frame=pd.DataFrame({'x':[0.,1.,2.]});y=pd.Series([1.,2.,3.])
        task=dict(kind='regression',metric='rmse',greater_is_better=False)
        options=fit_options(task,recipe(),frame,y,np.array([2]),[],True)
        self.assertEqual(set(options),{'eval_set','callbacks','eval_metric'})
        name,value,direction=options['eval_metric'](np.log1p([2.,3.]),np.log1p([1.,4.]))
        self.assertEqual(name,'rmse');self.assertFalse(direction)
        self.assertAlmostEqual(value,1.,places=12)

    def test_ensemble_inventory_retains_leaf_loss_receipts_and_iteration_tree(self):
        proof=loss_profile_fit_receipt(recipe('lgbm_l1_v1'),'regression',
            SimpleNamespace(booster_=SimpleNamespace(params={'objective':'regression_l1','metric':'None'})))
        proof.update(model_scope='full_refit',fit_index=1,primary_metric='rmse',target_scale='original')
        parent=dict(engine='ensemble',params={},components=[recipe('lgbm_l1_v1'),recipe()],weights=[.75,.25])
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);np.savez(out/'split.npz',train=np.array([0,1]),validation=np.array([2]))
            expected=[]
            def fake_leaf(job):
                index=len(expected);self.assertEqual(job['fit_iterations'],[31,47][index])
                record=dict(status='ok',recipe=job['recipe'],full_fit=True,metrics=None,
                            fit_iterations=job['fit_iterations'],feature_count=2,data_policy_runs=[{}])
                if index==0:
                    record['data_policy_runs'][0]['loss_profile']=deepcopy(proof)
                    record.update(loss_profile_id='lgbm_l1_v1',effective_loss_profile=deepcopy(proof))
                expected.append(record)
                (Path(job['output_dir'])/'result.json').write_text(json.dumps(record),encoding='utf-8')
            spec=dict(kind='regression',paths={'train':'train','test':'test'})
            with patch.object(worker,'run',side_effect=fake_leaf), \
                 patch.object(worker,'read_input_table',return_value=pd.DataFrame({'x':[1.,2.]})), \
                 patch.object(worker,'read_task_sample',return_value=pd.DataFrame()), \
                 patch.object(worker,'read_submission_values',return_value=np.array([1.,2.])), \
                 patch.object(worker,'save_submission'):
                worker.run_ensemble(dict(recipe=parent,spec=spec,output_dir=str(out),
                    split_path=str(out/'split.npz'),threads=1,full_fit=True,fit_iterations=[31,47]))
            record=json.loads((out/'result.json').read_text('utf-8'))
            self.assertEqual(record['components'],expected)
            self.assertEqual(record['fit_iterations'],[31,47])
            leaves=record['components']
            self.assertEqual(leaves[0]['data_policy_runs'][0]['loss_profile'],proof)
            self.assertNotIn('loss_profile',leaves[1]['data_policy_runs'][0])
            self.assertNotIn('effective_loss_profile',record)


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
