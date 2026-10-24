from pathlib import Path
import hashlib, importlib.util, json, sys
WORK = BASE = BASE_SHA = None
RA1_ORIGINAL_REFS = {'manifest': ('private/rq6-manifest.ready-r1.json', 'f4eb5dca1e3560de66206c76937d0314a790047436bd80f218422c9324afd65a'), 'campaign': ('rq6/campaign.json', '60afb434d1e6f943d05be02c0761cdb255745fe3e543961ed407e559eaf38725'), 'root': ('rq6/terminal-root-closure.json', 'f9e26b3a9e9223fc903909aafd3172dbd0b4242b142d9d29cf8593a3379d9810'), 'negative': ('rq6/current-negative-closure.json', 'fe8941210806633144b53f2f1345daa3922f7099dc81148637da7240592ce0bc'), 'post': ('rq6/current-negative-post-tool-confirmation.json', '9ad55350293113fbf7c026762979e06cc40a350b948718c39b998b8dea316fdc'), 'barrier': ('rq6/pretruth-barrier.json', '1a1c52f62d0badc5e579437e3f90b376e6f3e8440ca6948afbc92e45c1d79781'), 'regression_seal': ('rq6/regression-core-seal.json', '53c6dde06429214624ad071349b6365e0ddd5f73f8a8f5080c8b0dfa81cc7a9d'), 'classification_seal': ('rq6/classification-core-seal.json', '6d9345942bcb8e3752cdf66ba35f13292ed3f0f3da64481c3418f63bea1652fd'), 'old_auditor': ('last-submission-repair-qualification-next-dev-r6/artifact_audit.py', '910f8c5374b147c1d665ed01cb93f9b492f17d5cee330621f0f23685854b7209')}

def need(value,code):
    if not value:raise RuntimeError(code)

def read(path):return json.loads(Path(path).read_text('utf-8'))

def sha(path,check=lambda:None):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            check();block=stream.read(2**20)
            if not block:break
            h.update(block)
    check();return h.hexdigest()

def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module

def qualified():
    need(sha(BASE)==BASE_SHA,'qualified_C5_helper_changed')
    return imported('_q3h_qualified_C5',BASE)

def strong_authority(cfg,row,check=lambda:None):
    """Bind raw strong recipe to this qualified report, never deployment trees."""
    pins=cfg['immutable_files'];ref=row['strong_authority'];qualification=cfg['source_qualification']
    need(pins.get(ref['path'])==ref['sha256'] and sha(ref['path'],check)==ref['sha256'],'strong_authority_changed')
    authority=read(ref['path']);root_ref=qualification['root']
    need(authority.get('schema')=='qwen-three-hour-strong-recipe-authority-v1'
         and authority.get('qualified_root_sha256')==root_ref['sha256']
         and authority.get('kind')==row['task']['kind'] and authority.get('metric')==row['task']['metric'],
         'current_qualified_raw_recipe_authority_required')
    need(pins.get(root_ref['path'])==root_ref['sha256'] and sha(root_ref['path'],check)==root_ref['sha256'],
         'source_qualification_root_changed')
    root=read(root_ref['path']);audit_ref=root['independent_audit']
    need(root.get('technical_procedure_passed') is True and pins.get(audit_ref['path'])==audit_ref['sha256']
         and sha(audit_ref['path'],check)==audit_ref['sha256'],'actual_qualified_independent_artifact_map_required')
    audited=read(audit_ref['path']);report_ref=authority['source_report'];actual=audited['actual_artifact_sha256']
    need(audited.get('artifact_procedure_passed') is True and audited.get('archive_sha256')==qualification['archive']['sha256']
         and actual.get(report_ref['path'])==pins.get(report_ref['path'])==report_ref['sha256']
         and sha(report_ref['path'],check)==report_ref['sha256'],'strong_report_not_qualified_and_source_bound')
    report=read(report_ref['path']);recipe=report['selected_recipe'] if row['task']['kind']=='classification' else report['recipe']
    need(row['spec']==report['spec'] and authority.get('recipe')==row['task']['strong_recipe']==recipe,
         'actual_selected_raw_recipe_and_strict_spec_required')
    def raw(value):
        if isinstance(value,dict):
            need('fit_iterations' not in value,'historical_or_fullfit_tree_override_forbidden')
            for item in value.values():raw(item)
        elif isinstance(value,list):
            for item in value:raw(item)
    raw(recipe)
    need(all(actual.get(cut['path'])==pins.get(cut['path'])==cut['sha256'] for cut in row['task']['cuts']),
         'new_control_cuts_must_bind_actual_qualified_row_partitions')

def postfailure_qualification(cfg,check,root,fresh,post,c):
    """A new no-fit qualification of saved standard artifacts; old RQ6 stays FAIL."""
    refs=cfg['source_qualification'];pins=cfg['immutable_files']
    need(refs.get('mode')=='postfailure_saved_standard_artifacts_v1','typed_postfailure_admission_required')
    expected={k:dict(path=str(WORK/rel),sha256=h) for k,(rel,h) in RA1_ORIGINAL_REFS.items()}
    need(refs.get('original_rq6')==root.get('original_rq6')==expected,'exact_original_failed_RQ6_lineage_required')
    def bound(ref,decode=True):
        need(type(ref) is dict and set(ref)=={'path','sha256'} and Path(ref['path']).is_absolute()
             and pins.get(ref['path'])==ref['sha256'] and sha(ref['path'],check)==ref['sha256'],
             'postfailure_saved_proof_changed')
        return read(ref['path']) if decode else None
    old={key:bound(ref,key!='old_auditor') for key,ref in expected.items()}
    need(root.get('schema')=='postfailure-standard-artifact-qualification-root-v1'
         and root.get('technical_procedure_passed') is True and root.get('original_RQ6_FAIL_preserved') is True
         and root.get('original_RQ6_procedure_requalified') is False
         and root.get('original_failed_driver')==dict(session=49569,exit_code=1,tool='dbc6a1')
         and root.get('original_failed_frozen_closer')==dict(exit_code=1,tool='fb3841'),
         'new_saved_artifact_proof_never_relabels_old_RQ6')
    need(all(root.get(k) is True for k in ('source_unchanged','cleanup_confirmed','temporary_cleanup_confirmed'))
         and root.get('active_owned_processes')==root.get('uncertain_owned')==root.get('changed_source_or_core')==[],
         'current_postfailure_source_cleanup_required')
    qmanifest=bound(refs['qualification_manifest'])
    qualified_output=Path(qmanifest.get('output',''))
    need(qmanifest.get('readiness')=='READY_REVIEWED_FROZEN' and qualified_output.is_absolute()
         and qualified_output.resolve()==qualified_output and qualified_output!=WORK and qualified_output.is_relative_to(WORK)
         and refs['root']['path']==str(qualified_output/'terminal-root-closure.json')
         and refs['confirmation']['path']==str(qualified_output/'root-confirmation.json')
         and refs['post_tool']['path']==str(qualified_output/'actual-wrapper-exit-confirmation.json')
         and root.get('manifest_sha256')==refs['qualification_manifest']['sha256'],
         'actual_new_RA1_manifest_required')
    manifest,campaign,failed=old['manifest'],old['campaign'],old['root']
    need(manifest.get('readiness')=='READY_REVIEWED_FROZEN' and manifest.get('output')==str(WORK/'rq6')
         and manifest['executor']['archive']==refs['archive']
         and len(manifest['immutable_files'])==1017
         and all(pins.get(p)==h for p,h in manifest['immutable_files'].items()),'same_original_standard_source_input_union')
    need(campaign.get('status')=='failed' and campaign.get('manifest_sha256')==expected['manifest']['sha256']
         and campaign.get('active_supervisor') is None and campaign.get('independent_audit') is None
         and campaign.get('failure_code')==campaign.get('first_failure',{}).get('code')=='child_nonzero_exit'
         and campaign['first_failure'].get('child_kind')=='independent-audit'
         and len(campaign.get('contracts',[]))==9 and sum(row['expected'] for row in campaign['contracts'])==119
         and len(campaign.get('supervisors',[]))==12
         and [row['kind'] for row in campaign.get('tasks',[])]==['regression','classification'],
         'original_119_and_both_sealed_models_followed_by_audit_failure_required')
    need(failed.get('schema')=='standard-repair-qualification-root-closure-v1'
         and failed.get('technical_procedure_passed') is False and failed.get('qualified_ML_metrics') is None
         and failed.get('independent_audit') is None and failed.get('manifest_sha256')==expected['manifest']['sha256']
         and failed.get('actual_exec_session')==49569 and failed.get('actual_exec_exit_code_observed_by_root')==1
         and failed.get('actual_tool_evidence')=='dbc6a1'
         and all(failed.get(k) is True and campaign.get(k) is True for k in ('cleanup_confirmed','source_unchanged','temporary_cleanup_confirmed')),
         'original_failed_procedure_must_remain_failed')
    for row in campaign['tasks']:
        seal=expected[row['kind']+'_seal'];record=row['supervisor']
        need(row['seal']['sha256']==seal['sha256'],'original_two_core_seals_required')
        sup_ref=dict(path=str(WORK/record['path']),sha256=record['sha256']);sup=bound(sup_ref)
        need(sup.get('status')=='ok' and sup.get('exit_code')==0 and sup.get('cleanup_confirmed') is True
             and sup.get('cleanup_observation',{}).get('denial_count')==0
             and sup.get('cleanup_observation',{}).get('unresolved')==[], 'actual_original_both_standard_solvers_exit0_required')
    negative,oldpost=old['negative'],old['post']
    need(negative.get('schema')=='rq6-separate-current-negative-closure-v1'
         and oldpost.get('schema')=='rq6-current-negative-post-tool-confirmation-v1'
         and negative.get('known_count')==8010 and oldpost.get('known_count')==8013
         and oldpost.get('negative_closure_sha256')==expected['negative']['sha256']
         and oldpost.get('post_tool_current_confirmation') is True,'actual_separate_current_negative_proofs_required')
    for value in (negative,oldpost):
        need(value.get('technical_procedure_passed') is False and value.get('original_RQ6_FAIL_preserved') is True
             and value.get('root60_requalified') is False and value.get('new_metrics') is None
             and value.get('original_negative_root_sha256')==expected['root']['sha256']
             and all(value.get(k) is True for k in ('current_source_unchanged','current_cleanup_confirmed','current_temporary_absent','inside_original6000'))
             and value.get('known_exact_live')==value.get('uncertain')==[], 'negative_ownership_proof_is_not_old_qualification')
    oldknown=c.ids(oldpost['known_identities'])|c.ids(oldpost['observer_preparer_identities'])
    need(len(c.ids(oldpost['known_identities']))==len(oldpost['known_identities'])==8013
         and c.ids(negative['known_identities'])|c.ids(negative['observer_preparer_identities'])==c.ids(oldpost['known_identities'])
         and len(oldknown)==8016,'complete_original8016_scope_required')
    context=bound(root['repair_context']);audit_ref={k:root['independent_audit'][k] for k in ('path','sha256')};audit=bound(audit_ref)
    need(context.get('schema')=='rq6-saved-terminal-audit-repair-private-v1'
         and context.get('current_caller_manifest')==refs['qualification_manifest']
         and audit.get('schema')=='postfailure-standard-artifact-audit-v1'
         and audit.get('artifact_procedure_passed') is True and audit.get('archive_sha256')==refs['archive']['sha256']
         and audit.get('manifest_sha256')==expected['manifest']['sha256']
         and audit.get('repair_context_sha256')==root['repair_context']['sha256']
         and audit.get('original_RQ6_procedure_requalified') is False and audit.get('original_failure_preserved') is True
         and audit.get('audit_within_original_common_clock') is True and audit.get('audit_within_repair_clock') is True,
         'new_no_fit_independent_artifact_qualification_required')
    actual,wrapper=refs['driver_actual'],refs['wrapper_actual']
    need(root.get('actual_exec_session')==actual['session'] and root.get('actual_exec_exit_code_observed_by_root')==0
         and root.get('actual_tool_evidence')==actual['tool'] and root.get('archive_sha256')==refs['archive']['sha256'],
         'actual_new_RA1_driver_exit_and_archive_required')
    flags=('source_unchanged','current_temporary_absent','current_cleanup_confirmed',
        'inside_actual_closer_birth60','inside_original600','inside_inherited_RQ6_common6000')
    need(fresh.get('schema')=='postfailure-standard-artifact-atomic-root-confirmation-v1'
         and fresh.get('root_sha256')==refs['root']['sha256'] and fresh.get('actual_driver')==actual
         and fresh.get('actual_closer_exit')==0 and fresh.get('technical_procedure_passed') is True
         and fresh.get('inside_existing_driver_final240') is True and all(fresh.get(k) is True for k in flags)
         and fresh.get('known_exact_live')==fresh.get('uncertain')==fresh.get('errors')==[], 'actual_new_RA1_atomic_fresh_required')
    known=c.ids(fresh['known_identities'])|c.ids(fresh['wrapper_preparer_identities'])
    need(len(c.ids(fresh['known_identities']))==fresh['known_count']==len(fresh['known_identities'])
         and oldknown<=known and c.ids(root['owned_identities']+root['closure_preparer_identities'])<=known,
         'complete_old_and_new_RA1_owned_scope_required')
    need(post.get('schema')=='postfailure-standard-artifact-actual-wrapper-exit-confirmation-v1'
         and post.get('root_sha256')==refs['root']['sha256'] and post.get('root_confirmation_sha256')==refs['confirmation']['sha256']
         and post.get('actual_driver')==actual and post.get('actual_wrapper')==wrapper
         and post.get('known_count')==len(post['known_identities'])==len(known) and c.ids(post['known_identities'])==known
         and all(post.get(k) is True for k in flags) and post.get('post_tool_confirmed') is True
         and post.get('inside_saved_driver_final240') is True
         and post.get('known_exact_live')==post.get('uncertain')==[], 'actual_new_RA1_posttool_and_full_union_required')
    return known|c.ids(post['post_tool_preparer_identities'])

def predecessor(cfg,check):
    c=qualified();pins=cfg['immutable_files'];refs=cfg['source_qualification']
    for name in ('archive','root','confirmation','post_tool'):
        ref=refs[name];need(pins.get(ref['path'])==ref['sha256'] and sha(ref['path'],check)==ref['sha256'],'actual_archive_qualification_ref_changed')
    root,fresh,post=(read(refs[k]['path']) for k in ('root','confirmation','post_tool'))
    actual=refs['driver_actual'];wrapper=refs['wrapper_actual'];post_actual=refs['post_tool_actual']
    need(set(actual)=={'session','exit_code','tool'} and actual['exit_code']==0 and actual['tool']
         and (actual['session'] is None or type(actual['session']) is int and actual['session']>0)
         and set(wrapper)==set(post_actual)=={'exit_code','tool'} and wrapper['exit_code']==post_actual['exit_code']==0
         and wrapper['tool'] and post_actual['tool'],'actual_whole_archive_driver_and_wrapper_exits_required')
    if root.get('schema')=='postfailure-standard-artifact-qualification-root-v1':
        known=postfailure_qualification(cfg,check,root,fresh,post,c)
    else:
        need(root.get('schema')=='standard-repair-qualification-root-closure-v1' and root.get('technical_procedure_passed') is True
             and all(root.get(k) is True for k in ('source_unchanged','cleanup_confirmed','temporary_cleanup_confirmed'))
             and root.get('actual_exec_session')==actual['session'] and root.get('actual_exec_exit_code_observed_by_root')==0
             and root.get('actual_tool_evidence')==actual['tool'] and root.get('archive_sha256')==refs['archive']['sha256']
             and root.get('active_owned_processes')==root.get('uncertain_owned')==root.get('changed_source_or_core')==[],'actual_both_task_archive_qualification_required')
        need(fresh.get('schema')=='standard-repair-atomic-root-confirmation-v1' and fresh.get('root_sha256')==refs['root']['sha256']
             and fresh.get('actual_driver')==actual and fresh.get('actual_closer_exit')==0
             and all(fresh.get(k) is True for k in ('technical_procedure_passed','source_unchanged','current_temporary_absent','current_cleanup_confirmed',
                 'inside_actual_closer_birth60','inside_original6000','inside_existing_driver_final240'))
             and fresh.get('known_exact_live')==fresh.get('uncertain')==fresh.get('errors')==[],'actual_archive_atomic_root_fresh_required')
        known=c.ids(fresh['known_identities'])|c.ids(fresh['wrapper_preparer_identities'])
        need(len(c.ids(fresh['known_identities']))==fresh['known_count']==len(fresh['known_identities'])
             and c.ids(root['owned_identities']+root['closure_preparer_identities'])<=known,'complete_archive_owned_and_preparer_scope')
        need(post.get('schema')=='standard-repair-actual-wrapper-exit-confirmation-v1'
             and post.get('root_sha256')==refs['root']['sha256'] and post.get('root_confirmation_sha256')==refs['confirmation']['sha256']
             and post.get('actual_driver')==actual and post.get('actual_wrapper')==wrapper
             and post.get('known_count')==len(known) and post.get('known_exact_live')==post.get('uncertain')==[]
             and post.get('source_unchanged') is True and post.get('post_tool_confirmed') is True,'actual_wrapper_tool_exit_and_full_known_fresh')
        known|=c.ids(post['post_tool_preparer_identities'])
    for ref in cfg.get('launch_preparer_receipts',[]):
        need(set(ref)=={'path','sha256','actual_tool'} and ref['actual_tool']['exit_code']==0 and ref['actual_tool']['tool']
             and pins.get(ref['path'])==ref['sha256'] and sha(ref['path'],check)==ref['sha256'],'actual_later_preparer_binding')
        known|=c.ids(read(ref['path'])['identities'])
    return known
