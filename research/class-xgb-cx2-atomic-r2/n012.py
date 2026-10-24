"""Prepared synthetic ordering/clock/argv contracts; no actual closer/process."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

SOURCE=Path(__file__).with_name('run_root.py')
spec=importlib.util.spec_from_file_location('atomic_root_contract_source',SOURCE)
atomic=importlib.util.module_from_spec(spec)
spec.loader.exec_module(atomic)


class AtomicRootContracts(unittest.TestCase):
    def test_child_birth_cannot_reset_enclosing60_common600_or_existing_final(self):
        state=dict(start_unix=1000.,start_monotonic=20.,absolute_deadline_unix=1600.,
            common_deadline_monotonic=620.,final_deadline_monotonic=300.)
        before=state.copy()
        initial=atomic.bounds(state,1100.,120.)
        late_child=atomic.bounds(state,1100.,120.,1115.)
        self.assertEqual(initial,(1160.,180.))
        self.assertEqual(late_child,initial)
        self.assertLessEqual(late_child[0],1115.+60)
        self.assertLessEqual(late_child[1],state['start_monotonic']+1115.-state['start_unix']+60)
        self.assertEqual(state,before)
        final=dict(state,final_deadline_monotonic=150.)
        self.assertEqual(atomic.bounds(final,1100.,120.,1115.),(1130.,150.))
        for changed in [dict(state,absolute_deadline_unix=1601.),
                        dict(state,common_deadline_monotonic=float('nan'))]:
            with self.assertRaises(RuntimeError):atomic.bounds(changed,1100.,120.)
        with self.assertRaises(RuntimeError):atomic.bounds(state,1100.,120.,1099.)

    def test_actual_exit_is_saved_before_fresh_and_late_or_failed_exit_never_qualifies(self):
        order=[]
        save=lambda:order.append('actual_exit_saved')
        fresh=lambda:(order.append('fresh'),{'qualified':True})[1]
        check=lambda:order.append('check')
        self.assertEqual(atomic.postexit(0,0,save,fresh,check),{'qualified':True})
        self.assertEqual(order,['actual_exit_saved','check','fresh','check'])
        for shell,native in [(1,1),(0,1),(1,0),(None,0)]:
            order.clear()
            with self.assertRaises(RuntimeError):atomic.postexit(shell,native,save,fresh,check)
            self.assertEqual(order,['actual_exit_saved','check'])
        order.clear()
        def expired():
            order.append('expired')
            raise TimeoutError('same-original-window')
        with self.assertRaises(TimeoutError):atomic.postexit(0,0,save,fresh,expired)
        self.assertEqual(order,['actual_exit_saved','expired'])

    def test_fixed_child_shell_argv_has_no_payload_and_requires_absolute_typed_evidence(self):
        root=SOURCE.parent.resolve()
        cfg={k:{'path':str(root/(k+'.fixed')),'sha256':'a'*64}
             for k in ['powershell','python','closer','manifest','driver','campaign']}
        actual=dict(session=123,exit_code=0,tool='actual-tool')
        argv=atomic.child_command(cfg,actual,root/'native-exit.json')
        self.assertIn('-File',argv)
        self.assertEqual(argv[argv.index('-File')+1],str(atomic.PACKET/'close_child.ps1'))
        self.assertNotIn('-Command',argv)
        self.assertNotIn('-ExecutionPolicy',argv)
        self.assertIn('-ActualSession',argv)
        self.assertEqual(argv[argv.index('-ActualExit')+1],'0')
        self.assertNotIn('-LaunchParentPid',argv)  # Child script observes its own actual shell.
        actual_shell={'pid':123,'create_time':100.0000004}
        declared={'pid':123,'create_time':100.}
        early={'launch_parent_observation':{'verified':True,'observed_shell':actual_shell,'declared':declared}}
        atomic.native_shell_verified({'shell':declared},early,actual_shell)
        for wrong in [{'pid':124,'create_time':100.}, {'pid':123,'create_time':100.0000008}]:
            with self.assertRaises(RuntimeError):atomic.native_shell_verified({'shell':wrong},early,actual_shell)
        with self.assertRaises(RuntimeError):
            atomic.native_shell_verified({'shell':declared},early,dict(actual_shell,create_time=100.))

        with self.assertRaises(RuntimeError):
            atomic.child_command(dict(cfg,closer={'path':'relative.py','sha256':'a'*64}),actual,root/'exit.json')
        with self.assertRaises(RuntimeError):
            atomic.child_command(cfg,dict(actual,tool='x; arbitrary-command'),root/'exit.json')


if __name__=='__main__':unittest.main(verbosity=2)
