"""Four source-only contracts. No model, solver, API or real Git invocation."""
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import argparse, copy, hashlib, importlib.util, json, sys, unittest

ARGS = None
NATIVE = 'research/remote-experiments/sources/native-cut-contract-v3-r2.json'
NATIVE_SHA = 'f5ad8c55aec198b689abf4bd8cf4ed0caf967fcd9f0d9f6db12f70513e1a60e5'
QUEUE_SHA = 'd42cb979db953eeffabfa65ee2a40d8763dfd835f91ce35149327f3d181e4c49'


def read(path):
    return json.loads(Path(path).read_text('utf-8'))


class NativeReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(ARGS.fixtures_root)
        cls.binding = read(cls.root/'compact-binding-example.json')
        cls.native_raw = (cls.root/'native-cut-contract-v3-r2.json').read_bytes()
        assert hashlib.sha256(cls.native_raw).hexdigest() == NATIVE_SHA
        cls.native = json.loads(cls.native_raw)
        cls.proof = read(cls.root/'reconstruction-proof.json')
        queue = Path(ARGS.queue_file)
        assert hashlib.sha256(queue.read_bytes()).hexdigest() == QUEUE_SHA
        spec = importlib.util.spec_from_file_location('_pinned_reference_queue', queue)
        cls.q = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.q)
        sys.path.insert(0, str(Path(ARGS.harness_dir).resolve()))
        import portable_harness
        cls.h = portable_harness

    def test_exact_expansion_preserves_canonical_private_binding(self):
        expanded = self.h.expand_native_references(self.binding, self.native)
        self.assertEqual(self.h.canonical(expanded),
                         self.proof['exact_full_binding_canonical_sha256'])
        self.assertEqual([r['private_job_sha256'] for r in expanded['components']],
                         self.proof['six_job_hashes'])
        self.assertNotIn('binding_schema', expanded)
        self.assertNotIn('native_contract_ref', expanded)

    def test_native_tamper_and_unknown_reference_are_refused(self):
        native = copy.deepcopy(self.native)
        for cut in native['cuts']:
            if cut['kind'] == 'classification' and cut['cut'] == 42:
                cut['native_profiles']['Linux']['members'][0]['dtype'] = '<f8'
        with self.assertRaises(self.h.Blocked):
            self.h.expand_native_references(self.binding, native)
        binding = copy.deepcopy(self.binding)
        binding['components'][0]['native_cut_canonical_sha256'] = '0'*64
        with self.assertRaises(self.h.Blocked):
            self.h.expand_native_references(binding, self.native)

    def test_unchanged_transport_limits_and_exact_typed_schema(self):
        self.q.bounded_json(self.binding)
        self.q.bounded_json(self.native)
        expanded = self.h.expand_native_references(self.binding, self.native)
        with self.assertRaises(Exception) as raised:
            self.q.bounded_json(expanded)
        self.assertIn('json_structure_cap', str(raised.exception))
        for field in ['binding_schema', 'native_contract_ref', 'components']:
            binding = copy.deepcopy(self.binding)
            binding.pop(field)
            with self.assertRaises(self.h.Blocked):
                self.h.expand_native_references(binding, self.native)
        binding = copy.deepcopy(self.binding)
        binding['encoded_components'] = 'opaque payload is not a supported field'
        with self.assertRaises(self.h.Blocked):
            self.h.expand_native_references(binding, self.native)

    def test_queue_admission_checks_actual_native_source_pin(self):
        binding = copy.deepcopy(self.binding)
        job_id, worker = binding['job_id'], binding['worker_id']
        path = 'research/remote-experiments/sources/'+job_id+'-execution-binding.json'
        payload = json.dumps(binding).encode()
        job = dict(id=job_id, kind='bounded_experiment', caps={'max_fits':16},
                   source_refs=[dict(path=path, sha256=hashlib.sha256(payload).hexdigest()),
                                dict(path=NATIVE, sha256=NATIVE_SHA)])
        import time
        claim = dict(worker_id=worker, dispatch_sha='d'*40, deadline_unix=time.time()+60)
        native_bytes = [self.native_raw]

        class GitFixture:
            def blob(_, dispatch, reference):
                if reference == path:
                    return payload
                if reference == NATIVE:
                    return native_bytes[0]
                raise AssertionError('unexpected fixture reference')

        # This unit isolates the new codec inside queue_admission. Real queue
        # claim/approval checks retain their separately tested implementation.
        fixture = SimpleNamespace(Git=lambda _:GitFixture(),
            read_claim=lambda *_:('c'*40, claim, job, None), jobs=lambda *_:None,
            bounded_admission=lambda *_:None, digest=self.q.digest, decode=self.q.decode)
        spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda _:None))
        with mock.patch('importlib.util.spec_from_file_location', return_value=spec), \
             mock.patch('importlib.util.module_from_spec', return_value=fixture):
            _, _, expanded = self.h.queue_admission('fixture', ARGS.queue_file,
                                                     QUEUE_SHA, job_id, worker, 'c'*40)
            self.assertEqual(self.h.canonical(expanded),
                             self.proof['exact_full_binding_canonical_sha256'])
            native_bytes[0] = self.native_raw+b' '
            with self.assertRaisesRegex(self.h.Blocked, 'native_reference_source_changed'):
                self.h.queue_admission('fixture', ARGS.queue_file,
                                       QUEUE_SHA, job_id, worker, 'c'*40)
            native_bytes[0] = self.native_raw
            job['source_refs'] = job['source_refs'][:1]
            with self.assertRaisesRegex(self.h.Blocked, 'native_reference_must_be_job_source'):
                self.h.queue_admission('fixture', ARGS.queue_file,
                                       QUEUE_SHA, job_id, worker, 'c'*40)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixtures-root', required=True)
    parser.add_argument('--harness-dir', required=True)
    parser.add_argument('--queue-file', required=True)
    ARGS = parser.parse_args()
    unittest.main(argv=[sys.argv[0], '-v'])
