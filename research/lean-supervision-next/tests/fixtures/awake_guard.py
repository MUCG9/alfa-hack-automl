"""Per-process Windows idle/PLM requests; no global power-policy mutation.

API success proves request acceptance, not immunity to forced sleep. Requests
can be terminated by user sleep or policy. Call heartbeat() in the supervisor;
it records scheduling gaps and never grants extra experiment time.
"""
import ctypes
from ctypes import wintypes
import os
import time


class _Detailed(ctypes.Structure):
    _fields_ = [('module', wintypes.HMODULE), ('reason_id', wintypes.ULONG),
                ('count', wintypes.ULONG), ('strings', ctypes.POINTER(wintypes.LPWSTR))]


class _Reason(ctypes.Union):
    _fields_ = [('detailed', _Detailed), ('simple', wintypes.LPWSTR)]


class _Context(ctypes.Structure):
    _fields_ = [('version', wintypes.ULONG), ('flags', wintypes.DWORD), ('reason', _Reason)]


class PowerRequestGuard:
    """One enter/exit lifecycle; failure to acquire both requests blocks entry."""
    TYPES = [(1, 'SystemRequired'), (3, 'ExecutionRequired')]

    def __init__(self, reason, gap_threshold_seconds=10.):
        if not isinstance(reason, str) or not reason or '\x00' in reason:
            raise ValueError('A nonempty reason without NUL is required')
        if not 0 < gap_threshold_seconds < float('inf'):
            raise ValueError('A finite positive heartbeat threshold is required')
        self.reason, self.threshold = reason, float(gap_threshold_seconds)
        self.handle, self.active, self.entered = None, [], False
        self.previous, self.largest_gap = None, 0.
        self.record = dict(owner_pid=os.getpid(), reason=reason, acquire_results=[],
            clear_results=[], handle_closed=None, requested_types=[n for _, n in self.TYPES],
            API_acquisition_verified=False, continuous_effectiveness_verified=False,
            forced_sleep_prevention_claimed=False, global_policy_changed=False)

    def __enter__(self):
        if self.entered:
            raise RuntimeError('PowerRequestGuard cannot be reused')
        self.entered = True
        if os.name != 'nt':
            raise OSError('Windows power request APIs are required')
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.PowerCreateRequest.argtypes = [ctypes.POINTER(_Context)]
        self.kernel.PowerCreateRequest.restype = wintypes.HANDLE
        for name in ['PowerSetRequest', 'PowerClearRequest']:
            f = getattr(self.kernel, name)
            f.argtypes, f.restype = [wintypes.HANDLE, ctypes.c_int], wintypes.BOOL
        self.kernel.CloseHandle.argtypes, self.kernel.CloseHandle.restype = [wintypes.HANDLE], wintypes.BOOL
        self.buffer = ctypes.create_unicode_buffer(self.reason)
        self.context = _Context(version=0, flags=1)
        self.context.reason.simple = ctypes.cast(self.buffer, wintypes.LPWSTR)
        ctypes.set_last_error(0)
        self.handle = self.kernel.PowerCreateRequest(ctypes.byref(self.context))
        if self.handle in (None, ctypes.c_void_p(-1).value):
            self.handle = None
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            for code, name in self.TYPES:
                ctypes.set_last_error(0)
                ok = bool(self.kernel.PowerSetRequest(self.handle, code))
                error = ctypes.get_last_error() if not ok else 0
                self.record['acquire_results'].append(dict(type=name, accepted=ok, winerror=error))
                if not ok:
                    raise ctypes.WinError(error)
                self.active.append((code, name))
            self.record.update(API_acquisition_verified=True, acquired_unix=time.time())
            self.heartbeat()
            return self
        except BaseException:
            self.close(raise_on_failure=False)
            raise

    def heartbeat(self):
        if self.handle is None or len(self.active) != 2:
            raise RuntimeError('The process power-request context is not active')
        wall, mono = time.time(), time.monotonic()
        previous = self.previous or (wall, mono)
        dw, dm = wall-previous[0], mono-previous[1]
        self.largest_gap = max(self.largest_gap, dw, dm)
        sample = dict(unix=wall, monotonic=mono, wall_gap_seconds=dw,
            monotonic_gap_seconds=dm, wall_minus_monotonic_gap_seconds=dw-dm,
            scheduling_gap_exceeded=max(dw, dm) > self.threshold,
            largest_observed_gap_seconds=self.largest_gap,
            threshold_seconds=self.threshold, request_still_effective=None,
            deadline_extension_granted=False)
        self.previous = wall, mono
        self.record['last_heartbeat'] = sample
        return sample

    def close(self, raise_on_failure=True):
        if self.handle is None:
            return
        errors = []
        for code, name in reversed(self.active):
            ctypes.set_last_error(0)
            ok = bool(self.kernel.PowerClearRequest(self.handle, code))
            error = ctypes.get_last_error() if not ok else 0
            self.record['clear_results'].append(dict(type=name, cleared=ok, winerror=error))
            if not ok:
                errors.append(error)
        self.active.clear()
        ctypes.set_last_error(0)
        ok = bool(self.kernel.CloseHandle(self.handle))
        error = ctypes.get_last_error() if not ok else 0
        self.record.update(handle_closed=ok, close_winerror=error, released_unix=time.time())
        self.handle = None
        if not ok:
            errors.append(error)
        self.record['release_API_verified'] = not errors
        if errors and raise_on_failure:
            raise ctypes.WinError(errors[0])

    def __exit__(self, kind, value, traceback):
        self.close(raise_on_failure=kind is None)
        return False
