"""No-fit checks for mixture objective boundaries and the mandatory cut gate."""
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from benchmark_marginal_hpo import mixed_rmse, inner_subset, objective_result, summarize, worker_closure


class MarginalTests(unittest.TestCase):
    def test_objective_is_mixture_and_native_record_is_unchanged(self):
        native={'status':'ok','metrics':{'rmse':9.,'mae':8.}}
        value=mixed_rmse([0.,2.],[0.,2.],[10.,12.])
        self.assertAlmostEqual(value,1.)
        modified=objective_result(native,value)
        self.assertEqual(modified['metrics']['rmse'],1.)
        self.assertEqual(native['metrics']['rmse'],9.)
        with self.assertRaises(ValueError):mixed_rmse([1,2],[1],[2,3])
        with self.assertRaises(ValueError):mixed_rmse([1],[1],[np.nan])

    def test_inner_control_must_not_include_outer_validation(self):
        inner_subset((np.array([1,2]),np.array([3])),np.array([1,2,3]))
        for a,b in [([1,4],[3]),([1,2],[2,3])]:
            with self.assertRaises(ValueError):inner_subset((np.array(a),np.array(b)),np.array([1,2,3]))

    def test_failed_first_cut_cannot_have_full_mean_or_promotion(self):
        cut={'complete_studies':True,'tpe_improved_PIPE02':False,'outer':{'random':{'mixture_rmse':5},'tpe':{'mixture_rmse':4}}}
        self.assertEqual(summarize({'cuts':[cut]}),{'complete_screen':False,'mean':None,'passed':False})
        self.assertFalse(summarize({'cuts':[cut]*3})['passed'])

    def test_worker_closure_includes_transitive_dependencies(self):
        files={'automl_worker.py':b'from a import run','a.py':b'import b','b.py':b'answer=1','unused.py':b'pass'}
        self.assertEqual(worker_closure(files),['a.py','automl_worker.py','b.py'])


if __name__=='__main__':unittest.main()
