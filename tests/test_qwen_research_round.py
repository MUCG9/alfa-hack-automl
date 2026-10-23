"""Proposal validation must retain the strongest control and a finite tool schema."""
from pathlib import Path
import sys
import unittest
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from qwen_research_round import validate


class QwenRoundTests(unittest.TestCase):
    def proposal(self):
        return {'experiment_id': 'MARGINAL_HPO', 'control_id': 'PIPE02_COMPLETE', 'evidence_ids': ['PIPE02_REG'],
                'hypothesis': 'test contribution', 'falsification': 'any cut fails', 'leakage_guard': 'inner fit only',
                'next_if_rejected': 'different mechanism'}

    def test_weaker_control_unknown_operation_and_extra_actions_are_rejected(self):
        document = self.proposal();self.assertIs(validate(document, {'PIPE02_REG': {}}), document)
        for changes in [{'control_id': 'REG_SINGLE'}, {'experiment_id': 'shell'}, {'code': 'anything'}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate(dict(document, **changes), {'PIPE02_REG': {}})

    def test_evidence_ids_must_exist_and_explanations_cannot_be_empty(self):
        for changes in [{'evidence_ids': []}, {'evidence_ids': ['invented']}, {'hypothesis': ''}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate(dict(self.proposal(), **changes), {'PIPE02_REG': {}})


if __name__ == '__main__': unittest.main(verbosity=2)
