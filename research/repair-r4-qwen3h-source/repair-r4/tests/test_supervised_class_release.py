"""Prospective mock contracts. Source prepared only; no author execution."""
import ast
from contextlib import ExitStack
import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'candidate'))
import automl_release_supervision as supervision


class SupervisedClassContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch('socket.create_connection',side_effect=AssertionError('No API')))
        self.stack.enter_context(patch('subprocess.Popen',side_effect=AssertionError('No processes')))
        self.now=[100.]
        self.stack.enter_context(patch.object(supervision.time,'monotonic',side_effect=lambda:self.now[0]))
        self.stack.enter_context(patch.object(supervision.time,'time',side_effect=lambda:1000.+self.now[0]))
        self.parent=SimpleNamespace(pid=10,create_time=lambda:1.,ppid=lambda:1)
        self.child=SimpleNamespace(pid=20,create_time=lambda:2.,ppid=lambda:10)
        self.stack.enter_context(patch.object(supervision.os,'getpid',return_value=20))
        self.stack.enter_context(patch.object(supervision.psutil,'Process',side_effect=lambda pid:self.parent if pid==10 else self.child))
        self.stack.enter_context(patch.object(supervision,'source_hashes',return_value={'x.py':'a'*64}))

    def manifest(self):
        return dict(schema='owned-class-parent-authority-v1',session='a'*32,
            parent_identity=[10,1.],child_identity=[20,2.],launch_identity=[20,2.],
            launch_executable='unused',launch_executable_sha256='b'*64,
            start_unix=1000.,start_monotonic=0.,global_deadline_unix=10900.,
            global_deadline_monotonic=9900.,declared_seconds=9900.,
            execution_deadline_unix=10870.,execution_deadline_monotonic=9870.,
            observation_path=str(self.directory/'observation.json'),source_sha256={'x.py':'a'*64},
            worker_cap=1536*2**20,whole_cap=2048*2**20)

    def observation(self,manifest,**changes):
        sample=dict(sequence=4,successful_sample_monotonic=self.now[0],
            sampled=[dict(pid=10,create_time=1.,rss_bytes=10),dict(pid=20,create_time=2.,rss_bytes=20)],
            departed=[],worker_tree_rss_bytes=20,whole_rss_bytes=30,
            maximum_observation_gap_seconds=.25,actual_successful_samples=4,failure=None)
        sample.update(changes)
        keys=('session','parent_identity','child_identity','start_unix','start_monotonic',
              'execution_deadline_unix','execution_deadline_monotonic')
        value=dict(schema='owned-class-parent-observation-v1',**{k:manifest[k] for k in keys},observation=sample)
        (self.directory/'observation.json').write_bytes(supervision.observation_frame(value))
        return value

    def authority(self,**changes):
        manifest=self.manifest();manifest.update(changes);self.observation(manifest)
        return supervision.DelegatedResourceAuthority(manifest,directory=self.directory)

    def test_real_fresh_parent_sample_covers_native_pause_without_child_sample_advance(self):
        authority=self.authority()
        self.assertEqual(authority.last_sequence,4)
        self.now[0]=300.
        self.observation(authority.manifest,sequence=800,actual_successful_samples=800)
        authority.check()
        self.assertEqual(authority.start_monotonic,0.)
        self.assertEqual(authority.last_sequence,800)

    def test_stale_parent_is_sticky_and_new_file_cannot_erase_failure(self):
        authority=self.authority();self.now[0]=111.
        with self.assertRaisesRegex(RuntimeError,'stale_or_unqualified') as first:authority.check()
        self.observation(authority.manifest,sequence=8,actual_successful_samples=8)
        with self.assertRaises(RuntimeError) as again:authority.check()
        self.assertIs(first.exception,again.exception)

    def test_missing_parent_sample_or_wrong_nonce_or_uncertainty_stops(self):
        for change in ('missing_child','nonce','uncertain'):
            with self.subTest(change=change):
                manifest=self.manifest();value=self.observation(manifest)
                if change=='missing_child':value['observation']['sampled']=value['observation']['sampled'][:1]
                elif change=='nonce':value['session']='b'*32
                else:value['observation']['failure']={'type':'AccessDenied'}
                (self.directory/'observation.json').write_bytes(supervision.observation_frame(value))
                with self.assertRaises(RuntimeError):supervision.DelegatedResourceAuthority(manifest,directory=self.directory)

    def test_denied_parent_and_reused_birth_never_grant_delegation(self):
        for error in (supervision.psutil.AccessDenied(10),None):
            manifest=self.manifest();self.observation(manifest)
            process=SimpleNamespace(pid=10,create_time=lambda:999.)
            with self.subTest(error=type(error).__name__),patch.object(supervision.psutil,'Process',
                    side_effect=error if error else lambda pid:process if pid==10 else self.child):
                with self.assertRaises((RuntimeError,supervision.psutil.AccessDenied)):
                    supervision.DelegatedResourceAuthority(manifest,directory=self.directory)

    def test_one_pinned_launcher_hop_allowed_extra_hop_and_wrong_hash_rejected(self):
        manifest=self.manifest();manifest['launch_identity']=[15,1.5]
        manifest['launch_executable']=str((self.directory/'python.exe').resolve())
        self.observation(manifest)
        intermediate=SimpleNamespace(pid=15,create_time=lambda:1.5,ppid=lambda:10,
            exe=lambda:manifest['launch_executable'])
        child=SimpleNamespace(pid=20,create_time=lambda:2.,ppid=lambda:15)
        def process(pid):return {10:self.parent,15:intermediate,20:child}[pid]
        with patch.object(supervision.psutil,'Process',side_effect=process),\
             patch.object(supervision,'file_sha',return_value='b'*64):
            supervision.DelegatedResourceAuthority(manifest,directory=self.directory)
        with patch.object(supervision.psutil,'Process',side_effect=process),\
             patch.object(supervision,'file_sha',return_value='c'*64):
            with self.assertRaisesRegex(RuntimeError,'interpreter_changed'):
                supervision.DelegatedResourceAuthority(manifest,directory=self.directory)
        intermediate.ppid=lambda:999
        with patch.object(supervision.psutil,'Process',side_effect=process):
            with self.assertRaisesRegex(RuntimeError,'extra_hop'):
                supervision.DelegatedResourceAuthority(manifest,directory=self.directory)

    def test_caps_clock_source_and_path_are_exact_not_relaxed(self):
        for key,value in [('worker_cap',2**31),('global_deadline_unix',10901.),
                          ('execution_deadline_monotonic',9900.),('observation_path',str(self.directory/'elsewhere.json'))]:
            manifest=self.manifest();manifest[key]=value;self.observation(manifest)
            with self.subTest(key=key),self.assertRaises(RuntimeError):
                supervision.DelegatedResourceAuthority(manifest,directory=self.directory)
        manifest=self.manifest();self.observation(manifest)
        with patch.object(supervision,'source_hashes',return_value={'x.py':'c'*64}):
            with self.assertRaisesRegex(RuntimeError,'source_changed'):
                supervision.DelegatedResourceAuthority(manifest,directory=self.directory)

    def test_successful_observation_must_be_bounded_and_nonfuture(self):
        for changes in [dict(successful_sample_monotonic=101.),dict(maximum_observation_gap_seconds=10.1),
                        dict(worker_tree_rss_bytes=1536*2**20+1),dict(whole_rss_bytes=2048*2**20+1),
                        dict(sequence=0,actual_successful_samples=0)]:
            manifest=self.manifest();self.observation(manifest,**changes)
            with self.subTest(changes=changes),self.assertRaises(RuntimeError):
                supervision.DelegatedResourceAuthority(manifest,directory=self.directory)

    def test_v16_portfolio_omits_inapplicable_feature_views_without_changing_REG(self):
        policy=importlib.import_module('automl_v16_class_policy')
        for categories in ([],['a']):
            values=policy.portfolio(dict(kind='classification',metric='macro_f1',features=['a','b'],
                categorical_features=categories,text_features=[]))
            self.assertFalse(any('feature_views' in r['params'] for r in values))
            self.assertTrue(any(r['engine']=='lightgbm' for r in values))
        inventory=json.loads((ROOT/'base-inventory.json').read_text())['members_sha256']
        for name in ('automl_fixed_release.py','automl_release_recipes.py','automl_worker.py',
                     'automl_evaluation.py','requirements.txt'):
            self.assertEqual(hashlib.sha256((ROOT/'candidate'/name).read_bytes()).hexdigest(),inventory[name])

    def test_v16_strict_adapter_requires_exact_original_clock_and_preserves_arguments(self):
        runner=importlib.import_module('automl_v16_class_runner')
        runtime=importlib.import_module('automl_release_runtime')
        clock=runtime.ReleaseClock.__new__(runtime.ReleaseClock)
        with self.assertRaisesRegex(RuntimeError,'typed release clock'):
            runner.run_worker({}, {},self.directory,'unused',30)
        token=runner._CLASS_RELEASE_CLOCK.set(clock)
        try:
            with patch.object(runner,'run_release_worker',return_value={'status':'ok'}) as called:
                runner.run_worker({'kind':'classification'},{'engine':'lightgbm'},self.directory,'split',30,
                    full_fit=True,fit_iterations=111)
            self.assertIs(called.call_args.kwargs['clock'],clock)
            self.assertEqual(called.call_args.kwargs['fit_iterations'],111)
        finally:runner._CLASS_RELEASE_CLOCK.reset(token)

    def test_inherited_budget_origin_and_deadline_charge_import_elapsed(self):
        release=importlib.import_module('automl_v16_class_release')
        authority=SimpleNamespace(start_monotonic=0.,deadline_monotonic=9870.)
        budget=release.inherited_budget(authority,self.directory)
        self.assertEqual(budget.started,0.);self.assertEqual(budget.deadline,9870.)
        self.assertEqual(budget.remaining(),9770.)
        self.assertEqual(budget.max_calls,0)

    def test_shared_pure_objective_body_equals_fixed_REG_authority(self):
        def function(path):
            tree=ast.parse(path.read_text(encoding='utf-8-sig'))
            return next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='resolved_policy')
        self.assertEqual(ast.dump(function(ROOT/'candidate/automl_release_authority.py')),
                         ast.dump(function(ROOT/'candidate/automl_fixed_release.py')))

    def test_safe_failure_records_first_type_and_location_without_exception_values(self):
        try:raise ValueError('untrusted private raw value')
        except ValueError as first:record=supervision.safe_failure(first)
        self.assertEqual(record['type'],'ValueError')
        self.assertIsNotNone(record['location'])
        self.assertNotIn('untrusted private raw value',json.dumps(record))

    def test_parent_sample_only_ticks_after_actual_success_and_denial_is_sticky(self):
        sampler=Mock();sampler.known={(20,2.)}
        sampler.sample.return_value=dict(sampled=[dict(pid=20,create_time=2.,rss_bytes=100)],departed=[])
        with patch.object(supervision,'VerifiedResourceSampler',return_value=sampler):
            clock=supervision.ParentObservationClock((1100.,100.),600,self.directory)
        clock.observe(force=True);self.assertEqual(clock.samples,1)
        self.now[0]=100.1;clock.observe();self.assertEqual(clock.samples,1)
        self.assertEqual(clock.last,100.)
        self.now[0]=100.25;clock.observe();self.assertEqual(clock.samples,2)
        sampler.sample.side_effect=supervision.psutil.AccessDenied(20)
        self.now[0]=100.5
        with self.assertRaises(supervision.psutil.AccessDenied) as first:clock.observe()
        sampler.sample.side_effect=None
        with self.assertRaises(supervision.psutil.AccessDenied) as again:clock.observe()
        self.assertIs(first.exception,again.exception);self.assertEqual(clock.last,100.25)

    def inert_parent_run(self,cleanup_error=None):
        own=(10,1.);child=(20,2.)
        observation=dict(sequence=1,successful_sample_monotonic=100.,
            sampled=[dict(pid=10,create_time=1.,rss_bytes=10),dict(pid=20,create_time=2.,rss_bytes=20)],
            departed=[],worker_tree_rss_bytes=20,whole_rss_bytes=30,
            maximum_observation_gap_seconds=.25,actual_successful_samples=1,failure=None)
        clock=SimpleNamespace(own=own,start_monotonic=0.,seconds=600.,end_monotonic=600.,end_unix=1600.,
            sampler=SimpleNamespace(known={own,child}),samples=1,max_gap=.25,peak_worker=20,peak_whole=30,
            check=lambda:None,observe=lambda *args,**kwargs:observation)
        process=Mock(pid=20,returncode=0);process.poll.return_value=0
        tree=Mock();tree.members={child:None};tree.process=process
        if cleanup_error:tree.terminate.side_effect=cleanup_error
        def spawn(*args,**kwargs):
            directory=self.directory/'automl_runs'/('class-supervision-'+'a'*32)
            (directory/'hello.json').write_text(json.dumps(dict(schema='owned-class-child-hello-v1',session='a'*32,child_identity=list(child))))
            (directory/'child-diagnostic.json').write_text(json.dumps(dict(status='completed')))
            return process
        with patch.object(supervision,'ParentObservationClock',return_value=clock),\
             patch.object(supervision.secrets,'token_hex',return_value='a'*32),\
             patch.object(supervision,'file_sha',return_value='b'*64),\
             patch.object(supervision.subprocess,'Popen',side_effect=spawn) as popen,\
             patch.object(supervision,'ProcessTree',return_value=tree):
            if cleanup_error:
                with self.assertRaises(supervision.ProcessCleanupError):
                    supervision.supervise_class(self.directory/'task.md',(1000.,0.),600)
            else:self.assertEqual(supervision.supervise_class(self.directory/'task.md',(1000.,0.),600),0)
        report=json.loads((self.directory/'automl_runs'/('class-supervision-'+'a'*32)/'supervision.json').read_text())
        return tree,popen,report

    def test_parent_success_requires_full_owned_cleanup_under_original_deadline(self):
        tree,popen,report=self.inert_parent_run()
        tree.terminate.assert_called_once();self.assertTrue(report['cleanup_confirmed'])
        self.assertEqual(report['global_deadline_monotonic'],600.)
        self.assertEqual(report['status'],'completed_pending_independent_qualification')
        self.assertFalse(report['qualified'])
        self.assertEqual(popen.call_args.kwargs['env']['AUTOML_THREADS'],'2')

    def test_parent_cleanup_uncertainty_preserves_failure_and_never_qualifies(self):
        error=supervision.ProcessCleanupError(dict(status='cleanup_unconfirmed',unresolved=[dict(pid=20)],actions=[]))
        tree,_,report=self.inert_parent_run(cleanup_error=error)
        tree.terminate.assert_called_once();self.assertFalse(report['cleanup_confirmed'])
        self.assertFalse(report['qualified']);self.assertEqual(report['first_failure']['type'],'ProcessCleanupError')


    def test_child_environment_keeps_model_threads_two_and_native_pools_one(self):
        native = ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
                  'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'BLIS_NUM_THREADS')
        inherited = dict.fromkeys(native, '99')
        inherited['AUTOML_THREADS'] = '99'
        with patch.dict(supervision.os.environ, inherited):
            _, popen, report = self.inert_parent_run()
        environment = popen.call_args.kwargs['env']
        self.assertEqual(environment['AUTOML_THREADS'], '2')
        self.assertEqual({name: environment[name] for name in native}, dict.fromkeys(native, '1'))
        self.assertTrue(report['cleanup_confirmed'])
        self.assertFalse(report['qualified'])


    def test_complete_frame_then_partial_append_keeps_only_still_fresh_real_sample(self):
        authority=self.authority();path=self.directory/'observation.json'
        with path.open('ab') as stream:stream.write(b'OBS1 000100 incomplete')
        authority.check();self.assertEqual(authority.last_sequence,4)
        self.now[0]=111.
        with self.assertRaisesRegex(RuntimeError,'stale_or_unqualified'):authority.check()

    def test_complete_bad_digest_never_falls_back_to_old_or_later_good_frame(self):
        authority=self.authority();path=self.directory/'observation.json'
        good=path.read_bytes();bad=bytearray(good);bad[20]=ord('f') if bad[20]!=ord('f') else ord('e')
        path.write_bytes(good+bytes(bad)+good)
        with self.assertRaisesRegex(RuntimeError,'frame_integrity'):authority.check()
        path.write_bytes(good)
        with self.assertRaisesRegex(RuntimeError,'frame_integrity'):authority.check()

    def test_seek_cut_fragment_and_maximum_partial_tail_preserve_latest_complete(self):
        path=self.directory/'observation.json'
        frames=[supervision.observation_frame({'n':n,'padding':'x'*200000}) for n in range(4)]
        path.write_bytes(b''.join(frames)+frames[-1][:-1])
        self.assertEqual(supervision.read_observation(path)['n'],3)
        self.assertGreater(path.stat().st_size,2*supervision.OBSERVATION_MAX_FRAME)
        full=supervision.observation_frame({'p':'x'*(supervision.OBSERVATION_MAX_JSON-8)})
        self.assertEqual(len(full),supervision.OBSERVATION_MAX_FRAME-2)
        bad=bytearray(full);bad[20]=ord('f') if bad[20]!=ord('f') else ord('e')
        prefix=supervision.observation_frame({'n':-1})
        path.write_bytes(prefix+bytes(bad)+full+b'OBS1')
        with self.assertRaisesRegex(RuntimeError,'frame_integrity'):supervision.read_observation(path)

    def test_unterminated_first_frame_and_complete_malformed_json_are_rejected(self):
        path=self.directory/'observation.json';path.write_bytes(supervision.observation_frame({'n':1})[:-1])
        with self.assertRaisesRegex(RuntimeError,'no_complete_frame'):supervision.read_observation(path)
        payload=b'not-json'
        path.write_bytes(('OBS1 %06x %s ' % (len(payload),hashlib.sha256(payload).hexdigest())).encode()+payload+b'\n')
        with self.assertRaises(json.JSONDecodeError):supervision.read_observation(path)

    def test_permanent_read_access_denial_is_immediate_sticky_without_cached_fallback(self):
        authority=self.authority();error=PermissionError(13,'synthetic observation denial')
        with patch.object(Path,'open',side_effect=error) as opened:
            with self.assertRaises(PermissionError) as first:authority.check()
        self.assertEqual(opened.call_count,1)
        self.assertIs(first.exception,error)
        with self.assertRaises(PermissionError) as second:authority.check()
        self.assertIs(second.exception,error)

    def test_write_denial_propagates_without_retry_or_atomic_replace(self):
        manifest=self.manifest();value=self.observation(manifest)
        error=PermissionError(13,'synthetic append denial')
        with patch.object(Path,'open',side_effect=error) as opened,patch.object(supervision,'atomic_json') as atomic:
            with self.assertRaises(PermissionError):
                supervision.write_observation(self.directory/'observation.json',manifest,value['observation'])
        self.assertEqual(opened.call_count,1);atomic.assert_not_called()

    def test_frame_size_bound_and_existing_clock_caps_are_not_extended_by_partial_append(self):
        with self.assertRaisesRegex(RuntimeError,'frame_size'):
            supervision.observation_frame({'padding':'x'*supervision.OBSERVATION_MAX_JSON})
        authority=self.authority();path=self.directory/'observation.json'
        with path.open('ab') as stream:stream.write(b'OBS1 ')
        self.now[0]=9870.
        with self.assertRaisesRegex(RuntimeError,'original_clock_invalid'):authority.check()
        self.assertEqual(authority.last_sequence,4)


class NativeObservationTransportContracts(unittest.TestCase):
    def test_native_concurrent_append_read_frames_without_replace_or_model_process(self):
        import threading,time
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'observation.json'
            path.write_bytes(supervision.observation_frame({'sequence':0}))
            errors=[];stop=threading.Event();seen=[]
            def writer():
                try:
                    for sequence in range(1,201):
                        raw=supervision.observation_frame({'sequence':sequence,'padding':'x'*1000})
                        with path.open('ab') as stream:
                            stream.write(raw[:len(raw)//2]);stream.flush()
                            time.sleep(.001)
                            stream.write(raw[len(raw)//2:]);stream.flush()
                except BaseException as error:errors.append(type(error).__name__)
                finally:stop.set()
            thread=threading.Thread(target=writer)
            with patch('socket.create_connection',side_effect=AssertionError('No API')),\
                 patch('subprocess.Popen',side_effect=AssertionError('No model processes')):
                thread.start();deadline=time.monotonic()+3
                try:
                    while not stop.is_set() and time.monotonic()<deadline:
                        seen.append(supervision.read_observation(path)['sequence'])
                    thread.join(max(0,deadline-time.monotonic()))
                finally:
                    thread.join(3)
            self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
            self.assertTrue(seen);self.assertEqual(seen,sorted(seen))
            self.assertEqual(supervision.read_observation(path)['sequence'],200)



if __name__=='__main__':unittest.main(verbosity=2)
