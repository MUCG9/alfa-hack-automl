"""Source-only prospective packet contract, NOT an operational campaign builder.
Outer table/split primitives live in outer_materializer_draft.py. A full driver
must first prove actual-reader parity, derived-only input flow on every worker,
derived-inner audit semantics and seal-before-judge contracts. This source never
materializes inputs or starts a research clock. No runtime/application imports.
"""
import hashlib,json,math,re
from pathlib import Path

PHASES=[('setup_source_exact_materialize',900),('regression_agent',2100),
    ('classification_agent',6000),('regression_control_refit',180),
    ('classification_control_refit',1200),('inner_and_outer_audit',300),('terminal_cleanup',120)]

def declared_budget():
    total=sum(cap for _,cap in PHASES)
    if total!=10800:raise ValueError('common_budget_not10800')
    return dict(common_seconds=total,phase_caps_seconds=dict(PHASES),
        absolute_start_unix=None,absolute_deadline_unix=None,
        setup=dict(source=600,exact=180,materializer_and_new_contracts=120),
        parent_accounting='Every phase cap includes its startup/checks/cleanup/receipts; no reinvestment/reset/retry. First HPO worker must prove full requested900/2100 available plus export reserve. Admission requires full remaining mandatory caps.')

def admit_phase(index,now_unix,now_monotonic,start_unix,start_monotonic):
    """Future pure admission arithmetic; does not read a clock or grant launch."""
    if type(index) is not int or not 0<=index<len(PHASES):raise ValueError('invalid_phase')
    values=[now_unix,now_monotonic,start_unix,start_monotonic]
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):raise ValueError('invalid_clock')
    if abs((now_unix-start_unix)-(now_monotonic-start_monotonic))>5:raise ValueError('clock_disagreement')
    elapsed=max(now_unix-start_unix,now_monotonic-start_monotonic)
    if elapsed<0:raise ValueError('clock_before_start')
    if index==0:
        # Clock assignment itself begins setup. Its startup/receipt work spends
        # the SAME900s, never demands a fresh900s after time has already passed.
        if elapsed>=PHASES[0][1]:raise ValueError('setup_cap_exhausted')
        return dict(phase=PHASES[0][0],phase_cap_seconds=900,
            phase_remaining_seconds=900-elapsed,phase_start_is_common_start=True,
            reserved_future_phase_caps_seconds=sum(cap for _,cap in PHASES[1:]))
    required=sum(cap for _,cap in PHASES[index:])
    if min(start_unix+10800-now_unix,start_monotonic+10800-now_monotonic)<required:raise ValueError('mandatory_remaining_caps_unavailable')
    return dict(phase=PHASES[index][0],phase_cap_seconds=PHASES[index][1],mandatory_remainder_including_phase=required)

def assert_plan_template(plan):
    if plan.get('schema')!='outer-holdout-protocol-template-v3':raise ValueError('new_derived_plan_required')
    if plan.get('historical_R4_global_split_refs_reused') is not False:raise ValueError('old_global_splits_forbidden')
    if plan.get('researcher_unseen') is not False:raise ValueError('public_reuse_must_be_explicit')
    if plan.get('outer_metrics') is not None:raise ValueError('source_preparation_has_no_metrics')
    if plan.get('actual_inputs_materialized') is not False:raise ValueError('not_a_source_only_template')
    return declared_budget()

def valid_sha(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None

def instantiate_task_judge_plan(template,kind,binding,common_clock,immutable_sources,classes):
    """Future pure instantiation from actual frozen metadata, never raw rows.
    This does not create a clock, validate numeric scores, open files or certify
    semantic access/owner/inner proofs. It resolves the combined/per-task schema.
    """
    assert_plan_template(template)
    if kind not in ('regression','classification'):raise ValueError('ordinary_task_kind_required')
    clock_keys={'original_start_unix','original_start_monotonic','original_deadline_unix','original_deadline_monotonic'}
    if type(common_clock) is not dict or len(common_clock)!=4 or set(common_clock)!=clock_keys:raise ValueError('actual_common_clock_required')
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in common_clock.values()):raise ValueError('finite_positive_common_clock_required')
    for axis in ('unix','monotonic'):
        if abs(common_clock['original_deadline_'+axis]-common_clock['original_start_'+axis]-10800)>1e-6:raise ValueError('original10800_clock_required')
    required=('original_train_sha256','outer_positions_sha256','row_mapping_sha256',
        'original_feature_hash_vector_sha256','original_dtype_schema_sha256',
        'ordered_feature_schema_sha256','class_schema_sha256','split_producer_sha256')
    if type(binding) is not dict or any(not valid_sha(binding.get(k)) for k in required):raise ValueError('actual_nonnull_partition_bindings_required')
    inputs=binding.get('derived_inputs_sha256')
    names={'task.md','train.csv','test.csv','sample_submission.csv','data_dictionary.csv'}
    if type(inputs) is not dict or len(inputs)!=5 or set(inputs)!=names or any(not valid_sha(h) for h in inputs.values()):raise ValueError('derived_five_input_SHAs_required')
    ref=template['fixed_strong_control']['recipes'][kind]
    if binding.get('protected_control_recipe_sha256')!=ref['sha256']:raise ValueError('unchanged_strong_control_required')
    if type(immutable_sources) is not dict or not 0<len(immutable_sources)<=10000 or any(type(n) is not str or not valid_sha(h) for n,h in immutable_sources.items()):raise ValueError('actual_immutable_sources_required')
    if type(classes) is not list or len(classes)!=(10 if kind=='classification' else 0):raise ValueError('current_task_class_schema_required')
    if any(type(c) is not str for c in classes) or len(set(classes))!=len(classes):raise ValueError('ordered_class_schema_required')
    partition={k:binding[k] for k in required};partition['derived_inputs_sha256']=dict(inputs)
    combined=hashlib.sha256(json.dumps(partition,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return dict(schema='outer-holdout-judge-task-plan-v3',kind=kind,
        outer_partition_sha256=binding['outer_positions_sha256'],partition_binding_sha256=combined,
        partition_binding=partition,protected_control_recipe_sha256=ref['sha256'],
        protected_control_recipe_signature=ref['signature'],classes=list(classes),
        immutable_sources=dict(immutable_sources),**dict(common_clock),
        outer_metrics=None,researcher_unseen=False,semantic_inner_and_algorithm_IO_validation_pending=True,
        authorizes_label_read=False)

if __name__=='__main__':
    raise SystemExit('SOURCE/PLAN ONLY: operational driver deliberately unavailable until listed technical contracts are implemented and verified; no input build, clock or model job performed.')
