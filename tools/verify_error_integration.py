"""Bounded fit-free integration gate; does not replace the complete release gate."""
from pathlib import Path
import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.processes import wait_owned
from build_submission import build_files

SCRIPTS = ('test_error_analysis_contracts.py', 'test_error_analysis.py',
           'test_error_preparation.py', 'test_architecture.py', 'test_diversity.py',
           'test_marginal_selection.py', 'test_local_error_preparation.py',
           'test_marginal_replay.py')
FROZEN_SHA = '565e0b40d225022f91a3217fae34ac1895044f63d40f854d69ddd4f2e2767a49'


def digests():
    return {name: hashlib.sha256(value).hexdigest() for name, value in build_files().items()}


def verify(output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / 'tmp').mkdir()
    (output / 'mpl').mkdir()
    archive = ROOT / 'release/solution-long01-anytime1.zip'
    if hashlib.sha256(archive.read_bytes()).hexdigest() != FROZEN_SHA:
        raise ValueError('Frozen LONG-01 archive differs')
    before = digests()
    with zipfile.ZipFile(archive) as packed:
        unchanged = {name: before.get(name) == hashlib.sha256(packed.read(name)).hexdigest()
                     for name in packed.namelist()}
    if not all(unchanged.values()):
        raise ValueError('Existing ML/requirements compiled bytes changed during diagnostic integration')
    env = {k: v for k, v in os.environ.items()
           if not any(x in k.upper() for x in ('KEY', 'TOKEN', 'SECRET', 'AUTH', 'PASSWORD', 'PROXY'))}
    env.update(AUTOML_THREADS='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
               MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1', TMPDIR=str(output / 'tmp'),
               MPLCONFIGDIR=str(output / 'mpl'), PYTHONDONTWRITEBYTECODE='1')
    rows = []
    for name in SCRIPTS:
        source = (ROOT / 'tests' / name).read_text()
        expected = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and node.name.startswith('test_') for node in ast.walk(ast.parse(source)))
        started = time.monotonic()
        log = output / (name + '.log')
        with log.open('w') as stream:
            process = subprocess.Popen([sys.executable, '-B', str(ROOT / 'tests' / name)],
                cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code = wait_owned(process, timeout=90, memory_bytes=768 * 2**20)
            except subprocess.TimeoutExpired:
                code = 'timeout'
            except MemoryError:
                code = 'memory_limit'
        found = re.findall(r'Ran (\d+) tests? in ', log.read_text())
        observed = int(found[-1]) if found else None
        row = dict(script=name, expected=expected, observed=observed, exit_code=code,
                   passed=code == 0 and observed == expected,
                   seconds=round(time.monotonic() - started, 3),
                   script_sha256=hashlib.sha256(source.encode()).hexdigest(), log=str(log))
        rows.append(row)
        print(json.dumps(row), flush=True)
        atomic_json(output / 'progress.json', {'checks': rows})
    result = dict(scope='Fit-free ERR-01 integration, NOT a full release or quality gate',
        frozen_archive_sha256=FROZEN_SHA, legacy_compiled_files_unchanged=unchanged,
        added_compiled_modules=sorted(set(before) - set(unchanged)), source_sha256=before,
        source_unchanged=digests() == before, checks=rows, new_model_fits=0,
        unique_checks_passed=sum(r['observed'] or 0 for r in rows if r['passed']))
    result['passed'] = result['source_unchanged'] and all(r['passed'] for r in rows)
    atomic_json(output / 'results.json', result)
    return result['passed']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    raise SystemExit(0 if verify(parser.parse_args().output) else 1)
