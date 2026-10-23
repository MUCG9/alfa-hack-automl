"""Diagnose paired benchmark predictions without fitting or choosing blend weights.

Examples:
    python tools/analyze_diversity.py --results run/results.json --control baseline \
        --candidate alternative --output run/diversity.json
    python tools/analyze_diversity.py --results run --control baseline \
        --expand-components --output run/components-diversity.json

With no --candidate, compare every available candidate to the control. Component
names are ``parent::component-0``, etc.; they use their parent's frozen split.
Only explicit, complete, exactly-once CV partitions receive pooled OOF metrics.
The output contains aggregate diagnostics and hashes, never prediction rows.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from automl.evaluation.api import evaluate


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _positions(values, label):
    values = np.asarray(values)
    if values.ndim != 1 or values.dtype.kind not in 'iu':
        raise ValueError(f'{label}: expected a one-dimensional integer row array')
    values = values.astype(np.int64)
    if not len(values) or np.any(values < 0) or len(np.unique(values)) != len(values):
        raise ValueError(f'{label}: empty, negative or duplicate row positions')
    return values


def _row_hash(rows):
    return hashlib.sha256(np.asarray(rows, dtype='<i8').tobytes()).hexdigest()


def _inside(root, path):
    path = Path(path)
    path = (root / path if not path.is_absolute() else path).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Benchmark artifact must be inside the results directory')
    return path


def _finite(value):
    """Undefined secondary metrics (e.g. one-row R2) serialize as null."""
    if isinstance(value, dict):
        return {str(k): _finite(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_finite(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    return value


def _score(spec, truth, predictions, probabilities=None):
    metrics = _finite(evaluate(truth, predictions, spec['kind'], spec['metric'],
                               probabilities, spec.get('classes')))
    primary = metrics.get(spec['metric'])
    if primary is None or not np.isfinite(primary):
        raise ValueError('Recomputed primary metric is not finite')
    return metrics


def _index(manifest, expand_components):
    recipes = {}
    for candidate in manifest['candidates']:
        name = candidate['name']
        if not isinstance(name, str) or not name or name in recipes:
            raise ValueError('Empty or duplicate candidate name')
        recipes[name] = candidate['recipe']
    indexed = {name: {} for name in recipes}
    for entry in manifest['results']:
        name, seed = entry['name'], entry['seed']
        if name not in indexed or type(seed) is not int:
            raise ValueError('Unknown result candidate or non-integer seed')
        if seed in indexed[name]:
            raise ValueError('Duplicate candidate/fold result')
        indexed[name][seed] = dict(entry, expected_recipe=recipes[name])
    if expand_components:
        for name, recipe in recipes.items():
            if recipe.get('engine') != 'ensemble':
                continue
            components = recipe.get('components', [])
            if not components:
                raise ValueError('Ensemble has no declared components')
            for number, component in enumerate(components):
                child_name = f'{name}::component-{number}'
                if child_name in indexed:
                    raise ValueError('Generated component name collides with a candidate')
                indexed[child_name] = {}
                for seed, entry in indexed[name].items():
                    indexed[child_name][seed] = dict(
                        entry, name=child_name,
                        directory=str(Path(entry['directory']) / f'component-{number}'),
                        split_directory=entry['directory'], expected_recipe=component,
                        component=True)
    return indexed


def _load(root, entry, spec):
    if entry.get('status') != 'ok' or entry.get('exit_code', 0) != 0:
        raise ValueError(f"{entry['name']}: benchmark fold did not complete successfully")
    directory = _inside(root, entry['directory'])
    split_directory = _inside(root, entry.get('split_directory', entry['directory']))
    paths = {name: _inside(root, directory / filename) for name, filename in {
        'predictions': 'validation_predictions.csv', 'result': 'result.json'}.items()}
    paths['split'] = _inside(root, split_directory / 'split.npz')
    if spec['kind'] == 'classification':
        paths['probabilities'] = _inside(root, directory / 'validation_probabilities.npz')
    if any(not path.is_file() for path in paths.values()):
        raise ValueError(f"{entry['name']}: missing validation artifact")
    result = json.loads(paths['result'].read_text())
    if result.get('status') != 'ok' or result.get('full_fit', False):
        raise ValueError('Expected successful validation result, not a full-fit result')
    if result.get('recipe') != entry['expected_recipe']:
        raise ValueError('Result recipe differs from frozen candidate recipe')
    with np.load(paths['split'], allow_pickle=False) as split:
        training = _positions(split['train'], 'split training')
        rows = _positions(split['validation'], 'split validation')
    info = entry['split']
    signature = hashlib.sha256(np.asarray(training, dtype='<i8').tobytes()
                               + np.asarray(rows, dtype='<i8').tobytes()).hexdigest()
    if signature != info.get('split_sha256'):
        raise ValueError('Split SHA differs from manifest')
    if len(np.intersect1d(training, rows)):
        raise ValueError('Training and validation rows overlap')
    if info.get('train_rows') != len(training) or info.get('validation_rows') != len(rows):
        raise ValueError('Split row counts differ from manifest')
    with paths['predictions'].open(newline='') as stream:
        header = next(csv.reader(stream), [])
    if len(header) != 3 or set(header) != {'row_position', 'y_true', 'y_pred'}:
        raise ValueError('Unexpected or duplicate prediction CSV columns')
    frame = pd.read_csv(paths['predictions'], dtype=str, keep_default_na=False)
    if not frame.row_position.str.fullmatch(r'\d+').all():
        raise ValueError('Prediction row positions must be non-negative integers')
    actual_rows = _positions(frame.row_position.to_numpy(dtype=np.int64), 'prediction CSV')
    if not np.array_equal(actual_rows, rows):
        raise ValueError('Prediction CSV row order differs from frozen split')
    probabilities = None
    if spec['kind'] == 'classification':
        classes = spec['classes']
        truth = frame.y_true.to_numpy()
        predictions = frame.y_pred.to_numpy()
        if not set(truth).issubset(classes) or not set(predictions).issubset(classes):
            raise ValueError('Prediction CSV contains an unknown class')
        with np.load(paths['probabilities'], allow_pickle=False) as stored:
            stored_rows = _positions(stored['row_position'], 'probabilities')
            raw_classes = stored['classes']
            if raw_classes.ndim != 1:
                raise ValueError('Probability classes must be one-dimensional')
            stored_classes = raw_classes.astype(str).tolist()
            raw = np.asarray(stored['probabilities'], dtype=float)
        if not np.array_equal(stored_rows, rows):
            raise ValueError('Probability row order differs from frozen split')
        if len(set(stored_classes)) != len(stored_classes) or set(stored_classes) != set(classes):
            raise ValueError('Probability class set differs from manifest or contains duplicates')
        if raw.shape != (len(rows), len(classes)):
            raise ValueError('Probability matrix shape differs from rows/classes')
        if not np.isfinite(raw).all() or np.any(raw < 0) or np.any(raw > 1):
            raise ValueError('Probabilities must be finite values in [0, 1]')
        totals = raw.sum(axis=1, keepdims=True)
        if np.any(totals <= 0):
            raise ValueError('Probability row has zero mass')
        if not np.array_equal(np.asarray(stored_classes)[raw.argmax(axis=1)], predictions):
            raise ValueError('CSV predictions differ from probability decisions')
        probabilities = (raw / totals)[:, [stored_classes.index(c) for c in classes]]
    else:
        truth = frame.y_true.to_numpy(dtype=float)
        predictions = frame.y_pred.to_numpy(dtype=float)
        if not np.isfinite(truth).all() or not np.isfinite(predictions).all():
            raise ValueError('Regression truth/predictions must be finite')
    metrics = _score(spec, truth, predictions, probabilities)
    expected = [result.get('metrics')]
    if not entry.get('component'):
        expected.append(entry.get('metrics'))
    for recorded in expected:
        value = (recorded or {}).get(spec['metric'])
        if not isinstance(value, (int, float)) or not np.isfinite(value):
            raise ValueError('Missing or non-finite recorded primary metric')
        if not np.isclose(metrics[spec['metric']], value, rtol=1e-8, atol=1e-10):
            raise ValueError('Recomputed primary metric differs from recorded metric')
    return dict(rows=rows, training=training, truth=truth, predictions=predictions,
                probabilities=probabilities, metrics=metrics, split=info,
                artifacts_sha256={name: _sha(path) for name, path in paths.items()})


def _conditional(numerator, denominator):
    return {'numerator': int(numerator), 'denominator': int(denominator),
            'rate': float(numerator / denominator) if denominator else None}


def _errors(truth, control, candidate):
    wrong_a, wrong_b = control != truth, candidate != truth
    both = int(np.sum(wrong_a & wrong_b))
    count = len(truth)
    return {
        'support': count, 'control_error_rate': float(wrong_a.mean()) if count else None,
        'candidate_error_rate': float(wrong_b.mean()) if count else None,
        'both_wrong_count': both, 'shared_error_rate': both / count if count else None,
        'double_fault_rate': both / count if count else None,
        'disagreement_rate': float(np.mean(control != candidate)) if count else None,
        'candidate_correct_given_control_wrong': _conditional(
            np.sum(wrong_a & ~wrong_b), np.sum(wrong_a)),
        'control_correct_given_candidate_wrong': _conditional(
            np.sum(~wrong_a & wrong_b), np.sum(wrong_b)),
    }


def _pair(spec, control, candidate):
    truth = control['truth']
    if not np.array_equal(control['rows'], candidate['rows']):
        raise ValueError('Control/candidate row positions or order differ')
    if not np.array_equal(truth, candidate['truth']):
        raise ValueError('Control/candidate validation truth differs')
    if spec['kind'] == 'classification':
        blend = .5 * control['probabilities'] + .5 * candidate['probabilities']
        prediction = np.asarray(spec['classes'])[blend.argmax(axis=1)]
        diversity = _errors(truth, control['predictions'], candidate['predictions'])
        diversity['per_class'] = {}
        for label in spec['classes']:
            mask = truth == label
            diversity['per_class'][label] = _errors(truth[mask], control['predictions'][mask],
                                                   candidate['predictions'][mask])
        blended_metrics = _score(spec, truth, prediction, blend)
    else:
        residual_a = control['predictions'] - truth
        residual_b = candidate['predictions'] - truth
        if not np.isfinite(residual_a).all() or not np.isfinite(residual_b).all():
            raise ValueError('Residual arithmetic is not finite')
        constant = len(truth) < 2 or np.ptp(residual_a) == 0 or np.ptp(residual_b) == 0
        correlation = None if constant else float(np.corrcoef(residual_a, residual_b)[0, 1])
        if correlation is not None and not np.isfinite(correlation):
            correlation = None
        diversity = {'support': len(truth), 'residual_correlation': correlation,
                     'residual_correlation_undefined': correlation is None}
        blended_metrics = _score(spec, truth, .5 * control['predictions'] + .5 * candidate['predictions'])
    metrics = {'control': control['metrics'], 'candidate': candidate['metrics'],
               'fixed_blend': blended_metrics}
    primary = {role: values[spec['metric']] for role, values in metrics.items()}
    primary['candidate_minus_control'] = primary['candidate'] - primary['control']
    primary['blend_minus_control'] = primary['fixed_blend'] - primary['control']
    return {'metrics': metrics, 'primary_metric': primary, 'diversity': diversity}


def _oof_partitions(folds):
    """Require explicit CV metadata and independently prove full row coverage."""
    explicit = ['fold' in f['split'] or 'n_splits' in f['split'] for f in folds]
    if not any(explicit):
        return False
    counts = {f['split'].get('n_splits') for f in folds}
    if (not all(explicit) or counts != {len(folds)}
            or {f['split'].get('fold') for f in folds} != set(range(len(folds)))):
        raise ValueError('Incomplete or inconsistent explicit OOF folds')
    universe = np.sort(np.concatenate([folds[0]['training'], folds[0]['rows']]))
    if not np.array_equal(universe, np.arange(len(universe))):
        raise ValueError('OOF row universe must be all original row positions')
    for fold in folds:
        if not np.array_equal(np.sort(np.concatenate([fold['training'], fold['rows']])), universe):
            raise ValueError('OOF folds have different row universes')
    if not np.array_equal(np.sort(np.concatenate([f['rows'] for f in folds])), universe):
        raise ValueError('OOF validation coverage is not exactly once')
    return True


def _pool(spec, folds):
    rows = np.concatenate([f['rows'] for f in folds])
    order = np.argsort(rows)
    pooled = {key: np.concatenate([f[key] for f in folds])[order]
              for key in ['rows', 'truth', 'predictions']}
    pooled['probabilities'] = (np.concatenate([f['probabilities'] for f in folds])[order]
                               if spec['kind'] == 'classification' else None)
    pooled['metrics'] = _score(spec, pooled['truth'], pooled['predictions'], pooled['probabilities'])
    return pooled


def analyze(results, control, candidates=None, expand_components=False):
    results = Path(results).resolve()
    if results.is_dir():
        results /= 'results.json'
    manifest = json.loads(results.read_text())
    root, spec = results.parent, manifest['spec']
    if spec.get('kind') not in {'classification', 'regression'} or spec.get('metric') == 'ndcg':
        raise ValueError('Only classification/regression metrics without query context are supported')
    classes = spec.get('classes')
    if spec['kind'] == 'classification' and (
            not isinstance(classes, list) or not classes or any(not isinstance(c, str) for c in classes)
            or len(set(classes)) != len(classes)):
        raise ValueError('Manifest needs unique string classes in declared order')
    fingerprints = {}
    for field in ['source', 'harness', 'inputs']:
        values = manifest.get(field)
        if not isinstance(values, dict) or not values or any(
                not isinstance(v, str) or re.fullmatch(r'[0-9a-f]{64}', v) is None for v in values.values()):
            raise ValueError(f'Missing or malformed {field} fingerprints')
        fingerprints[field] = values
    if re.fullmatch(r'[0-9a-f]{64}', manifest.get('task_sha256', '')) is None:
        raise ValueError('Missing or malformed task fingerprint')
    indexed = _index(manifest, expand_components)
    names = list(candidates) if candidates else [name for name in indexed if name != control]
    if not names or len(names) != len(set(names)) or control in names:
        raise ValueError('Select distinct candidates different from the control')
    if control not in indexed or any(name not in indexed for name in names):
        raise ValueError('Unknown control/candidate name')
    reference = indexed[control]
    if not reference:
        raise ValueError('Control has no completed folds')
    loaded = {}
    for name in [control] + names:
        if set(indexed[name]) != set(reference):
            raise ValueError('Control/candidate fold sets differ')
        loaded[name] = [_load(root, indexed[name][seed], spec) for seed in sorted(reference)]
    control_folds = loaded[control]
    full_oof = _oof_partitions(control_folds)
    comparisons = []
    for name in names:
        folds = []
        if _oof_partitions(loaded[name]) != full_oof:
            raise ValueError('Control/candidate evaluation strategies differ')
        for seed, a, b in zip(sorted(reference), control_folds, loaded[name]):
            if a['split']['split_sha256'] != b['split']['split_sha256']:
                raise ValueError('Control/candidate split SHA differs')
            if not np.array_equal(a['training'], b['training']):
                raise ValueError('Control/candidate training row order differs')
            folds.append(dict(
                seed=seed, split_sha256=a['split']['split_sha256'],
                alignment={'matched_rows': len(a['rows']), 'row_position_sha256': _row_hash(a['rows']),
                           'exact_row_order': True, 'classes': classes if spec['kind'] == 'classification' else [],
                           'classes_aligned': spec['kind'] == 'classification'},
                artifacts_sha256={'control': a['artifacts_sha256'], 'candidate': b['artifacts_sha256']},
                **_pair(spec, a, b)))
        mean = {key: float(np.mean([fold['primary_metric'][key] for fold in folds]))
                for key in folds[0]['primary_metric']}
        comparison = {'candidate': name, 'folds': folds,
                      'fold_mean': {'fold_count': len(folds), 'primary_metric': mean}}
        if full_oof:
            a, b = _pool(spec, control_folds), _pool(spec, loaded[name])
            comparison['pooled_oof'] = dict(
                coverage='exactly_once', matched_rows=len(a['rows']),
                row_position_sha256=_row_hash(a['rows']), **_pair(spec, a, b))
        else:
            comparison['pooled_oof'] = {
                'status': 'omitted', 'reason': 'Holdouts/backtests are not explicit complete OOF; validation rows may overlap.'}
        comparisons.append(comparison)
    return {
        'schema_version': 1, 'kind': spec['kind'], 'metric': spec['metric'],
        'greater_is_better': spec.get('greater_is_better'), 'control': control,
        'fixed_blend': {'control_weight': .5, 'candidate_weight': .5,
                        'weights_fitted': False, 'classification_ties': 'first manifest class'},
        'provenance': dict(fingerprints, task_sha256=manifest['task_sha256'], results_sha256=_sha(results),
                           analysis_source_sha256={str(p.relative_to(ROOT)): _sha(p) for p in [
                               Path(__file__).resolve(), ROOT / 'src/automl/evaluation/service.py',
                               ROOT / 'src/automl/evaluation/api.py']}),
        'definitions': {'control': 'A', 'candidate': 'B',
                        'shared_error_rate': 'P(A wrong and B wrong); identical to double_fault_rate',
                        'conditional_zero_denominator': 'rate is null; numerator and denominator remain explicit',
                        'residual': 'prediction minus truth'},
        'comparisons': comparisons,
        'limitations': [
            'Reused public predictions: diagnostics only, not validation certification or a private-score estimate.',
            'No training, weight fitting, threshold search, or oracle F1 is performed.',
            'Fold means and pooled OOF metrics are separate; holdout/backtest predictions are never pooled.',
            'Input/source fingerprints are retained from the frozen manifest; original input files are not reread.',
            'No uncertainty interval or refit uncertainty is estimated; undefined residual correlation is null.',
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--control', required=True)
    parser.add_argument('--candidate', action='append', default=[])
    parser.add_argument('--expand-components', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise ValueError('Use a new output path')
    report = analyze(args.results, args.control, args.candidate, args.expand_components)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(encoded)
    print(json.dumps({'output': str(args.output), 'comparisons': len(report['comparisons'])}))


if __name__ == '__main__':
    main()
