"""Prepared native-value/mock instrumentation contracts. No model is fitted.

Synthetic native bytes are fixture inputs, not a real runtime/native authority.
Only the actual worker helper definitions are projected; importing the worker
module itself (and its learner dependencies) is deliberately unnecessary.
"""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType,SimpleNamespace
import unittest
from unittest.mock import patch

PACKET=Path(__file__).resolve().parent.parent


class WorkerIdentityContracts(unittest.TestCase):
    def helpers(self):
        import numpy as np
        import pandas as pd
        source=PACKET/'src/automl/execution/worker.py'
        selected={'_bank_value','_bank_before_fit','_bank_after_fit'}
        nodes=[n for n in ast.parse(source.read_text('utf-8')).body if isinstance(n,ast.FunctionDef) and n.name in selected]
        self.assertEqual({n.name for n in nodes},selected)
        path=PACKET/'src/automl/infrastructure/hpo_bank.py'
        spec=importlib.util.spec_from_file_location('_producer_native_contract_target',path)
        bank=importlib.util.module_from_spec(spec);spec.loader.exec_module(bank)
        namespace=dict(np=np,pd=pd)
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(source),'exec'),namespace)
        modules={'automl':ModuleType('automl'),'automl.infrastructure':ModuleType('automl.infrastructure'),
            'automl.infrastructure.hpo_bank':bank}
        return namespace,bank,modules,np,pd

    def test_actual_prepared_value_encoder_preserves_order_dtype_missing_categories_and_weight_values(self):
        helpers,bank,modules,np,pd=self.helpers();calls=[]
        with patch.dict(sys.modules,modules):
            value=lambda x:helpers['_bank_value'](x,lambda:calls.append(True))
            frame=pd.DataFrame({'x':np.array([1.,np.nan],dtype=np.float64),
                'category':pd.Categorical(['001','NA'],categories=['NA','001'],ordered=True)},index=[10,20])
            baseline=value(frame)
            changed=frame.copy();changed['x']=changed['x'].astype('float32')
            self.assertNotEqual(baseline,value(changed))
            changed=frame.iloc[::-1].copy();self.assertNotEqual(baseline,value(changed))
            changed=frame.copy();changed['x']=changed['x'].fillna(0.);self.assertNotEqual(baseline,value(changed))
            changed=frame.copy();changed['category']=changed['category'].cat.reorder_categories(['001','NA'])
            self.assertNotEqual(baseline,value(changed))
            self.assertNotEqual(value(np.array([1.,2.])),value(np.array([2.,1.])))
            self.assertNotEqual(value(np.array([0.])),value(np.array([-0.])))
            self.assertNotEqual(value(np.array(['001','NA'],dtype=object)),value(np.array(['NA','001'],dtype=object)))
            self.assertIsInstance(baseline['vectors'][0]['values']['sha256'],str)
            self.assertNotIn('NaN',json.dumps(baseline,allow_nan=False));self.assertTrue(calls)
            with self.assertRaises(bank.BankRejected):value(object())

    def test_actual_fit_hooks_separate_stopping_X_y_positions_and_capture_effective_without_fitting(self):
        helpers,bank,modules,np,pd=self.helpers()
        with tempfile.TemporaryDirectory() as tmp,patch.dict(sys.modules,modules):
            native_path=Path(tmp).resolve()/'synthetic-native.bin';native_path.write_bytes(b'synthetic native witness')
            files={str(native_path):hashlib.sha256(native_path.read_bytes()).hexdigest()}
            native=dict(files=files,python={'implementation':'synthetic'},threads=[],environment={})
            job={'_hpo_trial_bank':dict(schema='hpo-trial-bank-worker-request-v1',epoch_id='a'*64,native_refs=files,leaf_path=[])}
            recorder=bank.FitIdentityRecorder(job,lambda:None)
            helpers['_bank_native']=lambda actual:dict(native)
            class Estimator:
                booster_=SimpleNamespace(params={'objective':'regression','num_threads':2},feature_name=lambda:['x'],
                    current_iteration=lambda:17,num_trees=lambda:17)
                best_iteration_=17
                def get_params(self,deep=False):return {'n_jobs':2,'random_state':7}
                def fit(self,*args,**kwargs):raise AssertionError('SOURCE contract cannot fit a learner')
            estimator=Estimator();x=pd.DataFrame({'x':[2.,3.]},index=[0,1]);y=pd.Series([4.,5.],index=[0,1])
            vx=pd.DataFrame({'x':[7.]},index=[2]);vy=pd.Series([8.],index=[2])
            token=helpers['_bank_before_fit'](recorder,estimator,x,y,np.array([1.,2.]),np.array([0,1]),
                {'eval_set':[(vx,vy)],'eval_metric':'rmse'},'inner',np.array([0,1]),np.array([2]))
            helpers['_bank_after_fit'](recorder,token,estimator)
            receipt=recorder.receipt();node=receipt['nodes'][0]
            self.assertTrue(receipt['complete']);self.assertIsNone(receipt['actual_recursive_learner_fits'])
            self.assertEqual(node['identity']['validation_x'],[helpers['_bank_value'](vx,lambda:None)])
            self.assertEqual(node['identity']['validation_y'],[helpers['_bank_value'](vy,lambda:None)])
            self.assertIn('original_fitting_positions',node['identity']['fit_settings'])
            self.assertIn('original_validation_positions',node['identity']['fit_settings'])
            self.assertEqual(node['effective']['best_iteration'],17)
            self.assertEqual(node['effective']['actual_iteration_count'],17)
            self.assertEqual(node['effective']['actual_tree_count'],17)
            self.assertEqual(node['effective']['native']['files'],files)
            self.assertFalse(bank.supported_recipe({'engine':'lightgbm','params':{'feature_selection_top_k':32}}))
            self.assertFalse(bank.supported_recipe({'engine':'catboost','params':{}}))
            self.assertTrue(bank.supported_recipe({'engine':'lightgbm','params':{'feature_views':'categorical_te_pair'}}))

    def test_actual_parent_retains_observed_birth_tuple_after_terminal_members_removed_before_qualification(self):
        helpers,bank,modules,np,pd=self.helpers()
        source=PACKET/'src/automl/search/runner.py'
        node=next(n for n in ast.parse(source.read_text('utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='_run_worker_strict')
        with tempfile.TemporaryDirectory() as tmp,patch.dict(sys.modules,modules):
            root=Path(tmp).resolve();events=[];observed=[]
            class Process:
                pid=1234
                returncode=0
                def poll(self):return 0
            class Tree:
                def __init__(self,process,strict_observation):
                    self.members={(1234,10.25):process};self.strict_observation=strict_observation
                def refresh(self):self.members.clear();events.append('terminal_members_removed')
            class Producer:
                def worker_request(self,job,deadline):return {'synthetic':True}
                def qualify_parent(self,result,**proof):
                    self_test.assertEqual(events[-1],'cleanup_confirmed')
                    observed.extend(proof['process_identities']);self_test.assertTrue(proof['cleanup_confirmed'])
                    self_test.assertEqual(proof['actual_exit_code'],0);events.append('qualified');return result
            self_test=self;producer=Producer()
            def atomic(path,value):path.write_text(json.dumps(value),encoding='utf-8')
            def popen(*args,**kwargs):
                atomic(root/'trial/result.json',{'status':'ok','metrics':{'rmse':2.5},'fit_iterations':17})
                return Process()
            namespace=dict(Path=Path,np=np,json=json,time=SimpleNamespace(monotonic=lambda:100.,sleep=lambda x:None),
                _hpo_trial_bank_checkpoint=lambda:None,_selector_cache_job=lambda job:job,
                _HPO_TRIAL_BANK_ACTIVE=SimpleNamespace(get=lambda:producer),_HPO_FAIR_RESERVE_PROVENANCE=SimpleNamespace(get=lambda:False),
                ExperimentRequest=lambda *args:SimpleNamespace(validate=lambda:None),THREADS=2,atomic_json=atomic,
                os=SimpleNamespace(environ={}),sys=SimpleNamespace(executable='SYNTHETIC_NO_PROCESS'),
                subprocess=SimpleNamespace(Popen=popen,TimeoutExpired=TimeoutError),worker_entrypoint=lambda:root/'synthetic-worker.py',
                ProcessTree=Tree,ResourceBudget=lambda:SimpleNamespace(inspect_artifacts=lambda directory:0),
                ProcessCleanupError=type('MockCleanupError',(RuntimeError,),{}),
                ProcessObservationError=type('MockObservationError',(RuntimeError,),{}),
                psutil=SimpleNamespace(AccessDenied=PermissionError,NoSuchProcess=ProcessLookupError),
                _strict_worker_cleanup=lambda *args:events.append('cleanup_confirmed'))
            exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(source),'exec'),namespace)
            result=namespace['_run_worker_strict']({'root':str(root)},{'engine':'lightgbm'},root/'trial',root/'split.bin',60)
            self.assertEqual(result['status'],'ok');self.assertEqual(observed,[{'pid':1234,'create_time':10.25}])
            self.assertLess(events.index('terminal_members_removed'),events.index('cleanup_confirmed'))
            self.assertLess(events.index('cleanup_confirmed'),events.index('qualified'))


if __name__=='__main__':unittest.main()
