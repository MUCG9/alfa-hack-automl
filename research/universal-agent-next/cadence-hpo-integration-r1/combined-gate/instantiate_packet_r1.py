"""Fixed UAR08 source/JSON/AST metadata preparation; never imports the gate."""
from pathlib import Path
import argparse
import ast
import copy
import hashlib
import json
import math
import re

PACKET = Path(__file__).resolve().parent
WORK = PACKET.parent
ROOT = WORK / 'alfa-hack-automl'
HANDOFF_SHA = '4fb7fe138ffde1875f6520e0d7198a3100dabbc5e7f76c702128957fa517b72d'
PEER_SHA = 'd58700176d1d753f12cb8eadce36759ecee0ac0602112515fd2663264dd5f5cc'
OLD_PRIVATE_SHA = 'b8dae322501349622326313f94430042729e2cb1310ecdd32d09796812cf797d'
REVIEW_PATHS = {
    'io03': 'universal-early-declaration-review-r1.json',
    'vertical': 'uar-vertical-contract-independent-review-r1.json',
    'loss': 'uar-loss-backend-independent-review-r1.json',
    'retention': 'uar-strong-retention-independent-review-r1.json',
    'metric_contrast': 'uar-metric-contrast-independent-review-r1.json',
    'cadence': 'uar-task-checkpoint-cadence-independent-review-r1.json',
    'hpo_fair_reserve': 'uar-hpo-fair-reserve-independent-review-r2.json',
}
HELPER_PATHS = {
    'coordinator': 'run_lean_mvp_r2.py',
    'owner': 'support_component_coordinator.py',
    'processes': 'historical-runtime-support/fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d.py',
    'lock': 'alfa-hack-automl/tools/research_lock.py',
    'awake': 'awake-next-dev/awake_guard.py',
}
NEGATIVE_PATHS = {
    'root_confirmation': 'uq2-audit-close-repair-r1/root-confirmation.json',
    'helper_source': 'uq2-audit-close-repair-next-dev/close_pair.py',
    'helper_review': 'uq2-audit-close-repair-independent-review-r3.json',
}


def need(value, code):
    if not value:
        raise RuntimeError(code)


def read(path):
    return json.loads(Path(path).read_text('utf-8'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')


def methods(path):
    result = [cls.name + '.' + node.name
              for cls in ast.parse(Path(path).read_bytes()).body if isinstance(cls, ast.ClassDef)
              for node in cls.body if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]
    need(len(result) == len(set(result)), 'duplicate_qualified_test_method')
    return result


def registry():
    result = None
    for node in ast.parse((ROOT / 'tools/run_checks.py').read_bytes()).body:
        if isinstance(node, ast.Assign) and any(isinstance(v, ast.Name) and v.id == 'CHECKS' for v in node.targets):
            need(result is None, 'duplicate_registry_assignment')
            result = ast.literal_eval(node.value)
        elif (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
              and isinstance(node.value.func, ast.Attribute)
              and isinstance(node.value.func.value, ast.Name)
              and node.value.func.value.id == 'CHECKS' and node.value.func.attr == 'update'):
            need(result is not None and len(node.value.args) == 1 and not node.value.keywords,
                 'nonliteral_registry_update')
            extra = ast.literal_eval(node.value.args[0])
            need(type(extra) is dict and not set(extra) & set(result), 'duplicate_registry_keys')
            result.update(extra)
    need(type(result) is dict and len(result) == 59
         and all(type(k) is str and type(v) is int and v > 0 for k, v in result.items())
         and sum(result.values()) == 634, 'actual_registry_not59_634')
    return result


def identities(rows):
    need(type(rows) is list and len(rows) <= 20000, 'bounded_saved_identity_list_required')
    need(all(type(v) is dict and type(v.get('pid')) is int and v['pid'] > 0
             and type(v.get('create_time')) in (int, float) and math.isfinite(v['create_time'])
             and v['create_time'] > 0 for v in rows), 'invalid_saved_PID_create_time')
    return {(v['pid'], v['create_time']) for v in rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root-reviewed', action='store_true', required=True)
    parser.add_argument('--canonical-commit', required=True)
    parser.add_argument('--self-sha256', required=True)
    args = parser.parse_args()
    need(re.fullmatch('[0-9a-f]{40}', args.canonical_commit), 'actual_published_commit_required')
    need(re.fullmatch('[0-9a-f]{64}', args.self_sha256) and sha(__file__) == args.self_sha256,
         'metadata_instantiator_source_changed')
    targets = {name: PACKET / name for name in ('private-manifest-uar08-r1.json', 'public-manifest.json',
                                                'public-protocol.json', 'packet-summary.json')}
    need(all(not path.exists() for path in targets.values()), 'exclusive_packet_already_exists')
    need(sha(PACKET / 'source-handoff.json') == HANDOFF_SHA, 'frozen_handoff_changed')
    handoff = read(PACKET / 'source-handoff.json')
    need(len(handoff['files_sha256']) == 16, 'exact_sixteen_frozen_source_files_required')
    for name, expected in handoff['files_sha256'].items():
        need(sha(PACKET / name) == expected, 'frozen_source_packet_changed')
    peer = WORK / 'uar08-combined-gate-independent-review-r1.json'
    need(sha(peer) == PEER_SHA, 'exact_combined_source_peer_review_required')
    binding = read(PACKET / 'canonical-source-binding.json')
    cfg = read(PACKET / 'private-manifest.template.json')
    need(cfg['readiness'] == 'NOT_READY' and not cfg['files_sha256'], 'original_template_must_remain_NOT_READY')
    old_path = WORK / 'uar07-composite-next-dev/private-manifest-uar07-r1.json'
    need(sha(old_path) == OLD_PRIVATE_SHA, 'immutable_metadata_lookup_changed')
    old = read(old_path)
    cfg.update(readiness='READY_FROZEN_SOURCE_REVIEWED', missing_bindings=[], run_id='UAR08',
               work_root=str(WORK), canonical_root=str(ROOT),
               python=str((WORK / 'venv/Scripts/python.exe').resolve()),
               output=str(PACKET / 'attempt-r1'), lock_path=str(ROOT / 'test-runs/.owned-research.lock'),
               technical_entry=str(PACKET / 'technical_entry.py'), contracts=str(PACKET / 'contracts.py'),
               focused_helper=str(WORK / 'uar-focused-gate-next-dev/run_gate.py'),
               canonical_commit=args.canonical_commit)
    need(not Path(cfg['output']).exists(), 'future_attempt_already_exists')
    cfg['registry'] = registry()
    need(cfg['registry'] == binding['registry'] and sha(ROOT / 'tools/run_checks.py') ==
         binding['source_registry_sha256'], 'frozen_registry_binding_changed')
    canonical = sorted(p.resolve() for folder in ('src', 'tests', 'tools') for p in (ROOT / folder).rglob('*.py'))
    actual = {p.relative_to(ROOT).as_posix(): sha(p) for p in canonical}
    counts = {folder: sum(p.is_relative_to(ROOT / folder) for p in canonical) for folder in ('src', 'tests', 'tools')}
    need(counts == binding['canonical_python_counts'] == {'src': 81, 'tests': 61, 'tools': 29}
         and len(canonical) == 171 and actual == binding['canonical_python_inventory_sha256'],
         'frozen_canonical_source_inventory_changed')
    mapping = read(ROOT / 'tools/module_map.json')
    for path in (ROOT / 'src/automl').rglob('*.py'):
        if path.name != '__init__.py':
            module = '.'.join(path.relative_to(ROOT / 'src').with_suffix('').parts)
            mapping.setdefault(module, module.replace('.', '_'))
    need(len(mapping) == len(set(mapping.values())) == 67 and mapping == binding['module_mapping']
         and sha(ROOT / 'tools/module_map.json') == binding['module_map_sha256'], 'frozen_transitive_mapping_changed')
    cfg['flat_inventory'] = sorted([v + '.py' for v in mapping.values()] +
        ['agent_runner.py', 'agent_policy.py', 'agent_worker.py', 'ensemble_cache.py', 'solution.py', 'requirements.txt'])
    need(cfg['flat_inventory'] == binding['flat_inventory'] and len(cfg['flat_inventory']) == 73,
         'exact_73_flat_members_required')
    cfg['canonical_python_inventory'] = [str(p) for p in canonical]
    pins = {str(p): actual[p.relative_to(ROOT).as_posix()] for p in canonical}
    extra = [peer, old_path, Path(__file__).resolve(), PACKET / 'source-handoff.json', Path(cfg['python']),
             Path(cfg['focused_helper']), ROOT / 'requirements.txt', ROOT / 'tools/module_map.json']
    extra += [PACKET / name for name in handoff['files_sha256']]
    inputpins = {}
    # Opaque byte hashing only: the instantiator does not parse any fixture table, target or prediction.
    for raw, expected in old['files_sha256'].items():
        path = Path(raw)
        if path.is_relative_to(ROOT / 'public_tasks'):
            need(sha(path) == expected, 'immutable_pristine_fixture_input_changed')
            pins[str(path)] = expected
            inputpins[path.relative_to(ROOT).as_posix()] = expected
    need(len(inputpins) == 10, 'exact_ten_opaque_fixture_inputs_required')
    need(sha(ROOT / 'requirements.txt') == binding['requirements_sha256'], 'requirements_changed')
    for name, ref in cfg['helpers'].items():
        ref['path'] = str((WORK / HELPER_PATHS[name]).resolve())
        need(sha(ref['path']) == ref['sha256'], 'reviewed_guard_source_changed')
        extra.append(Path(ref['path']))
    old_by_id = {ref['id']: ref for ref in old['predecessors']}
    known = set()
    public_predecessors = []
    for ref in cfg['predecessors']:
        ref['path'] = (str(WORK / 'uq2-audit-close-repair-r1/terminal-root-closure.json')
                       if ref['id'] == 'uq2' else old_by_id[ref['id']]['path'])
        need(sha(ref['path']) == ref['sha256'], 'immutable_predecessor_receipt_changed')
        proof = read(ref['path'])
        need(proof.get('cleanup_confirmed') is True and proof.get('source_unchanged') is True
             and not proof.get('active_owned_processes') and not proof.get('uncertain_owned'),
             'predecessor_known_cleanup_or_source_not_confirmed')
        need(proof.get('actual_exec_session') == ref['actual_exec_session']
             and proof.get('actual_exec_exit_code_observed_by_root') == ref['actual_exit_code']
             and proof.get('actual_tool_evidence') == ref['actual_tool_evidence'],
             'predecessor_actual_exit_or_tool_changed')
        rows = proof['owned_identities'] + proof.get('closure_preparer_identities', [])
        known |= identities(rows)
        public_predecessors.append({k: v for k, v in ref.items() if k != 'path'} |
                                   {'explicit_identity_records': len(rows)})
        extra.append(Path(ref['path']))
    need(len(known) == 6300, 'latest_clean_negative_known_union_not6300')
    for key, ref in cfg['latest_UQ2_negative_audit'].items():
        if key == 'schema':
            continue
        ref['path'] = str((WORK / NEGATIVE_PATHS[key]).resolve())
        need(sha(ref['path']) == ref['sha256'], 'negative_audit_confirmation_source_or_review_changed')
        extra.append(Path(ref['path']))
    latest = read(WORK / 'uq2-audit-close-repair-r1/terminal-root-closure.json')
    confirmation = read(cfg['latest_UQ2_negative_audit']['root_confirmation']['path'])
    need(latest.get('technical_procedure_passed') is False
         and latest.get('original_global_qualification') == 'FAIL'
         and latest.get('qualified_ML_metrics') is None
         and confirmation.get('audit_actual_exit') == 0 and confirmation.get('audit_actual_tool') == '1d6371'
         and confirmation.get('known_count') == 6300 and not confirmation.get('known_exact_live')
         and not confirmation.get('uncertain') and identities(confirmation['known_identities']) == known,
         'negative_qualification_and_confirmed_union_must_remain_separate')
    evidence_paths = ['uar02-next-dev/attempt-r1/terminal-root-closure.json', 'uq1/terminal-root-closure.json']
    for ref, relative in zip(cfg['historical_failure_evidence'], evidence_paths, strict=True):
        ref['path'] = str((WORK / relative).resolve())
        need(sha(ref['path']) == ref['sha256'] and ref['scope'] == 'immutable_evidence_only_not_owned_grant',
             'historical_failure_evidence_changed')
        extra.append(Path(ref['path']))
    coverage = []
    for suite in cfg['mapped_suites']:
        suite['test'] = str((ROOT / suite['test_relative_path']).resolve())
        observed = methods(suite['test'])
        need(observed == suite['all_methods'] and suite['selected_methods'] ==
             [name for name in observed if name not in suite['excluded_methods']]
             and cfg['registry'][Path(suite['test']).name] == len(observed)
             and suite['expected_tests'] == len(suite['selected_methods']), 'exact_AST_mapped_method_binding_changed')
        ref = suite['source_review_ref']
        ref['path'] = str((WORK / REVIEW_PATHS[suite['id']]).resolve())
        need(sha(ref['path']) == ref['sha256'], 'exact_mapped_source_peer_review_changed')
        extra.append(Path(ref['path']))
        coverage.append({k: copy.deepcopy(v) for k, v in suite.items() if k not in ('test', 'source_review_ref')} |
                        {'source_test_sha256': pins[suite['test']], 'source_review_sha256': ref['sha256']})
    need(len(coverage) == 7 and sum(s['expected_tests'] for s in cfg['mapped_suites']) == 104,
         'seven_suites_104_mapped_methods_required')
    for path in extra:
        absolute = str(path.resolve())
        value = sha(path)
        need(absolute not in pins or pins[absolute] == value, 'conflicting_input_pin')
        pins[absolute] = value
    cfg['files_sha256'] = pins
    cfg['binding_hints'].update(candidate_source_final_binding=args.canonical_commit,
        actual_future_registry_inventory_source_pins=HANDOFF_SHA, root_review_of_instantiation_pending=True,
        source_peer_review_sha256=PEER_SHA, new_UAR08_actual_clock=None,
        immutable_historical_source_invariance_is_point_in_time=True)
    public = dict(schema='uar-full-sanitized-source-manifest-v1', run_id='UAR08',
        status='PRIVATE_FROZEN_PENDING_ROOT_REVIEW_PUBLICATION_AND_ACTUAL_LAUNCH',
        canonical_commit=args.canonical_commit, private_manifest_sha256=hashlib.sha256(encoded(cfg)).hexdigest(),
        private_manifest_not_public=True, source_gate_expected=dict(scripts=59, unique_checks=634,
            registry_sha256=binding['source_registry_sha256']), canonical_python_by_folder=counts,
        flat_inventory=cfg['flat_inventory'], module_map=mapping, exact_repeated_checks=23,
        mapped_repeated_checks=104, mapped_suites=coverage,
        candidate_local_execution_file_sha256=actual, public_input_manifest_hashes_only_no_rows=inputpins,
        guard_sources_sha256={k: v['sha256'] for k, v in cfg['helpers'].items()},
        gate_sources_sha256={name: handoff['files_sha256'][name] for name in
                             ('run_gate.py', 'technical_entry.py', 'contracts.py', 'close_gate.py')},
        source_handoff_sha256=HANDOFF_SHA, source_review_sha256=PEER_SHA,
        predecessor_refs=public_predecessors, distinct_known_owned_and_preparer_identities=len(known),
        latest_negative_UQ2_root_sha256=next(r['sha256'] for r in cfg['predecessors'] if r['id'] == 'uq2'),
        latest_negative_confirmation_sha256=cfg['latest_UQ2_negative_audit']['root_confirmation']['sha256'],
        historical_failure_evidence_only=[{k: v for k, v in ref.items() if k != 'path'}
                                          for ref in cfg['historical_failure_evidence']],
        previous_UQ2_technical_PASS=False, previous_failed_closer_retroqualified=False,
        current_PID_observation_performed_here=False, actual_clock=None, actual_execution=None,
        actual_tests=0, actual_builds=0, candidate_imports=0, model_fits=0, API_calls=0,
        fixture_learner_fits=None, external_API_calls=None, public_experiment_fits=0,
        fixture_count_reason='Future broad fixtures may fit synthetic learners; aggregate is uninstrumented.',
        metadata_preparer_identity=None, metadata_preparer_identity_limit='Not captured; no child spawning in this source.',
        quality_metric=None, promotion=False, submit=False)
    protocol = copy.deepcopy(read(PACKET / 'protocol.json'))
    protocol.update(status='PRIVATE_FROZEN_PENDING_ROOT_REVIEW_PUBLICATION_AND_ACTUAL_LAUNCH',
        canonical_commit=args.canonical_commit, private_READY_manifest_sha256=public['private_manifest_sha256'],
        public_manifest_sha256=hashlib.sha256(encoded(public)).hexdigest(), pending_final_source_review=False)
    protocol['HPO_policy_scope'] = ('Reviewed R2 defaultOFF; CLASS900 future optin pilot, REG300 unchanged/OFF; '
        'technical gate does not certify 8 valid trials, guided success, savings or ML gain.')
    protocol['approved_source_only_flat_exclusions'] = [
        {'suite': s['id'], 'methods': s['excluded_methods'], 'reason': s['exclusion_reason']}
        for s in cfg['mapped_suites'] if s['excluded_methods']]
    summary = dict(schema='uar08-metadata-instantiation-v1', canonical_commit=args.canonical_commit,
        status='SOURCE_METADATA_ONLY_PENDING_ROOT_REVIEW_PUBLICATION_NO_LAUNCH',
        immutable_files=len(pins), canonical_python_files=171, canonical_python_by_folder=counts,
        source_scripts=59, source_unique_expected_checks=634, flat_members=73,
        exact_repeated_checks=23, mapped_repeated_checks=104, known_saved_identity_union=6300,
        private_manifest_sha256=public['private_manifest_sha256'],
        public_manifest_sha256=protocol['public_manifest_sha256'],
        public_protocol_sha256=hashlib.sha256(encoded(protocol)).hexdigest(),
        source_handoff_sha256=HANDOFF_SHA, source_review_sha256=PEER_SHA, instantiator_sha256=args.self_sha256,
        original_NOT_READY_template_preserved=True, actual_clock=None, actual_run=None,
        candidate_imports=0, tests=0, builds=0, fits=0, API=0, PID_scans=0, Git_writes=0)
    # Only immutable bytes and saved metadata are rechecked; old nested canonical maps are historical evidence.
    need(all(sha(path) == expected for path, expected in pins.items()), 'source_changed_during_metadata_instantiation')
    values = {'private-manifest-uar08-r1.json': cfg, 'public-manifest.json': public,
              'public-protocol.json': protocol, 'packet-summary.json': summary}
    for name, path in targets.items():
        with path.open('xb') as stream:
            stream.write(encoded(values[name]))
    print(json.dumps(summary, ensure_ascii=True, allow_nan=False))


if __name__ == '__main__':
    main()
