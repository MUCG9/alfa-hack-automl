"""Prepared synthetic credential-boundary contract; no real credentials/API."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import os
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from provider_environment import provider_credentials


class ProviderEnvironmentContracts(unittest.TestCase):
    def test_technical_copy_provider_only_and_exact_function_restored_after_failure(self):
        mapping={key:'1' for key in ('AUTOML_THREADS','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}
        mapping['PATH']='synthetic-local-path';calls=[]
        def original(directory,model,manifest):
            calls.append((directory,model,manifest));self.assertIs(model,False);return mapping
        coor=SimpleNamespace(environment=original)
        synthetic={'OPENAI_API_KEY':'SYNTHETIC_NOT_A_CREDENTIAL','OPENAI_BASE_URL':'https://changellenge.up.railway.app/v1'}
        with patch.dict(os.environ,synthetic,clear=True):
            with self.assertRaisesRegex(RuntimeError,'synthetic-parent-failure'):
                with provider_credentials(coor):
                    result=coor.environment('synthetic-dir',False,{'requested_model':'synthetic-qwen-model','reasoning_effort':'off'})
                    self.assertEqual(result['OPENAI_API_KEY'],synthetic['OPENAI_API_KEY'])
                    self.assertEqual(result['OPENAI_MODEL'],'synthetic-qwen-model')
                    self.assertEqual(result['AUTOML_THREADS'],'1')
                    self.assertNotIn('OPENAI_API_KEY',mapping);self.assertIsNot(result,mapping)
                    with self.assertRaisesRegex(RuntimeError,'technical_environment'):coor.environment('unused',True,{})
                    raise RuntimeError('synthetic-parent-failure')
            self.assertIs(coor.environment,original)
            result=coor.environment('ordinary-technical',False,{})
            self.assertNotIn('OPENAI_API_KEY',result)
        self.assertEqual(len(calls),2)
        self.assertIs(coor.environment,original)


class GatewaySourceClosureContracts(unittest.TestCase):
    def synthetic(self):
        import task_entry as entry
        # Comparable long UTF8 Windows paths and the actual 963.py/2299 map census.
        root=Path('C:/Users/Исследователь/Documents/Codex/2026-10-22/'+'bounded-workspace-'*5+'/work/alfa-hack-automl')
        pins={str(root/rel):'a'*64 for rel in entry.GATEWAY_SOURCE_RELATIVE}
        pins.update({str(root/'historical/source-evidence'/('module-'+str(i)+'.py')):'b'*64 for i in range(958)})
        pins.update({str(root/'historical/metadata'/('receipt-'+str(i)+'.json')):'c'*64 for i in range(1336)})
        return entry,root,pins

    def test_long_UTF8_963_source_2299_parent_map_serializes_below_unchanged_request_bound_only_with_exact_five(self):
        import copy,json
        entry,root,pins=self.synthetic();before=copy.deepcopy(pins)
        projected=entry.gateway_source_projection(pins,root)
        self.assertEqual(len(pins),2299);self.assertEqual(len(projected),5);self.assertEqual(pins,before)
        request=dict(schema='qwen-three-hour-single-gateway-v1',call_number=1,clock={'synthetic':1},
            source_files={p:h for p,h in pins.items() if Path(p).suffix=='.py'},canonical_root=str(root),
            output=str(root/'gateway-1/result.json'),timeout=60,prompt='s'*1400,context={'feedback':'c'*5000})
        self.assertEqual(len(request['source_files']),963)
        self.assertGreater(len(json.dumps(request,indent=2,ensure_ascii=False).encode('utf-8')),131072)
        reduced=dict(request,source_files=projected)
        self.assertLessEqual(len(json.dumps(reduced,indent=2,ensure_ascii=False).encode('utf-8')),131072)
        self.assertEqual({k:v for k,v in request.items() if k!='source_files'},
            {k:v for k,v in reduced.items() if k!='source_files'})
        projected.pop(next(iter(projected)));self.assertEqual(pins,before)

    def test_missing_extra_or_changed_source_hash_never_reaches_gateway_import(self):
        import copy
        import gateway_child as child
        entry,root,pins=self.synthetic();sources=entry.gateway_source_projection(pins,root)
        self.assertEqual(tuple(entry.GATEWAY_SOURCE_RELATIVE),tuple(child.GATEWAY_SOURCE_RELATIVE))
        for path in sources:
            missing=dict(pins);missing.pop(path)
            with self.subTest(missing=Path(path).name),self.assertRaises(RuntimeError):entry.gateway_source_projection(missing,root)
        cfg=dict(canonical_root=str(root),source_files=dict(sources));checks=[]
        with patch.object(child,'sha',side_effect=lambda path:sources[str(path)]):
            self.assertEqual(child.verified_gateway_sources(cfg,lambda:checks.append(True)),sources)
            self.assertEqual(len(checks),5)
            for mode in ('missing','extra','changed','malformed'):
                bad=copy.deepcopy(cfg);key=next(iter(sources))
                if mode=='missing':bad['source_files'].pop(key)
                elif mode=='extra':bad['source_files'][str(root/'historical.py')]='d'*64
                elif mode=='changed':bad['source_files'][key]='d'*64
                else:bad['source_files'][key]='not-a-sha'
                with self.subTest(mode=mode),self.assertRaises(RuntimeError):child.verified_gateway_sources(bad,lambda:None)
        self.assertEqual(pins.keys()&sources.keys(),sources.keys())

    def test_installed_projection_is_pre_model_and_request_child_cap_and_full_parent_barriers_remain(self):
        import ast
        import task_entry as entry
        import gateway_child as child
        task_source=Path(entry.__file__).read_text('utf-8');tree=ast.parse(task_source)
        run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        call=next(n for n in ast.walk(run) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='gateway_source_projection')
        first_import=min(n.lineno for n in ast.walk(run) if isinstance(n,(ast.Import,ast.ImportFrom)))
        self.assertLess(call.lineno,first_import)
        self.assertIn('source_files=dict(gateway_code)',task_source)
        self.assertIn("for path,expected in pins.items():",task_source)
        self.assertIn("request.stat().st_size<=131072",task_source)
        child_source=Path(child.__file__).read_text('utf-8');child_tree=ast.parse(child_source)
        child_run=next(n for n in child_tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        verify=next(n for n in ast.walk(child_run) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='verified_gateway_sources')
        imports=[n.lineno for n in ast.walk(child_run) if isinstance(n,(ast.Import,ast.ImportFrom))]
        self.assertLess(verify.lineno,min(imports));self.assertIn('request.stat().st_size<=131072',child_source)
        self.assertIn('max_output=8192,timeout=timeout',child_source)


class GatewayOutcomeContracts(unittest.TestCase):
    def outcome(self,terminal,provider_status='ok',terminal_wall=None,sdk_usage=None,sdk_content='synthetic-safe-content',source_delay=0.):
        """Run the real child body with a synthetic SDK and original clock only."""
        import hashlib
        import json
        import tempfile
        from types import ModuleType
        import gateway_child as child
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name).resolve();request=root/'request.json';output=root/'result.json'
        clock=dict(start_unix=2000.,start_monotonic=1000.,absolute_deadline_unix=12800.,
            common_deadline_monotonic=11800.,task_deadline_monotonic=5800.,provider_deadline_monotonic=1180.)
        cfg=dict(schema='qwen-three-hour-single-gateway-v1',call_number=1,clock=clock,
            canonical_root=str(root),output=str(output),source_files={},timeout=180.,prompt='synthetic',context={})
        request.write_text(json.dumps(cfg),encoding='utf-8')
        digest=hashlib.sha256(request.read_bytes()).hexdigest();current={'mono':1000.,'wall':2000.};calls=[]
        budget=ModuleType('automl.infrastructure.run_budget');budget.current_budget=lambda:None
        gateway=ModuleType('automl.infrastructure.llm_gateway')
        def sdk(*args,**kwargs):
            calls.append(kwargs);current['mono']=terminal
            if terminal_wall is not None:current['wall']=terminal_wall
            return sdk_content,(sdk_usage if sdk_usage is not None else dict(status=provider_status,attempts=1,usage_complete=True,
                usage={'prompt_tokens':2,'completion_tokens':3},secret='MUST_NOT_PERSIST',reasoning='MUST_NOT_PERSIST'))
        gateway.request_json=sdk
        modules={'automl':ModuleType('automl'),'automl.infrastructure':ModuleType('automl.infrastructure'),
            'automl.infrastructure.run_budget':budget,'automl.infrastructure.llm_gateway':gateway}
        args=SimpleNamespace(request=str(request),request_sha256=digest,
            self_sha256=hashlib.sha256(Path(child.__file__).read_bytes()).hexdigest())
        error=None
        def verified(*args):current['mono']+=source_delay;return {}
        with patch.dict(sys.modules,modules),patch.object(child,'verified_gateway_sources',side_effect=verified),\
             patch.object(child.time,'monotonic',side_effect=lambda:current['mono']),\
             patch.object(child.time,'time',side_effect=lambda:current['wall']),\
             patch.object(child.sys,'path',list(sys.path)),patch.object(child.sys,'dont_write_bytecode',True):
            try:code=child.run(args)
            except RuntimeError as exc:error=exc;code=None
        return output,error,code,calls,cfg

    def test_late_provider_only_outcome_is_saved_but_still_exits_fatal(self):
        import json
        output,error,code,calls,cfg=self.outcome(1181.25)
        self.assertIsNone(code);self.assertIsInstance(error,RuntimeError)
        self.assertIn('original_provider_task_common_deadline',str(error))
        self.assertTrue(output.is_file());row=json.loads(output.read_text('utf-8'))
        self.assertEqual(row['call']['attempts'],1);self.assertEqual(row['call']['status'],'ok')
        self.assertEqual(row['content'],'synthetic-safe-content')
        self.assertNotIn('MUST_NOT_PERSIST',output.read_text('utf-8'))
        self.assertEqual(len(calls),1);self.assertEqual(calls[0]['timeout'],170.)
        self.assertEqual(cfg['clock']['provider_deadline_monotonic'],1180.)

    def test_hard_task_and_common_expiry_never_publish_qualified_sdk_result(self):
        for terminal,wall in ((5800.,None),(1001.,12800.)):
            with self.subTest(terminal=terminal,wall=wall):
                output,error,code,calls,cfg=self.outcome(terminal,terminal_wall=wall)
                self.assertIsNone(code);self.assertIsInstance(error,RuntimeError)
                self.assertIn('original_task_common_deadline',str(error))
                self.assertFalse(output.exists());self.assertEqual(len(calls),1)

    def test_inner170_receipt_reserve_keeps_original180_and_missing_tokens_NULL(self):
        import json
        usage=dict(status='error',exception_type='TimeoutError',attempts=1,usage=None,usage_complete=False)
        output,error,code,calls,cfg=self.outcome(1179.,sdk_usage=usage,sdk_content=None)
        self.assertIsNone(error);self.assertEqual(code,0)
        self.assertEqual(calls[0]['timeout'],170.);self.assertEqual(cfg['timeout'],180.)
        self.assertEqual(cfg['clock']['provider_deadline_monotonic'],1180.)
        self.assertEqual(cfg['clock']['task_deadline_monotonic'],5800.)
        self.assertEqual(cfg['clock']['common_deadline_monotonic'],11800.)
        row=json.loads(output.read_text('utf-8'))
        self.assertIsNone(row['content']);self.assertIsNone(row['call']['usage'])
        self.assertFalse(row['call']['usage_complete']);self.assertEqual(row['call']['exception_type'],'TimeoutError')
        output,error,code,calls,cfg=self.outcome(1179.,source_delay=176.)
        self.assertIsInstance(error,RuntimeError);self.assertIsNone(code)
        self.assertFalse(output.exists());self.assertEqual(calls,[])


class ActualBrokerBoundaryContracts(unittest.TestCase):
    def broker(self,observed,*,wrong_request=False):
        """Project actual nested gateway body; synthetic coordinator launches nothing."""
        import ast,copy,contextlib,hashlib,json,tempfile
        import task_entry as entry
        source=Path(entry.__file__).read_text('utf-8');tree=ast.parse(source)
        run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        gateway=copy.deepcopy(next(n for n in run.body if isinstance(n,ast.FunctionDef) and n.name=='gateway'))
        factory=ast.parse('def factory():\n provider_count=0\n return None\n').body[0]
        factory.body[1:]=[gateway,ast.Return(value=ast.Name(id='gateway',ctx=ast.Load()))]
        module=ast.fix_missing_locations(ast.Module(body=[factory],type_ignores=[]))
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name).resolve()
        def save(path,value):path.write_text(json.dumps(value),encoding='utf-8')
        def supervise(*args,**kwargs):
            receipt=args[2];request=json.loads((receipt.parent/'request.json').read_text('utf-8'))
            payload=dict(schema='qwen-three-hour-single-gateway-result-v1',call_number=request['call_number'],
                request_sha256='f'*64 if wrong_request else hashlib.sha256((receipt.parent/'request.json').read_bytes()).hexdigest(),
                content=None,call=dict(status='error',exception_type='TimeoutError',attempts=1,usage=None,
                    usage_complete=False,parent_return_receipt={'path':'FORGED_CHILD','sha256':'f'*64}))
            save(receipt.parent/'result.json',payload);save(receipt,observed);return observed
        namespace=dict(Path=Path,json=json,time=SimpleNamespace(monotonic=lambda:1000.),need=entry.need,sha=entry.sha,
            output=root,root=root,HERE=root,pins={str(root/'gateway_child.py'):'a'*64},cfg={'python':'MOCK_NO_PROCESS'},
            view=SimpleNamespace(check=lambda:None),policy=SimpleNamespace(GATEWAY_LIMIT=4800),
            timing=dict(start_unix=2000.,start_monotonic=1000.,absolute_deadline_unix=12800.,
                common_deadline_monotonic=11800.,task_deadline_monotonic=5800.,task_deadline_unix=6800.),
            save=save,gateway_code={},provider_credentials=lambda coor:contextlib.nullcontext(),
            coor=SimpleNamespace(supervise=supervise),state={},persist_supervision=lambda:None,
            frozen=lambda:None,owner=None,processes=None)
        exec(compile(module,str(entry.__file__),'exec'),namespace)
        return namespace['factory'](),root

    def test_actual_clean_return_overwrites_child_claim_and_rejects_parent_or_request_failure(self):
        import hashlib
        good=dict(status='ok',exit_code=0,cleanup_confirmed=True,error_history=[])
        gateway,root=self.broker(good);content,usage=gateway('synthetic',{},180.)
        receipt=root/'gateway-1/supervisor.json'
        self.assertIsNone(content);self.assertEqual(usage['parent_return_receipt'],
            {'path':str(receipt),'sha256':hashlib.sha256(receipt.read_bytes()).hexdigest()})
        self.assertNotEqual(usage['parent_return_receipt']['path'],'FORGED_CHILD')
        for changed in [dict(status='timeout'),dict(status='memory_limit'),dict(exit_code=1),
                        dict(cleanup_confirmed=False),dict(error_history=['observation_denied'])]:
            gateway,root=self.broker(dict(good,**changed))
            with self.subTest(changed=changed),self.assertRaisesRegex(RuntimeError,'provider_owned_supervision_or_cleanup_failed'):
                gateway('synthetic',{},180.)
        gateway,root=self.broker(good,wrong_request=True)
        with self.assertRaisesRegex(RuntimeError,'provider_actual_request_binding_failed'):gateway('synthetic',{},180.)


if __name__=='__main__':unittest.main()
