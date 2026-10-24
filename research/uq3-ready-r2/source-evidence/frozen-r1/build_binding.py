"""Root metadata tool: inspect by default, exclusive READY JSON only after actual PASS.

No coordinator/config/provider import, clock, subprocess, task/CSV read or arm
materialization. Actual source/ZIP checks occur only on the future --write path.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import math
import re
import zipfile

WORK = Path(__file__).resolve().parents[1]
PACKET = 'uq3-cadence-hpo-next-dev/candidate'
TEMPLATE_SHA = '37359debe953ca3d795b1b80fc0a7c6eb6ed545b3a56e437824b4d62c33b1738'
HANDOFF_SHA = 'cd6898045edd61110e6fce08f964389914e37b93f3d9b2241316e57b8a122471'
RUNTIME = {
    'run_pair.py': '464305881ab1661fdf2f7b7f4a443aeec59b4bb4664f6d3f18dece2c204d25dd',
    'launcher.py': 'c6d0dfa82939160200b39a4b176a9a462a1f6530e6089a9f5445dfd5850d76a5',
    'audit_pair.py': 'f58a17c218ca89461c3c97c3498d197fa105b5a8ea0b240b26b232b12badf7ff',
    'close_pair.py': '81292f982a6cdf235905940c977115ae11ef3745626f4a28069841a291cfb462',
    'r4_adapter.py': '823d9629119bcd03560cafb62e8b240af8dea5b3f3ba63b4d196b96a62a518cd'}
BASE = ('m4packet/manifest.json', '8faf33cd81c0e864bcf338828c34447000111eda85bc719b8f43312d2babae9a')
AUTHORITY = ('uar-qwen-authority-next-dev/source-handoff.json', '2a2145d87d6ac08e0ad72927608509e715e0e5a83d11d86341de15afc0a5e8e3')
LATEST = ('uq2-audit-close-repair-r1/terminal-root-closure.json', '5c9bfc7f8f4f9c5d760e52963f89a4983172144698b7dd334d252a5dce18eabd')
LATEST_CONFIRMATION = ('uq2-audit-close-repair-r1/root-confirmation.json', 'ec6ee6b4e4e0452d787f69a8735edc4ea56da8d782fe1fd62210fbd1a222997e')
FAC3 = 'fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d'
CURRENT_PROCESS = '9f84f64199b63dc4cef095e026d23084e338f1e42a97d5b4bd083e10f687bdb3'
STATIC = {
    'run_lean_mvp_r2.py': '43be86ece6c453641afdcc6f8eccef02d713986e2ac8bf3314756f0bb78e0818',
    'repaired-mvp-r1-dev/evaluator_r4.py': 'c08e9f0be13a708d67b3266518381d6f1be3b0f43c384ef6425634160d7e2783',
    'champion-seed-next-dev/champion-t5-lineage.json': '408d24be5c884152531552bb0016611eb55b9123aadb4c1a361396d3f7115cf3'}
SOURCE_PINS = {'src/automl/search/hpo.py': 'e11ac8f7ca8b9c844b1524f4f3d43e95b91374ac214e75aacb873c3b4ed89d51',
               'src/automl/search/runner.py': '12091e5a3eb30744fb135fbd47d7a70ceddcf6c48c57fa9074def27e9cd4a4df'}
MODULES = {'hpo': 'automl.search.hpo', 'runner': 'automl.search.runner',
           'metric': 'automl.task_understanding.metric_contract'}
COUNTS = dict(source_scripts=59, source_unique_checks=634, exact_repeated_checks=23,
              mapped_repeated_checks=104, flat_members=73)
MAX_JSON = 4 * 2**20


def need(value, code):
    if not value:
        raise ValueError(code)


def is_sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def local(name):
    need(type(name) is str and name and '\\' not in name and ':' not in name,
         'WORK_relative_POSIX_reference_required')
    parts = PurePosixPath(name)
    need(not parts.is_absolute() and '..' not in parts.parts, 'reference_outside_WORK')
    result = (WORK/name).resolve()
    need(result.is_relative_to(WORK), 'reference_outside_WORK')
    return result


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(2**20), b''):
            value.update(chunk)
    return value.hexdigest()


def metadata(path):
    need(path.suffix == '.json' and path.is_file() and path.stat().st_size <= MAX_JSON,
         'bounded_JSON_metadata_required')
    value = json.loads(path.read_text('utf-8-sig'))
    need(type(value) is dict, 'JSON_object_required')
    return value


def reference(text, extension='.json'):
    need(type(text) is str and '=' in text, 'actual_reference_PATH_equals_SHA_required')
    name, expected = text.rsplit('=', 1)
    path = local(name)
    need(is_sha(expected) and path.suffix == extension and path.is_file()
         and digest(path) == expected, 'actual_reference_bytes_changed')
    return dict(path=path.relative_to(WORK).as_posix(), sha256=expected)


def load_reference(ref):
    return metadata(local(ref['path']))


def fixed(pair):
    return reference(pair[0]+'='+pair[1])


def identities(rows):
    need(type(rows) is list and 0 < len(rows) <= 20000, 'bounded_exact_identities_required')
    need(all(type(v) is dict and set(v) == {'pid', 'create_time'}
             and type(v['pid']) is int and v['pid'] > 0
             and type(v['create_time']) in (int, float) and math.isfinite(v['create_time'])
             and v['create_time'] > 0 for v in rows), 'typed_PID_birth_required')
    result = {(v['pid'], v['create_time']) for v in rows}
    need(len(result) == len(rows), 'duplicate_identity')
    return result


def actual_exec(value):
    need(type(value) is dict and set(value) == {'session', 'exit_code', 'tool'}
         and (value['session'] is None or type(value['session']) is int and value['session'] > 0)
         and type(value['exit_code']) is int and value['exit_code'] == 0
         and type(value['tool']) is str and value['tool'].strip(), 'actual_successful_exec_required')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--self-sha256')
    names = ['private-manifest', 'driver', 'closer', 'campaign', 'root-closure',
             'root-confirmation', 'archive', 'candidate-manifest', 'authority-review']
    for name in names:
        parser.add_argument('--'+name, help='Actual WORK-relative path=SHA256')
    parser.add_argument('--output', default='uq3-ready-binding-next-dev/binding.ready-root.json')
    args = parser.parse_args()
    if not args.write:
        print(json.dumps(dict(status='inspection_only_NOT_READY_no_reads_no_clock_no_write',
            required_actual_refs=names, expected_counts=COUNTS)))
        return 0
    need(__debug__ and is_sha(args.self_sha256) and digest(Path(__file__)) == args.self_sha256,
         'reviewed_unoptimized_builder_self_pin_required')
    need(all(getattr(args, name.replace('-', '_')) for name in names), 'actual_PASS_references_missing')
    output = local(args.output)
    need(output.suffix == '.json' and output.parent.is_dir() and not output.exists(), 'exclusive_NEW_JSON_output_required')
    # No archive hashing/opening before the actual positive gate/root confirmation.
    refs = {name: reference(getattr(args, name.replace('-', '_')),
             '.py' if name in ('driver', 'closer') else '.json') for name in names
             if name not in ('archive', 'candidate-manifest')}
    cfg, campaign, proof, confirmation = [load_reference(refs[n]) for n in
                                          ('private-manifest', 'campaign', 'root-closure', 'root-confirmation')]
    need(cfg.get('schema') == 'uar-full-private-manifest-v1'
         and cfg.get('readiness') == 'READY_FROZEN_SOURCE_REVIEWED'
         and cfg.get('missing_bindings') == [] and cfg.get('common_seconds') == 1200,
         'actual_READY_full_gate_manifest_required')
    need(Path(cfg['work_root']).resolve() == WORK and type(cfg['files_sha256']) is dict,
         'actual_WORK_and_frozen_gate_inventory_required')
    pins = cfg['files_sha256']
    for name in ('driver', 'closer'):
        need(pins.get(str(local(refs[name]['path']))) == refs[name]['sha256'], 'gate_source_not_in_actual_freeze')
    need(campaign.get('private_manifest_sha256') == refs['private-manifest']['sha256']
         and proof.get('private_manifest_sha256') == refs['private-manifest']['sha256']
         and proof.get('campaign_sha256') == refs['campaign']['sha256'],
         'actual_private_manifest_lineage_changed')
    need(proof.get('schema') == 'uar-full-root-closure-v1'
         and all(r.get('technical_procedure_passed') is True and r.get('cleanup_confirmed') is True
                 and r.get('source_unchanged') is True for r in (campaign, proof))
         and not campaign.get('error_history') and proof.get('active_owned_processes') == []
         and proof.get('uncertain_owned') == [] and proof.get('leaf_cleanup_confirmed') is True
         and proof.get('leaf_cleanup_uncertainty') == [] and proof.get('temporary_cleanup_confirmed') is True
         and proof.get('temporary_cleanup_uncertainty') == [], 'actual_positive_full_gate_and_clean_root_required')
    summary = campaign.get('qualified_checks')
    need(type(summary) is dict and summary == proof.get('qualified_checks')
         and all(summary.get(k) == v for k, v in COUNTS.items())
         and summary.get('public_experiment_fits') == 0 and summary.get('quality_metric') is None,
         'actual_59_634_23_104_73_summary_required')
    need(confirmation.get('schema') == 'uar-full-gate-root-exec-confirmation-v1'
         and all(confirmation.get(field) == refs[name] for field, name in
                 [('root_closure', 'root-closure'), ('private_manifest', 'private-manifest'),
                  ('campaign', 'campaign'), ('closer_source', 'closer')]), 'root_confirmation_reference_lineage_changed')
    for name in ('gate_actual_exec', 'closer_actual_exec'):
        actual_exec(confirmation.get(name))
    actual = confirmation['gate_actual_exec']
    need(proof.get('actual_exec_session') == actual['session']
         and proof.get('actual_exec_exit_code_observed_by_root') == 0
         and proof.get('actual_tool_evidence') == actual['tool'], 'root_proof_actual_exec_mismatch')
    need(confirmation.get('common_seconds') == 1200
         and confirmation.get('known_exact_live') == [] and confirmation.get('uncertain') == []
         and confirmation.get('root_and_closure_preparer_union_included') is True,
         'actual_fresh_gate_and_preparer_absence_required')
    known = identities(confirmation.get('known_identities'))
    need(len(known) == confirmation.get('known_count')
         and (identities(proof['owned_identities']) | identities(proof['closure_preparer_identities'])) <= known,
         'confirmed_gate_root_preparer_union_incomplete')
    for side, end_field in [('unix', 'absolute_deadline_unix'), ('monotonic', 'common_deadline_monotonic')]:
        start, end, checked = (confirmation.get('original_start_'+side),
            confirmation.get('original_deadline_'+side), confirmation.get('checked_'+side))
        need(all(type(v) in (int, float) and math.isfinite(v) for v in (start, end, checked))
             and start == campaign['start_'+side] and end == campaign[end_field] == start+1200
             and campaign['finished_'+side] <= checked < end, 'original_gate_clock_confirmation_changed')

    # Only positive actual gate receipts may authorize opening its code-only ZIP.
    refs['archive'] = reference(args.archive, '.zip')
    refs['candidate-manifest'] = reference(args.candidate_manifest)
    archive, manifest = local(refs['archive']['path']), load_reference(refs['candidate-manifest'])
    gate_output = Path(cfg['output']).resolve()
    need(archive == gate_output/'candidate.zip'
         and local(refs['candidate-manifest']['path']) == gate_output/'candidate.manifest.json'
         and manifest.get('sha256') == refs['archive']['sha256'], 'qualified_gate_archive_lineage_changed')
    compiled = manifest.get('files')
    need(type(compiled) is dict and len(compiled) == 73 and set(compiled) == set(cfg['flat_inventory'])
         and all(is_sha(v) for v in compiled.values())
         and archive.stat().st_size == manifest.get('bytes'), 'same73_actual_compiled_members_required')
    with zipfile.ZipFile(archive) as stream:
        entries = stream.infolist()
        need(len(entries) == len(set(v.filename for v in entries)) == 73
             and set(v.filename for v in entries) == set(compiled)
             and sum(v.file_size for v in entries) <= 16*2**20, 'bounded_exact_code_only_archive_required')
        for entry in entries:
            name = entry.filename
            need('/' not in name and '\\' not in name and (name.endswith('.py') or name == 'requirements.txt')
                 and (entry.external_attr >> 16) & 0o170000 != 0o120000,
                 'noncode_or_symlink_archive_member')
            need(hashlib.sha256(stream.read(entry)).hexdigest() == compiled[name], 'qualified_flat_member_changed')
    canonical = Path(cfg['canonical_root']).resolve()
    need(canonical.is_relative_to(WORK), 'canonical_root_outside_WORK')
    for rel, expected in SOURCE_PINS.items():
        path = canonical/rel
        need(pins.get(str(path)) == expected and digest(path) == expected, 'actual_repaired_HPO_source_not_qualified')
    metric_path = canonical/'src/automl/task_understanding/metric_contract.py'
    need(is_sha(pins.get(str(metric_path))) and digest(metric_path) == pins[str(metric_path)], 'qualified_metric_source_changed')
    map_path = canonical/'tools/module_map.json'
    need(is_sha(pins.get(str(map_path))) and digest(map_path) == pins[str(map_path)], 'qualified_module_map_changed')
    mapping = metadata(map_path)
    member = {key: mapping.get(module, module.replace('.', '_'))+'.py' for key, module in MODULES.items()}
    need(all(name in compiled for name in member.values()), 'actual_policy_member_mapping_missing')

    template = local(PACKET+'/binding.template.json')
    need(digest(template) == TEMPLATE_SHA and digest(local(PACKET+'/source-handoff.json')) == HANDOFF_SHA,
         'reviewed_UQ3_template_or_source_handoff_changed')
    for name, expected in RUNTIME.items():
        need(digest(local(PACKET+'/'+name)) == expected, 'reviewed_UQ3_runtime_source_changed')
    authority_ref, latest_ref, latest_confirm_ref = fixed(AUTHORITY), fixed(LATEST), fixed(LATEST_CONFIRMATION)
    authority, latest, latest_confirmation = map(load_reference, (authority_ref, latest_ref, latest_confirm_ref))
    need(latest.get('schema') == 'uq2-clean-negative-audit-root-closure-v1'
         and latest.get('technical_procedure_passed') is False and latest.get('original_full_procedure_passed') is False
         and latest.get('original_global_qualification') == 'FAIL' and latest.get('cleanup_confirmed') is True
         and latest.get('source_unchanged') is True and latest.get('active_owned_processes') == []
         and latest.get('uncertain_owned') == [] and latest.get('actual_exec_session') == 3588
         and latest.get('actual_exec_exit_code_observed_by_root') == 1, 'exact_UQ2_clean_negative_required')
    need(latest_confirmation.get('audit_root_sha256') == LATEST[1]
         and latest_confirmation.get('audit_actual_exit') == 0
         and latest_confirmation.get('known_exact_live') == [] and latest_confirmation.get('uncertain') == [],
         'actual_UQ2_audit_confirmation_required')
    need(any(v.get('id') == 'uq2' and v.get('sha256') == LATEST[1]
             and Path(v['path']).resolve() == local(LATEST[0]) for v in cfg['predecessors']),
         'latest_UQ2_must_be_actual_gate_predecessor')

    # Detect pin collisions exactly as the reviewed launch path, without reading inputs.
    merged = {}
    def merge(name, expected):
        local(name)
        need(is_sha(expected) and (name not in merged or merged[name] == expected), 'conflicting_input_pin:'+name)
        merged[name] = expected
    for absolute, expected in pins.items():
        merge(Path(absolute).resolve().relative_to(WORK).as_posix(), expected)
    base_ref = fixed(BASE);base = load_reference(base_ref)
    process_key = 'alfa-hack-automl/src/automl/infrastructure/processes.py'
    historical = cfg['helpers']['processes'];historical_path = Path(historical['path']).resolve()
    need(base['immutable_files'].get(process_key) == historical['sha256'] == FAC3
         and merged.get(process_key) == cfg['candidate_process_sha256'] == CURRENT_PROCESS
         and pins.get(str(historical_path)) == FAC3 and digest(historical_path) == FAC3,
         'exact_single_historical_fac3_relocation_required')
    for name, expected in base['immutable_files'].items():
        merge(historical_path.relative_to(WORK).as_posix() if name == process_key else name, expected)
    for name, expected in authority['files_sha256'].items():
        merge((local(AUTHORITY[0]).parent/name).relative_to(WORK).as_posix(), expected)
    for ref in [*refs.values(), authority_ref, latest_ref, latest_confirm_ref, base_ref]:
        merge(ref['path'], ref['sha256'])
    for name, expected in RUNTIME.items():
        merge(PACKET+'/'+name, expected)
    for name, expected in STATIC.items():
        need(digest(local(name)) == expected, 'reviewed_controller_static_dependency_changed')
        merge(name, expected)
    need(output.relative_to(WORK).as_posix() not in merged, 'output_conflicts_with_frozen_input')
    binding = metadata(template)
    need(binding.get('readiness') == 'NOT_READY', 'preserved_NOT_READY_template_required')
    binding.update(readiness='READY_REVIEWED_SOURCE_AND_AUTHORITY', missing_bindings=[],
        source_archive=refs['archive'], latest_terminal=latest_ref,
        policy_sources={key: dict(flat_member=member[key], sha256=compiled[member[key]]) for key in ('hpo', 'runner')})
    binding['source_gate'].update(driver=refs['driver'], closer=refs['closer'],
        private_manifest=refs['private-manifest'], campaign=refs['campaign'], root_closure=refs['root-closure'],
        root_confirmation=refs['root-confirmation'], actual_exec_session=actual['session'],
        actual_tool_evidence=actual['tool'], expected_checks=summary)
    binding['authority'].update(handoff=authority_ref, independent_review=refs['authority-review'],
        metric_contrast_fixed_source_qualified=True,
        qualified_metric_source=dict(flat_member=member['metric'], sha256=compiled[member['metric']]))
    raw = json.dumps(binding, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
    need(len(raw.encode('utf-8')) <= 256*2**10, 'bounded_ready_binding_required')
    # Recheck every explicitly read authority/source/ZIP reference before exclusive output.
    for ref in [*refs.values(), authority_ref, latest_ref, latest_confirm_ref, base_ref]:
        need(digest(local(ref['path'])) == ref['sha256'], 'reference_changed_before_binding_write')
    for name, expected in {**STATIC, **{PACKET+'/'+n: h for n, h in RUNTIME.items()},
                           PACKET+'/binding.template.json': TEMPLATE_SHA,
                           PACKET+'/source-handoff.json': HANDOFF_SHA}.items():
        need(digest(local(name)) == expected, 'reviewed_source_changed_before_binding_write')
    for path in [*(canonical/n for n in SOURCE_PINS), metric_path, map_path]:
        need(digest(path) == pins[str(path)], 'qualified_source_changed_before_binding_write')
    need(digest(Path(__file__)) == args.self_sha256, 'builder_source_changed_before_binding_write')
    with output.open('x', encoding='utf-8') as stream:
        stream.write(raw)
    print(json.dumps(dict(status='exclusive_READY_metadata_written_no_launch',
        output=output.relative_to(WORK).as_posix(), sha256=digest(output),
        code_members=73, input_rows_read=0, model_fits=0, API_calls=0, clock_assigned=False)))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        # No private path or exception text is emitted by this metadata tool.
        print(json.dumps(dict(status='NOT_READY_no_launch', error_type=type(error).__name__)))
        raise SystemExit(1)
