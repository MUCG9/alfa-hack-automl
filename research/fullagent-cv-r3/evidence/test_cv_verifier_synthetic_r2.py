"""Scoped saved-artifact contracts; no real outcomes, learners or network."""
from pathlib import Path
import hashlib, importlib.abc, importlib.util, json, os, socket, subprocess, sys, time, unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','AUTOML_THREADS']:
    os.environ[key]='1'
WORK=Path(__file__).resolve().parent
SOURCE=WORK/'verify_fullagent_cv.py'
EXPECTED='33f98e1bdb44743b8b55e7e694459c2dc2c19dd5db8359c51747cc5c62274519'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==EXPECTED
COUNTS={'network':0,'process_launch':0,'learner_import':0}
def forbidden(kind):
    def reject(*args,**kwargs):
        COUNTS[kind]+=1
        raise AssertionError('Forbidden '+kind)
    return reject
socket.socket.connect=forbidden('network')
socket.create_connection=forbidden('network')
subprocess.Popen=forbidden('process_launch')
class DenyLearners(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in {'lightgbm','catboost','xgboost','optuna','sklearn'}:
            COUNTS['learner_import']+=1
            raise AssertionError('Forbidden learner import')
sys.meta_path.insert(0,DenyLearners())
spec=importlib.util.spec_from_file_location('frozen_cv_verifier',SOURCE)
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
np,pd=v.np,v.pd
BASE=WORK/'vs2'
BASE.mkdir(exist_ok=False)
DETAILS=[]

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes((json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode('utf-8'))
def split_rule(spec,frame,hashes,seed):
    n=len(frame);half=n//2
    tr,va=np.arange(half),np.arange(half,n)
    if seed==43:tr,va=va,tr
    info={'method':'synthetic_fixed_no_fit','seed':seed,'train_rows':len(tr),'validation_rows':len(va),
          'split_sha256':hashlib.sha256(np.asarray(tr,dtype='<i8').tobytes()+np.asarray(va,dtype='<i8').tobytes()).hexdigest(),
          'shared_feature_hashes':0,'validation_class_counts':frame.iloc[va][spec['target']].value_counts().to_dict()}
    return tr,va,info

class Fixture:
    def __init__(self,number):
        self.root=BASE/str(number);self.root.mkdir()
        self.classes=['A','B','C'];self.events=[]
        self.source=pd.DataFrame({'id':np.arange(18),'x':np.arange(18,dtype=float),
            'cat1':np.tile(['a','b','c'],6),'cat2':np.tile(['u','v'],9),'target':np.tile(self.classes,6)})
        self.features=['x','cat1','cat2']
        self.source_path=self.root/'evaluation/multiclass/train.csv';self.source_path.parent.mkdir(parents=True)
        self.source.to_csv(self.source_path,index=False)
        self.hashes=pd.util.hash_pandas_object(self.source[self.features],index=False).to_numpy(dtype='uint64')
        self.arrays={'raw_feature_hashes':self.hashes}
        for fold in range(3):
            va=np.arange(fold*6,(fold+1)*6);self.arrays[f'fold{fold}_validation']=va
            self.arrays[f'fold{fold}_train']=np.setdiff1d(np.arange(18),va)
        self.folds={'row_count':18,'canonical_class_order':self.classes,'target_column':'target','id_column':'id',
            'raw_feature_schema_order':self.features,'pristine_input_sha256':{'evaluation/multiclass/train.csv':v.digest(self.source_path)},'folds':[]}
        self.plan={'common_absolute_deadline_unix':time.time()+600,'common_deadline_monotonic':time.monotonic()+600,
            'manifest_sha256':'synthetic-not-a-production-manifest','stage_receipt_path':'stage.json'}
        self.stage={'common_start_unix':self.plan['common_absolute_deadline_unix']-64800,
            'common_start_monotonic':self.plan['common_deadline_monotonic']-64800,'arms':[]}
        self.archives={};self.slots=[];self.reports={}
        for arm in ['a','b']:self.arm(arm)
        for fold,arm in v.ORDER:
            if fold==0:self.stage['arms'].append(self.slots[0 if arm=='a' else 1])
            else:self.stage['arms'].append({'fold':fold,'arm':arm,'status':'not_attempted','metrics':None,
                'outer_predictions_sha256':None,'final_refit_status':None,'final_csv_sha256':None})
        self.save_stage()
    def save_stage(self):write(self.root/'stage.json',self.stage)
    def arm(self,arm):
        root=self.root/('0'+arm);root.mkdir();runs=root/'automl_runs/run-v2';runs.mkdir(parents=True)
        fit=self.arrays['fold0_train'];outer=self.arrays['fold0_validation']
        train=self.source.iloc[fit].reset_index(drop=True);test=self.source.iloc[outer].drop(columns='target').reset_index(drop=True)
        sample=pd.DataFrame({'id':test.id,'target':'A'})
        dictionary=pd.DataFrame({'feature':self.source.columns,'dtype':['id','numeric','category','category','target']})
        for frame,name in [(train,'train.csv'),(test,'test.csv'),(sample,'sample_submission.csv'),(dictionary,'data_dictionary.csv')]:frame.to_csv(root/name,index=False)
        (root/'task.md').write_text('Synthetic classification Macro F1.',encoding='utf-8')
        (root/'solution.py').write_text('# Synthetic archive stand-in; never executed.\n',encoding='utf-8')
        self.archives[arm]={'solution.py':v.digest(root/'solution.py')}
        spec={'kind':'classification','metric':'macro_f1','classes':self.classes,'features':self.features,
            'target':'target','id':'id','prediction_type':'label','output_columns':['target'],'categorical_features':['cat1','cat2'],
            'duplicate_feature_rate':0.,'validation_strategy':'auto','root':str(root),
            'paths':{role:str(root/name) for role,name in [('train','train.csv'),('test','test.csv'),('sample_submission','sample_submission.csv'),('data_dictionary','data_dictionary.csv')]}}
        tr,va,_=split_rule(spec,train,None,42);np.savez(runs/'split.npz',train=tr,validation=va)
        source_hashes=pd.util.hash_pandas_object(train[self.features],index=False).to_numpy(dtype='uint64')
        def node(folder,recipe,iterations,full=False):
            folder.mkdir(parents=True,exist_ok=True)
            scopes=np.arange(len(train)) if full else tr
            validation=None if full else va
            testp=np.eye(3)[outer%3]*.8+.2/3
            valp=None if full else np.eye(3)[train.target.iloc[va].map(dict(zip(self.classes,range(3)))).to_numpy()]*.8+.2/3
            result={'status':'ok','recipe':recipe,'full_fit':full,'fit_iterations':iterations,'metrics':{} if full else {'macro_f1':1.}}
            if recipe.get('params',{}).get('feature_views'):
                children=v.view_children(recipe,spec)
                result['components']=[]
                for i,child in enumerate(children):result['components'].append(node(folder/('component-'+str(i)),child,iterations[i],full))
                result['feature_views']={'method':v.FIXED,'weights':[.25]*4,'groups':children[1]['params']['target_encoding_groups'],'iteration_tree':iterations}
            else:
                result['data_policy_runs']=[{'source_parent_sha256':v.canonical(scopes.tolist()),'source_rows':len(scopes)}]
                if recipe['engine']=='lightgbm':result.update(inner_split=split_rule(spec,train.iloc[scopes].reset_index(drop=True),source_hashes[scopes],73)[2],
                    early_stopping_source='inner_training_holdout',calibration_status='inner_training_holdout_matching_iterations')
                else:result['inner_split']=None
            np.savez(folder/'test_probabilities.npz',classes=self.classes,probabilities=testp)
            sample.assign(target=np.asarray(self.classes)[testp.argmax(axis=1)]).to_csv(folder/'submission.csv',index=False)
            if not full:
                np.savez(folder/'validation_probabilities.npz',classes=self.classes,probabilities=valp,row_position=va)
                pd.DataFrame({'row_position':va,'y_true':train.target.iloc[va].to_numpy(),'y_pred':np.asarray(self.classes)[valp.argmax(axis=1)]}).to_csv(folder/'validation_predictions.csv',index=False)
            write(folder/'result.json',result)
            write(folder/'job.json',{'recipe':recipe,'spec':spec,'threads':2,'full_fit':full,'split_path':str(runs/'split.npz'),'fit_iterations':iterations if full else None})
            return result
        records=[]
        for i in range(11):
            recipe={'engine':'extra_trees','params':{'synthetic_index':i}}
            if i==5:record={'status':'timeout','recipe':recipe,'metrics':None,'experiment_index':i}
            else:record=dict(node(runs/('experiment-'+str(i)),recipe,31+i),experiment_index=i,output_dir=str(runs/('experiment-'+str(i))))
            records.append(record)
        selected=records[0];iterations=31
        if arm=='b':
            recipe={'engine':'lightgbm','params':{'feature_views':v.FIXED,'num_leaves':63,'calibrate':True}}
            iterations=[31,41,51,61]
            selected=dict(node(runs/'experiment-11',recipe,iterations),experiment_index=11,output_dir=str(runs/'experiment-11'));records.append(selected)
        node(runs/'final-fit',selected['recipe'],iterations,True)
        (root/'submission.csv').write_bytes((runs/'final-fit/submission.csv').read_bytes())
        provenance={'task':v.digest(root/'task.md'),'source:'+str(root/'solution.py'):v.digest(root/'solution.py')}
        provenance.update({'input:'+role:v.digest(Path(path)) for role,path in spec['paths'].items()});write(runs/'provenance.json',{'sha256':provenance})
        report={'spec':spec,'final_fit_status':'ok','integrity_ok':True,'run_budget':{'gateway_call_limit':0,'gateway_calls_started':0,'http_attempts_reported':0},
            'llm_calls':[],'provenance_path':str(runs/'provenance.json'),'experiments':records,'confirmations':[],'selection':[],
            'selected_recipe':selected['recipe'],'final_fit_iterations':iterations,'submission_sha256':v.digest(root/'submission.csv')}
        self.reports[arm]=report;write(runs/'report.json',report)
        fold={'solver_inputs_sha256':{n:v.digest(root/n) for n in ['task.md','train.csv','test.csv','sample_submission.csv','data_dictionary.csv']},'excluded_rarest_class_frozen_before_scoring':'A'}
        if not self.folds['folds']:self.folds['folds'].append(fold)
        else:assert self.folds['folds'][0]==fold
        now=time.time();mono=time.monotonic()
        supervisor={'status':'ok','exit_code':0,'cleanup_confirmed':True,'owned_root':{'pid':999999,'create_time':1.},
            'owned_process_identities':[{'pid':999999,'create_time':1.}], 'API_limit':0,'maximum_logical_worker_jobs':1,
            'peak_owned_tree_rss_mib':1.,'start_unix':now-1,'end_unix':now,'start_monotonic':mono-1,'seconds':1.}
        superpath=self.root/('0'+arm+'-supervisor.json');write(superpath,supervisor)
        slot={'fold':0,'arm':arm,'status':'sealed_complete','exit_code':0,'cleanup_confirmed':True,'output_dir':str(root),
            'report_path':str(runs/'report.json'),'source_archive_sha256':v.ARCHIVE_SHA[arm],
            'command':['<same_python>','-u','solution.py','task.md','--offline','--max-llm-calls','0'],
            'supervisor':supervisor,'supervisor_sha256':v.canonical(supervisor),'supervisor_receipt_path':str(superpath),'supervisor_receipt_sha256':v.digest(superpath)}
        self.slots.append(slot);self.reseal(arm)
    def reseal(self,arm):
        slot=self.slots[0 if arm=='a' else 1];root=Path(slot['output_dir'])
        files={p.relative_to(root).as_posix():v.digest(p) for p in sorted(root.rglob('*')) if p.is_file()}
        seal={'root':str(root),'files_sha256':files,'sealed_unix':time.time()}
        slot.update(seal=seal,seal_sha256=v.canonical(seal),sealed=files)
        if self.stage.get('arms'):self.save_stage()
    def patch_context(self,*args):return self.root,self.archives,self.stage
    def patch_inputs(self,*args):self.events.append('outer_label_boundary');return self.arrays
    def audit(self):
        with patch.object(v,'context',side_effect=self.patch_context),patch.object(v,'frozen_inputs',side_effect=self.patch_inputs),\
             patch.object(v,'fresh_gone',return_value=None),patch.object(v,'expected_inner_split',side_effect=split_rule):
            return v.audit_pair(self.root,self.plan,self.slots,self.folds)

class Contracts(unittest.TestCase):
    serial=0
    def setUp(self):
        type(self).serial+=1;self.f=Fixture(type(self).serial)
    def tearDown(self):self.assertEqual(COUNTS,dict.fromkeys(COUNTS,0))
    def reject(self,code):
        with self.assertRaises(v.AuditError) as got:self.f.audit()
        self.assertEqual(str(got.exception),code)
    def test_valid_tiny_pair_failed_students_and_no_confirmation(self):
        result=self.f.audit()
        self.assertEqual(len(result['prefix11']),11)
        self.assertTrue(result['prefix11'][5]['failure_null_no_prediction_claim'])
        self.assertEqual(result['arms']['b']['selected_internal_confirmation_status'],'not_attempted')
        self.assertIsNone(result['arms']['b']['selected_internal_confirmation_metrics'])
        self.assertTrue(result['arms']['b']['fixed_four_leaf_nodes_verified'])
        self.assertEqual(self.f.events,['outer_label_boundary'])
    def test_unsealed_second_arm_before_any_arm_or_outer_labels(self):
        self.f.slots[1]['status']='running'
        with patch.object(v,'SealedArm',side_effect=AssertionError('arm opened too early')):self.reject('pair_not_terminal_sealed_clean')
        self.assertEqual(self.f.events,[])
    def test_corrupt_second_seal_before_outer_labels(self):
        (Path(self.f.slots[1]['output_dir'])/'task.md').write_text('altered',encoding='utf-8')
        self.reject('sealed_artifact_changed');self.assertEqual(self.f.events,[])
    def test_actual_saved_supervisor_bytes_bound(self):
        Path(self.f.slots[1]['supervisor_receipt_path']).write_text('{}',encoding='utf-8')
        self.reject('saved_supervisor_receipt_changed');self.assertEqual(self.f.events,[])
    def test_inline_supervisor_cannot_replace_saved_object(self):
        self.f.slots[1]['supervisor']['seconds']=2.
        self.reject('inline_supervisor_differs_saved_receipt')
    def test_saved_stage_slot_binding(self):
        stage=deepcopy(self.f.stage);stage['arms'][1]['exit_code']=9
        with patch.object(v,'context',return_value=(self.f.root,self.f.archives,stage)),patch.object(v,'fresh_gone',return_value=None):
            with self.assertRaisesRegex(v.AuditError,'slot_disagrees_with_saved_stage'):v.audit_pair(self.f.root,self.f.plan,self.f.slots,self.f.folds)
    def test_wrong_probability_classes_rejected(self):
        p=Path(self.f.slots[1]['output_dir'])/'automl_runs/run-v2/experiment-11/component-0/test_probabilities.npz'
        with np.load(p,allow_pickle=False) as s:values=s['probabilities'].copy()
        np.savez(p,classes=['A','B','Z'],probabilities=values);self.f.reseal('b');self.reject('probability_classes_wrong')
    def test_wrong_probability_rows_rejected(self):
        p=Path(self.f.slots[1]['output_dir'])/'automl_runs/run-v2/experiment-11/component-0/validation_probabilities.npz'
        with np.load(p,allow_pickle=False) as s:values=s['probabilities'].copy();rows=s['row_position'].copy()
        np.savez(p,classes=self.f.classes,probabilities=values,row_position=rows[::-1]);self.f.reseal('b');self.reject('probability_row_order_wrong')
    def test_wrong_csv_id_order_rejected(self):
        p=Path(self.f.slots[1]['output_dir'])/'automl_runs/run-v2/experiment-11/component-0/submission.csv'
        pd.read_csv(p).iloc[::-1].to_csv(p,index=False);self.f.reseal('b');self.reject('csv_ids_wrong')
    def test_wrong_probability_mixture_rejected(self):
        folder=Path(self.f.slots[1]['output_dir'])/'automl_runs/run-v2/experiment-11'
        p=folder/'test_probabilities.npz'
        with np.load(p,allow_pickle=False) as s:values=s['probabilities'].copy()
        values=values[:,[1,0,2]];np.savez(p,classes=self.f.classes,probabilities=values)
        frame=pd.read_csv(folder/'submission.csv');frame.target=np.asarray(self.f.classes)[values.argmax(axis=1)];frame.to_csv(folder/'submission.csv',index=False)
        self.f.reseal('b');self.reject('recursive_probability_mixture_wrong')
    def test_wrong_nested_iteration_rejected(self):
        folder=Path(self.f.slots[1]['output_dir'])/'automl_runs/run-v2/experiment-11';p=folder/'result.json';r=v.load(p)
        r['fit_iterations']=[31,41];r['feature_views']['iteration_tree']=[31,41];write(p,r)
        self.f.reports['b']['experiments'][11].update(fit_iterations=[31,41],feature_views=r['feature_views'])
        write(folder.parent/'report.json',self.f.reports['b']);self.f.reseal('b');self.reject('child_iteration_tree_wrong')
    def test_handled_failed_student_nonnull_metrics_rejected(self):
        for arm in ['a','b']:
            self.f.reports[arm]['experiments'][5]['metrics']={'macro_f1':0.}
            write(Path(self.f.slots[0 if arm=='a' else 1]['report_path']),self.f.reports[arm]);self.f.reseal(arm)
        self.reject('failed_student_metrics_not_null')
    def test_no_confirmation_branch_and_failed_confirmation(self):
        report=deepcopy(self.f.reports['a']);report['confirmations']=[{'status':'timeout','metrics':None,'recipe':report['selected_recipe']}]
        self.assertIsNone(v.selected_records(report)['confirmation'])
        report['selection']=[{'unexpected':'nonempty'}]
        with self.assertRaisesRegex(v.AuditError,'selected_confirmation_missing_despite_selection'):v.selected_records(report)
    def test_partial_matrix_keeps_six_slots_and_null_aggregates(self):
        with patch.object(v,'context',side_effect=self.f.patch_context),patch.object(v,'frozen_inputs',side_effect=self.f.patch_inputs),\
             patch.object(v,'fresh_gone',return_value=None),patch.object(v,'expected_inner_split',side_effect=split_rule):
            result=v.audit_complete_oof(self.f.root,self.f.plan,self.f.stage['arms'],self.f.folds)
        self.assertEqual(len(result['declared_arms']),6);self.assertEqual(len(result['fold_audits']),1)
        self.assertIsNone(result['fold_mean']);self.assertIsNone(result['pooled_macro_f1'])
        self.assertFalse(result['OOF_complete']);self.assertFalse(result['all_gates_passed'])
        for slot in result['declared_arms'][2:]:self.assertIsNone(slot['metrics']);self.assertIsNone(slot['final_csv_sha256'])
    def test_fresh_identity_gone_reused_live_and_denial(self):
        class Missing(Exception):pass
        class Denied(Exception):pass
        saved=self.f.slots[0]['supervisor']
        def process(mode):
            if mode=='missing':raise Missing()
            if mode=='denied':raise Denied()
            return SimpleNamespace(create_time=lambda:2. if mode=='reused' else 1.,is_running=lambda:True)
        for mode in ['missing','reused','live','denied']:
            fake=SimpleNamespace(NoSuchProcess=Missing,AccessDenied=Denied,Process=lambda pid:process(mode))
            with patch.dict(sys.modules,{'psutil':fake}):
                if mode in ['missing','reused']:v.fresh_gone(saved)
                else:
                    with self.assertRaisesRegex(v.AuditError,'owned_identity_still_live' if mode=='live' else 'owned_identity_access_denied'):v.fresh_gone(saved)

    def test_early_rejection_unattempted_slots_need_prior_audit_not_cleanup(self):
        prior=self.f.audit()
        self.assertFalse(prior['mandatory_fold_gates_passed'])
        path=self.f.root/'prior-negative-pair.json';write(path,prior)
        for slot in self.f.stage['arms'][2:]:
            slot.update(status='not_attempted_due_prior_gate_failure',prior_gate_audit={'path':str(path),'sha256':v.digest(path)})
        self.f.save_stage()
        with patch.object(v,'context',side_effect=self.f.patch_context),patch.object(v,'frozen_inputs',side_effect=self.f.patch_inputs),\
             patch.object(v,'fresh_gone',return_value=None),patch.object(v,'expected_inner_split',side_effect=split_rule):
            result=v.audit_complete_oof(self.f.root,self.f.plan,self.f.stage['arms'],self.f.folds)
        self.assertEqual(result['status'],'rejected_early_incomplete_CV')
        self.assertEqual(len(result['declared_arms']),6)
        self.assertIsNone(result['fold_mean']);self.assertIsNone(result['pooled_macro_f1'])
        self.assertFalse(result['OOF_complete'])
        for slot in result['declared_arms'][2:]:self.assertIsNone(slot['metrics'])

if __name__=='__main__':
    suite=unittest.TestSuite([Contracts('test_early_rejection_unattempted_slots_need_prior_audit_not_cleanup')])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    record={'status':'PASS' if result.wasSuccessful() else 'FAIL','source_sha256':EXPECTED,'checks':result.testsRun,
        'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'guards':COUNTS,'threads':1,
        'fits':0,'API_calls':0,'real_CV_outcomes_read':False,'actual_CV_metrics_computed':False,
        'scope':'Tiny real synthetic JSON/NPZ/CSV; context/publication/archive/frozen-input bindings and expected inner split mocked. Core pair/SealedArm/probability/mixture/supervisor/partial-matrix functions execute. Not a complete CV pass or source gate.',
        'mock_boundaries':['production context/publications/68-member archive inventory','frozen_inputs exact public hashes and outer split reproduction','expected_inner_split uses deterministic synthetic rule','fresh_gone normally mocked; separate fake-psutil identity contracts execute real fresh_gone'],
        'known_combined_gate_dependency':'Root final-fit/job.json requirement, wall9900/events[] are additionally enforced by mechanical verification.py; this independent module alone does not certify all procedure evidence.',
        'promotion':False,'launch_authorized':False}
    write(BASE/'results.json',record)
    raise SystemExit(0 if result.wasSuccessful() else 1)
