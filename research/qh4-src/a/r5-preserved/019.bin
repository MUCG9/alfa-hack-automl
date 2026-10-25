"""Stdlib SOURCE/AST/hash census only. Never imports auditor/tests/candidate."""
from pathlib import Path
import argparse
import ast
import copy
import difflib
import hashlib
import json

P=Path(__file__).resolve().parent
ROOT=P.parent.parent
OLD=P/'source-evidence/r2'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ah(node):return hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
def ref(path):return dict(path=str(Path(path).resolve().relative_to(ROOT)).replace('\\','/'),sha256=sha(path))
def save(name,value):(P/name).write_bytes((json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())


def main(a):
    assert not (P/'source-handoff.json').exists(),'frozen_packet_no_rewrite'
    old=json.loads((OLD/'source-handoff.json').read_text('utf-8'))
    assert sha(OLD/'source-handoff.json')=='c751420ad4df2411ee50f6c7789b4f554206954575ae7c5d2f4702cf81984edc'
    for n,h in old['files_sha256'].items():assert sha(OLD/n)==h
    assert sha(OLD/'independent-review-r2.json')=='0a989362cff22dfe3d3ce25440898285faffbffb366f40ddb56a12412793a68c'
    for n in ['r4_primitives.py','primitive-provenance.json','test_csv_role_contracts.py','binding.template.NOT_READY.json']:
        assert (P/n).read_bytes()==(OLD/n).read_bytes()
    before=ast.parse((OLD/'audit_final.py').read_text('utf-8'));after=ast.parse((P/'audit_final.py').read_text('utf-8'))
    defs=lambda tr:{n.name:n for n in tr.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    olddefs,newdefs=defs(before),defs(after)
    changed={n for n in olddefs if ah(olddefs[n])!=ah(newdefs[n])}
    added=set(newdefs)-set(olddefs)
    assert changed=={'verify_all_seals','parent_records','usage_summary','verify_task'}
    assert added=={'anytime_time_goal','anytime_accounting'}
    constants={'GATEWAY_LIMIT','CALLBACK_LIMIT','CORE_FILES_LIMIT'}
    inv=copy.deepcopy(after);inv.body=[copy.deepcopy(olddefs[n.name]) if isinstance(n,(ast.ClassDef,ast.FunctionDef))
        and n.name in changed else n for n in inv.body if not (isinstance(n,ast.FunctionDef) and n.name in added)
        and not (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in constants for t in n.targets))]
    assert ah(inv)==ah(before)
    tb=ast.parse((OLD/'test_audit_contracts.py').read_text('utf-8'));ta=ast.parse((P/'test_audit_contracts.py').read_text('utf-8'))
    tinv=copy.deepcopy(ta);tinv.body=[n for n in tinv.body if not (isinstance(n,ast.FunctionDef) and n.name=='anytime_fixture')
        and not (isinstance(n,ast.ClassDef) and n.name=='AnytimeAuditContracts')]
    assert ah(tinv)==ah(tb)
    methods={};sources={}
    for q in sorted(P.glob('*.py')):
        tree=ast.parse(q.read_text('utf-8'));compile(tree,str(q),'exec')
        sources[q.name]=dict(sha256=sha(q),AST_sha256=ah(tree))
        for cl in tree.body:
            if isinstance(cl,ast.ClassDef):methods.update({cl.name+'.'+m.name:ah(m) for m in cl.body
                if isinstance(m,ast.FunctionDef) and m.name.startswith('test_')})
    base_methods=json.loads((OLD/'source-proof.json').read_text('utf-8'))['methods_AST_sha256']
    assert len(base_methods)==17 and len(methods)==25 and all(methods[n]==h for n,h in base_methods.items())
    core=Path(a.core_handoff).resolve();peer=Path(a.core_review).resolve()
    assert sha(core)==a.core_sha256 and sha(peer)==a.core_review_sha256
    ch=json.loads(core.read_text('utf-8'));assert ch['actual_clock'] is None and ch['actual_metrics'] is None
    for n,h in ch['files_sha256'].items():assert sha(core.parent/n)==h
    core_refs=[ref(core),ref(peer)]+[ref(core.parent/n) for n in
        ['research_loop.py','task_entry.py','gateway_child.py','provider_environment.py','r5_worker_runtime.py','native-census.json']]
    refs=old['external_source_refs']+[ref(OLD/'source-handoff.json'),ref(OLD/'independent-review-r2.json')]+core_refs
    for r in refs:assert sha(ROOT/r['path'])==r['sha256']
    patch=''.join(difflib.unified_diff((OLD/'audit_final.py').read_text('utf-8').splitlines(True),
        (P/'audit_final.py').read_text('utf-8').splitlines(True),fromfile='frozen-R2/audit_final.py',tofile='R3/audit_final.py'))
    (P/'R3-anytime-only.patch').write_bytes(patch.encode())
    save('R2-preservation.json',dict(handoff=ref(OLD/'source-handoff.json'),review=ref(OLD/'independent-review-r2.json'),
        all_R2_local_files_exact=old['files_sha256'],original_directory_unchanged=True))
    save('source-proof.json',dict(schema='qwen-three-hour-anytime-auditor-R3-source-proof-v1',
        status='SOURCE_ONLY_NOT_EXECUTED',changed_existing_definitions=sorted(changed),new_definitions=sorted(added),
        constants=dict(GATEWAY_LIMIT=4800,CALLBACK_LIMIT=19204,CORE_FILES_LIMIT=20000),
        whole_runtime_inverse_to_frozen_R2_AST_exact=True,whole_test_inverse_to_frozen_R2_AST_exact=True,
        R2_runtime_AST_sha256=ah(before),source_AST=sources,methods_AST_sha256=methods,
        prepared_methods=25,old17_method_AST_exact=True,existing_R4_primitives_and_CSV_role_fixture_bytes_exact=True,
        same_two_fixture_entrypoints=['test_audit_contracts.py','test_csv_role_contracts.py'],
        physical_bounds='report/parentJSON32MiB; actualcore20k; worker1536/whole2048MiB RSS retained; no diskcapacity provision',
        qualification='semantic4800/19204 are independent safety maxima, not capacity or elapsed time',
        actual_imports_tests_fits_API_data_PID_Git_clock=0,actual_archive_root_READY_clock_metrics=None))
    protocol=json.loads((OLD/'protocol.json').read_text('utf-8'))
    protocol.update(status='FROZEN_R3_SOURCE_ONLY_NOT_READY',prepared_contracts=25,
        producer_report_schema='qwen-iterative-task-v2-anytime',producer_core=ref(core),producer_core_review=ref(peer),
        semantic_bounds=dict(gateway=4800,parent_callback=19204),core_file_limit=20000,
        selected_rule='Exact last completed current-run checkpoint; all primary/freshconfirmation/median/full refs match actual parent ledgers.',
        unfinalized_rule='Ordinary confirmed timeout/invalid/quality/budget leaves previous complete selection; scoresNULL and every actualcallback accounted.',
        time_goal='Actual original task admission margin<=85s and elapsed>=4715, plus observed task supervisor end>=original task deadline-85.',
        actual_total_disk_capacity_qualified=None,actual_learner_fits=None)
    save('protocol.json',protocol)
    (P/'README.txt').write_bytes(('''R3 independent ANYTIME saved-artifact adapter — SOURCE ONLY

The exact R2 c751 packet and peer0a989 remain under source-evidence/r2 and in the
original directory. R4/C5/LOSS numerical primitives, role-scoped CSV parsing,
both-task pretruth seals, source qualification, original10800/audit600 clocks,
typed parent cleanup/origin/RSS and actualHTTP usage formulas stay unchanged.

The new bounded accounting consumes the reviewed time-driven producer schema.
Every actual callback is bound to a control, adaptive pair or checkpoint stage.
Unattempted/duplicate rows have no callback and NULL objective. A partial or
timed-out checkpoint cannot replace the last completed checkpoint's exact raw
recipe, primary, freshconfirmation, recursive-median fullrefit and CSV. All
historical checkpoints/usage/parent ledgers remain checked; none is a learner-fit
counter. Pure accounting checks do not transfer their adaptive feedback as a
blind score. Selected/control cuts and finalCSV still use exact R4 independent
rescore after ALL input/source/core/usage byte barriers.

Semantic4800 gateways/19204 callbacks are safety bounds, not provisioned file,
disk or time capacity. Preserve report/parent32MiB, actual20k corefiles and
1536/2048MiB RSS. Any actualcap/time/source/cleanup gap is nonqualifying with
NULL metrics. No new disk capacity claim, retry, clock, parser or fitting.

The original17 test methods/assertions are AST exact; eight new synthetic
contracts cover completed selection, late timeout, unattempted rows, orphan
refs/cuts, freshmedian/leases, actual timegoal, >64/256 truthfulcounts and finite
bounds. Total25 methods in the SAME two test entrypoints, all PREPARED/0run.
Old iteration_accounting remains for old pure contracts; the R3 runtime uses
anytime_accounting exclusively. Current actual archive/root/READY/clock and all
metrics are NULL. This packet authorizes no experiment or promotion.
''').encode())
    files={str(q.relative_to(P)).replace('\\','/'):sha(q) for q in sorted(P.rglob('*')) if q.is_file()}
    save('source-handoff.json',dict(schema='qwen-three-hour-independent-artifact-audit-source-handoff-v1',revision='R3_ANYTIME_ADAPTER',
        status='FROZEN_SOURCE_ONLY_NOT_READY_PENDING_INDEPENDENT_PEER',files_sha256=files,external_source_refs=refs,
        prepared_method_count=25,fixture_entrypoints=['test_audit_contracts.py','test_csv_role_contracts.py'],
        producer_core=ref(core),producer_core_review=ref(peer),actual_tests_executed=0,actual_candidate_imports=0,
        actual_fits=0,actual_API_calls=0,actual_metrics=None,actual_archive_root_outer_binding=None,actual_clock=None))
    print(json.dumps(dict(handoff=ref(P/'source-handoff.json'),auditor=ref(P/'audit_final.py'),local_pins=len(files),
        external_pins=len(refs),prepared_methods=25,actual_executed=0)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--core-handoff',required=True);p.add_argument('--core-sha256',required=True)
    p.add_argument('--core-review',required=True);p.add_argument('--core-review-sha256',required=True)
    main(p.parse_args())
