"""Pointwise ranking contracts and NDCG semantics against pinned sklearn 1.5.2."""
from pathlib import Path
import json,os,subprocess,sys,tempfile,unittest
import numpy as np
import pandas as pd
from sklearn.metrics import ndcg_score
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src')); sys.path.insert(0,str(ROOT/'tools'))
from build_submission import build_files
from automl.evaluation.ranking import NDCGByQuery
from automl.evaluation.api import evaluate,lgbm_metric,choose_validation,make_split,metric_context
from automl.task_understanding.api import discover
from automl.execution.api import combine


class RankingTests(unittest.TestCase):
    def task(self,root,no_id=False,exponential=False):
        rng=np.random.default_rng(57); x=rng.random(240)
        train=pd.DataFrame({'row_id':range(240),'request':np.repeat(np.arange(30),8),'signal':x,'relevance':np.floor(x*4)})
        test=pd.DataFrame({'row_id':range(500,518),'request':np.repeat(np.arange(100,103),6),'signal':rng.random(18)})
        sample=pd.DataFrame({'row_id':test.row_id,'score':0.})
        if no_id: sample=sample[['score']]
        else: sample=sample.iloc[::-1].reset_index(drop=True)
        for name,frame in [('train',train),('test',test),('sample_submission',sample)]: frame.to_csv(root/(name+'.csv'),index=False)
        pd.DataFrame({'feature':train.columns,'role':['id','query','feature','target']}).to_csv(root/'data_dictionary.csv',index=False)
        text='Ranking documents within each request. Primary metric: NDCG@3. Mean across queries. Return a numeric relevance score per document in sample order.'
        if exponential: text+=' Gain = 2**relevance - 1.'
        (root/'task.md').write_text(text+' Files: train.csv test.csv sample_submission.csv data_dictionary.csv')
        return discover(root/'task.md')

    def test_ties_and_topk_match_pinned_sklearn(self):
        y=np.array([3.,0.,1.,2.,0.,4.]); pred=np.array([1.,1.,.2,.4,.4,.1]); groups=np.repeat([0,1],3)
        for k in [None,1,2,10]:
            expected=np.mean([ndcg_score(y[i:i+3][None,:],pred[i:i+3][None,:],k=k) for i in [0,3]])
            self.assertAlmostEqual(NDCGByQuery(groups,k)(y,pred),expected,places=12)

    def test_random_interleaved_queries_match_reference(self):
        rng=np.random.default_rng(5); groups=np.tile(np.arange(7),11); y=rng.integers(0,5,len(groups)); pred=rng.integers(0,4,len(groups))
        expected=np.mean([ndcg_score(y[groups==g][None,:],pred[groups==g][None,:],k=4) for g in range(7)])
        self.assertAlmostEqual(NDCGByQuery(groups,4)(y,pred),expected,places=12)

    def test_exponential_gain_is_explicit_not_assumed(self):
        y=np.array([0.,1.,4.]); pred=np.array([3.,2.,1.]); group=[0,0,0]
        actual=NDCGByQuery(group,2,'exponential')(y,pred)
        self.assertAlmostEqual(actual,ndcg_score((2**y-1)[None,:],pred[None,:],k=2))
        self.assertNotAlmostEqual(actual,NDCGByQuery(group,2,'linear')(y,pred))

    def test_zero_relevance_and_single_document_queries(self):
        self.assertEqual(NDCGByQuery([0,0,1,2])([0,0,2,0],[1,1,5,3]),1/3)

    def test_invalid_groups_grades_and_cutoffs_are_rejected(self):
        for groups,k in [(None,None),([0,np.nan],None),([0,0],0),([0,0],1.5)]:
            with self.assertRaises(ValueError): NDCGByQuery(groups,k)
        for truth,pred in [([-1,1],[0,1]),([0,1],[float('inf'),1]),([0],[1])]:
            with self.assertRaises(ValueError): NDCGByQuery([0,0])(truth,pred)

    def test_cached_scorer_recomputes_when_truth_changes(self):
        scorer=NDCGByQuery([0,0],1); self.assertEqual(scorer([1,0],[2,1]),1)
        self.assertEqual(scorer([0,1],[2,1]),0)

    def test_query_mean_is_not_document_weighted_or_one_global_ranking(self):
        y=[1,0,0,0,0,3]; pred=[1,0,4,3,2,1]; groups=[0,0,1,1,1,1]
        expected=.5*(1+ndcg_score(np.array(y[2:])[None,:],np.array(pred[2:])[None,:],k=1))
        self.assertAlmostEqual(NDCGByQuery(groups,1)(y,pred),expected)

    def test_inner_callback_matches_outer_metric_and_log_inverse(self):
        y=np.array([0.,1.,2.,3.]); pred=np.array([.3,.8,2.2,2.9]); groups=[1,1,2,2]
        context={'groups':groups,'top_k':1,'gain':'linear'}
        spec={'kind':'regression','metric':'ndcg','greater_is_better':True}
        expected=evaluate(y,pred,'regression','ndcg',**context)['ndcg']
        for logged in [False,True]:
            callback=lgbm_metric(spec,logged,**context)
            self.assertAlmostEqual(callback(np.log1p(y) if logged else y,np.log1p(pred) if logged else pred)[1],expected)

    def test_discovery_uses_scorer_and_excludes_query_id(self):
        with tempfile.TemporaryDirectory() as directory:
            spec,_,train,_,_,_,hashes=self.task(Path(directory),exponential=True)
            self.assertEqual(spec['kind'],'regression'); self.assertIsNone(spec['classes'])
            self.assertEqual(spec['task_family'],'pointwise_ranking'); self.assertEqual(spec['ranking_k'],3)
            self.assertEqual(spec['ranking_gain'],'exponential'); self.assertEqual(spec['features'],['signal'])
            spec=choose_validation(spec,train); tr,va,_=make_split(spec,train,hashes)
            self.assertFalse(set(train.request.iloc[tr])&set(train.request.iloc[va]))
            with self.assertRaises(ValueError): choose_validation(spec,train,'legacy')

    def test_cached_blend_uses_query_context(self):
        spec={'kind':'regression','metric':'ndcg','classes':None}; y=np.array([3,0,1,0]); rows=np.arange(4)
        context={'groups':np.array([0,0,1,1]),'top_k':1,'gain':'linear'}
        caches=[{'rows':rows,'truth':y,'validation':np.array([1.,0.,1.,0.]),'test':np.array([1.,2.]),'metric_context':context},
                {'rows':rows,'truth':y,'validation':np.array([1.,1.,0.,1.]),'test':np.array([2.,1.]),'metric_context':context}]
        metrics,val,_,_=combine(spec,caches,[.5,.5])
        self.assertAlmostEqual(metrics['ndcg'],NDCGByQuery(context['groups'],1)(y,val))

    def cli(self,no_id=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); self.task(root,no_id=no_id)
            for name,data in build_files().items(): (root/name).write_bytes(data)
            env={k:v for k,v in os.environ.items() if not k.startswith('OPENAI_')}; env.update(AUTOML_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
            result=subprocess.run([sys.executable,'solution.py','task.md','--offline','--max-experiments','2','--time-budget','400'],cwd=root,env=env,capture_output=True,text=True,timeout=180)
            self.assertEqual(result.returncode,0,result.stderr[-2500:]+'\n'+result.stdout[-1500:])
            report=json.loads((root/'automl_runs/run-v2/report.json').read_text()); output=pd.read_csv(root/'submission.csv'); sample=pd.read_csv(root/'sample_submission.csv')
            self.assertEqual(report['final_fit_status'],'ok'); self.assertTrue(report['integrity_ok'])
            self.assertTrue(0<=report['best_validation']['ndcg']<=1.0000001)
            self.assertEqual(output.columns.tolist(),sample.columns.tolist()); self.assertTrue(np.isfinite(output.score).all())
            if not no_id: self.assertEqual(output.row_id.tolist(),sample.row_id.tolist())

    def test_flat_cli_ranking_scores_with_reordered_ids(self): self.cli()
    def test_flat_cli_ranking_scores_without_id(self): self.cli(no_id=True)

    def test_xgboost_inner_callback_receives_query_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); spec,_,train,*rest=self.task(root); spec=choose_validation(spec,train)
            hashes=rest[-1]; tr,va,_=make_split(spec,train,hashes)
            np.savez(root/'split.npz',train=tr,validation=va)
            for name,data in build_files().items(): (root/name).write_bytes(data)
            output=root/'worker'; output.mkdir()
            job={'spec':spec,'recipe':{'engine':'xgboost','params':{'iterations':60,'max_depth':4,'nested_stopping':True,'min_iterations':30}},
                 'output_dir':str(output),'split_path':str(root/'split.npz'),'threads':1,'full_fit':False}
            (root/'job.json').write_text(json.dumps(job))
            env={k:v for k,v in os.environ.items() if not k.startswith('OPENAI_')}; env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
            result=subprocess.run([sys.executable,'automl_worker.py',str(root/'job.json')],cwd=root,env=env,capture_output=True,text=True,timeout=120)
            self.assertEqual(result.returncode,0,result.stderr[-1500:])
            value=json.loads((output/'result.json').read_text())
            self.assertEqual(value['status'],'ok'); self.assertTrue(0<=value['metrics']['ndcg']<=1.0000001)


if __name__=='__main__': unittest.main(verbosity=2)
