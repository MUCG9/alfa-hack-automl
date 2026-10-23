"""Adapt declared organizer inputs to BASE-01, without copying data or fitting."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from automl.task_understanding.api import load_inputs
from automl.error_analysis.api import audit_baseline
from automl.infrastructure.atomic import atomic_json


def prepare(tasks, output):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Refusing an existing preparation directory')
    expected = json.loads((ROOT / 'docs/handoff/public_inputs.json').read_text())
    checked = {}
    if set(tasks) != {'classification', 'regression'}:
        raise ValueError('Both public task roles must be explicit')
    for kind, task in tasks.items():
        task = Path(task).resolve(strict=True)
        inputs = load_inputs(task)
        paths = {role + '.csv': Path(value).resolve(strict=True)
                 for role, value in inputs['paths'].items()}
        paths['task.md'] = task
        if set(paths) != set(expected[kind]['sha256']):
            raise ValueError('Unexpected declared input roles')
        for name, path in paths.items():
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected[kind]['sha256'][name]:
                raise ValueError('Original public input SHA mismatch: ' + kind + '/' + name)
        checked[kind] = paths
    output.mkdir(parents=True, exist_ok=False)
    view = output / 'input-view'
    for kind, paths in checked.items():
        directory = view / kind
        directory.mkdir(parents=True)
        for name, source in paths.items():
            (directory / name).symlink_to(source)
    transfer = json.loads((ROOT / 'transfer/v11-v16-caches/manifest.json').read_text())
    mapping = {transfer['source_root']: str(ROOT)}
    atomic_json(output / 'root-mapping.json', {'root_mapping': mapping})
    result = audit_baseline(ROOT, view, output / 'audit',
                           ROOT / 'test-runs/llm-upgrade-20261022', mapping)
    receipt = {'scope': 'Independent local BASE preparation only; passports not executed',
               'new_model_fits': 0, 'input_files_verified': sum(map(len, checked.values())),
               'independent_checks_complete': result['independent_checks_complete'],
               'raw_prediction_analysis': result['raw_prediction_analysis'],
               'prepared_requests': sum(len(r['requests']) for r in result['cache_inventory']),
               'baseline_complete': False, 'original_data_modified': False,
               'inventory': str(output / 'audit/baseline_inventory.json')}
    atomic_json(output / 'preparation.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--classification-task', type=Path, required=True)
    parser.add_argument('--regression-task', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare({'classification': args.classification_task,
                             'regression': args.regression_task}, args.output)))
