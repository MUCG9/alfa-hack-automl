"""One prospective serial technical Stage0; never a model-quality experiment.

Launch only after the pinned actual KERN00 and historical fresh ownership closure.
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
OUTPUT = WORK/'ls0'
BASE = 'm4packet/manifest.json'
BASE_SHA = '8faf33cd81c0e864bcf338828c34447000111eda85bc719b8f43312d2babae9a'
COORDINATOR = 'run_lean_mvp_r2.py'
COORDINATOR_SHA = '43be86ece6c453641afdcc6f8eccef02d713986e2ac8bf3314756f0bb78e0818'
PROTOCOL = 'loss-seed-stage0-next-dev/protocol.json'
PROTOCOL_SHA = 'b0c5f0081e3c2876bec5b70ccbf14b2d067fa60c423b0d9e3929a2a7f49d534d'
PREPARED_BASE_REF = 'loss-stage0-packet/manifest.json'
PREPARED_BASE_SHA = '319d6035162f46e6a1272a833d5f8668c731294b443eeae2dd8fc8c897dabfdc'
PREPARER = 'loss-seed-stage0-next-dev/prepare_source.py'
PREPARER_SHA = 'a38afa862c6a0bf222317694074aadb1d943891c4852c03f4a5b72cf4fac5d85'
LOSS_PINS = {'loss-agent-seed-next-dev/source-handoff.json': '00a41c5c9d9bb4363e58e7c5a98ebd6356b86bbf107a23065249c2958edf2086',
 'loss-agent-seed-next-dev/flat-mapping-static-proof.json': '253aa66749bf178242467d43c87eb82fcf2013b311fd4c94d1b32865c7dedc61',
 'loss-agent-seed-next-dev/flat-test-import-map.json': 'c050a0e72385e8bb4353fb1dcbc642b1b85e1a6016795f23cc2e77041dc46ae2',
 'loss-agent-seed-next-dev/fixture-inventory-closure.json': 'fa4b44fbf4ff30b70f07acc29350edac7d2040ddee3d6686a1ea50190b0bcddf',
 'loss-agent-seed-independent-source-review-r2.json': '7da6c5c52b0b9e924c1146f803d9a214a9710e201add891a599a11698d8b1c1a',
 'loss-selection-next-dev/flat-test-import-map.json': 'b0ecbff853bf2c9c9f0621ac8fdaa14a86acecdff4ec9942ad1b2433d592dd69'}
LOSS_TEST_SHA = '5c26ac47d7ca1299bad73baa64ce7bfbd9793c99fffad60ad971bc9ff9a4dc14'
SEED_TEST_SHA = '5ecaf144a615989073ba34cf6b5b37cd57c4c402d65cbd1e7bf190ccf8624d4b'
TERMINAL = {'loss0/terminal-root-closure.json': ('c4916f2e7c7bd38e394bcb2ab33a51daf7a472a2aec8e08ff4b8a79a8fd5ba69',
                                      99080,
                                      0),
 'kern-checks/terminal-root-closure.json': ('fef1f0342a991a76c6d1e99ed408d4660f738b11b31726ac78f991757d69f0f0',
                                            None,
                                            0),
 'queue-checks/terminal-root-closure.json': ('4006102127dd971c97843642754a748fc97199e20505c037f1688a80b8e12d27',
                                             None,
                                             1),
 'queue-checks-r2/terminal-root-closure.json': ('887a4b82614ca18d4589102a9f385d513e96ff5562dcb56ca3d2f95b6a186c34',
                                                None,
                                                0),
 'meth03l/terminal-root-closure.json': ('e02fd31162f1db27342895901ebb52764b140d59f9cd7651c9be447283bd3b9d',
                                        63424,
                                        0),
 'meth02b/terminal-root-closure.json': ('fe00067cb099fdd4fdcd036861f5c3d55cd1c9ee0ee75bcddf488cfc035fe7f7',
                                        38041,
                                        0),
 'meth02/terminal-root-closure.json': ('220e7c93f56eaa4a9c2e09ce70aa3ba406d864686cc68520bf69eace4ed75361',
                                       None,
                                       1),
 'meth03/terminal-root-closure.json': ('901f3c928d95d992800aef808ff70f84768a456bc23235e0ae63fd539fe159bf',
                                       33253,
                                       0),
 'meth01/terminal-root-closure.json': ('2c67361da8f95875b35d124ac6c19d6cccba28c899f1e20dada88f3bec4ea283',
                                       3417,
                                       0),
 'cp1/terminal-root-closure.json': ('96f5d956fa235cfd0904d55f67aeeaae8c93a083391fe8b370836f6e39ba309d',
                                    43472,
                                    0),
 'cs0/terminal-root-closure.json': ('06d20ce5b1bfd51ceefc924f8d09eb06b4022e9998bcef4d36343cb58669fba8',
                                    79591,
                                    0),
 'm4packet/terminal-root-closure.json': ('d19648a53253c0b070fe12068d6eafef5569e2d51332d9b212ef44cc828b9ddc',
                                         65008,
                                         0),
 'loss01/terminal-root-closure.json': ('ce6accf1ec6b6f1e0c14dbb0c8913b55538f6a460450cbb2705ae36a37d3bcf3',
                                       68631,
                                       0)}
HISTORY = {
    't7-report-publication-closure-r2.json':'154eca18b219f8c62ec79ec391da2b09fa59c891fcb444e96732e1c2f1afed20',
    'method-update-publication-closure-r1.json':'93bd05d3ff741eadf9bfc8858c875e8c130ec2aadc216c77e9480283b2692030'}
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
         and result.get('unique_checks_passed') == 499
         and result.get('unique_checks_skipped') == 0, 'source499_counts_or_skips_failed')


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


def test_methods(source):
    return {node.name:ast.dump(node,include_attributes=False)
            for cls in ast.parse(source).body if isinstance(cls,ast.ClassDef)
            for node in cls.body if isinstance(node,ast.FunctionDef) and node.name.startswith('test_')}


def flat_imports(source,mapping,remove_src):
    changed=source;rewrites={}
    if remove_src:
        need(changed.count("str(ROOT/'src')")==1,'stage0_flat_ROOT_marker_changed')
        changed=changed.replace("str(ROOT/'src')",'str(ROOT)')
        rewrites["str(ROOT/'src')"]='str(ROOT)'
    special='from automl.execution import worker'
    if special in changed:
        need(changed.count(special)==1,'stage0_flat_worker_import_marker_changed')
        changed=changed.replace(special,'import automl_worker as worker')
        rewrites[special]='import automl_worker as worker'
    special='from automl.search import runner'
    if special in changed:
        need(changed.count(special)==1,'stage0_flat_runner_import_marker_changed')
        changed=changed.replace(special,'import automl_runner as runner')
        rewrites[special]='import automl_runner as runner'
    for old,new in mapping.items():
        pattern=r'(^[ \t]*from )'+re.escape(old)+r'( import )'
        changed,count=re.subn(pattern,lambda m:m.group(1)+new+m.group(2),changed,flags=re.MULTILINE)
        if count:rewrites[old]=dict(flat=new,count=count)
    need(not any(isinstance(n,ast.ImportFrom) and n.module and n.module.startswith('automl.')
                 for n in ast.walk(ast.parse(changed))),'stage0_flat_unmapped_project_import')
    compile(changed,'import_only_flat_LOSS_contract','exec')
    return changed,rewrites


def main():
    global FAILURE_TYPE
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--launch', action='store_true', required=True)
    p.add_argument('--self-sha256', required=True)
    p.add_argument('--prepared-manifest-sha256', required=True)
    p.add_argument('--parent-terminal-closure-sha256', required=True)
    p.add_argument('--parent-exec-session', type=int, required=True)
    p.add_argument('--parent-exec-exit-code', type=int, required=True)
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
        source = WORK/'lsdev'
        actual_python = {q.relative_to(source).as_posix() for folder in ['src', 'tests', 'tools']
                         for q in (source/folder).rglob('*.py')}
        expected_python = {n.removeprefix('lsdev/') for n in pins if n.startswith('lsdev/')
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
        for name, digest in {COORDINATOR: COORDINATOR_SHA, BASE: BASE_SHA, PROTOCOL: PROTOCOL_SHA,
                PREPARER: PREPARER_SHA, **LOSS_PINS,
                PREPARED_BASE_REF:PREPARED_BASE_SHA, **DEPS}.items():
            need(sha(local(name), lambda: checkpoint(start_mono+SOURCE)) == digest, 'stage0_dependency_pin_failed')
            merge(pins, name, digest)
        coor = imported('_loss_stage0_proven_coordinator', local(COORDINATOR))
        # Preserve precise first guard causes in the reused supervisor receipt.
        FAILURE_TYPE = coor.TechnicalFailure
        base = read(local(BASE))
        for name, digest in base['immutable_files'].items():
            merge(pins, name, digest)
        manifest_ref = 'ls-stage0-packet/manifest.json'
        need(sha(local(manifest_ref)) == args.prepared_manifest_sha256, 'stage0_prepared_manifest_pin_failed')
        prepared = read(local(manifest_ref))
        prior=read(local(PREPARED_BASE_REF))
        overlay=read(local('loss-agent-seed-next-dev/source-handoff.json'))
        closure=read(local('loss-agent-seed-next-dev/fixture-inventory-closure.json'))
        flat_proof=read(local('loss-agent-seed-next-dev/flat-mapping-static-proof.json'))
        expected_union=set(prior['source_files_sha256'])|set(closure['new_test_fixture_sha256'])
        expected_overlay={**{name:overlay['files_sha256'][name] for name in overlay['scheduler_modified_paths']},
                          **closure['new_test_fixture_sha256']}
        expected_compiled={**prior['compiled_sha256'],
            **{name:entry['candidate_sha256'] for name,entry in flat_proof['changed_vs_tested_LOSS'].items()}}
        need(type(prepared) is dict and type(prepared.get('source_files_sha256')) is dict
             and type(prepared.get('registry')) is dict and type(prepared.get('compiled_sha256')) is dict,
             'stage0_prepared_JSON_types_changed')
        need(prepared['registry']=={**prior['registry'],'test_loss_seed.py':12}
             and prepared['source_root']=='lsdev' and prepared['source_expected_checks']==499
             and prepared['source_skipped_expected']==0 and sum(prepared['registry'].values())==499
             and prepared['exact_repeated_expected_checks']==23 and prepared['exact_flat_loss_checks']==16
             and prepared['exact_flat_seed_checks']==12 and prepared['exact_flat_combined_checks']==28
             and prepared['base_manifest_sha256']==PREPARED_BASE_SHA
             and prepared['base_archive_sha256']==prior['archive_sha256']
             and prepared['self_sha256']==PREPARER_SHA
             and prepared['original_loss_test_sha256']==LOSS_TEST_SHA
             and prepared['original_seed_test_sha256']==SEED_TEST_SHA
             and prepared['overlay_handoff_sha256']==LOSS_PINS['loss-agent-seed-next-dev/source-handoff.json']
             and set(prepared['source_files_sha256'])==expected_union
             and prepared['source_union_count']==len(expected_union)==len(prepared['source_files_sha256'])
             and prepared['base_source_file_count']==len(prior['source_files_sha256'])
             and prepared['overlay_files_sha256']==expected_overlay
             and all(prepared['source_files_sha256'][name]==digest for name,digest in expected_overlay.items())
             and all(prepared['source_files_sha256'][name]==digest for name,digest in prior['source_files_sha256'].items()
                     if name not in set(overlay['scheduler_modified_paths'])|{'tools/run_checks.py'})
             and prepared['source_files_sha256']['tests/fixtures/cp1_fixture_sha.json']==prior['source_files_sha256']['tests/fixtures/cp1_fixture_sha.json']
             and prepared['unchanged_flat_members']==66
             and prepared['changed_flat_modules']==['automl_runner.py','automl_search_stages.py']
             and prepared['compiled_sha256']==expected_compiled and len(prepared['compiled_sha256'])==68,
             'stage0_prepared_contract_changed')
        merge(pins, manifest_ref, args.prepared_manifest_sha256)
        merge(pins, prepared['archive'], prepared['archive_sha256'])
        merge(pins, Path(__file__).resolve().relative_to(WORK).as_posix(), args.self_sha256)
        for name, digest in prepared['source_files_sha256'].items():
            merge(pins, 'lsdev/'+name, digest)
        owner = imported('_loss_stage0_owner', local(coor.LIBS['owner']))
        processes = imported('_loss_stage0_processes', local(coor.LIBS['processes']))
        locker = imported('_loss_stage0_lock', local(coor.LIBS['lock']))
        guard_class = imported('_loss_stage0_awake', local(coor.AWAKE)).PowerRequestGuard
        awake = guard_class('Alfa LOSS seed Stage0 technical pid'+str(os.getpid()), 10)
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
            predecessor_KERN00_exec_session=args.parent_exec_session,
            predecessor_KERN00_exec_exit_code=args.parent_exec_exit_code)
        parent_ref='kern0/terminal-root-closure.json'
        need(args.parent_exec_exit_code==0,'actual_terminal_KERN00_exit0_required')
        dynamic=[(parent_ref,args.parent_terminal_closure_sha256,args.parent_exec_session,args.parent_exec_exit_code)]
        dynamic.extend((name,digest,session,exitcode) for name,(digest,session,exitcode) in TERMINAL.items())
        dynamic.extend((name,digest,'not_checked','not_checked') for name,digest in HISTORY.items())
        for value in args.extra_terminal_receipt:
            name,digest=value.rsplit('=',1)
            dynamic.append((name,digest,'not_checked','not_checked'))
        root_refs=[]
        for name,digest,session,exitcode in dynamic:
            need(sha(local(name),lambda:checkpoint(start_mono+SOURCE)) == digest,
                 'stage0_terminal_closure_pin_failed')
            proof=read(local(name))
            need(proof.get('cleanup_confirmed') is True and proof.get('source_unchanged') is True
                 and proof.get('active_owned_processes',[]) == [] and proof.get('uncertain_owned',[]) == [],
                 'stage0_terminal_closure_not_clean')
            need(proof.get('owned_identities') and proof.get('closure_preparer_identities'),
                 'stage0_terminal_complete_identity_and_preparer_union_required')
            if session != 'not_checked':
                need(proof.get('actual_exec_session') == session
                     and proof.get('actual_exec_exit_code_observed_by_root') == exitcode,
                     'stage0_root_observed_predecessor_exec_binding_failed')
            if name==parent_ref:
                need(proof.get('technical_procedure_passed') is True
                     and proof.get('source_checks')==483 and proof.get('source_skipped')==0
                     and proof.get('exact_default_repeated')==23 and proof.get('exact_flat_same_KERN_contracts')==12,
                     'actual_KERN00_technical_root_proof_required')
            previous_ids.update(coor.identities(proof['owned_identities']))
            previous_ids.update(coor.identities(proof['closure_preparer_identities']))
            merge(pins,name,digest)
            root_refs.append(dict(path=name,sha256=digest,actual_exec_session=session,
                actual_exec_exit_code_observed_by_root=exitcode))
        # Consume only real declared identities, never analytical edges, names or PPID scans.
        # The original METH02 exit1/null session remains a failed predecessor, not renamed.
        state.update(terminal_predecessor_receipts=root_refs,
            prior_METH02_actual_failure_preserved=True,immutable_files=pins,
            awake_guard=awake.record,_manifest={},_pulse=lambda:checkpoint())
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
                    phase([sys.executable, '-B', '-X', 'utf8', str(WORK/'lsdev/tools/run_checks.py'),
                           '--output', str(OUTPUT/'source')], WORK/'lsdev', 'source',
                          start_mono, SOURCE, min(570, cap_left-30), EXACT+FINAL)
                    source_result = read(OUTPUT/'source/results.json')
                    check_counts(source_result, prepared['registry'])
                    state['gates'].append(dict(name='source', passed=True, checks=499,
                        result='ls0/source/results.json', sha256=sha(OUTPUT/'source/results.json')))
                    exact_start = time.monotonic()
                    exact_end = exact_start+EXACT
                    checkpoint(deadline-FINAL, 'stage0_final_reserve_unavailable')
                    absence()
                    phase([sys.executable, '-B', '-X', 'utf8', str(WORK/'lsdev/tools/verify_release.py'),
                           '--archive', str(local(prepared['archive'])), '--output', str(OUTPUT/'exact.json'),
                           '--timeout', '120', '--memory-gb', '1.2'], WORK/'lsdev', 'exact',
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
                    # The exact same16 test bodies/assertions execute against flat modules.
                    # The legacy CP1 adapter fixture imports need the same mapping;
                    # its SHA sidecar is explicitly rebound to import-only fixture bytes.
                    mapping=read(local('loss-selection-next-dev/flat-test-import-map.json'))['module_map']
                    fixture=flat/'tests/fixtures';fixture.mkdir(parents=True)
                    test_source=WORK/'lsdev/tests/test_loss_profiles.py'
                    original=test_source.read_text('utf-8')
                    need(sha(test_source)==LOSS_TEST_SHA,'stage0_LOSS_test_pin_failed')
                    changed,test_rewrites=flat_imports(original,mapping,True)
                    before_methods=test_methods(original);after_methods=test_methods(changed)
                    need(len(before_methods)==16 and before_methods==after_methods,
                         'stage0_LOSS_test_bodies_or_assertions_changed')
                    (flat/'tests/test_loss_profiles.py').write_text(changed,encoding='utf-8')
                    old_fixture=WORK/'lsdev/tests/fixtures/cp1_lightgbm.py'
                    fixture_code,fixture_rewrites=flat_imports(old_fixture.read_text('utf-8'),mapping,False)
                    (fixture/'cp1_lightgbm.py').write_text(fixture_code,encoding='utf-8')
                    raw_meta=read(WORK/'lsdev/tests/fixtures/cp1_fixture_sha.json')
                    need(set(raw_meta)=={'lightgbm'} and raw_meta['lightgbm']==sha(old_fixture),
                         'stage0_raw_CP1_fixture_hash_failed')
                    flat_meta={'lightgbm':sha(fixture/'cp1_lightgbm.py')}
                    (fixture/'cp1_fixture_sha.json').write_text(json.dumps(flat_meta,indent=2)+'\n',encoding='utf-8')
                    (fixture/'cp1_capabilities.json').write_bytes((WORK/'lsdev/tests/fixtures/cp1_capabilities.json').read_bytes())
                    seed_source=WORK/'lsdev/tests/test_loss_seed.py'
                    need(sha(seed_source)==SEED_TEST_SHA,'stage0_seed_test_pin_failed')
                    seed_text,seed_rewrites=flat_imports(seed_source.read_text('utf-8'),mapping,True)
                    need(len(test_methods(seed_text))==12 and test_methods(seed_text)==test_methods(seed_source.read_text('utf-8')),
                         'stage0_seed_test_bodies_or_assertions_changed')
                    (flat/'tests/test_loss_seed.py').write_text(seed_text,encoding='utf-8')
                    seed_fixture=WORK/'lsdev/tests/fixtures/cp1_stages.py'
                    seed_fixture_text,seed_fixture_rewrites=flat_imports(seed_fixture.read_text('utf-8'),mapping,False)
                    (fixture/'cp1_stages.py').write_text(seed_fixture_text,encoding='utf-8')
                    seed_meta=read(WORK/'lsdev/tests/fixtures/loss_seed_cp1_fixture_sha.json')
                    need(set(seed_meta)=={'stages'} and seed_meta['stages']==sha(seed_fixture),
                         'stage0_raw_seed_CP1_fixture_hash_failed')
                    (fixture/'loss_seed_cp1_fixture_sha.json').write_text(json.dumps({'stages':sha(fixture/'cp1_stages.py')},indent=2)+'\n',encoding='utf-8')
                    for name in ['cp1_champion_regression.json','fixed_l1_seed_template.json','protected_control_regression.json']:
                        (fixture/name).write_bytes((WORK/'lsdev/tests/fixtures'/name).read_bytes())
                    state['flat_seed_adaptation']=dict(original_test_sha256=sha(seed_source),
                        transformed_test_sha256=sha(flat/'tests/test_loss_seed.py'),test_methods=12,
                        test_rewrites=seed_rewrites,fixture_rewrites=seed_fixture_rewrites,
                        original_fixture_sha256=sha(seed_fixture),transformed_fixture_sha256=sha(fixture/'cp1_stages.py'),
                        assertion_changes=0,test_bodies_AST_equal=True,source_package_imported=False,
                        metadata_change='Only namespace-specific expected SHA of import-only adapted CP1 stages fixture')
                    for q in flat.rglob('*'):
                        if q.is_file():deployment[q.relative_to(WORK).as_posix()]=sha(q)
                    state['flat_loss_adaptation']=dict(original_test_sha256=sha(test_source),
                        transformed_test_sha256=sha(flat/'tests/test_loss_profiles.py'),test_methods=16,
                        test_rewrites=test_rewrites,fixture_rewrites=fixture_rewrites,
                        original_fixture_sha256=sha(old_fixture),transformed_fixture_sha256=flat_meta['lightgbm'],
                        original_fixture_metadata_sha256=sha(WORK/'lsdev/tests/fixtures/cp1_fixture_sha.json'),
                        transformed_fixture_metadata_sha256=sha(fixture/'cp1_fixture_sha.json'),
                        assertion_changes=0,test_bodies_AST_equal=True,source_package_imported=False,
                        metadata_change='Only expected SHA of import-only adapted CP1 fixture; raw source remains pinned')
                    state['flat_deployment_sha256']=dict(deployment)
                    tick = time.monotonic()
                    left = exact_end-tick
                    need(left > 15, 'stage0_flat_contract_exact_allocation_unavailable')
                    phase([sys.executable, '-B', '-X', 'utf8', '-m','unittest','discover','-s',str(flat/'tests'),'-p','test_loss*.py','-v'],
                          flat, 'exact-optin', tick, left, left-10, FINAL)
                    text = (OUTPUT/'exact-optin-supervisor.log').read_text('utf-8')
                    need(re.findall(r'Ran (\d+) tests? in ', text) == ['28'] and '\nOK\n' in text
                         and 'skipped=' not in text, 'stage0_flat_LOSS16_seed12_contracts_failed')
                    state['gates'].extend([dict(name='exact-default', passed=True, checks=23,
                        result='ls0/exact.json', sha256=sha(OUTPUT/'exact.json')),
                        dict(name='exact-optin', passed=True, checks=28,
                        same_test_bodies_and_assertions=True,
                        log='ls0/exact-optin-supervisor.log', sha256=sha(OUTPUT/'exact-optin-supervisor.log'))])
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
            manifest_ref, COORDINATOR, PROTOCOL, PREPARER, *LOSS_PINS,
            *TERMINAL, *HISTORY, *DEPS, *[ref['path'] for ref in root_refs]]
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
