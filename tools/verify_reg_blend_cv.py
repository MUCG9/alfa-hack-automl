"""Verify REG-BLEND-01 forward qualification against the complete control."""
from pathlib import Path
import json
import math

import numpy as np
import pandas as pd

from summarize_research import Verifier, digest, summarize_hpo

ROOT = Path(__file__).resolve().parents[1]


def verify(path):
    path = Path(path)
    manifest = json.loads(path.read_text())
    contract = ROOT/'docs/experiments/reg_blend01_candidates_20261023.json'
    expected = json.loads(contract.read_text())
    if manifest['candidates'] != expected:
        raise ValueError('Forward control differs from fixed qualified recipe')
    verifier = Verifier(manifest, path.parent/'sources')
    hpo_path = ROOT/'test-runs/qwen-optuna-20261022/overnight-20261023/regression-hpo/results.json'
    hpo = json.loads(hpo_path.read_text())
    hpo_verified = summarize_hpo(hpo_path)
    old = json.loads((ROOT/'docs/experiments/reg_blend01_replay_20261023.json').read_text())
    if (manifest['inputs'] != hpo['input_sha256'] or manifest['inputs'] != old['input_sha256']
            or manifest['source'] != hpo['source_sha256'] or not hpo_verified['complete_verified_screen']):
        raise ValueError('Forward controls and nested-HPO artifacts differ in source/inputs')
    if verifier.spec['metric'] != 'rmse' or verifier.spec['kind'] != 'regression' or verifier.periods is None:
        raise ValueError('Expected forward RMSE regression')
    records = {r['seed']: r for r in manifest['results']}
    if len(manifest['results']) != 3 or set(records) != {0, 1, 2}:
        raise ValueError('Incomplete forward control workers')
    folds = []
    for cut in range(3):
        row = records[cut]
        if row['status'] != 'ok' or row['name'] != expected[0]['name']:
            raise ValueError('Forward control worker failed')
        directory = Path(row['directory'])
        job = json.loads((directory/'job.json').read_text())
        if job['recipe'] != expected[0]['recipe'] or job['full_fit'] or job['threads'] != 2:
            raise ValueError('Forward control worker contract changed')
        split_paths = [directory/'split.npz', hpo_path.parent/f'cut-{cut}/outer-split.npz']
        left, right = [verifier.split(p) for p in split_paths]
        if not all(np.array_equal(a, b) for a, b in zip(left, right)):
            raise ValueError('Forward control/nested-TPE partitions differ')
        tr, va = left
        control = verifier.outcome(row, directory, va)
        if cut < 2 and not math.isclose(control['value'], old['cuts'][cut]['control']['value'], abs_tol=1e-9, rel_tol=1e-12):
            raise ValueError('Qualified control numerical parity mismatch')
        tpe_directory = hpo_path.parent/f'cut-{cut}/outer-tpe'
        control_predictions = pd.read_csv(directory/'validation_predictions.csv').y_pred.to_numpy()
        tpe_predictions = pd.read_csv(tpe_directory/'validation_predictions.csv').y_pred.to_numpy()
        # summarize_hpo above already verified source labels, exact row order,
        # selected outer recipes and every inner objective in these artifacts.
        blend = .9*control_predictions+.1*tpe_predictions
        value = float(np.sqrt(np.mean((verifier.train[verifier.spec['target']].iloc[va].to_numpy()-blend)**2)))
        if not math.isfinite(value):
            raise ValueError('Nonfinite forward blend metric')
        folds.append({'cut': cut, 'control': control,
            'tpe': hpo_verified['cuts'][cut]['outcomes']['tpe'], 'blend_rmse': value,
            'gate_passed': value < control['value'], 'split_sha256': list(map(digest, split_paths)),
            'fitting_rows': len(tr), 'validation_rows': len(va)})
    return {'scope': 'REG-BLEND-01 complete-control plus separately nested inner-TPE procedure, three forward cuts, reused public; not full exactly-once OOF/private/official score',
            'source_sha256': manifest['source'], 'input_sha256': manifest['inputs'],
            'source_matches_current': verifier.source_matches_current,
            'candidate_contract_sha256': digest(contract), 'hpo_manifest_sha256': digest(hpo_path),
            'benchmark_manifest_sha256': digest(path), 'verifier_sha256': digest(__file__),
            'gate_implementation_sha256': digest(ROOT/'tools/summarize_research.py'),
            'cuts': folds, 'control_mean': float(np.mean([c['control']['value'] for c in folds])),
            'blend_mean': float(np.mean([c['blend_rmse'] for c in folds])),
            'measured_cv_gate_passed': all(c['gate_passed'] for c in folds),
            'coverage': 'three forward periods; not full exactly-once OOF',
            'temporal_uncertainty': 'unavailable: one validation period per cut',
            'worker_seconds': [r['seconds'] for r in manifest['results']],
            'worker_peak_mib': [r['peak_mb'] for r in manifest['results']],
            'qualified_release': False, 'official_submission': False}
