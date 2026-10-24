"""Prospective fixed two-task iterative Qwen campaign. SOURCE ONLY / NOT_READY."""
from pathlib import Path
from contextlib import contextmanager
import argparse,ast,hashlib,importlib.util,json,math,os,re,shutil,sys,tempfile,time

PACKET=Path(__file__).resolve().parent
WORK=PACKET.parent
OUT=WORK/'qh3'
COMMON,SETUP,AUDIT,FINAL,ROOT_CLOSE=10800,300,600,240,60
BASE=WORK/'br-standard-release-qualification-next-dev/controller-r5/run_controller.py'
BASE_SHA='d5f41cad6de2168cd520e442223428285dd3714854079d9305dd1b34938abd7d'
CORE=WORK/'qwen-three-hour-autoresearch-next-dev-r8'
CORE_SHA='efa770c766eaa4a49392193d24fd867cfd8ca5a9b64f44a8f07c4466e8aecd58'
AUDITOR=WORK/'qwen-three-hour-independent-audit-next-dev-r5'
AUDITOR_HANDOFF_SHA='9b125b77d9bab42b32cda96f42ac3379968dfdd80f0e7e59a153942024d217f8'
SOURCE_REVIEWS={'core': ('qwen-core-r8-audit-contract-source-review-r1.json', 'ad7276ef831c01596cb02ab520bdab2ca35beb908ac4a3e845a46d31c4eda632'), 'auditor': ('qwen-three-hour-independent-audit-source-review-r5.json', 'b6281b8dfd3226f9e787b8a98b1f0683a3e37b7e6755b9f74d663dd393453521')}
LAUNCHER_PATH=WORK/'venv/Scripts/python.exe'
LAUNCHER_SHA='d59c9a894b319828d023f3aa83d9a3488d2339f9e27e60e49b02abb0d53cf538'
HELPERS={
 'coordinator':('verified-supervision-next-dev-r2/coordinator.py','bd864b13460d31176d57e1dbddbe179ad8e6911163b117e3f9698228c5540f76'),
 'sampling':('verified-resource-sampling-next-dev/verified_sampling.py','d65ee39eb80c9fc4590cbbf474ee6c09e84cb65abe2d2c367ebcfa415a390cf0'),
 'owner':('support_component_coordinator.py','8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8'),
 'processes':('historical-runtime-support/fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d.py','fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d'),
 'lock':('alfa-hack-automl/tools/research_lock.py','78a0441bb3b9ea60197e9a1a6e1087f6e4cd0886593ec54bcfc4e41c9abe5a45'),
 'awake':('awake-next-dev/awake_guard.py','9a0bae0acb6ddb37e638420c52ad1e587a9180fbd7ef68ebc6e1a3c43e4bfc9b')}

def need(value,code):
    if not value:raise RuntimeError(code)

def read(path):return json.loads(Path(path).read_text('utf-8'))

def save(path,value):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.pending')
    with temporary.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    os.replace(temporary,path)

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

def methods(path):
    result={}
    for cls in ast.parse(Path(path).read_text('utf-8-sig')).body:
        if isinstance(cls,ast.ClassDef):
            for node in cls.body:
                if isinstance(node,ast.FunctionDef) and node.name.startswith('test_'):
                    key=cls.name+'.'+node.name;need(key not in result,'duplicate_method')
                    result[key]=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
    return result

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

def qualified():
    need(sha(BASE)==BASE_SHA,'qualified_C5_helper_changed')
    return imported('_q3h_qualified_C5',BASE)

def ids(rows):return qualified().ids(rows)
def guard(*args,**kwargs):return qualified().guard(*args,**kwargs)
def absent(*args,**kwargs):return qualified().absent(*args,**kwargs)

@contextmanager
def trusted_broker_environment(coor,entry,entry_sha,requested_model,reasoning_effort):
    """ONLY fixed task_entry broker receives provider transport. Never workers."""
    need(Path(entry)==CORE/'task_entry.py' and sha(entry)==entry_sha,'fixed_hash_pinned_task_broker_required')
    need(os.environ.get('OPENAI_API_KEY') and os.environ.get('OPENAI_BASE_URL','').rstrip('/')=='https://changellenge.up.railway.app/v1',
         'existing_authorized_provider_environment_required')
    original=coor.environment
    def environment(directory,model,manifest):
        need(model is False,'task_broker_requires_technical_environment')
        raw=original(directory,False,manifest)
        need(not any(any(s in key.upper() for s in ('KEY','TOKEN','SECRET','AUTH','PASSWORD','PROXY')) for key in raw),'broker_base_environment_not_scrubbed')
        env=dict(raw)
        need(all(env.get(k)=='1' for k in ('AUTOML_THREADS','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')),
             'technical_broker_thread_mapping_changed')
        env.update(OPENAI_API_KEY=os.environ['OPENAI_API_KEY'],OPENAI_BASE_URL=os.environ['OPENAI_BASE_URL'],
                   OPENAI_MODEL=requested_model,AUTOML_REASONING_EFFORT=reasoning_effort)
        return env
    coor.environment=environment
    try:yield
    finally:coor.environment=original

def task_clock(state,wall,mono):
    need(all(type(v) in (int,float) and math.isfinite(v) for v in (wall,mono,*[state[k] for k in
         ('start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic')])),'finite_original_clock')
    need(state['absolute_deadline_unix']==state['start_unix']+10800
         and state['common_deadline_monotonic']==state['start_monotonic']+10800,'original10800_not_reset')
    need(state['start_unix']<=wall and state['start_monotonic']<=mono
         and wall+4800<=state['absolute_deadline_unix'] and mono+4800<=state['common_deadline_monotonic'],
         'full_equal4800_admission_inside_original_common')
    need(abs((wall-state['start_unix'])-(mono-state['start_monotonic']))<=5,'actual_phase_wall_monotonic_disagreement')
    return {**{k:state[k] for k in ('start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic')},
            'task_start_unix':wall,'task_start_monotonic':mono,'task_deadline_unix':wall+4800,'task_deadline_monotonic':mono+4800}

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

def config(path,expected,self_sha):
    need(__debug__ and Path(path).is_absolute() and Path(path).stat().st_size<=2**20 and sha(path)==expected,'private_manifest_changed')
    cfg=read(path);pins=cfg['immutable_files']
    need(cfg.get('schema')=='qwen-three-hour-outer-private-v1' and cfg.get('readiness')=='READY_REVIEWED_FROZEN'
         and cfg.get('missing_bindings')==[],'NOT_READY')
    need(cfg['output']==str(OUT) and cfg['common_seconds']==10800
         and cfg['caps']==dict(setup=300,regression=[4800,4770],classification=[4800,4770],audit=[600,570],final=240,root=60),'fixed_equal_task_caps')
    need(type(pins) is dict and 1<=len(pins)<=4096 and all(Path(p).is_absolute() and type(h) is str
         and re.fullmatch('[0-9a-f]{64}',h) for p,h in pins.items()),'typed_complete_source_input_union')
    need(pins.get(str(Path(__file__).resolve()))==self_sha and sha(__file__)==self_sha
         and cfg['python']==str(LAUNCHER_PATH) and pins.get(cfg['python'])==LAUNCHER_SHA
         and pins.get(str(BASE))==BASE_SHA,'exact_entry_and_qualified_helper')
    need(cfg['canonical_root']==str(WORK/'alfa-hack-automl')
         and cfg['lock']==str(WORK/'alfa-hack-automl/test-runs/.owned-research.lock'),'fixed_canonical_source_and_lease')
    need(cfg['core_handoff']==dict(path=str(CORE/'source-handoff-final.json'),sha256=CORE_SHA)
         and pins.get(cfg['core_handoff']['path'])==CORE_SHA,'reviewed_core_R4_required')
    need(type(AUDITOR_HANDOFF_SHA) is str and cfg['auditor_handoff']==dict(path=str(AUDITOR/'source-handoff.json'),sha256=AUDITOR_HANDOFF_SHA)
         and cfg['auditor_entry']==str(AUDITOR/'audit_final.py')
         and pins.get(cfg['auditor_handoff']['path'])==AUDITOR_HANDOFF_SHA,'NOT_READY_final_auditor_required')
    for ref in [cfg['core_handoff'],cfg['auditor_handoff']]:
        need(sha(ref['path'])==ref['sha256'],'source_handoff_changed')
        folder=Path(ref['path']).parent
        for rel,h in read(ref['path'])['files_sha256'].items():need(pins.get(str(folder/rel))==h,'all_reviewed_source_files_required')
    for name,(rel,h) in SOURCE_REVIEWS.items():
        need(cfg['source_reviews'][name]==dict(path=str(WORK/rel),sha256=h) and pins.get(str(WORK/rel))==h,
             'actual_independent_core_and_auditor_source_reviews_required')
    for name,(rel,h) in HELPERS.items():need(cfg['helpers'][name]==dict(path=str(WORK/rel),sha256=h) and pins.get(str(WORK/rel))==h,'qualified_helper_changed')
    need([row['task']['kind'] for row in cfg['tasks']]==['regression','classification'],'exact_two_task_order')
    for row in cfg['tasks']:
        need(row['task']['context_flag'] is False and row['task']['selector_cache_flag'] is False,'unconfounded_factors_OFF')
        need(pins.get(row['strong_authority']['path'])==row['strong_authority']['sha256'],'actual_qualified_strong_authority_required')
        need(all(pins.get(cut['path'])==cut['sha256'] for cut in row['task']['cuts'])
             and [cut['seed'] for cut in row['task']['cuts']]==[42,43],'exact_qualified_cuts')
        strong_authority(cfg,row)
    core_tests=['test_parent_callback_ledger.py','test_provider_environment.py','test_r5_worker_consumer.py','test_research_loop.py','test_resource_origin.py']
    need([r['path'] for r in cfg['contracts'][:5]]==[str(CORE/n) for n in core_tests]
         and [r['name'] for r in cfg['contracts']]==['core-parent-ledger','core-provider-environment','core-worker-consumer',
             'core-iterative-policy','core-resource-origin','independent-audit-contracts','audit-CSV-role-contracts',
             'outer-broker-authority-contracts','outer-atomic-contracts'],'fixed_core_auditor_broker_atomic_test_whitelist')
    for row in cfg['contracts']:
        need(row['path'] in pins and methods(row['path'])==row['methods'] and row['expected']==len(row['methods'])>0
             and row['parent']==30 and row['child']==20,'all_exact_frozen_contract_methods')
    need(cfg['contracts'][5]['path']==str(AUDITOR/'test_audit_contracts.py')
         and cfg['contracts'][6]['path']==str(AUDITOR/'test_csv_role_contracts.py')
         and cfg['contracts'][-2]['path']==str(PACKET/'test_broker_contracts.py')
         and cfg['contracts'][-1]['path']==str(PACKET/'test_atomic_root.py'),'fixed_changed_orchestration_contracts')
    need(cfg['counts']['path']==str(WORK/'uar-count-parser-next-dev/counts.py')
         and cfg['counts']['sha256']=='bc320fd4723476c8a73404ed17a7bdec0cd4c69b1b1d41b321e370549c8cf4d3'
         and pins.get(cfg['counts']['path'])==cfg['counts']['sha256'],'unchanged_structural_counter')
    for name in ['close_controller.py','run_root.py','close_child.ps1','test_broker_contracts.py','test_atomic_root.py','confirm_post_tool.py']:
        need(str(PACKET/name) in pins,'complete_outer_source_pins')
    for p,h in pins.items():need(sha(p)==h,'immutable_source_input_changed')
    return cfg

RA1_ORIGINAL_REFS={'manifest': ('private/rq6-manifest.ready-r1.json', 'f4eb5dca1e3560de66206c76937d0314a790047436bd80f218422c9324afd65a'), 'campaign': ('rq6/campaign.json', '60afb434d1e6f943d05be02c0761cdb255745fe3e543961ed407e559eaf38725'), 'root': ('rq6/terminal-root-closure.json', 'f9e26b3a9e9223fc903909aafd3172dbd0b4242b142d9d29cf8593a3379d9810'), 'negative': ('rq6/current-negative-closure.json', 'fe8941210806633144b53f2f1345daa3922f7099dc81148637da7240592ce0bc'), 'post': ('rq6/current-negative-post-tool-confirmation.json', '9ad55350293113fbf7c026762979e06cc40a350b948718c39b998b8dea316fdc'), 'barrier': ('rq6/pretruth-barrier.json', '1a1c52f62d0badc5e579437e3f90b376e6f3e8440ca6948afbc92e45c1d79781'), 'regression_seal': ('rq6/regression-core-seal.json', '53c6dde06429214624ad071349b6365e0ddd5f73f8a8f5080c8b0dfa81cc7a9d'), 'classification_seal': ('rq6/classification-core-seal.json', '6d9345942bcb8e3752cdf66ba35f13292ed3f0f3da64481c3418f63bea1652fd'), 'old_auditor': ('last-submission-repair-qualification-next-dev-r6/artifact_audit.py', '910f8c5374b147c1d665ed01cb93f9b492f17d5cee330621f0f23685854b7209')}

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

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--launch',required=True,action='store_true')
    for key in ('manifest','manifest-sha256','self-sha256'):p.add_argument('--'+key,required=True)
    p.add_argument('--launch-parent-pid',required=True,type=int);p.add_argument('--launch-parent-create-time',required=True,type=float)
    a=p.parse_args();wall0,mono0=time.time(),time.monotonic();wall,end=wall0+10800,mono0+10800
    import psutil
    preparers,chain=capture(psutil,a.launch_parent_pid,a.launch_parent_create_time)
    need(not OUT.exists(),'exclusive_new_campaign_no_resume');OUT.mkdir()
    save(OUT/'preparer-identity.json',dict(identities=preparers,launch_parent_observation=chain))
    state=dict(schema='qwen-three-hour-campaign-v1',status='starting',start_unix=wall0,start_monotonic=mono0,
        absolute_deadline_unix=wall,common_deadline_monotonic=end,common_seconds=10800,owned_root=preparers[0] if preparers else None,
        coordinator_bootstrap_identities=preparers[1:],launch_parent_observation=chain,supervisors=[],active_supervisor=None,
        tasks=[],contracts=[],error_history=[],cleanup_uncertainty=[],cleanup_confirmed=False,source_unchanged=False,
        temporary_cleanup_confirmed=False,artifact_procedure_passed=False,quality_metric=None,promotion=False,submit=False,_manifest={})
    cfg=owner=coor=lease=awake=tmp=None;c=None;known=set();pins={};cores={};pulse=lambda **kw:None
    def persist():save(OUT/'campaign.json',{k:v for k,v in state.items() if not k.startswith('_')})
    def failure(exc,phase):
        row=dict(phase=phase,type=type(exc).__name__,code=str(exc) if isinstance(exc,RuntimeError) else None)
        state.setdefault('first_failure',row);state['error_history'].append(row);state.update(status='failed',artifact_procedure_passed=False,quality_metric=None)
    def check(phase=None):
        pulse();need(time.monotonic()<end and time.time()<wall,'original10800_exhausted')
        if phase is not None:need(time.monotonic()<phase,'phase_cap')
    def frozen(phase=None,code='immutable_or_phase_changed'):
        for path,h in {**pins,**cores}.items():need(sha(path,lambda:check(phase))==h,code)
    def run(argv,cwd,name,parent,child,reserve,broker=False,origin=None):
        now=time.monotonic();tick=now if origin is None else origin
        need(tick<=now and min(end-now,wall-time.time())>=reserve-(now-tick),'remaining_reserved_phases_unavailable')
        receipt=tmp/(name+'.json');observed=None
        try:
            if broker:
                with trusted_broker_environment(coor,CORE/'task_entry.py',pins[str(CORE/'task_entry.py')],cfg['requested_model'],cfg['reasoning_effort']):
                    observed=coor.supervise(argv,cwd,receipt,name,tick,parent,child,end,wall,reserve,state,persist,frozen,owner,modules['processes'],preparers[1:],solver_seconds=None)
            else:observed=coor.supervise(argv,cwd,receipt,name,tick,parent,child,end,wall,reserve,state,persist,frozen,owner,modules['processes'],preparers[1:],solver_seconds=None)
        finally:
            if receipt.exists():
                observed=read(receipt);known.update(c.ids(observed.get('owned_process_identities',[])))
                if observed.get('owned_root'):known.update(c.ids([observed['owned_root']]))
                ob=observed.get('cleanup_observation',{})
                if observed.get('cleanup_confirmed') is not True or ob.get('unresolved')!=[] or ob.get('denial_count')!=0:
                    state['cleanup_uncertainty'].append(dict(scope=name,observation=ob))
                dest=OUT/'supervisors';dest.mkdir(exist_ok=True)
                for ext in ('.json','.log'):
                    source=receipt.with_suffix(ext);target=dest/(name+ext);shutil.copyfile(source,target);cores[str(target)]=sha(target,check)
                    need(sha(source,check)==cores[str(target)],'saved_terminal_copy_changed')
                if state['supervisors']:state['supervisors'][-1]['path']=coor.relative(dest/(name+'.json'))
                persist()
            else:state['cleanup_uncertainty'].append(dict(scope=name,reason='missing_actual_supervisor_receipt'))
        need(observed is not None,'actual_supervisor_required');coor.child_errors(state,observed)
        need(observed.get('status')=='ok' and observed.get('exit_code')==0 and observed.get('cleanup_confirmed') is True
             and not observed.get('error_history'),'actual_child_failed')
        return dict(path=str(OUT/'supervisors'/(name+'.json')),sha256=cores[str(OUT/'supervisors'/(name+'.json'))],record=observed)
    try:
        need(chain.get('verified') is True,'actual_launch_chain_unconfirmed');cfg=config(a.manifest,a.manifest_sha256,a.self_sha256);c=qualified()
        modules={name:imported('_q3h_'+name,WORK/rel) for name,(rel,h) in HELPERS.items()}
        coor,owner=modules['coordinator'],modules['owner'];pulse=c.guard(mono0,end,wall,owner,preparers,state);state['_pulse']=pulse
        pins=dict(cfg['immutable_files']);pins[str(Path(a.manifest).resolve())]=a.manifest_sha256
        known=predecessor(cfg,check);c.absent(owner,known,check)
        lease=modules['lock'].ResearchLock(cfg['lock']);lease.__enter__();lease.write_identity(preparers[0]);c.absent(owner,known,check)
        awake=modules['awake'].PowerRequestGuard('Qwen equal task original10800');awake.__enter__();state['_awake']=awake
        setup_end=mono0+300;check(setup_end);frozen(setup_end)
        # Local credential/host validation only, inside setup; no network preflight.
        with trusted_broker_environment(coor,CORE/'task_entry.py',pins[str(CORE/'task_entry.py')],cfg['requested_model'],cfg['reasoning_effort']):pass
        state['provider_preflight']=dict(existing_authorized_environment_present=True,network_calls=0,credentials_saved=False)
        (WORK/'t').mkdir(exist_ok=True);tmp=Path(tempfile.mkdtemp(prefix='qh-',dir=WORK/'t')).resolve();state['temporary_root']=str(tmp)
        counter=imported('_q3h_counts',cfg['counts']['path'])
        for row in cfg['contracts']:
            check(setup_end);need(setup_end-time.monotonic()>=30,'full_contract_slot_inside_setup')
            test=Path(row['path']);sup=run([cfg['python'],'-B','-X','utf8',str(test),'-v'],test.parent,row['name'],30,20,30+9600+600+300)
            need(counter.counts(Path(sup['path']).with_suffix('.log').read_text('utf-8'),row['expected']),'actual_contract_count_or_skip_failed')
            state['contracts'].append(dict(name=row['name'],expected=row['expected'],supervisor=sup));persist()
        for index,row in enumerate(cfg['tasks']):
            check();kind=row['task']['kind'];tick_wall,tick_mono=time.time(),time.monotonic();timing=task_clock(state,tick_wall,tick_mono)
            need(min(end-tick_mono,wall-tick_wall)>=4800+(4800 if index==0 else 0)+600+300,'complete_nominal_task_and_later_reserves')
            output=OUT/('r' if index==0 else 'c');manifest=OUT/(kind+'-task-manifest.json');need(not manifest.exists() and not output.exists(),'new_task_no_resume')
            task_cfg={**row,'schema':'qwen-three-hour-task-private-v1','readiness':'READY_SOURCE_REVIEWED_FROZEN','missing_bindings':[],
                'canonical_root':cfg['canonical_root'],'python':cfg['python'],'output':str(output),'immutable_files':dict(pins),
                'helpers':cfg['helpers'],'clock':timing,'requested_model':cfg['requested_model'],'reasoning_effort':cfg['reasoning_effort']}
            save(manifest,task_cfg);pins[str(manifest)]=sha(manifest,check)
            sup=run([cfg['python'],'-B','-X','utf8',str(CORE/'task_entry.py'),'--manifest',str(manifest),'--manifest-sha256',pins[str(manifest)],
                     '--self-sha256',pins[str(CORE/'task_entry.py')]],WORK,kind,4800,4770,4800+(4800 if index==0 else 0)+600+300,broker=True,origin=tick_mono)
            report=output/'report.json';terminal=output/'task-terminal.json'
            need(report.is_file() and terminal.is_file(),'complete_task_report_and_terminal_required')
            state['tasks'].append(dict(kind=kind,task_manifest=dict(path=str(manifest),sha256=pins[str(manifest)]),spec=row['spec'],output=str(output),
                report=dict(path=str(report),sha256=sha(report,check)),terminal=dict(path=str(terminal),sha256=sha(terminal,check)),supervisor=sup));persist()
        need(len(state['tasks'])==2,'both_tasks_complete_before_truth')
        for entry in state['tasks']:
            rows=c.seal(entry['output'],check);seal=OUT/(entry['kind']+'-core-seal.json')
            save(seal,dict(schema='qwen-three-hour-task-core-seal-v1',kind=entry['kind'],task_manifest=entry['task_manifest'],output=entry['output'],
                files_sha256=rows,immutable_files_sha256=dict(pins)))
            cores.update(rows);cores[str(seal)]=sha(seal,check);entry['seal']=dict(path=str(seal),sha256=cores[str(seal)])
        audit_wall,audit_mono=time.time(),time.monotonic();audit_manifest=OUT/'audit-manifest.json'
        audit_clock={k:state[k] for k in ('start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic')}
        audit_clock.update(audit_start_unix=audit_wall,audit_start_monotonic=audit_mono,audit_deadline_unix=audit_wall+600,audit_deadline_monotonic=audit_mono+600)
        audit_cfg=dict(schema='qwen-three-hour-independent-audit-private-v1',readiness='READY_SOURCE_REVIEWED_FROZEN',missing_bindings=[],immutable_files=dict(pins),
            clock=audit_clock,tasks=state['tasks'],source_qualification=dict(archive=cfg['source_qualification']['archive'],root=cfg['source_qualification']['root'],
                confirmation=cfg['source_qualification']['post_tool']),output=str(OUT/'independent-audit.json'))
        save(audit_manifest,audit_cfg);cores[str(audit_manifest)]=sha(audit_manifest,check);persist()
        sup=run([cfg['python'],'-B','-X','utf8',cfg['auditor_entry'],'--manifest',str(audit_manifest),'--manifest-sha256',cores[str(audit_manifest)],
            '--self-sha256',pins[cfg['auditor_entry']],'--output',str(OUT/'independent-audit.json')],WORK,'independent-audit',600,570,600+300,origin=audit_mono)
        result=read(OUT/'independent-audit.json');need(result.get('artifact_procedure_passed') is True,'independent_artifacts_unqualified')
        state.update(independent_audit=dict(path=str(OUT/'independent-audit.json'),sha256=sha(OUT/'independent-audit.json',check),supervisor=sup,
            manifest=dict(path=str(audit_manifest),sha256=cores[str(audit_manifest)])),
            artifact_procedure_passed=True,quality_metric=result['quality_metric'],status='completed_pending_root');persist()
    except BaseException as exc:failure(exc,'campaign')
    finally:
        final=time.monotonic();state['final_start_monotonic']=final;state['final_deadline_monotonic']=min(final+240,end-60)
        try:
            check(state['final_deadline_monotonic']);need(owner is not None and cfg is not None,'final_authority_unavailable')
            c.absent(owner,known,check);frozen(state['final_deadline_monotonic'])
            need(state['active_supervisor'] is None and not state['cleanup_uncertainty']
                 and all(row.get('cleanup_confirmed') is True for row in state['supervisors']),'sticky_child_cleanup_unconfirmed')
            if tmp is not None:
                need(tmp.is_relative_to((WORK/'t').resolve()) and tmp.name.startswith('qh-') and not tmp.is_symlink(),'owned_shallow_temp_fence')
                shutil.rmtree(tmp);check(state['final_deadline_monotonic']);need(not tmp.exists(),'temporary_cleanup_unconfirmed')
            state.update(cleanup_confirmed=True,source_unchanged=True,temporary_cleanup_confirmed=True)
        except BaseException as exc:failure(exc,'final_cleanup');state['cleanup_confirmed']=False
        try:
            if awake is not None:awake.close();state['awake_guard']=awake.record
            pulse(force=True);check(state['final_deadline_monotonic']);need(state.get('awake_guard',{}).get('release_API_verified') is True,'Power_release_unconfirmed')
        except BaseException as exc:failure(exc,'Power_release')
        state['owned_process_identities']=[dict(pid=p,create_time=b) for p,b in sorted(known)]
        if lease is not None:
            try:lease.__exit__(None,None,None);check(state['final_deadline_monotonic'])
            except BaseException as exc:failure(exc,'lease_release')
        try:
            state.update(finished_unix=time.time(),finished_monotonic=time.monotonic(),elapsed_common_seconds=time.monotonic()-mono0)
            persist();check(state['final_deadline_monotonic'])
        except BaseException as exc:failure(exc,'terminal_save');persist()
    passed=state['status']=='completed_pending_root' and not state['error_history'] and state['cleanup_confirmed']
    print(json.dumps(dict(artifact_procedure_passed=bool(passed),quality_metric=state['quality_metric']),allow_nan=False))
    return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
