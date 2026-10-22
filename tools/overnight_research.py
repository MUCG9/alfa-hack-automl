"""Bounded sequential research queue. Wait for the owned MVP before any fits.

All artifacts stay ignored; no Git mutations, uploads, default promotion or GPU.
The coordinator owns every child and uses an exclusive host/project lock.
"""
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
from build_submission import build_files


def source_hashes():
    return {n: hashlib.sha256(v).hexdigest() for n, v in build_files().items()}


def identity_alive(identity):
    try:
        process = psutil.Process(identity['pid'])
        return process.create_time() == identity['create_time'] and process.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--after-campaign', type=Path, required=True)
    parser.add_argument('--after-identity', type=Path, required=True)
    parser.add_argument('--regression-task', type=Path, required=True)
    parser.add_argument('--classification-task', type=Path, required=True)
    parser.add_argument('--dsl-candidates', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-seconds', type=int, default=21600)
    args = parser.parse_args()
    if not 600 <= args.max_seconds <= 28800:
        parser.error('Use a bounded600..28800s queue')
    output = args.output.resolve()
    if not output.is_relative_to((ROOT/'test-runs').resolve()):
        parser.error('Research artifacts must stay in ignored test-runs/')
    output.mkdir(parents=True, exist_ok=False)
    lock_path = ROOT/'test-runs/.owned-research.lock'
    lock = lock_path.open('a+')
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('Another owned research queue holds the training lock')
    identity = {'pid': os.getpid(), 'create_time': psutil.Process().create_time()}
    lock.seek(0)
    lock.truncate()
    json.dump(identity, lock)
    lock.flush()
    started = time.monotonic()
    deadline = started+args.max_seconds
    initial = source_hashes()
    report = {'status': 'waiting_for_mvp', 'identity': identity, 'max_seconds': args.max_seconds,
              'source_sha256': initial, 'jobs': [], 'source_unchanged': True,
              'scope': 'Sequential predeclared component screens and matched Qwen prompts; no promotion/submission'}
    path = output/'queue.json'
    atomic_json(path, report)
    predecessor = json.loads(args.after_identity.read_text())
    predecessor_members = {(predecessor['pid'],predecessor['create_time']):predecessor}
    finished_kinds = []
    env = os.environ.copy()
    env.update(AUTOML_THREADS='2', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2',
               MKL_NUM_THREADS='2', NUMEXPR_NUM_THREADS='2', PYTHONIOENCODING='utf-8')
    for name in list(env):
        if any(s in name.upper() for s in ['KEY', 'TOKEN', 'SECRET', 'AUTH', 'PASSWORD', 'PROXY']):
            env.pop(name)

    def interrupted(signum, frame):
        raise SystemExit(128+signum)
    previous = signal.signal(signal.SIGTERM, interrupted)

    def invoke(name, script, arguments, cap, network=False):
        if deadline-time.monotonic() < 120:
            report['status'] = 'budget_exhausted'
            return False
        if source_hashes() != initial:
            report.update(status='source_changed', source_unchanged=False)
            raise RuntimeError('Canonical source changed during frozen research')
        child_env = env.copy()
        if network:
            from dotenv import dotenv_values
            private = dotenv_values(ROOT/'.env')
            for key in ['OPENAI_API_KEY', 'OPENAI_BASE_URL', 'OPENAI_MODEL']:
                if not private.get(key): raise ValueError('Missing private API configuration')
                child_env[key] = private[key]
        command = [sys.executable, str(ROOT/'tools'/script), *map(str, arguments)]
        tick = time.monotonic()
        entry = {'name': name, 'status': 'running', 'script': script,
                 'harness_sha256': hashlib.sha256((ROOT/'tools'/script).read_bytes()).hexdigest(),
                 'arguments': list(map(str, arguments))}
        report['jobs'].append(entry)
        report['status'] = 'running'
        atomic_json(path, report)
        print(json.dumps({'job': name, 'event': 'started'}), flush=True)
        with (output/(name+'.log')).open('x') as log:
            process = subprocess.Popen(command, cwd=ROOT, env=child_env, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                status = wait_owned(process, min(cap, max(1, deadline-time.monotonic()-30)),
                                    memory_bytes=2*2**30)
            except subprocess.TimeoutExpired:
                status = 'timeout'
            except MemoryError:
                status = 'memory_limit'
        entry.update(status='ok' if status == 0 else 'failed', exit_code=status,
                     seconds=round(time.monotonic()-tick, 3))
        report['source_unchanged'] = source_hashes() == initial
        atomic_json(path, report)
        print(json.dumps(entry), flush=True)
        if not report['source_unchanged']:
            raise RuntimeError('Canonical source changed during research')
        return status == 0

    try:
        while any(identity_alive(member) for member in predecessor_members.values()):
            if identity_alive(predecessor):
                try:
                    for child in psutil.Process(predecessor['pid']).children(recursive=True):
                        member={'pid':child.pid,'create_time':child.create_time()}
                        predecessor_members[(member['pid'],member['create_time'])]=member
                except psutil.NoSuchProcess: pass
            if time.monotonic() >= deadline:
                report['status'] = 'budget_exhausted_waiting'
                return
            time.sleep(5)
        predecessor_report = json.loads(args.after_campaign.read_text())
        report['mvp_predecessor_status'] = predecessor_report['status']
        atomic_json(path, report)
        invoke('mvp-summary', 'summarize_mvp.py', ['--campaign', args.after_campaign,
               '--output', output/'mvp-verified.json', '--allow-partial'], 120)
        for kind, task in [('regression', args.regression_task), ('classification', args.classification_task)]:
            if deadline-time.monotonic() < 600: break
            invoke(kind+'-feature-selection', 'benchmark_hpo.py', ['--task', task, '--output',
                output/(kind+'-feature-selection'), '--mode', 'selection', '--time-budget',
                min(3600, int(deadline-time.monotonic()-60))], 3660)
            if deadline-time.monotonic() < 600: break
            hpo_output = output/(kind+'-hpo')
            success = invoke(kind+'-hpo', 'benchmark_hpo.py', ['--task', task, '--output', hpo_output,
                '--trials', '8', '--study-seconds', '1800', '--time-budget',
                min(10800, int(deadline-time.monotonic()-60))], 10860)
            if kind == 'regression' and deadline-time.monotonic() > 600:
                invoke('har02-structured-regression', 'benchmark_candidates.py', ['--task', task,
                    '--candidates', args.dsl_candidates, '--output', output/'har02-regression',
                    '--time-backtests', '0', '1', '2', '--validation-strategy', 'auto',
                    '--threads', '2', '--timeout', '600', '--memory-gb', '1.5'], 3660)
            if success and deadline-time.monotonic() > 600:
                proposals = output/(kind+'-matched-prompts')
                generated = invoke(kind+'-prompt-proposals', 'compare_planners.py', ['--task', task,
                    '--screen', hpo_output/'results.json', '--output', proposals], 330, network=True)
                if generated:
                    for mode in ['baseline', 'staged']:
                        candidates = proposals/(mode+'-candidates.json')
                        if len(json.loads(candidates.read_text())) <= 1:
                            continue
                        arguments = ['--task', task, '--candidates', candidates, '--output',
                            output/(kind+'-prompt-'+mode), '--validation-strategy', 'auto',
                            '--threads', '2', '--timeout', '600', '--memory-gb', '1.5']
                        arguments += ['--time-backtests', '0', '1', '2'] if kind == 'regression' else ['--seeds', '42', '43']
                        invoke(kind+'-prompt-'+mode, 'benchmark_candidates.py', arguments, 5460)
            finished_kinds.append(kind)
        report['finished_task_kinds']=finished_kinds
        report['status'] = ('completed_with_failures' if any(j['status']=='failed' for j in report['jobs']) else 'completed') if len(finished_kinds)==2 else 'budget_exhausted'
    except BaseException as exc:
        report.update(status='interrupted' if isinstance(exc, (SystemExit, KeyboardInterrupt)) else 'failed',
                      exception_type=type(exc).__name__)
        raise
    finally:
        report.update(seconds=round(time.monotonic()-started, 3), source_unchanged=source_hashes() == initial)
        atomic_json(path, report)
        signal.signal(signal.SIGTERM, previous)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()


if __name__ == '__main__':
    main()
