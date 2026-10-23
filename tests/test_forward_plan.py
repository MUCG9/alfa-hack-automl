"""High reasoning still requires strict fact namespaces and negative memory."""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from plan_forward_objective import validate


class ForwardPlanTests(unittest.TestCase):
    def test_context_sections_cannot_be_used_as_fact_ids(self):
        ctx={'facts':{'ROUND04':{}},'allowed_experiments':{'FORWARD_WORST':{}},'new_factor':{}}
        d={'objective_id':'FORWARD_WORST','control_id':'PIPE02_COMPLETE','component_id':'V16_COMPLETE','evidence_ids':['ROUND04'],
            'hypothesis':'new objective','falsification':'all cuts and Random','leakage_guard':'inner only','next_if_rejected':'different mechanism'}
        self.assertIs(validate(d,ctx),d)
        for changes in [{'evidence_ids':['new_factor']},{'objective_id':'FORWARD_MEAN'},{'component_id':'PIPE02_COMPLETE'}]:
            with self.assertRaises(ValueError):validate(dict(d,**changes),ctx)


if __name__=='__main__':unittest.main()
