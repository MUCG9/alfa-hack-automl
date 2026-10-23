"""Named-class alignment, source-row isolation and independent coefficient audit."""
from pathlib import Path
import json,sys,tempfile,unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from fit_probability_stacker import fit
from verify_probability_stacker import numerical_meta


class ProbabilityStackerTests(unittest.TestCase):
    def fixture(self,where):
        classes=['z','a','m'];rows=np.arange(10,40);outer=np.arange(60,70);truth=np.full(80,'unavailable',dtype='<U12');truth[rows]=np.tile(classes,10)
        rng=np.random.default_rng(137)
        def features(n):
            values=[]
            for _ in range(3):
                p=rng.uniform(.01,1,(n,3));p/=p.sum(axis=1,keepdims=True);values.append(np.log(p))
            return np.concatenate(values,axis=1)
        np.savez_compressed(where/'meta-input.npz',X=features(len(rows)),y=truth[rows],Z=features(len(outer)),classes=np.asarray(classes),fit_rows=rows,outer_rows=outer)
        (where/'meta').mkdir();return truth,classes,rows,outer

    def test_nonlexical_class_order_matches_independent_softmax(self):
        with tempfile.TemporaryDirectory() as tmp:
            where=Path(tmp);truth,classes,rows,outer=self.fixture(where);fit(where/'meta-input.npz',where/'meta',.1)
            _,_,p,checked=numerical_meta(where,truth,classes,rows,outer,.1)
            self.assertTrue(np.allclose(p.sum(axis=1),1));self.assertEqual(checked['features'],9)
            with np.load(where/'meta/meta_probabilities.npz',allow_pickle=False) as d:stored={k:d[k] for k in d.files}
            stored['probabilities']=stored['probabilities'][:,::-1];np.savez_compressed(where/'meta/meta_probabilities.npz',**stored)
            with self.assertRaises(ValueError):numerical_meta(where,truth,classes,rows,outer,.1)

    def test_outer_labels_are_unread_and_altered_meta_labels_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            where=Path(tmp);truth,classes,rows,outer=self.fixture(where);fit(where/'meta-input.npz',where/'meta',.1)
            truth[outer]='POISON';numerical_meta(where,truth,classes,rows,outer,.1)
            truth[rows[0]]='POISON'
            with self.assertRaises(ValueError):numerical_meta(where,truth,classes,rows,outer,.1)

    def test_meta_fit_and_outer_rows_must_be_disjoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            where=Path(tmp);truth,classes,rows,outer=self.fixture(where)
            with np.load(where/'meta-input.npz',allow_pickle=False) as d:stored={k:d[k] for k in d.files}
            stored['outer_rows'][0]=rows[0];np.savez_compressed(where/'meta-input.npz',**stored)
            with self.assertRaises(ValueError):fit(where/'meta-input.npz',where/'meta',.1)


if __name__=='__main__':unittest.main()
