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

def ra1_proof_fixture():
    refs={k:dict(path=str(c.WORK/rel),sha256=h) for k,(rel,h) in c.RA1_ORIGINAL_REFS.items()}
    pins={v['path']:v['sha256'] for v in refs.values()};values={}
    def saved(name,value,path=None):
        path=path or str(c.WORK/('mock-'+name+'.json'));h=hashlib.sha256(name.encode()).hexdigest()
        pins[path]=h;values[path]=value;return dict(path=path,sha256=h)
    def ident(n):return dict(pid=n,create_time=1000.+n)
    prior=[ident(n) for n in range(1,8011)];observers=[ident(n) for n in range(8011,8014)]
    later=[ident(n) for n in range(8014,8017)];rootpreps=[ident(n) for n in range(8017,8020)]
    wrapper=[ident(n) for n in range(8020,8023)];postpreps=[ident(n) for n in range(8023,8026)]
    flags=dict.fromkeys(('technical_procedure_passed','source_unchanged','current_temporary_absent','current_cleanup_confirmed',
        'inside_actual_closer_birth60','inside_original600','inside_inherited_RQ6_common6000','inside_existing_driver_final240'),True)
    archive=dict(path=str(c.WORK/'mock-archive.zip'),sha256='a'*64)
    inherited={str(c.WORK/('mock-old-source-'+str(n))):'b'*64 for n in range(1017)};pins.update(inherited)
    values[refs['manifest']['path']]=dict(readiness='READY_REVIEWED_FROZEN',output=str(c.WORK/'rq6'),executor=dict(archive=archive),immutable_files=inherited)
    oldtasks=[]
    for kind in ('regression','classification'):
        sup=saved(kind+'-supervisor',dict(status='ok',exit_code=0,cleanup_confirmed=True,cleanup_observation=dict(denial_count=0,unresolved=[])))
        oldtasks.append(dict(kind=kind,supervisor=sup,seal=refs[kind+'_seal']))
    values[refs['campaign']['path']]=dict(status='failed',manifest_sha256=refs['manifest']['sha256'],active_supervisor=None,independent_audit=None,
        failure_code='child_nonzero_exit',first_failure=dict(code='child_nonzero_exit',child_kind='independent-audit'),
        contracts=[dict(expected=v) for v in (24,24,18,12,16,4,2,11,8)],supervisors=[{}]*12,tasks=oldtasks,
        cleanup_confirmed=True,source_unchanged=True,temporary_cleanup_confirmed=True)
    values[refs['root']['path']]=dict(schema='standard-repair-qualification-root-closure-v1',technical_procedure_passed=False,
        qualified_ML_metrics=None,independent_audit=None,manifest_sha256=refs['manifest']['sha256'],actual_exec_session=49569,
        actual_exec_exit_code_observed_by_root=1,actual_tool_evidence='dbc6a1',cleanup_confirmed=True,source_unchanged=True,temporary_cleanup_confirmed=True)
    negative=dict(schema='rq6-separate-current-negative-closure-v1',known_count=8010,known_identities=prior,observer_preparer_identities=observers)
    oldpost=dict(schema='rq6-current-negative-post-tool-confirmation-v1',known_count=8013,known_identities=prior+observers,
        observer_preparer_identities=later,negative_closure_sha256=refs['negative']['sha256'],post_tool_current_confirmation=True)
    for value in (negative,oldpost):value.update(technical_procedure_passed=False,original_RQ6_FAIL_preserved=True,root60_requalified=False,new_metrics=None,
        original_negative_root_sha256=refs['root']['sha256'],current_source_unchanged=True,current_cleanup_confirmed=True,current_temporary_absent=True,inside_original6000=True,known_exact_live=[],uncertain=[])
    values[refs['negative']['path']]=negative;values[refs['post']['path']]=oldpost
    for key in ('barrier','regression_seal','classification_seal'):values[refs[key]['path']]={}
    qmanifest=saved('RA1-private',dict(readiness='READY_REVIEWED_FROZEN',output=str(c.WORK/'ra2')))
    context=saved('RA1-context',dict(schema='rq6-saved-terminal-audit-repair-private-v1',current_caller_manifest=qmanifest))
    audit=saved('RA1-audit',dict(schema='postfailure-standard-artifact-audit-v1',artifact_procedure_passed=True,archive_sha256=archive['sha256'],
        manifest_sha256=refs['manifest']['sha256'],repair_context_sha256=context['sha256'],original_RQ6_procedure_requalified=False,
        original_failure_preserved=True,audit_within_original_common_clock=True,audit_within_repair_clock=True))
    actual=dict(session=1,exit_code=0,tool='fixture-RA1');actual_wrapper=dict(exit_code=0,tool='fixture-wrapper')
    root=dict(schema='postfailure-standard-artifact-qualification-root-v1',technical_procedure_passed=True,original_RQ6_FAIL_preserved=True,
        original_RQ6_procedure_requalified=False,original_failed_driver=dict(session=49569,exit_code=1,tool='dbc6a1'),
        original_failed_frozen_closer=dict(exit_code=1,tool='fb3841'),original_rq6=refs,source_unchanged=True,cleanup_confirmed=True,temporary_cleanup_confirmed=True,
        active_owned_processes=[],uncertain_owned=[],changed_source_or_core=[],manifest_sha256=qmanifest['sha256'],repair_context=context,independent_audit=audit,
        actual_exec_session=1,actual_exec_exit_code_observed_by_root=0,actual_tool_evidence='fixture-RA1',archive_sha256=archive['sha256'],
        owned_identities=prior[:1],closure_preparer_identities=rootpreps)
    rootref=saved('RA1-root',root,str(c.WORK/'ra2/terminal-root-closure.json'));freshref=saved('RA1-fresh',{},str(c.WORK/'ra2/root-confirmation.json'));postref=saved('RA1-post',{},str(c.WORK/'ra2/actual-wrapper-exit-confirmation.json'))
    known=prior+observers+later+rootpreps
    fresh=dict(flags,schema='postfailure-standard-artifact-atomic-root-confirmation-v1',root_sha256=rootref['sha256'],actual_driver=actual,
        actual_closer_exit=0,known_identities=known,known_count=len(known),wrapper_preparer_identities=wrapper,known_exact_live=[],uncertain=[],errors=[])
    post=dict(flags,schema='postfailure-standard-artifact-actual-wrapper-exit-confirmation-v1',root_sha256=rootref['sha256'],root_confirmation_sha256=freshref['sha256'],
        actual_driver=actual,actual_wrapper=actual_wrapper,known_identities=known+wrapper,known_count=len(known+wrapper),post_tool_confirmed=True,inside_saved_driver_final240=True,
        known_exact_live=[],uncertain=[],post_tool_preparer_identities=postpreps)
    post.pop('technical_procedure_passed');post.pop('inside_existing_driver_final240')
    cfg=dict(immutable_files=pins,source_qualification=dict(mode='postfailure_saved_standard_artifacts_v1',original_rq6=refs,qualification_manifest=qmanifest,
        archive=archive,root=rootref,confirmation=freshref,post_tool=postref,driver_actual=actual,wrapper_actual=actual_wrapper))
    return cfg,root,fresh,post,values

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

    def test_RA1_saved_artifacts_require_complete_new_proof_without_relabelling_old_FAIL(self):
        cfg,root,fresh,post,values=ra1_proof_fixture()
        ids=lambda rows:{(row['pid'],row['create_time']) for row in rows}
        before=copy.deepcopy(values)
        def run():
            with patch.object(c,'sha',side_effect=lambda path,check=lambda:None:cfg['immutable_files'][str(path)]),patch.object(c,'read',side_effect=lambda path:values[str(path)]):
                return c.postfailure_qualification(cfg,lambda:None,root,fresh,post,SimpleNamespace(ids=ids))
        actual=run();self.assertEqual(values,before)
        self.assertTrue(ids(post['known_identities'])<=actual)
        self.assertIs(values[cfg['source_qualification']['original_rq6']['root']['path']]['technical_procedure_passed'],False)
        for mode in ('old_PASS','old_status','119','model_exit','new_old_qualified','late_post','wrong_current_manifest','missing_original_pin'):
            cfg,root,fresh,post,values=ra1_proof_fixture();original=cfg['source_qualification']['original_rq6']
            if mode=='old_PASS':values[original['root']['path']]['technical_procedure_passed']=True
            elif mode=='old_status':values[original['campaign']['path']]['status']='completed_pending_root'
            elif mode=='119':values[original['campaign']['path']]['contracts'][0]['expected']+=1
            elif mode=='model_exit':values[values[original['campaign']['path']]['tasks'][0]['supervisor']['path']]['exit_code']=1
            elif mode=='new_old_qualified':root['original_RQ6_procedure_requalified']=True
            elif mode=='late_post':post['inside_actual_closer_birth60']=False
            elif mode=='wrong_current_manifest':values[root['repair_context']['path']]['current_caller_manifest']={}
            else:cfg['immutable_files'].pop(original['old_auditor']['path'])
            with self.subTest(mode=mode),self.assertRaises(RuntimeError):run()

if __name__=='__main__':unittest.main(verbosity=2)
