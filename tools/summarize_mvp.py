"""Independently verify MVP prediction artifacts and export metadata-only results."""
from pathlib import Path
import argparse
import hashlib
import json
import math

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score
from summarize_research import partition


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def selected_records(report):
    ensemble = report.get('ensemble')
    if ensemble:
        return ensemble['primary'], ensemble['confirmation']
    chosen = report.get('selected_recipe')
    primary = next((r for r in report['experiments'] if r['recipe'] == chosen and r['status'] == 'ok'), None)
    confirmation = next((r for r in report['confirmations'] if r['recipe'] == chosen and r['status'] == 'ok'), None)
    if not primary or not confirmation:
        raise ValueError('Both selected search/confirmation artifacts are required')
    return primary, confirmation


def verify_validation(record, spec, train, split):
    directory = Path(record['output_dir'])
    path = directory/'validation_predictions.csv'
    frame = pd.read_csv(path)
    hashes = (pd.util.hash_pandas_object(train[spec['features']], index=False).to_numpy(dtype='uint64')
              if spec['kind'] == 'classification' else None)
    periods = (train[spec['time_column']].to_numpy() if spec.get('validation_strategy') == 'time' else None)
    fitting, rows = partition(split, len(train), hashes, periods)
    if not np.array_equal(rows, frame.row_position.to_numpy()) or len(np.unique(rows)) != len(rows):
        raise ValueError('Prediction row order/coverage does not match immutable split')
    truth = train[spec['target']].iloc[rows]
    diagnostics = {}
    if spec['kind'] == 'classification':
        if not np.array_equal(truth.astype(str), frame.y_true.astype(str)):
            raise ValueError('Classification truth does not match source rows')
        if frame.y_pred.isna().any() or not set(frame.y_pred.astype(str)) <= set(spec['classes']):
            raise ValueError('Invalid validation class prediction')
        value = float(f1_score(truth.astype(str), frame.y_pred.astype(str), average='macro', zero_division=0))
        values = f1_score(truth.astype(str), frame.y_pred.astype(str), labels=spec['classes'], average=None, zero_division=0)
        per_class = dict(zip(spec['classes'], map(float, values)))
        declared = record['metrics'].get('per_class_f1')
        if declared and any(not math.isclose(per_class[c], declared[c], abs_tol=1e-10, rel_tol=1e-10) for c in spec['classes']):
            raise ValueError('Recomputed per-class F1 disagrees with worker')
        labels = train[spec['target']].astype(str).to_numpy()
        diagnostics = {'per_class_f1': per_class,
            'independent_fitting_groups': {c: len(np.unique(hashes[fitting][labels[fitting] == c])) for c in spec['classes']},
            'validation_class_rows': {c: int(np.sum(labels[rows] == c)) for c in spec['classes']},
            'independent_validation_groups': {c: len(np.unique(hashes[rows][labels[rows] == c])) for c in spec['classes']},
            'feature_groups_disjoint_verified': True}
    else:
        if not np.allclose(truth, frame.y_true, rtol=1e-12, atol=1e-12):
            raise ValueError('Regression truth does not match source rows')
        value = float(np.sqrt(np.mean((truth.to_numpy()-frame.y_pred.to_numpy())**2)))
    if not math.isfinite(value) or not math.isclose(value, record['metrics'][spec['metric']], rel_tol=1e-10, abs_tol=1e-10):
        raise ValueError('Independently computed metric disagrees with worker')
    return {'value': value, 'rows': len(rows), 'prediction_sha256': digest(path),
            'split_sha256': digest(split), 'row_order_verified': True, **diagnostics}


def selectors(record):
    values = [p['feature_selection'] for p in record.get('data_policy_runs', []) if p.get('feature_selection')]
    for component in record.get('components', []):
        values.extend(selectors(component))
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    campaign = json.loads(args.campaign.read_text())
    control_path = Path(__file__).resolve().parents[1]/'release/v16-mean1/full-default-parity.json'
    baseline = json.loads(control_path.read_text())['tasks']
    summary = {'scope': 'Exploratory complete procedure on reused public cuts, not OOF/private/official score; multiple factors changed',
               'campaign_status': campaign['status'], 'archive_sha256': campaign['archive_sha256'],
               'qualified_control': 'V11/V16 saved full-default procedure; no new control refit',
               'tasks': {}, 'official_submission': False}
    for entry in campaign['tasks']:
        path = Path(entry['report_path'])
        report = json.loads(path.read_text())
        spec = report['spec']
        train = pd.read_csv(spec['paths']['train'])
        test = pd.read_csv(spec['paths']['test'])
        sample = pd.read_csv(spec['paths']['sample_submission'])
        primary, secondary = selected_records(report)
        runs = path.parent
        first = verify_validation(primary, spec, train, runs/'split.npz')
        second = verify_validation(secondary, spec, train, runs/'confirmation_split.npz')
        csv = Path(report['submission_path'])
        prediction = pd.read_csv(csv)
        if list(prediction) != list(sample) or len(prediction) != len(test) or not np.array_equal(prediction[spec['id']], sample[spec['id']]):
            raise ValueError('Final CSV schema, IDs or row order mismatch')
        if prediction[spec['id']].duplicated().any() or prediction[spec['target']].isna().any():
            raise ValueError('Invalid final predictions')
        if spec['kind'] == 'regression':
            if not np.isfinite(prediction[spec['target']]).all(): raise ValueError('Nonfinite regression output')
        elif not set(prediction[spec['target']].astype(str)) <= set(spec['classes']):
            raise ValueError('Unknown predicted class')
        if digest(csv) != report['submission_sha256'] or report['final_fit_status'] != 'ok' or not report['integrity_ok']:
            raise ValueError('Final refit/CSV/integrity failure')
        mean = (first['value']+second['value'])/2
        known = baseline[spec['kind']]
        selector_runs = [s for r in report['experiments'] for s in selectors(r)]
        hpo = report.get('hpo') or {}
        summary['tasks'][spec['kind']] = {
            'metric': spec['metric'], 'search': first, 'confirmation': second, 'mean': mean,
            'control_search': known['search'], 'control_confirmation': known['confirmation'],
            'control_mean': known['mean'], 'mean_delta': mean-known['mean'],
            'search_experiments': len(report['experiments']),
            'failed_experiments': sum(r['status'] != 'ok' for r in report['experiments']),
            'hpo_status': hpo.get('status'), 'hpo_completed_trials': hpo.get('completed_trials'),
            'planner_calls': report.get('llm_calls'), 'selector_fit_count_in_search': len(selector_runs),
            'selector_selected_count_in_search': sum(s['status'] == 'selected' for s in selector_runs),
            'seconds': report['elapsed_seconds'], 'selected_recipe': report['selected_recipe'],
            'final_fit_iterations': report['final_fit_iterations'],
            'submission_sha256': digest(csv), 'final_csv_verified': True, 'integrity_ok': True}
    if not args.allow_partial and (campaign['status'] != 'completed' or len(summary['tasks']) != 2):
        raise ValueError('Complete two-task campaign required')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: {p: v[p] for p in ['mean', 'control_mean', 'mean_delta', 'seconds']} for k, v in summary['tasks'].items()}))


if __name__ == '__main__':
    main()
