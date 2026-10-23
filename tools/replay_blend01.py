"""Preregistered one-weight, no-fit replay against the complete qualified agent."""
from pathlib import Path
import argparse
import json
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from automl.infrastructure.atomic import atomic_json
from summarize_mvp import selected_records
from summarize_research import digest, paired_gate, partition, verify_predictions


def aligned_probabilities(directory, rows, classes):
    directory = Path(directory)
    with np.load(directory/'validation_probabilities.npz', allow_pickle=False) as saved:
        if not np.array_equal(saved['row_position'], rows):
            raise ValueError('Probability row order differs from saved split')
        stored_classes = saved['classes'].astype(str).tolist()
        if len(set(stored_classes)) != len(stored_classes) or set(stored_classes) != set(classes):
            raise ValueError('Probability class schema differs')
        probability = saved['probabilities'][:, [stored_classes.index(c) for c in classes]]
    if (probability.shape != (len(rows), len(classes)) or not np.isfinite(probability).all()
            or (probability < 0).any() or (probability > 1).any()
            or not np.allclose(probability.sum(axis=1), 1, atol=1e-7, rtol=1e-7)):
        raise ValueError('Invalid normalized probabilities')
    csv = pd.read_csv(directory/'validation_predictions.csv')
    if (not np.array_equal(csv.row_position.to_numpy(), rows)
            or not np.array_equal(csv.y_pred.astype(str), np.asarray(classes)[probability.argmax(axis=1)])):
        raise ValueError('Probabilities disagree with saved CSV predictions')
    return probability


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control-report', type=Path, required=True)
    parser.add_argument('--mvp-report', type=Path, required=True)
    parser.add_argument('--root-mapping-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to((ROOT/'test-runs').resolve()):
        parser.error('Raw replay receipts belong in ignored test-runs/')
    if args.output.exists():
        parser.error('Preserve existing replay receipts')
    parity = json.loads((ROOT/'release/v16-mean1/full-default-parity.json').read_text())
    if digest(args.control_report) != parity['tasks']['classification']['report_sha256']:
        raise ValueError('Not the preserved qualified complete control')
    mapping = json.loads(args.root_mapping_file.read_text())
    mapping = mapping.get('root_mapping', mapping)
    def resolve(value):
        path = Path(value)
        for old, new in sorted(mapping.items(), key=lambda item: len(item[0]), reverse=True):
            if path.is_relative_to(old):
                return Path(new)/path.relative_to(old)
        return path
    controls = json.loads(args.control_report.read_text())
    mvp = json.loads(args.mvp_report.read_text())
    spec = controls['spec']
    if spec['kind'] != 'classification' or spec['metric'] != 'macro_f1':
        raise ValueError('BLEND-01 requires classification Macro F1')
    provenance_path = resolve(controls['provenance_path'])
    expected_train = json.loads(provenance_path.read_text())['sha256']['input:train']
    train_path = resolve(mvp['spec']['paths']['train'])
    if digest(train_path) != expected_train:
        raise ValueError('Candidate and control source rows differ')
    train = pd.read_csv(train_path)
    hashes = pd.util.hash_pandas_object(train[spec['features']], index=False).to_numpy(dtype='uint64')
    labels = train[spec['target']].astype(str).to_numpy()
    from sklearn.metrics import f1_score
    report = {'scope': 'BLEND-01 posthoc fixed .9qualified-control+.1MVP, reused-public, not a refit or official score',
              'weights': [.9, .1], 'configurations': 1, 'model_fits': 0,
              'control_report_sha256': digest(args.control_report), 'mvp_report_sha256': digest(args.mvp_report),
              'train_sha256': digest(train_path), 'control_provenance_sha256': digest(provenance_path),
              'harness_sha256': digest(__file__), 'cuts': []}
    for index, split_name in enumerate(['split.npz', 'confirmation_split.npz']):
        control, candidate = selected_records(controls)[index], selected_records(mvp)[index]
        paths = [args.control_report.parent/split_name, args.mvp_report.parent/split_name]
        left, right = [partition(path, len(train), hashes) for path in paths]
        if not all(np.array_equal(a, b) for a, b in zip(left, right)):
            raise ValueError('Actual candidate/control partitions differ')
        tr, va = left
        probabilities, verified, probability_hashes = [], [], []
        for record in [control, candidate]:
            directory = resolve(record['output_dir'])
            verified.append(verify_predictions(record, directory, spec, train, va))
            probabilities.append(aligned_probabilities(directory, va, spec['classes']))
            probability_hashes.append(digest(directory/'validation_probabilities.npz'))
        mixed = .9*probabilities[0]+.1*probabilities[1]
        predicted = np.asarray(spec['classes'])[mixed.argmax(axis=1)]
        values = f1_score(labels[va], predicted, labels=spec['classes'], average=None, zero_division=0)
        measured = {'value': float(values.mean()), 'per_class_f1': dict(zip(spec['classes'], map(float, values)))}
        support = {c: len(np.unique(hashes[tr][labels[tr] == c])) for c in spec['classes']}
        report['cuts'].append({'cut': index, 'split_sha256': list(map(digest, paths)),
            'probabilities_sha256': probability_hashes, 'control': verified[0],
            'mvp': verified[1], 'blend': measured, 'gate': paired_gate(verified[0], measured, spec, support)})
    report.update(control_mean=float(np.mean([c['control']['value'] for c in report['cuts']])),
                  blend_mean=float(np.mean([c['blend']['value'] for c in report['cuts']])),
                  measured_replay_gate_passed=all(c['gate']['passed'] for c in report['cuts']),
                  qualified_complete_agent=False, full_refit=False, automatic_promotion=False)
    atomic_json(args.output, report)
    print(json.dumps({k: report[k] for k in ['control_mean', 'blend_mean', 'measured_replay_gate_passed', 'model_fits']}))


if __name__ == '__main__':
    main()
