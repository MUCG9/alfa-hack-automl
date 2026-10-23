"""Independently audit marginal-HPO objectives from labels and native artifacts."""
from pathlib import Path
import argparse
import json
import math
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from summarize_research import Verifier, digest, verify_predictions
from verify_reg_blend_cv import verify as verify_reference


def close(left, right):
    if not math.isclose(float(left), float(right), rel_tol=1e-10, abs_tol=1e-10):
        raise ValueError('Independent recomputation differs')


def same_json(left, right):
    """Reports may contain tuple-valued search bounds before JSON persistence."""
    return json.loads(json.dumps(left)) == right


def load(verifier, directory, expected_split, expected_recipe):
    directory = Path(directory)
    record = json.loads((directory/'result.json').read_text())
    job = json.loads((directory/'job.json').read_text())
    if job['full_fit'] or job['threads'] != 2 or job['recipe'] != expected_recipe or record['recipe'] != expected_recipe:
        raise ValueError('Worker recipe or fitting contract changed')
    actual = verifier.split(job['split_path'])
    if not all(np.array_equal(a, b) for a, b in zip(actual, expected_split)):
        raise ValueError('Fitting/validation rows differ from declared partition')
    checked = verify_predictions(record, directory, verifier.spec, verifier.train, expected_split[1])
    return pd.read_csv(directory/'validation_predictions.csv').y_pred.to_numpy(dtype=float), checked


def verify(path, in_progress=None):
    path = Path(path)
    manifest = in_progress if in_progress is not None else json.loads(path.read_text())
    verifier = Verifier(manifest, path.parent/'sources')
    if not verifier.source_matches_current: raise ValueError('Current source differs')
    if manifest['comparison_control'] != 'PIPE02_COMPLETE' or manifest['mixture_component_control'] != 'V16_COMPLETE':
        raise ValueError('Wrong comparison/component control')
    reference_path = ROOT/'test-runs/qwen-optuna-20261022/reg-blend01-forward-20261023/benchmark/results.json'
    hpo_path = ROOT/'test-runs/qwen-optuna-20261022/overnight-20261023/regression-hpo/results.json'
    if digest(reference_path) != manifest['reference_manifest_sha256'] or digest(hpo_path) != manifest['old_hpo_manifest_sha256']:
        raise ValueError('Historical manifests changed')
    reference = verify_reference(reference_path)
    forward = json.loads(reference_path.read_text()); old = json.loads(hpo_path.read_text())
    control = json.loads((ROOT/'docs/experiments/reg_blend01_candidates_20261023.json').read_text())[0]['recipe']
    if manifest['input_sha256'] != old['input_sha256']: raise ValueError('Historical input mismatch')
    for name in manifest['worker_historical_dependency_parity']:
        if manifest['source_sha256'][name] != old['source_sha256'][name]: raise ValueError('Historical worker mismatch')
    cuts = []
    for row in manifest['cuts']:
        cut = row['cut']; where = path.parent/f'cut-{cut}'
        outer = verifier.split(where/'outer-split.npz'); inner = verifier.split(where/'inner-split.npz')
        historical = verifier.split(hpo_path.parent/f'cut-{cut}/outer-split.npz')
        if not all(np.array_equal(a, b) for a,b in zip(outer,historical)):
            raise ValueError('Outer partitions changed')
        if not np.isin(np.concatenate(inner), outer[0]).all(): raise ValueError('Inner rows escaped fitting partition')
        c_inner, _ = load(verifier, where/'inner-control', inner, control)
        c_outer_dir = next(r['directory'] for r in forward['results'] if r['seed'] == cut)
        c_outer, _ = load(verifier, c_outer_dir, outer, control)
        a_old, _ = load(verifier, hpo_path.parent/f'cut-{cut}/outer-tpe', outer, old['cuts'][cut]['tpe']['selected_recipe'])
        truth = verifier.train[verifier.spec['target']].to_numpy(dtype=float)
        strong = float(np.sqrt(np.mean((truth[outer[1]]-(.9*c_outer+.1*a_old))**2)))
        close(strong, row['PIPE02_rmse']);close(strong, reference['cuts'][cut]['blend_rmse'])
        verified_row = {'cut':cut, 'PIPE02_rmse':strong, 'inner_subset_verified':True, 'studies':{}, 'outer':{}}
        for sampler in ['random','tpe']:
            study = row['studies'][sampler]
            if not same_json(study,json.loads((where/sampler/'hpo.json').read_text())): raise ValueError('Ledger copies differ')
            actual = verifier.split(where/sampler/'split.npz')
            if not all(np.array_equal(a,b) for a,b in zip(actual,inner)): raise ValueError('Sampler used another inner split')
            if study['sampler'] != sampler or study['seed'] != 137 or study['startup_trials'] != 3 or study['maximum_trials'] != 8:
                raise ValueError('Study sampler/budget changed')
            if study['objective_contract'] != manifest['objective']: raise ValueError('Objective contract changed')
            values = []
            for entry in study['trials']:
                if entry.get('value') is None: continue
                directory = where/sampler/f'trial-{entry["number"]:02d}'
                predictions, checked = load(verifier, directory, inner, entry['recipe'])
                value = float(np.sqrt(np.mean((truth[inner[1]]-(.9*c_inner+.1*predictions))**2)))
                close(value, entry['value'])
                sidecar = json.loads((directory/'objective.json').read_text())
                close(checked['value'], sidecar['native_rmse']);close(value, sidecar['mixture_rmse'])
                if (sidecar['inner_control_prediction_sha256'] != digest(where/'inner-control/validation_predictions.csv')
                        or sidecar['trial_prediction_sha256'] != checked['prediction_sha256']):
                    raise ValueError('Objective provenance changed')
                values.append((value, entry['recipe']))
            if len(values) != study['completed_trials'] or len(values) != 8:
                raise ValueError('Expected eight successful objectives')
            best = min(values, key=lambda p:p[0]);close(best[0], study['best_inner_value'])
            if best[1] != study['selected_recipe']: raise ValueError('Selected recipe does not minimize mixture objective')
            predictions, checked = load(verifier, where/f'outer-{sampler}', outer, best[1])
            value = float(np.sqrt(np.mean((truth[outer[1]]-(.9*c_outer+.1*predictions))**2)))
            close(value, row['outer'][sampler]['mixture_rmse'])
            verified_row['studies'][sampler] = {'completed_trials':len(values), 'successful_after_startup':len(values)-3,
                'native_and_mixture_independently_verified':True, 'best_inner_mixture_rmse':best[0],
                'seconds':study['seconds']}
            verified_row['outer'][sampler] = {'native_rmse':checked['value'],'mixture_rmse':value,'gain_over_PIPE02':strong-value}
        verified_row['tpe_improved_PIPE02'] = verified_row['outer']['tpe']['mixture_rmse'] < strong
        if verified_row['tpe_improved_PIPE02'] != row['tpe_improved_PIPE02']: raise ValueError('Gate mismatch')
        cuts.append(verified_row)
    complete = len(cuts) == 3 and [c['cut'] for c in cuts] == [0,1,2]
    means = {name:float(np.mean([c['outer'][name]['mixture_rmse'] for c in cuts])) for name in ['random','tpe']} if complete else None
    passed = bool(complete and all(c['tpe_improved_PIPE02'] for c in cuts) and means['tpe'] < means['random'])
    if manifest['summary'] != {'complete_screen':complete,'mean':means,'passed':passed}:
        raise ValueError('Summary includes absent cuts or violates gates')
    if manifest['status'] == 'rejected_futility' and (not cuts or cuts[-1]['tpe_improved_PIPE02']):
        raise ValueError('Futility stop is unsupported')
    return {'status':'verified', 'cuts':cuts,'complete_screen':complete,'mean':means,'passed':passed,
        'comparison_control':'PIPE02_COMPLETE','objective':manifest['objective'],
        'source_sha256':manifest['source_sha256'],'input_sha256':manifest['input_sha256'],
        'verifier_sha256':digest(__file__),'no_full_procedure_promotion':True}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('manifest',type=Path)
    args=parser.parse_args(); print(json.dumps(verify(args.manifest),indent=2))
