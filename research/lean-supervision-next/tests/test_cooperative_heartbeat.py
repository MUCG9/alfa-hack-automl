"""Two future no-fit contracts, UNEXECUTED during source-only preparation.

Uses a byte-identical portable PowerRequestGuard fixture but never enters its
Windows API context. Hash stream/time are fake; no real task/source inputs are
opened. There is no model, network, child process, sleep or real experiment clock.
"""
from pathlib import Path
import hashlib
import importlib.util
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def module(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


class CooperativeHeartbeatContracts(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]
        self.c=module('_future_supervision_fixture',root/'run_lean_mvp_r1.py')
        self.power=module('_future_power_fixture',root/'tests/fixtures/awake_guard.py')
        self.seconds=0.;self.base_wall=1000000.
        clock=SimpleNamespace(time=lambda:self.base_wall+self.seconds,
                              monotonic=lambda:self.seconds)
        self.clocks=[patch.object(self.c,'time',clock),patch.object(self.power,'time',clock)]
        for item in self.clocks:item.start();self.addCleanup(item.stop)
        self.awake=self.power.PowerRequestGuard('synthetic-no-API',10.)
        # Model an already active context ONLY for the pure heartbeat method.
        self.awake.handle=1;self.awake.active=[(1,'SystemRequired'),(3,'ExecutionRequired')]
        self.addCleanup(self.clear_fake_context)

    def clear_fake_context(self):
        self.awake.handle=None;self.awake.active=[]

    def test_long_chunked_work_keeps_gap_valid_and_charges_unchanged_deadline(self):
        owner=self
        class Stream:
            count=0
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,size):
                if self.count==4:return b''
                self.count+=1;owner.seconds+=6.
                return b'x'*64
        deadline=25.;unix=self.base_wall+deadline
        check=lambda:self.c.cooperative_checkpoint(self.awake,deadline,unix)
        with patch.object(self.c.Path,'open',return_value=Stream()):
            actual=self.c.sha('synthetic-input-never-opened.bin',checkpoint=check)
        self.assertEqual(actual,hashlib.sha256(b'x'*256).hexdigest())
        self.assertEqual(self.seconds,24.)
        self.assertEqual(self.awake.record['last_heartbeat']['largest_observed_gap_seconds'],6.)
        self.assertFalse(self.awake.record['last_heartbeat']['scheduling_gap_exceeded'])
        self.assertNotIn('first_exceeded_heartbeat',self.awake.record)
        self.seconds+=2.
        with self.assertRaisesRegex(self.c.TechnicalFailure,'original_common_deadline_exhausted'):
            check()
        self.assertEqual(deadline,25.)
        self.assertFalse(self.awake.record['last_heartbeat']['deadline_extension_granted'])

    def test_real_uninstrumented_over10_gap_fails_without_reset_or_extension(self):
        deadline=100.;unix=self.base_wall+deadline
        check=lambda:self.c.cooperative_checkpoint(self.awake,deadline,unix)
        check();self.seconds+=10.5
        with self.assertRaisesRegex(self.c.TechnicalFailure,'host_supervisor_heartbeat_gap_over10s'):
            check()
        first=self.awake.record['first_exceeded_heartbeat'].copy()
        self.assertEqual(first['wall_gap_seconds'],10.5)
        self.assertEqual(first['monotonic_gap_seconds'],10.5)
        self.assertTrue(first['scheduling_gap_exceeded'])
        self.assertFalse(first['deadline_extension_granted'])
        # A later nonexceeded cleanup sample cannot erase first-failure evidence.
        check()
        self.assertEqual(self.awake.record['first_exceeded_heartbeat'],first)
        self.assertEqual(self.awake.record['last_heartbeat']['largest_observed_gap_seconds'],10.5)
        self.assertEqual(deadline,100.)


if __name__=='__main__':unittest.main(verbosity=2)
