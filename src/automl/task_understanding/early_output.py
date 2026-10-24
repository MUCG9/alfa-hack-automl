"""Opt-in output projections before profiling; no discovery, models or API.

Roles are supplied by a trusted deterministic caller, never inferred from file
names, integer targets or sample placeholders. This helper does not publish a
CSV. Its resolved frames feed the existing C01 dummy_predictions/save_submission
boundary. A resolved *format* with an unresolved MetricSpec is format-only.
All work uses the mandatory caller checkpoint; this module creates no clock.
"""
from dataclasses import dataclass
from pathlib import Path
import csv
import hashlib
import json
import math
import sys

import pandas as pd

from automl.contracts.metrics import MetricSpec
from automl.task_understanding.metric_contract import resolve_metric_spec


class EarlyOutputError(ValueError):
    """Invalid input/resource bound; no publication or score is implied."""


@dataclass(frozen=True)
class ProjectionLimits:
    max_rows: int = 1000000
    max_columns: int = 4096
    max_header_bytes: int = 65536
    max_record_bytes: int = 1048576
    max_field_bytes: int = 65536
    max_text_bytes: int = 65536
    max_projection_bytes: int = 128 * 1024 * 1024
    max_prediction_bytes: int = 128 * 1024 * 1024
    max_source_bytes: int = 2 * 1024**3
    max_classes: int = 4096

    def __post_init__(self):
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= 2**63 - 1:
                raise ValueError('Invalid projection limit: ' + name)


@dataclass(frozen=True)
class DeclaredOutput:
    target: str | None = None
    kind: str | None = None
    id_policy: str = 'unknown'  # unknown, none, column
    identifier: str | None = None
    output_kind: str | None = None  # C01 value/probability/probability_matrix
    positive_class: str | None = None
    evidence: tuple[str, ...] = ()

    def __post_init__(self):
        for name in ('target', 'identifier', 'positive_class'):
            value = getattr(self, name)
            if value is not None and (type(value) is not str or not value
                                      or len(value) > 256 or len(value.encode('utf-8')) > 256):
                raise ValueError('Invalid declared ' + name)
        if self.kind not in (None, 'regression', 'classification', 'binary', 'multiclass'):
            raise ValueError('Invalid declared task kind')
        if self.id_policy not in ('unknown', 'none', 'column'):
            raise ValueError('Invalid ID policy')
        if self.output_kind not in (None, 'value', 'probability', 'probability_matrix'):
            raise ValueError('Invalid output kind')
        if (type(self.evidence) is not tuple or len(self.evidence) > 8
                or any(type(x) is not str or not x or len(x) > 256
                       or len(x.encode('utf-8')) > 256 for x in self.evidence)):
            raise ValueError('Invalid bounded declaration evidence')


@dataclass(frozen=True)
class EarlyOutputResult:
    status: str
    reason: str
    metric_spec: MetricSpec
    writer_spec: dict | None = None
    target_frame: pd.DataFrame | None = None
    sample: pd.DataFrame | None = None
    test_ids: pd.DataFrame | None = None
    receipt: dict | None = None

    @property
    def ready_for_publication(self):
        return self.status == 'resolved' and self.writer_spec is not None

    @property
    def objective_resolved(self):
        return self.ready_for_publication and self.metric_spec.status == 'resolved'


def _unknown(status, reason, declaration, metric=None):
    metric = metric or MetricSpec(None, None, None, 'unknown', 'early_output', (), reason)
    return EarlyOutputResult(status, reason, metric, receipt={
        'schema_status': status, 'reason': reason, 'metric': metric.to_dict(),
        'declaration_evidence': list(declaration.evidence),
        'ready_for_publication': False, 'model_fits': 0, 'API_calls': 0})


def prepare_early_output(root, paths, declaration, task_text, *, checkpoint,
                         limits=ProjectionLimits()):
    """Return a bounded C01-compatible context; no output file is written.

    ``paths`` has exactly train/test/sample_submission roles. Declaration
    evidence is caller provenance, not authenticated authority. Input paths
    must stay within root. CSV feature cells are parsed transiently to locate
    columns; only target/ID/sample projections are retained, never profiled.
    Limits bound records, retained representation and prospective predictions;
    they do not certify process peak RSS or time spent blocked inside the OS.
    """
    if (type(declaration) is not DeclaredOutput or type(limits) is not ProjectionLimits
            or not callable(checkpoint)):
        raise ValueError('Typed declaration/limits and caller checkpoint required')
    checkpoint()
    if (type(task_text) is not str or len(task_text) > limits.max_text_bytes
            or len(task_text.encode('utf-8')) > limits.max_text_bytes):
        raise EarlyOutputError('task_text_bound')
    if not declaration.target or not declaration.kind or declaration.id_policy == 'unknown' or not declaration.evidence:
        return _unknown('unknown', 'explicit_output_roles_required', declaration)
    if ((declaration.id_policy == 'column') != (declaration.identifier is not None)
            or declaration.target == declaration.identifier):
        return _unknown('ambiguous', 'conflicting_target_ID_roles', declaration)
    if type(paths) is not dict or set(paths) != {'train', 'test', 'sample_submission'}:
        return _unknown('unknown', 'explicit_file_roles_required', declaration)
    root = Path(root).resolve()
    resolved = {}
    for role, value in paths.items():
        checkpoint()
        path = Path(value)
        path = path if path.is_absolute() else root / path
        if path.is_symlink():
            raise EarlyOutputError('input_symlink')
        path = path.resolve()
        if not path.is_relative_to(root) or not path.is_file() or path.suffix.lower() not in ('.csv', '.tsv', '.tab'):
            raise EarlyOutputError('invalid_input_path')
        resolved[role] = path
    if len(set(resolved.values())) != 3:
        return _unknown('ambiguous', 'file_roles_not_distinct', declaration)
    used = {'source': 0, 'projection': 0}

    def bound(name, count, limit):
        checkpoint()
        used[name] += count
        if used[name] > limit:
            raise EarlyOutputError(name + '_bytes_bound')

    def project(path, wanted=None, header_only=False, class_target=False):
        checkpoint()
        if path.stat().st_size > limits.max_source_bytes:
            raise EarlyOutputError('source_file_bytes_bound')
        with path.open('r', encoding='utf-8-sig', newline='') as stream:
            probe = stream.read(min(8192, limits.max_header_bytes))
            bound('source', len(probe.encode('utf-8')), limits.max_source_bytes)
            if path.suffix.lower() in ('.tsv', '.tab'):
                delimiter = '\t'
            else:
                try:
                    delimiter = csv.Sniffer().sniff(probe, delimiters=',;\t|').delimiter
                except csv.Error:
                    try:
                        delimiter = csv.Sniffer().sniff(probe.splitlines()[0], delimiters=',;\t|').delimiter
                    except (csv.Error, IndexError):
                        delimiter = ','
            stream.seek(0)
            record_bytes = [0]
            header_phase = [True]

            def lines():
                while True:
                    checkpoint()
                    line = stream.readline(limits.max_record_bytes + 1)
                    if not line:
                        return
                    size = len(line.encode('utf-8'))
                    bound('source', size, limits.max_source_bytes)
                    record_bytes[0] += size
                    cap = limits.max_header_bytes if header_phase[0] else limits.max_record_bytes
                    if record_bytes[0] > cap:
                        raise EarlyOutputError('CSV_record_bytes_bound')
                    yield line

            reader = csv.reader(lines(), delimiter=delimiter, strict=True)
            try:
                header = next(reader)
                if (not header or len(header) > limits.max_columns or len(set(header)) != len(header)
                        or any(not c or len(c.encode('utf-8')) > 256 for c in header)):
                    raise EarlyOutputError('invalid_CSV_header')
                checkpoint()
                if header_only:
                    return header
                selected = list(header) if wanted is None else list(wanted)
                if any(c not in header for c in selected):
                    raise EarlyOutputError('declared_column_missing')
                indices = [header.index(c) for c in selected]
                values = {c: [] for c in selected}
                bound('projection', len(selected) * 256, limits.max_projection_bytes)
                count = 0
                hashed = hashlib.sha256()
                seen_classes = set()
                header_phase[0] = False
                record_bytes[0] = 0
                for row in reader:
                    record_bytes[0] = 0
                    checkpoint()
                    count += 1
                    if count > limits.max_rows:
                        raise EarlyOutputError('row_count_bound')
                    if len(row) != len(header):
                        raise EarlyOutputError('CSV_row_width_changed')
                    if any(len(value.encode('utf-8')) > limits.max_field_bytes for value in row):
                        raise EarlyOutputError('CSV_field_bytes_bound')
                    kept = [row[i] for i in indices]
                    if class_target:
                        if kept[0] == '':
                            raise EarlyOutputError('empty_class_label')
                        seen_classes.add(kept[0])
                        if len(seen_classes) > limits.max_classes:
                            raise EarlyOutputError('class_count_bound')
                    bound('projection', sum(sys.getsizeof(v) + 32 for v in kept), limits.max_projection_bytes)
                    for column, value in zip(selected, kept):
                        values[column].append(value)
                    hashed.update(json.dumps(kept, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
                    hashed.update(b'\n')
                checkpoint()
                return header, values, count, hashed.hexdigest()
            except (StopIteration, csv.Error, UnicodeError) as exc:
                raise EarlyOutputError('invalid_CSV') from exc

    headers = {role: project(path, header_only=True) for role, path in resolved.items()}
    target, identifier = declaration.target, declaration.identifier
    if target not in headers['train'] or target in headers['test']:
        return _unknown('ambiguous', 'target_role_schema_conflict', declaration)
    if identifier is not None and any(identifier not in headers[r] for r in ('test', 'sample_submission')):
        return _unknown('ambiguous', 'ID_role_schema_conflict', declaration)
    columns = [c for c in headers['sample_submission'] if c != identifier]
    if not columns:
        return _unknown('unknown', 'prediction_columns_missing', declaration)
    train_header, train_values, n_train, train_sha = project(resolved['train'], [target],
        class_target=declaration.kind != 'regression')
    if train_header != headers['train']:
        raise EarlyOutputError('input_schema_changed:train')
    test_header, test_values, n_test, test_sha = project(resolved['test'], [identifier] if identifier else [])
    if test_header != headers['test']:
        raise EarlyOutputError('input_schema_changed:test')
    sample_header, sample_values, n_sample, sample_sha = project(resolved['sample_submission'])
    if sample_header != headers['sample_submission']:
        raise EarlyOutputError('input_schema_changed:sample_submission')
    if not n_train or not n_test or n_sample != n_test:
        raise EarlyOutputError('empty_or_mismatched_row_counts')
    checkpoint()
    kind = 'regression' if declaration.kind == 'regression' else 'classification'
    target_frame = pd.DataFrame(train_values)
    if kind == 'regression':
        try:
            numbers = pd.to_numeric(target_frame[target], errors='raise')
        except (ValueError, TypeError) as exc:
            raise EarlyOutputError('invalid_numeric_target') from exc
        if not all(math.isfinite(float(v)) for v in numbers):
            raise EarlyOutputError('nonfinite_numeric_target')
        target_frame[target] = numbers
        classes = None
    else:
        if any(value == '' for value in train_values[target]):
            raise EarlyOutputError('empty_class_label')
        classes = sorted(set(train_values[target]))
        if len(classes) > limits.max_classes:
            raise EarlyOutputError('class_count_bound')
        if ((declaration.kind == 'binary' and len(classes) != 2)
                or (declaration.kind == 'multiclass' and len(classes) < 3)):
            return _unknown('ambiguous', 'declared_class_cardinality_conflict', declaration)
    metric = resolve_metric_spec(task_text, declaration.kind,
        class_count=len(classes) if classes is not None and len(classes) >= 2 else None)
    checkpoint()
    if metric.name == 'rmsle' and any(float(v) < 0 for v in target_frame[target]):
        raise EarlyOutputError('negative_RMSLE_target')
    output_kind = declaration.output_kind
    if output_kind is None:
        if kind == 'regression' and len(columns) == 1:
            output_kind = 'value'
        elif classes is not None and len(columns) > 1 and set(columns) == set(classes):
            output_kind = 'probability_matrix'
        elif metric.status == 'resolved' and len(columns) == 1:
            output_kind = 'value' if metric.prediction_kind == 'label' else 'probability'
        else:
            return _unknown('unknown', 'output_format_not_declared', declaration, metric)
    if kind == 'regression' and (output_kind != 'value' or len(columns) != 1):
        return _unknown('ambiguous', 'regression_output_schema_conflict', declaration, metric)
    if kind == 'classification':
        if output_kind == 'probability_matrix':
            if set(columns) != set(classes) or len(columns) != len(classes):
                return _unknown('ambiguous', 'class_probability_columns_conflict', declaration, metric)
        elif len(columns) != 1:
            return _unknown('ambiguous', 'scalar_output_columns_conflict', declaration, metric)
        if output_kind == 'probability' and (len(classes) != 2 or declaration.positive_class not in classes):
            return _unknown('unknown', 'explicit_positive_class_required', declaration, metric)
        if metric.status == 'resolved' and metric.prediction_kind in ('probability', 'probability_matrix') and output_kind == 'value':
            return _unknown('ambiguous', 'metric_requires_probability_output', declaration, metric)
    prediction_bytes = n_test * len(columns) * 8
    if kind == 'classification' and output_kind == 'value':
        # C01 np.repeat on a literal label may allocate a fixed-width Unicode
        # array, not one eight-byte object pointer per row.
        prediction_bytes = n_test * 4 * max(len(label) for label in classes)
    if prediction_bytes > limits.max_prediction_bytes:
        raise EarlyOutputError('prediction_bytes_bound')
    sample = pd.DataFrame(sample_values)
    test_ids = pd.DataFrame(test_values, index=range(n_test))
    positions = None
    if identifier is not None:
        bound('projection', n_test * 176, limits.max_projection_bytes)
        test_labels, sample_labels = test_values[identifier], sample_values[identifier]
        if (any(value == '' for values in (test_labels, sample_labels) for value in values)
                or len(set(test_labels)) != n_test or len(set(sample_labels)) != n_test):
            raise EarlyOutputError('missing_or_duplicate_IDs')
        index = {label: i for i, label in enumerate(test_labels)}
        if any(label not in index for label in sample_labels):
            raise EarlyOutputError('sample_test_IDs_not_bijection')
        order = [index[label] for label in sample_labels]
        if any(i != position for i, position in enumerate(order)):
            positions = order
    checkpoint()
    retained_bytes = 0
    for frame in (target_frame, sample, test_ids):
        checkpoint()
        retained_bytes += int(frame.memory_usage(index=True, deep=True).sum())
        if retained_bytes > limits.max_projection_bytes:
            raise EarlyOutputError('retained_frame_bytes_bound')
    writer = {'kind': kind, 'target': target, 'id': identifier, 'metric': metric.name,
              'greater_is_better': None if metric.direction is None else metric.direction == 'maximize',
              'prediction_type': output_kind, 'output_columns': columns, 'classes': classes}
    if positions is not None:
        writer['sample_test_positions'] = positions
    if output_kind == 'probability':
        writer['positive_class'] = declaration.positive_class
        writer['positive_class_source'] = 'explicit_declaration'
    receipt = {'schema_status': 'resolved', 'format_only': metric.status != 'resolved',
               'metric': metric.to_dict(), 'declaration_evidence': list(declaration.evidence),
               'row_counts': {'train': n_train, 'test': n_test, 'sample': n_sample},
               'projection_sha256': {'train': train_sha, 'test': test_sha, 'sample': sample_sha},
               'source_bytes_read': used['source'], 'projection_bytes_estimate': used['projection'],
               'retained_frame_bytes': retained_bytes, 'prediction_bytes_estimate': prediction_bytes,
               'input_roles': {r: p.relative_to(root).as_posix() for r, p in resolved.items()},
               'target_scope': 'entire_training_target_for_output_only_not_fitting_analysis',
               'feature_profiling': False, 'model_fits': 0, 'API_calls': 0,
               'full_input_provenance_pending': True, 'new_clock_created': False}
    checkpoint()
    return EarlyOutputResult('resolved', 'known_metric' if metric.status == 'resolved' else 'format_only_metric_unresolved',
                             metric, writer, target_frame, sample, test_ids, receipt)
