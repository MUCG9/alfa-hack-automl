"""Prepared synthetic checkpoint contracts; no learner/API/resource process query."""
from pathlib import Path
import sys,unittest
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from automl.search import runner


class Clock:
    def __init__(self,value=0.):self.value=value;self.calls=0
    def __call__(self):self.calls+=1;return self.value


class Inspector:
    def __init__(self,action=None):self.calls=0;self.action=action
    def inspect(self,pid,root):
        self.calls+=1
        if self.action:return self.action()
        return None,1,2


def case(action=None,start=0.,deadline=100.):
    clock=Clock(start);resources=Inspector(action)
    budget=SimpleNamespace(clock=clock,deadline=deadline)
    check=runner._TaskContractCheckpoint(budget,resources,Path('.'))
    return clock,resources,budget,check


class TaskContractCadenceTests(unittest.TestCase):
    def test_burst_checks_original_clock_but_only_first_resource_sample(self):
        clock,res,budget,check=case();check();seen=clock.calls
        for _ in range(100):check()
        self.assertEqual(res.calls,1);self.assertGreaterEqual(clock.calls-seen,100)
        self.assertEqual(check._last_sample,0.);self.assertEqual(budget.deadline,100.)

    def test_exact_cadence_boundary_samples_and_skips_do_not_move_last_sample(self):
        clock,res,_,check=case();check();clock.value=.249;check()
        self.assertEqual(res.calls,1);self.assertEqual(check._last_sample,0.)
        clock.value=.25;check();self.assertEqual(res.calls,2);self.assertEqual(check._last_sample,.25)

    def test_phase_force_really_inspects_even_inside_cadence(self):
        clock,res,_,check=case();check();clock.value=.01;check(force=True)
        self.assertEqual(res.calls,2);self.assertEqual(check._last_sample,.01)

    def test_deadline_on_otherwise_skipped_callback_is_sticky(self):
        clock,res,budget,check=case(deadline=.1);check();clock.value=.1
        with self.assertRaises(TimeoutError) as first:check()
        clock.value=.01
        with self.assertRaises(TimeoutError) as again:check(force=True)
        self.assertIs(first.exception,again.exception);self.assertEqual(res.calls,1);self.assertEqual(budget.deadline,.1)

    def test_inspection_crossing_original_deadline_cannot_commit_sample(self):
        clock,res,_,check=case(deadline=1.)
        def slow():clock.value=1.;return None,1,2
        res.action=slow
        with self.assertRaises(TimeoutError):check()
        self.assertIsNone(check._last_sample);self.assertEqual(res.calls,1)

    def test_slow_inspection_duration_over10_is_sticky(self):
        clock,res,_,check=case()
        def slow():clock.value=10.01;return None,1,2
        res.action=slow
        with self.assertRaises(runner.ProcessObservationError) as first:check()
        self.assertIsNone(check._last_sample);clock.value=10.02
        with self.assertRaises(runner.ProcessObservationError) as again:check()
        self.assertIs(first.exception,again.exception);self.assertEqual(res.calls,1)

    def test_gap_includes_due_inspection_duration_and_cannot_be_laundered(self):
        clock,res,_,check=case();check();clock.value=9.9
        def slow():clock.value=10.1;return None,1,2
        res.action=slow
        with self.assertRaises(runner.ProcessObservationError):check()
        self.assertEqual(check._last_sample,0.);self.assertEqual(res.calls,2)

    def test_presample_gap_over10_rejects_before_any_new_inspection(self):
        clock,res,_,check=case();check();clock.value=10.001
        with self.assertRaises(runner.ProcessObservationError):check(force=True)
        self.assertEqual(res.calls,1);self.assertEqual(check._last_sample,0.)

    def test_raw_denials_are_fatal_sticky_and_do_not_advance_last_sample(self):
        for error in (runner.psutil.AccessDenied(1),runner.psutil.NoSuchProcess(1),PermissionError('inert')):
            with self.subTest(error=type(error).__name__):
                clock,res,_,check=case();check();clock.value=.25
                def denied():raise error
                res.action=denied
                with self.assertRaises(runner.ProcessObservationError) as first:check()
                clock.value=.26
                with self.assertRaises(runner.ProcessObservationError) as again:check()
                self.assertIs(first.exception,again.exception);self.assertEqual(res.calls,2);self.assertEqual(check._last_sample,0.)

    def test_resource_limit_failure_is_sticky_and_never_becomes_cached_pass(self):
        clock,res,_,check=case();check();clock.value=.25;res.action=lambda:('memory_limit',2,4)
        with self.assertRaisesRegex(RuntimeError,'resource_limit') as first:check()
        res.action=None;clock.value=.26
        with self.assertRaises(RuntimeError) as again:check(force=True)
        self.assertIs(first.exception,again.exception);self.assertEqual(res.calls,2);self.assertEqual(check._last_sample,0.)

    def test_rollback_or_nonfinite_clock_fails_before_resource_and_stays_sticky(self):
        for value in (-.1,float('nan'),float('inf'),None,True):
            with self.subTest(value=repr(value)):
                clock,res,_,check=case();check();clock.value=value
                with self.assertRaises(runner.ProcessObservationError) as first:check()
                clock.value=.5
                with self.assertRaises(runner.ProcessObservationError) as again:check(force=True)
                self.assertIs(first.exception,again.exception);self.assertEqual(res.calls,1)

    def test_flow_state_is_local_original_helper_still_inspects_every_direct_call(self):
        ca,ra,ba,a=case();cb,rb,bb,b=case();a();b();ca.value=.25;a();b()
        self.assertEqual((ra.calls,rb.calls),(2,1));self.assertIs(a.budget,ba);self.assertIs(b.budget,bb)
        self.assertIsNot(ba,bb);self.assertEqual((ba.deadline,bb.deadline),(100.,100.))
        for _ in range(3):runner._task_contract_checkpoint(bb,rb,Path('.'))
        self.assertEqual(rb.calls,4)


if __name__=='__main__':unittest.main()
