"""Prepare BASE-01 from portable reports and explicitly relocated caches; no fits."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from automl.error_analysis.api import audit_baseline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, default=ROOT / 'public_tasks')
    parser.add_argument('--cache-root', type=Path, help='Transferred llm-upgrade-20261022 directory; never inferred or replaced with V10')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit_baseline(ROOT, args.data_root, args.output, args.cache_root)
    print(json.dumps({'independent_checks_complete': result['independent_checks_complete'],
                      'raw_prediction_analysis': result['raw_prediction_analysis'],
                      'inventory': str(args.output / 'baseline_inventory.json')}))
    return 0 if result['independent_checks_complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
