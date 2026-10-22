"""HAR-01 proposal budget and factor boundary, without API calls or fits."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from compare_planners import bounded_candidates


class PlannerComparisonTests(unittest.TestCase):
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
