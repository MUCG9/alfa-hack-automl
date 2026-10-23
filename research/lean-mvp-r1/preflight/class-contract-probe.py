"""One old tm1 classification worker through frozen R4 core; bounded NOFIT probe.

No full-campaign audit, historical clock qualification, model runtime, API ledger,
quality claim or printed ML score. The parent supplies lock, memory and timeout.
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
for name in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
    os.environ[name] = '1'
WORK = Path(__file__).resolve().parent


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            value.update(block)
    return value.hexdigest()


def inside(value):
    path = Path(value)
    path = path.resolve() if path.is_absolute() else (WORK / path).resolve()
    assert path.is_relative_to(WORK)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--deadline-monotonic', type=float)
    args = parser.parse_args()
    output = inside(args.output)
    assert output.parent.is_dir() and not output.exists()
    started = time.monotonic()
    deadline = min(started + 25, args.deadline_monotonic) if args.deadline_monotonic else started + 25
    result = {'status': 'starting', 'stage': 'plan', 'model_fits': 0, 'API_calls': 0,
              'full_MVP_audit': False, 'historical_clock_requalified': False,
              'ML_score_printed': False, 'quality_or_official_score_claim': False,
              'promotion': False}
    exit_code = 1
    try:
        assert __debug__ and math.isfinite(deadline) and time.monotonic() < deadline
        plan_path = inside(args.plan)
        plan = json.loads(plan_path.read_text('utf-8'))
        assert plan['scope'] == 'one_successful_old_tm1_classification_worker_contract_only'
        assert plan['worker_path'].startswith('alfa-hack-automl/test-runs/tm1/c/')
        assert plan['pristine_directory'] == 'evaluation/multiclass'
        assert plan['maximum_workers'] == 1 and plan['maximum_model_fits'] == 0
        assert digest(Path(__file__)) == plan['probe_source_sha256']
        pins = plan['sha256_inputs_and_verifier']
        result['stage'] = 'precheck_hashes'
        for name, expected in pins.items():
            assert digest(inside(name)) == expected
        assert time.monotonic() < deadline
        result['stage'] = 'import_frozen_manual_R4'
        module_spec = importlib.util.spec_from_file_location('frozen_r4_class_contract_probe',
                                                          inside(plan['verifier_path']))
        evaluator = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(evaluator)
        forbidden = ('sklearn', 'catboost', 'lightgbm', 'xgboost', 'torch', 'autogluon')
        assert not any(name == root or name.startswith(root + '.')
                       for name in sys.modules for root in forbidden)
        report = evaluator.load(inside(plan['report_path']))
        record = report['experiments'][plan['experiment_index']]
        assert record['status'] == 'ok' and record['recipe']['engine'] == 'lightgbm'
        assert record['recipe'].get('params', {}).get('feature_views') is None
        assert inside(record['output_dir']) == inside(plan['worker_path'])
        assert report['spec']['kind'] == 'classification'
        assert report['spec']['metric'] == 'macro_f1' and report['spec']['prediction_type'] == 'value'
        directory = inside(plan['task_directory'])
        pristine = inside(plan['pristine_directory'])
        for name in ['train.csv', 'test.csv', 'sample_submission.csv', 'task.md', 'data_dictionary.csv']:
            assert digest(directory / name) == digest(pristine / name)
        result['stage'] = 'load_pristine_inputs'
        train, test, sample = [evaluator.pd.read_csv(pristine / name)
                               for name in ['train.csv', 'test.csv', 'sample_submission.csv']]
        verifier = evaluator.TaskVerifier(directory, report, train, test, sample)
        partition = inside(plan['partition_path'])
        tr, va = evaluator.split(partition, len(train))
        assert evaluator.index_sha(tr, va) == plan['positions_sha256']
        assert report['split']['split_sha256'] == plan['positions_sha256']
        assert not evaluator.np.intersect1d(verifier.hashes[tr], verifier.hashes[va]).size
        assert time.monotonic() < deadline
        result['stage'] = 'one_worker_core_verify'
        checked = verifier.verify(record, partition, 'primary', full=False,
                                  expected_recipe=record['recipe'])
        assert len(verifier.records) == 1 and checked['mixture_children'] == 0
        assert evaluator.close(checked['value'], record['metrics']['macro_f1'])
        stored = evaluator.load(inside(plan['worker_path']) / 'result.json')
        assert evaluator.close(checked['value'], stored['metrics']['macro_f1'])
        assert set(checked['per_class_f1']) == set(verifier.classes)
        assert all(evaluator.close(value, stored['metrics']['per_class_f1'][label])
                   for label, value in checked['per_class_f1'].items())
        result['stage'] = 'postcheck_hashes'
        for name, expected in pins.items():
            assert digest(inside(name)) == expected
        assert not any(name == root or name.startswith(root + '.')
                       for name in sys.modules for root in forbidden)
        assert time.monotonic() < deadline
        result.update(status='classification_worker_contract_probe_passed', stage='complete',
            worker_count=1, classes_count=len(verifier.classes),
            canonical_value_enum_verified=True, pristine_input_hashes_and_labels_verified=True,
            validation_row_positions_and_ID_order_verified=True,
            class_order_finite_normalized_proba_and_argmax_verified=True,
            original_feature_group_split_disjoint=True,
            manual_all_class_macro_F1_and_per_class_match_saved=True,
            source_and_input_SHA_unchanged=True, model_runtime_imports=False,
            plan_sha256=digest(plan_path), verifier_sha256=pins[plan['verifier_path']],
            sha256_inputs_and_verifier=pins)
        exit_code = 0
    except BaseException as exc:
        result.update(status='technical_failure', exception_type=type(exc).__name__)
    result['seconds'] = time.monotonic() - started
    if time.monotonic() >= deadline:
        result.update(status='technical_failure', failure_code='probe_deadline_exhausted')
        exit_code = 1
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'status': result['status'], 'stage': result['stage'],
                      'seconds': result['seconds'], 'model_fits': 0, 'ML_score_printed': False}))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
