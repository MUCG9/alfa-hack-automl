"""HAR-01 proposal budget and factor boundary, without API calls or fits."""
from copy import deepcopy
from pathlib import Path
import sys
import json
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from compare_planners import bounded_candidates, measured_support, plan_with_receipt, proposal_diagnostics, runner


class PlannerComparisonTests(unittest.TestCase):
    def test_raw_receipt_exposes_rejected_feature_proposal_without_changing_plans(self):
        control = {'engine': 'lightgbm', 'params': {'feature_views': 'categorical_te_pair', 'calibrate': True}, 'feature_code': ''}
        content = json.dumps({'candidates': [
            {'engine': 'lightgbm', 'params': {'num_leaves': 31}},
            {'engine': 'lightgbm', 'feature_code': 'def transform(df):\n    return df.copy()'}]})
        def gateway(*args, **kwargs):
            return content, {'status': 'ok'}
        with tempfile.TemporaryDirectory() as temporary, patch.object(runner, 'request_json', gateway):
            output = Path(temporary)
            plans, call, diagnostics = plan_with_receipt({'best_recipe': control}, output, 'staged')
            self.assertEqual(len(plans), 1)
            self.assertEqual(call['status'], 'ok')
            self.assertEqual(diagnostics['raw_candidates'], 2)
            self.assertEqual([r['status'] for r in diagnostics['candidates']], ['supported', 'rejected'])
            self.assertIs(runner.request_json, gateway)
            self.assertEqual(json.loads((output/'staged-raw.json').read_text())['content'], content)

    def test_support_counts_fitting_groups_instead_of_duplicate_rows(self):
        train = pd.DataFrame({'target': ['A', 'A', 'B', 'A', 'B']})
        result = measured_support({'kind': 'classification', 'target': 'target', 'classes': ['A', 'B']},
                                  train, np.array([1, 1, 2, 3, 4]), np.array([0, 1, 2]), np.array([3, 4]))
        self.assertEqual(result['independent_fitting_feature_groups_per_class'], {'A': 1, 'B': 1})
        self.assertEqual(result['validation_rows_per_class'], {'A': 1, 'B': 1})
        with self.assertRaisesRegex(ValueError, 'disjoint'):
            measured_support({'kind': 'classification', 'target': 'target', 'classes': ['A', 'B']},
                             train, np.array([1, 1, 2, 1, 4]), np.array([0, 1, 2]), np.array([3, 4]))

    def test_duplicate_control_does_not_consume_two_distinct_slots(self):
        control = {'engine': 'lightgbm', 'params': {'num_leaves': 63}, 'feature_code': ''}
        proposals = [deepcopy(control)]+[dict(control, params={'num_leaves': n}) for n in [31, 95, 127]]
        selected, rejected = bounded_candidates(control, proposals, 'staged')
        self.assertEqual([r['recipe']['params']['num_leaves'] for r in selected], [63, 31, 95])
        self.assertEqual([r['reason'] for r in rejected], ['duplicate', 'two_candidate_limit'])
        selected[0]['recipe']['params']['num_leaves'] = 42
        self.assertEqual(control['params']['num_leaves'], 63)

    def test_unqualified_selector_is_rejected_instead_of_silently_changed(self):
        control = {'engine': 'lightgbm', 'params': {'num_leaves': 63}, 'feature_code': ''}
        candidate = dict(control, params={'num_leaves': 31, 'feature_selection_top_k': 32})
        selected, rejected = bounded_candidates(control, [candidate], 'baseline')
        self.assertEqual(len(selected), 1)
        self.assertEqual(rejected[0]['reason'], 'feature_selection_not_in_prompt_screen')
        self.assertEqual(candidate['params']['feature_selection_top_k'], 32)


if __name__ == '__main__':
    unittest.main(verbosity=2)
