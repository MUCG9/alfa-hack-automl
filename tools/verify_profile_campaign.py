"""Independently verify PIPE-02 actual cuts, inner studies and full exports."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import numpy as np
import pandas as pd
from automl.publishing.api import read_submission_values
from automl.search.policy import signature
from automl.search.runner import median_iterations
from replay_blend01 import aligned_probabilities
from summarize_research import Verifier, digest, paired_gate, verify_study


def same_recipe(left, right):
    if left['engine'] != right['engine']:
        return False
    if left['engine'] != 'ensemble':
        return signature(left) == signature(right)
    return (len(left['components']) == len(right['components'])
            and np.allclose(left['weights'], right['weights'], atol=1e-15, rtol=0)
            and all(same_recipe(a, b) for a, b in zip(left['components'], right['components'])))


def full_leaves(record, count):
    if record.get('status') != 'ok' or not record.get('full_fit'):
        raise ValueError('Full deployment contains an unsuccessful/non-full worker')
    if record.get('components'):
        return sum(full_leaves(child, count) for child in record['components'])
    runs = record.get('data_policy_runs', [])
    expected = hashlib.sha256(np.arange(count, dtype=np.int64).tobytes()).hexdigest()
    if (not runs or runs[-1]['source_rows'] != count or runs[-1]['source_parent_sha256'] != expected
            or record['early_stopping_source'] != 'full_refit'):
        raise ValueError('Final learner did not fit all original training rows in order')
    return 1


def full_values(spec, record):
    if spec['kind'] != 'classification':
        return np.asarray(read_submission_values(spec, record['submission']), dtype=float)
    with np.load(Path(record['submission']).parent/'test_probabilities.npz', allow_pickle=False) as data:
        classes = data['classes'].astype(str).tolist()
        if len(set(classes)) != len(classes) or set(classes) != set(spec['classes']):
            raise ValueError('Final class schema mismatch')
        values = data['probabilities'][:, [classes.index(c) for c in spec['classes']]]
    if not np.isfinite(values).all() or (values < 0).any() or not np.allclose(values.sum(axis=1), 1, atol=1e-7):
        raise ValueError('Invalid final class probabilities')
    return values


def verify(path):
    path = Path(path); campaign = json.loads(path.read_text())
    if (campaign['status'] != 'completed' or len(campaign['tasks']) != 2
            or not campaign['source_unchanged'] or not campaign['harness_unchanged']):
        raise ValueError('Complete frozen campaign required')
    results = []
    for task in campaign['tasks']:
        rp = Path(task['report_path']); report = json.loads(rp.read_text()); spec = report['spec']
        directory = rp.parent; copied = directory.parents[1]
        verifier = Verifier({'spec': spec, 'source_sha256': campaign['source_sha256'],
            'input_sha256': {k: v for k, v in task['input_sha256'].items() if k != 'task'}}, copied)
        provenance = json.loads((directory/'provenance.json').read_text())['sha256']
        for name, value in provenance.items():
            if name.startswith('input:'):
                source = spec['paths'][name[6:]]
            elif name == 'task':
                source = spec['task_path']
            elif name.startswith('source:'):
                source = name[7:]
            else:
                raise ValueError('Unknown protected fingerprint')
            if digest(source) != value:
                raise ValueError('Protected source/input fingerprint changed')
        qualified = json.loads((ROOT/'docs/experiments'/('reg_blend01_candidates_20261023.json'
            if spec['kind'] == 'regression' else 'blend01_candidates_20261023.json')).read_text())[0]['recipe']
        if not all(same_recipe(r['recipe'], qualified) for r in report['profile_controls']):
            raise ValueError('Control is not the qualified complete procedure')
        cuts = []; partitions = []
        augmented = report['augmentation_qualified']
        for cut in range(2):
            split = directory/('split.npz' if cut == 0 else 'confirmation_split.npz')
            tr, va = verifier.split(split); partitions.append((tr, va))
            control = report['profile_controls'][cut]; where = Path(control['submission']).parent
            job = json.loads((where/'job.json').read_text())
            if job['full_fit'] or job['threads'] != 2 or job['recipe'] != control['recipe']:
                raise ValueError('Control job contract changed')
            measured = verifier.outcome(control, where, va)
            chosen = measured; candidate = None; gate = None
            if augmented:
                arm = report['profile_augmentations'][cut]; arm_dir = Path(arm['submission']).parent
                verifier.outcome(arm, arm_dir, va)
                job = json.loads((arm_dir/'job.json').read_text())
                if job['full_fit'] or job['threads'] != 2 or job['recipe'] != arm['recipe']:
                    raise ValueError('Augmentation job contract changed')
                mixture = report['ensemble']['primary' if cut == 0 else 'confirmation']
                mixed_dir = Path(mixture['submission']).parent
                candidate = verifier.outcome(mixture, mixed_dir, va)
                if spec['kind'] == 'classification':
                    expected = .9*aligned_probabilities(where, va, spec['classes'])+.1*aligned_probabilities(arm_dir, va, spec['classes'])
                    if not np.allclose(expected, aligned_probabilities(mixed_dir, va, spec['classes']), atol=1e-15, rtol=0):
                        raise ValueError('Validation class mixture changed')
                else:
                    expected = .9*pd.read_csv(where/'validation_predictions.csv').y_pred.to_numpy()+.1*pd.read_csv(arm_dir/'validation_predictions.csv').y_pred.to_numpy()
                    if not np.allclose(expected, pd.read_csv(mixed_dir/'validation_predictions.csv').y_pred, atol=1e-12, rtol=1e-12):
                        raise ValueError('Validation regression mixture changed')
                    study = report['hpo_studies'][cut]
                    checked = verify_study(directory/f'inner-study-{cut}', study, tr, verifier)
                    if checked.get('completed_trials') != 8 or not same_recipe(study['selected_recipe'], arm['recipe']):
                        raise ValueError('Nested eight-trial procedure was not fully executed')
                gate = paired_gate(measured, candidate, spec, verifier.support(tr))
                if not gate['passed']:
                    raise ValueError('Deployed augmentation failed paired gate')
                chosen = candidate
            cuts.append({'cut': cut, 'control': measured, 'candidate': candidate, 'selected': chosen,
                         'gate': gate, 'split_sha256': digest(split)})
        full = json.loads((directory/'final-fit/result.json').read_text())
        arms = full['components']
        if len(arms) != (2 if augmented else 1):
            raise ValueError('Full mixture arm count mismatch')
        if not same_recipe(arms[0]['recipe'], qualified):
            raise ValueError('Full control changed')
        expected_iterations = median_iterations(*[r['fit_iterations'] for r in report['profile_controls']])
        if arms[0]['fit_iterations'] != expected_iterations:
            raise ValueError('Full control iteration transfer differs')
        if augmented:
            if spec['kind'] == 'regression':
                study = report['hpo_studies'][2]
                checked = verify_study(directory/'full-inner-study', study, np.arange(len(verifier.train)), verifier)
                if checked.get('completed_trials') != 8 or not same_recipe(study['selected_recipe'], arms[1]['recipe']):
                    raise ValueError('Full training inner selection incomplete')
                selected = next(r for r in study['trials'] if r.get('value') is not None and same_recipe(r['recipe'], arms[1]['recipe']))
                expected_iterations = selected['fit_iterations']
            else:
                expected_iterations = median_iterations(*[r['fit_iterations'] for r in report['profile_augmentations']])
            if arms[1]['fit_iterations'] != expected_iterations:
                raise ValueError('Full augmentation iteration provenance differs')
        for arm in arms:
            job = json.loads((Path(arm['submission']).parent/'job.json').read_text())
            if not job['full_fit'] or job['threads'] != 2 or job['fit_iterations'] != arm['fit_iterations']:
                raise ValueError('Full job contract mismatch')
        leaves = full_leaves(full, len(verifier.train))
        values = full_values(spec, full)
        expected = (.9*full_values(spec, arms[0])+.1*full_values(spec, arms[1])) if augmented else full_values(spec, arms[0])
        if not np.allclose(values, expected, atol=1e-12, rtol=1e-12):
            raise ValueError('Full outputs do not reproduce fixed mixture')
        exported = np.asarray(read_submission_values(spec, report['submission_path']))
        actual = np.asarray(spec['classes'])[values.argmax(axis=1)] if spec['kind'] == 'classification' else values
        if (not np.array_equal(exported.astype(str), actual.astype(str)) if spec['kind'] == 'classification'
                else not np.allclose(exported, actual, atol=1e-12, rtol=1e-12)):
            raise ValueError('Final CSV differs from actual full-fit mixture')
        sample = pd.read_csv(spec['paths']['sample_submission']); submission = pd.read_csv(report['submission_path'])
        if list(sample.columns) != list(submission.columns) or len(sample) != len(submission) or submission.isna().any().any():
            raise ValueError('Final CSV shape/schema/null contract failed')
        if spec.get('id') and not np.array_equal(sample[spec['id']], submission[spec['id']]):
            raise ValueError('Final CSV ID order mismatch')
        if (not report['integrity_ok'] or report['final_fit_status'] != 'ok'
                or digest(report['submission_path']) != report['submission_sha256']):
            raise ValueError('Final report integrity/hash mismatch')
        if spec['kind'] == 'regression' and not augmented:
            raise ValueError('Regression profile fell back; tested augmentation procedure incomplete')
        results.append({'kind': spec['kind'], 'metric': spec['metric'], 'cuts': cuts,
                        'control_mean': float(np.mean([r['control']['value'] for r in cuts])),
                        'selected_mean': float(np.mean([r['selected']['value'] for r in cuts])),
                        'augmentation_qualified': augmented, 'full_training_rows': len(verifier.train),
                        'final_leaf_learners': leaves, 'final_iterations': full['fit_iterations'],
                        'submission_sha256': digest(report['submission_path']), 'csv_rows': len(submission),
                        'source_matches_current': verifier.source_matches_current,
                        'refit_csv_integrity_verified': True})
    return {'scope': campaign['scope'], 'verified': True, 'tasks': results,
            'archive_sha256': campaign['archive_sha256'], 'source_sha256': campaign['source_sha256'],
            'campaign_sha256': digest(path), 'verifier_sha256': digest(__file__),
            'default_changed': False, 'official_submission': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Preserve existing verification receipts')
    report = verify(args.campaign)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'verified': True, 'metrics': [(r['kind'], r['selected_mean']) for r in report['tasks']]}))


if __name__ == '__main__':
    main()
