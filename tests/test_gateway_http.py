"""Actual SDK/HTTP/CLI roundtrip against a local fake server, never real Qwen."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json,os,subprocess,sys,tempfile,threading,unittest,zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from build_submission import build_files


class GatewayHTTPTests(unittest.TestCase):
    def test_live_harness_rejects_nonfixture_credentials_for_local_mock(self):
        with tempfile.TemporaryDirectory() as directory:
            env=dict(os.environ,OPENAI_API_KEY='not-a-fixture-credential')
            result=subprocess.run([sys.executable,str(ROOT/'tools/live_smoke.py'),'--output',str(Path(directory)/'out'),
                '--archive','unused.zip','--endpoint','http://127.0.0.1:1/v1'],env=env,capture_output=True,text=True,timeout=20)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('fixed non-secret fixture credential',result.stderr)
            self.assertNotIn('not-a-fixture-credential',result.stdout+result.stderr)

    def test_sdk_semantic_planner_fit_export_through_local_mock_http(self):
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                length=int(self.headers['Content-Length']); request=json.loads(self.rfile.read(length))
                context=json.loads(request['messages'][1]['content'])
                if 'catalog' in context:
                    value={'files':{'train':'alpha.csv','test':'beta.csv','sample_submission':'gamma.csv','data_dictionary':'delta.csv'}}
                    purpose='file_roles'
                else:
                    value={'candidates':[{'engine':'lightgbm','hypothesis':'Local mock HTTP fixture, not an actual Qwen proposal',
                        'params':{'iterations':100,'num_leaves':15,'learning_rate':.08},'feature_code':''}]}
                    purpose='planner'
                requests.append({'purpose':purpose,'authorization_is_fixture':self.headers.get('Authorization')=='Bearer fixture-http-only'})
                body=json.dumps({'id':'fixture','object':'chat.completion','created':0,'model':'fixture',
                    'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(value)}}],
                    'usage':{'prompt_tokens':10,'completion_tokens':8,'total_tokens':18}}).encode()
                self.send_response(200); self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); archive=root/'fixture.zip'
            with zipfile.ZipFile(archive,'x') as packed:
                for name,data in build_files().items(): packed.writestr(name,data)
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ['KEY','TOKEN','AUTH','PROXY','PASSWORD','SECRET'])}
            env.update(OPENAI_API_KEY='fixture-http-only',NO_PROXY='127.0.0.1,localhost',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
            try:
                result=subprocess.run([sys.executable,str(ROOT/'tools/live_smoke.py'),'--archive',str(archive),
                    '--output',str(root/'out'),'--endpoint',f'http://127.0.0.1:{server.server_port}/v1',
                    '--model','fixture','--time-budget','180'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=150)
            finally: server.shutdown();server.server_close();thread.join(timeout=5)
            self.assertEqual(result.returncode,0,(result.stdout+result.stderr)[-5000:])
            value=json.loads((root/'out/live-summary.json').read_text())
            self.assertTrue(value['passed']);self.assertEqual(value['provider_scope'],'local_mock_http')
            self.assertFalse(value['semantic_live_ok']);self.assertFalse(value['planner_live_ok'])
            self.assertTrue(value['semantic_http_ok']);self.assertTrue(value['planner_http_ok'])
            self.assertEqual({r['purpose'] for r in requests},{'file_roles','planner'})
            self.assertTrue(all(r['authorization_is_fixture'] for r in requests))
            traces=list((root/'out/automl_runs').glob('run-budget-*/report.json'))
            ledger=json.loads(traces[0].read_text())
            self.assertEqual(ledger['status'],'completed');self.assertEqual(ledger['gateway_calls_started'],2)
            self.assertEqual(ledger['prompt_tokens_reported'],20);self.assertEqual(ledger['completion_tokens_reported'],16)


if __name__=='__main__': unittest.main(verbosity=2)
