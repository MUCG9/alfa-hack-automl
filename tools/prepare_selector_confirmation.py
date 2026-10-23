"""Prepare the ONE missing SEL-01 confirmation. This command never trains."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from automl.contracts.messages import canonical_hash
from automl.infrastructure.atomic import atomic_json
from build_submission import build_files

FROZEN_SHA = '565e0b40d225022f91a3217fae34ac1895044f63d40f854d69ddd4f2e2767a49'

def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            digest.update(block)
    return digest.hexdigest()


def long_run_ready(directory):
    """Files, not PID visibility, certify both completed LONG-01 lifecycles."""
    directory = Path(directory)
    for index in range(2):
        task = directory / f'task-{index:02d}'
        paths = [task / 'assessment.json', task / 'automl_runs/run-v2/report.json',
                 task / 'automl_runs/run-v2/anytime_state.json']
        if not all(path.is_file() for path in paths):
            return False
        assessment, report, state = [json.loads(path.read_text()) for path in paths]
        if type(assessment.get('exit_code')) is not int or assessment['exit_code'] != 0:
            raise ValueError('LONG-01 failed: manual review before starting another fit')
        if state.get('phase') != 'completed':
            return False
        if (report.get('version') != 'long-01-anytime'
                or report.get('integrity_ok') is not True
                or report.get('exported_full_fit_ok') is not True):
            raise ValueError('LONG-01 did not certify integrity and a trained export')
        metric = report.get('exported_mean')
        if type(metric) not in (float, int) or not math.isfinite(metric):
            raise ValueError('LONG-01 exported metric unavailable')
        output = task / 'submission.csv'
        if not output.is_file() or not (sha(output) == report.get('submission_sha256')
                                       == assessment.get('submission_sha256')):
            raise ValueError('LONG-01 actual CSV does not match its reports')
    return True


def prepare(inventory_path, replay_path, output, long_run):
    if Path(output).resolve().is_relative_to(Path(long_run).resolve()):
        raise ValueError('Never write a plan inside the active LONG-01 directory')
    if output.exists():
        raise FileExistsError('Do not replace a confirmation plan')
    inventory = json.loads(inventory_path.read_text())
    replay = json.loads(replay_path.read_text())
    missing = replay.get('missing_confirmation_ids', [])
    if (replay.get('recommendation') != 'needs_confirmation_fit' or len(missing) != 1
            or replay.get('legacy_replay_matches') is not True
            or missing != [replay['proposal']['third_slot']['model_id']]):
        raise ValueError('Only the frozen single missing confirmation is allowed')
    entries = [r for r in inventory['cache_inventory']
               if r['version'] == 'v11-featureviews1' and r['kind'] == 'classification']
    if len(entries) != 1:
        raise ValueError('Explicit original V11 classification inventory required')
    entry = entries[0]
    requests = {r['scope']: json.loads(Path(r['path']).read_text()) for r in entry['requests']}
    if set(requests) != {'search', 'confirmation'}:
        raise ValueError('Original pair of requests required')
    report_path = Path(entry['run_dir']) / 'report.json'
    report = json.loads(report_path.read_text())
    records = [r for r in report['experiments'] if r['status'] == 'ok'
               and 'model-' + canonical_hash(r['recipe'])[:20] == missing[0]]
    if len(records) != 1:
        raise ValueError('Candidate is not uniquely identified in the frozen search')
    record = records[0]
    matched = [r for r in requests['search']['predictions'] if r['model_id'] == missing[0]]
    if len(matched) != 1 or matched[0]['recipe_sha256'] != canonical_hash(record['recipe']):
        raise ValueError('Candidate recipe differs from verified primary prediction')
    if any(r['model_id'] == missing[0] for r in requests['confirmation']['predictions']):
        raise ValueError('Do not refit an already available confirmation')
    protected = dict(replay['verified_artifacts_sha256'])
    protected.update({str(p.resolve()): sha(p) for p in [inventory_path, replay_path, report_path]})
    for descriptor in entry['requests']:
        path = Path(descriptor['path'])
        protected[str(path.resolve())] = sha(path)
    for path, expected in protected.items():
        if sha(path) != expected:
            raise ValueError('Verified cached evidence changed before planning')
    current = build_files()
    archive = ROOT / 'release/solution-long01-anytime1.zip'
    if sha(archive) != FROZEN_SHA:
        raise ValueError('Frozen LONG-01 archive differs')
    with zipfile.ZipFile(archive) as packed:
        if any(current.get(name) != packed.read(name) for name in packed.namelist()):
            raise ValueError('Existing worker policy differs from frozen LONG-01')
    ready = long_run_ready(long_run)
    plan = {'schema_version': '1.0', 'experiment': 'SEL-01-one-confirmation-screen',
        'status': 'prepared_not_run', 'new_model_fits': 0,
        'blocked_by': [] if ready else ['LONG-01 still incomplete; no overlapping fits'],
        'candidate_id': missing[0], 'recipe': record['recipe'],
        'primary_fit_iterations': record['fit_iterations'],
        'original_report': str(report_path.resolve()),
        'original_confirmation_request': next(r['path'] for r in entry['requests'] if r['scope'] == 'confirmation'),
        'original_confirmation_split': requests['confirmation']['predictions'][0]['split'],
        'protected_artifacts_sha256': protected,
        'compiled_source_sha256': {name: hashlib.sha256(value).hexdigest() for name, value in current.items()},
        'frozen_archive_sha256': sha(archive), 'long_run': str(Path(long_run).resolve()),
        'budget': {'timeout_seconds': 900, 'threads': 2, 'whole_tree_memory_gib': 1.7},
        'first_two_ids': replay['proposal']['selected_ids'][:2], 'control': replay['control'],
        'keep_screen_only_if': 'Both same public cuts strictly improve after the UNCHANGED fixed blending grid',
        'promotion': 'Never from this screen alone: fitting-inner selection plus external group/forward, CV, full-agent and export gates required',
        'scope': 'ONE additional confirmation recipe evaluation (nested view fits counted separately), reused public; NOT independent evaluation or a new full submission',
        'runtime_selector_enabled': False}
    atomic_json(output, plan)
    return plan


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--replay', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--long-run', type=Path, required=True)
    args = parser.parse_args()
    plan = prepare(args.inventory, args.replay, args.output, args.long_run)
    print(json.dumps({k: plan[k] for k in ['status', 'candidate_id', 'blocked_by', 'new_model_fits']}))
