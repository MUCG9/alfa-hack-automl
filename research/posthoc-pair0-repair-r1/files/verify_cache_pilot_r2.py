"""Independent sealed six-callback parity/LRU/timing audit; no model imports.

Reads pristine target/ID columns only after both arms of that fixed pair are
terminal, clean, source guarded and byte sealed. No fitting, API, tuning,
promotion or full-agent qualification exists in this verifier.
"""
from pathlib import Path
from collections import OrderedDict
import argparse
import hashlib
import json
import math
import os
import struct
import sys
import time

sys.dont_write_bytecode = True


class AuditError(RuntimeError):
    pass


def require(condition, code):
    if not condition:
        raise AuditError(code)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        allow_nan=False).encode('utf-8')).hexdigest()


def probe_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        allow_nan=False).encode('utf-8')).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def typed_digest(value, array=False):
    """Independent implementation of the published exact metadata/array stream."""
    import numpy as np
    h = hashlib.sha256()
    def feed(v):
        if isinstance(v, np.generic):
            v = v.item()
        if isinstance(v, dict):
            h.update(b'd' + struct.pack('!Q', len(v)))
            for key, item in v.items():
                feed(key)
                feed(item)
            return
        if isinstance(v, (list, tuple)):
            h.update((b'l' if isinstance(v, list) else b't') + struct.pack('!Q', len(v)))
            for item in v:
                feed(item)
            return
        if v is None:
            b = b'n'
        elif type(v) is bool:
            b = b'b1' if v else b'b0'
        elif type(v) is int:
            b = b'i' + str(v).encode('ascii')
        elif type(v) is float:
            b = b'f' + struct.pack('!d', v)
        elif type(v) is str:
            b = b's' + v.encode('utf-8')
        elif type(v) is bytes:
            b = b'y' + v
        else:
            raise AuditError('unsupported_diagnostic_metadata')
        h.update(struct.pack('!Q', len(b)))
        h.update(b)
    if array:
        a = np.asarray(value)
        feed(('array', a.dtype.str, tuple(a.shape)))
        require(not a.dtype.hasobject and a.dtype.kind in 'biufcSU', 'unexpected_importance_or_rank_array_type')
        h.update(memoryview(np.ascontiguousarray(a)).cast('B'))
    else:
        feed(value)
    return h.hexdigest()


def within(root, value):
    result = Path(value).resolve()
    require(result.is_relative_to(root.resolve()), 'artifact_reference_escape')
    return result


def files(root):
    found = {}
    for parent, dirs, names in os.walk(root):
        require(not any((Path(parent) / n).is_symlink() for n in [*dirs, *names]), 'artifact_symlink')
        for name in names:
            p = Path(parent) / name
            found[p.relative_to(root).as_posix()] = digest(p)
    return found


def sealed(work, slot):
    require(slot.get('status') == 'sealed_complete', 'slot_not_complete')
    root = within(work, work / 'k1' / slot['id'])
    ref = slot['seal']
    path = within(work, work / ref['path'])
    require(digest(path) == ref['sha256'], 'seal_receipt_changed')
    seal = load(path)
    require(seal.get('root') == root.relative_to(work).as_posix() and
            seal.get('source_unchanged') is True and seal.get('cleanup_confirmed') is True
            and seal['files_sha256'] == files(root), 'sealed_artifact_changed')
    supervisor = within(work, work / slot['supervisor']['path'])
    require(digest(supervisor) == slot['supervisor']['sha256'], 'supervisor_changed')
    sup = load(supervisor)
    require(seal.get('supervisor_sha256') == slot['supervisor']['sha256']
            and seal.get('job_sha256') == slot.get('job_sha256') == digest(root / 'job.json'),
            'seal_job_supervisor_binding_mismatch')
    require(sup == slot['supervisor']['object'] and sup.get('status') == 'ok'
            and sup.get('exit_code') == 0 and sup.get('cleanup_confirmed') is True
            and sup.get('maximum_logical_jobs') == 1
            and sup.get('seconds') <= slot['parent_cap'], 'supervisor_not_qualified')
    timing = slot.get('timing', {})
    require(type(timing.get('parent_seconds')) in (int, float) and math.isfinite(timing['parent_seconds'])
            and 0 < timing['parent_seconds'] <= slot['parent_cap'], 'parent_timing_invalid')
    require(timing.get('timer_start_monotonic') == sup['parent_start_monotonic']
            and abs(timing['timer_end_monotonic'] - timing['timer_start_monotonic'] - timing['parent_seconds']) <= 1e-6
            and sup['seconds'] <= timing['parent_seconds']
            and sup['child_cap_seconds'] == slot['worker_cap']
            and sup.get('child_seconds', float('inf')) <= slot['worker_cap']
            and sup['parent_cap_seconds'] == slot['parent_cap'], 'parent_or_child_timer_binding_invalid')
    return root, seal


def leaves(root, record):
    children = record.get('components')
    if children is None:
        return [(root, record)]
    require(isinstance(children, list) and len(children) == 2 and
            record.get('feature_views', {}).get('method') == 'categorical_te_pair'
            and record['feature_views']['weights'] == [.5, .5], 'two_view_record_changed')
    result = []
    for i, child in enumerate(children):
        directory = root / ('component-' + str(i))
        require(child == load(directory / 'result.json') and 'components' not in child,
                'leaf_embedded_record_mismatch')
        result.append((directory, child))
    return result


def clean_semantics(value, root, key=None):
    """Exclude only operational timings/cache/probe telemetry, retain new fields.

    The allowed numeric tolerance for class factors is checked separately. A
    previously unknown semantic field remains in comparison and fails on drift.
    """
    ignored = {'wall_seconds', 'peak_rss_mb', 'teacher_diagnostics', 'selector_importance_cache',
               'importance_cache', 'teacher_fitted', 'selector_seconds', 'class_factors'}
    if isinstance(value, dict):
        return {k: clean_semantics(v, root, k) for k, v in value.items() if k not in ignored}
    if isinstance(value, list):
        return [clean_semantics(v, root, key) for v in value]
    if isinstance(value, str) and key in {'submission', 'validation_predictions', 'parent_rows_artifact', 'path'}:
        return within(root, value).relative_to(root).as_posix()
    return value


def close_arrays(a, b, atol, rtol=0):
    import numpy as np
    a, b = np.asarray(a), np.asarray(b)
    require(a.shape == b.shape and np.isfinite(a).all() and np.isfinite(b).all()
            and np.allclose(a, b, atol=atol, rtol=rtol), 'numeric_parity_failed')
    return float(np.max(np.abs(a - b))) if a.size else 0.


def replay(sidecar, enabled):
    """Replay cache4/262144 from bounded recorded exact keys and payload metadata.

    Input typed-stream computation is independently performed in each arm by
    the pinned common probe; equality is checked request-for-request separately.
    This function imports neither the implementation nor its key/cache helpers.
    """
    import numpy as np
    records = sidecar['requests']
    require(sidecar.get('maximum_requests') == 64 and len(records) <= 64
            and sidecar.get('context_sha256') == probe_json(sidecar['context']), 'sidecar_context_invalid')
    leaf = sidecar['leaf_identity']
    resident, origins = OrderedDict(), {}
    hits = misses = bypasses = evictions = 0
    cache_identity = None
    for i, r in enumerate(records):
        require(r['request'] == i and r['leaf_identity'] == leaf and r['scope'] in {'inner', 'outer'}
                and r['context_sha256'] == sidecar['context_sha256'], 'request_scope_invalid')
        require(r.get('effective_teacher_params_status') == 'available'
                and isinstance(r.get('effective_teacher_params_sha256'), str), 'teacher_params_uncertified')
        importance = np.asarray(r['importance'], dtype=float)
        require(importance.shape == (r['input_columns'],) and r['importance_length'] == len(importance)
                and r['importance_finite'] is True and np.isfinite(importance).all()
                and len(importance) <= 4096 and r['column_metadata_status'] == 'serializable',
                'importance_schema_invalid')
        require(len(r['columns']) == len(importance) and len(r['selected_columns']) == 32
                and len(set(r['columns'])) == len(r['columns']), 'selection_schema_invalid')
        ranked = np.argsort(-importance, kind='stable')[:32]
        expected_columns = [n for j, n in enumerate(r['columns']) if j in set(ranked.tolist())]
        require(expected_columns == r['selected_columns'], 'independent_ranking_failed')
        require(typed_digest(importance, True) == r['importance_sha256']
                and typed_digest(ranked, True) == r['ranked_indices_sha256']
                and typed_digest(r['columns']) == r['columns_sha256']
                and typed_digest(r['selected_columns']) == r['selected_columns_sha256'],
                'independent_importance_rank_metadata_digest_mismatch')
        require(set(r['timings_seconds']) >= {'teacher_constructor', 'teacher_pure_fit',
                'teacher_importance_extraction', 'teacher_constructor_fit_importance_inclusive',
                'teacher_parameter_probe', 'cache_key_lookup', 'cache_store',
                'cache_store_invoked', 'common_probe_finish', 'whole_selector_through_probe'}, 'timers_missing')
        for name, value in r['timings_seconds'].items():
            require(value is None or type(value) is bool or type(value) in (int, float)
                    and math.isfinite(value) and value >= 0, 'timer_invalid')
        require(type(r['common_probe_digest_seconds']) in (int, float)
                and math.isfinite(r['common_probe_digest_seconds']) and r['common_probe_digest_seconds'] >= 0,
                'common_probe_time_invalid')
        key, eligible = r['key_sha256'], r['store_eligibility']
        require(eligible['maximum_bytes'] == 262144 and
                eligible['candidate_payload_conservative_bytes'] == r['candidate_payload_conservative_bytes'],
                'store_accounting_invalid')
        if r['status'] == 'cacheable':
            require(isinstance(key, str) and len(key) == 64 and set(r['components']) ==
                {'rows', 'X_index', 'X_schema', 'X_values', 'y', 'weights', 'teacher_settings',
                 'context', 'source', 'libraries'}, 'cacheable_key_invalid')
            require(r['components']['source'] == probe_json(sidecar['source_modules_sha256']) and
                    r['components']['libraries'] == probe_json(sidecar['libraries']), 'component_binding_invalid')
        else:
            require(r['status'] == 'uncacheable' and key is None and r['components'] == {}, 'bypass_contract_invalid')
        size = r['candidate_payload_conservative_bytes']
        computed_size = None
        if key is not None:
            columns = tuple(r['columns'])
            encoded = json.dumps(columns, ensure_ascii=False, allow_nan=False).encode('utf-8')
            computed_size = (importance.nbytes + sys.getsizeof(importance) + sys.getsizeof(columns)
                + sum(sys.getsizeof(n) for n in columns) + sys.getsizeof(key) + len(encoded) + 256)
            require(size == computed_size, 'independent_payload_bytes_mismatch')
        should_store = key is not None and computed_size <= 262144
        require(eligible['eligible_if_enabled'] is should_store, 'store_eligibility_mismatch')
        if not enabled:
            require(r['cache_status'] == 'disabled' and r['teacher_invoked'] is True
                    and r['cache_trace'] is None and r['source_miss_request'] is None
                    and r['timings_seconds']['cache_key_lookup'] is None
                    and r['timings_seconds']['cache_store_invoked'] is False
                    and r['timings_seconds']['cache_store'] == 0, 'OFF_cache_work_detected')
            require(probe_json(r['effective_teacher_params']) == r['effective_teacher_params_sha256'],
                    'effective_params_digest_mismatch')
            continue
        expected = 'bypass' if key is None else 'hit' if key in resident else 'miss'
        require(r['cache_status'] == expected and r['teacher_invoked'] is (expected != 'hit'),
                'bounded_LRU_hit_miss_bypass_mismatch')
        trace = r['cache_trace']
        if cache_identity is None:
            cache_identity = trace['cache_identity']
        require(trace['cache_identity'] == cache_identity and cache_identity != leaf,
                'cache_identity_changed')
        stored = False
        if expected == 'hit':
            hits += 1
            old = resident.pop(key)
            resident[key] = old
            origin = origins[key]
            require(r['source_miss_request'] == origin and records[origin]['scope'] == r['scope']
                    and records[origin]['key_sha256'] == key and r['scope'] == 'inner'
                    and r['importance_sha256'] == records[origin]['importance_sha256']
                    and r['effective_teacher_params_sha256'] == records[origin]['effective_teacher_params_sha256'],
                    'hit_origin_or_scope_invalid')
            require(r['timings_seconds']['cache_store_invoked'] is False and
                    r['timings_seconds']['cache_store'] == 0 and all(
                    r['timings_seconds'][k] == 0 for k in ['teacher_constructor', 'teacher_pure_fit',
                    'teacher_importance_extraction', 'teacher_parameter_probe']), 'hit_invokes_teacher_or_store')
        else:
            if expected == 'bypass':
                bypasses += 1
            else:
                misses += 1
            require(r['source_miss_request'] is None and
                    probe_json(r['effective_teacher_params']) == r['effective_teacher_params_sha256'],
                    'miss_effective_params_invalid')
            require(r['timings_seconds']['cache_store_invoked'] is True, 'normal_fit_store_not_attempted')
            if should_store:
                while resident and (len(resident) >= 4 or sum(resident.values()) + size > 262144):
                    resident.popitem(last=False)
                    evictions += 1
                resident[key] = size
                origins[key] = i
                stored = True
            elif key is not None:
                bypasses += 1
        require(trace['stored'] is stored and trace['resident_keys_lru'] == list(resident)
                and trace['resident_payload_bytes_lru'] == dict(resident), 'LRU_resident_trace_mismatch')
        snap = trace['snapshot']
        require(snap['enabled'] is True and snap['worker_cache_identity'] == cache_identity
                and snap['maximum_entries'] == 4 and snap['maximum_bytes'] == 262144
                and snap['entries'] == len(resident) and snap['metadata_and_importance_bytes'] == sum(resident.values())
                and (snap['hits'], snap['misses'], snap['bypasses'], snap['evictions']) ==
                (hits, misses, bypasses, evictions), 'LRU_snapshot_counter_mismatch')
    return {'hits': hits, 'misses': misses, 'bypasses': bypasses, 'evictions': evictions,
            'requests': len(records), 'leaf_identity': leaf, 'cache_identity': cache_identity}


def compare_leaf(work, aroot, arec, broot, brec, spec, validation_rows, manifest):
    import numpy as np
    import pandas as pd
    require(clean_semantics(arec, aroot) == clean_semantics(brec, broot), 'student_procedure_drift')
    factors_a, factors_b = arec['class_factors'], brec['class_factors']
    require(set(factors_a) == set(factors_b), 'class_factor_keys_changed')
    close_arrays([factors_a[k] for k in factors_a], [factors_b[k] for k in factors_a], 1e-12)
    refs, sides = [], []
    for root, record in [(aroot, arec), (broot, brec)]:
        ref = record['teacher_diagnostics']
        p = within(root, ref['path'])
        require(p == root / 'teacher-diagnostics.json' and digest(p) == ref['sha256'], 'diagnostic_sidecar_unbound')
        side = load(p)
        compiled = manifest['arms']['candidate']['compiled_sha256']
        source_roles = {'worker': 'automl_worker.py',
            'selection': 'automl_execution_feature_engineering_selection.py', 'frames': 'automl_frames.py',
            'features': 'automl_features.py', 'target_encoding': 'automl_execution_preprocessing_target_encoding.py',
            'history': 'automl_execution_preprocessing_history.py', 'weights': 'automl_weights.py',
            'teacher_probe': 'automl_execution_feature_engineering_teacher_probe.py',
            'teacher_key': 'automl_execution_feature_engineering_importance_cache.py',
            'teacher_adapter': 'automl_model_catboost.py'}
        require(side['source_modules_sha256'] == {role: compiled[n] for role, n in source_roles.items()},
                'actual_probe_runtime_source_not_bound')
        dep = manifest['dependencies']
        require(side['libraries'] == {k: dep[k] if k in {'python', 'implementation'} else dep[k]['version']
            for k in ['python', 'implementation', 'numpy', 'pandas', 'catboost']}
            and side['runtime_versions'] == {k: dep[k]['version'] for k in
                ['lightgbm', 'scikit-learn', 'scipy', 'threadpoolctl']}, 'actual_probe_libraries_not_bound')
        params = record['recipe'].get('params', {})
        require(side['context'] == {'recipe_sha256': canonical(record['recipe']), 'params_sha256': canonical(params),
            'spec_semantics_sha256': canonical({k: v for k, v in spec.items() if k not in {'root', 'task_path', 'paths'}}),
            'history_min_periods': params.get('history_min_periods', 2),
            'history_asof': params.get('history_asof', False)}, 'actual_probe_recipe_spec_context_not_bound')
        require(ref['leaf_identity'] == side['leaf_identity'] and ref['requests'] == len(side['requests'])
                and len(record['data_policy_runs']) == len(side['requests']), 'diagnostic_request_count_mismatch')
        for policy, request in zip(record['data_policy_runs'], side['requests']):
            require(policy['feature_selection']['teacher_diagnostics'] == request
                    and policy['feature_selection']['selected_columns'] == request['selected_columns']
                    and policy['feature_selection']['teacher_fitted'] is request['teacher_invoked'], 'student_probe_binding_mismatch')
        sides.append(side)
    x, y = sides
    require(x['leaf_identity'] != y['leaf_identity'] and x['context'] == y['context']
            and x['context_sha256'] == y['context_sha256'] and x['source_modules_sha256'] == y['source_modules_sha256']
            and x['libraries'] == y['libraries'] and x['runtime_versions'] == y['runtime_versions']
            and len(x['requests']) == len(y['requests']), 'corresponding_leaf_context_changed')
    for a, b in zip(x['requests'], y['requests']):
        for key in ['request', 'scope', 'fitting_rows', 'input_columns', 'key_sha256', 'context_sha256',
                    'components', 'status', 'columns', 'selected_columns', 'ranked_indices_sha256',
                    'effective_teacher_params_sha256', 'effective_teacher_params_status']:
            require(a[key] == b[key], 'actual_fitting_context_or_selection_drift')
        require({k: a['store_eligibility'][k] for k in ['eligible_if_enabled', 'maximum_bytes',
                    'candidate_payload_conservative_bytes']} ==
                {k: b['store_eligibility'][k] for k in ['eligible_if_enabled', 'maximum_bytes',
                    'candidate_payload_conservative_bytes']}, 'store_eligibility_parity_failed')
        close_arrays(a['importance'], b['importance'], 1e-12, 1e-12)
    off, on = replay(x, False), replay(y, True)
    require('selector_importance_cache' not in arec and brec['selector_importance_cache'] ==
            y['requests'][-1]['cache_trace']['snapshot'], 'result_cache_snapshot_mismatch')
    return {'off': off, 'on': on, 'importance_exact_digest_equal': all(
            a['importance_sha256'] == b['importance_sha256'] for a, b in zip(x['requests'], y['requests']))}


def predictions(root, spec, rows):
    import numpy as np
    import pandas as pd
    validation = pd.read_csv(root / 'validation_predictions.csv')
    require(list(validation.columns) == ['row_position', 'y_true', 'y_pred']
            and np.array_equal(validation['row_position'].to_numpy(), rows), 'validation_rows_changed')
    submission = pd.read_csv(root / 'submission.csv', dtype={spec['id']: str})
    require(list(submission.columns) == [spec['id'], *spec['output_columns']]
            and len(submission) == spec['n_test'] and not submission.isna().any().any(), 'submission_schema_invalid')
    if spec['kind'] == 'classification':
        require(spec.get('prediction_type') == 'value' and spec['output_columns'] == [spec['target']],
                'canonical_value_label_contract_required')
        matrices = []
        for name in ['validation', 'test']:
            with np.load(root / (name + '_probabilities.npz'), allow_pickle=False) as z:
                classes = z['classes'].astype(str).copy()
                prob = z['probabilities'].copy()
                if name == 'validation':
                    require(np.array_equal(z['row_position'], rows), 'probability_validation_row_order_changed')
            require(classes.tolist() == spec['classes'] and prob.shape ==
                    ((len(rows) if name == 'validation' else spec['n_test']), len(classes))
                    and np.isfinite(prob).all() and (prob >= 0).all() and (prob <= 1).all()
                    and np.allclose(prob.sum(axis=1), 1, atol=1e-6, rtol=0), 'probability_matrix_invalid')
            expected = classes[prob.argmax(axis=1)]
            saved = validation['y_pred'].astype(str).to_numpy() if name == 'validation' else submission[spec['target']].astype(str).to_numpy()
            require(np.array_equal(expected, saved), 'CSV_argmax_mismatch')
            matrices.append(prob)
        return validation, submission, matrices
    pred = validation['y_pred'].to_numpy(dtype=float)
    test = submission[spec['target']].to_numpy(dtype=float)
    require(np.isfinite(pred).all() and np.isfinite(test).all(), 'regression_prediction_nonfinite')
    return validation, submission, [pred, test]


def audit(work, manifest, campaign, deadline):
    import numpy as np
    import pandas as pd
    from sklearn.metrics import f1_score, mean_squared_error
    require(campaign['manifest_sha256'] == manifest['_sha256'] and campaign['API_limit'] == 0,
            'campaign_binding_invalid')
    require(campaign.get('cleanup_confirmed') is True and campaign.get('source_unchanged') is True,
            'campaign_terminal_pre_audit_not_clean')
    by_id = {s['id']: s for s in campaign['slots']}
    require(len(campaign['slots']) == len(by_id) == len(manifest['slots']) == 6
            and list(by_id) == ['c0o', 'c0n', 'c1n', 'c1o', 'r0o', 'r0n'], 'fixed_order_changed')
    fields = ['id', 'anchor', 'enabled', 'worker_cap', 'parent_cap']
    for actual, frozen in zip(campaign['slots'], manifest['slots']):
        require({k: actual[k] for k in fields} == {k: frozen[k] for k in fields}
                and all(type(actual[k]) is type(frozen[k]) for k in fields), 'frozen_slot_contract_changed')
    require(campaign['common_seconds'] == manifest['total_seconds'] == 7200
            and abs(campaign['common_deadline_unix'] - campaign['common_start_unix'] - 7200) <= 1e-6
            and abs(campaign['common_deadline_monotonic'] - campaign['common_start_monotonic'] - 7200) <= 1e-6,
            'original_common_clock_binding_invalid')
    expected = manifest['immutable_files']
    for n, sha in expected.items():
        require(digest(within(work, work / n)) == sha, 'immutable_source_input_changed')
    pairs, total_hits, complete = [], 0, True
    global_leaves, global_caches = set(), set()
    for anchor, off_id, on_id in [('c-trial00', 'c0o', 'c0n'), ('c-trial01', 'c1o', 'c1n'), ('r-trial00', 'r0o', 'r0n')]:
        require(time.monotonic() < deadline, 'audit_deadline_exhausted')
        off, on = by_id[off_id], by_id[on_id]
        if off['status'] != 'sealed_complete' or on['status'] != 'sealed_complete':
            complete = False
            pairs.append({'anchor': anchor, 'status': 'incomplete', 'metrics': None,
                'parent_delta_OFF_minus_ON': None, 'mechanism': None})
            continue
        aroot, aseal = sealed(work, off)
        broot, bseal = sealed(work, on)
        # Both pair seals/cleanups are established before parsing prediction
        # files (which also contain the worker's outer truth) or pristine labels.
        ja, jb = load(aroot / 'job.json'), load(broot / 'job.json')
        a = next(a for a in manifest['anchors'] if a['id'] == anchor)
        original = load(work / a['source_job'])
        for job, slot, root in [(ja, off, aroot), (jb, on, broot)]:
            spec = job['spec']
            require(job['recipe'] == original['recipe'] and job.get('threads') == 2 and job.get('full_fit') is False
                    and 'fit_iterations' not in job and job['selector_importance_diagnostics'] is True
                    and job['selector_importance_cache'] is slot['enabled']
                    and canonical({k: v for k, v in spec.items() if k not in {'root', 'task_path', 'paths'}})
                    == a['spec_nonpath_semantics_sha256'], 'materialized_job_semantic_drift')
            permitted = {'spec', 'output_dir', 'split_path', 'selector_importance_cache', 'selector_importance_diagnostics'}
            require({k: v for k, v in job.items() if k not in permitted} ==
                    {k: v for k, v in original.items() if k not in permitted}, 'undeclared_job_change')
            require(Path(job['output_dir']).resolve() == root and digest(job['split_path']) == a['source_split_sha256'],
                    'job_output_or_split_changed')
        spec = ja['spec']
        require(ja['spec'] == jb['spec'], 'OFF_ON_spec_differs')
        with np.load(ja['split_path'], allow_pickle=False) as z:
            rows = z['validation'].copy()
            fitting = z['train'].copy()
        require(fitting.dtype == np.dtype('int64') and rows.dtype == np.dtype('int64')
                and len(set(fitting.tolist())) == len(fitting) and len(set(rows.tolist())) == len(rows)
                and not set(fitting.tolist()) & set(rows.tolist()), 'split_invalid')
        ra, rb = load(aroot / 'result.json'), load(broot / 'result.json')
        require(ra['status'] == rb['status'] == 'ok' and ra['full_fit'] is rb['full_fit'] is False
                and clean_semantics(ra, aroot) == clean_semantics(rb, broot), 'callback_procedure_drift')
        la, lb = leaves(aroot, ra), leaves(broot, rb)
        require(len(la) == len(lb) == (2 if anchor[0] == 'c' else 1), 'fixed_leaf_count_changed')
        mechanism = []
        for (ad, ar), (bd, br) in zip(la, lb):
            item = compare_leaf(work, ad, ar, bd, br, spec, rows, manifest)
            for field in ['off', 'on']:
                leaf = item[field]['leaf_identity']
                require(leaf not in global_leaves, 'cross_callback_leaf_identity_reuse')
                global_leaves.add(leaf)
            cache = item['on']['cache_identity']
            require(cache not in global_caches, 'cross_callback_cache_identity_reuse')
            global_caches.add(cache)
            total_hits += item['on']['hits']
            mechanism.append(item)
        pair_hits = sum(item['on']['hits'] for item in mechanism)
        require(anchor[0] != 'r' or pair_hits == 0, 'regression_negative_control_hit')
        # Every corresponding node must preserve both CSV files exactly.
        for ad, bd in [(aroot, broot), *[(x[0], y[0]) for x, y in zip(la, lb)]]:
            for filename in ['submission.csv', 'validation_predictions.csv']:
                require(digest(ad / filename) == digest(bd / filename), 'exact_CSV_bytes_drift')
        av, at, ap = predictions(aroot, spec, rows)
        bv, bt, bp = predictions(broot, spec, rows)
        for x, y in zip(ap, bp):
            close_arrays(x, y, 1e-12 if anchor[0] == 'c' else 1e-9)
        if anchor[0] == 'c':
            for root, children, parent in [(aroot, la, ap), (broot, lb, bp)]:
                child_predictions = [predictions(d, spec, rows)[2] for d, _ in children]
                for index in range(2):
                    close_arrays(parent[index], .5 * child_predictions[0][index] + .5 * child_predictions[1][index], 1e-12)
        # Only here read pristine truth/IDs, after both seals and all parity.
        task = manifest['input_fingerprints']['tasks'][anchor[0]]
        pristine = work / task['pristine_source']
        for filename, sha in task['expected_files_sha256'].items():
            require(digest(pristine / filename) == sha, 'pristine_input_changed_before_score')
        train = pd.read_csv(pristine / 'train.csv', usecols=[spec['target'], spec['id']], dtype={spec['id']: str})
        test = pd.read_csv(pristine / 'test.csv', usecols=[spec['id']], dtype={spec['id']: str})
        sample = pd.read_csv(pristine / 'sample_submission.csv', dtype={spec['id']: str})
        require(at[spec['id']].tolist() == test[spec['id']].tolist() == sample[spec['id']].tolist(), 'CSV_ID_order_changed')
        truth = train[spec['target']].iloc[rows]
        if anchor[0] == 'c':
            require(av['y_true'].astype(str).tolist() == truth.astype(str).tolist(), 'saved_truth_drift')
            scores = [float(f1_score(truth.astype(str), v['y_pred'].astype(str), labels=spec['classes'],
                                    average='macro', zero_division=0)) for v in [av, bv]]
            require(abs(scores[0] - scores[1]) <= 1e-12, 'macroF1_drift')
        else:
            close_arrays(av['y_true'].to_numpy(dtype=float), truth.to_numpy(dtype=float), 0)
            scores = [float(math.sqrt(mean_squared_error(truth.to_numpy(dtype=float), v['y_pred'].to_numpy(dtype=float)))) for v in [av, bv]]
            require(abs(scores[0] - scores[1]) <= 1e-9, 'RMSE_drift')
        delta = off['timing']['parent_seconds'] - on['timing']['parent_seconds']
        pairs.append({'anchor': anchor, 'status': 'paired_parity_pass', 'metrics': {'OFF': scores[0], 'ON': scores[1]},
            'parent_seconds_OFF': off['timing']['parent_seconds'], 'parent_seconds_ON': on['timing']['parent_seconds'],
            'parent_delta_OFF_minus_ON': delta, 'eligible_hits': pair_hits, 'mechanism': mechanism,
            'zero_hit_pair_timing_only_observational': pair_hits == 0})
        require(aseal['files_sha256'] == files(aroot) and bseal['files_sha256'] == files(broot), 'late_pair_artifact_drift')
    for n, sha in expected.items():
        require(digest(work / n) == sha, 'late_immutable_source_input_drift')
    require(time.monotonic() < deadline, 'audit_deadline_exhausted')
    mechanism_pass = complete and total_hits > 0
    time_positive = complete and pairs[0]['parent_delta_OFF_minus_ON'] > 0 and \
        pairs[1]['parent_delta_OFF_minus_ON'] > 0 and sum(p['parent_delta_OFF_minus_ON'] for p in pairs) > 0
    return {'status': 'complete_six_parity_pass' if complete else 'incomplete_fixed_matrix',
        'complete_six': complete, 'pairs': pairs, 'verified_eligible_hits': total_hits,
        'mechanism_pass': mechanism_pass, 'mechanism_interpretation': 'verified_eligible_reuse' if mechanism_pass else
            'no_eligible_reuse_or_incomplete',
        'positive_descriptive_time_label': bool(time_positive),
        'time_attribution': 'Small fixed matrix observation; eligible reuse mechanism reported separately. Zero-hit pair deltas are observational.',
        'primary_time_rule_pass': bool(time_positive),
        'total_parent_delta_OFF_minus_ON': sum(p['parent_delta_OFF_minus_ON'] for p in pairs) if complete else None,
        'quality_gain': None, 'stable_speedup': None, 'full_agent_gain': None,
        'promotion': False, 'default_change': False, 'submit': False, 'fits': 0, 'API_calls': 0}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work-root', type=Path, required=True)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--campaign', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--deadline-monotonic', type=float, required=True)
    a = p.parse_args()
    result = None
    try:
        manifest = load(a.manifest)
        manifest['_sha256'] = digest(a.manifest)
        result = audit(a.work_root.resolve(), manifest, load(a.campaign), a.deadline_monotonic)
    except BaseException as exc:
        result = {'status': 'technical_audit_failure', 'exception_type': type(exc).__name__,
            'failure_code': str(exc) if isinstance(exc, AuditError) else 'unclassified_audit_error',
            'complete_six': False, 'mechanism_pass': False, 'positive_descriptive_time_label': False,
            'pairs': None, 'quality_gain': None, 'full_agent_gain': None, 'measured_savings': None,
            'promotion': False, 'fits': 0, 'API_calls': 0}
    with a.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    raise SystemExit(1 if result['status'] == 'technical_audit_failure' else 0)


if __name__ == '__main__':
    main()
