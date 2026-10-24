"""One fixed cache-only CLASS experiment. SOURCE ONLY until root READY/launch."""
from pathlib import Path
import argparse,ast,copy,hashlib,importlib.util,json,math,os,re,shutil,sys,tempfile,time

PACKET=Path(__file__).resolve().parent;WORK=PACKET.parent;OUT=WORK/'cx1'
COMMON,SETUP,AUDIT,FINAL,ROOT_CLOSE=600,180,120,240,60
BASE_PATH=WORK/'br-standard-release-qualification-next-dev/controller-r5/run_controller.py'
BASE_SHA='d5f41cad6de2168cd520e442223428285dd3714854079d9305dd1b34938abd7d'
LAUNCHER_PATH=WORK/'venv/Scripts/python.exe'
LAUNCHER_SHA='d59c9a894b319828d023f3aa83d9a3488d2339f9e27e60e49b02abb0d53cf538'
AUDITOR_PATH='class-xgb-contribution-audit-next-dev/audit_cache.py'
AUDITOR_SHA='0fe46e3f4e95456910aa62c6e8694d620df84f6cda92c661e68cd4c0ec318bcc'
AUDITOR_TEST_PATH='class-xgb-contribution-audit-next-dev/tests/test_audit_cache.py'
AUDITOR_TEST_SHA='6fd00a8c11104e9ebe9e166698509304322490df4c52eeae6164ab87d5b22631'
AUDITOR_TEST_METHODS={'CacheAuditContracts.test_retained_components_exact_deep_copy_and_control_unchanged': '9836c057d38e9373ac042aef6866c347cfa1a91b6f7dd7de90d5c133f275cbfc', 'CacheAuditContracts.test_wrong_component_weight_or_family_is_stop': 'b12843244f058fd9c81af14512eb1798ed9b1aaa07b0d69d7f068bd2f6e3d141', 'CacheAuditContracts.test_both_control_cuts_complete_before_any_candidate': 'c23d8e624ac3b86513449ccba999a65b138dfe5f80297ddc6a1cf98d8c2d7ed2', 'CacheAuditContracts.test_second_control_failure_prevents_all_comparative_scores': '2291ef31e97954e2d1da7096f4c293cf1ba12a5f7452c9d909a14f9894dd5c61', 'CacheAuditContracts.test_fixed_weight_mixture_normalizes_without_input_mutation': 'a109c81827cf91716a136da203f88abac4001d3f240d7f1b6d8edba9c7b77a9b', 'CacheAuditContracts.test_original_clock_assignment_and_successful_checkpoint': 'a1bef2f55a8b80e50cd8e57a2027ede63b4202ea78c16d60275951b8a01bc3b3', 'CacheAuditContracts.test_gap_failure_sticks_and_never_advances_to_recover': '4a2eea9302a0b89197287ca8ed574e0fc32f9244eb4ffbeeb36c261193ff69f4', 'CacheAuditContracts.test_deadline_rollback_nonfinite_and_drift_stop_on_same_origin': 'b173bd8469535650a0ee1bbad2c433471dca405f1695b6b340101c61b1b9ed34', 'CacheAuditContracts.test_saved_control_requires_same_positions_classes_support_and_metrics': 'b4d1d5426d5e38c3d0f1e585127c4d24017e026bacd1d52947653a3988397eed', 'CacheAuditContracts.test_quality_requires_both_cut_and_mean_improvement_and_existing_class_gates': 'c781880e92b5eb05c4e77a4af9ebd5ce4fe4b050f811b909903546a751da38ea', 'CacheAuditContracts.test_missing_or_changed_cache_has_no_fit_or_reconstruction_route': 'ff7dd83b1ded41d44335264db6780aaa2951bbc85ebaec4e6c44edf7fd46140a', 'CacheAuditContracts.test_failure_result_clears_comparative_metrics_and_preserves_first_error': '899402b7d714b616ed1b251968c4456f364c5362aaaa8bd3aedf04d6fe01444e'}
COUNTS=('uar-count-parser-next-dev/counts.py','bc320fd4723476c8a73404ed17a7bdec0cd4c69b1b1d41b321e370549c8cf4d3')
ROOT_REF=('brq3/terminal-root-closure.json','7578f3ea5f4d3b14e9925bec5705a3169ab17ae77de5a45cfc7583edeaedf42d')
FRESH_REF=('brq3/root-confirmation.json','85a00effb05fa5cb7218e1021c446855a84a508f1c9f68c01b6d83eee440fdd0')
TIMING_REF=('brq3/root-fresh-timing-addendum.json','d2436badbad18f75b2f67feafede7b3ee5b91da840344b2aba4b4154c264b2c8')

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
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def methods(path):
    result={}
    for cls in ast.parse(Path(path).read_text('utf-8-sig')).body:
        if isinstance(cls,ast.ClassDef):
            for node in cls.body:
                if isinstance(node,ast.FunctionDef) and node.name.startswith('test_'):
                    key=cls.name+'.'+node.name;need(key not in result,'duplicate_test_method')
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

def predecessor_documents(root,fresh,timing):
    need(root.get('schema')=='br-standard-qualification-root-closure-v1'
        and root.get('technical_procedure_passed') is True and root.get('cleanup_confirmed') is True
        and root.get('source_unchanged') is True and root.get('active_owned_processes')==[]
        and root.get('uncertain_owned')==[] and root.get('changed_source_or_core')==[]
        and root.get('actual_exec_session')==37018 and root.get('actual_exec_exit_code_observed_by_root')==0
        and root.get('actual_tool_evidence')=='757206','closed_actual_BRQ3_required')
    need(fresh.get('schema')=='BRQ3-current-full-root-source-cleanup-confirmation-v1'
        and fresh.get('root_sha256')==ROOT_REF[1]
        and fresh.get('actual_driver_execution')==dict(session=37018,exit_code=0,tool='757206')
        and fresh.get('actual_closer_execution')==dict(session=None,exit_code=0,tool='d1005d')
        and fresh.get('known_exact_live')==[] and fresh.get('uncertain')==[]
        and fresh.get('all354_immutable_source_input_pins_current') is True
        and fresh.get('temporary_root_absent') is True and fresh.get('current_source_cleanup_confirmed') is True
        and fresh.get('inside_original_common') is True,'BRQ3_actual_closer_and_full_fresh_scope_required')
    need(timing.get('root_sha256')==ROOT_REF[1] and timing.get('fresh_confirmation_sha256')==FRESH_REF[1]
        and timing.get('fresh_inside_actual_closer_birth_plus60') is True
        and timing.get('fresh_inside_existing_final240') is True and timing.get('fresh_inside_original_common') is True,
        'BRQ3_fresh_timing_witness_required')

def audit_clock(start,begin,admission_unix,admission_mono):
    need(all(type(v) in (int,float) and math.isfinite(v) for v in (start,begin,admission_unix,admission_mono)), 'finite_original_clock_required')
    need(admission_mono>=begin and admission_unix>=start
        and admission_mono+AUDIT+FINAL+ROOT_CLOSE<=begin+COMMON
        and admission_unix+AUDIT+FINAL+ROOT_CLOSE<=start+COMMON,'complete_audit_and_final_reserve_required')
    return dict(start_unix=start,start_monotonic=begin,absolute_deadline_unix=start+COMMON,common_deadline_monotonic=begin+COMMON,
        audit_start_unix=admission_unix,audit_start_monotonic=admission_mono,
        audit_deadline_unix=admission_unix+AUDIT,audit_deadline_monotonic=admission_mono+AUDIT,
        prior_checkpoint_monotonic=admission_mono)

def audit_command(python,manifest,manifest_sha,output):
    need(type(AUDITOR_PATH) is str and type(AUDITOR_SHA) is str,'NOT_READY_final_auditor_required')
    need(all(Path(p).is_absolute() for p in (python,manifest,output)),'absolute_forwarded_paths_required')
    return [python,'-B','-X','utf8',str(WORK/AUDITOR_PATH),'--manifest',manifest,'--manifest-sha256',manifest_sha,
        '--self-sha256',AUDITOR_SHA,'--output',output]

def result_qualified(value,manifest_sha,inventory_sha):
    return (value.get('schema')=='class-xgb-contribution-audit-v1' and value.get('status')=='complete'
        and value.get('artifact_procedure_passed') is True and type(value.get('quality_gate_passed')) is bool
        and type(value.get('comparison')) is dict and value.get('manifest_sha256')==manifest_sha
        and value.get('expected_inventory_sha256')==inventory_sha and value.get('audit_within_original_common_clock') is True
        and value.get('new_model_fits')==0 and value.get('API_calls')==0 and value.get('Qwen_calls')==0
        and value.get('candidate_refit') is False and value.get('submission_written') is False and value.get('new_release_qualified') is False
        and value.get('promotion') is False and value.get('submit') is False
        and value.get('first_failure') is None and value.get('error_history')==[])

def config(path,digest,self_sha):
    need(__debug__ and Path(path).is_absolute() and Path(path).stat().st_size<=4*2**20 and sha(path)==digest,'bounded_frozen_absolute_manifest')
    cfg=read(path);need(cfg.get('schema')=='class-xgb-cache-caller-private-v1' and cfg.get('readiness')=='READY_FROZEN'
        and cfg.get('missing_bindings')==[],'NOT_READY')
    pins=cfg['immutable_files'];need(type(pins) is dict and 1<=len(pins)<=4096
        and all(Path(p).is_absolute() and type(h) is str and re.fullmatch('[0-9a-f]{64}',h) for p,h in pins.items()),'typed_absolute_source_input_core_pins')
    need(sha(__file__)==self_sha and pins.get(str(Path(__file__).resolve()))==self_sha
        and pins.get(str(BASE_PATH))==BASE_SHA and pins.get(str(LAUNCHER_PATH))==LAUNCHER_SHA,'caller_and_base_capture_source_pins_required')
    need(cfg['output']==str(OUT) and cfg['common_seconds']==COMMON
        and cfg['caps']==dict(setup=SETUP,audit=[120,90],final=FINAL,root=ROOT_CLOSE),'fixed_no_fit_caps_output')
    need(Path(cfg['python']).resolve()==Path(sys.executable).resolve() and cfg['python'] in pins,'actual_interpreter_required')
    need(cfg['lock']==str(WORK/'alfa-hack-automl/test-runs/.owned-research.lock'),'canonical_lock_required')
    for key,(relative,h) in [('root',ROOT_REF),('fresh',FRESH_REF),('timing',TIMING_REF)]:
        need(cfg['brq3'][key]==dict(path=str(WORK/relative),sha256=h) and pins.get(str(WORK/relative))==h,'fixed_BRQ3_predecessor_ref_required')
    need(type(AUDITOR_PATH) is str and type(AUDITOR_SHA) is str and cfg['auditor']==dict(path=str(WORK/AUDITOR_PATH),sha256=AUDITOR_SHA)
        and pins.get(str(WORK/AUDITOR_PATH))==AUDITOR_SHA,'frozen_fixed_auditor_only')
    need(type(AUDITOR_TEST_PATH) is str and cfg['auditor_test']['path']==str(WORK/AUDITOR_TEST_PATH)
        and cfg['auditor_test']['sha256']==AUDITOR_TEST_SHA and pins.get(str(WORK/AUDITOR_TEST_PATH))==AUDITOR_TEST_SHA
        and cfg['auditor_test']['methods']==AUDITOR_TEST_METHODS,'final_changed_auditor_contracts_required')
    need(cfg['counts']==dict(path=str(WORK/COUNTS[0]),sha256=COUNTS[1]) and pins.get(str(WORK/COUNTS[0]))==COUNTS[1], 'frozen_structural_counter_required')
    need(cfg['auditor_test']['count']==len(methods(WORK/AUDITOR_TEST_PATH))==len(AUDITOR_TEST_METHODS)
        and methods(WORK/AUDITOR_TEST_PATH)==AUDITOR_TEST_METHODS,'actual_auditor_method_AST_count')
    own=PACKET/'test_caller.py';need(cfg['caller_test']['count']==len(cfg['caller_test']['methods'])==4
        and cfg['caller_test']['methods']==methods(own) and str(own) in pins,'actual_three_changed_caller_method_AST_count')
    need(str(PACKET/'close_audit.py') in pins,'frozen_root_closer_required')
    need(type(cfg['audit_payload']) is dict and cfg['audit_payload'].get('clock') is None,'static_payload_must_not_assign_clock')
    review=cfg['caller_source_review'];need(pins.get(review['path'])==review['sha256']
        and cfg['audit_payload']['reviewed_caller']==dict(path=str(Path(__file__).resolve()),sha256=self_sha,
            review_path=review['path'],review_sha256=review['sha256']),'independent_caller_review_binding_required')
    return cfg

def temporary_fence(directory,check=lambda:None):
    root=(WORK/'t').resolve();need(directory.resolve()==directory and directory.parent==root
        and directory.name.startswith('cx-'),'exact_owned_shallow_temp_required')
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
    state=dict(schema='class-xgb-cache-campaign-v1',status='starting',start_unix=start,start_monotonic=begin,
        absolute_deadline_unix=wall,common_deadline_monotonic=end,common_seconds=COMMON,
        owned_root=preparers[0] if preparers else None,coordinator_bootstrap_identities=preparers[1:],supervisors=[],active_supervisor=None,
        contracts=[],error_history=[],cleanup_uncertainty=[],cleanup_confirmed=False,source_unchanged=False,temporary_cleanup_confirmed=False,
        comparison_procedure_passed=False,quality_gate_passed=None,qualified_comparison=None,promotion=False,submit=False,new_model_fits=0,API_calls=0,_manifest={})
    cfg=base=coor=owner=awake=lease=tmp=None;modules={};known=set();sealed={};pulse=lambda **kwargs:None
    def persist():save(OUT/'campaign.json',{k:v for k,v in state.items() if not k.startswith('_')})
    def fail(exc,phase):
        code=str(exc) if isinstance(exc,RuntimeError) and re.fullmatch('[A-Za-z0-9_:+.-]{1,200}',str(exc)) else type(exc).__name__
        row=dict(code=code,phase=phase,exception_type=type(exc).__name__,errno=getattr(exc,'errno',None),winerror=getattr(exc,'winerror',None))
        state.setdefault('first_failure',row);state['error_history'].append(row)
        state.update(status='failed',comparison_procedure_passed=False,quality_gate_passed=None,qualified_comparison=None)
    def check(phase=None,code='phase_cap'):
        pulse();need(time.monotonic()<end and time.time()<wall,'original600_exhausted')
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
        cfg=config(a.manifest,a.manifest_sha256,a.self_sha256)
        need(sha(BASE_PATH)==BASE_SHA,'verified_C5_base_changed');base=imported('_cx_base',BASE_PATH)
        for key,(relative,h) in base.HELPERS.items():
            need(cfg['immutable_files'].get(str(WORK/relative))==h and sha(WORK/relative)==h,'qualified_helper_changed')
            modules[key]=imported('_cx_'+key,WORK/relative)
        coor,owner=modules['coordinator'],modules['owner'];pulse=base.guard(begin,end,wall,owner,preparers,state);state['_pulse']=pulse
        check();frozen();docs={k:read(cfg['brq3'][k]['path']) for k in ('root','fresh','timing')}
        predecessor_documents(**docs);known=base.ids(docs['fresh']['known_identities'])
        need(len(known)==len(docs['fresh']['known_identities'])==docs['fresh']['known_count']==7305
            and base.ids(docs['root']['owned_identities']+docs['root']['closure_preparer_identities'])<=known,'complete_BRQ3_root_preparer_union')
        for ref in cfg.get('additional_preparer_receipts',[]):
            need(cfg['immutable_files'].get(ref['path'])==ref['sha256'] and sha(ref['path'],check)==ref['sha256'],'additional_preparer_pin_required')
            known|=base.ids(read(ref['path'])['identities'])
        base.absent(owner,known,check);lease=modules['lock'].ResearchLock(cfg['lock']);lease.__enter__();lease.write_identity(preparers[0])
        base.absent(owner,known,check);awake=modules['awake'].PowerRequestGuard('CLASS-XGB-CONTRIBUTION-01-cache-audit');awake.__enter__();state['_awake']=awake
        check();setup_end=begin+SETUP;frozen(setup_end);(WORK/'t').mkdir(exist_ok=True)
        tmp=Path(tempfile.mkdtemp(prefix='cx-',dir=WORK/'t')).resolve();state['temporary_root']=str(tmp);state['status']='contracts';persist()
        counter=imported('_cx_counter',cfg['counts']['path'])
        for name,path,expected in [('auditor-contracts',cfg['auditor_test']['path'],cfg['auditor_test']['count']),
            ('caller-contracts',str(PACKET/'test_caller.py'),cfg['caller_test']['count'])]:
            check(setup_end);need(setup_end-time.monotonic()>=60,'full_changed_contract_slot_required')
            ref=run([cfg['python'],'-B','-X','utf8',path,'-v'],Path(path).parent,name,60,45,420+60)
            need(counter.counts(Path(ref['path']).with_suffix('.log').read_text('utf-8'),expected),'exact_changed_contract_count_no_skip_required')
            state['contracts'].append(dict(name=name,expected=expected,supervisor=ref));persist();check(setup_end)
        # A genuine admission timestamp BEFORE forced verified sampling. It is
        # a conservative old observation bound, never a reset after slow work.
        admission_unix,admission_mono=time.time(),time.monotonic();pulse(force=True)
        payload=copy.deepcopy(cfg['audit_payload']);payload['clock']=audit_clock(start,begin,admission_unix,admission_mono)
        payload['caller_private_manifest']=dict(path=str(Path(a.manifest)),sha256=a.manifest_sha256)
        audit_manifest=OUT/'audit-manifest.json';save(audit_manifest,payload);sealed[str(audit_manifest)]=sha(audit_manifest,check)
        output=OUT/'independent-cache-audit.json';state['status']='auditing';state['audit_binding']=dict(path=str(audit_manifest),sha256=sealed[str(audit_manifest)]);persist()
        ref=run(audit_command(cfg['python'],str(audit_manifest),sealed[str(audit_manifest)],str(output)),WORK,
            'fixed-cache-audit',120,90,420,parent_start=admission_mono)
        result=read(output);need(result_qualified(result,sealed[str(audit_manifest)],payload['expected_inventory']['sha256']),
            'cache_comparison_artifacts_binding_or_procedure_unqualified')
        sealed[str(output)]=sha(output,check);state.update(status='completed_pending_root',comparison_procedure_passed=True,
            independent_audit=dict(path=str(output),sha256=sealed[str(output)],supervisor=ref),quality_gate_passed=result.get('quality_gate_passed'),
            qualified_comparison=result.get('comparison'))
    except BaseException as exc:fail(exc,'research_audit')
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
    print(json.dumps(dict(comparison_procedure_passed=bool(passed),quality_gate_passed=state['quality_gate_passed'],promotion=False),allow_nan=False))
    return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
