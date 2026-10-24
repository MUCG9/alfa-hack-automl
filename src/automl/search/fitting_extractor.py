"""Prospective trusted post-split projection; no CSV, gateway, model or clock owner.

The caller owns the loader, MetricSpec, role/input authority and frozen split.
Only that caller may construct these records. SHA syntax is not proof of origin.
No value from a validation/test/ID vector is accepted or needed. Original-row
column views are trusted in-process objects, not arbitrary deserialized code.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import re
import struct
import sys
from pathlib import Path

from automl.search.fitting_context import build_fitting_context, preflight_gateway_messages

MAX_ROWS = 200000
MAX_FEATURES = 64
MAX_NAME_BYTES = 128
MAX_SCALAR_BYTES = 4096
MAX_SCALAR_VIEW_BYTES = 64 * 2**20
MAX_RETAINED_ESTIMATE_BYTES = 128 * 2**20
MAX_IO_BYTES = 256 * 2**20
CHUNK_CELLS = 256
POSITION_SPACE = 'original_source_train_row_position'


class ExtractionRejected(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _need(value, code):
    if not value:
        raise ExtractionRejected(code)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _sha(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _text(value, limit, code):
    _need(type(value) is str and len(value) <= limit, code)
    try:
        raw = value.encode('utf-8')
    except UnicodeEncodeError:
        raise ExtractionRejected(code) from None
    _need(len(raw) <= limit, code)
    return raw


@dataclass(frozen=True)
class RoleAuthority:
    """Explicit validated roles, never a column-name/task-kind heuristic."""
    features: tuple
    target: str
    identifiers: tuple
    kind: str
    metric: str
    objective_status: str = 'resolved'
    source_role: str = 'train'


@dataclass(frozen=True)
class SplitInputAuthority:
    """Expected evidence from the caller's independently frozen input/split."""
    source_rows: int
    train_sha256: str
    task_sha256: str
    dictionary_sha256: object
    split_file_sha256: str
    ordered_fitting_int64le_sha256: str
    ordered_validation_int64le_sha256: str
    combined_positions_int64le_sha256: str
    position_space: str = POSITION_SPACE


class CallerBudget:
    """Truthy forwarding adapter, with no new clock or preparation allowance.

    RunBudget's ORIGINAL started/deadline/clock are retained. The zero-argument
    checkpoint is the caller's existing resource/observation guard. Its failures
    remain sticky. IO is a caller-supplied actual cumulative counter plus explicit
    charges; this module performs no input IO. This is not an independent meter.
    """
    def __init__(self, original, checkpoint, *, io_bytes_already_charged):
        _need(bool(original) and callable(getattr(original, 'clock', None))
              and bool(checkpoint) and callable(checkpoint), 'original_caller_budget_required')
        _need(_number(getattr(original, 'started', None))
              and _number(getattr(original, 'deadline', None))
              and original.deadline > original.started, 'original_absolute_deadline_required')
        _need(type(io_bytes_already_charged) is int
              and 0 <= io_bytes_already_charged <= MAX_IO_BYTES, 'actual_IO_counter_required')
        self.original, self.checkpoint = original, checkpoint
        self.clock, self.started, self.deadline = original.clock, original.started, original.deadline
        self.io_bytes = io_bytes_already_charged
        self._last = self.started
        self._failure = None
        self.check()

    def _now(self):
        _need(self.original.clock is self.clock and _number(self.original.started)
              and _number(self.original.deadline) and self.original.started == self.started
              and self.original.deadline == self.deadline, 'original_budget_origin_changed')
        now = self.clock()
        _need(_number(now) and now >= self._last, 'caller_clock_nonfinite_or_rollback')
        _need(now < self.deadline, 'original_caller_deadline_exhausted')
        self._last = now  # rollback check only; NEVER a resource/heartbeat sample.
        return now

    def check(self):
        if self._failure is not None:
            raise self._failure
        try:
            self._now()
            self.checkpoint()
            self._now()
        except Exception as exc:
            self._failure = exc
            raise

    def charge_io(self, count):
        self.check()
        try:
            _need(type(count) is int and count >= 0, 'nonnegative_actual_IO_charge_required')
            _need(self.io_bytes + count <= MAX_IO_BYTES, 'original_parent_IO_limit')
            self.io_bytes += count
        except Exception as exc:
            self._failure = exc
            raise
        self.check()

    def receipt(self):
        self.check()
        return dict(preparation_seconds=self._last - self.started,
            preparation_IO_bytes=self.io_bytes, charged_inside_existing_parent_deadline=True,
            timing_scope='Original parent elapsed, NOT a new preparation clock or exclusive extractor time.',
            IO_scope='Trusted caller actual cumulative counter; upstream loader/hash instrumentation required.')


def _roles(roles):
    _need(type(roles) is RoleAuthority and type(roles.source_role) is str
          and roles.source_role == 'train' and type(roles.objective_status) is str
          and roles.objective_status == 'resolved', 'resolved_trusted_train_roles_required')
    _need(type(roles.kind) is str and type(roles.metric) is str
          and roles.kind in ('classification', 'regression')
          and roles.metric == ('macro_f1' if roles.kind == 'classification' else 'rmse'),
          'supported_resolved_MetricSpec_required')
    _need(type(roles.features) is tuple and 1 <= len(roles.features) <= MAX_FEATURES
          and type(roles.identifiers) is tuple and len(roles.identifiers) <= 16,
          'bounded_closed_role_names_required')
    names = (roles.target, *roles.features, *roles.identifiers)
    for name in names:
        _need(bool(_text(name, MAX_NAME_BYTES, 'role_name_UTF8_limit')), 'empty_role_name')
    _need(len(set(names)) == len(names), 'target_ID_or_duplicate_feature_role')
    view = dict(features=list(roles.features), target=roles.target,
        identifiers=list(roles.identifiers), kind=roles.kind, metric=roles.metric,
        objective_status=roles.objective_status, source_role=roles.source_role)
    raw = json.dumps(view, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _positions(values, rows, budget, code):
    _need(type(values) in (tuple, list) and 1 <= len(values) < rows, code)
    seen, digest = set(), hashlib.sha256()
    for index, value in enumerate(values):
        if index % CHUNK_CELLS == 0:
            budget.check()
        _need(type(value) is int and 0 <= value < rows and value not in seen, code)
        seen.add(value)
        digest.update(struct.pack('<q', value))
    budget.check()
    return seen, digest.hexdigest()


def _authority(authority, observed_input_sha256, observed_split_file_sha256,
               fitting_positions, validation_positions, budget):
    _need(type(authority) is SplitInputAuthority and type(authority.position_space) is str
          and authority.position_space == POSITION_SPACE,
          'original_train_position_authority_required')
    _need(type(authority.source_rows) is int and 2 <= authority.source_rows <= MAX_ROWS,
          'bounded_source_row_count_required')
    expected_inputs = dict(train=authority.train_sha256, task=authority.task_sha256,
                           dictionary=authority.dictionary_sha256)
    _need(all(_sha(value) for key, value in expected_inputs.items() if key != 'dictionary')
          and (authority.dictionary_sha256 is None or _sha(authority.dictionary_sha256)),
          'expected_input_SHA_required')
    _need(type(observed_input_sha256) is dict and len(observed_input_sha256) == 3
          and set(observed_input_sha256) == set(expected_inputs)
          and _sha(observed_input_sha256['train']) and _sha(observed_input_sha256['task'])
          and (observed_input_sha256['dictionary'] is None or _sha(observed_input_sha256['dictionary']))
          and observed_input_sha256 == expected_inputs, 'observed_expected_input_SHA_mismatch')
    _need(_sha(authority.split_file_sha256)
          and _sha(observed_split_file_sha256)
          and observed_split_file_sha256 == authority.split_file_sha256,
          'observed_expected_split_file_SHA_mismatch')
    for value in (authority.ordered_fitting_int64le_sha256,
                  authority.ordered_validation_int64le_sha256,
                  authority.combined_positions_int64le_sha256):
        _need(_sha(value), 'expected_ordered_split_SHA_required')
    fit, fit_sha = _positions(fitting_positions, authority.source_rows, budget,
                               'unique_original_fitting_positions_required')
    va, va_sha = _positions(validation_positions, authority.source_rows, budget,
                            'unique_original_validation_positions_required')
    _need(fit.isdisjoint(va), 'fitting_validation_overlap')
    combined = hashlib.sha256()
    for values in (fitting_positions, validation_positions):
        for index, value in enumerate(values):
            if index % CHUNK_CELLS == 0:
                budget.check()
            combined.update(struct.pack('<q', value))
    _need(fit_sha == authority.ordered_fitting_int64le_sha256
          and va_sha == authority.ordered_validation_int64le_sha256
          and combined.hexdigest() == authority.combined_positions_int64le_sha256,
          'ordered_original_split_digest_mismatch')
    budget.check()


def _plain(value, *, target, kind):
    # Series.iloc yields NumPy scalars; convert ONLY scalars, not ndarray/objects.
    if any(base.__module__ == 'numpy' and base.__name__ == 'generic'
           for base in type(value).__mro__):
        value = value.item()
    if type(value).__module__.startswith('pandas.') and type(value).__name__ in ('NAType', 'NaTType'):
        value = None
    if value is None or (type(value) is float and math.isnan(value)):
        _need(not target, 'missing_fitting_target_not_allowed')
        return None
    _need(type(value) in (str, bool, int, float), 'unsupported_fitting_scalar')
    if type(value) is int:
        _need(value.bit_length() <= 1024, 'fitting_integer_limit')
    if type(value) in (int, float):
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        _need(finite, 'nonfinite_fitting_scalar_not_allowed')
    if target and kind == 'regression':
        _need(type(value) in (int, float), 'numeric_regression_target_required')
    if target and kind == 'classification':
        value = str(value)  # matches native scalar string labels; literal NA/001 unchanged.
    if type(value) is str:
        _text(value, MAX_NAME_BYTES if target else MAX_SCALAR_BYTES, 'fitting_scalar_UTF8_limit')
    return value


def extract_fitting_context(*, source_columns, fitting_positions, validation_positions,
                            roles, expected_role_sha256, authority, observed_input_sha256,
                            observed_split_file_sha256, system_prompt, bounds, budget):
    """Return a fresh gateway-context view and evidence; never send a request.

    Columns are ONLY named feature+target original-row views from a trusted
    validated CSV loader. list/tuple or positional .iloc views are supported.
    Extra columns, including ID/test/validation target roles, reject pre-read.
    Split positions must already be mapped back to ORIGINAL source rows.
    No legacy profile/split_info/feedback context is an accepted argument.
    """
    _need(type(budget) is CallerBudget, 'original_CallerBudget_adapter_required')
    budget.check()
    role_sha = _roles(roles)
    _need(_sha(expected_role_sha256) and role_sha == expected_role_sha256,
          'trusted_role_digest_mismatch')
    _authority(authority, observed_input_sha256, observed_split_file_sha256,
               fitting_positions, validation_positions, budget)
    names = (*roles.features, roles.target)
    _need(type(source_columns) is dict and len(source_columns) == len(names)
          and set(source_columns) == set(names), 'closed_train_feature_target_views_required')
    # Validate ALL shapes before any scalar access. No full-column copy/iteration.
    for name in names:
        column = source_columns[name]
        _need(type(column) in (list, tuple) or hasattr(column, 'iloc'), 'positional_column_view_required')
        _need(len(column) == authority.source_rows, 'original_source_column_length_mismatch')
        budget.check()
    projected, scalar_bytes = {}, 0
    retained = sys.getsizeof(projected) + len(fitting_positions) * 16
    for name in names:
        budget.check()
        column, values = source_columns[name], []
        positional = column if type(column) in (list, tuple) else column.iloc
        for index, row in enumerate(fitting_positions):
            if index % CHUNK_CELLS == 0:
                budget.check()
            value = _plain(positional[row], target=name == roles.target, kind=roles.kind)
            token = json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
            scalar_bytes += len(token) + 4
            _need(scalar_bytes <= MAX_SCALAR_VIEW_BYTES, 'projected_scalar_byte_limit')
            retained += sys.getsizeof(value) + 8
            _need(retained <= MAX_RETAINED_ESTIMATE_BYTES, 'retained_projection_estimate_limit')
            values.append(value)
        projected[name] = values
        budget.check()
    packet, builder_receipt = build_fitting_context(
        fitting_positions=fitting_positions, source_row_count=authority.source_rows,
        fitting_features={name: projected[name] for name in roles.features},
        fitting_target=projected[roles.target], allowed_features=roles.features,
        target_name=roles.target, protected_identifiers=roles.identifiers,
        kind=roles.kind, metric=roles.metric,
        input_sha256={'train': authority.train_sha256, 'task': authority.task_sha256},
        split_sha256=authority.combined_positions_int64le_sha256, bounds=bounds, budget=budget)
    context, message_proof = preflight_gateway_messages(system_prompt, packet,
        receipt=builder_receipt, bounds=bounds, budget=budget)
    budget.check()
    receipt = dict(schema='trusted-fitting-extraction-v1', status='prepared_not_sent',
        role_sha256=role_sha, input_sha256=dict(observed_input_sha256),
        split_file_sha256=authority.split_file_sha256,
        ordered_fitting_int64le_sha256=authority.ordered_fitting_int64le_sha256,
        ordered_validation_int64le_sha256=authority.ordered_validation_int64le_sha256,
        combined_positions_int64le_sha256=authority.combined_positions_int64le_sha256,
        position_space=POSITION_SPACE, fitting_rows=len(fitting_positions),
        validation_positions_only=len(validation_positions),
        scalar_view_UTF8_bytes=scalar_bytes, retained_projection_estimate_bytes=retained,
        memory_scope='Conservative scalar/list estimate only; original caller owns actual RSS guard.',
        upstream_authority='Trusted extractor caller must bind actual loader columns, input hashes and original split; hashes alone grant no authority.',
        new_input_IO_bytes=0, caller_budget=budget.receipt(), builder=builder_receipt,
        gateway_preflight=message_proof, API_calls=0, model_fits=0, quality_metric=None,
        whole_feedback_fitting_only=False, legacy_context_merged=False)
    return context, receipt


@dataclass(frozen=True)
class TrustedFrameWitness:
    """References captured by the trusted strict producer, never JSON authority.

    Identity binds the original validated objects; it is not a content fingerprint
    of a native matrix or a sandbox against arbitrary Python supplied by a caller.
    source_paths/source_fingerprints are the producer's full protected provenance.
    """
    producer_frame: object
    producer_spec: object
    producer_declaration: object
    producer_metric_spec: object
    producer_budget: object
    producer_checkpoint: object
    declaration_receipt: object
    source_fingerprints: object
    source_paths: object


def _frame_guard(budget, checkpoint, *, force=False):
    """Observe existing guard state; never create a resource guard or allowance."""
    resources = getattr(checkpoint, 'resources', None)
    _need(getattr(checkpoint, 'budget', None) is budget.original
          and callable(getattr(resources, 'inspect', None))
          and type(getattr(resources, 'memory_limit', None)) is int
          and resources.memory_limit > 0, 'original_RSS_guard_required')
    budget.check()
    if force:
        checkpoint(force=True)
    budget.check()
    sampled = getattr(checkpoint, '_last_sample', None)
    _need(getattr(checkpoint, '_failure', object()) is None and _number(sampled)
          and budget.started <= sampled <= budget._last
          and budget._last - sampled <= 10, 'successful_original_RSS_observation_required')
    return dict(last_successful_sample_monotonic=sampled,
                memory_limit_bytes=resources.memory_limit,
                raw_RSS_bytes=None, raw_total_RSS_bytes=None,
                scope='Existing source-bound guard succeeded; raw RSS is not retained by that guard.')


def _frame_file(path, check):
    path = Path(path)
    _need(path.is_absolute(), 'absolute_producer_path_required')
    for part in (path, *path.parents):
        check()
        info = part.lstat()
        _need(not part.is_symlink() and not (getattr(info, 'st_file_attributes', 0) & 0x400),
              'producer_path_symlink_or_reparse')
    _need(path.is_file() and path.resolve(strict=True) == path,
          'exact_regular_producer_file_required')
    return path


def _frame_hash(path, budget, check, counter):
    path = _frame_file(path, check)
    before = path.stat()
    _need(before.st_size <= MAX_IO_BYTES - budget.io_bytes, 'fresh_hash_IO_limit')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while True:
            check()
            block = stream.read(2**20)
            if not block:
                break
            counter[0] += len(block)
            budget.charge_io(len(block))
            digest.update(block)
    after = path.stat()
    _need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
          == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
          'producer_file_changed_during_hash')
    check()
    return digest.hexdigest()


def prepare_validated_frame_context(*, frame, spec, declaration, metric_spec, witness,
                                    roles, expected_role_sha256, authority,
                                    fitting_positions, validation_positions, split_path,
                                    system_prompt, bounds, budget):
    """Use the exact trusted, already validated frame; NEVER reparse a table.

    Fresh hash-stream IO is measured here. Earlier native parser/hash IO remains
    UNKNOWN, not zero or total-parent IO qualification. The producer must be the
    reviewed strict task flow and hold exact references in its scoped ContextVar.
    """
    counter = [0]
    try:
        _need(type(budget) is CallerBudget and type(witness) is TrustedFrameWitness,
              'trusted_frame_and_original_budget_required')
        _need(frame is witness.producer_frame and spec is witness.producer_spec
              and declaration is witness.producer_declaration
              and metric_spec is witness.producer_metric_spec
              and budget.original is witness.producer_budget
              and budget.checkpoint is witness.producer_checkpoint,
              'exact_strict_producer_objects_required')
        checkpoint = witness.producer_checkpoint
        check = lambda: _frame_guard(budget, checkpoint)
        initial_guard = _frame_guard(budget, checkpoint, force=True)
        _need(type(spec) is dict and spec.get('strict_task_contract', {}).get(
              'full_input_provenance_verified') is True, 'validated_strict_frame_required')
        _need(getattr(declaration, 'ready_for_projection', False) is True
              and getattr(declaration, 'receipt', None) is witness.declaration_receipt
              and type(witness.declaration_receipt) is dict,
              'exact_IO03_declaration_receipt_required')
        role_sha = _roles(roles)
        _need(getattr(metric_spec, 'status', None) == 'resolved'
              and getattr(metric_spec, 'name', None) == spec.get('metric') == roles.metric
              and callable(getattr(metric_spec, 'require_resolved', None)),
              'exact_resolved_metric_object_required')
        metric_spec.require_resolved()
        _need(role_sha == expected_role_sha256
              and spec.get('kind') == roles.kind and spec.get('target') == roles.target
              and tuple(spec.get('features', ())) == roles.features
              and roles.identifiers == (() if spec.get('id') is None else (spec['id'],)),
              'validated_frame_closed_roles_mismatch')
        stated = getattr(declaration, 'declaration', None)
        _need(getattr(stated, 'target', None) == roles.target
              and getattr(stated, 'identifier', None) == spec.get('id')
              and getattr(stated, 'kind', None) in ((roles.kind,) if roles.kind == 'regression'
                  else ('classification', 'binary', 'multiclass')),
              'IO03_roles_disagree_with_validated_frame')
        _need(type(authority) is SplitInputAuthority and type(frame).__module__.startswith('pandas.')
              and type(frame).__name__ == 'DataFrame' and len(frame) == authority.source_rows
              and spec.get('n_train') == authority.source_rows, 'original_full_training_frame_required')
        columns = list(frame.columns)
        _need(all(type(v) is str for v in columns) and len(columns) == len(set(columns))
              and set(columns) == set((*roles.features, roles.target, *roles.identifiers)),
              'closed_validated_frame_schema_required')
        paths, expected = witness.source_paths, witness.source_fingerprints
        _need(type(paths) is dict and type(expected) is dict and set(paths) == set(expected)
              and 4 <= len(paths) <= 1024 and all(type(k) is str and
                  (k == 'task' or k in ('input:train', 'input:test', 'input:sample_submission',
                   'input:data_dictionary') or k.startswith('source:')) for k in paths)
              and all(_sha(v) for v in expected.values()), 'complete_strict_producer_provenance_required')
        frozen_paths = {k: str(Path(v)) for k, v in paths.items()}
        frozen_expected = dict(expected)
        _need({'task', 'input:train', 'input:test', 'input:sample_submission'} <= set(paths)
              and any(k.startswith('source:') for k in paths), 'strict_role_and_source_paths_required')
        root = Path(frozen_paths['task']).parent
        declared_paths = getattr(declaration, 'paths', None)
        _need(type(declared_paths) is dict and set(declared_paths) == {'train','test','sample_submission'}
              and Path(spec.get('task_path', '')).resolve() == Path(frozen_paths['task'])
              and Path(getattr(checkpoint, 'root', '')).resolve() == root,
              'exact_declared_task_and_resource_root_required')
        for role in ('train', 'test', 'sample_submission'):
            _need((root / declared_paths[role]).resolve() == Path(frozen_paths['input:'+role])
                  == Path(spec.get('paths', {}).get(role, '')).resolve(), 'strict_input_path_drift')
        dictionary = witness.declaration_receipt.get('dictionary_path')
        _need(('input:data_dictionary' in paths) == (dictionary is not None),
              'declared_dictionary_binding_required')
        if dictionary is not None:
            _need((root / dictionary).resolve() == Path(frozen_paths['input:data_dictionary'])
                  and expected['input:data_dictionary'] == witness.declaration_receipt.get(
                      'dictionary_metadata_sha256'), 'dictionary_provenance_drift')
        _need(expected['task'] == witness.declaration_receipt.get('task_text_sha256'),
              'task_declaration_provenance_drift')
        # Bind the real guard's Python source to the frozen strict source map.
        for method in (type(checkpoint).__call__, type(checkpoint.resources).inspect):
            code = getattr(method, '__code__', None)
            _need(code is not None and any(k.startswith('source:') and
                  Path(v).resolve() == Path(code.co_filename).resolve() for k,v in frozen_paths.items()),
                  'original_resource_guard_source_binding_required')
        hash_before = budget.io_bytes
        observed = {k: _frame_hash(v, budget, check, counter) for k,v in frozen_paths.items()}
        _need(observed == frozen_expected, 'strict_producer_input_or_source_changed')
        split_sha = _frame_hash(split_path, budget, check, counter)
        observed_inputs = dict(train=observed['input:train'], task=observed['task'],
            dictionary=observed.get('input:data_dictionary'))
        # Original-space rows and expected source/split digests remain independently
        # supplied by the trusted split producer; never derive authority from them here.
        _authority(authority, observed_inputs, split_sha, fitting_positions, validation_positions, budget)
        context, receipt = extract_fitting_context(source_columns={
            name: frame[name] for name in (*roles.features, roles.target)},
            fitting_positions=fitting_positions, validation_positions=validation_positions,
            roles=roles, expected_role_sha256=expected_role_sha256, authority=authority,
            observed_input_sha256=observed_inputs, observed_split_file_sha256=split_sha,
            system_prompt=system_prompt, bounds=bounds, budget=budget)
        post = {k: _frame_hash(v, budget, check, counter) for k,v in frozen_paths.items()}
        _need(post == frozen_expected and _frame_hash(split_path, budget, check, counter) == split_sha
              and {k:str(Path(v)) for k,v in witness.source_paths.items()} == frozen_paths
              and witness.source_fingerprints == frozen_expected, 'post_projection_provenance_changed')
        final_guard = _frame_guard(budget, checkpoint, force=True)
        receipt.update(schema='validated-strict-frame-fitting-context-v2',
            trusted_producer_object_identity_verified=True, source_paths_rehashed=len(observed),
            measured_fresh_hash_IO_bytes=counter[0],
            caller_hash_IO_counter_delta=budget.io_bytes-hash_before,
            upstream_native_parser_IO_bytes=None, total_parent_IO_bytes=None,
            total_parent_IO_qualified=False, table_reparsed=False,
            initial_resource_guard=initial_guard, final_resource_guard=final_guard,
            native_matrix_content_identity_claim=False,
            source_authority='Exact trusted strict-flow objects plus fresh original file hashes, not SHA-string-only matrix authority.')
        return context, receipt
    except Exception as exc:
        if type(budget) is CallerBudget and budget._failure is None:
            budget._failure = exc
        # Counts only; no raw messages, private paths or labels are attached.
        try:
            exc.measured_fresh_hash_IO_bytes = counter[0]
            exc.upstream_native_parser_IO_bytes = None
        except Exception:
            pass
        raise
