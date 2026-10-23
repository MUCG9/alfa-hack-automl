"""Inspect by default; explicitly write one new prospective binding after closure.

No coordinator import, prepare, launch, deadline, learner, API or ledger access.
Only reviewed ownership and ResearchLock definitions are imported in --write mode.
"""
from copy import deepcopy
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import time

SOURCE_SHA = '45dd8bc9e56b4874e43e051cf279f0497c0b82f628d5c1db7cb6ec2e2bad8a24'
OWNER_SHA = '8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8'
LOCK_SHA = '78a0441bb3b9ea60197e9a1a6e1087f6e4cd0886593ec54bcfc4e41c9abe5a45'
TM1_MANIFEST_SHA = 'a9cabbff77f0cc795c12ee0cb9afed71f330cdd4c803536ea0be3a2ce73a7e94'
ARCHIVES = {'a': '88dac47a9a815b98b5d00c44e5650518f84db5197c9eac56b79fb1ce465c92a0',
            'b': 'd5144685e682654bfed3a0e216ecec4f2ada4868b7df0e0d9779aba9f79d77bc'}
VERIFIER_SHA = '161a55202d7824f21f954d66455e8449de4056d24fb5912c79a316ac7dca6355'
PLAN_SHA = '662b348fb2b4f04a0ea538615804f7f5e0d8a3ed5c7f8343c623ceddc3093f4c'
KNOWN = {(8148, 1792724976.640077), (1488, 1792724976.6293917), (24548, 1792724980.8335724)}
STATIC = {
    'fullagent_cv_coordinator.py': SOURCE_SHA,
    'support_component_coordinator.py': OWNER_SHA,
    'alfa-hack-automl/tools/research_lock.py': LOCK_SHA,
    'fullagent-cv-supervisor-plan-r1/binding-template-r2.json': 'bab28e48a27538a563089a778d7c72c22a5d8ce85fa8a86a14ffe1923b915568',
    'fullagent-cv-supervisor-plan-r1/source-snapshot-manifest-r3.json': '0c72192e008ccde9ed6b2ea05b1fd3582c3603d8415af151e5c2ddad9e531ae9',
    'fullagent-cv-coordinator-publication-r3.json': '08b75d88ceb8b237d605cdf5dee6c2bb5f29a2a1513eaae72bc0464a17f24e64',
    'four-leaf-default-source-publication-r3.json': 'd4b3ac1ebdbb860d6cb126224807db29de80d997c209aa9a9e206290186c9a51',
    'fullagent-protocol-publication-r3.json': '1c416cc08ea700fc2c6bece457f1f38e46e897bfa1c8cd3c007036a68685be98',
    'fullagent-fixed-half-plan-r3/protocol.json': '5b2164c3721c84b8e6eb85c0dec7571474316b2e956d6ecdeee235d0193addcb',
    'fullagent-cv-stage1-plan-r1/manifest.json': 'f8a0b9ad5b3e9e403aa9a567234ba203c8537c19eee78dd6257d9d8259bb4910',
    'fullagent-cv-stage1-plan-r1/frozen-files.json': '9883c8fe781be541dbbeefe831ea73a3b939628aea09a470e155ee1e1fac1224',
    'fullagent-cv-stage1-binding-r3.json': '7409d72701580d103d8f49200015b6080f3a3ef089a6800f4fcb9c74ecdaa6b0',
    'four-leaf-default-plan-r1/manifest-r3.json': 'd367c6c18b7aecc5e53803897db0d21a3cb7411e644f158d80508cad3f5467c2',
    'close_true_mvp_owned.py': '9e8336f8fe4948cd9b8efe47bd16e88dd4b073c36fe7564c65176ad48bc94c99',
    'run_tm1_classification_audit.py': 'c03c2969aac665abfc9eb065d2bc13ca3e8985a61fb963909dd352b71f38dcc9',
    'finalize_true_mvp_tm1.py': 'a7f5e75f5df2380e23c8d38857e3a7e703a24587beea9dbc536e54f837e3d6a9',
    'verify_true_mvp_tm1.py': VERIFIER_SHA,
    'tm1-independent-verification-plan-r3.json': PLAN_SHA,
    'true-four-stage-launch-r1/manifest.json': TM1_MANIFEST_SHA}
TERMINAL = {
    'closure': 'true-mvp-completion-ownership.json',
    'campaign': 'alfa-hack-automl/test-runs/tm1/campaign.json',
    'launcher': 'true-mvp-launch-receipt.json',
    'r': 'alfa-hack-automl/test-runs/tm1/r/supervisor.json',
    'c': 'alfa-hack-automl/test-runs/tm1/c/supervisor.json',
    'class_guard': 'tm1-classification-audit-guard-r1/supervisor.json',
    'class_audit': 'true-four-stage-classification-independent-tm1.json',
    'summary': 'true-four-stage-terminal-summary-tm1.json',
    'reg_audit': 'true-four-stage-regression-independent-tm1.json'}


class Blocked(RuntimeError):
    """Fixed diagnostic code; no untrusted paths, source text or secrets."""


def require(condition, code):
    if not condition:
        raise Blocked(code)


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            value.update(block)
    return value.hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def path(work, name):
    result = (work / name).resolve()
    require(not Path(name).is_absolute() and result.is_relative_to(work), 'path_outside_work')
    return result


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def identities(value):
    result = set()
    if isinstance(value, dict):
        if 'pid' in value and 'create_time' in value:
            pid, created = value['pid'], value['create_time']
            require(type(pid) is int and pid > 0 and finite(created) and created > 0, 'unverified_identity')
            result.add((pid, float(created)))
        for child in value.values():
            result.update(identities(child))
    elif isinstance(value, list):
        for child in value:
            result.update(identities(child))
    return result


def static_context(work):
    for name, expected in STATIC.items():
        require(path(work, name).is_file(), 'missing_static_reference')
        require(sha(path(work, name)) == expected, 'static_reference_changed')
    template = load(path(work, 'fullagent-cv-supervisor-plan-r1/binding-template-r2.json'))
    snapshot = load(path(work, 'fullagent-cv-supervisor-plan-r1/source-snapshot-manifest-r3.json'))
    for name, expected in snapshot['files_sha256'].items():
        require(sha(path(work, 'fullagent-cv-supervisor-plan-r1/' + name)) == expected, 'snapshot_file_changed')
    require(snapshot['source_sha256'] == SOURCE_SHA, 'snapshot_source_mismatch')
    for name in ['fullagent-cv-coordinator-publication-r3.json', 'four-leaf-default-source-publication-r3.json']:
        receipt = load(path(work, name))
        require(receipt.get('root_source_reviewed') is True and receipt.get('remote_sha_verified') is True
                and receipt.get('archive_sha256') == ARCHIVES and receipt.get('launch_authorized') is False,
                'source_publication_not_reviewed')
    coordinator = load(path(work, 'fullagent-cv-coordinator-publication-r3.json'))
    require(coordinator.get('coordinator_source_sha256') == SOURCE_SHA and
            coordinator.get('independent_verifier_sha256') == template['independent_verifier_sha256'],
            'coordinator_publication_identity_wrong')
    require(template['root_approved_r3'] is True and
            template['root_approved_source_factor'] == 'A_exact88dac_B_backend_plus_default_lastslot_only',
            'source_factor_not_reviewed')
    libraries = {'ownership.py': 'support_component_coordinator.py',
        'awake.py': 'hpo_campaign_coordinator.py',
        'processes.py': 'alfa-hack-automl/src/automl/infrastructure/processes.py',
        'research_lock.py': 'alfa-hack-automl/tools/research_lock.py',
        'verification.py': 'fullagent-cv-supervisor-plan-r1/verification.py'}
    for name, filename in libraries.items():
        require(sha(path(work, filename)) == template['supervisor_library_sha256'][name], 'supervisor_library_changed')
    for arm in ['a', 'b']:
        require(template['arms'][arm]['archive_sha256'] == ARCHIVES[arm], 'archive_factor_changed')
        require(sha(path(work, template['arms'][arm]['archive'])) == ARCHIVES[arm], 'archive_bytes_changed')
    return template


def terminal_context(work):
    missing = [name for name in TERMINAL.values() if not path(work, name).is_file()]
    if missing:
        return None, missing
    refs = {key: {'path': name, 'sha256': sha(path(work, name))} for key, name in TERMINAL.items()}
    data = {key: load(path(work, name)) for key, name in TERMINAL.items()}
    proof, campaign, launcher = data['closure'], data['campaign'], data['launcher']
    require(proof.get('status') == 'completed' and proof.get('cleanup_confirmed') is True and
            proof.get('active_owned_processes') == [] and proof.get('source_input_packet_unchanged') is True and
            proof.get('exclusive_training_lock_acquired') is True and proof.get('no_process_was_signalled') is True,
            'terminal_ownership_proof_incomplete')
    require(proof.get('exec_result_verified') is True and type(proof.get('exec_exit_code')) is int,
            'actual_exec_completion_unverified')
    require(campaign.get('status') in {'completed_qualified_four_stage_mvp', 'completed_unqualified_four_stage_mvp', 'stopped'}
            and campaign.get('source_unchanged') is True and campaign.get('cleanup_confirmed') is True,
            'campaign_not_terminal_clean')
    require(campaign.get('manifest_sha256') == proof.get('manifest_sha256') == TM1_MANIFEST_SHA and
            campaign.get('source_archive_sha256') == ARCHIVES['a'], 'tm1_source_identity_wrong')
    require(finite(campaign.get('finished_unix')) and finite(campaign.get('finished_monotonic')) and
            proof.get('actual_finished_unix') == campaign['finished_unix'], 'actual_terminal_timestamps_missing')
    require(isinstance(launcher.get('status'), str) and launcher['status'] not in {'launching', 'running', 'preparing'} and
            any(finite(launcher.get(key)) for key in ['finished_unix', 'end_unix']), 'launcher_still_active')
    require(proof.get('campaign_receipt_sha256') == refs['campaign']['sha256'] and
            proof.get('launcher_receipt_sha256') == refs['launcher']['sha256'] and
            proof.get('campaign_status') == campaign['status'] and proof.get('launcher_status') == launcher['status'] and
            proof.get('closure_source_sha256') == STATIC['close_true_mvp_owned.py'], 'closure_lineage_mismatch')
    for code in ['r', 'c']:
        supervisor = data[code]
        require(supervisor.get('cleanup_confirmed') is True and isinstance(supervisor.get('status'), str)
                and supervisor['status'] not in {'starting', 'running'}, 'task_not_terminal_clean')
        require(proof['task_supervisors'][code]['sha256'] == refs[code]['sha256'], 'task_supervisor_changed')
    guard, audit, summary = data['class_guard'], data['class_audit'], data['summary']
    require(guard.get('status') == 'PASS' and type(guard.get('exit_code')) is int and guard['exit_code'] == 0 and
            guard.get('cleanup_confirmed') is True and guard.get('source_unchanged') is True,
            'saved_class_audit_execution_not_clean')
    require(guard.get('source_sha256') == VERIFIER_SHA and guard.get('plan_sha256') == PLAN_SHA and
            guard.get('guard_source_sha256') == STATIC['run_tm1_classification_audit.py'] and
            guard.get('threads') == 1 and finite(guard.get('seconds')) and 0 <= guard['seconds'] <= 300 and
            finite(guard.get('peak_owned_rss_mib')) and 0 <= guard['peak_owned_rss_mib'] <= 1024,
            'saved_class_audit_source_or_resource_mismatch')
    require(audit.get('campaign_sha256') == refs['campaign']['sha256'] and
            audit.get('manifest_sha256') == TM1_MANIFEST_SHA and audit.get('runtime_archive_sha256') == ARCHIVES['a'] and
            audit.get('campaign_still_active_at_task_only_verification') is False and
            audit.get('new_model_fits') == audit.get('api_calls') == 0, 'saved_class_audit_lineage_mismatch')
    require(summary.get('status') == 'terminal_core_artifacts_verified_with_explicit_independent_API_limits' and
            summary.get('campaign_sha256') == refs['campaign']['sha256'] and
            summary.get('closure_receipt_sha256') == refs['closure']['sha256'] and
            summary.get('classification_audit_guard_sha256') == refs['class_guard']['sha256'] and
            summary.get('summary_source_sha256') == STATIC['finalize_true_mvp_tm1.py'] and
            summary.get('fresh_owned_processes_absent') is True and
            summary.get('regression_known_API_denial_retried') is False and
            summary.get('new_fits') == summary.get('API_calls') == 0, 'terminal_summary_lineage_mismatch')
    for kind, key in [('classification', 'class_audit'), ('regression', 'reg_audit')]:
        require(summary['tasks'][kind]['audit_sha256'] == refs[key]['sha256'], 'summary_audit_reference_changed')
    require(refs['reg_audit']['sha256'] == 'c9f71c3b48e200079d4ac9e9704e0e0ade8b798d3c8d243e110ee2a6236c1447',
            'preserved_regression_audit_changed')
    require(identities(proof.get('launcher_identities')) == identities(launcher.get('launcher_identities')) and
            len(identities(proof.get('launcher_identities'))) == 2, 'launcher_identity_union_missing')
    known = set().union(*(identities(data[key]) for key in ['closure', 'campaign', 'launcher', 'r', 'c', 'class_guard']))
    require(KNOWN <= known and identities(proof['launcher_identities']) <= identities(proof['tracked_identities']),
            'known_tm1_roots_or_tracking_missing')
    return {'refs': refs, 'known': [{'pid': p, 'create_time': c} for p, c in sorted(known)]}, []


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def strict_orphan_check(owner, known):
    """Supplement the reviewed snapshot only for visible known-parent uncertainty.

    Unrelated protected Windows processes are not rejected for missing fields.
    The PID-reuse exclusion matches frozen45dd before a verified orphan is added.
    """
    import psutil
    observer = owner.StrictOwnedObserver()
    observer.remember((item['pid'], item['create_time']) for item in known)
    require(not observer.observe() and not observer.denials, 'strict_owned_identity_or_traversal_unresolved')
    try:
        entries = list(psutil.process_iter(['pid', 'ppid', 'create_time', 'status'], ad_value=None))
    except psutil.AccessDenied:
        raise Blocked('orphan_inventory_enumeration_denied') from None
    changed = True
    while changed:
        changed = False
        for process in entries:
            info = process.info
            for parent_pid, parent_created in tuple(observer.seen):
                if info.get('ppid') != parent_pid:
                    continue
                pid, created = info.get('pid', process.pid), info.get('create_time')
                if not finite(created) or created <= 0:
                    observer.denied(pid, None, 'known_parent_orphan_identity', 'AccessDenied_or_unknown_birth_time')
                    raise Blocked('known_parent_orphan_birth_time_unverifiable')
                if created < parent_created or (pid, created) in observer.seen:
                    continue
                try:
                    actual_parent = psutil.Process(parent_pid).create_time()
                    if actual_parent != parent_created and created >= actual_parent:
                        continue  # Child of a reused unrelated parent PID.
                except psutil.NoSuchProcess:
                    pass
                except psutil.AccessDenied:
                    observer.denied(parent_pid, parent_created, 'known_parent_orphan_parent', 'AccessDenied')
                    raise Blocked('known_parent_orphan_parent_unverifiable') from None
                try:
                    current = psutil.Process(pid)
                    if current.create_time() != created or current.ppid() != parent_pid:
                        continue  # Do not adopt a PID that changed after the snapshot.
                    current.status()  # A known-parent status denial is not silently ignored.
                except psutil.NoSuchProcess:
                    continue
                except psutil.AccessDenied:
                    observer.denied(pid, created, 'known_parent_orphan_reverify', 'AccessDenied')
                    raise Blocked('known_parent_orphan_reverification_denied') from None
                observer.remember([(pid, created)])
                changed = True
    require(not observer.final_check()['unresolved'], 'strict_owned_orphan_denied_or_live')
    return [{'pid': pid, 'create_time': created} for pid, created in sorted(observer.seen)]


def write_binding(work, output, template, terminal):
    require(output.parent == work and output.suffix == '.json' and not output.exists(), 'new_top_level_binding_path_required')
    owner = module('_binding_reviewed_ownership', path(work, 'support_component_coordinator.py'))
    owner.configure_work_root(work)
    lock = module('_binding_reviewed_lock', path(work, 'alfa-hack-automl/tools/research_lock.py'))
    before = owner.predecessor_snapshot(terminal['known'])
    require(before['cleanup_confirmed'] is True and not before['active'], 'fresh_owned_predecessor_or_orphan_present')
    before_strict = strict_orphan_check(owner, [*terminal['known'], *before['tracked']])
    lock_path = path(work, 'alfa-hack-automl/test-runs/.owned-research.lock')
    require(lock_path.is_file() and lock_path.stat().st_size > 0, 'existing_training_lock_missing')
    with lock.ResearchLock(lock_path):
        fresh = owner.predecessor_snapshot([*terminal['known'], *before_strict])
        require(fresh['cleanup_confirmed'] is True and not fresh['active'], 'fresh_owned_union_not_gone_under_lock')
        fresh_strict = strict_orphan_check(owner, [*terminal['known'], *fresh['tracked']])
        static_context(work)
        for ref in terminal['refs'].values():
            require(sha(path(work, ref['path'])) == ref['sha256'], 'terminal_readiness_receipt_changed')
        binding = deepcopy(template)
        binding.update(status='completed_binding_for_root_review_preparation_only',
            coordinator_publication_receipt='fullagent-cv-coordinator-publication-r3.json',
            coordinator_publication_receipt_sha256=STATIC['fullagent-cv-coordinator-publication-r3.json'])
        binding['tm1_completion']['sha256'] = {template['tm1_completion']['receipt']: terminal['refs']['closure']['sha256'],
                                             template['tm1_completion']['campaign']: terminal['refs']['campaign']['sha256']}
        binding['terminal_readiness_receipts'] = terminal['refs']
        binding['binding_builder_proof'] = {'source_sha256': sha(Path(__file__)),
            'template_sha256': STATIC['fullagent-cv-supervisor-plan-r1/binding-template-r2.json'],
            'checked_epoch': time.time(), 'fresh_tracked_count': len(fresh['tracked']),
            'fresh_strict_owned_absence': True, 'exclusive_lock_acquired': True,
            'no_predecessor_signalled': True, 'positive_MVP_quality_required': False,
            'independent_API_completeness_required': False, 'ledger_retried': False}
        binding['required_before_prepare'] = ['Root reviews this actual binding; no automatic prepare or launch',
            'Prepare manifest with exact45dd only after root checkpoint; review resulting manifest separately',
            'Actual Stage0 gates and future root-assigned immutable clocks remain mandatory']
        last = owner.predecessor_snapshot([*terminal['known'], *fresh_strict])
        require(last['cleanup_confirmed'] is True and not last['active'], 'last_owned_union_not_gone')
        last_strict = strict_orphan_check(owner, [*terminal['known'], *last['tracked']])
        binding['binding_builder_proof']['fresh_tracked_count'] = len(last_strict)
        binding['binding_builder_proof']['checked_epoch'] = time.time()
        with output.open('x', encoding='utf-8') as stream:
            json.dump(binding, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
    return {'status': 'new_binding_written_for_root_review', 'binding': output.name, 'sha256': sha(output),
            'coordinator_imported': False, 'prepare_executed': False, 'launch_executed': False,
            'deadline_assigned': False, 'fits': 0, 'api_calls': 0, 'promotion': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--write', action='store_true', help='Write one NEW binding only after actual terminal readiness and fresh ownership/lock proof')
    parser.add_argument('--output', default='fullagent-cv-launch-binding-r1.json', help='New top-level work JSON; never overwrite')
    args = parser.parse_args()
    work = args.work_root.expanduser().resolve()
    try:
        template = static_context(work)
        terminal, missing = terminal_context(work)
        if missing:
            answer = {'status': 'blocked_inspection_only', 'missing': missing, 'binding_written': False,
                'fresh_process_check_executed': False, 'deadline_assigned': False, 'fits': 0, 'api_calls': 0}
            print(json.dumps(answer))
            raise SystemExit(1 if args.write else 0)
        if not args.write:
            print(json.dumps({'status': 'inspection_only_actual_terminal_refs_present', 'binding_written': False,
                'fresh_process_check_executed': False, 'fresh_ownership_and_lock_required_on_write': True,
                'coordinator_imported': False, 'deadline_assigned': False, 'fits': 0, 'api_calls': 0}))
            return
        print(json.dumps(write_binding(work, path(work, args.output), template, terminal)))
    except Exception as exc:
        print(json.dumps({'status': 'blocked', 'code': str(exc) if isinstance(exc, Blocked) else type(exc).__name__,
            'binding_written': False, 'coordinator_imported': False, 'deadline_assigned': False,
            'fits': 0, 'api_calls': 0, 'launch_executed': False}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
