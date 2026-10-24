"""Trusted cold-start fitting context; no gateway, parser, clock or model owner."""
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import struct

from automl.contracts.metrics import MetricSpec

VALIDATION_FIELDS = {'validation_strategy', 'time_column', 'group_column', 'validation_warning'}


class InitialFittingContextRejected(ValueError):
    pass


def need(value, code):
    if not value:
        raise InitialFittingContextRejected(code)


def canonical(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class InitialFittingAuthority:
    """Only the strict IO03 producer constructs this in the trusted CLI path."""
    producer_frame: object
    producer_spec: object
    producer_declaration: object
    producer_metric_spec: object
    producer_budget: object
    producer_checkpoint: object
    source_fingerprints: dict
    source_paths: dict
    _spec_sha: str = field(init=False, repr=False)
    _fingerprints_sha: str = field(init=False, repr=False)
    _paths_sha: str = field(init=False, repr=False)

    def __post_init__(self):
        need(type(self.producer_metric_spec) is MetricSpec, 'authoritative_MetricSpec_required')
        self.producer_metric_spec.require_resolved()
        need(bool(self.producer_checkpoint) and callable(self.producer_checkpoint), 'existing_strict_checkpoint_required')
        object.__setattr__(self, '_spec_sha', canonical(self.producer_spec))
        object.__setattr__(self, '_fingerprints_sha', canonical(self.source_fingerprints))
        object.__setattr__(self, '_paths_sha', canonical({k:str(v) for k,v in self.source_paths.items()}))

    def validate(self, spec, frame, budget, fingerprints):
        need(frame is self.producer_frame and budget is self.producer_budget,
             'same_strict_producer_frame_and_RunBudget_required')
        need(canonical(self.producer_spec) == self._spec_sha
             and canonical(self.source_fingerprints) == self._fingerprints_sha
             and canonical({k:str(v) for k,v in self.source_paths.items()}) == self._paths_sha,
             'strict_producer_authority_mutated')
        before = {k:v for k,v in self.producer_spec.items() if k not in VALIDATION_FIELDS}
        after = {k:v for k,v in spec.items() if k not in VALIDATION_FIELDS}
        need(before == after, 'only_existing_choose_validation_fields_may_differ')
        need(spec.get('strict_task_contract', {}).get('full_input_provenance_verified') is True
             and spec['strict_task_contract']['metric_spec'] == self.producer_metric_spec.to_dict(),
             'strict_resolved_metric_provenance_required')
        for label in self.source_paths:
            if label == 'task' or label.startswith('input:'):
                need(fingerprints.get(label) == self.source_fingerprints[label], 'strict_to_search_input_fingerprint_drift')


def dependencies():
    # Lazy ON-only package ports. Builder body remains exact reviewed48793;
    # extractor R2 owns trusted-frame/hash/native-scalar validation, no reparse.
    from automl.search.fitting_extractor import (CallerBudget, RoleAuthority, SplitInputAuthority,
        TrustedFrameWitness, prepare_validated_frame_context, _roles, _positions, MAX_ROWS)
    from automl.search.fitting_bounds import _json_text, bounded_messages
    from automl.search.fitting_context import preflight_gateway_messages
    from automl.infrastructure.run_budget import current_budget
    return SimpleNamespace(CallerBudget=CallerBudget, RoleAuthority=RoleAuthority,
        SplitInputAuthority=SplitInputAuthority, TrustedFrameWitness=TrustedFrameWitness,
        prepare=prepare_validated_frame_context, roles_sha=_roles, positions=_positions,
        bounds=SimpleNamespace(_json_text=_json_text, bounded_messages=bounded_messages),
        preflight=preflight_gateway_messages, current_budget=current_budget, MAX_ROWS=MAX_ROWS)


def original_positions(values, rows, budget):
    """Bound the real splitter array before converting native integers, no casts."""
    budget.check()
    need(1 <= len(values) < rows <= 200000, 'bounded_original_split_positions_required')
    if type(values).__module__ == 'numpy' and type(values).__name__ == 'ndarray':
        need(values.ndim == 1 and values.dtype.kind in ('i','u') and values.dtype.itemsize <= 8,
             'native_integer_split_array_required')
        values = values.tolist()
    need(type(values) in (list, tuple), 'ordered_native_original_positions_required')
    result = list(values)
    budget.check()
    return result


def split_digest(path, budget):
    path = Path(path)
    need(not path.is_symlink() and path.is_file() and path.stat().st_size <= 8*2**20,
         'bounded_saved_original_split_required')
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while True:
            budget.check()
            block = stream.read(65536)
            if not block:
                break
            budget.charge_io(len(block)); h.update(block)
    budget.check()
    return h.hexdigest()


@dataclass
class PreparedInitialFittingContext:
    context: dict
    receipt: dict
    _budget: object = field(repr=False)
    _dependencies: object = field(repr=False)
    _prompt: str = field(repr=False)

    def before_request(self, system_prompt):
        """Immediately before the unchanged real gateway, validate exact bytes."""
        need(system_prompt == self._prompt and set(self.context) == {'fitting_context'},
             'exact_SYSTEM_STAGED_and_fresh_context_only_required')
        context, proof = self._dependencies.preflight(system_prompt, self.context['fitting_context'],
            receipt=self.receipt['builder'], bounds=self._dependencies.bounds, budget=self._budget)
        need(context == self.context and proof['messages_sha256'] == self.receipt['gateway_preflight']['messages_sha256']
             and proof['messages_UTF8_bytes'] <= 65536 and self.receipt['builder']['packet_UTF8_bytes'] <= 8192,
             'fitting_packet_or_complete_message_changed_before_API')
        self._budget.check()


def prepare_initial_fitting_context(*, authority, spec, frame, fitting_positions, validation_positions,
                                    split_path, fingerprints, system_prompt, _dependencies=None):
    """Return ONLY the fresh builder context, never profile/split_info/feedback.

    Actual model/task JSON cannot create authority or select this entry point.
    The private dependencies argument is for bounded synthetic contract fixtures;
    the production runner always uses the exact lazy package imports above.
    """
    need(type(authority) is InitialFittingAuthority, 'live_strict_CLI_authority_required')
    d = dependencies() if _dependencies is None else _dependencies
    original = d.current_budget()
    authority.validate(spec, frame, original, fingerprints)
    metric = authority.producer_metric_spec
    need(spec['kind'] in ('regression','classification')
         and metric.name == spec['metric'] == ('rmse' if spec['kind'] == 'regression' else 'macro_f1'),
         'initial_fitting_context_supports_only_resolved_RMSE_or_MacroF1')
    budget = d.CallerBudget(original, authority.producer_checkpoint, io_bytes_already_charged=0)
    budget.check()
    need(2 <= len(frame) <= d.MAX_ROWS, 'bounded_original_training_frame_required')
    # Never coerce arbitrary bool/float/string indices or replace order by a set.
    fit = original_positions(fitting_positions, len(frame), budget)
    va = original_positions(validation_positions, len(frame), budget)
    fit_set, fit_sha = d.positions(fit, len(frame), budget, 'original_fitting_positions_required')
    va_set, va_sha = d.positions(va, len(frame), budget, 'original_validation_positions_required')
    need(fit_set.isdisjoint(va_set), 'fitting_validation_overlap')
    combined = hashlib.sha256()
    for rows in (fit, va):
        for index, row in enumerate(rows):
            if index % 256 == 0: budget.check()
            combined.update(struct.pack('<q', row))
    declarations = authority.producer_declaration
    identifiers = () if spec.get('id') is None else (spec['id'],)
    roles = d.RoleAuthority(features=tuple(spec['features']), target=spec['target'],
        identifiers=identifiers, kind=spec['kind'], metric=metric.name)
    role_sha = d.roles_sha(roles)
    protected = authority.source_fingerprints
    input_authority = d.SplitInputAuthority(source_rows=len(frame), train_sha256=protected['input:train'],
        task_sha256=protected['task'], dictionary_sha256=protected.get('input:data_dictionary'),
        split_file_sha256=split_digest(split_path, budget), ordered_fitting_int64le_sha256=fit_sha,
        ordered_validation_int64le_sha256=va_sha, combined_positions_int64le_sha256=combined.hexdigest())
    witness = d.TrustedFrameWitness(producer_frame=frame, producer_spec=spec,
        producer_declaration=declarations, producer_metric_spec=metric, producer_budget=original,
        producer_checkpoint=authority.producer_checkpoint, declaration_receipt=declarations.receipt,
        source_fingerprints=authority.source_fingerprints, source_paths=authority.source_paths)
    context, receipt = d.prepare(frame=frame, spec=spec, declaration=declarations, metric_spec=metric,
        witness=witness, roles=roles, expected_role_sha256=role_sha, authority=input_authority,
        fitting_positions=fit, validation_positions=va, split_path=split_path, system_prompt=system_prompt,
        bounds=d.bounds, budget=budget)
    need(type(context) is dict and set(context) == {'fitting_context'}, 'fresh_context_only_no_legacy_merge')
    receipt = dict(receipt, consumer_schema='initial-fitting-context-consumer-v1',
        initial_request_only=True, whole_feedback_fitting_only=False, legacy_context_merged=False,
        authoritative_metric_spec=metric.to_dict(), actual_input_role_paths_verified=True,
        derived_validation_spec_fields={k:spec[k] for k in VALIDATION_FIELDS if k in spec},
        source_spec_sha256=authority._spec_sha, current_spec_sha256=canonical(spec),
        actual_gateway_calls_from_preparation=0, API_credentials_or_attempt_semantics_changed=False)
    prepared = PreparedInitialFittingContext(context, receipt, budget, d, system_prompt)
    prepared.before_request(system_prompt)
    return prepared
