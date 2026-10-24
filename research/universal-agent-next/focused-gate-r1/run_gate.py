"""Reusable focused-unit gate: explicit reviewed manifest, never arbitrary commands."""
from pathlib import Path
import argparse, ast, hashlib, importlib.util, json, math, re, sys, time

COMMON, PARENT, CHILD, FINAL, ROOT_CLOSE = 600, 300, 240, 60, 30
MINIMUM_REMAINING = 390
HELPERS = {
    'coordinator': '43be86ece6c453641afdcc6f8eccef02d713986e2ac8bf3314756f0bb78e0818',
    'owner': '8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8',
    'processes': 'fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d',
    'lock': '78a0441bb3b9ea60197e9a1a6e1087f6e4cd0886593ec54bcfc4e41c9abe5a45',
    'awake': '9a0bae0acb6ddb37e638420c52ad1e587a9180fbd7ef68ebc6e1a3c43e4bfc9b'}
sys.dont_write_bytecode = True


def need(value, code):
    if not value:
        raise RuntimeError(code)


def read(path):
    return json.loads(Path(path).read_text('utf-8'))


def digest(path, pulse=lambda: None):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            pulse(); block = stream.read(2**20)
            if not block:
                break
            h.update(block)
    pulse(); return h.hexdigest()


def imported(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def suite_names(cfg):
    return tuple(s['id'] for s in cfg['suites'])


def frozen(cfg, pulse=lambda: None):
    for path, expected in cfg['files_sha256'].items():
        need(digest(path,pulse)==expected,'frozen_source_changed')
    root=Path(cfg['canonical_root'])
    actual={str(p.resolve()) for p in (root/'src').rglob('*.py')}
    need(actual==set(cfg['source_inventory']),'canonical_source_inventory_changed')
    for suite in cfg['suites']:
        tree=ast.parse(Path(suite['test']).read_bytes())
        names=[n.name for c in tree.body if isinstance(c,ast.ClassDef) for n in c.body
               if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')]
        need(len(names)==len(set(names))==suite['expected_tests'] and names==suite['test_methods'],
             'exact_unique_focused_test_methods_required')
        pulse()


def config(path, expected_sha, self_sha, pulse=lambda: None):
    need(Path(path).is_absolute(),'absolute_manifest_required')
    need(Path(path).stat().st_size<=2**20,'private_manifest_bytes_bound')
    need(digest(path,pulse)==expected_sha,'private_manifest_changed');cfg=read(path)
    need(type(cfg) is dict,'typed_private_manifest_required')
    need(cfg.get('schema')=='uar-focused-private-manifest-v1'
         and cfg.get('readiness')=='READY_FROZEN_SOURCE_REVIEWED'
         and not cfg.get('missing_bindings'),'NOT_READY_missing_frozen_source_review_bindings')
    need(cfg.get('common_seconds')==COMMON,'exact_common600_required')
    need(all(type(cfg.get(k)) is str and Path(cfg[k]).is_absolute()
             for k in ('canonical_root','work_root','python','output','suite_entry','lock_path')),
         'all_forwarded_paths_must_be_explicit_absolute_paths')
    need(type(cfg.get('files_sha256')) is dict and 1<=len(cfg['files_sha256'])<=4096
         and all(type(k) is str and Path(k).is_absolute() and type(v) is str
                 and re.fullmatch('[0-9a-f]{64}',v) for k,v in cfg['files_sha256'].items()),
         'bounded_absolute_source_hash_inventory_required')
    root=Path(cfg['canonical_root']);work=Path(cfg['work_root'])
    need(root.is_absolute() and work.is_absolute() and root.resolve()==(work/'alfa-hack-automl').resolve(),
         'canonical_source_root_required')
    need(Path(cfg['lock_path']).resolve()==(root/'test-runs/.owned-research.lock').resolve(),
         'canonical_single_training_slot_lock_required')
    need(type(cfg.get('source_inventory')) is list and 1<=len(cfg['source_inventory'])<=4096
         and len(set(cfg['source_inventory']))==len(cfg['source_inventory'])
         and all(type(v) is str and Path(v).is_absolute()
                 and Path(v).is_relative_to(root/'src') and v in cfg['files_sha256']
                 for v in cfg['source_inventory']),'exact_canonical_source_inventory_required')
    need(type(cfg['suites']) is list and 1<=len(cfg['suites'])<=8,'bounded_explicit_suites_required')
    need(type(cfg['reviewed_test_whitelist']) is dict,'source_reviewed_test_whitelist_required')
    ids=[];paths=[];total=0
    for suite in cfg['suites']:
        need(type(suite) is dict and set(suite)=={'id','root','test','test_relative_path','expected_tests','test_methods'},
             'typed_suite_no_arbitrary_command_fields')
        need(type(suite['id']) is str and re.fullmatch('[a-z][a-z0-9_]{0,31}',suite['id']), 'typed_suite_id')
        rel=suite['test_relative_path']
        need(type(rel) is str and re.fullmatch(r'tests/test_uar_[a-z0-9_]+\.py',rel), 'canonical_unit_test_path_required')
        test=root/rel;need(Path(suite['test']).is_absolute() and Path(suite['root']).is_absolute()
            and Path(suite['root']).resolve()==root.resolve()
            and Path(suite['test']).resolve()==test.resolve() and not test.is_symlink(),'exact_canonical_test_location')
        need(type(suite['expected_tests']) is int and 1<=suite['expected_tests']<=256
            and type(suite['test_methods']) is list and all(type(n) is str for n in suite['test_methods']),
            'typed_expected_test_methods_required')
        white=cfg['reviewed_test_whitelist'].get(rel)
        need(type(white) is dict and set(white)=={'test_sha256','method_list_sha256','source_review_ref'},
             'explicit_source_review_whitelist_binding')
        methodsha=hashlib.sha256(json.dumps(suite['test_methods'],separators=(',',':')).encode()).hexdigest()
        need(cfg['files_sha256'].get(str(test.resolve()))==white['test_sha256']
            and white['method_list_sha256']==methodsha,'test_hash_and_methods_must_match_reviewed_whitelist')
        review=white['source_review_ref']
        need(type(review) is dict and set(review)=={'path','sha256'} and Path(review['path']).is_absolute()
            and cfg['files_sha256'].get(review['path'])==review['sha256'],'actual_source_review_receipt_required')
        ids.append(suite['id'].casefold());paths.append(rel.casefold());total+=suite['expected_tests']
    need(len(ids)==len(set(ids)) and len(paths)==len(set(paths)) and 1<=total<=256
         and type(cfg['expected_tests']) is int and cfg['expected_tests']==total,
         'unique_explicit_suite_paths_and_exact_total_required')
    need(set(cfg['reviewed_test_whitelist'])==set(s['test_relative_path'] for s in cfg['suites']),
         'whitelist_must_exactly_match_declared_suites')
    need(cfg['files_sha256'].get(str(Path(__file__).resolve()))==self_sha
         and digest(__file__,pulse)==self_sha,'driver_source_binding')
    need(Path(cfg['output']).is_absolute() and Path(cfg['output']).parent.resolve()==Path(__file__).resolve().parent,
         'exclusive_output_within_own_packet')
    need(Path(cfg['suite_entry']).resolve()==Path(__file__).with_name('suite_entry.py').resolve()
         and Path(cfg['suite_entry']).is_absolute() and cfg['files_sha256'].get(cfg['suite_entry']),
         'reviewed_serial_entry_must_be_pinned')
    need(cfg['files_sha256'].get(str((root/'src/automl/infrastructure/processes.py').resolve()))==
         cfg['candidate_process_sha256'] and cfg['candidate_process_sha256']!=HELPERS['processes'],
         'candidate_infrastructure_separate_from_historical_guard')
    for name,expected in HELPERS.items():
        ref=cfg['helpers'][name]
        need(Path(ref['path']).is_absolute() and ref['sha256']==expected
            and cfg['files_sha256'].get(ref['path'])==expected,'proven_guard_dependency_changed')
    history=cfg.get('historical_failure_evidence',[])
    need(type(history) is list and any(ref.get('sha256')==
         '87f691b5774ed6f604069d952041bdd6af6a6022f9ea1268ac77a8364180a106' for ref in history),
         'original_unqualified_UAR02_history_must_be_preserved')
    for ref in history:
        need(type(ref) is dict and set(ref)=={'path','sha256','scope'}
             and ref['scope']=='immutable_evidence_only_not_owned_grant'
             and Path(ref['path']).is_absolute()
             and cfg['files_sha256'].get(ref['path'])==ref['sha256'],'historical_failure_evidence_changed')
    frozen(cfg,pulse);return cfg


def source_union(cfg, coor, pulse=lambda: None):
    known=set()
    need({r['id'] for r in cfg['predecessors']} >=
         {'la2','postfailure_audit','uar00','uar01_failed','uar01_recovery','uar02_recovery'},
         'all_actual_predecessor_roots_required')
    need(len({r['id'] for r in cfg['predecessors']})==len(cfg['predecessors']),
         'duplicate_predecessor_id')
    for ref in cfg['predecessors']:
        need(digest(ref['path'],pulse)==ref['sha256'], 'predecessor_root_changed')
        proof=read(ref['path'])
        need(proof.get('cleanup_confirmed') is True and proof.get('source_unchanged') is True
             and proof.get('active_owned_processes')==[] and not proof.get('uncertain_owned'),
             'predecessor_cleanup_or_source_unknown')
        need(type(proof.get('actual_exec_exit_code_observed_by_root')) is int
             and proof['actual_exec_exit_code_observed_by_root']==ref['actual_exit_code']
             and proof.get('actual_exec_session')==ref['actual_exec_session']
             and proof.get('actual_tool_evidence')==ref['actual_tool_evidence'],
             'predecessor_actual_root_exit_binding')
        known |= coor.identities(proof['owned_identities']+proof['closure_preparer_identities'])
    return known


def absence(owner, known):
    ob=owner.StrictOwnedObserver(); ob.remember(known)
    need(not ob.observe() and not ob.denials and not ob.final_check()['unresolved'],
         'known_owned_or_preparer_live_or_denied')


def own_bootstraps(psutil):
    me=psutil.Process(); result=[]; parent=me.parent()
    while parent is not None:
        created=parent.create_time()
        if not any(Path(v).resolve()==Path(__file__).resolve()
                   for v in parent.cmdline() if v and not v.startswith('-')):
            break
        need(parent.create_time()==created, 'bootstrap_identity_changed')
        result.append(dict(pid=parent.pid,create_time=created)); parent=parent.parent()
    return dict(pid=me.pid,create_time=me.create_time()),result


def leaf_cleanup_status(cfg, out, entry_started):
    """Saved uncertainty is sticky even if currently known PIDs are absent."""
    path=out/'focused-results.json'; uncertain=[]
    if not path.exists():
        if entry_started:
            uncertain.append(dict(action='leaf_cleanup_receipts',reason='missing_after_entry_started'))
        return not uncertain,uncertain
    try:
        rows=read(path)['suites']
        need(type(rows) is list and len(rows)<=len(cfg['suites']),'malformed_leaf_receipts')
        for index,row in enumerate(rows):
            need(type(row) is dict and row.get('id')==suite_names(cfg)[index],'malformed_leaf_receipt_order')
            obs=row.get('cleanup_observation')
            if type(obs) is not dict:
                uncertain.append(dict(suite=row['id'],action='leaf_cleanup_receipt',reason='observation_missing'))
                continue
            unresolved=obs.get('unresolved')
            if type(unresolved) is not list:
                uncertain.append(dict(suite=row['id'],action='leaf_cleanup_receipt',reason='unresolved_missing'))
            else:
                for item in unresolved:
                    uncertain.append(dict(suite=row['id'],action='saved_leaf_cleanup_uncertainty',receipt=item))
            if row.get('cleanup_confirmed') is not True or obs.get('denial_count')!=0:
                uncertain.append(dict(suite=row['id'],action='leaf_cleanup_receipt',reason='unconfirmed_or_denied',
                    owned_root=row.get('owned_root')))
    except (OSError,ValueError,KeyError,RuntimeError,TypeError,IndexError) as exc:
        uncertain.append(dict(action='leaf_cleanup_receipts',reason='malformed_or_unreadable',error_type=type(exc).__name__))
    return not uncertain,uncertain


def focused_results(cfg, out, pulse=lambda: None):
    path=out/'focused-results.json'; raw=read(path); artifacts={str(path):digest(path,pulse)}
    need(raw.get('schema')=='uar02-focused-results-v1' and raw.get('status')=='passed'
         and raw.get('checks_observed')==cfg['expected_tests'] and not raw.get('first_failure')
         and raw.get('model_fits')==raw.get('API_calls')==0,
         'focused_results_not_all_passed')
    need(tuple(r['id'] for r in raw['suites'])==suite_names(cfg), 'focused_result_order')
    for row,suite in zip(raw['suites'],cfg['suites']):
        log=out/(suite['id']+'.log'); text=log.read_text('utf-8',errors='replace')
        artifacts[str(log)]=digest(log,pulse)
        need(row.get('status')=='passed' and row.get('passed') is True and row.get('exit_code')==0
             and row.get('checks_observed')==row.get('expected_tests')==suite['expected_tests']
             and row.get('no_skips') is True and row.get('owned_root')
             and row.get('cleanup_confirmed') is True
             and row.get('cleanup_observation',{}).get('unresolved')==[]
             and row.get('cleanup_observation',{}).get('denial_count')==0
             and row.get('log_sha256')==artifacts[str(log)]
             and re.findall(r'Ran (\d+) tests?',text)==[str(suite['expected_tests'])]
             and re.search(r'\bskip(?:ped)?\b',text,re.I) is None
             and re.search(r'\nOK\s*$',text) is not None, 'focused_log_counts_or_exit_failed')
    return raw,artifacts


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--launch',action='store_true',required=True)
    p.add_argument('--private-manifest',required=True)
    p.add_argument('--private-manifest-sha256',required=True)
    p.add_argument('--self-sha256',required=True)
    p.add_argument('--latest-root-closure-sha256',required=True)
    a=p.parse_args(); start,mono=time.time(),time.monotonic(); unix,end=start+COMMON,mono+COMMON
    a.private_manifest=str(Path(a.private_manifest).resolve())
    final_end=None
    def clock():
        need(time.time()<unix and time.monotonic()<end, 'original600_deadline_exhausted')
        if final_end is not None:need(time.monotonic()<final_end,'actual_final60_cap_exhausted')
        need(abs((unix-time.time())-(end-time.monotonic()))<=5, 'clock_disagreement')
    cfg=config(a.private_manifest,a.private_manifest_sha256,a.self_sha256,clock)
    refs={r['id']:r for r in cfg['predecessors']}
    need(cfg['latest_predecessor_id'] in refs and refs[cfg['latest_predecessor_id']]['sha256']==a.latest_root_closure_sha256,
         'explicit_actual_latest_root_closure_pin_required')
    need(__debug__ and Path(cfg['python']).resolve()==Path(sys.executable).resolve(),
         'nonoptimized_pinned_interpreter_required')
    modules={n:imported('_uar02_'+n,cfg['helpers'][n]['path']) for n in HELPERS}
    coor,owner,proc=(modules[n] for n in ('coordinator','owner','processes'))
    need(coor.WORK.resolve()==Path(cfg['work_root']).resolve(), 'proven_work_root_mismatch')
    import psutil
    known=source_union(cfg,coor,clock); absence(owner,known)
    out=Path(cfg['output']); need(not out.exists(), 'exclusive_attempt_no_retry_or_reset')
    need(unix-time.time()>=MINIMUM_REMAINING and end-time.monotonic()>=MINIMUM_REMAINING,'mandatory_remaining390_unavailable')
    need(time.monotonic()<mono+PARENT-CHILD, 'preflight_consumed_full_child_admission')
    out.mkdir(); root,boot=own_bootstraps(psutil)
    state=dict(schema='uar-focused-campaign-v1',status='starting',start_unix=start,start_monotonic=mono,
        absolute_deadline_unix=unix,common_deadline_monotonic=end,common_seconds=COMMON,
        private_manifest_sha256=a.private_manifest_sha256,owned_root=root,
        coordinator_bootstrap_identities=boot,supervisors=[],active_supervisor=None,error_history=[],
        cleanup_confirmed=False,source_unchanged=False,model_fits=0,API_calls=0,quality_metric=None,
        root_actual_exec_confirmation_pending=True,known_predecessor_count=len(known),
        suites=[dict(id=s['id'],status='not_attempted',checks_observed=None) for s in cfg['suites']],_manifest={})
    children=set(); suite_ob=owner.StrictOwnedObserver(); awake=None
    def persist():
        coor.save(out/'campaign.json',{k:v for k,v in state.items() if not k.startswith('_')})
    def pulse():
        coor.cooperative_checkpoint(awake,end,unix)
        if final_end is not None:need(time.monotonic()<final_end,'actual_final60_cap_exhausted')
        active=state.get('active_supervisor')
        if active:
            record=read(Path(cfg['work_root'])/active)
            if record.get('owned_root'):suite_ob.remember(coor.identities([record['owned_root']]))
            live=suite_ob.observe(); need(not suite_ob.denials,'suite_observation_denied'); rss=0
            for identity,obj in live.items():
                try:
                    need(obj.create_time()==identity[1],'suite_identity_changed'); rss+=obj.memory_info().rss
                except psutil.NoSuchProcess:pass
            children.update(suite_ob.seen); need(rss<=1536*2**20,'suite_subtree_memory_limit')
            state['peak_suite_tree_rss_mib']=max(state.get('peak_suite_tree_rss_mib',0.),rss/2**20)
    def guard(parent_end=None,code='parent_cap_exhausted'):
        coor.cooperative_checkpoint(awake,end,unix,parent_end,code)
        need(digest(a.private_manifest,pulse)==a.private_manifest_sha256,'private_manifest_changed')
        frozen(cfg,pulse)
    state['_pulse']=pulse
    try:
        with modules['awake'].PowerRequestGuard('Explicit serial focused no-fit contracts',10) as awake:
            with modules['lock'].ResearchLock(cfg['lock_path']) as lease:
                lease.write_identity(root); absence(owner,known); persist(); guard()
                child_end=min(mono+PARENT,time.monotonic()+CHILD)
                command=[cfg['python'],'-B','-X','utf8',cfg['suite_entry'],
                    '--private-manifest',a.private_manifest,'--private-manifest-sha256',a.private_manifest_sha256,
                    '--deadline-monotonic',str(child_end),'--deadline-unix',str(start+child_end-mono)]
                sup=coor.supervise(command,Path(cfg['work_root']),out/'focused.json','focused',
                    mono,PARENT,CHILD,end,unix,MINIMUM_REMAINING,state,persist,guard,owner,proc,boot)
                final_start=time.monotonic();final_end=min(final_start+FINAL,end-ROOT_CLOSE)
                state.update(final_start_monotonic=final_start,final_deadline_monotonic=final_end)
                coor.child_errors(state,sup)
                children |= coor.identities(sup.get('owned_process_identities',[]))
                if sup.get('owned_root'):children |= coor.identities([sup['owned_root']])
                # Keep the entry's own failure detail even when supervisor exit is already nonzero.
                if (out/'focused-results.json').exists():
                    detail=read(out/'focused-results.json');state['focused_raw_first_failure']=detail.get('first_failure')
                    for row in detail.get('suites',[]):
                        if row.get('owned_root'):children |= coor.identities([row['owned_root']])
                        children |= coor.identities(row.get('owned_process_identities',[]))
                persist(); absence(owner,known|children)
                need(sup['status']=='ok' and sup['exit_code']==0 and sup['cleanup_confirmed'] is True
                     and not sup.get('error_history'),'mandatory_focused_child_failed')
                detail,artifacts=focused_results(cfg,out,pulse)
                state['suites']=detail['suites'];state['focused_artifacts']=artifacts
                guard(); absence(owner,known|children)
                state.update(status='tests_completed_pending_root',checks_observed=cfg['expected_tests'],
                    suite_procedure_passed=True,cleanup_confirmed=True,source_unchanged=True)
                persist(); guard()
        state['awake_guard']=awake.record
        need(awake.record.get('release_API_verified') is True,'power_request_cleanup_unconfirmed')
    except BaseException as exc:
        coor.error(state,str(exc) if isinstance(exc,RuntimeError) else 'queue_operation_failed','queue',exc)
        state.update(status='technical_failure',suite_procedure_passed=False)
    finally:
        if final_end is None:
            final_start=time.monotonic();final_end=min(final_start+FINAL,mono+PARENT+FINAL,end-ROOT_CLOSE)
            state.update(final_start_monotonic=final_start,final_deadline_monotonic=final_end)
        if awake is not None:state['awake_guard']=awake.record
        state['owned_process_identities']=[dict(pid=p,create_time=b) for p,b in sorted(children)]
        state['cleanup_confirmed']=False;state['source_unchanged']=False
        try:
            entry_record=read(out/'focused.json') if (out/'focused.json').exists() else {}
            leaf_ok,leaf_uncertain=leaf_cleanup_status(cfg,out,bool(entry_record.get('owned_root')))
            state.update(leaf_cleanup_confirmed=leaf_ok,leaf_cleanup_uncertainty=leaf_uncertain)
            absence(owner,known|children)
            need(state.get('active_supervisor') is None and all(r.get('cleanup_confirmed') is True
                 for r in state['supervisors']),'saved_supervisor_cleanup_unconfirmed')
            need(leaf_ok,'saved_leaf_cleanup_unconfirmed')
            state['cleanup_confirmed']=True
        except BaseException as exc:
            coor.error(state,'final_owned_cleanup_unconfirmed','final_cleanup',exc)
            state.update(status='technical_failure',suite_procedure_passed=False)
        try:
            frozen(cfg,clock);need(digest(a.private_manifest,clock)==a.private_manifest_sha256,'private_manifest_changed')
            state['source_unchanged']=True
            need(time.monotonic()<final_end,'final_or_root_reserve_exhausted')
        except BaseException as exc:
            coor.error(state,str(exc) if isinstance(exc,RuntimeError) else 'final_guard_failed','final',exc)
            state.update(status='technical_failure',suite_procedure_passed=False)
        state.update(finished_unix=time.time(),finished_monotonic=time.monotonic(),
                     elapsed_common_seconds=time.monotonic()-mono)
        persist()
        if time.time()>=unix or time.monotonic()>=final_end:
            coor.error(state,'terminal_save_exhausted_original_or_root_reserve','terminal_save')
            state.update(status='technical_failure',suite_procedure_passed=False);persist()
    passed=state.get('suite_procedure_passed') is True and not state['error_history'] and state['cleanup_confirmed'] and state['source_unchanged']
    print(json.dumps({k:state.get(k) for k in ('status','checks_observed','suite_procedure_passed',
        'cleanup_confirmed','source_unchanged','elapsed_common_seconds')},allow_nan=False))
    return 0 if passed else 1


if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as exc:
        print(json.dumps(dict(status='blocked_before_or_during_queue',error_type=type(exc).__name__,
            error_code=str(exc) if re.fullmatch('[A-Za-z0-9_]+',str(exc)) else 'preflight_operation_failed',
            model_fits=0,API_calls=0)))
        raise SystemExit(1)
