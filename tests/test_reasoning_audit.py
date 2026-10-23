"""Decision-audit contracts: completed/absent means, exact types and evidence IDs."""
from pathlib import Path
import json
import sys
import unittest
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from evaluate_reasoning_profiles import audit


class DecisionAuditTests(unittest.TestCase):
    def setUp(self):self.cases=json.loads((ROOT/'docs/experiments/reasoning02_cases_20261023.json').read_text())

    def answer(self,case):return dict(deepcopy(case['expected']),evidence_ids=[case['required_evidence_id']],reason='The declared gate determines this decision.')

    def test_all_golden_gates_and_available_means_are_distinct(self):
        for case in self.cases:
            self.assertTrue(audit(json.dumps(self.answer(case)),case)['scientific_correct'])
            changed=self.answer(case);changed['complete_mean_available']=not changed['complete_mean_available']
            result=audit(json.dumps(changed),case);self.assertTrue(result['schema_valid']);self.assertFalse(result['scientific_correct'])

    def test_empty_object_boolean_strings_and_context_namespace_are_rejected(self):
        case=self.cases[0]
        for changed in [{},dict(self.answer(case),promote='false'),dict(self.answer(case),evidence_ids=['operator_registry'])]:
            self.assertFalse(audit(json.dumps(changed),case)['schema_valid'])
        self.assertFalse(audit('',case)['json_valid'])

    def test_repeating_negative_operator_cannot_pass_correct_json(self):
        case=self.cases[2];changed=self.answer(case);changed['allowed_next_operator_ids'].append('REPEAT_CLASS_BLEND')
        result=audit(json.dumps(changed),case);self.assertTrue(result['schema_valid']);self.assertFalse(result['scientific_correct'])


if __name__=='__main__':unittest.main()
