"""Stdlib SOURCE preparation: no candidate/test imports or execution."""
from pathlib import Path
import ast
import copy
import difflib
import hashlib
import json

WORK=Path(__file__).resolve().parent
OLD=WORK/'qwen-three-hour-independent-audit-next-dev-r6'
NEW=WORK/'qwen-three-hour-independent-audit-next-dev-r7'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(n):return ast.dump(n,include_attributes=False)
def save(p,o):p.write_bytes((json.dumps(o,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))

hp=OLD/'source-handoff.json'
assert sha(hp)=='55028e01b968db3fc826951fbe827fdc96dda71264e2096a41fe03c41ac0ee3d'
base=json.loads(hp.read_text(encoding='utf-8'))
assert not NEW.exists()
for rel,s in base['files_sha256'].items():assert sha(OLD/rel)==s,rel
for rel,s in base['external_refs_sha256'].items():assert sha(WORK/rel)==s,rel
NEW.mkdir()
essential=['audit_final.py','r4_primitives.py','test_audit_contracts.py','test_csv_role_contracts.py',
    'binding.template.NOT_READY.json','primitive-provenance.json']
for rel in essential:(NEW/rel).write_bytes((OLD/rel).read_bytes())
external=dict(base['external_refs_sha256'])
preserve={}
for rel,s in list(base['files_sha256'].items())+[('source-handoff.json',sha(hp))]:
    path=(OLD/rel).relative_to(WORK).as_posix();assert path not in external or external[path]==s
    external[path]=s;preserve[rel]=dict(path=path,sha256=s)
save(NEW/'R6-external-preservation.json',dict(schema='immutable-original-path-source-preservation-v1',files=preserve,
    original_files=214,original_handoff_preserved=True,source_trees_duplicated=False))

old=(OLD/'audit_final.py').read_text(encoding='utf-8');new=old
needle="and row.get('status') in {'invalid','duplicate','unattempted_budget','completed','failed'},'anytime_round_sequence_or_status_changed')"
repl="and row.get('status') in {'invalid','duplicate','unattempted_budget','completed','failed','provider_timeout'},'anytime_round_sequence_or_status_changed')"
assert new.count(needle)==1;new=new.replace(needle,repl,1)
old_branch="""        if row['status'] in {'invalid','duplicate','unattempted_budget'}:
"""
new_branch="""        if row['status']=='provider_timeout':
            # Structural failed-NULL accounting only; actual sealed clean broker
            # proof is checked in verify_usage, whose strict final gate remains.
            need(set(row)=={'round','signature','status','decision','scores','error_type','hypothesis',
                 'checkpoint','worker_attempted','parent_return_receipt'} and not actual
                 and all(row.get(k) is None for k in ('scores','signature','hypothesis','checkpoint'))
                 and row.get('decision')=='discard' and row.get('error_type')=='TimeoutError'
                 and row.get('worker_attempted') is False,'provider_timeout_is_NULL_not_worker_attempt')
            key(row['parent_return_receipt'])
        elif row['status'] in {'invalid','duplicate','unattempted_budget'}:
"""
assert new.count(old_branch)==1;new=new.replace(old_branch,new_branch,1)
before="""        rows.append(res)
    return usage_summary(rows,report)
"""
after="""        declared=report.get('records',[])
        if type(declared) is list and index<=len(declared) and type(declared[index-1]) is dict and declared[index-1].get('status')=='provider_timeout':
            declared=declared[index-1];call=res.get('call');saved=report.get('usage',[])
            need(declared.get('parent_return_receipt')==dict(path=str(supervisor),sha256=sha(supervisor,check))
                 and declared.get('error_type')=='TimeoutError' and declared.get('worker_attempted') is False
                 and type(call) is dict and call.get('status')=='error' and call.get('exception_type')=='TimeoutError'
                 and type(call.get('attempts')) is int and 1<=call['attempts']<=3 and res.get('content') is None
                 and type(saved) is list and index<=len(saved) and type(saved[index-1]) is dict
                 and set(saved[index-1])=={'status','attempts','usage','usage_complete','finish_reason','reasoning_effort_requested','response_model'}
                 and saved[index-1]=={k:call.get(k) for k in saved[index-1]}
                 and report.get('usage_complete') is False,'provider_timeout_actual_clean_return_binding_changed')
        rows.append(res)
    return usage_summary(rows,report)
"""
assert new.count(before)==1;new=new.replace(before,after,1)
(NEW/'audit_final.py').write_bytes(new.encode('utf-8'))
inverse=new.replace(repl,needle,1).replace(new_branch,old_branch,1).replace(after,before,1)
assert inverse==old and dump(ast.parse(inverse))==dump(ast.parse(old))
old_funcs={n.name:dump(n)for n in ast.parse(old).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
new_funcs={n.name:dump(n)for n in ast.parse(new).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
assert set(old_funcs)==set(new_funcs)
assert {k for k in old_funcs if old_funcs[k]!=new_funcs[k]}=={'anytime_accounting','verify_usage'}
assert old_funcs['usage_summary']==new_funcs['usage_summary']

tests=(OLD/'test_audit_contracts.py').read_text(encoding='utf-8')
addition='''class CleanProviderTimeoutAuditContracts(unittest.TestCase):
    def accounting_fixture(self):
        report,parents,task,strong,add=anytime_fixture()
        report['records'][0]['round']=2
        parents[-1]['phase']='round-2-0'
        report['gateway_calls']=2
        report['records'].insert(0,dict(round=1,signature=None,status='provider_timeout',decision='discard',
            scores=None,error_type='TimeoutError',hypothesis=None,checkpoint=None,worker_attempted=False,
            parent_return_receipt=dict(path=str((P/'synthetic-gateway-1/supervisor.json').resolve()),sha256='a'*64)))
        return report,parents,task,strong

    def test_provider_timeout_NULL_row_adds_no_worker_or_candidate_or_checkpoint(self):
        report,parents,task,strong=self.accounting_fixture()
        result=A.anytime_accounting(report,parents,task,lambda a,b:max(30,(a+b)//2),strong)
        self.assertEqual(result['all_rounds'],2)
        self.assertEqual(result['actual_candidate_recipe_attempts'],1)
        self.assertEqual(result['actual_candidate_worker_callbacks'],1)
        self.assertEqual(len(parents),5);self.assertEqual(result['selected_checkpoint'],1)
        self.assertIsNone(result['learner_fit_count'])
        for change in [dict(scores=[0.]),dict(worker_attempted=True),dict(signature='f'*64),
                       dict(parent_return_receipt={'path':'forged','sha256':'invalid'})]:
            bad=copy.deepcopy(report);bad['records'][0].update(change)
            with self.subTest(change=change),self.assertRaises(A.AuditStop):
                A.anytime_accounting(bad,parents,task,lambda a,b:max(30,(a+b)//2),strong)
        bad=copy.deepcopy(parents);bad[-1]['phase']='round-1-0'
        with self.assertRaisesRegex(A.AuditStop,'provider_timeout_is_NULL'):
            A.anytime_accounting(report,bad,task,lambda a,b:max(30,(a+b)//2),strong)
        bad=copy.deepcopy(report);bad['executed_Qwen_candidates']=2
        with self.assertRaisesRegex(A.AuditStop,'actual_attempt_counter'):
            A.anytime_accounting(bad,parents,task,lambda a,b:max(30,(a+b)//2),strong)

    def test_sealed_clean_timeout_binding_still_reaches_unchanged_strict_usage_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();taskcfg,expected=GatewaySourceClosureContracts().fixture(root)
            output=root/'output';folder=output/'gateway-1';folder.mkdir(parents=True)
            row=dict(output=str(output))
            def fixture(parent_change=None,call_change=None,forged=False):
                supervisor=dict(status='ok',exit_code=0,cleanup_confirmed=True,error_history=[],solver_budget_seconds=None,
                    cleanup_observation=dict(denial_count=0,unresolved=[]))
                supervisor.update(parent_change or {})
                sup=save(folder/'supervisor.json',supervisor)
                request=save(folder/'request.json',dict(schema='qwen-three-hour-single-gateway-v1',call_number=1,
                    source_files=dict(expected),canonical_root=taskcfg['canonical_root'],output=str(folder/'result.json'),
                    clock=dict(taskcfg['clock'],provider_deadline_monotonic=280.),timeout=180,
                    prompt='synthetic system',context=dict(actual_resources=dict(learner_threads=2,worker_RSS_MiB=1536,whole_RSS_MiB=2048))))
                call=dict(status='error',exception_type='TimeoutError',attempts=1,usage=None,usage_complete=None)
                call.update(call_change or {})
                result=save(folder/'result.json',dict(schema='qwen-three-hour-single-gateway-result-v1',request_sha256=request['sha256'],
                    call_number=1,content=None,call=call))
                record=dict(round=1,signature=None,status='provider_timeout',decision='discard',scores=None,
                    error_type='TimeoutError',hypothesis=None,checkpoint=None,worker_attempted=False,parent_return_receipt=dict(sup))
                if forged:record['parent_return_receipt']['sha256']='f'*64
                report=dict(gateway_calls=1,records=[record],http_attempts_reported=1,http_attempts_complete=True,usage_complete=False,
                    usage=[{k:call.get(k)for k in ('status','attempts','usage','usage_complete','finish_reason','reasoning_effort_requested','response_model')}])
                seal=dict(files_sha256={ref['path']:ref['sha256']for ref in (request,result,sup)})
                return report,seal
            report,seal=fixture()
            with self.assertRaisesRegex(A.AuditStop,'provider_failed'):
                A.verify_usage(row,report,seal,taskcfg,lambda:None)
            self.assertFalse(report['usage_complete']);self.assertIsNone(report['usage'][0]['usage'])
            for parent_change,call_change,forged in [({}, {}, True),({'status':'child_failed','exit_code':1},{},False),
                    ({'cleanup_confirmed':False},{},False),({'error_history':['observation_denied']},{},False),
                    ({},{'exception_type':'RuntimeError'},False),({},{'attempts':None},False)]:
                report,seal=fixture(parent_change,call_change,forged)
                with self.subTest(parent=parent_change,call=call_change,forged=forged),self.assertRaisesRegex(A.AuditStop,
                        'provider_timeout_actual_clean_return_binding_changed|provider_parent_or_technical_environment_unqualified'):
                    A.verify_usage(row,report,seal,taskcfg,lambda:None)


'''
needle_main="if __name__=='__main__':unittest.main()"
assert tests.count(needle_main)==1
newtests=tests.replace(needle_main,addition+needle_main,1)
(NEW/'test_audit_contracts.py').write_bytes(newtests.encode('utf-8'))
def methods(src):
    ans={}
    for cls in ast.parse(src).body:
        if isinstance(cls,ast.ClassDef):
            for n in cls.body:
                if isinstance(n,ast.FunctionDef)and n.name.startswith('test_'):ans[cls.name+'.'+n.name]=n
    return ans
oldmethods=methods(tests);newmethods=methods(newtests)
assert all(dump(newmethods[k])==dump(v)for k,v in oldmethods.items())
assert len(newmethods)==len(oldmethods)+2==30
ti=ast.parse(newtests);ti.body=[n for n in ti.body if not(isinstance(n,ast.ClassDef)and n.name=='CleanProviderTimeoutAuditContracts')]
assert dump(ti)==dump(ast.parse(tests))
allmethods={k:hashlib.sha256(dump(v).encode()).hexdigest()for k,v in {**newmethods,**methods((NEW/'test_csv_role_contracts.py').read_text(encoding='utf-8'))}.items()}
assert len(allmethods)==32
patch=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='R6/audit_final.py',tofile='R7/audit_final.py'))
patch+=''.join(difflib.unified_diff(tests.splitlines(True),newtests.splitlines(True),fromfile='R6/test_audit_contracts.py',tofile='R7/test_audit_contracts.py'))
(NEW/'R7-provider-timeout-accounting-only.patch').write_bytes(patch.encode('utf-8'))
(NEW/'prepare_source.py').write_bytes(Path(__file__).read_bytes())
save(NEW/'source-proof.json',dict(schema='QH-auditor-R7-source-inverse-proof-v1',whole_R6_runtime_text_and_AST_inverse_exact=True,
    changed_functions=['anytime_accounting','verify_usage'],all_other_functions_classes_AST_exact=True,
    usage_summary_AST_exact=True,whole_old_test_module_inverse_exact=True,old30_test_method_AST_exact=True,
    CSV_test_bytes_exact=sha(NEW/'test_csv_role_contracts.py')==sha(OLD/'test_csv_role_contracts.py'),
    primitive_bytes_exact=sha(NEW/'r4_primitives.py')==sha(OLD/'r4_primitives.py'),prepared_methods=allmethods,
    prepared_count=32,entrypoint_counts=[30,2],actual_executions=0,history_external_original_paths=True))
save(NEW/'protocol.json',dict(schema='QH-auditor-R7-provider-timeout-ledger-source-protocol-v1',status='SOURCE_ONLY_NOT_READY',
    original_task_seconds=4800,original_common_seconds=10800,admission_margin_seconds=270,
    source_schema='qwen-iterative-task-v2-anytime',new_ledger_row='provider_timeout discardedNULL with no actual worker',
    source_proof='Existing sealed clean parent/source/request/result checks plus exact parent_return_receipt and typed raw TimeoutError.',
    strict_final_usage_summary_unchanged=True,error_or_incomplete_usage_cannot_qualify_metrics=True,
    prepared_method_count=32,entrypoint_counts=[30,2],actual_tests=0,actual_imports=0,actual_READY=None,actual_clock=None,actual_metrics=None))
(NEW/'README.txt').write_bytes(b'R7 SOURCE ONLY / NOT READY.\nProvider timeout records are failed NULL, not worker/candidate calls.\nActual sealed clean supervisor/result binding is verified.\nUnchanged final usage_summary still rejects every statuserror/incomplete usage; no qualified metrics after timeout.\n32 prepared methods, same2 entrypoints; zero author executions/imports/fits/API.\nAll214 R6 files+handoff preserved by exact external original-path pins, no historical tree duplication.\n')
extra={
 'qwen-three-hour-independent-audit-source-review-r6.json':'6fa28b1348c9b57e67a73a0563e0918758f6d15929cbff0524e951ca6483eb0d',
 'qwen-three-hour-autoresearch-next-dev-r10/source-handoff-final.json':'2ef1d62f1ad923dc00382502c9ece525df56c1304353dfa3d50ff31fa163c61c',
 'qh5-core-r10-audit-contract-source-review-r1.json':'cd4e6a47c77a498daa5a9af27d4e18ec42fa86e7ff623011706df222ec6e5fe7',
 'qh5-clean-provider-timeout-root-source-decision-r1.json':'e179f316b12d476cbd7860dfa573fef95c6ec21d24cac34834db3d4717163754'}
for rel,s in extra.items():assert sha(WORK/rel)==s;external[rel]=s
for p in NEW.glob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
files={p.name:sha(p)for p in sorted(NEW.iterdir())if p.is_file()}
handoff=dict(schema='qwen-three-hour-independent-audit-R7-source-handoff-v1',status='FROZEN_SOURCE_ONLY_NOT_READY_PENDING_INDEPENDENT_PEER',
    files_sha256=files,external_refs_sha256=external,external_refs_origin='WORK-relative immutable original paths',
    runtime='audit_final.py',test_entrypoints=['test_audit_contracts.py','test_csv_role_contracts.py'],prepared_method_count=32,
    prepared_method_counts_by_entrypoint=[30,2],prepared_methods=allmethods,old30_method_AST_exact=True,
    whole_R6_runtime_inverse_exact=True,whole_old_test_module_inverse_exact=True,usage_summary_unchanged=True,
    final_statusok_and_complete_usage_and_all_ML_resource_source_cleanup_gates_unchanged=True,
    failed_provider_history_cannot_qualify_final_metrics=True,actual_imports=0,actual_tests=0,actual_models=0,actual_API=0,
    actual_PID_scans=0,actual_array_truth_prediction_metric_reads=0,actual_clock=None,actual_READY=None,actual_metrics=None)
save(NEW/'source-handoff.json',handoff)
for rel,s in base['files_sha256'].items():assert sha(OLD/rel)==s
print(json.dumps(dict(handoff_sha256=sha(NEW/'source-handoff.json'),runtime_sha256=sha(NEW/'audit_final.py'),
    tests_sha256=sha(NEW/'test_audit_contracts.py'),local=len(files),external=len(external),prepared=32,executed=0)))
