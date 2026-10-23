"""Fake PID reuse must never reach discovery, signals, or waits for another owner."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from automl.infrastructure import processes


def fake_member(pid,created):
    member=Mock()
    member.pid=pid
    member.create_time.return_value=created
    member.children.return_value=[]
    member.is_running.return_value=True
    return member


class ProcessIdentityTests(unittest.TestCase):
    def setUp(self):
        self.root=fake_member(100,10.)
        self.child=fake_member(200,20.)
        self.root.children.return_value=[self.child]
        self.current={100:self.root,200:self.child}
        self.popen=Mock(pid=100,args=['owned-fixture'])
        self.popen.poll.return_value=None
        self.popen.wait.return_value=0
        self.popen.terminate.side_effect=lambda:setattr(self.popen.poll,'return_value',0)
        self.factory=patch.object(processes.psutil,'Process',side_effect=self.lookup).start()
        self.addCleanup(patch.stopall)
        self.wait=patch.object(processes.psutil,'wait_procs',side_effect=lambda members,timeout:(members,[])).start()
        self.tree=processes.ProcessTree(self.popen)
        self.root.children.return_value=[]
        self.root.children.reset_mock()
        self.child.children.reset_mock()
        self.factory.reset_mock()

    def lookup(self,pid):
        if pid not in self.current:
            raise processes.psutil.NoSuchProcess(pid)
        return self.current[pid]

    def reuse_child(self):
        reused=fake_member(200,99.)
        self.current[200]=reused
        return reused

    def assert_no_signal_or_discovery(self,member):
        member.children.assert_not_called()
        member.terminate.assert_not_called()
        member.kill.assert_not_called()

    def test_reused_child_is_removed_before_refresh_or_cleanup(self):
        reused=self.reuse_child()
        self.tree.refresh()
        self.tree.terminate()
        self.assertNotIn((200,20.),self.tree.members)
        self.assert_no_signal_or_discovery(self.child)
        self.assert_no_signal_or_discovery(reused)
        self.assertTrue(all(member.pid!=200 for call in self.wait.call_args_list for member in call.args[0]))

    def test_identity_is_rechecked_after_refresh_before_terminate(self):
        with patch.object(self.tree,'refresh',side_effect=self.reuse_child):
            self.tree.terminate()
        self.child.terminate.assert_not_called()
        self.assert_no_signal_or_discovery(self.current[200])

    def test_live_owned_child_terminates_and_root_uses_popen(self):
        self.tree.terminate()
        self.child.terminate.assert_called_once_with()
        self.popen.terminate.assert_called_once_with()
        self.root.terminate.assert_not_called()
        self.root.kill.assert_not_called()
        self.assertTrue(all(member.pid!=100 for call in self.wait.call_args_list for member in call.args[0]))

    def test_exited_root_is_never_reopened_or_signalled_by_pid(self):
        reused_root=fake_member(100,88.)
        self.current[100]=reused_root
        self.popen.poll.return_value=0
        self.tree.terminate()
        self.assertTrue(all(call.args[0]!=100 for call in self.factory.call_args_list))
        self.popen.terminate.assert_not_called()
        self.popen.kill.assert_not_called()
        self.assert_no_signal_or_discovery(reused_root)
        self.child.terminate.assert_called_once_with()

    def test_pid_reused_after_terminate_is_excluded_from_wait(self):
        self.child.terminate.side_effect=self.reuse_child
        self.tree.terminate()
        self.assertTrue(all(member.pid!=200 for call in self.wait.call_args_list for member in call.args[0]))
        self.assert_no_signal_or_discovery(self.current[200])

    def test_pid_reused_while_waiting_is_not_killed_or_waited_again(self):
        def waiting(members,timeout):
            if members:
                self.reuse_child()
                return [],members
            return [],[]
        self.wait.side_effect=waiting
        self.tree.terminate()
        self.child.kill.assert_not_called()
        self.assert_no_signal_or_discovery(self.current[200])
        self.assertEqual(self.wait.call_args_list[-1].args[0],[])

    def test_owned_live_child_is_reverified_before_kill(self):
        self.wait.side_effect=lambda members,timeout:([],members)
        self.tree.terminate()
        self.child.terminate.assert_called_once_with()
        self.child.kill.assert_called_once_with()
        self.assertGreaterEqual(sum(call.args==(200,) for call in self.factory.call_args_list),4)

    def test_disappeared_child_is_removed_without_signals(self):
        del self.current[200]
        self.tree.terminate()
        self.assertNotIn((200,20.),self.tree.members)
        self.assert_no_signal_or_discovery(self.child)

    def test_access_denied_is_not_retried_as_kill(self):
        self.child.terminate.side_effect=processes.psutil.AccessDenied(200)
        # Cleanup now fails closed for an owned child still alive after grace;
        # this changes no ML evaluator or signal/identity safety assertion.
        with self.assertRaises(processes.ProcessCleanupError):
            self.tree.terminate(grace=0)
        self.child.kill.assert_not_called()
        self.assertEqual(self.tree.cleanup_errors,[{'pid':200,'create_time':20.,'action':'terminate','error':'AccessDenied'}])
        self.assertTrue(all(member.pid!=200 for call in self.wait.call_args_list for member in call.args[0]))


if __name__=='__main__':
    unittest.main(verbosity=2)
