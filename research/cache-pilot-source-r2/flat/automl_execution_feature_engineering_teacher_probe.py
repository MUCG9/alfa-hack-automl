"""Opt-in fitting-only teacher diagnostics; never a cache or training input."""
from copy import deepcopy
import hashlib
from importlib import metadata
import json
from pathlib import Path
import sys
import time
import uuid
import numpy as np
import pandas as pd
from automl_execution_feature_engineering_importance_cache import UncacheableInput, _array, _feed, library_identity, teacher_key
from automl_model_catboost import create_model
from automl_atomic import atomic_json

def json_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def source_digests(files):
    """Persist logical roles and bytes only, never machine paths."""
    return {role: hashlib.sha256(Path(path).read_bytes()).hexdigest() for role, path in sorted(files.items())}

def _digest(writer):
    hasher = hashlib.sha256()
    writer(hasher)
    return hasher.hexdigest()

def _metadata_digest(writer):
    try:
        return _digest(writer)
    except (UncacheableInput, UnicodeError, OverflowError):
        return None

def _schema(hasher, frame, categorical):
    _feed(hasher, (list(frame.columns), list(categorical)))
    for name in frame:
        col = frame[name]
        _feed(hasher, (name, str(col.dtype)))
        if isinstance(col.dtype, pd.CategoricalDtype):
            _feed(hasher, (col.cat.ordered, list(col.cat.categories)))

def _values(hasher, frame):
    for name in frame:
        _array(hasher, frame[name].to_numpy())

def _target(hasher, target):
    _feed(hasher, (target.name, str(target.dtype), list(target.index.names)))
    _array(hasher, target.index.to_numpy())
    _array(hasher, target.to_numpy())

def _weights(hasher, weights):
    _feed(hasher, ('weights', None if weights is None else type(weights).__name__))
    if weights is not None:
        _array(hasher, weights)

class TeacherImportanceProbe:
    """Compact digests and flow records for one leaf; contains no fitting data."""

    def __init__(self, context=None, sources=None, libraries=None, maximum_requests=64):
        if type(maximum_requests) is not int or not 1 <= maximum_requests <= 64:
            raise ValueError('Teacher probe request bound must be from 1 to 64')
        self.identity = uuid.uuid4().hex
        self.maximum_requests = maximum_requests
        self.context = deepcopy(context or {})
        self.libraries = deepcopy(libraries) if libraries is not None else library_identity()
        self.sources = source_digests(dict(sources or {}, teacher_probe=__file__, teacher_key=teacher_key.__code__.co_filename, teacher_adapter=create_model.__code__.co_filename))
        self.runtime_versions = {}
        for name in ['lightgbm', 'scikit-learn', 'scipy', 'threadpoolctl']:
            try:
                self.runtime_versions[name] = metadata.version(name)
            except metadata.PackageNotFoundError:
                self.runtime_versions[name] = None
        self.context_sha256 = json_digest(self.context)
        self.records, self.origins = ([], {})

    def begin(self, **context):
        tick = time.monotonic()
        scope = context['selection'].get('fitting_scope')
        if type(scope) is not str or not scope:
            raise ValueError('Enabled teacher probe requires an explicit fitting scope')
        if len(self.records) >= self.maximum_requests:
            raise ValueError('Teacher probe request bound exceeded')
        frame, target = (context['fitting_x'], context['fitting_y'])
        if len(frame.columns) > 4096:
            raise ValueError('Teacher probe column bound exceeded')
        record = {'request': len(self.records), 'leaf_identity': self.identity, 'scope': scope, 'fitting_rows': len(context['rows']), 'input_columns': len(frame.columns), 'key_sha256': None, 'context_sha256': self.context_sha256, 'components': {}, 'status': 'cacheable'}
        try:
            record['key_sha256'] = teacher_key(**context, libraries=self.libraries)

            def index(h):
                _feed(h, (type(frame.index).__name__, list(frame.index.names)))
                _array(h, frame.index.to_numpy())

            def settings(h):
                _feed(h, (context['teacher_recipe'], context['kind'], context['threads'], 100, list(context['categorical']), context['selection'], self.libraries))
            record['components'] = {'rows': _digest(lambda h: _array(h, context['rows'])), 'X_index': _digest(index), 'X_schema': _digest(lambda h: _schema(h, frame, context['categorical'])), 'X_values': _digest(lambda h: _values(h, frame)), 'y': _digest(lambda h: _target(h, target)), 'weights': _digest(lambda h: _weights(h, context['weights'])), 'teacher_settings': _digest(settings), 'context': self.context_sha256, 'source': json_digest(self.sources), 'libraries': json_digest(self.libraries)}
        except (UncacheableInput, UnicodeError, OverflowError) as exc:
            record.update(status='uncacheable', reason=type(exc).__name__, key_sha256=None, components={})
        record['common_probe_digest_seconds'] = time.monotonic() - tick
        return record

    def finish(self, record, importance, columns, selected, ranked, teacher_params, timings, cache_record=None, cache=None, selector_started=None):
        tick = time.monotonic()
        values = np.asarray(importance, dtype=float)
        record['importance_sha256'] = _digest(lambda h: _array(h, np.asarray(importance, dtype=float)))
        record['importance'] = values.tolist()
        try:
            record['columns'] = json.loads(json.dumps(list(columns), ensure_ascii=False, allow_nan=False))
            record['selected_columns'] = json.loads(json.dumps(list(selected), ensure_ascii=False, allow_nan=False))
            record['column_metadata_status'] = 'serializable'
        except (TypeError, ValueError, UnicodeError):
            record['columns'], record['selected_columns'] = (None, None)
            record['column_metadata_status'] = 'unsupported_JSON_metadata'
        record['columns_sha256'] = _metadata_digest(lambda h: _feed(h, list(columns)))
        record['selected_columns_sha256'] = _metadata_digest(lambda h: _feed(h, list(selected)))
        record['ranked_indices_sha256'] = _digest(lambda h: _array(h, ranked))
        record['importance_length'] = len(importance)
        record['importance_finite'] = bool(np.isfinite(importance).all())
        record['timings_seconds'] = dict(timings)
        cache_key = None if cache_record is None else cache_record.get('key_sha256')
        if cache_key is not None and record['key_sha256'] != cache_key:
            raise ValueError('Common teacher probe and cache keys disagree')
        cache_status = 'disabled' if cache_record is None else cache_record['status']
        record['cache_status'] = cache_status
        record['teacher_invoked'] = cache_status != 'hit'
        column_metadata = tuple(columns)
        key = record['key_sha256']
        limit_bytes = 262144 if cache is None else cache.maximum_bytes
        size, reason = (None, 'uncacheable_key' if key is None else None)
        if key is not None:
            try:
                encoded_columns = json.dumps(column_metadata, ensure_ascii=False, allow_nan=False).encode('utf-8')
                size = values.nbytes + sys.getsizeof(values) + sys.getsizeof(column_metadata) + sum((sys.getsizeof(name) for name in column_metadata)) + sys.getsizeof(key) + len(encoded_columns) + 256
                if size > limit_bytes:
                    reason = 'payload_exceeds_maximum_bytes'
            except (TypeError, ValueError, UnicodeError):
                reason = 'unsupported_JSON_column_metadata'
        if cache_record is not None and cache_status == 'bypass':
            reason = 'cache_lookup_bypass'
        record['candidate_payload_conservative_bytes'] = size
        record['store_eligibility'] = {'eligible_if_enabled': reason is None, 'reason': 'eligible' if reason is None else reason, 'maximum_bytes': limit_bytes, 'candidate_payload_conservative_bytes': size}
        params = None
        if teacher_params is not None:
            try:
                encoded = json.dumps(teacher_params, sort_keys=True, allow_nan=False)
                if len(encoded.encode('utf-8')) <= 32768:
                    params = json.loads(encoded)
            except (TypeError, ValueError):
                pass
        if cache_status == 'hit':
            if cache_key not in self.origins:
                raise ValueError('Teacher probe hit has no same-leaf source miss')
            origin = self.origins[cache_key]
            record['source_miss_request'] = origin
            record['effective_teacher_params_sha256'] = self.records[origin]['effective_teacher_params_sha256']
        else:
            record['source_miss_request'] = None
            record['effective_teacher_params'] = params
            record['effective_teacher_params_sha256'] = None if params is None else json_digest(params)
        record['effective_teacher_params_status'] = 'available' if record['effective_teacher_params_sha256'] is not None else 'unavailable_not_certified'
        if cache is not None:
            record['cache_trace'] = {'cache_identity': cache.identity, 'stored': bool((cache_record or {}).get('stored', False)), 'resident_keys_lru': list(cache.entries), 'resident_payload_bytes_lru': {key: entry[2] for key, entry in cache.entries.items()}, 'snapshot': cache.snapshot()}
            if cache_record.get('stored'):
                self.origins[cache_key] = record['request']
        else:
            record['cache_trace'] = None
        self.records.append(deepcopy(record))
        finish_seconds = time.monotonic() - tick
        selector_seconds = None if selector_started is None else time.monotonic() - selector_started
        for target in [record, self.records[-1]]:
            target['timings_seconds']['common_probe_finish'] = finish_seconds
            if selector_seconds is not None:
                target['timings_seconds']['whole_selector_through_probe'] = selector_seconds
        return record

    def snapshot(self):
        return {'leaf_identity': self.identity, 'maximum_requests': self.maximum_requests, 'context': deepcopy(self.context), 'context_sha256': self.context_sha256, 'source_modules_sha256': dict(self.sources), 'libraries': deepcopy(self.libraries), 'runtime_versions': dict(self.runtime_versions), 'requests': deepcopy(self.records), 'scope': 'One leaf only; diagnostic digests never supply cache key or fitting data'}

    def write_receipt(self, path):
        tick = time.monotonic()
        atomic_json(path, self.snapshot())
        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        return {'path': str(path), 'sha256': digest, 'common_receipt_IO_seconds': time.monotonic() - tick, 'leaf_identity': self.identity, 'requests': len(self.records)}
