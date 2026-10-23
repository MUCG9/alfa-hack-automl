"""Source-only pre-label gate. No scoring/target reader or application imports.
Future independent judge must call this BEFORE opening heldout label files.
No availability boolean, parent-reported metric or old R4 global split certifies
an outer result. Scope is trusted algorithm-facing I/O/source flow only; no
OS/ACL sandbox requirement or permission flow is introduced by this helper.
"""
from pathlib import Path
import hashlib,json,math,re

MAX_REFS=10000

def need(value,code):
    if not value:raise ValueError(code)

def valid_sha(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None

def digest(path,checkpoint):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(2**20),b''):checkpoint();h.update(block)
    checkpoint();return h.hexdigest()

def verify_prelabel_seal(plan,seal,agent_root,judge_vault,checkpoint,*,work_root):
    """Plan/seal are root SHA-bound objects, not mutable agent assertions.
    All artifacts/source/refit/control/inner-audit ownership proof must have been
    closed and sealed by a parent independent of the agent. No labels are read.
    """
    agent=Path(agent_root).resolve();vault=Path(judge_vault).resolve()
    work=Path(work_root).resolve()
    need(not vault.is_relative_to(agent) and not agent.is_relative_to(vault),'label_vault_not_disjoint')
    need(agent.is_relative_to(work) and vault.is_relative_to(work),'declared_work_scope_required')
    need(plan['schema']=='outer-holdout-judge-task-plan-v3' and seal['schema']=='outer-prelabel-seal-v3','per_task_actual_outer_contract_required')
    need(plan['kind'] in ('regression','classification') and seal['kind']==plan['kind'],'task_kind_mismatch')
    for field in ['outer_partition_sha256','partition_binding_sha256']:
        need(valid_sha(plan.get(field)) and seal.get(field)==plan[field],'missing_or_mismatched_actual_SHA:'+field)
    need(valid_sha(plan.get('protected_control_recipe_sha256')),'actual_protected_control_SHA_required')
    need(seal['outer_partition_sha256']==plan['outer_partition_sha256'],'outer_partition_changed')
    need(seal['candidate_terminal_cleanup_confirmed'] is True and seal['control_terminal_cleanup_confirmed'] is True,'prediction_producer_not_closed')
    need(seal['inner_audit_passed'] is True and seal['roundtrip_verified'] is True,'inner_or_roundtrip_gate_missing')
    need(type(seal['algorithm_label_access_attempts_before_seal']) is int
         and seal['algorithm_label_access_attempts_before_seal']==0
         and seal['judge_labels_opened_before_seal'] is False,'prelabel_algorithm_IO_violation')
    # These flags require independent raw access/closure receipts pinned below;
    # they alone never establish proof or authorize a target-file open.
    required={'candidate_selected_recipe','candidate_iteration_tree','candidate_final_job','candidate_prediction_CSV',
        'control_recipe','control_iteration_tree','control_final_job','control_prediction_CSV',
        'derived_inner_audit','roundtrip_receipt','candidate_owned_closure','control_owned_closure','label_access_receipt'}
    artifacts=seal.get('artifacts');sources=plan.get('immutable_sources')
    need(type(artifacts) is dict and 0<len(artifacts)<=MAX_REFS and type(sources) is dict
         and 0<len(sources)<=MAX_REFS,'bounded_actual_ref_maps_required')
    need(required<=set(artifacts),'prelabel_artifact_bindings_incomplete')
    all_refs={}
    def add_ref(name,h):
        need(type(name) is str and 0<len(name)<=4096 and valid_sha(h),'invalid_artifact_path_or_SHA')
        path=Path(name);p=(path if path.is_absolute() else work/path).resolve()
        need(p.is_relative_to(work),'reference_outside_declared_work_scope')
        need(p!=vault and not p.is_relative_to(vault),'prelabel_gate_attempted_vault_read')
        if p in all_refs:need(all_refs[p]==h,'conflicting_SHA_for_same_canonical_path')
        else:all_refs[p]=h
    for path,h in sources.items():add_ref(path,h)
    for ref in artifacts.values():
        need(type(ref) is dict and len(ref)==2 and set(ref)=={'path','sha256'},'invalid_artifact_reference')
        add_ref(ref['path'],ref['sha256'])
    need(len(all_refs)<=MAX_REFS,'combined_ref_bound')
    for p,h in all_refs.items():
        checkpoint()
        need(digest(p,checkpoint)==h,'prelabel_source_or_artifact_changed')
    for key in ['original_start_unix','original_start_monotonic','original_deadline_unix','original_deadline_monotonic']:
        need(type(plan[key]) in (int,float) and math.isfinite(plan[key]) and plan[key]>0,'actual_common_clock_required')
    need(abs(plan['original_deadline_unix']-plan['original_start_unix']-10800)<=1e-6
         and abs(plan['original_deadline_monotonic']-plan['original_start_monotonic']-10800)<=1e-6,'shared10800_clock_changed')
    need(type(seal['sealed_unix']) in (int,float) and math.isfinite(seal['sealed_unix'])
         and type(seal['sealed_monotonic']) in (int,float) and math.isfinite(seal['sealed_monotonic']),'finite_seal_clock_required')
    need(seal['sealed_unix']>=plan['original_start_unix'] and seal['sealed_monotonic']>=plan['original_start_monotonic'],'seal_before_attempt')
    need(seal['sealed_unix']<=plan['original_deadline_unix'] and seal['sealed_monotonic']<=plan['original_deadline_monotonic'],'seal_after_original_clock')
    need(seal['control_recipe_sha256']==plan['protected_control_recipe_sha256'],'strong_control_changed')
    need(seal['candidate_input_partition_sha256']==seal['control_input_partition_sha256']==plan['outer_partition_sha256'],'control_not_same_outer_training')
    checkpoint()
    return dict(status='prelabel_hash_inventory_checked_not_a_label_permit',outer_metrics=None,
        authorizes_label_read=False,labels_read_by_this_gate=False,
        trusted_materializer_original_label_reads_are_a_separate_declared_role=True,
        independent_semantic_inner_and_algorithm_IO_receipt_validation_still_required=True)

if __name__=='__main__':
    raise SystemExit('SOURCE ONLY: no target reader/numeric judge implemented; this module never scores a real dataset.')
