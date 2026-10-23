"""Recompute development screen metrics and apply the predeclared paired gates.

Reads immutable saved partitions; never reconstructs them or fits a model.
Export contains metadata/aggregate scores, never input rows or predictions.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from build_submission import build_files


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def partition(path, count, hashes=None, periods=None):
    with np.load(path, allow_pickle=False) as stored:
        tr, va = stored['train'], stored['validation']
    for rows in [tr, va]:
        if (rows.ndim != 1 or rows.dtype.kind not in 'iu' or not len(rows)
                or len(np.unique(rows)) != len(rows) or rows.min() < 0 or rows.max() >= count):
            raise ValueError('Invalid saved partition row positions')
    if np.intersect1d(tr, va).size:
        raise ValueError('Fitting and validation rows overlap')
    if hashes is not None and np.intersect1d(hashes[tr], hashes[va]).size:
        raise ValueError('Fitting and validation feature groups overlap')
    if periods is not None and not np.max(periods[tr]) < np.min(periods[va]):
        raise ValueError('Forward partition chronology failed')
    return tr, va


def verify_predictions(record, directory, spec, train, rows):
    path = Path(directory)/'validation_predictions.csv'
    frame = pd.read_csv(path)
    if not np.array_equal(frame.row_position.to_numpy(), rows):
        raise ValueError('Prediction row order differs from saved validation partition')
    truth = train[spec['target']].iloc[rows]
    if spec['kind'] == 'classification':
        classes = spec['classes']
        if not np.array_equal(truth.astype(str), frame.y_true.astype(str)):
            raise ValueError('Saved truth differs from source classification labels')
        predicted = frame.y_pred.astype(str)
        if frame.y_pred.isna().any() or not set(predicted) <= set(classes):
            raise ValueError('Invalid classification prediction')
        values = f1_score(truth.astype(str), predicted, labels=classes, average=None, zero_division=0)
        value = float(np.mean(values))
        per_class = dict(zip(classes, map(float, values)))
        declared = record['metrics'].get('per_class_f1')
        if declared and any(not math.isclose(per_class[c], declared[c], abs_tol=1e-10, rel_tol=1e-10) for c in classes):
            raise ValueError('Recomputed per-class F1 disagrees with worker')
    else:
        if not np.allclose(truth, frame.y_true, rtol=1e-12, atol=1e-12):
            raise ValueError('Saved truth differs from source regression labels')
        if not np.isfinite(frame.y_pred.to_numpy(dtype=float)).all():
            raise ValueError('Nonfinite regression prediction')
        value = float(np.sqrt(np.mean((truth.to_numpy()-frame.y_pred.to_numpy())**2)))
        per_class = None
    if not math.isfinite(value) or not math.isclose(value, record['metrics'][spec['metric']], rel_tol=1e-10, abs_tol=1e-10):
        raise ValueError('Recomputed primary metric disagrees with worker')
    result = {'value': value, 'validation_rows': len(rows), 'prediction_sha256': digest(path),
              'row_order_verified': True}
    if per_class is not None:
        result['per_class_f1'] = per_class
    return result


def paired_gate(control, candidate, spec, group_support=None):
    gain = candidate['value']-control['value']
    if not spec['greater_is_better']:
        gain = -gain
    result = {'oriented_gain': gain, 'primary_improved': gain > 0}
    if spec['kind'] == 'classification':
        if not group_support:
            raise ValueError('Independent fitting-group class support required')
        deltas = {c: candidate['per_class_f1'][c]-control['per_class_f1'][c] for c in spec['classes']}
        rarest = min(spec['classes'], key=lambda c: group_support[c])
        remaining = [v for c, v in deltas.items() if c != rarest]
        violations = {c: d for c, d in deltas.items() if group_support[c] >= 100 and d < -.01-1e-12}
        result.update(per_class_delta=deltas, independent_fitting_groups=group_support,
                      rarest_class=rarest, gain_without_rarest_class=float(np.mean(remaining)),
                      supported_class_violations=violations)
        result['passed'] = gain > 0 and not violations and result['gain_without_rarest_class'] > 0
    else:
        result['passed'] = gain > 0
    return result


class Verifier:
    def __init__(self, manifest, source_directory):
        self.spec = spec = manifest['spec']
        self.train = pd.read_csv(spec['paths']['train'])
        self.hashes = (pd.util.hash_pandas_object(self.train[spec['features']], index=False).to_numpy(dtype='uint64')
                       if spec['kind'] == 'classification' else None)
        self.periods = (self.train[spec['time_column']].to_numpy()
                        if spec.get('validation_strategy') == 'time' else None)
        expected_inputs = manifest.get('input_sha256', manifest.get('inputs'))
        if expected_inputs != {n: digest(p) for n, p in spec['paths'].items()}:
            raise ValueError('Source inputs changed since screen')
        original = manifest.get('source_sha256', manifest.get('source'))
        if original != {name: digest(Path(source_directory)/name) for name in original}:
            raise ValueError('Frozen source bytes differ from screen manifest')
        current = {n: hashlib.sha256(b).hexdigest() for n, b in build_files().items()}
        self.source_matches_current = all(original.get(n) == value for n, value in current.items())
        self.source_sha256 = original

    def split(self, path):
        return partition(path, len(self.train), self.hashes, self.periods)

    def support(self, tr):
        if self.hashes is None:
            return None
        labels = self.train[self.spec['target']].astype(str).to_numpy()
        return {c: len(np.unique(self.hashes[tr][labels[tr] == c])) for c in self.spec['classes']}

    def outcome(self, record, directory, va):
        if record.get('status') != 'ok':
            return {'status': record.get('status', 'missing')}
        result = verify_predictions(record, directory, self.spec, self.train, va)
        return dict(result, status='verified', seconds=record.get('wall_seconds', record.get('seconds')))


def verify_study(directory, ledger, outer_tr, verifier):
    directory = Path(directory)
    if ledger.get('status') != 'ok':
        return {'status': ledger.get('status', 'missing'), 'completed_trials': ledger.get('completed_trials', 0)}
    tr, va = verifier.split(directory/'split.npz')
    if not np.isin(np.concatenate([tr, va]), outer_tr).all():
        raise ValueError('Inner study escaped outer fitting rows')
    completed, adaptive, scores = 0, 0, []
    for entry in ledger['trials']:
        if entry.get('value') is None:
            continue
        path = directory/f'trial-{entry["number"]:02d}'
        record = json.loads((path/'result.json').read_text())
        if record.get('status') != 'ok':
            raise ValueError('Successful study trial has no successful result')
        verified = verify_predictions(record, path, verifier.spec, verifier.train, va)
        if not math.isclose(verified['value'], entry['value'], abs_tol=1e-10, rel_tol=1e-10):
            raise ValueError('Study objective differs from saved trial predictions')
        if completed >= ledger['startup_trials']:
            adaptive += 1
        completed += 1
        scores.append((verified['value'], entry['recipe']))
    if completed != ledger['completed_trials'] or not completed:
        raise ValueError('Completed study trial count is inconsistent')
    best = (max if verifier.spec['greater_is_better'] else min)(scores, key=lambda item: item[0])
    if best[1] != ledger['selected_recipe'] or not math.isclose(best[0], ledger['best_inner_value'], abs_tol=1e-10, rel_tol=1e-10):
        raise ValueError('Study selected recipe is inconsistent with inner values')
    return {'status': 'verified', 'completed_trials': completed,
            'successful_trials_after_startup': adaptive,
            'sampler': ledger['sampler'], 'seconds': ledger['seconds'],
            'best_inner_value': best[0], 'split_sha256': digest(directory/'split.npz'),
            'inside_outer_fitting_rows_verified': True}


def summarize_hpo(path):
    path = Path(path)
    manifest = json.loads(path.read_text())
    verifier = Verifier(manifest, path.parent/'sources')
    mode = manifest['mode']
    arms = ['random', 'tpe'] if mode == 'hpo' else ['selection']
    expected = manifest['limits'].get('cuts') or ([0, 1, 2] if verifier.periods is not None else [42, 43])
    report = {'mode': mode, 'metric': verifier.spec['metric'], 'cuts': [],
              'source_matches_current': verifier.source_matches_current,
              'source_sha256': verifier.source_sha256, 'expected_cuts': expected,
              'screen_status': manifest['status']}
    for cut in manifest['cuts']:
        directory = path.parent/f'cut-{cut["cut"]}'
        tr, va = verifier.split(directory/'outer-split.npz')
        entry = {'cut': cut['cut'], 'outcomes': {}, 'gates': {},
                 'split_sha256': digest(directory/'outer-split.npz')}
        for name in ['control', *arms]:
            record = cut['outcomes'].get(name, {'status': 'pending'})
            entry['outcomes'][name] = verifier.outcome(record, directory/f'outer-{name}', va)
        control = entry['outcomes']['control']
        for name in arms:
            candidate = entry['outcomes'][name]
            if control['status'] == candidate['status'] == 'verified':
                entry['gates'][name] = paired_gate(control, candidate, verifier.spec, verifier.support(tr))
            if mode == 'hpo' and name in cut:
                entry.setdefault('studies', {})[name] = verify_study(directory/name, cut[name], tr, verifier)
                if (candidate['status'] == 'verified' and cut[name].get('status') == 'ok'
                        and cut['outcomes'][name]['recipe'] != cut[name]['selected_recipe']):
                    raise ValueError('Outer model differs from inner-selected recipe')
        if mode == 'hpo' and all(entry.get('studies', {}).get(n, {}).get('status') == 'verified' for n in arms):
            left = verifier.split(directory/'random/split.npz')
            right = verifier.split(directory/'tpe/split.npz')
            if not all(np.array_equal(a, b) for a, b in zip(left, right)):
                raise ValueError('Random and TPE used different inner partitions')
            entry['matched_inner_partitions_verified'] = True
        report['cuts'].append(entry)
    complete = (manifest['status'] == 'completed' and [c['cut'] for c in report['cuts']] == expected
                and all(all(o['status'] == 'verified' for o in c['outcomes'].values()) for c in report['cuts']))
    report['complete_verified_screen'] = complete
    report['mean'] = {name: float(np.mean([c['outcomes'][name]['value'] for c in report['cuts']]))
                      for name in ['control', *arms] if report['cuts'] and all(c['outcomes'][name]['status'] == 'verified' for c in report['cuts'])}
    report['paired_gate_passed'] = {name: complete and all(c['gates'].get(name, {}).get('passed', False) for c in report['cuts']) for name in arms}
    if mode == 'hpo':
        report['tpe_mean_beats_random'] = (complete and (report['mean']['tpe'] > report['mean']['random']
            if verifier.spec['greater_is_better'] else report['mean']['tpe'] < report['mean']['random']))
        report['measured_screen_gate_passed'] = (report['paired_gate_passed']['tpe'] and report['tpe_mean_beats_random']
            and all(c['studies'].get('tpe', {}).get('status') == 'verified' for c in report['cuts']))
    else:
        report['measured_screen_gate_passed'] = report['paired_gate_passed']['selection']
    report['advance_gate_passed'] = report['measured_screen_gate_passed'] and verifier.source_matches_current
    return report


def summarize_candidates(path):
    path = Path(path)
    manifest = json.loads(path.read_text())
    verifier = Verifier(manifest, path.parent/'sources')
    control_name = manifest['candidates'][0]['name']
    expected = [0, 1, 2] if verifier.periods is not None else [42, 43]
    outcomes, partitions = {}, {}
    report = {'mode': 'candidate_screen', 'metric': verifier.spec['metric'], 'control': control_name,
              'source_matches_current': verifier.source_matches_current, 'source_sha256': verifier.source_sha256,
              'expected_cuts': expected, 'candidates': {}}
    for record in manifest['results']:
        key = (record['name'], record['seed'])
        if key in outcomes:
            raise ValueError('Duplicate candidate/cut result')
        directory = Path(record['directory'])
        tr, va = verifier.split(directory/'split.npz')
        if record['seed'] in partitions:
            previous = partitions[record['seed']]
            if not all(np.array_equal(a, b) for a, b in zip(previous, [tr, va])):
                raise ValueError('Candidate and control partitions differ')
        partitions[record['seed']] = (tr, va)
        outcomes[key] = verifier.outcome(record, directory, va)
    for candidate in manifest['candidates'][1:]:
        name = candidate['name']
        entry = {'cuts': [], 'feature_code': bool(candidate['recipe'].get('feature_code'))}
        for cut in expected:
            control = outcomes.get((control_name, cut), {'status': 'pending'})
            treatment = outcomes.get((name, cut), {'status': 'pending'})
            row = {'cut': cut, 'control': control, 'candidate': treatment}
            if control['status'] == treatment['status'] == 'verified':
                row['gate'] = paired_gate(control, treatment, verifier.spec, verifier.support(partitions[cut][0]))
            entry['cuts'].append(row)
        entry['complete_verified_screen'] = all(c['control']['status'] == c['candidate']['status'] == 'verified' for c in entry['cuts'])
        entry['measured_screen_gate_passed'] = entry['complete_verified_screen'] and all(c['gate']['passed'] for c in entry['cuts'])
        entry['advance_gate_passed'] = entry['measured_screen_gate_passed'] and verifier.source_matches_current
        if entry['complete_verified_screen']:
            entry['control_mean'] = float(np.mean([c['control']['value'] for c in entry['cuts']]))
            entry['candidate_mean'] = float(np.mean([c['candidate']['value'] for c in entry['cuts']]))
        report['candidates'][name] = entry
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queue', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    queue = json.loads(args.queue.read_text())
    report = {'scope': 'Independently recomputed reused-public development screens; positive gates require further qualification, not a release',
              'queue_status': queue['status'], 'queue_source_unchanged': queue['source_unchanged'],
              'screens': {}, 'planner_generation': {}, 'errors': {}, 'official_submission': False}
    for directory in args.queue.parent.iterdir():
        proposals = directory/'proposals.json'
        if directory.is_dir() and proposals.is_file():
            document = json.loads(proposals.read_text())
            report['planner_generation'][directory.name] = {mode: {key: value.get(key) for key in
                ['call', 'distinct_candidates', 'raw_supported_proposals', 'candidate_limit', 'rejected', 'diagnostics']}
                for mode, value in document['modes'].items()}
        path = directory/'results.json'
        if not directory.is_dir() or not path.is_file():
            continue
        try:
            document = json.loads(path.read_text())
            report['screens'][directory.name] = summarize_hpo(path) if 'mode' in document else summarize_candidates(path)
        except Exception as exc:
            report['errors'][directory.name] = {'exception_type': type(exc).__name__, 'reason': str(exc)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'queue_status': report['queue_status'], 'screens': list(report['screens']), 'errors': report['errors']}))
    if report['errors']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
