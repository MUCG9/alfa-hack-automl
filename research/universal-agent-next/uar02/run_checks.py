"""UAR02: one fresh600s serial focused unit gate; source prepared, not launched."""
from pathlib import Path
import argparse, ast, hashlib, importlib.util, json, math, re, sys, time

COMMON, PARENT, CHILD, FINAL, ROOT_CLOSE = 600, 500, 450, 70, 30
HELPERS = {
    'coordinator': '43be86ece6c453641afdcc6f8eccef02d713986e2ac8bf3314756f0bb78e0818',
    'owner': '8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8',
    'processes': 'fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d',
    'lock': '78a0441bb3b9ea60197e9a1a6e1087f6e4cd0886593ec54bcfc4e41c9abe5a45',
    'awake': '9a0bae0acb6ddb37e638420c52ad1e587a9180fbd7ef68ebc6e1a3c43e4bfc9b'}
SUITES = ('io02', 'run02')
EXPECTED = (15, 14)
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


def frozen(cfg, pulse=lambda: None):
    for path, expected in cfg['files_sha256'].items():
        need(digest(path, pulse)==expected, 'frozen_source_changed')
    for suite in cfg['suites']:
        actual = {str(p.resolve()) for p in (Path(suite['root'])/'src').rglob('*.py')}
        need(actual==set(suite['source_inventory']), 'suite_source_inventory_changed')
        tree = ast.parse(Path(suite['test']).read_bytes())
        names = [n.name for c in tree.body if isinstance(c, ast.ClassDef) for n in c.body
                 if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')]
        need(len(names)==len(set(names))==suite['expected_tests'] and names==suite['test_methods'],
             'exact_unique_focused_test_methods_required')
        pulse()


def config(path, expected_sha, self_sha, pulse=lambda: None):
    need(digest(path,pulse)==expected_sha, 'private_manifest_changed'); cfg=read(path)
    need(cfg['schema']=='uar02-private-manifest-v1' and cfg['common_seconds']==COMMON
         and cfg['expected_tests']==29, 'exact_uar02_contract_required')
    need(tuple(s['id'] for s in cfg['suites'])==SUITES
         and tuple(s['expected_tests'] for s in cfg['suites'])==EXPECTED, 'exact_two_suite_order')
    need(cfg['files_sha256'].get(str(Path(__file__).resolve()))==self_sha
         and digest(__file__,pulse)==self_sha, 'driver_source_binding')
    need(Path(cfg['output']).parent.resolve()==Path(__file__).resolve().parent,
         'exclusive_output_within_own_packet')
    for name, expected in HELPERS.items():
        ref=cfg['helpers'][name]
        need(ref['sha256']==expected and cfg['files_sha256'].get(ref['path'])==expected,
             'proven_guard_dependency_changed')
    need(cfg['files_sha256'].get(cfg['suite_entry']), 'serial_entry_not_pinned')
    frozen(cfg,pulse); return cfg


def source_union(cfg, coor, pulse=lambda: None):
    known=set()
    need({r['id'] for r in cfg['predecessors']} >=
         {'la2','postfailure_audit','uar00','uar01_failed','uar01_recovery'},
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


def leaf_cleanup_status(out, entry_started):
    """Saved uncertainty is sticky even if currently known PIDs are absent."""
    path=out/'focused-results.json'; uncertain=[]
    if not path.exists():
        if entry_started:
            uncertain.append(dict(action='leaf_cleanup_receipts',reason='missing_after_entry_started'))
        return not uncertain,uncertain
    try:
        rows=read(path)['suites']
        need(type(rows) is list and len(rows)<=2,'malformed_leaf_receipts')
        for index,row in enumerate(rows):
            need(type(row) is dict and row.get('id')==SUITES[index],'malformed_leaf_receipt_order')
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
         and raw.get('checks_observed')==29 and not raw.get('first_failure')
         and raw.get('model_fits')==raw.get('API_calls')==0,
         'focused_results_not_all_passed')
    need(tuple(r['id'] for r in raw['suites'])==SUITES, 'focused_result_order')
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
    p.add_argument('--la2-closure-sha256',required=True)
    p.add_argument('--uar01r2-closure-sha256',required=True)
    a=p.parse_args(); start,mono=time.time(),time.monotonic(); unix,end=start+COMMON,mono+COMMON
    final_end=None
    def clock():
        need(time.time()<unix and time.monotonic()<end, 'original600_deadline_exhausted')
        if final_end is not None:need(time.monotonic()<final_end,'actual_final70_cap_exhausted')
        need(abs((unix-time.time())-(end-time.monotonic()))<=5, 'clock_disagreement')
    cfg=config(a.private_manifest,a.private_manifest_sha256,a.self_sha256,clock)
    refs={r['id']:r for r in cfg['predecessors']}
    need(refs['la2']['sha256']==a.la2_closure_sha256
         and refs['uar01_recovery']['sha256']==a.uar01r2_closure_sha256,
         'explicit_actual_LA2_and_recovery_closure_pins_required')
    need(__debug__ and Path(cfg['python']).resolve()==Path(sys.executable).resolve(),
         'nonoptimized_pinned_interpreter_required')
    modules={n:imported('_uar02_'+n,cfg['helpers'][n]['path']) for n in HELPERS}
    coor,owner,proc=(modules[n] for n in ('coordinator','owner','processes'))
    need(coor.WORK.resolve()==Path(cfg['work_root']).resolve(), 'proven_work_root_mismatch')
    import psutil
    known=source_union(cfg,coor,clock); absence(owner,known)
    out=Path(cfg['output']); need(not out.exists(), 'exclusive_attempt_no_retry_or_reset')
    need(time.monotonic()<mono+PARENT-CHILD, 'preflight_consumed_full_child_admission')
    out.mkdir(); root,boot=own_bootstraps(psutil)
    state=dict(schema='uar02-campaign-v1',status='starting',start_unix=start,start_monotonic=mono,
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
        if final_end is not None:need(time.monotonic()<final_end,'actual_final70_cap_exhausted')
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
        with modules['awake'].PowerRequestGuard('UAR02 serial focused no-fit contracts',10) as awake:
            with modules['lock'].ResearchLock(cfg['lock_path']) as lease:
                lease.write_identity(root); absence(owner,known); persist(); guard()
                child_end=min(mono+PARENT,time.monotonic()+CHILD)
                command=[cfg['python'],'-B','-X','utf8',cfg['suite_entry'],
                    '--private-manifest',a.private_manifest,'--private-manifest-sha256',a.private_manifest_sha256,
                    '--deadline-monotonic',str(child_end),'--deadline-unix',str(start+child_end-mono)]
                sup=coor.supervise(command,Path(cfg['work_root']),out/'focused.json','focused',
                    mono,PARENT,CHILD,end,unix,COMMON,state,persist,guard,owner,proc,boot)
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
                state.update(status='tests_completed_pending_root',checks_observed=29,
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
            leaf_ok,leaf_uncertain=leaf_cleanup_status(out,bool(entry_record.get('owned_root')))
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
    except (OSError,ValueError,RuntimeError,KeyError) as exc:
        print(json.dumps(dict(status='blocked_before_or_during_queue',error_type=type(exc).__name__,
            error_code=str(exc) if re.fullmatch('[A-Za-z0-9_]+',str(exc)) else 'preflight_operation_failed',
            model_fits=0,API_calls=0)))
        raise SystemExit(1)
