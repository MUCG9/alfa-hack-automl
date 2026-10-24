"""Read verified bytes and align frozen predictions; never fit a model."""
from dataclasses import dataclass
import csv
import hashlib
import io
from pathlib import Path
import time
import zipfile
import numpy as np
import pandas as pd
import psutil
from automl_contracts_error_analysis import ErrorAnalysisProtocol
from automl_contracts_messages import canonical_hash
from automl_evaluation_api import evaluate
from automl_infrastructure_observation_time import observation_values

class AnalysisLimit(RuntimeError):
    pass

class Guard:
    """Cooperative limits, plus pre-allocation bounds on artifact bytes."""

    def __init__(self, budget):
        self.deadline = time.monotonic() + budget.max_seconds
        self.max_bytes = budget.max_memory_mb * 2 ** 20
        self.process = psutil.Process()
        self.verified = {}

    def check(self):
        if time.monotonic() >= self.deadline:
            raise AnalysisLimit('Analysis deadline exceeded')
        if self.process.memory_info().rss > self.max_bytes:
            raise AnalysisLimit('Analysis process memory budget exceeded')

    def read(self, path, expected):
        self.check()
        path = Path(path).resolve(strict=True)
        if not path.is_file() or path.stat().st_size > self.max_bytes // 3:
            raise AnalysisLimit('Input artifact is not a bounded regular file')
        digest = hashlib.sha256()
        content = bytearray()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                self.check()
                content.extend(block)
                if len(content) > self.max_bytes // 3:
                    raise AnalysisLimit('Input artifact grew beyond byte budget')
                digest.update(block)
        if digest.hexdigest() != expected:
            raise ValueError('Artifact content SHA256 mismatch: ' + path.name)
        old = self.verified.setdefault(path, expected)
        if old != expected:
            raise ValueError('Conflicting artifact references')
        return bytes(content)

    def verify_unchanged(self):
        for path, expected in list(self.verified.items()):
            self.read(path, expected)

def sha_rows(rows):
    return hashlib.sha256(np.asarray(rows, dtype='<i8').tobytes()).hexdigest()

def positions(values, count):
    values = np.asarray(values)
    if values.ndim != 1 or values.dtype.kind not in 'iu' or (not len(values)):
        raise ValueError('Expected nonempty integer row positions')
    if np.any(values >= count) or np.any(values < 0) or len(np.unique(values)) != len(values):
        raise ValueError('Invalid, duplicate or out-of-range row positions')
    return values.astype(np.int64)

def table(content, target=None):
    text = content.decode('utf-8-sig')
    header = text.splitlines()[0]
    try:
        delimiter = csv.Sniffer().sniff(header, delimiters=',;\t|').delimiter
    except csv.Error:
        delimiter = ','
    columns = next(csv.reader([header], delimiter=delimiter))
    if not columns or len(columns) != len(set(columns)):
        raise ValueError('Duplicate/empty table header')
    frame = pd.read_csv(io.BytesIO(content), sep=delimiter, encoding='utf-8-sig')
    if target is not None:
        frame[target] = pd.read_csv(io.BytesIO(content), sep=delimiter, usecols=[target], dtype=str, keep_default_na=False)[target]
    return frame

def npz(content, guard):
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        if sum((i.file_size for i in archive.infolist())) > guard.max_bytes // 3:
            raise AnalysisLimit('Expanded NPZ exceeds byte budget')
        if len(archive.namelist()) != len(set(archive.namelist())):
            raise ValueError('Duplicate NPZ members')
    return np.load(io.BytesIO(content), allow_pickle=False)

def finite(value):
    if isinstance(value, dict):
        return {str(k): finite(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [finite(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value

def score(task, truth, predicted, probabilities=None, classes=()):
    return finite(evaluate(truth, predicted, task.kind, task.metric, probabilities, list(classes) if classes else None))

@dataclass
class LoadedPrediction:
    model_id: str
    fold_id: str
    training: np.ndarray
    rows: np.ndarray
    truth: np.ndarray
    predicted: np.ndarray
    probabilities: np.ndarray | None
    classes: tuple
    probability_kind: str
    metrics: dict

@dataclass
class AnalysisData:
    request: object
    protocol: object
    dataset: pd.DataFrame
    groups: np.ndarray
    times: np.ndarray | None
    predictions: dict
    alignment: dict

def _metadata(ref, guard, count):
    frame = table(guard.read(ref.path, ref.sha256), target='value')
    if list(frame.columns) != ['row_position', 'value'] or len(frame) != count:
        raise ValueError('Metadata must contain row_position,value for all original rows')
    if not np.array_equal(positions(frame.row_position.to_numpy(), count), np.arange(count)):
        raise ValueError('Metadata row order mismatch')
    if (frame.value.str.strip() == '').any():
        raise ValueError('Missing group/time metadata')
    return frame.value

def load(request, guard):
    protocol = ErrorAnalysisProtocol.from_json(guard.read(request.protocol.path, request.protocol.sha256))
    if protocol.protocol_id != request.protocol_id:
        raise ValueError('Protocol identity mismatch')
    for ref in protocol.evidence:
        guard.read(ref.path, ref.sha256)
    dataset = table(guard.read(request.dataset.path, request.dataset.sha256), target=request.task.target)
    if len(dataset) != request.dataset.rows or set(request.task.features) - set(dataset):
        raise ValueError('Dataset row count or feature schema mismatch')
    if request.task.kind == 'regression':
        truth = pd.to_numeric(dataset[request.task.target], errors='raise').to_numpy(dtype=float)
        if not np.isfinite(truth).all():
            raise ValueError('Regression targets must be finite')
        dataset[request.task.target] = truth
    else:
        truth = dataset[request.task.target].to_numpy(dtype=str)
        if any((not t.strip() for t in truth)):
            raise ValueError('Empty target label')
    requested = set(protocol.numeric_features) | set(protocol.categorical_features)
    requested.update((c for group in protocol.context_groups for c in group))
    if protocol.period_column:
        requested.add(protocol.period_column)
    if requested - set(request.task.features):
        raise ValueError('Slice columns must be declared input features')
    groups = _metadata(request.groups, guard, len(dataset)).to_numpy() if request.groups else pd.util.hash_pandas_object(dataset[list(request.task.features)], index=False).to_numpy()
    times = None
    if request.observation_time:
        times = observation_values(_metadata(request.observation_time, guard, len(dataset)))[0].to_numpy()
    elif protocol.period_column:
        times = observation_values(dataset[protocol.period_column])[0].to_numpy()
    if request.prediction_scope == 'forward' and times is None:
        raise ValueError('Forward diagnostics require observation time')
    loaded = {}
    canonical_classes = request.predictions[0].predictions.classes
    model_ids = {p.model_id for p in request.predictions}
    if any((set(b.models) - model_ids or b.name in model_ids for b in protocol.blends)):
        raise ValueError('Blend references unknown models or collides with model identity')
    for ref in request.predictions:
        guard.check()
        with npz(guard.read(ref.split.path, ref.split.sha256), guard) as split:
            if set(split.files) != {'train', 'validation'}:
                raise ValueError('Unexpected split fields')
            training = positions(split['train'], len(dataset))
            rows = positions(split['validation'], len(dataset))
        signature = hashlib.sha256(training.astype('<i8').tobytes() + rows.astype('<i8').tobytes()).hexdigest()
        if signature != ref.predictions.split_sha256 or sha_rows(rows) != ref.row_positions_sha256:
            raise ValueError('Split/row-order fingerprint mismatch')
        if np.intersect1d(training, rows).size:
            raise ValueError('Fitting and validation rows overlap')
        if protocol.require_group_disjoint and np.intersect1d(groups[training], groups[rows]).size:
            raise ValueError('Fitting and validation groups overlap')
        if request.prediction_scope == 'forward' and (not np.max(times[training]) < np.min(times[rows])):
            raise ValueError('Forward split contains present/future fitting rows')
        frame = table(guard.read(ref.predictions.path, ref.predictions_sha256), target='y_true')
        if tuple(frame.columns) != ref.predictions.columns or set(frame) != {'row_position', 'y_true', 'y_pred'}:
            raise ValueError('Unexpected prediction CSV columns')
        if len(frame) != ref.predictions.rows or not np.array_equal(positions(frame.row_position.to_numpy(), len(dataset)), rows):
            raise ValueError('Prediction row count/order differs from split')
        expected = truth[rows]
        if request.task.kind == 'classification':
            frame_pred = table(guard.read(ref.predictions.path, ref.predictions_sha256), target='y_pred')
            predicted = frame_pred.y_pred.to_numpy(dtype=str)
            actual = frame.y_true.to_numpy(dtype=str)
            if set(ref.predictions.classes) != set(canonical_classes) or not set(truth).issubset(canonical_classes):
                raise ValueError('Declared class set mismatch')
            if not set(predicted).issubset(canonical_classes):
                raise ValueError('Unknown predicted class')
        else:
            actual = pd.to_numeric(frame.y_true, errors='raise').to_numpy(dtype=float)
            predicted = pd.to_numeric(frame.y_pred, errors='raise').to_numpy(dtype=float)
            if not np.isfinite(predicted).all():
                raise ValueError('Nonfinite regression prediction')
        if not np.array_equal(actual, expected):
            raise ValueError('Prediction truth differs from original dataset')
        probabilities = None
        if ref.probabilities:
            with npz(guard.read(ref.probabilities.path, ref.probabilities.sha256), guard) as stored:
                if set(stored.files) != {'row_position', 'classes', 'probabilities'}:
                    raise ValueError('Unexpected probability fields')
                stored_classes = tuple(stored['classes'].astype(str))
                probabilities = np.asarray(stored['probabilities'], dtype=float)
                if not np.array_equal(stored['row_position'], rows) or stored_classes != ref.predictions.classes:
                    raise ValueError('Probability row/class order mismatch')
            if probabilities.shape != (len(rows), len(stored_classes)) or not np.isfinite(probabilities).all():
                raise ValueError('Invalid probability shape or values')
            if np.any(probabilities < 0) or np.any(probabilities > 1) or (not np.allclose(probabilities.sum(axis=1), 1, atol=1e-06, rtol=0)):
                raise ValueError('Invalid probability mass')
            if not np.array_equal(np.asarray(stored_classes)[probabilities.argmax(axis=1)], predicted):
                raise ValueError('Probability decisions disagree with CSV predictions')
            probabilities = probabilities[:, [stored_classes.index(c) for c in canonical_classes]]
        metrics = score(request.task, expected, predicted, probabilities, canonical_classes)
        if ref.recorded_result is None:
            raise ValueError('A recorded result is required for metric/recipe verification')
        import json
        result = json.loads(guard.read(ref.recorded_result.path, ref.recorded_result.sha256))
        if result.get('status') != 'ok' or result.get('full_fit') is not False:
            raise ValueError('Expected successful held-out result, not full-fit predictions')
        if canonical_hash(result.get('recipe')) != ref.recipe_sha256:
            raise ValueError('Recorded recipe fingerprint mismatch')
        recorded = result.get('metrics', {}).get(request.task.metric)
        if type(recorded) not in (int, float) or not np.isfinite(recorded) or (not np.isclose(metrics[request.task.metric], recorded, rtol=1e-08, atol=1e-10)):
            raise ValueError('Recomputed primary metric differs from recorded result')
        loaded[ref.model_id, ref.fold_id] = LoadedPrediction(ref.model_id, ref.fold_id, training, rows, expected, predicted, probabilities, canonical_classes, ref.probability_kind, metrics)
        guard.check()
    folds = {p.fold_id for p in loaded.values()}
    reference = {}
    for fold in folds:
        control = loaded.get((request.control_model_id, fold))
        if control is None:
            raise ValueError('Control missing on a fold')
        reference[fold] = control
        for model in model_ids:
            value = loaded.get((model, fold))
            if value is None or not np.array_equal(value.training, control.training) or (not np.array_equal(value.rows, control.rows)):
                raise ValueError('Models do not share the same fitting/validation folds')
    coverage = np.zeros(len(dataset), dtype=int)
    for value in reference.values():
        coverage[value.rows] += 1
    if request.prediction_scope == 'oof' and (not np.all(coverage == 1)):
        raise ValueError('OOF requires complete exactly-once original-row coverage')
    alignment = {'models': sorted(model_ids), 'folds': sorted(folds), 'original_rows': len(dataset), 'oof_coverage': 'exactly_once' if request.prediction_scope == 'oof' else 'not_oof', 'validation_rows_counted_with_repetitions': int(coverage.sum()), 'repeated_validation_rows': int((coverage > 1).sum()), 'independence_unit': 'declared_group' if request.groups else 'full_feature_hash', 'verified_artifacts': len(guard.verified), 'recorded_metrics_verified': True}
    return AnalysisData(request, protocol, dataset, groups, times, loaded, alignment)
