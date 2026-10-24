"""Prepared no-fit mock/CSV contracts; not executed during source preparation."""
from pathlib import Path
import csv, hashlib, importlib.util, tempfile, types, unittest
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

if __name__=='__main__':unittest.main()
