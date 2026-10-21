"""Offline contracts, provenance and no-leakage tests for fitting-only policies."""
from pathlib import Path
import sys,unittest
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from automl.contracts.messages import DataPolicy,PredictionBundle
from automl.execution.sampling.policies import prepare_training

class DataPolicyTests(unittest.TestCase):
    def setUp(self):
        self.x=pd.DataFrame({'x':np.arange(100,dtype=float),'weather':np.arange(100,dtype=float),'category':pd.Categorical(['a','b']*50)})
        self.x.loc[::5,'weather']=np.nan
        self.y=pd.Series(['major']*90+['rare']*10)
        self.hashes=pd.util.hash_pandas_object(self.x,index=False).to_numpy(dtype='uint64')
        self.parents=np.arange(100)+500
    def run_policy(self,value,**kwargs):
        return prepare_training(self.x,self.y,self.y,None,self.hashes,self.parents,value,**kwargs)
    def test_noop_does_not_disable_existing_weights(self):
        weights=np.linspace(.1,2,100)
        x,y,w,parents,meta=prepare_training(self.x,self.y,self.y,weights,self.hashes,self.parents)
        self.assertIs(x,self.x); self.assertIs(y,self.y); self.assertIs(w,weights)
        self.assertEqual(meta['output_rows'],100)
    def test_version_and_unknown_parameters_rejected(self):
        for value in [{'schema_version':'9'},{'execute_code':'unsafe'},{'factor':float('nan')},{'augmentation':'smotenc'}]:
            with self.assertRaises((ValueError,TypeError)): DataPolicy.parse(value)
    def test_only_fitting_parents_survive_over_under_mask(self):
        for policy in [{'sampling':'under'},{'sampling':'over'},{'augmentation':'mask'}]:
            x,y,w,parents,meta=self.run_policy(policy)
            self.assertTrue(set(parents)<=set(self.parents)); self.assertEqual(len(x),len(y)); self.assertEqual(len(x),len(w))
            self.assertTrue(np.isfinite(w).all()); self.assertLessEqual(len(x),125)
    def test_deterministic_and_input_not_mutated(self):
        original=self.x.copy(deep=True)
        first=self.run_policy({'augmentation':'mask','seed':19}); second=self.run_policy({'augmentation':'mask','seed':19})
        pd.testing.assert_frame_equal(first[0],second[0]); np.testing.assert_array_equal(first[3],second[3])
        pd.testing.assert_frame_equal(self.x,original)
    def test_oversampling_actually_adds_rare_rows(self):
        self.y=pd.Series(['major']*95+['rare']*5)
        out,targets,w,parents,meta=self.run_policy({'sampling':'over','factor':1.5})
        self.assertEqual(len(out),103)
        self.assertEqual(int((targets=='rare').sum()),8)
        self.assertTrue(set(parents[100:])<=set(self.parents[95:]))
    def test_compression_preserves_conflicting_label_mass(self):
        x=pd.DataFrame({'x':[1.]*10+[2.]}); y=pd.Series(['a']*8+['b']*2+['a']); h=pd.util.hash_pandas_object(x,index=False).to_numpy()
        out,targets,w,_,meta=prepare_training(x,y,y,None,h,np.arange(11),{'sampling':'compress'})
        self.assertEqual(len(out),3)
        pair={label:weight for label,weight in zip(targets.iloc[:2],w[:2])}
        self.assertAlmostEqual(pair['a']/pair['b'],4)
    def test_duplicate_beta_controls_mass(self):
        x=pd.DataFrame({'x':[1.]*100+[2.]}); y=pd.Series(['a']*101); h=pd.util.hash_pandas_object(x,index=False).to_numpy()
        _,_,w,_,_=prepare_training(x,y,y,None,h,np.arange(101),{'duplicate_beta':.5})
        self.assertAlmostEqual(w[:100].sum()/w[-1],10)
    def test_masking_changes_only_permitted_numeric_values(self):
        out,y,w,parents,meta=self.run_policy({'augmentation':'mask','copy_fraction':.25,'mask_probability':.3})
        self.assertEqual(out.category.astype(str).iloc[100:].tolist(),self.x.loc[parents[100:]-500,'category'].astype(str).tolist())
        self.assertTrue(out.x.notna().all()); self.assertEqual(meta['synthetic_rows'],25)
    def test_prediction_contract_rejects_order_and_split(self):
        bundle=PredictionBundle('pred.npz',3,('a','b'),('no','yes'),'abc')
        bundle.validate(3,['a','b'],'abc')
        with self.assertRaises(ValueError): bundle.validate(3,['b','a'],'abc')
        with self.assertRaises(ValueError): bundle.validate(3,['a','b'],'other')
    def test_foreign_or_repeated_initial_ids_rejected(self):
        with self.assertRaises(ValueError): prepare_training(self.x,self.y,self.y,None,self.hashes,np.zeros(100))
    def test_resampling_regression_rejected(self):
        with self.assertRaises(ValueError): self.run_policy({'sampling':'over'},kind='regression')

if __name__=='__main__': unittest.main(verbosity=2)
