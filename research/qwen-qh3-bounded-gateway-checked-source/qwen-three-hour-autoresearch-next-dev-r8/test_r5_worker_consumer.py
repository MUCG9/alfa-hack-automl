"""Prepared consumer regression fixture; no real Popen/model/network.

Source-only authoring.  A future root-owned flat test may use this same file:
only a source checkout has the sibling candidate directory below.
"""
from pathlib import Path
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch
import json
import sys
import tempfile
import unittest

candidate = Path(__file__).resolve().parent
sys.path.insert(0,str(candidate.parent/'alfa-hack-automl/src'))
if candidate.is_dir():
    sys.path.insert(0, str(candidate))
import r5_worker_runtime as runtime


class SamplingCheckpointConsumerContracts(unittest.TestCase):
    def test_unfinished_worker_resource_round_uses_only_original_clock_hook(self):
        events = []
        inside = [False]
        # Preserve the trusted exact ReleaseClock type without constructor IO.
        # No new or actual wall/monotonic clock is created by this fake.
        clock = object.__new__(runtime.ReleaseClock)
        def full_check(force=False):
            if inside[0]:
                raise AssertionError('Nested full RSS check during unfinished sample')
            events.append('outer_full_check')
        def clock_only():
            self.assertTrue(inside[0])
            events.append('original_clock_only')
        clock.check = full_check
        clock._resource_checkpoint = clock_only
        clock.remaining = lambda: 100.
        clock.receipt = lambda: {'synthetic_original_clock': True}
        process = Mock(pid=123, returncode=0)
        process.poll.return_value = 0
        tree = Mock()
        tree.members = {(123, 1.): object()}
        own = Mock(pid=99)
        own.create_time.return_value = 9.
        budget = SimpleNamespace(last_verified_sample=None, inspect_artifacts=lambda path: 0)
        def inspect(pid, root):
            self.assertEqual(pid, 123)
            inside[0] = True
            events.append('worker_round_begin')
            try:
                # Exercise the REAL callback installed by _run_worker_strict.
                budget._verified_sampling['checkpoint']()
                return None, 17, 28
            finally:
                events.append('worker_round_end')
                inside[0] = False
        budget.inspect = inspect
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'mock-worker'
            def spawn(*args, **kwargs):
                (output / 'result.json').write_text(json.dumps({'status': 'ok'}), encoding='utf-8')
                return process
            with patch.object(runtime.subprocess, 'Popen', side_effect=spawn), \
                 patch.object(runtime, 'ProcessTree', return_value=tree), \
                 patch.object(runtime, 'ResourceBudget', return_value=budget), \
                 patch.object(runtime.psutil, 'Process', return_value=own), \
                 patch.object(runtime.os, 'getpid', return_value=99), \
                 patch.object(runtime.time, 'monotonic', return_value=0.):
                result = runtime.run_release_worker({'root': directory}, {'engine': 'lightgbm', 'params': {}}, output,
                                                    'unused-synthetic-split', 100., clock=clock)
        self.assertEqual(result['status'], 'ok')
        self.assertTrue(result['cleanup_confirmed'])
        self.assertEqual(result['worker_resource_root'], {'pid': 123, 'create_time': 1.})
        self.assertEqual(result['worker_resource_self'], {'pid': 99, 'create_time': 9.})
        self.assertEqual(result['parent_observed_worker_exit_code'], 0)
        tree.terminate.assert_called_once()
        begin = events.index('worker_round_begin')
        end = events.index('worker_round_end')
        self.assertEqual(events[begin + 1:end], ['original_clock_only'])
        self.assertIn('outer_full_check', events[:begin])
        self.assertIn('outer_full_check', events[end + 1:])
        self.assertIsNone(runtime._CALLER_CLOCK.get())


class FirstActualResourceSampleContracts(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.now=[20.];self.inspection_delay=.25;self.inspection_error=None
        self.inspection_total=84;self.rounds=[]
        self.budget=SimpleNamespace(memory_limit=runtime.WHOLE_MEMORY_LIMIT_BYTES)
        def inspect(pid,root):
            self.assertEqual(pid,99)
            clock=self.budget._verified_sampling['checkpoint'].__self__
            self.rounds.append(dict(clock=clock,last=clock.last,samples=clock.samples))
            self.budget._verified_sampling['checkpoint']()
            self.now[0]+=self.inspection_delay
            if self.inspection_error is not None:raise self.inspection_error
            return None,42,self.inspection_total
        self.budget.inspect=Mock(side_effect=inspect)
        own=SimpleNamespace(pid=99,create_time=lambda:9.)
        for target,name,value in [(runtime,'ResourceBudget',Mock(return_value=self.budget)),
                (runtime,'VerifiedResourceSampler',Mock(return_value=object())),
                (runtime.psutil,'Process',Mock(return_value=own)),
                (runtime.os,'getpid',lambda:99),
                (runtime.time,'monotonic',lambda:self.now[0]),
                (runtime.time,'time',lambda:1000.+self.now[0])]:
            self.stack.enter_context(patch.object(target,name,value))

    def create(self):
        return runtime.ReleaseClock(4800,'unused-synthetic-root',origin=(1000.,0.))

    def test_slow_import_before_first_real_sample_keeps_original_clock_and_unknown_prior(self):
        clock=self.create()
        self.assertIsNone(self.rounds[0]['last']);self.assertEqual(self.rounds[0]['samples'],0)
        self.assertEqual((clock.start_unix,clock.start_monotonic),(1000.,0.))
        self.assertEqual((clock.deadline_unix,clock.deadline_monotonic),(5800.,4800.))
        self.assertEqual(clock.last,20.25);self.assertEqual(clock.samples,1)
        self.assertEqual(clock.sampling_identity,(99,9.))
        self.assertEqual(clock.resources._verified_sampling['self_identity'],(99,9.))
        self.assertEqual(clock.resources._verified_sampling['root_identity'],(99,9.))
        self.assertIs(clock.resources._verified_sampling['checkpoint'].__self__,clock)
        self.assertEqual(clock.receipt()['actual_resource_samples'],1)
        self.assertEqual(clock.receipt()['last_actual_resource_observation'],
            dict(parent_tree_rss_bytes=42,conservative_combined_bytes=84))
        self.budget.inspect.assert_called_once_with(99,Path('unused-synthetic-root'))

    def test_slow_or_denied_or_over_cap_first_inspection_never_becomes_a_sample(self):
        self.inspection_delay=10.001
        with self.assertRaisesRegex(RuntimeError,'resource_inspection_gap') as first:self.create()
        clock=self.rounds[-1]['clock'];self.assertIsNone(clock.last);self.assertEqual(clock.samples,0)
        self.assertIs(clock.failure,first.exception)
        with self.assertRaises(RuntimeError) as sticky:clock.check(force=True)
        self.assertIs(sticky.exception,first.exception);self.assertEqual(self.budget.inspect.call_count,1)
        self.inspection_delay=.25;self.inspection_error=PermissionError('synthetic actual observation denial')
        with self.assertRaises(PermissionError) as denied:self.create()
        denied_clock=self.rounds[-1]['clock'];self.assertIsNone(denied_clock.last)
        self.assertEqual(denied_clock.samples,0);self.assertIs(denied_clock.failure,denied.exception)
        self.inspection_error=None;self.inspection_total=runtime.WHOLE_MEMORY_LIMIT_BYTES+1
        with self.assertRaisesRegex(RuntimeError,'whole_memory_limit'):self.create()
        self.assertIsNone(self.rounds[-1]['clock'].last)
        self.assertEqual(self.rounds[-1]['clock'].samples,0)

    def test_later_observation_gap_stays_sticky_and_deadline_cannot_rebase(self):
        clock=self.create();last=clock.last;self.now[0]=last+10.001
        with self.assertRaisesRegex(RuntimeError,'observation_gap_over10s') as first:clock.check()
        self.assertEqual(clock.last,last);self.assertEqual(clock.samples,1)
        self.assertEqual(self.budget.inspect.call_count,1)
        with self.assertRaises(RuntimeError) as sticky:clock.check(force=True)
        self.assertIs(sticky.exception,first.exception)
        self.assertEqual((clock.deadline_unix,clock.deadline_monotonic),(5800.,4800.))
        self.now[0]=4800.
        with self.assertRaisesRegex(RuntimeError,'original_common_deadline'):self.create()


if __name__ == '__main__':
    unittest.main()
