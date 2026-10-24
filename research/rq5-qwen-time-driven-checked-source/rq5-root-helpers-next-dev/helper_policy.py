"""Pure pin/window/publication rules for the RQ4 metadata helpers only."""
from pathlib import Path
import json
import math
import os

ROLE_FLAGS = ('post_tool_confirmed', 'technical_procedure_passed', 'source_unchanged',
              'current_temporary_absent', 'current_cleanup_confirmed',
              'inside_original6000', 'inside_saved_driver_final240',
              'inside_actual_closer_birth60')


def need(value, code):
    if not value:
        raise RuntimeError(code)


def bind_pin(pins, path, observed_sha256, *, allowed_new):
    """An existing frozen value can never be replaced by a newly observed one."""
    path = str(Path(path).resolve())
    if path in pins:
        need(pins[path] == observed_sha256, 'immutable_pin_collision')
    else:
        need(allowed_new.get(path) == observed_sha256, 'unapproved_new_pin')
        pins[path] = observed_sha256
    return dict(path=path, sha256=observed_sha256)


def exact_union(original, later):
    need(all(later.get(path) == value for path, value in original.items()),
         'original_frozen_pin_missing_or_rebound')
    return dict(later)


def window(state, now_unix, now_monotonic, *, reserve=0, begin=None, closer_birth=None):
    values = [state[k] for k in ('start_unix', 'start_monotonic',
              'absolute_deadline_unix', 'common_deadline_monotonic', 'final_deadline_monotonic')]
    need(all(type(v) in (int, float) and math.isfinite(v) for v in values + [now_unix, now_monotonic]),
         'finite_inherited_clock_required')
    start, initial, wall, end, final = values
    need(wall == start + 6000 and end == initial + 6000, 'original6000_assignment_required')
    need(initial <= now_monotonic and start <= now_unix and final <= end - 60,
         'original_origin_and_saved_final_required')
    need(abs((now_unix - start) - (now_monotonic - initial)) <= 5,
         'original_wall_monotonic_disagreement')
    need(now_monotonic + reserve < min(end, final)
         and now_unix + reserve < min(wall, start + final - initial),
         'original_common_final_reserve_expired')
    if begin is not None:
        need(type(begin) in (int, float) and math.isfinite(begin)
             and begin <= now_monotonic < begin + 30, 'posttool_observer30_expired')
    if closer_birth is not None:
        need(type(closer_birth) in (int, float) and math.isfinite(closer_birth)
             and now_unix < closer_birth + 60, 'actual_closer_birth60_expired')


def revoked(value, error):
    answer = dict(value)
    for key in ROLE_FLAGS:
        answer[key] = False
    for key in ('metrics', 'quality_metric', 'qualified_ML_metrics'):
        answer[key] = None
    if 'readiness' in answer:
        answer['readiness'] = 'NOT_READY'
        answer['missing_bindings'] = list(answer.get('missing_bindings', [])) + ['terminal_helper_failure']
    answer.update(helper_failed=True, primary_exception_type=type(error).__name__,
                  secondary_exception_type=getattr(error, 'helper_secondary_exception_type', None))
    return answer


def publish_checked(value, write, check):
    """Revoke this helper's own output if any post-publication check fails."""
    try:
        check()
        write(value, True)
        check()
    except BaseException as primary:
        negative = revoked(value, primary)
        try:
            write(negative, False)
        except BaseException as secondary:
            # A storage failure can also prevent revocation. Never report success:
            # the original exception/exit1 remains authoritative and records the
            # secondary type without exposing exception text or changing root.
            try:
                primary.helper_secondary_exception_type = type(secondary).__name__
            except BaseException:
                pass
        raise


def save_json(path, value, exclusive):
    path = Path(path)
    if exclusive:
        need(not path.exists(), 'exclusive_new_helper_output_required')
    pending = path.with_name(path.name + '.pending')
    with pending.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(pending, path)
