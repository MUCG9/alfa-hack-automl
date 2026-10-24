"""Prepared metadata/clock/argv contracts only; no actual saved-data reads."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import copy,importlib.util,math,tempfile,unittest
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('_ra1_caller_contract',ROOT/'run_audit.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

class SavedArtifactCallerContracts(unittest.TestCase):
    def test_new_artifact_qualification_keeps_old_failure_and_exact_independent_binding(self):
        value=dict(schema='postfailure-standard-artifact-audit-v1',artifact_procedure_passed=True,
            manifest_sha256='a'*64,repair_context_sha256='b'*64,archive_sha256=c.ARCHIVE_SHA,
            audit_within_original_common_clock=True,audit_within_repair_clock=True,
            original_RQ6_procedure_requalified=False,original_failure_preserved=True,
            quality_metric=dict(regression=34.15,classification=.65),tasks=dict(regression={},classification={}),
            new_model_fits=0,promotion=False,submit=False)
        before=copy.deepcopy(value);self.assertTrue(c.result_qualified(value,'a'*64,'b'*64));self.assertEqual(value,before)
        for key,bad in [('artifact_procedure_passed',False),('manifest_sha256','c'*64),('repair_context_sha256','c'*64),
            ('original_RQ6_procedure_requalified',True),('original_failure_preserved',False),('new_model_fits',1),
            ('quality_metric',dict(regression=float('nan'),classification=.65)),('tasks',dict(regression={})),('submit',True)]:
            with self.subTest(key=key):self.assertFalse(c.result_qualified(dict(value,**{key:bad}),'a'*64,'b'*64))

    def test_actual_new600_audit120_preserves_final300_and_never_rebases_origin(self):
        start,begin=1792849529.7788615,108535.046
        value=c.audit_clock(start,begin,start+100,begin+100)
        self.assertEqual(set(value),{'start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic',
            'audit_start_unix','audit_start_monotonic','audit_deadline_unix','audit_deadline_monotonic'})
        self.assertEqual(value['start_unix'],start);self.assertEqual(value['start_monotonic'],begin)
        self.assertEqual(value['absolute_deadline_unix'],start+600);self.assertEqual(value['common_deadline_monotonic'],begin+600)
        self.assertEqual(value['audit_deadline_unix'],start+100+120)
        self.assertLessEqual(value['audit_deadline_monotonic']+300,begin+600)
        for inputs in [(start,begin,start+181,begin+181),(start,begin,start-1,begin-1),
            (start,begin,float('nan'),begin+1),(start,begin,start+100,begin+120)]:
            with self.subTest(inputs=inputs),self.assertRaises(RuntimeError):c.audit_clock(*inputs)

    def test_fixed_no_fit_argv_keeps_original_manifest_and_new_context_roles_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory).resolve();python=str(p/'python.exe');original=str(p/'original.json');context=str(p/'context.json');output=str(p/'audit.json')
            with patch.object(c,'AUDITOR_SHA','a'*64):
                argv=c.audit_command(python,original,'b'*64,context,'c'*64,output)
                self.assertEqual(argv,[python,'-B','-X','utf8',str(c.WORK/c.AUDITOR_PATH),'--manifest',original,'--manifest-sha256','b'*64,
                    '--self-sha256','a'*64,'--repair-context',context,'--repair-context-sha256','c'*64,'--output',output])
                self.assertNotIn('--time-budget',argv);self.assertNotIn('--hpo-trials',argv)
                with self.assertRaises(RuntimeError):c.audit_command(python,original,'b'*64,'relative.json','c'*64,output)
            with patch.object(c,'AUDITOR_SHA',None),self.assertRaises(RuntimeError):c.audit_command(python,original,'b'*64,context,'c'*64,output)

    def test_current_clean_negative_admission_preserves_failed_root_and_full8016_scope(self):
        def row(pid):return dict(pid=pid,create_time=10000.+pid)
        def ids(rows):return {(v['pid'],v['create_time']) for v in rows}
        refs={key:dict(path=str(c.WORK/rel),sha256=h) for key,(rel,h) in c.ORIGINAL_REFS.items()}
        negative=dict(schema='rq6-separate-current-negative-closure-v1',technical_procedure_passed=False,original_RQ6_FAIL_preserved=True,
            root60_requalified=False,original_negative_root_sha256=refs['root']['sha256'],original_manifest_sha256=refs['manifest']['sha256'],
            source_pins_checked=1017,actual_failed_driver=dict(session=49569,exit_code=1,tool='dbc6a1'),
            actual_failed_frozen_closer=dict(exit_code=1,tool='fb3841'),current_source_unchanged=True,current_cleanup_confirmed=True,
            current_temporary_absent=True,inside_original6000=True,known_exact_live=[],uncertain=[],
            known_identities=[row(i) for i in range(1,8011)],known_count=8010,observer_preparer_identities=[row(i) for i in (9001,9002,9003)])
        post=copy.deepcopy(negative);post.update(schema='rq6-current-negative-post-tool-confirmation-v1',
            post_tool_current_confirmation=True,
            known_identities=negative['known_identities']+negative['observer_preparer_identities'],known_count=8013,
            observer_preparer_identities=[row(i) for i in (9011,9012,9013)],negative_closure_sha256=refs['negative']['sha256'],
            actual_negative_observer=dict(exit_code=0,tool='b449e3'))
        root=dict(technical_procedure_passed=False,actual_exec_session=49569,actual_exec_exit_code_observed_by_root=1,
            actual_tool_evidence='dbc6a1',source_unchanged=True,cleanup_confirmed=True,temporary_cleanup_confirmed=True,
            manifest_sha256=refs['manifest']['sha256'],independent_audit=None)
        state=dict(status='failed',first_failure=dict(child_kind='independent-audit'),contracts=[dict(expected=n) for n in (24,24,18,12,16,5,2,11,7)],
            tasks=[dict(kind='regression'),dict(kind='classification')])
        docs={refs[k]['path']:v for k,v in [('root',root),('campaign',state),('negative',negative),('post',post)]}
        hashes={str(c.BASE_PATH):c.BASE_SHA,**{v['path']:v['sha256'] for v in refs.values()}}
        cfg=dict(rq6=refs,immutable_files=hashes,negative_actual=dict(exit_code=0,tool='b449e3'),post_actual=dict(exit_code=0,tool='317ee6'),launch_preparer_receipts=[])
        def checked(changed):
            with (patch.object(c,'sha',side_effect=lambda path,*args:hashes[str(path)]),
                patch.object(c,'read',side_effect=lambda path:changed[str(path)]),
                patch.object(c,'imported',return_value=SimpleNamespace(ids=ids)),
                patch.object(c,'ra1_previous',side_effect=lambda cfg,base,known,check:known)):
                return c.predecessor(cfg)
        before=copy.deepcopy(docs);self.assertEqual(len(checked(docs)),8016);self.assertEqual(docs,before)
        for role,key,bad in [('root','technical_procedure_passed',True),('root','cleanup_confirmed',False),
            ('negative','current_source_unchanged',False),('post','uncertain',[row(9999)]),('post','known_count',8014)]:
            changed=copy.deepcopy(docs);changed[refs[role]['path']][key]=bad
            with self.subTest(role=role,key=key),self.assertRaises(RuntimeError):checked(changed)

    def test_current_RA1_failure_stays_negative_and_all8045_are_admitted_without_missing_observers(self):
        def row(pid):return dict(pid=pid,create_time=20000.+pid)
        def ids(rows):return {(v['pid'],v['create_time']) for v in rows}
        refs={key:dict(path=str(c.WORK/rel),sha256=h) for key,(rel,h) in c.RA1_REFS.items()}
        refs.update(driver_actual=dict(session=25644,exit_code=1,tool='19905f'),closer_actual=dict(exit_code=1,tool='8efa0b'),
            negative_actual=dict(exit_code=0,tool='0707d9'),post_actual=dict(exit_code=0,tool='cd0ef7'))
        oldpins={'synthetic-source-'+str(i):'a'*64 for i in range(1560)}
        hashes={**oldpins,**{refs[k]['path']:refs[k]['sha256'] for k in c.RA1_REFS}}
        manifest=dict(output=str(c.WORK/'ra1'),immutable_files=oldpins)
        state=dict(status='failed',contracts=[dict(expected=n) for n in (12,4,6)],artifact_procedure_passed=False,
            quality_metric=None,active_supervisor=None,first_failure=dict(child_kind='saved-standard-artifact-audit'))
        root=dict(schema='postfailure-standard-artifact-qualification-root-v1',technical_procedure_passed=False,
            manifest_sha256=refs['manifest']['sha256'],actual_exec_session=25644,actual_exec_exit_code_observed_by_root=1,
            actual_tool_evidence='19905f',independent_audit=None,quality_metric=None,original_RQ6_FAIL_preserved=True,
            original_RQ6_procedure_requalified=False,source_unchanged=True,cleanup_confirmed=True,temporary_cleanup_confirmed=True,
            owned_identities=[row(8036)],closure_preparer_identities=[row(i) for i in (8037,8038,8039)])
        negative=dict(schema='ra1-separate-current-negative-closure-v1',technical_procedure_passed=False,
            original_RA1_FAIL_preserved=True,original_RQ6_FAIL_preserved=True,root60_requalified=False,
            original_negative_root_sha256=refs['root']['sha256'],original_manifest_sha256=refs['manifest']['sha256'],
            actual_failed_driver=refs['driver_actual'],actual_failed_frozen_closer=refs['closer_actual'],source_pins_checked=1560,new_metrics=None,
            current_source_unchanged=True,current_cleanup_confirmed=True,current_temporary_absent=True,
            inside_original_RA1_common600=True,inside_inherited_RQ6_common6000=True,known_exact_live=[],uncertain=[],
            known_count=8039,known_identities=[row(i) for i in range(1,8040)],observer_preparer_identities=[row(i) for i in (9001,9002,9003)])
        post=copy.deepcopy(negative);post.update(schema='ra1-current-negative-post-tool-confirmation-v1',known_count=8042,
            known_identities=negative['known_identities']+negative['observer_preparer_identities'],
            observer_preparer_identities=[row(i) for i in (9011,9012,9013)],post_tool_current_confirmation=True,
            negative_closure_sha256=refs['negative']['sha256'],actual_negative_observer=refs['negative_actual'])
        docs={refs[k]['path']:v for k,v in [('manifest',manifest),('campaign',state),('root',root),('negative',negative),('post',post)]}
        cfg=dict(ra1_previous=refs,immutable_files=hashes)
        def checked(changed):
            with patch.object(c,'sha',side_effect=lambda path,*args:hashes[str(path)]),patch.object(c,'read',side_effect=lambda path:changed[str(path)]):
                return c.ra1_previous(cfg,SimpleNamespace(ids=ids),ids([row(i) for i in range(1,8017)]))
        before=copy.deepcopy(docs);accepted=checked(docs)
        self.assertEqual(len(accepted),8045);self.assertEqual(docs,before)
        self.assertTrue(ids(post['observer_preparer_identities'])<=accepted)
        for role,key,bad in [('root','technical_procedure_passed',True),('negative','current_source_unchanged',False),
            ('post','known_count',8043),('post','observer_preparer_identities',[]),('post','uncertain',[row(9999)]),('post','root60_requalified',True)]:
            changed=copy.deepcopy(docs);changed[refs[role]['path']][key]=bad
            with self.subTest(role=role,key=key),self.assertRaises(RuntimeError):checked(changed)

if __name__=='__main__':unittest.main(verbosity=2)
