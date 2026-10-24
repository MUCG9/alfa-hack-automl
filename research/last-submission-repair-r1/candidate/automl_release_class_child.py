"""Private owned child bootstrap. No numerical import before live delegation."""
import json
import math
import os
from pathlib import Path
import sys
import time


def main():
    task,directory,session,wall,mono,endwall,endmono=sys.argv[1:]
    task=Path(task).resolve();directory=Path(directory).resolve()
    values=tuple(map(float,(wall,mono,endwall,endmono)))
    if not all(math.isfinite(v) for v in values):raise ValueError('child_original_clock_nonfinite')
    import psutil
    from automl_atomic import atomic_json
    from automl_release_supervision import (bounded_json,DelegatedResourceAuthority,
        _DELEGATION,safe_failure)
    own=psutil.Process(os.getpid())
    atomic_json(directory/'hello.json',dict(schema='owned-class-child-hello-v1',
        session=session,child_identity=[own.pid,own.create_time()]))
    token=None;primary=None;secondary=[];receipt=None
    try:
        while not (directory/'authority.json').exists():
            if time.monotonic()>=values[3] or time.time()>=values[2]:
                raise RuntimeError('child_original_deadline_before_authority')
            time.sleep(.05)
        manifest=bounded_json(directory/'authority.json')
        if (manifest.get('session')!=session or manifest.get('start_unix')!=values[0]
                or manifest.get('start_monotonic')!=values[1]
                or manifest.get('execution_deadline_unix')!=values[2]
                or manifest.get('execution_deadline_monotonic')!=values[3]):
            raise RuntimeError('child_bootstrap_clock_or_nonce_changed')
        authority=DelegatedResourceAuthority(manifest,directory=directory)
        token=_DELEGATION.set(authority)
        # Heavy imports/native preparation are observed by the actual parent.
        from automl_v16_class_release import execute_class
        receipt=execute_class(task,authority)
        authority.check()
    except BaseException as error:
        primary=error
    finally:
        if token is not None:_DELEGATION.reset(token)
        diagnostic=dict(schema='owned-class-child-diagnostic-v1',session=session,
            child_identity=[own.pid,own.create_time()],status='failed' if primary else 'completed',
            first_failure=safe_failure(primary) if primary else None,secondary_failures=secondary,
            result=receipt,new_metric=None,API_calls=0)
        try:atomic_json(directory/'child-diagnostic.json',diagnostic)
        except BaseException as error:
            secondary.append(safe_failure(error))
            if primary is None:primary=error
        if primary:
            print(json.dumps(dict(status='failed',phase='class_child',first_failure=safe_failure(primary),
                secondary_failures=secondary)),flush=True)
    if primary:raise primary
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except BaseException as first:
        if isinstance(first,SystemExit) and first.code in (None,0):raise
        record=dict(schema='owned-class-child-early-failure-v1',status='failed',
            session=sys.argv[3] if len(sys.argv)>3 else None,
            first_failure=dict(type=type(first).__name__),secondary_failures=[])
        try:print(json.dumps(record),flush=True)
        except BaseException as secondary:
            try:first.release_secondary_types=[type(secondary).__name__]
            except BaseException:pass
        raise
