"""Denied owned cleanup must stop sequential work; fake processes, no model fits."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from automl.infrastructure import processes


def fake_member(pid,created):
    member=Mock(pid=pid)
    member.create_time.return_value=created
    member.children.return_value=[]
    member.is_running.return_value=True
    member.status.return_value='running'
    return member


class CleanupFailureTests(unittest.TestCase):
    def setUp(self):
        self.root=fake_member(100,10.)
        self.child=fake_member(200,20.)
        self.root.children.return_value=[self.child]
        self.current={100:self.root,200:self.child}
        self.popen=Mock(pid=100,args=['not-for-receipt','private-fixture-argument'])
        self.popen.poll.return_value=None
        self.popen.wait.return_value=0
        self.popen.terminate.side_effect=lambda:setattr(self.popen.poll,'return_value',0)
        self.factory=patch.object(processes.psutil,'Process',side_effect=self.lookup).start()
        self.addCleanup(patch.stopall)
        self.wait=patch.object(processes.psutil,'wait_procs',side_effect=lambda members,timeout:(members,[])).start()
        self.tree=processes.ProcessTree(self.popen)
        self.root.children.return_value=[]
        self.factory.reset_mock()

    def lookup(self,pid):
        value=self.current.get(pid)
        if isinstance(value,Exception):
            raise value
        if value is None:
            raise processes.psutil.NoSuchProcess(pid)
        return value

    def deny_terminate(self):
        self.child.terminate.side_effect=processes.psutil.AccessDenied(200)

    def test_denied_live_owned_child_raises_safe_receipt_without_kill_bypass(self):
        self.deny_terminate()
        with self.assertRaises(processes.ProcessCleanupError) as caught:
            self.tree.terminate(grace=0)
        receipt=caught.exception.receipt
        self.assertEqual(receipt['status'],'cleanup_unconfirmed')
        self.assertEqual(receipt['unresolved'],[{'pid':200,'create_time':20.,
            'action':'terminate','error':'AccessDenied','reason':'still_alive'}])
        self.assertNotIn('private-fixture-argument',str(caught.exception))
        self.assertNotIn('not-for-receipt',str(caught.exception))
        self.child.kill.assert_not_called()
        self.assertTrue(all(member.pid!=200 for call in self.wait.call_args_list for member in call.args[0]))

    def test_denied_child_naturally_gone_by_final_recheck_is_not_a_blocker(self):
        def denied_then_gone():
            del self.current[200]
            raise processes.psutil.AccessDenied(200)
        self.child.terminate.side_effect=denied_then_gone
        self.tree.terminate(grace=0)
        self.assertFalse(self.tree._pending_cleanup)
        self.assertEqual(self.tree.cleanup_errors[0]['action'],'terminate')
        self.child.kill.assert_not_called()

    def test_denied_child_reused_pid_is_ignored_and_never_signalled(self):
        reused=fake_member(200,99.)
        def denied_then_reused():
            self.current[200]=reused
            raise processes.psutil.AccessDenied(200)
        self.child.terminate.side_effect=denied_then_reused
        self.tree.terminate(grace=0)
        self.assertFalse(self.tree._pending_cleanup)
        reused.terminate.assert_not_called()
        reused.kill.assert_not_called()
        reused.children.assert_not_called()

    def test_identity_access_denied_stays_unknown_and_never_reaches_signals(self):
        self.current[200]=processes.psutil.AccessDenied(200)
        with self.assertRaises(processes.ProcessCleanupError) as caught:
            self.tree.terminate(grace=0)
        self.assertEqual(caught.exception.receipt['unresolved'][0]['reason'],'identity_unverifiable')
        self.assertEqual(caught.exception.receipt['unresolved'][0]['action'],'verify_identity')
        self.child.terminate.assert_not_called()
        self.child.kill.assert_not_called()

    def test_identity_becomes_verifiable_but_alive_after_denial_still_blocks(self):
        reads=[0]
        def initially_denied(pid):
            if pid==200:
                reads[0]+=1
                if reads[0]==1:
                    raise processes.psutil.AccessDenied(pid)
            return self.lookup(pid)
        self.factory.side_effect=initially_denied
        with self.assertRaises(processes.ProcessCleanupError) as caught:
            self.tree.terminate(grace=0)
        self.assertEqual(caught.exception.receipt['unresolved'][0]['reason'],'still_alive')
        self.child.terminate.assert_not_called()
        self.child.kill.assert_not_called()

    def test_denied_kill_of_verified_owned_child_is_also_a_blocker(self):
        self.wait.side_effect=lambda members,timeout:([],members)
        self.child.kill.side_effect=processes.psutil.AccessDenied(200)
        with self.assertRaises(processes.ProcessCleanupError) as caught:
            self.tree.terminate(grace=0)
        self.child.terminate.assert_called_once_with()
        self.child.kill.assert_called_once_with()
        self.assertEqual(caught.exception.receipt['unresolved'][0]['action'],'kill')

    def test_fresh_recheck_after_grace_allows_natural_exit(self):
        self.deny_terminate()
        def leave_during_grace(seconds):
            self.assertGreater(seconds,0)
            del self.current[200]
        with patch.object(processes.time,'sleep',side_effect=leave_during_grace) as sleep:
            self.tree.terminate(grace=.05)
        sleep.assert_called_once()
        self.assertFalse(self.tree._pending_cleanup)

    def test_same_identity_no_longer_running_or_zombie_is_resolved(self):
        for state in ('not_running','zombie'):
            with self.subTest(state=state):
                self.tree.members[(200,20.)]=self.child
                self.child.is_running.return_value=state!='not_running'
                self.child.status.return_value=state
                self.deny_terminate()
                self.tree.terminate(grace=0)
                self.assertFalse(self.tree._pending_cleanup)
        self.child.kill.assert_not_called()

    def test_unknown_discovered_identity_cannot_be_killed_and_blocks_if_live(self):
        unknown=fake_member(300,30.)
        unknown.create_time.side_effect=processes.psutil.AccessDenied(300)
        self.current[300]=unknown
        self.root.children.return_value=[unknown]
        with self.assertRaises(processes.ProcessCleanupError) as caught:
            self.tree.terminate(grace=0)
        entry=caught.exception.receipt['unresolved'][0]
        self.assertEqual(entry['pid'],300)
        self.assertIsNone(entry['create_time'])
        self.assertEqual(entry['action'],'discover_identity')
        unknown.terminate.assert_not_called()
        unknown.kill.assert_not_called()

    def test_wait_owned_cannot_return_success_after_denied_cleanup(self):
        self.deny_terminate()
        self.popen.poll.return_value=0
        with patch.object(processes,'ProcessTree',return_value=self.tree), \
             patch.object(processes.time,'sleep'):
            with self.assertRaises(processes.ProcessCleanupError):
                processes.wait_owned(self.popen,timeout=1)

    def test_repeated_cleanup_keeps_denial_but_can_resolve_after_natural_exit(self):
        self.deny_terminate()
        with self.assertRaises(processes.ProcessCleanupError):
            self.tree.terminate(grace=0)
        del self.current[200]
        self.tree.terminate(grace=0)
        self.assertFalse(self.tree._pending_cleanup)
        self.child.terminate.assert_called_once_with()
        self.child.kill.assert_not_called()


if __name__=='__main__':
    unittest.main(verbosity=2)
