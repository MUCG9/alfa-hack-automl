"""New UAR08 technical gate; prior UAR05/UAR04 remain closed FAIL, never resumed."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, math, re, shutil, sys, tempfile, time
sys.dont_write_bytecode=True
COMMON,PARENT,CHILD,FINAL,ROOT_CLOSE,MINIMUM_REMAINING=1200,900,840,180,60,1140
HELPERS={'coordinator':'43be86ece6c453641afdcc6f8eccef02d713986e2ac8bf3314756f0bb78e0818',
 'owner':'8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8',
 'processes':'fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d',
 'lock':'78a0441bb3b9ea60197e9a1a6e1087f6e4cd0886593ec54bcfc4e41c9abe5a45',
 'awake':'9a0bae0acb6ddb37e638420c52ad1e587a9180fbd7ef68ebc6e1a3c43e4bfc9b'}
BASE_SHA='c3e87a486e0b4bdd9a2189dd6151e6871d838923f04efde1f884cf0fda7d9ae3'

def need(value,code):
    if not value:raise RuntimeError(code)

def read(path):return json.loads(Path(path).read_text('utf-8'))

def digest(path,pulse=lambda:None):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            pulse();block=stream.read(2**20)
            if not block:break
            h.update(block)
    pulse();return h.hexdigest()

def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module

def config(path,expected,self_sha):
    need(Path(path).is_absolute() and Path(path).stat().st_size<=2**20,'bounded_absolute_manifest_required')
    need(digest(path)==expected,'private_manifest_changed');cfg=read(path)
    need(type(cfg) is dict and cfg.get('schema')=='uar-full-private-manifest-v1'
         and cfg.get('readiness')=='READY_FROZEN_SOURCE_REVIEWED' and cfg.get('missing_bindings')==[],
         'NOT_READY_combined_source_review_and_freeze_required')
    need(cfg.get('common_seconds')==COMMON,'exact_fresh_common1200_required')
    for key in ('work_root','canonical_root','python','output','lock_path','technical_entry','contracts','focused_helper'):
        need(type(cfg.get(key)) is str and Path(cfg[key]).is_absolute(),'all_forwarded_paths_must_be_absolute')
    root=Path(cfg['canonical_root']);work=Path(cfg['work_root']);packet=Path(__file__).resolve().parent
    need(root.resolve()==(work/'alfa-hack-automl').resolve()
         and Path(cfg['output']).parent.resolve()==packet
         and Path(cfg['technical_entry']).resolve()==packet/'technical_entry.py'
         and Path(cfg['contracts']).resolve()==packet/'contracts.py'
         and Path(cfg['focused_helper']).resolve()==work/'uar-focused-gate-next-dev/run_gate.py'
         and Path(cfg['lock_path']).resolve()==root/'test-runs/.owned-research.lock','fixed_gate_paths_required')
    pins=cfg.get('files_sha256')
    need(type(pins) is dict and 1<=len(pins)<=4096 and all(type(k) is str and Path(k).is_absolute()
        and type(v) is str and re.fullmatch('[0-9a-f]{64}',v) for k,v in pins.items()),'typed_frozen_hash_inventory')
    need(pins.get(str(Path(__file__).resolve()))==self_sha and digest(__file__)==self_sha,'driver_changed')
    need(pins.get(cfg['focused_helper'])==BASE_SHA,'proven_focused_helper_pin_required')
    for name,expected_sha in HELPERS.items():
        ref=cfg['helpers'][name];need(ref['sha256']==expected_sha and pins.get(ref['path'])==expected_sha
            and Path(ref['path']).is_absolute(),'proven_guard_changed')
    need(cfg['candidate_process_sha256']=='9f84f64199b63dc4cef095e026d23084e338f1e42a97d5b4bd083e10f687bdb3'
         and pins.get(str((root/'src/automl/infrastructure/processes.py').resolve()))==cfg['candidate_process_sha256'],
         'candidate_process_separate_from_historical_fac3_guard')
    need(type(cfg.get('canonical_python_inventory')) is list and len(cfg['canonical_python_inventory'])<=2048
         and len(set(cfg['canonical_python_inventory']))==len(cfg['canonical_python_inventory'])
         and all(v in pins and Path(v).is_relative_to(root) for v in cfg['canonical_python_inventory']),
         'exact_canonical_python_inventory_required')
    need(type(cfg.get('registry')) is dict and type(cfg.get('flat_inventory')) is list,
         'actual_registry_and_flat_inventory_required')
    need(type(cfg.get('mapped_suites')) is list and 2<=len(cfg['mapped_suites'])<=8,'bounded_mapped_whitelist_required')
    ids=[];testpaths=[]
    for suite in cfg['mapped_suites']:
        need(type(suite) is dict and set(suite)=={'id','test','test_relative_path','expected_tests','all_methods',
            'selected_methods','excluded_methods','exclusion_reason','source_review_ref'},'typed_mapped_suite_no_commands')
        rel=suite['test_relative_path'];need(type(rel) is str and re.fullmatch(r'tests/test_uar_[a-z0-9_]+\.py',rel),
            'reviewed_uar_test_path_required')
        need(re.fullmatch('[a-z][a-z0-9_]{0,31}',suite['id']) and Path(suite['test']).is_absolute()
             and Path(suite['test']).resolve()==(root/rel).resolve() and suite['test'] in pins,'fixed_test_path_required')
        for name in ('all_methods','selected_methods','excluded_methods'):
            need(type(suite[name]) is list and len(suite[name])<=256
                 and len(set(suite[name]))==len(suite[name]) and all(type(v) is str and
                 re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*\.test_[A-Za-z0-9_]+',v) for v in suite[name]),
                 'explicit_qualified_method_whitelist_required')
        need(type(suite['expected_tests']) is int and 1<=suite['expected_tests']==len(suite['selected_methods'])<=256,
             'exact_selected_test_count_required')
        expected_exclusion=['LossContractTests.test_default_OFF_all_six_modules_preserve_base_UAR_AST']
        if suite['excluded_methods']:
            need(rel=='tests/test_uar_loss_backend.py' and suite['excluded_methods']==expected_exclusion
                 and suite['exclusion_reason']=='modular_source_AST_assertion_covered_by_full_source_not_flat',
                 'only_predeclared_modular_source_AST_exclusion_allowed')
        else:need(suite['exclusion_reason'] is None,'unannounced_mapped_exclusion')
        ref=suite['source_review_ref'];need(type(ref) is dict and set(ref)=={'path','sha256'}
             and Path(ref['path']).is_absolute() and pins.get(ref['path'])==ref['sha256'],'actual_source_review_required')
        ids.append(suite['id'].casefold());testpaths.append(rel.casefold())
    mandatory={'tests/test_uar_early_declaration.py':(14,14),
               'tests/test_uar_vertical_contract.py':(14,14),
               'tests/test_uar_loss_backend.py':(17,16),
               'tests/test_uar_strong_retention.py':(15,15),
               'tests/test_uar_metric_contrast.py':(16,16),
               'tests/test_uar_task_checkpoint_cadence.py':(12,12)}
    need(len(ids)==len(set(ids)) and len(testpaths)==len(set(testpaths)) and set(testpaths)==set(mandatory),
         'exact_six_mandatory_mapped_suites_required')
    for suite in cfg['mapped_suites']:
        rel=suite['test_relative_path'];all_count,selected_count=mandatory[rel]
        need(len(suite['all_methods'])==all_count and suite['expected_tests']==selected_count
             and cfg['registry'].get(Path(rel).name)==all_count
             and suite['selected_methods']==[n for n in suite['all_methods'] if n not in suite['excluded_methods']],
             'mandatory_full_source_and_flat_coverage_required')
        if rel=='tests/test_uar_loss_backend.py':
            need(suite['excluded_methods']==
                 ['LossContractTests.test_default_OFF_all_six_modules_preserve_base_UAR_AST']
                 and suite['exclusion_reason']=='modular_source_AST_assertion_covered_by_full_source_not_flat',
                 'LOSS17_source_and_exact16_applicable_flat_required')
        else:
            need(suite['excluded_methods']==[] and suite['exclusion_reason'] is None,
                 'all_IO03_vertical_retention_methods_mandatory')
    need(len(cfg['registry'])==58 and sum(cfg['registry'].values())==616
         and len(cfg['flat_inventory'])==73,'declared_combined_source58_616_flat73_required')
    need(type(cfg.get('predecessors')) is list and any(r.get('id')=='uar03' and r.get('sha256')==
         'e86a151481b5b2849d9d0b6b4dc8ef6787a6ccf766dd97486b65de9d05cbf5d9' for r in cfg['predecessors']),
         'actual_UAR03_terminal_root_required')
    latest=[r for r in cfg['predecessors'] if r.get('id')=='uq2']
    need(cfg.get('latest_predecessor_id')=='uq2' and len(latest)==1
         and cfg.get('requires_whole_UQ2_terminal_and_fresh_closure') is True,
         'whole_UQ2_terminal_fresh_root_required_before_new_gate')
    ref=latest[0]
    need(Path(ref['path']).resolve()==work/'uq2/terminal-root-closure.json'
         and ref.get('actual_exec_session')==3588 and type(ref.get('actual_exit_code')) is int
         and ref['actual_exit_code'] in (0,1) and type(ref.get('actual_tool_evidence')) is str
         and bool(ref['actual_tool_evidence'].strip()),'actual_UQ2_exit_evidence_not_pending_required')
    # Normal source_union checks actual cleanup/source and current absence. A
    # false/unqualified root needs a separately reviewed typed observation;
    # this fixed source does not coerce a negative receipt into normal success.
    for ref in cfg['predecessors']:
        need(type(ref) is dict and pins.get(ref['path'])==ref['sha256'],'predecessor_must_be_frozen')
    history=cfg.get('historical_failure_evidence',[])
    need(any(r.get('sha256')=='87f691b5774ed6f604069d952041bdd6af6a6022f9ea1268ac77a8364180a106'
         and r.get('scope')=='immutable_evidence_only_not_owned_grant' and pins.get(r['path'])==r['sha256']
         for r in history),'unqualified_UAR02_failure_must_remain_evidence_only')
    for pathkey in ('technical_entry','contracts','focused_helper'):
        need(cfg[pathkey] in pins,'gate_dependency_pin_missing')
    return cfg

def own_bootstraps(psutil):
    me=psutil.Process();result=[];parent=me.parent()
    while parent is not None:
        birth=parent.create_time()
        if not any(Path(v).resolve()==Path(__file__).resolve() for v in parent.cmdline() if v and not v.startswith('-')):break
        need(parent.create_time()==birth,'bootstrap_identity_changed')
        result.append(dict(pid=parent.pid,create_time=birth));parent=parent.parent()
    return dict(pid=me.pid,create_time=me.create_time()),result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--launch',action='store_true',required=True)
    for name in ('private-manifest','private-manifest-sha256','self-sha256','latest-root-closure-sha256'):
        p.add_argument('--'+name,required=True)
    a=p.parse_args();start,mono=time.time(),time.monotonic();unix,end=start+COMMON,mono+COMMON;final_end=None
    a.private_manifest=str(Path(a.private_manifest).resolve())
    def clock():
        need(time.time()<unix and time.monotonic()<end,'original1200_deadline_exhausted')
        need(abs((unix-time.time())-(end-time.monotonic()))<=5,'clock_disagreement')
        if final_end is not None:need(time.monotonic()<final_end,'actual_final180_cap_exhausted')
    cfg=config(a.private_manifest,a.private_manifest_sha256,a.self_sha256)
    need(__debug__ and Path(cfg['python']).resolve()==Path(sys.executable).resolve(),'pinned_nonoptimized_interpreter_required')
    refs={r['id']:r for r in cfg['predecessors']}
    need(refs[cfg['latest_predecessor_id']]['sha256']==a.latest_root_closure_sha256,'actual_latest_closure_pin_required')
    for name in ('contracts','focused_helper'):
        need(digest(cfg[name],clock)==cfg['files_sha256'][cfg[name]],'standalone_dependency_changed')
    contract=imported('_uar04_contracts',cfg['contracts']);base=imported('_uar04_focused_helpers',cfg['focused_helper'])
    for name in HELPERS:need(digest(cfg['helpers'][name]['path'],clock)==HELPERS[name],'guard_dependency_changed')
    modules={n:imported('_uar04_'+n,cfg['helpers'][n]['path']) for n in HELPERS}
    coor,owner,proc=(modules[n] for n in ('coordinator','owner','processes'))
    need(coor.WORK.resolve()==Path(cfg['work_root']).resolve(),'proven_work_root_mismatch')
    import psutil
    root,boot=own_bootstraps(psutil);out=Path(cfg['output']);need(not out.exists(),'exclusive_attempt_no_reset')
    out.mkdir();state=dict(schema='uar-full-campaign-v1',status='starting',start_unix=start,start_monotonic=mono,
        absolute_deadline_unix=unix,common_deadline_monotonic=end,common_seconds=COMMON,
        phase_caps_seconds=dict(parent=PARENT,child=CHILD,actual_final=FINAL,root_close=ROOT_CLOSE),
        private_manifest_sha256=a.private_manifest_sha256,owned_root=root,coordinator_bootstrap_identities=boot,
        supervisors=[],active_supervisor=None,error_history=[],cleanup_confirmed=False,source_unchanged=False,
        fixture_learner_fits=None,external_API_calls=None,public_experiment_fits=0,quality_metric=None,
        root_actual_exec_confirmation_pending=True,promotion=False,submit=False,_manifest={},
        temporary_root=None,temporary_cleanup_confirmed=False)
    known=children=set();suite_ob=owner.StrictOwnedObserver();awake=None;temporary_root=None;power_released=False
    def persist():coor.save(out/'campaign.json',{k:v for k,v in state.items() if not k.startswith('_')})
    pulse_previous=mono;pulse_maximum_gap=0.;pulse_sticky_error=None
    def pulse():
        nonlocal pulse_previous,pulse_maximum_gap,pulse_sticky_error
        if pulse_sticky_error is not None:raise RuntimeError(pulse_sticky_error)
        try:
            observed=time.monotonic();pulse_maximum_gap=max(pulse_maximum_gap,observed-pulse_previous)
            need(observed-pulse_previous<=10,'parent_observation_gap10')
            if not power_released:coor.cooperative_checkpoint(awake,end,unix)
            clock()
            rss=psutil.Process().memory_info().rss
            for saved in boot:
                try:
                    obj=psutil.Process(saved['pid'])
                    if obj.create_time()==saved['create_time']:rss+=obj.memory_info().rss
                except psutil.NoSuchProcess:pass
            need(rss<=2048*2**20,'parent_bootstrap_memory_limit')
            active=state.get('active_supervisor')
            if active:
                record=read(Path(cfg['work_root'])/active)
                if record.get('owned_root'):suite_ob.remember(coor.identities([record['owned_root']]))
                live=suite_ob.observe();need(not suite_ob.denials,'technical_tree_observation_denied');rss=0
                for identity,obj in live.items():
                    try:need(obj.create_time()==identity[1],'technical_identity_changed');rss+=obj.memory_info().rss
                    except psutil.NoSuchProcess:pass
                children.update(suite_ob.seen);need(rss<=1536*2**20,'technical_child_tree_memory_limit')
                state['peak_technical_tree_rss_mib']=max(state.get('peak_technical_tree_rss_mib',0.),rss/2**20)
            sampled=time.monotonic();pulse_maximum_gap=max(pulse_maximum_gap,sampled-pulse_previous)
            need(sampled-pulse_previous<=10,'parent_observation_gap10');clock()
            pulse_previous=sampled
        except Exception as exc:
            pulse_sticky_error=str(exc) if isinstance(exc,RuntimeError) else 'parent_resource_observation_unconfirmed'
            raise RuntimeError(pulse_sticky_error) from exc
    def guard(parent_end=None,code='parent_cap_exhausted'):
        coor.cooperative_checkpoint(awake,end,unix,parent_end,code);clock()
        need(digest(a.private_manifest,pulse)==a.private_manifest_sha256,'private_manifest_changed');contract.frozen(cfg,pulse)
    state['_pulse']=pulse
    try:
        need(time.monotonic()-mono<10,'pre_power_guard_setup_gap')
        awake=modules['awake'].PowerRequestGuard('UAR08 cadence combined serial technical fixtures',10)
        awake.__enter__();pulse()
        guard();known=base.source_union(cfg,coor,pulse);base.absence(owner,known)
        with modules['lock'].ResearchLock(cfg['lock_path']) as lease:
            lease.write_identity(root);base.absence(owner,known);persist();guard()
            need(unix-time.time()>=MINIMUM_REMAINING and end-time.monotonic()>=MINIMUM_REMAINING,
                 'mandatory_remaining1140_unavailable')
            need(time.monotonic()<mono+PARENT-CHILD,'setup60_consumed_full_child_admission')
            temporary_base=Path(cfg['work_root'])/'t'
            need(not temporary_base.is_symlink() and temporary_base.resolve()==temporary_base,
                 'temporary_base_symlink_or_junction_denied')
            temporary_base.mkdir(exist_ok=True)
            temporary_root=Path(tempfile.mkdtemp(prefix='u8-',dir=temporary_base)).resolve()
            need(temporary_root.parent==temporary_base.resolve() and not temporary_root.is_symlink(),
                 'exclusive_shallow_temporary_root_required')
            (temporary_root/'m').mkdir()
            state['temporary_root']=str(temporary_root)
            coor.save(out/'temporary-root.json',dict(schema=1,root=str(temporary_root),
                owner=root,run_id='UAR08',scope='exclusive_shallow_leaf_environment'),True)
            persist();guard()
            child_end=min(mono+PARENT,time.monotonic()+CHILD)
            command=[cfg['python'],'-B','-X','utf8',cfg['technical_entry'],
                '--private-manifest',a.private_manifest,'--private-manifest-sha256',a.private_manifest_sha256,
                '--deadline-monotonic',str(child_end),'--deadline-unix',str(start+child_end-mono),
                '--temporary-root',str(temporary_root)]
            sup=coor.supervise(command,Path(cfg['work_root']),out/'technical.json','technical',mono,PARENT,CHILD,
                end,unix,MINIMUM_REMAINING,state,persist,guard,owner,proc,boot)
            final_start=time.monotonic();final_end=min(final_start+FINAL,end-ROOT_CLOSE)
            state.update(final_start_monotonic=final_start,final_deadline_monotonic=final_end);coor.child_errors(state,sup)
            children.update(coor.identities(sup.get('owned_process_identities',[])))
            if sup.get('owned_root'):children.update(coor.identities([sup['owned_root']]))
            for name in ('technical-results.json','mapped-results.json'):
                if (out/name).exists():
                    raw=read(out/name);state[name.replace('.json','')+'_first_failure']=raw.get('first_failure')
                    for row in raw.get('leaves',[]):
                        if row.get('owned_root'):children.update(coor.identities([row['owned_root']]))
                        children.update(coor.identities(row.get('owned_process_identities',[])))
            persist();base.absence(owner,known|children)
            need(sup['status']=='ok' and sup['exit_code']==0 and sup['cleanup_confirmed'] is True
                 and not sup.get('error_history'),'mandatory_technical_child_failed')
            summary,artifacts=contract.artifact_checks(cfg,out,pulse);state.update(summary);state['qualified_checks']=summary
            state['technical_artifacts']=artifacts;guard();base.absence(owner,known|children)
            state.update(status='technical_completed_pending_root',technical_procedure_passed=True,
                cleanup_confirmed=True,source_unchanged=True);persist();guard()
    except BaseException as exc:
        coor.error(state,str(exc) if isinstance(exc,RuntimeError) else 'full_gate_operation_failed','full_gate',exc)
        state.update(status='technical_failure',technical_procedure_passed=False)
    finally:
        if final_end is None:
            now=time.monotonic();final_end=min(now+FINAL,mono+PARENT+FINAL,end-ROOT_CLOSE)
            state.update(final_start_monotonic=now,final_deadline_monotonic=final_end)
        try:
            state['owned_process_identities']=[dict(pid=p,create_time=b) for p,b in sorted(children)]
            state.update(cleanup_confirmed=False,source_unchanged=False)
            try:
                started=False
                for phase in ('technical',):
                    pulse();path=out/'technical.json';record=read(path) if path.exists() else {}
                    started|=bool(record.get('owned_root'))
                    if record.get('owned_root'):children.update(coor.identities([record['owned_root']]))
                    children.update(coor.identities(record.get('owned_process_identities',[])))
                    for name in ('technical-results.json','mapped-results.json'):
                        raw=read(out/name) if (out/name).exists() else {}
                        for row in raw.get('leaves',[]):
                            if row.get('owned_root'):children.update(coor.identities([row['owned_root']]))
                            children.update(coor.identities(row.get('owned_process_identities',[])))
                state['owned_process_identities']=[dict(pid=p,create_time=b) for p,b in sorted(children)]
                leaf_ok,uncertain=contract.cleanup_status(cfg,out,started)
                state.update(leaf_cleanup_confirmed=leaf_ok,leaf_cleanup_uncertainty=uncertain)
                pulse();base.absence(owner,known|children);pulse()
                need(state.get('active_supervisor') is None and all(r.get('cleanup_confirmed') is True
                     for r in state['supervisors']) and leaf_ok,'saved_leaf_or_supervisor_cleanup_unconfirmed')
                # Delete only our exclusive shallow tree, after exact owned absence.
                pulse();cleanup_start=time.monotonic()
                if temporary_root is not None:
                    expected_base=(Path(cfg['work_root'])/'t').resolve()
                    need(temporary_root.parent==expected_base and temporary_root.resolve()==temporary_root
                         and not temporary_root.is_symlink()
                         and re.fullmatch(r'u8-[a-z0-9_]{8}',temporary_root.name),
                         'temporary_cleanup_path_or_identity_changed')
                    shutil.rmtree(temporary_root)
                    need(not temporary_root.exists(),'temporary_root_remains_after_cleanup')
                pulse();need(time.monotonic()-cleanup_start<10,'temporary_cleanup_gap10_exhausted')
                coor.save(out/'temporary-cleanup.json',dict(schema=1,root=str(temporary_root) if temporary_root else None,
                    created=temporary_root is not None,cleanup_confirmed=True,
                    elapsed_seconds=time.monotonic()-cleanup_start),True)
                temp_ok,temp_uncertain=contract.temporary_status(cfg,out,state['temporary_root'])
                state.update(temporary_cleanup_confirmed=temp_ok,temporary_cleanup_uncertainty=temp_uncertain)
                need(temp_ok,'saved_temporary_cleanup_unconfirmed');pulse()
                state['cleanup_confirmed']=True
            except BaseException as exc:
                coor.error(state,'final_owned_cleanup_unconfirmed','final_cleanup',exc)
                state.update(status='technical_failure',technical_procedure_passed=False)
            try:
                pulse();contract.frozen(cfg,pulse);need(digest(a.private_manifest,pulse)==a.private_manifest_sha256,'private_manifest_changed')
                state['source_unchanged']=True;pulse()
            except BaseException as exc:
                coor.error(state,str(exc) if isinstance(exc,RuntimeError) else 'final_guard_failed','final',exc)
                state.update(status='technical_failure',technical_procedure_passed=False)
        finally:
            # A prior gap/denial stays sticky; release is attempted even if its pulse fails.
            try:pulse()
            except BaseException as exc:
                coor.error(state,str(exc) if isinstance(exc,RuntimeError) else 'final_pulse_unconfirmed','final_guard',exc)
                state.update(status='technical_failure',technical_procedure_passed=False)
            finally:
                try:
                    if awake is not None:awake.close()
                except BaseException as exc:
                    coor.error(state,'power_request_cleanup_unconfirmed','power_release',exc)
                    state.update(status='technical_failure',technical_procedure_passed=False)
                finally:
                    power_released=True
                    if awake is not None:state['awake_guard']=awake.record
            try:
                pulse()
                need(awake is not None and awake.record.get('release_API_verified') is True,
                     'power_request_cleanup_unconfirmed')
            except BaseException as exc:
                coor.error(state,str(exc) if isinstance(exc,RuntimeError) else 'released_guard_unconfirmed','power_release',exc)
                state.update(status='technical_failure',technical_procedure_passed=False)
        state.update(parent_guard_sticky_error=pulse_sticky_error,parent_maximum_observed_gap_seconds=pulse_maximum_gap)
        if state.get('technical_procedure_passed') is not True and state.get('qualified_checks') is not None:
            state['unqualified_completed_checks']=state['qualified_checks'];state['qualified_checks']=None
        state.update(finished_unix=time.time(),finished_monotonic=time.monotonic(),elapsed_common_seconds=time.monotonic()-mono)
        persist()
        try:pulse()
        except BaseException as exc:
            coor.error(state,str(exc) if isinstance(exc,RuntimeError) else 'terminal_guard_unconfirmed','terminal_save',exc)
            state.update(status='technical_failure',technical_procedure_passed=False,
                parent_guard_sticky_error=pulse_sticky_error,parent_maximum_observed_gap_seconds=pulse_maximum_gap)
            if state.get('qualified_checks') is not None:
                state['unqualified_completed_checks']=state['qualified_checks'];state['qualified_checks']=None
            persist()
    passed=state.get('technical_procedure_passed') is True and not state['error_history'] and state['cleanup_confirmed'] and state['source_unchanged'] and pulse_sticky_error is None and state.get('awake_guard',{}).get('release_API_verified') is True
    print(json.dumps({k:state.get(k) for k in ('status','qualified_checks',
        'source_unique_checks','mapped_repeated_checks','technical_procedure_passed','cleanup_confirmed','source_unchanged')},allow_nan=False))
    return 0 if passed else 1

if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as exc:
        print(json.dumps(dict(status='blocked_before_or_during_gate',error_type=type(exc).__name__,
            error_code=str(exc) if re.fullmatch('[A-Za-z0-9_]+',str(exc)) else 'preflight_operation_failed',quality_metric=None)))
        raise SystemExit(1)
