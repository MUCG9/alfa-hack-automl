"""Lightweight standard entry: retain fixed REG, supervise V16 CLASS offline."""
import argparse
import json
from pathlib import Path
import sys
from automl_release_authority import resolved_policy
from automl_release_supervision import safe_failure, supervise_class


def main(origin):
    try:
        parser=argparse.ArgumentParser()
        parser.add_argument('task',type=Path)
        parser.add_argument('--time-budget',type=int,default=9900)
        args=parser.parse_args()
        task=args.task.resolve()
        if not 30 <= args.time_budget <= 9900: raise ValueError('release_time_budget')
        kind,metric=resolved_policy(task.read_text(encoding='utf-8-sig'))
        if kind=='regression':
            # Exact fixed REG numerical procedure and original entry origin.
            from automl_fixed_release import execute
            return execute(task,seconds=args.time_budget,origin=origin)
        return supervise_class(task,origin,args.time_budget)
    except BaseException as first:
        if isinstance(first,SystemExit) and first.code in (None,0): raise
        diagnostic=dict(schema='release-early-failure-v1',status='failed',
            first_failure=safe_failure(first),secondary_failures=[],metric=None,API_calls=0)
        try: print(json.dumps(diagnostic),file=sys.stderr,flush=True)
        except BaseException as secondary:
            diagnostic['secondary_failures'].append(dict(type=type(secondary).__name__))
        raise
