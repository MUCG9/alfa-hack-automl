"""RA1: one saved-standard-artifact audit; no training/API or old PASS rewrite."""
from pathlib import Path
import argparse,ast,copy,hashlib,importlib.util,json,math,os,re,shutil,sys,tempfile,time

PACKET=Path(__file__).resolve().parent;WORK=PACKET.parent;OUT=WORK/'ra2'
COMMON,SETUP,AUDIT,FINAL,ROOT_CLOSE=600,180,120,240,60
BASE_PATH=WORK/'br-standard-release-qualification-next-dev/controller-r5/run_controller.py'
BASE_SHA='d5f41cad6de2168cd520e442223428285dd3714854079d9305dd1b34938abd7d'
LAUNCHER_PATH=WORK/'venv/Scripts/python.exe'
LAUNCHER_SHA='d59c9a894b319828d023f3aa83d9a3488d2339f9e27e60e49b02abb0d53cf538'
AUDITOR_PATH='rq6-no-fit-audit-repair-next-dev-r2/artifact_audit.py'
AUDITOR_SHA='7d201758d1af8f6ca6f73c6e3715d15301817426bd1987060776039815e15ce6'
AUDITOR_TEST_PATH='rq6-no-fit-audit-repair-next-dev-r2/test_saved_terminal_bridge.py'
AUDITOR_TEST_SHA='4def680502b9d10cc54e8f970f7328dd51e81dd30342db88a8ba8c59a02a51d9'
AUDITOR_TEST_METHODS={'SavedTerminalTests.test_stable_sample_then_exit_preserves_original_None_and_unknown_timestamp': '5cea1a7d196cef14d784941143fc2be516c4fc883dbc4e26e10b90f3866395f7', 'SavedTerminalTests.test_None_without_qualified_source_or_exact_proof_stops': '56c30d4880072bd33a40f2a138d148df128275562b6627aab47fce0f0e579f4c', 'SavedTerminalTests.test_missing_denied_or_unconfirmed_strict_receipts_stop': 'd2cce5aff2b34c14d6f4a5c13dabb6bd5834622e0eabd7795a89afaef9e3ba80', 'SavedTerminalTests.test_wrong_birth_or_missing_self_root_is_not_zero_RSS': '19de28636f37c3990b387e6a72db8845f0427c24b89592b96ca9f8d3d94abe03', 'SavedTerminalTests.test_duplicate_departed_and_invalid_RSS_samples_stop': '063da51e641080a778d34e6ad630951622c697010a6e2edadbe773471b0d9cb7', 'SavedTerminalTests.test_worker_whole_caps_and_underreported_peaks_stop': '5ad433cb415fdcbc1a31576f2983f46e8d79bfca27da51219d823fac4c545525', 'SavedTerminalTests.test_original_clock_or_actual_sample_receipt_mismatch_stops': '30ae78b9a27711cb69dcd8671dabd9d83fae9c48ef475e16e30740b09729ce19', 'SavedTerminalTests.test_original_two_terminal_branches_remain_separate_and_malformed_stops': '2530fdede3da38fe0a9b8ab2dacba62df5b3737ba159decbacaa8f6b342293a7', 'SavedTerminalTests.test_current_negative_exact_union_never_changes_old_FAIL': 'd0d733495a0fbeb1aef811f3dd2067c83b7526940b765dfa1d579b7b8775ca87', 'SavedTerminalTests.test_negative_post_actual_exit_and_current_identity_gaps_stop': 'e687dd7fb6d9791d794dba194de584554282be61dd09943107af4c2fab51ecd5', 'SavedTerminalTests.test_new_phase_and_common_clocks_are_both_original_and_finite': '4c013913eb57d80e56d092541e3478c2565a8b6b15948fc32a09926feaf85d48', 'SavedTerminalTests.test_all_cores_and_repair_proofs_precede_first_manual_verifier_import': '92478ed16c84b1f817d48578e0d1d9a78999cc511f761bf348cd32a341d9d008', 'CachedMixtureContracts.test_cached_mixture_requires_same_R4_parent_and_all_children_without_faking_leaf_receipts': '1c4685d614e9f7a76ba8e17367b1bb9aec0d8c9b5b84fd4817eb21a523cc95ae', 'CachedMixtureContracts.test_unverified_missing_duplicate_wrong_cut_full_or_job_cached_parent_stops': '1c2c087c8d07c689200887592414cc6907c8ee9db875482b77635a5aecb6784f', 'CachedMixtureContracts.test_hash_bound_current_caller_requires_exact_failed_RA1_and_current_full_union': 'c7e2892bf5da254736efd2f7eefd177754e6888b6cb27f726523342d626222ef'}
COUNTS=('uar-count-parser-next-dev/counts.py','bc320fd4723476c8a73404ed17a7bdec0cd4c69b1b1d41b321e370549c8cf4d3')
ARCHIVE_SHA='eb85becbff8da0be93b97a8dafff108e426cdbed07476ed4f1dc0fb95e73c6fc'
ORIGINAL_REFS={'manifest': ('private/rq6-manifest.ready-r1.json', 'f4eb5dca1e3560de66206c76937d0314a790047436bd80f218422c9324afd65a'), 'campaign': ('rq6/campaign.json', '60afb434d1e6f943d05be02c0761cdb255745fe3e543961ed407e559eaf38725'), 'root': ('rq6/terminal-root-closure.json', 'f9e26b3a9e9223fc903909aafd3172dbd0b4242b142d9d29cf8593a3379d9810'), 'negative': ('rq6/current-negative-closure.json', 'fe8941210806633144b53f2f1345daa3922f7099dc81148637da7240592ce0bc'), 'post': ('rq6/current-negative-post-tool-confirmation.json', '9ad55350293113fbf7c026762979e06cc40a350b948718c39b998b8dea316fdc'), 'barrier': ('rq6/pretruth-barrier.json', '1a1c52f62d0badc5e579437e3f90b376e6f3e8440ca6948afbc92e45c1d79781'), 'regression_seal': ('rq6/regression-core-seal.json', '53c6dde06429214624ad071349b6365e0ddd5f73f8a8f5080c8b0dfa81cc7a9d'), 'classification_seal': ('rq6/classification-core-seal.json', '6d9345942bcb8e3752cdf66ba35f13292ed3f0f3da64481c3418f63bea1652fd'), 'old_auditor': ('last-submission-repair-qualification-next-dev-r6/artifact_audit.py', '910f8c5374b147c1d665ed01cb93f9b492f17d5cee330621f0f23685854b7209')}

def need(value,code):
    if not value:raise RuntimeError(code)
def read(path):return json.loads(Path(path).read_text('utf-8'))
def save(path,value):
    path=Path(path);pending=path.with_name(path.name+'.pending')
    with pending.open('x',encoding='utf-8',newline='\n') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    os.replace(pending,path)
def sha(path,check=lambda:None):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            check();block=stream.read(2**20)
            if not block:break
            h.update(block)
    check();return h.hexdigest()
def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module
def methods(path):
    result={}
    for cls in ast.parse(Path(path).read_text('utf-8-sig')).body:
        if isinstance(cls,ast.ClassDef):
            for node in cls.body:
                if isinstance(node,ast.FunctionDef) and node.name.startswith('test_'):
                    key=cls.name+'.'+node.name;need(key not in result,'duplicate_contract_method')
                    result[key]=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
    return result

RA1_REFS={'manifest': ('private/ra1-manifest.ready-r2.json', '84b93538b73d73e2636b0730ad4cd105b2901633990e4654ccf9463e724d63f3'), 'campaign': ('ra1/campaign.json', '20fb2e4f4251218e62f1e91126ce581dc2c4cfc6a692d004d4b1b6aad7585536'), 'root': ('ra1/terminal-root-closure.json', '94132c7d68a49e7e85ee795f648db724891b8ea6ba7f670dacb151ac63afc6ca'), 'negative': ('ra1/current-negative-closure.json', '8d8031316908f5924077fec9a59a4b8b6d0629e061cb41c914fd02a3df22a4f6'), 'post': ('ra1/current-negative-post-tool-confirmation.json', 'df952820dfaf86b662b7b5a0dbfb01b5ca951565e73b579c247ce5aa4c81f541')}

def ra1_previous(cfg,base,known,check=lambda:None):
    pins=cfg['immutable_files'];refs=cfg['ra1_previous']
    for key,(rel,h) in RA1_REFS.items():
        need(refs[key]==dict(path=str(WORK/rel),sha256=h) and pins.get(str(WORK/rel))==h and sha(WORK/rel,check)==h,'exact_failed_RA1_lineage_required')
    need(refs['driver_actual']==dict(session=25644,exit_code=1,tool='19905f')
        and refs['closer_actual']==dict(exit_code=1,tool='8efa0b')
        and refs['negative_actual']==dict(exit_code=0,tool='0707d9') and refs['post_actual']==dict(exit_code=0,tool='cd0ef7'),'actual_failed_RA1_and_current_tools_required')
    manifest,state,root,negative,post=(read(refs[k]['path']) for k in ('manifest','campaign','root','negative','post'))
    need(manifest.get('output')==str(WORK/'ra1') and len(manifest['immutable_files'])==1560
        and all(pins.get(p)==h for p,h in manifest['immutable_files'].items()),'complete_unchanged_RA1_source_union_required')
    need(state.get('status')=='failed' and len(state['contracts'])==3 and sum(r['expected'] for r in state['contracts'])==22
        and state.get('artifact_procedure_passed') is False and state.get('quality_metric') is None
        and state.get('active_supervisor') is None and state.get('first_failure',{}).get('child_kind')=='saved-standard-artifact-audit','actual_failed_RA1_after22_required')
    need(root.get('schema')=='postfailure-standard-artifact-qualification-root-v1' and root.get('technical_procedure_passed') is False
        and root.get('manifest_sha256')==refs['manifest']['sha256'] and root.get('actual_exec_session')==25644
        and root.get('actual_exec_exit_code_observed_by_root')==1 and root.get('actual_tool_evidence')=='19905f'
        and root.get('independent_audit') is None and root.get('quality_metric') is None
        and root.get('original_RQ6_FAIL_preserved') is True and root.get('original_RQ6_procedure_requalified') is False
        and all(root.get(k) is True for k in ('source_unchanged','cleanup_confirmed','temporary_cleanup_confirmed')),'failed_RA1_must_never_be_requalified')
    for key,value in [('negative',negative),('post',post)]:
        need(value.get('schema')==('ra1-separate-current-negative-closure-v1' if key=='negative' else 'ra1-current-negative-post-tool-confirmation-v1')
            and value.get('technical_procedure_passed') is False and value.get('original_RA1_FAIL_preserved') is True
            and value.get('original_RQ6_FAIL_preserved') is True and value.get('root60_requalified') is False
            and value.get('original_negative_root_sha256')==refs['root']['sha256'] and value.get('original_manifest_sha256')==refs['manifest']['sha256']
            and value.get('actual_failed_driver')==refs['driver_actual'] and value.get('actual_failed_frozen_closer')==refs['closer_actual']
            and value.get('source_pins_checked')==1560 and value.get('new_metrics') is None
            and all(value.get(k) is True for k in ('current_source_unchanged','current_cleanup_confirmed','current_temporary_absent','inside_original_RA1_common600','inside_inherited_RQ6_common6000'))
            and value.get('known_exact_live')==value.get('uncertain')==[],'current_RA1_negative_proof_is_not_positive_qualification')
    prior=base.ids(negative['known_identities']);obs=base.ids(negative['observer_preparer_identities']);confirmed=base.ids(post['known_identities']);postown=base.ids(post['observer_preparer_identities'])
    need(len(prior)==negative['known_count']==len(negative['known_identities'])==8039 and len(obs)==3 and not prior&obs
        and confirmed==prior|obs and len(confirmed)==post['known_count']==len(post['known_identities'])==8042
        and len(postown)==3 and not confirmed&postown and post.get('post_tool_current_confirmation') is True
        and post.get('negative_closure_sha256')==refs['negative']['sha256'] and post.get('actual_negative_observer')==refs['negative_actual']
        and base.ids(root['owned_identities']+root['closure_preparer_identities'])<=prior,'complete_current_RA1_8039_plus3_plus3_scope_required')
    confirmed|=postown;need(len(confirmed)==8045,'complete_RA1_8045_current_scope_required')
    return known|confirmed

def predecessor(cfg,check=lambda:None):
    need(sha(BASE_PATH)==BASE_SHA,'qualified_C5_changed');base=imported('_ra1_predecessor_C5',BASE_PATH)
    pins=cfg['immutable_files'];refs=cfg['rq6']
    for key,(relative,h) in ORIGINAL_REFS.items():
        need(refs[key]==dict(path=str(WORK/relative),sha256=h) and pins.get(str(WORK/relative))==h
             and sha(WORK/relative,check)==h,'exact_actual_RQ6_metadata_required')
    state,root,negative,post=(read(refs[k]['path']) for k in ('campaign','root','negative','post'))
    need(root.get('technical_procedure_passed') is False and root.get('actual_exec_session')==49569
         and root.get('actual_exec_exit_code_observed_by_root')==1 and root.get('actual_tool_evidence')=='dbc6a1'
         and all(root.get(k) is True for k in ('source_unchanged','cleanup_confirmed','temporary_cleanup_confirmed'))
         and root.get('manifest_sha256')==refs['manifest']['sha256'] and root.get('independent_audit') is None,
         'original_failed_RQ6_never_requalified')
    need(state.get('status')=='failed' and state.get('first_failure',{}).get('child_kind')=='independent-audit'
         and len(state['contracts'])==9 and sum(v['expected'] for v in state['contracts'])==119
         and [r['kind'] for r in state['tasks']]==['regression','classification'],'actual_saved119_and_both_tasks_required')
    for key,value in [('negative',negative),('post',post)]:
        expected_schema='rq6-separate-current-negative-closure-v1' if key=='negative' else 'rq6-current-negative-post-tool-confirmation-v1'
        need(value.get('schema')==expected_schema and value.get('technical_procedure_passed') is False
             and value.get('original_RQ6_FAIL_preserved') is True and value.get('root60_requalified') is False
             and value.get('original_negative_root_sha256')==refs['root']['sha256']
             and value.get('original_manifest_sha256')==refs['manifest']['sha256'] and value.get('source_pins_checked')==1017
             and value.get('actual_failed_driver')==dict(session=49569,exit_code=1,tool='dbc6a1')
             and value.get('actual_failed_frozen_closer')==dict(exit_code=1,tool='fb3841')
             and all(value.get(k) is True for k in ('current_source_unchanged','current_cleanup_confirmed','current_temporary_absent','inside_original6000'))
             and value.get('known_exact_live')==value.get('uncertain')==[],'actual_typed_current_negative_only_required')
    known=base.ids(post['known_identities']);prior=base.ids(negative['known_identities']);observer=base.ids(negative['observer_preparer_identities'])
    need(len(prior)==negative['known_count']==len(negative['known_identities'])==8010
         and len(observer)==3 and not prior&observer and known==prior|observer
         and len(known)==post['known_count']==len(post['known_identities'])==8013
         and post.get('post_tool_current_confirmation') is True
         and post.get('negative_closure_sha256')==refs['negative']['sha256']
         and post.get('actual_negative_observer')==dict(exit_code=0,tool='b449e3')
         and cfg['negative_actual']==dict(exit_code=0,tool='b449e3') and cfg['post_actual']==dict(exit_code=0,tool='317ee6'),
         'actual_negative_and_post_exit_scope_required')
    own=base.ids(post['observer_preparer_identities']);need(len(own)==3 and not own&known,'distinct_actual_post_observer_scope_required')
    known|=own;need(len(known)==8016,'complete8016_current_predecessor_scope')
    for ref in cfg.get('launch_preparer_receipts',[]):
        need(set(ref)=={'path','sha256','actual_tool'} and set(ref['actual_tool'])=={'exit_code','tool'}
             and ref['actual_tool']['exit_code']==0 and ref['actual_tool']['tool'] and 'PENDING' not in ref['actual_tool']['tool']
             and pins.get(ref['path'])==ref['sha256'] and sha(ref['path'],check)==ref['sha256'],'actual_later_preparer_receipt_required')
        known|=base.ids(read(ref['path'])['identities'])
    return ra1_previous(cfg,base,known,check)

def audit_clock(start,begin,admit_wall,admit_mono):
    values=(start,begin,admit_wall,admit_mono)
    need(all(type(v) in (int,float) and math.isfinite(v) for v in values),'finite_original_admission_required')
    need(start<=admit_wall and begin<=admit_mono and admit_mono+120+300<=begin+600
         and admit_wall+120+300<=start+600 and abs((admit_wall-start)-(admit_mono-begin))<=5,'original600_audit120_final300_reserve')
    return dict(start_unix=start,start_monotonic=begin,absolute_deadline_unix=start+600,common_deadline_monotonic=begin+600,
        audit_start_unix=admit_wall,audit_start_monotonic=admit_mono,audit_deadline_unix=admit_wall+120,audit_deadline_monotonic=admit_mono+120)

def audit_command(python,original_manifest,original_sha,context,context_sha,output):
    need(type(AUDITOR_SHA) is str and all(Path(p).is_absolute() for p in (python,original_manifest,context,output)),
         'fixed_auditor_and_absolute_metadata_required')
    return [python,'-B','-X','utf8',str(WORK/AUDITOR_PATH),'--manifest',original_manifest,'--manifest-sha256',original_sha,
        '--self-sha256',AUDITOR_SHA,'--repair-context',context,'--repair-context-sha256',context_sha,'--output',output]

def result_qualified(value,original_manifest_sha,context_sha):
    return (value.get('schema')=='postfailure-standard-artifact-audit-v1' and value.get('artifact_procedure_passed') is True
        and value.get('manifest_sha256')==original_manifest_sha and value.get('repair_context_sha256')==context_sha
        and value.get('archive_sha256')==ARCHIVE_SHA and value.get('audit_within_original_common_clock') is True
        and value.get('audit_within_repair_clock') is True and value.get('original_RQ6_procedure_requalified') is False
        and value.get('original_failure_preserved') is True and set(value.get('quality_metric',{}))=={'regression','classification'}
        and set(value.get('tasks',{}))=={'regression','classification'}
        and all(type(v) in (int,float) and math.isfinite(v) for v in value['quality_metric'].values())
        and value.get('new_model_fits')==0 and value.get('promotion') is False and value.get('submit') is False)

def config(path,digest,self_sha):
    need(__debug__ and Path(path).is_absolute() and Path(path).stat().st_size<=4*2**20 and sha(path)==digest,'bounded_frozen_absolute_manifest')
    cfg=read(path);pins=cfg['immutable_files']
    need(cfg.get('schema')=='postfailure-standard-artifact-qualification-private-v1' and cfg.get('readiness')=='READY_REVIEWED_FROZEN'
         and cfg.get('missing_bindings')==[],'NOT_READY')
    need(cfg['output']==str(OUT) and cfg['common_seconds']==600 and cfg['caps']==dict(setup=180,audit=[120,90],final=240,root=60),
         'fixed_new600_caps_and_output_required')
    need(type(pins) is dict and 1<=len(pins)<=4096 and all(Path(p).is_absolute() and type(h) is str and re.fullmatch('[0-9a-f]{64}',h) for p,h in pins.items()),
         'complete_typed_absolute_source_input_union')
    need(sha(__file__)==self_sha and pins.get(str(Path(__file__).resolve()))==self_sha and pins.get(str(BASE_PATH))==BASE_SHA
         and cfg['python']==str(LAUNCHER_PATH) and pins.get(cfg['python'])==LAUNCHER_SHA,'exact_caller_base_and_interpreter_required')
    need(cfg['lock']==str(WORK/'alfa-hack-automl/test-runs/.owned-research.lock'),'canonical_absolute_lock_required')
    need(type(AUDITOR_SHA) is str and cfg['auditor']==dict(path=str(WORK/AUDITOR_PATH),sha256=AUDITOR_SHA)
         and pins.get(cfg['auditor']['path'])==AUDITOR_SHA,'exact_final_auditor_required')
    for key,rel,h in [('auditor_handoff','rq6-no-fit-audit-repair-next-dev-r2/source-handoff-final.json','63228d4e3231f863893c07d5cd1c53ece52506cc4e767af2f7787ba0f84a15c6'),
        ('auditor_source_review','rq6-no-fit-audit-repair-fm-independent-review-r2.json','0971a8a5115747cfff33bc86148e831d73e7f21b25768d32269b95e0df8444d9')]:
        need(cfg[key]==dict(path=str(WORK/rel),sha256=h) and pins.get(str(WORK/rel))==h and sha(WORK/rel)==h,'final_independent_adapter_source_review_required')
    need(cfg['counts']==dict(path=str(WORK/COUNTS[0]),sha256=COUNTS[1]) and pins.get(cfg['counts']['path'])==COUNTS[1],'qualified_structural_counter_required')
    expected=[(str(WORK/AUDITOR_TEST_PATH),AUDITOR_TEST_SHA,AUDITOR_TEST_METHODS),
        (str(PACKET/'test_caller.py'),sha(PACKET/'test_caller.py'),methods(PACKET/'test_caller.py')),
        (str(PACKET/'test_atomic_root.py'),sha(PACKET/'test_atomic_root.py'),methods(PACKET/'test_atomic_root.py'))]
    need(len(cfg['contracts'])==3,'only_changed_adapter_caller_atomic_contract_slots')
    for row,(p,h,mm) in zip(cfg['contracts'],expected):
        need(row==dict(path=p,sha256=h,methods=mm,count=len(mm),parent=60,child=45)
             and pins.get(p)==h and methods(p)==mm and len(mm)>0,'exact_final_changed_method_AST_maps_required')
    for name in ('close_audit.py','run_root.py','close_child.ps1','confirm_post_tool.py'):
        need(str(PACKET/name) in pins,'complete_reviewed_orchestration_source_required')
    for key,(rel,h) in ORIGINAL_REFS.items():need(cfg['rq6'][key]==dict(path=str(WORK/rel),sha256=h) and pins.get(str(WORK/rel))==h,'exact_original_source_roles')
    payload=cfg['repair_payload'];need(payload.get('schema')=='rq6-saved-terminal-audit-repair-private-v1' and payload.get('clock') is None
         and payload.get('output')==str(OUT/'independent-artifact-audit.json') and payload.get('current_caller_manifest') is None
         and payload.get('original_failure_preserved') is True and payload.get('original_RQ6_procedure_requalified') is False,'static_reviewed_repair_payload_no_clock')
    for key,role in [('original_manifest','manifest'),('original_campaign','campaign'),('original_root','root'),
                     ('original_auditor','old_auditor'),('current_negative','negative'),('post_tool_confirmation','post')]:
        need(payload[key]==cfg['rq6'][role],'actual_repair_payload_roles_must_match_source')
    need(payload.get('actual_current_negative_observer')==cfg['negative_actual']
         and payload.get('actual_post_tool_observer')==cfg['post_actual'],'actual_context_observer_tools_required')
    original=read(cfg['rq6']['manifest']['path'])
    need(sha(cfg['rq6']['manifest']['path'])==cfg['rq6']['manifest']['sha256']
         and payload.get('executor_runtime_sha256')==original['executor']['members_sha256']['automl_release_runtime.py'],
         'exact_original_executor_runtime_source_required')
    return cfg


def capture(psutil,parent_pid,parent_birth):
    """Observe self/direct/shell; allow only direct or ONE pinned venv launcher.

    One microsecond absolute tolerance is ONLY for Get-Process ticks/Unix float
    transport. Saved identities always contain the exact observed psutil birth.
    Shell PID and fresh bounded OS relationships must match independently.
    """
    transported=parent_birth if type(parent_birth) in (int,float) and math.isfinite(parent_birth) else None
    rows=[];record=dict(declared=dict(pid=parent_pid,create_time=transported),
        declared_birth_invalid=transported is None,
        observed_parent=None,observed_shell=None,verified=False,transport_absolute_tolerance_seconds=1e-6)
    try:
        me=psutil.Process();own_birth=me.create_time();rows.append(dict(pid=me.pid,create_time=own_birth))
        parent=me.parent();need(parent is not None,'direct_launch_parent_missing')
        birth=parent.create_time();observed=dict(pid=parent.pid,create_time=birth);record['observed_parent']=observed
        need(type(parent_pid) is int and parent_pid>0 and type(parent_birth) in (int,float)
            and math.isfinite(parent_birth) and parent_birth>0,'typed_launch_parent_required')
        shell=parent;record['mode']='direct_declared_shell'
        if parent.pid!=parent_pid:
            exe=Path(parent.exe())
            need(not exe.is_symlink() and os.path.normcase(os.path.abspath(exe))==os.path.normcase(os.path.abspath(LAUNCHER_PATH))
                and sha(exe)==LAUNCHER_SHA,'exact_pinned_venv_launcher_required')
            shell=parent.parent();need(shell is not None,'declared_shell_missing_after_one_launcher')
            record['mode']='one_pinned_venv_launcher';record['launcher_executable_sha256']=LAUNCHER_SHA
        shell_birth=shell.create_time();shell_row=dict(pid=shell.pid,create_time=shell_birth);record['observed_shell']=shell_row
        need(shell.pid==parent_pid and abs(shell_birth-parent_birth)<=1e-6,'declared_shell_transport_or_extra_hop_mismatch')
        need(me.ppid()==parent.pid and me.create_time()==own_birth and parent.create_time()==birth,
            'direct_launch_parent_relationship_or_identity_changed')
        if shell.pid!=parent.pid:
            need(parent.ppid()==shell.pid and shell.create_time()==shell_birth,'launcher_shell_relationship_or_identity_changed')
        else:need(shell.create_time()==shell_birth,'declared_shell_identity_changed')
        rows.append(observed)
        if shell.pid!=parent.pid:rows.append(shell_row)
        record['verified']=True
    except BaseException as exc:
        record['error']=str(exc) if isinstance(exc,RuntimeError) else 'launch_parent_observation_unconfirmed'
        record['exception_type']=type(exc).__name__
    return rows,record

def temporary_fence(directory,check=lambda:None):
    root=(WORK/'t').resolve();need(directory.resolve()==directory and directory.parent==root
        and directory.name.startswith('ra-'),'exact_owned_shallow_temp_required')
    count=0
    for current,dirs,files in os.walk(directory,followlinks=False):
        for p in [Path(current),*[Path(current)/n for n in dirs+files]]:
            check()
            s=p.lstat();need(not p.is_symlink() and not (getattr(s,'st_file_attributes',0)&0x400),'temp_symlink_junction_or_reparse_denied')
            need(p.resolve().is_relative_to(directory),'temp_entry_outside_owned_root');count+=1
            need(count<=20000,'bounded_owned_temp_inventory')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--launch',action='store_true',required=True)
    for key in ('manifest','manifest-sha256','self-sha256'):p.add_argument('--'+key,required=True)
    p.add_argument('--launch-parent-pid',type=int,required=True);p.add_argument('--launch-parent-create-time',type=float,required=True)
    a=p.parse_args();start,begin=time.time(),time.monotonic();wall,end=start+COMMON,begin+COMMON
    import psutil
    preparers,parent=capture(psutil,a.launch_parent_pid,a.launch_parent_create_time)
    need(not OUT.exists(),'exclusive_new_output_no_retry');OUT.mkdir()
    save(OUT/'preparer-identity.json',dict(identities=preparers,launch_parent_observation=parent))
    allowed={'PATH','PATHEXT','SYSTEMROOT','WINDIR','COMSPEC','LOCALAPPDATA'}
    for key in list(os.environ):
        if key.upper() not in allowed:os.environ.pop(key,None)
    os.environ.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',AUTOML_THREADS='1',
        OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
    sys.dont_write_bytecode=True
    state=dict(schema='postfailure-standard-artifact-qualification-campaign-v1',status='starting',start_unix=start,start_monotonic=begin,
        absolute_deadline_unix=wall,common_deadline_monotonic=end,common_seconds=COMMON,
        owned_root=preparers[0] if preparers else None,coordinator_bootstrap_identities=preparers[1:],supervisors=[],active_supervisor=None,
        contracts=[],error_history=[],cleanup_uncertainty=[],cleanup_confirmed=False,source_unchanged=False,temporary_cleanup_confirmed=False,
        artifact_procedure_passed=False,quality_metric=None,qualified_artifacts=None,promotion=False,submit=False,new_model_fits=0,API_calls=0,_manifest={})
    cfg=base=coor=owner=awake=lease=tmp=None;modules={};known=set();sealed={};pulse=lambda **kwargs:None
    def persist():save(OUT/'campaign.json',{k:v for k,v in state.items() if not k.startswith('_')})
    def fail(exc,phase):
        code=str(exc) if isinstance(exc,RuntimeError) and re.fullmatch('[A-Za-z0-9_:+.-]{1,200}',str(exc)) else type(exc).__name__
        row=dict(code=code,phase=phase,exception_type=type(exc).__name__,errno=getattr(exc,'errno',None),winerror=getattr(exc,'winerror',None))
        state.setdefault('first_failure',row);state['error_history'].append(row)
        state.update(status='failed',artifact_procedure_passed=False,quality_metric=None,qualified_artifacts=None)
    def check(phase=None,code='phase_cap'):
        pulse();need(time.monotonic()<end and time.time()<wall,'new600_or_inherited_original6000_exhausted')
        if phase is not None:need(time.monotonic()<phase,code)
    def frozen(phase=None,code='frozen_over_cap'):
        callback=lambda:check(phase,code)
        for path,h in {**cfg['immutable_files'],**sealed}.items():need(sha(path,callback)==h,'source_input_core_or_terminal_changed')
    def run(argv,cwd,name,parent_seconds,child_seconds,reserve,parent_start=None):
        tick=time.monotonic() if parent_start is None else parent_start
        need(min(end-time.monotonic(),wall-time.time())>=reserve,'remaining_complete_phases_required')
        receipt=tmp/(name+'.json')
        try:sup=coor.supervise(argv,cwd,receipt,name,tick,parent_seconds,child_seconds,end,wall,reserve,
            state,persist,frozen,owner,modules['processes'],preparers[1:],solver_seconds=None)
        finally:
            if receipt.exists():
                observed=read(receipt);known.update(base.ids(observed.get('owned_process_identities',[])))
                if observed.get('owned_root'):known.update(base.ids([observed['owned_root']]))
                ob=observed.get('cleanup_observation',{})
                if observed.get('cleanup_confirmed') is not True or ob.get('unresolved')!=[] or ob.get('denial_count')!=0:
                    state['cleanup_uncertainty'].append(dict(scope=name,receipt=str(receipt),observation=ob))
            else:state['cleanup_uncertainty'].append(dict(scope=name,reason='missing_actual_supervisor_receipt'))
        coor.child_errors(state,sup);target=OUT/'supervisors';target.mkdir(exist_ok=True)
        for ext in ('.json','.log'):
            src=receipt.with_suffix(ext);dest=target/(name+ext);shutil.copyfile(src,dest);sealed[str(dest)]=sha(dest,check)
            need(sha(src,check)==sealed[str(dest)],'terminal_copy_changed')
        state['supervisors'][-1]['path']=coor.relative(target/(name+'.json'));persist()
        need(sup.get('status')=='ok' and sup.get('exit_code')==0 and sup.get('cleanup_confirmed') is True
            and not sup.get('error_history'),'mandatory_changed_contract_or_audit_failed')
        return dict(path=str(target/(name+'.json')),sha256=sealed[str(target/(name+'.json'))],record=sup)
    try:
        need(parent.get('verified') is True,'exact_launch_parent_unconfirmed')
        cfg=config(a.manifest,a.manifest_sha256,a.self_sha256);state['_manifest']=cfg
        original=read(cfg['rq6']['campaign']['path'])
        need(sha(cfg['rq6']['campaign']['path'])==cfg['rq6']['campaign']['sha256'],'original_RQ6_campaign_changed')
        need(original['absolute_deadline_unix']==original['start_unix']+6000
            and original['common_deadline_monotonic']==original['start_monotonic']+6000,'inherited_original6000_not_reset')
        state['inherited_original_clock']={k:original[k] for k in ('start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic')}
        end=min(end,original['common_deadline_monotonic']);wall=min(wall,original['absolute_deadline_unix'])
        state['effective_deadline_monotonic']=end;state['effective_deadline_unix']=wall
        need(sha(BASE_PATH)==BASE_SHA,'verified_C5_base_changed');base=imported('_ra1_base',BASE_PATH)
        for key,(relative,h) in base.HELPERS.items():
            need(cfg['immutable_files'].get(str(WORK/relative))==h and sha(WORK/relative)==h,'qualified_helper_changed')
            modules[key]=imported('_ra1_'+key,WORK/relative)
        coor,owner=modules['coordinator'],modules['owner'];pulse=base.guard(begin,end,wall,owner,preparers,state);state['_pulse']=pulse
        check();known=predecessor(cfg,check)
        # Only immutable previously sealed inventories; no copy/unpack/fit.
        for role in ('regression_seal','classification_seal'):
            ref=cfg['rq6'][role];need(sha(ref['path'],check)==ref['sha256'],'saved_core_seal_changed')
            inventory=read(ref['path'])['files_sha256'];need(type(inventory) is dict and len(inventory)<=20000,'bounded_saved_core_inventory')
            for path,h in inventory.items():
                need(Path(path).is_absolute() and re.fullmatch('[0-9a-f]{64}',h),'typed_saved_core_hash')
                need(path not in cfg['immutable_files'] or cfg['immutable_files'][path]==h,'saved_core_source_pin_collision')
                need(path not in sealed or sealed[path]==h,'two_saved_core_pin_collision');sealed[path]=h
        frozen()
        base.absent(owner,known,check);lease=modules['lock'].ResearchLock(cfg['lock']);lease.__enter__();lease.write_identity(preparers[0])
        base.absent(owner,known,check);awake=modules['awake'].PowerRequestGuard('RA1-saved-standard-artifact-audit');awake.__enter__();state['_awake']=awake
        check();setup_end=begin+SETUP;frozen(setup_end);(WORK/'t').mkdir(exist_ok=True)
        tmp=Path(tempfile.mkdtemp(prefix='ra-',dir=WORK/'t')).resolve();state['temporary_root']=str(tmp);state['status']='contracts';persist()
        counter=imported('_ra1_counter',cfg['counts']['path'])
        for index,contract in enumerate(cfg['contracts']):
            name=('auditor-contracts','caller-contracts','atomic-root-contracts')[index];path=contract['path'];expected=contract['count']
            check(setup_end);need(setup_end-time.monotonic()>=60,'full_changed_contract_slot_required')
            ref=run([cfg['python'],'-B','-X','utf8',path,'-v'],Path(path).parent,name,60,45,420+60)
            need(counter.counts(Path(ref['path']).with_suffix('.log').read_text('utf-8'),expected),'exact_changed_contract_count_no_skip_required')
            state['contracts'].append(dict(name=name,expected=expected,supervisor=ref));persist();check(setup_end)
        # A genuine admission timestamp BEFORE forced verified sampling. It is
        # a conservative old observation bound, never a reset after slow work.
        admission_unix,admission_mono=time.time(),time.monotonic();pulse(force=True)
        payload=copy.deepcopy(cfg['repair_payload']);payload['clock']=audit_clock(start,begin,admission_unix,admission_mono)
        payload['current_caller_manifest']=dict(path=str(Path(a.manifest).resolve()),sha256=a.manifest_sha256)
        need(payload['clock']['audit_deadline_monotonic']+300<=end
            and payload['clock']['audit_deadline_unix']+300<=wall,'full_audit_and_final_inside_both_commons')
        context=OUT/'repair-context.json';save(context,payload);sealed[str(context)]=sha(context,check)
        output=OUT/'independent-artifact-audit.json';state['status']='auditing';state['audit_binding']=dict(path=str(context),sha256=sealed[str(context)]);persist()
        original_manifest=cfg['rq6']['manifest']
        ref=run(audit_command(cfg['python'],original_manifest['path'],original_manifest['sha256'],str(context),sealed[str(context)],str(output)),WORK,
            'saved-standard-artifact-audit',120,90,420,parent_start=admission_mono)
        result=read(output);need(result_qualified(result,original_manifest['sha256'],sealed[str(context)]),
            'saved_standard_artifact_audit_unqualified')
        sealed[str(output)]=sha(output,check);state.update(status='completed_pending_root',artifact_procedure_passed=True,
            independent_audit=dict(path=str(output),sha256=sealed[str(output)],supervisor=ref),quality_metric=result['quality_metric'],qualified_artifacts=result['tasks'])
    except BaseException as exc:fail(exc,'saved_artifact_audit')
    finally:
        final_begin=time.monotonic();final_deadline=min(final_begin+FINAL,end-ROOT_CLOSE)
        state.update(final_start_monotonic=final_begin,final_deadline_monotonic=final_deadline)
        try:
            check(final_deadline);need(base is not None and cfg is not None,'final_authority_unavailable')
            base.absent(owner,known,check);frozen(final_deadline)
            need(state['active_supervisor'] is None and not state['cleanup_uncertainty']
                and all(s.get('cleanup_confirmed') is True for s in state['supervisors']),'sticky_child_cleanup_unconfirmed')
            if tmp is not None:
                temporary_fence(tmp,lambda:check(final_deadline));state['temporary_pins_verified_before_removal']=base.seal(tmp,lambda:check(final_deadline))
                base.absent(owner,known,check);shutil.rmtree(tmp);check(final_deadline);need(not tmp.exists(),'owned_temp_not_removed')
            state.update(cleanup_confirmed=True,source_unchanged=True,temporary_cleanup_confirmed=True)
        except BaseException as exc:fail(exc,'final_cleanup');state['cleanup_confirmed']=False
        try:
            if awake is not None:awake.close();state['awake_guard']=awake.record
            pulse(force=True);check(final_deadline);need(state.get('awake_guard',{}).get('release_API_verified') is True,'power_release_unconfirmed')
        except BaseException as exc:fail(exc,'power_release')
        state['owned_process_identities']=[dict(pid=p,create_time=b) for p,b in sorted(known)]
        state.update(finished_unix=time.time(),finished_monotonic=time.monotonic(),elapsed_common_seconds=time.monotonic()-begin)
        try:persist();pulse(force=True);check(final_deadline)
        except BaseException as exc:fail(exc,'terminal_save');persist()
        finally:
            if lease is not None:lease.__exit__(None,None,None)
        try:
            check(final_deadline);state.update(finished_unix=time.time(),finished_monotonic=time.monotonic(),elapsed_common_seconds=time.monotonic()-begin)
            persist();check(final_deadline)
        except BaseException as exc:fail(exc,'postlease');persist()
    passed=state['status']=='completed_pending_root' and not state['error_history'] and state['cleanup_confirmed']
    print(json.dumps(dict(artifact_procedure_passed=bool(passed),quality_metric=state['quality_metric'],promotion=False),allow_nan=False))
    return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
