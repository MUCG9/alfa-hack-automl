"""Run preregistered BLEND-01 CV only after the existing frozen jobs finish.

This coordinator refuses active predecessors or a busy lock. It does not wait,
change source, select new recipes, publish anything, or promote defaults.
"""
from pathlib import Path
import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.processes import wait_owned
from overnight_research import identity_alive, source_hashes
from verify_blend_cv import verify
from summarize_research import digest
import psutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    base = ROOT/'test-runs/qwen-optuna-20261022'
    if not args.output.resolve().is_relative_to((ROOT/'test-runs').resolve()):
        parser.error('Keep research artifacts in ignored test-runs/')
    initial = source_hashes()
    for identity_name, receipt_name in [
            ('overnight-identity.json', 'overnight-20261023/queue.json'),
            ('fe02-identity.json', 'fe02-20261023/followup.json')]:
        identity = json.loads((base/identity_name).read_text())
        if identity_alive(identity):
            raise SystemExit('Owned predecessor still active; no CV fit started')
        receipt = json.loads((base/receipt_name).read_text())
        if (receipt['status'] not in {'completed', 'completed_with_failures', 'incomplete', 'budget_exhausted'}
                or not receipt.get('source_unchanged') or receipt['source_sha256'] != initial):
            raise SystemExit('Predecessor receipt/source does not qualify continuation')
    if not json.loads((base/'blend01-attempt2-20261023/result.json').read_text())['measured_replay_gate_passed']:
        raise SystemExit('No positive fixed replay')
    with (ROOT/'test-runs/.owned-research.lock').open('a+') as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Training lock busy; no CV fit started')
        args.output.mkdir(parents=True, exist_ok=False)
        identity = {'pid': os.getpid(), 'create_time': psutil.Process().create_time()}
        lock.seek(0); lock.truncate(); json.dump(identity, lock); lock.flush()
        candidates = ROOT/'docs/experiments/blend01_candidates_20261023.json'
        report = {'status': 'running', 'identity': identity, 'source_sha256': initial,
                  'candidates_sha256': digest(candidates), 'maximum_seconds': 6000,
                  'worker_seconds': 900, 'memory_mib': 1536, 'threads': 2,
                  'maximum_workers': 6, 'scope': 'BLEND-01 grouped CV only; no integration/promotion/upload'}
        path = args.output/'coordinator.json'
        atomic_json(path, report)
        started = time.monotonic()
        def interrupted(signum, frame):
            raise SystemExit(128+signum)
        previous = signal.signal(signal.SIGTERM, interrupted)
        env = {k: v for k, v in os.environ.items() if not any(s in k.upper() for s in
               ['KEY', 'TOKEN', 'SECRET', 'PROXY', 'AUTH', 'PASSWORD'])}
        env.update(AUTOML_THREADS='2', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2',
                   MKL_NUM_THREADS='2', NUMEXPR_NUM_THREADS='2')
        command = [sys.executable, str(ROOT/'tools/benchmark_candidates.py'), '--task', str(args.task),
                   '--candidates', str(candidates), '--output', str(args.output/'benchmark'),
                   '--folds', '3', '--seeds', '42', '--validation-strategy', 'auto',
                   '--threads', '2', '--timeout', '900', '--memory-gb', '1.5']
        try:
            with (args.output/'benchmark.log').open('x') as log:
                process = subprocess.Popen(command, env=env, cwd=ROOT, stdin=subprocess.DEVNULL,
                                           stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                code = wait_owned(process, 5900, 2*2**30)
            report['exit_code'] = code
            if code == 0:
                summary = verify(args.output/'benchmark/results.json')
                atomic_json(args.output/'verified.json', summary)
                report.update(status='completed', measured_cv_gate_passed=summary['measured_cv_gate_passed'])
            else:
                report['status'] = 'failed'
        except BaseException as exc:
            report.update(status='interrupted' if isinstance(exc, (SystemExit, KeyboardInterrupt)) else 'failed',
                          exception_type=type(exc).__name__)
            raise
        finally:
            report.update(seconds=round(time.monotonic()-started, 3), source_unchanged=source_hashes() == initial)
            atomic_json(path, report)
            signal.signal(signal.SIGTERM, previous)
        if report['status'] != 'completed' or not report['source_unchanged']:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
