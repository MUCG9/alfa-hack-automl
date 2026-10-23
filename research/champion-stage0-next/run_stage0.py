"""One prospective serial technical Stage0; never a model-quality experiment.

Do not launch until root has observed T7 terminal and frozen its fresh closure.
The new900s clock is assigned only by one explicit --launch, never resumed.
Source600 includes setup; exact180 includes the additional flat ON contract;
final120 includes source/cleanup/export and subsequent root confirmation.
"""
from pathlib import Path
import argparse
import ast
import hashlib
import importlib.util
import json
import math
import os
import re
import signal
import sys
import time
import zipfile

sys.dont_write_bytecode = True
WORK = Path(__file__).resolve().parents[1]
# Reuse the proven short technical-fixture depth on Windows.
OUTPUT = WORK/'cs0'
BASE = 'm4packet/manifest.json'
BASE_SHA = '8faf33cd81c0e864bcf338828c34447000111eda85bc719b8f43312d2babae9a'
COORDINATOR = 'run_lean_mvp_r2.py'
COORDINATOR_SHA = '43be86ece6c453641afdcc6f8eccef02d713986e2ac8bf3314756f0bb78e0818'
PROTOCOL = 'champion-stage0-next-dev/protocol.json'
PROTOCOL_SHA = 'b1bc726b63d847a11c8adc70cfe82f1bb5776e2bcb92c13285383307ff0e96e4'
DEPS = {
    'support_component_coordinator.py': '8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8',
    'alfa-hack-automl/src/automl/infrastructure/processes.py': 'fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d',
    'alfa-hack-automl/tools/research_lock.py': '78a0441bb3b9ea60197e9a1a6e1087f6e4cd0886593ec54bcfc4e41c9abe5a45',
    'awake-next-dev/awake_guard.py': '9a0bae0acb6ddb37e638420c52ad1e587a9180fbd7ef68ebc6e1a3c43e4bfc9b'}
COMMON, SOURCE, EXACT, FINAL, ROOT_RESERVE = 900, 600, 180, 120, 10
FAILURE_TYPE = RuntimeError


def need(value, code):
    if not value:
        raise FAILURE_TYPE(code)


def local(name):
    p = (WORK/name).resolve()
    need(not Path(name).is_absolute() and p.is_relative_to(WORK), 'reference_outside_work')
    return p


def sha(path, checkpoint=None):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            if checkpoint is not None:
                checkpoint()
            block = stream.read(2**20)
            if not block:
                break
            result.update(block)
    if checkpoint is not None:
        checkpoint()
    return result.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def imported(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def merge(pins, name, digest):
    local(name)
    need(re.fullmatch('[0-9a-f]{64}', digest) is not None, 'invalid_sha256')
    need(name not in pins or pins[name] == digest, 'conflicting_input_pin')
    pins[name] = digest


def check_counts(result, registry):
    checks = result.get('checks', [])
    need(result.get('passed') is True and result.get('source_unchanged') is True
         and result.get('fixture_cleanup_confirmed') is True, 'source_result_not_passed')
    need(len(checks) == len(registry) and {r['script'] for r in checks} == set(registry)
         and len({r['script'] for r in checks}) == len(checks), 'source_registry_inventory_changed')
    need(all(r.get('passed') is True and r.get('status') == 0
             and r.get('observed_checks') == registry[r['script']]
             and r.get('expected_checks') == registry[r['script']]
             and r.get('skipped_checks') == 0 for r in checks)
         and result.get('unique_checks_passed') == 471
         and result.get('unique_checks_skipped') == 0, 'source471_counts_or_skips_failed')


def exact_counts(result):
    counts = {'test_v2.py': 11, 'test_resilience.py': 7, 'smoke.py': 5}
    need(result.get('passed') is True and result.get('matches_current_source') is True
         and result.get('compiled_files') == 68, 'exact_result_not_passed')
    rows = result.get('checks', [])
    need(len(rows) == 3 and [r['script'] for r in rows] == list(counts), 'exact_script_inventory_changed')
    for row in rows:
        text = row.get('stdout', '')+'\n'+row.get('stderr', '')
        found = re.findall(r'Ran (\d+) tests? in ', text)
        observed = int(found[-1]) if found else 5 if row['script'] == 'smoke.py' and row.get('exit_code') == 0 else None
        need(row.get('exit_code') == 0 and observed == counts[row['script']]
             and re.search(r'\bskipped=([1-9]\d*)', text) is None, 'exact23_counts_or_skips_failed')


def main():
    global FAILURE_TYPE
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--launch', action='store_true', required=True)
    p.add_argument('--self-sha256', required=True)
    p.add_argument('--prepared-manifest-sha256', required=True)
    p.add_argument('--t7-terminal-closure', required=True)
    p.add_argument('--t7-terminal-closure-sha256', required=True)
    p.add_argument('--t7-exec-session', type=int, required=True)
    p.add_argument('--t7-exec-exit-code', type=int, required=True)
    p.add_argument('--extra-terminal-receipt', action='append', default=[], metavar='WORK_REL_PATH=SHA256')
    args = p.parse_args()
    need(sys.flags.optimize == 0, 'assert_based_source_gate_requires_nonoptimized_python')
    need(not OUTPUT.exists(), 'exclusive_stage0_output_required_no_resume_or_retry')
    # This is the only clock assignment. Argument parsing never imports a worker.
    start_unix, start_mono = time.time(), time.monotonic()
    unix, deadline = start_unix+COMMON, start_mono+COMMON
    OUTPUT.mkdir()
    import psutil
    pins, deployment, previous_ids, finished = {}, {}, set(), set()
    coor = owner = processes = awake = None
    state = dict(status='starting', qualification='PENDING', scope='serial technical Stage0 only; no ML gain',
        start_unix=start_unix, start_monotonic=start_mono, absolute_deadline_unix=unix,
        common_deadline_monotonic=deadline, common_seconds=COMMON,
        phase_caps_seconds=dict(setup_source=SOURCE, exact_default_and_optin=EXACT, final=FINAL),
        owned_root=dict(pid=os.getpid(), create_time=psutil.Process().create_time()),
        coordinator_bootstrap_identities=[], supervisors=[], gates=[], active_supervisor=None,
        cleanup_confirmed=False, source_unchanged=False, error_history=[],
        root_actual_exec_qualification='pending_root_observed_actual_exec_and_fresh_closure',
        root_confirmation_required_before_unix=unix, root_confirmation_reserved_seconds=ROOT_RESERVE,
        technical_checks_passed=False, quality_metric=None, promotion=False, submit=False,
        production_model_experiments=0, production_gateway_calls_requested=0,
        synthetic_fixture_fits='Only already registered technical source/exact suites; not public ML measurements')
    def persist():
        raw = {k: v for k, v in state.items() if not k.startswith('_')}
        if coor is not None:
            coor.save(OUTPUT/'campaign.json', raw)
        else:
            with (OUTPUT/'campaign.json').open('x', encoding='utf-8') as stream:
                json.dump(raw, stream, ensure_ascii=False, indent=2, allow_nan=False)
    def fail(exc, phase):
        code = str(exc) if isinstance(exc, RuntimeError) and re.fullmatch('[A-Za-z0-9_:+.-]{1,200}', str(exc)) else 'stage0_'+type(exc).__name__
        item = dict(code=code, phase=phase, unix=time.time(), monotonic=time.monotonic(),
            exception_type=type(exc).__name__, errno=getattr(exc, 'errno', None), winerror=getattr(exc, 'winerror', None))
        if state.get('first_failure') is None:
            state['first_failure'] = item
        state['error_history'].append(item)
        state.update(status='technical_failure', qualification='FAIL', technical_checks_passed=False)
    def checkpoint(parent_end=None, parent_code='stage0_parent_cap_exhausted'):
        if awake is not None and awake.handle is not None:
            coor.cooperative_checkpoint(awake, deadline, unix, parent_end, parent_code)
        else:
            need(time.monotonic() < deadline and time.time() < unix, 'stage0_common_clock_exhausted')
            need(abs((deadline-time.monotonic())-(unix-time.time())) <= 5, 'wall_monotonic_clock_disagreement')
            if parent_end is not None:
                need(time.monotonic() < parent_end, parent_code)
        total = psutil.Process().memory_info().rss
        for saved in state['coordinator_bootstrap_identities']:
            try:
                proc = psutil.Process(saved['pid'])
                if proc.create_time() == saved['create_time']:
                    total += proc.memory_info().rss
            except psutil.NoSuchProcess:
                pass
        need(total <= 2*2**30, 'stage0_parent_bootstrap_memory_limit')
    def frozen(parent_end=None, parent_code='stage0_parent_cap_exhausted'):
        check = lambda: checkpoint(parent_end, parent_code)
        check()
        for name, digest in {**pins, **deployment}.items():
            need(sha(local(name), check) == digest, 'stage0_frozen_input_changed')
        source = WORK/'csdev'
        actual_python = {q.relative_to(source).as_posix() for folder in ['src', 'tests', 'tools']
                         for q in (source/folder).rglob('*.py')}
        expected_python = {n.removeprefix('csdev/') for n in pins if n.startswith('csdev/')
                           and n.endswith('.py') and n.split('/')[1] in {'src', 'tests', 'tools'}}
        need(actual_python == expected_python, 'stage0_python_inventory_changed')
        check()
    def absence():
        history = coor.predecessor(owner, finished, base.get('extra_predecessor_receipts', []),
                                   base['terminal_predecessor_receipts'])
        previous_ids.update(coor.identities(history))
        observer = owner.StrictOwnedObserver()
        observer.remember(previous_ids | finished)
        need(not observer.observe() and not observer.denials and not observer.final_check()['unresolved'],
             'stage0_predecessor_or_prior_child_live_or_denied')
        state['fresh_predecessor_identity_count'] = len(observer.seen)
    def phase(command, cwd, name, parent_start, cap, child_cap, future):
        record = coor.supervise(command, cwd, OUTPUT/(name+'-supervisor.json'), name,
            parent_start, cap, child_cap, deadline, unix, cap+future,
            state, persist, frozen, owner, processes, state['coordinator_bootstrap_identities'])
        coor.child_errors(state, record)
        finished.update(coor.identities(record.get('owned_process_identities', [])))
        need(record.get('status') == 'ok' and record.get('exit_code') == 0
             and record.get('cleanup_confirmed') is True, 'stage0_'+name+'_supervisor_failed')
        return record
    try:
        need(sha(__file__, lambda: checkpoint(start_mono+SOURCE)) == args.self_sha256, 'stage0_self_pin_failed')
        for name, digest in {COORDINATOR: COORDINATOR_SHA, BASE: BASE_SHA, PROTOCOL: PROTOCOL_SHA, **DEPS}.items():
            need(sha(local(name), lambda: checkpoint(start_mono+SOURCE)) == digest, 'stage0_dependency_pin_failed')
            merge(pins, name, digest)
        coor = imported('_champion_stage0_proven_coordinator', local(COORDINATOR))
        # Preserve precise first guard causes in the reused supervisor receipt.
        FAILURE_TYPE = coor.TechnicalFailure
        base = read(local(BASE))
        for name, digest in base['immutable_files'].items():
            merge(pins, name, digest)
        manifest_ref = 'cs-stage0-packet/manifest.json'
        need(sha(local(manifest_ref)) == args.prepared_manifest_sha256, 'stage0_prepared_manifest_pin_failed')
        prepared = read(local(manifest_ref))
        need(prepared['source_root'] == 'csdev' and prepared['source_expected_checks'] == 471
             and prepared['source_skipped_expected'] == 0 and sum(prepared['registry'].values()) == 471
             and prepared['exact_repeated_expected_checks'] == 23
             and prepared['base_manifest_sha256'] == BASE_SHA
             and prepared['changed_flat_modules'] == ['automl_runner.py', 'automl_search_stages.py']
             and len(prepared['compiled_sha256']) == 68, 'stage0_prepared_contract_changed')
        merge(pins, manifest_ref, args.prepared_manifest_sha256)
        merge(pins, prepared['archive'], prepared['archive_sha256'])
        merge(pins, Path(__file__).resolve().relative_to(WORK).as_posix(), args.self_sha256)
        for name, digest in prepared['source_files_sha256'].items():
            merge(pins, 'csdev/'+name, digest)
        owner = imported('_champion_stage0_owner', local(coor.LIBS['owner']))
        processes = imported('_champion_stage0_processes', local(coor.LIBS['processes']))
        locker = imported('_champion_stage0_lock', local(coor.LIBS['lock']))
        guard_class = imported('_champion_stage0_awake', local(coor.AWAKE)).PowerRequestGuard
        awake = guard_class('Alfa champion Stage0 technical pid'+str(os.getpid()), 10)
        own_paths = {Path(__file__).resolve()}
        parent = psutil.Process().parent()
        while parent is not None:
            birth = parent.create_time()
            if not any(Path(arg).resolve() in own_paths for arg in parent.cmdline() if not arg.startswith('-')):
                break
            need(parent.create_time() == birth, 'stage0_bootstrap_identity_changed')
            state['coordinator_bootstrap_identities'].append(dict(pid=parent.pid, create_time=birth))
            parent = parent.parent()
        state.update(prepared_manifest_sha256=args.prepared_manifest_sha256,
            predecessor_T7_exec_session=args.t7_exec_session, predecessor_T7_exec_exit_code=args.t7_exec_exit_code)
        need(args.t7_exec_session == 65008, 'expected_actual_T7_session_required')
        dynamic = [(args.t7_terminal_closure, args.t7_terminal_closure_sha256)]
        for value in args.extra_terminal_receipt:
            name, digest = value.rsplit('=', 1)
            dynamic.append((name, digest))
        for index, (name, digest) in enumerate(dynamic):
            need(sha(local(name)) == digest, 'stage0_terminal_closure_pin_failed')
            proof = read(local(name))
            need(proof.get('cleanup_confirmed') is True and proof.get('source_unchanged') is True
                 and proof.get('active_owned_processes', []) == []
                 and proof.get('uncertain_owned', []) == [], 'stage0_terminal_closure_not_clean')
            need(proof.get('owned_identities') and proof.get('closure_preparer_identities'),
                 'stage0_terminal_complete_identity_and_preparer_union_required')
            if index == 0:
                need(proof.get('actual_exec_session') == args.t7_exec_session
                     and proof.get('actual_exec_exit_code_observed_by_root') == args.t7_exec_exit_code,
                     'stage0_root_observed_T7_exec_binding_failed')
            previous_ids.update(coor.identities(proof['owned_identities']))
            previous_ids.update(coor.identities(proof['closure_preparer_identities']))
            merge(pins, name, digest)
        # Only declared real identity fields are consumed; excluded analytical
        # edges are never traversed and no historical PPID adoption is performed.
        launch, campaign = read(local('m4packet/launch.json')), read(local('t7/campaign.json'))
        need(type(launch.get('coordinator_exit_code')) is int
             and launch['coordinator_exit_code'] == args.t7_exec_exit_code
             and type(campaign.get('finished_unix')) in (int, float)
             and math.isfinite(campaign['finished_unix'])
             and type(launch.get('finished_unix')) in (int, float)
             and math.isfinite(launch['finished_unix']), 'stage0_T7_parent_not_terminal')
        required_ids = coor.identities(launch['launcher_identities']) | coor.identities([campaign['owned_root']])
        required_ids |= coor.identities(campaign['coordinator_bootstrap_identities'])
        for ref in campaign['supervisors']:
            sup = read(local(ref['path']))
            need(sha(local(ref['path'])) == ref['sha256'], 'stage0_terminal_supervisor_changed')
            required_ids |= coor.identities(sup.get('owned_process_identities', []))
            if sup.get('owned_root'):
                required_ids |= coor.identities([sup['owned_root']])
            merge(pins, ref['path'], ref['sha256'])
        need(required_ids <= previous_ids, 'stage0_closure_missing_declared_T7_identity')
        for name in ['m4packet/launch.json', 't7/campaign.json']:
            merge(pins, name, sha(local(name)))
        state.update(predecessor_T7_qualification=campaign.get('qualification'),
            immutable_files=pins, awake_guard=awake.record, _manifest={}, _pulse=lambda: checkpoint())
        previous_signals = {}
        with awake:
            absence()
            frozen(start_mono+SOURCE)
            with locker.ResearchLock(WORK/'alfa-hack-automl/test-runs/.owned-research.lock') as lock:
                lock.write_identity(state['owned_root'])
                absence()
                frozen(start_mono+SOURCE)
                def interrupted(signum, frame):
                    raise SystemExit(128+signum)
                for sig in [signal.SIGINT, signal.SIGTERM]:
                    previous_signals[sig] = signal.signal(sig, interrupted)
                persist()
                try:
                    cap_left = start_mono+SOURCE-time.monotonic()
                    need(cap_left > 30, 'stage0_setup_exhausted_source_allocation')
                    phase([sys.executable, '-B', '-X', 'utf8', str(WORK/'csdev/tools/run_checks.py'),
                           '--output', str(OUTPUT/'source')], WORK/'csdev', 'source',
                          start_mono, SOURCE, min(570, cap_left-30), EXACT+FINAL)
                    source_result = read(OUTPUT/'source/results.json')
                    check_counts(source_result, prepared['registry'])
                    state['gates'].append(dict(name='source', passed=True, checks=471,
                        result='cs0/source/results.json', sha256=sha(OUTPUT/'source/results.json')))
                    exact_start = time.monotonic()
                    exact_end = exact_start+EXACT
                    checkpoint(deadline-FINAL, 'stage0_final_reserve_unavailable')
                    absence()
                    phase([sys.executable, '-B', '-X', 'utf8', str(WORK/'csdev/tools/verify_release.py'),
                           '--archive', str(local(prepared['archive'])), '--output', str(OUTPUT/'exact.json'),
                           '--timeout', '120', '--memory-gb', '1.2'], WORK/'csdev', 'exact',
                          exact_start, 150, 120, 30+FINAL)
                    exact_result = read(OUTPUT/'exact.json')
                    exact_counts(exact_result)
                    need(exact_result['sha256'] == prepared['archive_sha256'], 'stage0_exact_archive_hash_failed')
                    # Same pinned test assertions and JSON bytes, adapted ONLY
                    # to flat import names and the flat root instead of src.
                    flat = OUTPUT/'flat'
                    flat.mkdir()
                    with zipfile.ZipFile(local(prepared['archive'])) as archive:
                        need(len(archive.namelist()) == 68 and set(archive.namelist()) == set(prepared['compiled_sha256']),
                             'stage0_flat_archive_inventory_failed')
                        for name, digest in prepared['compiled_sha256'].items():
                            checkpoint(exact_end)
                            need(Path(name).name == name, 'stage0_archive_not_flat')
                            data = archive.read(name)
                            need(hashlib.sha256(data).hexdigest() == digest, 'stage0_flat_member_hash_failed')
                            (flat/name).write_bytes(data)
                    fixture = flat/'tests/fixtures/champion_seed'
                    fixture.mkdir(parents=True)
                    for name in ['champion.json', 'protected_control.json']:
                        (fixture/name).write_bytes((WORK/'csdev/tests/fixtures/champion_seed'/name).read_bytes())
                    original = (WORK/'csdev/tests/test_pinned_champion_seed.py').read_text('utf-8')
                    replacements = {"parents[1]/'src'": 'parents[1]',
                        'from automl.search.policy import': 'from automl_policy import',
                        'from automl.search.stages import': 'from automl_search_stages import'}
                    changed = original
                    for old, new in replacements.items():
                        need(changed.count(old) == 1, 'stage0_flat_test_adaptation_marker_changed')
                        changed = changed.replace(old, new)
                    compile(changed, 'test_pinned_champion_seed.py', 'exec')
                    (flat/'tests/test_pinned_champion_seed.py').write_text(changed, encoding='utf-8')
                    for q in flat.rglob('*'):
                        if q.is_file():
                            deployment[q.relative_to(WORK).as_posix()] = sha(q)
                    state['flat_pinned_test_adaptation'] = dict(source_sha256=sha(WORK/'csdev/tests/test_pinned_champion_seed.py'),
                        transformed_sha256=sha(flat/'tests/test_pinned_champion_seed.py'), replacements=replacements,
                        assertion_changes=0, source_package_imported=False)
                    tick = time.monotonic()
                    left = exact_end-tick
                    need(left > 15, 'stage0_flat_contract_exact_allocation_unavailable')
                    phase([sys.executable, '-B', '-X', 'utf8', str(flat/'tests/test_pinned_champion_seed.py')],
                          flat, 'exact-optin', tick, left, left-10, FINAL)
                    text = (OUTPUT/'exact-optin-supervisor.log').read_text('utf-8')
                    need(re.findall(r'Ran (\d+) tests? in ', text) == ['1'] and '\nOK\n' in text
                         and 'skipped=' not in text, 'stage0_flat_optin_one_contract_failed')
                    state['gates'].extend([dict(name='exact-default', passed=True, checks=23,
                        result='cs0/exact.json', sha256=sha(OUTPUT/'exact.json')),
                        dict(name='exact-optin', passed=True, checks=1,
                        log='cs0/exact-optin-supervisor.log', sha256=sha(OUTPUT/'exact-optin-supervisor.log'))])
                    state.update(status='technical_checks_passed_pending_root_exec_and_closure',
                        qualification='PENDING_ROOT', technical_checks_passed=True)
                except BaseException as exc:
                    fail(exc, 'technical_gates')
                finally:
                    final_end = min(time.monotonic()+FINAL, deadline-ROOT_RESERVE)
                    state['finalization_deadline_monotonic'] = final_end
                    try:
                        frozen(final_end, 'stage0_finalization_cap_exhausted')
                        absence()
                        need(all(r['cleanup_confirmed'] is True for r in state['supervisors']), 'stage0_child_cleanup_unknown')
                        state.update(cleanup_confirmed=True, source_unchanged=True)
                    except BaseException as exc:
                        fail(exc, 'terminal_source_cleanup')
                    try:
                        checkpoint(final_end, 'stage0_finalization_cap_exhausted')
                        persist()
                    finally:
                        for sig, handler in previous_signals.items():
                            signal.signal(sig, handler)
        need(awake.record.get('release_API_verified') is True, 'stage0_power_release_unverified')
        last = awake.record['last_heartbeat']
        def after_release():
            checkpoint(state['finalization_deadline_monotonic'], 'stage0_terminal_export_cap_exhausted')
            need(max(time.time()-last['unix'], time.monotonic()-last['monotonic']) <= 10,
                 'stage0_terminal_heartbeat_gap_over10s')
        # The full frozen walk just finished while heartbeat/power were active.
        # After release only rebind small authority files, retaining a real10s
        # terminal gap check rather than a second unpulsed full fixture walk.
        terminal_pins = [Path(__file__).resolve().relative_to(WORK).as_posix(),
            manifest_ref, COORDINATOR, PROTOCOL, args.t7_terminal_closure, *DEPS]
        for name in terminal_pins:
            digest = pins[name]
            need(sha(local(name), after_release) == digest, 'stage0_post_power_source_changed')
        absence()
        after_release()
    except BaseException as exc:
        fail(exc, 'stage0_parent')
        state.update(cleanup_confirmed=False, source_unchanged=False)
    finally:
        if awake is not None:
            state['awake_guard'] = awake.record
            if awake.handle is not None:
                try:
                    awake.close()
                except BaseException as exc:
                    fail(exc, 'power_release')
        state.update(finished_unix=time.time(), finished_monotonic=time.monotonic(),
            elapsed_common_seconds=time.monotonic()-start_mono,
            owned_process_identities=[dict(pid=pid, create_time=birth) for pid, birth in sorted(finished)])
        if time.time() >= unix-ROOT_RESERVE or time.monotonic() >= deadline-ROOT_RESERVE:
            fail(RuntimeError('stage0_terminal_root_reserve_exhausted'), 'terminal_export')
        try:
            persist()
            if time.monotonic() >= min(deadline-ROOT_RESERVE, state.get('finalization_deadline_monotonic', deadline)):
                fail(RuntimeError('stage0_terminal_receipt_over_cap'), 'terminal_export')
                persist()
        except BaseException:
            raise
    print(json.dumps({k: state[k] for k in ['status', 'qualification', 'cleanup_confirmed',
        'source_unchanged', 'technical_checks_passed', 'elapsed_common_seconds', 'root_actual_exec_qualification']}))
    raise SystemExit(0 if state['technical_checks_passed'] and state['cleanup_confirmed']
                     and state['source_unchanged'] and not state['error_history'] else 1)


if __name__ == '__main__':
    main()
