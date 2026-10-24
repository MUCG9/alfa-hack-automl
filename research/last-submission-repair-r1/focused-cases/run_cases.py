"""One fixed12-case technical leaf; SOURCE ONLY until actual UAR10 closure."""
from pathlib import Path
import argparse,ast,hashlib,importlib.util,json,math,os,shutil,stat,sys,tempfile,time
sys.dont_write_bytecode=True

PACKET=Path(__file__).resolve().parent;WORK=PACKET.parent;OUT=WORK/'lc1'
COMMON,PARENT,CHILD,FINAL,DRIVER_FINAL,ROOT=180,120,90,60,30,30
BASE=WORK/'br-standard-release-qualification-next-dev/controller-r5/run_controller.py'
BASE_SHA='d5f41cad6de2168cd520e442223428285dd3714854079d9305dd1b34938abd7d'
TEST=WORK/'last-submission-class-runtime-cases-next-dev/test_class_runtime_contracts.py'
TEST_SHA='36106384c503e7f86d145f171f73c8b9a6ef68fe662cde92d21c9ffffa5ae728'
SUITE_HANDOFF='3ca0c66813836ce3b851bf6bc0b77b9c9228686e6c9cfcc45f5e462136406235'
SUITE_PEER='21e80e3fc9497f2aca03bdd15b9ab2b3c4c9ba777db4704fb6cf7b3a298dffd6'
ARCHIVE=WORK.parent/'outputs/solution-br-rmse34.15502.zip'
ARCHIVE_SHA='c7b54a8996e36dfaaf582b104d1f38ecca71d91d4f38362ed50775381f42f930'
FINITE_REF=('private/uar10-prelaunch-finite-r1.json','edc1c981bd03a53a1c92d35d5e5c655d26eb432454fbc35a61e53a51a301d1ad')
U10_REFS={
 'root':('uar10-context-selector-gate-next-dev-r3/attempt-r1/terminal-root-closure.json','0410ab460a9b5bc61cc6cb5049c477db9c96f55384ed135338dee18e317227d8'),
 'fresh':('uar10-context-selector-gate-next-dev-r3/attempt-r1/root-confirmation.json','dede0e94b7919b603cc2ffb575b2401d2eabef8a8889f8cd2a7d7141f84e64b8'),
 'post_tool':('uar10-context-selector-gate-next-dev-r3/attempt-r1/actual-wrapper-exit-confirmation.json','311dbe0d3eaa0f343b0c4c9cd991b5113ddf6977842545bff2d7304d0956b48b')}
COUNTER=('uar-count-parser-next-dev/counts.py','bc320fd4723476c8a73404ed17a7bdec0cd4c69b1b1d41b321e370549c8cf4d3')

def need(v,code):
    if not v:raise RuntimeError(code)
def read(p):return json.loads(Path(p).read_text('utf-8'))
def sha(p,check=lambda:None):
    h=hashlib.sha256()
    with Path(p).open('rb') as stream:
        while True:
            check();block=stream.read(2**20)
            if not block:break
            h.update(block)
    check();return h.hexdigest()
def save(p,value):
    p=Path(p);pending=p.with_name(p.name+'.pending')
    with pending.open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2,ensure_ascii=False,allow_nan=False)
    os.replace(pending,p)
def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def methods(p):
    return {n.name:hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest()
        for c in ast.parse(Path(p).read_bytes()).body if isinstance(c,ast.ClassDef)
        for n in c.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')}
def fence(path):
    p=Path(path);base=WORK/'t'
    need(base.resolve()==base and p.parent==base and p.name.startswith('lc-') and p.resolve()==p,'exact_shallow_owned_temp_required')
    for item in [base,p,*p.rglob('*')]:
        metadata=item.lstat()
        need(not item.is_symlink() and not(getattr(metadata,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',1024)),
             'owned_temp_symlink_or_junction_denied')
        need(item.resolve().is_relative_to(base),'owned_temp_escape_denied')

def config(path,expected,self_sha):
    need(Path(path).is_absolute() and sha(path)==expected and Path(path).stat().st_size<=2**20,'exact_absolute_private_manifest')
    cfg=read(path);pins=cfg['immutable_files']
    need(cfg.get('schema')=='last-submission-class-cases-private-v1' and cfg.get('readiness')=='READY_FROZEN_SOURCE_REVIEWED'
         and cfg.get('missing_bindings')==[],'NOT_READY_actual_UAR10_closure_review_publication_required')
    need(cfg['output']==str(OUT) and cfg['work_root']==str(WORK) and cfg['common_seconds']==180
         and cfg['lock']==str(WORK/'alfa-hack-automl/test-runs/.owned-research.lock'),'fixed_output_work_lock_common_required')
    need(pins.get(str(Path(__file__).resolve()))==self_sha==sha(__file__)
         and cfg['python']==str(WORK/'venv/Scripts/python.exe')
         and pins.get(cfg['python'])=='d59c9a894b319828d023f3aa83d9a3488d2339f9e27e60e49b02abb0d53cf538',
         'fixed_self_and_python_required')
    need(pins.get(str(BASE))==BASE_SHA and pins.get(str(TEST))==TEST_SHA
         and pins.get(str(ARCHIVE))==ARCHIVE_SHA,'fixed_C5_suite_and_c7b_required')
    need(cfg['counter']==dict(path=str(WORK/COUNTER[0]),sha256=COUNTER[1])
         and pins.get(cfg['counter']['path'])==COUNTER[1],'unchanged_structural12_counter_required')
    packet=TEST.parent;handoff=read(packet/'source-handoff.json')
    need(pins.get(str(packet/'source-handoff.json'))==sha(packet/'source-handoff.json')==SUITE_HANDOFF
         and pins.get(str(WORK/'last-submission-class-runtime-cases-independent-review-r1.json'))==SUITE_PEER,
         'fixed_12_case_suite_handoff_and_peer_required')
    need(methods(TEST)==handoff['method_AST_sha256'] and len(methods(TEST))==12,'exact12_methods_no_suite_change')
    for rel,h in handoff['files_sha256'].items():need(pins.get(str(packet/rel))==h,'suite_all_source_dependencies_pinned')
    r5=read(WORK/'br-standard-release-next-dev-r5/source-handoff.json')
    need(pins.get(str(WORK/'br-standard-release-next-dev-r5/source-handoff.json'))=='92cfd41804ca162ba5ec4aeff53a3cb45e6b0c798b93e0c36c1cbb969fdfef08','exact_R5_runtime_inventory_required')
    for rel,h in r5['files_sha256'].items():
        if rel.startswith('candidate/'):
            need(pins.get(str(WORK/'br-standard-release-next-dev-r5'/rel))==h,'all74_source_members_bound_before_test_import')
    for p,h in pins.items():need(Path(p).is_absolute() and sha(p)==h,'immutable_source_pin_changed')
    return cfg

def predecessor(cfg,base,check):
    refs=cfg['uar10'];pins=cfg['immutable_files']
    need(set(refs)=={'root','fresh','post_tool','driver_actual','wrapper_actual','post_tool_actual'},'actual_UAR10_exact_refs_required')
    for k in ('root','fresh','post_tool'):
        ref=refs[k];relative,expected=U10_REFS[k]
        need(ref==dict(path=str(WORK/relative),sha256=expected) and pins.get(ref['path'])==ref['sha256']
            and sha(ref['path'],check)==ref['sha256'],'actual_UAR10_ref_changed')
    actual=refs['driver_actual'];wrapper=refs['wrapper_actual'];postactual=refs['post_tool_actual']
    need(set(actual)=={'session','exit_code','tool'} and type(actual['session']) is int and actual['session']>0
         and actual['exit_code']==0 and type(actual['tool']) is str and actual['tool']
         and set(wrapper)==set(postactual)=={'exit_code','tool'} and wrapper['exit_code']==postactual['exit_code']==0
         and wrapper['tool'] and postactual['tool'],'root_observed_whole_wrapper_and_post_tool_exits_required')
    need(actual==dict(session=87837,exit_code=0,tool='5ebb6b') and wrapper==dict(exit_code=0,tool='1b3208')
         and postactual==dict(exit_code=0,tool='52e793'),'exact_actual_closed_UAR10_execs_required')
    root,fresh,post=(read(refs[k]['path']) for k in ('root','fresh','post_tool'))
    need(root.get('schema')=='uar-full-root-closure-v1' and root.get('technical_procedure_passed') is True
         and root.get('actual_exec_session')==actual['session'] and root.get('actual_exec_exit_code_observed_by_root')==0
         and root.get('actual_tool_evidence')==actual['tool']
         and all(root.get(k) is True for k in ('source_unchanged','cleanup_confirmed','temporary_cleanup_confirmed'))
         and root.get('active_owned_processes')==[] and root.get('uncertain_owned')==[],
         'closed_actual_clean_UAR10_required_no_false_flag_coercion')
    need(fresh.get('schema')=='uar10-atomic-root-confirmation-v1' and fresh.get('root_sha256')==refs['root']['sha256']
         and fresh.get('actual_driver')==actual and fresh.get('actual_closer_exit')==0
         and all(fresh.get(k) is True for k in ('technical_procedure_passed','source_unchanged','current_temporary_absent','current_cleanup_confirmed',
             'inside_actual_closer_birth60','inside_original1200','inside_existing_driver_final180'))
         and fresh.get('known_exact_live')==[] and fresh.get('uncertain')==[] and fresh.get('errors')==[],
         'atomic_original_UAR10_closer_window_must_be_qualified')
    known=base.ids(fresh['known_identities']);need(len(known)==fresh['known_count']==len(fresh['known_identities']),'explicit_saved_known_array_required')
    known|=base.ids(fresh['wrapper_preparer_identities'])
    need(base.ids(root['owned_identities']+root['closure_preparer_identities'])<=known,'entire_UAR10_owned_and_root_union_required')
    extras=cfg['additional_preparer_receipts']
    need(extras==post.get('additional_preparer_receipts')==[dict(path=str(WORK/FINITE_REF[0]),sha256=FINITE_REF[1],actual_tool=dict(exit_code=0,tool='29e446'))],
         'three_actual_prelaunch_observer_preparers_must_be_bound')
    for ref in extras:
        need(set(ref)=={'path','sha256','actual_tool'} and ref['actual_tool']['exit_code']==0 and ref['actual_tool']['tool']
             and pins.get(ref['path'])==ref['sha256'] and sha(ref['path'],check)==ref['sha256'],'actual_additional_preparer_receipt_required')
        known|=base.ids(read(ref['path'])['identities'])
    need(post.get('schema')=='uar10-actual-wrapper-exit-confirmed-v1' and post.get('root_confirmation_sha256')==refs['fresh']['sha256']
         and post.get('actual_wrapper')==wrapper and post.get('known_count')==len(known)
         and post.get('known_exact_live')==[] and post.get('uncertain')==[]
         and post.get('source_unchanged') is True and post.get('post_tool_confirmed') is True,
         'actual_post_tool_count_must_match_explicit_fresh_preparer_union')
    # These tuples are the post-tool observer's actual identities, not an
    # invented array in a count-only receipt. Their own actual tool0 is mandatory.
    need(type(post.get('post_tool_preparer_identities')) is list and len(post['post_tool_preparer_identities'])==3,'actual_post_tool_observer_tuple_required')
    known|=base.ids(post['post_tool_preparer_identities'])
    for ref in cfg.get('launch_preparer_receipts',[]):
        need(set(ref)=={'path','sha256','actual_tool'} and set(ref['actual_tool'])=={'exit_code','tool'}
             and ref['actual_tool']['exit_code']==0 and ref['actual_tool']['tool']
             and pins.get(ref['path'])==ref['sha256'] and sha(ref['path'],check)==ref['sha256'],
             'actual_later_metadata_preparer_source_and_exit_required')
        known|=base.ids(read(ref['path'])['identities'])
    return known

def main():
    p=argparse.ArgumentParser();p.add_argument('--launch',action='store_true',required=True)
    for name in ('manifest','manifest-sha256','self-sha256'):p.add_argument('--'+name,required=True)
    p.add_argument('--launch-parent-pid',type=int,required=True);p.add_argument('--launch-parent-create-time',type=float,required=True)
    a=p.parse_args();start,mono=time.time(),time.monotonic();unix,end=start+COMMON,mono+COMMON;final_end=None
    need(sha(BASE)==BASE_SHA,'qualified_C5_guard_changed');base=imported('_class_cases_C5',BASE)
    import psutil
    preparers,chain=base.capture(psutil,a.launch_parent_pid,a.launch_parent_create_time)
    with (PACKET/'driver-preparer-identity.json').open('x',encoding='utf-8') as stream:
        json.dump(dict(identities=preparers,launch_parent_observation=chain,original_start_unix=start,original_start_monotonic=mono),stream,allow_nan=False)
    need(chain.get('verified') is True,'actual_self_direct_shell_launch_chain_required')
    need(not OUT.exists(),'exclusive_new_fixed_case_attempt');OUT.mkdir()
    state=dict(schema='last-submission-class-cases-campaign-v1',status='starting',start_unix=start,start_monotonic=mono,
        absolute_deadline_unix=unix,common_deadline_monotonic=end,common_seconds=180,
        owned_root=preparers[0],coordinator_bootstrap_identities=preparers[1:],supervisors=[],active_supervisor=None,
        error_history=[],cleanup_uncertainty=[],cleanup_confirmed=False,source_unchanged=False,temporary_cleanup_confirmed=False,
        technical_procedure_passed=False,actual_tests=None,model_fits=0,API_calls=0,quality_metric=None,promotion=False,submit=False,_manifest={})
    cfg=None;modules={};coor=owner=lease=awake=None;known=set();children=set();tmp=None;pulse=lambda **kw:None
    def persist():save(OUT/'campaign.json',{k:v for k,v in state.items() if not k.startswith('_')})
    def clock():
        need(time.monotonic()<end and time.time()<unix,'original180_exhausted')
        need(abs((end-time.monotonic())-(unix-time.time()))<=5,'wall_monotonic_disagreement')
        if final_end is not None:need(time.monotonic()<final_end,'driver_final30_exhausted')
    def fail(exc,phase):
        row=dict(phase=phase,type=type(exc).__name__,code=str(exc) if isinstance(exc,RuntimeError) else None)
        state.setdefault('first_failure',row);state['error_history'].append(row);state['status']='failed'
    def frozen(parent_end=None,code='phase_cap'):
        for path,h in cfg['immutable_files'].items():need(sha(path,pulse)==h,'immutable_source_changed')
        need(sha(a.manifest,pulse)==a.manifest_sha256,'private_binding_changed');clock()
        if parent_end is not None:need(time.monotonic()<parent_end,code)
    try:
        cfg=config(a.manifest,a.manifest_sha256,a.self_sha256)
        for key,(rel,h) in base.HELPERS.items():
            need(cfg['immutable_files'].get(str(WORK/rel))==h and sha(WORK/rel)==h,'qualified_dependency_missing')
            modules[key]=imported('_class_cases_'+key,WORK/rel)
        coor,owner=modules['coordinator'],modules['owner'];root=preparers[0]
        parent_pulse=base.guard(mono,end,unix,owner,preparers,state,sampling=modules['sampling'])
        parent_clock=state['_resource_checkpoint'];last_technical_sample=mono;pulse_maximum_gap=0.;pulse_sticky_error=None
        suite_ob=owner.StrictOwnedObserver();sampler=modules['sampling'].VerifiedResourceSampler();required=(root['pid'],root['create_time'])
        def resource_clock():
            nonlocal pulse_maximum_gap,pulse_sticky_error
            if pulse_sticky_error is not None:raise RuntimeError(pulse_sticky_error)
            try:
                parent_clock();clock();now=time.monotonic()
                pulse_maximum_gap=max(pulse_maximum_gap,now-last_technical_sample)
                need(now-last_technical_sample<=10,'technical_observation_gap10')
                return now
            except BaseException as exc:
                pulse_sticky_error=str(exc) if isinstance(exc,RuntimeError) else 'technical_resource_unconfirmed'
                raise
        def pulse(force=False):
            nonlocal last_technical_sample,pulse_sticky_error
            try:
                now=resource_clock();parent_pulse(force=force)
                if not force and now-last_technical_sample<.25:return
                # The exact C5 parent round has already birth-verified its
                # actual descendants; observe them immediately, before the
                # supervisor's periodic on-disk receipt publishes owned_root.
                suite_ob.remember([(r['pid'],r['create_time']) for r in state['verified_resource_sample']['sampled']
                    if (r['pid'],r['create_time']) not in coor.identities(preparers)])
                active=state.get('active_supervisor')
                if active:
                    record=read(Path(cfg['work_root'])/active)
                    if record.get('owned_root'):suite_ob.remember(coor.identities([record['owned_root']]))
                live=suite_ob.observe();need(not suite_ob.denials,'technical_tree_observation_denied')
                children.update(suite_ob.seen)
                sample=sampler.sample(set(suite_ob.seen)|set(live)|coor.identities(preparers),required=[required],checkpoint=resource_clock)
                child_rss=sum(row['rss_bytes'] for row in sample['sampled'] if (row['pid'],row['create_time']) in suite_ob.seen)
                need(child_rss<=1536*2**20,'technical_child_tree_memory_limit')
                need(sum(row['rss_bytes'] for row in sample['sampled'])<=2048*2**20,'whole_technical_parent_memory_limit')
                state['peak_technical_tree_rss_mib']=max(state.get('peak_technical_tree_rss_mib',0.),child_rss/2**20)
                state['verified_technical_resource_sample']=sample
                last_technical_sample=resource_clock()
            except BaseException as exc:
                pulse_sticky_error=str(exc) if isinstance(exc,RuntimeError) else 'technical_resource_observation_unconfirmed'
                raise
        state['_pulse']=pulse;state['_resource_checkpoint']=resource_clock
        known=predecessor(cfg,base,pulse);base.absent(owner,known,pulse)
        lease=modules['lock'].ResearchLock(cfg['lock']);lease.__enter__();lease.write_identity(preparers[0])
        base.absent(owner,known,pulse);awake=modules['awake'].PowerRequestGuard('last-submitted-CLASS12cases');awake.__enter__();state['_awake']=awake
        frozen();need(time.monotonic()+CHILD<mono+PARENT,'setup_must_leave_full_child90_inside_parent120')
        (WORK/'t').mkdir(exist_ok=True);tmp=Path(tempfile.mkdtemp(prefix='lc-',dir=WORK/'t')).resolve();fence(tmp)
        state['temporary_root']=str(tmp);save(OUT/'temporary-root.json',dict(root=str(tmp),owner=preparers[0],scope='exclusive_fixed_CLASS_case_environment'))
        state['status']='running12';persist();receipt=tmp/'cases.json'
        try:
            sup=coor.supervise([cfg['python'],'-B','-X','utf8',str(TEST),'-v'],TEST.parent,receipt,'class-cases',mono,PARENT,CHILD,
                end,unix,60,state,persist,frozen,owner,modules['processes'],preparers[1:],solver_seconds=None)
        finally:
            if receipt.exists():
                row=read(receipt);known|=base.ids(row.get('owned_process_identities',[]))
                if row.get('owned_root'):known|=base.ids([row['owned_root']])
                ob=row.get('cleanup_observation',{})
                if row.get('cleanup_confirmed') is not True or ob.get('unresolved')!=[] or ob.get('denial_count')!=0:
                    state['cleanup_uncertainty'].append(dict(receipt=str(receipt),observation=ob))
                for ext in ('.json','.log'):
                    source=receipt.with_suffix(ext);destination=OUT/('cases'+ext);shutil.copyfile(source,destination)
                    need(sha(source,pulse)==sha(destination,pulse),'terminal_receipt_log_copy_changed')
            else:state['cleanup_uncertainty'].append(dict(reason='no_actual_child_receipt'))
        coor.child_errors(state,sup)
        counter=imported('_class_cases_counter',cfg['counter']['path'])
        need(sup.get('status')=='ok' and sup.get('exit_code')==0 and sup.get('cleanup_confirmed') is True
             and not sup.get('error_history') and counter.counts((OUT/'cases.log').read_text('utf-8'),12),
             'exact12_actual_tests_exit0_OK_no_skips_required')
        state.update(status='cases_passed_pending_terminal',actual_tests=12)
    except BaseException as exc:fail(exc,'case_run')
    finally:
        final_begin=time.monotonic();post_tool_end=min(final_begin+FINAL,end);final_end=min(final_begin+DRIVER_FINAL,post_tool_end-ROOT)
        state.update(final_start_monotonic=final_begin,driver_final_deadline_monotonic=final_end,post_tool_deadline_monotonic=post_tool_end)
        try:
            pulse(force=True);clock();need(cfg is not None and owner is not None,'terminal_authority_unavailable')
            known|=children;base.absent(owner,known,pulse);frozen(final_end)
            need(state['active_supervisor'] is None and not state['cleanup_uncertainty']
                 and all(s.get('cleanup_confirmed') is True for s in state['supervisors']),'sticky_child_cleanup_unconfirmed')
            if tmp is not None:
                fence(tmp);state['temporary_inventory_before_removal']=base.seal(tmp,pulse);base.absent(owner,known,pulse)
                shutil.rmtree(tmp);pulse(force=True);need(not tmp.exists(),'owned_temp_not_removed')
            state.update(cleanup_confirmed=True,source_unchanged=True,temporary_cleanup_confirmed=True)
        except BaseException as exc:fail(exc,'final_source_temp_cleanup')
        try:
            if awake is not None:awake.close();state['awake_guard']=awake.record
            pulse(force=True);clock();need(state.get('awake_guard',{}).get('release_API_verified') is True,'Power_release_unconfirmed')
        except BaseException as exc:fail(exc,'Power_release')
        if lease is not None:
            try:lease.__exit__(None,None,None);pulse(force=True);clock()
            except BaseException as exc:fail(exc,'lease_release')
        try:frozen(final_end)
        except BaseException as exc:fail(exc,'terminal_source_hash');state['source_unchanged']=False
        state['owned_identities']=[dict(pid=p,create_time=b) for p,b in sorted(known|children)]
        state['closure_preparer_identities']=preparers
        passed=state['status']=='cases_passed_pending_terminal' and not state['error_history']
        passed=passed and all(state[k] is True for k in ('cleanup_confirmed','source_unchanged','temporary_cleanup_confirmed'))
        state.update(technical_procedure_passed=bool(passed),status='terminal_pending_actual_tool_and_fresh_root' if passed else 'failed',
            finished_unix=time.time(),finished_monotonic=time.monotonic(),actual_tool_exit_and_fresh_preparer_absence_pending=True)
        try:
            pulse(force=True);clock();persist()
            save(OUT/'terminal-root-closure.json',{k:v for k,v in state.items() if not k.startswith('_')})
            pulse(force=True);clock()
        except BaseException as exc:
            fail(exc,'terminal_save');state['technical_procedure_passed']=False;persist();passed=False
            save(OUT/'terminal-root-closure.json',{k:v for k,v in state.items() if not k.startswith('_')})
    print(json.dumps(dict(technical_procedure_passed=bool(passed),actual_tests=state['actual_tests'],model_fits=0,API_calls=0,tool_and_fresh_pending=True)))
    return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
