"""Prospective serial whole-agent champion-policy A/B, not a component benchmark.

Source only until root publishes/reviews it and certifies actual Stage0 success.
One fresh5400s clock: setup420 + A2100 + B2100 + audit600 + cleanup180.
The only treatment is B's reviewed archive and pinned --champion-recipe input.
No earlier run, process identity, clock, metric or qualification is overwritten.
"""
from pathlib import Path
import argparse
import copy
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
OUTPUT = WORK/'cp1'
BASE, BASE_SHA = 'm4packet/manifest.json', '8faf33cd81c0e864bcf338828c34447000111eda85bc719b8f43312d2babae9a'
PREPARED, PREPARED_SHA = 'cs-stage0-packet/manifest.json', '5160562be127dc6130a1f3349a21b552c8aac526ead484048982716b037aa1c1'
COORDINATOR, COORDINATOR_SHA = 'run_lean_mvp_r2.py', '43be86ece6c453641afdcc6f8eccef02d713986e2ac8bf3314756f0bb78e0818'
R4, R4_SHA = 'repaired-mvp-r1-dev/evaluator_r4.py', 'c08e9f0be13a708d67b3266518381d6f1be3b0f43c384ef6425634160d7e2783'
CHAMPION, CHAMPION_SHA = 'champion-seed-next-dev/champion-t5-regression.json', '914880505ed751da9fd0a38d7f1724dd860c20d98456ff3efd16a195a0709ad4'
LINEAGE, LINEAGE_SHA = 'champion-seed-next-dev/champion-t5-lineage.json', '408d24be5c884152531552bb0016611eb55b9123aadb4c1a361396d3f7115cf3'
STAGE0, STAGE0_SHA = 'cs0/terminal-root-closure.json', '06d20ce5b1bfd51ceefc924f8d09eb06b4022e9998bcef4d36343cb58669fba8'
NEW_TERMINAL = {
    'm4packet/terminal-root-closure.json': 'd19648a53253c0b070fe12068d6eafef5569e2d51332d9b212ef44cc828b9ddc',
    't7-report-publication-closure-r2.json': '154eca18b219f8c62ec79ec391da2b09fa59c891fcb444e96732e1c2f1afed20',
    'method-update-publication-closure-r1.json': '93bd05d3ff741eadf9bfc8858c875e8c130ec2aadc216c77e9480283b2692030'}
ARCHIVES = {'A': ('m4packet/lean-source.zip', '16120391716fe43b7f0ec2b36f35eaea7511a08cba4f4108da01cd81dea314d0'),
    'B': ('cs-stage0-packet/champion-source.zip', '52627ac5b9da5ee47d8d40951f84edf9b9dede28cca4b4f90504be6bb4e672b8')}
COMMON, SETUP, TASK, TASK_SUPERVISOR, SOLVER, AUDIT, CLEANUP = 5400, 420, 2100, 2040, 2010, 600, 180
CHAMPION_SIGNATURE = '959a9b8fed203d71bafbbd4770b6bfb5b6aa5da79d08ee568b93979d7f795421'
FAILURE_TYPE = RuntimeError


def need(value, code):
    if not value:
        raise FAILURE_TYPE(code)


def local(name):
    target = (WORK/name).resolve()
    need(not Path(name).is_absolute() and target.is_relative_to(WORK), 'reference_outside_work')
    return target


def sha(path, checkpoint=None):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            if checkpoint is not None:
                checkpoint()
            block = stream.read(2**20)
            if not block:
                break
            digest.update(block)
    if checkpoint is not None:
        checkpoint()
    return digest.hexdigest()


def load(path):
    return json.loads(Path(path).read_text('utf-8'))


def imported(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def merge(pins, name, digest):
    local(name)
    need(isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest), 'invalid_sha256')
    need(name not in pins or pins[name] == digest, 'conflicting_input_pin')
    pins[name] = digest


def solver_argv(arm):
    argv = [sys.executable, '-B', '-X', 'utf8', '-u', 'solution.py', 'task.md',
        '--four-stage', '--preserve-anchor', '--protect-original-features',
        '--control-recipe', 'protected_control.json', '--max-experiments', '9',
        '--max-planner-calls', '2', '--max-llm-calls', '4', '--hpo-trials', '8',
        '--hpo-budget', '900', '--hpo-sampler', 'tpe', '--validation-strategy', 'auto',
        '--feature-selection-top-k', '32', '--planner-mode', 'staged',
        '--run-name', 'repair4', '--time-budget', str(SOLVER)]
    if arm == 'B':
        argv += ['--champion-recipe', 'champion_recipe_input.json']
    return argv


def main():
    global FAILURE_TYPE
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--launch', action='store_true', required=True)
    p.add_argument('--self-sha256', required=True)
    p.add_argument('--auditor-sha256', required=True)
    p.add_argument('--stage0-root-closure', required=True)
    p.add_argument('--stage0-root-closure-sha256', required=True)
    p.add_argument('--stage0-exec-session', type=int, required=True)
    p.add_argument('--bootstrap-launcher', help='Only for a root-pinned same-process private-env launcher')
    p.add_argument('--bootstrap-launcher-sha256')
    p.add_argument('--extra-terminal-receipt', action='append', default=[], metavar='WORK_REL_PATH=SHA256')
    args = p.parse_args()
    need(sys.flags.optimize == 0, 'nonoptimized_python_required')
    need(not OUTPUT.exists(), 'new_pair_output_required_no_resume_or_retry')
    # No clock is assigned by source preparation; only this future launch does it.
    start_unix, start_mono = time.time(), time.monotonic()
    unix, deadline = start_unix+COMMON, start_mono+COMMON
    OUTPUT.mkdir()
    import psutil
    state = dict(status='starting', qualification='PENDING', start_unix=start_unix,
        start_monotonic=start_mono, common_deadline_monotonic=deadline,
        absolute_deadline_unix=unix, common_seconds=COMMON,
        allocations=dict(setup=SETUP, A=TASK, B=TASK, independent_pair_audit=AUDIT, final_cleanup=CLEANUP),
        owned_root=dict(pid=os.getpid(), create_time=psutil.Process().create_time()),
        coordinator_bootstrap_identities=[], supervisors=[], active_supervisor=None, arms=[],
        cleanup_confirmed=False, source_unchanged=False, pair_artifact_checks_passed=False,
        independent_audit=None, descriptive_retention_win=None, error_history=[],
        root_actual_exec_qualification='pending_root_observed_actual_exec_and_fresh_closure',
        root_confirmation_required_before_unix=unix, quality_metric=None,
        promotion=False, submit=False, official_score=None,
        scope='One sequential stochastic whole-agent A/B on reused public temporal cuts; not stable causal or blind/private gain')
    pins, deployment, known, finished = {}, {}, set(), set()
    coor = owner = processes = awake = None
    final_end = None
    auditor = 'champion-pair-next-dev/audit_pair.py'
    manifest_path, plan_path = OUTPUT/'manifest.json', OUTPUT/'verification-plan.json'
    def persist():
        data = {k: v for k, v in state.items() if not k.startswith('_')}
        if coor is None:
            with (OUTPUT/'campaign.json').open('x', encoding='utf-8') as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        else:
            coor.save(OUTPUT/'campaign.json', data)
    def error(exc, phase):
        code = str(exc) if isinstance(exc, RuntimeError) and re.fullmatch('[A-Za-z0-9_:+.-]{1,200}', str(exc)) else 'pair_'+type(exc).__name__
        entry = dict(code=code, phase=phase, unix=time.time(), monotonic=time.monotonic(),
            exception_type=type(exc).__name__, errno=getattr(exc, 'errno', None), winerror=getattr(exc, 'winerror', None))
        state.setdefault('first_failure', entry)
        state['error_history'].append(entry)
        state.update(status='technical_failure', qualification='FAIL', pair_artifact_checks_passed=False,
            descriptive_retention_win=None, quality_metric=None)
    def checkpoint(parent_end=None, code='pair_parent_cap_exhausted'):
        if awake is not None and awake.handle is not None:
            coor.cooperative_checkpoint(awake, deadline, unix, parent_end, code)
        else:
            need(time.monotonic() < deadline and time.time() < unix, 'pair_common_clock_exhausted')
            need(abs((deadline-time.monotonic())-(unix-time.time())) <= 5, 'wall_monotonic_clock_disagreement')
            if parent_end is not None:
                need(time.monotonic() < parent_end, code)
        rss = psutil.Process().memory_info().rss
        for saved in state['coordinator_bootstrap_identities']:
            try:
                proc = psutil.Process(saved['pid'])
                if proc.create_time() == saved['create_time']:
                    rss += proc.memory_info().rss
            except psutil.NoSuchProcess:
                pass
        need(rss <= 2*2**30, 'pair_parent_bootstrap_memory_limit')
    def frozen(parent_end=None, code='pair_parent_cap_exhausted'):
        check = lambda: checkpoint(parent_end, code)
        check()
        for name, digest in {**pins, **deployment}.items():
            need(sha(local(name), check) == digest, 'pair_frozen_source_input_or_seal_changed')
        check()
    def absence():
        history = coor.predecessor(owner, finished, base.get('extra_predecessor_receipts', []),
                                   base['terminal_predecessor_receipts'])
        known.update(coor.identities(history))
        observer = owner.StrictOwnedObserver()
        observer.remember(known | finished)
        need(not observer.observe() and not observer.denials and not observer.final_check()['unresolved'],
             'pair_closed_predecessor_or_prior_child_live_or_denied')
        state['fresh_predecessor_identity_count'] = len(observer.seen)
    try:
        setup_end = start_mono+SETUP
        check = lambda: checkpoint(setup_end, 'pair_setup_cap_exhausted')
        for name, digest in {BASE: BASE_SHA, PREPARED: PREPARED_SHA, COORDINATOR: COORDINATOR_SHA,
                            R4: R4_SHA, CHAMPION: CHAMPION_SHA, LINEAGE: LINEAGE_SHA,
                            auditor: args.auditor_sha256,
                            Path(__file__).resolve().relative_to(WORK).as_posix(): args.self_sha256}.items():
            need(sha(local(name), check) == digest, 'pair_explicit_source_binding_failed')
            merge(pins, name, digest)
        need(bool(args.bootstrap_launcher) == bool(args.bootstrap_launcher_sha256), 'paired_bootstrap_path_SHA_required')
        if args.bootstrap_launcher:
            need(sha(local(args.bootstrap_launcher), check) == args.bootstrap_launcher_sha256,
                 'explicit_bootstrap_launcher_pin_failed')
            merge(pins, args.bootstrap_launcher, args.bootstrap_launcher_sha256)
        coor = imported('_champion_pair_proven_coordinator', local(COORDINATOR))
        FAILURE_TYPE = coor.TechnicalFailure
        base, prepared, lineage = load(local(BASE)), load(local(PREPARED)), load(local(LINEAGE))
        need(base['source_root'] == 'm3dev' and prepared['source_root'] == 'csdev'
             and prepared['base_manifest_sha256'] == BASE_SHA
             and prepared['changed_flat_modules'] == ['automl_runner.py', 'automl_search_stages.py'],
             'pair_only_reviewed_champion_overlay_required')
        for name, digest in base['immutable_files'].items():
            merge(pins, name, digest)
        for name, digest in prepared['source_files_sha256'].items():
            merge(pins, 'csdev/'+name, digest)
        raw_archives = {}
        arms = {}
        for arm, frozen_archive in ARCHIVES.items():
            name, digest = frozen_archive
            need(sha(local(name), check) == digest, 'pair_exact_archive_required')
            merge(pins, name, digest)
            compiled = base['compiled_sha256'] if arm == 'A' else prepared['compiled_sha256']
            with zipfile.ZipFile(local(name)) as archive:
                need(len(archive.namelist()) == 68 and set(archive.namelist()) == set(compiled),
                     'pair_archive_inventory_changed')
                raw_archives[arm] = {n: archive.read(n) for n in archive.namelist()}
                need(all(hashlib.sha256(data).hexdigest() == compiled[n] for n, data in raw_archives[arm].items()),
                     'pair_archive_member_changed')
            arms[arm] = dict(archive=name, archive_sha256=digest, compiled_sha256=compiled,
                source_root='m3dev' if arm == 'A' else 'csdev')
        need([n for n in sorted(raw_archives['A']) if raw_archives['A'][n] != raw_archives['B'][n]]
             == ['automl_runner.py', 'automl_search_stages.py'], 'pair_runtime_factor_confounded')
        del raw_archives
        for name in [*coor.LIBS.values(), coor.AWAKE]:
            need(name in pins, 'pair_runtime_dependency_unbound')
        # Guard every leaf before importing these pinned, previously used helpers.
        frozen(setup_end, 'pair_setup_cap_exhausted')
        owner = imported('_champion_pair_owner', local(coor.LIBS['owner']))
        processes = imported('_champion_pair_processes', local(coor.LIBS['processes']))
        locker = imported('_champion_pair_lock', local(coor.LIBS['lock']))
        awake = imported('_champion_pair_awake', local(coor.AWAKE)).PowerRequestGuard(
            'Alfa champion whole-agent pair pid'+str(os.getpid()), 10)
        parent = psutil.Process().parent()
        own_paths = {Path(__file__).resolve()}
        if args.bootstrap_launcher:
            own_paths.add(local(args.bootstrap_launcher))
        while parent is not None:
            birth = parent.create_time()
            if not any(Path(v).resolve() in own_paths for v in parent.cmdline() if not v.startswith('-')):
                break
            need(parent.create_time() == birth, 'pair_bootstrap_identity_changed')
            state['coordinator_bootstrap_identities'].append(dict(pid=parent.pid, create_time=birth))
            parent = parent.parent()
        need(args.stage0_exec_session == 79591, 'actual_Stage0_session_required')
        need(args.stage0_root_closure == STAGE0 and args.stage0_root_closure_sha256 == STAGE0_SHA,
             'exact_root_certified_Stage0_proof_required')
        refs = [(args.stage0_root_closure, args.stage0_root_closure_sha256)]
        refs += list(NEW_TERMINAL.items())
        refs += [tuple(v.rsplit('=', 1)) for v in args.extra_terminal_receipt]
        for index, (name, digest) in enumerate(refs):
            need(sha(local(name), check) == digest, 'pair_terminal_closure_pin_failed')
            proof = load(local(name))
            need(proof.get('cleanup_confirmed') is True and proof.get('source_unchanged') is True
                 and proof.get('active_owned_processes', []) == [] and proof.get('uncertain_owned', []) == []
                 and proof.get('owned_identities') and proof.get('closure_preparer_identities'),
                 'pair_complete_terminal_closure_required')
            if index == 0:
                stage0_proof = proof
                need(proof.get('actual_exec_session') == args.stage0_exec_session
                     and proof.get('actual_exec_exit_code_observed_by_root') == 0
                     and proof.get('technical_procedure_passed') is True
                     and proof.get('source_checks') == 471 and proof.get('source_skipped') == 0
                     and proof.get('exact_default_repeated') == 23 and proof.get('extra_exact_pinned_optin') == 1
                     and proof.get('source_compilation_matches_prepared_archive') is True
                     and proof.get('original_common_seconds') == 900
                     and 0 <= proof['raw_parent_elapsed_seconds'] < 900
                     and abs(proof['original_deadline_unix']-proof['original_start_unix']-900) <= 1e-6,
                     'pair_root_certified_Stage0_success_required')
            known.update(coor.identities(proof['owned_identities']))
            known.update(coor.identities(proof['closure_preparer_identities']))
            merge(pins, name, digest)
        stage0 = load(local('cs0/campaign.json'))
        need(stage0.get('technical_checks_passed') is True and stage0.get('cleanup_confirmed') is True
             and stage0.get('source_unchanged') is True and not stage0.get('error_history')
             and isinstance(stage0.get('finished_unix'), (int, float)), 'pair_actual_Stage0_checks_required')
        need(stage0.get('prepared_manifest_sha256') == PREPARED_SHA
             and stage0['start_unix'] == stage0_proof['original_start_unix']
             and stage0['absolute_deadline_unix'] == stage0_proof['original_deadline_unix']
             and math.isfinite(stage0['finished_unix'])
             and stage0['start_unix'] <= stage0['finished_unix'] < stage0['absolute_deadline_unix']
             and math.isclose(stage0['elapsed_common_seconds'], stage0_proof['raw_parent_elapsed_seconds'],
                              rel_tol=0, abs_tol=.01), 'pair_exact_Stage0_manifest_and_clock_lineage_required')
        gate_counts = {g['name']: g['checks'] for g in stage0['gates'] if g.get('passed') is True}
        need(gate_counts == {'source': 471, 'exact-default': 23, 'exact-optin': 1}, 'pair_Stage0_count_proof_incomplete')
        declared = coor.identities([stage0['owned_root']]) | coor.identities(stage0['coordinator_bootstrap_identities'])
        declared |= coor.identities(stage0['owned_process_identities'])
        need(declared <= known, 'pair_Stage0_closure_missing_real_identity')
        merge(pins, 'cs0/campaign.json', sha(local('cs0/campaign.json'), check))
        for name, digest in stage0['immutable_files'].items():
            merge(pins, name, digest)
        for ref in stage0['supervisors']:
            need(sha(local(ref['path']), check) == ref['sha256'], 'pair_Stage0_supervisor_changed')
            terminal = load(local(ref['path']))
            need(terminal.get('status') == 'ok' and terminal.get('exit_code') == 0
                 and terminal.get('cleanup_confirmed') is True, 'pair_Stage0_child_not_clean')
            need(coor.identities(terminal['owned_process_identities']) <= known, 'pair_Stage0_child_missing_from_closure')
            merge(pins, ref['path'], ref['sha256'])
        task = copy.deepcopy(next(t for t in base['tasks'] if t['kind'] == 'regression'))
        need(task['code'] == 'r' and task['files'] == lineage['raw_task_input_sha256'], 'pair_five_inputs_or_task_changed')
        need(task['control_recipe']['sha256'] == '0480d5e60c6aa42be4a78e300c3baf7a0346d431707ce79cb6850c73d84adf1b',
             'pair_exact_V16_control_required')
        for arm in arms:
            arms[arm]['tasks'] = [task]
            arms[arm]['argv'] = solver_argv(arm)
        manifest = dict(schema='champion-whole-agent-pair-v1', output_root='cp1',
            immutable_files=pins, arms=arms, task=task, common_seconds=COMMON,
            source_archive_factor='Only B archive two reviewed modules and --champion-recipe input; A has no flag/input',
            champion=dict(path=CHAMPION, sha256=CHAMPION_SHA, signature=CHAMPION_SIGNATURE),
            solver_budget_seconds=SOLVER, supervisor_parent_seconds=TASK_SUPERVISOR,
            task_allocation_seconds=TASK, maximum_experiments=9, hpo_trials=8, hpo_budget_seconds=900,
            max_planner_calls=2, gateway_call_limit=4, threads=2,
            interpreter_path=sys.executable, interpreter_sha256=sha(sys.executable, check),
            interpreter_version=sys.version, interpreter_prefix=sys.prefix, interpreter_base_prefix=sys.base_prefix,
            requested_model=base['requested_model'], reasoning_effort=base['reasoning_effort'])
        plan = copy.deepcopy(base['verification_plan_template'])
        plan.update(verifier_source_sha256=args.auditor_sha256, manual_metric_verifier_path=R4,
            manual_metric_verifier_sha256=R4_SHA, original_common_start_unix=start_unix,
            original_absolute_deadline_unix=unix, common_seconds=COMMON,
            expected_regression_splits=copy.deepcopy(lineage['split_fingerprints']),
            T5_cut_floors=copy.deepcopy(lineage['selected_independently_verified_metrics']),
            reproduction_absolute_tolerance=1e-9, expected_champion_signature=CHAMPION_SIGNATURE,
            expected_champion_input_sha256=CHAMPION_SHA, pair_order=['A', 'B'])
        state.update(_manifest=base, _pulse=lambda: checkpoint(), awake_guard=awake.record,
            stage0_root_closure=dict(path=args.stage0_root_closure, sha256=args.stage0_root_closure_sha256))
        with awake:
            absence()
            frozen(setup_end, 'pair_setup_cap_exhausted')
            with locker.ResearchLock(WORK/'alfa-hack-automl/test-runs/.owned-research.lock') as lock:
                lock.write_identity(state['owned_root'])
                absence()
                frozen(setup_end, 'pair_setup_cap_exhausted')
                coor.save(manifest_path, manifest, True)
                state['manifest_sha256'] = sha(manifest_path, check)
                plan['execution_manifest_sha256'] = state['manifest_sha256']
                coor.save(plan_path, plan, True)
                deployment[coor.relative(manifest_path)] = state['manifest_sha256']
                deployment[coor.relative(plan_path)] = sha(plan_path, check)
                state['verification_plan_sha256'] = deployment[coor.relative(plan_path)]
                checkpoint(setup_end, 'pair_setup_cap_exhausted')
                state['setup_seconds'] = time.monotonic()-start_mono
                previous = {}
                def interrupted(signum, frame):
                    raise SystemExit(128+signum)
                for sig in [signal.SIGINT, signal.SIGTERM]:
                    previous[sig] = signal.signal(sig, interrupted)
                persist()
                try:
                    for index, arm in enumerate(['A', 'B']):
                        tick = time.monotonic()
                        future = (TASK if index == 0 else 0)+AUDIT+CLEANUP
                        need(deadline-tick >= TASK+future, 'pair_full_fixed_remaining_allocations_unavailable')
                        absence()
                        (OUTPUT/arm).mkdir()
                        directory = OUTPUT/arm/'r'
                        coor.materialize(task, directory, {**arms[arm], 'immutable_files': pins}, deployment)
                        if arm == 'B':
                            target = directory/'champion_recipe_input.json'
                            target.write_bytes(local(CHAMPION).read_bytes())
                            need(sha(target) == CHAMPION_SHA, 'pair_champion_deployment_changed')
                            deployment[coor.relative(target)] = CHAMPION_SHA
                        argv = list(arms[arm]['argv'])
                        state.update(status='running', active_arm=arm)
                        state.setdefault('actual_arm_argv', {})[arm] = argv
                        persist()
                        sup = coor.supervise(argv, directory, directory/'supervisor.json', 'regression-'+arm,
                            tick, TASK_SUPERVISOR, SOLVER, deadline, unix, TASK+future,
                            state, persist, frozen, owner, processes, state['coordinator_bootstrap_identities'], SOLVER, 900)
                        coor.child_errors(state, sup)
                        finished.update(coor.identities(sup.get('owned_process_identities', [])))
                        need(sup.get('cleanup_confirmed') is True and sup.get('status') in {'ok', 'child_failed'},
                             'pair_arm_systemic_or_ownership_failure')
                        arm_check = lambda: checkpoint(tick+TASK, 'pair_arm_metadata_seal_over_cap')
                        frozen(tick+TASK, 'pair_arm_metadata_seal_over_cap')
                        proof = coor.task_proof(directory, arm_check)
                        core = coor.core_seal(directory, arm_check)
                        seal_path = OUTPUT/(arm+'-seal.json')
                        coor.save(seal_path, dict(arm=arm, files_sha256=core,
                            cleanup_confirmed=True, source_unchanged=True,
                            sealed_before_independent_label_scoring=True), True)
                        seal_sha = sha(seal_path, arm_check)
                        deployment[coor.relative(seal_path)] = seal_sha
                        # Frozen closed core files are checked during subsequent
                        # B fitting and audit; no outcome-dependent repair/refit.
                        deployment.update(core)
                        entry = dict(sup, arm=arm, kind='regression', code='r', proof=proof,
                            supervisor_path=coor.relative(directory/'supervisor.json'),
                            supervisor_sha256=sha(directory/'supervisor.json', arm_check),
                            seal=dict(path=coor.relative(seal_path), sha256=seal_sha),
                            task_allocation_seconds=TASK, qualified=False,
                            measurement_status='pending_independent_saved_artifact_audit')
                        state['arms'].append(entry)
                        state['active_arm'] = None
                        persist()
                        arm_check()
                    tick = time.monotonic()
                    need(deadline-tick >= AUDIT+CLEANUP, 'pair_audit_cleanup_reserve_unavailable')
                    absence()
                    frozen()
                    state.update(status='verifying', cleanup_confirmed=True, source_unchanged=True)
                    persist()
                    audit_argv = [sys.executable, '-B', '-X', 'utf8', str(local(auditor)),
                        '--work-root', str(WORK), '--pair-root', 'cp1',
                        '--manifest', 'cp1/manifest.json', '--manifest-sha256', state['manifest_sha256'],
                        '--plan', 'cp1/verification-plan.json', '--plan-sha256', state['verification_plan_sha256'],
                        '--self-sha256', args.auditor_sha256, '--output', 'cp1/independent-audit.json']
                    sup = coor.supervise(audit_argv, WORK, OUTPUT/'audit-supervisor.json', 'pair-audit',
                        tick, AUDIT, AUDIT-30, deadline, unix, AUDIT+CLEANUP,
                        state, persist, frozen, owner, processes, state['coordinator_bootstrap_identities'])
                    coor.child_errors(state, sup)
                    finished.update(coor.identities(sup.get('owned_process_identities', [])))
                    need(sup.get('status') == 'ok' and sup.get('exit_code') == 0
                         and sup.get('cleanup_confirmed') is True, 'pair_independent_auditor_process_failed')
                    audit_path = OUTPUT/'independent-audit.json'
                    audit = load(audit_path)
                    state['independent_audit'] = dict(path=coor.relative(audit_path), sha256=sha(audit_path), raw_result=audit)
                    need(audit.get('artifact_procedure_checks_passed') is True
                         and audit.get('audit_within_original_common_clock') is True
                         and audit.get('parent_exec_terminal_qualification_required') is True,
                         'pair_independent_artifact_contract_failed')
                    state.update(status='completed_pair_pending_root_exec_and_closure', qualification='PENDING_ROOT',
                        pair_artifact_checks_passed=True, descriptive_retention_win=audit.get('descriptive_retention_win'))
                except BaseException as exc:
                    error(exc, 'pair_procedure')
                finally:
                    final_end = min(time.monotonic()+CLEANUP, deadline-10)
                    state['finalization_deadline_monotonic'] = final_end
                    try:
                        frozen(final_end, 'pair_final_cleanup_cap_exhausted')
                        absence()
                        need(all(r['cleanup_confirmed'] is True for r in state['supervisors']), 'pair_child_cleanup_unknown')
                        state.update(cleanup_confirmed=True, source_unchanged=True)
                        checkpoint(final_end)
                        persist()
                    except BaseException as exc:
                        error(exc, 'pair_terminal_source_cleanup')
                        state.update(cleanup_confirmed=False, source_unchanged=False)
                    finally:
                        for sig, handler in previous.items():
                            signal.signal(sig, handler)
        need(awake.record.get('release_API_verified') is True, 'pair_power_release_unverified')
        last = awake.record['last_heartbeat']
        checkpoint(final_end, 'pair_terminal_export_cap_exhausted')
        need(max(time.time()-last['unix'], time.monotonic()-last['monotonic']) <= 10,
             'pair_terminal_heartbeat_gap_over10s')
        absence()
    except BaseException as exc:
        error(exc, 'pair_parent')
        state.update(cleanup_confirmed=False, source_unchanged=False)
    finally:
        if awake is not None:
            state['awake_guard'] = awake.record
            if awake.handle is not None:
                try:
                    awake.close()
                except BaseException as exc:
                    error(exc, 'pair_power_release')
        state.update(finished_unix=time.time(), finished_monotonic=time.monotonic(),
            elapsed_common_seconds=time.monotonic()-start_mono,
            owned_process_identities=[dict(pid=pid, create_time=birth) for pid, birth in sorted(finished)])
        if time.monotonic() >= min(deadline-10, final_end if final_end is not None else deadline) or time.time() >= unix-10:
            error(RuntimeError('pair_terminal_export_over_cap'), 'pair_terminal_export')
        persist()
        if time.monotonic() >= min(deadline-10, final_end if final_end is not None else deadline):
            error(RuntimeError('pair_terminal_receipt_write_over_cap'), 'pair_terminal_export')
            persist()
    print(json.dumps({k: state[k] for k in ['status', 'qualification', 'pair_artifact_checks_passed',
        'cleanup_confirmed', 'source_unchanged', 'elapsed_common_seconds', 'root_actual_exec_qualification']}))
    raise SystemExit(0 if state['pair_artifact_checks_passed'] and state['cleanup_confirmed']
                     and state['source_unchanged'] and not state['error_history'] else 1)


if __name__ == '__main__':
    main()
