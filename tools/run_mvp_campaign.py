"""Run the explicit four-stage MVP on copied tasks, sequentially within3hours.

Development coordinator only. Loads the captain-authorized private env file;
never included in the contest ZIP. No submission or account/browser operation.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tools'))
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.processes import wait_owned
from automl.task_understanding.api import discover
from benchmark_hpo import digest
from build_submission import build_files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks', nargs='+', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--private-env', type=Path, default=ROOT/'.env')
    parser.add_argument('--time-budget', type=int, default=10800)
    parser.add_argument('--top-k', type=int, default=32)
    parser.add_argument('--hpo-trials', type=int, default=8)
    args = parser.parse_args()
    if not 180 <= args.time_budget <= 10800 or not 1 <= args.top_k <= 512 or not 1 <= args.hpo_trials <= 32:
        parser.error('Invalid MVP limits')
    output = args.output.resolve()
    if not output.is_relative_to((ROOT/'test-runs').resolve()):
        parser.error('Campaign artifacts must remain in ignored test-runs/')
    from dotenv import load_dotenv
    load_dotenv(args.private_env, override=False)
    if not all(os.environ.get(k) for k in ['OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_MODEL']):
        raise ValueError('Private coordinator API environment is missing')
    if os.environ['OPENAI_BASE_URL'].rstrip('/') != 'https://changellenge.up.railway.app/v1':
        raise ValueError('Use the authorized organizer endpoint')
    with zipfile.ZipFile(args.archive) as packed:
        if len(packed.namelist()) != len(set(packed.namelist())):
            raise ValueError('Duplicate archive entry')
        files = {n: packed.read(n) for n in packed.namelist()}
    if files != build_files():
        raise ValueError('Campaign archive differs from current source')
    output.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    deadline = start+args.time_budget
    report = {'scope': 'Exploratory four-stage complete MVP; reused public validation, not private/official score',
              'archive_sha256': digest(args.archive), 'time_budget': args.time_budget,
              'feature_selection_top_k': args.top_k, 'hpo_trials': args.hpo_trials,
              'source_sha256': {n: hashlib.sha256(v).hexdigest() for n, v in files.items()},
              'tasks': [], 'status': 'running'}
    receipt = output/'campaign.json'
    atomic_json(receipt, report)
    env = os.environ.copy()
    env.update(AUTOML_THREADS='2', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2',
               MKL_NUM_THREADS='2', NUMEXPR_NUM_THREADS='2', PYTHONIOENCODING='utf-8')

    def interrupted(signum, frame):
        raise SystemExit(128+signum)
    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        for index, task in enumerate(args.tasks):
            remaining = deadline-time.monotonic()
            if remaining < 180:
                break
            spec, *_ = discover(task)
            original = {'task': digest(task), **{n: digest(p) for n, p in spec['paths'].items()}}
            directory = output/f'task-{index:02d}'
            directory.mkdir()
            for name, payload in files.items():
                (directory/name).write_bytes(payload)
            (directory/'task.md').write_bytes(task.read_bytes())
            for path in spec['paths'].values():
                source = Path(path)
                target = directory/source.relative_to(Path(spec['root']))
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            seconds = max(120, min(9900, int(deadline-time.monotonic()-30)))
            command = [sys.executable, '-u', 'solution.py', 'task.md', '--time-budget', str(seconds),
                       '--max-experiments', '14', '--max-planner-calls', '2', '--max-llm-calls', '4',
                       '--hpo-trials', str(args.hpo_trials), '--hpo-budget', '900',
                       '--feature-selection-top-k', str(args.top_k), '--planner-mode', 'staged',
                       '--run-name', 'mvp-four-stage']
            env.update(MPLCONFIGDIR=str(directory/'mpl'), TMPDIR=str(directory/'tmp'))
            (directory/'tmp').mkdir()
            print(json.dumps({'event': 'task_started', 'kind': spec['kind'], 'index': index,
                              'budget_seconds': seconds}), flush=True)
            tick = time.monotonic()
            with (directory/'process.log').open('w') as log:
                process = subprocess.Popen(command, cwd=directory, env=env, stdout=log,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                try:
                    status = wait_owned(process, min(seconds+20, max(1, deadline-time.monotonic())),
                                        memory_bytes=2*2**30)
                except subprocess.TimeoutExpired:
                    status = 'watchdog_timeout'
                except MemoryError:
                    status = 'memory_limit'
            path = directory/'automl_runs/mvp-four-stage/report.json'
            result = json.loads(path.read_text()) if path.exists() else {}
            observed = {'task': digest(task), **{n: digest(p) for n, p in spec['paths'].items()}}
            metrics = result.get('best_validation')
            search = (result.get('ensemble') or {}).get('primary', {}).get('metrics')
            confirmation = (result.get('ensemble') or {}).get('confirmation', {}).get('metrics')
            if not confirmation and result.get('selection'):
                chosen = result['selection'][0]['recipe']
                primary = next((r for r in result.get('experiments', []) if r['recipe'] == chosen), {})
                secondary = next((r for r in result.get('confirmations', []) if r['recipe'] == chosen), {})
                search, confirmation = primary.get('metrics'), secondary.get('metrics')
            row = {'index': index, 'kind': spec['kind'], 'exit_code': status,
                   'seconds': round(time.monotonic()-tick, 3), 'report_path': str(path),
                   'input_sha256': original, 'original_inputs_unchanged': original == observed,
                   'final_fit_status': result.get('final_fit_status'),
                   'integrity_ok': result.get('integrity_ok'), 'search': search,
                   'confirmation': confirmation, 'best_validation': metrics,
                   'hpo_status': (result.get('hpo') or {}).get('status'),
                   'llm_calls': result.get('llm_calls'),
                   'submission_sha256': result.get('submission_sha256'),
                   'complete': status == 0 and result.get('final_fit_status') == 'ok' and
                               result.get('integrity_ok') and original == observed}
            report['tasks'].append(row)
            atomic_json(receipt, report)
            print(json.dumps({'event': 'task_finished', **row}), flush=True)
        report.update(status='completed' if len(report['tasks']) == len(args.tasks) and
                      all(r['complete'] for r in report['tasks']) else 'incomplete',
                      seconds=round(time.monotonic()-start, 3),
                      source_unchanged=files == build_files())
        atomic_json(receipt, report)
    finally:
        signal.signal(signal.SIGTERM, previous)
    if report['status'] != 'completed' or not report['source_unchanged']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
