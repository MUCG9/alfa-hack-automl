from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from automl.search.runner import coordinator_plans
from automl.search.policy import normalize

class PlannerIsolationTests(unittest.TestCase):
    def test_unsupported_proposal_does_not_abort_valid_sibling(self):
        unsupported=normalize({'engine':'linear_text','params':{}})
        valid=normalize({'engine':'lightgbm','params':{}})
        accepted,rejected=coordinator_plans([unsupported,valid],32)
        self.assertEqual(len(accepted),1);self.assertEqual(accepted[0]['engine'],'lightgbm')
        self.assertEqual(accepted[0]['params']['feature_selection_top_k'],32)
        self.assertEqual(rejected[0]['engine'],'linear_text')

if __name__=='__main__':unittest.main(verbosity=2)
