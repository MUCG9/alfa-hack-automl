"""Run PIPE-02 offline from the exact checked ZIP, with one owned training lock."""
from pathlib import Path
import argparse
import fcntl
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
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.processes import wait_owned
from automl.task_understanding.api import discover, load_inputs
from build_submission import build_files
from overnight_research import identity_alive
import psutil


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks', nargs=2, type=Path, required=True, help='Regression then classification')
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--source-gate', type=Path, required=True)
    parser.add_argument('--unpacked-gate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--time-budget', type=int, default=10800)
    args = parser.parse_args()
    if not 180 <= args.time_budget <= 10800:
        parser.error('Invalid common deadline')
    if not args.output.resolve().is_relative_to((ROOT/'test-runs').resolve()):
        parser.error('Artifacts must remain in ignored test-runs/')
    base = ROOT/'test-runs/qwen-optuna-20261022'
    for name in ['detached-blend01-cv.json', 'detached-reg-blend01-forward.json']:
        identity = json.loads((base/name).read_text())
        identity = identity.get('identity', identity)
        if identity_alive(identity):
            raise SystemExit('Qualification process is still active')
    reg = json.loads((base/'reg-blend01-forward-20261023/coordinator.json').read_text())
    cls = json.loads((base/'blend01-cv-20261023/coordinator.json').read_text())
    for receipt, permitted in [(reg, {'completed'}), (cls, {'completed', 'failed'})]:
        if receipt.get('status') not in permitted or not all(receipt.get(k) for k in
                ['source_unchanged', 'harness_unchanged', 'candidates_unchanged']):
            raise SystemExit('Qualification did not finish with frozen evidence')
    if not reg['measured_cv_gate_passed']:
        raise SystemExit('Regression procedure did not qualify')
    source_gate = json.loads(args.source_gate.read_text())
    unpacked = json.loads(args.unpacked_gate.read_text())
    files = build_files()
    fingerprints = {n: hashlib.sha256(b).hexdigest() for n, b in files.items()}
    if not source_gate.get('passed') or not source_gate.get('source_unchanged') or source_gate['source_sha256'] != fingerprints:
        raise SystemExit('Current source has no passing unchanged-source gate')
    if not unpacked.get('passed') or not unpacked.get('matches_current_source') or unpacked['sha256'] != digest(args.archive):
        raise SystemExit('Exact archive has no passing unpacked gate')
    with zipfile.ZipFile(args.archive) as archive:
        if len(archive.namelist()) != len(files) or {n: archive.read(n) for n in archive.namelist()} != files:
            raise SystemExit('Archive is not the checked current source')
    with (ROOT/'test-runs/.owned-research.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        args.output.mkdir(parents=True, exist_ok=False)
        identity = {'pid': os.getpid(), 'create_time': psutil.Process().create_time()}
        lock.seek(0); lock.truncate(); json.dump(identity, lock); lock.flush()
        started = time.monotonic(); deadline = started+args.time_budget
        harness = digest(__file__)
        report = {'status': 'running', 'identity': identity, 'source_sha256': fingerprints,
                  'archive_sha256': digest(args.archive), 'harness_sha256': harness,
                  'source_gate_sha256': digest(args.source_gate), 'unpacked_gate_sha256': digest(args.unpacked_gate),
                  'time_budget': args.time_budget, 'threads': 2, 'worker_memory_mib': 1536,
                  'llm_calls': 0, 'classification_augmentation_qualified': bool(cls.get('measured_cv_gate_passed')),
                  'classification_cv_status': cls['status'],
                  'scope': 'Opt-in frozen learned procedure on reused public cuts; no official score/upload', 'tasks': []}
        receipt_path = args.output/'campaign.json'
        atomic_json(receipt_path, report)
        env = {k: v for k, v in os.environ.items() if not any(s in k.upper() for s in
               ['KEY', 'TOKEN', 'SECRET', 'PROXY', 'AUTH', 'PASSWORD', 'PASSWD'])}
        env.update(AUTOML_THREADS='2', OPENBLAS_NUM_THREADS='2', OMP_NUM_THREADS='2',
                   MKL_NUM_THREADS='2', NUMEXPR_NUM_THREADS='2', PYTHONIOENCODING='utf-8')
        previous = signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(128+signum))
        try:
            for index, task in enumerate(args.tasks):
                spec, *_ = discover(task, loaded=load_inputs(task, allow_llm=False))
                if spec['kind'] != ['regression', 'classification'][index]:
                    raise ValueError('Unexpected task order')
                before = {'task': digest(task), **{name: digest(p) for name, p in spec['paths'].items()}}
                directory = args.output/f'task-{index:02d}'; directory.mkdir()
                for name, payload in files.items():
                    (directory/name).write_bytes(payload)
                (directory/'task.md').write_bytes(task.read_bytes())
                for source in spec['paths'].values():
                    source = Path(source); target = directory/source.relative_to(Path(spec['root']))
                    target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target)
                seconds = int(min(3600 if index == 0 else 9900, deadline-time.monotonic()-30))
                if seconds < 180:
                    break
                command = [sys.executable, '-u', 'solution.py', 'task.md', '--offline', '--time-budget', str(seconds),
                           '--max-planner-calls', '0', '--max-llm-calls', '0', '--research-profile', 'incumbent_mix',
                           '--run-name', 'pipe02']
                tick = time.monotonic()
                print(json.dumps({'event': 'task_started', 'kind': spec['kind'], 'seconds': seconds}), flush=True)
                with (directory/'process.log').open('x') as log:
                    process = subprocess.Popen(command, cwd=directory, env=env, stdin=subprocess.DEVNULL,
                                               stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                    code = wait_owned(process, min(seconds+20, deadline-time.monotonic()), 2*2**30)
                path = directory/'automl_runs/pipe02/report.json'
                actual = json.loads(path.read_text()) if path.exists() else {}
                unchanged = before == {'task': digest(task), **{name: digest(p) for name, p in spec['paths'].items()}}
                complete = (code == 0 and actual.get('research_profile') == 'incumbent_mix' and unchanged
                            and actual.get('validation_complete') and actual.get('integrity_ok')
                            and actual.get('final_fit_status') == 'ok')
                row = {'kind': spec['kind'], 'exit_code': code, 'seconds': round(time.monotonic()-tick, 3),
                       'input_sha256': before, 'original_inputs_unchanged': unchanged, 'complete': bool(complete),
                       'report_path': str(path), 'submission_sha256': actual.get('submission_sha256')}
                report['tasks'].append(row); atomic_json(receipt_path, report)
                print(json.dumps({'event': 'task_finished', **row}), flush=True)
            report['status'] = 'completed' if len(report['tasks']) == 2 and all(r['complete'] for r in report['tasks']) else 'incomplete'
        except BaseException as exc:
            report.update(status='interrupted' if isinstance(exc, (SystemExit, KeyboardInterrupt)) else 'failed',
                          exception_type=type(exc).__name__)
            raise
        finally:
            report.update(seconds=round(time.monotonic()-started, 3), source_unchanged=files == build_files(),
                          harness_unchanged=harness == digest(__file__))
            if report['status'] == 'completed' and not (report['source_unchanged'] and report['harness_unchanged']):
                report['status'] = 'frozen_inputs_changed'
            atomic_json(receipt_path, report)
            signal.signal(signal.SIGTERM, previous)
        if report['status'] != 'completed':
            raise SystemExit(1)


if __name__ == '__main__':
    main()
