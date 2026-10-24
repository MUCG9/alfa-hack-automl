'Prepared package-import contracts only; not executed. This canonical script runs only its own declared methods. Original standalone loader arguments are replaced by frozen package imports; all other class/helper/method ASTs are unchanged.'
import argparse
import copy
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import struct
import sys
import unittest
from unittest.mock import patch

BUILDER_SHA = '48793ea77b607583c480965e31c9658ba6465cf2e05545239549bf2349e69314'
BOUNDS_SHA = '1f6b27debfdf2609e03641beae8235ad1a034bd97450b61156bd991cc588a93c'
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'tests'))
from automl.search import fitting_extractor as extractor, fitting_bounds as bounds


class FakeClock:
    def __init__(self):
        self.now = 12.

    def __call__(self):
        return self.now


class OriginalBudget:
    def __init__(self):
        self.clock, self.started, self.deadline = FakeClock(), 10., 100.
        self.checks, self.denied = 0, False

    def checkpoint(self):
        self.checks += 1
        if self.denied:
            raise PermissionError('synthetic_original_resource_denial')


class Column:
    """Trusted positional stand-in; poison outside the declared fitting rows."""
    def __init__(self, values, allowed=(4, 0, 2)):
        self.values, self.allowed, self.touched = values, set(allowed), []
        self.iloc = self

    def __len__(self):
        return len(self.values)

    def __getitem__(self, index):
        if index not in self.allowed:
            raise AssertionError('nonfitting_row_was_read')
        self.touched.append(index)
        return self.values[index]


def ordered_digest(values):
    return hashlib.sha256(b''.join(struct.pack('<q', value) for value in values)).hexdigest()


def role_digest(roles):
    raw = json.dumps(dict(features=list(roles.features), target=roles.target,
        identifiers=list(roles.identifiers), kind=roles.kind, metric=roles.metric,
        objective_status=roles.objective_status, source_role=roles.source_role),
        ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


class FittingExtractorContracts(unittest.TestCase):
    def arguments(self, *, names=('number', 'category', 'response', 'identifier'), **changes):
        number, category, target, identifier = names
        tr, va = [4, 0, 2], [1, 3]
        roles = extractor.RoleAuthority((number, category), target, (identifier,), 'regression', 'rmse')
        original = OriginalBudget()
        columns = {number: Column([1., object(), 3., object(), None, object()]),
                   category: Column(['x', object(), 'y', object(), 'x', object()]),
                   target: Column([2., object(), 4., object(), 6., object()])}
        authority = extractor.SplitInputAuthority(6, 'a'*64, 'b'*64, None, 'c'*64,
            ordered_digest(tr), ordered_digest(va), ordered_digest(tr+va))
        result = dict(source_columns=columns, fitting_positions=tr, validation_positions=va,
            roles=roles, expected_role_sha256=role_digest(roles), authority=authority,
            observed_input_sha256=dict(train='a'*64, task='b'*64, dictionary=None),
            observed_split_file_sha256='c'*64, system_prompt='SAME SYSTEM', bounds=bounds,
            budget=extractor.CallerBudget(original, original.checkpoint, io_bytes_already_charged=123))
        result.update(changes)
        return result

    def extract(self, **changes):
        return extractor.extract_fitting_context(**self.arguments(**changes))

    def assert_untouched(self, arguments):
        for column in arguments['source_columns'].values():
            self.assertEqual(column.touched, [])

    def test_ordered_projection_reads_only_fitting_and_matches_statistics(self):
        args = self.arguments()
        context, receipt = extractor.extract_fitting_context(**args)
        packet = context['fitting_context']
        for column in args['source_columns'].values():
            self.assertEqual(column.touched, [4, 0, 2])
        self.assertEqual(packet['data']['target']['mean'], 4.)
        self.assertEqual(packet['data']['features']['number']['numeric'], dict(min=1., max=3., mean=2.))
        self.assertEqual(packet['data']['features']['number']['missing'], 1)
        self.assertEqual(receipt['ordered_fitting_int64le_sha256'], ordered_digest([4, 0, 2]))
        self.assertIsNone(receipt['quality_metric'])

    def test_poisoned_validation_unselected_and_unused_tail_never_read(self):
        args = self.arguments()
        _, receipt = extractor.extract_fitting_context(**args)
        self.assertEqual(receipt['validation_positions_only'], 2)
        self.assertEqual(receipt['fitting_rows'], 3)
        self.assertFalse(receipt['whole_feedback_fitting_only'])
        # Row5 is neither fit nor validation: forward-split unused rows are fine.
        for column in args['source_columns'].values():
            self.assertNotIn(5, column.touched)

    def test_ID_extra_test_or_unsupported_role_rejects_before_column_access(self):
        class Poison:
            def __len__(self):
                raise AssertionError('ID_vector_was_inspected')
        for extra in ['identifier', 'test_target', 'validation_target']:
            args = self.arguments()
            args['source_columns'][extra] = Poison()
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, 'closed_train_feature_target'):
                extractor.extract_fitting_context(**args)
        for roles in [extractor.RoleAuthority(('identifier',), 'response', ('identifier',), 'regression', 'rmse'),
                      extractor.RoleAuthority(('number',), 'response', (), 'regression', 'rmse', source_role='test'),
                      extractor.RoleAuthority(('number',), 'response', (), 'regression', 'unknown')]:
            args = self.arguments(roles=roles, expected_role_sha256=role_digest(roles))
            with self.subTest(roles=roles), self.assertRaises(ValueError):
                extractor.extract_fitting_context(**args)
            self.assert_untouched(args)

    def test_input_dictionary_roles_and_split_file_bindings_are_pre_read(self):
        for change in [dict(observed_input_sha256=dict(train='d'*64, task='b'*64, dictionary=None)),
                       dict(observed_input_sha256=dict(train='a'*64, task='b'*64, dictionary='d'*64)),
                       dict(expected_role_sha256='d'*64), dict(observed_split_file_sha256='d'*64)]:
            args = self.arguments(**change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                extractor.extract_fitting_context(**args)
            self.assert_untouched(args)

    def test_duplicates_boolean_outside_and_inner_relative_positions_reject(self):
        for tr in [[4, 4, 2], [4, True, 2], [-1, 0, 2], [6, 0, 2], [0, 1, 2]]:
            args = self.arguments(fitting_positions=tr)
            with self.subTest(tr=tr), self.assertRaises(ValueError):
                extractor.extract_fitting_context(**args)
            self.assert_untouched(args)
        args = self.arguments()
        args['authority'] = replace(args['authority'], position_space='inner_relative')
        with self.assertRaisesRegex(ValueError, 'original_train_position_authority'):
            extractor.extract_fitting_context(**args)
        self.assert_untouched(args)

    def test_order_and_validation_disjointness_are_not_set_only_bindings(self):
        for change in [dict(fitting_positions=[0, 2, 4]), dict(validation_positions=[1, 1]),
                       dict(validation_positions=[1, 2]), dict(validation_positions=[3, 1])]:
            args = self.arguments(**change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                extractor.extract_fitting_context(**args)
            self.assert_untouched(args)

    def test_column_shapes_all_checked_before_first_scalar(self):
        args = self.arguments()
        args['source_columns']['response'] = Column([2., 4., 6.])
        with self.assertRaisesRegex(ValueError, 'original_source_column_length'):
            extractor.extract_fitting_context(**args)
        self.assert_untouched(args)

    def test_finite_scalar_and_no_target_imputation_policy(self):
        for value in [float('inf'), float('-inf'), ['nested']]:
            args = self.arguments()
            args['source_columns']['number'].values[4] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                extractor.extract_fitting_context(**args)
        for value in [None, float('nan'), True, '12']:
            args = self.arguments()
            args['source_columns']['response'].values[4] = value
            with self.subTest(target=value), self.assertRaises(ValueError):
                extractor.extract_fitting_context(**args)

    def test_class_labels_NA_and_001_are_lexical_and_no_outside_class(self):
        args = self.arguments()
        roles = replace(args['roles'], kind='classification', metric='macro_f1')
        args.update(roles=roles, expected_role_sha256=role_digest(roles))
        args['source_columns']['response'] = Column(['001', object(), 'NA', object(), '001', object()])
        context, _ = extractor.extract_fitting_context(**args)
        self.assertEqual(context['fitting_context']['data']['target']['class_counts'], {'001': 2, 'NA': 1})
        self.assertIsNone(context['fitting_context']['data']['group_support'])

    def test_falsey_original_or_non_adapter_budget_rejects_without_reads(self):
        class Falsey(OriginalBudget):
            def __bool__(self):
                return False
        bad = Falsey()
        with self.assertRaisesRegex(ValueError, 'original_caller_budget'):
            extractor.CallerBudget(bad, bad.checkpoint, io_bytes_already_charged=0)
        self.assertEqual(bad.checks, 0)
        for bad in [None, False, object()]:
            args = self.arguments(budget=bad)
            with self.subTest(budget=bad), self.assertRaisesRegex(ValueError, 'CallerBudget_adapter'):
                extractor.extract_fitting_context(**args)
            self.assert_untouched(args)

    def test_same_original_deadline_rollback_and_denial_are_sticky(self):
        for fault in ['deadline', 'rollback', 'denial', 'origin']:
            args = self.arguments()
            adapter = args['budget']
            parent = adapter.original
            if fault == 'deadline':
                parent.clock.now = 100.
            elif fault == 'rollback':
                parent.clock.now = 11.
            elif fault == 'origin':
                parent.deadline = 110.
            else:
                parent.denied = True
            with self.subTest(fault=fault), self.assertRaises(Exception) as first:
                extractor.extract_fitting_context(**args)
            parent.clock.now, parent.deadline, parent.denied = 20., 100., False
            with self.assertRaises(Exception) as second:
                adapter.check()
            self.assertIs(first.exception, second.exception)
            self.assert_untouched(args)

    def test_IO_counter_additive_limit_and_no_local_IO_or_clock(self):
        args = self.arguments()
        adapter = args['budget']
        adapter.charge_io(7)
        _, receipt = extractor.extract_fitting_context(**args)
        self.assertEqual(receipt['new_input_IO_bytes'], 0)
        self.assertEqual(receipt['caller_budget']['preparation_IO_bytes'], 130)
        self.assertEqual(receipt['caller_budget']['preparation_seconds'], 2.)
        self.assertIs(adapter.clock, adapter.original.clock)
        with self.assertRaisesRegex(ValueError, 'original_parent_IO_limit'):
            adapter.charge_io(extractor.MAX_IO_BYTES)
        with self.assertRaisesRegex(ValueError, 'original_parent_IO_limit'):
            adapter.check()

    def test_scalar_and_projection_memory_limits_fail_without_truncation(self):
        for constant in ['MAX_SCALAR_VIEW_BYTES', 'MAX_RETAINED_ESTIMATE_BYTES']:
            with self.subTest(constant=constant), patch.object(extractor, constant, 1), self.assertRaises(ValueError):
                self.extract()
        args = self.arguments()
        args['source_columns']['category'].values[4] = 'я' * 2049
        with self.assertRaisesRegex(ValueError, 'scalar_UTF8_limit'):
            extractor.extract_fitting_context(**args)

    def test_renamed_unicode_schema_has_same_stats_and_UTF8_role_cap(self):
        first, _ = self.extract()
        second, _ = self.extract(names=('длина', '種類', 'цель', 'ключ'))
        self.assertEqual(first['fitting_context']['data']['target']['mean'], second['fitting_context']['data']['target']['mean'])
        self.assertEqual(second['fitting_context']['data']['features']['длина'], first['fitting_context']['data']['features']['number'])
        with self.assertRaisesRegex(ValueError, 'role_name_UTF8_limit'):
            self.extract(names=('я'*65, 'category', 'response', 'identifier'))

    def test_packet_message_caps_reuse_existing_preflight_and_are_fresh(self):
        args = self.arguments()
        context, receipt = extractor.extract_fitting_context(**args)
        self.assertEqual(set(context), {'fitting_context'})
        self.assertLessEqual(receipt['builder']['packet_UTF8_bytes'], 8192)
        self.assertLessEqual(receipt['gateway_preflight']['messages_UTF8_bytes'], 65536)
        self.assertTrue(receipt['gateway_preflight']['charged_inside_existing_parent_deadline'])
        args['source_columns']['number'].values[0] = 999.
        self.assertEqual(context['fitting_context']['data']['features']['number']['numeric']['max'], 3.)
        with self.assertRaises(ValueError):
            self.extract(system_prompt='я'*32768)
        wide = self.arguments()
        names = tuple('feature_%02d_' % i + 'n'*100 for i in range(64))
        roles = replace(wide['roles'], features=names)
        wide.update(roles=roles, expected_role_sha256=role_digest(roles),
            source_columns={**{name: Column([1., object(), 2., object(), 3., object()]) for name in names},
                            'response': wide['source_columns']['response']})
        with self.assertRaises(ValueError):
            extractor.extract_fitting_context(**wide)
        with patch.object(bounds, 'PreparationBudget', side_effect=AssertionError('fresh_5s_budget_forbidden')):
            self.extract()

    def test_no_network_and_no_legacy_profile_or_advice_authority_surface(self):
        with patch.object(socket, 'socket', side_effect=AssertionError('network_forbidden')):
            context, receipt = self.extract()
        self.assertEqual((receipt['API_calls'], receipt['model_fits']), (0, 0))
        self.assertFalse(receipt['legacy_context_merged'])
        for key in ['profile', 'split_info', 'validation_targets', 'outer_scores', 'advice']:
            with self.subTest(key=key), self.assertRaises(TypeError):
                extractor.extract_fitting_context(**dict(self.arguments(), **{key: {}}))
        self.assertEqual(context['fitting_context']['advice'], dict(data=None, method=None, loss=None, kernel=None))


def main():
    unittest.main()


if __name__ == '__main__':
    main()
