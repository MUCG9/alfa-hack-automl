"""Pure prospective fitting-only context; no file, model, gateway or clock access.

The caller passes ONLY aligned fitting vectors, not a full-train profile/frame.
It pins the existing class_support R3 JSON contract and supplies the SAME shared
preparation budget used for input extraction, both arms and message preflight.
Advice is source-bound trusted knowledge, never a tool/admission authority.
"""
import hashlib
import json
import math
import re
import struct

MAX_PACKET_BYTES = 8192
MAX_MESSAGE_BYTES = 65536
MAX_ROWS = 200000
MAX_FEATURES = 64
MAX_NAME_BYTES = 128
MAX_SCALAR_BYTES = 4096
MAX_INSPECTED_BYTES = 64 * 2**20
DISTINCT_CAP = 2048
SCHEMA = 'fitting-context-v1'


class ContextRejected(ValueError):
    def __init__(self, code):
        self.code = code
        self.receipt = dict(status='fitting_context_rejected_before_API', code=code,
                            quality_metric=None, API_calls=0, fields_dropped=False)
        super().__init__(code)


def _need(value, code):
    if not value:
        raise ContextRejected(code)


def _sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _text(value, maximum, code):
    _need(type(value) is str and len(value) <= maximum, code)
    try:
        encoded = value.encode('utf-8')
    except UnicodeEncodeError:
        raise ContextRejected(code) from None
    _need(len(encoded) <= maximum, code)
    return encoded


def _budget(budget):
    # The reused JSON helper uses `budget or PreparationBudget()`: reject a
    # falsey shared object before it can be replaced by a fresh local clock.
    _need(bool(budget) and callable(getattr(budget, 'check', None))
          and callable(getattr(budget, 'receipt', None)), 'shared_preparation_budget_required')
    budget.check()


def _vector(value, count, code):
    # Check shape BEFORE any enumeration; full-train labels must not be reduced.
    _need(type(value) in (list, tuple) and len(value) == count, code)


def _rounded(value):
    _need(math.isfinite(value), 'numeric_summary_overflow')
    return float(format(value, '.8g'))


def _scalar(value):
    """Typed, length-delimited digest view; no raw scalar is placed in context."""
    if value is None or (type(value) is float and math.isnan(value)):
        return b'm', True, None, False
    if type(value) is str:
        raw = _text(value, MAX_SCALAR_BYTES, 'feature_scalar_UTF8_limit')
        return b's' + struct.pack('<I', len(raw)) + raw, False, None, False
    if type(value) is bool:
        return b'b' + bytes([value]), False, float(value), False
    if type(value) is int:
        _need(value.bit_length() <= 1024, 'integer_scalar_limit')
        raw = str(value).encode('ascii')
        try:
            number = float(value)
        except OverflowError:
            raise ContextRejected('numeric_scalar_overflow') from None
        _need(math.isfinite(number), 'numeric_scalar_overflow')
        return b'i' + struct.pack('<I', len(raw)) + raw, False, number, False
    if type(value) is float:
        if not math.isfinite(value):
            return b'p' if value > 0 else b'n', False, None, True
        return b'f' + struct.pack('<d', value), False, value, False
    raise ContextRejected('plain_scalar_fitting_values_required')


def _summary(values, count, budget, digest, inspected):
    missing = nonfinite = finite = 0
    numeric = True
    smallest = largest = mean = second = 0.
    distinct = set()
    overflow = False
    for index, value in enumerate(values):
        if index % 1024 == 0:
            budget.check()
        token, absent, number, infinite = _scalar(value)
        inspected[0] += len(token)
        _need(inspected[0] <= MAX_INSPECTED_BYTES, 'inspected_scalar_byte_limit')
        digest.update(struct.pack('<I', len(token)) + token)
        missing += int(absent)
        nonfinite += int(infinite)
        if absent:
            continue
        if len(distinct) <= DISTINCT_CAP:
            distinct.add(hashlib.sha256(token).digest())
            overflow = len(distinct) > DISTINCT_CAP
        if infinite:
            continue
        if number is None:
            numeric = False
            continue
        finite += 1
        if finite == 1:
            smallest = largest = mean = number
        else:
            smallest, largest = min(smallest, number), max(largest, number)
            delta = number - mean
            mean += delta / finite
            second += delta * (number - mean)
            _need(math.isfinite(mean) and math.isfinite(second), 'numeric_summary_overflow')
    result = dict(missing=missing,
                  distinct='at_least_2049' if overflow else len(distinct))
    if nonfinite:
        result['nonfinite'] = nonfinite
    if numeric and finite:
        result['numeric'] = dict(min=_rounded(smallest), max=_rounded(largest),
                                 mean=_rounded(mean))
    elif numeric:
        result['numeric'] = None
    # Only a numeric regression target asks for std; do not add dozens of
    # redundant feature statistics or data samples to the bounded packet.
    budget.check()
    return result, finite, mean, second


def _advice(value, bounds, budget):
    if value is None:
        return None
    _need(type(value) is dict and len(value) == 2 and set(value) == {'source_sha256', 'packet'}
          and _sha(value['source_sha256']) and type(value['packet']) is dict,
          'source_bound_advice_required')
    raw, _ = bounds._json_text(value, MAX_PACKET_BYTES, budget)
    return json.loads(raw)


def build_fitting_context(*, fitting_positions, source_row_count, fitting_features,
                         fitting_target, allowed_features, target_name,
                         protected_identifiers, kind, metric, input_sha256,
                         split_sha256, bounds, budget, data_advice=None, method_advice=None,
                         loss_advice=None, kernel_advice=None):
    """Return (new packet, receipt). All values are plain Python fitting vectors.

    No full frame/profile, validation/test target, outer metric, fitted model,
    prior-best outcome or protected-ID value is an accepted argument. The trusted
    upstream extractor must select exact positions and normalize scalar types
    BEFORE invoking this function, inside the same caller-owned parent clock.
    """
    _budget(budget)
    _need(callable(getattr(bounds, '_json_text', None)), 'pinned_JSON_contract_required')
    _need(kind in {'classification', 'regression'}
          and metric == ('macro_f1' if kind == 'classification' else 'rmse'),
          'ordinary_supervised_objective_required')
    _need(type(source_row_count) is int and 2 <= source_row_count <= MAX_ROWS,
          'source_row_count_limit')
    _need(type(fitting_positions) in (list, tuple)
          and 1 <= len(fitting_positions) < source_row_count,
          'proper_fitting_subset_required_not_full_train')
    count = len(fitting_positions)
    _need(type(allowed_features) in (list, tuple)
          and 1 <= len(allowed_features) <= MAX_FEATURES, 'allowed_feature_count_limit')
    _need(type(protected_identifiers) in (list, tuple)
          and len(protected_identifiers) <= 16, 'protected_identifier_role_limit')
    _text(target_name, MAX_NAME_BYTES, 'target_role_name_limit')
    for name in [*allowed_features, *protected_identifiers]:
        _text(name, MAX_NAME_BYTES, 'feature_role_name_limit')
    _need(len(set(allowed_features)) == len(allowed_features)
          and len(set(protected_identifiers)) == len(protected_identifiers),
          'duplicate_role_names')
    forbidden = set(protected_identifiers) | {target_name}
    _need(not set(allowed_features) & forbidden, 'target_or_protected_ID_in_features')
    _need(type(fitting_features) is dict and len(fitting_features) == len(allowed_features)
          and set(fitting_features) == set(allowed_features), 'closed_fitting_feature_roles_required')
    _need(type(input_sha256) is dict and len(input_sha256) == 2
          and set(input_sha256) == {'train', 'task'}
          and all(_sha(h) for h in input_sha256.values()) and _sha(split_sha256),
          'frozen_input_and_split_SHA_required')
    _vector(fitting_target, count, 'aligned_fitting_target_only_required')
    for name in allowed_features:
        _vector(fitting_features[name], count, 'aligned_fitting_features_only_required')
    positions = hashlib.sha256()
    seen = set()
    for index, row in enumerate(fitting_positions):
        if index % 1024 == 0:
            budget.check()
        _need(type(row) is int and 0 <= row < source_row_count and row not in seen,
              'unique_bounded_integer_fitting_positions_required')
        seen.add(row)
        positions.update(struct.pack('<q', row))
    del seen
    # Validate and bound knowledge BEFORE reductions; caller pins its origin.
    advice = {name: _advice(value, bounds, budget) for name, value in
              [('data', data_advice), ('method', method_advice),
               ('loss', loss_advice), ('kernel', kernel_advice)]}
    features = {}
    observed = [0]
    feature_digest = hashlib.sha256()
    for name in allowed_features:
        encoded = name.encode('utf-8')
        feature_digest.update(struct.pack('<I', len(encoded)) + encoded)
        features[name] = _summary(fitting_features[name], count, budget,
                                  feature_digest, observed)[0]
    target_digest = hashlib.sha256()
    if kind == 'classification':
        counts = {}
        for index, label in enumerate(fitting_target):
            if index % 1024 == 0:
                budget.check()
            encoded = _text(label, MAX_NAME_BYTES, 'plain_fitting_class_label_limit')
            observed[0] += 4 + len(encoded)
            _need(observed[0] <= MAX_INSPECTED_BYTES, 'inspected_scalar_byte_limit')
            _need(label in counts or len(counts) < 64, 'fitting_class_count_limit')
            counts[label] = counts.get(label, 0) + 1
            target_digest.update(struct.pack('<I', len(encoded)) + encoded)
        target = dict(class_counts={c: counts[c] for c in sorted(counts)})
    else:
        for index, value in enumerate(fitting_target):
            if index % 1024 == 0:
                budget.check()
            _need(type(value) in (int, float), 'finite_numeric_fitting_target_required')
            if type(value) is int:
                _need(value.bit_length() <= 1024, 'integer_scalar_limit')
            else:
                _need(math.isfinite(value), 'finite_numeric_fitting_target_required')
        info, finite, mean, second = _summary(fitting_target, count, budget,
                                             target_digest, observed)
        _need(finite == count, 'complete_fitting_target_required')
        target = dict(info['numeric'], std=_rounded(math.sqrt(max(0., second/count))))
    packet = dict(schema=SCHEMA, scope='explicit_fitting_rows_only_before_FE_or_resampling',
        objective=dict(kind=kind, metric=metric, greater_is_better=kind == 'classification'),
        provenance=dict(input_sha256=dict(input_sha256), split_sha256=split_sha256,
            source_rows=source_row_count, fitting_rows=count,
            position_space='original_source_train_row_position',
            ordered_fitting_positions_int64le_sha256=positions.hexdigest(),
            fitting_feature_scalar_view_sha256=feature_digest.hexdigest(),
            fitting_target_scalar_view_sha256=target_digest.hexdigest()),
        data=dict(features=features, target=dict(column=target_name, **target),
            forbidden_feature_columns=[target_name, *protected_identifiers],
            group_support=None,
            group_support_limitation='No row/label-independent entity or raw-feature group count is inferred.',
            numeric_significant_digits=8, distinct_cap=DISTINCT_CAP),
        advice=advice,
        authority='Data and source-bound advice only; does not change tools, metric, splits, models, HPO or job admission.')
    raw, size = bounds._json_text(packet, MAX_PACKET_BYTES, budget)
    _need(size <= MAX_PACKET_BYTES, 'fitting_packet_UTF8_overflow')
    # Serialization returns an independent, finite plain-JSON value without
    # sharing mutable input/advice objects across the two prospective arms.
    packet = json.loads(raw)
    receipt = dict(status='fitting_context_prepared', packet_UTF8_bytes=size,
        packet_sha256=hashlib.sha256(raw.encode('utf-8')).hexdigest(),
        fitting_rows=count, inspected_scalar_bytes=observed[0],
        scope='plain_scalar_snapshot_identity_not_native_model_cache_identity',
        cost_scope='Caller must charge extraction/input IO plus this reduction/preflight inside the same parent; no local clock is created.',
        quality_metric=None, API_calls=0, model_fits=0, fields_dropped=False)
    budget.check()
    return packet, receipt


def preflight_gateway_messages(system_prompt, packet, *, receipt, bounds, budget):
    """Exact existing gateway user serialization; no old full-train context merge.

    BOTH arm views must be built/preflighted by the future harness before either
    actual request. This helper neither requests Qwen nor owns an experiment.
    """
    _budget(budget)
    _need(type(packet) is dict and packet.get('schema') == SCHEMA,
          'fitting_packet_schema_required')
    raw, _ = bounds._json_text(packet, MAX_PACKET_BYTES, budget)
    _need(type(receipt) is dict and receipt.get('status') == 'fitting_context_prepared'
          and hashlib.sha256(raw.encode('utf-8')).hexdigest() == receipt.get('packet_sha256'),
          'builder_packet_receipt_mismatch')
    context = {'fitting_context': json.loads(raw)}
    proof = bounds.bounded_messages(system_prompt, context, budget=budget)
    _need(proof['messages_UTF8_bytes'] <= MAX_MESSAGE_BYTES,
          'complete_gateway_messages_UTF8_overflow')
    budget.check()
    return context, proof
