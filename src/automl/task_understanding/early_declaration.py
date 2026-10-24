"""Bounded explicit declarations before full table loading; no inferred roles.

The task file is data, not executable instructions. Only labelled scalar fields
below and an explicitly named feature/role dictionary are understood. Prose,
file basenames, target values and sample placeholders grant no authority.
This bootstrap resolves a declaration for IO02, not an objective or valid CSV.
"""
from dataclasses import dataclass
from pathlib import Path
import csv
import hashlib
import json
import re

from automl.task_understanding.early_output import DeclaredOutput


class EarlyDeclarationError(ValueError):
    """Invalid or over-budget declaration input; no guessed fallback follows."""


_CEILINGS = dict(max_task_bytes=65536, max_task_lines=4096,
                 max_line_bytes=4096, max_header_bytes=65536,
                 max_columns=4096, max_metadata_bytes=1048576,
                 max_metadata_rows=4096, max_metadata_columns=32,
                 max_field_bytes=4096)


@dataclass(frozen=True)
class DeclarationLimits:
    max_task_bytes: int = 65536
    max_task_lines: int = 4096
    max_line_bytes: int = 4096
    max_header_bytes: int = 65536
    max_columns: int = 4096
    max_metadata_bytes: int = 1048576
    max_metadata_rows: int = 4096
    max_metadata_columns: int = 32
    max_field_bytes: int = 4096

    def __post_init__(self):
        for name, maximum in _CEILINGS.items():
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError('Invalid declaration limit: ' + name)


@dataclass(frozen=True)
class EarlyDeclaration:
    status: str
    reason: str
    task_text: str
    paths: dict | None = None
    declaration: DeclaredOutput | None = None
    receipt: dict | None = None

    @property
    def ready_for_projection(self):
        return self.status == 'resolved' and self.declaration is not None


_FIELDS = {
    'train': ('train', 'train file', 'training file', 'train table', 'файл обучения'),
    'test': ('test', 'test file', 'test table', 'тестовый файл'),
    'sample_submission': ('sample submission', 'sample submission file',
                          'output template', 'шаблон ответа'),
    'dictionary': ('data dictionary', 'data dictionary file', 'dictionary file',
                   'словарь данных'),
    'target': ('target', 'target column', 'целевая переменная'),
    'targets': ('targets', 'target columns', 'целевые переменные'),
    'kind': ('task kind', 'task type', 'тип задачи'),
    'identifier': ('id column', 'identifier column', 'колонка идентификатора'),
    'id_policy': ('id policy', 'identifier policy', 'политика идентификатора'),
    'output_kind': ('output kind', 'prediction type', 'тип предсказания'),
    'output_columns': ('output columns', 'prediction columns', 'колонки ответа'),
    'positive_class': ('positive class', 'положительный класс'),
}
_KEYS = {alias: field for field, aliases in _FIELDS.items() for alias in aliases}
_KINDS = {'regression': 'regression', 'регрессия': 'regression',
          'classification': 'classification', 'классификация': 'classification',
          'binary': 'binary', 'binary classification': 'binary',
          'multiclass': 'multiclass', 'multiclass classification': 'multiclass'}


def _scalar(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "`'\"":
        value = value[1:-1]
    if not value or len(value.encode('utf-8')) > 512 or '\x00' in value:
        raise EarlyDeclarationError('invalid_declaration_value')
    return value


def _list(value):
    if not value.lstrip().startswith('['):
        return [_scalar(value)]
    try:
        values = json.loads(value)
    except (ValueError, TypeError, RecursionError) as exc:
        raise EarlyDeclarationError('invalid_declaration_list') from exc
    if (type(values) is not list or not 1 <= len(values) <= 16
            or any(type(v) is not str for v in values)):
        raise EarlyDeclarationError('invalid_declaration_list')
    values = [_scalar(v) for v in values]
    if len(set(values)) != len(values):
        raise EarlyDeclarationError('duplicate_declaration_list')
    return values


def bootstrap_early_declaration(task_path, *, checkpoint,
                                limits=DeclarationLimits()):
    """Read bounded task/role metadata and CSV headers only for IO02.

    Recognized fields are documented in ``_FIELDS``; file paths must be explicit
    task fields. ``ID policy: none`` is an explicit no-ID declaration; an absent
    ID field is unknown. A supplied dictionary uses feature/role columns with
    exact target/id roles. Its missing roles never trigger train-minus-test or
    sample/test intersection guesses. Checkpoint exceptions propagate; this
    module creates no clock and never publishes or loads feature/target rows.
    """
    if not callable(checkpoint) or type(limits) is not DeclarationLimits:
        raise ValueError('Caller checkpoint and typed limits required')
    checkpoint()
    task_path = Path(task_path)
    if task_path.is_symlink():
        raise EarlyDeclarationError('task_symlink')
    task_path = task_path.resolve()
    root = task_path.parent
    with task_path.open('rb') as stream:
        checkpoint()
        raw_text = stream.read(limits.max_task_bytes + 1)
    checkpoint()
    if len(raw_text) > limits.max_task_bytes:
        raise EarlyDeclarationError('task_text_bytes_bound')
    try:
        text = raw_text.decode('utf-8-sig')
    except UnicodeError as exc:
        raise EarlyDeclarationError('invalid_task_UTF8') from exc
    lines = text.splitlines()
    if len(lines) > limits.max_task_lines:
        raise EarlyDeclarationError('task_line_count_bound')
    declarations = {}
    fence = None
    for line in lines:
        checkpoint()
        if len(line.encode('utf-8')) > limits.max_line_bytes:
            raise EarlyDeclarationError('task_line_bytes_bound')
        stripped = line.lstrip()
        if stripped.startswith(('```', '~~~')):
            marker = stripped[:3]
            fence = None if marker == fence else marker if fence is None else fence
            continue
        if fence is not None:
            continue
        match = re.fullmatch(r'\s*(?:[-*]\s+)?([^:=]{1,64})\s*[:=]\s*(.*?)\s*', line)
        if not match:
            continue
        key = re.sub(r'[\s_-]+', ' ', match[1].strip().strip('*').strip().lower())
        field = _KEYS.get(key)
        if field is not None:
            value = _list(match[2]) if field in ('targets', 'output_columns') else _scalar(match[2])
            declarations.setdefault(field, []).append(value)
    receipt = {'source': 'explicit_task_fields_and_optional_role_dictionary',
               'task_text_sha256': hashlib.sha256(raw_text).hexdigest(),
               'feature_rows_loaded': False, 'target_rows_loaded': False,
               'model_fits': 0, 'API_calls': 0, 'new_clock_created': False,
               'metric_resolution': 'deferred_to_IO02_strict_MetricSpec',
               'full_input_provenance_pending': True}

    def result(status, reason, paths=None, declaration=None):
        checkpoint()
        return EarlyDeclaration(status, reason, text, paths, declaration,
                                dict(receipt, declaration_status=status, reason=reason))

    if any(any(value != values[0] for value in values) for values in declarations.values()):
        return result('ambiguous', 'conflicting_explicit_task_fields')
    fields = {key: values[0] for key, values in declarations.items()}
    if any(role not in fields for role in ('train', 'test', 'sample_submission')):
        return result('unknown', 'explicit_file_roles_required')

    def local(value):
        checkpoint()
        relative = Path(value)
        if relative.is_absolute() or '\\' in value or ':' in value or '..' in relative.parts:
            raise EarlyDeclarationError('invalid_declared_relative_path')
        path = root / relative
        if path.is_symlink():
            raise EarlyDeclarationError('input_symlink')
        path = path.resolve()
        if not path.is_relative_to(root) or path.suffix.lower() not in ('.csv', '.tsv', '.tab'):
            raise EarlyDeclarationError('invalid_declared_table_path')
        if not path.is_file():
            raise EarlyDeclarationError('declared_table_missing')
        checkpoint()
        return path

    paths = {role: local(fields[role]) for role in ('train', 'test', 'sample_submission')}
    if len(set(paths.values())) != 3:
        return result('ambiguous', 'file_roles_not_distinct')

    def table(path, metadata=False):
        maximum = limits.max_metadata_bytes if metadata else limits.max_header_bytes
        seen_bytes = 0
        header_phase = True
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            checkpoint()
            first = stream.readline(min(maximum, limits.max_header_bytes) + 1)
            if len(first) > limits.max_header_bytes:
                raise EarlyDeclarationError('header_bytes_bound')

            def decoded_lines():
                nonlocal seen_bytes
                line = first
                initial = True
                while line:
                    checkpoint()
                    seen_bytes += len(line)
                    if seen_bytes > maximum:
                        raise EarlyDeclarationError('metadata_bytes_bound' if metadata else 'header_bytes_bound')
                    if header_phase and seen_bytes > limits.max_header_bytes:
                        raise EarlyDeclarationError('header_bytes_bound')
                    digest.update(line)
                    try:
                        yield line.decode('utf-8-sig' if initial else 'utf-8')
                    except UnicodeError as exc:
                        raise EarlyDeclarationError('invalid_CSV_UTF8') from exc
                    initial = False
                    line = stream.readline((min(maximum, limits.max_header_bytes)
                                            if header_phase else maximum) + 1)
                checkpoint()

            try:
                # Infer a delimiter from the header only; never sample data.
                probe = first.decode('utf-8-sig')
                if path.suffix.lower() in ('.tsv', '.tab'):
                    delimiter = '\t'
                else:
                    try:
                        delimiter = csv.Sniffer().sniff(probe, delimiters=',;\t|').delimiter
                    except csv.Error:
                        delimiter = ','
                reader = csv.reader(decoded_lines(), delimiter=delimiter, strict=True)
                header = next(reader)
                header_phase = False
                cap = limits.max_metadata_columns if metadata else limits.max_columns
                if (not header or len(header) > cap or len(set(header)) != len(header)
                        or any(not c or len(c.encode('utf-8')) > 256 for c in header)):
                    raise EarlyDeclarationError('invalid_CSV_header')
                if not metadata:
                    checkpoint()
                    return header, None, digest.hexdigest()
                normalized = [c.strip().lower() for c in header]
                if len(set(normalized)) != len(normalized) or not {'feature', 'role'} <= set(normalized):
                    raise EarlyDeclarationError('dictionary_feature_role_schema_required')
                feature_index, role_index = normalized.index('feature'), normalized.index('role')
                roles = {'target': [], 'id': []}
                for count, row in enumerate(reader, 1):
                    checkpoint()
                    if count > limits.max_metadata_rows:
                        raise EarlyDeclarationError('metadata_rows_bound')
                    if len(row) != len(header) or any(len(c.encode('utf-8')) > limits.max_field_bytes for c in row):
                        raise EarlyDeclarationError('invalid_dictionary_row')
                    role = row[role_index].strip().lower()
                    if role in roles:
                        name = row[feature_index]
                        if not name or len(name.encode('utf-8')) > 256:
                            raise EarlyDeclarationError('invalid_dictionary_role_name')
                        if name not in roles[role]:
                            roles[role].append(name)
                            if len(roles[role]) > 16:
                                raise EarlyDeclarationError('dictionary_role_count_bound')
                return header, roles, digest.hexdigest()
            except (StopIteration, csv.Error, UnicodeError) as exc:
                raise EarlyDeclarationError('invalid_CSV_metadata_or_header') from exc

    dictionary_roles = {'target': [], 'id': []}
    if 'dictionary' in fields:
        dictionary = local(fields['dictionary'])
        if dictionary in paths.values():
            return result('ambiguous', 'dictionary_reuses_input_table')
        _, dictionary_roles, dictionary_sha = table(dictionary, metadata=True)
        receipt['dictionary_path'] = dictionary.relative_to(root).as_posix()
        receipt['dictionary_metadata_sha256'] = dictionary_sha
    targets = fields.get('targets', [fields['target']] if 'target' in fields else [])
    if 'target' in fields and targets != [fields['target']]:
        return result('ambiguous', 'conflicting_target_fields')
    if len(targets) > 1 or len(dictionary_roles['target']) > 1:
        return result('multitarget', 'multiple_explicit_targets_not_implemented')
    if targets and dictionary_roles['target'] and targets != dictionary_roles['target']:
        return result('ambiguous', 'target_authority_conflict')
    targets = targets or dictionary_roles['target']
    if not targets:
        return result('unknown', 'explicit_target_required')
    target = targets[0]
    kind = _KINDS.get(fields.get('kind', '').lower())
    if kind is None:
        return result('unknown', 'explicit_supported_task_kind_required')
    identifiers = [fields['identifier']] if 'identifier' in fields else dictionary_roles['id']
    if len(dictionary_roles['id']) > 1 or (identifiers and dictionary_roles['id'] and identifiers != dictionary_roles['id']):
        return result('ambiguous', 'ID_authority_conflict')
    id_policy = fields.get('id_policy', 'column' if identifiers else 'unknown').lower()
    if id_policy not in ('none', 'column'):
        return result('unknown', 'explicit_ID_policy_required')
    if (id_policy == 'column') != bool(identifiers):
        return result('ambiguous', 'conflicting_ID_policy')
    identifier = identifiers[0] if identifiers else None
    if target == identifier:
        return result('ambiguous', 'target_ID_overlap')
    headers = {role: table(path)[0] for role, path in paths.items()}
    if target not in headers['train'] or target in headers['test']:
        return result('ambiguous', 'target_header_conflict')
    if identifier is not None and any(identifier not in headers[role] for role in ('test', 'sample_submission')):
        return result('ambiguous', 'ID_header_conflict')
    columns = [c for c in headers['sample_submission'] if c != identifier]
    if not columns:
        return result('unknown', 'output_columns_required')
    if 'output_columns' in fields and fields['output_columns'] != columns:
        return result('ambiguous', 'explicit_output_header_conflict')
    output_kind = fields.get('output_kind')
    if output_kind is not None and output_kind not in ('value', 'probability', 'probability_matrix'):
        return result('unknown', 'unsupported_explicit_output_kind')
    if kind == 'regression' and (len(columns) != 1 or output_kind not in (None, 'value')):
        return result('ambiguous', 'regression_output_header_conflict')
    if output_kind in ('value', 'probability') and len(columns) != 1:
        return result('ambiguous', 'scalar_output_header_conflict')
    positive = fields.get('positive_class')
    if kind == 'regression' and positive is not None:
        return result('ambiguous', 'positive_class_in_regression')
    if kind == 'multiclass' and output_kind == 'probability':
        return result('ambiguous', 'multiclass_requires_probability_matrix')
    if output_kind == 'probability' and positive is None:
        return result('unknown', 'explicit_positive_class_required')
    if any(len(v.encode('utf-8')) > 256 for v in (target, identifier, positive) if v is not None):
        raise EarlyDeclarationError('declared_column_or_class_bytes_bound')
    evidence = ('Explicit labelled task file roles; CSV headers validated',
                'Explicit task-kind field; no dtype/cardinality inference',
                'Explicit target and ID policy from task fields or role dictionary',
                'Sample output header validated; labels and placeholder cells unread')
    declaration = DeclaredOutput(target=target, kind=kind, id_policy=id_policy,
        identifier=identifier, output_kind=output_kind, positive_class=positive, evidence=evidence)
    relative_paths = {role: path.relative_to(root).as_posix() for role, path in paths.items()}
    receipt['header_sha256'] = {role: hashlib.sha256(json.dumps(header, ensure_ascii=False,
        separators=(',', ':')).encode('utf-8')).hexdigest() for role, header in headers.items()}
    receipt['output_contract_pending_IO02'] = True
    return result('resolved', 'explicit_declaration_ready_for_IO02', relative_paths, declaration)
