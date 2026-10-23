"""Explicit root entry point: preserve one SC1 deadline and this process identity."""
from pathlib import Path
import argparse
import ctypes
import hashlib
import json
import os
import runpy
import subprocess
import sys
import time
import psutil

def sha(value):
    return hashlib.sha256(value).hexdigest()
def write(path, value):
    temporary = path.with_suffix(path.suffix + '.pending')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    os.replace(temporary, path)

parser = argparse.ArgumentParser()
parser.add_argument('--manifest-sha256', required=True)
parser.add_argument('--expected-commit', required=True)
parser.add_argument('--work-root', type=Path, default=Path(__file__).resolve().parent)
args = parser.parse_args()
work = args.work_root.resolve()
repo = work / 'alfa-hack-automl'
source = repo / 'research/support-context/run_support_component.py'
manifest_path = work / 'support-component-launch/manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
review = json.loads((work / 'support-component-launch/review.json').read_text(encoding='utf-8'))
if sha(manifest_path.read_bytes()) != args.manifest_sha256 or review['manifest_sha256'] != args.manifest_sha256:
    raise ValueError('Explicit reviewed SC1 manifest differs')
if sha(source.read_bytes()) != manifest['coordinator_sha256'] or review['source_sha256'] != manifest['coordinator_sha256']:
    raise ValueError('Published SC1 supervisor differs from review')
git = ['git', '-c', 'safe.directory=' + repo.as_posix(), '-C', str(repo)]
head = subprocess.run(git + ['rev-parse', 'HEAD'], check=True, capture_output=True).stdout.decode().strip()
committed = subprocess.run(git + ['show', 'HEAD:research/support-context/run_support_component.py'], check=True, capture_output=True).stdout
launcher_committed = subprocess.run(git + ['show', 'HEAD:research/support-context/launch_in_task.py'], check=True, capture_output=True).stdout
if head != args.expected_commit or sha(committed) != manifest['coordinator_sha256'] or sha(launcher_committed) != sha(Path(__file__).read_bytes()):
    raise ValueError('Run only the exact reviewed published commit')
receipt_path = work / 'sc1-launcher-receipt.json'
if receipt_path.exists() or (repo / 'test-runs/sc1').exists():
    raise FileExistsError('Never overwrite/restart an SC1 attempt or its clock')
started = time.time()
deadline = started + 4200
receipt = {'status':'launching', 'launch_started_unix':started, 'absolute_deadline_unix':deadline,
    'common_seconds':4200, 'verification_reserve_seconds':600,
    'owned_root':{'pid':os.getpid(), 'create_time':psutil.Process().create_time()},
    'manifest_sha256':args.manifest_sha256, 'source_sha256':manifest['coordinator_sha256'],
    'launcher_sha256':sha(Path(__file__).read_bytes()),
    'git_commit':head, 'promotion':False}
with receipt_path.open('x', encoding='utf-8') as stream:
    stream.write(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
awake = None
try:
    state_path = work / 'SESSION_STATE.json'
    state = json.loads(state_path.read_text(encoding='utf-8'))
    state['support_context'].update(component_status='launching_frozen_sc1',
        component_receipt='work/alfa-hack-automl/test-runs/sc1/coordinator.json',
        launcher_receipt='work/sc1-launcher-receipt.json',
        launch_manifest_sha256=args.manifest_sha256,
        absolute_deadline_unix=deadline, owned_launcher_identity=receipt['owned_root'],
        committed_supervisor=head)
    state['updated_epoch'] = time.time()
    write(state_path, state)
    if os.name == 'nt':
        awake = bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000001))
    receipt['windows_awake_requested'] = awake
    write(receipt_path, receipt)
    sys.argv = [str(source), '--work-root', str(work), '--launch', '--manifest-sha256', args.manifest_sha256,
                '--deadline-unix', str(deadline)]
    runpy.run_path(str(source), run_name='__main__')
    receipt['status'] = 'supervisor_completed'
except BaseException as exc:
    receipt.update(status='supervisor_exited', exception_type=type(exc).__name__)
    if isinstance(exc, SystemExit):
        receipt['exit_code'] = exc.code
    raise
finally:
    receipt.update(finished_unix=time.time(), elapsed_common_seconds=time.time()-started)
    if os.name == 'nt':
        receipt['windows_awake_released'] = bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000000))
    write(receipt_path, receipt)
