"""Prepared no-fit mock/CSV contracts; not executed during source preparation."""
from pathlib import Path
from contextlib import contextmanager
from collections import deque
import copy, csv, hashlib, importlib.util, tempfile, types, unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
controller=module('_brq_contract_controller',ROOT/'run_controller.py')
audit=module('_brq_contract_audit',ROOT/'artifact_audit.py')
closer=module('_brq_contract_closer',ROOT/'close_controller.py')

class LaunchParentContracts(unittest.TestCase):
    def _two_hop_fixture(self,directory,mode='normal'):
        exe=Path(directory)/'python.exe';exe.write_bytes(b'fixture-launcher-not-a-real-executable')
        class Shell:
            pid=10 if mode!='extra_hop' else 11
            def __init__(self):self.samples=0
            def create_time(self):
                self.samples+=1
                return 1700000000.0+(1 if mode=='shell_reuse' and self.samples>1 else 0)
            def parent(self):raise AssertionError('Must never traverse beyond one launcher')
        shell=Shell()
        class Launcher:
            pid=20
            def __init__(self):self.samples=0
            def create_time(self):
                self.samples+=1
                return 1700000000.43+(1 if mode=='launcher_reuse' and self.samples>1 else 0)
            def exe(self):
                if mode=='denied':raise PermissionError('fixture')
                return str(Path(directory)/'other.exe') if mode=='other_exe' else str(exe)
            def parent(self):return None if mode=='missing_shell' else shell
            def ppid(self):return 99 if mode=='reparent' else shell.pid
            def cmdline(self):raise AssertionError('No argv inspection')
        launcher=Launcher()
        class Me:
            pid=21
            def create_time(self):return 1700000001.0
            def parent(self):return launcher
            def ppid(self):return 99 if mode=='self_reparent' else 20
        return types.SimpleNamespace(Process=Me),exe,hashlib.sha256(exe.read_bytes()).hexdigest()

    def test_one_exact_pinned_launcher_binds_actual_direct_and_separate_declared_shell(self):
        for implementation in (controller,closer):
            with self.subTest(implementation=implementation.__name__),tempfile.TemporaryDirectory() as d:
                fake,exe,expected=self._two_hop_fixture(d)
                with patch.object(implementation,'LAUNCHER_PATH',exe),patch.object(implementation,'LAUNCHER_SHA',expected):
                    rows,receipt=implementation.capture(fake,10,1700000000.0)
                self.assertTrue(receipt['verified']);self.assertEqual(receipt['mode'],'one_pinned_venv_launcher')
                self.assertEqual(rows,[{'pid':21,'create_time':1700000001.0},
                    {'pid':20,'create_time':1700000000.43},{'pid':10,'create_time':1700000000.0}])
                self.assertEqual(receipt['observed_parent'],rows[1]);self.assertEqual(receipt['observed_shell'],rows[2])
                self.assertEqual(receipt['declared'],{'pid':10,'create_time':1700000000.0})
    def test_launcher_path_hash_extra_hop_reparent_reuse_or_denial_never_grant_parent(self):
        for implementation in (controller,closer):
            for mode in ('other_exe','wrong_hash','extra_hop','missing_shell','reparent','self_reparent','launcher_reuse','shell_reuse','denied'):
                with self.subTest(implementation=implementation.__name__,mode=mode),tempfile.TemporaryDirectory() as d:
                    fake,exe,expected=self._two_hop_fixture(d,mode)
                    if mode=='wrong_hash':expected='0'*64
                    with patch.object(implementation,'LAUNCHER_PATH',exe),patch.object(implementation,'LAUNCHER_SHA',expected):
                        rows,receipt=implementation.capture(fake,10,1700000000.0)
                    self.assertFalse(receipt['verified']);self.assertIn('error',receipt)
                    self.assertEqual(rows,[{'pid':21,'create_time':1700000001.0}])

    def test_actual_direct_parent_and_full_birth_saved_without_argv_parsing(self):
        class Parent:
            pid=20
            def create_time(self):return 1700000000.1234567
            def cmdline(self):raise AssertionError('Whole PowerShell -Command must never be parsed')
            def parent(self):raise AssertionError('Unrelated ancestor must never be adopted')
        class Me:
            pid=21
            def create_time(self):return 1700000001.25
            def parent(self):return Parent()
            def ppid(self):return 20
        fake=types.SimpleNamespace(Process=Me)
        for implementation in (controller,closer):
            with self.subTest(implementation=implementation.__name__):
                rows,receipt=implementation.capture(fake,20,1700000000.123457)
                self.assertTrue(receipt['verified']);self.assertEqual(len(rows),2)
                self.assertEqual(rows[1],{'pid':20,'create_time':1700000000.1234567})
                self.assertNotEqual(rows[1]['create_time'],receipt['declared']['create_time'])
    def test_missing_mismatch_reuse_and_denial_are_sticky_unverified_not_adopted(self):
        class Parent:
            pid=20
            def __init__(self,mode):self.mode=mode;self.samples=0
            def create_time(self):
                self.samples+=1
                if self.mode=='denied':raise PermissionError('fixture')
                return 1700000000.0+(1 if self.mode=='reuse' and self.samples>1 else 0)
        class Me:
            pid=21
            def __init__(self,mode):self.mode=mode;self.process=Parent(mode)
            def create_time(self):return 1700000001.0
            def parent(self):return None if self.mode=='missing' else self.process
            def ppid(self):return 99 if self.mode=='relationship' else 20
        for implementation in (controller,closer):
            for mode,pid,birth in [('missing',20,1700000000.0),('denied',20,1700000000.0),
                ('reuse',20,1700000000.0),('relationship',20,1700000000.0),('wrongPID',99,1700000000.0),
                ('wrongbirth',20,1700000002.0),('nonfinite',20,float('nan'))]:
                with self.subTest(implementation=implementation.__name__,mode=mode):
                    rows,receipt=implementation.capture(types.SimpleNamespace(Process=lambda:Me(mode)),pid,birth)
                    self.assertFalse(receipt['verified']);self.assertIn('error',receipt)
                    self.assertEqual(rows,[{'pid':21,'create_time':1700000001.0}])

class EnvironmentContracts(unittest.TestCase):
    def test_facade_copies_mapping_changes_only_AUTOML_THREADS_and_keeps_scrub(self):
        original={'PATH':'allowed','AUTOML_THREADS':'1','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'}
        calls=[]
        def environment(directory,model,manifest):calls.append(model);return original
        coor=types.SimpleNamespace(environment=environment)
        with controller.two_learner_threads(coor):
            actual=coor.environment('unused',False,{})
            self.assertEqual(actual,{**original,'AUTOML_THREADS':'2'});self.assertIsNot(actual,original)
        self.assertEqual(original['AUTOML_THREADS'],'1');self.assertEqual(calls,[False]);self.assertIs(coor.environment,environment)
    def test_facade_restores_on_primary_failure_and_refuses_model_API_route(self):
        def environment(*args):return {'AUTOML_THREADS':'1'}
        coor=types.SimpleNamespace(environment=environment);primary=ValueError('primary')
        with self.assertRaises(ValueError) as caught:
            with controller.two_learner_threads(coor):raise primary
        self.assertIs(caught.exception,primary);self.assertIs(coor.environment,environment)
        with controller.two_learner_threads(coor),self.assertRaisesRegex(RuntimeError,'API'):coor.environment(None,True,{})
    def test_facade_fails_closed_if_original_scrub_returns_credential(self):
        coor=types.SimpleNamespace(environment=lambda *args:{'OPENAI_API_KEY':'fixture-not-a-secret'})
        with controller.two_learner_threads(coor),self.assertRaisesRegex(RuntimeError,'scrub'):coor.environment(None,False,{})

class LexicalAuditContracts(unittest.TestCase):
    def test_stdlib_witness_keeps_NA_001_and_empty_distinct(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'classification.csv';path.write_text('id,out\n001,NA\nNA,001\nend,\n',encoding='utf-8')
            self.assertEqual(audit.lexical_witness(path,['out']),{'out':['NA','001','']})
    def test_proxy_converts_only_explicit_path_and_declared_class_cells(self):
        with tempfile.TemporaryDirectory() as d:
            import pandas as pd
            path=Path(d)/'predictions.csv';path.write_text('id,feature,target\n001,2.5,NA\nNA,,001\n',encoding='utf-8')
            proxy=audit.DeclaredClassCSV(pd,{str(path.resolve()):['target']})
            frame=proxy.read_csv(path,converters={'id':str});baseline=pd.read_csv(path,converters={'id':str})
            self.assertEqual(frame['id'].tolist(),['001','NA']);self.assertEqual(frame['target'].tolist(),['NA','001'])
            pd.testing.assert_series_equal(frame['feature'],baseline['feature'])
            other=Path(d)/'regression.csv';other.write_text('id,target\n001,1.25\n',encoding='utf-8')
            self.assertEqual(proxy.read_csv(other)['target'].dtype,pd.read_csv(other)['target'].dtype)
    def test_witness_rejects_duplicate_or_missing_headers_and_wrong_width(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'bad.csv'
            for raw in ['out,out\na,b\n','other\na\n','out\na,b\n']:
                path.write_text(raw,encoding='utf-8')
                with self.subTest(raw=raw),self.assertRaises(RuntimeError):audit.lexical_witness(path,['out'])

class VerifiedGuardContracts(unittest.TestCase):
    @contextmanager
    def fixture(self,deadline=200.):
        sampling=module('_brq_guard_sample_fixture',controller.WORK/'verified-resource-sampling-next-dev/verified_sampling.py')
        source=sampling.VerifiedResourceSampler;clock=types.SimpleNamespace(value=100.)
        plans={};reads=[];opens=[];power=[]
        defaults={10:dict(birth=1.,rss=11),20:dict(birth=2.,rss=17)}
        def factory(pid):
            opens.append(pid);queue=plans.get(pid);row=queue.popleft() if queue else defaults[pid]
            if isinstance(row,BaseException):raise row
            def memory_info():
                reads.append(pid);value=row.get('rss',7)
                if callable(value):value=value()
                if isinstance(value,BaseException):raise value
                return types.SimpleNamespace(rss=value)
            return types.SimpleNamespace(pid=pid,create_time=lambda:row['birth'],memory_info=memory_info)
        class Observer:
            def __init__(self):self.seen={(20,2.)};self.denials=[]
            def remember(self,rows):self.seen.update(rows)
            def observe(self):return {identity:object() for identity in self.seen}
        owner=types.SimpleNamespace(StrictOwnedObserver=Observer)
        awake=types.SimpleNamespace(handle=object(),heartbeat=lambda:(power.append(True) or dict(scheduling_gap_exceeded=False)))
        state={}
        with patch.object(controller.time,'monotonic',lambda:clock.value),patch.object(controller.time,'time',lambda:clock.value+1000):
            pulse=controller.guard(100.,deadline,deadline+1000,owner,[dict(pid=10,create_time=1.)],state,
                awake=awake,sampling=types.SimpleNamespace(VerifiedResourceSampler=lambda:source(factory)))
            yield types.SimpleNamespace(clock=clock,state=state,pulse=pulse,plans=plans,reads=reads,opens=opens,power=power,
                defaults=defaults,psutil=sampling.psutil)

    def test_exported_clock_only_hook_checks_original_history_without_RSS_power_or_sample_tick(self):
        with self.fixture() as f:
            f.pulse(force=True);self.assertEqual(f.state['actual_resource_samples'],1)
            counts=(len(f.opens),len(f.reads),len(f.power));receipt=f.state['verified_resource_sample']
            f.clock.value=100.5;f.state['_resource_checkpoint']()
            self.assertEqual((len(f.opens),len(f.reads),len(f.power)),counts)
            self.assertEqual(f.state['actual_resource_samples'],1);self.assertIs(f.state['verified_resource_sample'],receipt)
            # If the exported hook had advanced last-successful observation,
            # 110.25 would fit its new10s window. It must instead STOP.
            f.clock.value=110.25
            with self.assertRaisesRegex(RuntimeError,'gap10'):f.state['_resource_checkpoint']()
            self.assertEqual(f.state['actual_resource_samples'],1)
            self.assertEqual((len(f.opens),len(f.reads),len(f.power)),counts)
        for value,deadline,reason in [(99.,200.,'rollback'),(106.,105.,'deadline')]:
            with self.subTest(reason=reason),self.fixture(deadline) as f:
                f.clock.value=value
                with self.assertRaisesRegex(RuntimeError,reason):f.state['_resource_checkpoint']()
                self.assertEqual(f.opens,[]);self.assertEqual(f.power,[]);self.assertNotIn('actual_resource_samples',f.state)

    def test_verified_departure_keeps_known_provenance_and_established_peak(self):
        with self.fixture() as f:
            f.pulse(force=True);peak=f.state['peak_parent_bootstrap_mib']
            f.plans[20]=deque([f.psutil.NoSuchProcess(20),f.psutil.NoSuchProcess(20)])
            f.clock.value=101.;f.pulse(force=True)
            self.assertEqual(f.state['peak_parent_bootstrap_mib'],peak);self.assertEqual(f.state['actual_resource_samples'],2)
            sample=f.state['verified_resource_sample'];self.assertEqual(sample['known_count'],2)
            self.assertEqual(sample['sampled'],[dict(pid=10,create_time=1.,rss_bytes=11)])
            self.assertEqual(sample['departed'][0]['state'],'fresh_confirmed_absent')
            self.assertIsNone(sample['departed'][0]['rss_bytes']);self.assertEqual(len(f.state['departed_known_resource_identities']),1)

    def test_same_birth_or_denial_is_sticky_without_successful_timestamp_or_sample(self):
        for mode in ('same_birth','denied'):
            with self.subTest(mode=mode),self.fixture() as f:
                error=f.psutil.NoSuchProcess(20) if mode=='same_birth' else f.psutil.AccessDenied(20)
                f.plans[20]=deque([dict(birth=2.,rss=error),dict(birth=2.,rss=17)])
                with self.assertRaises(RuntimeError):f.pulse(force=True)
                count=len(f.opens);self.assertNotIn('actual_resource_samples',f.state)
                self.assertIn('guard_sticky_error',f.state)
                with self.assertRaises(RuntimeError):f.pulse(force=True)
                self.assertEqual(len(f.opens),count);self.assertEqual(f.power,[])

    def test_full_guard_enforces_cap_and_sampling_time_against_original_gap(self):
        for mode in ('overcap','slow_sample'):
            with self.subTest(mode=mode),self.fixture() as f:
                def slow():f.clock.value=111.;return 17
                f.defaults[20]['rss']=2048*2**20+1 if mode=='overcap' else slow
                with self.assertRaises(RuntimeError):f.pulse(force=True)
                self.assertNotIn('actual_resource_samples',f.state);self.assertIn('guard_sticky_error',f.state)
                self.assertEqual(f.power,[])

class VerifiedTerminalContracts(unittest.TestCase):
    def test_new_departure_requires_exact_root_stable_self_actual_exit_and_full_cleanup(self):
        departed=dict(pid=20,create_time=2.,state='fresh_confirmed_absent',replacement_create_time=None,rss_bytes=None)
        sample=dict(schema='verified-known-resource-sample-v1',sampled=[dict(pid=10,create_time=1.,rss_bytes=11)],
            departed=[departed],sampled_count=1,required_count=1,known_count=2,
            scope='sampled_stable_known_RSS_not_OS_lifetime_peak')
        record=dict(worker_resource_root=dict(pid=20,create_time=2.),worker_resource_self=dict(pid=10,create_time=1.),
            parent_observed_worker_exit_code=0,cleanup_confirmed=True,verified_resource_sample=sample,
            terminal_resource_observation=dict(status='fresh_known_root_departed_after_observed_exit',worker_root_rss_bytes=None,
                sampled_known_worker_rss_bytes=0,departed=[departed],remaining_owned_cleanup_still_required=True))
        self.assertTrue(audit.verified_terminal(record))
        changed=copy.deepcopy(record);row=changed['verified_resource_sample']['departed'][0]
        row.update(state='fresh_confirmed_reused',replacement_create_time=3.)
        changed['terminal_resource_observation']['departed']=copy.deepcopy(changed['verified_resource_sample']['departed'])
        self.assertTrue(audit.verified_terminal(changed))
        cases=[]
        for key,value in [('worker_resource_root',None),('worker_resource_root',dict(pid=21,create_time=2.)),
            ('worker_resource_self',dict(pid=11,create_time=1.)),('parent_observed_worker_exit_code',1),
            ('parent_observed_worker_exit_code',None),('parent_observed_worker_exit_code',False),('cleanup_confirmed',False)]:
            changed=copy.deepcopy(record);changed[key]=value;cases.append(changed)
        for key,value in [('remaining_owned_cleanup_still_required',False),('worker_root_rss_bytes',0),
            ('sampled_known_worker_rss_bytes',1),('departed',[])]:
            changed=copy.deepcopy(record);changed['terminal_resource_observation'][key]=value;cases.append(changed)
        for key,value in [('sampled',[]),('required_count',0),('known_count',1),('scope','unknown')]:
            changed=copy.deepcopy(record);changed['verified_resource_sample'][key]=value;cases.append(changed)
        changed=copy.deepcopy(record);changed['verified_resource_sample']['sampled'].append(dict(pid=20,create_time=2.,rss_bytes=17))
        changed['verified_resource_sample']['sampled_count']=2;cases.append(changed)
        for key,value in [('state','uncertain'),('rss_bytes',0),('create_time',float('nan'))]:
            changed=copy.deepcopy(record);changed['verified_resource_sample']['departed'][0][key]=value
            changed['terminal_resource_observation']['departed']=copy.deepcopy(changed['verified_resource_sample']['departed']);cases.append(changed)
        changed=copy.deepcopy(record);changed['verified_resource_sample']['sampled'][0]['rss_bytes']=2048*2**20+1;cases.append(changed)
        for index,changed in enumerate(cases):
            with self.subTest(case=index):self.assertFalse(audit.verified_terminal(changed))

if __name__=='__main__':unittest.main()
