"""Prepared synthetic bootstrap contracts; no candidate/native imports or fits."""
from pathlib import Path
import ast
import copy
import hashlib
import importlib.util
import math
import tempfile
import unittest
from unittest.mock import Mock, patch

HERE=Path(__file__).resolve().parent
ACTUAL_WORK=HERE.parent
spec=importlib.util.spec_from_file_location('_technical_bootstrap_contract_target',HERE/'technical_entry.py')
B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B)


class TechnicalBootstrapContracts(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.work=Path(self.temp.name).resolve();self.output=self.work/'current-rq'
        self.output.mkdir();self.manifest_sha='a'*64
        self.state=dict(schema='standard-repair-qualification-campaign-v1',status='setup',
            manifest_sha256=self.manifest_sha,common_seconds=6000,
            owned_root=dict(pid=100,create_time=900.),launch_parent_observation=dict(verified=True),
            start_unix=1000.,start_monotonic=10.,absolute_deadline_unix=7000.,common_deadline_monotonic=6010.)
        coor=self.work/'verified-supervision-next-dev-r2/coordinator.py'
        digest='bd864b13460d31176d57e1dbddbe179ad8e6911163b117e3f9698228c5540f76'
        self.cfg=dict(schema='standard-repair-qualification-private-v1',readiness='READY_REVIEWED_FROZEN',
            missing_bindings=[],common_seconds=6000,output=str(self.output),
            helpers=dict(coordinator=dict(path=str(coor),sha256=digest)),immutable_files={str(coor):digest})
        context=patch.object(B,'WORK',self.work);context.start();self.addCleanup(context.stop)

    def test_current_campaign_is_read_only_from_exact_absolute_bound_output(self):
        wrong_old=self.work/'rq4';wrong_old.mkdir()
        reader=Mock(return_value=self.state)
        output,state=B.current_campaign(self.cfg,self.manifest_sha,'source',reader)
        self.assertEqual(output,self.output);self.assertIs(state,self.state)
        reader.assert_called_once_with(self.output/'campaign.json')
        self.assertNotEqual(reader.call_args.args[0],wrong_old/'campaign.json')
        self.assertFalse(hasattr(B,'OUT'))

    def test_relative_output_and_wrong_campaign_manifest_never_gain_authority(self):
        reader=Mock(return_value=self.state)
        with self.assertRaisesRegex(RuntimeError,'absolute_actual_parent'):
            B.current_campaign(dict(self.cfg,output='rq4'),self.manifest_sha,'source',reader)
        reader.assert_not_called()
        for changes in [dict(manifest_sha256='b'*64),dict(status='failed'),dict(common_seconds=6001),
                        dict(schema='old-campaign'),dict(launch_parent_observation=dict(verified=False))]:
            with self.subTest(changes=changes),self.assertRaisesRegex(RuntimeError,'campaign_manifest_or_owner'):
                B.current_campaign(self.cfg,self.manifest_sha,'unpacked',lambda p:dict(self.state,**changes))

    def test_parent_supervision_source_authority_is_required_without_new_resource_claim(self):
        bad=copy.deepcopy(self.cfg);bad['helpers']['coordinator']['sha256']='c'*64
        with self.assertRaisesRegex(RuntimeError,'independent_parent_supervision'):
            B.current_campaign(bad,self.manifest_sha,'source',lambda p:self.state)
        bad=copy.deepcopy(self.cfg);bad['immutable_files']={}
        with self.assertRaisesRegex(RuntimeError,'independent_parent_supervision'):
            B.current_campaign(bad,self.manifest_sha,'source',lambda p:self.state)
        parent_source=ACTUAL_WORK/'verified-supervision-next-dev-r2/coordinator.py'
        self.assertEqual(hashlib.sha256(parent_source.read_bytes()).hexdigest(),
            'bd864b13460d31176d57e1dbddbe179ad8e6911163b117e3f9698228c5540f76')

    def test_long_native_import_interval_is_covered_by_independent_parent_samples(self):
        original=copy.deepcopy(self.state);now=11.;previous=B.clock_only_checkpoint(self.state,10.,now,1001.)
        samples=[];inspect=Mock(return_value=dict(verified=True,rss_bytes=1024))
        # Synthetic native import blocks child callbacks for20s. Only the
        # independent parent performs these successful resource observations.
        for _ in range(80):
            now+=.25;actual=inspect();self.assertTrue(actual['verified']);samples.append(now)
        previous=B.clock_only_checkpoint(self.state,previous,now,1000.+now-10.)
        self.assertEqual(previous,31.);self.assertEqual(inspect.call_count,80)
        self.assertTrue(all(b-a<=.25 for a,b in zip(samples,samples[1:])))
        self.assertEqual(self.state,original)  # No fabricated parent lastsample.

    def test_long_import_does_not_extend_original_deadline(self):
        original=copy.deepcopy(self.state)
        with self.assertRaisesRegex(RuntimeError,'original_common_deadline'):
            B.clock_only_checkpoint(self.state,5990.,6010.,7000.)
        self.assertEqual(self.state,original)

    def test_rollback_nonfinite_assignment_and_wall_drift_still_STOP(self):
        for state,previous,mono,wall in [(self.state,12.,11.,1001.),(self.state,10.,math.nan,1001.),
                (dict(self.state,absolute_deadline_unix=7001.),10.,11.,1001.),(self.state,10.,11.,1007.)]:
            with self.subTest(mono=mono,wall=wall),self.assertRaises(RuntimeError):
                B.clock_only_checkpoint(state,previous,mono,wall)

    def test_existing24_bytes_network_tripwire_and_dependency_only_preload_remain(self):
        source=(HERE/'technical_entry.py').read_text(encoding='utf-8-sig');tree=ast.parse(source)
        main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        native=[n for n in ast.walk(main) if isinstance(n,ast.Import)
            and any(a.name in {'numpy','numpy.testing','scipy','scipy.sparse','sklearn','sklearn.metrics','sklearn.model_selection'} for a in n.names)]
        tripwire=[n for n in ast.walk(main) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Attribute)
            and isinstance(t.value,ast.Name) and t.value.id=='socket' and t.attr=='create_connection' for t in n.targets)
            and isinstance(n.value,ast.Name) and n.value.id=='no_network']
        self.assertEqual(len(native),7);self.assertEqual(len(tripwire),1)
        self.assertLess(tripwire[0].lineno,min(n.lineno for n in native))
        self.assertIn("for name,h in cfg['executor']['members_sha256'].items():check();need(digest(candidate/name)==h",source)
        original_test=ACTUAL_WORK/'last-submission-repair-next-dev-r4/tests/test_supervised_class_release.py'
        self.assertEqual(hashlib.sha256(original_test.read_bytes()).hexdigest(),B.TEST_SHA)
        methods=[n for c in ast.parse(original_test.read_text(encoding='utf-8-sig')).body if isinstance(c,ast.ClassDef)
            for n in c.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')]
        self.assertEqual(len(methods),24)


if __name__=='__main__':unittest.main(verbosity=2)
