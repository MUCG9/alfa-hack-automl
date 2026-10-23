"""Mocked gateway tests: these are not evidence of a real Qwen HTTP session."""
from pathlib import Path
import json,sys,tempfile,unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from automl.task_understanding.api import discover
from automl.task_understanding.semantic_inputs import validated_roles
from automl.task_understanding import semantic_inputs
from automl.task_understanding import service
from automl.search import runner
from path_fixtures import escaping_csv_reference


class SemanticInputTests(unittest.TestCase):
    def fixture(self,root,multi=False):
        x=np.linspace(-1,1,100)
        train=pd.DataFrame({'key':range(100),'signal':x,'note':['private-value-never-send']*100,'answer':x*2+3})
        test=pd.DataFrame({'key':range(500,506),'signal':np.linspace(-1,1,6),'note':['private-value-never-send']*6})
        sample=pd.DataFrame({'key':test.key,'answer':0.})
        if multi: train['cost']=x*x+2; sample['cost']=0.
        dictionary=pd.DataFrame({'feature':train.columns,'role':['id' if c=='key' else 'target' if c in {'answer','cost'} else 'feature' for c in train]})
        for frame,name in zip([train,test,sample,dictionary],['alpha.csv','beta.csv','gamma.csv','delta.csv']): frame.to_csv(root/name,index=False)
        path=root/'task.md'; path.write_text('Regression. Metric RMSE. alpha.csv is fitting data, beta.csv requires predictions, gamma.csv is the expected answer format; delta.csv describes the schema.')
        response={'files':{'train':'alpha.csv','test':'beta.csv','sample_submission':'gamma.csv','data_dictionary':'delta.csv'},'reason':'Map documented roles and observed columns'}
        return path,response

    def mock_response(self,value): return json.dumps(value),{'status':'fixture_mock','usage':{'fixture_tokens':1}}

    def test_arbitrary_names_are_selected_without_sending_raw_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path,response=self.fixture(root)
            with patch('automl.task_understanding.semantic_inputs.request_json',return_value=self.mock_response(response)) as call:
                spec,*_=discover(path,allow_llm=True)
            self.assertEqual(call.call_count,1); self.assertEqual(spec['target'],'answer')
            context=call.call_args.args[1]
            self.assertNotIn('private-value-never-send',json.dumps(context))
            self.assertEqual({f['path'] for f in context['catalog']},{'alpha.csv','beta.csv','gamma.csv','delta.csv'})
            trace=spec['file_role_resolution']; self.assertTrue(trace['validated'])
            self.assertTrue(json.loads(Path(trace['trace']).read_text())['validated'])

    def test_library_and_offline_default_never_call_the_gateway(self):
        with tempfile.TemporaryDirectory() as directory:
            path,_=self.fixture(Path(directory))
            with patch('automl.task_understanding.semantic_inputs.request_json',side_effect=AssertionError('network forbidden')) as call:
                with self.assertRaises(ValueError): discover(path)
            self.assertEqual(call.call_count,0)

    def test_canonical_files_do_not_need_a_decorative_llm_call(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path,_=self.fixture(root)
            for source,dest in zip(['alpha.csv','beta.csv','gamma.csv','delta.csv'],['train.csv','test.csv','sample_submission.csv','data_dictionary.csv']):
                (root/source).rename(root/dest)
            with patch('automl.task_understanding.semantic_inputs.request_json',side_effect=AssertionError('not needed')) as call:
                spec,*_=discover(path,allow_llm=True)
            self.assertEqual(call.call_count,0); self.assertNotIn('file_role_resolution',spec)

    def test_paths_duplicates_and_unknown_response_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path,response=self.fixture(root)
            catalog={name:root/name for name in ['alpha.csv','beta.csv','gamma.csv','delta.csv']}
            for bad in [dict(response,command='touch outside'),{'files':dict(response['files'],train='../outside.csv')},
                        {'files':dict(response['files'],test='alpha.csv')},dict(response,reason={'execute':'no'})]:
                with self.assertRaises(ValueError): validated_roles(bad,catalog)

    def test_invalid_mapping_gets_only_one_bounded_feedback_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path,response=self.fixture(root)
            bad={'files':dict(response['files'],test='alpha.csv')}
            with patch('automl.task_understanding.semantic_inputs.request_json',side_effect=[self.mock_response(bad),self.mock_response(response)]) as call:
                spec,*_=discover(path,allow_llm=True)
            self.assertEqual(call.call_count,2)
            self.assertIn('previous_mapping_error',call.call_args_list[1].args[1])
            self.assertEqual(spec['file_role_resolution']['call_count'],2)
            with patch('automl.task_understanding.semantic_inputs.request_json',return_value=(None,{'status':'unconfigured'})) as unavailable:
                with self.assertRaises(ValueError): discover(path,allow_llm=True)
            self.assertEqual(unavailable.call_count,1)

    def test_security_rejection_is_not_sent_to_an_llm_for_a_workaround(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory); root=base/'task'; root.mkdir(); path,_=self.fixture(root)
            reference=escaping_csv_reference(base,root,'private\n1\n')
            path.write_text(path.read_text(encoding='utf-8')+'\nRequired input: `'+reference+'`.',encoding='utf-8')
            with patch('automl.task_understanding.semantic_inputs.request_json',side_effect=AssertionError('must not be called')) as call:
                with self.assertRaisesRegex(ValueError,'leaves task directory'): discover(path,allow_llm=True)
            self.assertEqual(call.call_count,0)

    def test_multitarget_dispatch_reuses_one_validated_file_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path,response=self.fixture(root,multi=True)
            reports=[]
            def solver(args,task_data,output_root):
                reports.append(task_data[0]['target'])
                return {'best_validation':None,'final_fit_status':'fallback_or_search_checkpoint'}
            with (patch('automl.task_understanding.semantic_inputs.request_json',return_value=self.mock_response(response)) as call,
                  patch.object(sys,'argv',['solution.py',str(path),'--time-budget','400']),patch.object(runner,'solve_single',side_effect=solver)):
                value=runner._main()
            self.assertEqual(call.call_count,1); self.assertEqual(reports,['answer','cost'])
            self.assertTrue(value['integrity_ok']); self.assertEqual(pd.read_csv(root/'submission.csv').columns.tolist(),['key','answer','cost'])

    def test_mocked_role_choice_then_real_single_target_fit_and_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); path,response=self.fixture(root)
            with (patch('automl.task_understanding.semantic_inputs.request_json',return_value=self.mock_response(response)),
                  patch.object(sys,'argv',['solution.py',str(path),'--time-budget','300','--max-experiments','1','--max-planner-calls','0'])):
                report=runner._main()
            self.assertEqual(report['final_fit_status'],'ok'); self.assertTrue(report['integrity_ok'])
            self.assertEqual(pd.read_csv(root/'submission.csv').columns.tolist(),['key','answer'])

    def test_serialized_metadata_limit_rejects_long_headers_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path,_=self.fixture(root)
            pd.DataFrame({('column'+str(i)+'x'*1000):[i] for i in range(100)}).to_csv(root/'extra.csv',index=False)
            with patch.object(semantic_inputs,'request_json',side_effect=AssertionError('oversize context must not reach gateway')) as call:
                with self.assertRaisesRegex(ValueError,'context bound'): discover(path,allow_llm=True)
            self.assertEqual(call.call_count,0)
            trace=list((root/'automl_runs').glob('task-contract-*/file-roles.json'))[0]
            self.assertEqual(json.loads(trace.read_text())['status'],'metadata_too_large')

    def test_retry_feedback_is_checked_against_the_same_byte_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path,response=self.fixture(root)
            def first(system,context,**kwargs):
                semantic_inputs.MAX_CONTEXT_BYTES=len(json.dumps(context,ensure_ascii=False,default=str).encode())+1
                return self.mock_response({'files':dict(response['files'],test='alpha.csv')})
            with (patch.object(semantic_inputs,'MAX_CONTEXT_BYTES',65536),
                  patch.object(semantic_inputs,'request_json',side_effect=first) as call):
                with self.assertRaisesRegex(ValueError,'context bound'): discover(path,allow_llm=True)
            self.assertEqual(call.call_count,1)

    def test_validated_semantic_tables_are_loaded_once_and_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path,response=self.fixture(root)
            with (patch.object(semantic_inputs,'request_json',return_value=self.mock_response(response)),
                  patch.object(service,'_read_tables',wraps=service._read_tables) as read):
                spec,*_=discover(path,allow_llm=True)
            self.assertEqual(spec['target'],'answer');self.assertEqual(read.call_count,1)

    def test_schema_invalid_but_catalog_valid_roles_get_one_feedback_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path,response=self.fixture(root)
            wrong={'files':dict(response['files'],train='beta.csv',test='alpha.csv')}
            with patch.object(semantic_inputs,'request_json',side_effect=[self.mock_response(wrong),self.mock_response(response)]) as call:
                spec,*_=discover(path,allow_llm=True)
            self.assertEqual(call.call_count,2)
            self.assertIn('row counts differ',call.call_args_list[1].args[1]['previous_mapping_error'])
            trace=json.loads(Path(spec['file_role_resolution']['trace']).read_text())
            self.assertEqual(trace['attempts'][0]['validation'],'rejected_table_contract');self.assertTrue(trace['validated'])

    def test_identifier_feedback_never_sends_private_row_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path,response=self.fixture(root)
            sample=pd.read_csv(root/'gamma.csv');sample.to_csv(root/'epsilon.csv',index=False)
            sample['key']=['private_identifier_value_'+str(i) for i in range(len(sample))];sample.to_csv(root/'gamma.csv',index=False)
            corrected={'files':dict(response['files'],sample_submission='epsilon.csv')}
            with patch.object(semantic_inputs,'request_json',side_effect=[self.mock_response(response),self.mock_response(corrected)]) as call:
                spec,*_=discover(path,allow_llm=True)
            self.assertEqual(call.call_count,2)
            for args in call.call_args_list: self.assertNotIn('private_identifier_value_',json.dumps(args.args[1]))
            self.assertEqual(Path(spec['paths']['sample_submission']).name,'epsilon.csv')

    def test_repeated_structural_failure_never_accepts_a_wrong_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path,response=self.fixture(root)
            wrong={'files':dict(response['files'],train='beta.csv',test='alpha.csv')}
            with patch.object(semantic_inputs,'request_json',return_value=self.mock_response(wrong)) as call:
                with self.assertRaisesRegex(ValueError,'No valid semantic input mapping'): discover(path,allow_llm=True)
            self.assertEqual(call.call_count,2)
            trace=json.loads(next((root/'automl_runs').glob('task-contract-*/file-roles.json')).read_text())
            self.assertFalse(trace['validated']);self.assertEqual(len(trace['attempts']),2)

    def test_unsupported_objective_is_terminal_not_a_mapping_workaround(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path,response=self.fixture(root)
            path.write_text(path.read_text().replace('Metric RMSE','Primary metric Cohen kappa'))
            with patch.object(semantic_inputs,'request_json',return_value=self.mock_response(response)) as call:
                with self.assertRaisesRegex(ValueError,'No supported objective'): discover(path,allow_llm=True)
            self.assertEqual(call.call_count,1)

    def test_table_read_errors_are_terminal_and_not_sent_as_feedback(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path,response=self.fixture(root)
            with (patch.object(semantic_inputs,'request_json',return_value=self.mock_response(response)) as call,
                  patch.object(service,'_read_tables',side_effect=ValueError('private_parser_row_value'))):
                with self.assertRaises(ValueError): discover(path,allow_llm=True)
            self.assertEqual(call.call_count,1)
            trace=json.loads(next((root/'automl_runs').glob('task-contract-*/file-roles.json')).read_text())
            self.assertEqual(trace['attempts'][0]['validation'],'terminal_table_error')
            self.assertNotIn('private_parser_row_value',json.dumps(trace))


if __name__=='__main__': unittest.main(verbosity=2)
