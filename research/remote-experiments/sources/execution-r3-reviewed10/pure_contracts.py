"""Bounded synthetic/mock/inert contracts only; no estimator fitting or API."""
from pathlib import Path
from unittest.mock import patch, MagicMock
import copy, hashlib, io, json, os, subprocess, sys, tempfile, time, unittest, zipfile
import numpy as np
import pandas as pd
import portable_harness as h
import component_audit as a
import experiment_driver as d

LIBROOT=None
QUEUE=None
ORIGINAL_SOURCE=None
SOURCE_MANIFEST=None
ROOT_REFS=None
def write(path,v):Path(path).write_text(json.dumps(v))
def clock(seconds=60):
    w,m=time.time(),time.monotonic();return h.Clock(w,m,w+seconds,m+seconds,m)

def cut_contract(path,tr,va,kind='classification'):
    np.savez(path,train=tr,validation=va)
    members=[]
    with zipfile.ZipFile(path) as z:
        for info,x in zip(z.infolist(),[tr,va]):
            members.append(dict(name=info.filename,shape=list(x.shape),fortran_order=False,dtype=x.dtype.str,
                                npy_sha256=hashlib.sha256(z.read(info.filename)).hexdigest(),
                                canonical_ordered_values_sha256=hashlib.sha256(x.astype('<i8').tobytes()).hexdigest()))
    return dict(kind=kind,cut=42,canonical_concat_train_validation_sha256=hashlib.sha256(tr.astype('<i8').tobytes()+va.astype('<i8').tobytes()).hexdigest(),
                native_profiles={'Linux':dict(raw_npz_sha256=h.sha(path),zip_creator_system=3,members=members)})

def fixture(root,r4,feature_views=False,ensemble=False):
    root=Path(root);root.mkdir(exist_ok=True)
    train=pd.DataFrame(dict(id=list(range(6)),x=list(range(6)),y=['A','B','A','B','A','B']))
    test=pd.DataFrame(dict(id=[10,11],x=[8,9]));sample=pd.DataFrame(dict(id=[10,11],y=['A','B']))
    spec=dict(kind='classification',metric='macro_f1',prediction_type='value',output_columns=['y'],target='y',id='id',features=['x'],
              categorical_features=[],n_train=6,n_test=2,classes=['A','B'])
    split=root/'split.npz';tr=np.array([0,1,2,3],dtype='int64');va=np.array([4,5],dtype='int64');np.savez(split,train=tr,validation=va)
    recipe=dict(engine='lightgbm',params={},hypothesis='synthetic inert artifact')
    if feature_views:recipe['params']['feature_views']='categorical_te_pair'
    if ensemble:recipe=dict(engine='ensemble',components=[copy.deepcopy(recipe),copy.deepcopy(recipe)],weights=[.5,.5],params={})
    folder=root/'out';folder.mkdir()
    probs=np.array([[.8,.2],[.2,.8]])
    def leaf(folder,recipe,top):
        if recipe['engine']=='ensemble':children=recipe['components']
        elif recipe.get('params',{}).get('feature_views'):children=r4.child_feature_views(recipe,spec)
        else:children=[]
        its=[1,1] if children else 1
        record=dict(status='ok',recipe=recipe,full_fit=False,fit_iterations=its,metrics={'macro_f1':1.})
        write(folder/'result.json',record)
        if top:write(folder/'job.json',dict(spec=spec,recipe=recipe,threads=2,full_fit=False,output_dir=str(folder),split_path=str(split)))
        sample.to_csv(folder/'submission.csv',index=False)
        pd.DataFrame(dict(row_position=va,y_true=['A','B'],y_pred=['A','B'])).to_csv(folder/'validation_predictions.csv',index=False)
        np.savez(folder/'validation_probabilities.npz',probabilities=probs,classes=np.array(['A','B']),row_position=va)
        np.savez(folder/'test_probabilities.npz',probabilities=probs,classes=np.array(['A','B']))
        for i,child in enumerate(children):
            d=folder/('component-'+str(i));d.mkdir();leaf(d,child,False)
        return record
    record=leaf(folder,recipe,True);record['output_dir']=str(folder)
    return root,spec,train,test,sample,split,folder,recipe,record

class Contracts(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory(prefix='automl-contract-');self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def libs(self):return a.libraries(LIBROOT)
    def matrix(self):
        protocol=h.load(ROOT_REFS/'protocol.json');native=h.load(ROOT_REFS/'native-cut-contract-v3-r2.json')
        source=h.load(ROOT_REFS/'source-manifest.json');inputs=h.load(ROOT_REFS/'approved-input-manifest.json');control=h.load(ROOT_REFS/'protected-single-controls.json')
        roles={r:str(self.root/(r+'.csv')) for r in ('train','test','sample_submission','data_dictionary')}
        spec=dict(kind='classification',metric='macro_f1',prediction_type='value',paths=roles)
        approved={v['name']:v['sha256'] for v in inputs['files'] if v['task']=='multiclass'}
        authority=dict(spec=spec,roles=roles,source_manifest=source,input_sha256={r:approved[r+'.csv'] for r in roles},task_sha256=approved['task.md'],components=[],comparisons={})
        for cut,arm in d.ORDER:
            key=f'classification{cut}-{arm}'
            authority['components'].append(dict(key=key,cut=cut,arm=arm,output_relative='cores/'+key,job_relative='jobs/'+key+'.json',
                split_relative=f'splits/classification-{cut}.npz',native_cut=next(v for v in native['cuts'] if v['kind']=='classification' and v['cut']==cut),
                recipe=copy.deepcopy(protocol['recipes'][arm]),spec_canonical_sha256=h.canonical(spec),threads=2,full_fit=False))
        for name,candidate,reference in [('rbf_vs_fresh_strong','rbf','strong'),('linear_vs_fresh_strong','linear','strong'),('rbf_vs_matched_linear','rbf','linear')]:
            authority['comparisons'][name]=dict(candidate={'primary':f'classification42-{candidate}','confirmation':f'classification43-{candidate}'},control={'primary':f'classification42-{reference}','confirmation':f'classification43-{reference}'})
        return authority,protocol,native,source,inputs,control
    def test_terminal_before450(self):
        p=MagicMock();p.poll.return_value=0
        with patch.object(h.time,'monotonic',return_value=449.999):self.assertEqual(h.terminal_poll(p,450)[0],0)
    def test_terminal_at450_refused(self):
        p=MagicMock();p.poll.return_value=0
        with patch.object(h.time,'monotonic',return_value=450):
            with self.assertRaisesRegex(h.Blocked,'child_deadline'):h.terminal_poll(p,450)
    def test_terminal_after450_refused(self):
        p=MagicMock();p.poll.return_value=0
        with patch.object(h.time,'monotonic',return_value=450.03):
            with self.assertRaisesRegex(h.Blocked,'child_deadline'):h.terminal_poll(p,450)
    def test_driver_finalize_parent480(self):
        receipt=self.root/'raw.json';write(receipt,{'original':'untouched'});c=MagicMock();c.wall_deadline=10000
        raw=dict(status='completed',cleanup_confirmed=True,first_error=None,secondary_errors=[])
        with patch.object(h.time,'monotonic',return_value=480):result=h.driver_finalize(raw,c,480,receipt,[])
        self.assertEqual(result['status'],'blocked');self.assertFalse(result['cleanup_confirmed']);self.assertEqual(h.load(receipt),{'original':'untouched'})
    def test_driver_finalize_common_gap(self):
        receipt=self.root/'raw.json';write(receipt,{});c=clock();c.last-=11
        result=h.driver_finalize(dict(status='completed',cleanup_confirmed=True,first_error=None,secondary_errors=[]),c,time.monotonic()+480,receipt,[])
        self.assertEqual(result['status'],'blocked');self.assertFalse(result['cleanup_confirmed'])
    def test_driver_failure_errors_preserved(self):
        receipt=self.root/'raw.json';write(receipt,{})
        first=dict(code='nonzero_child_exit',detail='original failure');second=dict(code='secondary',detail='retained')
        result=h.driver_finalize(dict(status='failed',cleanup_confirmed=True,first_error=first,secondary_errors=[second]),clock(),time.monotonic()+480,receipt,[])
        self.assertEqual(result['first_error'],first);self.assertEqual(result['secondary_errors'],[second]);self.assertEqual(result['status'],'failed')
    def test_driver_success_after_contexts(self):
        receipt=self.root/'raw.json';write(receipt,{});raw=dict(status='completed',cleanup_confirmed=True,first_error=None,secondary_errors=[])
        result=h.driver_finalize(raw,clock(),time.monotonic()+480,receipt,[])
        self.assertEqual(result['status'],'completed');self.assertTrue(result['cleanup_confirmed'])
    def test_driver_context_exception_downgrade(self):
        receipt=self.root/'raw.json';write(receipt,{})
        result=h.driver_finalize(dict(status='completed',cleanup_confirmed=True,first_error=None,secondary_errors=[]),clock(),time.monotonic()+480,receipt,[dict(code='PermissionError',detail='context release denied')])
        self.assertEqual(result['status'],'blocked');self.assertFalse(result['cleanup_confirmed']);self.assertEqual(result['first_error']['code'],'PermissionError')
    def invoke_context_driver(self,denied=None):
        from contextlib import contextmanager
        repo=self.root/'repo';repo.mkdir();state=self.root/'remote-research-state';state.mkdir()
        bundle=self.root/'bundle';bundle.mkdir();(bundle/'automl_worker.py').write_text('# inert fixture never invoked\n')
        manifest=dict(source_archive_sha256='ca8a0898af84a4ddb8039343f94edc73aa7360005f215125907a34427a3c6d5c',flat_files_sha256=h.inventory(bundle))
        leaf=dict(threads=2,full_fit=False,recipe={'engine':'inert'},spec={'kind':'synthetic'});p=self.root/'job.json';write(p,leaf)
        binding=dict(manifest_canonical_sha256=h.canonical(manifest),private_job_sha256=h.sha(p),entrypoint='automl_worker.py',recipe=leaf['recipe'],spec_canonical_sha256=h.canonical(leaf['spec']))
        c=clock(1000);claim=dict(claimed_at_unix=c.wall_start,deadline_unix=c.wall_deadline);job={'caps':dict(cpu_threads=2,worker_memory_mib=1536,whole_memory_mib=2048)}
        flags=[];receipt=self.root/'raw.json';raw=dict(status='completed',cleanup_confirmed=True,first_error=None,secondary_errors=[])
        @contextmanager
        def temporary(*args,**kwargs):
            yield str(self.root);flags.append('temp_exit')
            if denied=='temp':raise PermissionError('temp cleanup denied')
        @contextmanager
        def lock(*args,**kwargs):
            yield {'owned':'fixture'};flags.append('lock_exit')
            if denied=='lock':raise PermissionError('lock exit denied')
        def supervised(*args,**kwargs):write(receipt,raw);return raw
        with patch.object(h,'queue_admission',return_value=(claim,job,binding)),patch.object(h,'supervise',side_effect=supervised),patch.object(h.tempfile,'TemporaryDirectory',side_effect=temporary),patch.object(h,'selected_lock',side_effect=lock):
            result=h.model_driver(repo,__file__,'pin','j','w','c',bundle,manifest,p,h.sha(p),self.root/'clock.json',state/'experiment.lock',receipt,common_clock=c)
        return result,flags,h.load(receipt)
    def test_real_driver_after_both_context_exits(self):
        result,flags,raw=self.invoke_context_driver();self.assertEqual(flags,['temp_exit','lock_exit']);self.assertEqual(result['status'],'completed');self.assertEqual(raw['status'],'completed')
    def test_real_driver_temp_exit_denial(self):
        result,flags,raw=self.invoke_context_driver('temp');self.assertEqual(result['status'],'blocked');self.assertFalse(result['cleanup_confirmed']);self.assertEqual(raw['status'],'completed')
    def test_real_driver_lock_exit_denial(self):
        result,flags,raw=self.invoke_context_driver('lock');self.assertEqual(result['status'],'blocked');self.assertFalse(result['cleanup_confirmed']);self.assertEqual(raw['status'],'completed')
    def test_fixed_matrix_positive(self):self.assertTrue(d.validate_matrix(*self.matrix()))
    def test_fixed_matrix_duplicate_key(self):
        args=self.matrix();args[0]['components'][1]['key']=args[0]['components'][0]['key']
        with self.assertRaises(h.Blocked):d.validate_matrix(*args)
    def test_fixed_matrix_duplicate_folder(self):
        args=self.matrix();args[0]['components'][1]['output_relative']=args[0]['components'][0]['output_relative']
        with self.assertRaises(h.Blocked):d.validate_matrix(*args)
    def test_fixed_matrix_wrong_recipe(self):
        args=self.matrix();args[0]['components'][0]['recipe']['params']['seed']=42
        with self.assertRaisesRegex(h.Blocked,'exact_raw_recipe'):d.validate_matrix(*args)
    def test_fixed_matrix_wrong_spec(self):
        args=self.matrix();args[0]['components'][0]['spec_canonical_sha256']='0'*64
        with self.assertRaises(h.Blocked):d.validate_matrix(*args)
    def test_fixed_matrix_wrong_native_cut(self):
        args=self.matrix();args[0]['components'][0]['native_cut']=args[0]['components'][3]['native_cut']
        with self.assertRaises(h.Blocked):d.validate_matrix(*args)
    def test_fixed_matrix_wrong_source(self):
        args=self.matrix();args[0]['source_manifest']=dict(args[3],source_archive_sha256='0'*64)
        with self.assertRaises(h.Blocked):d.validate_matrix(*args)
    def test_fixed_matrix_wrong_input(self):
        args=self.matrix();args[0]['input_sha256']['train']='0'*64
        with self.assertRaises(h.Blocked):d.validate_matrix(*args)
    def test_fixed_matrix_wrong_contrast_phase(self):
        args=self.matrix();args[0]['comparisons']['rbf_vs_fresh_strong']['candidate']['primary']='classification43-rbf'
        with self.assertRaises(h.Blocked):d.validate_matrix(*args)
    def test_source05_caller_denied_before_model(self):
        with patch.object(h,'queue_admission',side_effect=h.Blocked('source_only_fit_refused')),patch.object(h.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(h.Blocked,'source_only'):d.execute('.',__file__,'source05','w','c',self.root,self.root/'unused.json',self.root/'clock.json')
            spawn.assert_not_called()
    def test_default_caller_inspection_no_models(self):
        with patch.object(h.subprocess,'Popen') as spawn:self.assertEqual(d.inspect_plan()['model_processes'],0);spawn.assert_not_called()
    def test_fixed_remaining_budget(self):
        c=MagicMock();d.reserve(c,0);c.tick.assert_called_once_with(4800)
        c.reset_mock();d.reserve(c,5);c.tick.assert_called_once_with(2400)
    def test_fit_count_unique_leaf_not_parent_embedded(self):
        folder=self.root/'strong';folder.mkdir();write(folder/'result.json',dict(status='ok',recipe={'params':{'feature_views':'categorical_te_pair'}},components=[{'data_policy_runs':[{}]*100}]))
        for i,n in [(0,3),(1,2)]:
            leaf=folder/f'component-{i}';leaf.mkdir();write(leaf/'result.json',dict(status='ok',data_policy_runs=[{}]*n))
        self.assertEqual(d.fixed_fit_count(folder,'strong'),5)
    def test_failed_fit_count_unknown_not_zero(self):
        folder=self.root/'failed';folder.mkdir();write(folder/'result.json',dict(status='error'))
        self.assertIsNone(d.fixed_fit_count(folder,'linear'))
    def test_incomplete_matrix_no_truth(self):
        slots=[dict(key=key,status='not_attempted_due_prior_technical_failure',fits=None) for key in d.KEYS]
        with patch.object(pd,'read_csv') as read:
            result=d.audit_matrix(self.root,{}, {},slots,LIBROOT,clock());self.assertFalse(result['qualified']);read.assert_not_called()
    def test_environment_ascii_no_credentials(self):
        with patch.dict(os.environ,{'OPENAI_BASE_URL':'private','QWEN_MODEL':'private','SOME_SECRET':'private','PYTHONPATH':'private'}):
            env=h.clean_environment(self.root)
        self.assertNotIn('OPENAI_BASE_URL',env);self.assertNotIn('QWEN_MODEL',env);self.assertNotIn('SOME_SECRET',env);self.assertNotIn('PYTHONPATH',env)
        self.assertTrue(env['JOBLIB_TEMP_FOLDER'].isascii())
        with self.assertRaises(h.Blocked):h.clean_environment(self.root/'é')
    def test_actual_exclusive_lock(self):
        p=self.root/'host.lock'
        with h.host_lock(p):
            with self.assertRaises(h.Blocked):
                with h.host_lock(p):pass
        self.assertFalse(p.exists())
    def test_lock_identity_replacement(self):
        p=self.root/'host.lock'
        with self.assertRaises(h.Blocked):
            with h.host_lock(p):write(p,{'pid':0})
        self.assertTrue(p.exists())
    def test_retained_original_clock(self):
        claim=dict(claimed_at_unix=time.time(),deadline_unix=time.time()+60);p=self.root/'clock.json'
        h.Clock.retained(claim,p);before=p.read_bytes();h.Clock.retained(claim,p);self.assertEqual(before,p.read_bytes())
        with self.assertRaises(h.Blocked):h.Clock.retained(dict(claim,deadline_unix=claim['deadline_unix']+1),p)
    def test_gap_clock(self):
        c=clock();c.last-=11
        with self.assertRaises(h.Blocked):c.tick()
    def test_full_allocation_no_popen(self):
        frozen=self.root/'frozen';frozen.mkdir()
        with patch.object(h.subprocess,'Popen') as spawn:
            with self.assertRaises(h.Blocked):h.supervise([],self.root,{},frozen,clock(3),self.root/'r.json',parent_seconds=8,child_seconds=1)
            spawn.assert_not_called()
    def test_hash_expiry_before_popen(self):
        frozen=self.root/'frozen';frozen.mkdir();c=clock()
        def expired(*args):c.wall_deadline=time.time()-1;return {}
        with patch.object(h,'inventory',side_effect=expired),patch.object(h.subprocess,'Popen') as spawn:
            with self.assertRaises(h.Blocked):h.supervise([],self.root,{},frozen,c,self.root/'r.json',parent_seconds=8,child_seconds=1)
            spawn.assert_not_called()
    def test_real_inert_child(self):
        frozen=self.root/'frozen';frozen.mkdir();env=h.clean_environment(self.root)
        result=h.supervise([sys.executable,'-c','print(123)'],self.root,env,frozen,clock(),self.root/'r.json',parent_seconds=8,child_seconds=1)
        self.assertEqual(result['status'],'completed');self.assertTrue(result['cleanup_confirmed']);self.assertEqual(result['exit_code'],0)
    def test_late_finalization_downgrade(self):
        frozen=self.root/'frozen';frozen.mkdir();c=clock()
        def late(*args):c.wall_deadline=time.time()-1
        with patch.object(h,'check_inventory',side_effect=late):
            r=h.supervise([sys.executable,'-c','pass'],self.root,h.clean_environment(self.root),frozen,c,self.root/'r.json',parent_seconds=8,child_seconds=1)
        self.assertEqual(r['status'],'blocked');self.assertFalse(r['cleanup_confirmed'])
    def test_descendant_rss_not_direct_only(self):
        p=MagicMock();p.pid=11;p.create_time.return_value=1;p.memory_info.return_value.rss=3
        child=MagicMock();child.pid=12;child.create_time.return_value=2;child.memory_info.return_value.rss=7
        p.children.return_value=[child];child.children.return_value=[]
        with patch.object(h.psutil,'Process',side_effect=lambda pid:p if pid==11 else child):
            tree=h.OwnedTree(11);self.assertEqual(tree.sample(),10);self.assertEqual(tree.known,{(11,1),(12,2)})
    def test_traversal_denial_sticky(self):
        p=MagicMock();p.pid=11;p.create_time.return_value=1;p.children.side_effect=h.psutil.AccessDenied(11)
        with patch.object(h.psutil,'Process',return_value=p):
            tree=h.OwnedTree(11)
            with self.assertRaises(h.Blocked):tree.sample()
            p.children.side_effect=None;p.children.return_value=[]
            with self.assertRaises(h.Blocked):tree.sample()
            self.assertFalse(tree.absent())
    def test_final_cleanup_identity_replacement(self):
        p=MagicMock();p.pid=11;p.create_time.return_value=1
        with patch.object(h.psutil,'Process',return_value=p):
            tree=h.OwnedTree(11);p.create_time.return_value=2
            self.assertFalse(tree.absent());p.kill.assert_not_called();p.terminate.assert_not_called()
    def test_final_cleanup_denied(self):
        p=MagicMock();p.pid=11;p.create_time.return_value=1
        with patch.object(h.psutil,'Process',return_value=p):
            tree=h.OwnedTree(11);p.create_time.side_effect=h.psutil.AccessDenied(11)
            self.assertFalse(tree.absent());self.assertTrue(tree.errors)
    def test_source_cli_refuses(self):
        result=subprocess.run([sys.executable,str(Path(h.__file__).resolve())],capture_output=True,timeout=5,env=h.clean_environment(self.root))
        self.assertNotEqual(result.returncode,0);self.assertIn(b'learner execution refused',result.stderr)
    def test_source_admission_refuses_before_popen(self):
        q=MagicMock();q.Git.return_value=object();q.read_claim.return_value=('c',{'worker_id':'w'},{'id':'j','kind':'source_only','caps':{'max_fits':0}},None)
        s=MagicMock();s.loader.exec_module.side_effect=lambda mod:mod.__dict__.update(q.__dict__)
        # Test the real admission path with a mocked immutable queue module.
        with patch.object(h,'sha',return_value='pin'),patch('importlib.util.spec_from_file_location',return_value=s),patch('importlib.util.module_from_spec',return_value=q):
            with self.assertRaises(h.Blocked):h.queue_admission('.',__file__,'pin','j','w','c')
        q.bounded_admission.assert_not_called()
    def test_wrong_worker_or_claim_refused(self):
        q=MagicMock();q.read_claim.return_value=('wrong',{'worker_id':'other'},{'id':'j'},None)
        s=MagicMock()
        with patch.object(h,'sha',return_value='pin'),patch('importlib.util.spec_from_file_location',return_value=s),patch('importlib.util.module_from_spec',return_value=q):
            with self.assertRaises(h.Blocked):h.queue_admission('.',__file__,'pin','j','w','c')
    def test_primary_approval_result_binding(self):
        import importlib.util
        self.assertEqual(h.sha(QUEUE),'d42cb979db953eeffabfa65ee2a40d8763dfd835f91ce35149327f3d181e4c49')
        s=importlib.util.spec_from_file_location('_actual_queue_test',QUEUE);q=importlib.util.module_from_spec(s);s.loader.exec_module(q)
        approval=dict(schema=1,job_id='dependency',result_sha='incorrect',worker_id='w',approved_for_bounded_experiments=True,
                      caps=dict(wall_seconds=900,cpu_threads=2,worker_memory_mib=1536,whole_memory_mib=2048,max_fits=10,max_api_calls=0))
        raw=json.dumps(approval).encode();g=MagicMock();g.blob.return_value=raw
        job=dict(id='j',kind='bounded_experiment',dependencies=['dependency'],source_refs=[dict(path='research/remote-experiments/reviews/dependency.json',sha256=hashlib.sha256(raw).hexdigest())])
        with patch.object(q,'read_claim',return_value=(None,None,{'kind':'source_only'},None)),patch.object(q,'collect',return_value={'worker_id':'w','result_sha':'actual','report':{'status':'completed'}}):
            with self.assertRaises(q.QueueError):q.bounded_admission(g,'dispatch',job,'w')
    def test_model_driver_lock_is_wired(self):
        bundle=self.root/'bundle';bundle.mkdir();(bundle/'automl_worker.py').write_text('# inert fixture, never executed\n')
        manifest={'source_archive_sha256':'ca8a0898af84a4ddb8039343f94edc73aa7360005f215125907a34427a3c6d5c','flat_files_sha256':h.inventory(bundle)}
        leaf={'threads':2,'full_fit':False,'recipe':{'engine':'inert'},'spec':{'kind':'synthetic'}};p=self.root/'private.json';write(p,leaf)
        binding=dict(manifest_canonical_sha256=h.canonical(manifest),private_job_sha256=h.sha(p),entrypoint='automl_worker.py',recipe=leaf['recipe'],spec_canonical_sha256=h.canonical(leaf['spec']))
        claim={'claimed_at_unix':time.time(),'deadline_unix':time.time()+1000};repo=self.root/'remote-research';repo.mkdir()
        state=self.root/'remote-research-state';state.mkdir();lock=state/'experiment.lock'
        job={'caps':dict(cpu_threads=2,worker_memory_mib=1536,whole_memory_mib=2048)}
        with h.host_lock(lock),patch.object(h,'queue_admission',return_value=(claim,job,binding)),patch.object(h,'supervise') as spawn:
            with self.assertRaisesRegex(h.Blocked,'host_lock_occupied_no_reclaim'):h.model_driver(repo,__file__,'pin','j','w','c',bundle,manifest,p,h.sha(p),self.root/'clock.json',lock,self.root/'receipt.json')
            spawn.assert_not_called()
    def test_wrong_job_identity_refused(self):
        q=MagicMock();q.read_claim.return_value=('c',{'worker_id':'w'},{'id':'another'},None);s=MagicMock()
        with patch.object(h,'sha',return_value='pin'),patch('importlib.util.spec_from_file_location',return_value=s),patch('importlib.util.module_from_spec',return_value=q):
            with self.assertRaises(h.Blocked):h.queue_admission('.',__file__,'pin','j','w','c')
    def test_native_linux_exact(self):
        p=self.root/'s.npz';tr=np.array([0,1],dtype='int64');va=np.array([2],dtype='int64');cut=cut_contract(p,tr,va)
        actual=h.native_split(p,cut,3,np.arange(3));self.assertTrue(np.array_equal(actual[0],tr))
    def test_native_tampered_dtype(self):
        p=self.root/'s.npz';tr=np.array([0,1],dtype='int64');va=np.array([2],dtype='int64');cut=cut_contract(p,tr,va);cut['native_profiles']['Linux']['members'][0]['dtype']='<i4'
        with self.assertRaises(h.Blocked):h.native_split(p,cut,3,np.arange(3))
    def test_native_tampered_order_hash(self):
        p=self.root/'s.npz';cut=cut_contract(p,np.array([0,1]),np.array([2]));np.savez(p,train=np.array([1,0]),validation=np.array([2]))
        with self.assertRaises(h.Blocked):h.native_split(p,cut,3,np.arange(3))
    def test_native_tampered_values_digest(self):
        p=self.root/'s.npz';cut=cut_contract(p,np.array([0,1]),np.array([2]));cut['canonical_concat_train_validation_sha256']='0'*64
        with self.assertRaises(h.Blocked):h.native_split(p,cut,3,np.arange(3))
    def test_native_group_chronology(self):
        p=self.root/'s.npz';cut=cut_contract(p,np.array([0,1]),np.array([2]))
        with self.assertRaises(h.Blocked):h.native_split(p,cut,3,np.zeros(3))
        cut['kind']='regression'
        with self.assertRaises(h.Blocked):h.native_split(p,cut,3,times=np.array([2,1,1]))
    def test_native_path_role_mapping(self):
        roles={k:str(self.root/(k+'.csv')) for k in ('train','test','sample_submission','data_dictionary')};a.native_roles({'paths':roles},roles)
        roles['train']='C'+':'+chr(92)+'synthetic'+chr(92)+'train.csv'
        with self.assertRaises(h.Blocked):a.native_roles({'paths':roles},roles)
    def test_r4_leaf_and_diagnostics(self):
        r4,_=self.libs();root,spec,train,test,sample,split,out,recipe,record=fixture(self.root,r4)
        v=r4.TaskVerifier(root,{'spec':spec,'experiments':[],'confirmations':[]},train,test,sample)
        self.assertEqual(v.verify(record,split,'primary',False,recipe)['value'],1.)
        d=r4.diagnostics(v,record,split,'primary');self.assertTrue(d['feature_groups_disjoint'])
        comparison=r4.matched_control_comparison({'primary':d,'confirmation':d},{'primary':d,'confirmation':d},'classification')
        self.assertFalse(comparison['each_cut_primary_gate_passed'])
    def check_r4(self,mutate,views=False,ensemble=False):
        r4,_=self.libs();root,spec,train,test,sample,split,out,recipe,record=fixture(self.root,r4,views,ensemble);mutate(out,record)
        v=r4.TaskVerifier(root,{'spec':spec,'experiments':[],'confirmations':[]},train,test,sample)
        with self.assertRaises((AssertionError,h.Blocked)):v.verify(record,split,'primary',False,recipe)
    def test_r4_probability_width_tamper(self):
        self.check_r4(lambda out,r:np.savez(out/'test_probabilities.npz',probabilities=np.ones((2,1)),classes=np.array(['A','B'])))
    def test_r4_probability_csv_mismatch(self):
        self.check_r4(lambda out,r:pd.DataFrame(dict(id=[10,11],y=['B','B'])).to_csv(out/'submission.csv',index=False))
    def test_r4_truth_tamper(self):
        self.check_r4(lambda out,r:pd.DataFrame(dict(row_position=[4,5],y_true=['B','B'],y_pred=['A','B'])).to_csv(out/'validation_predictions.csv',index=False))
    def test_r4_validation_positions_tamper(self):
        self.check_r4(lambda out,r:np.savez(out/'validation_probabilities.npz',probabilities=np.array([[.8,.2],[.2,.8]]),classes=np.array(['A','B']),row_position=np.array([5,4])))
    def test_r4_nonfinite_probability(self):
        self.check_r4(lambda out,r:np.savez(out/'test_probabilities.npz',probabilities=np.array([[np.nan,.2],[.2,.8]]),classes=np.array(['A','B'])))
    def test_r4_probability_sum(self):
        self.check_r4(lambda out,r:np.savez(out/'test_probabilities.npz',probabilities=np.array([[.8,.8],[.2,.8]]),classes=np.array(['A','B'])))
    def test_r4_reversed_class_label_tamper(self):
        self.check_r4(lambda out,r:np.savez(out/'test_probabilities.npz',probabilities=np.array([[.8,.2],[.2,.8]]),classes=np.array(['B','A'])))
    def test_r4_recursive_ensemble_tamper(self):
        def change(out,r):np.savez(out/'component-0/test_probabilities.npz',probabilities=np.array([[.7,.3],[.3,.7]]),classes=np.array(['A','B']))
        self.check_r4(change,ensemble=True)
    def test_r4_feature_view_tamper(self):
        def change(out,r):np.savez(out/'component-1/test_probabilities.npz',probabilities=np.array([[.7,.3],[.3,.7]]),classes=np.array(['A','B']))
        self.check_r4(change,views=True)
    def test_recursive_iterations_bound(self):
        r4,_=self.libs();*_,out,recipe,record=fixture(self.root,r4,ensemble=True);a.iterations(out,recipe)
        child=h.load(out/'component-0/result.json');child['fit_iterations']=2;write(out/'component-0/result.json',child)
        with self.assertRaises(h.Blocked):a.iterations(out,recipe)
    def test_pretruth_inventory_tamper(self):
        frozen=self.root/'core';frozen.mkdir();(frozen/'result.json').write_text('{}');sealed=h.inventory(frozen);(frozen/'result.json').write_text('{"changed":1}')
        with self.assertRaises(h.Blocked):h.check_inventory(frozen,sealed)
    def test_audit_authority_before_truth(self):
        with patch.object(pd,'read_csv') as read:
            with self.assertRaises(h.Blocked):a.audit(self.root,{},'bad-authority',LIBROOT,clock())
            read.assert_not_called()
    def test_outer_component_audit_synthetic_positive(self):
        import shutil
        r4,_=self.libs();root,spec,train,test,sample,split,out,recipe,record=fixture(self.root,r4)
        manifest=h.load(SOURCE_MANIFEST);algorithm=root/'algorithm'
        shutil.copytree(ORIGINAL_SOURCE,algorithm);h.check_inventory(algorithm,manifest['flat_files_sha256'])
        inputs=root/'inputs';inputs.mkdir();roles={r:str(inputs/(r+'.csv')) for r in ('train','test','sample_submission','data_dictionary')}
        train.to_csv(roles['train'],index=False);test.to_csv(roles['test'],index=False);sample.to_csv(roles['sample_submission'],index=False)
        pd.DataFrame({'feature':['x']}).to_csv(roles['data_dictionary'],index=False)
        spec['paths']=roles;job=h.load(out/'job.json');job['spec']=spec;write(out/'job.json',job)
        c=clock();terminal=dict(status='completed',exit_code=0,cleanup_confirmed=True,original_deadline=c.wall_deadline,
                               finished_unix=time.time(),peak_worker_subtree_rss_mib=1,peak_whole_owned_rss_mib=1)
        write(root/'synthetic-terminal.json',terminal)
        cut=cut_contract(split,np.array([0,1,2,3],dtype='int64'),np.array([4,5],dtype='int64'))
        authority=dict(spec=spec,roles=roles,input_sha256={r:h.sha(p) for r,p in roles.items()},source_manifest=manifest,
                       algorithm_relative='algorithm',source_inventories={'algorithm':manifest['flat_files_sha256']},
                       components=[dict(key='synthetic42',arm='strong',output_relative='out',recipe=recipe,split_relative='split.npz',native_cut=cut,
                                        terminal_relative='synthetic-terminal.json',terminal_sha256=h.sha(root/'synthetic-terminal.json'),core_sha256=h.inventory(out))],comparisons={})
        result=a.audit(root,authority,h.canonical(authority),LIBROOT,c)
        self.assertEqual(result['status'],'component_audit_only');self.assertEqual(result['diagnostics']['synthetic42']['value'],1.)
        self.assertFalse(result['promotion'])
        # A dirty recursive/output seal must fail before pristine labels are loaded.
        (out/'result.json').write_text('{}')
        with patch.object(pd,'read_csv') as read:
            with self.assertRaises(h.Blocked):a.audit(root,authority,h.canonical(authority),LIBROOT,clock())
            read.assert_not_called()
    def representation(self,arm):
        r4,kern=self.libs();root,spec,train,test,sample,split,out,recipe,record=fixture(self.root,r4)
        v=r4.TaskVerifier(root,{'spec':spec,'experiments':[],'confirmations':[]},train,test,sample);n=4;dim=128 if arm=='rbf' else 1
        budget=dict(fitting_rows=n,numeric_columns=1,categorical_columns=0,maximum_encoded_columns=1,
                    estimated_live_matrix_bytes=n*(8*3+16*2)+(n*dim*8*2 if arm=='rbf' else n*16)+(dim*8 if arm=='rbf' else 0)+64*dim*8,
                    matrix_limit_bytes=128000000,matrix_limit_scope='each_logical_matrix',
                    matrix_bytes_upper_bounds={'numeric_dense':n*8,'category_codes':0,'prepared_CSR_upper_bound':n*12+(n+1)*4,'representation_dense':n*dim*8 if arm=='rbf' else 0,'random_projection':dim*8 if arm=='rbf' else 0},process_RSS_requires_external_guard=True)
        tr=np.arange(4,dtype='int64');rowsha=hashlib.sha256(str(tr.dtype).encode()+str(tr.shape).encode()+tr.tobytes()).hexdigest()
        info=dict(prepared_columns=1,representation_columns=dim,budget=budget,representation_profile=kern.PROFILES[arm],fitting_rows=n,
                  fitting_row_order_sha256=rowsha,seed=42,numeric_columns=1,categorical_columns=0,threads=2,calibration='disabled',log_target=False,
                  preprocessing_scope='fitting_rows_only',representation_scope='fitting_rows_only',fitting_state_sha256='0'*64,
                  actual_prepared_matrix_bytes=n*8,actual_representation_matrix_bytes=n*dim*8,projection_bytes=dim*8+128*8 if arm=='rbf' else 0,
                  gamma=1. if arm=='rbf' else None,estimator=dict(family='LogisticRegression',C=1.,solver='lbfgs',class_weight_power=.5),classes=['A','B'])
        record.update(representation=info,fit_iterations=1);job=dict(arm=arm,kind='classification',_absolute_split=str(split))
        return r4,kern,v,record,job
    def test_frozen_linear_representation_receipt(self):
        r4,kern,v,record,job=self.representation('linear');self.assertTrue(kern.representation_receipt(r4,v,record,job)['verified'])
    def test_frozen_rbf_representation_receipt(self):
        r4,kern,v,record,job=self.representation('rbf');self.assertTrue(kern.representation_receipt(r4,v,record,job)['verified'])
    def test_frozen_rbf_gamma_tamper(self):
        r4,kern,v,record,job=self.representation('rbf');record['representation']['gamma']=2.
        with self.assertRaises(AssertionError):kern.representation_receipt(r4,v,record,job)
    def test_frozen_representation_fit_scope_tamper(self):
        r4,kern,v,record,job=self.representation('linear');record['representation']['fitting_row_order_sha256']='1'*64
        with self.assertRaises(AssertionError):kern.representation_receipt(r4,v,record,job)

if __name__=='__main__':
    LIBROOT=Path(sys.argv.pop(1));output=Path(sys.argv.pop(1));QUEUE=Path(sys.argv.pop(1));ORIGINAL_SOURCE=Path(sys.argv.pop(1));SOURCE_MANIFEST=Path(sys.argv.pop(1));ROOT_REFS=Path(sys.argv.pop(1));start=time.monotonic()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Contracts);result=unittest.TextTestRunner(verbosity=2).run(suite)
    report=dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),passed=result.wasSuccessful(),
                fits=0,api_calls=0,wall_seconds=time.monotonic()-start,
                source_sha256={p.name:h.sha(p) for p in Path(__file__).parent.glob('*.py')})
    h.write_new(output,report);raise SystemExit(0 if result.wasSuccessful() else 1)
