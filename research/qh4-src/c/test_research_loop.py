"""Prepared synthetic time-driven contracts. No actual clocks/models/providers."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import research_loop as R


class Clock:
    def __init__(self):self.left=4800.;self.checks=0;self.failure=None
    def check(self):
        self.checks+=1
        if self.failure:raise self.failure
        if self.left<=0:raise RuntimeError('original_task_deadline')
    def remaining(self):self.check();return self.left
    def common_remaining(self):self.check();return self.left+900


def normalizer(candidate,prior):
    result=deepcopy(prior);result['hypothesis']=candidate['hypothesis'];result['engine']=candidate['engine']
    result.setdefault('params',{}).update(candidate['params'])
    if 'feature_code' in candidate:result['feature_code']=candidate['feature_code']
    return result


def signature(recipe):
    value=deepcopy(recipe);value.pop('hypothesis',None)
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def compiler(features,numeric,original):
    if any(not set(row['columns'])<=set(numeric) for row in features):raise ValueError('undeclared')
    return 'trusted_compiler_output:'+json.dumps(features,sort_keys=True)


def task():
    return dict(kind='regression',metric='rmse',greater_is_better=False,
        cuts=[dict(seed=42,sha256='a'*64),dict(seed=43,sha256='b'*64)],
        context_flag=False,selector_cache_flag=False,features=['x'],numeric_features=['x'],
        forbidden_columns=['target','ID'],strong_recipe=dict(engine='lightgbm',params={'v':0},feature_code=''))


def proposal(value=1):
    return dict(hypothesis='One measured parameter factor',discard_rule='Reject either cut loss',component_path=[],params={'v':value})


class ThreeHourResearchContracts(unittest.TestCase):
    def harness(self,provider=None,worker_override=None,*,gateway_seconds=60.,worker_seconds=1.):
        clock=Clock();calls=[];saved=[];gateway_calls=[]
        def gateway(prompt,context,timeout):
            gateway_calls.append((prompt,deepcopy(context),timeout))
            clock.left-=min(gateway_seconds,max(.1,timeout-1))
            if provider:return provider(len(gateway_calls))
            return json.dumps(proposal(min(len(gateway_calls),20))),dict(status='ok',attempts=1,usage_complete=True,
                usage={'prompt_tokens':11,'completion_tokens':7})
        def worker(recipe,cut,timeout,phase,fit_iterations=None):
            clock.left-=min(worker_seconds,max(.1,timeout-1));calls.append((deepcopy(recipe),cut['seed'],timeout,phase,fit_iterations))
            if worker_override:return worker_override(recipe,cut,phase,fit_iterations)
            return dict(status='ok',cleanup_confirmed=True,split_sha256=cut['sha256'],
                metrics={'rmse':10-recipe['params']['v']*.01},
                fit_iterations=deepcopy(fit_iterations) if phase=='full-refit' else (101 if cut['seed']==42 else 205),
                full_fit=phase=='full-refit',submission='owned/final.csv',recipe=deepcopy(recipe),
                hpo_fair_reserve_provenance=dict(schema='hpo-fair-reserve-worker-origin-v1',cleanup_confirmed=True,
                    coordinator_killed=None,primary_exception_type=None,prior_result_status='ok'),
                parent_callback_receipt=dict(path='synthetic-owned/worker-'+str(len(calls))+'/parent-result.json',
                    sha256=hashlib.sha256(str(len(calls)).encode()).hexdigest()))
        return clock,gateway,worker,calls,gateway_calls,saved

    def run_policy(self,provider=None,override=None,**kwargs):
        clock,gateway,worker,calls,gcalls,saved=self.harness(provider,override,**kwargs)
        result=R.run_task(task(),clock,gateway,worker,normalizer,signature,compiler,saved.append)
        return result,clock,calls,gcalls,saved

    def test_time_driven_rounds_exceed64_gateway_and_callback_counts(self):
        result,clock,calls,gcalls,saved=self.run_policy()
        self.assertGreater(len(gcalls),64);self.assertGreater(len(calls),64)
        self.assertEqual(result['stop_reason'],'original_task_time_admission_margin')
        self.assertLessEqual(clock.left,R.TASK_ADMISSION_MARGIN)
        self.assertGreater(clock.left,R.SEAL_RESERVE)
        self.assertEqual(result['gateway_calls'],len(gcalls));self.assertEqual(result['worker_calls_attempted'],len(calls))
        self.assertIsNone(result['actual_learner_fit_calls']);self.assertFalse(result['quality_qualified'])

    def test_cheap_initial_checkpoint_does_not_finish_or_refit_unchanged_incumbent_repeatedly(self):
        provider=lambda n:(json.dumps(proposal()),dict(status='ok',attempts=1,usage_complete=True))
        result,clock,calls,gcalls,saved=self.run_policy(provider)
        self.assertGreater(len(gcalls),64)
        full=[row for row in calls if row[3]=='full-refit']
        self.assertEqual([row[0]['params']['v'] for row in full],[0,1])
        self.assertEqual(result['selected_checkpoint'],2)
        self.assertTrue(any(row['status']=='duplicate' for row in result['records']))

    def test_late_valid_gain_can_finalize_with_less_than_old1560_reserve(self):
        provider=lambda n:(json.dumps(proposal(0 if n<25 else 1)),dict(status='ok',attempts=1,usage_complete=True))
        result,clock,calls,gcalls,saved=self.run_policy(provider,gateway_seconds=170.)
        late=result['checkpoints'][1]
        self.assertEqual(late['round'],25);self.assertEqual(late['status'],'completed')
        self.assertLess(late['confirmation_lease_seconds'],600)
        self.assertLess(late['refit_lease_seconds'],900)
        self.assertGreaterEqual(late['confirmation_lease_seconds'],5);self.assertGreaterEqual(late['refit_lease_seconds'],5)
        self.assertEqual(result['selected_recipe']['params']['v'],1)

    def test_selected_output_always_belongs_to_last_completed_checkpoint(self):
        clock,gateway,ordinary,calls,gcalls,saved=self.harness()
        def worker(recipe,cut,timeout,phase,fit_iterations=None):
            row=ordinary(recipe,cut,timeout,phase,fit_iterations)
            if recipe['params']['v']==20 and phase=='full-refit':
                row.update(status='timeout',metrics=None,hpo_fair_reserve_provenance=dict(
                    schema='hpo-fair-reserve-worker-origin-v1',cleanup_confirmed=True,
                    coordinator_killed='timeout',primary_exception_type=None,prior_result_status='timeout'))
            return row
        result=R.run_task(task(),clock,gateway,worker,normalizer,signature,compiler,saved.append)
        selected=result['checkpoints'][result['selected_checkpoint']-1]
        self.assertEqual(selected['status'],'completed');self.assertEqual(result['selected_recipe']['params']['v'],19)
        self.assertEqual(result['full_refit']['parent_callback_receipt'],selected['full_refit_ref'])
        self.assertTrue(any(row['status']=='unfinalized_timeout' and row['scores'] is None for row in result['checkpoints']))
        self.assertIsNone(result['first_failure'])

    def test_confirmed_pair_timeout_is_NULL_and_later_real_rounds_continue(self):
        clock,gateway,ordinary,calls,gcalls,saved=self.harness()
        def worker(recipe,cut,timeout,phase,fit_iterations=None):
            row=ordinary(recipe,cut,timeout,phase,fit_iterations)
            if recipe['params']['v']==1:row.update(status='timeout',metrics=None,
                hpo_fair_reserve_provenance=dict(schema='hpo-fair-reserve-worker-origin-v1',cleanup_confirmed=True,
                    coordinator_killed='timeout',primary_exception_type=None,prior_result_status='timeout'))
            return row
        result=R.run_task(task(),clock,gateway,worker,normalizer,signature,compiler,saved.append)
        self.assertIsNone(next(row for row in result['records'] if row['status']=='failed')['scores'])
        self.assertGreater(result['selected_recipe']['params']['v'],1);self.assertIsNone(result['first_failure'])

    def test_resource_origin_masked_by_final_timeout_remains_fatal(self):
        clock,gateway,ordinary,calls,gcalls,saved=self.harness()
        def worker(recipe,cut,timeout,phase,fit_iterations=None):
            row=ordinary(recipe,cut,timeout,phase,fit_iterations)
            if recipe['params']['v']==1:row.update(status='timeout',metrics=None,
                hpo_fair_reserve_provenance=dict(schema='hpo-fair-reserve-worker-origin-v1',cleanup_confirmed=True,
                    coordinator_killed='memory_limit',primary_exception_type=None,prior_result_status='memory_limit'))
            return row
        with self.assertRaises(R.ResearchStop):R.run_task(task(),clock,gateway,worker,normalizer,signature,compiler,saved.append)
        self.assertEqual(len(gcalls),1);self.assertEqual(saved[-1]['status'],'failed')
        self.assertFalse(saved[-1]['quality_qualified'])

    def test_cleanup_and_unknown_provenance_are_not_discarded_as_checkpoint_timeouts(self):
        for mutation in ({'cleanup_confirmed':False},{'hpo_fair_reserve_provenance':None}):
            clock,gateway,ordinary,calls,gcalls,saved=self.harness()
            def worker(recipe,cut,timeout,phase,fit_iterations=None):
                row=ordinary(recipe,cut,timeout,phase,fit_iterations);row.update(mutation);return row
            with self.subTest(mutation=mutation),self.assertRaises(R.ResearchStop):
                R.run_task(task(),clock,gateway,worker,normalizer,signature,compiler,saved.append)
            self.assertEqual(len(gcalls),0)

    def test_safety_ceiling_early_hit_is_INCOMPLETE_never_normal_success(self):
        clock,gateway,worker,calls,gcalls,saved=self.harness(gateway_seconds=1.)
        with patch.object(R,'GATEWAY_LIMIT',2),self.assertRaisesRegex(R.ResearchStop,'INCOMPLETE'):
            R.run_task(task(),clock,gateway,worker,normalizer,signature,compiler,saved.append)
        self.assertEqual(len(gcalls),2);self.assertGreater(clock.left,4000)
        self.assertEqual(saved[-1]['status'],'failed');self.assertFalse(saved[-1]['quality_qualified'])

    def test_provider_failure_and_unknown_attempts_are_fatal_with_truthful_counters(self):
        for usage in (dict(status='error',attempts=3,usage_complete=False),dict(status='ok',attempts=None,usage_complete=False)):
            clock,gateway,worker,calls,gcalls,saved=self.harness(lambda n:(None,usage))
            with self.subTest(usage=usage),self.assertRaises(R.ResearchStop):
                R.run_task(task(),clock,gateway,worker,normalizer,signature,compiler,saved.append)
            self.assertEqual(len(calls),4);self.assertEqual(len(gcalls),1)
            self.assertEqual(saved[-1]['http_attempts_reported'],3 if usage['attempts']==3 else 0)
            self.assertEqual(saved[-1]['http_attempts_complete'],usage['attempts']==3)

    def test_all_callback_and_HTTP_ledgers_remain_cumulative_across_checkpoints(self):
        result,clock,calls,gcalls,saved=self.run_policy()
        self.assertEqual(len(result['callback_ledger_refs']),len(calls))
        self.assertEqual(len({ref['path'] for ref in result['callback_ledger_refs']}),len(calls))
        self.assertEqual(result['http_attempts_reported'],len(gcalls));self.assertEqual(len(result['usage']),len(gcalls))
        self.assertEqual(len(result['records']),len(gcalls));self.assertGreater(len(result['checkpoints']),1)

    def test_recursive_median_uses_fresh_checkpoint_pair_only(self):
        result,clock,calls,gcalls,saved=self.run_policy()
        self.assertTrue(all(row[4] is None for row in calls if row[3]!='full-refit'))
        self.assertTrue(all(row[4]==153 for row in calls if row[3]=='full-refit'))
        self.assertEqual(result['full_refit']['fit_iterations'],153)
        for a,b in [([100],100),([100],[100,200]),(None,100),(True,100),(0,100)]:
            with self.subTest(a=a,b=b),self.assertRaises(R.ResearchStop):R.median_iterations(a,b)

    def test_same_original_task_windows_and_no_transfer(self):
        self.assertEqual(R.task_window(10.,10810.,310.,'regression'),5110.)
        self.assertEqual(R.task_window(10.,10810.,5110.,'classification'),9910.)
        self.assertEqual(300+4800+4800+600+300,10800)
        with self.assertRaises(R.ResearchStop):R.task_window(10.,10811.,310.,'regression')

    def test_leaf_DSL_and_raw_complete_recipe_guards_are_unchanged(self):
        leaf=task()['strong_recipe'];seed=dict(engine='ensemble',components=[leaf,deepcopy(leaf)],weights=[.75,.25],params={})
        before=deepcopy(seed);p=proposal(3);p['component_path']=[1]
        changed=R.mutate_recipe(p,seed,['x'],['x'],normalizer,compiler)
        self.assertEqual(seed,before);self.assertEqual(changed['components'][0],seed['components'][0]);self.assertEqual(changed['weights'],[.75,.25])
        for delta in [dict(feature_code='import os'),dict(component_path=[99]),dict(params={'threads':8}),dict(features=[],params={})]:
            p=proposal();p.update(delta)
            with self.subTest(delta=delta),self.assertRaises(R.ResearchStop):R.mutate_recipe(p,task()['strong_recipe'],['x'],['x'],normalizer,compiler)

    def test_regression_and_supported_class_guards_remain_strict(self):
        def rows(values,t):return [dict(status='ok',cleanup_confirmed=True,split_sha256=c['sha256'],metrics=dict(rmse=v)) for c,v in zip(t['cuts'],values)]
        t=task();baseline=rows([10,10],t)
        self.assertTrue(R.keep_candidate(rows([9,9],t),baseline,baseline,t))
        self.assertFalse(R.keep_candidate(rows([9,10],t),baseline,baseline,t))
        cls=dict(t,kind='classification',metric='macro_f1',greater_is_better=True,classes=['a','b','r'])
        cls['cuts']=[dict(c,independent_fitting_groups={'a':200,'b':100,'r':5},rarest_fitting_class='r') for c in t['cuts']]
        def cr(v):return [dict(status='ok',cleanup_confirmed=True,split_sha256=c['sha256'],metrics={'macro_f1':sum(v)/3,'per_class_f1':dict(zip(cls['classes'],v))}) for c in cls['cuts']]
        base=cr([.5,.5,.2]);self.assertTrue(R.keep_candidate(cr([.52,.52,.3]),base,base,cls))
        self.assertFalse(R.keep_candidate(cr([.47,.55,.4]),base,base,cls));self.assertFalse(R.keep_candidate(cr([.5,.5,.8]),base,base,cls))

    def test_actual_report_byte_bound_stops_instead_of_claiming_truncated_evidence(self):
        clock,gateway,worker,calls,gcalls,saved=self.harness()
        with patch.object(R,'REPORT_BYTES_LIMIT',4096),self.assertRaisesRegex(R.ResearchStop,'JSON_bound_INCOMPLETE'):
            R.run_task(task(),clock,gateway,worker,normalizer,signature,compiler,saved.append)
        self.assertEqual(saved[-1]['status'],'failed');self.assertIsNone(saved[-1]['actual_learner_fit_calls'])

    def test_cheap_checkpoints_do_not_claim_4800_or_10800_elapsed(self):
        result,clock,calls,gcalls,saved=self.run_policy()
        self.assertEqual(result['elapsed_task_seconds_at_stop'],4800-clock.left)
        self.assertGreaterEqual(result['elapsed_task_seconds_at_stop'],4800-R.TASK_ADMISSION_MARGIN)
        self.assertLess(result['elapsed_task_seconds_at_stop'],4800)
        self.assertGreater(result['remaining_task_seconds_at_stop'],0)
        self.assertNotIn('measured_three_hours',result)

    def test_oversized_failure_state_is_bounded_with_exact_counts_refs_and_hashes(self):
        refs=[dict(path='owned/worker-1/parent-result.json',sha256='a'*64)]
        state=dict(kind='regression',first_failure=dict(type='ResearchStop',code='actual_report_JSON_bound_INCOMPLETE'),
            secondary_failures=[],callback_ledger_refs=refs,records=[{'payload':'x'*20000}],checkpoints=[],usage=[],
            gateway_calls=7,http_attempts_reported=8,http_attempts_complete=True,usage_complete=True,
            worker_calls_attempted=1,worker_calls_succeeded=1,executed_Qwen_candidates=1)
        before=deepcopy(state)
        with patch.object(R,'REPORT_BYTES_LIMIT',4096):summary=R.failure_summary(state)
        self.assertEqual(state,before);self.assertLessEqual(len(json.dumps(summary,ensure_ascii=False,indent=2).encode()),4096)
        self.assertEqual(summary['status'],'failed');self.assertFalse(summary['complete_ledger_qualification'])
        self.assertEqual(summary['first_failure'],state['first_failure']);self.assertEqual(summary['callback_ledger_refs'],refs)
        self.assertEqual(summary['gateway_calls'],7);self.assertEqual(summary['http_attempts_reported'],8)
        self.assertEqual(len(summary['ledger_descriptor']['sha256']),64)
        self.assertEqual(len(summary['records_descriptor']['sha256']),64)
        self.assertIsNone(summary['metrics']);self.assertIsNone(summary['quality_metric'])
        # If refs alone overflow, preserve their exact hash/count and raw-file
        # recovery scope rather than writing another oversized negative state.
        state['callback_ledger_refs']=[dict(path='owned/'+str(i)+'x'*200,sha256='a'*64) for i in range(100)]
        with patch.object(R,'REPORT_BYTES_LIMIT',4096):bounded=R.failure_summary(state)
        self.assertIsNone(bounded['callback_ledger_refs']);self.assertFalse(bounded['callback_ledger_refs_inlined'])
        self.assertEqual(bounded['ledger_descriptor']['count'],100)
        self.assertLessEqual(len(json.dumps(bounded,ensure_ascii=False,indent=2).encode()),4096)

    def test_failure_persist_secondary_is_saved_without_replacing_original_primary(self):
        clock,gateway,worker,calls,gcalls,saved=self.harness();primary=R.ResearchStop('synthetic_primary')
        def broken_worker(*args,**kwargs):raise primary
        writes=[0]
        def persist(row):
            writes[0]+=1
            if writes[0]==1:raise PermissionError('synthetic_secondary')
            saved.append(deepcopy(row))
        with self.assertRaises(R.ResearchStop) as caught:
            R.run_task(task(),clock,gateway,broken_worker,normalizer,signature,compiler,persist)
        self.assertIs(caught.exception,primary);self.assertEqual(writes[0],2)
        self.assertEqual(saved[-1]['schema'],'qwen-iterative-task-failure-summary-v1')
        self.assertEqual(saved[-1]['first_failure']['code'],'synthetic_primary')
        self.assertEqual(saved[-1]['secondary_failures'][0]['type'],'PermissionError')
        self.assertEqual(saved[-1]['worker_calls_attempted'],1)
        self.assertFalse(saved[-1]['quality_qualified']);self.assertIsNone(saved[-1]['quality_metric'])


class FullProviderAdmissionContracts(unittest.TestCase):
    harness=ThreeHourResearchContracts.harness

    def test_exact270_stops_and_above270_admits_only_full180_with_completed_checkpoint(self):
        self.assertEqual(R.TASK_ADMISSION_MARGIN,180+10+60+10+2*5)
        for tail,expected in ((270.,1),(270.001,2)):
            clock,gateway,ordinary,calls,gcalls,saved=self.harness()
            def worker(recipe,cut,timeout,phase,fit_iterations=None):
                row=ordinary(recipe,cut,timeout,phase,fit_iterations)
                if recipe['params']['v']==1 and phase=='full-refit':clock.left=tail
                return row
            with self.subTest(tail=tail):
                result=R.run_task(task(),clock,gateway,worker,normalizer,signature,compiler,saved.append)
                self.assertEqual(len(gcalls),expected)
                self.assertTrue(all(call[2]==180 for call in gcalls))
                self.assertEqual(result['gateway_calls'],len(gcalls))
                self.assertEqual(result['stop_reason'],'original_task_time_admission_margin')
                self.assertLessEqual(clock.left,270.)
                self.assertEqual(result['checkpoints'][result['selected_checkpoint']-1]['status'],'completed')
                if tail==270.:self.assertEqual(result['selected_checkpoint'],2)

    def test_context_persistence_cost_recheck_creates_no_extra_gateway_obligation(self):
        clock,gateway,worker,calls,gcalls,saved=self.harness();late_saves=[0]
        def persist(row):
            saved.append(deepcopy(row))
            if len(row.get('records',[]))==1 and row['gateway_calls']==1:
                late_saves[0]+=1
                if late_saves[0]==1:clock.left=271.
                elif late_saves[0]==2:clock.left=270.
        result=R.run_task(task(),clock,gateway,worker,normalizer,signature,compiler,persist)
        self.assertGreaterEqual(late_saves[0],2)
        self.assertEqual(len(gcalls),1);self.assertEqual(result['gateway_calls'],1)
        self.assertEqual(len(result['usage']),1);self.assertEqual(len(result['records']),1)
        self.assertEqual(result['http_attempts_reported'],1)
        self.assertTrue(result['http_attempts_complete']);self.assertTrue(result['usage_complete'])
        self.assertEqual(result['selected_checkpoint'],2)
        self.assertEqual(result['remaining_task_seconds_at_stop'],270.)

    def test_raised_unrecorded_gateway_is_fatal_with_prior_attempts_lower_bound(self):
        clock,ordinary,worker,calls,gcalls,saved=self.harness();primary=RuntimeError('synthetic_owned_provider_failure')
        def gateway(prompt,context,timeout):
            answer=ordinary(prompt,context,timeout)
            if len(gcalls)==2:raise primary
            return answer
        with self.assertRaises(RuntimeError) as caught:
            R.run_task(task(),clock,gateway,worker,normalizer,signature,compiler,saved.append)
        self.assertIs(caught.exception,primary)
        summary=saved[-1]
        self.assertEqual(summary['gateway_calls'],2);self.assertEqual(summary['http_attempts_reported'],1)
        self.assertFalse(summary['http_attempts_complete']);self.assertFalse(summary['usage_complete'])
        self.assertTrue(summary['http_attempts_reported_is_lower_bound'])
        self.assertEqual(summary['unrecorded_gateway_outcomes'],1)
        self.assertEqual(summary['status'],'failed');self.assertFalse(summary['complete_ledger_qualification'])
        self.assertIsNone(summary['metrics']);self.assertEqual(summary['last_completed_checkpoint_index'],2)
        self.assertEqual(len([row for row in calls if row[3]=='full-refit']),2)


if __name__=='__main__':unittest.main(verbosity=2)
