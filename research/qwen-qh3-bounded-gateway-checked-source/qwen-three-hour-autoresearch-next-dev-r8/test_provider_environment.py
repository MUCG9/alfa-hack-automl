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


if __name__=='__main__':unittest.main()
