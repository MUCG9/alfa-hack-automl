"""Two tiny synthetic CatBoost contract fits; root must provide the bounded guard.

No historical/current data, evaluator, API client, retry or extra baseline fit.
This is a technical fixture, never evidence of model quality improvement.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import os
import sys
import time

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
for variable in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
    os.environ[variable] = '1'

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
ADAPTER = HERE / 'src/automl/execution/model_adapters/catboost.py'
ADAPTER_SHA256 = '74071bdf978327ff53aedc1e3209da75107aa76cd2040f9c1fda8befcdb9222b'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def macro_f1(truth, predicted, classes):
    values = []
    for label in classes:
        tp = sum(a == label and b == label for a, b in zip(truth, predicted))
        fp = sum(a != label and b == label for a, b in zip(truth, predicted))
        fn = sum(a == label and b != label for a, b in zip(truth, predicted))
        denominator = 2 * tp + fp + fn
        values.append(0. if not denominator else 2 * tp / denominator)
    return sum(values) / len(values)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--deadline-monotonic', type=float)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(HERE) and output.parent.is_dir() and not output.exists()
    started = time.monotonic()
    deadline = min(started + 25, args.deadline_monotonic) if args.deadline_monotonic else started + 25
    result = {'status': 'starting', 'scope': 'synthetic_technical_fixture_only',
              'actual_fits_attempted': 0, 'API_calls': 0, 'current_or_historical_data_read': False,
              'fixture_rows': {'fitting': 36, 'validation': 12}, 'threads': 1,
              'iterations_per_fit': 10, 'subcases': [], 'model_quality_claim': False,
              'promotion': False}
    exit_code = 1
    try:
        assert __debug__ and math.isfinite(deadline) and time.monotonic() < deadline
        assert digest(ADAPTER) == ADAPTER_SHA256
        sys.path.insert(0, str(WORK / 'm2dev/src'))
        source = importlib.util.spec_from_file_location('catboost_metric_fix_fixture', ADAPTER)
        adapter = importlib.util.module_from_spec(source)
        source.loader.exec_module(adapter)
        import numpy as np
        import catboost

        # Fixed fixture only. Unequal 24/8/4 fitting class counts make Balanced
        # weights nonuniform; validation has all three classes represented.
        fitting_x = np.column_stack((np.arange(36) % 7, np.arange(36) / 36))
        fitting_y = np.asarray(['A'] * 24 + ['B'] * 8 + ['C'] * 4)
        validation_x = np.column_stack((np.arange(12) % 7, (np.arange(12) + .5) / 12))
        validation_y = np.asarray(['A', 'B', 'C'] * 4)
        classes = ['A', 'B', 'C']
        result.update(numpy_version=np.__version__, catboost_version=catboost.__version__)
        for name, weighted in [('unit_weights', False), ('auto_balanced_weights', True)]:
            assert time.monotonic() < deadline and result['actual_fits_attempted'] < 2
            params = {'depth': 4, 'learning_rate': .05, 'l2_leaf_reg': 3,
                      'early_metric': 'primary', 'seed': 137}
            if weighted:
                params['class_weights'] = True  # Legacy adapter path -> auto Balanced.
            recipe = {'engine': 'catboost', 'metric': 'macro_f1', 'params': params,
                      'feature_code': ''}
            model = adapter.create_model(recipe, 'classification', 1, 10)
            expected = 'TotalF1:average=Macro' + (';use_weights=false' if weighted else '')
            assert model.get_params()['eval_metric'] == expected
            assert model.get_params()['thread_count'] == 1
            assert model.get_params()['iterations'] == 10
            assert model.get_params().get('auto_class_weights') == ('Balanced' if weighted else None)
            result['actual_fits_attempted'] += 1
            model.fit(fitting_x, fitting_y, eval_set=(validation_x, validation_y),
                      use_best_model=False)
            assert time.monotonic() < deadline and model.tree_count_ == 10
            actual_classes = list(map(str, model.classes_))
            assert actual_classes == classes
            probabilities = np.asarray(model.predict_proba(validation_x))
            assert probabilities.shape == (12, 3) and np.isfinite(probabilities).all()
            assert (probabilities >= 0).all() and (probabilities <= 1).all()
            assert np.allclose(probabilities.sum(axis=1), 1., atol=1e-12, rtol=1e-12)
            predicted = np.asarray(classes)[probabilities.argmax(axis=1)]
            assert np.array_equal(predicted, np.asarray(model.predict(validation_x)).reshape(-1))
            manual = macro_f1(validation_y, predicted, classes)
            diagnostics = model.get_evals_result()['validation']
            metric_keys = [key for key in diagnostics if key.startswith('TotalF1:')
                           and 'average=Macro' in key
                           and (not weighted or 'use_weights=false' in key)]
            assert len(metric_keys) == 1
            recorded = float(diagnostics[metric_keys[0]][-1])
            assert math.isfinite(recorded) and abs(recorded - manual) <= 1e-12
            realized_class_weights = model.get_all_params().get('class_weights', [])
            nonuniform = bool(realized_class_weights and
                              max(realized_class_weights) - min(realized_class_weights) > 1e-12)
            assert not weighted or nonuniform
            result['subcases'].append({'name': name, 'status': 'passed',
                'eval_metric': expected, 'class_order_verified': True,
                'finite_normalized_probabilities': True,
                'unweighted_macro_f1_matches_CatBoost_metric': True,
                'absolute_metric_difference': abs(recorded - manual),
                'nonuniform_auto_class_weights_verified': nonuniform,
                'synthetic_fixture_macro_f1': manual, 'model_quality_claim': False})
        assert result['actual_fits_attempted'] == 2 and digest(ADAPTER) == ADAPTER_SHA256
        assert time.monotonic() < deadline
        result.update(status='passed', adapter_source_unchanged=True,
                      adapter_sha256=ADAPTER_SHA256)
        exit_code = 0
    except BaseException as exc:
        result.update(status='technical_failure', exception_type=type(exc).__name__)
    result['seconds'] = time.monotonic() - started
    if time.monotonic() >= deadline:
        result.update(status='technical_failure', failure_code='fixture_deadline_exhausted')
        exit_code = 1
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'status': result['status'], 'actual_fits_attempted': result['actual_fits_attempted'],
                      'seconds': result['seconds'], 'model_quality_claim': False}))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
