"""PROPOSED posthoc saved-artifact pair0 diagnostic; never executed during preparation.

Derived from the pre-outcome independent CV verifier after its canonical enum defect.
Original campaign remains terminal technical failure and incomplete CV. This module
requires a new root-reviewed declaration and successful terminal ownership closure;
it never launches/fits/signals or opens the private run-budget ledger.
"""
from copy import deepcopy
from itertools import combinations
from pathlib import Path
import argparse
import hashlib
import json
import math
import sys
import time
import zipfile

import numpy as np
import pandas as pd


PROTOCOL_SHA = '5b2164c3721c84b8e6eb85c0dec7571474316b2e956d6ecdeee235d0193addcb'
PUBLICATION_SHA = '1c416cc08ea700fc2c6bece457f1f38e46e897bfa1c8cd3c007036a68685be98'
SOURCE_PUBLICATION_SHA = 'd4b3ac1ebdbb860d6cb126224807db29de80d997c209aa9a9e206290186c9a51'
FOLD_MANIFEST_SHA = 'f8a0b9ad5b3e9e403aa9a567234ba203c8537c19eee78dd6257d9d8259bb4910'
FROZEN_FILES_SHA = '9883c8fe781be541dbbeefe831ea73a3b939628aea09a470e155ee1e1fac1224'
ARCHIVE_SHA = {'a': '88dac47a9a815b98b5d00c44e5650518f84db5197c9eac56b79fb1ce465c92a0',
               'b': 'd5144685e682654bfed3a0e216ecec4f2ada4868b7df0e0d9779aba9f79d77bc'}
FIXED = 'categorical_te_capacity_pair'
ORDER = [(0, 'a'), (0, 'b'), (1, 'b'), (1, 'a'), (2, 'a'), (2, 'b')]


class AuditError(RuntimeError):
    """Fixed-code evidence error; do not expose arbitrary source error text."""


def require(condition, code):
    if not condition:
        raise AuditError(code)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            value.update(block)
    return value.hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def same_number(actual, reported):
    return finite(reported) and math.isclose(actual, reported, rel_tol=1e-10, abs_tol=1e-10)


def within(work, value):
    path = Path(value)
    if not path.is_absolute():
        if path.parts and path.parts[0] == 'work':
            path = Path(*path.parts[1:])
        path = work / path
    path = path.resolve()
    require(path.is_relative_to(work), 'path_outside_work')
    return path


def check_clock(plan, deadline=None):
    absolute = plan.get('common_absolute_deadline_unix')
    monotonic = plan.get('common_deadline_monotonic')
    require(finite(absolute) and finite(monotonic), 'missing_common_deadline')
    require(time.time() <= absolute, 'common_absolute_deadline_exhausted')
    require(time.monotonic() <= monotonic, 'common_monotonic_deadline_exhausted')
    if deadline is not None:
        require(finite(deadline) and deadline <= monotonic, 'invalid_audit_deadline')
        require(time.monotonic() <= deadline, 'audit_deadline_exhausted')


def bound_ref(work, ref, expected):
    require(isinstance(ref, dict) and ref.get('sha256') == expected, 'reference_hash_mismatch')
    path = within(work, ref['path'])
    require(digest(path) == expected, 'reference_bytes_changed')
    return path


# This separate diagnostic never repairs or resumes the original CV attempt.
ORIGINAL_VERIFIER_SHA = '33f98e1bdb44743b8b55e7e694459c2dc2c19dd5db8359c51747cc5c62274519'
ORIGINAL_STAGE_SHA = 'd2e5f64276e639fd6f20b315014701bb12352b2f2c65b3294ced04a9ccd7c456'
ORIGINAL_MANIFEST_SHA = 'a70f2a0cefb686dd04535c76b4c9e9e80073aba23d86fd7aad7e52fc7b9eee6a'
POSTHOC_SCOPE = 'posthoc_pair0_saved_artifact_diagnostic_only'


def posthoc_context(work, plan, stage, deadline):
    """Require a separate root decision and complete terminal ownership proof."""
    check_clock(plan, deadline)
    require(deadline is not None, 'posthoc_bounded_deadline_required')
    require(plan.get('stage_receipt_path') == 'f4/stage1.json' and
            digest(within(work, plan['stage_receipt_path'])) == ORIGINAL_STAGE_SHA,
            'posthoc_original_terminal_stage_changed')
    require(plan.get('manifest_sha256') == ORIGINAL_MANIFEST_SHA and
            plan.get('verifier_source_sha256') == ORIGINAL_VERIFIER_SHA and
            digest(work / 'fullagent-cv-launch-r4/independent_verifier.py') == ORIGINAL_VERIFIER_SHA,
            'posthoc_original_verifier_ancestry_wrong')
    require(stage.get('status') == 'rejected_early_incomplete_CV' and
            stage.get('rejection_kind') == 'technical_failure' and
            stage.get('exception_type') == 'AuditError' and
            stage.get('failure_code') == 'unsupported_outer_output_contract' and
            stage.get('complete_CV') is False and stage.get('OOF_complete') is False and
            stage.get('final_CV') is None and stage.get('promotion') is False and
            stage.get('source_unchanged') is True and stage.get('cleanup_confirmed') is True,
            'posthoc_original_failure_scope_wrong')
    declaration_ref = plan.get('posthoc_declaration') or {}
    require(isinstance(declaration_ref.get('sha256'), str), 'posthoc_declaration_binding_missing')
    declaration = load(bound_ref(work, declaration_ref, declaration_ref['sha256']))
    require(declaration.get('scope') == POSTHOC_SCOPE and
            declaration.get('root_reviewed') is True and
            declaration.get('execution_authorized') is True and
            declaration.get('original_stage_sha256') == ORIGINAL_STAGE_SHA and
            declaration.get('original_manifest_sha256') == ORIGINAL_MANIFEST_SHA and
            declaration.get('original_verifier_sha256') == ORIGINAL_VERIFIER_SHA and
            declaration.get('posthoc_verifier_sha256') == digest(Path(__file__)) and
            declaration.get('fits_allowed') is False and declaration.get('api_calls_allowed') is False and
            declaration.get('full_CV_or_qualification_allowed') is False,
            'posthoc_root_declaration_wrong')
    start, seconds = declaration.get('audit_start_monotonic'), declaration.get('audit_cap_seconds')
    require(finite(start) and finite(seconds) and 0 < seconds <= 600 and
            start <= time.monotonic() and deadline == start + seconds,
            'posthoc_audit_cap_wrong')
    closure_ref = declaration.get('terminal_ownership') or {}
    require(isinstance(closure_ref.get('sha256'), str), 'posthoc_terminal_ownership_binding_missing')
    closure = load(bound_ref(work, closure_ref, closure_ref['sha256']))
    require(closure.get('stage_receipt_sha256') == ORIGINAL_STAGE_SHA and
            closure.get('cleanup_confirmed') is True and
            closure.get('source_unchanged') is True and
            closure.get('immutable_files_rehashed') == 430 and
            closure.get('fresh_absence_before_and_inside_canonical_lock') is True and
            closure.get('strict_known_parent_orphan_scan') is True and
            closure.get('active_owned_processes') == [] and
            closure.get('exec_exit_code_observed_by_root') == 1,
            'posthoc_complete_terminal_ownership_required')
    tracked = closure.get('tracked_identities')
    launchers = closure.get('launcher_identities')
    require(isinstance(tracked, list) and tracked and isinstance(launchers, list) and launchers,
            'posthoc_terminal_identity_union_missing')
    fresh_gone({'cleanup_confirmed': True, 'owned_root': launchers[0],
                'owned_process_identities': tracked + launchers})
    return declaration


def posthoc_slot_terminal(slot, stage):
    # Keep stage_slot's exact comparison with the original terminal receipt.
    if slot.get('fold') == 0 and slot.get('arm') == 'a':
        return slot.get('status') == 'sealed_complete'
    if slot.get('fold') == 0 and slot.get('arm') == 'b':
        return (slot.get('status') == 'technical_failure' and
                stage.get('failure_code') == 'unsupported_outer_output_contract' and
                stage.get('exception_type') == 'AuditError')
    return False


def context(work, plan, fold_manifest, deadline):
    work = Path(work).resolve()
    check_clock(plan, deadline)
    stage = load(within(work, plan['stage_receipt_path']))
    require(stage.get('common_seconds') == 64800, 'stage_duration_changed')
    for name in ['common_absolute_deadline_unix', 'common_deadline_monotonic']:
        require(finite(stage.get(name)) and stage[name] == plan[name], 'stage_clock_binding_mismatch')
    require(finite(stage.get('common_start_unix')) and finite(stage.get('common_start_monotonic')) and
            math.isclose(stage['common_start_unix'] + 64800, plan['common_absolute_deadline_unix'], abs_tol=1e-6, rel_tol=0) and
            math.isclose(stage['common_start_monotonic'] + 64800, plan['common_deadline_monotonic'], abs_tol=1e-6, rel_tol=0),
            'stage_clock_reset_or_extension')
    posthoc_context(work, plan, stage, deadline)
    require(digest(within(work, plan['manifest_path'])) == plan['manifest_sha256'], 'supervisor_manifest_changed')
    require(load(within(work, plan['manifest_path'])) == plan['manifest'], 'supervisor_manifest_object_mismatch')
    require(stage.get('manifest_sha256') == plan['manifest_sha256'], 'stage_manifest_binding_wrong')
    require(plan['manifest'].get('independent_verifier_sha256') == plan['verifier_source_sha256'],
            'supervisor_does_not_pin_verifier')
    immutable = plan['manifest'].get('immutable_files')
    require(isinstance(immutable, dict) and immutable, 'immutable_source_registry_missing')
    bound_ref(work, plan['r3_protocol'], PROTOCOL_SHA)
    publication = load(bound_ref(work, plan['publication_receipt'], PUBLICATION_SHA))
    require(publication.get('root_protocol_reviewed') is True and publication.get('remote_sha_verified') is True,
            'protocol_not_published')
    source_publication = load(bound_ref(work, plan['source_publication_receipt'], SOURCE_PUBLICATION_SHA))
    require(source_publication.get('root_source_reviewed') is True and source_publication.get('remote_sha_verified') is True and
            source_publication.get('archive_sha256') == ARCHIVE_SHA, 'candidate_source_not_published')
    base = work / 'fullagent-cv-stage1-plan-r1'
    require(digest(base / 'manifest.json') == FOLD_MANIFEST_SHA, 'fold_manifest_changed')
    require(load(base / 'manifest.json') == fold_manifest, 'fold_manifest_object_mismatch')
    import sklearn
    require(fold_manifest['versions'] == {'python': sys.version.split()[0], 'numpy': np.__version__,
                                         'pandas': pd.__version__, 'sklearn': sklearn.__version__},
            'split_dependency_versions_changed')
    require(digest(base / 'frozen-files.json') == FROZEN_FILES_SHA, 'frozen_input_registry_changed')
    archives = {}
    for arm in ['a', 'b']:
        path = bound_ref(work, plan['archives'][arm], ARCHIVE_SHA[arm])
        with zipfile.ZipFile(path) as packed:
            names = packed.namelist()
            require(len(names) == len(set(names)) == 68, 'archive_member_inventory_invalid')
            archives[arm] = {name: hashlib.sha256(packed.read(name)).hexdigest() for name in names}
    require([(s['fold'], s['arm']) for s in stage['arms']] == ORDER, 'saved_stage_six_slots_changed')
    return work, archives, stage


def frozen_inputs(work, plan, fold_manifest, deadline):
    """Called only after BOTH arm seals/terminal ownership have been verified."""
    for relative, expected in plan['manifest']['immutable_files'].items():
        check_clock(plan, deadline)
        require(digest(within(work, relative)) == expected, 'immutable_source_changed')
    base = work / 'fullagent-cv-stage1-plan-r1'
    for relative, expected in load(base / 'frozen-files.json')['files_sha256'].items():
        check_clock(plan, deadline)
        require(digest(base / relative) == expected, 'frozen_fold_file_changed')
    for relative, expected in fold_manifest['pristine_input_sha256'].items():
        require(digest(within(work, relative)) == expected, 'pristine_input_changed')
    arrays_path = within(work, fold_manifest['outer_fold_arrays'])
    require(digest(arrays_path) == fold_manifest['outer_fold_arrays_sha256'], 'outer_arrays_changed')
    with np.load(arrays_path, allow_pickle=False) as saved:
        arrays = {name: saved[name].copy() for name in saved.files}
    n = fold_manifest['row_count']
    coverage = np.zeros(n, dtype=np.int64)
    for fold in range(3):
        train, validation = arrays[f'fold{fold}_train'], arrays[f'fold{fold}_validation']
        validate_partition(train, validation, n)
        require(not np.intersect1d(arrays['raw_feature_hashes'][train], arrays['raw_feature_hashes'][validation]).size,
                'outer_feature_group_overlap')
        coverage[validation] += 1
    require(np.all(coverage == 1) and np.array_equal(coverage, arrays['coverage']), 'outer_coverage_invalid')
    return arrays


def validate_partition(train, validation, n):
    for rows in [train, validation]:
        require(rows.ndim == 1 and rows.dtype.kind in 'iu' and len(rows) > 0, 'split_rows_invalid')
        require(rows.min() >= 0 and rows.max() < n and len(np.unique(rows)) == len(rows), 'split_indices_invalid')
    require(not np.intersect1d(train, validation).size and len(train) + len(validation) == n,
            'split_not_disjoint_complete')


def expected_inner_split(spec, frame, hashes, seed):
    """Independent reproduction of the frozen non-temporal classification split."""
    from sklearn.model_selection import StratifiedGroupKFold, train_test_split
    require(spec.get('validation_strategy') not in ('time', 'group'), 'unsupported_inner_semantic_split')
    positions, y = np.arange(len(frame)), frame[spec['target']]
    method = 'stratified_holdout_20pct'
    if spec['duplicate_feature_rate'] > .05:
        groups = pd.DataFrame({'y': y.to_numpy(), 'g': hashes}).groupby('y')['g'].nunique()
        size = min(5, int(groups.min()))
        if size >= 2:
            train, validation = next(StratifiedGroupKFold(n_splits=size, shuffle=True,
                random_state=seed).split(positions, y, groups=hashes))
            method = f'stratified_group_feature_hash_{size}fold_fold0'
        else:
            train, validation = train_test_split(positions, test_size=.2, random_state=seed,
                stratify=y if y.value_counts().min() >= 2 else None)
            method = 'stratified_holdout_20pct_rare_group_fallback'
    else:
        train, validation = train_test_split(positions, test_size=.2, random_state=seed,
            stratify=y if y.value_counts().min() >= 2 else None)
    require(not set(y.iloc[validation]) - set(y.iloc[train]), 'inner_split_missing_fitting_class')
    info = {'method': method, 'seed': seed, 'train_rows': len(train), 'validation_rows': len(validation),
        'split_sha256': hashlib.sha256(np.asarray(train, dtype='<i8').tobytes() +
                                      np.asarray(validation, dtype='<i8').tobytes()).hexdigest(),
        'shared_feature_hashes': len(set(hashes[train]) & set(hashes[validation])),
        'validation_class_counts': y.iloc[validation].value_counts().to_dict()}
    return np.asarray(train), np.asarray(validation), info


def identity(value):
    require(isinstance(value, dict), 'owned_identity_missing')
    pid, created = value.get('pid'), value.get('create_time')
    require(type(pid) is int and pid > 0 and finite(created), 'owned_identity_invalid')
    return pid, created


def fresh_gone(supervisor):
    """Read-only PID/create_time check. Never act on an unowned or reused PID."""
    import psutil
    require(supervisor.get('cleanup_confirmed') is True, 'owned_cleanup_unconfirmed')
    seen = [identity(supervisor['owned_root'])]
    values = supervisor.get('owned_process_identities')
    require(isinstance(values, list) and values, 'owned_tracker_empty')
    seen.extend(identity(value) for value in values)
    for pid, created in set(seen):
        try:
            process = psutil.Process(pid)
            if abs(process.create_time() - created) > 1e-6:
                continue
            require(not process.is_running(), 'owned_identity_still_live')
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied as exc:
            raise AuditError('owned_identity_access_denied') from None


def stage_slot(slot, stage):
    matches = [saved for saved in stage['arms'] if saved['fold'] == slot['fold'] and saved['arm'] == slot['arm']]
    require(len(matches) == 1, 'slot_missing_from_saved_stage')
    saved = matches[0]
    for key in ['fold', 'arm', 'status', 'exit_code', 'cleanup_confirmed', 'output_dir', 'report_path',
                'source_archive_sha256', 'command', 'seal', 'seal_sha256', 'sealed', 'supervisor',
                'supervisor_sha256', 'supervisor_receipt_path', 'supervisor_receipt_sha256']:
        require(saved.get(key) == slot.get(key), 'slot_disagrees_with_saved_stage')


def supervisor_receipt(work, slot, stage):
    stage_slot(slot, stage)
    expected = slot.get('supervisor_receipt_sha256')
    require(isinstance(expected, str), 'saved_supervisor_hash_missing')
    path = within(work, slot['supervisor_receipt_path'])
    require(digest(path) == expected, 'saved_supervisor_receipt_changed')
    require(load(path) == slot['supervisor'], 'inline_supervisor_differs_saved_receipt')
    require(canonical(slot['supervisor']) == slot.get('supervisor_sha256'), 'supervisor_receipt_unbound')
    fresh_gone(slot['supervisor'])
    return slot['supervisor']


class SealedArm:
    def __init__(self, work, slot, archives, plan, deadline, stage):
        require(posthoc_slot_terminal(slot, stage), 'posthoc_arm_not_original_terminal_complete')
        require(type(slot.get('exit_code')) is int and slot['exit_code'] == 0 and
                slot.get('cleanup_confirmed') is True, 'arm_not_terminal_clean')
        require(slot.get('source_archive_sha256') == ARCHIVE_SHA[slot['arm']], 'arm_archive_wrong')
        supervisor = supervisor_receipt(work, slot, stage)
        require(supervisor.get('status') == 'ok' and type(supervisor.get('exit_code')) is int and
                supervisor['exit_code'] == 0, 'successful_saved_supervisor_required')
        require(supervisor.get('API_limit') == 0 and
                type(supervisor.get('maximum_logical_worker_jobs')) is int and
                0 <= supervisor['maximum_logical_worker_jobs'] <= 1 and
                finite(supervisor.get('peak_owned_tree_rss_mib')) and
                0 <= supervisor['peak_owned_tree_rss_mib'] <= 2048,
                'saved_resource_or_serial_guard_violation')
        require(all(finite(supervisor.get(key)) for key in ['start_unix', 'start_monotonic', 'end_unix', 'seconds']) and
                supervisor['seconds'] >= 0 and
                stage['common_start_unix'] <= supervisor['start_unix'] <= supervisor['end_unix'] <= plan['common_absolute_deadline_unix'] and
                stage['common_start_monotonic'] <= supervisor['start_monotonic'] and
                supervisor['start_monotonic'] + supervisor['seconds'] <= plan['common_deadline_monotonic'],
                'saved_supervisor_outside_common_clock')
        self.work = work
        self.root = within(work, slot['output_dir'])
        self.slot, self.plan, self.deadline = slot, plan, deadline
        seal = slot['seal']
        require(canonical(seal) == slot.get('seal_sha256'), 'seal_hash_mismatch')
        require(within(work, seal['root']) == self.root, 'seal_root_mismatch')
        require(finite(seal.get('sealed_unix')) and seal['sealed_unix'] <= time.time(), 'seal_clock_invalid')
        require(seal['sealed_unix'] <= plan['common_absolute_deadline_unix'], 'seal_after_common_deadline')
        self.files = seal['files_sha256']
        require(isinstance(self.files, dict) and self.files, 'empty_seal')
        require(slot.get('sealed') == self.files, 'seal_alias_mismatch')
        for relative, expected in self.files.items():
            check_clock(plan, deadline)
            path = self.path(relative, verify=False)
            require(digest(path) == expected, 'sealed_artifact_changed')
        for name, expected in archives[slot['arm']].items():
            require(self.sha(name) == expected, 'deployed_source_changed')
        command = slot['command']
        require(isinstance(command, list) and len(command) == 7, 'command_contract_wrong')
        require(command[0] == '<same_python>' and
                command[1:] == ['-u', 'solution.py', 'task.md', '--offline', '--max-llm-calls', '0'],
                'offline_zero_cap_command_wrong')
        # Length includes one executable and six fixed arguments.
        self.report_path = self.path(within(work, slot['report_path']))
        self.report = load(self.report_path)
        require(self.report.get('final_fit_status') == 'ok' and self.report.get('integrity_ok') is True,
                'mandatory_refit_or_integrity_failed')
        budget = self.report.get('run_budget') or {}
        require(budget.get('gateway_call_limit') == 0 and budget.get('gateway_calls_started') == 0,
                'api_zero_cap_report_mismatch')
        require(budget.get('http_attempts_reported') == 0 and self.report.get('llm_calls') == [],
                'api_zero_activity_report_mismatch')
        require('hpo' not in self.report and 'pipeline' not in self.report and
                not self.report.get('feature_selection_top_k'), 'ordinary_route_changed')
        provenance = self.json(self.report['provenance_path'])['sha256']
        require(provenance.get('task') == self.sha('task.md'), 'task_provenance_wrong')
        for role, name in [('train', 'train.csv'), ('test', 'test.csv'), ('sample_submission', 'sample_submission.csv'),
                           ('data_dictionary', 'data_dictionary.csv')]:
            require(provenance.get('input:' + role) == self.sha(name), 'input_provenance_wrong')
        for name in archives[slot['arm']]:
            if name.endswith('.py'):
                key = 'source:' + str(self.root / name)
                require(provenance.get(key) == self.sha(name), 'source_provenance_wrong')

    def path(self, value, verify=True):
        path = Path(value)
        path = (self.root / path).resolve() if not path.is_absolute() else path.resolve()
        require(path.is_relative_to(self.root), 'artifact_outside_arm')
        relative = path.relative_to(self.root).as_posix()
        require(not any(part.startswith('run-budget-') for part in path.parts), 'private_ledger_read_forbidden')
        require(relative in self.files, 'mandatory_artifact_not_sealed')
        if verify:
            require(digest(path) == self.files[relative], 'sealed_artifact_changed')
        return path

    def sha(self, value):
        return digest(self.path(value))

    def json(self, value):
        return load(self.path(value))

    def recheck(self):
        supervisor_receipt(self.work, self.slot, load(within(self.work, self.plan['stage_receipt_path'])))
        for relative, expected in self.files.items():
            check_clock(self.plan, self.deadline)
            require(digest(self.path(relative, verify=False)) == expected, 'sealed_artifact_changed_after_audit')


def probability(arm, path, classes, rows=None, expected_rows=None):
    with np.load(arm.path(path), allow_pickle=False) as saved:
        order = saved['classes'].astype(str).tolist()
        values = saved['probabilities'].copy()
        if rows is not None:
            require('row_position' in saved and saved['row_position'].dtype.kind in 'iu' and
                    np.array_equal(saved['row_position'], rows), 'probability_row_order_wrong')
    require(len(order) == len(set(order)) == len(classes) and set(order) == set(classes), 'probability_classes_wrong')
    require(values.ndim == 2 and values.shape[1] == len(classes), 'probability_shape_wrong')
    if expected_rows is not None:
        require(len(values) == expected_rows, 'probability_row_count_wrong')
    require(np.isfinite(values).all() and (values >= 0).all() and (values <= 1).all(), 'probability_invalid')
    require(np.allclose(values.sum(axis=1), 1, rtol=1e-10, atol=1e-10), 'probability_not_normalized')
    return values[:, [order.index(name) for name in classes]]


def score(truth, predicted, classes):
    lookup = {name: i for i, name in enumerate(classes)}
    require(set(truth) <= set(classes) and set(predicted) <= set(classes), 'prediction_label_invalid')
    counts = np.zeros((len(classes), len(classes)), dtype=np.int64)
    np.add.at(counts, ([lookup[name] for name in truth], [lookup[name] for name in predicted]), 1)
    denominator = counts.sum(axis=0) + counts.sum(axis=1)
    per_class = np.divide(2 * np.diag(counts), denominator, out=np.zeros(len(classes)), where=denominator > 0)
    return float(per_class.mean()), dict(zip(classes, map(float, per_class)))


def view_children(recipe, spec):
    mode = recipe['params']['feature_views']
    require(mode in ('categorical_te_pair', FIXED), 'unknown_feature_view')
    plain = deepcopy(recipe)
    plain['params'].pop('feature_views')
    encoded = deepcopy(plain)
    columns = [name for name in spec['features'] if name in set(spec['categorical_features'])][:3]
    encoded['params'].update(target_encoding=True, target_encoding_groups=[list(pair) for pair in combinations(columns, 2)],
                             target_encoding_smoothing=20.)
    plain['hypothesis'] = 'Fixed feature view: original categorical features'
    encoded['hypothesis'] = 'Fixed feature view: fitting-cross-fitted categorical statistics'
    children = [plain, encoded]
    if mode == FIXED:
        require(plain['params']['num_leaves'] == 63, 'fixed_base_capacity_wrong')
        larger = deepcopy(children)
        for child in larger:
            child['params']['num_leaves'] = 98
        children += larger
    return children


def median_tree(a, b):
    if isinstance(a, list) or isinstance(b, list):
        require(isinstance(a, list) and isinstance(b, list) and len(a) == len(b), 'iteration_tree_mismatch')
        return [median_tree(x, y) for x, y in zip(a, b)]
    require(type(a) is int and type(b) is int and 1 <= a <= 3000 and 1 <= b <= 3000, 'iteration_leaf_invalid')
    return max(30, int(np.median([a, b])))


def has_fixed(recipe):
    return recipe.get('params', {}).get('feature_views') == FIXED or any(has_fixed(c) for c in recipe.get('components', []))


class ArtifactAudit:
    def __init__(self, arm, fold, manifest, expected_split_cache):
        self.arm, self.report, self.fold = arm, arm.report, fold
        self.spec = self.report['spec']
        self.classes = manifest['canonical_class_order']
        require(self.spec['kind'] == 'classification' and self.spec['metric'] == 'macro_f1', 'task_metric_wrong')
        require(self.spec['classes'] == self.classes and self.spec['features'] == manifest['raw_feature_schema_order'],
                'task_schema_wrong')
        require(self.spec['target'] == manifest['target_column'] and self.spec['id'] == manifest['id_column'],
                'target_id_roles_wrong')
        require(self.spec['target'] not in self.spec['features'] and self.spec['id'] not in self.spec['features'], 'target_id_in_features')
        require(self.spec.get('prediction_type') == 'value' and self.spec.get('output_columns') == [self.spec['target']],
                'unsupported_outer_output_contract')
        for name, expected in fold['solver_inputs_sha256'].items():
            require(arm.sha(name) == expected, 'deployed_fold_input_changed')
        require(Path(self.spec['root']).resolve() == arm.root, 'spec_root_wrong')
        require(set(self.spec['paths']) == {'train', 'test', 'sample_submission', 'data_dictionary'}, 'spec_input_roles_wrong')
        for role, name in [('train', 'train.csv'), ('test', 'test.csv'), ('sample_submission', 'sample_submission.csv'),
                           ('data_dictionary', 'data_dictionary.csv')]:
            require(Path(self.spec['paths'][role]).resolve() == arm.path(name), 'spec_path_wrong')
        self.train = pd.read_csv(arm.path('train.csv'))
        self.test = pd.read_csv(arm.path('test.csv'))
        self.sample = pd.read_csv(arm.path('sample_submission.csv'))
        dictionary = pd.read_csv(arm.path('data_dictionary.csv'))
        declared = [str(row['feature']) for row in dictionary.to_dict(orient='records')
                    if str(row.get('dtype', '')).lower() in ('category', 'categorical') and row['feature'] in self.spec['features']]
        require(self.spec['categorical_features'] == declared, 'categorical_schema_roles_wrong')
        require(self.spec['target'] not in self.test, 'outer_target_leaked')
        self.hashes = pd.util.hash_pandas_object(self.train[self.spec['features']], index=False).to_numpy(dtype='uint64')
        require(same_number(float(pd.Series(self.hashes).duplicated().mean()), self.spec['duplicate_feature_rate']),
                'duplicate_feature_rate_wrong')
        self.visited = {}
        self.leaves = {}
        self.fixed_nodes = {}
        self.split_cache, self.expected_split_cache = {}, expected_split_cache

    def expected(self, rows, seed):
        # Both arms have the same SHA-bound fitting CSV; preserve ordered scope.
        key = (seed, hashlib.sha256(np.asarray(rows, dtype='<i8').tobytes()).hexdigest())
        if key not in self.expected_split_cache:
            frame = self.train.iloc[rows].reset_index(drop=True)
            self.expected_split_cache[key] = expected_inner_split(self.spec, frame, self.hashes[rows], seed)
        return self.expected_split_cache[key]

    def split(self, path, seed=None):
        key = str(path)
        if key not in self.split_cache:
            with np.load(self.arm.path(path), allow_pickle=False) as saved:
                self.split_cache[key] = saved['train'].copy(), saved['validation'].copy()
        train, validation = self.split_cache[key]
        validate_partition(train, validation, len(self.train))
        require(not np.intersect1d(self.hashes[train], self.hashes[validation]).size, 'inner_feature_group_overlap')
        if seed is not None:
            expected_train, expected_validation, _ = self.expected(np.arange(len(self.train)), seed)
            require(np.array_equal(train, expected_train) and np.array_equal(validation, expected_validation),
                    'inner_split_differs_frozen_rule')
        return train, validation

    def verify(self, record, partition, phase, full=False, expected_recipe=None):
        check_clock(self.arm.plan, self.arm.deadline)
        recipe = record['recipe']
        require(expected_recipe is None or recipe == expected_recipe, 'child_recipe_wrong')
        folder = Path(record.get('output_dir') or Path(record['submission']).parent)
        folder = (self.arm.root / folder).resolve() if not folder.is_absolute() else folder.resolve()
        require(folder.is_relative_to(self.arm.root), 'record_folder_outside_arm')
        stored = self.arm.json(folder / 'result.json')
        require(record.get('status') == stored.get('status') == 'ok', 'successful_record_expected')
        require(stored['recipe'] == recipe and stored['full_fit'] is full, 'stored_record_wrong')
        key = (str(folder), phase, full)
        if key in self.visited:
            return self.visited[key]
        tr, va = self.split(partition, 42 if phase == 'primary' else 43)
        job_path = folder / 'job.json'
        job = None
        if job_path.relative_to(self.arm.root).as_posix() in self.arm.files:
            job = self.arm.json(job_path)
            require(job['recipe'] == recipe and job['spec'] == self.spec and job['threads'] == 2 and
                    job['full_fit'] is full and Path(job['split_path']).resolve() == Path(partition).resolve(), 'job_contract_wrong')
        elif not stored.get('training_reused'):
            require(expected_recipe is not None, 'top_level_job_missing')
        test = probability(self.arm, folder / 'test_probabilities.npz', self.classes, expected_rows=len(self.test))
        csv = pd.read_csv(self.arm.path(folder / 'submission.csv'))
        require(list(csv) == list(self.sample) and len(csv) == len(self.sample) and not csv.isna().any().any(), 'csv_schema_wrong')
        require(csv[self.spec['id']].astype(str).tolist() == self.sample[self.spec['id']].astype(str).tolist(), 'csv_ids_wrong')
        require(np.array_equal(csv[self.spec['target']].astype(str), np.asarray(self.classes)[test.argmax(axis=1)]), 'csv_probability_argmax_wrong')
        val = None
        if not full:
            val = probability(self.arm, folder / 'validation_probabilities.npz', self.classes, va, len(va))
            frame = pd.read_csv(self.arm.path(folder / 'validation_predictions.csv'))
            require(frame['row_position'].dtype.kind in 'iu' and np.array_equal(frame['row_position'], va), 'validation_rows_wrong')
            truth = self.train[self.spec['target']].iloc[va].astype(str).to_numpy()
            predicted = np.asarray(self.classes)[val.argmax(axis=1)]
            require(np.array_equal(frame['y_true'].astype(str), truth) and np.array_equal(frame['y_pred'].astype(str), predicted),
                    'validation_truth_prediction_wrong')
            value, _ = score(truth, predicted, self.classes)
            require(same_number(value, stored['metrics']['macro_f1']) and same_number(value, record['metrics']['macro_f1']),
                    'internal_metric_wrong')
        child_recipes, children, weights = [], [], None
        if recipe['engine'] == 'ensemble':
            child_recipes = recipe['components']
            require(2 <= len(child_recipes) <= 3 and all(child.get('engine') != 'ensemble' for child in child_recipes),
                    'global_ensemble_shape_wrong')
            weights = np.asarray(recipe['weights'], dtype=float)
            require(len(weights) == len(child_recipes) and np.isfinite(weights).all() and (weights > 0).all(), 'ensemble_weights_wrong')
            weights /= weights.sum()
        elif recipe.get('params', {}).get('feature_views'):
            child_recipes = view_children(recipe, self.spec)
            weights = np.full(len(child_recipes), 1. / len(child_recipes))
            views = stored.get('feature_views') or {}
            require(views.get('method') == recipe['params']['feature_views'] and views.get('weights') == weights.tolist() and
                    views.get('groups') == child_recipes[1]['params']['target_encoding_groups'] and
                    views.get('iteration_tree') == stored['fit_iterations'], 'feature_view_metadata_wrong')
        for index, child_recipe in enumerate(child_recipes):
            if stored.get('training_reused'):
                field = 'experiments' if phase == 'primary' else 'confirmations'
                matches = [r for r in self.report[field] if r.get('status') == 'ok' and r['recipe'] == child_recipe]
                require(len(matches) == 1, 'cached_child_ambiguous')
                child = matches[0]
            else:
                child_folder = folder / f'component-{index}'
                child = dict(self.arm.json(child_folder / 'result.json'), output_dir=str(child_folder))
            children.append(self.verify(child, partition, phase, full, child_recipe))
        if children:
            for name, actual in [('test', test)] + ([] if full else [('validation', val)]):
                expected = sum(weight * child[name] for weight, child in zip(weights, children))
                require(np.allclose(actual, expected, rtol=1e-10, atol=1e-10), 'recursive_probability_mixture_wrong')
            require(stored['fit_iterations'] == [child['fit_iterations'] for child in children], 'child_iteration_tree_wrong')
            if recipe.get('params', {}).get('feature_views') == FIXED:
                self.fixed_nodes[str(folder)] = {'phase': phase, 'full_fit': full,
                    'fit_iterations': stored['fit_iterations'], 'leaf_count': 4,
                    'num_leaves': [63, 63, 98, 98], 'weights': [.25] * 4}
        else:
            selected = stored['fit_iterations']
            require(type(selected) is int and 1 <= selected <= 3000, 'fitted_iteration_leaf_invalid')
            require(isinstance(stored.get('data_policy_runs'), list) and stored['data_policy_runs'], 'successful_fit_scope_receipts_missing')
            fitting_rows = np.arange(len(self.train)) if full else tr
            if stored.get('inner_split') is not None:
                inner_tr, _, expected = self.expected(fitting_rows, 73)
                require(stored['inner_split'] == expected, 'leaf_inner_split_receipt_wrong')
                require(expected['shared_feature_hashes'] == 0, 'leaf_inner_group_overlap')
                allowed_scopes = {canonical(fitting_rows.tolist()): len(fitting_rows),
                                  canonical(fitting_rows[inner_tr].tolist()): len(inner_tr)}
            else:
                ordinary_forest = recipe['engine'] == 'extra_trees' and not recipe.get('params', {}).get('calibrate')
                split_fallback = stored.get('early_stopping_source') == 'fixed_iterations_split_fallback' and bool(stored.get('inner_split_error'))
                require(ordinary_forest or split_fallback, 'leaf_inner_scope_unproven')
                allowed_scopes = {canonical(fitting_rows.tolist()): len(fitting_rows)}
            require(not stored.get('calibration_folds'), 'unexpected_multi_fold_calibration_outside_default_scope')
            for policy in stored['data_policy_runs']:
                require(policy.get('source_parent_sha256') in allowed_scopes and
                        type(policy.get('source_rows')) is int and
                        policy['source_rows'] == allowed_scopes[policy['source_parent_sha256']],
                        'leaf_fitting_parent_scope_wrong')
            require(stored['data_policy_runs'][-1]['source_parent_sha256'] == canonical(fitting_rows.tolist()) and
                    stored['data_policy_runs'][-1]['source_rows'] == len(fitting_rows), 'final_leaf_fitting_scope_wrong')
            self.leaves[str(folder)] = {'full_fit': full, 'fit_iterations': selected,
                'successful_fitting_scope_calls': len(stored['data_policy_runs']),
                'inner_split': stored.get('inner_split'), 'early_stopping_source': stored.get('early_stopping_source')}
        if full and job is not None:
            require(job.get('fit_iterations') == stored['fit_iterations'], 'fresh_refit_iterations_wrong')
        answer = {'test': test, 'validation': val, 'fit_iterations': stored['fit_iterations'], 'record': stored,
                  'inner_tree': [child['inner_tree'] for child in children] if children else
                    {'inner_split': stored.get('inner_split'), 'early_stopping_source': stored.get('early_stopping_source')}}
        self.visited[key] = answer
        return answer


def experiment_map(report):
    records = report['experiments']
    indices = [record['experiment_index'] for record in records]
    require(len(indices) == len(set(indices)) and indices == sorted(indices) and all(0 <= i < 12 for i in indices), 'experiment_order_wrong')
    return {record['experiment_index']: record for record in records}


def selected_records(report):
    selected = report['selected_recipe']
    if report.get('ensemble'):
        pair = {phase: report['ensemble'][phase] for phase in ['primary', 'confirmation']}
    else:
        pair = {}
        for phase, field in [('primary', 'experiments'), ('confirmation', 'confirmations')]:
            matches = [record for record in report[field] if record.get('status') == 'ok' and record['recipe'] == selected]
            require(len(matches) == 1 if phase == 'primary' else len(matches) <= 1, 'selected_recipe_ambiguous')
            pair[phase] = matches[0] if matches else None
        if pair['confirmation'] is None:
            require(report.get('selection') == [], 'selected_confirmation_missing_despite_selection')
    require(all(record is None or record['recipe'] == selected for record in pair.values()), 'selected_recipe_mismatch')
    return pair


def _audit_pair(work, plan, slots, fold_manifest, deadline_monotonic):
    work, archives, stage = context(work, plan, fold_manifest, deadline_monotonic)
    require(len(slots) == 2 and {slot['arm'] for slot in slots} == {'a', 'b'} and len({slot['fold'] for slot in slots}) == 1,
            'pair_slots_wrong')
    fold = slots[0]['fold']
    require(type(fold) is int and fold == 0, 'posthoc_fold0_only')
    # Reject either nonterminal/unsealed slot before opening either arm artifact.
    for slot in slots:
        require(posthoc_slot_terminal(slot, stage) and type(slot.get('exit_code')) is int and
                slot['exit_code'] == 0 and slot.get('cleanup_confirmed') is True, 'pair_not_terminal_sealed_clean')
        supervisor_receipt(work, slot, stage)
        seal = slot.get('seal')
        require(isinstance(seal, dict) and canonical(seal) == slot.get('seal_sha256') and
                seal.get('files_sha256') == slot.get('sealed') and bool(slot['sealed']), 'pair_seal_unbound')
    # Both headers are validated before any pristine outer label or prediction is read.
    arms = {slot['arm']: SealedArm(work, slot, archives, plan, deadline_monotonic, stage) for slot in slots}
    arrays = frozen_inputs(work, plan, fold_manifest, deadline_monotonic)
    shared_expected_splits = {}
    audits = {name: ArtifactAudit(arm, fold_manifest['folds'][fold], fold_manifest, shared_expected_splits)
              for name, arm in arms.items()}
    primary, confirmation = {}, {}
    for name, audit in audits.items():
        primary[name] = audit.arm.report_path.parent / 'split.npz'
        path = audit.arm.report_path.parent / 'confirmation_split.npz'
        confirmation[name] = path if path.relative_to(audit.arm.root).as_posix() in audit.arm.files else None
    left, right = audits['a'].split(primary['a'], 42), audits['b'].split(primary['b'], 42)
    require(all(np.array_equal(x, y) for x, y in zip(left, right)), 'A_B_inner_split_mismatch')
    # Confirmation happens after the intervention and may legitimately be unreached.
    for name, path in confirmation.items():
        if path is not None:
            audits[name].split(path, 43)
    maps = {name: experiment_map(audit.report) for name, audit in audits.items()}
    prefix = []
    for index in range(11):
        require(all(index in records for records in maps.values()), 'first11_not_reached')
        a, b = maps['a'][index], maps['b'][index]
        require(a['recipe'] == b['recipe'] and a['status'] == b['status'], 'first11_recipe_or_status_mismatch')
        require(a.get('metrics') == b.get('metrics'), 'first11_metric_or_failure_null_mismatch')
        if a['status'] == 'ok':
            values = {name: audits[name].verify(maps[name][index], primary[name], 'primary') for name in ['a', 'b']}
            require(values['a']['fit_iterations'] == values['b']['fit_iterations'] and
                    values['a']['inner_tree'] == values['b']['inner_tree'], 'first11_inner_fit_tree_mismatch')
            require(all(np.array_equal(values['a'][key], values['b'][key]) for key in ['test', 'validation']),
                    'first11_prediction_probability_mismatch')
        else:
            require(a.get('metrics') is None and b.get('metrics') is None, 'failed_student_metrics_not_null')
        prefix.append({'experiment_index': index, 'status': a['status'], 'parity': True,
                       'failure_null_no_prediction_claim': a['status'] != 'ok'})
    # Audit successful unselected work too; failures retain status/unknown fit cost.
    for name, audit in audits.items():
        for field, partition, phase in [('experiments', primary[name], 'primary'),
                                         ('confirmations', confirmation[name], 'confirmation')]:
            for record in audit.report[field]:
                if record['status'] == 'ok':
                    require(partition is not None, 'successful_confirmation_has_no_partition')
                    audit.verify(record, partition, phase)
                else:
                    require(record.get('metrics') is None, 'failed_student_metrics_not_null')
    result, vectors = {}, {}
    source = pd.read_csv(work / 'evaluation/multiclass/train.csv')
    direct_hashes = pd.util.hash_pandas_object(source[fold_manifest['raw_feature_schema_order']], index=False).to_numpy(dtype='uint64')
    require(np.array_equal(direct_hashes, arrays['raw_feature_hashes']), 'pristine_raw_feature_hashes_wrong')
    validation = arrays[f'fold{fold}_validation']
    fitting = arrays[f'fold{fold}_train']
    classes = fold_manifest['canonical_class_order']
    target, identifier = fold_manifest['target_column'], fold_manifest['id_column']
    truth = source[target].iloc[validation].astype(str).to_numpy()
    raw_hashes = arrays['raw_feature_hashes']
    fitting_y = source[target].iloc[fitting].astype(str).to_numpy()
    support = {label: int(np.unique(raw_hashes[fitting][fitting_y == label]).size) for label in classes}
    rarest = min(classes, key=lambda label: (support[label], label))
    require(rarest == fold_manifest['folds'][fold]['excluded_rarest_class_frozen_before_scoring'], 'rarest_definition_changed')
    for name, audit in audits.items():
        require(audit.train[target].astype(str).tolist() == source[target].iloc[fitting].astype(str).tolist(), 'outer_fitting_labels_wrong')
        require(audit.test[identifier].astype(str).tolist() == source[identifier].iloc[validation].astype(str).tolist(), 'outer_test_id_mapping_wrong')
        require(np.array_equal(audit.hashes, direct_hashes[fitting]), 'outer_fitting_raw_features_wrong')
        test_hashes = pd.util.hash_pandas_object(audit.test[audit.spec['features']], index=False).to_numpy(dtype='uint64')
        require(np.array_equal(test_hashes, direct_hashes[validation]), 'outer_test_raw_features_wrong')
        chosen = selected_records(audit.report)
        selected = {'primary': audit.verify(chosen['primary'], primary[name], 'primary'), 'confirmation': None}
        if chosen['confirmation'] is not None:
            require(confirmation[name] is not None, 'selected_confirmation_has_no_partition')
            selected['confirmation'] = audit.verify(chosen['confirmation'], confirmation[name], 'confirmation')
            expected_iterations = median_tree(selected['primary']['fit_iterations'], selected['confirmation']['fit_iterations'])
        else:
            expected_iterations = selected['primary']['fit_iterations']
        require(audit.report['final_fit_iterations'] == expected_iterations, 'selection_median_iterations_wrong')
        folder = audit.arm.report_path.parent / 'final-fit'
        final_record = dict(audit.arm.json(folder / 'result.json'), output_dir=str(folder))
        final = audit.verify(final_record, primary[name], 'primary', full=True, expected_recipe=audit.report['selected_recipe'])
        require(final['fit_iterations'] == expected_iterations, 'final_iteration_tree_wrong')
        require(audit.arm.sha('submission.csv') == audit.report['submission_sha256'] and
                audit.arm.sha('submission.csv') == audit.arm.sha(folder / 'submission.csv'), 'final_export_not_refit_csv')
        predicted = np.asarray(classes)[final['test'].argmax(axis=1)]
        value, per_class = score(truth, predicted, classes)
        successful_leaves = list(audit.leaves.values())
        result[name] = {'macro_f1': value, 'per_class_f1': per_class,
            'ex_rarest_macro_f1': float(np.mean([per_class[c] for c in classes if c != rarest])),
            'selected_recipe': audit.report['selected_recipe'], 'final_fit_iterations': expected_iterations,
            'selected_internal_confirmation_status': ('ok' if selected['confirmation'] is not None else
                'failed_no_successful_selection' if any(record['recipe'] == audit.report['selected_recipe']
                    for record in audit.report['confirmations']) else 'not_attempted'),
            'selected_internal_confirmation_metrics': chosen['confirmation'].get('metrics') if chosen['confirmation'] is not None else None,
            'fixed_component_reached': any(has_fixed(record['recipe']) for record in maps[name].values()),
            'fixed_component_selected': has_fixed(audit.report['selected_recipe']),
            'student_status_counts': {status: sum(r['status'] == status for r in maps[name].values())
                                      for status in sorted({r['status'] for r in maps[name].values()})},
            'confirmation_status_counts': {status: sum(r['status'] == status for r in audit.report['confirmations'])
                                           for status in sorted({r['status'] for r in audit.report['confirmations']})},
            'successful_unique_leaf_records_verified': len(successful_leaves),
            'successful_fitting_scope_calls_verified': sum(row['successful_fitting_scope_calls'] for row in successful_leaves),
            'failed_student_fitting_calls': None,
            'fresh_refit_leaf_iterations': [row['fit_iterations'] for row in successful_leaves if row['full_fit']],
            'fixed_four_leaf_nodes_verified': list(audit.fixed_nodes.values()),
            'final_csv_sha256': audit.arm.sha('submission.csv'),
            'outer_prediction_vector_sha256': canonical(predicted.tolist()),
            'api_zero_source_CLI_report_evidence': True,
            'private_closed_ledger_independent_read': None, 'provider_usage_independent_proof': None}
        vectors[name] = predicted
    delta = {label: result['b']['per_class_f1'][label] - result['a']['per_class_f1'][label] for label in classes}
    gates = {'macro_f1_strict_positive': result['b']['macro_f1'] > result['a']['macro_f1'],
             'ex_rarest_strict_positive': result['b']['ex_rarest_macro_f1'] > result['a']['ex_rarest_macro_f1'],
             'supported_loss_not_below_minus_0_01': all(delta[label] >= -.01 for label in classes if support[label] >= 100)}
    public = {'fold': fold, 'status': 'posthoc_pair0_diagnostic_audited', 'arms': result, 'prefix11': prefix,
        'scope': POSTHOC_SCOPE, 'original_technical_failure_preserved': True,
        'complete_CV': False, 'OOF_complete': False, 'final_CV': None,
        'qualification': 'not_qualified_incomplete_CV', 'promotion': False,
        'stage2_quality_prerequisite_passed': False,
        'posthoc_declaration': plan['posthoc_declaration'],
        'posthoc_verifier_sha256': digest(Path(__file__)),
        'independent_fitting_groups': support, 'excluded_rarest_class': rarest, 'per_class_deltas': delta,
        'gates': gates, 'mandatory_fold_gates_passed': all(gates.values()),
        'violated_gates': [name for name, passed in gates.items() if not passed],
        'component_nonselection_alone_is_not_early_rejection': True,
        'bindings': {'protocol_sha256': PROTOCOL_SHA, 'fold_manifest_sha256': FOLD_MANIFEST_SHA,
                     'archives_sha256': ARCHIVE_SHA, 'seal_sha256': {s['arm']: s['seal_sha256'] for s in slots},
                     'supervisor_manifest_sha256': plan['manifest_sha256'],
                      'supervisor_receipt_sha256': {s['arm']: s['supervisor_receipt_sha256'] for s in slots},
                     'common_absolute_deadline_unix': plan['common_absolute_deadline_unix']},
        'score_scope': 'Adaptive reused-public whole-procedure outer fold; not private/official evaluation'}
    for arm in arms.values():
        arm.recheck()
    for relative, expected in fold_manifest['pristine_input_sha256'].items():
        require(digest(within(work, relative)) == expected, 'pristine_input_changed_after_audit')
    posthoc_context(work, plan, load(within(work, plan['stage_receipt_path'])), deadline_monotonic)
    return public, validation, truth, vectors


def audit_pair(work, plan, slots, fold_manifest, deadline_monotonic=None):
    """Quality audit refuses to run unless BOTH current-fold arms are sealed/clean."""
    try:
        return _audit_pair(work, plan, slots, fold_manifest, deadline_monotonic)[0]
    except AuditError:
        raise
    except Exception as exc:
        raise AuditError('artifact_decode_or_schema_error:' + type(exc).__name__) from None


def _audit_complete_oof(work, plan, slots, fold_manifest, deadline_monotonic=None):
    require(len(slots) == 6 and [(s['fold'], s['arm']) for s in slots] == ORDER, 'six_declared_slots_required')
    resolved_work, _, stage = context(work, plan, fold_manifest, deadline_monotonic)
    for slot in slots:
        stage_slot(slot, stage)
    require(not any(slot['status'] in ('running', 'started', 'auditing', 'cleanup_pending') for slot in slots),
            'matrix_has_nonterminal_arm')
    summary = [{'fold': slot['fold'], 'arm': slot['arm'], 'status': slot['status'], 'metrics': None,
                'outer_predictions_sha256': None, 'final_refit_status': None, 'final_csv_sha256': None,
                'prior_gate_audit': slot.get('prior_gate_audit')} for slot in slots]
    answer = {'status': 'incomplete_CV', 'complete_CV': False, 'all_gates_passed': False,
        'declared_arms': summary, 'fold_audits': [], 'fold_mean': None,
        'pooled_macro_f1': None, 'OOF_complete': False, 'qualification': 'FAIL',
        'stage2_allowed': False, 'stage2_quality_prerequisite_passed': False,
        'promotion': False, 'launch_authorized': False}
    for slot in slots:
        if slot['status'] != 'sealed_complete':
            require(slot.get('metrics') is None, 'incomplete_arm_metrics_must_be_null')
        if slot['status'] == 'not_attempted_due_prior_gate_failure':
            require(all(slot.get(key) is None for key in ['outer_predictions_sha256', 'final_refit_status', 'final_csv_sha256']),
                    'unattempted_artifacts_must_be_null')
            reference = slot.get('prior_gate_audit')
            require(isinstance(reference, dict) and isinstance(reference.get('path'), str) and
                    isinstance(reference.get('sha256'), str), 'decisive_failure_audit_missing')
            prior = load(bound_ref(Path(work).resolve(), reference, reference['sha256']))
            require(prior.get('mandatory_fold_gates_passed') is False or prior.get('status') == 'technical_failure',
                    'prior_audit_does_not_reject')
            bindings = prior.get('bindings') or {}
            require(bindings.get('protocol_sha256') == PROTOCOL_SHA and bindings.get('fold_manifest_sha256') == FOLD_MANIFEST_SHA and
                    bindings.get('archives_sha256') == ARCHIVE_SHA and
                    bindings.get('supervisor_manifest_sha256') == plan['manifest_sha256'] and
                    bindings.get('common_absolute_deadline_unix') == plan['common_absolute_deadline_unix'],
                    'prior_audit_belongs_to_different_stage')
            require(type(prior.get('fold')) is int and prior['fold'] <= slot['fold'], 'prior_audit_fold_order_wrong')
            for record in summary:
                if record['fold'] == slot['fold'] and record['arm'] == slot['arm']:
                    record['prior_gate_audit'] = {'path': within(Path(work).resolve(), reference['path']).relative_to(Path(work).resolve()).as_posix(),
                                                'sha256': reference['sha256']}
    all_valid = all(slot['status'] == 'sealed_complete' for slot in slots)
    counts = np.zeros(fold_manifest['row_count'], dtype=int)
    predictions = {arm: np.empty(fold_manifest['row_count'], dtype=object) for arm in ['a', 'b']}
    truth = np.empty(fold_manifest['row_count'], dtype=object)
    for fold in range(3):
        pair = [slot for slot in slots if slot['fold'] == fold]
        if not all(slot['status'] == 'sealed_complete' for slot in pair):
            continue
        audited, rows, observed, values = _audit_pair(work, plan, pair, fold_manifest, deadline_monotonic)
        answer['fold_audits'].append(audited)
        for record in summary:
            if record['fold'] == fold:
                record['metrics'] = audited['arms'][record['arm']]
                record['outer_predictions_sha256'] = record['metrics']['outer_prediction_vector_sha256']
                record['final_refit_status'] = 'ok'
                record['final_csv_sha256'] = record['metrics']['final_csv_sha256']
        counts[rows] += 1
        truth[rows] = observed
        for arm in ['a', 'b']:
            predictions[arm][rows] = values[arm]
    if not all_valid:
        for slot in slots:
            if slot['status'] not in ('sealed_complete', 'not_attempted', 'not_attempted_due_prior_gate_failure'):
                require(slot.get('cleanup_confirmed') is True, 'failed_arm_cleanup_unproven')
                supervisor_receipt(resolved_work, slot, stage)
        if any(slot['status'] not in ('sealed_complete', 'not_attempted') for slot in slots):
            answer['status'] = 'rejected_early_incomplete_CV'
        return answer
    require(len(answer['fold_audits']) == 3 and np.all(counts == 1), 'complete_OOF_coverage_invalid')
    classes = fold_manifest['canonical_class_order']
    means = {arm: float(np.mean([f['arms'][arm]['macro_f1'] for f in answer['fold_audits']])) for arm in ['a', 'b']}
    pooled = {arm: score(truth, predictions[arm], classes)[0] for arm in ['a', 'b']}
    selected_somewhere = any(f['arms']['b']['fixed_component_selected'] for f in answer['fold_audits'])
    gates = {'all_fold_gates': all(f['mandatory_fold_gates_passed'] for f in answer['fold_audits']),
             'fold_mean_strict_positive': means['b'] > means['a'],
             'pooled_strict_positive': pooled['b'] > pooled['a'],
             'fixed_component_selected_somewhere': selected_somewhere}
    answer.update(status='complete_CV_audited', complete_CV=True, OOF_complete=True,
        fold_mean=means, pooled_macro_f1=pooled, final_gates=gates,
        all_gates_passed=all(gates.values()), qualification='PASS' if all(gates.values()) else 'FAIL',
        stage2_quality_prerequisite_passed=all(gates.values()))
    return answer


def audit_complete_oof(work, plan, slots, fold_manifest, deadline_monotonic=None):
    """Full CV is forbidden in this separate first-pair diagnostic."""
    raise AuditError('posthoc_full_CV_or_qualification_forbidden')
    try:
        return _audit_complete_oof(work, plan, slots, fold_manifest, deadline_monotonic)
    except AuditError:
        raise
    except Exception as exc:
        raise AuditError('artifact_decode_or_schema_error:' + type(exc).__name__) from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--slots', type=Path, required=True)
    parser.add_argument('--fold-manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pair', type=int, choices=[0], required=True)
    parser.add_argument('--audit-deadline-monotonic', type=float, required=True)
    args = parser.parse_args()
    plan, slots, folds = load(args.plan), load(args.slots), load(args.fold_manifest)
    selected = [s for s in slots if s['fold'] == args.pair] if args.pair is not None else slots
    value = audit_pair(args.work, plan, selected, folds, args.audit_deadline_monotonic) if args.pair is not None else audit_complete_oof(args.work, plan, slots, folds)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    posthoc_context(args.work.resolve(), plan,
                    load(within(args.work.resolve(), plan['stage_receipt_path'])),
                    args.audit_deadline_monotonic)


if __name__ == '__main__':
    main()
