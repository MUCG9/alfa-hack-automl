"""Twelve prepared pure/mock contracts; no real arrays, targets or models."""
from copy import deepcopy
from pathlib import Path
import importlib.util
import math
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('cache_audit_under_test', ROOT/'audit_cache.py')
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)


class Values:
    def __init__(self, values): self.values = tuple(values)
    def __mul__(self, weight): return Values([x*weight for x in self.values])
    def __add__(self, other):
        if len(self.values) != len(other.values): raise ValueError('width')
        return Values([a+b for a,b in zip(self.values, other.values)])


def clock():
    return dict(start_unix=1000., start_monotonic=100., absolute_deadline_unix=1600.,
        common_deadline_monotonic=700., audit_start_unix=1001., audit_start_monotonic=101.,
        audit_deadline_unix=1121., audit_deadline_monotonic=221., prior_checkpoint_monotonic=101.)


def recipe():
    return dict(engine='ensemble', params={}, weights=[1/3]*3, components=[
        dict(engine='lightgbm', params=dict(feature_views='categorical_te_pair',seed=42)),
        dict(engine='lightgbm', params=dict(feature_views='categorical_te_pair',seed=48)),
        dict(engine='xgboost', params=dict(seed=42))])


def diagnostic():
    return dict(phase='primary',metric='macro_f1',fitting_rows=6,validation_rows=2,
        positions_sha256='a'*64,training_rows_canonical_sha256='b'*64,split_file_sha256='c'*64,
        prediction_sha256='d'*64,mixture_children=3,independent_fitting_groups={'a':101,'b':4},
        rarest_fitting_class='b',feature_groups_disjoint=True,value=.6,
        per_class_f1={'a':.7,'b':.5},ex_rarest_macro_f1=.7)


class CacheAuditContracts(unittest.TestCase):
    def test_retained_components_exact_deep_copy_and_control_unchanged(self):
        original = recipe(); before = deepcopy(original)
        actual = A.candidate_recipe(original)
        self.assertEqual(original,before)
        self.assertEqual(actual['components'],before['components'][:2])
        self.assertEqual(actual['weights'],[.5,.5])
        actual['components'][0]['params']['seed']=999
        self.assertEqual(original,before)

    def test_wrong_component_weight_or_family_is_stop(self):
        for change in ('weight','family','arity'):
            value=recipe()
            if change=='weight':value['weights']=[.5,.25,.25]
            if change=='family':value['components'][1]['engine']='xgboost'
            if change=='arity':value['components'].pop()
            with self.subTest(change=change),self.assertRaises(A.Stop):A.candidate_recipe(value)

    def test_both_control_cuts_complete_before_any_candidate(self):
        events=[]
        def control(p):events.append('control:'+p);return {'cut':p}
        def candidate(p,c):events.append('candidate:'+p);self.assertEqual(c,{'cut':p});return p
        control_rows,candidate_rows=A.both_controls_first(control,candidate)
        self.assertEqual(events,['control:primary','control:confirmation','candidate:primary','candidate:confirmation'])
        self.assertEqual(set(control_rows),set(A.PHASES));self.assertEqual(candidate_rows['confirmation'],'confirmation')

    def test_second_control_failure_prevents_all_comparative_scores(self):
        candidate=Mock()
        def control(p):
            if p=='confirmation':raise A.Stop('missing_child_cache')
            return diagnostic()
        with self.assertRaisesRegex(A.Stop,'missing_child_cache'):A.both_controls_first(control,candidate)
        candidate.assert_not_called()

    def test_fixed_weight_mixture_normalizes_without_input_mutation(self):
        parts=[Values([.2,.8]),Values([.6,.4]),Values([.4,.6])]
        self.assertEqual(A.blend(parts[:2],[.5,.5]).values,(.4,.6000000000000001))
        for a,b in zip(A.blend(parts,[1,1,1]).values,(.4,.6)):self.assertAlmostEqual(a,b)
        self.assertEqual(parts[0].values,(.2,.8))
        for weights in ([0,1],[True,1],[float('nan'),1]):
            with self.assertRaises(A.Stop):A.blend(parts[:2],weights)

    def test_original_clock_assignment_and_successful_checkpoint(self):
        value=clock();c=A.RetainedClock(value)
        with patch.object(A.time,'monotonic',return_value=102.),patch.object(A.time,'time',return_value=1002.):c.check()
        self.assertEqual(c.last,102.);self.assertEqual(c.clock,value)
        broken=clock();broken['audit_deadline_monotonic']+=1
        with self.assertRaises(A.Stop):A.RetainedClock(broken)

    def test_gap_failure_sticks_and_never_advances_to_recover(self):
        c=A.RetainedClock(clock())
        with patch.object(A.time,'monotonic',return_value=111.01),patch.object(A.time,'time',return_value=1011.01):
            with self.assertRaisesRegex(A.Stop,'gap_over10'):c.check()
        self.assertEqual(c.last,101.)
        with patch.object(A.time,'monotonic',return_value=102.),patch.object(A.time,'time',return_value=1002.):
            with self.assertRaisesRegex(A.Stop,'gap_over10'):c.check()

    def test_deadline_rollback_nonfinite_and_drift_stop_on_same_origin(self):
        for now,wall in [(100.,1000.),(102.,float('nan')),(102.,1020.),(221.,1121.)]:
            with self.subTest(now=now,wall=wall):
                c=A.RetainedClock(clock())
                if now==221.:c.last=220.
                with patch.object(A.time,'monotonic',return_value=now),patch.object(A.time,'time',return_value=wall):
                    with self.assertRaises(A.Stop):c.check()

    def test_saved_control_requires_same_positions_classes_support_and_metrics(self):
        close=lambda a,b:math.isclose(a,b,abs_tol=1e-10,rel_tol=1e-10)
        A.confirm_saved_control(diagnostic(),diagnostic(),close)
        for field,value in [('positions_sha256','e'*64),('independent_fitting_groups',{'a':100,'b':4}),
                            ('rarest_fitting_class','a'),('value',.61),('per_class_f1',{'a':.7,'b':.4})]:
            wrong=diagnostic();wrong[field]=value
            with self.subTest(field=field),self.assertRaises(A.Stop):A.confirm_saved_control(wrong,diagnostic(),close)

    def test_quality_requires_both_cut_and_mean_improvement_and_existing_class_gates(self):
        controls={p:dict(value=.6) for p in A.PHASES};candidates={p:dict(value=.61) for p in A.PHASES}
        def comparison(a,b,kind):
            self.assertEqual(kind,'classification');return dict(each_cut_primary_gate_passed=True,class_each_cut_gate_passed=True)
        self.assertTrue(A.decide(controls,candidates,comparison)['quality_gate_passed'])
        candidates['confirmation']['value']=.59
        self.assertFalse(A.decide(controls,candidates,comparison)['quality_gate_passed'])
        candidates['confirmation']['value']=.61
        for first,second in ((False,True),(True,False)):
            value=A.decide(controls,candidates,lambda *args:dict(each_cut_primary_gate_passed=first,class_each_cut_gate_passed=second))
            self.assertFalse(value['quality_gate_passed'])
        for value in (None,float('nan'),True):
            candidates['confirmation']['value']=value
            with self.assertRaises(A.Stop):A.decide(controls,candidates,comparison)

    def test_missing_or_changed_cache_has_no_fit_or_reconstruction_route(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(A,'WORK',Path(d)):
                with self.assertRaises(FileNotFoundError):A.rehash({'missing.npz':'a'*64},lambda:None)
                p=Path(d)/'cache.npz';p.write_bytes(b'opaque synthetic bytes, not an NPZ')
                with self.assertRaisesRegex(A.Stop,'changed'):A.rehash({'cache.npz':'a'*64},lambda:None)
                for rel in ('../outside.npz',str(Path(d).resolve()/'cache.npz')):
                    with self.assertRaises(A.Stop):A.work_path(rel)

    def test_failure_result_clears_comparative_metrics_and_preserves_first_error(self):
        source=(ROOT/'audit_cache.py').read_text('utf-8')
        self.assertIn("result.update(status='STOP', artifact_procedure_passed=False, quality_gate_passed=None, cuts=None, comparison=None)",source)
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)/'independent-cache-audit.json';manifest=Path(d)/'manifest.json';manifest.write_text('{}')
            with (patch.object(A,'OUTPUT',output),patch.object(A.argparse.ArgumentParser,'parse_args',return_value=
                  type('Args',(),dict(manifest=str(manifest),manifest_sha256='a'*64,self_sha256='b'*64,output=str(output)))()),
                  patch.object(A,'RetainedClock',side_effect=A.Stop('missing_original_clock'))):
                self.assertEqual(A.main(),2)
            result=A.load(output)
            self.assertIsNone(result['comparison']);self.assertIsNone(result['cuts']);self.assertIsNone(result['quality_gate_passed'])
            self.assertEqual(result['first_failure']['code'],'missing_original_clock')
            self.assertFalse(result['artifact_procedure_passed']);self.assertEqual(result['new_model_fits'],0)


if __name__=='__main__':unittest.main()
