"""Opt-in, in-memory teacher importances for one leaf worker only.

Keys use the actual ordered fitting teacher input, not raw-data lineage or a
recipe signature. No frame, target, model, prediction or disk cache is retained.
"""
from collections import OrderedDict
import hashlib
from importlib import metadata
import json
import platform
import struct
import sys
import time
import uuid
import numpy as np
import pandas as pd

class UncacheableInput(TypeError):
    """A key cannot be represented exactly; retain ordinary fitting behavior."""

def _scalar(value):
    if isinstance(value, np.generic):
        value = value.item()
    if value is None:
        return b'n'
    if value is pd.NA:
        return b'a'
    if type(value) is bool:
        return b'b1' if value else b'b0'
    if type(value) is int:
        return b'i' + str(value).encode('ascii')
    if type(value) is float:
        return b'f' + struct.pack('!d', value)
    if type(value) is str:
        return b's' + value.encode('utf-8')
    if type(value) is bytes:
        return b'y' + value
    raise UncacheableInput('Unsupported exact scalar type')

def _feed(hasher, value):
    """Typed, length-delimited stream; no Python hash or 64-bit row shortcut."""
    if isinstance(value, dict):
        hasher.update(b'd' + struct.pack('!Q', len(value)))
        for key, item in value.items():
            _feed(hasher, key)
            _feed(hasher, item)
    elif isinstance(value, (list, tuple)):
        hasher.update((b'l' if isinstance(value, list) else b't') + struct.pack('!Q', len(value)))
        for item in value:
            _feed(hasher, item)
    else:
        encoded = _scalar(value)
        hasher.update(struct.pack('!Q', len(encoded)))
        hasher.update(encoded)

def _array(hasher, values):
    array = np.asarray(values)
    _feed(hasher, ('array', array.dtype.str, tuple(array.shape)))
    if array.dtype.hasobject:
        for value in array.flat:
            _feed(hasher, value)
    else:
        if array.dtype.kind not in 'biufcSU':
            raise UncacheableInput('Unsupported exact array dtype')
        contiguous = np.ascontiguousarray(array)
        hasher.update(memoryview(contiguous).cast('B'))

def library_identity():
    versions = {'python': platform.python_version(), 'implementation': platform.python_implementation()}
    for name in ['numpy', 'pandas', 'catboost']:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            raise UncacheableInput('Teacher library version unavailable') from None
    return versions

def teacher_key(fitting_x, fitting_y, rows, weights, teacher_recipe, kind, threads, categorical, selection, libraries):
    if not fitting_x.columns.is_unique:
        raise UncacheableInput('Teacher columns are not unique')
    h = hashlib.sha256()
    _feed(h, ('worker-teacher-importance-v1', teacher_recipe, kind, threads, 100, list(categorical), selection, libraries))
    _array(h, rows)
    _feed(h, (type(fitting_x.index).__name__, list(fitting_x.index.names)))
    _array(h, fitting_x.index.to_numpy())
    _feed(h, list(fitting_x.columns))
    for name in fitting_x:
        column = fitting_x[name]
        _feed(h, (name, str(column.dtype)))
        if isinstance(column.dtype, pd.CategoricalDtype):
            _feed(h, (column.cat.ordered, list(column.cat.categories)))
        _array(h, column.to_numpy())
    _feed(h, (fitting_y.name, str(fitting_y.dtype), list(fitting_y.index.names)))
    _array(h, fitting_y.index.to_numpy())
    _array(h, fitting_y.to_numpy())
    if weights is None:
        _feed(h, ('weights', None))
    else:
        _feed(h, ('weights', type(weights).__name__))
        _array(h, weights)
    return h.hexdigest()

class TeacherImportanceCache:
    """Bounded LRU. Construct a fresh instance inside each leaf worker run."""

    def __init__(self, enabled=False, maximum_entries=4, maximum_bytes=262144):
        if type(enabled) is not bool:
            raise ValueError('Teacher importance cache enabled must be a boolean')
        if type(maximum_entries) is not int or maximum_entries < 1 or type(maximum_bytes) is not int or (maximum_bytes < 1):
            raise ValueError('Teacher importance cache bounds must be positive integers')
        self.enabled, self.maximum_entries, self.maximum_bytes = (enabled, maximum_entries, maximum_bytes)
        self.identity = uuid.uuid4().hex
        self.entries, self.bytes = (OrderedDict(), 0)
        self.hits, self.misses, self.bypasses, self.evictions = (0, 0, 0, 0)
        self.libraries = None

    def lookup(self, **context):
        tick = time.monotonic()
        receipt = {'enabled': self.enabled, 'worker_cache_identity': self.identity, 'key_sha256': None, 'status': 'disabled'}
        if not self.enabled:
            return (None, None, receipt)
        try:
            if self.libraries is None:
                self.libraries = library_identity()
            key = teacher_key(**context, libraries=self.libraries)
        except (UncacheableInput, UnicodeError, OverflowError) as exc:
            self.bypasses += 1
            receipt.update(status='bypass', reason=type(exc).__name__, hash_seconds=time.monotonic() - tick)
            return (None, None, receipt)
        receipt.update(key_sha256=key, hash_seconds=time.monotonic() - tick)
        if key in self.entries:
            importance, columns, size = self.entries.pop(key)
            self.entries[key] = (importance, columns, size)
            self.hits += 1
            receipt['status'] = 'hit'
            return (key, importance.copy(), receipt)
        self.misses += 1
        receipt['status'] = 'miss'
        return (key, None, receipt)

    def store(self, key, columns, importance):
        if not self.enabled or key is None:
            return False
        values = np.asarray(importance, dtype=float)
        if values.shape != (len(columns),) or not np.isfinite(values).all():
            raise ValueError('Invalid cache importance')
        column_metadata = tuple(columns)
        try:
            encoded = json.dumps(column_metadata, ensure_ascii=False, allow_nan=False).encode('utf-8')
        except (TypeError, ValueError):
            self.bypasses += 1
            return False
        size = values.nbytes + sys.getsizeof(values) + sys.getsizeof(column_metadata) + sum((sys.getsizeof(name) for name in column_metadata)) + sys.getsizeof(key) + len(encoded) + 256
        if size > self.maximum_bytes:
            self.bypasses += 1
            return False
        if key in self.entries:
            self.bytes -= self.entries.pop(key)[2]
        while self.entries and (len(self.entries) >= self.maximum_entries or self.bytes + size > self.maximum_bytes):
            self.bytes -= self.entries.popitem(last=False)[1][2]
            self.evictions += 1
        self.entries[key] = (values.copy(), column_metadata, size)
        self.bytes += size
        return True

    def snapshot(self):
        return {'enabled': self.enabled, 'worker_cache_identity': self.identity, 'entries': len(self.entries), 'metadata_and_importance_bytes': self.bytes, 'maximum_entries': self.maximum_entries, 'maximum_bytes': self.maximum_bytes, 'hits': self.hits, 'misses': self.misses, 'bypasses': self.bypasses, 'evictions': self.evictions, 'scope': 'One leaf worker; no cross-worker/inner-outer-cut reuse'}
