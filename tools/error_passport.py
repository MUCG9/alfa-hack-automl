"""Run an aggregate-only passport from a versioned request with process guards."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from automl.error_analysis.api import ErrorAnalysisRequest, analyze


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.request.stat().st_size > 4 * 2**20:
        parser.error('Request exceeds 4 MiB')
    request = ErrorAnalysisRequest.from_json(args.request.read_text())
    if args.worker:
        profile = analyze(request)
        print(json.dumps({'status': profile.status, 'request_sha256': profile.request_sha256,
                          'report': str(Path(request.output_dir) / 'error_profile.json')}))
        return 2 if profile.status == 'failed' else 0
    if Path(request.output_dir).exists():
        parser.error('Output directory already exists')
    from automl.infrastructure.processes import wait_owned
    env = {k: v for k, v in os.environ.items() if not any(s in k.upper() for s in ('KEY', 'TOKEN', 'SECRET', 'AUTH', 'PASSWORD', 'PROXY'))}
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        env[name] = str(request.budget.threads)
    with tempfile.TemporaryFile(mode='w+t') as output, tempfile.TemporaryFile(mode='w+t') as errors:
        process = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '--worker', '--request', str(args.request.resolve())],
                                   stdout=output, stderr=errors, env=env, start_new_session=True)
        try:
            code = wait_owned(process, request.budget.max_seconds + 5, request.budget.max_memory_mb * 2**20)
        except (subprocess.TimeoutExpired, MemoryError) as exc:
            # No new run is started, and partial files are never reported as success.
            print(json.dumps({'status': 'failed', 'reason': type(exc).__name__, 'request_sha256': request.sha256}), file=sys.stderr)
            return 3
        output.seek(0)
        errors.seek(0)
        sys.stdout.write(output.read())
        sys.stderr.write(errors.read()[-4000:])
        return code


if __name__ == '__main__':
    raise SystemExit(main())
