"""Finite RQ4 actual-wrapper-exit proof; never rewrites the original root."""
from pathlib import Path
import argparse
import json
import sys
import time
from bind_atomic import authority, imported, read, sha, WORK, PACKET, OUT, BASE, BASE_SHA
from helper_policy import exact_union, need, publish_checked, revoked, save_json, window

sys.dont_write_bytecode = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('authority', 'authority-sha256', 'wrapper-tool', 'binding-sha256'):
        parser.add_argument('--' + key, required=True)
    parser.add_argument('--wrapper-exit-code', type=int, required=True)
    parser.add_argument('--launch-parent-pid', type=int, required=True)
    parser.add_argument('--launch-parent-create-time', type=float, required=True)
    args = parser.parse_args(); begin = time.monotonic()
    destination = OUT / 'actual-wrapper-exit-confirmation.json'
    result = dict(schema='standard-repair-actual-wrapper-exit-confirmation-v1', post_tool_confirmed=False)
    try:
        auth = authority(args.authority, args.authority_sha256)
        need(args.wrapper_exit_code == 0 and bool(args.wrapper_tool), 'actual_wrapper_exit0_required')
        manifest = Path(auth['manifest']['path']); cfg = read(manifest)
        binding_path = WORK / 'private/rq4-atomic-binding.ready-r1.json'
        need(sha(binding_path) == args.binding_sha256, 'atomic_binding_changed')
        binding = read(binding_path)
        need(binding.get('readiness') == 'READY_REVIEWED_FROZEN' and binding.get('missing_bindings') == [],
             'actual_atomic_binding_NOT_READY')
        pins = exact_union(cfg['immutable_files'], binding['immutable_files'])
        fresh_path = OUT / 'root-confirmation.json'; root_path = OUT / 'terminal-root-closure.json'
        campaign = OUT / 'campaign.json'; fresh, root, state = read(fresh_path), read(root_path), read(campaign)
        need(binding['manifest'] == auth['manifest'] and binding['campaign'] == dict(path=str(campaign), sha256=sha(campaign)),
             'actual_driver_manifest_campaign_binding_changed')
        need(fresh.get('schema') == 'standard-repair-atomic-root-confirmation-v1'
             and fresh.get('root_sha256') == sha(root_path) and fresh.get('technical_procedure_passed') is True
             and fresh.get('actual_closer_exit') == 0 and fresh.get('known_exact_live') == []
             and fresh.get('uncertain') == [] and fresh.get('errors') == [], 'positive_atomic_root_required')
        need(all(fresh.get(k) is True for k in ('source_unchanged', 'current_temporary_absent', 'current_cleanup_confirmed',
             'inside_actual_closer_birth60', 'inside_original6000', 'inside_existing_driver_final240')), 'atomic_flags_required')
        need(root.get('schema') == 'standard-repair-qualification-root-closure-v1'
             and root.get('manifest_sha256') == auth['manifest']['sha256']
             and root.get('technical_procedure_passed') is True and all(root.get(k) is True for k in
             ('cleanup_confirmed', 'source_unchanged', 'temporary_cleanup_confirmed')), 'qualified_root_flags_required')
        actual = fresh['actual_driver']
        need(root.get('actual_exec_session') == actual['session'] and actual['exit_code'] == 0
             and root.get('actual_exec_exit_code_observed_by_root') == 0
             and root.get('actual_tool_evidence') == actual['tool'], 'actual_driver_root_lineage_changed')
        need(sha(BASE) == BASE_SHA, 'C5_changed'); base = imported('_rq4_post_C5', BASE)
        import psutil
        preparers, chain = base.capture(psutil, args.launch_parent_pid, args.launch_parent_create_time)
        need(chain.get('verified') is True, 'actual_posttool_chain_unconfirmed')
        early = OUT / 'post-tool-preparer-identity.json'
        save_json(early, dict(identities=preparers, launch_parent_observation=chain), True)
        modules = {}
        for key in ('owner', 'sampling'):
            relative, expected = base.HELPERS[key]
            need(sha(WORK / relative) == expected, 'qualified_helper_changed')
            modules[key] = imported('_rq4_post_' + key, WORK / relative)
        statistics = {}
        pulse = base.guard(begin, state['common_deadline_monotonic'], state['absolute_deadline_unix'],
                           modules['owner'], preparers, statistics, sampling=modules['sampling'])
        def check():
            window(state, time.time(), time.monotonic(), begin=begin, closer_birth=fresh['actual_closer_birth'])
            pulse()
        pulse(force=True); check()
        known = base.ids(fresh['known_identities'])
        need(len(known) == fresh['known_count'] == len(fresh['known_identities']), 'exact_saved_atomic_known_array_required')
        need(base.ids(root['owned_identities'] + root['closure_preparer_identities']) <= known,
             'complete_root_closer_union_required')
        known |= base.ids(fresh['wrapper_preparer_identities'])
        ref = binding['binding_preparer_receipt']
        need(sha(ref['path']) == ref['sha256'], 'atomic_binding_preparer_changed')
        known |= base.ids(read(ref['path'])['identities'])
        driver = imported('_rq4_post_source_driver', PACKET / 'run_controller.py')
        inherited = driver.predecessor(cfg, check)
        need(inherited <= known and not (known & base.ids(preparers)), 'complete_current_union_required')
        bound = {str(manifest): auth['manifest']['sha256'], str(binding_path): args.binding_sha256,
                 str(root_path): sha(root_path), str(fresh_path): sha(fresh_path),
                 str(campaign): binding['campaign']['sha256'], str(Path(args.authority)): args.authority_sha256,
                 str(early): sha(early)}
        for path, expected in bound.items():
            need(path not in pins or pins[path] == expected, 'proof_or_source_pin_collision')
            pins[path] = expected
        def frozen():
            for path, expected in pins.items():
                check(); need(sha(path) == expected, 'saved_source_input_core_changed')
            check()
        base.absent(modules['owner'], known, check); frozen()
        temp = state.get('temporary_root')
        need(temp is None or not Path(temp).exists(), 'owned_temporary_root_remains')
        base.absent(modules['owner'], known, check); pulse(force=True); check()
        result = dict(schema='standard-repair-actual-wrapper-exit-confirmation-v1', root_sha256=sha(root_path),
            root_confirmation_sha256=sha(fresh_path), actual_driver=actual,
            actual_wrapper=dict(exit_code=args.wrapper_exit_code, tool=args.wrapper_tool),
            known_identities=[dict(pid=p, create_time=b) for p, b in sorted(known)], known_count=len(known),
            known_exact_live=[], uncertain=[], source_unchanged=True, current_temporary_absent=True,
            current_cleanup_confirmed=True, post_tool_confirmed=True, inside_original6000=True,
            inside_saved_driver_final240=True, inside_actual_closer_birth60=True,
            observation_seconds=time.monotonic()-begin,
            observation_seconds_scope='before final source/publication checks; all later costs remain charged',
            post_tool_preparer_identities=preparers,
            launch_parent_observation=chain, resource_observation={k:v for k,v in statistics.items() if not k.startswith('_')},
            actual_observer_tool_exit_pending=True)
        def terminal():
            frozen(); base.absent(modules['owner'], known, check); pulse(force=True); check()
        publish_checked(result, lambda value, exclusive: save_json(destination, value, exclusive), terminal)
        print(json.dumps(dict(post_tool_confirmed=True, known_count=len(known), receipt_sha256=sha(destination),
            observation_seconds=result['observation_seconds'])))
        check()
        return 0
    except BaseException as primary:
        # Includes stdout/late-check failure AFTER a successful positive write.
        negative = revoked(result, primary)
        try:
            save_json(destination, negative, False)
        except BaseException as secondary:
            try:
                primary.helper_secondary_exception_type = type(secondary).__name__
            except BaseException:
                pass
        raise


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps(dict(post_tool_confirmed=False, error_type=type(error).__name__,
            secondary_exception_type=getattr(error, 'helper_secondary_exception_type', None))))
        raise SystemExit(1)
