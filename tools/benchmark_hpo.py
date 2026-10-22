"""Nested HPO/feature-selection screens; sequential fits from frozen source bytes."""
from pathlib import Path
import argparse
from copy import deepcopy
import hashlib
import json
import os
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tools'))
import numpy as np

from automl.evaluation.api import choose_validation, make_split, make_time_split
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.processes import wait_owned
from automl.search.hpo import optimize_recipe
from automl.search.policy import portfolio
from automl.task_understanding.api import discover
from build_submission import build_files


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=['hpo', 'selection'], default='hpo')
    parser.add_argument('--trials', type=int, default=8)
    parser.add_argument('--study-seconds', type=int, default=1800)
    parser.add_argument('--time-budget', type=int, default=10800)
    parser.add_argument('--worker-seconds', type=int, default=600)
    parser.add_argument('--memory-mb', type=int, default=1536)
    parser.add_argument('--selection-top-k', type=int, default=32)
    parser.add_argument('--cuts', nargs='+', type=int)
    args = parser.parse_args()
    if not 1 <= args.trials <= 32 or not 5 <= args.time_budget <= 10800:
        parser.error('Invalid trial/time budget')
    if min(args.study_seconds, args.worker_seconds, args.memory_mb) < 1:
        parser.error('Resource limits must be positive')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output/'sources'
    source.mkdir()
    files = build_files()
    for name, content in files.items():
        (source/name).write_bytes(content)
    spec, profile, train, _, _, _, hashes = discover(args.task)
    spec = choose_validation(spec, train, 'auto')
    recipes = portfolio(spec)
    if spec['kind'] == 'classification':
        control = next(r for r in recipes if r['params'].get('feature_views'))
    else:
        control = next(r for r in recipes if r['params'].get('history_asof'))
    start = time.monotonic()
    deadline = start+args.time_budget
    report = {'scope': 'Nested component screen on reused public fitting data; not full-agent/private/official score',
              'mode': args.mode, 'control_recipe': control, 'spec': spec,
              'limits': vars(args) | {'task': str(args.task), 'output': str(output)},
              'source_sha256': {n: hashlib.sha256(b).hexdigest() for n, b in files.items()},
              'harness_sha256': {str(p): digest(p) for p in [Path(__file__), ROOT/'src/automl/search/hpo.py']},
              'input_sha256': {n: digest(p) for n, p in spec['paths'].items()},
              'task_sha256': digest(args.task), 'cuts': [], 'status': 'running'}
    path = output/'results.json'
    atomic_json(path, report)
    env = {k: v for k, v in os.environ.items()
           if not any(s in k.upper() for s in ['KEY', 'TOKEN', 'SECRET', 'PROXY', 'PASSWORD', 'AUTH'])}
    env.update(AUTOML_THREADS='2', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2',
               MKL_NUM_THREADS='2', NUMEXPR_NUM_THREADS='2')

    def worker(task_spec, recipe, directory, split, timeout):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=False)
        job = {'spec': task_spec, 'recipe': recipe, 'output_dir': str(directory),
               'split_path': str(split), 'threads': 2, 'full_fit': False}
        atomic_json(directory/'job.json', job)
        tick = time.monotonic()
        timeout = min(timeout, args.worker_seconds, deadline-time.monotonic())
        if timeout <= 0:
            return {'status': 'deadline', 'wall_seconds': 0}
        with (directory/'worker.log').open('w') as log:
            proc = subprocess.Popen([sys.executable, str(source/'automl_worker.py'), str(directory/'job.json')],
                                    env=env, cwd=spec['root'], stdout=log, stderr=subprocess.STDOUT,
                                    start_new_session=True)
            try:
                status = wait_owned(proc, timeout, args.memory_mb*2**20)
            except subprocess.TimeoutExpired:
                status = 'timeout'
            except MemoryError:
                status = 'memory_limit'
        result = directory/'result.json'
        record = json.loads(result.read_text()) if status == 0 and result.exists() else {'status': status or 'missing_result'}
        record.update(wall_seconds=round(time.monotonic()-tick, 3), directory=str(directory))
        return record

    def interrupted(signum, frame):
        raise SystemExit(128+signum)
    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        cuts = args.cuts or ([0, 1, 2] if spec.get('validation_strategy') == 'time' else [42, 43])
        for cut in cuts:
            if deadline-time.monotonic() < 5:
                break
            tr, va, info = (make_time_split(spec, train, offset=cut) if spec.get('validation_strategy') == 'time'
                            else make_split(spec, train, hashes, seed=cut))
            directory = output/f'cut-{cut}'
            directory.mkdir()
            split = directory/'outer-split.npz'
            np.savez(split, train=tr, validation=va)
            row = {'cut': cut, 'split': info, 'outcomes': {}}
            report['cuts'].append(row)
            selected = [('control', control)]
            if args.mode == 'hpo':
                for sampler in ['random', 'tpe']:
                    tuned, study = optimize_recipe(spec, train, hashes, tr, control,
                        directory/sampler, worker, min(deadline, time.monotonic()+args.study_seconds),
                        trials=args.trials, seed=137, sampler=sampler, worker_timeout=args.worker_seconds)
                    row[sampler] = study
                    selected.append((sampler, tuned))
                    atomic_json(path, report)
            else:
                candidate = deepcopy(control)
                candidate['params']['feature_selection_top_k'] = args.selection_top_k
                selected.append(('selection', candidate))
            for name, recipe in selected:
                if deadline-time.monotonic() < 5:
                    break
                result = worker(spec, recipe, directory/f'outer-{name}', split, args.worker_seconds)
                row['outcomes'][name] = result
                atomic_json(path, report)
                print(json.dumps({'cut': cut, 'name': name, 'status': result['status'],
                                  'metrics': result.get('metrics'), 'seconds': result['wall_seconds']}), flush=True)
        report.update(status='completed' if len(report['cuts']) == len(cuts) and
            all(len(c['outcomes']) == (3 if args.mode == 'hpo' else 2) for c in report['cuts']) else 'budget_exhausted',
            seconds=round(time.monotonic()-start, 3),
            inputs_unchanged=report['input_sha256'] == {n: digest(p) for n, p in spec['paths'].items()},
            source_unchanged=report['source_sha256'] == {n: hashlib.sha256(b).hexdigest() for n, b in build_files().items()})
        atomic_json(path, report)
    finally:
        signal.signal(signal.SIGTERM, previous)
    if report['status'] != 'completed' or not report['inputs_unchanged'] or not report['source_unchanged']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
