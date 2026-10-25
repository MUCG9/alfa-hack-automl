"""Prepared synthetic metadata contracts. No numerical primitive/model imports."""
from pathlib import Path
import copy
import importlib.util
import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('_independent_audit_contract_target',P/'audit_final.py')
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,allow_nan=False),encoding='utf-8')
    return dict(path=str(path),sha256=A.sha(path))


def clocks():
    return dict(start_unix=1000.,start_monotonic=100.,absolute_deadline_unix=11800.,common_deadline_monotonic=10900.,
        audit_start_unix=10900.,audit_start_monotonic=10000.,audit_deadline_unix=11500.,audit_deadline_monotonic=10600.)


def sealed_pair(root):
    pin=save(root/'source.json',{'source':1});pins={pin['path']:pin['sha256']};rows=[]
    for kind in A.KINDS:
        output=root/kind;output.mkdir()
        manifest=save(root/(kind+'-manifest.json'),dict(kind=kind))
        pins[manifest['path']]=manifest['sha256']
        report=save(output/'report.json',dict(status='unparsed'))
        terminal=save(output/'terminal.json',dict(status='unparsed'))
        observed=dict(status='ok',exit_code=0,cleanup_confirmed=True,error_history=[],
            cleanup_observation=dict(denial_count=0,unresolved=[]))
        supervisor=save(root/(kind+'-supervisor.json'),observed)
        rows.append(dict(kind=kind,task_manifest=manifest,spec={},output=str(output),report=report,
            terminal=terminal,supervisor=dict(supervisor,record=observed),seal=None))
    for row in rows:
        files={str(p):A.sha(p) for p in Path(row['output']).iterdir()}
        row['seal']=save(Path(row['output'])/'seal.json',dict(schema='qwen-three-hour-task-core-seal-v1',
            kind=row['kind'],task_manifest=row['task_manifest'],output=row['output'],
            files_sha256=files,immutable_files_sha256=pins))
    return dict(immutable_files=pins,tasks=rows)


def callback_fixture(root,status='ok'):
    output=root/'output';folder=output/'worker-1';folder.mkdir(parents=True)
    timing=dict(task_start_unix=1000.,task_start_monotonic=100.,task_deadline_unix=5800.,task_deadline_monotonic=4900.)
    taskcfg=dict(immutable_files={},spec={},clock=timing,task=dict(cuts=[dict(path=str(root/'cut.npz'),sha256='a'*64,seed=42)]))
    recipe=dict(engine='synthetic',params={})
    result=dict(status=status,recipe=recipe,output_dir=str(folder),cleanup_confirmed=True,strict_runtime=True,
        split_sha256='a'*64,hpo_fair_reserve_provenance=dict(schema='hpo-fair-reserve-worker-origin-v1',
            cleanup_confirmed=True,coordinator_killed=None,primary_exception_type=None,prior_result_status=status),
        release_worker_allocation_seconds=50.,worker_memory_limit_bytes=1536*2**20,whole_memory_limit_bytes=2048*2**20,
        observed_worker_tree_peak_bytes=10,observed_combined_peak_bytes=20,
        parent_observed_worker_exit_code=0 if status=='ok' else 1,
        release_original_clock=dict(start_unix=1000.,start_monotonic=100.,deadline_unix=5800.,deadline_monotonic=4900.,
            actual_failure_type=None,actual_resource_samples=2,resource_limit_bytes=2048*2**20,
            observation_gap_limit_seconds=10,resource_sample_cadence_seconds=.25))
    rawjob=save(folder/'job.json',dict(spec={},recipe=recipe,threads=2,output_dir=str(folder),
        split_path=taskcfg['task']['cuts'][0]['path'],full_fit=False,fit_iterations=None))
    rawresult=save(folder/'result.json',{})
    row=dict(output=str(output),task_manifest=dict(path='manifest',sha256='b'*64))
    parent=dict(schema='qwen-three-hour-parent-result-v1',callback_index=1,phase='control-0',task_manifest=row['task_manifest'],
        source_union_canonical_sha256=A.canonical({}),spec_canonical_sha256=A.canonical({}),
        recipe_canonical_sha256=A.canonical(recipe),cut=taskcfg['task']['cuts'][0],raw_job=rawjob,raw_result=rawresult,result=result)
    ref=save(folder/'parent-result.json',parent)
    report=dict(callback_ledger_refs=[ref],worker_calls_attempted=1,worker_calls_succeeded=int(status=='ok'),actual_learner_fit_calls=None)
    seal=dict(files_sha256={v['path']:v['sha256'] for v in (ref,rawjob,rawresult)})
    return row,report,taskcfg,seal,parent,folder/'parent-result.json'


def resave_parent(values,parent,path):
    row,report,taskcfg,seal,*_=values
    ref=save(path,parent);report['callback_ledger_refs']=[ref];seal['files_sha256'][ref['path']]=ref['sha256']


def reported_usage(call):
    return {k:copy.deepcopy(call.get(k)) for k in ('status','attempts','usage','usage_complete','finish_reason',
        'reasoning_effort_requested','response_model')}


class IndependentAuditContracts(unittest.TestCase):
    def test_both_complete_seals_before_any_numerical_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg=sealed_pair(Path(tmp).resolve())
            with patch.object(A,'numerical_primitives',side_effect=AssertionError('must stay inert')) as numerical:
                self.assertEqual(len(A.verify_all_seals(cfg,lambda:None)),2)
                numerical.assert_not_called()
            Path(cfg['tasks'][1]['report']['path']).write_text('changed',encoding='utf-8')
            with self.assertRaisesRegex(A.AuditStop,'ref_SHA_changed'):A.verify_all_seals(cfg,lambda:None)

    def test_unsealed_extra_file_or_swapped_terminal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg=sealed_pair(Path(tmp).resolve());row=cfg['tasks'][0]
            extra=Path(row['output'])/'unsealed.txt';extra.write_text('x',encoding='utf-8')
            with self.assertRaisesRegex(A.AuditStop,'entire_task_tree'):A.verify_all_seals(cfg,lambda:None)
            extra.unlink();row['terminal']=cfg['tasks'][1]['terminal']
            with self.assertRaisesRegex(A.AuditStop,'mandatory_core_role'):A.verify_all_seals(cfg,lambda:None)

    def test_JSON_duplicate_nonfinite_and_bounded_size_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'x.json'
            for raw,code in [('{"a":1,"a":2}','duplicate_JSON_key'),('{"a":NaN}','nonfinite_JSON')]:
                path.write_text(raw,encoding='utf-8')
                with self.assertRaisesRegex(A.AuditStop,code):A.load(path)
            path.write_text('{}',encoding='utf-8')
            with self.assertRaisesRegex(A.AuditStop,'bounded_regular'):A.load(path,maximum=1)

    def test_callback_count_never_becomes_learner_fit_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            values=callback_fixture(Path(tmp).resolve());row,report,cfg,seal,*_=values
            self.assertEqual(len(A.parent_records(row,report,cfg,seal,lambda:None,lambda r:True)),1)
            report['actual_learner_fit_calls']=1
            with self.assertRaisesRegex(A.AuditStop,'not_learner_fit_count'):A.parent_records(row,report,cfg,seal,lambda:None,lambda r:True)

    def test_late_timeout_resource_origin_stays_technical_STOP(self):
        with tempfile.TemporaryDirectory() as tmp:
            values=callback_fixture(Path(tmp).resolve(),'timeout');row,report,cfg,seal,parent,path=values
            self.assertEqual(len(A.parent_records(row,report,cfg,seal,lambda:None,lambda r:False)),1)
            parent['result']['hpo_fair_reserve_provenance']['coordinator_killed']='memory_limit'
            resave_parent(values,parent,path)
            with self.assertRaisesRegex(A.AuditStop,'resource_or_technical_origin'):A.parent_records(row,report,cfg,seal,lambda:None,lambda r:True)

    def test_success_requires_actual_raw_roles_exit_and_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            values=callback_fixture(Path(tmp).resolve());row,report,cfg,seal,parent,path=values
            with self.assertRaisesRegex(A.AuditStop,'typed_terminal'):A.parent_records(row,report,cfg,seal,lambda:None,lambda r:False)
            parent['raw_result']=None;resave_parent(values,parent,path)
            with self.assertRaisesRegex(A.AuditStop,'raw_evidence_missing'):A.parent_records(row,report,cfg,seal,lambda:None,lambda r:True)

    def test_parent_source_union_duplicate_and_output_roles_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            values=callback_fixture(Path(tmp).resolve());row,report,cfg,seal,parent,path=values
            parent['source_union_canonical_sha256']='0'*64;resave_parent(values,parent,path)
            with self.assertRaisesRegex(A.AuditStop,'parent_source_spec'):A.parent_records(row,report,cfg,seal,lambda:None,lambda r:True)
            parent['source_union_canonical_sha256']=A.canonical({});parent['raw_job']['path']=str(path)
            resave_parent(values,parent,path)
            with self.assertRaisesRegex(A.AuditStop,'role_path_changed'):A.parent_records(row,report,cfg,seal,lambda:None,lambda r:True)

    def test_failed_timeout_NULL_duplicate_and_actual_attempts_separate(self):
        rows=[dict(round=1,status='duplicate',scores=None,decision='discard'),dict(round=2,status='failed',scores=None,decision='discard')]
        report=dict(records=rows,gateway_calls=2,executed_Qwen_candidates=1)
        parents=[dict(phase='control-0'),dict(phase='round-2-0',result=dict(status='timeout'))]
        result=A.iteration_accounting(report,parents)
        self.assertEqual(result['actual_candidate_recipe_attempts'],1);self.assertEqual(result['actual_candidate_worker_callbacks'],1)
        self.assertIsNone(result['learner_fit_count'])
        rows[1]['scores']=[1.,2.]
        with self.assertRaisesRegex(A.AuditStop,'failed_objective_must_be_NULL'):A.iteration_accounting(report,parents)

    def test_invalid_proposal_cannot_claim_callback_or_completed_score(self):
        report=dict(records=[dict(round=1,status='invalid',scores=None,decision='discard')],gateway_calls=1,executed_Qwen_candidates=0)
        with self.assertRaisesRegex(A.AuditStop,'not_a_fit'):
            A.iteration_accounting(report,[dict(phase='round-1-0',result=dict(status='ok'))])
        report['records'][0].update(status='completed',scores=[1.,2.])
        with self.assertRaisesRegex(A.AuditStop,'two_valid_callbacks'):
            A.iteration_accounting(report,[dict(phase='round-1-0',result=dict(status='ok'))])

    def test_actual_HTTP_usage_complete_and_reasoning_not_attested(self):
        call=dict(status='ok',attempts=2,usage_complete=True,usage=dict(prompt_tokens=10,completion_tokens=5),
            reasoning_effort_requested='high',response_model='reported-model',reasoning_tokens_reported=None)
        report=dict(gateway_calls=1,usage=[reported_usage(call)],http_attempts_reported=2,http_attempts_complete=True,usage_complete=True)
        result=A.usage_summary([dict(call_number=1,call=call)],report)
        self.assertEqual(result['HTTP_attempts'],2);self.assertFalse(result['requested_reasoning_is_backend_attestation'])
        self.assertEqual(result['reasoning_token_counts_reported'],[None])
        call['attempts']=True
        with self.assertRaisesRegex(A.AuditStop,'HTTP_attempts_missing'):A.usage_summary([dict(call_number=1,call=call)],report)

    def test_incomplete_usage_and_reported_counter_mismatch_STOP(self):
        call=dict(status='ok',attempts=1,usage_complete=False,usage=dict(prompt_tokens=1,completion_tokens=1))
        report=dict(gateway_calls=1,usage=[reported_usage(call)],http_attempts_reported=1,http_attempts_complete=True,usage_complete=False)
        with self.assertRaisesRegex(A.AuditStop,'incomplete_actual_usage'):A.usage_summary([dict(call_number=1,call=call)],report)
        call['usage_complete']=True;report['usage']=[reported_usage(call)];report['usage_complete']=True;report['http_attempts_reported']=2
        with self.assertRaisesRegex(A.AuditStop,'incomplete_actual_usage'):A.usage_summary([dict(call_number=1,call=call)],report)

    def test_original_clock_reserves_rollback_and_no_reset(self):
        timing=clocks();self.assertEqual(A.check_clock(timing,10000.,10001.,10901.),10001.)
        for previous,now,wall in [(10002.,10001.,10901.),(10000.,10570.,11470.),(10000.,10001.,10910.)]:
            with self.assertRaises(A.AuditStop):A.check_clock(timing,previous,now,wall)
        timing['common_deadline_monotonic']+=1
        with self.assertRaisesRegex(A.AuditStop,'assignment'):A.check_clock(timing,10000.,10001.,10901.)

    def test_qualification_requires_final_posttool_not_pending_atomic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();archive=root/'code.zip';archive.write_bytes(b'code')
            ar=dict(path=str(archive),sha256=A.sha(archive))
            rr=save(root/'root.json',dict(schema='standard-repair-qualification-root-closure-v1',archive_sha256=ar['sha256'],
                actual_exec_exit_code_observed_by_root=0,actual_tool_evidence='actual-driver-tool',
                technical_procedure_passed=True,source_unchanged=True,cleanup_confirmed=True,temporary_cleanup_confirmed=True))
            value=dict(root_sha256=rr['sha256'],source_unchanged=True,post_tool_confirmed=True,known_exact_live=[],uncertain=[],
                actual_wrapper=dict(exit_code=0,tool='actual-root-observation'))
            cr=save(root/'post.json',value)
            cfg=dict(source_qualification=dict(archive=ar,root=rr,confirmation=cr),immutable_files={r['path']:r['sha256'] for r in (ar,rr,cr)})
            self.assertEqual(A.source_qualification(cfg,lambda:None)['archive'],ar)
            value['post_tool_confirmed']=False;new=save(root/'post.json',value);cfg['source_qualification']['confirmation']=new;cfg['immutable_files'][new['path']]=new['sha256']
            with self.assertRaisesRegex(A.AuditStop,'wrapper_exit_and_fresh'):A.source_qualification(cfg,lambda:None)

    def test_pretruth_failure_emits_NULL_without_numerical_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();cfg=dict(schema='qwen-three-hour-independent-audit-private-v1',readiness='READY_SOURCE_REVIEWED_FROZEN',
                missing_bindings=[],clock=clocks(),immutable_files={str(Path(A.__file__).resolve()):A.sha(A.__file__)})
            manifest=save(root/'audit.json',cfg);output=root/'negative.json'
            args=SimpleNamespace(manifest=manifest['path'],manifest_sha256=manifest['sha256'],self_sha256=A.sha(A.__file__),output=str(output))
            with patch.object(A.time,'time',return_value=10901.),patch.object(A.time,'monotonic',return_value=10001.), \
                 patch.object(A,'verify_all_seals',side_effect=A.AuditStop('synthetic_core_missing')), \
                 patch.object(A,'numerical_primitives',side_effect=AssertionError('not before barrier')) as numerical:
                self.assertEqual(A.main(args),1);numerical.assert_not_called()
            result=json.loads(output.read_text('utf-8'))
            self.assertFalse(result['artifact_procedure_passed']);self.assertIsNone(result['metrics']);self.assertIsNone(result['quality_metric'])
            self.assertEqual(result['first_failure']['code'],'synthetic_core_missing')

    def test_reused_R4_requires_both_cuts_and_supported_class_protection(self):
        r4=A.numerical_primitives(A.sha(A.PRIMITIVES))
        def rows(value,f1):
            return {phase:dict(value=value,per_class_f1=dict(f1),independent_fitting_groups=dict(a=100,b=20,c=1),
                rarest_fitting_class='c',positions_sha256=('a' if phase=='primary' else 'b')*64)
                for phase in ('primary','confirmation')}
        control=rows(.6,dict(a=.7,b=.5,c=.3));candidate=rows(.61,dict(a=.68,b=.54,c=.4))
        result=r4.matched_control_comparison(candidate,control,'classification')
        self.assertTrue(result['each_cut_primary_gate_passed']);self.assertFalse(result['class_each_cut_gate_passed'])
        candidate=rows(.61,dict(a=.71,b=.51,c=.31));candidate['primary']['value']=.59;candidate['confirmation']['value']=.64
        self.assertGreater(sum(v['value'] for v in candidate.values())/2,.6)
        self.assertFalse(r4.matched_control_comparison(candidate,control,'classification')['each_cut_primary_gate_passed'])
        candidate=rows(.61,dict(a=.71,b=.51,c=.31))
        self.assertTrue(r4.matched_control_comparison(candidate,control,'classification')['class_each_cut_gate_passed'])


if __name__=='__main__':unittest.main()
