"""Bound only the synthetic controller test Python, not any experiment worker."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time
import psutil

ROOT = Path(__file__).resolve().parent
CHECKS = ROOT / 'checks.py'
SOURCE = ROOT.parent / 'fullagent_cv_coordinator.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    freeze = json.loads((ROOT / 'premock-freeze-r2.json').read_text(encoding='utf-8'))
    assert sha(CHECKS) == freeze['checks_sha256']
    assert sha(SOURCE) == freeze['source_sha256']
    assert sha(__file__ and Path(__file__)) == freeze['guard_sha256']
    allowed = {'PATH', 'SystemRoot', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'ComSpec', 'PATHEXT'}
    env = {k: v for k, v in os.environ.items() if k in allowed}
    env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1',
        AUTOML_THREADS='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
        MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    tick = time.monotonic()
    seen, peak, exception = {}, 0, None
    with (ROOT / 'guarded-stdout.log').open('x', encoding='utf-8') as stream:
        # Stdlib-only contracts need no venv package bootstrap process.
        test_python = Path(getattr(sys, '_base_executable', sys.executable)).resolve()
        child = subprocess.Popen([str(test_python), '-B', str(CHECKS)], cwd=ROOT, env=env,
            stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        root = psutil.Process(child.pid)
        identity = (child.pid, root.create_time())
        seen[identity] = root
        try:
            while child.poll() is None:
                current = psutil.Process(identity[0])
                if current.create_time() != identity[1]:
                    raise RuntimeError('Synthetic root identity changed')
                descendants = current.children(recursive=True)
                for process in descendants:
                    seen[(process.pid, process.create_time())] = process
                if descendants:
                    raise RuntimeError('Synthetic checks unexpectedly launched a real descendant')
                memory = current.memory_info().rss
                peak = max(peak, memory)
                if memory > 512 * 2**20:
                    raise MemoryError('Synthetic512MiBcap')
                if time.monotonic() - tick >= 300:
                    raise TimeoutError('Synthetic300secondcap')
                time.sleep(.05)
        except psutil.NoSuchProcess:
            pass
        except BaseException as exc:
            exception = type(exc).__name__
        finally:
            for (pid, created), process in reversed(list(seen.items())):
                try:
                    if process.create_time() == created and process.is_running():
                        process.terminate()
                except psutil.NoSuchProcess:
                    pass
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                current = psutil.Process(identity[0])
                if current.create_time() == identity[1]:
                    current.kill()
                child.wait(timeout=5)
    unresolved = []
    for pid, created in seen:
        try:
            process = psutil.Process(pid)
            if process.create_time() == created and process.is_running():
                unresolved.append({'pid': pid, 'create_time': created})
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied:
            unresolved.append({'pid': pid, 'create_time': created, 'reason': 'AccessDenied'})
    unchanged = all([sha(CHECKS) == freeze['checks_sha256'], sha(SOURCE) == freeze['source_sha256'],
        sha(Path(__file__)) == freeze['guard_sha256']])
    result = json.loads((ROOT / 'results.json').read_text(encoding='utf-8')) if (ROOT / 'results.json').is_file() else None
    passed = child.returncode == 0 and not unresolved and not exception and unchanged and result and result['status'] == 'passed'
    record = {'status': 'passed' if passed else 'failed', 'checks_sha256': freeze['checks_sha256'],
        'source_sha256': freeze['source_sha256'], 'guard_sha256': freeze['guard_sha256'],
        'exit_code': child.returncode, 'exception_type': exception, 'seconds': time.monotonic()-tick,
        'maximum_seconds': 300, 'maximum_rss_mib': 512, 'peak_rss_mib': peak / 2**20, 'threads': 1,
        'owned_cleanup_confirmed': not unresolved, 'unresolved': unresolved,
        'source_unchanged': unchanged, 'test_python_processes': 1, 'real_worker_processes': 0,
        'test_interpreter_sha256': sha(test_python), 'test_interpreter_scope': 'base Python; stdlib-only mocked target execution',
        'fits': 0, 'api_calls': 0, 'actual_stage0_gates': 0, 'promotion': False}
    with (ROOT / 'guarded-results.json').open('x', encoding='utf-8') as stream:
        json.dump(record, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(record))
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
