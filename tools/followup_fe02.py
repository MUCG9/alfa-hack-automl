"""Wait for the owned overnight queue, then run only the predeclared FE-02 pair."""
from copy import deepcopy
from pathlib import Path
import argparse
import fcntl
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
import psutil
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.processes import wait_owned
from automl.evaluation.api import choose_validation
from automl.search.policy import portfolio
from automl.task_understanding.api import discover
from overnight_research import identity_alive, source_hashes
from protected_selection_worker import ENGINE
from summarize_research import summarize_candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--after-identity', type=Path, required=True)
    parser.add_argument('--after-queue', type=Path, required=True)
    parser.add_argument('--task', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-seconds', type=int, default=21600)
    args = parser.parse_args()
    if not 3600 <= args.max_seconds <= 28800:
        parser.error('Bound the wait+screen to3600..28800s')
    output = args.output.resolve()
    if not output.is_relative_to((ROOT/'test-runs').resolve()):
        parser.error('Use an ignored test-runs output')
    output.mkdir(parents=True, exist_ok=False)
    predecessor = json.loads(args.after_identity.read_text())
    members = {(predecessor['pid'], predecessor['create_time']): predecessor}
    source = source_hashes()
    extension = ROOT/'tools/protected_selection_worker.py'
    extension_sha = hashlib.sha256(extension.read_bytes()).hexdigest()
    benchmark = ROOT/'tools/benchmark_candidates.py'
    benchmark_sha = hashlib.sha256(benchmark.read_bytes()).hexdigest()
    started = time.monotonic()
    deadline = started+args.max_seconds
    report = {'status': 'waiting_for_overnight',
              'identity': {'pid': os.getpid(), 'create_time': psutil.Process().create_time()},
              'source_sha256': source, 'extension_sha256': extension_sha,
              'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'benchmark_sha256': benchmark_sha,
              'maximum_seconds': args.max_seconds, 'fit_cap_seconds': 3600,
              'scope': 'FE-02 developer screen only; no source integration or publication'}
    path = output/'followup.json'
    lock = None
    def interrupted(signum, frame):
        raise SystemExit(128+signum)
    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        while any(identity_alive(member) for member in members.values()):
            if identity_alive(predecessor):
                try:
                    for child in psutil.Process(predecessor['pid']).children(recursive=True):
                        identity = {'pid': child.pid, 'create_time': child.create_time()}
                        members[(identity['pid'], identity['create_time'])] = identity
                except psutil.NoSuchProcess:
                    pass
            if deadline-time.monotonic() < 2460:
                report['status'] = 'budget_exhausted_waiting'
                return
            atomic_json(path, report)
            time.sleep(5)
        prior = json.loads(args.after_queue.read_text())
        report['predecessor_status'] = prior['status']
        if (prior['status'] not in {'completed', 'completed_with_failures', 'budget_exhausted'}
                or not prior['source_unchanged'] or prior['source_sha256'] != source):
            report['status'] = 'predecessor_not_qualified_to_continue'
            return
        if deadline-time.monotonic() < 2460:
            report['status'] = 'budget_exhausted'
            return
        lock = (ROOT/'test-runs/.owned-research.lock').open('a+')
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            report['status'] = 'training_lock_busy'
            return
        lock.seek(0)
        lock.truncate()
        json.dump(report['identity'], lock)
        lock.flush()
        if (source_hashes() != source or hashlib.sha256(extension.read_bytes()).hexdigest() != extension_sha
                or hashlib.sha256(benchmark.read_bytes()).hexdigest() != benchmark_sha):
            report['status'] = 'frozen_source_changed'
            return
        spec, _, train, *_ = discover(args.task)
        spec = choose_validation(spec, train, 'auto')
        if spec['kind'] != 'classification' or spec['metric'] != 'macro_f1':
            raise ValueError('FE-02 requires MacroF1 classification')
        control = next(recipe for recipe in portfolio(spec) if recipe['params'].get('feature_views'))
        treatment = deepcopy(control)
        treatment['engine'] = ENGINE
        treatment['params']['feature_selection_top_k'] = 32
        candidates = [{'name': 'qualified-control', 'recipe': control},
                      {'name': 'union-original-top32', 'recipe': treatment}]
        atomic_json(output/'candidates.json', candidates)
        report['status'] = 'running'
        atomic_json(path, report)
        env = {k: v for k, v in os.environ.items() if not any(s in k.upper() for s in
               ['KEY', 'TOKEN', 'SECRET', 'PROXY', 'AUTH', 'PASSWORD', 'PASSWD'])}
        env.update(AUTOML_THREADS='2', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2',
                   MKL_NUM_THREADS='2', NUMEXPR_NUM_THREADS='2')
        command = [sys.executable, str(ROOT/'tools/benchmark_candidates.py'), '--task', str(args.task),
                   '--candidates', str(output/'candidates.json'), '--output', str(output/'benchmark'),
                   '--worker-extension', str(extension), '--seeds', '42', '43',
                   '--validation-strategy', 'auto', '--threads', '2', '--timeout', '600', '--memory-gb', '1.5']
        with (output/'benchmark.log').open('x') as log:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code = wait_owned(process, min(3600, max(1, deadline-time.monotonic()-30)), 2*2**30)
            except subprocess.TimeoutExpired:
                code = 'timeout'
            except MemoryError:
                code = 'memory_limit'
        report['exit_code'] = code
        if code == 0:
            verified = summarize_candidates(output/'benchmark/results.json')
            atomic_json(output/'verified.json', verified)
            outcome = verified['candidates']['union-original-top32']
            report.update(status='completed' if outcome['complete_verified_screen'] else 'incomplete',
                          measured_screen_gate_passed=outcome['measured_screen_gate_passed'])
        else:
            report['status'] = 'failed'
    except BaseException as exc:
        report.update(status='interrupted' if isinstance(exc, (SystemExit, KeyboardInterrupt)) else 'failed',
                      exception_type=type(exc).__name__)
        raise
    finally:
        report.update(seconds=round(time.monotonic()-started, 3), source_unchanged=source_hashes() == source)
        atomic_json(path, report)
        signal.signal(signal.SIGTERM, previous)
        if lock is not None:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
            lock.close()


if __name__ == '__main__':
    main()
