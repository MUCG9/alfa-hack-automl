"""Three meaningful no-fit changed-caller mocks. Prepared, not executed."""
from pathlib import Path
from unittest.mock import patch
import copy,importlib.util,math,tempfile,unittest
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('_cx_caller_contract',ROOT/'run_audit.py')
caller=importlib.util.module_from_spec(spec);spec.loader.exec_module(caller)

class CacheCallerContracts(unittest.TestCase):
    def test_valid_negative_quality_is_technical_success_but_unbound_or_partial_result_is_not(self):
        value=dict(schema='class-xgb-contribution-audit-v1',status='complete',artifact_procedure_passed=True,
            quality_gate_passed=False,comparison={'quality_gate_passed':False},manifest_sha256='a'*64,expected_inventory_sha256='b'*64,
            audit_within_original_common_clock=True,new_model_fits=0,API_calls=0,Qwen_calls=0,candidate_refit=False,
            submission_written=False,new_release_qualified=False,promotion=False,submit=False,first_failure=None,error_history=[])
        self.assertTrue(caller.result_qualified(value,'a'*64,'b'*64))
        for key,v in [('artifact_procedure_passed',False),('quality_gate_passed',None),('comparison',None),
            ('manifest_sha256','c'*64),('expected_inventory_sha256','c'*64),('new_model_fits',1),('submit',True),('first_failure',{'code':'failed'})]:
            changed=dict(value);changed[key]=v
            with self.subTest(key=key):self.assertFalse(caller.result_qualified(changed,'a'*64,'b'*64))
    def test_original600_and_parent120_assignments_keep_all_final_reserve(self):
        start,begin=1792849529.7788615,108535.046
        clock=caller.audit_clock(start,begin,start+100,begin+100)
        self.assertEqual(clock['absolute_deadline_unix'],start+600)
        self.assertEqual(clock['common_deadline_monotonic'],begin+600)
        self.assertEqual(clock['audit_deadline_unix'],start+100+120)
        self.assertEqual(clock['audit_deadline_monotonic'],begin+100+120)
        self.assertEqual(clock['prior_checkpoint_monotonic'],begin+100)
        self.assertEqual(clock['start_monotonic'],begin)
        for values in [(start,begin,start+181,begin+181),(start,begin,start-1,begin-1),(start,begin,float('nan'),begin+1)]:
            with self.subTest(values=values),self.assertRaises(RuntimeError):caller.audit_clock(*values)

    def test_only_fixed_auditor_argv_accepts_absolute_paths_no_payload_or_fit(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();manifest=str(root/'manifest.json');output=str(root/'comparison.json');python=str(root/'python.exe')
            with patch.object(caller,'AUDITOR_PATH','class-xgb-contribution-audit-next-dev/audit_cache.py'),patch.object(caller,'AUDITOR_SHA','a'*64):
                result=caller.audit_command(python,manifest,'b'*64,output)
                self.assertEqual(result,[python,'-B','-X','utf8',str(caller.WORK/'class-xgb-contribution-audit-next-dev/audit_cache.py'),
                    '--manifest',manifest,'--manifest-sha256','b'*64,'--self-sha256','a'*64,'--output',output])
                self.assertNotIn('--time-budget',result);self.assertNotIn('--hpo-trials',result)
                with self.assertRaises(RuntimeError):caller.audit_command(python,'relative.json','b'*64,output)
            with patch.object(caller,'AUDITOR_PATH',None),self.assertRaises(RuntimeError):caller.audit_command(python,manifest,'b'*64,output)

    def test_failed_false_or_unconfirmed_predecessor_never_admits_cache_reader(self):
        root=dict(schema='br-standard-qualification-root-closure-v1',technical_procedure_passed=True,cleanup_confirmed=True,
            source_unchanged=True,active_owned_processes=[],uncertain_owned=[],changed_source_or_core=[],actual_exec_session=37018,
            actual_exec_exit_code_observed_by_root=0,actual_tool_evidence='757206')
        fresh=dict(schema='BRQ3-current-full-root-source-cleanup-confirmation-v1',root_sha256=caller.ROOT_REF[1],
            actual_driver_execution=dict(session=37018,exit_code=0,tool='757206'),actual_closer_execution=dict(session=None,exit_code=0,tool='d1005d'),
            known_exact_live=[],uncertain=[],all354_immutable_source_input_pins_current=True,temporary_root_absent=True,
            current_source_cleanup_confirmed=True,inside_original_common=True)
        timing=dict(root_sha256=caller.ROOT_REF[1],fresh_confirmation_sha256=caller.FRESH_REF[1],fresh_inside_actual_closer_birth_plus60=True,
            fresh_inside_existing_final240=True,fresh_inside_original_common=True)
        caller.predecessor_documents(root,fresh,timing)
        for scope,key,value in [('root','technical_procedure_passed',False),('root','cleanup_confirmed',False),('root','source_unchanged',False),
            ('root','actual_tool_evidence','unknown'),('fresh','uncertain',[{'pid':1,'create_time':None}]),
            ('fresh','temporary_root_absent',False),('fresh','actual_closer_execution',dict(session=None,exit_code=1,tool='d1005d')),
            ('timing','fresh_inside_actual_closer_birth_plus60',False)]:
            docs=copy.deepcopy(dict(root=root,fresh=fresh,timing=timing));docs[scope][key]=value
            with self.subTest(scope=scope,key=key),self.assertRaises(RuntimeError):caller.predecessor_documents(**docs)

if __name__=='__main__':unittest.main()
