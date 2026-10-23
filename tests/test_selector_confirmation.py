"""Pre-fit checks for the single-confirmation executor; never trains."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import run_selector_confirmation as executor


class ConfirmationExecutorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.search=self.root/'search.json';self.search.write_text('{}')
        self.split=self.root/'split.npz';self.split.write_bytes(b'fixture-not-loaded')
        profile=self.root/'profile.json';profile.write_text('{}')
        inventory=self.root/'baseline_inventory.json';inventory.write_text(json.dumps({'data_root':str(self.root),'inputs':{}}))
        self.baseline=self.root/'baseline_verified.json'
        self.baseline.write_text(json.dumps({'baseline_complete':True,'inventory_sha256':executor.sha(inventory),
            'original_runs':[{'version':v,'kind':k,'scopes':[{'scope':s,'path':str(profile),'profile_sha256':executor.sha(profile)}
                for s in ('search','confirmation')]} for v in ('v11-featureviews1','v16-mean1') for k in ('classification','regression')]}))
        self.output=self.root/'fresh'
        self.compiled={'a.py':b'pass'}
        recipe={'engine':'xgboost','params':{},'feature_code':''}
        self.plan={'experiment':'SEL-01-one-confirmation-screen',
            'budget':{'timeout_seconds':900,'threads':2,'whole_tree_memory_gib':1.7},
            'recipe':recipe,'candidate_id':'model-'+executor.canonical_hash(recipe)[:20],
            'long_run':str(self.root/'LONG'),
            'protected_artifacts_sha256':{str(p):executor.sha(p) for p in (self.search,inventory)},
            'original_confirmation_split':{'path':str(self.split),'sha256':executor.sha(self.split)},
            'compiled_source_sha256':{n:hashlib.sha256(b).hexdigest() for n,b in self.compiled.items()}}

    def call(self,plan=None,ready=True,compiled=None):
        with patch.object(executor,'build_files',return_value=self.compiled if compiled is None else compiled),patch.object(executor,'long_run_ready',return_value=ready):
            return executor.validate(self.plan if plan is None else plan,self.output,self.baseline,self.search)

    def test_validated_plan_creates_no_output(self):
        self.assertEqual(self.call(),self.plan['compiled_source_sha256'])
        self.assertFalse(self.output.exists())

    def test_refuses_overlap(self):
        with self.assertRaisesRegex(ValueError,'LONG-01 not complete'):self.call(ready=False)

    def test_refuses_changed_recipe_and_budget(self):
        for key,value in [('candidate_id','model-wrong'),('budget',{})]:
            with self.subTest(key=key):
                plan=deepcopy(self.plan);plan[key]=value
                with self.assertRaises(ValueError):self.call(plan)

    def test_refuses_changed_input_or_source(self):
        with self.assertRaisesRegex(ValueError,'Compiled source changed'):self.call(compiled={'a.py':b'changed'})
        self.search.write_text('changed')
        with self.assertRaisesRegex(ValueError,'Frozen artifact changed'):self.call()

    def test_refuses_existing_or_protected_output(self):
        self.output=self.root/'LONG'/'forbidden'
        with self.assertRaisesRegex(ValueError,'inside LONG'):self.call()
        self.output=self.root/'existing';self.output.mkdir()
        with self.assertRaises(FileExistsError):self.call()

    def test_refuses_unverified_baseline(self):
        self.baseline.write_text(json.dumps({'baseline_complete':False}))
        with self.assertRaisesRegex(ValueError,'BASE-01 closure'):self.call()


if __name__=='__main__':unittest.main()
