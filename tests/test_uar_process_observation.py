"""Prepared mock contracts for strict observation; no real processes or fits."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from automl.infrastructure import processes


def member(pid, birth):
    value = Mock(pid=pid)
    value.create_time.return_value = birth
    value.children.return_value = []
    value.is_running.return_value = True
    value.status.return_value = 'running'
    value.memory_info.return_value.rss = 1
    return value


class StrictObservationTests(unittest.TestCase):
    def setUp(self):
        self.root = member(100, 10.)
        self.child = member(200, 20.)
        self.current = {100: self.root, 200: self.child}
        self.popen = Mock(pid=100, args=['inert-fixture'], returncode=0)
        self.popen.poll.return_value = None
        self.popen.wait.return_value = 0
        self.popen.terminate.side_effect = lambda: setattr(self.popen.poll, 'return_value', 0)

    def fake_psutil(self):
        return patch.object(processes.psutil, 'Process', side_effect=lambda pid: self.current[pid])

    def test_traversal_denial_is_sticky_and_owned_root_cleanup_is_attempted(self):
        self.root.children.side_effect = processes.psutil.AccessDenied(100)
        with self.fake_psutil(), patch.object(processes.psutil, 'wait_procs', return_value=([], [])):
            tree = processes.ProcessTree(self.popen, strict_observation=True)
            with self.assertRaises(processes.ProcessObservationError):
                tree.refresh()
            self.root.children.side_effect = None
            self.root.children.return_value = []
            with self.assertRaises(processes.ProcessObservationError):
                tree.refresh()
            with self.assertRaises(processes.ProcessObservationError):
                tree.terminate(grace=0)
        self.popen.terminate.assert_called_once()
        self.assertEqual(tree.observation_errors[0]['action'], 'discover_descendants')

    def test_unknown_child_birth_is_never_signalled(self):
        self.root.children.return_value = [self.child]
        self.child.create_time.side_effect = processes.psutil.AccessDenied(200)
        with self.fake_psutil(), patch.object(processes.psutil, 'wait_procs', return_value=([], [])):
            tree = processes.ProcessTree(self.popen, strict_observation=True)
            with self.assertRaises(processes.ProcessObservationError):
                tree.refresh()
            with self.assertRaises(processes.ProcessCleanupError):
                tree.terminate(grace=0)
        self.child.terminate.assert_not_called()
        self.child.kill.assert_not_called()

    def test_default_keeps_legacy_traversal_behavior_explicit(self):
        self.root.children.side_effect = processes.psutil.AccessDenied(100)
        with self.fake_psutil():
            tree = processes.ProcessTree(self.popen)
            tree.refresh()
            tree.require_observed()
        self.assertFalse(tree.strict_observation)
        self.assertEqual(tree.observation_errors, [])

    def test_reused_child_pid_is_not_adopted_or_signalled(self):
        self.root.children.return_value = [self.child]
        replacement = member(200, 21.)
        with self.fake_psutil(), patch.object(processes.psutil, 'wait_procs', return_value=([], [])):
            tree = processes.ProcessTree(self.popen, strict_observation=True)
            self.root.children.return_value = []
            self.current[200] = replacement
            tree.terminate(grace=0)
        self.assertNotIn((200, 21.), tree.members)
        replacement.terminate.assert_not_called()
        replacement.kill.assert_not_called()
        self.child.terminate.assert_not_called()

    def test_resource_read_denial_cannot_be_a_successful_wait(self):
        self.root.children.return_value = [self.child]
        self.child.memory_info.side_effect = processes.psutil.AccessDenied(200)
        with self.fake_psutil(), patch.object(processes.psutil, 'wait_procs', return_value=([], [])), \
                patch.object(processes.time, 'monotonic', return_value=0.), patch.object(processes.time, 'sleep'):
            with self.assertRaises(processes.ProcessCleanupError) as caught:
                processes.wait_owned(self.popen, timeout=1, memory_bytes=100, strict_observation=True)
        self.assertEqual(caught.exception.receipt['prior_failure_type'], 'ProcessObservationError')
        self.assertIn('inspect_memory', [v['action'] for v in caught.exception.receipt['actions']])
        self.child.terminate.assert_not_called()
        self.child.kill.assert_not_called()

    def terminal_wait(self, times, cleanup_error=None):
        tree = Mock(members={})
        if cleanup_error is not None:
            tree.terminate.side_effect = cleanup_error
        self.popen.poll.return_value = 0
        with patch.object(processes, 'ProcessTree', return_value=tree), \
                patch.object(processes.time, 'monotonic', side_effect=times):
            result = processes.wait_owned(self.popen, timeout=1, strict_observation=True)
        return result, tree

    def test_terminal_observed_before_deadline_returns_only_after_cleanup(self):
        result, tree = self.terminal_wait([0., .99, .99])
        self.assertEqual(result, 0)
        tree.terminate.assert_called_once()
        tree.require_observed.assert_called()

    def test_terminal_at_or_after_deadline_is_not_success(self):
        for observed in [1., 1.01]:
            with self.subTest(observed=observed):
                with self.assertRaises(subprocess.TimeoutExpired):
                    self.terminal_wait([0., observed])

    def test_cleanup_crossing_original_deadline_does_not_return_zero(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            self.terminal_wait([0., .5, 1.01])

    def test_terminal_cleanup_failure_stays_fatal(self):
        error = processes.ProcessCleanupError({'status': 'cleanup_unconfirmed', 'unresolved': [{'pid': 200}]})
        with self.assertRaises(processes.ProcessCleanupError) as caught:
            self.terminal_wait([0., .5], error)
        self.assertIs(caught.exception, error)

    def test_timeout_and_cleanup_failure_are_both_retained(self):
        tree = Mock(members={})
        tree.terminate.side_effect = processes.ProcessCleanupError(
            {'status': 'cleanup_unconfirmed', 'unresolved': [{'pid': 200}]})
        with patch.object(processes, 'ProcessTree', return_value=tree), \
                patch.object(processes.time, 'monotonic', side_effect=[0., 1.]):
            with self.assertRaises(processes.ProcessCleanupError) as caught:
                processes.wait_owned(self.popen, timeout=1, strict_observation=True)
        self.assertEqual(caught.exception.receipt['prior_failure_type'], 'TimeoutExpired')
        self.assertIsInstance(caught.exception.__cause__, subprocess.TimeoutExpired)
        tree.terminate.assert_called_once()


if __name__ == '__main__':
    unittest.main()
