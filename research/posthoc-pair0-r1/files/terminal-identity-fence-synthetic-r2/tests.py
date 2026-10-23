"""Synthetic ownership tests only. No real psutil inventory is consulted."""
from pathlib import Path
import importlib.abc
import importlib.util
import io
import json
import os
import threading
import socket
import sys
import types
import unittest

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
COUNTERS = {'network_calls': 0, 'forbidden_ml_imports': 0}


def forbidden_network(*args, **kwargs):
    COUNTERS['network_calls'] += 1
    raise RuntimeError('network_forbidden_in_synthetic_suite')


socket.socket = forbidden_network
socket.create_connection = forbidden_network


class NoMLImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'numpy', 'pandas', 'sklearn', 'catboost',
                'lightgbm', 'xgboost', 'optuna', 'requests', 'httpx', 'openai'}:
            COUNTERS['forbidden_ml_imports'] += 1
            raise RuntimeError('ML_or_API_import_forbidden_in_synthetic_suite')
        return None


sys.meta_path.insert(0, NoMLImports())
spec = importlib.util.spec_from_file_location('fenced_proposal', WORK/'terminal_identity_fence_r1.py')
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)
PARENT = candidate.PARENT
FENCE = candidate.FENCE_EPOCH
PROOF = WORK/'fullagent-cv-stage1-review-r4/stage0-terminal-ownership.json'


class NoSuchProcess(Exception):
    pass


class AccessDenied(Exception):
    pass


class FakeProcess:
    def __init__(self, pid, created, ppid=0, *, birth_denied=False,
                 status_denied=False, ppid_denied=False, status='running'):
        self.pid, self.created, self.parent_pid = pid, created, ppid
        self.birth_denied, self.status_denied = birth_denied, status_denied
        self.ppid_denied, self.saved_status = ppid_denied, status
        self.info = {'pid':pid, 'create_time':created, 'ppid':ppid, 'status':status}

    def create_time(self):
        if self.birth_denied:
            raise AccessDenied()
        return self.created

    def status(self):
        if self.status_denied:
            raise AccessDenied()
        return self.saved_status

    def ppid(self):
        if self.ppid_denied:
            raise AccessDenied()
        return self.parent_pid


class FakePsutil:
    NoSuchProcess, AccessDenied = NoSuchProcess, AccessDenied
    def __init__(self, entries=(), processes=(), *, inventory_denied=False,
                 after_inventory=None):
        self.entries = list(entries)
        self.processes = {p.pid:p for p in processes}
        self.inventory_denied = inventory_denied
        self.after_inventory = after_inventory
        self.reads = []

    def Process(self, pid):
        self.reads.append(pid)
        value = self.processes.get(pid)
        if isinstance(value, BaseException):
            raise value
        if value is None:
            raise NoSuchProcess()
        return value

    def process_iter(self, attrs, ad_value=None):
        if attrs != ['pid','ppid','create_time','status']:
            raise AssertionError('unexpected_inventory_fields')
        if self.inventory_denied:
            raise AccessDenied()
        if self.after_inventory:
            self.after_inventory(self)
        return list(self.entries)


def fake_owner(psutil):
    class Observer:
        def __init__(self):
            self.seen, self.denials = set(), []

        def remember(self, values):
            self.seen.update((p,float(c)) for p,c in values)

        def denied(self, pid, created, action, reason):
            self.denials.append({'pid':pid,'create_time':created,'action':action,'reason':reason})

        def observe(self):
            live = {}
            for p,c in list(self.seen):
                try:
                    cur = psutil.Process(p)
                    if cur.create_time() == c and cur.status() not in {'dead','zombie'}:
                        live[(p,c)] = cur
                except NoSuchProcess:
                    pass
                except AccessDenied:
                    self.denied(p,c,'verify_identity','AccessDenied')
            return live

        def final_check(self):
            live = self.observe()
            return {'unresolved':self.denials + list(live)}
    return types.SimpleNamespace(StrictOwnedObserver=Observer)


class FenceTests(unittest.TestCase):
    def call(self, fake, known=None, proof=PROOF):
        known = known or [{'pid':PARENT[0],'create_time':PARENT[1]}]
        return candidate.strict_orphan_check_with_one_fence(fake_owner(fake),known,proof,fake)

    def one_child(self, created, **kwargs):
        child = FakeProcess(901,created,PARENT[0],**kwargs)
        return FakePsutil([child],[child])

    def blocked(self, code, fake, known=None, proof=PROOF):
        with self.assertRaisesRegex(candidate.Blocked,'^'+code+'$'):
            self.call(fake,known,proof)

    def test_01_after_fence_child_of_pinned_absent_parent_excluded(self):
        result = self.call(self.one_child(FENCE+1))
        self.assertEqual(result['tracked_identities'],[{'pid':PARENT[0],'create_time':PARENT[1]}])
        self.assertEqual(len(result['excluded_impossible_parent_edges']),1)
        edge = result['excluded_impossible_parent_edges'][0]
        self.assertEqual(edge['proof_sha256'],candidate.CLOSURE_SHA256)
        self.assertEqual(edge['create_time'],FENCE+1)

    def test_02_equal_fence_child_adopted_and_blocks(self):
        self.blocked('strict_owned_orphan_denied_or_live',self.one_child(FENCE))

    def test_03_before_fence_child_adopted_and_blocks(self):
        self.blocked('strict_owned_orphan_denied_or_live',self.one_child(FENCE-1))

    def test_04_after_fence_child_of_unfenced_parent_blocks(self):
        other=(777,PARENT[1]-1)
        child=FakeProcess(901,FENCE+1,other[0])
        self.blocked('strict_owned_orphan_denied_or_live',FakePsutil([child],[child]),
            [{'pid':PARENT[0],'create_time':PARENT[1]},{'pid':other[0],'create_time':other[1]}])

    def test_05_matching_child_birth_missing_blocks(self):
        self.blocked('known_parent_orphan_birth_time_unverifiable',self.one_child(None))

    def test_06_matching_child_birth_nan_blocks(self):
        self.blocked('known_parent_orphan_birth_time_unverifiable',self.one_child(float('nan')))

    def test_07_matching_child_birth_bool_blocks(self):
        self.blocked('known_parent_orphan_birth_time_unverifiable',self.one_child(True))

    def test_08_parent_access_denied_after_inventory_blocks(self):
        fake=self.one_child(FENCE+1)
        fake.after_inventory=lambda f:f.processes.update({PARENT[0]:AccessDenied()})
        self.blocked('known_parent_orphan_parent_unverifiable',fake)

    def test_09_child_status_reverify_access_denied_blocks(self):
        self.blocked('known_parent_orphan_reverification_denied',self.one_child(FENCE+1,status_denied=True))

    def test_10_child_birth_reverify_access_denied_blocks(self):
        self.blocked('known_parent_orphan_reverification_denied',self.one_child(FENCE+1,birth_denied=True))

    def test_11_child_ppid_reverify_access_denied_blocks(self):
        self.blocked('known_parent_orphan_reverification_denied',self.one_child(FENCE+1,ppid_denied=True))

    def test_12_saved_exact_live_identity_blocks_before_inventory(self):
        parent=FakeProcess(*PARENT)
        self.blocked('strict_owned_identity_or_traversal_unresolved',FakePsutil([], [parent]))

    def test_13_saved_exact_identity_access_denied_blocks(self):
        fake=FakePsutil()
        fake.processes[PARENT[0]]=AccessDenied()
        self.blocked('strict_owned_identity_or_traversal_unresolved',fake)

    def test_14_proof_wrong_sha_blocks(self):
        bad=HERE/'tampered-proof.json'
        with bad.open('x',encoding='utf-8') as stream:stream.write('{}\n')
        self.blocked('historical_absence_proof_changed',FakePsutil(),proof=bad)

    def test_15_current_live_reused_parent_child_exclusion_preserved(self):
        parent=FakeProcess(PARENT[0],FENCE+1)
        child=FakeProcess(901,FENCE+2,PARENT[0])
        result=self.call(FakePsutil([child],[parent,child]))
        self.assertEqual(result['excluded_impossible_parent_edges'],[])
        self.assertEqual(len(result['tracked_identities']),1)

    def test_16_unfenced_incarnation_of_same_pid_not_exempt(self):
        old=PARENT[1]-1
        child=FakeProcess(901,FENCE+1,PARENT[0])
        self.blocked('strict_owned_orphan_denied_or_live',FakePsutil([child],[child]),
            [{'pid':PARENT[0],'create_time':PARENT[1]},{'pid':PARENT[0],'create_time':old}])

    def test_17_inventory_access_denied_blocks(self):
        self.blocked('orphan_inventory_enumeration_denied',FakePsutil(inventory_denied=True))

    def test_18_current_parent_unknown_birth_blocks(self):
        fake=self.one_child(FENCE+1)
        fake.after_inventory=lambda f:f.processes.update({PARENT[0]:FakeProcess(PARENT[0],None)})
        self.blocked('known_parent_birth_time_unknown',fake)

    def test_19_exact_parent_appearing_after_initial_check_blocks(self):
        fake=self.one_child(FENCE+1)
        fake.after_inventory=lambda f:f.processes.update({PARENT[0]:FakeProcess(*PARENT)})
        self.blocked('exact_historical_parent_alive',fake)

    def test_20_child_pid_reused_before_reverify_not_adopted(self):
        fake=self.one_child(FENCE+1)
        fake.after_inventory=lambda f:f.processes.update({901:FakeProcess(901,FENCE+100,0)})
        result=self.call(fake)
        self.assertEqual(result['excluded_impossible_parent_edges'],[])
        self.assertEqual(len(result['tracked_identities']),1)

    def test_21_child_ppid_changed_before_reverify_not_adopted(self):
        fake=self.one_child(FENCE+1)
        fake.after_inventory=lambda f:f.processes.update({901:FakeProcess(901,FENCE+1,0)})
        result=self.call(fake)
        self.assertEqual(result['excluded_impossible_parent_edges'],[])

    def test_22_child_disappeared_before_reverify_not_adopted(self):
        fake=self.one_child(FENCE+1)
        fake.after_inventory=lambda f:f.processes.pop(901)
        result=self.call(fake)
        self.assertEqual(result['excluded_impossible_parent_edges'],[])

    def test_23_prefence_uncertain_orphan_blocks_despite_late_sibling(self):
        early=FakeProcess(900,FENCE-1,PARENT[0])
        late=FakeProcess(901,FENCE+1,PARENT[0])
        self.blocked('strict_owned_orphan_denied_or_live',FakePsutil([late,early],[early,late]))

    def test_24_pinned_parent_missing_from_known_union_blocks(self):
        self.blocked('one_fence_parent_not_in_known_union',FakePsutil(),
                     [{'pid':777,'create_time':PARENT[1]}])

    def test_25_child_born_before_historical_parent_ignored(self):
        result=self.call(self.one_child(PARENT[1]-1))
        self.assertEqual(result['excluded_impossible_parent_edges'],[])

    def test_26_matching_child_pid_unknown_blocks(self):
        child=FakeProcess(901,FENCE+1,PARENT[0])
        child.info['pid']=None
        self.blocked('known_parent_child_pid_unknown',FakePsutil([child],[child]))


class RecordedResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.records=[]
    def addSuccess(self,test):
        super().addSuccess(test);self.records.append({'test':test.id(),'status':'PASS'})
    def addFailure(self,test,error):
        super().addFailure(test,error);self.records.append({'test':test.id(),'status':'FAIL','error':str(error[1])})
    def addError(self,test,error):
        super().addError(test,error);self.records.append({'test':test.id(),'status':'ERROR','error':str(error[1])})


if __name__=='__main__':
    with (HERE/'checks.log').open('x',encoding='utf-8') as stream:
        runner=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=RecordedResult)
        result=runner.run(unittest.defaultTestLoader.loadTestsFromTestCase(FenceTests))
    receipt={'status':'PASS' if result.wasSuccessful() else 'FAIL','tests_run':result.testsRun,
             'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
             'records':result.records,'tripwire_counters':COUNTERS,'real_model_fits':0,
             'real_API_calls':0,'real_process_inventory_calls':0,
             'python_execution_threads':threading.active_count(),
             'compute_thread_environment':{k:os.environ.get(k) for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS']},
             'scope':'Fake process topology and fake observer only; actual terminal closure not executed'}
    with (HERE/'results.json').open('x',encoding='utf-8') as stream:
        json.dump(receipt,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='records'}))
    raise SystemExit(0 if result.wasSuccessful() and COUNTERS=={'network_calls':0,'forbidden_ml_imports':0} and threading.active_count()==1 and all(os.environ.get(k)=='1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS']) else 1)
