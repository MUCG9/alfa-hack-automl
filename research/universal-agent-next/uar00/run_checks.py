"""UAR00: one prospective600s serial no-fit queue; launch only after LA2 closure.

All machine paths live in the private manifest. This imports proven supervision
only after hashing it; suites are child commands, never imported by this module.
"""
from pathlib import Path
import argparse, ast, hashlib, importlib.util, json, math, os, re, sys, time

COMMON, PARENT, CHILD, FINAL, ROOT_CLOSE = 600, 100, 75, 140, 30
HELPERS = {
    'coordinator': '43be86ece6c453641afdcc6f8eccef02d713986e2ac8bf3314756f0bb78e0818',
    'owner': '8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8',
    'processes': 'fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d',
    'lock': '78a0441bb3b9ea60197e9a1a6e1087f6e4cd0886593ec54bcfc4e41c9abe5a45',
    'awake': '9a0bae0acb6ddb37e638420c52ad1e587a9180fbd7ef68ebc6e1a3c43e4bfc9b'}
SUITES = ('contracts', 'models', 'evaluation', 'metrics')
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
            pulse()
            chunk = stream.read(2**20)
            if not chunk:
                break
            h.update(chunk)
    pulse()
    return h.hexdigest()


def imported(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frozen(cfg, pulse=lambda: None):
    for path, expected in cfg['files_sha256'].items():
        need(digest(path, pulse) == expected, 'frozen_source_changed')
    for suite in cfg['suites']:
        root = Path(suite['root'])
        actual = {str(p.resolve()) for p in (root/'src').rglob('*.py')}
        need(actual == set(suite['source_inventory']), 'suite_source_inventory_changed')
        tree = ast.parse(Path(suite['test']).read_bytes())
        names = [n.name for c in tree.body if isinstance(c, ast.ClassDef)
                 for n in c.body if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')]
        need(len(names) == len(set(names)) == 12 and names == suite['test_methods'],
             'exact_unique12_test_methods_required')
    pulse()
    for ref in cfg.get('extra_terminal_receipts', []):
        need(digest(ref['path'], pulse) == ref['sha256'], 'extra_terminal_receipt_changed')


def config(path, expected_sha, self_sha, pulse=lambda: None):
    need(digest(path, pulse) == expected_sha, 'private_manifest_changed')
    cfg = read(path)
    need(cfg['schema'] == 'uar00-private-manifest-v1', 'private_manifest_schema')
    need(tuple(s['id'] for s in cfg['suites']) == SUITES, 'exact_four_suite_order')
    need(cfg['common_seconds'] == COMMON and cfg['expected_tests'] == 48, 'declared600_48_required')
    need(cfg['files_sha256'].get(str(Path(__file__).resolve())) == self_sha,
         'driver_binding_missing')
    need(digest(__file__, pulse) == self_sha, 'driver_changed')
    need(Path(cfg['output']).parent.resolve() == Path(__file__).resolve().parent,
         'output_must_stay_in_own_packet')
    for name, expected in HELPERS.items():
        ref = cfg['helpers'][name]
        need(ref['sha256'] == expected and cfg['files_sha256'].get(ref['path']) == expected,
             'proven_guard_dependency_changed')
    frozen(cfg, pulse)
    return cfg


def bind_extra(cfg, values):
    refs = {}
    for value in values:
        name, sep, expected = value.partition('=')
        need(sep and name not in refs and re.fullmatch('[0-9a-f]{64}', expected),
             'typed_unique_extra_closure_binding_required')
        refs[name] = expected
    need(set(refs) == set(cfg['extra_closures']) and 'postfailure_audit' in refs,
         'all_future_extra_closures_required')
    cfg['extra_terminal_receipts'] = []
    for name, expected in refs.items():
        path = cfg['extra_closures'][name]
        need(type(path) is str and Path(path).is_file(), 'future_extra_root_closure_not_bound')
        cfg['extra_terminal_receipts'].append(dict(id=name, path=path, sha256=expected))


def source_union(cfg, closure, coor, pulse):
    """Only explicit owned fields; never recursively adopt analytical PID edges."""
    proof = read(closure)
    need(proof.get('cleanup_confirmed') is True and proof.get('source_unchanged') is True
         and proof.get('active_owned_processes') == [] and not proof.get('uncertain_owned'),
         'LA2_terminal_cleanup_or_source_unknown')
    granted = coor.identities(proof['owned_identities'] + proof['closure_preparer_identities'])
    c = read(cfg['la2_campaign'])
    need(c.get('finished_unix') is not None and c.get('finished_monotonic') is not None
         and c.get('active_supervisor') is None, 'LA2_parent_not_terminal')
    need(proof['original_common_seconds'] == c['common_seconds'] == 10800
         and proof['original_start_unix'] == c['start_unix']
         and proof['original_deadline_unix'] == c['absolute_deadline_unix'], 'LA2_original_clock_binding')
    known = coor.identities([c['owned_root']] + c.get('coordinator_bootstrap_identities', [])
                           + c.get('owned_process_identities', []))
    work = Path(cfg['work_root'])
    for ref in c.get('supervisors', []):
        p = work/ref['path']; need(digest(p, pulse) == ref['sha256'], 'LA2_supervisor_changed')
        sup = read(p)
        known |= coor.identities(sup.get('owned_process_identities', []) + sup.get('observed_worker_roots', []))
        if sup.get('owned_root'):
            known |= coor.identities([sup['owned_root']])
    p = Path(cfg['la2_manifest'])
    need(digest(p, pulse) == c['manifest_sha256'], 'LA2_manifest_binding')
    manifest = read(p)
    for name, expected in manifest['immutable_files'].items():
        if name.endswith('.json') and ('terminal-root-closure' in Path(name).name
                or name == manifest['stage0_root_closure']['path']):
            p = work/name; need(digest(p, pulse) == expected, 'LA2_prior_proof_changed')
            prior = read(p)
            if 'owned_identities' in prior and 'closure_preparer_identities' in prior:
                need(prior['cleanup_confirmed'] is True and prior['source_unchanged'] is True,
                     'LA2_prior_proof_not_clean')
                known |= coor.identities(prior['owned_identities'] + prior['closure_preparer_identities'])
    need(known <= granted, 'LA2_root_closure_missing_prior_or_supervisor_union')
    for ref in cfg.get('extra_terminal_receipts', []):
        need(digest(ref['path'], pulse) == ref['sha256'], 'extra_terminal_receipt_changed')
        extra = read(ref['path'])
        need(extra.get('cleanup_confirmed') is True and extra.get('source_unchanged') is True
             and extra.get('active_owned_processes') == [] and not extra.get('uncertain_owned')
             and type(extra.get('actual_exec_exit_code_observed_by_root')) is int,
             'extra_terminal_root_exit_or_cleanup_unknown')
        granted |= coor.identities(extra['owned_identities'] + extra['closure_preparer_identities'])
    return granted, proof


def absence(owner, known):
    ob = owner.StrictOwnedObserver(); ob.remember(known)
    need(not ob.observe() and not ob.denials and not ob.final_check()['unresolved'],
         'known_owned_or_preparer_live_or_denied')


def own_bootstraps(psutil):
    me = psutil.Process(); result = []; parent = me.parent()
    while parent is not None:
        created = parent.create_time()
        if not any(Path(v).resolve() == Path(__file__).resolve()
                   for v in parent.cmdline() if v and not v.startswith('-')):
            break
        need(parent.create_time() == created, 'bootstrap_identity_changed')
        result.append(dict(pid=parent.pid, create_time=created)); parent = parent.parent()
    return dict(pid=me.pid, create_time=me.create_time()), result


def log_counts(path, expected=12):
    text = Path(path).read_text('utf-8', errors='replace')
    counts = re.findall(r'Ran (\d+) tests?', text)
    no_skip = re.search(r'\bskip(?:ped)?\b', text, re.I) is None
    return dict(checks_observed=int(counts[0]) if len(counts) == 1 else None,
                no_skips=no_skip, log_passed=counts == [str(expected)] and no_skip
                and re.search(r'\nOK\s*$', text) is not None)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--launch', action='store_true', required=True)
    p.add_argument('--private-manifest', required=True)
    p.add_argument('--private-manifest-sha256', required=True)
    p.add_argument('--self-sha256', required=True)
    p.add_argument('--la2-closure-sha256', required=True)
    p.add_argument('--la2-actual-exec-session', type=int, default=None)
    p.add_argument('--la2-actual-exit-code', type=int, required=True)
    p.add_argument('--la2-actual-tool-evidence', required=True)
    p.add_argument('--extra-closure', action='append', required=True,
                   help='Private-manifest closure ID=actual SHA; no machine path in argv')
    a = p.parse_args()
    start, mono = time.time(), time.monotonic(); unix, end = start+COMMON, mono+COMMON
    def clock():
        need(time.time() < unix and time.monotonic() < end, 'original600_deadline_exhausted')
        need(abs((unix-time.time())-(end-time.monotonic())) <= 5, 'clock_disagreement')
    cfg = config(a.private_manifest, a.private_manifest_sha256, a.self_sha256, clock)
    bind_extra(cfg, a.extra_closure)
    need(Path(cfg['python']).resolve() == Path(sys.executable).resolve(), 'pinned_interpreter_required')
    need(__debug__ and a.la2_actual_exit_code in (0, 1) and a.la2_actual_tool_evidence.strip(),
         'root_actual_LA2_exit_evidence_required')
    closure = Path(cfg['la2_closure'])
    need(a.la2_closure_sha256 == cfg['known_la2_closure_sha256_from_root'],
         'root_declared_LA2_proof_required')
    need(digest(closure, clock) == a.la2_closure_sha256, 'LA2_root_closure_changed')
    modules = {n: imported('_uar00_'+n, cfg['helpers'][n]['path']) for n in HELPERS}
    coor, owner, proc = (modules[n] for n in ('coordinator', 'owner', 'processes'))
    need(coor.WORK.resolve() == Path(cfg['work_root']).resolve(), 'proven_supervisor_work_root_mismatch')
    import psutil
    known, proof = source_union(cfg, closure, coor, clock)
    need(proof.get('actual_exec_session') == a.la2_actual_exec_session
         and proof.get('actual_exec_exit_code_observed_by_root') == a.la2_actual_exit_code
         and proof.get('actual_tool_evidence') == a.la2_actual_tool_evidence,
         'LA2_actual_tool_exit_mismatch')
    absence(owner, known)
    out = Path(cfg['output']); need(not out.exists(), 'exclusive_attempt_no_retry_or_reset')
    need(end-time.monotonic() >= 4*PARENT+FINAL, 'preflight_consumed_setup60')
    out.mkdir()
    root, boot = own_bootstraps(psutil)
    state = dict(schema='uar00-campaign-v1', status='starting', start_unix=start,
        start_monotonic=mono, absolute_deadline_unix=unix, common_deadline_monotonic=end,
        common_seconds=COMMON, private_manifest_sha256=a.private_manifest_sha256,
        la2_closure_sha256=a.la2_closure_sha256, owned_root=root,
        la2_actual_exec_session=a.la2_actual_exec_session,
        la2_actual_exit_code=a.la2_actual_exit_code, la2_actual_tool_evidence=a.la2_actual_tool_evidence,
        extra_closure_args=a.extra_closure,
        coordinator_bootstrap_identities=boot, supervisors=[], active_supervisor=None,
        error_history=[], cleanup_confirmed=False, source_unchanged=False,
        model_fits=0, API_calls=0, quality_metric=None, root_actual_exec_confirmation_pending=True,
        suites=[dict(id=s['id'], status='not_attempted', checks_observed=None) for s in cfg['suites']],
        _manifest={}, known_predecessor_count=len(known))
    children = set(); suite_ob = None; awake = None
    def persist():
        coor.save(out/'campaign.json', {k:v for k,v in state.items() if not k.startswith('_')})
    def pulse():
        coor.cooperative_checkpoint(awake, end, unix)
        active = state.get('active_supervisor')
        if active and suite_ob is not None:
            r = read(Path(cfg['work_root'])/active)
            if r.get('owned_root'):
                suite_ob.remember(coor.identities([r['owned_root']]))
            live = suite_ob.observe(); need(not suite_ob.denials, 'suite_observation_denied')
            rss = 0
            for identity, obj in live.items():
                try:
                    need(obj.create_time() == identity[1], 'suite_identity_changed')
                    rss += obj.memory_info().rss
                except psutil.NoSuchProcess:
                    pass
            children.update(suite_ob.seen)
            need(rss <= 1536*2**20, 'suite_subtree_memory_limit')
            state['peak_suite_tree_rss_mib'] = max(state.get('peak_suite_tree_rss_mib', 0.), rss/2**20)
    def guard(parent_end=None, code='parent_cap_exhausted'):
        coor.cooperative_checkpoint(awake, end, unix, parent_end, code)
        need(digest(a.private_manifest, pulse) == a.private_manifest_sha256, 'private_manifest_changed')
        frozen(cfg, pulse)
        need(digest(closure, pulse) == a.la2_closure_sha256, 'LA2_closure_changed')
    state['_pulse'] = pulse
    try:
        with modules['awake'].PowerRequestGuard('UAR00 serial no-fit contracts', 10) as awake:
            with modules['lock'].ResearchLock(cfg['lock_path']) as lease:
                lease.write_identity(root); absence(owner, known); persist()
                for index, suite in enumerate(cfg['suites']):
                    guard(); absence(owner, known | children)
                    need(end-time.monotonic() >= (4-index)*PARENT+FINAL, 'future_suite_and_final_reserve')
                    suite_ob = owner.StrictOwnedObserver(); parent_start = time.monotonic()
                    command = [cfg['python'], '-B', '-X', 'utf8', suite['test'], '-v']
                    sup = coor.supervise(command, Path(suite['root']), out/(suite['id']+'.json'),
                        suite['id'], parent_start, PARENT, CHILD, end, unix,
                        (4-index)*PARENT+FINAL, state, persist, guard, owner, proc, boot)
                    coor.child_errors(state, sup)
                    children |= coor.identities(sup.get('owned_process_identities', []))
                    if sup.get('owned_root'):
                        children |= coor.identities([sup['owned_root']])
                    row = state['suites'][index]
                    row.update(status=sup['status'], exit_code=sup['exit_code'],
                        cleanup_confirmed=sup['cleanup_confirmed'], **log_counts(out/(suite['id']+'.log')))
                    persist(); absence(owner, known | children)
                    need(sup['status'] == 'ok' and sup['exit_code'] == 0 and sup['cleanup_confirmed']
                         and not sup.get('error_history') and row['log_passed'], 'mandatory_suite_failed')
                guard(); absence(owner, known | children)
                state.update(status='tests_completed_pending_root', checks_observed=48,
                    suite_procedure_passed=True, cleanup_confirmed=True, source_unchanged=True)
                persist(); guard()
        state['awake_guard'] = awake.record
        need(awake.record.get('release_API_verified') is True, 'power_request_cleanup_unconfirmed')
    except BaseException as exc:
        coor.error(state, str(exc) if isinstance(exc, RuntimeError) else 'queue_operation_failed', 'queue', exc)
        state.update(status='technical_failure', suite_procedure_passed=False)
    finally:
        if awake is not None:
            state['awake_guard'] = awake.record
        state['owned_process_identities'] = [dict(pid=p, create_time=c) for p,c in sorted(children)]
        state['cleanup_confirmed'] = False
        state['source_unchanged'] = False
        try:
            absence(owner, known | children)
            need(state.get('active_supervisor') is None
                 and all(ref.get('cleanup_confirmed') is True for ref in state['supervisors']),
                 'saved_supervisor_cleanup_unconfirmed')
            state['cleanup_confirmed'] = True
        except BaseException as exc:
            coor.error(state, 'final_owned_cleanup_unconfirmed', 'final_cleanup', exc)
            state.update(status='technical_failure', suite_procedure_passed=False)
        try:
            frozen(cfg, clock); need(digest(a.private_manifest, clock) == a.private_manifest_sha256,
                                    'private_manifest_changed')
            state['source_unchanged'] = True
            need(end-time.monotonic() >= ROOT_CLOSE, 'root_closure30_reserve_missing')
        except BaseException as exc:
            coor.error(state, str(exc) if isinstance(exc, RuntimeError) else 'final_queue_guard_failed', 'final', exc)
            state.update(status='technical_failure', suite_procedure_passed=False)
        state.update(finished_unix=time.time(), finished_monotonic=time.monotonic(),
                     elapsed_common_seconds=time.monotonic()-mono)
        persist()
        if time.time() >= unix or time.monotonic() >= end-ROOT_CLOSE:
            coor.error(state, 'terminal_save_exhausted_original_or_root_reserve', 'terminal_save')
            state.update(status='technical_failure', suite_procedure_passed=False); persist()
    passed = (state.get('suite_procedure_passed') is True and not state['error_history']
              and state['cleanup_confirmed'] and state['source_unchanged'])
    print(json.dumps({k:state.get(k) for k in ('status','checks_observed','suite_procedure_passed',
        'cleanup_confirmed','source_unchanged','elapsed_common_seconds')}, allow_nan=False))
    return 0 if passed else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(json.dumps(dict(status='blocked_before_or_during_queue', error_type=type(exc).__name__,
                              error_code=str(exc) if re.fullmatch('[A-Za-z0-9_]+', str(exc)) else 'preflight_operation_failed',
                              model_fits=0, API_calls=0)))
        raise SystemExit(1)
