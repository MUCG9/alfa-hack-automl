"""One fixed saved-cache CLASS comparison; no fitting or submission output."""
from copy import deepcopy
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import time

PACKET = Path(__file__).resolve().parent
WORK = PACKET.parent
OUTPUT = WORK / 'cx1/independent-cache-audit.json'
INVENTORY_SHA = '0a6fd55a64ddf885aac05a427d9b62857b0fc3bd67bac2977d6b040571f95fb8'
R4_SHA = '823d9629119bcd03560cafb62e8b240af8dea5b3f3ba63b4d196b96a62a518cd'
FIXED_AUDITOR_SHA = '39678926216dd7ea45305f02efc86989f9bdea63b3f8b163ebe6ad0ff8490c64'
BRQ3_MANIFEST_SHA = '3ee656535bfb61813ce9f288d4ddf45eaa2bc9b2a3433ae23b0c3182215f611e'
ARCHIVE_SHA = 'c7b54a8996e36dfaaf582b104d1f38ecca71d91d4f38362ed50775381f42f930'
PHASES = ('primary', 'confirmation')


class Stop(RuntimeError):
    pass


def need(value, code):
    if not value:
        raise Stop(code)


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def work_path(relative):
    p = Path(relative)
    need(type(relative) is str and not p.is_absolute() and '..' not in p.parts,
         'relative_saved_reference_required')
    p = WORK / p
    need(p.resolve().is_relative_to(WORK.resolve()) and not p.is_symlink(), 'saved_reference_escape_or_symlink')
    return p


def digest(path, check):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            check()
            block = stream.read(2**20)
            if not block:
                break
            result.update(block)
    check()
    return result.hexdigest()


class RetainedClock:
    """Only inherited original clocks; the external reviewed parent owns RSS."""
    def __init__(self, clock):
        keys = ('start_unix', 'start_monotonic', 'absolute_deadline_unix', 'common_deadline_monotonic',
                'audit_start_unix', 'audit_start_monotonic', 'audit_deadline_unix',
                'audit_deadline_monotonic', 'prior_checkpoint_monotonic')
        need(type(clock) is dict and all(type(clock.get(k)) in (int, float)
             and math.isfinite(clock[k]) for k in keys), 'actual_retained_clock_required')
        need(clock['absolute_deadline_unix'] == clock['start_unix'] + 600
             and clock['common_deadline_monotonic'] == clock['start_monotonic'] + 600
             and clock['audit_deadline_unix'] == clock['audit_start_unix'] + 120
             and clock['audit_deadline_monotonic'] == clock['audit_start_monotonic'] + 120
             and clock['start_monotonic'] <= clock['prior_checkpoint_monotonic'] <= clock['audit_start_monotonic']
             and clock['audit_deadline_unix'] <= clock['absolute_deadline_unix'] - 300
             and clock['audit_deadline_monotonic'] <= clock['common_deadline_monotonic'] - 300,
             'assigned_common600_audit120_final300_required')
        self.clock, self.last, self.sticky = dict(clock), clock['prior_checkpoint_monotonic'], None

    def check(self):
        if self.sticky is not None:
            raise self.sticky
        try:
            now, wall = time.monotonic(), time.time()
            c = self.clock
            need(math.isfinite(now) and math.isfinite(wall) and now >= self.last, 'clock_nonfinite_or_rollback')
            need(now - self.last <= 10, 'audit_checkpoint_gap_over10')
            need(now < min(c['common_deadline_monotonic'], c['audit_deadline_monotonic'])
                 and wall < min(c['absolute_deadline_unix'], c['audit_deadline_unix']), 'original_audit_clock_exhausted')
            need(abs((wall-c['start_unix'])-(now-c['start_monotonic'])) <= 5, 'wall_monotonic_drift')
            self.last = now
        except BaseException as exc:
            self.sticky = exc
            raise


def candidate_recipe(control):
    need(control.get('engine') == 'ensemble' and control.get('weights') == [1/3, 1/3, 1/3]
         and len(control.get('components', [])) == 3, 'exact_three_child_control_required')
    need(all(c.get('engine') == 'lightgbm' and c.get('params', {}).get('feature_views') == 'categorical_te_pair'
             for c in control['components'][:2]) and control['components'][2].get('engine') == 'xgboost',
         'fixed_retained_LGBM0_1_XGB2_required')
    result = deepcopy(control)
    result['components'] = deepcopy(control['components'][:2])
    result['weights'] = [.5, .5]
    return result


def blend(parts, weights):
    need(len(parts) == len(weights) and len(parts) in (2, 3)
         and all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in weights), 'fixed_positive_weights')
    total = sum(weights)
    result = parts[0] * (weights[0]/total)
    for part, weight in zip(parts[1:], weights[1:]):
        result = result + part * (weight/total)
    return result


def both_controls_first(control, candidate):
    controls = {p: control(p) for p in PHASES}
    candidates = {p: candidate(p, controls[p]) for p in PHASES}
    return controls, candidates


def confirm_saved_control(actual, saved, close):
    for k in ('phase', 'metric', 'fitting_rows', 'validation_rows', 'positions_sha256',
              'training_rows_canonical_sha256', 'split_file_sha256', 'prediction_sha256',
              'mixture_children', 'independent_fitting_groups', 'rarest_fitting_class', 'feature_groups_disjoint'):
        need(actual.get(k) == saved.get(k), 'closed_control_metadata_mismatch_'+k)
    need(close(actual['value'], saved['value']) and set(actual['per_class_f1']) == set(saved['per_class_f1'])
         and all(close(actual['per_class_f1'][c], saved['per_class_f1'][c]) for c in actual['per_class_f1'])
         and close(actual['ex_rarest_macro_f1'], saved['ex_rarest_macro_f1']), 'closed_control_metric_mismatch')


def decide(controls, candidates, comparison):
    need(set(controls) == set(candidates) == set(PHASES), 'both_complete_cuts_required')
    need(all(type(v[p]['value']) in (int, float) and math.isfinite(v[p]['value'])
             for v in (controls, candidates) for p in PHASES), 'finite_unimputed_metrics_required')
    matched = comparison(candidates, controls, 'classification')
    control_mean = sum(controls[p]['value'] for p in PHASES)/2
    candidate_mean = sum(candidates[p]['value'] for p in PHASES)/2
    passed = (all(candidates[p]['value'] > controls[p]['value'] for p in PHASES)
              and matched['each_cut_primary_gate_passed'] is True
              and matched['class_each_cut_gate_passed'] is True and candidate_mean > control_mean)
    matched['scope'] = 'Same sealed BRQ3 child caches; no new learner fits or candidate refit.'
    return dict(control_mean=control_mean, candidate_mean=candidate_mean,
                delta_candidate_minus_control=candidate_mean-control_mean,
                matched=matched, quality_gate_passed=passed)


def rehash(files, check):
    need(type(files) is dict and 1 <= len(files) <= 4096, 'bounded_hash_inventory')
    for rel, h in files.items():
        need(type(h) is str and re.fullmatch('[0-9a-f]{64}', h), 'typed_saved_SHA256')
        need(digest(work_path(rel), check) == h, 'saved_source_input_split_core_changed')


def imported(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit(cfg, manifest_sha, self_sha, check):
    ref = cfg['expected_inventory']
    need(ref == dict(path=str(PACKET/'expected-inventory.json'), sha256=INVENTORY_SHA)
         and digest(ref['path'], check) == INVENTORY_SHA, 'fixed_expected_inventory_changed')
    inventory = load(ref['path'])
    need(inventory['schema'] == 'class-xgb-contribution-expected-inventory-v1'
         and len(inventory['files_sha256']) == 676 and inventory['candidate_indices'] == [0,1]
         and inventory['candidate_weights'] == [.5,.5], 'exact_closed_inventory_required')
    sources = cfg['source_files']
    need(type(sources) is dict and 1 <= len(sources) <= 128
         and sources.get(str(Path(__file__).resolve())) == self_sha, 'reviewed_caller_auditor_source_pins_required')
    for path, h in sources.items():
        need(Path(path).is_absolute() and Path(path).resolve().is_relative_to(WORK.resolve())
             and type(h) is str and re.fullmatch('[0-9a-f]{64}', h)
             and digest(path, check) == h, 'caller_or_auditor_source_changed')
    caller = cfg['reviewed_caller']
    need(Path(caller['path']).is_absolute() and sources.get(caller['path']) == caller['sha256']
         and Path(caller['review_path']).is_absolute()
         and sources.get(caller['review_path']) == caller['review_sha256'], 'actual_reviewed_caller_pin_required')
    rehash(inventory['files_sha256'], check)
    old_cfg = load(work_path(inventory['original_private_manifest']))
    need(inventory['files_sha256'][inventory['original_private_manifest']] == BRQ3_MANIFEST_SHA
         and old_cfg['executor']['archive']['sha256'] == ARCHIVE_SHA, 'original_BRQ3_manifest_archive_changed')
    root, fresh = load(work_path(inventory['root'])), load(work_path(inventory['fresh']))
    need(root['technical_procedure_passed'] is True and root['cleanup_confirmed'] is True
         and root['source_unchanged'] is True and root['active_owned_processes'] == []
         and root['uncertain_owned'] == [] and root['changed_source_or_core'] == []
         and root['actual_exec_session'] == 37018 and root['actual_exec_exit_code_observed_by_root'] == 0
         and root['actual_tool_evidence'] == '757206', 'closed_BRQ3_positive_prerequisite_missing')
    need(fresh['root_sha256'] == inventory['files_sha256'][inventory['root']]
         and fresh['actual_driver_execution'] == dict(session=37018, exit_code=0, tool='757206')
         and fresh['actual_closer_execution'] == dict(session=None, exit_code=0, tool='d1005d')
         and fresh['known_exact_live'] == [] and fresh['uncertain'] == [] and fresh['known_count'] == 7305
         and fresh['inside_original_common'] is True and fresh['current_source_cleanup_confirmed'] is True,
         'closed_root_closer_fresh_binding_missing')
    report = load(work_path(inventory['report']))
    saved = load(work_path(inventory['independent_audit']))
    barrier = load(work_path(inventory['barrier']))
    task = old_cfg['tasks'][1]
    need(task['kind'] == report['spec']['kind'] == 'classification' and report['spec']['metric'] == 'macro_f1'
         and report['recipe'] == task['expected_recipe'] and report['cleanup_confirmed'] is True
         and report['source_unchanged'] is True and report['first_failure'] is None
         and report['secondary_failures'] == [] and len(report['measurements']) == 2,
         'qualified_fixed_CLASS_report_required')
    candidate = candidate_recipe(report['recipe'])
    need(saved['artifact_procedure_passed'] is True and saved['archive_sha256'] == ARCHIVE_SHA
         and saved['manifest_sha256'] == BRQ3_MANIFEST_SHA and saved['new_model_fits'] == 0,
         'original_independent_control_audit_required')
    entry = barrier['tasks'][1]
    sup = entry['supervisor']['record']
    need(entry['kind'] == 'classification' and sup['status'] == 'ok' and sup['exit_code'] == 0
         and sup['cleanup_confirmed'] is True and not sup.get('error_history')
         and sup['parent_cap_seconds'] == 3600 and sup['child_cap_seconds'] == 3570
         and sup['solver_budget_seconds'] is None and sup['peak_owned_tree_rss_mib'] <= 2048,
         'closed_CLASS_supervisor_caps_required')
    for phase, record in zip(PHASES, report['measurements']):
        item = inventory['phases'][phase]
        job = load(work_path(item['folder'])/'job.json')
        need(record['recipe'] == report['recipe'] and record['status'] == 'ok'
             and job['threads'] == 2 and job['full_fit'] is False and 'fit_iterations' not in job
             and len(record['components']) == 3 and record['strict_runtime'] is True
             and record['cleanup_confirmed'] is True and record['worker_memory_limit_bytes'] == 1536*2**20
             and record['whole_memory_limit_bytes'] == 2048*2**20
             and record['observed_worker_tree_peak_bytes'] <= 1536*2**20
             and record['observed_combined_peak_bytes'] <= 2048*2**20, 'closed_cut_caps_or_stopping_changed')
        need(len(item['outer_caches']) == 6 and all(inventory['files_sha256'].get(p) == h
             for p, h in item['outer_caches'].items()), 'missing_exact_child_cache_STOP_no_fit')
    # This complete source/input/core/closure barrier precedes NumPy/Pandas and truth.
    check()
    helper_path, r4_path = work_path(inventory['fixed_auditor']), work_path(inventory['r4'])
    need(digest(helper_path, check) == FIXED_AUDITOR_SHA and digest(r4_path, check) == R4_SHA, 'manual_audit_source_changed')
    helper = imported('_cx_fixed_audit_helpers', helper_path)
    need(all(helper.verified_terminal(r) for r in report['measurements']), 'verified_terminal_receipt_required')
    r4 = imported('_cx_manual_R4', r4_path)
    r4.WORK = WORK
    spec, directory = report['spec'], work_path(inventory['class_directory'])
    classes, identifier = list(spec['classes']), spec.get('id')
    need(len(classes) == len(set(classes)) > 1, 'unique_canonical_classes_required')
    source = Path(task['source'])
    roles = {str((source/'train.csv').resolve()): [spec['target']]}
    for rel in inventory['files_sha256']:
        p = work_path(rel)
        if p.is_relative_to(directory) and p.name == 'validation_predictions.csv': roles[str(p.resolve())] = ['y_true','y_pred']
        elif p.is_relative_to(directory) and p.name == 'submission.csv': roles[str(p.resolve())] = [spec['output_columns'][0]]
    parser = helper.DeclaredClassCSV(r4.pd, roles)
    r4.pd = parser
    converters = {identifier:str} if identifier is not None else {}
    train, test, sample = [parser.read_csv(source/n, converters=converters)
                           for n in ('train.csv','test.csv','sample_submission.csv')]
    check()
    verifier = r4.TaskVerifier(directory, dict(spec=spec), train, test, sample)
    material = {}
    def control(phase):
        check()
        index = PHASES.index(phase)
        record, item = report['measurements'][index], inventory['phases'][phase]
        partition = work_path(item['partition'])
        expected = r4.expected_partition(task, spec, train, phase, old_cfg['verification_plan'])
        observed = r4.split(partition, len(train))
        need(all(r4.np.array_equal(a,b) for a,b in zip(expected,observed)), 'exact_saved_cut_positions_required')
        verified = verifier.verify(record, partition, phase, expected_recipe=report['recipe'])
        parts = []
        for i, child_recipe in enumerate(report['recipe']['components']):
            folder = work_path(item['folder'])/('component-'+str(i))
            child = load(folder/'result.json')
            parts.append(verifier.verify(dict(child, output_dir=str(folder)), partition, phase,
                                         expected_recipe=child_recipe)['validation'])
        mixed = blend(parts, report['recipe']['weights'])
        need(r4.np.allclose(mixed, verified['validation'], atol=1e-10, rtol=1e-10)
             and r4.np.array_equal(mixed.argmax(axis=1), verified['validation'].argmax(axis=1)),
             'full3_control_child_cache_not_equivalent_STOP_no_fit')
        diag = r4.diagnostics(verifier, record, partition, phase)
        confirm_saved_control(diag, saved['tasks']['classification']['cuts'][phase], r4.close)
        material[phase] = (parts, observed[1])
        check()
        return diag
    def candidate_score(phase, control_diag):
        check()
        parts, va = material[phase]
        proba = blend(parts[:2], [.5,.5])
        truth = train[spec['target']].iloc[va].astype(str).to_numpy()
        predicted = r4.np.asarray(classes)[proba.argmax(axis=1)]
        value, per_class = r4.f1(truth, predicted, classes)
        diag = deepcopy(control_diag)
        rarest = diag['rarest_fitting_class']
        diag.update(value=value, per_class_f1=per_class, mixture_children=2,
                    prediction_sha256=None, prediction_source='Fixed half-half sealed outer child0 and child1 validation caches; no prediction file written',
                    ex_rarest_macro_f1=float(r4.np.mean([v for k,v in per_class.items() if k != rarest])))
        check()
        return diag
    controls, candidates = both_controls_first(control, candidate_score)
    decision = decide(controls, candidates, r4.matched_control_comparison)
    need(r4.close(sum(controls[p]['value'] for p in PHASES)/2, saved['tasks']['classification']['selected_cut_mean']),
         'closed_control_two_cut_mean_changed')
    rehash(inventory['files_sha256'], check)
    for path, h in sources.items(): need(digest(path, check) == h, 'posttruth_caller_auditor_source_changed')
    check()
    return dict(schema='class-xgb-contribution-audit-v1', status='complete', artifact_procedure_passed=True,
                quality_gate_passed=decision['quality_gate_passed'], cuts=dict(control=controls,candidate=candidates),
                comparison=decision, candidate_recipe=candidate, manifest_sha256=manifest_sha,
                expected_inventory_sha256=INVENTORY_SHA, reused_BRQ3_archive_sha256=ARCHIVE_SHA,
                audit_within_original_common_clock=True, new_model_fits=0, API_calls=0, Qwen_calls=0,
                historical_model_compute_is_not_free=True, candidate_refit=False, submission_written=False,
                new_release_qualified=False, promotion=False, submit=False, first_failure=None, error_history=[])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','manifest-sha256','self-sha256','output'):p.add_argument('--'+name, required=True)
    a = p.parse_args()
    need(Path(a.output).is_absolute() and Path(a.output).resolve() == OUTPUT and not OUTPUT.exists(), 'exclusive_fixed_audit_output')
    result = dict(schema='class-xgb-contribution-audit-v1', status='STOP', artifact_procedure_passed=False,
                  quality_gate_passed=None, cuts=None, comparison=None, new_model_fits=0, API_calls=0,
                  candidate_refit=False, submission_written=False, new_release_qualified=False, promotion=False,
                  submit=False, first_failure=None, error_history=[])
    code, check = 2, lambda: None
    def failure(exc, phase):
        row = dict(phase=phase, exception_type=type(exc).__name__,
                   code=str(exc) if isinstance(exc, Stop) else type(exc).__name__)
        result['first_failure'] = result.get('first_failure') or row
        result['error_history'].append(row)
        result.update(status='STOP', artifact_procedure_passed=False, quality_gate_passed=None, cuts=None, comparison=None)
        result['audit_within_original_common_clock'] = False
    try:
        need(__debug__ and Path(a.manifest).is_absolute() and Path(a.manifest).stat().st_size <= 2**20,
             'bounded_explicit_private_manifest')
        cfg = load(a.manifest)
        check = RetainedClock(cfg.get('clock')).check
        check()
        need(digest(a.manifest, check) == a.manifest_sha256 and digest(__file__, check) == a.self_sha256,
             'manifest_or_auditor_changed')
        need(cfg['schema'] == 'class-xgb-contribution-audit-private-v1' and cfg['readiness'] == 'READY_REVIEWED_FROZEN'
             and cfg['missing_bindings'] == [] and cfg['output'] == str(OUTPUT)
             and cfg['guard_caps'] == dict(parent_seconds=120,child_seconds=90,worker_RSS_MiB=1536,
                   whole_RSS_MiB=2048,technical_threads=1,BLAS_threads=1,API_calls=0), 'reviewed_typed_private_binding_required')
        result = audit(cfg, a.manifest_sha256, a.self_sha256, check)
        code = 0
    except BaseException as exc:
        failure(exc, 'audit')
    try:
        check()
    except BaseException as exc:
        failure(exc, 'final_clock');code = 2
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open('x', encoding='utf-8') as stream:json.dump(result, stream, indent=2, allow_nan=False)
    try:
        check()
    except BaseException as exc:
        failure(exc, 'post_save_clock');code = 2
        pending = OUTPUT.with_suffix('.failure.pending')
        with pending.open('x', encoding='utf-8') as stream:json.dump(result, stream, indent=2, allow_nan=False)
        os.replace(pending, OUTPUT)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
