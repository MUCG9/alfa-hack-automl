"""Verify transport settings and truthful failure metadata without live calls."""
from pathlib import Path
import os,sys,unittest
from types import SimpleNamespace
from unittest.mock import patch,MagicMock
import httpx
from openai import BadRequestError
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from automl.infrastructure.llm_gateway import _request_json,reasoning_settings

ENV={'OPENAI_API_KEY':'fixture-secret','OPENAI_BASE_URL':'https://fixture.invalid/v1'}

class ReasoningTests(unittest.TestCase):
    def test_mode_changes_only_requested_transport_and_reports_observation(self):
        for mode,expected in [('off',{'extra_body':{'reasoning':{'enabled':False}}}),
                              ('default',{}),('xhigh',{'reasoning_effort':'xhigh'})]:
            with self.subTest(mode=mode),patch.dict(os.environ,dict(ENV,AUTOML_REASONING_EFFORT=mode)),patch('openai.OpenAI') as factory:
                client=MagicMock();factory.return_value=client;client.with_options.return_value=client
                client.chat.completions.create.return_value=SimpleNamespace(model='fixture',usage=SimpleNamespace(model_dump=lambda:{'prompt_tokens':5,'completion_tokens':8,'completion_tokens_details':{'reasoning_tokens':3}}),choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content='{}'))])
                content,call=_request_json('system',{},timeout=10)
                request=client.chat.completions.create.call_args.kwargs
                self.assertEqual({k:v for k,v in request.items() if k in {'extra_body','reasoning_effort'}},expected)
                self.assertEqual(content,'{}');self.assertEqual(call['reasoning_tokens_reported'],3)
                self.assertEqual(call['reasoning_effort_requested'],mode)
                self.assertNotIn('fixture-secret',str(call))

    def test_rejected_maximum_does_not_silently_switch_to_default(self):
        with patch.dict(os.environ,dict(ENV,AUTOML_REASONING_EFFORT='xhigh')),patch('openai.OpenAI') as factory:
            client=MagicMock();factory.return_value=client;client.with_options.return_value=client
            response=httpx.Response(400,request=httpx.Request('POST','https://fixture.invalid/v1/chat/completions'))
            client.chat.completions.create.side_effect=BadRequestError('unsupported effort',response=response,body={})
            content,call=_request_json('system',{},timeout=10)
            self.assertIsNone(content);self.assertEqual(call['status'],'error')
            self.assertEqual(client.chat.completions.create.call_count,1)
            self.assertFalse(call['compatibility_retry']);self.assertEqual(call['reasoning_effort_requested'],'xhigh')

    def test_unknown_effort_is_rejected_before_transport(self):
        with patch.dict(os.environ,dict(ENV,AUTOML_REASONING_EFFORT='max')),patch('openai.OpenAI') as factory:
            content,call=_request_json('system',{})
            self.assertIsNone(content);self.assertEqual(call['exception_type'],'ValueError')
            factory.assert_not_called()

if __name__=='__main__':unittest.main(verbosity=2)
