"""Cache reuse requires the entire fitting context and untampered origin."""
from pathlib import Path
from copy import deepcopy
import json
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tools'))
from research_execution_cache import ExecutionCache,cache_key


def context():
    return {'source_sha256':{'worker':'a'},'input_sha256':{'train':'b'},'spec':{'target':'y'},'task_sha256':'c',
        'recipe':{'engine':'lightgbm','params':{'seed':42},'feature_code':'','hypothesis':'explanation'},
        'split_rows_sha256':'d','threads':2,'full_fit':False,'fit_iterations':None,'python':'3.12','libraries':{'numpy':'1'}}


class CacheTests(unittest.TestCase):
    def test_every_fitting_context_change_misses_but_descriptive_hypothesis_does_not(self):
        base=context();key=cache_key(base)
        for field in base:
            changed=deepcopy(base)
            if field=='recipe':changed[field]['params']['seed']=43
            elif isinstance(changed[field],dict):changed[field]['changed']=True
            elif field=='threads':changed[field]=1
            elif field=='full_fit':changed[field]=True
            elif field=='fit_iterations':changed[field]=100
            else:changed[field]='changed'
            with self.subTest(field=field):self.assertNotEqual(key,cache_key(changed))
        changed=deepcopy(base);changed['recipe']['hypothesis']='same model, different prose'
        self.assertEqual(key,cache_key(changed))
        with self.assertRaises(ValueError):cache_key({'recipe':{}})

    def test_hit_has_explicit_origin_and_no_fit_and_tampering_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cache=ExecutionCache(root/'cache',root);c=context();origin=root/'cold';origin.mkdir()
            native={'status':'ok','metrics':{'rmse':1.},'output_dir':str(origin)}
            job={k:c[k] for k in ['spec','threads','full_fit','recipe']}
            (origin/'result.json').write_text(json.dumps(native));(origin/'job.json').write_text(json.dumps(job))
            (origin/'predictions.csv').write_text('row,value\n0,1\n')
            cache.store(c,native);calls=[]
            result=cache.execute(c,root/'hit',lambda:calls.append('fit'))
            self.assertEqual(calls,[]);self.assertTrue(result['cache_hit']);self.assertEqual(result['output_dir'],str(origin))
            self.assertTrue((root/'hit/cache_reuse.json').exists());self.assertFalse((root/'hit/job.json').exists())
            (origin/'predictions.csv').write_text('row,value\n0,2\n')
            with self.assertRaises(ValueError):cache.lookup(c)

    def test_failed_worker_and_mismatched_training_context_are_not_stored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cache=ExecutionCache(root/'cache',root);c=context()
            with self.assertRaises(ValueError):cache.store(c,{'status':'timeout'})
            origin=root/'bad';origin.mkdir();native={'status':'ok','metrics':{'rmse':1.},'output_dir':str(origin)}
            (origin/'result.json').write_text(json.dumps(native));(origin/'job.json').write_text(json.dumps(dict(spec=c['spec'],threads=8,full_fit=False)))
            with self.assertRaises(ValueError):cache.store(c,native)


if __name__=='__main__':unittest.main()
