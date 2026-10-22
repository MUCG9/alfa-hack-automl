"""Typed two-view contract, fitting isolation and genuine nested full refit."""
from copy import deepcopy
from pathlib import Path
import contextlib,io,json,sys,tempfile,unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'))
import numpy as np
import pandas as pd
from agent_core import discover
from automl.execution import worker
from automl.execution.feature_views import validate_feature_view,feature_view_components,validate_fit_iterations
from automl.search.policy import normalize,portfolio,signature,fallback
from automl.search.runner import median_iterations


def schema():
    return {'kind':'classification','metric':'macro_f1','text_features':[],
            'features':['measure','segment','channel','region','fourth'],
            'categorical_features':['fourth','region','channel','segment']}


def recipe():
    return normalize({'engine':'lightgbm','params':{'iterations':35,'min_iterations':10,
        'num_leaves':7,'class_weight_power':.5,'calibrate':True,
        'feature_views':'categorical_te_pair'}})


def fixture(root):
    n=360
    train=pd.DataFrame({'record':np.arange(n),'measure':np.arange(n,dtype=float),
        'segment':np.tile(['a','b','c'],120),'channel':np.tile(['q','r'],180),
        'answer':np.tile(['M','Z','A'],120)})
    test=train.iloc[:12].drop(columns='answer').copy();test['record']+=1000
    train.to_csv(root/'train.csv',index=False);test.to_csv(root/'test.csv',index=False)
    pd.DataFrame({'record':test.record,'answer':'A'}).to_csv(root/'sample_submission.csv',index=False)
    pd.DataFrame({'feature':train.columns,'role':['id','feature','feature','feature','target']}).to_csv(root/'data_dictionary.csv',index=False)
    path=root/'task.md'
    path.write_text('Classification. Target: answer. Metric: Macro F1. train.csv test.csv data_dictionary.csv sample_submission.csv')
    spec,*_=discover(path)
    np.savez(root/'split.npz',train=np.arange(288),validation=np.arange(288,360))
    return spec,train


def run(root,spec,selected,name,**extra):
    out=root/name;out.mkdir()
    with contextlib.redirect_stdout(io.StringIO()):
        worker.run(dict(spec=spec,recipe=selected,output_dir=str(out),
            split_path=str(root/'split.npz'),threads=1,**extra))
    return out,json.loads((out/'result.json').read_text())


class FeatureViewTests(unittest.TestCase):
    def test_schema_order_not_names_or_declaration_order_controls_pairs(self):
        spec=schema(); expected=[['segment','channel'],['segment','region'],['channel','region']]
        self.assertEqual(validate_feature_view(recipe(),spec),expected)
        rename={c:f'opaque_{i}' for i,c in enumerate(spec['features'])}
        changed=dict(spec,features=[rename[c] for c in spec['features']],
            categorical_features=[rename[c] for c in spec['categorical_features']])
        self.assertEqual(validate_feature_view(recipe(),changed),[[rename[c] for c in pair] for pair in expected])

    def test_static_eligibility_rejects_incompatible_tasks(self):
        for change in [{'kind':'regression'}, {'metric':'accuracy'}, {'text_features':['text']},
                       {'task_family':'pointwise_ranking'}, {'categorical_features':['segment']},
                       {'categorical_features':['missing','segment']}]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_feature_view(recipe(),dict(schema(),**change))

    def test_conflicting_treatments_fail_closed(self):
        for change in [{'target_encoding':False},{'target_encoding_smoothing':20},
                       {'history_asof':False},{'generic_features':'skew'},{'log_target':True},
                       {'calibrate':False},{'calibration_folds':3},{'pair_refinement':True},
                       {'multiclass_strategy':'ova'},{'feature_views':True}]:
            candidate=recipe();candidate['params'].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):normalize(candidate)
        for engine in ['xgboost','catboost','linear_text']:
            with self.subTest(engine=engine),self.assertRaises(ValueError):normalize(dict(recipe(),engine=engine))
        for change in [{'feature_code':'def transform(df): return df'},
                       {'data_policy':{'sampling':'under'}}]:
            with self.subTest(change=change),self.assertRaises(ValueError):normalize(dict(recipe(),**change))

    def test_components_are_independent_and_use_existing_fixed_encoder(self):
        original=recipe();before=deepcopy(original)
        first,second=feature_view_components(original,schema())
        self.assertNotIn('feature_views',first['params']);self.assertNotIn('target_encoding',first['params'])
        self.assertEqual(second['params']['target_encoding_smoothing'],20.)
        self.assertEqual(len(second['params']['target_encoding_groups']),3)
        second['params']['iterations']=999;second['params']['target_encoding_groups'][0][0]='changed'
        self.assertEqual(original,before);self.assertEqual(first['params']['iterations'],35)

    def test_one_candidate_preserves_old_order_and_regression_policy(self):
        spec=schema();old=portfolio(dict(spec,categorical_features=[]));new=portfolio(spec)
        self.assertEqual([r for r in new if 'feature_views' not in r['params']],old)
        self.assertEqual([i for i,r in enumerate(new) if 'feature_views' in r['params']],[2])
        for change in [{'metric':'accuracy'},{'text_features':['review']},{'kind':'regression','metric':'rmse'},
                       {'task_family':'pointwise_ranking'}]:
            actual=dict(spec,**change)
            self.assertEqual(portfolio(actual),portfolio(dict(actual,categorical_features=[])))

    def test_signature_and_fallback_preserve_typed_method(self):
        selected=recipe();plain=deepcopy(selected);plain['params'].pop('feature_views')
        self.assertNotEqual(signature(selected),signature(plain))
        for number in range(6,9):
            candidate=fallback(schema(),number,selected)
            self.assertEqual(candidate['params']['feature_views'],'categorical_te_pair')
            validate_feature_view(candidate,schema())

    def test_nested_iteration_tree_validation(self):
        selected=recipe();plain=feature_view_components(selected,schema())[0]
        combined={'engine':'ensemble','components':[selected,plain]}
        validate_fit_iterations(combined,[[31,37],43])
        for invalid in [[31,43],[[31],43],[[31,37,40],43],[[31,37]],[[31,True],43],[[31,3.5],43]]:
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):validate_fit_iterations(combined,invalid)

    def test_recursive_median_keeps_shapes_and_rejects_truncation(self):
        self.assertEqual(median_iterations([[40,60],80],[[60,100],100]),[[50,80],90])
        for first,second in [([40,50],[40]),([40,50],40),(40,[40,50])]:
            with self.subTest(first=first,second=second),self.assertRaises(ValueError):median_iterations(first,second)

    def test_real_two_view_average_and_outer_label_isolation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);spec,train=fixture(root);exports=[];factors=[]
            for number in range(2):
                out,record=run(root,spec,recipe(),str(number))
                self.assertEqual(len(record['fit_iterations']),2)
                self.assertEqual(record['feature_views']['weights'],[.5,.5])
                self.assertFalse(any(c.startswith('__te_') for c in record['components'][0]['feature_names']))
                self.assertTrue(any(c.startswith('__te_') for c in record['components'][1]['feature_names']))
                factors.append([c['class_factors'] for c in record['components']])
                with np.load(out/'test_probabilities.npz') as stored,np.load(out/'component-0/test_probabilities.npz') as a,np.load(out/'component-1/test_probabilities.npz') as b:
                    np.testing.assert_allclose(stored['probabilities'],.5*a['probabilities']+.5*b['probabilities'])
                    np.testing.assert_allclose(stored['probabilities'].sum(axis=1),1.)
                exports.append((out/'submission.csv').read_bytes())
                train.loc[288:,'answer']=np.tile(['A','M','Z'],24)
                train.to_csv(spec['paths']['train'],index=False)
            self.assertEqual(exports[0],exports[1]);self.assertEqual(factors[0],factors[1])

    def test_actual_global_blend_full_refit_retains_each_view_iterations(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);spec,_=fixture(root)
            selected=recipe();plain=feature_view_components(selected,spec)[0]
            combined={'engine':'ensemble','params':{},'components':[selected,plain],'weights':[.75,.25]}
            out,record=run(root,spec,combined,'nested',full_fit=True,fit_iterations=[[31,37],43])
            self.assertEqual(record['fit_iterations'],[[31,37],43])
            self.assertEqual(record['components'][0]['feature_views']['iteration_tree'],[31,37])
            children=record['components'][0]['components']
            self.assertTrue(all(c['early_stopping_source']=='full_refit' for c in children))
            self.assertEqual([c['fit_iterations'] for c in children],[31,37])
            result=pd.read_csv(out/'submission.csv')
            self.assertEqual(len(result),12);self.assertFalse(result.isna().any().any())
            self.assertEqual(result.record.tolist(),list(range(1000,1012)))

    def test_invalid_iteration_shape_fails_before_any_input_read(self):
        with self.assertRaisesRegex(ValueError,'exactly two'):
            worker.run({'spec':schema(),'recipe':recipe(),'fit_iterations':[31],
                        'split_path':'missing','output_dir':'missing','threads':1})


if __name__=='__main__':unittest.main(verbosity=2)
