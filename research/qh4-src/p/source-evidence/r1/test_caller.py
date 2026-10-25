"""Prepared pure/mock caller contracts; zero author executions."""
from pathlib import Path
import importlib.util,types,unittest

def load():
    path=Path(__file__).with_name('run_preflight.py');spec=importlib.util.spec_from_file_location('_metadata_caller_contracts',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class MetadataCallerContracts(unittest.TestCase):
    def test_evaluate_clock_checkpoints_are_continuous_and_local_and_restore_primary_exception(self):
        m=load();original=object();utility=types.SimpleNamespace(time=original);calls=[];ticks=iter([1.,2.,3.])
        def pulse():calls.append('actual_full_guard')
        failure=RuntimeError('primary')
        with self.assertRaisesRegex(RuntimeError,'primary'):
            with m.continuous_clock_checkpoints(utility,pulse,lambda:next(ticks)):
                self.assertEqual(utility.time.monotonic(),1.)
                self.assertEqual(utility.time.monotonic(),2.)
                self.assertEqual(utility.time.monotonic(),3.)
                self.assertEqual(calls,['actual_full_guard']*3)
                self.assertIsNot(utility.time,original)
                raise failure
        self.assertIs(utility.time,original)
        with self.assertRaisesRegex(RuntimeError,'denial'):
            with m.continuous_clock_checkpoints(utility,lambda:(_ for _ in ()).throw(RuntimeError('denial')),lambda:99.):
                utility.time.monotonic()
        self.assertIs(utility.time,original)

    def test_guard_observer_seen_is_retained_even_when_a_round_fails_without_role_adoption(self):
        m=load();seen={(1,1.)}
        class Original:
            def __init__(self):self.seen={(2,2.)}
            def observe(self):
                self.seen.add((3,3.));raise RuntimeError('resource_denial')
        Recorder=m.recording_observer_class(Original,seen);observer=Recorder()
        with self.assertRaisesRegex(RuntimeError,'resource_denial'):observer.observe()
        self.assertEqual(seen,{(1,1.),(2,2.),(3,3.)})
        self.assertEqual(m.identity_rows(seen),[{'pid':1,'create_time':1.},{'pid':2,'create_time':2.},{'pid':3,'create_time':3.}])
        self.assertFalse(any('role' in row or 'owned' in row for row in m.identity_rows(seen)))

if __name__=='__main__':unittest.main(verbosity=2)
