"""REG-BLEND-01 fixed .9complete-control+.1nested-TPE replay; no fitting."""
from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd

from summarize_mvp import selected_records
from summarize_research import Verifier, digest, partition, verify_predictions, summarize_hpo

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control-report', type=Path, required=True)
    parser.add_argument('--hpo-screen', type=Path, required=True)
    parser.add_argument('--root-mapping-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or not args.output.resolve().is_relative_to((ROOT/'test-runs').resolve()):
        parser.error('Use a new ignored output receipt')
    control = json.loads(args.control_report.read_text())
    parity = json.loads((ROOT/'release/v16-mean1/full-default-parity.json').read_text())
    if digest(args.control_report) != parity['tasks']['regression']['report_sha256']:
        raise ValueError('Not the qualified complete regression control')
    mapping = json.loads(args.root_mapping_file.read_text())
    mapping = mapping.get('root_mapping', mapping)
    def resolve(value):
        path = Path(value)
        for old, new in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
            if path.is_relative_to(old):
                return Path(new)/path.relative_to(old)
        return path
    screen = json.loads(args.hpo_screen.read_text())
    verified = summarize_hpo(args.hpo_screen)
    if not verified['complete_verified_screen']:
        raise ValueError('Require completed independently verified nested HPO')
    verifier = Verifier(screen, args.hpo_screen.parent/'sources')
    spec, train = verifier.spec, verifier.train
    if spec['kind'] != 'regression' or spec['metric'] != 'rmse' or verifier.periods is None:
        raise ValueError('Expected forward RMSE regression')
    provenance = resolve(control['provenance_path'])
    if json.loads(provenance.read_text())['sha256']['input:train'] != screen['input_sha256']['train']:
        raise ValueError('Historical/source train fingerprints differ')
    result = {'scope': 'REG-BLEND-01 fixed no-fit .9complete-control+.1inner-selected TPE8; posthoc reused public, not qualified/private/official',
        'weights': [.9, .1], 'configurations': 1, 'model_fits': 0,
        'control_report_sha256': digest(args.control_report), 'hpo_manifest_sha256': digest(args.hpo_screen),
        'control_provenance_sha256': digest(provenance), 'input_sha256': screen['input_sha256'],
        'harness_sha256': digest(__file__), 'cuts': []}
    for index, split_name in enumerate(['split.npz', 'confirmation_split.npz']):
        historical = selected_records(control)[index]
        current = next(c for c in screen['cuts'] if c['cut'] == index)
        cut_path = args.hpo_screen.parent/f'cut-{index}'
        paths = [args.control_report.parent/split_name, cut_path/'outer-split.npz']
        left, right = [partition(p, len(train), periods=verifier.periods) for p in paths]
        if not all(np.array_equal(a, b) for a, b in zip(left, right)):
            raise ValueError('Actual source partitions differ')
        va = left[1]
        directories = [resolve(historical['output_dir']), cut_path/'outer-tpe']
        records = [historical, current['outcomes']['tpe']]
        scores = [verify_predictions(r, d, spec, train, va) for r, d in zip(records, directories)]
        predictions = [pd.read_csv(d/'validation_predictions.csv').y_pred.to_numpy() for d in directories]
        mixed = .9*predictions[0]+.1*predictions[1]
        value = float(np.sqrt(np.mean((train[spec['target']].iloc[va].to_numpy()-mixed)**2)))
        result['cuts'].append({'cut': index, 'split_sha256': list(map(digest, paths)),
            'control': scores[0], 'tpe': scores[1], 'blend_rmse': value, 'gate_passed': value < scores[0]['value']})
    result.update(control_mean=float(np.mean([c['control']['value'] for c in result['cuts']])),
                  blend_mean=float(np.mean([c['blend_rmse'] for c in result['cuts']])),
                  measured_replay_gate_passed=all(c['gate_passed'] for c in result['cuts']),
                  full_refit=False, qualified_release=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ['control_mean', 'blend_mean', 'measured_replay_gate_passed', 'model_fits']}))


if __name__ == '__main__':
    main()
