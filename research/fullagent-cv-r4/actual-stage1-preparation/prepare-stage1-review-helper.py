"""Prepare saved Stage0 evidence for a separate root Stage1 decision; never launch.

Default mode reports this source's pins only. After root source review and actual
exec-session73599 exit0, --write --expect-source-sha256 <reviewed SHA>
--confirmed-exec-session 73599 --confirmed-exec-exit-code 0 creates one new
work/fullagent-cv-stage1-review-r4 directory. It neither replaces packet/review.json
nor assigns a Stage1 clock. The explicit exec arguments are root attestations;
saved launcher/gate/source evidence and fresh owned absence are checked separately.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import os
import sys
import tempfile
import time


WORK = Path(__file__).resolve().parent
PACKET = WORK / 'fullagent-cv-launch-r4'
OUTPUT = WORK / 'fullagent-cv-stage1-review-r4'
SOURCE_SHA = 'b85d04ec335a6cccefd3ed5214d05ea196fc4a62b619a054644b568c6d05d627'
MANIFEST_SHA = 'a70f2a0cefb686dd04535c76b4c9e9e80073aba23d86fd7aad7e52fc7b9eee6a'
BINDING_SHA = 'd106e33958fbd553561df602609f69bc8eca827c6fd2b5ab60ed63bfa8bf51f4'
BUILDER_SHA = '84a519c3f6a916c82c568be1944f5c9e0fac6409b5ac50f8fbafac2a7398b5ff'
WRAPPER_SHA = '12e420432c338f511b5f26a56a509e461987def53499f59b40cc847f7974ccdd'
STAGE0_REVIEW_SHA = 'f151c6013fb0e484885a41126cb5495ab987ab5e035a1e5ad42d814980eb42d4'
STAGE0_PUBLICATION_SHA = '0c35d57fa0faf4cfdcd494e2e7e1b54e4139b584b6ac410cc073ae455eab2c75'
LIBRARY_SHA = {
    'ownership.py': '8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8',
    'research_lock.py': '78a0441bb3b9ea60197e9a1a6e1087f6e4cd0886593ec54bcfc4e41c9abe5a45',
}
GATES = ('a_source', 'b_source', 'a_exact', 'b_exact')
EXEC_SESSION = 73599


class ReviewPreparationError(RuntimeError):
    pass


def require(condition, code):
    if not condition:
        raise ReviewPreparationError(code)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def relative(path):
    return Path(path).resolve().relative_to(WORK).as_posix()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def pins():
    manifest = load(PACKET / 'manifest.json')
    require(digest(WORK / 'fullagent_cv_coordinator_r4.py') == SOURCE_SHA, 'coordinator_changed')
    require(digest(PACKET / 'manifest.json') == MANIFEST_SHA, 'manifest_changed')
    require(manifest.get('coordinator_sha256') == SOURCE_SHA and
            manifest.get('source_binding_sha256') == BINDING_SHA and
            len(manifest.get('immutable_files', {})) == 430, 'manifest_lineage_changed')
    require(digest(WORK / 'fullagent-cv-launch-binding-r4.json') == BINDING_SHA and
            digest(PACKET / 'source-binding.json') == BINDING_SHA, 'binding_changed')
    require(digest(WORK / 'build_fullagent_cv_binding.py') == BUILDER_SHA, 'strict_builder_changed')
    require(digest(WORK / 'launch_cv_stage0_r4.py') == WRAPPER_SHA, 'stage0_wrapper_changed')
    require(digest(PACKET / 'review.json') == STAGE0_REVIEW_SHA, 'preserve_stage0_review')
    require(digest(WORK / 'fullagent-cv-stage0-publication-r4.json') == STAGE0_PUBLICATION_SHA,
            'stage0_publication_changed')
    for name, expected in LIBRARY_SHA.items():
        require(digest(PACKET / name) == expected, 'ownership_or_lock_library_changed')
    for name, expected in manifest['immutable_files'].items():
        require(digest(WORK / name) == expected, 'immutable_changed')
    return manifest


def terminal_context(cv, manifest):
    """Read only saved actual terminal evidence; do not poll or reconstruct it."""
    stage_path = WORK / 'f4/stage0.json'
    launcher_path = WORK / 'fullagent-cv-stage0-launch-r4.json'
    stage, launcher = load(stage_path), load(launcher_path)
    require(launcher.get('status') == 'stage0_exec_completed' and
            type(launcher.get('exec_exit_code')) is int and launcher['exec_exit_code'] == 0,
            'stage0_wrapper_not_terminal_exec0')
    require(launcher.get('stage') == 'stage0' and launcher.get('manifest_sha256') == MANIFEST_SHA and
            launcher.get('source_sha256') == SOURCE_SHA and launcher.get('wrapper_sha256') == WRAPPER_SHA and
            launcher.get('root_review_sha256') == STAGE0_REVIEW_SHA,
            'stage0_launcher_lineage_changed')
    require(stage.get('status') == 'completed_stage0_pass' and stage.get('stage') == 'stage0' and
            stage.get('gates_passed') is True and stage.get('cleanup_confirmed') is True and
            stage.get('source_unchanged') is True and stage.get('manifest_sha256') == MANIFEST_SHA,
            'stage0_not_complete_clean_pass')
    final_owned = stage.get('final_owned_recheck') or {}
    require(final_owned.get('unresolved') == [] and final_owned.get('denial_count') == 0,
            'stage0_final_owned_recheck_uncertain')
    require(stage.get('common_seconds') == stage.get('stage_cap_seconds') == 3600 and
            launcher.get('common_seconds') == 3600 and
            stage.get('absolute_deadline_unix') == launcher.get('absolute_deadline_unix') ==
            stage.get('common_absolute_deadline_unix'), 'original_stage0_clock_mismatch')
    for record in (stage, launcher):
        require(all(finite(record.get(k)) for k in ('start_unix', 'end_unix', 'absolute_deadline_unix')) and
                record['start_unix'] <= record['end_unix'] <= record['absolute_deadline_unix'],
                'stage0_outside_original_clock')
    require(finite(stage.get('seconds')) and 0 <= stage['seconds'] <= 3600 and
            finite(launcher.get('elapsed_seconds')) and 0 <= launcher['elapsed_seconds'] <= 3600 and
            launcher['start_unix'] <= stage['start_unix'] <= stage['end_unix'] <= launcher['end_unix'],
            'stage0_saved_timing_incomplete')
    require(abs(stage['common_start_unix'] - launcher['start_unix']) < .001 and
            stage.get('prior_failed_clock_reset_or_extended') is False and
            launcher.get('prior_failed_clock_reset_or_extended') is False,
            'stage0_clock_not_separate_technical_attempt')
    require(stage.get('API_limit') == 0 and launcher.get('stage1_started') is False and
            stage.get('stage2_started') is False and stage.get('pairs') == [] and
            stage.get('complete_CV') is False and stage.get('OOF_complete') is False and
            stage.get('final_CV') is None and stage.get('full_three_fold_macro_f1_mean') is None and
            stage.get('full_pooled_macro_f1') is None and stage.get('promotion') is False,
            'unexpected_CV_or_quality_claim_before_stage1')
    require(len(stage.get('arms', [])) == 6 and all(
        slot.get('status') == 'not_attempted' and slot.get('metrics') is None for slot in stage['arms']),
        'CV_arms_already_attempted')
    require([r.get('name') for r in stage.get('gates', [])] == list(GATES),
            'all_four_actual_gates_required_in_order')
    refs = {relative(stage_path): digest(stage_path), relative(launcher_path): digest(launcher_path)}
    known = cv.identities(stage) | cv.identities(launcher)
    summaries = []
    previous_end = stage['start_unix']
    for gate in stage['gates']:
        name = gate['name']
        arm, kind = name.split('_')
        path = WORK / ('f4/gate-' + name + '.json')
        supervisor = load(path)
        require(supervisor == gate.get('supervisor'), 'saved_inline_gate_supervisor_mismatch')
        require(supervisor.get('status') == 'ok' and supervisor.get('exit_code') == 0 and
                supervisor.get('cleanup_confirmed') is True and supervisor.get('API_limit') == 0,
                'gate_not_terminal_clean_exec0')
        observation = supervisor.get('cleanup_observation') or {}
        require(observation.get('unresolved') == [] and observation.get('denial_count') == 0,
                'gate_cleanup_uncertain')
        require(finite(supervisor.get('peak_owned_tree_rss_mib')) and
                0 <= supervisor['peak_owned_tree_rss_mib'] <= 2048 and
                type(supervisor.get('maximum_logical_worker_jobs')) is int and
                0 <= supervisor['maximum_logical_worker_jobs'] <= 1,
                'gate_resource_or_serial_receipt_invalid')
        cap = manifest['stage0_caps'][name]
        require(gate.get('parent_cap_seconds') == cap and
                finite(gate.get('parent_seconds_including_cleanup_and_proof')) and
                0 <= gate['parent_seconds_including_cleanup_and_proof'] <= cap and
                all(finite(supervisor.get(k)) for k in ('start_unix', 'end_unix', 'seconds')) and
                previous_end <= supervisor['start_unix'] <= supervisor['end_unix'] <= stage['end_unix'] and
                0 <= supervisor['seconds'] <= gate['parent_seconds_including_cleanup_and_proof'],
                'gate_individual_cap_or_sequential_timing_invalid')
        previous_end = supervisor['end_unix']
        if kind == 'source':
            result_path = WORK / 'f4/gates' / name / 'results.json'
            proof = cv.source_gate(supervisor, manifest['arms'][arm], result_path.parent)
            result = load(result_path)
            rows = result['checks']
            require(len(rows) == len(manifest['arms'][arm]['registry']) and
                    sum(r['observed_checks'] for r in rows) == manifest['arms'][arm]['expected_source_checks'],
                    'source_duplicate_or_missing_registered_checks')
            summary = {'name': name, 'passed': True, 'checks': result['unique_checks_passed'],
                       'scripts': len(rows), 'skips': result['unique_checks_skipped']}
        else:
            result_path = WORK / 'f4/gates' / (name + '.json')
            proof = cv.exact_gate(supervisor, manifest['arms'][arm], result_path)
            summary = {'name': name, 'passed': True, 'checks': 23, 'scripts': 3, 'skips': 0,
                       'counts': {'test_v2.py': 11, 'test_resilience.py': 7, 'smoke.py': 5}}
            require(sum(manifest['arms'][arm]['registry'][n] for n in summary['counts']) == 23 and
                    all(manifest['arms'][arm]['registry'][n] == c for n, c in summary['counts'].items()),
                    'exact_counts_differ_from_reviewed_registry')
        require(proof == gate.get('proof') and proof.get('passed') is True, 'saved_gate_proof_changed')
        for rel, expected in manifest['arms'][arm]['source_files_sha256'].items():
            require(digest(WORK / 'f4' / ('s' + arm) / rel) == expected, 'deployed_gate_source_changed')
        refs[relative(path)], refs[relative(result_path)] = digest(path), digest(result_path)
        known |= cv.identities(supervisor)
        summaries.append(dict(summary, parent_cap_seconds=cap,
            parent_seconds_including_cleanup_and_proof=gate['parent_seconds_including_cleanup_and_proof'],
            supervised_seconds=supervisor['seconds'], peak_owned_tree_rss_mib=supervisor['peak_owned_tree_rss_mib'],
            supervisor_sha256=digest(path), result_sha256=digest(result_path)))
    require(cv.identities(launcher.get('launcher_identity')) and
            cv.identities(launcher.get('coordinator_launcher_identity')) and
            cv.identities(stage.get('owned_root')), 'actual_stage0_wrapper_or_root_identity_missing')
    return {'stage': stage, 'launcher': launcher, 'refs': refs, 'known': known, 'gates': summaries}


def fresh(owner, builder, identities):
    known = [{'pid': p, 'create_time': c} for p, c in sorted(identities)]
    # The exact reviewed supplementary orphan check uses StrictOwnedObserver and
    # blocks unknown identity/AccessDenied/live children. It sends no signals.
    tracked = builder.strict_orphan_check(owner, known)
    require(set((r['pid'], float(r['create_time'])) for r in tracked) >= identities,
            'fresh_check_omitted_known_identity')
    return tracked


def preparer_identities(psutil):
    """Record this helper and exact same-script Python redirector ancestors only."""
    current = psutil.Process()
    result = [{'pid': current.pid, 'create_time': current.create_time()}]
    parent = current.parent()
    while parent is not None and parent.name().lower() in {'python.exe', 'pythonw.exe'}:
        argv = parent.cmdline()
        matching = [a for a in argv if Path(a).name == Path(__file__).name]
        if not any(Path(a).resolve() == Path(__file__).resolve() for a in matching):
            break
        created = parent.create_time()
        require(psutil.Process(parent.pid).create_time() == created, 'review_preparer_parent_identity_changed')
        result.append({'pid': parent.pid, 'create_time': created})
        parent = parent.parent()
    return result


def execute(args):
    require(args.confirmed_exec_session == EXEC_SESSION and args.confirmed_exec_exit_code == 0,
            'root_actual_exec0_attestation_required')
    own_sha = digest(__file__)
    require(args.expect_source_sha256 == own_sha, 'exact_root_reviewed_helper_sha_required')
    require(not OUTPUT.exists(), 'append_only_review_bundle_already_exists')
    manifest = pins()
    # Test terminal plain JSON before importing any reviewed application helper.
    require(load(WORK / 'fullagent-cv-stage0-launch-r4.json').get('status') == 'stage0_exec_completed' and
            load(WORK / 'f4/stage0.json').get('status') == 'completed_stage0_pass',
            'actual_stage0_not_terminal_pass')
    cv = module('_stage1_review_cv_r4', WORK / 'fullagent_cv_coordinator_r4.py')
    cv.configure(WORK, 'fullagent-cv-launch-r4')
    owner = module('_stage1_review_owner', PACKET / 'ownership.py')
    builder = module('_stage1_review_strict_builder', WORK / 'build_fullagent_cv_binding.py')
    lock_module = module('_stage1_review_lock', PACKET / 'research_lock.py')
    import psutil
    cv.guard(manifest)
    context = terminal_context(cv, manifest)
    before = fresh(owner, builder, context['known'])
    with lock_module.ResearchLock(WORK / 'alfa-hack-automl/test-runs/.owned-research.lock') as lock:
        self_identity = {'pid': os.getpid(), 'create_time': psutil.Process().create_time()}
        lock.write_identity(self_identity)
        pins()
        cv.guard(manifest)
        current = terminal_context(cv, manifest)
        require(current['refs'] == context['refs'], 'terminal_evidence_changed_during_review')
        tracked = fresh(owner, builder, current['known'] | cv.identities(before))
        own_identities = preparer_identities(psutil)
        recorded = time.time()
        refs = dict(current['refs'], **{
            'fullagent_cv_coordinator_r4.py': SOURCE_SHA,
            'fullagent-cv-launch-r4/manifest.json': MANIFEST_SHA,
            'fullagent-cv-launch-binding-r4.json': BINDING_SHA,
            'launch_cv_stage0_r4.py': WRAPPER_SHA,
            'fullagent-cv-launch-r4/review.json': STAGE0_REVIEW_SHA,
            'fullagent-cv-stage0-publication-r4.json': STAGE0_PUBLICATION_SHA,
            'prepare_cv_stage1_review_r4.py': own_sha})
        closure = {'status': 'completed_Stage0_terminal_owned_absence_confirmed',
            'recorded_epoch': recorded, 'source_sha256': SOURCE_SHA, 'manifest_sha256': MANIFEST_SHA,
            'stage_status': current['stage']['status'], 'cleanup_confirmed': True,
            'active_owned_processes': [], 'fresh_absence_before_and_inside_canonical_lock': True,
            'strict_known_parent_orphan_scan': True, 'no_process_signalled': True,
            'tracked_identities': tracked, 'known_saved_identity_count': len(current['known']),
            'root_confirmed_exec_session': args.confirmed_exec_session,
            'root_confirmed_exec_exit_code': args.confirmed_exec_exit_code,
            'saved_launcher_exec_exit_code': current['launcher']['exec_exit_code'],
            'exec_observation_limit': 'Tool-session exit is explicitly attested by root; saved wrapper child exit and all exact owned identities are verified separately.',
            'review_preparer_identity': self_identity,
            'review_preparer_identities': own_identities,
            'review_preparer_must_be_absent_before_future_stage1_launch': True,
            'source_unchanged': True, 'immutable_files_rehashed': 430,
            'evidence_sha256': refs, 'original_Stage0_absolute_deadline_unix': current['stage']['absolute_deadline_unix'],
            'stage1_started': False, 'new_clock_assigned': False, 'new_fits': 0, 'API_calls': 0,
            'promotion': False, 'official_submission': False}
        aggregate = {'status': 'actual_R4_Stage0_technical_gates_verified_ready_for_root_Stage1_review',
            'source_sha256': SOURCE_SHA, 'manifest_sha256': MANIFEST_SHA,
            'gates': current['gates'], 'all_four_gates_passed': True,
            'source_checks': {'a': 451, 'b': 468}, 'source_scripts': {'a': 46, 'b': 48},
            'exact_checks_per_arm': 23, 'exact_scripts_per_arm': 3, 'skips': 0,
            'original_stage0_common_seconds': 3600, 'actual_stage0_seconds': current['stage']['seconds'],
            'original_stage0_end_unix': current['stage']['end_unix'],
            'fresh_owned_absence_verified': True, 'source430_unchanged': True,
            'actual_CV_arms': 0, 'complete_CV': False, 'OOF_complete': False,
            'quality_metrics': None, 'Stage1_authorized': False, 'Stage1_deadline_assigned': False,
            'API_provider_closed_ledger_certified': None,
            'API_proof_scope': 'Reviewed technical controller/source/CLI API cap0; not a provider-side usage certification.',
            'reviewer_new_fits': 0, 'reviewer_API_calls': 0, 'promotion': False}
        proposal = {'status': 'PROPOSAL_requires_separate_root_Stage1_review_publication_and_clock',
            'requested_stage': 'stage1', 'source_sha256': SOURCE_SHA, 'manifest_sha256': MANIFEST_SHA,
            'existing_packet_review_preserved_sha256': STAGE0_REVIEW_SHA,
            'root_launch_reviewed': False, 'launch_authorized': False, 'deadline_assigned': False,
            'limits': manifest['limits'], 'slots': manifest['slots'], 'solver_cli': manifest['solver_cli'],
            'reviewed_future_resources': {'worker_threads': 2, 'worker_subtree_memory_mib': 1536,
                                         'whole_parent_owned_tree_memory_mib': 2048},
            'r3_sha256': manifest['r3_sha256'], 'outer_manifest_sha256': manifest['outer_manifest_sha256'],
            'source_archive_sha256': {a: v['archive_sha256'] for a, v in manifest['arms'].items()},
            'requires_before_any_Stage1_launch': [
                'Root reviews and publishes this actual technical aggregate and closure plus exact prepared manifest.',
                'Root makes a separate concrete Stage1 launch-review decision; this proposal does not replace packet/review.json.',
                'Fresh strict absence of the complete Stage0/launcher/gate/prior union AND this review-preparer identity under canonical lock.',
                'Only then root assigns a new independent64800-second absolute and monotonic Stage1 clock; no Stage0 remaining-time reuse.',
                'Use unchanged six slots AB/BA/AB, full9900 solver allocations and original R3 fail-closed quality/integrity/refit gates.'],
            'actual_CV_outcomes_read': False, 'Stage2_started': False, 'promotion': False}
        payloads = {'stage0-terminal-ownership.json': closure, 'technical-summary.json': aggregate,
                    'stage1-root-review-PROPOSAL.json': proposal}
        # No receipt is visible at its final path until the whole new directory is
        # populated and all pinned sources/evidence/owned identities pass again.
        staging = Path(tempfile.mkdtemp(prefix='cv1-review-r4-', dir=WORK)).resolve()
        require(staging.parent == WORK and not OUTPUT.exists(), 'owned_append_only_directory_required')
        committed = False
        try:
            for name, value in payloads.items():
                with (staging / name).open('x', encoding='utf-8', newline='\n') as stream:
                    json.dump(value, stream, ensure_ascii=False, indent=2)
                    stream.write('\n')
                    stream.flush()
                    os.fsync(stream.fileno())
            marker = {'status': 'prepared_only_for_root_review_no_Stage1_authorization',
                'source_sha256': own_sha, 'recorded_epoch': recorded,
                'files_sha256': {name: digest(staging / name) for name in payloads},
                'Stage1_clock_assigned': False, 'Stage1_launched': False, 'new_fits': 0, 'API_calls': 0}
            with (staging / 'completion.json').open('x', encoding='utf-8', newline='\n') as stream:
                json.dump(marker, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            pins()
            cv.guard(manifest)
            require(terminal_context(cv, manifest)['refs'] == current['refs'], 'terminal_evidence_changed_before_commit')
            require(fresh(owner, builder, cv.identities(tracked)) == tracked, 'owned_identity_union_changed_before_commit')
            require(digest(__file__) == own_sha and not OUTPUT.exists(), 'source_changed_or_target_exists')
            staging.rename(OUTPUT)
            committed = True
        finally:
            if not committed:
                # Delete only this helper's named regular scratch files; never
                # recurse or touch any pre-existing review/runtime directory.
                for name in list(payloads) + ['completion.json']:
                    target = staging / name
                    if target.is_file() and target.parent == staging:
                        target.unlink()
                staging.rmdir()
    print(json.dumps({'status': marker['status'], 'review_bundle': relative(OUTPUT),
        'completion_sha256': digest(OUTPUT / 'completion.json'), 'new_fits': 0, 'API_calls': 0,
        'Stage1_clock_assigned': False, 'Stage1_launched': False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--expect-source-sha256')
    parser.add_argument('--confirmed-exec-session', type=int)
    parser.add_argument('--confirmed-exec-exit-code', type=int)
    args = parser.parse_args()
    if not args.write:
        print(json.dumps({'status': 'source_prepared_only_no_terminal_reads_or_process_scan',
            'source_sha256': digest(__file__), 'expected_coordinator_sha256': SOURCE_SHA,
            'expected_manifest_sha256': MANIFEST_SHA, 'write_performed': False,
            'Stage1_clock_assigned': False, 'Stage1_launched': False}))
        return
    execute(args)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        code = str(exc) if isinstance(exc, ReviewPreparationError) else 'stage1_review_preparation_failed'
        print(json.dumps({'status': 'blocked_no_Stage1_authorization', 'error_type': type(exc).__name__,
                          'code': code, 'Stage1_clock_assigned': False, 'Stage1_launched': False}), file=sys.stderr)
        raise SystemExit(1)
