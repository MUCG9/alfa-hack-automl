"""Prepared consumer regression fixture; no real Popen/model/network.

Source-only authoring.  A future root-owned flat test may use this same file:
only a source checkout has the sibling candidate directory below.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import json
import sys
import tempfile
import unittest

candidate = Path(__file__).resolve().parents[1] / 'candidate'
if candidate.is_dir():
    sys.path.insert(0, str(candidate))
import automl_release_runtime as runtime


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


if __name__ == '__main__':
    unittest.main()
