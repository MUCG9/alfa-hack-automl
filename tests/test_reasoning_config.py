"""Actual local HTTP transport checks for explicit thinking and no silent downgrade."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
import sys
import threading
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tools'))
from automl.infrastructure.llm_gateway import request_json,reasoning_options
from research_llm_config import configure,MAX_OUTPUT,CALL_TIMEOUT


class ReasoningTests(unittest.TestCase):
    def test_research_profile_is_xhigh_with_a_real_final_output_reserve(self):
        private={'OPENAI_API_KEY':'fixture-only','OPENAI_BASE_URL':'https://changellenge.up.railway.app/v1','OPENAI_MODEL':'fixture'}
        with patch.dict(os.environ,{},clear=True),patch('dotenv.dotenv_values',return_value=private):
            config=configure();self.assertEqual(os.environ['AUTOML_REASONING_EFFORT'],'xhigh')
            self.assertFalse(config['automatic_effort_downgrade']);self.assertEqual(MAX_OUTPUT,32768);self.assertEqual(CALL_TIMEOUT,300)
        with patch.dict(os.environ,{'AUTOML_REASONING_EFFORT':'ultra'},clear=True):
            with self.assertRaises(ValueError):reasoning_options()

    def transport(self,effort,error_first=False):
        captured=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                data=json.loads(self.rfile.read(int(self.headers['Content-Length'])));captured.append(data)
                if error_first and len(captured)==1:
                    code=400;payload={'error':{'message':'unsupported reasoning fixture','type':'invalid_request_error','code':'fixture'}}
                else:
                    code=200;payload={'id':'fixture','object':'chat.completion','created':0,'model':'fixture',
                        'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':'{}','reasoning_content':'PRIVATE_REASONING_MUST_NOT_BE_RETURNED'}}],
                        'usage':{'prompt_tokens':10,'completion_tokens':20,'total_tokens':30,'completion_tokens_details':{'reasoning_tokens':12}}}
                body=json.dumps(payload).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        env={'OPENAI_API_KEY':'fixture-only','OPENAI_BASE_URL':f'http://127.0.0.1:{server.server_port}/v1','OPENAI_MODEL':'fixture','NO_PROXY':'127.0.0.1,localhost'}
        if effort is not None:env['AUTOML_REASONING_EFFORT']=effort
        try:
            with patch.dict(os.environ,env,clear=True):content,call=request_json('return json',{},max_output=32768,timeout=15)
        finally:server.shutdown();server.server_close();thread.join(timeout=3)
        return captured,content,call

    def test_xhigh_reaches_http_and_never_returns_internal_reasoning(self):
        captured,content,call=self.transport('xhigh')
        self.assertEqual(captured[0]['reasoning'],{'enabled':True,'effort':'xhigh','exclude':True})
        self.assertEqual(captured[0]['max_tokens'],32768);self.assertEqual(content,'{}')
        self.assertTrue(call['reasoning_requested']);self.assertEqual(call['reasoning_tokens_reported'],12)
        self.assertIsNone(call['server_effective_effort_echoed'])
        self.assertNotIn('PRIVATE_REASONING',json.dumps(call));self.assertEqual(call['attempts'],1)

    def test_explicit_effort_400_is_not_silently_retried_without_effort(self):
        captured,content,call=self.transport('xhigh',error_first=True)
        self.assertEqual(len(captured),1);self.assertIsNone(content);self.assertEqual(call['status'],'error')
        self.assertEqual(call['status_code'],400);self.assertFalse(call['compatibility_retry'])

    def test_unconfigured_effort_preserves_historical_off_compatibility_retry(self):
        captured,content,call=self.transport(None,error_first=True)
        self.assertEqual(len(captured),2);self.assertEqual(captured[0]['reasoning'],{'enabled':False})
        self.assertNotIn('reasoning',captured[1]);self.assertEqual(content,'{}');self.assertTrue(call['compatibility_retry'])


if __name__=='__main__':unittest.main()
