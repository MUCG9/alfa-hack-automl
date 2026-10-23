"""No-fit checks for review facts, references, comparators and resource bounds."""
from pathlib import Path
import copy
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from research_evidence import CONTRACT_ID, evidence_context, validate_review


class ResearchEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.context = evidence_context({'mvp': {'tasks': {}}, 'cost': {'selector_diagnostic': {
            'per_class': {'Analysis': {'delta': -.012, 'independent_fitting_groups': 695},
                          'Worms': {'delta': -.12, 'independent_fitting_groups': 46}},
            'rarest_class': 'Worms', 'supported_class_drop_gate_passed': False}}})
        self.review = {'hypotheses': [{'hypothesis': 'A testable explanation',
                        'evidence_ids': ['SELECTOR_GATE'], 'limitation': 'Association only'}],
            'next_experiments': [{'hypothesis': 'A testable explanation', 'single_change': 'one factor',
                'evidence_ids': ['SELECTOR_GATE'], 'control_id': 'CLS_SINGLE',
                'acceptance_contract_id': CONTRACT_ID, 'falsification': 'fails fixed paired gates',
                'budget': {'threads': 2, 'worker_seconds': 600, 'worker_memory_mib': 1536,
                           'max_fits': 4, 'total_seconds': 2400}}], 'unknowns': []}

    def test_derive_supported_violation_from_independent_groups(self):
        gate = self.context['evidence_cards']['SELECTOR_GATE']['facts']
        self.assertEqual(gate['supported_class_violations'], {'Analysis': -.012})
        self.assertEqual(gate['rarest_fitting_groups'], 46)
        validate_review(self.review, self.context)

    def test_reject_unknown_reference_and_weak_control(self):
        for field, value, error in [('evidence_ids', ['invented'], 'evidence ID'),
                                     ('control_id', 'selector32', 'Unqualified control')]:
            review = copy.deepcopy(self.review)
            review['next_experiments'][0][field] = value
            with self.assertRaisesRegex(ValueError, error):
                validate_review(review, self.context)

    def test_reject_changed_gate_and_extra_resource(self):
        review = copy.deepcopy(self.review)
        review['next_experiments'][0]['acceptance_contract_id'] = 'weakened'
        with self.assertRaisesRegex(ValueError, 'Changed acceptance'):
            validate_review(review, self.context)
        review = copy.deepcopy(self.review)
        review['next_experiments'][0]['budget']['threads'] = 8
        with self.assertRaisesRegex(ValueError, 'Resource cap'):
            validate_review(review, self.context)

    def test_empty_live_response_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Invalid review envelope'):
            validate_review({}, self.context)

    def test_complete_unit_and_rmse_direction_are_computed_by_tool(self):
        context = evidence_context({'mvp': {'tasks': {
            'regression': {'metric': 'rmse', 'mean': 36., 'control_mean': 35.},
            'classification': {'metric': 'macro_f1', 'mean': .6, 'control_mean': .65}}}})
        reg = context['evidence_cards']['MVP_REGRESSION']['facts']
        cls = context['evidence_cards']['MVP_CLASSIFICATION']['facts']
        self.assertEqual(reg['comparison_unit'], 'complete_agent')
        self.assertEqual(reg['control_id'], 'COMPLETE_AGENT')
        self.assertEqual(reg['observed_mean_oriented_gain'], -1.)
        self.assertEqual(reg['metric_direction'], 'minimize')
        self.assertFalse(reg['observed_mean_improved'])
        self.assertFalse(cls['observed_mean_improved'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
