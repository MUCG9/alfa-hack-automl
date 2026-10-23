"""Narrow controller contracts; every child and ownership observation is synthetic."""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parent
SOURCE = WORK / 'fullagent_cv_coordinator_r4.py'
SOURCE_SHA = 'b85d04ec335a6cccefd3ed5214d05ea196fc4a62b619a054644b568c6d05d627'
COUNTS = {'network_attempts': 0, 'dummy_Popen_calls': 0}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def forbidden_network(*args, **kwargs):
    COUNTS['network_attempts'] += 1
    raise AssertionError('Network is forbidden in synthetic controller checks')


assert digest(SOURCE) == SOURCE_SHA
spec = importlib.util.spec_from_file_location('controller_under_mock', SOURCE)
controller = importlib.util.module_from_spec(spec)
with patch.object(socket.socket, 'connect', forbidden_network), patch.object(socket, 'create_connection', forbidden_network):
    spec.loader.exec_module(controller)


class NoSuchProcess(Exception):
    pass


class AccessDenied(Exception):
    pass


class SyntheticCase:
    def __init__(self, name, stage1, outside=False, cleanup_denied=False):
        self.root = ROOT / name
        self.output = self.root / 'f4'
        self.cwd = self.output / ('0a' if stage1 else 'sa')
        self.cwd.mkdir(parents=True)
        self.job = (self.output / 'gates' / 'a_source' if outside or not stage1 else self.cwd) / 'job.json'
        self.job.parent.mkdir(parents=True, exist_ok=True)
        self.job.write_text(json.dumps({'threads': 2, 'spec': {'paths': {}}}), encoding='utf-8')
        self.cleanup_denied = cleanup_denied
        self.starts = 0
        self.cleanup_calls = 0
        self.saves = 0
        self.child = None
        self.pid = 901
        self.created = 11.5
        case = self

        class Process:
            def __init__(self, pid=None):
                self.pid = case.pid if pid is not None else 999

            def create_time(self):
                return case.created

            def memory_info(self):
                return SimpleNamespace(rss=1024)

            def ppid(self):
                return 0

            def cmdline(self):
                return ['python', 'automl_worker.py', str(case.job)]

        class Observer:
            def __init__(self):
                self.seen, self.denials = set(), []

            def remember(self, values):
                self.seen.update(values)

            def observe(self):
                if case.cleanup_denied:
                    self.denials.append({'pid': case.pid, 'create_time': case.created, 'reason': 'AccessDenied'})
                return {(case.pid, case.created): Process(case.pid)}

            def denied(self, *args):
                self.denials.append({'reason': 'AccessDenied'})

        class Tree:
            def __init__(self, child):
                self.members = {(case.pid, case.created)}

        self.psutil = SimpleNamespace(Process=Process, NoSuchProcess=NoSuchProcess, AccessDenied=AccessDenied)
        self.owner = SimpleNamespace(StrictOwnedObserver=Observer, cleanup_owned=self.cleanup)
        self.processes = SimpleNamespace(ProcessTree=Tree)

    def popen(self, *args, **kwargs):
        COUNTS['dummy_Popen_calls'] += 1
        self.starts += 1
        case = self

        class Child:
            pid = case.pid
            returncode = 0
            polls = 0

            def poll(self):
                self.polls += 1
                return None if self.polls == 1 else 0

        self.child = Child()
        return self.child

    def cleanup(self, child, tree, observer, verified, factory):
        self.cleanup_calls += 1
        return {'cleanup_confirmed': not self.cleanup_denied,
                'owned_process_identities': [{'pid': self.pid, 'create_time': self.created}] if child else [],
                'unresolved': [{'pid': self.pid, 'reason': 'AccessDenied'}] if self.cleanup_denied else []}

    def save(self):
        self.saves += 1

    @contextmanager
    def patches(self):
        fake_subprocess = SimpleNamespace(Popen=self.popen, DEVNULL=-3, STDOUT=-2)
        with patch.dict(sys.modules, {'psutil': self.psutil}), \
                patch.object(controller, 'WORK', self.root, create=True), \
                patch.object(controller, 'OUTPUT', self.output, create=True), \
                patch.object(controller, 'guard', lambda manifest: None), \
                patch.object(controller, 'subprocess', fake_subprocess), \
                patch.object(controller.time, 'sleep', lambda seconds: None), \
                patch.object(socket.socket, 'connect', forbidden_network), \
                patch.object(socket, 'create_connection', forbidden_network):
            yield

    def run(self, *, stage1, expired=False, insufficient_reserve=False):
        now = time.monotonic()
        with self.patches():
            return controller.supervise(['dummy-controller-child'], self.cwd, self.root / 'supervisor.json',
                now + 10000, now - 1 if expired else now + 20000,
                time.time() - 1 if expired else time.time() + 20000,
                {}, self.owner, self.processes, self.save, stage1=stage1,
                admission_reserve=30000 if insufficient_reserve else 0)


class ControllerContracts(unittest.TestCase):
    def test_all_nine_shared_metadata_entries_are_required_in_both_arms(self):
        metadata = dict(controller.GATE_METADATA)
        binding = {'gate_metadata': metadata.copy(), 'arms': {
            arm: {'source_files_sha256': metadata.copy()} for arm in ['a', 'b']}}
        self.assertEqual(controller.gate_metadata(binding), metadata)
        for mutate in ['missing_map', 'missing_one', 'different_B_sha']:
            changed = deepcopy(binding)
            if mutate == 'missing_map':
                del changed['gate_metadata']
            elif mutate == 'missing_one':
                changed['gate_metadata'].pop(next(iter(metadata)))
            else:
                changed['arms']['b']['source_files_sha256'][next(iter(metadata))] = '0' * 64
            with self.subTest(mutate=mutate), self.assertRaises(controller.IntegrityError):
                controller.gate_metadata(changed)

    def prior_fixture(self):
        closure = 'fullagent-cv-stage0-terminal-ownership-r1.json'
        stage = {'status': 'failed_stage0', 'cleanup_confirmed': True, 'source_unchanged': True,
            'manifest_sha256': controller.PRIOR_MANIFEST_SHA, 'owned_root': {'pid': 11, 'create_time': 1.},
            'end_unix': 20.}
        launcher = {'status': 'stage0_exec_completed', 'exec_exit_code': 1,
            'manifest_sha256': controller.PRIOR_MANIFEST_SHA, 'source_sha256': controller.PRIOR_SOURCE_SHA,
            'launcher_identity': {'pid': 12, 'create_time': 2.}}
        gate = {'cleanup_confirmed': True, 'owned_root': {'pid': 13, 'create_time': 3.}}
        evidence = {'f3/stage0.json': '1' * 64, 'fullagent-cv-stage0-launch-r1.json': '2' * 64,
            'f3/gate-a_source.json': '3' * 64, 'f3/gates/a_source/results.json': '4' * 64,
            'f3/gates/a_source/test_error_preparation.py.log': '5' * 64}
        proof = {'status': 'failed_technical_Stage0_terminal_owned_absence_confirmed',
            'cleanup_confirmed': True, 'active_owned_processes': [], 'source_unchanged': True,
            'no_process_signalled': True, 'fresh_absence_before_and_inside_canonical_lock': True,
            'strict_known_parent_orphan_scan': True, 'clock_reset_or_retry': False,
            'CV_started': False, 'model_quality_inferred': False, 'metrics': None,
            'exec_exit_code_observed_by_root': 1, 'evidence_sha256': evidence.copy(),
            'stage_receipt': 'f3/stage0.json', 'launcher_receipt': 'fullagent-cv-stage0-launch-r1.json',
            'original_absolute_deadline_unix': 3600.,
            'tracked_identities': [{'pid': 11, 'create_time': 1.}, {'pid': 12, 'create_time': 2.},
                                   {'pid': 13, 'create_time': 3.}]}
        old_manifest = {'source_binding_sha256': 'f' * 64, 'coordinator_sha256': controller.PRIOR_SOURCE_SHA,
                        'API_limit': 0, 'immutable_files': {'example.py': 'a' * 64}}
        references = dict(evidence)
        references.update({closure: controller.PRIOR_CLOSURE_SHA,
            'fullagent-cv-launch-r1/manifest.json': controller.PRIOR_MANIFEST_SHA,
            'fullagent_cv_coordinator.py': controller.PRIOR_SOURCE_SHA,
            'fullagent-cv-launch-r1/source-binding.json': 'f' * 64})
        payloads = {closure: proof, 'f3/stage0.json': stage, 'fullagent-cv-stage0-launch-r1.json': launcher,
            'f3/gate-a_source.json': gate, 'fullagent-cv-launch-r1/manifest.json': old_manifest}
        return {'prior_technical_attempt': {'receipt': closure, 'sha256': references.copy()}}, payloads, references

    @contextmanager
    def prior_patches(self, payloads, references):
        # Every evidence object/hash is synthetic; no real old f3 receipt is opened.
        with patch.object(controller, 'resolve', lambda name: Path(name)), \
                patch.object(controller, 'load', lambda filename: deepcopy(payloads[str(filename).replace('\\', '/') ])), \
                patch.object(controller, 'digest', lambda filename: references[str(filename).replace('\\', '/')]):
            yield

    def test_expected_failed_prior_exec1_is_accepted_as_terminal_not_quality_gate(self):
        binding, payloads, references = self.prior_fixture()
        with self.prior_patches(payloads, references):
            result = controller.prior_technical_evidence(binding)
        self.assertEqual(result['identities'], {(11, 1.), (12, 2.), (13, 3.)})
        self.assertEqual(result['references'], references)
        self.assertEqual(result['finished_unix'], 20.)

    def test_missing_or_altered_prior_evidence_cannot_authorize_new_attempt(self):
        binding, payloads, references = self.prior_fixture()
        changed = deepcopy(binding)
        changed['prior_technical_attempt']['sha256'].pop('f3/gates/a_source/results.json')
        with self.prior_patches(payloads, references), self.assertRaises(controller.IntegrityError):
            controller.prior_technical_evidence(changed)
        with self.prior_patches(payloads, references), self.assertRaises(controller.IntegrityError):
            controller.prior_technical_evidence({})

    def test_live_unclean_changed_or_clock_reset_prior_proof_is_rejected(self):
        for field, value in [('cleanup_confirmed', False), ('source_unchanged', False),
                ('active_owned_processes', [{'pid': 11, 'create_time': 1.}]),
                ('clock_reset_or_retry', True), ('CV_started', True)]:
            binding, payloads, references = self.prior_fixture()
            payloads['fullagent-cv-stage0-terminal-ownership-r1.json'][field] = value
            with self.subTest(field=field), self.prior_patches(payloads, references), self.assertRaises(controller.IntegrityError):
                controller.prior_technical_evidence(binding)

    def test_prior_tracked_union_must_include_all_saved_owned_roots(self):
        binding, payloads, references = self.prior_fixture()
        payloads['fullagent-cv-stage0-terminal-ownership-r1.json']['tracked_identities'].pop()
        with self.prior_patches(payloads, references), self.assertRaises(controller.IntegrityError):
            controller.prior_technical_evidence(binding)

    def test_source_gate_worker_under_output_not_source_cwd_is_allowed(self):
        case = SyntheticCase('source-gate-path', stage1=False)
        result = case.run(stage1=False)
        self.assertEqual(result['status'], 'ok')
        self.assertTrue(result['cleanup_confirmed'])
        self.assertEqual(result['maximum_logical_worker_jobs'], 1)
        self.assertTrue(result['observed_workers'])
        self.assertEqual(case.starts, 1)

    def test_stage1_job_outside_exact_arm_is_rejected(self):
        case = SyntheticCase('outside-arm', stage1=True, outside=True)
        result = case.run(stage1=True)
        self.assertEqual(result['status'], 'technical_failure')
        self.assertEqual(result['exception_type'], 'IntegrityError')
        self.assertTrue(result['cleanup_confirmed'])
        self.assertEqual(case.cleanup_calls, 1)

    def test_exact_arm_job_positive_control_is_allowed(self):
        case = SyntheticCase('inside-arm', stage1=True)
        result = case.run(stage1=True)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['maximum_logical_worker_jobs'], 1)
        self.assertEqual(case.starts, 1)

    def test_exhausted_deadline_refuses_before_dummy_popen(self):
        case = SyntheticCase('expired', stage1=False)
        result = case.run(stage1=False, expired=True)
        self.assertEqual(result['status'], 'technical_failure')
        self.assertEqual(result['exception_type'], 'TimeoutError')
        self.assertEqual(case.starts, 0)
        self.assertNotIn('owned_root', result)

    def test_insufficient_full_admission_reserve_refuses_before_dummy_popen(self):
        case = SyntheticCase('reserve', stage1=True)
        result = case.run(stage1=True, insufficient_reserve=True)
        self.assertEqual(result['status'], 'technical_failure')
        self.assertEqual(result['exception_type'], 'TimeoutError')
        self.assertEqual(case.starts, 0)

    def test_cleanup_denial_raises_and_stops_next_admission(self):
        case = SyntheticCase('denied', stage1=True, cleanup_denied=True)
        with self.assertRaises(controller.IntegrityError):
            case.run(stage1=True)
            self.fail('Uncertain cleanup must stop before another admission')
        self.assertEqual(case.starts, 1)
        self.assertEqual(case.cleanup_calls, 1)
        saved = json.loads((case.root / 'supervisor.json').read_text(encoding='utf-8'))
        self.assertFalse(saved['cleanup_confirmed'])
        self.assertEqual(saved['status'], 'technical_failure')

    def test_post_audit_technical_invalidation_clears_nested_and_full_claims(self):
        receipt = {'path': 'synthetic-final-audit.json', 'sha256': 'b' * 64}
        report = {'complete_CV': True, 'OOF_complete': True,
            'final_CV': {'all_gates_passed': True, 'qualification': 'PASS', 'complete_CV': True},
            'full_three_fold_macro_f1_mean': {'a': .5, 'b': .6},
            'full_pooled_macro_f1': {'a': .5, 'b': .6}, 'final_CV_audit_receipt': receipt.copy()}
        controller.invalidate_cv_completion(report)
        self.assertFalse(report['complete_CV'])
        self.assertFalse(report['OOF_complete'])
        for name in ['final_CV', 'full_three_fold_macro_f1_mean', 'full_pooled_macro_f1']:
            self.assertIsNone(report[name])
        self.assertEqual(report['final_CV_audit_receipt'], receipt)
        self.assertEqual(report['final_CV_audit_qualification'], 'unqualified_due_to_technical_failure')


def main():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ControllerContracts)
    tick = time.monotonic()
    with (ROOT / 'checks.log').open('x', encoding='utf-8') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    forbidden = [m for m in sys.modules if m.split('.')[0] in {'numpy', 'pandas', 'sklearn', 'catboost', 'lightgbm', 'xgboost', 'optuna', 'requests'}]
    unchanged = digest(SOURCE) == SOURCE_SHA
    passed = result.wasSuccessful() and unchanged and not forbidden and not COUNTS['network_attempts']
    answer = {'status': 'passed' if passed else 'failed', 'source_sha256': SOURCE_SHA,
        'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
        'skips': len(result.skipped), 'source_unchanged': unchanged, 'seconds': time.monotonic() - tick,
        **COUNTS, 'learner_or_HTTP_modules_loaded': forbidden, 'real_worker_launches': 0,
        'actual_gates': 0, 'fits': 0, 'api_calls': 0, 'real_f3_or_tm1_accessed': False,
        'scope': 'Seven inherited controller plus five metadata/prior-failure synthetic contracts only; fake evidence/dummy children; no actual prior closure or Stage0/solver/CV qualification',
        'promotion': False}
    with (ROOT / 'results.json').open('x', encoding='utf-8') as stream:
        json.dump(answer, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(answer, ensure_ascii=True))
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
