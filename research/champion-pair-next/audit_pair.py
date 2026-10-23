"""Thin prospective paired regression audit using frozen R4 formulas unchanged.

Import R4 as a library, never its two-task main. Both arm cores must be sealed
before any training labels are parsed. Qualification remains pending the real
parent exec and fresh terminal ownership/source closure. No fits or API calls.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
import time
import zipfile

R4 = 'repaired-mvp-r1-dev/evaluator_r4.py'
R4_SHA = 'c08e9f0be13a708d67b3266518381d6f1be3b0f43c384ef6425634160d7e2783'
ARCHIVE_SHA = {'A': '16120391716fe43b7f0ec2b36f35eaea7511a08cba4f4108da01cd81dea314d0',
    'B': '52627ac5b9da5ee47d8d40951f84edf9b9dede28cca4b4f90504be6bb4e672b8'}
CHAMPION_SHA = '914880505ed751da9fd0a38d7f1724dd860c20d98456ff3efd16a195a0709ad4'
CHAMPION_SIGNATURE = '959a9b8fed203d71bafbbd4770b6bfb5b6aa5da79d08ee568b93979d7f795421'


def need(value, code):
    if not value:
        raise AssertionError(code)


def load(path):
    return json.loads(Path(path).read_text('utf-8'))


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            result.update(block)
    return result.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for field in ['work-root', 'pair-root', 'manifest', 'manifest-sha256', 'plan', 'plan-sha256', 'self-sha256', 'output']:
        p.add_argument('--'+field, required=True)
    args = p.parse_args()
    need(__debug__, 'nonoptimized_python_required')
    work = Path(args.work_root).resolve()
    def local(name):
        target = (work/name).resolve()
        need(not Path(name).is_absolute() and target.is_relative_to(work), 'audit_reference_outside_work')
        return target
    root, output = local(args.pair_root), local(args.output)
    need(root == work/'cp1' and output == root/'independent-audit.json' and not output.exists(),
         'exclusive_expected_pair_output_required')
    need(digest(__file__) == args.self_sha256 and digest(local(args.manifest)) == args.manifest_sha256
         and digest(local(args.plan)) == args.plan_sha256, 'pair_audit_explicit_pin_failed')
    manifest, plan, campaign = load(local(args.manifest)), load(local(args.plan)), load(root/'campaign.json')
    need(plan['verifier_source_sha256'] == args.self_sha256
         and plan['execution_manifest_sha256'] == args.manifest_sha256
         and plan['manual_metric_verifier_path'] == R4 and plan['manual_metric_verifier_sha256'] == R4_SHA
         and digest(local(R4)) == R4_SHA, 'frozen_manual_metric_source_required')
    need(manifest['schema'] == 'champion-whole-agent-pair-v1' and manifest['common_seconds'] == 5400
         and plan['common_seconds'] == 5400 and plan['pair_order'] == ['A', 'B']
         and plan['reproduction_absolute_tolerance'] == 1e-9, 'declared_pair_contract_changed')
    need(campaign['manifest_sha256'] == args.manifest_sha256
         and campaign['verification_plan_sha256'] == args.plan_sha256
         and campaign['absolute_deadline_unix'] == plan['original_absolute_deadline_unix']
         and campaign['start_unix'] == plan['original_common_start_unix']
         and abs(campaign['absolute_deadline_unix']-campaign['start_unix']-5400) <= 1e-6,
         'original_pair_clock_binding_failed')
    need(campaign['status'] == 'verifying' and campaign['cleanup_confirmed'] is True
         and campaign['source_unchanged'] is True and campaign.get('finished_unix') is None,
         'both_arms_closed_before_live_parent_audit_required')
    def clock():
        need(time.time() < campaign['absolute_deadline_unix']
             and time.monotonic() < campaign['common_deadline_monotonic'], 'original_pair_audit_clock_exhausted')
    def frozen():
        clock()
        need(digest(__file__) == args.self_sha256 and digest(local(args.manifest)) == args.manifest_sha256
             and digest(local(args.plan)) == args.plan_sha256, 'pair_audit_authority_changed')
        for name, expected in manifest['immutable_files'].items():
            need(digest(local(name)) == expected, 'pair_immutable_source_or_input_changed')
            clock()
    entries = {v['arm']: v for v in campaign['arms']}
    need(len(campaign['arms']) == 2 and set(entries) == {'A', 'B'}, 'two_exact_arm_entries_required')
    need(manifest['arms']['B']['argv'] == manifest['arms']['A']['argv']+
         ['--champion-recipe', 'champion_recipe_input.json'], 'only_champion_flag_treatment_required')
    for arm in ['A', 'B']:
        need(campaign['actual_arm_argv'][arm] == manifest['arms'][arm]['argv'], 'actual_frozen_arm_argv_changed')
        entry, arm_meta = entries[arm], manifest['arms'][arm]
        directory = root/arm/'r'
        need(entry['task_allocation_seconds'] == 2100 and entry['solver_budget_seconds'] == 2010
             and entry['parent_cap_seconds'] == 2040, 'equal_task_solver_parent_caps_required')
        need(digest(local(entry['supervisor_path'])) == entry['supervisor_sha256'], 'closed_arm_supervisor_changed')
        terminal = load(local(entry['supervisor_path']))
        for key in ['status', 'exit_code', 'cleanup_confirmed', 'solver_budget_seconds',
                    'parent_cap_seconds', 'child_cap_seconds', 'requested_hpo_budget_seconds',
                    'owned_root', 'owned_process_identities', 'cleanup_observation']:
            need(terminal.get(key) == entry.get(key), 'inline_arm_differs_from_saved_supervisor:'+key)
        need(terminal['cleanup_confirmed'] is True and entry['cleanup_confirmed'] is True
             and terminal['cleanup_observation']['unresolved'] == [], 'arm_owned_cleanup_required')
        need(digest(local(entry['seal']['path'])) == entry['seal']['sha256'], 'arm_prelabel_seal_changed')
        seal = load(local(entry['seal']['path']))
        need(seal['arm'] == arm and seal['cleanup_confirmed'] is True and seal['source_unchanged'] is True
             and seal['sealed_before_independent_label_scoring'] is True, 'arm_prelabel_seal_contract_failed')
        actual = {}
        runs = directory/'automl_runs/repair4'
        if runs.exists():
            for parent, dirs, files in os.walk(runs):
                need(not any((Path(parent)/n).is_symlink() for n in [*dirs, *files]), 'sealed_core_symlink')
                for name in files:
                    need(not name.endswith(('.tmp', '.pending')), 'unfinished_arm_core')
                    path = Path(parent)/name
                    actual[path.relative_to(work).as_posix()] = digest(path)
        if (directory/'submission.csv').exists():
            actual[(directory/'submission.csv').relative_to(work).as_posix()] = digest(directory/'submission.csv')
        need(actual == seal['files_sha256'], 'sealed_arm_core_inventory_or_bytes_changed')
        need(digest(local(arm_meta['archive'])) == ARCHIVE_SHA[arm] == arm_meta['archive_sha256'],
             'frozen_arm_archive_changed')
        with zipfile.ZipFile(local(arm_meta['archive'])) as z:
            need(len(z.namelist()) == 68 and len(set(z.namelist())) == 68
                 and all(Path(n).name == n for n in z.namelist()), 'arm_archive_inventory_changed')
            need({n: hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()} == arm_meta['compiled_sha256'],
                 'arm_compiled_archive_changed')
    frozen()
    # This is the first import of NumPy/Pandas, and the first point after which
    # verify_task may parse pristine training labels. Both seals already passed.
    spec = importlib.util.spec_from_file_location('_frozen_R4_pair_library', local(R4))
    r4 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(r4)
    r4.WORK, r4.REPO, r4.RUN_NAME = work, work/'alfa-hack-automl', 'repair4'
    rows = {}
    for arm in ['A', 'B']:
        clock()
        entry, arm_meta = entries[arm], manifest['arms'][arm]
        directory = root/arm/'r'
        if entry.get('status') != 'ok' or entry.get('exit_code') != 0:
            rows[arm] = dict(procedure_passed=False, qualified_selected_cut_mean=None,
                errors=['whole_agent_arm_nonzero_or_not_ok'], raw_r4=None, champion_primary=None,
                failed_metric_zero_imputed=False)
            continue
        try:
            r4.ROOT = root/arm
            raw = r4.verify_task(arm_meta['tasks'][0], arm_meta, plan, entry)
            report = load(directory/'automl_runs/repair4/report.json')
            need(Path(report['spec']['root']).resolve() == directory.resolve(), 'arm_spec_root_changed')
            need({'lightgbm', 'catboost', 'xgboost'} <= set(raw['successful_model_families']),
                 'all_three_required_model_families_must_succeed')
            hpo = load(directory/'automl_runs/repair4/inner-hpo/hpo.json')
            protected = load(local(plan['protected_control_recipes']['regression']['path']))
            need(hpo['control_recipe'] == protected['components'][0], 'exact_preserved_SINGLE_HPO_anchor_changed')
            for phase in ['primary', 'confirmation']:
                expected = plan['expected_regression_splits'][phase]
                for key in ['fitting_rows', 'validation_rows', 'positions_sha256',
                            'training_rows_canonical_sha256', 'split_file_sha256', 'validation_periods']:
                    need(raw['cuts'][phase][key] == expected[key], 'arm_exact_declared_regression_cut_changed')
            champion_primary = champion_confirmation = None
            if arm == 'A':
                need(not (directory/'champion_recipe_input.json').exists()
                     and 'champion_recipe' not in report and 'champion_seed' not in report['pipeline'],
                     'control_arm_has_champion_treatment')
            else:
                input_path = directory/'champion_recipe_input.json'
                need(digest(input_path) == CHAMPION_SHA == plan['expected_champion_input_sha256'],
                     'champion_input_identity_changed')
                champion = load(input_path)
                runs = directory/'automl_runs/repair4'
                need(report['champion_recipe'] == champion == load(runs/'champion_recipe.json'),
                     'champion_normalized_snapshot_or_report_changed')
                provenance = load(runs/'provenance.json')['sha256']
                need(provenance['champion_recipe'] == CHAMPION_SHA
                     and provenance['champion_recipe_snapshot'] == digest(runs/'champion_recipe.json'),
                     'champion_runtime_provenance_changed')
                receipt = load(runs/'champion-seed.json')
                seed = report['pipeline']['champion_seed']
                need(receipt['input_sha256'] == CHAMPION_SHA and receipt['input_bytes'] == input_path.stat().st_size
                     and receipt['recipe_signature'] == CHAMPION_SIGNATURE == plan['expected_champion_signature']
                     and seed['recipe_signature'] == CHAMPION_SIGNATURE and seed['maximum_initial'] == 7,
                     'champion_loader_or_admission_receipt_changed')
                admission = [v for v in report['pipeline']['initial_queue_receipts'] if v.get('source') == 'prior_champion']
                need(len(admission) == 1 and admission[0]['status'] == 'scheduled'
                     and admission[0]['signature'] == CHAMPION_SIGNATURE and admission[0]['queue_index'] == 5,
                     'champion_required_actual_admission_missing')
                record = report['champion_measurements']['primary']
                need(record is not None and record['status'] == 'ok' and record['recipe'] == champion
                     and record.get('experiment_index') == 5 and record in report['experiments'],
                     'champion_successful_actual_primary_measurement_missing')
                # verify_task already parsed exact immutable inputs and audited
                # selected/control/FE/HPO records. Verify this additional seed
                # even when it did not become the selected full procedure.
                train, test, sample = [r4.pd.read_csv(directory/name) for name in ['train.csv', 'test.csv', 'sample_submission.csv']]
                verifier = r4.TaskVerifier(directory, report, train, test, sample)
                champion_primary = r4.diagnostics(verifier, record, runs/'split.npz', 'primary')
                second = report['champion_measurements']['confirmation']
                if second is not None:
                    need(second['status'] == 'ok' and second['recipe'] == champion and second in report['confirmations'],
                         'champion_confirmation_reference_changed')
                    champion_confirmation = r4.diagnostics(verifier, second, runs/'confirmation_split.npz', 'confirmation')
            rows[arm] = dict(procedure_passed=raw['procedure_passed'],
                qualified_selected_cut_mean=raw['selected_cut_mean'] if raw['procedure_passed'] else None,
                errors=list(raw['errors']), raw_r4=raw, champion_primary=champion_primary,
                champion_confirmation=champion_confirmation, actual_initial_queue_receipts=report['pipeline']['initial_queue_receipts'],
                planner_calls_reported=len(report.get('llm_calls', [])),
                failed_metric_zero_imputed=False)
        except Exception as exc:
            trace = exc.__traceback__
            while trace is not None and trace.tb_next is not None:
                trace = trace.tb_next
            reason = str(exc)
            rows[arm] = dict(procedure_passed=False, qualified_selected_cut_mean=None,
                errors=['R4_or_pair_arm_contract_failed'], exception_type=type(exc).__name__,
                contract_reason=reason if isinstance(exc, AssertionError)
                    and re.fullmatch('[A-Za-z0-9_:+.-]{1,200}', reason) else None,
                errno=getattr(exc, 'errno', None), winerror=getattr(exc, 'winerror', None),
                failure_source_basename=Path(trace.tb_frame.f_code.co_filename).name if trace else None,
                failure_source_line=trace.tb_lineno if trace else None,
                raw_r4=locals().get('raw') if isinstance(locals().get('raw'), dict) else None,
                champion_primary=None, failed_metric_zero_imputed=False)
        finally:
            # Prevent a failed B check from accidentally referring to A raw data.
            raw = None
    passed = all(rows[a]['procedure_passed'] for a in ['A', 'B'])
    comparison = None
    win = None
    if passed:
        a, b = rows['A']['raw_r4'], rows['B']['raw_r4']
        toler = plan['reproduction_absolute_tolerance']
        floors = plan['T5_cut_floors']
        cuts = []
        for phase, floor_key in [('primary', 'primary_rmse'), ('confirmation', 'confirmation_rmse')]:
            av, bv = a['cuts'][phase]['value'], b['cuts'][phase]['value']
            need(all(type(x) in (int, float) and math.isfinite(x) for x in [av, bv, floors[floor_key]]),
                 'nonfinite_pair_comparison')
            cuts.append(dict(phase=phase, A=av, B=bv, delta_B_minus_A=bv-av,
                B_no_worse_than_A=bv <= av+toler, retained_T5_floor=floors[floor_key],
                B_meets_retained_T5_floor=bv <= floors[floor_key]+toler))
        win = b['selected_cut_mean'] < a['selected_cut_mean'] and all(
            c['B_no_worse_than_A'] and c['B_meets_retained_T5_floor'] for c in cuts)
        comparison = dict(cuts=cuts, A_mean=a['selected_cut_mean'], B_mean=b['selected_cut_mean'],
            delta_B_minus_A=b['selected_cut_mean']-a['selected_cut_mean'],
            absolute_reproduction_tolerance=toler, descriptive_retention_win=win,
            independent_raw_T5_predictions_reverified=False,
            limitation='T5 cut floor is pinned previously audited reused-public evidence; one stochastic A/B does not establish stable causal or blind/private gain.')
    frozen()
    # Recheck every sealed byte AFTER scoring as well; a late change is fatal.
    for arm in ['A', 'B']:
        seal = load(local(entries[arm]['seal']['path']))
        need(digest(local(entries[arm]['seal']['path'])) == entries[arm]['seal']['sha256'], 'late_arm_seal_changed')
        for name, expected in seal['files_sha256'].items():
            need(digest(local(name)) == expected, 'late_arm_core_changed')
        directory = root/arm/'r'
        need(digest(local(entries[arm]['supervisor_path'])) == entries[arm]['supervisor_sha256'],
             'late_arm_supervisor_changed')
        for name, expected in manifest['arms'][arm]['compiled_sha256'].items():
            need(digest(directory/name) == expected, 'late_deployed_flat_source_changed')
        for name, expected in manifest['task']['files'].items():
            need(digest(directory/name) == digest(local(manifest['task']['source'])/name) == expected,
                 'late_deployed_pristine_input_changed')
    clock()
    result = dict(status='paired_saved_artifacts_verified_pending_parent_terminal' if passed else 'paired_saved_artifacts_unqualified_pending_parent_terminal',
        arms=rows, artifact_procedure_checks_passed=passed, audit_within_original_common_clock=True,
        campaign_terminal_confirmed=False, parent_exec_terminal_qualification_required=True,
        actual_common_deadline_satisfied=None, manifest_sha256=args.manifest_sha256,
        verification_plan_sha256=args.plan_sha256, campaign_sha256=digest(root/'campaign.json'),
        manual_metric_source_sha256=R4_SHA, comparison=comparison, descriptive_retention_win=win,
        quality_metric=None if not passed else {'A_mean_rmse': rows['A']['qualified_selected_cut_mean'],
            'B_mean_rmse': rows['B']['qualified_selected_cut_mean']},
        failed_metrics_zero_imputed=False, source_and_core_rechecked=True,
        new_model_fits=0, API_calls=0, tests_run=0, promotion=False, submit=False, official_score=None,
        scope='Independent sealed-artifact whole-regression-agent A/B on reused public temporal cuts; source/parent terminal qualification is separate')
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    clock()
    print(json.dumps({'status': result['status'], 'artifact_procedure_checks_passed': passed,
        'output': output.name, 'parent_exec_terminal_qualification_required': True}))


if __name__ == '__main__':
    main()
