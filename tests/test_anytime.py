"""Clock-controlled deadline/refit tests; no API calls or long sleeps."""
from pathlib import Path
from types import SimpleNamespace
from contextlib import ExitStack
from unittest.mock import patch
import hashlib,json,sys,tempfile,unittest
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from automl.search import anytime as a
from automl.search.policy import normalize


class AnytimeTests(unittest.TestCase):
    def spec(self,root,metric='macro_f1'):
        return {'root':str(root),'task_path':str(root/'task.md'),'paths':{'train':str(root/'inputs.csv')},
                'kind':'classification' if metric=='macro_f1' else 'regression','metric':metric,
                'greater_is_better':metric=='macro_f1','features':['x'],'target':'y','id':'id',
                'classes':['a','b'],'text_features':[]}

    def execute(self,mode='gain',step=1,attempts=20,metric='macro_f1',nested=False):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        (root/'task.md').write_text('fixture');(root/'inputs.csv').write_text('fixed input')
        spec=self.spec(root,metric);ticks=[0.];events=[];baseline_bytes=b'id,y\n0,a\n1,a\n'
        data=(spec,{},pd.DataFrame({'y':['a','b']}),pd.DataFrame({'id':[0,1]}),
              pd.DataFrame({'id':[0,1],'y':['a','a']}),'task',np.arange(2))
        args=SimpleNamespace(task=root/'task.md',run_name='anytime',time_budget=240,
            finalization_reserve=60,max_experiments=12,max_extended_experiments=attempts,
            offline=True,max_planner_calls=0,search_until_deadline=True,validation_strategy='auto')
        def record(recipe,value,folder):
            folder.mkdir(parents=True,exist_ok=True);(folder/'submission.csv').write_bytes(b'id,y\n0,b\n1,b\n')
            return {'status':'ok','recipe':recipe,'metrics':{metric:value},'fit_iterations':[[60,120],50] if nested else 100,
                    'submission':str(folder/'submission.csv'),'output_dir':str(folder),'wall_seconds':step}
        def baseline(initial,passed,output_root):
            self.assertFalse(initial.search_until_deadline);self.assertEqual(initial.max_experiments,12)
            ticks[0]=20.;br=root/'automl_runs'/initial.run_name;br.mkdir(parents=True)
            (br/'split.npz').write_bytes(b'search');(br/'confirmation_split.npz').write_bytes(b'confirmation')
            records=[record(normalize({'engine':'lightgbm','params':{'seed':i}}),
                    .6-i*.005 if metric=='macro_f1' else .6+i*.005,br/f'search-{i}') for i in range(12)]
            confirmations=[record(r['recipe'],r['metrics'][metric],br/f'confirm-{i}') for i,r in enumerate(records[:2])]
            (root/'submission.csv').write_bytes(baseline_bytes)
            return {'spec':spec,'experiments':records,'confirmations':[] if mode=='unconfirmed' else confirmations,
                    'selected_recipe':records[0]['recipe'],'ensemble':None,'llm_calls':[],
                    'split':{'fixture':True},'journal_path':str(br/'results.tsv'),
                    'final_fit_status':'timeout' if mode=='baseline_failed' else 'ok'}
        def worker(s,recipe,folder,split,timeout,full_fit=False,fit_iterations=None):
            self.assertEqual((root/'submission.csv').read_bytes(),baseline_bytes)
            events.append({'full_fit':full_fit,'time':ticks[0],'timeout':timeout,'split':Path(split).name,
                           'fit_iterations':fit_iterations})
            if mode=='exception':raise RuntimeError('fixture failure')
            ticks[0]+=min(step,timeout)
            if full_fit and mode=='refit_failed':return {'status':'timeout','recipe':recipe,'output_dir':str(folder)}
            if not full_fit and mode=='worker_failures':return {'status':'error','recipe':recipe,'output_dir':str(folder)}
            value=(.8 if metric=='macro_f1' else .4) if mode!='no_gain' else (.5 if metric=='macro_f1' else .7)
            if Path(split).name=='confirmation_split.npz' and mode=='one_cut_worse':value=.4
            r=record(recipe,value,folder)
            if Path(split).name=='confirmation_split.npz' and nested:r['fit_iterations']=[[80,100],70]
            return r
        def promote(pairs,champion,floor,spec,*rest):
            p=pairs[-1];return p if a.eligible(p['search'],p['confirmation'],champion,floor,spec) else champion
        with ExitStack() as stack:
            for name,value in [('solve_single',baseline),('run_worker',worker),('promote',promote),
                               ('source_files',lambda:[]),('constrain_deadline',lambda x:x)]:
                stack.enter_context(patch.object(a,name,side_effect=value))
            stack.enter_context(patch.object(a.time,'monotonic',side_effect=lambda:ticks[0]))
            if mode=='exception':
                with self.assertRaises(RuntimeError):a.solve_anytime(args,data)
                report=json.loads((root/'automl_runs/anytime/anytime_state.json').read_text())
            else:report=a.solve_anytime(args,data)
        return root,report,events,baseline_bytes

    def test_budget_reserves_half_for_baseline(self):
        self.assertEqual(a.baseline_budget(10800,1200),5400)

    def test_invalid_budget_is_rejected(self):
        for total,reserve in [(0,1200),(1200,1200),(10800,0),(float('nan'),1200),(10800,float('inf'))]:
            with self.subTest(total=total,reserve=reserve),self.assertRaises(ValueError):a.baseline_budget(total,reserve)

    def test_maximize_gate_requires_both_cuts(self):
        spec={'greater_is_better':True};floor={'search':.6,'confirmation':.6,'mean':.6}
        self.assertTrue(a.eligible(.7,.7,floor,floor,spec))
        self.assertFalse(a.eligible(.9,.5,floor,floor,spec))

    def test_minimize_gate_requires_both_cuts(self):
        spec={'greater_is_better':False};floor={'search':10.,'confirmation':10.,'mean':10.}
        self.assertTrue(a.eligible(9.,8.,floor,floor,spec))
        self.assertFalse(a.eligible(5.,11.,floor,floor,spec))

    def test_nonfinite_values_never_promote(self):
        for x in [float('nan'),float('inf')]:
            self.assertFalse(a.eligible(x,.9,{'mean':.5},{'search':.5,'confirmation':.5},{'greater_is_better':True}))

    def test_equal_mean_is_not_a_promotion(self):
        p={'mean':.6,'search':.6,'confirmation':.6}
        self.assertFalse(a.eligible(.6,.6,p,p,{'greater_is_better':True}))

    def test_fixed_blend_grid_unchanged(self):
        self.assertEqual(len(a.configurations(2)),5);self.assertEqual(len(a.configurations(3)),19)

    def test_continues_beyond_old_fourteen_trial_cap(self):
        _,r,_,_=self.execute();self.assertEqual(len(r['experiments']),32)
        self.assertEqual(r['anytime']['extended_attempts'],20)

    def test_successful_refit_exports_confirmed_gain(self):
        root,r,events,base=self.execute()
        self.assertTrue(events[-1]['full_fit']);self.assertEqual(r['exported_mean'],.8)
        self.assertNotEqual((root/'submission.csv').read_bytes(),base);self.assertTrue(r['integrity_ok'])

    def test_failed_refit_preserves_trained_baseline_and_honest_score(self):
        root,r,_,base=self.execute('refit_failed')
        self.assertEqual((root/'submission.csv').read_bytes(),base);self.assertEqual(r['exported_mean'],.6)
        self.assertEqual(r['best_observed_mean'],.8);self.assertEqual(r['final_fit_status'],'timeout')

    def test_no_gain_never_refits_or_overwrites_baseline(self):
        root,r,events,base=self.execute('no_gain')
        self.assertFalse(any(e['full_fit'] for e in events));self.assertEqual(r['exported_mean'],.6)
        self.assertEqual((root/'submission.csv').read_bytes(),base)

    def test_improvement_on_one_cut_does_not_replace_baseline(self):
        root,r,events,base=self.execute('one_cut_worse')
        self.assertFalse(any(e['full_fit'] for e in events));self.assertEqual(r['exported_mean'],.6)
        self.assertEqual((root/'submission.csv').read_bytes(),base)

    def test_reserve_stops_search_and_confirmation_before_final_phase(self):
        _,r,events,_=self.execute(step=25,attempts=1000)
        self.assertEqual(r['anytime']['stop_reason'],'search_deadline')
        self.assertTrue(all(e['time']<180 for e in events if not e['full_fit']))
        self.assertTrue(all(e['timeout']<=180-e['time'] for e in events if not e['full_fit']))
        self.assertGreaterEqual(events[-1]['time'],175)

    def test_confirmation_uses_original_second_split(self):
        _,_,events,_=self.execute()
        self.assertTrue(any(e['split']=='confirmation_split.npz' for e in events))

    def test_nested_iteration_tree_reaches_full_refit(self):
        _,_,events,_=self.execute(nested=True)
        self.assertEqual(events[-1]['fit_iterations'],[[70,110],60])

    def test_baseline_without_confirmation_does_not_launch_extension(self):
        _,r,events,_=self.execute('unconfirmed')
        self.assertEqual(events,[]);self.assertIn('baseline_not_confirmed',r['anytime']['stop_reason'])

    def test_failed_baseline_refit_does_not_launch_extension(self):
        _,r,events,_=self.execute('baseline_failed')
        self.assertEqual(events,[]);self.assertEqual(r['final_fit_status'],'timeout')

    def test_consecutive_failure_guard_preserves_baseline(self):
        root,r,events,base=self.execute('worker_failures')
        self.assertEqual(len(events),8);self.assertEqual(r['anytime']['stop_reason'],'consecutive_worker_failures')
        self.assertEqual((root/'submission.csv').read_bytes(),base)

    def test_exception_records_failure_without_losing_baseline(self):
        root,r,_,base=self.execute('exception')
        self.assertEqual(r['phase'],'failed');self.assertEqual((root/'submission.csv').read_bytes(),base)

    def test_regression_refit_promotes_lower_error(self):
        _,r,_,_=self.execute(metric='rmse');self.assertEqual(r['exported_mean'],.4)

    def blend_fixture(self):
        spec={'metric':'macro_f1','greater_is_better':True}
        def p(value,seed):
            record={'recipe':normalize({'engine':'lightgbm','params':{'seed':seed}}),
                    'metrics':{'macro_f1':value},'fit_iterations':[80,100]}
            return a.pair(record,record,spec)
        return spec,p(.6,0),[p(.7,1),p(.65,2)]

    def test_blend_materialization_failure_does_not_keep_hypothetical_metric(self):
        spec,floor,pairs=self.blend_fixture()
        with tempfile.TemporaryDirectory() as d,patch.object(a,'read_cache',return_value={}),\
                patch.object(a,'combine',return_value=({'macro_f1':.9},None,None,None)),\
                patch.object(a,'materialize',side_effect=OSError('fixture')):
            chosen=a.promote(pairs,floor,floor,spec,None,None,None,Path(d),1,a.time.monotonic()+60)
        self.assertEqual(chosen['mean'],.7);self.assertEqual(chosen['primary']['recipe']['engine'],'lightgbm')

    def test_materialized_blend_preserves_matching_nested_iterations(self):
        spec,floor,pairs=self.blend_fixture()
        def materialized(*args):
            return {'recipe':{'engine':'ensemble','params':{},'components':[p['primary']['recipe'] for p in pairs],
                              'weights':[.5,.5]},'metrics':{'macro_f1':.9},'fit_iterations':[[80,100],[80,100]]}
        with tempfile.TemporaryDirectory() as d,patch.object(a,'read_cache',return_value={}),\
                patch.object(a,'combine',return_value=({'macro_f1':.9},None,None,None)),\
                patch.object(a,'materialize',side_effect=materialized):
            chosen=a.promote(pairs,floor,floor,spec,None,None,None,Path(d),1,a.time.monotonic()+60)
        self.assertEqual(chosen['mean'],.9);self.assertEqual(chosen['fit_iterations'],[[80,100],[80,100]])

    def test_no_blend_work_is_started_at_search_cutoff(self):
        spec,floor,pairs=self.blend_fixture()
        with patch.object(a,'read_cache',side_effect=AssertionError('deadline')):
            chosen=a.promote(pairs,floor,floor,spec,None,None,None,Path('.'),1,a.time.monotonic())
        self.assertEqual(chosen['mean'],.7)

    def test_existing_third_family_rule_prevents_three_near_identical_views(self):
        spec,floor,pairs=self.blend_fixture()
        third=dict(pairs[1],mean=.64,primary=dict(pairs[1]['primary'],recipe=normalize({'engine':'lightgbm','params':{'seed':3}})))
        independent=dict(floor,mean=.63,primary=dict(floor['primary'],recipe=normalize({'engine':'xgboost','params':{'seed':4}})))
        chosen=a.shortlist(pairs+[third,independent],spec)
        self.assertEqual([p['primary']['recipe']['engine'] for p in chosen],['lightgbm','lightgbm','xgboost'])

    def test_two_different_leading_families_keep_third_ranked_pair(self):
        spec,floor,pairs=self.blend_fixture()
        second=dict(pairs[1],primary=dict(pairs[1]['primary'],recipe=normalize({'engine':'xgboost','params':{'seed':2}})))
        self.assertEqual(a.shortlist([pairs[0],second,floor],spec),[pairs[0],second,floor])


if __name__=='__main__':unittest.main(verbosity=2)
