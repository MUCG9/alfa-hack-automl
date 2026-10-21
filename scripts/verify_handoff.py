"""Verify the frozen release and run offline tests from its unpacked source.

Does not call Qwen, submit to the platform, or change the release archive.
"""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = 'b429f04a231b5fa7f5fb52d8008aa019dbc6c53cc6e5f81a6ff06999edc1602a'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'test-runs/handoff_verification.json')
    args = parser.parse_args()
    archive_path = ROOT/'release/solution-v2.zip'
    sha = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if sha != EXPECTED:
        raise ValueError('Frozen release archive changed')
    result = {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'python': sys.version.split()[0], 'zip_sha256': sha,
              'real_api_calls': False, 'official_submission_made': False,
              'source_matches_submitted_v2': True, 'tests': []}
    with tempfile.TemporaryDirectory(prefix='alfa-handoff-') as directory:
        unpacked = Path(directory)
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            if any('/' in n or '\\' in n for n in names):
                raise ValueError('Unexpected nested file')
            for name in names:
                if archive.read(name) != (ROOT/name).read_bytes():
                    raise ValueError(f'Current source differs from frozen v2: {name}')
            archive.extractall(unpacked)
        shutil.copytree(ROOT/'tests', unpacked/'tests', ignore=shutil.ignore_patterns('__pycache__'))
        environment = {k: v for k, v in os.environ.items() if not k.startswith('OPENAI_')}
        for filename in ['test_v2.py', 'test_resilience.py', 'smoke.py']:
            command = [sys.executable, str(unpacked/'tests'/filename)]
            process = subprocess.run(command, cwd=unpacked, env=environment,
                                     capture_output=True, text=True, timeout=240)
            if filename == 'smoke.py' and process.returncode == 0:
                count = len(json.loads(process.stdout))
            else:
                match = re.search(r'Ran (\d+) tests?', process.stderr)
                count = int(match[1]) if match else None
            result['tests'].append({'script': 'tests/'+filename,
                                    'exit_code': process.returncode, 'count': count,
                                    'stdout': process.stdout, 'stderr': process.stderr})
            if process.returncode:
                break
    result['passed'] = len(result['tests']) == 3 and all(t['exit_code'] == 0 for t in result['tests'])
    result['total_test_cases'] = sum(t['count'] or 0 for t in result['tests'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'tests'}, ensure_ascii=False, indent=2))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
