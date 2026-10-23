"""Prepare BASE-01 from portable reports and explicitly relocated caches; no fits."""
import argparse
import json
from pathlib import Path
import sys
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from automl.error_analysis.api import audit_baseline, ErrorAnalysisRequest, finalize_baseline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, default=ROOT / 'public_tasks')
    parser.add_argument('--cache-root', type=Path, help='Transferred llm-upgrade-20261022 directory; never inferred or replaced with V10')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--root-mapping-file', type=Path, help='JSON root_mapping emitted by the verified transfer')
    parser.add_argument('--analyze', action='store_true', help='Run prepared passports sequentially, then verify actual final CSVs')
    args = parser.parse_args()
    if args.analyze and args.root_mapping_file is None:
        parser.error('--analyze requires --root-mapping-file for original final CSV locations')
    mapping = json.loads(args.root_mapping_file.read_text()) if args.root_mapping_file else None
    if mapping is not None:
        mapping = mapping.get('root_mapping', mapping)
    result = audit_baseline(ROOT, args.data_root, args.output, args.cache_root, mapping)
    print(json.dumps({'independent_checks_complete': result['independent_checks_complete'],
                      'raw_prediction_analysis': result['raw_prediction_analysis'],
                      'inventory': str(args.output / 'baseline_inventory.json')}))
    if args.analyze:
        from automl.infrastructure.processes import wait_owned
        for entry in result['cache_inventory']:
            for descriptor in entry['requests']:
                request = ErrorAnalysisRequest.from_json(Path(descriptor['path']).read_text())
                with tempfile.TemporaryFile(mode='w+t') as log:
                    process = subprocess.Popen([sys.executable, '-B', str(ROOT / 'tools/error_passport.py'), '--request', descriptor['path']],
                                               stdout=log, stderr=log, start_new_session=True)
                    code = wait_owned(process, request.budget.max_seconds + 20, (request.budget.max_memory_mb + 256) * 2**20)
                    log.seek(0)
                    content = log.read()
                    print(content[-4000:], flush=True)
                    if code:
                        raise RuntimeError('Passport child failed with exit code ' + str(code))
        if any(len(entry['requests']) != 2 for entry in result['cache_inventory']):
            print(json.dumps({'baseline_complete': False, 'reason': 'Original caches/splits missing; available passports analyzed, no fallback/refit.'}))
            return 2
        closed = finalize_baseline(args.output / 'baseline_inventory.json')
        print(json.dumps({'baseline_complete': closed['baseline_complete'], 'verified_runs': len(closed['original_runs'])}))
    return 0 if result['independent_checks_complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
