"""Prepared pure mocks only; no network, model, process or real credential reads."""
from pathlib import Path
from types import SimpleNamespace
import copy,hashlib,importlib.util,json,tempfile,unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('_future_q3h_outer',Path(__file__).with_name('run_campaign.py'))
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

def qualified_recipe_fixture(root,recipe):
    def saved(name,value):
        path=root/name;path.write_text(json.dumps(value),encoding='utf-8')
        return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    spec=dict(kind='classification',metric='macro_f1')
    report=saved('report.json',dict(spec=spec,selected_recipe=recipe))
    cuts=[dict(saved('cut-'+str(seed)+'.json',dict(synthetic_fixed_partition=seed)),seed=seed) for seed in (42,43)]
    actual={report['path']:report['sha256'],**{v['path']:v['sha256'] for v in cuts}}
    audit=saved('qualified-audit.json',dict(artifact_procedure_passed=True,archive_sha256='a'*64,actual_artifact_sha256=actual))
    prior=saved('qualified-root.json',dict(technical_procedure_passed=True,independent_audit=audit))
    authority=saved('strong-authority.json',dict(schema='qwen-three-hour-strong-recipe-authority-v1',
        qualified_root_sha256=prior['sha256'],kind='classification',metric='macro_f1',recipe=recipe,source_report=report))
    pins={**actual,**{v['path']:v['sha256'] for v in (audit,prior,authority)}}
    cfg=dict(immutable_files=pins,source_qualification=dict(root=prior,archive=dict(sha256='a'*64)))
    row=dict(spec=spec,strong_authority=authority,task=dict(kind='classification',metric='macro_f1',strong_recipe=recipe,cuts=cuts))
    return cfg,row

class TrustedBrokerContracts(unittest.TestCase):
    def test_exact_broker_facade_copies_scrubbed_mapping_and_restores_after_exception(self):
        base={k:'1' for k in ('AUTOML_THREADS','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}
        base['PATH']='fixture-path';before=dict(base);calls=[]
        def original(directory,model,manifest):calls.append((directory,model,manifest));return base
        coor=SimpleNamespace(environment=original)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);entry=root/'task_entry.py';entry.write_bytes(b'inert fixture, never executed')
            digest=hashlib.sha256(entry.read_bytes()).hexdigest()
            env={'OPENAI_API_KEY':'fixture-authorized-secret','OPENAI_BASE_URL':'https://changellenge.up.railway.app/v1'}
            with patch.object(c,'CORE',root),patch.dict(c.os.environ,env,clear=True):
                with self.assertRaisesRegex(ValueError,'deliberate'):
                    with c.trusted_broker_environment(coor,entry,digest,'fixture-model','off'):
                        projected=coor.environment(root,False,{'safe':True})
                        self.assertIsNot(projected,base);self.assertEqual(base,before)
                        self.assertEqual(projected['OPENAI_API_KEY'],env['OPENAI_API_KEY'])
                        self.assertEqual(projected['OPENAI_BASE_URL'],env['OPENAI_BASE_URL'])
                        self.assertEqual(projected['OPENAI_MODEL'],'fixture-model')
                        self.assertEqual(projected['AUTOML_REASONING_EFFORT'],'off')
                        self.assertTrue(all(projected[k]=='1' for k in before if k!='PATH'))
                        with self.assertRaises(RuntimeError):coor.environment(root,True,{})
                        raise ValueError('deliberate')
                self.assertIs(coor.environment,original);self.assertEqual(base,before)
                self.assertNotIn('OPENAI_API_KEY',coor.environment(root,False,{}))
                with self.assertRaises(RuntimeError):
                    with c.trusted_broker_environment(coor,root/'other.py',digest,'fixture-model','off'):pass
                with self.assertRaises(RuntimeError):
                    with c.trusted_broker_environment(coor,entry,'0'*64,'fixture-model','off'):pass
                with patch.dict(c.os.environ,{'OPENAI_BASE_URL':'https://unapproved.invalid'},clear=False):
                    with self.assertRaises(RuntimeError):
                        with c.trusted_broker_environment(coor,entry,digest,'fixture-model','off'):pass
                self.assertIs(coor.environment,original)
        self.assertTrue(calls)

    def test_equal_task_origin_never_rebases_common_or_borrows_other_task_time(self):
        state=dict(start_unix=1000.,start_monotonic=20.,absolute_deadline_unix=11800.,common_deadline_monotonic=10820.)
        before=dict(state);a=c.task_clock(state,1300.,320.);b=c.task_clock(state,6100.,5120.)
        self.assertEqual(a['task_deadline_monotonic'],5120.)
        self.assertEqual(b['task_deadline_monotonic'],9920.)
        self.assertEqual(a['task_deadline_unix']-a['task_start_unix'],4800.)
        self.assertEqual(b['task_deadline_unix']-b['task_start_unix'],4800.)
        self.assertEqual(state,before)
        for bad,wall,mono in [(dict(state,absolute_deadline_unix=11801.),1300.,320.),
            (state,7001.,6021.),(state,1300.,330.),(state,float('nan'),320.),(state,999.,19.)]:
            with self.subTest(wall=wall,mono=mono),self.assertRaises(RuntimeError):c.task_clock(bad,wall,mono)
        self.assertEqual(state,before)

    def test_raw_strong_recipe_requires_actual_qualified_report_and_never_fullfit_iterations(self):
        raw=dict(engine='ensemble',components=[dict(engine='lightgbm',params={'max_depth':4})])
        with tempfile.TemporaryDirectory() as directory:
            cfg,row=qualified_recipe_fixture(Path(directory),copy.deepcopy(raw))
            before=copy.deepcopy((cfg,row));c.strong_authority(cfg,row)
            self.assertEqual((cfg,row),before)
            wrong=copy.deepcopy(row);wrong['task']['strong_recipe']['components'][0]['params']['max_depth']=9
            with self.assertRaisesRegex(RuntimeError,'actual_selected_raw_recipe'):c.strong_authority(cfg,wrong)
            wrong=copy.deepcopy(cfg);wrong['immutable_files'].pop(row['task']['cuts'][0]['path'])
            with self.assertRaisesRegex(RuntimeError,'qualified_row_partitions'):c.strong_authority(wrong,row)
            with tempfile.TemporaryDirectory() as other:
                bad=copy.deepcopy(raw);bad['components'][0]['fit_iterations']=339
                cfg2,row2=qualified_recipe_fixture(Path(other),bad)
                with self.assertRaisesRegex(RuntimeError,'tree_override_forbidden'):c.strong_authority(cfg2,row2)

if __name__=='__main__':unittest.main(verbosity=2)
