'Prepared package-import contracts only; not executed. This canonical script runs only its own declared methods. Original standalone loader arguments are replaced by frozen package imports; all other class/helper/method ASTs are unchanged.'
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import struct
import sys
import unittest

BOUNDS_SHA = '1f6b27debfdf2609e03641beae8235ad1a034bd97450b61156bd991cc588a93c'
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'tests'))
from automl.search import fitting_context as builder, fitting_bounds as bounds


class SharedBudget:
    """Synthetic check probe, not evidence of real preparation time or IO."""
    def __init__(self, fail=False):
        self.checks = 0
        self.fail = fail

    def check(self):
        self.checks += 1
        if self.fail:
            raise RuntimeError('synthetic_shared_parent_exhausted')

    def receipt(self):
        return dict(synthetic_preparation_budget=True)


class FitContextContracts(unittest.TestCase):
    def arguments(self, **changes):
        result = dict(fitting_positions=[0, 2, 4], source_row_count=6,
            fitting_features={'number': [1., 3., None], 'category': ['x', 'x', 'y']},
            fitting_target=[2., 4., 6.], allowed_features=['number', 'category'],
            target_name='response', protected_identifiers=['identifier'],
            kind='regression', metric='rmse', input_sha256={'train': 'a'*64, 'task': 'b'*64},
            split_sha256='c'*64, bounds=bounds, budget=SharedBudget())
        result.update(changes)
        return result

    def build(self, **changes):
        return builder.build_fitting_context(**self.arguments(**changes))

    def test_regression_reduces_only_aligned_fitting_vectors(self):
        packet, receipt = self.build()
        self.assertEqual(packet['data']['features']['number']['missing'], 1)
        self.assertEqual(packet['data']['features']['number']['numeric'], dict(min=1., max=3., mean=2.))
        self.assertEqual(packet['data']['target']['mean'], 4.)
        self.assertAlmostEqual(packet['data']['target']['std'], math.sqrt(8./3), places=7)
        self.assertEqual(packet['provenance']['fitting_rows'], 3)
        self.assertIsNone(packet['data']['group_support'])
        self.assertIsNone(receipt['quality_metric'])

    def test_class_counts_do_not_accept_or_infer_nonfitting_classes(self):
        packet, _ = self.build(kind='classification', metric='macro_f1',
                               fitting_target=['left', 'left', 'right'])
        self.assertEqual(packet['data']['target']['class_counts'], {'left': 2, 'right': 1})
        self.assertNotIn('outside', json.dumps(packet))
        self.assertTrue(packet['objective']['greater_is_better'])
        # Full-train profile and validation labels are not accepted surfaces.
        for forbidden in ['full_train_profile', 'validation_targets', 'outer_scores']:
            with self.subTest(forbidden=forbidden), self.assertRaises(TypeError):
                builder.build_fitting_context(**dict(self.arguments(), **{forbidden: object()}))

    def test_full_length_target_rejected_before_values_are_inspected(self):
        class Opaque:
            def __str__(self):
                raise AssertionError('nonfitting target was inspected')
        with self.assertRaises(builder.ContextRejected) as caught:
            self.build(fitting_target=[Opaque() for _ in range(6)])
        self.assertEqual(caught.exception.code, 'aligned_fitting_target_only_required')

    def test_target_and_ID_roles_rejected_before_feature_reduction(self):
        for name in ['response', 'identifier']:
            with self.subTest(name=name), self.assertRaises(builder.ContextRejected) as caught:
                self.build(allowed_features=[name], fitting_features={name: [object()]*3})
            self.assertEqual(caught.exception.code, 'target_or_protected_ID_in_features')

    def test_positions_reject_duplicates_boolean_and_outside_rows(self):
        for positions in [[0, 0, 4], [0, True, 4], [-1, 2, 4], [0, 2, 6]]:
            with self.subTest(positions=positions), self.assertRaises(builder.ContextRejected):
                self.build(fitting_positions=positions)
        with self.assertRaises(builder.ContextRejected) as caught:
            self.build(source_row_count=3, fitting_positions=[0, 1, 2])
        self.assertEqual(caught.exception.code, 'proper_fitting_subset_required_not_full_train')

    def test_closed_feature_mapping_and_vector_lengths(self):
        for columns in [{'number': [1, 2, 3], 'category': ['x']},
                        {'number': [1, 2, 3], 'category': ['x']*3, 'hidden_target': [0]*3}]:
            with self.subTest(columns=columns), self.assertRaises(builder.ContextRejected):
                self.build(fitting_features=columns)

    def test_order_fingerprints_change_but_inputs_do_not_mutate(self):
        args = self.arguments()
        original = copy.deepcopy({k: v for k, v in args.items() if k not in {'bounds', 'budget'}})
        first, _ = builder.build_fitting_context(**args)
        reverse = self.arguments(fitting_positions=[4, 2, 0],
            fitting_features={k: list(reversed(v)) for k, v in args['fitting_features'].items()},
            fitting_target=list(reversed(args['fitting_target'])))
        second, _ = builder.build_fitting_context(**reverse)
        self.assertEqual(first['data'], second['data'])
        for field in ['ordered_fitting_positions_int64le_sha256',
                      'fitting_feature_scalar_view_sha256', 'fitting_target_scalar_view_sha256']:
            self.assertNotEqual(first['provenance'][field], second['provenance'][field])
        expected = hashlib.sha256(b''.join(struct.pack('<q', n) for n in [0, 2, 4])).hexdigest()
        self.assertEqual(first['provenance']['ordered_fitting_positions_int64le_sha256'], expected)
        self.assertEqual(original, {k: v for k, v in args.items() if k not in {'bounds', 'budget'}})

    def test_nonfinite_features_are_described_but_target_is_not_imputed(self):
        packet, _ = self.build(fitting_features={'number': [float('nan'), float('inf'), 2.],
                                                'category': ['x', None, 'y']})
        self.assertEqual(packet['data']['features']['number']['missing'], 1)
        self.assertEqual(packet['data']['features']['number']['nonfinite'], 1)
        json.dumps(packet, allow_nan=False)
        for target in [[1., float('nan'), 2.], [1., float('inf'), 2.], [1, 2**2048, 3]]:
            with self.subTest(target=type(target[1]).__name__), self.assertRaises(builder.ContextRejected):
                self.build(fitting_target=target)

    def test_cardinality_is_explicitly_lower_bounded_after_cap(self):
        n = 2050
        packet, _ = self.build(fitting_positions=list(range(n)), source_row_count=n+1,
            fitting_features={'category': [str(i) for i in range(n)]},
            fitting_target=list(range(n)), allowed_features=['category'])
        self.assertEqual(packet['data']['features']['category']['distinct'], 'at_least_2049')
        self.assertEqual(packet['data']['distinct_cap'], 2048)

    def test_UTF8_packet_limit_is_measured_without_column_name_heuristics(self):
        advice = {'source_sha256': 'd'*64, 'packet': {'text': 'x'*4096}}
        packet, receipt = self.build(method_advice=advice)
        self.assertLessEqual(receipt['packet_UTF8_bytes'], 8192)
        self.assertEqual(packet['advice']['method']['packet']['text'], 'x'*4096)
        advice['packet']['text'] = 'я'*4096
        with self.assertRaises(ValueError):
            self.build(method_advice=advice)
        with self.assertRaises(ValueError):
            self.build(method_advice={'source_sha256': 'd'*64, 'packet': {'bad': float('nan')}})

    def test_separate_advice_copy_and_exact_gateway_serialization(self):
        knowledge = {'source_sha256': 'd'*64, 'packet': {'notice': 'source-bound advice'}}
        packet, receipt = self.build(data_advice=knowledge, method_advice=knowledge,
                                     loss_advice=knowledge, kernel_advice=knowledge)
        knowledge['packet']['notice'] = 'mutated after preparation'
        self.assertEqual(set(packet['advice']), {'data', 'method', 'loss', 'kernel'})
        self.assertEqual(packet['advice']['method']['packet']['notice'], 'source-bound advice')
        context, proof = builder.preflight_gateway_messages('SYSTEM😀', packet,
            receipt=receipt, bounds=bounds, budget=SharedBudget())
        messages = [{'role': 'system', 'content': 'SYSTEM😀'},
                    {'role': 'user', 'content': json.dumps(context, ensure_ascii=False, default=str)}]
        raw = json.dumps(messages, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.assertEqual(proof['messages_UTF8_bytes'], len(raw))
        self.assertEqual(proof['messages_sha256'], hashlib.sha256(raw).hexdigest())

    def test_receipt_recheck_shared_budget_and_complete_message_overflow(self):
        with self.assertRaisesRegex(RuntimeError, 'synthetic_shared_parent_exhausted'):
            self.build(budget=SharedBudget(fail=True))
        packet, receipt = self.build()
        class FalseyBudget(SharedBudget):
            def __bool__(self):
                return False
        class MissingReceipt:
            def check(self):
                raise AssertionError('invalid shared budget must reject before check')
        for bad in [FalseyBudget(), MissingReceipt()]:
            with self.subTest(budget=type(bad).__name__):
                with self.assertRaises(builder.ContextRejected) as rejected:
                    self.build(budget=bad)
                self.assertEqual(rejected.exception.code, 'shared_preparation_budget_required')
                with self.assertRaises(builder.ContextRejected) as rejected:
                    builder.preflight_gateway_messages('SYSTEM', packet, receipt=receipt,
                        bounds=bounds, budget=bad)
                self.assertEqual(rejected.exception.code, 'shared_preparation_budget_required')
                if isinstance(bad, SharedBudget):
                    self.assertEqual(bad.checks, 0)
        with self.assertRaises(ValueError):
            builder.preflight_gateway_messages('я'*32768, packet,
                receipt=receipt, bounds=bounds, budget=SharedBudget())
        tampered = copy.deepcopy(packet)
        tampered['outer_score'] = .99
        with self.assertRaises(builder.ContextRejected) as caught:
            builder.preflight_gateway_messages('S', tampered,
                receipt=receipt, bounds=bounds, budget=SharedBudget())
        self.assertEqual(caught.exception.code, 'builder_packet_receipt_mismatch')


def main():
    unittest.main()


if __name__ == '__main__':
    main()
