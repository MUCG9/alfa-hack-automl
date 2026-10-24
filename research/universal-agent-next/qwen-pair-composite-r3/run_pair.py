"""Prospective real-Qwen four-slot UAR research pair; inspection by default.
ONE fresh 10800s launch origin, including loader/preflight/setup. No recovery,
resume, reset, submission or implied official-default qualification.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
import re
import signal
import sys
import time
import zipfile

sys.dont_write_bytecode = True
WORK = Path(__file__).resolve().parents[1]
OUTPUT = WORK/'uq1'
BASE, BASE_SHA = 'm4packet/manifest.json', '8faf33cd81c0e864bcf338828c34447000111eda85bc719b8f43312d2babae9a'
COORDINATOR, COORDINATOR_SHA = 'run_lean_mvp_r2.py', '43be86ece6c453641afdcc6f8eccef02d713986e2ac8bf3314756f0bb78e0818'
R4, R4_SHA = 'repaired-mvp-r1-dev/evaluator_r4.py', 'c08e9f0be13a708d67b3266518381d6f1be3b0f43c384ef6425634160d7e2783'
LINEAGE, LINEAGE_SHA = 'champion-seed-next-dev/champion-t5-lineage.json', '408d24be5c884152531552bb0016611eb55b9123aadb4c1a361396d3f7115cf3'
CLOSED_SPECS = {
    'regression': dict(path='la2/A/r/automl_runs/repair4/task_spec.json',sha256='00862f33275bb169d5c88eddc7a0c9037120acd412529cb06995085947720dc9'),
    'classification': dict(path='la2/A/c/automl_runs/repair4/task_spec.json',sha256='d6f2464a4807e01540333c5afd218069d82d4bb821b2b6b0531f6e7c4a1014bf')}
COMMON, SETUP, AUDIT, CLEANUP = 10800, 900, 600, 300
CAPS = {'regression': dict(parent=900, child=870, solver=810, hpo=300),
        'classification': dict(parent=3600, child=3570, solver=3510, hpo=900)}
ORDER = [('A','regression','r'),('B','regression','r'),('A','classification','c'),('B','classification','c')]
FAILURE_TYPE = RuntimeError
RETAINED_TERMINAL = {'kern-prep-r2-exec/terminal-root-closure.json': ('2042c250fefd526acee4ac40cd4d68fc3690220f6d3021bc691b885b5e3ae37e', 56393, 0), 'loss0/terminal-root-closure.json': ('c4916f2e7c7bd38e394bcb2ab33a51daf7a472a2aec8e08ff4b8a79a8fd5ba69', 99080, 0), 'kern-checks/terminal-root-closure.json': ('fef1f0342a991a76c6d1e99ed408d4660f738b11b31726ac78f991757d69f0f0', None, 0), 'queue-checks/terminal-root-closure.json': ('4006102127dd971c97843642754a748fc97199e20505c037f1688a80b8e12d27', None, 1), 'queue-checks-r2/terminal-root-closure.json': ('887a4b82614ca18d4589102a9f385d513e96ff5562dcb56ca3d2f95b6a186c34', None, 0), 'meth03l/terminal-root-closure.json': ('e02fd31162f1db27342895901ebb52764b140d59f9cd7651c9be447283bd3b9d', 63424, 0), 'meth02b/terminal-root-closure.json': ('fe00067cb099fdd4fdcd036861f5c3d55cd1c9ee0ee75bcddf488cfc035fe7f7', 38041, 0), 'meth02/terminal-root-closure.json': ('220e7c93f56eaa4a9c2e09ce70aa3ba406d864686cc68520bf69eace4ed75361', None, 1), 'meth03/terminal-root-closure.json': ('901f3c928d95d992800aef808ff70f84768a456bc23235e0ae63fd539fe159bf', 33253, 0), 'meth01/terminal-root-closure.json': ('2c67361da8f95875b35d124ac6c19d6cccba28c899f1e20dada88f3bec4ea283', 3417, 0), 'cp1/terminal-root-closure.json': ('96f5d956fa235cfd0904d55f67aeeaae8c93a083391fe8b370836f6e39ba309d', 43472, 0), 'cs0/terminal-root-closure.json': ('06d20ce5b1bfd51ceefc924f8d09eb06b4022e9998bcef4d36343cb58669fba8', 79591, 0), 'm4packet/terminal-root-closure.json': ('d19648a53253c0b070fe12068d6eafef5569e2d51332d9b212ef44cc828b9ddc', 65008, 0), 'loss01/terminal-root-closure.json': ('ce6accf1ec6b6f1e0c14dbb0c8913b55538f6a460450cbb2705ae36a37d3bcf3', 68631, 0)}


def need(value, code):
    if not value:
        raise FAILURE_TYPE(code)


def local(name):
    target = (WORK/name).resolve()
    need(not Path(name).is_absolute() and target.is_relative_to(WORK), 'reference_outside_work')
    return target


def sha(path, checkpoint=None):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            if checkpoint is not None:
                checkpoint()
            block = stream.read(2**20)
            if not block:
                break
            digest.update(block)
    if checkpoint is not None:
        checkpoint()
    return digest.hexdigest()


def load(path):
    return json.loads(Path(path).read_text('utf-8'))


def imported(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def merge(pins, name, digest):
    local(name)
    need(isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest), 'invalid_sha256')
    need(name not in pins or pins[name] == digest, 'conflicting_input_pin')
    pins[name] = digest


def solver_argv(arm,kind,retention_sha256):
    cfg=CAPS[kind]
    argv=[sys.executable,'-B','-X','utf8','-u','solution.py','task.md',
        '--four-stage','--strict-runtime','--protect-original-features',
        '--strong-retention','retention.json','--strong-retention-sha256',retention_sha256,
        '--max-experiments','9','--max-planner-calls','2','--max-llm-calls','4',
        '--hpo-trials','8','--hpo-budget',str(cfg['hpo']),'--hpo-sampler','tpe',
        '--validation-strategy','auto','--feature-selection-top-k','32',
        '--planner-mode','staged','--run-name','repair4','--time-budget',str(cfg['solver'])]
    if arm=='B':argv+=['--strict-task-contract']
    return argv


def launch_origin(args):
    fields=(args.start_unix,args.start_monotonic,args.absolute_deadline_unix,args.common_deadline_monotonic)
    need(all(type(v) in (int,float) and math.isfinite(v) for v in fields),'one_actual_launch_clock_required')
    start,mono,unix,end=fields
    need(unix==start+COMMON and end==mono+COMMON,'exact_assigned_common10800_no_reset')
    need(start<=time.time()<start+SETUP and mono<=time.monotonic()<mono+SETUP,'original_setup900_exhausted')
    need(abs((unix-time.time())-(end-time.monotonic()))<=5,'wall_monotonic_clock_disagreement')
    return start,mono,unix,end


def complete_core_seal(directory,coor,check):
    result=coor.core_seal(directory,check)
    checkpoint_path=directory/'authority-checkpoint.json'
    need(checkpoint_path.is_file(),'authority_checkpoint_input_missing')
    result[coor.relative(checkpoint_path)]=sha(checkpoint_path,check)
    # New strict receipts and the closed usage ledger are siblings of repair4.
    # Seal every JSON there, with no ACL bypass or inferred ledger completeness.
    for root in sorted((directory/'automl_runs').glob('run-budget-*')):
        need(root.is_dir() and not root.is_symlink(),'run_budget_symlink_or_non_directory')
        for path in sorted(root.rglob('*')):
            check();need(not path.is_symlink(),'run_budget_artifact_symlink')
            if path.is_file():
                need(path.suffix=='.json' and not path.name.endswith(('.tmp','.pending')),'unexpected_run_budget_artifact')
                result[coor.relative(path)]=sha(path,check)
    check();return result


def bind_source(ref,pins,check):
    need(type(ref) is dict and set(ref)=={'path','sha256'},'typed_source_reference_required')
    need(sha(local(ref['path']),check)==ref['sha256'],'reviewed_gate_driver_changed')
    merge(pins,ref['path'],ref['sha256'])
    return imported('_UAR05_proven_gate_driver',local(ref['path']))


def authority_checkpoint(tasks,source_directory,compiled,module_map,check):
    """Header/text authority and CLOSED-spec recipe compatibility; no rows/fits.

    All elapsed time belongs to the caller's original setup/common checkpoint.
    This does not replace actual B IO02/full discovery/provenance or R4 scoring.
    """
    check();source_directory=source_directory.resolve();previous=list(sys.path)
    required=('automl.task_understanding.early_declaration',
              'automl.task_understanding.metric_contract','automl.search.stages','automl.search.policy')
    modules={}
    try:
        sys.path.insert(0,str(source_directory))
        for name in required:
            check();flat=module_map[name];path=source_directory/(flat+'.py')
            need(path.name in compiled and sha(path,check)==compiled[path.name],'checkpoint_module_not_from_qualified_archive')
            if flat in sys.modules:
                need(Path(sys.modules[flat].__file__).resolve()==path,'checkpoint_flat_module_cache_collision')
            modules[name]=importlib.import_module(flat)
            need(Path(modules[name].__file__).resolve()==path,'checkpoint_flat_module_origin_changed');check()
        declaration=modules[required[0]];metric_module=modules[required[1]]
        stages=modules[required[2]];policy=modules[required[3]];rows={}
        for task in tasks:
            check();kind=task['kind'];root=local(task['source']);task_path=root/'task.md'
            for name,digest in task['files'].items():
                need(sha(root/name,check)==digest,'checkpoint_research_input_copy_changed')
            declared=declaration.bootstrap_early_declaration(task_path,checkpoint=check)
            need(declared.ready_for_projection and declared.status=='resolved','checkpoint_IO03_unresolved')
            need(declared.paths=={'train':'train.csv','test':'test.csv','sample_submission':'sample_submission.csv'}
                 and declared.receipt.get('dictionary_path')=='data_dictionary.csv','checkpoint_explicit_role_paths_changed')
            supplied=declared.declaration
            actual_kind='classification' if supplied.kind in ('classification','binary','multiclass') else supplied.kind
            need(actual_kind==kind and supplied.id_policy=='column' and supplied.output_kind=='value',
                 'checkpoint_task_kind_ID_or_output_not_declared')
            metric=metric_module.resolve_metric_spec(declared.task_text,supplied.kind,
                source='same_qualified_archive_before_first_Qwen')
            metric.require_resolved()
            need(metric.name==('rmse' if kind=='regression' else 'macro_f1')
                 and metric.direction==('minimize' if kind=='regression' else 'maximize')
                 and metric.prediction_kind==('value' if kind=='regression' else 'label'),
                 'checkpoint_explicit_primary_metric_changed')
            ref=CLOSED_SPECS[kind];path=local(ref['path'])
            need(path.stat().st_size<=2**20 and sha(path,check)==ref['sha256'],'checkpoint_closed_spec_changed')
            closed=load(path)
            need(closed['kind']==kind and closed['metric']==metric.name and closed['target']==supplied.target
                 and closed.get('id')==supplied.identifier,'checkpoint_closed_spec_disagrees_with_explicit_authority')
            # Only schema/time metadata is used. No profile, target summary, counts,
            # values or prior outcomes become task/metric authority or prompt facts.
            spec={k:copy.deepcopy(closed[k]) for k in ('kind','metric','target','id','features','numeric_features','categorical_features','text_features',
                'time_column','time_candidate','validation_strategy','task_family') if k in closed}
            packet_ref=task['retention'];need(sha(local(packet_ref['path']),check)==packet_ref['sha256'],
                'checkpoint_retention_input_changed')
            raw=load(local(packet_ref['path']));check()
            loaded=stages.load_retention_packet(local(packet_ref['path']),spec,packet_ref['sha256']);check()
            control=raw['control']['recipe'];anchor=control['components'][0]
            need(loaded['control']==control and policy.signature(control)==raw['control']['recipe_signature'],
                 'checkpoint_raw_whole_control_or_signature_changed')
            need(loaded['mode']==('l1_composite' if kind=='regression' else 'control')
                 and not anchor['params'].get('loss_profile_id'),'checkpoint_fixed_mode_or_unprofiled_HPO_anchor_changed')
            signatures=dict(control=policy.signature(control),unprofiled_HPO_single=policy.signature(anchor),
                            champion=None,retained=None)
            if kind=='regression':
                champion=raw['champion']['recipe'];seed=copy.deepcopy(anchor);seed['params']['loss_profile_id']='lgbm_l1_v1'
                retained=dict(engine='ensemble',params={},hypothesis='Fixed retained L1 SINGLE and prior champion; no weight search',
                              components=[seed,copy.deepcopy(champion)],weights=[.75,.25])
                need(loaded['champion']==champion and loaded['retained']==retained
                     and policy.signature(champion)==raw['champion']['recipe_signature']
                     and policy.signature(retained)==raw['retained_signature'],'checkpoint_raw_CP1_fixed_composite_changed')
                signatures.update(champion=policy.signature(champion),retained=policy.signature(retained))
            else:need(loaded['champion'] is None and loaded['retained'] is None,'checkpoint_CLASS_control_only_required')
            rows[kind]=dict(task_sha256=task['files']['task.md'],role_paths=declared.paths,
                header_sha256=declared.receipt['header_sha256'],dictionary_sha256=task['files']['data_dictionary.csv'],
                metric=dict(name=metric.name,direction=metric.direction,prediction_kind=metric.prediction_kind,status=metric.status,
                    evidence_sha256=hashlib.sha256(json.dumps(metric.to_dict(),sort_keys=True,ensure_ascii=False).encode()).hexdigest()),
                closed_spec=ref,retention_sha256=packet_ref['sha256'],retention_mode=loaded['mode'],signatures=signatures,
                required_primary_slots=7 if kind=='regression' else 5,feature_or_target_rows_parsed=False,input_bytes_hashed=True,
                recipe_validation_scope='closed-spec schema compatibility; actual full-input discovery remains pending')
            check()
        # Dependencies must also resolve to pinned flat source, never installed
        # canonical modules or modular sidecars. This is a one-off setup import.
        imported_pins={}
        for flat in set(module_map.values()):
            if flat not in sys.modules:continue
            path=source_directory/(flat+'.py');module=sys.modules[flat]
            need(path.name in compiled and Path(module.__file__).resolve()==path
                 and sha(path,check)==compiled[path.name],'checkpoint_import_dependency_not_from_same_archive')
            imported_pins[path.name]=compiled[path.name]
        result=dict(schema='UAR-authority-checkpoint-v1',status='validated_before_first_Qwen',tasks=rows,
            imported_flat_sha256=imported_pins,new_clock_created=False,model_fits=0,API_calls=0,
            full_input_or_fitting_only_claim=False,shared_original_setup_budget=True)
        need(len(json.dumps(result,ensure_ascii=False,allow_nan=False).encode('utf-8'))<=16384,
             'compact_authority_checkpoint_bound_exceeded')
        check();return result
    finally:
        sys.path[:]=previous


def main():
    global FAILURE_TYPE
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--launch',action='store_true')
    for name in ['self-sha256','auditor-sha256','closer-sha256','binding','binding-sha256']:
        p.add_argument('--'+name)
    for name in ['start-unix','start-monotonic','absolute-deadline-unix','common-deadline-monotonic']:
        p.add_argument('--'+name,type=float)
    p.add_argument('--bootstrap-launcher');p.add_argument('--bootstrap-launcher-sha256')
    p.add_argument('--extra-terminal-receipt',action='append',default=[],metavar='WORK_REL_PATH=SHA256')
    args=p.parse_args()
    if not args.launch:
        print(json.dumps(dict(status='inspection_only_no_clock_no_copy_no_import_no_children',
            common_seconds=COMMON,caps=CAPS,order=ORDER,research_only=True,official_default_ready=False)))
        return
    need(all(getattr(args,n.replace('-','_')) is not None for n in
        ['self-sha256','auditor-sha256','closer-sha256','binding','binding-sha256',
         'bootstrap-launcher','bootstrap-launcher-sha256']), 'actual_dynamic_source_authority_Stage0_bindings_required')
    need(sys.flags.optimize==0 and not OUTPUT.exists(),'new_unoptimized_pair_required_no_resume')
    start_unix,start_mono,unix,deadline=launch_origin(args)
    OUTPUT.mkdir()
    import psutil
    state=dict(status='starting',qualification='PENDING',start_unix=start_unix,start_monotonic=start_mono,
        common_deadline_monotonic=deadline,absolute_deadline_unix=unix,common_seconds=COMMON,
        clock_origin='same_process_root_launcher_before_publication_provider_and_setup',
        allocations=dict(setup=SETUP,A_regression=900,B_regression=900,A_classification=3600,B_classification=3600,
                         independent_pair_audit=AUDIT,final_cleanup=CLEANUP),
        owned_root=dict(pid=os.getpid(),create_time=psutil.Process().create_time()),
        coordinator_bootstrap_identities=[],supervisors=[],active_supervisor=None,arms=[],
        slot_matrix={a+c:dict(arm=a,kind=k,code=c,status='not_attempted',quality_metric=None) for a,k,c in ORDER},
        cleanup_confirmed=False,source_unchanged=False,pair_artifact_checks_passed=False,
        independent_audit=None,descriptive_retention_win=None,error_history=[],quality_metric=None,
        root_actual_exec_qualification='pending_root_observed_actual_exec_and_fresh_closure',
        root_confirmation_required_before_unix=unix,promotion=False,submit=False,official_score=None,
        official_default_ready=False,scope='Real stochastic Qwen; strict-task-contract OFF/ON with strict-runtime BOTH and identical common retention policy. Reused public; no official-default qualification.')
    pins,deployment,known,finished={},{},set(),set()
    coor=owner=processes=awake=None;final_end=None
    auditor='uar-qwen-pair-next-dev/audit_pair.py'
    closer='uar-qwen-pair-next-dev/close_pair.py'
    manifest_path,plan_path=OUTPUT/'manifest.json',OUTPUT/'verification-plan.json'
    def persist():
        data = {k: v for k, v in state.items() if not k.startswith('_')}
        if coor is None:
            with (OUTPUT/'campaign.json').open('x', encoding='utf-8') as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        else:
            coor.save(OUTPUT/'campaign.json', data)
    def error(exc, phase):
        code = str(exc) if isinstance(exc, RuntimeError) and re.fullmatch('[A-Za-z0-9_:+.-]{1,200}', str(exc)) else 'pair_'+type(exc).__name__
        entry = dict(code=code, phase=phase, unix=time.time(), monotonic=time.monotonic(),
            exception_type=type(exc).__name__, errno=getattr(exc, 'errno', None), winerror=getattr(exc, 'winerror', None))
        state.setdefault('first_failure', entry)
        state['error_history'].append(entry)
        state.update(status='technical_failure', qualification='FAIL', pair_artifact_checks_passed=False,
            descriptive_retention_win=None, quality_metric=None)
        active=state.get('active_arm')
        if active in state.get('slot_matrix',{}):
            state['slot_matrix'][active].update(status='technical_failure',quality_metric=None,failure_ref='campaign.first_failure')
        if isinstance(state.get('independent_audit'),dict):
            state['independent_audit'].update(explicitly_unqualified=True,qualified_result=None)
    def checkpoint(parent_end=None, code='pair_parent_cap_exhausted'):
        if awake is not None and awake.handle is not None:
            coor.cooperative_checkpoint(awake, deadline, unix, parent_end, code)
        else:
            need(time.monotonic() < deadline and time.time() < unix, 'pair_common_clock_exhausted')
            need(abs((deadline-time.monotonic())-(unix-time.time())) <= 5, 'wall_monotonic_clock_disagreement')
            if parent_end is not None:
                need(time.monotonic() < parent_end, code)
        rss = psutil.Process().memory_info().rss
        for saved in state['coordinator_bootstrap_identities']:
            try:
                proc = psutil.Process(saved['pid'])
                if proc.create_time() == saved['create_time']:
                    rss += proc.memory_info().rss
            except psutil.NoSuchProcess:
                pass
        need(rss <= 2*2**30, 'pair_parent_bootstrap_memory_limit')
    def frozen(parent_end=None, code='pair_parent_cap_exhausted'):
        check = lambda: checkpoint(parent_end, code)
        check()
        for name, digest in {**pins, **deployment}.items():
            need(sha(local(name), check) == digest, 'pair_frozen_source_input_or_seal_changed')
        check()
    def absence():
        history = coor.predecessor(owner, finished, base.get('extra_predecessor_receipts', []),
                                   base['terminal_predecessor_receipts'])
        known.update(coor.identities(history))
        observer = owner.StrictOwnedObserver()
        observer.remember(known | finished)
        need(not observer.observe() and not observer.denials and not observer.final_check()['unresolved'],
             'pair_closed_predecessor_or_prior_child_live_or_denied')
        state['fresh_predecessor_identity_count'] = len(observer.seen)
    try:
        setup_end=start_mono+SETUP
        check=lambda:checkpoint(setup_end,'pair_setup_cap_exhausted')
        explicit={BASE:BASE_SHA,COORDINATOR:COORDINATOR_SHA,R4:R4_SHA,
            LINEAGE:LINEAGE_SHA,auditor:args.auditor_sha256,closer:args.closer_sha256,
            'uar-qwen-pair-next-dev/r4_adapter.py':None,
            Path(__file__).resolve().relative_to(WORK).as_posix():args.self_sha256,
            args.binding:args.binding_sha256,args.bootstrap_launcher:args.bootstrap_launcher_sha256}
        need(sha(local(args.binding),check)==args.binding_sha256,'launch_binding_changed')
        binding=load(local(args.binding))
        need(binding.get('schema')=='uar-qwen-pair-binding-v1' and binding.get('readiness')=='READY_REVIEWED_SOURCE_AND_AUTHORITY'
             and binding.get('missing_bindings')==[],'NOT_READY_actual_UAR05_and_reviewed_authority_required')
        explicit['uar-qwen-pair-next-dev/r4_adapter.py']=binding['r4_adapter_sha256']
        def bind(ref):
            need(type(ref) is dict and set(ref)=={'path','sha256'},'typed_exact_reference_required')
            need(sha(local(ref['path']),check)==ref['sha256'],'explicit_reference_changed')
            merge(pins,ref['path'],ref['sha256']);return load(local(ref['path']))
        for name,digest in explicit.items():
            need(sha(local(name),check)==digest,'pair_explicit_source_binding_failed');merge(pins,name,digest)
        stage=binding['source_gate'];cfg_ref=stage['private_manifest'];cfg=bind(cfg_ref)
        # Explicit disjoint admission modes: composite evidence is never a full-gate fallback.
        gate_mode=stage.get('mode')
        need(gate_mode in ('full_gate_v1','uar07_composite_v1','uar07_composite_audit_repair_v1'),'explicit_source_gate_mode_required')
        need(type(stage['actual_tool_evidence']) is str and bool(stage['actual_tool_evidence'].strip())
             and (stage['actual_exec_session'] is None or type(stage['actual_exec_session']) is int
                  and stage['actual_exec_session']>0),'actual_root_observed_gate_tool_and_session_required')
        stage0=bind(stage['campaign']);stage0_proof=bind(stage['root_closure'])
        need(stage0_proof.get('technical_procedure_passed') is True and stage0_proof.get('actual_exec_exit_code_observed_by_root')==0
             and stage0_proof.get('actual_exec_session')==stage['actual_exec_session']
             and stage0_proof.get('actual_tool_evidence')==stage['actual_tool_evidence']
             and stage0_proof.get('private_manifest_sha256')==cfg_ref['sha256']
             and stage0_proof.get('campaign_sha256')==stage['campaign']['sha256']
             and stage0_proof.get('cleanup_confirmed') is True and stage0_proof.get('source_unchanged') is True
             and stage0_proof.get('active_owned_processes')==[] and stage0_proof.get('uncertain_owned')==[],
             'actual_UAR05_root_PASS_not_prospective_counts_required')
        if gate_mode in ('uar07_composite_v1','uar07_composite_audit_repair_v1'):
            need(stage0_proof.get('schema')==('uar-composite-audit-repair-root-closure-v1'
                 if gate_mode=='uar07_composite_audit_repair_v1' else 'uar-composite-root-closure-v1')
                 and cfg.get('schema')=='uar-composite-private-manifest-v1',
                 'typed_UAR07_composite_proof_and_manifest_required')
        else:
            need(stage0_proof.get('schema')=='uar-full-root-closure-v1'
                 and cfg.get('schema')=='uar-full-private-manifest-v1',
                 'typed_full_gate_proof_and_manifest_required')
        if gate_mode=='uar07_composite_audit_repair_v1':
            # This is a new audit-only qualification, NEVER the failed closer PASS.
            repair=stage.get('audit_repair')
            need(type(repair) is dict and set(repair)=={'helper','original_failure_binding','root_confirmation'},
                 'typed_separate_audit_repair_binding_required')
            helper=repair['helper']
            need(type(helper) is dict and set(helper)=={'path','sha256'}
                 and sha(local(helper['path']),check)==helper['sha256'],'separate_auditor_source_changed')
            merge(pins,helper['path'],helper['sha256'])
            failure=bind(repair['original_failure_binding']);confirmation=bind(repair['root_confirmation'])
            original_pins=stage0_proof.get('external_auditor_original_pins')
            need(type(original_pins) is dict and set(original_pins)=={
                'original_driver','original_closer','private_manifest','campaign','failed_preparer_receipt'}
                 and original_pins['original_driver']==stage['driver']['sha256']
                 and original_pins['private_manifest']==cfg_ref['sha256']
                 and original_pins['campaign']==stage['campaign']['sha256']
                 and original_pins['original_closer']=='1b3bfc4091426febdc49665e99cc6da2c98e06efd804ef7dc86648eb9bd3bfc5'
                 and original_pins['failed_preparer_receipt']=='0d79d0d94f5a51c98fbe06643f5ab8d33d0b7cc589341bcb42e2c6b60f81c79e',
                 'original_driver_failed_closer_manifest_campaign_pins_required')
            need(failure.get('schema')==1 and failure.get('original_pins')==original_pins
                 and failure.get('original_driver_actual')==dict(session=78888,exit_code=0,tool='8a9663')
                 and failure.get('original_closer_actual')==dict(session=19230,exit_code=1,tool='617a23',
                     failure='root_closure30_cap',source_line=177,raw_trace_file=None)
                 and failure.get('original_closer_retroqualified') is False and failure.get('actual_new_audit') is None
                 and failure.get('clock_reset') is False
                 and failure.get('original_clock')==dict(start_unix=1792825378.045702,deadline_unix=1792825978.045702,
                     start_monotonic=84383.171,deadline_monotonic=84983.171),
                 'original_failed_closer_actual_evidence_and_clock_must_remain_failed')
            need(stage['actual_exec_session']==78888 and stage['actual_tool_evidence']=='8a9663'
                 and stage0_proof.get('qualification_scope')=='separate_saved_artifact_audit_only'
                 and stage0_proof.get('original_closer_status')=='FAILED_root_closure30_cap'
                 and stage0_proof.get('original_closer_exec_session')==19230
                 and stage0_proof.get('original_closer_actual_exit_code')==1
                 and stage0_proof.get('original_closer_actual_tool_evidence')=='617a23'
                 and stage0_proof.get('original_closer_source_sha256')==original_pins['original_closer']
                 and stage0_proof.get('original_closer_preparer_receipt_sha256')==original_pins['failed_preparer_receipt']
                 and stage0_proof.get('original_closer_retroqualified') is False
                 and stage0_proof.get('original_full_procedure_passed') is False
                 and stage0_proof.get('original_closer_raw_trace_saved') is False
                 and stage0_proof.get('original_closer_failure_evidence_scope')==
                     'root_observed_exit_and_source_line177_no_synthetic_trace'
                 and stage0_proof.get('external_auditor_source_sha256')==helper['sha256']
                 and stage0_proof.get('separate_audit_actual_exec_confirmation_pending') is True
                 and stage0_proof.get('own_actual_exec_exit_and_fresh_preparer_absence_required') is True,
                 'distinct_driver_closer_and_new_audit_provenance_required')
            failed_path=local(stage['driver']['path']).parent/'preparer-identity.json'
            failed_ref=dict(path=failed_path.relative_to(WORK).as_posix(),sha256=original_pins['failed_preparer_receipt'])
            failed_preparers=bind(failed_ref)
            need(failed_preparers.get('schema')==1 and failed_preparers.get('identities')==[
                dict(pid=27264,create_time=1792825407.5485268),dict(pid=26980,create_time=1792825407.5320556)]
                 and stage0_proof.get('technical_artifact_refs',{}).get(str(failed_path))==failed_ref['sha256']
                 and all(v in stage0_proof['owned_identities'] for v in failed_preparers['identities']),
                 'failed_original_closer_preparers_must_be_sealed_and_observed')
            need(type(confirmation) is dict and set(confirmation)=={
                'schema','audit_receipt_sha256','helper_sha256','original_failure_binding_sha256',
                'actual_exec_session','actual_exit_code','actual_tool_evidence','checked_unix',
                'original_common_deadline_unix','known_count','known_exact_live','uncertain','preparer_identities',
                'original_closer_retroqualified','original_full_procedure_passed'}
                 and confirmation['schema']=='uar07-independent-audit-root-confirmation-v1'
                 and confirmation['audit_receipt_sha256']==stage['root_closure']['sha256']
                 and confirmation['helper_sha256']==helper['sha256']
                 and confirmation['original_failure_binding_sha256']==repair['original_failure_binding']['sha256']
                 and (confirmation['actual_exec_session'] is None or type(confirmation['actual_exec_session']) is int
                      and confirmation['actual_exec_session']>0)
                 and type(confirmation['actual_exit_code']) is int and confirmation['actual_exit_code']==0
                 and type(confirmation['actual_tool_evidence']) is str and bool(confirmation['actual_tool_evidence'].strip())
                 and type(confirmation['checked_unix']) in (int,float) and math.isfinite(confirmation['checked_unix'])
                 and confirmation['original_common_deadline_unix']==1792825978.045702==stage0['absolute_deadline_unix']
                 and stage0['finished_unix']<=confirmation['checked_unix']<confirmation['original_common_deadline_unix']
                 and type(confirmation['known_count']) is int and confirmation['known_count']>0
                 and confirmation['known_exact_live']==[] and confirmation['uncertain']==[]
                 and confirmation['original_closer_retroqualified'] is False
                 and confirmation['original_full_procedure_passed'] is False,
                 'actual_separate_audit_exit0_and_original_deadline_fresh_root_confirmation_required')
            confirmed=confirmation['preparer_identities']
            need(type(confirmed) is list and bool(confirmed) and all(type(v) is dict and set(v)=={'pid','create_time'}
                and type(v['pid']) is int and v['pid']>0 and type(v['create_time']) in (int,float)
                and math.isfinite(v['create_time']) and v['create_time']>0 for v in confirmed)
                 and all(v in confirmed for v in stage0_proof['closure_preparer_identities'])
                 and confirmation['known_count']>=len({(v['pid'],v['create_time'])
                     for v in stage0_proof['owned_identities']+stage0_proof['closure_preparer_identities']}),
                 'actual_audit_preparers_must_be_in_root_confirmed_known_union')
            known.update((v['pid'],v['create_time']) for v in confirmed)
        gate_driver=bind_source(stage['driver'],pins,check)
        cfg=gate_driver.config(str(local(cfg_ref['path'])),cfg_ref['sha256'],stage['driver']['sha256'])
        need(sha(Path(cfg['contracts']),check)==cfg['files_sha256'][cfg['contracts']],'gate_contract_changed')
        gate_contract=imported('_UAR05_artifact_contract',Path(cfg['contracts']))
        gate_summary,gate_refs=gate_contract.artifact_checks(cfg,Path(cfg['output']),check)
        need(stage0_proof['qualified_checks']==gate_summary and stage0.get('technical_procedure_passed') is True
             and stage0.get('cleanup_confirmed') is True and stage0.get('source_unchanged') is True
             and not stage0.get('error_history'),'actual_complete_UAR05_artifacts_required')
        if gate_mode in ('uar07_composite_v1','uar07_composite_audit_repair_v1'):
            # Recompute from actual sealed artifacts through the SHA-pinned producer,
            # then independently constrain the meaning of its composite summary.
            need(type(gate_summary) is dict and set(gate_summary)=={
                'schema','qualification_mode','archive_sha256','flat_members','reused_phases','new_phases',
                'reused_source_scripts','reused_source_unique_checks','reused_exact_repeated_checks',
                'newly_executed_source_checks','newly_executed_builds','newly_executed_exact_checks',
                'newly_executed_parser_checks','newly_executed_mapped_checks','original_UAR06_status',
                'original_UAR06_retroqualified','fixture_learner_fits','declared_mapped_tiny_learner_fits',
                'fixture_fit_count_reason','external_API_calls','external_API_usage_reason',
                'public_experiment_fits','quality_metric','official_default_ready'}
                 and gate_summary['schema']=='uar-composite-qualified-checks-v1'
                 and gate_summary['qualification_mode']=='explicit_composite',
                 'exact_composite_qualified_checks_schema_required')
            for field,expected in {'flat_members':73,'reused_source_scripts':57,'reused_source_unique_checks':604,
                    'reused_exact_repeated_checks':23,'newly_executed_source_checks':0,'newly_executed_builds':0,
                    'newly_executed_exact_checks':0,'newly_executed_parser_checks':16,
                    'newly_executed_mapped_checks':75,'declared_mapped_tiny_learner_fits':9,
                    'public_experiment_fits':0}.items():
                need(type(gate_summary[field]) is int and gate_summary[field]==expected,
                     'exact_reused604_build73_exact23_and_fresh16_75_required')
            need(gate_summary['original_UAR06_status']=='FAIL_PERMANENT'
                 and gate_summary['original_UAR06_retroqualified'] is False
                 and gate_summary['fixture_learner_fits'] is None and gate_summary['external_API_calls'] is None
                 and gate_summary['quality_metric'] is None and gate_summary['official_default_ready'] is False,
                 'composite_not_old_parent_PASS_or_measured_fit_API_quality_required')
            reused=gate_summary['reused_phases']
            need(type(reused) is list and len(reused)==3 and [r.get('id') for r in reused]==['source','build','exact'],
                 'exact_three_reused_phase_order_required')
            evidence=load(Path(cfg['reuse']['evidence']['path']))['files_sha256']
            for row in reused:
                detail={'source':{'checks':604,'scripts':57},'build':{'flat_members':73},'exact':{'checks':23}}[row['id']]
                need(type(row) is dict and set(row)=={'id','mode','exit_code','cleanup_confirmed',
                    'parent_receipt_sha256','phase_receipt_sha256','phase_clock'}|set(detail)
                     and row['mode']=='reused_completed_leaf' and type(row['exit_code']) is int
                     and row['exit_code']==0 and row['cleanup_confirmed'] is True
                     and row['parent_receipt_sha256']==evidence['technical.json']
                     and row['phase_receipt_sha256']==evidence['technical-results.json']
                     and all(type(row[k]) is int and row[k]==v for k,v in detail.items()),
                     'reused_phase_exit_cleanup_counts_and_receipt_binding_required')
            need(gate_summary['new_phases']==[dict(id='parser',mode='new_execution',checks=16),
                                             dict(id='mapped',mode='new_execution',checks=75)]
                 and all(type(r['checks']) is int for r in gate_summary['new_phases']),
                 'fresh_parser16_mapped75_not_reused_required')
            need(stage0.get('qualified_checks')==gate_summary and stage0.get('original_UAR06_status')=='FAIL_PERMANENT'
                 and stage0_proof.get('status')==('separate_saved_artifact_audit_pass_pending_root_exec'
                 if gate_mode=='uar07_composite_audit_repair_v1' else 'technical_pass') and not stage0_proof.get('error_history')
                 and stage0_proof.get('original_UAR06_status')=='FAIL_PERMANENT'
                 and stage0_proof.get('original_UAR06_retroqualified') is False
                 and stage0_proof.get('original_common_seconds')==600
                 and stage0_proof.get('original_start_unix')==stage0['start_unix']
                 and stage0_proof.get('original_deadline_unix')==stage0['absolute_deadline_unix']
                 and stage0['common_seconds']==600 and stage0['absolute_deadline_unix']==stage0['start_unix']+600,
                 'actual_new_UAR07_root_not_historical_parent_qualification_required')
            negative=cfg['negative_predecessor']
            need(type(negative) is dict and set(negative)=={'schema','late_observation','root_fresh_absence'}
                 and negative['schema']=='uar06_exact_late_negative_predecessor_v1',
                 'separate_typed_old_negative_evidence_required')
            negative_values={}
            for key,expected in (
                ('late_observation','fe4fbbbc58ca31bfecad23bf4eed912ccd69cc3e94cfbe2e53bddb15f0c64153'),
                ('root_fresh_absence','7a9a4ed0e8ea5d82f68efc375d59733b834f6457c4363008ded66ec17cfc3897')):
                ref=negative[key]
                need(type(ref) is dict and set(ref)=={'path','sha256'} and ref['sha256']==expected
                     and cfg['files_sha256'].get(ref['path'])==expected
                     and gate_refs.get(ref['path'])==expected,'old_negative_evidence_must_be_frozen_and_recomputed')
                relative=Path(ref['path']).resolve().relative_to(WORK).as_posix()
                negative_values[key]=bind(dict(path=relative,sha256=expected))
            late=negative_values['late_observation'];fresh=negative_values['root_fresh_absence']
            need(late.get('schema')=='UAR06-late-negative-observation-v1'
                 and late.get('technical_procedure_passed') is False and late.get('qualified_checks') is None
                 and late.get('cleanup_confirmed') is False and late.get('source_unchanged') is False
                 and late.get('original_UAR06_remains_failed') is True
                 and late.get('original_deadline_extended') is False and late.get('late_current_observation_only') is True
                 and late.get('current_known_absence_confirmed') is True
                 and late.get('current_source_pin_check_completed') is True and late.get('current_source_pins_match') is True
                 and late.get('actual_exec_session')==36525 and late.get('actual_exec_exit_code_observed_by_root')==1
                 and fresh.get('schema')==1 and fresh.get('late_audit_sha256')==negative['late_observation']['sha256']
                 and fresh.get('late_audit_actual_exit')==0 and fresh.get('known_exact_live')==[]
                 and fresh.get('uncertain')==[] and fresh.get('original_UAR06_FAIL_preserved') is True
                 and fresh.get('original_cleanup_or_source_posthash_retroqualified') is False
                 and stage0_proof.get('prior_UAR06_late_negative_sha256')==negative['late_observation']['sha256']
                 and stage0_proof.get('prior_UAR06_actual_root_fresh_absence_sha256')==negative['root_fresh_absence']['sha256'],
                 'old_UAR06_FAIL_false_flags_and_current_late_absence_not_retroqualified')
        for absolute,digest in {**cfg['files_sha256'],**gate_refs}.items():
            merge(pins,Path(absolute).resolve().relative_to(WORK).as_posix(),digest)
        archive_ref=binding['source_archive'];bind_archive=local(archive_ref['path'])
        need(bind_archive.resolve()==(Path(cfg['output'])/'candidate.zip').resolve()
             and sha(bind_archive,check)==archive_ref['sha256'],'exact_actual_UAR05_archive_required')
        merge(pins,archive_ref['path'],archive_ref['sha256'])
        compiled=load(Path(cfg['output'])/'candidate.manifest.json')['files']
        need(set(compiled)==set(cfg['flat_inventory']) and len(compiled)==gate_summary['flat_members'],'actual_flat_inventory_required')
        with zipfile.ZipFile(bind_archive) as archive:
            need(len(archive.namelist())==len(set(archive.namelist()))==len(compiled)
                 and set(archive.namelist())==set(compiled),'pair_archive_inventory_changed')
            for n,h in compiled.items():
                need(Path(n).name==n and (n.endswith('.py') or n=='requirements.txt')
                     and hashlib.sha256(archive.read(n)).hexdigest()==h,'pair_flat_archive_member_changed');check()
        if gate_mode in ('uar07_composite_v1','uar07_composite_audit_repair_v1'):
            need(len(compiled)==73 and gate_summary['archive_sha256']==archive_ref['sha256']
                 and load(Path(cfg['output'])/'candidate.manifest.json')['sha256']==archive_ref['sha256'],
                 'same_exact_qualified_73_member_archive_for_all_future_arms_required')
        source_archive,source_archive_sha256=archive_ref['path'],archive_ref['sha256']
        coor=imported('_UAR_pair_proven_coordinator',local(COORDINATOR));FAILURE_TYPE=coor.TechnicalFailure
        base,lineage=load(local(BASE)),load(local(LINEAGE))
        for name,digest in base['immutable_files'].items():merge(pins,name,digest)
        for name in [*coor.LIBS.values(),coor.AWAKE]:need(name in pins,'pair_runtime_dependency_unbound')
        owner=imported('_UAR_pair_owner',local(coor.LIBS['owner']))
        processes=imported('_UAR_pair_processes',local(coor.LIBS['processes']))
        locker=imported('_UAR_pair_lock',local(coor.LIBS['lock']))
        awake=imported('_UAR_pair_awake',local(coor.AWAKE)).PowerRequestGuard('UAR paired agent pid'+str(os.getpid()),10)
        parent=psutil.Process().parent();own_paths={Path(__file__).resolve(),local(args.bootstrap_launcher)}
        while parent is not None:
            birth=parent.create_time()
            if not any(Path(v).resolve() in own_paths for v in parent.cmdline() if not v.startswith('-')):break
            need(parent.create_time()==birth,'pair_bootstrap_identity_changed')
            state['coordinator_bootstrap_identities'].append(dict(pid=parent.pid,create_time=birth));parent=parent.parent()
        refs=[(stage['root_closure']['path'],stage['root_closure']['sha256'],stage['actual_exec_session'],0)]
        refs += [(n,h,s,e) for n,(h,s,e) in RETAINED_TERMINAL.items()]
        refs += [('la2/terminal-root-closure.json','3ae50a32e3931f214e59343eee99654c37b77bf66b1b8ec233d416586d6cfd8b',12413,1),
                 ('la2-audit-repair-r1/terminal-root-closure.json','9b6de5609bd18ca9a31356b96af375f62ec131cf173658142247a39701a2dcbc','saved',None)]
        refs += [(Path(r['path']).resolve().relative_to(WORK).as_posix(),r['sha256'],'saved',None) for r in cfg['predecessors']]
        for value in args.extra_terminal_receipt:
            n,h=value.rsplit('=',1);refs.append((n,h,'saved',None))
        for name,digest,sess,exitcode in refs:
            proof=bind(dict(path=name,sha256=digest))
            need(proof.get('cleanup_confirmed') is True and proof.get('source_unchanged') is True
                 and proof.get('active_owned_processes',[])==[] and proof.get('uncertain_owned',[])==[]
                 and proof.get('owned_identities') and proof.get('closure_preparer_identities'),'complete_terminal_closure_required')
            if sess!='saved':need(proof.get('actual_exec_session')==sess
                and proof.get('actual_exec_exit_code_observed_by_root')==exitcode,'actual_predecessor_exec_lineage_changed')
            known.update(coor.identities(proof['owned_identities']+proof['closure_preparer_identities']))
        # Authority SHA pins and independently reviewed semantics are mandatory.
        authority_ref=binding['authority']['handoff'];authority=bind(authority_ref)
        bind(binding['authority']['independent_review'])
        need(binding['authority'].get('metric_contrast_fixed_source_qualified') is True,
             'P0_metric_ambiguity_current_source_not_launch_ready')
        authority_root=local(authority_ref['path']).parent
        for name,digest in authority['files_sha256'].items():
            merge(pins,(authority_root/name).relative_to(WORK).as_posix(),digest)
        for ref in CLOSED_SPECS.values():
            need(sha(local(ref['path']),check)==ref['sha256'],'closed_spec_metadata_pin_failed')
            merge(pins,ref['path'],ref['sha256'])
        frozen(setup_end,'pair_setup_cap_exhausted')
        absence()
        tasks=copy.deepcopy(base['tasks']);need({t['kind'] for t in tasks}==set(CAPS) and len(tasks)==2,'two_frozen_tasks_required')
        for task in tasks:
            kind=task['kind'];rawsource=local(task['source']);inputs=OUTPUT/('inputs-'+task['code']);inputs.mkdir()
            need(set(task['files'])=={'task.md','train.csv','test.csv','data_dictionary.csv','sample_submission.csv'},'five_named_inputs_required')
            for name,digest in task['files'].items():
                source=rawsource/name
                if name=='task.md':
                    ref=authority['enriched_tasks'][kind];source=authority_root/ref['path'];digest=ref['sha256']
                need(sha(source,check)==digest,'research_input_original_or_authority_changed')
                target=inputs/name;target.write_bytes(source.read_bytes())
                need(sha(target,check)==digest,'research_input_copy_changed');task['files'][name]=digest
                deployment[target.relative_to(WORK).as_posix()]=digest
            task['source']=inputs.relative_to(WORK).as_posix()
            ref=authority['retention_packets'][kind];packet=authority_root/ref['path']
            task['retention']=dict(path=packet.relative_to(WORK).as_posix(),sha256=ref['sha256'])
            need(ref['mode']==('l1_composite' if kind=='regression' else 'control'),'fixed_REG7_CLASS5_modes_required')
        arms={a:dict(archive=source_archive,archive_sha256=source_archive_sha256,compiled_sha256=compiled,tasks=tasks) for a in ['A','B']}
        slots={a+c:dict(arm=a,kind=k,code=c,argv=solver_argv(a,k,next(t for t in tasks if t['kind']==k)['retention']['sha256']),caps=CAPS[k]) for a,k,c in ORDER}
        manifest=dict(schema='UAR-Qwen-pair-v1',output_root='uq1',immutable_files=pins,arms=arms,tasks=tasks,slots=slots,
            archive=source_archive,archive_sha256=source_archive_sha256,compiled_sha256=compiled,
            common_seconds=COMMON,caps=CAPS,order=[a+c for a,k,c in ORDER],maximum_experiments=9,hpo_trials=8,
            authority=dict(handoff=authority_ref,independent_review=binding['authority']['independent_review']),
            launch_binding=dict(path=args.binding,sha256=args.binding_sha256),
            stage0_root_closure=stage['root_closure'],stage0_private_manifest=cfg_ref,
            r4_adapter_sha256=binding['r4_adapter_sha256'],max_planner_calls=2,gateway_call_limit=4,
            threads=2,worker_memory_GiB=1.5,whole_tree_memory_GiB=2,
            interpreter_path=sys.executable,interpreter_sha256=sha(sys.executable,check),interpreter_version=sys.version,
            requested_model=base['requested_model'],reasoning_effort=base['reasoning_effort'],official_default_ready=False)
        plan=copy.deepcopy(base['verification_plan_template'])
        plan.update(verifier_source_sha256=args.auditor_sha256,manual_metric_verifier_path=R4,manual_metric_verifier_sha256=R4_SHA,
            r4_adapter_path='uar-qwen-pair-next-dev/r4_adapter.py',r4_adapter_sha256=binding['r4_adapter_sha256'],
            original_common_start_unix=start_unix,original_absolute_deadline_unix=unix,common_seconds=COMMON,
            hpo_requested_budget_seconds={k:v['hpo'] for k,v in CAPS.items()},
            expected_regression_splits=copy.deepcopy(lineage['split_fingerprints']),
            reproduction_absolute_tolerance=1e-9,pair_order=[a+c for a,k,c in ORDER],official_default_ready=False)
        # Pin the actual generic metric repair as part of the SAME gated runtime,
        # never an out-of-band input rewrite or a bypass in this controller.
        metric_source=binding['authority']['qualified_metric_source']
        need(type(metric_source) is dict and set(metric_source)=={'flat_member','sha256'}
             and compiled.get(metric_source['flat_member'])==metric_source['sha256'],
             'generic_metric_repair_must_be_in_actual_qualified_archive')
        manifest['qualified_metric_source']=metric_source
        state.update(_manifest=base,_pulse=lambda:checkpoint(),awake_guard=awake.record,
            stage0_root_closure=stage['root_closure'])
        with awake:
            absence();frozen(setup_end,'pair_setup_cap_exhausted')
            with locker.ResearchLock(WORK/'alfa-hack-automl/test-runs/.owned-research.lock') as lock:
                lock.write_identity(state['owned_root']);absence();frozen(setup_end,'pair_setup_cap_exhausted')
                # Shared source/input setup, charged once to setup900/common10800.
                # Every future slot has identical checkpoint bytes BEFORE Ar API.
                for arm,kind,code in ORDER:
                    (OUTPUT/arm).mkdir(exist_ok=True);directory=OUTPUT/arm/code
                    task=next(t for t in tasks if t['kind']==kind)
                    coor.materialize(task,directory,{**arms[arm],'immutable_files':pins},deployment)
                    target=directory/'retention.json';ref=task['retention']
                    target.write_bytes(local(ref['path']).read_bytes())
                    need(sha(target,check)==ref['sha256'],'retention_deployment_changed');deployment[coor.relative(target)]=ref['sha256']
                    check()
                validation_start=time.monotonic()
                checkpoint_data=authority_checkpoint(tasks,OUTPUT/'A/r',compiled,gate_contract.mapping(cfg['canonical_root']),check)
                checkpoint_data.update(original_common_start_unix=start_unix,original_common_start_monotonic=start_mono,
                    validation_start_monotonic=validation_start,validation_end_monotonic=time.monotonic(),
                    validation_elapsed_seconds=time.monotonic()-validation_start,source_archive_sha256=source_archive_sha256)
                checkpoint_path=OUTPUT/'authority-checkpoint.json';coor.save(checkpoint_path,checkpoint_data,True)
                checkpoint_ref=dict(path=coor.relative(checkpoint_path),sha256=sha(checkpoint_path,check))
                deployment[checkpoint_ref['path']]=checkpoint_ref['sha256']
                for arm,kind,code in ORDER:
                    target=OUTPUT/arm/code/'authority-checkpoint.json';target.write_bytes(checkpoint_path.read_bytes())
                    need(sha(target,check)==checkpoint_ref['sha256'],'authority_checkpoint_deployment_changed')
                    deployment[coor.relative(target)]=checkpoint_ref['sha256']
                manifest['authority_checkpoint']=checkpoint_ref;plan['authority_checkpoint']=checkpoint_ref
                absence();frozen(setup_end,'pair_setup_cap_exhausted')
                coor.save(manifest_path,manifest,True);state['manifest_sha256']=sha(manifest_path,check)
                plan['execution_manifest_sha256']=state['manifest_sha256'];coor.save(plan_path,plan,True)
                deployment[coor.relative(manifest_path)]=state['manifest_sha256']
                deployment[coor.relative(plan_path)]=sha(plan_path,check)
                state['verification_plan_sha256']=deployment[coor.relative(plan_path)]
                checkpoint(setup_end,'pair_setup_cap_exhausted');state['setup_seconds']=time.monotonic()-start_mono
                previous={}
                def interrupted(signum,frame):raise SystemExit(128+signum)
                for sig in [signal.SIGINT,signal.SIGTERM]:previous[sig]=signal.signal(sig,interrupted)
                persist()
                try:
                    for index,(arm,kind,code) in enumerate(ORDER):
                        key=arm+code;cfg=CAPS[kind];tick=time.monotonic()
                        future=sum(CAPS[k]['parent'] for a,k,c in ORDER[index+1:])+AUDIT+CLEANUP
                        need(deadline-tick>=cfg['parent']+future,'full_fixed_remaining_allocations_unavailable')
                        absence();frozen(tick+cfg['parent'],'task_materialization_over_parent_cap')
                        directory=OUTPUT/arm/code
                        task=next(t for t in tasks if t['kind']==kind)
                        need(sha(directory/'authority-checkpoint.json',lambda:checkpoint(tick+cfg['parent']))==checkpoint_ref['sha256'],
                             'prefirst_API_authority_checkpoint_changed')
                        argv=list(slots[key]['argv']);state.update(status='running',active_arm=key)
                        state.setdefault('actual_arm_argv',{})[key]=argv
                        state['slot_matrix'][key].update(status='admitted',admitted_monotonic=tick,quality_metric=None);persist()
                        sup=coor.supervise(argv,directory,directory/'supervisor.json',kind+'-'+arm,
                            tick,cfg['parent'],cfg['child'],deadline,unix,cfg['parent']+future,
                            state,persist,frozen,owner,processes,state['coordinator_bootstrap_identities'],cfg['solver'],cfg['hpo'])
                        coor.child_errors(state,sup);finished.update(coor.identities(sup.get('owned_process_identities',[])))
                        need(sup.get('cleanup_confirmed') is True and sup.get('status') in {'ok','child_failed'},'arm_systemic_or_ownership_failure')
                        arm_check=lambda:checkpoint(tick+cfg['parent'],'arm_metadata_seal_over_cap')
                        frozen(tick+cfg['parent'],'arm_metadata_seal_over_cap')
                        proof=coor.task_proof(directory,arm_check);core=complete_core_seal(directory,coor,arm_check)
                        seal_path=OUTPUT/(key+'-seal.json')
                        coor.save(seal_path,dict(slot=key,arm=arm,kind=kind,files_sha256=core,cleanup_confirmed=True,
                            source_unchanged=True,sealed_before_independent_label_scoring=True),True)
                        seal_sha=sha(seal_path,arm_check);deployment[coor.relative(seal_path)]=seal_sha;deployment.update(core)
                        entry=dict(sup,slot=key,arm=arm,kind=kind,code=code,proof=proof,
                            supervisor_path=coor.relative(directory/'supervisor.json'),supervisor_sha256=sha(directory/'supervisor.json',arm_check),
                            seal=dict(path=coor.relative(seal_path),sha256=seal_sha),task_allocation_seconds=cfg['parent'],
                            qualified=False,measurement_status='pending_independent_saved_artifact_audit')
                        state['arms'].append(entry);state['slot_matrix'][key].update(status='sealed',quality_metric=None)
                        state['active_arm']=None;persist();arm_check()
                    tick=time.monotonic();need(deadline-tick>=AUDIT+CLEANUP,'audit_cleanup_reserve_unavailable')
                    absence();frozen();state.update(status='verifying',cleanup_confirmed=True,source_unchanged=True);persist()
                    audit_argv=[sys.executable,'-B','-X','utf8',str(local(auditor)),
                        '--work-root',str(WORK),'--pair-root','uq1','--manifest','uq1/manifest.json',
                        '--manifest-sha256',state['manifest_sha256'],'--plan','uq1/verification-plan.json',
                        '--plan-sha256',state['verification_plan_sha256'],'--self-sha256',args.auditor_sha256,
                        '--output','uq1/independent-audit.json']
                    sup=coor.supervise(audit_argv,WORK,OUTPUT/'audit-supervisor.json','pair-audit',tick,AUDIT,AUDIT-30,
                        deadline,unix,AUDIT+CLEANUP,state,persist,frozen,owner,processes,state['coordinator_bootstrap_identities'])
                    coor.child_errors(state,sup);finished.update(coor.identities(sup.get('owned_process_identities',[])))
                    need(sup.get('status')=='ok' and sup.get('exit_code')==0 and sup.get('cleanup_confirmed') is True,'independent_auditor_process_failed')
                    audit_path=OUTPUT/'independent-audit.json';audit=load(audit_path)
                    state['independent_audit']=dict(path=coor.relative(audit_path),sha256=sha(audit_path),raw_result=audit,
                                                  qualification='pending_terminal_gates')
                    need(audit.get('artifact_procedure_checks_passed') is True and audit.get('audit_within_original_common_clock') is True
                         and audit.get('parent_exec_terminal_qualification_required') is True,'independent_artifact_contract_failed')
                    state.update(status='completed_pair_pending_root_exec_and_closure',qualification='PENDING_ROOT',
                        pair_artifact_checks_passed=True,descriptive_retention_win=audit.get('descriptive_retention_win'))
                except BaseException as exc:
                    error(exc, 'pair_procedure')
                finally:
                    final_end = min(time.monotonic()+CLEANUP, deadline-10)
                    state['finalization_deadline_monotonic'] = final_end
                    try:
                        frozen(final_end, 'pair_final_cleanup_cap_exhausted')
                        absence()
                        need(all(r['cleanup_confirmed'] is True for r in state['supervisors']), 'pair_child_cleanup_unknown')
                        state.update(cleanup_confirmed=True, source_unchanged=True)
                        checkpoint(final_end)
                        persist()
                    except BaseException as exc:
                        error(exc, 'pair_terminal_source_cleanup')
                        state.update(cleanup_confirmed=False, source_unchanged=False)
                    finally:
                        for sig, handler in previous.items():
                            signal.signal(sig, handler)
        need(awake.record.get('release_API_verified') is True, 'pair_power_release_unverified')
        last = awake.record['last_heartbeat']
        checkpoint(final_end, 'pair_terminal_export_cap_exhausted')
        need(max(time.time()-last['unix'], time.monotonic()-last['monotonic']) <= 10,
             'pair_terminal_heartbeat_gap_over10s')
        absence()
    except BaseException as exc:
        error(exc, 'pair_parent')
        state.update(cleanup_confirmed=False, source_unchanged=False)
    finally:
        if awake is not None:
            state['awake_guard'] = awake.record
            if awake.handle is not None:
                try:
                    awake.close()
                except BaseException as exc:
                    error(exc, 'pair_power_release')
        state.update(finished_unix=time.time(), finished_monotonic=time.monotonic(),
            elapsed_common_seconds=time.monotonic()-start_mono,
            owned_process_identities=[dict(pid=pid, create_time=birth) for pid, birth in sorted(finished)])
        if time.monotonic() >= min(deadline-10, final_end if final_end is not None else deadline) or time.time() >= unix-10:
            error(RuntimeError('pair_terminal_export_over_cap'), 'pair_terminal_export')
        persist()
        if time.monotonic() >= min(deadline-10, final_end if final_end is not None else deadline):
            error(RuntimeError('pair_terminal_receipt_write_over_cap'), 'pair_terminal_export')
            persist()
    print(json.dumps({k: state[k] for k in ['status', 'qualification', 'pair_artifact_checks_passed',
        'cleanup_confirmed', 'source_unchanged', 'elapsed_common_seconds', 'root_actual_exec_qualification']}))
    raise SystemExit(0 if state['pair_artifact_checks_passed'] and state['cleanup_confirmed']
                     and state['source_unchanged'] and not state['error_history'] else 1)


if __name__ == '__main__':
    main()
