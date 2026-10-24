"""Fourteen prepared mock contracts; no real processes, models or network.
The author has NOT imported this module or executed these tests.
"""
from collections import deque
from types import SimpleNamespace
import unittest
import psutil
from verified_sampling import ResourceSamplingError, VerifiedResourceSampler

SELF = (10, 1.0)
CHILD = (20, 2.0)


class FakeProcess:
    def __init__(self, backend, pid, spec):
        self.backend, self.pid, self.spec = backend, pid, spec

    def create_time(self):
        value = self.spec.get('birth', float(self.pid) / 10)
        if isinstance(value, BaseException):
            raise value
        return value

    def memory_info(self):
        self.backend.reads.append((self.pid, self.spec.get('birth', float(self.pid) / 10)))
        value = self.spec.get('rss', 7)
        if isinstance(value, BaseException):
            raise value
        return SimpleNamespace(rss=value)

    def children(self, recursive):
        if recursive is not True:
            raise AssertionError('Owned recursive traversal required')
        value = self.spec.get('children', [])
        if isinstance(value, BaseException):
            raise value
        return value


class Backend:
    def __init__(self, plans=None, defaults=None):
        self.plans = {pid: deque(rows) for pid, rows in (plans or {}).items()}
        self.defaults = {10: {'birth': 1., 'rss': 11}, 20: {'birth': 2., 'rss': 17}}
        self.defaults.update(defaults or {})
        self.opens, self.reads = [], []

    def __call__(self, pid):
        self.opens.append(pid)
        rows = self.plans.get(pid)
        value = rows.popleft() if rows else self.defaults[pid]
        if isinstance(value, BaseException):
            raise value
        return FakeProcess(self, pid, value)


class VerifiedSamplingContracts(unittest.TestCase):
    def sample(self, sampler, identities=(SELF, CHILD), checkpoint=lambda: None):
        return sampler.sample(identities, required=[SELF], checkpoint=checkpoint)

    def test_stable_fresh_before_and_after_RSS_and_exact_raw_bytes(self):
        backend = Backend()
        sampler = VerifiedResourceSampler(backend)
        result = self.sample(sampler)
        self.assertEqual(backend.opens, [10, 10, 20, 20])
        self.assertEqual([(r['pid'], r['rss_bytes']) for r in result['sampled']], [(10, 11), (20, 17)])
        self.assertEqual(result['departed'], [])
        self.assertEqual(sampler.successful_rounds, 1)

    def test_missing_known_child_requires_second_fresh_absence(self):
        backend = Backend({20: [psutil.NoSuchProcess(20), psutil.NoSuchProcess(20)]})
        sampler = VerifiedResourceSampler(backend)
        result = self.sample(sampler)
        self.assertEqual(backend.opens.count(20), 2)
        self.assertEqual(result['departed'][0]['state'], 'fresh_confirmed_absent')
        self.assertIsNone(result['departed'][0]['rss_bytes'])
        self.assertEqual([r['pid'] for r in result['sampled']], [10])
        self.assertIn(CHILD, sampler.known)

    def test_memory_NoSuch_then_fresh_reuse_never_reads_new_process(self):
        backend = Backend({20: [{'birth': 2., 'rss': psutil.NoSuchProcess(20)}, {'birth': 3., 'rss': 999}]})
        sampler = VerifiedResourceSampler(backend)
        result = self.sample(sampler)
        self.assertEqual(result['departed'][0]['state'], 'fresh_confirmed_reused')
        self.assertEqual(result['departed'][0]['replacement_create_time'], 3.)
        self.assertNotIn((20, 3.), backend.reads)
        self.assertIn(CHILD, sampler.known)
        self.assertNotIn((20, 3.), sampler.known)

    def test_same_original_identity_after_NoSuch_is_sticky_STOP(self):
        backend = Backend({20: [{'birth': 2., 'rss': psutil.NoSuchProcess(20)}, {'birth': 2.}]})
        sampler = VerifiedResourceSampler(backend)
        with self.assertRaisesRegex(ResourceSamplingError, 'same_identity') as caught:
            self.sample(sampler)
        count = len(backend.opens)
        with self.assertRaises(ResourceSamplingError) as again:
            self.sample(sampler)
        self.assertIs(caught.exception, again.exception)
        self.assertEqual(len(backend.opens), count)
        self.assertEqual(sampler.successful_rounds, 0)

    def test_first_AccessDenied_cannot_be_erased_by_later_absence(self):
        backend = Backend({20: [{'birth': 2., 'rss': psutil.AccessDenied(20)}, psutil.NoSuchProcess(20)]})
        sampler = VerifiedResourceSampler(backend)
        with self.assertRaises(ResourceSamplingError) as caught:
            self.sample(sampler)
        self.assertEqual(caught.exception.receipt['exception_type'], 'AccessDenied')
        count = len(backend.opens)
        with self.assertRaises(ResourceSamplingError) as again:
            sampler.confirm_departed(CHILD, checkpoint=lambda: None)
        self.assertIs(caught.exception, again.exception)
        self.assertEqual(len(backend.opens), count)

    def test_recheck_denial_or_unknown_exception_is_not_departure(self):
        for error in [psutil.AccessDenied(20), ValueError('private text must not escape')]:
            with self.subTest(kind=type(error).__name__):
                backend = Backend({20: [psutil.NoSuchProcess(20), error]})
                sampler = VerifiedResourceSampler(backend)
                with self.assertRaises(ResourceSamplingError) as caught:
                    self.sample(sampler)
                self.assertEqual(sampler.departed, [])
                self.assertEqual(caught.exception.receipt['exception_type'], type(error).__name__)
                self.assertNotIn('private text', str(caught.exception))

    def test_missing_untyped_or_nonfinite_identity_stops_before_PID_open(self):
        for bad in [None, (True, 1.), (0, 1.), (20, None), (20, float('nan')), (20, float('inf'))]:
            with self.subTest(identity=bad):
                backend = Backend(); sampler = VerifiedResourceSampler(backend)
                with self.assertRaises(ResourceSamplingError):
                    sampler.sample([bad], required=[SELF], checkpoint=lambda: None)
                self.assertEqual(backend.opens, [])
                self.assertIsNotNone(sampler.failure)
        sampler = VerifiedResourceSampler(Backend())
        with self.assertRaises(ResourceSamplingError):
            sampler.sample(None, required=[SELF], checkpoint=lambda: None)
        backend = Backend(); sampler = VerifiedResourceSampler(backend)
        with self.assertRaises(ResourceSamplingError):
            sampler.sample([SELF], required=[SELF], checkpoint=None)
        self.assertEqual(backend.opens, [])

    def test_post_RSS_disappearance_discards_unstable_value_not_to_zero(self):
        backend = Backend({20: [{'birth': 2., 'rss': 123}, psutil.NoSuchProcess(20), psutil.NoSuchProcess(20)]})
        sampler = VerifiedResourceSampler(backend)
        result = self.sample(sampler)
        self.assertEqual([r['pid'] for r in result['sampled']], [10])
        self.assertIsNone(result['departed'][0]['rss_bytes'])
        self.assertIn(CHILD, sampler.known)
        self.assertEqual(sampler.successful_rounds, 1)

    def test_mandatory_self_cannot_be_dropped_or_omitted(self):
        backend = Backend({10: [psutil.NoSuchProcess(10), psutil.NoSuchProcess(10)]})
        sampler = VerifiedResourceSampler(backend)
        with self.assertRaisesRegex(ResourceSamplingError, 'mandatory_identity_not_sampled'):
            self.sample(sampler, [SELF])
        self.assertEqual(sampler.successful_rounds, 0)
        for identities, required in [([], [SELF]), ([SELF], [])]:
            sampler = VerifiedResourceSampler(Backend())
            with self.assertRaises(ResourceSamplingError):
                sampler.sample(identities, required=required, checkpoint=lambda: None)

    def test_over_cap_RSS_is_preserved_not_clamped_for_consumer_caps(self):
        for amount in [1536 * 2**20, 1536 * 2**20 + 1, 2048 * 2**20 + 1]:
            backend = Backend(defaults={20: {'birth': 2., 'rss': amount}})
            result = self.sample(VerifiedResourceSampler(backend))
            self.assertEqual(next(r['rss_bytes'] for r in result['sampled'] if r['pid'] == 20), amount)
        for invalid in [True, -1, float('nan')]:
            sampler = VerifiedResourceSampler(Backend(defaults={20: {'birth': 2., 'rss': invalid}}))
            with self.assertRaises(ResourceSamplingError):
                self.sample(sampler)

    def test_caller_deadline_or_gap_during_confirmation_is_sticky(self):
        for failure in [TimeoutError('original caller deadline'),
                        RuntimeError('original gap over10'), RuntimeError('original clock rollback')]:
            with self.subTest(failure=type(failure).__name__, code=str(failure)):
                backend = Backend({20: [psutil.NoSuchProcess(20), psutil.NoSuchProcess(20)]})
                sampler = VerifiedResourceSampler(backend)
                def checkpoint():
                    if backend.opens.count(20) >= 2:
                        raise failure
                with self.assertRaises(type(failure)) as caught:
                    self.sample(sampler, checkpoint=checkpoint)
                self.assertIs(caught.exception, failure)
                self.assertEqual(sampler.successful_rounds, 0)
                self.assertIsNone(sampler.last_receipt)
                with self.assertRaises(type(failure)) as again:
                    self.sample(sampler)
                self.assertIs(again.exception, failure)

    def test_success_then_later_denial_preserves_prior_receipt_and_known(self):
        backend = Backend(); sampler = VerifiedResourceSampler(backend)
        first = self.sample(sampler)
        backend.plans[20] = deque([{'birth': 2., 'rss': psutil.AccessDenied(20)}])
        with self.assertRaises(ResourceSamplingError):
            self.sample(sampler)
        self.assertIs(sampler.last_receipt, first)
        self.assertEqual(sampler.successful_rounds, 1)
        self.assertEqual(sampler.known, {SELF, CHILD})

    def test_metadata_consumer_confirmation_requires_fresh_absence_not_same_birth(self):
        backend = Backend({20: [{'birth': 3., 'rss': 999}]})
        sampler = VerifiedResourceSampler(backend)
        row = sampler.confirm_departed(CHILD, checkpoint=lambda: None)
        self.assertEqual(row['state'], 'fresh_confirmed_reused')
        self.assertEqual(backend.reads, [])
        self.assertEqual(sampler.successful_rounds, 0)
        with self.assertRaises(ResourceSamplingError):
            VerifiedResourceSampler(Backend()).confirm_departed(CHILD, checkpoint=lambda: None)

    def test_owned_tree_discovery_preserves_known_and_rejects_unverified_birth(self):
        backend = Backend()
        child = FakeProcess(backend, 20, {'birth': 2.})
        backend.plans[10] = deque([{'birth': 1., 'children': [child]}, {'birth': 1.}])
        sampler = VerifiedResourceSampler(backend)
        sampler.discover_owned_tree(SELF, checkpoint=lambda: None)
        self.assertEqual(sampler.known, {SELF, CHILD})
        self.assertEqual(sampler.successful_rounds, 0)
        result = self.sample(sampler, list(sampler.known))
        self.assertEqual(result['sampled_count'], 2)
        broken = FakeProcess(backend, 30, {'birth': psutil.NoSuchProcess(30)})
        other = Backend({10: [{'birth': 1., 'children': [broken]}]})
        with self.assertRaisesRegex(ResourceSamplingError, 'discovered_birth_unverified'):
            VerifiedResourceSampler(other).discover_owned_tree(SELF, checkpoint=lambda: None)


if __name__ == '__main__':
    unittest.main()
