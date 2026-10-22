"""Mock gateway and clock coverage; no live API calls or private credentials."""
from pathlib import Path
import json,os,sys,tempfile,unittest
from unittest.mock import patch
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tests'))
from automl.infrastructure.run_budget import RunBudget,current_budget,constrain_deadline,budget_metadata
from automl.infrastructure import llm_gateway as gateway
from automl.search import runner
import test_semantic_inputs as semantic_tests

ENV={'OPENAI_API_KEY':'fixture-only-not-a-real-credential','OPENAI_BASE_URL':'https://fixture.invalid/v1'}


class RunBudgetTests(unittest.TestCase):
    def test_invalid_limits_are_rejected(self):
        for seconds,calls in [(0,1),(-1,1),(float('inf'),1),(float('nan'),1),(10,-1),(10,17),(10,True)]:
            with self.assertRaises(ValueError): RunBudget(seconds,calls,Path('.'))

    def test_context_restores_previous_budget_even_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            with RunBudget(100,2,directory) as outer:
                with self.assertRaises(ValueError):
                    with RunBudget(10,1,directory) as inner:
                        self.assertIs(current_budget(),inner)
                        raise ValueError('fixture')
                self.assertIs(current_budget(),outer)
                saved=json.loads(inner.trace.read_text())
                self.assertEqual(saved['status'],'failed'); self.assertEqual(saved['exception_type'],'ValueError')
            self.assertIsNone(current_budget())

    def test_deadline_is_shared_without_resetting_local_phases(self):
        with tempfile.TemporaryDirectory() as directory:
            ticks=[100.]
            with RunBudget(20,2,directory,clock=lambda:ticks[0]) as budget:
                self.assertEqual(constrain_deadline(200),120)
                ticks[0]=115
                self.assertEqual(budget.remaining(),5)
                self.assertEqual(constrain_deadline(118),118)
                ticks[0]=130; self.assertEqual(budget.remaining(),0)

    def test_gateway_call_cap_blocks_network_not_just_planner_counter(self):
        with tempfile.TemporaryDirectory() as directory:
            with (RunBudget(100,1,directory) as budget,patch.dict(os.environ,ENV),
                  patch.object(gateway,'_request_json',return_value=('{}',{'status':'ok','attempts':1,'usage_complete':True})) as request):
                self.assertEqual(gateway.request_json('fixture',{},purpose='file_roles')[1]['status'],'ok')
                self.assertEqual(gateway.request_json('fixture',{},purpose='planner')[1]['status'],'run_call_limit')
                self.assertEqual(request.call_count,1); self.assertEqual(budget.calls_started,1)
                self.assertEqual([e['purpose'] for e in budget.events],['file_roles','planner'])

    def test_zero_global_calls_never_reaches_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            with (RunBudget(100,0,directory),patch.dict(os.environ,ENV),
                  patch.object(gateway,'_request_json',side_effect=AssertionError('network forbidden')) as request):
                content,call=gateway.request_json('fixture',{})
            self.assertIsNone(content);self.assertEqual(call['status'],'run_call_limit');self.assertEqual(request.call_count,0)

    def test_gateway_timeout_is_clamped_to_remaining_wall_time(self):
        with tempfile.TemporaryDirectory() as directory:
            ticks=[0.]
            with (RunBudget(20,2,directory,clock=lambda:ticks[0]) as budget,patch.dict(os.environ,ENV),
                  patch.object(gateway,'_request_json',return_value=('{}',{'status':'ok','attempts':1,'usage_complete':True})) as request):
                ticks[0]=13; gateway.request_json('fixture',{},timeout=300)
                self.assertEqual(request.call_args.args[3],7)
                ticks[0]=16; content,call=gateway.request_json('fixture',{},timeout=300)
                self.assertIsNone(content);self.assertEqual(call['status'],'run_deadline_exhausted')
                self.assertEqual(request.call_count,1);self.assertEqual(budget.calls_started,1)

    def test_unconfigured_gateway_does_not_spend_a_network_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            with RunBudget(100,1,directory) as budget,patch.dict(os.environ,{},clear=True):
                self.assertEqual(gateway.request_json('fixture',{})[1]['status'],'unconfigured')
                self.assertEqual(budget.calls_started,0);self.assertTrue(budget.snapshot()['usage_complete'])

    def test_usage_aliases_do_not_double_count_and_errors_are_not_logged(self):
        with tempfile.TemporaryDirectory() as directory:
            with RunBudget(100,2,directory) as budget:
                budget.authorize(20,'planner')
                budget.record({'status':'ok','attempts':1,'usage_complete':True,
                    'usage':{'prompt_tokens':10,'input_tokens':999,'completion_tokens':3},
                    'error_message':'credential-or-private-row-must-not-be-copied'},'planner',reserved=True)
                value=budget.snapshot()
                self.assertEqual(value['prompt_tokens_reported'],10);self.assertEqual(value['completion_tokens_reported'],3)
                self.assertNotIn('credential-or-private-row',json.dumps(value));self.assertTrue(value['usage_complete'])

    def test_retry_usage_and_unreported_reserved_call_are_not_called_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            with RunBudget(100,2,directory) as budget:
                budget.authorize(20,'planner')
                self.assertFalse(budget.snapshot()['usage_complete'])
                budget.record({'status':'ok','attempts':3,'usage_complete':False,'usage':{'input_tokens':10,'output_tokens':2}},'planner',reserved=True)
                self.assertFalse(budget.snapshot()['usage_complete']);self.assertEqual(budget.snapshot()['http_attempts_reported'],3)

    def test_interruption_trace_is_final_and_does_not_swallow_system_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            budget=RunBudget(100,1,directory)
            with self.assertRaises(SystemExit):
                with budget:
                    self.assertEqual(json.loads(budget.trace.read_text())['status'],'running')
                    raise SystemExit(143)
            self.assertEqual(json.loads(budget.trace.read_text())['status'],'interrupted')
            self.assertIsNone(current_budget())

    def test_cli_budget_starts_before_input_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            path,_=semantic_tests.SemanticInputTests().fixture(Path(directory))
            ticks=[0.]; actual_load=runner.load_inputs; observed=[]
            def loader(*args,**kwargs):
                ticks[0]+=11
                return actual_load(*args,**dict(kwargs,allow_llm=False))
            for source,dest in zip(['alpha.csv','beta.csv','gamma.csv','delta.csv'],['train.csv','test.csv','sample_submission.csv','data_dictionary.csv']):
                (path.parent/source).rename(path.parent/dest)
            def solver(*args,**kwargs):
                observed.append(current_budget().remaining());return budget_metadata()
            with (patch('automl.infrastructure.run_budget.time.monotonic',side_effect=lambda:ticks[0]),
                  patch.object(runner,'load_inputs',side_effect=loader),patch.object(runner,'solve_single',side_effect=solver),
                  patch.object(sys,'argv',['solution.py',str(path),'--offline','--time-budget','10'])):
                result=runner._main()
            self.assertEqual(observed,[0]);self.assertEqual(json.loads(Path(result['run_budget_trace']).read_text())['elapsed_seconds'],11)

    def test_semantic_and_multiple_targets_share_exactly_one_gateway_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            path,response=semantic_tests.SemanticInputTests().fixture(Path(directory),multi=True)
            outcomes=[]
            def solver(*args,**kwargs):
                outcomes.append(gateway.request_json('fixture',{},purpose='planner')[1]['status'])
                return {'best_validation':None,'final_fit_status':'fallback_or_search_checkpoint',**budget_metadata()}
            def transport(system,context,*args):
                return json.dumps(response) if 'catalog' in context else '{}',{'status':'ok','attempts':1,'usage_complete':True,'usage':{'prompt_tokens':2}}
            with (patch.dict(os.environ,ENV),patch.object(gateway,'_request_json',side_effect=transport) as network,
                  patch.object(runner,'solve_single',side_effect=solver),
                  patch.object(sys,'argv',['solution.py',str(path),'--time-budget','400','--max-llm-calls','2'])):
                result=runner._main()
            self.assertEqual(outcomes,['ok','run_call_limit']);self.assertEqual(network.call_count,2)
            ledger=json.loads(Path(result['run_budget_trace']).read_text())
            self.assertEqual(ledger['gateway_calls_started'],2);self.assertEqual(ledger['prompt_tokens_reported'],4)
            self.assertEqual(ledger['status'],'completed');self.assertTrue(result['integrity_ok'])

    def test_client_setup_cannot_extend_the_global_transport_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            ticks=[0.]
            with (RunBudget(5,1,directory,clock=lambda:ticks[0]),patch.dict(os.environ,ENV),
                  patch('openai.OpenAI') as factory,
                  patch('automl.infrastructure.llm_gateway.time.monotonic',side_effect=lambda:ticks[0])):
                client=factory.return_value
                def setup(*args,**kwargs): ticks[0]=6;return client
                factory.side_effect=setup
                content,call=gateway.request_json('fixture',{},timeout=300)
                self.assertIsNone(content);self.assertEqual(call['attempts'],0)
                self.assertEqual(call['exception_type'],'TimeoutError')
                client.with_options.return_value.chat.completions.create.assert_not_called()

    def test_missing_usage_is_not_reported_as_known_zero_cost(self):
        with tempfile.TemporaryDirectory() as directory:
            response=SimpleNamespace(usage=None,choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content='{}'))])
            with RunBudget(100,1,directory) as budget,patch.dict(os.environ,ENV),patch('openai.OpenAI') as factory:
                factory.return_value.with_options.return_value.chat.completions.create.return_value=response
                content,call=gateway.request_json('fixture',{})
                self.assertEqual(content,'{}');self.assertEqual(call['status'],'ok')
                self.assertFalse(call['usage_complete']);self.assertFalse(budget.snapshot()['usage_complete'])


if __name__=='__main__': unittest.main(verbosity=2)
