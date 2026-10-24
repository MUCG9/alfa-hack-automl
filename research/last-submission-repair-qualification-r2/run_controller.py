"""Prospective two-standard-call qualification; SOURCE ONLY / NOT_READY."""
from pathlib import Path
from contextlib import contextmanager
import argparse, ast, hashlib, importlib.util, json, math, os, re, shutil, sys, tempfile, time, zipfile

PACKET=Path(__file__).resolve().parent
WORK=PACKET.parent
OUT=WORK/'rq2'
COMMON,SETUP,AUDIT,FINAL,ROOT_CLOSE=6000,600,600,240,60
CAPS={'regression':(900,870),'classification':(3600,3570)}
HELPERS={
 'coordinator':('verified-supervision-next-dev-r2/coordinator.py','bd864b13460d31176d57e1dbddbe179ad8e6911163b117e3f9698228c5540f76'),
 'sampling':('verified-resource-sampling-next-dev/verified_sampling.py','d65ee39eb80c9fc4590cbbf474ee6c09e84cb65abe2d2c367ebcfa415a390cf0'),
 'owner':('support_component_coordinator.py','8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8'),
 'processes':('historical-runtime-support/fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d.py','fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d'),
 'lock':('alfa-hack-automl/tools/research_lock.py','78a0441bb3b9ea60197e9a1a6e1087f6e4cd0886593ec54bcfc4e41c9abe5a45'),
 'awake':('awake-next-dev/awake_guard.py','9a0bae0acb6ddb37e638420c52ad1e587a9180fbd7ef68ebc6e1a3c43e4bfc9b')}
EXECUTOR_HANDOFF_SHA='381f4d31a5cadc97b46c3c84db78a3e0e72872c4f7e0abf3d82807acdc029346'
ARCHIVE_SHA='9bb8fe6e4c9a5d86e381e5412e4fa895b219d206415f2590a10ec071a69d78c1'
CASES_HANDOFF_SHA='2381ff5fbd0e77a4f0a3fa58f46a5bb93a9e3f102a9379c6e1c6584c26cac0df'
COUNTS_SHA='bc320fd4723476c8a73404ed17a7bdec0cd4c69b1b1d41b321e370549c8cf4d3'
LAUNCHER_PATH=WORK/'venv/Scripts/python.exe'
LAUNCHER_SHA='d59c9a894b319828d023f3aa83d9a3488d2339f9e27e60e49b02abb0d53cf538'
NEGATIVE_CURRENT={
 'BRQ1':('brq1/terminal-root-closure.json','243782d116baa00df12e87ec6ff99e2f48e611bef1b77f24ec1227b9284b8db6'),
 'BRQ2':('brq2/terminal-root-closure.json','2d259e647a64f2f1e48d06e450f6fd877d4dc07bac3363df9743d78fecb890a0'),
 'campaign':('brq2/campaign.json','fd85c8317ff187ffc37986613ea5169c4dbd1e9512545e51127469750416ae24'),
 'current_root':('brq2-negative-closure-r1/terminal-root-closure.json','0a2f2dae7962892a596a98b7d51d1135f1017358a6326abe31ff2e986b7b5ade'),
 'fresh':('brq2-negative-closure-r1/root-confirmation.json','a5f5d57f7137ea6159db0cb43e760cbae8cb7674172624199e3479b399eed325')}

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
    spec.loader.exec_module(module);return module

def methods(path):
    tree=ast.parse(Path(path).read_text('utf-8-sig'));result={}
    for cls in tree.body:
        if isinstance(cls,ast.ClassDef):
            for node in cls.body:
                if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name.startswith('test_'):
                    key=cls.name+'.'+node.name;need(key not in result,'duplicate_test_method')
                    result[key]=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
    return result

def ids(rows):
    need(type(rows) is list and len(rows)<=30000,'bounded_saved_identities_required')
    need(all(type(v) is dict and type(v.get('pid')) is int and v['pid']>0
        and type(v.get('create_time')) in (int,float) and math.isfinite(v['create_time'])
        and v['create_time']>0 for v in rows),'typed_PID_create_time_required')
    return {(v['pid'],v['create_time']) for v in rows}

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

def guard(begin,deadline,wall,owner,preparers,state,awake=None,sampling=None):
    ob=owner.StrictOwnedObserver();ob.remember(ids(preparers));last=begin;previous=begin;sticky=None
    required=(preparers[0]['pid'],preparers[0]['create_time'])
    def clock_only():
        nonlocal last,previous,sticky
        if sticky is not None:raise RuntimeError(sticky)
        try:
            now=time.monotonic();w=time.time()
            need(math.isfinite(now) and math.isfinite(w) and now>=previous,'clock_nonfinite_or_rollback')
            previous=now;state['maximum_observed_gap_seconds']=max(state.get('maximum_observed_gap_seconds',0),now-last)
            need(now-last<=10,'actual_observation_gap10')
            need(now<deadline and w<wall,'original_common_or_phase_deadline')
            need(abs((deadline-now)-(wall-w))<=5,'wall_monotonic_disagreement')
            return now
        except BaseException as exc:
            sticky=str(exc) if isinstance(exc,RuntimeError) else 'resource_observation_unconfirmed'
            state['guard_sticky_error']=sticky;raise
    # The coordinator primitive receives ONLY this original clock/gap closure.
    # Reading time never advances the last successful resource observation.
    state['_resource_checkpoint']=clock_only
    if sampling is None:
        relative,h=HELPERS['sampling'];clock_only()
        need(sha(WORK/relative,clock_only)==h,'verified_resource_sampler_source_changed')
        sampling=imported('_brq_verified_guard_sampling',WORK/relative);clock_only()
    sampler=sampling.VerifiedResourceSampler()
    def pulse(force=False):
        nonlocal last,sticky
        if sticky is not None:raise RuntimeError(sticky)
        try:
            now=clock_only()
            if not force and now-last<.25:return
            live=ob.observe();need(not ob.denials,'self_bootstrap_resource_denied')
            need(required in live,'self_identity_unconfirmed')
            receipt=sampler.sample(set(ob.seen)|set(live)|{required},required=[required],checkpoint=clock_only)
            rss=sum(row['rss_bytes'] for row in receipt['sampled'])
            need(rss<=2048*2**20,'parent_bootstrap_memory_limit')
            state['peak_parent_bootstrap_mib']=max(state.get('peak_parent_bootstrap_mib',0),rss/2**20)
            clock_only()
            current_awake=state.get('_awake',awake)
            if current_awake is not None and current_awake.handle is not None:
                sample=current_awake.heartbeat();need(not sample['scheduling_gap_exceeded'],'power_observation_gap10')
            after=clock_only()
            state['verified_resource_sample']=receipt
            state['departed_known_resource_identities']=list(sampler.departed)
            last=after;state['actual_resource_samples']=state.get('actual_resource_samples',0)+1
        except BaseException as exc:
            sticky=str(exc) if isinstance(exc,RuntimeError) else 'resource_observation_unconfirmed'
            state['guard_sticky_error']=sticky;raise
    return pulse

def config(path,expected,self_sha):
    need(__debug__ and Path(path).is_absolute() and Path(path).stat().st_size<=2**20 and sha(path)==expected,'private_manifest_changed')
    cfg=read(path);pins=cfg['immutable_files']
    need(type(pins) is dict and 1<=len(pins)<=4096 and all(Path(p).is_absolute()
        and type(h) is str and re.fullmatch('[0-9a-f]{64}',h) for p,h in pins.items()),'typed_absolute_immutable_pins')
    need(cfg.get('schema')=='standard-repair-qualification-private-v1'
         and cfg.get('readiness')=='READY_REVIEWED_FROZEN' and cfg.get('missing_bindings')==[], 'NOT_READY')
    need(pins.get(str(Path(__file__).resolve()))==self_sha and sha(__file__)==self_sha,'controller_changed')
    need(cfg['output']==str(OUT) and cfg['common_seconds']==6000
         and cfg['caps']==dict(setup=600,regression=[900,870],classification=[3600,3570],audit=[600,570],final=240,root=60),
         'same_allinclusive6000_caps_required')
    need(Path(cfg['python']).resolve()==Path(sys.executable).resolve() and pins.get(cfg['python'])==LAUNCHER_SHA,
         'pinned_unoptimized_interpreter_required')
    need(cfg['lock']==str(WORK/'alfa-hack-automl/test-runs/.owned-research.lock'),'canonical_lock_required')
    executor=cfg['executor'];source=WORK/'last-submission-repair-next-dev-r2'
    need(executor['handoff']==dict(path=str(source/'source-handoff.json'),sha256=EXECUTOR_HANDOFF_SHA)
         and pins.get(executor['handoff']['path'])==EXECUTOR_HANDOFF_SHA and sha(executor['handoff']['path'])==EXECUTOR_HANDOFF_SHA,
         'exact81_repaired_source_handoff_required')
    handoff=read(executor['handoff']['path'])
    members={Path(k).name:h for k,h in handoff['files_sha256'].items() if k.startswith('candidate/')}
    need(len(members)==81 and executor['members_sha256']==members
         and executor['archive']==dict(path=str(WORK/'last-submission-repair-root-r2/solution-br-class-repair-candidate.zip'),sha256=ARCHIVE_SHA)
         and pins.get(executor['archive']['path'])==executor['archive']['sha256'],'actual81ZIP_frozen_member_map_required')
    need(all(pins.get(str(source/'candidate'/name))==h for name,h in members.items()),'all_actual_SOURCE81_member_pins_required')
    need(cfg['candidate_source_review']['path']==str(WORK/'last-submission-repair-independent-source-review-r2.json')
         and pins.get(cfg['candidate_source_review']['path'])==cfg['candidate_source_review']['sha256'],
         'actual_independent_repair_R2_source_peer_required')
    need(executor['test']==str(source/'tests/test_supervised_class_release.py')
         and executor['base_inventory']==str(source/'base-inventory.json')
         and pins.get(executor['test'])==handoff['files_sha256']['tests/test_supervised_class_release.py']
         and methods(executor['test'])==cfg['repair_contract_methods'] and len(cfg['repair_contract_methods'])==16,
         'exact16_new_delegation_contracts_required_source_and_unpacked')
    legacy=cfg['legacy_reg_contracts'];old=WORK/'br-standard-release-next-dev-r5'
    need(legacy['test']==str(old/'tests/test_fixed_release.py')
         and pins.get(legacy['test'])=='53c3d8dc823cbaf74dc05ae4681457bd0e9459c1f686fb4a024df0d018c5b515'
         and len(legacy['methods'])==18 and methods(legacy['test'])==legacy['methods']
         and legacy['recipe_fixture']==str(old/'tests/fixtures/recipes.json')
         and legacy['base_inventory']==str(old/'base-inventory.json'),
         'applicable_fixed_REG_common_API18_contracts_actual81_required')
    need(all(pins.get(str(p))==sha(p) for p in [Path(executor['base_inventory']),Path(legacy['recipe_fixture']),Path(legacy['base_inventory'])]),
         'source_and_unpacked_fixture_pins_required')
    need(cfg['counts']==dict(path=str(WORK/'uar-count-parser-next-dev/counts.py'),sha256=COUNTS_SHA)
         and pins.get(cfg['counts']['path'])==COUNTS_SHA,'unchanged_structural_counter_required')
    need(len(cfg['caller_test_methods'])==15 and methods(PACKET/'test_controller_contracts.py')==cfg['caller_test_methods']
         and len(cfg['atomic_test_methods'])==3 and methods(PACKET/'test_atomic_root.py')==cfg['atomic_test_methods'],
         'preserved_guard_and_atomic_contracts_required')
    for key,(relative,h) in HELPERS.items():
        need(cfg['helpers'][key]==dict(path=str(WORK/relative),sha256=h) and pins.get(str(WORK/relative))==h,'proven_helper_changed')
    need([t['kind'] for t in cfg['tasks']]==['regression','classification'],'exact_two_task_order')
    for task in cfg['tasks']:
        need(Path(task['source']).is_absolute() and set(task['files'])=={'task.md','train.csv','test.csv','sample_submission.csv','data_dictionary.csv'},'five_original_inputs_required')
        need(all(pins.get(str(Path(task['source'])/n))==h for n,h in task['files'].items()),'task_source_pins_required')
    need(cfg['tasks'][0]['expected_recipe']==read(legacy['recipe_fixture'])['regression'],'unchanged_embedded_REG_recipe_required')
    for ref in cfg['verification_plan']['expected_classification_splits'].values():
        need(pins.get(str(WORK/ref['path']))==ref['sha256'],'frozen_CLASS42_43_row_reference_required')
    for ref in [cfg['candidate_source_review'],cfg['lc1']['root'],cfg['lc1']['current_negative']]:
        need(pins.get(ref['path'])==ref['sha256'],'source_and_actual_predecessor_refs_frozen')
    need(cfg['technical_entry']['path']==str(PACKET/'technical_entry.py') and pins.get(cfg['technical_entry']['path'])==cfg['technical_entry']['sha256'],'fixed_dependency_bootstrap_required')
    for name in ['artifact_audit.py','close_controller.py','run_root.py','close_child.ps1','test_controller_contracts.py','test_atomic_root.py']:
        need(str(PACKET/name) in pins,'all_fixed_runtime_and_contract_sources_required')
    for rel,h in [('br-standard-release-qualification-next-dev/controller-r5/run_controller.py','d5f41cad6de2168cd520e442223428285dd3714854079d9305dd1b34938abd7d'),
                  ('last-submission-class-cases-caller-next-dev/run_cases.py','e3f3482d91ec2accddc35758a883505baee9b5e968334ff2c824ff06eaf24fce')]:
        need(pins.get(str(WORK/rel))==h,'fixed_source_only_admission_helper_required')
    cases=cfg['cases_contracts']
    need(cases['handoff']==dict(path=str(WORK/'last-submission-class-runtime-cases-next-dev-r2/source-handoff.json'),sha256=CASES_HANDOFF_SHA)
         and pins.get(cases['handoff']['path'])==CASES_HANDOFF_SHA
         and cases['test']==str(WORK/'last-submission-class-runtime-cases-next-dev-r2/test_class_runtime_contracts.py')
         and len(cases['methods'])==cases['count']==12 and methods(cases['test'])==cases['methods']
         and pins.get(cases['test'])==read(cases['handoff']['path'])['files_sha256']['test_class_runtime_contracts.py'],
         'corrected_same12_mock_fixture_source_required')
    need(cases['source_review']==dict(path=str(WORK/'last-submission-class-runtime-cases-independent-source-review-r2.json'),
         sha256='b7ef256f6b75165f75d5c3023c0bc2e0233a12f5d8b49d5b4709cf43582cf2d5')
         and pins.get(cases['source_review']['path'])==cases['source_review']['sha256'],
         'actual_independent_corrected12_source_review_required')
    for p,h in pins.items():need(Path(p).is_absolute() and sha(p)==h,'immutable_source_input_changed')
    return cfg

def previous_admission(cfg,check):
    # The fixed source-only LC1 admission helper verifies exact UAR10 root,
    # atomic fresh, actual wrapper+posttool exits and their full explicit union.
    helper=WORK/'last-submission-class-cases-caller-next-dev/run_cases.py'
    need(cfg['immutable_files'].get(str(helper))=='e3f3482d91ec2accddc35758a883505baee9b5e968334ff2c824ff06eaf24fce'
         and sha(helper,check)=='e3f3482d91ec2accddc35758a883505baee9b5e968334ff2c824ff06eaf24fce',
         'exact_source_reviewed_UAR10_known_admission_required')
    source=imported('_repair_lc1_source_admission',helper)
    guard=imported('_repair_C5_source_admission',WORK/'br-standard-release-qualification-next-dev/controller-r5/run_controller.py')
    known=source.predecessor(dict(cfg,launch_preparer_receipts=[]),guard,check)
    fields=cfg['lc1'];actual=fields['actual_execution'];observer_actual=fields['negative_helper_actual_execution']
    need(actual==dict(session=None,exit_code=1,tool='7f198f')
         and observer_actual==dict(exit_code=0,tool='f07ac9'),'actual_failed_LC1_and_current_negative_helper0_required')
    need(fields['root']==dict(path=str(WORK/'lc1/terminal-root-closure.json'),sha256='8c370c8a2ffa59bf272cbdfb2893672b144f8978d4e7cfa060534977f958c10c')
         and fields['current_negative']==dict(path=str(WORK/'lc1/current-negative-closure.json'),
         sha256='27ea25b977b105d34dd57c6a61c85ae918bc0c052f44f65d57c9c6090e008e5e'),'exact_LC1_negative_history_and_current_proof_required')
    for key in ('root','current_negative'):
        ref=fields[key];need(sha(ref['path'],check)==ref['sha256'],'actual_LC1_negative_evidence_changed')
    root,fresh=read(fields['root']['path']),read(fields['current_negative']['path'])
    need(root.get('schema')=='last-submission-class-cases-campaign-v1' and root.get('technical_procedure_passed') is False
         and root.get('actual_tests') is None and root.get('status')=='failed'
         and root.get('model_fits')==root.get('API_calls')==0,'original_LC1_failure_never_requalified')
    need(fresh.get('schema')=='last-submission-class-cases-current-negative-closure-v1'
         and fresh.get('original_root_sha256')==fields['root']['sha256'] and fresh.get('actual_failed_execution')==actual
         and fresh.get('technical_procedure_passed') is False and fresh.get('original_failure_preserved') is True
         and fresh.get('known_exact_live')==[] and fresh.get('uncertain')==[]
         and all(fresh.get(k) is True for k in ('current_source_unchanged','current_temporary_absent','current_cleanup_confirmed','inside_original180'))
         and fresh.get('source_pins_checked')==116 and 0<=fresh['observation_seconds']<=30,
         'source_only_current_negative_cleanup_not_LC1_PASS_required')
    current=ids(fresh['known_identities'])
    need(len(current)==fresh['known_count']==len(fresh['known_identities'])==7811
         and (known|ids(root['owned_identities']+root['closure_preparer_identities']))<=current,'complete_current_LC1_known_union_required')
    known|=current|ids(fresh['observer_preparer_identities'])
    # Later source/binding preparers did not exist at the historical negative
    # observation. Bind their actual terminal receipt, then freshly inspect the
    # COMPLETE union before and under the current lock; never invent old rows.
    for ref in cfg.get('launch_preparer_receipts',[]):
        need(set(ref)=={'path','sha256','actual_tool'} and set(ref['actual_tool'])=={'exit_code','tool'}
            and ref['actual_tool']['exit_code']==0 and ref['actual_tool']['tool']
            and cfg['immutable_files'].get(ref['path'])==ref['sha256'] and sha(ref['path'],check)==ref['sha256'],
            'actual_later_metadata_preparer_source_and_exit_required')
        known|=ids(read(ref['path'])['identities'])
    return known

def predecessor(cfg,check):
    known=previous_admission(dict(cfg,launch_preparer_receipts=[]),check)
    refs=cfg['rq1_previous'];root_ref=refs['root'];current_ref=refs['current_negative']
    need(root_ref==dict(path=str(WORK/'rq1/terminal-root-closure.json'),sha256='750834001513669f72e29ad7c044e495aa99cfdcd20c31f19a3f8509f062acdb')
        and current_ref==dict(path=str(WORK/'rq1/current-negative-closure.json'),sha256='16e4c55a5d2fa918036bf9ffa12025bd59d794c0d44ad7e8a49efaa777d93d45'),
        'exact_RQ1_failed_history_and_current_negative_required')
    for ref in [root_ref,current_ref]:
        need(cfg['immutable_files'].get(ref['path'])==ref['sha256'] and sha(ref['path'],check)==ref['sha256'],'RQ1_negative_evidence_changed')
    need(refs['driver_actual']==dict(session=None,exit_code=1,tool='3754fa')
        and refs['closer_actual']==dict(exit_code=1,tool='81b95d') and refs['negative_helper_actual']==dict(exit_code=0,tool='5b80c8'),
        'actual_RQ1_driver_closer_failure_and_current_helper0_required')
    root,current=read(root_ref['path']),read(current_ref['path'])
    need(root.get('schema')=='standard-repair-qualification-root-closure-v1' and root.get('technical_procedure_passed') is False
        and root.get('qualified_ML_metrics') is None and root.get('actual_exec_exit_code_observed_by_root')==1
        and root.get('actual_tool_evidence')=='3754fa','RQ1_permanent_FAIL_not_requalified')
    need(current.get('schema')=='standard-repair-current-negative-closure-v1' and current.get('original_root_sha256')==root_ref['sha256']
        and current.get('actual_failed_driver')==refs['driver_actual'] and current.get('actual_frozen_closer')==refs['closer_actual']
        and current.get('technical_procedure_passed') is False and current.get('original_failure_preserved') is True
        and all(current.get(k) is True for k in ('current_source_unchanged','current_temporary_absent','current_cleanup_confirmed','inside_original6000','inside_actual_closer_birth60'))
        and current.get('known_exact_live')==current.get('uncertain')==[] and current.get('source_pins_checked')==287,
        'typed_current_RQ1_source_temp_cleanup_only_required')
    observed=ids(current['known_identities']);observers=ids(current['observer_preparer_identities'])
    need(len(observed)==current['known_count']==len(current['known_identities'])==7828
        and known|ids(root['owned_identities']+root['closure_preparer_identities'])<=observed
        and len(observers)==3 and len(observed|observers)==7831,'complete_current_RQ1_known_preparer_union')
    known|=observed|observers
    for ref in cfg.get('launch_preparer_receipts',[]):
        need(set(ref)=={'path','sha256','actual_tool'} and ref['actual_tool']['exit_code']==0 and ref['actual_tool']['tool']
            and cfg['immutable_files'].get(ref['path'])==ref['sha256'] and sha(ref['path'],check)==ref['sha256'],'actual_later_preparer_source_and_exit')
        known|=ids(read(ref['path'])['identities'])
    return known

def absent(owner,known,check=lambda:None):
    check();ob=owner.StrictOwnedObserver();ob.remember(known)
    need(not ob.observe() and not ob.denials and not ob.final_check()['unresolved'],'known_owned_live_or_unconfirmed');check()

def frozen(cfg,check):
    for path,h in cfg['immutable_files'].items():need(sha(path,check)==h,'immutable_source_input_or_dependency_changed')

def seal(directory,check):
    result={}
    for parent,dirs,files in os.walk(directory):
        need(not any((Path(parent)/n).is_symlink() for n in dirs+files),'sealed_tree_symlink')
        for name in files:
            need(not name.endswith(('.pending','.tmp')),'unfinished_artifact')
            path=Path(parent)/name;result[str(path.resolve())]=sha(path,check)
            need(len(result)<=20000,'bounded_core_inventory')
    return result

def archive(cfg,directory,check):
    ref=cfg['executor']['archive'];need(sha(ref['path'],check)==ref['sha256'],'candidate_archive_changed')
    with zipfile.ZipFile(ref['path']) as z:
        need(len(z.namelist())==len(set(z.namelist()))==len(cfg['executor']['members_sha256'])
            and set(z.namelist())==set(cfg['executor']['members_sha256']),'exact_flat_member_inventory')
        for n,h in cfg['executor']['members_sha256'].items():
            need(Path(n).name==n and n.endswith(('.py','.txt')),'flat_code_only_archive_required')
            raw=z.read(n);check();need(hashlib.sha256(raw).hexdigest()==h,'flat_member_changed')
            (directory/n).write_bytes(raw)

@contextmanager
def two_learner_threads(coor):
    original=coor.environment
    def facade(directory,model,manifest):
        need(model is False,'no_model_API_environment_allowed')
        raw=original(directory,False,manifest)
        need(not any(any(s in k.upper() for s in ('KEY','TOKEN','SECRET','AUTH','PASSWORD','PROXY')) for k in raw),'API_scrub_failed')
        env=dict(raw);env['AUTOML_THREADS']='2';return env
    coor.environment=facade
    try:yield
    finally:coor.environment=original

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--launch',action='store_true',required=True)
    for n in ('manifest','manifest-sha256','self-sha256'):p.add_argument('--'+n,required=True)
    p.add_argument('--launch-parent-pid',type=int,required=True,help='Actual declared PowerShell shell PID, direct or one pinned venv launcher above')
    p.add_argument('--launch-parent-create-time',type=float,required=True,help='Actual declared shell Unix birth, invariant float serialization')
    args=p.parse_args();start,begin=time.time(),time.monotonic();wall,end=start+COMMON,begin+COMMON
    import psutil
    preparers,parent_observation=capture(psutil,args.launch_parent_pid,args.launch_parent_create_time)
    need(not OUT.exists(),'exclusive_output_no_retry');OUT.mkdir()
    save(OUT/'preparer-identity.json',dict(schema=2,identities=preparers,launch_parent_observation=parent_observation))
    state=dict(schema='standard-repair-qualification-campaign-v1',status='starting',start_unix=start,start_monotonic=begin,
        absolute_deadline_unix=wall,common_deadline_monotonic=end,common_seconds=COMMON,
        owned_root=preparers[0] if preparers else None,coordinator_bootstrap_identities=preparers[1:],supervisors=[],active_supervisor=None,
        launch_parent_observation=parent_observation,
        tasks=[],contracts=[],error_history=[],cleanup_uncertainty=[],cleanup_confirmed=False,source_unchanged=False,temporary_cleanup_confirmed=False,
        artifact_procedure_passed=False,quality_metric=None,root_actual_exec_pending=True,promotion=False,submit=False,_manifest={})
    cfg=None;coor=owner=awake=lease=None;tmp=None;pulse=lambda **kwargs:None;known=set();cores={};deployment={}
    def persist():save(OUT/'campaign.json',{k:v for k,v in state.items() if not k.startswith('_')})
    def fail(exc,phase):
        row=dict(code=str(exc) if isinstance(exc,RuntimeError) and re.fullmatch('[A-Za-z0-9_:+.-]{1,200}',str(exc))
            else type(exc).__name__,phase=phase,exception_type=type(exc).__name__,errno=getattr(exc,'errno',None),winerror=getattr(exc,'winerror',None))
        state.setdefault('first_failure',row);state['error_history'].append(row)
        state.update(status='failed',artifact_procedure_passed=False,quality_metric=None)
    def check(phase_end=None,code='phase_cap'):
        pulse();need(time.monotonic()<end and time.time()<wall,'original6000_exhausted')
        if phase_end is not None:need(time.monotonic()<phase_end,code)
    def all_frozen(phase_end=None,code='source_over_cap'):
        callback=lambda:check(phase_end,code);frozen(cfg,callback)
        for path,h in {**deployment,**cores}.items():need(sha(path,callback)==h,'deployment_or_sealed_core_changed')
    def run(argv,cwd,name,parent,child,reserve,model=False):
        tick=time.monotonic();need(min(end-tick,wall-time.time())>=reserve,'remaining_reserved_phases_unavailable')
        receipt=tmp/(name+'.json')
        try:
            if model:
                with two_learner_threads(coor):sup=coor.supervise(argv,cwd,receipt,name,tick,parent,child,end,wall,reserve,
                    state,persist,all_frozen,owner,modules['processes'],preparers[1:],solver_seconds=None)
            else:sup=coor.supervise(argv,cwd,receipt,name,tick,parent,child,end,wall,reserve,
                    state,persist,all_frozen,owner,modules['processes'],preparers[1:],solver_seconds=None)
        finally:
            if receipt.exists():
                observed=read(receipt);known.update(ids(observed.get('owned_process_identities',[])))
                if observed.get('owned_root'):known.update(ids([observed['owned_root']]))
                ob=observed.get('cleanup_observation',{})
                if observed.get('cleanup_confirmed') is not True or ob.get('unresolved')!=[] or ob.get('denial_count')!=0:
                    state['cleanup_uncertainty'].append(dict(scope=name,receipt=dict(path=str(receipt),sha256=sha(receipt)),observation=ob))
            else:state['cleanup_uncertainty'].append(dict(scope=name,reason='missing_actual_supervisor_receipt'))
        known.update(ids(sup.get('owned_process_identities',[])))
        if sup.get('owned_root'):known.update(ids([sup['owned_root']]))
        target=OUT/'supervisors';target.mkdir(exist_ok=True)
        for ext in ('.json','.log'):
            src=receipt.with_suffix(ext);dest=target/(name+ext);shutil.copyfile(src,dest)
            cores[str(dest)]=sha(dest,check);need(sha(src,check)==cores[str(dest)],'terminal_receipt_copy_changed')
        state['supervisors'][-1]['path']=coor.relative(target/(name+'.json'));persist()
        coor.child_errors(state,sup)
        need(sup.get('status')=='ok' and sup.get('exit_code')==0 and sup.get('cleanup_confirmed') is True
            and not sup.get('error_history'),'mandatory_child_failed')
        return dict(path=str(target/(name+'.json')),sha256=cores[str(target/(name+'.json'))],record=sup)
    try:
        need(parent_observation['verified'] is True,'explicit_direct_launch_parent_unconfirmed')
        cfg=config(str(Path(args.manifest).resolve()),args.manifest_sha256,args.self_sha256)
        modules={}
        for key,(relative,h) in HELPERS.items():
            need(sha(WORK/relative)==h,'trusted_helper_changed');modules[key]=imported('_brq_'+key,WORK/relative)
        coor,owner=modules['coordinator'],modules['owner']
        pulse=guard(begin,end,wall,owner,preparers,state);state['_pulse']=pulse;check()
        known=predecessor(cfg,check);absent(owner,known,check)
        lease=modules['lock'].ResearchLock(cfg['lock']);lease.__enter__();lease.write_identity(preparers[0])
        absent(owner,known,check);awake=modules['awake'].PowerRequestGuard('br-fixed-standard-qualification')
        awake.__enter__();state['_awake']=awake;check()
        # All setup, tests and copies are inside the same original origin.
        setup_end=begin+SETUP;state.update(manifest_sha256=args.manifest_sha256,status='setup');persist()
        all_frozen(setup_end);(WORK/'t').mkdir(exist_ok=True);tmp=Path(tempfile.mkdtemp(prefix='bq-',dir=WORK/'t')).resolve()
        state['temporary_root']=str(tmp)
        # New delegation contracts against SOURCE and the actual81 unpacked
        # archive; unchanged REG/defaultNone contracts against the same archive.
        flat=tmp/'flat';(flat/'candidate').mkdir(parents=True);(flat/'tests').mkdir()
        archive(cfg,flat/'candidate',lambda:check(setup_end))
        shutil.copyfile(cfg['executor']['test'],flat/'tests/test_supervised_class_release.py')
        shutil.copyfile(cfg['executor']['base_inventory'],flat/'base-inventory.json')
        legacy=tmp/'legacy';(legacy/'candidate').mkdir(parents=True);(legacy/'tests/fixtures').mkdir(parents=True)
        archive(cfg,legacy/'candidate',lambda:check(setup_end))
        for key,dest in [('test',legacy/'tests/test_fixed_release.py'),('base_inventory',legacy/'base-inventory.json'),
                         ('recipe_fixture',legacy/'tests/fixtures/recipes.json')]:
            shutil.copyfile(cfg['legacy_reg_contracts'][key],dest)
        deployment.update(seal(flat,lambda:check(setup_end)));deployment.update(seal(legacy,lambda:check(setup_end)))
        counter=imported('_repair_counts',cfg['counts']['path'])
        slots=[('repair-source-contracts',Path(cfg['executor']['test']),90,60,16),
            ('repair-unpacked-contracts',flat/'tests/test_supervised_class_release.py',90,60,16),
            ('REG-common-unpacked-contracts',legacy/'tests/test_fixed_release.py',90,60,18),
            ('corrected-cases-source-contracts',Path(cfg['cases_contracts']['test']),90,60,12),
            ('caller-contracts',PACKET/'test_controller_contracts.py',60,45,15),
            ('atomic-contracts',PACKET/'test_atomic_root.py',30,20,3)]
        for name,test,parent,child,count in slots:
            check(setup_end);need(setup_end-time.monotonic()>=parent,'setup_full_contract_slot_unavailable')
            argv=[cfg['python'],'-B','-X','utf8',str(test),'-v']
            if name in ('repair-source-contracts','repair-unpacked-contracts'):
                argv=[cfg['python'],'-B','-X','utf8',str(PACKET/'technical_entry.py'),'--role',
                    'source' if name=='repair-source-contracts' else 'unpacked','--test',str(test),
                    '--manifest',str(Path(args.manifest).resolve()),'--manifest-sha256',args.manifest_sha256,
                    '--self-sha256',cfg['technical_entry']['sha256']]
            ref=run(argv,test.parent,name,parent,child,parent+4500+AUDIT+300)
            log=Path(ref['path']).with_suffix('.log').read_text('utf-8');need(counter.counts(log,count),'contract_count_or_skip_failed')
            state['contracts'].append(dict(name=name,expected=count,supervisor=ref));persist();check(setup_end)
        for index,task in enumerate(cfg['tasks']):
            directory=OUT/task['kind'];directory.mkdir();archive(cfg,directory,check)
            for n,h in task['files'].items():
                shutil.copyfile(Path(task['source'])/n,directory/n);need(sha(directory/n,check)==h,'pristine_copy_changed')
            deployment.update(seal(directory,check));kind=task['kind'];parent,child=CAPS[kind]
            ref=run([cfg['python'],'-B','-X','utf8','solution.py','task.md'],directory,kind,parent,child,
                parent+(3600 if index==0 else 0)+AUDIT+300,model=True)
            pattern='fixed-release-*/report.json' if kind=='regression' else 'v16-class-release*/report.json'
            reports=list((directory/'automl_runs').glob(pattern))
            need(len(reports)==1,'exact_one_fresh_task_report_required')
            delegation={}
            if kind=='classification':
                folders=list((directory/'automl_runs').glob('class-supervision-*'))
                need(len(folders)==1 and folders[0].is_dir(),'unique_actual_CLASS_supervision_required')
                delegation={name:str(folders[0]/name) for name in
                    ('supervision.json','authority.json','observation.json','hello.json','child-diagnostic.json','child.log')}
                need(all(Path(p).is_file() for p in delegation.values()),'complete_CLASS_delegation_receipts_required')
            # Seal complete data/code/cut/refit inventory before any pristine labels are opened by audit.
            sealed=seal(directory,check);core_ref=OUT/(kind+'-core-seal.json');save(core_ref,dict(files_sha256=sealed))
            cores.update(sealed);cores[str(core_ref)]=sha(core_ref,check)
            state['tasks'].append(dict(kind=kind,directory=str(directory),report=str(reports[0]),delegation=delegation,
                supervisor=ref,seal=dict(path=str(core_ref),sha256=cores[str(core_ref)])));persist()
        need(len(state['tasks'])==2,'both_complete_tasks_required_before_truth')
        state['status']='verifying';save(OUT/'pretruth-barrier.json',dict(tasks=state['tasks'],manifest_sha256=args.manifest_sha256,
            clock={k:state[k] for k in ('start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic')}))
        cores[str(OUT/'pretruth-barrier.json')]=sha(OUT/'pretruth-barrier.json',check);persist()
        state['pretruth_barrier']=dict(path=str(OUT/'pretruth-barrier.json'),sha256=cores[str(OUT/'pretruth-barrier.json')]);persist()
        audit=run([cfg['python'],'-B','-X','utf8',str(PACKET/'artifact_audit.py'),'--manifest',str(Path(args.manifest).resolve()),
            '--manifest-sha256',args.manifest_sha256,'--self-sha256',cfg['immutable_files'][str(PACKET/'artifact_audit.py')]],
            WORK,'independent-audit',600,570,AUDIT+300)
        result=read(OUT/'independent-audit.json');need(result.get('artifact_procedure_passed') is True,'independent_artifacts_unqualified')
        state.update(independent_audit=dict(path=str(OUT/'independent-audit.json'),sha256=sha(OUT/'independent-audit.json',check),supervisor=audit),
            artifact_procedure_passed=True,quality_metric=result['quality_metric'],status='completed_pending_root')
    except BaseException as exc:fail(exc,'qualification')
    finally:
        final_begin=time.monotonic();state['final_start_monotonic']=final_begin
        state['final_deadline_monotonic']=min(final_begin+FINAL,end-ROOT_CLOSE)
        try:
            check(state['final_deadline_monotonic']);need(owner is not None and cfg is not None,'final_authority_unavailable')
            absent(owner,known,check);all_frozen(state['final_deadline_monotonic'])
            need(state['active_supervisor'] is None and not state['cleanup_uncertainty']
                and all(r.get('cleanup_confirmed') is True for r in state['supervisors']),'sticky_child_cleanup_unconfirmed')
            if tmp is not None:
                need(tmp.is_relative_to((WORK/'t').resolve()) and tmp.name.startswith('bq-') and not tmp.is_symlink(),'owned_temp_fence')
                state['temporary_pins_verified_before_removal']=dict(files=deployment,
                    checked_monotonic=time.monotonic(),scope='Source/flat projection verified inside common; deleted paths are not later live pins')
                shutil.rmtree(tmp);check(state['final_deadline_monotonic']);need(not tmp.exists(),'temporary_cleanup_unconfirmed')
            state.update(cleanup_confirmed=True,temporary_cleanup_confirmed=True,source_unchanged=True)
        except BaseException as exc:fail(exc,'final_cleanup');state['cleanup_confirmed']=False
        try:
            if awake is not None:awake.close();state['awake_guard']=awake.record
            pulse(force=True);need(state.get('awake_guard',{}).get('release_API_verified') is True,'power_release_unconfirmed')
        except BaseException as exc:fail(exc,'power_release')
        state['owned_process_identities']=[dict(pid=p,create_time=b) for p,b in sorted(known)]
        state.update(finished_unix=time.time(),finished_monotonic=time.monotonic(),elapsed_common_seconds=time.monotonic()-begin)
        try:persist();pulse(force=True);check(state['final_deadline_monotonic'])
        except BaseException as exc:fail(exc,'terminal_save');persist()
        finally:
            if lease is not None:lease.__exit__(None,None,None)
        try:
            check(state['final_deadline_monotonic'],'final_phase_after_lease_over_cap')
            state.update(finished_unix=time.time(),finished_monotonic=time.monotonic(),elapsed_common_seconds=time.monotonic()-begin)
            persist();check(state['final_deadline_monotonic'],'terminal_save_after_lease_over_cap')
        except BaseException as exc:fail(exc,'postlease');persist()
    passed=state.get('status')=='completed_pending_root' and not state['error_history'] and state['cleanup_confirmed']
    print(json.dumps(dict(status=state['status'],artifact_procedure_passed=bool(passed),quality_metric=state['quality_metric']),allow_nan=False))
    return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
