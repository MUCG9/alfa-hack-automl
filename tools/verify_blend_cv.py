"""Independently verify fixed BLEND-01 grouped CV, without fitting or tuning."""
from pathlib import Path
import argparse
import json

import numpy as np
from sklearn.metrics import f1_score

from replay_blend01 import aligned_probabilities
from summarize_research import Verifier, digest, paired_gate

ROOT = Path(__file__).resolve().parents[1]


def check_coverage(splits, count):
    coverage = np.zeros(count, dtype=int)
    for fitting, validation in splits:
        if len(fitting)+len(validation) != count:
            raise ValueError('CV fitting rows are not the validation complement')
        coverage[validation] += 1
    if not np.all(coverage == 1):
        raise ValueError('CV validation coverage is not exactly once')


def measured(truth, predicted, classes):
    values = f1_score(truth, predicted, labels=classes, average=None, zero_division=0)
    return {'value': float(values.mean()), 'per_class_f1': dict(zip(classes, map(float, values)))}


def verify(path):
    path = Path(path)
    manifest = json.loads(path.read_text())
    expected = json.loads((ROOT/'docs/experiments/blend01_candidates_20261023.json').read_text())
    if manifest['candidates'] != expected:
        raise ValueError('CV recipes differ from preregistered candidates')
    verifier = Verifier(manifest, path.parent/'sources')
    spec, train = verifier.spec, verifier.train
    if (spec['kind'] != 'classification' or spec['metric'] != 'macro_f1'
            or spec.get('validation_strategy') == 'time'):
        raise ValueError('Expected grouped classification CV')
    classes = spec['classes']
    labels = train[spec['target']].astype(str).to_numpy()
    names = [r['name'] for r in expected]
    records = {(r['name'], r['seed']): r for r in manifest['results']}
    required = {(name, fold) for name in names for fold in range(3)}
    if len(records) != len(manifest['results']) or set(records) != required:
        raise ValueError('Incomplete or duplicate CV workers')
    pools = {name: np.zeros((len(train), len(classes))) for name in names}
    splits, folds, supports = [], [], []
    for fold in range(3):
        arm_partitions, arms = [], {}
        for entry in expected:
            name = entry['name']
            row = records[name, fold]
            if row['status'] != 'ok':
                raise ValueError('CV worker did not succeed')
            directory = Path(row['directory'])
            job = json.loads((directory/'job.json').read_text())
            if job['recipe'] != entry['recipe'] or job['full_fit'] or job['threads'] != 2:
                raise ValueError('CV worker contract changed')
            tr, va = verifier.split(directory/'split.npz')
            arm_partitions.append((tr, va))
            result = verifier.outcome(row, directory, va)
            probability = aligned_probabilities(directory, va, classes)
            pools[name][va] = probability
            arms[name] = {'score': result, 'probability': probability,
                         'probabilities_sha256': digest(directory/'validation_probabilities.npz'),
                         'split_sha256': digest(directory/'split.npz')}
        if not all(np.array_equal(a, b) for a, b in zip(*arm_partitions)):
            raise ValueError('CV control/candidate partitions differ')
        tr, va = arm_partitions[0]
        splits.append((tr, va))
        support = verifier.support(tr)
        supports.append(support)
        probability = .9*arms[names[0]]['probability']+.1*arms[names[1]]['probability']
        blend = measured(labels[va], np.asarray(classes)[probability.argmax(axis=1)], classes)
        folds.append({'fold': fold, 'control': arms[names[0]]['score'],
            'mvp': arms[names[1]]['score'], 'blend': blend,
            'gate': paired_gate(arms[names[0]]['score'], blend, spec, support),
            'split_sha256': [arms[name]['split_sha256'] for name in names],
            'probabilities_sha256': [arms[name]['probabilities_sha256'] for name in names]})
    check_coverage(splits, len(train))
    for name in names:
        with np.load(path.parent/name/'oof.npz', allow_pickle=False) as saved:
            if (not np.array_equal(saved['row_position'], np.arange(len(train)))
                    or not np.array_equal(saved['classes'].astype(str), classes)
                    or not np.array_equal(saved['predictions'], pools[name])):
                raise ValueError('Saved pooled probabilities differ from actual fold artifacts')
    pooled = {name: measured(labels, np.asarray(classes)[pools[name].argmax(axis=1)], classes) for name in names}
    combined = .9*pools[names[0]]+.1*pools[names[1]]
    pooled['blend'] = measured(labels, np.asarray(classes)[combined.argmax(axis=1)], classes)
    support_min = {c: min(s[c] for s in supports) for c in classes}
    pooled_gate = paired_gate(pooled[names[0]], pooled['blend'], spec, support_min)
    return {'scope': 'Independently verified fixed BLEND-01 procedure, reused-public grouped CV; not replay of the initial agent search or private/official score',
            'source_matches_current': verifier.source_matches_current,
            'source_sha256': verifier.source_sha256, 'input_sha256': manifest['inputs'],
            'candidate_contract_sha256': digest(ROOT/'docs/experiments/blend01_candidates_20261023.json'),
            'benchmark_manifest_sha256': digest(path), 'folds': folds,
            'coverage': 'exactly_once', 'rows': len(train), 'groups_disjoint': True,
            'fold_mean': {name: float(np.mean([f[name]['value'] for f in folds])) for name in ['control', 'mvp', 'blend']},
            'pooled': pooled, 'pooled_gate': pooled_gate,
            'pooled_support_scope': 'Minimum independent fitting feature-group count across folds',
            'measured_cv_gate_passed': all(f['gate']['passed'] for f in folds) and pooled_gate['passed'],
            'worker_seconds': [r['seconds'] for r in manifest['results']],
            'worker_peak_mib': [r['peak_mb'] for r in manifest['results']],
            'qualified_release': False, 'official_submission': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--benchmark', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Preserve existing CV verification receipts')
    report = verify(args.benchmark)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ['fold_mean', 'measured_cv_gate_passed', 'coverage']}))


if __name__ == '__main__':
    main()
