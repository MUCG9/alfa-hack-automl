'Prepared package-import contracts only; not executed. This canonical script runs only its own declared methods. Original standalone loader arguments are replaced by frozen package imports; all other class/helper/method ASTs are unchanged.'
import argparse
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'tests'))
from automl.search import fitting_extractor as E, fitting_bounds as B
import test_uar_fitting_extractor as OLD
BUILDER_SHA = '48793ea77b607583c480965e31c9658ba6465cf2e05545239549bf2349e69314'
BOUNDS_SHA = '1f6b27debfdf2609e03641beae8235ad1a034bd97450b61156bd991cc588a93c'


class Poison:
    def __str__(self): raise AssertionError('Unselected scalar was reduced')
    def __float__(self): raise AssertionError('Unselected scalar was reduced')


class NativeFittingContracts(unittest.TestCase):
    def arguments(self):
        return OLD.FittingExtractorContracts().arguments()

    def test_real_numpy_scalars_in_pandas_views_match_native_fitting_reductions(self):
        a = self.arguments()
        a['source_columns'] = {
            'number': pd.Series([np.float64(1), Poison(), np.int64(3), Poison(), np.float32(5), Poison()], dtype=object),
            'category': pd.Series([np.str_('NA'), Poison(), np.str_('001'), Poison(), pd.NA, Poison()], dtype=object),
            'response': pd.Series([np.int64(2), Poison(), np.float32(4), Poison(), np.float64(6), Poison()], dtype=object)}
        context, receipt = E.extract_fitting_context(**a)
        self.assertEqual(context['fitting_context']['data']['target']['mean'], 4.)
        number = context['fitting_context']['data']['features']['number']
        self.assertEqual(number['numeric'], dict(min=1., max=5., mean=3.))
        self.assertEqual(context['fitting_context']['data']['features']['category']['missing'], 1)
        self.assertEqual(receipt['fitting_rows'], 3)
        self.assertFalse(receipt['whole_feedback_fitting_only'])

    def test_pandas_string_labels_preserve_NA_001_without_unselected_label_leak(self):
        a = self.arguments()
        a['roles'] = replace(a['roles'], kind='classification', metric='macro_f1')
        a['expected_role_sha256'] = OLD.role_digest(a['roles'])
        a['source_columns']['response'] = pd.Series(['001', pd.NA, 'NA', pd.NA, 'NA', 'OUTSIDE'], dtype='string')
        context, _ = E.extract_fitting_context(**a)
        self.assertEqual(context['fitting_context']['data']['target']['class_counts'], {'001': 1, 'NA': 2})

    def test_native_missing_features_allowed_but_targets_and_infinite_values_reject(self):
        for missing in (pd.NA, pd.NaT, np.float64('nan')):
            a = self.arguments()
            a['source_columns']['number'].values[4] = missing
            context, _ = E.extract_fitting_context(**a)
            self.assertEqual(context['fitting_context']['data']['features']['number']['missing'], 1)
            a = self.arguments()
            a['source_columns']['response'].values[4] = missing
            with self.subTest(missing=type(missing).__name__), self.assertRaisesRegex(E.ExtractionRejected, 'missing_fitting_target'):
                E.extract_fitting_context(**a)
        a = self.arguments()
        a['source_columns']['number'].values[4] = np.float64('inf')
        with self.assertRaisesRegex(E.ExtractionRejected, 'nonfinite_fitting_scalar'):
            E.extract_fitting_context(**a)

    def test_numpy_bool_regression_and_non_scalar_objects_are_not_silently_coerced(self):
        for value in (np.bool_(True), np.complex128(1+2j), np.array([1, 2]), pd.Timestamp('2020-01-01')):
            a = self.arguments()
            a['source_columns']['response'].values[4] = value
            with self.subTest(value_type=type(value).__name__), self.assertRaises(E.ExtractionRejected):
                E.extract_fitting_context(**a)


class Resource:
    memory_limit = 2 * 2**30
    def inspect(self, pid, root): return None, 7, 11


class Checkpoint:
    def __init__(self, original, root):
        self.budget, self.root, self.resources = original, root, Resource()
        self._last_sample, self._failure = None, None
        self.denied = False

    def __call__(self, *, force=False):
        if self._failure is not None: raise self._failure
        if self.denied:
            self._failure = PermissionError('synthetic_RSS_denial')
            raise self._failure
        self.resources.inspect(None, self.root)
        self._last_sample = self.budget.clock()


class ValidatedFrameContracts(unittest.TestCase):
    def arguments(self, directory):
        root = Path(directory).resolve()
        raw = {'task.md': b'explicit synthetic task', 'train.csv': b'original synthetic train bytes',
               'test.csv': b'original test bytes', 'sample.csv': b'original sample bytes',
               'split.bin': b'original ordered split witness; not a parser fixture'}
        for name, value in raw.items(): (root/name).write_bytes(value)
        paths = {'task': root/'task.md', 'input:train': root/'train.csv',
                 'input:test': root/'test.csv', 'input:sample_submission': root/'sample.csv',
                 'source:0:fixture.py': Path(__file__).resolve()}
        fingerprints = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()}
        frame = pd.DataFrame({'number': [1., 9., 3., 9., 5., 9.],
            'category': ['x','outside','y','outside','x','outside'],
            'response': [2.,999.,4.,999.,6.,999.], 'identifier': [Poison() for _ in range(6)]})
        spec = dict(kind='regression', metric='rmse', target='response', id='identifier',
            features=['number','category'], n_train=6, task_path=str(root/'task.md'),
            paths={k:str(root/n) for k,n in [('train','train.csv'),('test','test.csv'),('sample_submission','sample.csv')]},
            strict_task_contract=dict(full_input_provenance_verified=True))
        declaration = SimpleNamespace(ready_for_projection=True,
            paths=dict(train='train.csv', test='test.csv', sample_submission='sample.csv'),
            declaration=SimpleNamespace(target='response', identifier='identifier', kind='regression'),
            receipt=dict(task_text_sha256=fingerprints['task'], dictionary_path=None))
        metric = SimpleNamespace(status='resolved', name='rmse', require_resolved=lambda: None)
        original = OLD.OriginalBudget()
        checkpoint = Checkpoint(original, root)
        budget = E.CallerBudget(original, checkpoint, io_bytes_already_charged=0)
        witness = E.TrustedFrameWitness(frame, spec, declaration, metric, original, checkpoint,
            declaration.receipt, fingerprints, paths)
        roles = E.RoleAuthority(('number','category'), 'response', ('identifier',), 'regression', 'rmse')
        tr, va = [4,0,2], [1,3]
        authority = E.SplitInputAuthority(6, fingerprints['input:train'], fingerprints['task'], None,
            hashlib.sha256((root/'split.bin').read_bytes()).hexdigest(), OLD.ordered_digest(tr),
            OLD.ordered_digest(va), OLD.ordered_digest(tr+va))
        return dict(frame=frame, spec=spec, declaration=declaration, metric_spec=metric,
            witness=witness, roles=roles, expected_role_sha256=OLD.role_digest(roles),
            authority=authority, fitting_positions=tr, validation_positions=va,
            split_path=root/'split.bin', system_prompt='SAME SYSTEM', bounds=B, budget=budget)

    def test_exact_frame_reuse_hash_IO_scope_and_original_RSS_no_parser_or_clock(self):
        with tempfile.TemporaryDirectory() as directory:
            a = self.arguments(directory)
            expected = 2 * (sum(Path(p).stat().st_size for p in a['witness'].source_paths.values())
                            + Path(a['split_path']).stat().st_size)
            with patch.object(pd, 'read_csv', side_effect=AssertionError('Second parser forbidden')):
                context, receipt = E.prepare_validated_frame_context(**a)
            self.assertEqual(context['fitting_context']['data']['target']['mean'], 4.)
            self.assertEqual(receipt['measured_fresh_hash_IO_bytes'], expected)
            self.assertEqual(receipt['caller_hash_IO_counter_delta'], expected)
            self.assertIsNone(receipt['upstream_native_parser_IO_bytes'])
            self.assertIsNone(receipt['total_parent_IO_bytes'])
            self.assertFalse(receipt['total_parent_IO_qualified'])
            self.assertFalse(receipt['table_reparsed'])
            self.assertEqual(a['budget'].started, 10.)
            self.assertEqual(a['budget'].deadline, 100.)
            self.assertIsNone(receipt['final_resource_guard']['raw_RSS_bytes'])

    def test_different_producer_objects_stop_before_fresh_hash_IO(self):
        for key in ('frame','spec','declaration','metric_spec'):
            with tempfile.TemporaryDirectory() as directory:
                a = self.arguments(directory)
                a[key] = object()
                with self.subTest(key=key), self.assertRaisesRegex(E.ExtractionRejected, 'exact_strict_producer_objects'):
                    E.prepare_validated_frame_context(**a)
                self.assertEqual(a['budget'].io_bytes, 0)

    def test_missing_resource_authority_or_unconfirmed_sample_never_starts_IO(self):
        for change in ('resource','budget','receipt','fingerprints'):
            with tempfile.TemporaryDirectory() as directory:
                a = self.arguments(directory)
                if change == 'resource': a['witness'].producer_checkpoint.resources = None
                if change == 'budget': a['budget'] = object()
                if change == 'receipt': a['declaration'].receipt = {}
                if change == 'fingerprints': a['witness'].source_fingerprints.clear()
                with self.subTest(change=change), self.assertRaises(E.ExtractionRejected):
                    E.prepare_validated_frame_context(**a)
                if type(a['budget']) is E.CallerBudget: self.assertEqual(a['budget'].io_bytes, 0)

    def test_actual_input_hash_drift_and_post_projection_change_return_no_context(self):
        with tempfile.TemporaryDirectory() as directory:
            a = self.arguments(directory)
            Path(a['witness'].source_paths['input:train']).write_bytes(b'changed train')
            with self.assertRaisesRegex(E.ExtractionRejected, 'strict_producer_input_or_source_changed'):
                E.prepare_validated_frame_context(**a)
        with tempfile.TemporaryDirectory() as directory:
            a = self.arguments(directory)
            original = E.extract_fitting_context
            def changing(**kwargs):
                value = original(**kwargs)
                Path(a['witness'].source_paths['task']).write_bytes(b'late drift')
                return value
            with patch.object(E, 'extract_fitting_context', side_effect=changing):
                with self.assertRaisesRegex(E.ExtractionRejected, 'post_projection_provenance_changed'):
                    E.prepare_validated_frame_context(**a)
            self.assertIsNotNone(a['budget']._failure)

    def test_guard_denial_and_original_deadline_are_sticky_without_recovery(self):
        for mode in ('denial','deadline'):
            with tempfile.TemporaryDirectory() as directory:
                a = self.arguments(directory)
                if mode == 'denial': a['witness'].producer_checkpoint.denied = True
                else: a['budget'].original.clock.now = 100.
                with self.subTest(mode=mode), self.assertRaises(Exception) as first:
                    E.prepare_validated_frame_context(**a)
                a['witness'].producer_checkpoint.denied = False
                a['budget'].original.clock.now = 12.
                with self.assertRaises(type(first.exception)) as repeated: a['budget'].check()
                self.assertIs(repeated.exception, first.exception)
                self.assertEqual(a['budget'].io_bytes, 0)

    def test_schema_role_and_original_position_witness_mismatches_fail_closed(self):
        for change in ('schema','role','inner_relative','row_order'):
            with tempfile.TemporaryDirectory() as directory:
                a = self.arguments(directory)
                if change == 'schema': a['frame'].rename(columns={'category':'renamed'}, inplace=True)
                if change == 'role': a['roles'] = replace(a['roles'], target='different')
                if change == 'inner_relative': a['authority'] = replace(a['authority'], position_space='inner_relative')
                if change == 'row_order': a['fitting_positions'] = [0,2,4]
                with self.subTest(change=change), self.assertRaises(E.ExtractionRejected):
                    E.prepare_validated_frame_context(**a)


def main():
    unittest.main()


if __name__ == '__main__': raise SystemExit(main())
