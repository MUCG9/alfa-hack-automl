"""Source/AST metadata only. Never import or call any candidate/test function."""
from pathlib import Path
import ast
import hashlib
import json

P=Path(__file__).resolve().parent
WORK=P.parent.parent


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ast_hash(node):return hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
def save(name,value):
    (P/name).write_bytes((json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8'))
def ref(path):return dict(path=str(path.relative_to(WORK)).replace('\\','/'),sha256=digest(path))
def definitions(path):
    return {n.name:n for n in ast.parse(path.read_text('utf-8')).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}


def main():
    handoff=P/'source-handoff.json'
    if handoff.exists():raise RuntimeError('already_frozen_no_rewrite')
    provenance=json.loads((P/'primitive-provenance.json').read_text('utf-8'))
    primitive=definitions(P/'r4_primitives.py');witness={}
    for source_key,names in [('R4_source',provenance['selected_names']),
                             ('C5_resource_source',['verified_terminal']),
                             ('loss_source',provenance['loss_selected_names'])]:
        source=WORK/Path(provenance[source_key]['path']);assert digest(source)==provenance[source_key]['sha256']
        original=definitions(source)
        for name in names:
            assert ast_hash(primitive[name])==ast_hash(original[name])
            witness[source_key+'.'+name]=ast_hash(original[name])
    sources={}
    for path in sorted(P.glob('*.py')):
        tree=ast.parse(path.read_text('utf-8'));compile(tree,str(path),'exec')
        sources[path.name]=dict(sha256=digest(path),whole_AST_sha256=ast_hash(tree))
    tests=ast.parse((P/'test_audit_contracts.py').read_text('utf-8'))
    methods={c.name+'.'+n.name:ast_hash(n) for c in tests.body if isinstance(c,ast.ClassDef)
             for n in c.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')}
    assert len(methods)==15
    auditor=definitions(P/'audit_final.py');body=auditor['main']
    calls={name:min(n.lineno for n in ast.walk(body) if isinstance(n,ast.Call)
            and isinstance(n.func,ast.Name) and n.func.id==name)
           for name in ('verify_all_seals','source_qualification','numerical_primitives','verify_task')}
    assert calls['verify_all_seals']<calls['source_qualification']<calls['numerical_primitives']<calls['verify_task']
    proof=dict(schema='qwen-three-hour-independent-audit-source-proof-v1',status='SOURCE_ONLY_NOT_EXECUTED',
        source_AST=sources,reused_definition_AST_sha256=witness,
        all_selected_R4_C5_and_LOSS_definitions_AST_exact=True,
        excluded_legacy_predicates=['verify_task','hpo_counts','four-stage/all-four-arm predicates','main'],
        main_source_order=calls,all_seals_and_qualification_precede_numerical_import_and_truth=True,
        prepared_method_count=len(methods),methods_AST_sha256=methods,actual_tests_executed=0,
        actual_candidate_imports=0,actual_fits=0,actual_API_calls=0,actual_data_or_array_reads=0,
        preparation='stdlib source reads, JSON/hash/AST/compile-as-text only; no code under test executed',
        whole_composition_runtime_qualification=None,actual_archive_root_and_outer_binding=None)
    save('source-proof.json',proof)
    save('binding.template.NOT_READY.json',dict(schema='qwen-three-hour-independent-audit-private-v1',
        readiness='NOT_READY',missing_bindings=['qualified repaired archive/root/FINAL post-tool receipt',
            'actual same original10800 common and audit600 clock','both runtime task manifests/specs/supervisors',
            'both complete all-source/input/task-output seals','immutable union and source peers/root actual admission'],
        immutable_files=None,clock=None,source_qualification=dict(archive=None,root=None,confirmation=None),tasks=None))
    save('protocol.json',dict(schema='qwen-three-hour-independent-artifact-audit-protocol-v1',
        status='FROZEN_SOURCE_ONLY_NOT_READY',common_seconds=10800,audit_parent_seconds=600,
        auditor_child_seconds=570,cleanup_reserve_seconds=300,root60_inside_cleanup300=True,
        task_order=['regression','classification'],actual_clock=None,
        task_row_fields=['kind','task_manifest','spec','output','report','terminal','supervisor','seal'],
        core_seal_schema='qwen-three-hour-task-core-seal-v1',
        core_seal_fields=['schema','kind','task_manifest','output','files_sha256','immutable_files_sha256'],
        parent_result_schema='qwen-three-hour-parent-result-v1',
        actual_parent_callback_count_separate_from_actual_learner_fit_count=True,
        all_immutable_sources_inputs_two_task_manifests_and_both_complete_output_trees_before_truth=True,
        independent_cut_audit='selected and actual initial strong control on SAME fixed42/43; fresh selected43; recursive median of actual42+fresh43 then fullrefit CSV',
        cut_jobs_fit_iterations=None,legacy_R4_formulas_unchanged=True,
        class_gates='strict MacroF1 improvement on BOTH cuts; inherited support>=100 loss tolerance0.01 and positive ex-rarest delta on BOTH',
        regression_gate='strict RMSE improvement on BOTH cuts; no mean-selected exception',
        quality_global_AND_is_conservative_summary_only=True,
        per_task_comparisons_retained=True,technical_success_does_not_require_quality_improvement=True,
        requested_reasoning_is_backend_attestation=False,complete_actual_HTTP_attempts_and_token_usage_required=True,
        failures_and_missing_bindings='STOP; all comparative/quality metrics NULL',
        API_calls=0,new_model_fits=0,promotion=False,submit=False,
        resource_scope='actual parent/supervisor sampled stable known RSS; not OS lifetime peak or complete external measurement',
        adaptive_validation='inner-loop feedback and final cuts reuse public validation; independent final rescore is not blind/official',
        actual_runtime_result=None,actual_archive_qualification=None))
    readme='''Source-only two-task independent final artifact audit

This packet is NOT READY and has not imported candidates, executed tests, read
real data/arrays/truth/predictions, fitted models, called a provider or assigned
an experiment clock. Fifteen synthetic metadata/mock methods are PREPARED only.

Future invocation (only after root review, actual qualification and both seals):
  <pinned-python> -B -X utf8 audit_final.py --manifest <ABS> \\
    --manifest-sha256 <ACTUAL> --self-sha256 <ACTUAL> --output <NEW-ABS>
The outer owns the original10800 clock, audit600 (child570), resource/ownership
observations, environment/credentials removal and cleanup300 (root60 inside).
The auditor creates no independent allowance, process, API client or learner.

Before numerical R4 import or target/prediction parsing, every immutable file
and BOTH complete task-output inventories are rehashed; both runtime manifests
must be in the same immutable map copied exactly to both core seals. Task rows
are ordered regression/classification and use exactly the fields in protocol.
Each supervisor is the actual saved record, exit0 with confirmed clean closure.
Source qualification binds the actual repaired archive/root and FINAL post-tool
receipt, including actual root/tool and wrapper exit0. An atomic pending receipt
does not replace final post-tool confirmation. Actual refs remain NULL here.

Exact AST-selected R4 manual metrics, row/ID/class/probability/mixture/CSV gates,
C5 terminal resource bridge and LOSS fitting receipts are pinned with provenance.
No old whole-agent HPO/four-stage predicate is inherited. Cut fit_iterations must
be absent/NULL; fullrefit uses the recursive median of actual selected42 and fresh
selected43 trees. Raw parent-job/result/source/cut/spec/cap/clock receipts bind
all returned callbacks. Callback calls are not model Popen or nested learner fit
counts; unknown actual learner fits stay NULL. Resource peaks are sampled known
RSS, never an OS lifetime peak claim. Missing/uncertain origins STOP even if late
cleanup left an ordinary final timeout status. Failed objectives remain NULL.

Real gateway requests/results/supervisors and bounded full messages bind actual
attempt counts, complete token usage and response-model fields. Requested
reasoning effort is reported separately and is never backend attestation.

artifact_procedure_passed == technical_procedure_passed. quality_metric is the
independently recomputed selected two-cut mean map. Per-task comparisons are
retained, while quality_gate_passed is a conservative AND of strict improvement
on both cuts and inherited CLASS protections. Valid unchanged strong incumbents
can pass artifact checks with quality false. No result promotes or uploads.
Feedback/public cuts are adaptive reused validation, not blind/official scores.
All source/root/current-cleanup/actual-exit/fresh absence qualification remains
the outer/root's obligation after the auditor exits; no runtime claim is made.
'''
    (P/'README.txt').write_bytes(readme.encode('utf-8'))
    external=[WORK/'work/qwen-three-hour-autoresearch-next-dev-r4/source-handoff-final.json',
        WORK/'work/qwen-three-hour-autoresearch-next-dev-r4/task_entry.py',
        WORK/'work/qwen-three-hour-autoresearch-next-dev-r4/research_loop.py',
        WORK/'work/qwen-three-hour-autoresearch-next-dev-r4/gateway_child.py',
        WORK/'work/qwen-three-hour-autoresearch-next-dev-r4/r5_worker_runtime.py',
        WORK/'work/qwen-three-hour-autoresearch-independent-review-r4.json']
    external += [WORK/Path(provenance[key]['path']) for key in ('R4_source','C5_resource_source','loss_source')]
    local={str(q.relative_to(P)).replace('\\','/'):digest(q) for q in sorted(P.rglob('*')) if q.is_file()}
    save('source-handoff.json',dict(schema='qwen-three-hour-independent-artifact-audit-source-handoff-v1',
        status='FROZEN_SOURCE_ONLY_NOT_READY_PENDING_INDEPENDENT_PEER',files_sha256=local,
        external_source_refs=[ref(q) for q in external],prepared_method_count=len(methods),
        actual_tests_executed=0,actual_candidate_imports=0,actual_fits=0,actual_API_calls=0,
        actual_metrics=None,actual_archive_root_outer_binding=None,actual_clock=None,
        requires='FM independent source peer, root source integration/review, qualified archive, actual sealed pair, original outer clock and actual whole-root closure'))
    print(json.dumps(dict(handoff_sha256=digest(handoff),auditor_sha256=digest(P/'audit_final.py'),
        primitives_sha256=digest(P/'r4_primitives.py'),test_sha256=digest(P/'test_audit_contracts.py'),
        local_pins=len(local),external_pins=len(external),prepared_methods=len(methods),actual_executed=0)))


if __name__=='__main__':main()
