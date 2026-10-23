"""Prepared pure/mock LOSS seed contracts; author execution count is zero.

No public rows, estimator fitting, API calls or real experiment clocks.
The mocked runner case validates failure/null lineage, not full-agent quality.
"""
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import numpy as np
import pandas as pd
from automl.search import runner
from automl.search.policy import normalize,signature
from automl.search.stages import LOSS_SEED_PROFILE_ID,make_loss_seed_l1_recipe,prepare_preserved_four_stage_recipes
from automl.execution.model_adapters.registry import CAPABILITIES,effective_parameters


def single(engine='lightgbm',**params):
    return normalize(dict(engine=engine,hypothesis='synthetic seed contract',feature_code='',params=params))


def fixture():
    task=dict(kind='regression',metric='rmse',greater_is_better=False,text_features=[],features=['period','cat','num'],
        categorical_features=['cat'],time_column='period',validation_strategy='time',time_candidate={'representation':'numeric','split_mode':'period'})
    control=json.loads((ROOT/'tests/fixtures/protected_control_regression.json').read_text('utf-8'))
    champion=json.loads((ROOT/'tests/fixtures/cp1_champion_regression.json').read_text('utf-8'))
    base=[control['components'][0],single('catboost'),single('xgboost')]
    plans=[single(reg_lambda=11),single(reg_lambda=17)]
    return task,base,plans,control,champion


class LossSeedContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=ROOT/'tests/fixtures/cp1_stages.py'
        expected=json.loads((ROOT/'tests/fixtures/loss_seed_cp1_fixture_sha.json').read_text('utf-8'))['stages']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==expected
        module=importlib.util.spec_from_file_location('_frozen_CP1_loss_seed_fixture',path)
        cls.cp1=importlib.util.module_from_spec(module);module.loader.exec_module(cls.cp1)

    def setUp(self):
        self.network_attempts=[]
        def forbidden(*args,**kwargs):self.network_attempts.append(True);raise AssertionError('Network forbidden')
        self.network=[patch.object(socket,n,side_effect=forbidden) for n in ['create_connection','getaddrinfo']]
        self.network += [patch.object(socket.socket,n,side_effect=forbidden) for n in ['connect','connect_ex','sendto']]
        for item in self.network:item.start()
    def tearDown(self):
        for item in reversed(self.network):item.stop()
        self.assertEqual(self.network_attempts,[])

    def test_default_OFF_regression_matches_frozen_CP1_champion_scheduler(self):
        task,base,plans,control,champion=fixture()
        expected=self.cp1.prepare_preserved_four_stage_recipes(task,base,plans,control,champion=champion)
        self.assertEqual(prepare_preserved_four_stage_recipes(task,base,plans,control,champion=champion),expected)
        self.assertEqual(prepare_preserved_four_stage_recipes(task,base,plans,control,champion=champion,loss_seed_l1=False),expected)

    def test_default_OFF_classification_scheduler_unchanged(self):
        task=dict(kind='classification',metric='macro_f1',text_features=[],features=['x'])
        base=[single(),single('catboost'),single('xgboost')]
        control=dict(engine='ensemble',params={},components=[base[0],base[2]],weights=[.5,.5])
        plans=[single(reg_lambda=11),single(reg_lambda=17)]
        self.assertEqual(prepare_preserved_four_stage_recipes(task,base,plans,control),self.cp1.prepare_preserved_four_stage_recipes(task,base,plans,control))

    def test_raw_constructor_changes_only_fixed_profile_and_preserves_narrative(self):
        task,_,_,control,_=fixture();before=deepcopy(control)
        value=make_loss_seed_l1_recipe(task,control)
        self.assertEqual(value['params'].pop('loss_profile_id'),LOSS_SEED_PROFILE_ID)
        self.assertEqual(value,control['components'][0]);self.assertEqual(control,before)
        changed=deepcopy(control);changed['components'][0]['hypothesis']='Different bounded description'
        second=make_loss_seed_l1_recipe(task,changed)
        self.assertEqual(second['hypothesis'],'Different bounded description')
        self.assertEqual(signature(make_loss_seed_l1_recipe(task,control)),signature(second))

    def test_actual_measured_template_equals_raw_constructor_with_no_other_parameters(self):
        task,_,_,control,_=fixture()
        expected=json.loads((ROOT/'tests/fixtures/fixed_l1_seed_template.json').read_text('utf-8'))
        actual=make_loss_seed_l1_recipe(task,control)
        self.assertEqual(actual,expected)
        self.assertEqual(signature(actual),signature(normalize(deepcopy(actual))))
        self.assertNotEqual(signature(actual),signature(control['components'][0]))

    def test_slot6_preserves_first6_and_replaces_optional_initial_Qwen(self):
        task,base,plans,control,champion=fixture()
        old=self.cp1.prepare_preserved_four_stage_recipes(task,base,plans,control,champion=champion)
        queue,receipts,anchor=prepare_preserved_four_stage_recipes(task,base,plans,control,champion=champion,loss_seed_l1=True)
        self.assertEqual(queue[:6],old[0][:6]);self.assertEqual(anchor,old[2])
        self.assertEqual(len(queue),7);self.assertEqual(9-len(queue),2)
        self.assertEqual(queue[5],normalize(champion));self.assertEqual(queue[6],make_loss_seed_l1_recipe(task,control))
        seed=next(r for r in receipts if r['source']=='fixed_regression_loss_seed')
        self.assertEqual(seed['queue_index'],6);self.assertEqual(seed['signature'],signature(queue[6]))
        self.assertEqual(seed['loss_profile_id'],LOSS_SEED_PROFILE_ID)
        self.assertEqual(sum(r['source']=='qwen' and r['status']=='not_scheduled_initial_capacity' for r in receipts),2)
        self.assertEqual({r['engine'] for r in queue[:5]},{'ensemble','lightgbm','catboost','xgboost'})

    def test_profile_duplicate_proposal_never_consumes_another_fit_slot(self):
        task,base,_,control,champion=fixture();seed=make_loss_seed_l1_recipe(task,control)
        plans=[deepcopy(seed),single(reg_lambda=19)]
        queue,receipts,_=prepare_preserved_four_stage_recipes(task,base,plans,control,champion=champion,loss_seed_l1=True)
        self.assertEqual(sum(signature(r)==signature(seed) for r in queue),1)
        self.assertTrue(any(r['source']=='qwen' and r['status']=='duplicate' and r['signature']==signature(seed) for r in receipts))

    def test_unprofiled_HPO_anchor_and_separate_protected_broad_branch_remain(self):
        task,base,plans,control,champion=fixture()
        queue,_,anchor=prepare_preserved_four_stage_recipes(task,base,plans,control,champion=champion,loss_seed_l1=True)
        self.assertEqual(anchor,control['components'][0]);self.assertNotIn('loss_profile_id',anchor['params'])
        broad=[r for r in queue if r.get('params',{}).get('feature_selection_top_k')]
        self.assertEqual(len(broad),1);self.assertEqual(broad[0]['params']['generic_features'],'broad')
        self.assertTrue(broad[0]['params']['feature_selection_protect_original'])
        self.assertNotIn('loss_profile_id',broad[0]['params'])
        self.assertEqual(queue[6]['params']['generic_features'],anchor['params']['generic_features'])

    def test_seed_queue_copies_do_not_alias_control_champion_or_prior_inputs(self):
        task,base,plans,control,champion=fixture();before=deepcopy((task,base,plans,control,champion))
        queue,_,anchor=prepare_preserved_four_stage_recipes(task,base,plans,control,champion=champion,loss_seed_l1=True)
        queue[0]['components'][0]['params']['reg_lambda']=100
        queue[5]['params']['learning_rate']=.2;queue[6]['params']['num_leaves']=15;anchor['params']['seed']=999
        self.assertEqual((task,base,plans,control,champion),before)

    def test_incompatible_kind_scope_control_or_partial_budget_rejected(self):
        task,base,plans,control,champion=fixture()
        for bad in [dict(task,kind='classification',metric='macro_f1'),dict(task,text_features=['num']),dict(task,task_family='pointwise_ranking'),dict(task,metric='mae')]:
            with self.subTest(task=bad),self.assertRaises(ValueError):make_loss_seed_l1_recipe(bad,control)
        for change in [('engine','xgboost'),('loss_profile_id','lgbm_l2_v1'),('nested_stopping',False),('early_metric','loss')]:
            bad=deepcopy(control)
            if change[0]=='engine':bad['components'][0]['engine']=change[1]
            else:bad['components'][0]['params'][change[0]]=change[1]
            with self.subTest(change=change),self.assertRaises(ValueError):make_loss_seed_l1_recipe(task,bad)
        for cap in [5,6,8]:
            with self.subTest(cap=cap),self.assertRaises(ValueError):prepare_preserved_four_stage_recipes(task,base,plans,control,maximum_initial=cap,champion=champion,loss_seed_l1=True)
        with self.assertRaises(ValueError):prepare_preserved_four_stage_recipes(task,base,plans,control,loss_seed_l1=True)
        with self.assertRaisesRegex(ValueError,'distinct prior champion'):
            prepare_preserved_four_stage_recipes(task,base,plans,control,champion=control['components'][0],loss_seed_l1=True)

    def test_normalizer_cannot_silently_change_raw_executable_package(self):
        task,_,_,control,_=fixture();bad=deepcopy(control);bad['components'][0]['params'].pop('min_iterations')
        with self.assertRaisesRegex(ValueError,'normalization'):make_loss_seed_l1_recipe(task,bad)
        bad=deepcopy(control);bad['components'][0]['params']['objective']='regression'
        with self.assertRaises(ValueError):make_loss_seed_l1_recipe(task,bad)
        bad=deepcopy(control);bad['components'][0]['feature_code']='out["x"] = 1'
        with self.assertRaises(ValueError):make_loss_seed_l1_recipe(task,bad)

    def test_CLI_invalid_admission_fails_before_RunBudget_and_IO(self):
        args=['loss-seed','--task','task.md','--four-stage','--preserve-anchor','--control-recipe','control.json',
              '--champion-recipe','champion.json','--max-experiments','9','--hpo-trials','8','--max-planner-calls','2','--loss-seed-l1']
        for name,value in [('--max-experiments','10'),('--hpo-trials','7'),('--max-planner-calls','1')]:
            bad=list(args);bad[bad.index(name)+1]=value
            with patch.object(sys,'argv',bad),patch.object(sys,'stderr',io.StringIO()),patch.object(runner,'RunBudget',side_effect=AssertionError('Budget must not start')):
                with self.subTest(name=name),self.assertRaises(SystemExit):runner._main()

    def test_mocked_failed_seed_keeps_snapshot_signature_and_null_measurements(self):
        task,_,_,control,champion=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);train=pd.DataFrame({'id':np.arange(30),'period':np.arange(30),'cat':['a','b']*15,'num':np.arange(30),'target':np.arange(30,dtype=float)})
            test=train.iloc[:3].drop(columns='target').copy();test['id']=[101,102,103]
            sample=pd.DataFrame({'id':[103,101,102],'target':[0.,0.,0.]})
            for name,frame in [('train',train),('test',test),('sample_submission',sample)]:frame.to_csv(root/(name+'.csv'),index=False)
            for name,value in [('control',control),('champion',champion)]: (root/(name+'.json')).write_text(json.dumps(value),encoding='utf-8')
            (root/'task.md').write_text('Synthetic contract task only',encoding='utf-8')
            task=dict(task,root=str(root),task_path=str(root/'task.md'),target='target',id='id',classes=[],prediction_type='value',output_columns=['target'],sample_test_positions=[2,0,1],paths={n:str(root/(n+'.csv')) for n in ['train','test','sample_submission']})
            args=SimpleNamespace(task=root/'task.md',validation_strategy='auto',run_name='mock-loss-seed',time_budget=3000,
                preserve_anchor=True,four_stage=True,control_recipe=root/'control.json',champion_recipe=root/'champion.json',
                loss_seed_l1=True,max_experiments=9,max_planner_calls=2,hpo_trials=8,hpo_budget=900,hpo_sampler='tpe',
                feature_selection_top_k=32,protect_original_features=True,offline=True,planner_mode='staged')
            def failed(spec,recipe,directory,split,seconds):
                return dict(status='error',recipe=deepcopy(recipe),metrics=None,output_dir=str(directory),wall_seconds=0.,error='synthetic_failure')
            with patch.object(runner,'choose_validation',side_effect=lambda s,*a:s),patch.object(runner,'source_files',return_value=[]),patch.object(runner,'make_split',return_value=(np.arange(20),np.arange(20,30),{'strategy':'synthetic'})),patch.object(runner,'run_worker',side_effect=failed),patch.object(runner,'request_json',side_effect=AssertionError('No API')),patch.object(runner,'llm_plan',side_effect=AssertionError('No API')):
                report=runner.solve_single(args,(task,{},train,test,sample,'',np.arange(30,dtype=np.uint64)))
            expected=make_loss_seed_l1_recipe(task,control)
            self.assertEqual(report['loss_seed_recipe'],expected)
            self.assertEqual(report['pipeline']['hpo_single_anchor_signature'],signature(control['components'][0]))
            primary=report['loss_seed_measurements']['primary'];self.assertEqual(primary['status'],'error');self.assertIsNone(primary['metrics'])
            self.assertIsNone(report['loss_seed_measurements']['confirmation']);self.assertIsNone(report['best_validation'])
            runs=root/'automl_runs/mock-loss-seed';receipt=json.loads((runs/'loss-seed.json').read_text('utf-8'))
            snapshot=runs/'loss_seed_recipe.json'
            self.assertEqual(receipt['snapshot_sha256'],hashlib.sha256(snapshot.read_bytes()).hexdigest())
            self.assertEqual(receipt['recipe_signature'],signature(expected));self.assertIsNone(receipt['metric'])
            self.assertEqual(receipt['measurement_status'],'not_run')
            self.assertNotIn('loss_profile_id',CAPABILITIES['lightgbm']['parameters'])
            self.assertEqual(effective_parameters('lightgbm',expected['params'])['loss_profile_id'],LOSS_SEED_PROFILE_ID)


if __name__=='__main__':unittest.main(verbosity=2)
