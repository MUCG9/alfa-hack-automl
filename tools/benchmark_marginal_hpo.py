"""Dev-only marginal HPO screen against the qualified complete PIPE-02 control."""
from pathlib import Path
from copy import deepcopy
import argparse
import ast
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tools'))
os.environ.setdefault('AUTOML_THREADS', '2')
import numpy as np
import pandas as pd
import psutil
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.processes import ProcessTree
from automl.search.hpo import nested_partition, optimize_recipe
from build_submission import build_files
from summarize_research import Verifier, digest, verify_predictions
from verify_reg_blend_cv import verify as verify_reference

BASE = ROOT/'test-runs/qwen-optuna-20261022'
HPO = BASE/'overnight-20261023/regression-hpo/results.json'
FORWARD = BASE/'reg-blend01-forward-20261023/benchmark/results.json'


def mixed_rmse(truth, control, trial):
    arrays = [np.asarray(x, dtype=float) for x in (truth, control, trial)]
    if any(a.ndim != 1 or a.shape != arrays[0].shape or not np.isfinite(a).all() for a in arrays) or not len(arrays[0]):
        raise ValueError('Mixture requires finite aligned one-dimensional arrays')
    return float(np.sqrt(np.mean((arrays[0]-(.9*arrays[1]+.1*arrays[2]))**2)))


def inner_subset(inner, outer):
    tr, va = inner
    if np.intersect1d(tr, va).size or not np.isin(np.concatenate([tr, va]), outer).all():
        raise ValueError('Inner partition escaped outer fitting rows')


def objective_result(native, value):
    result = deepcopy(native)
    result['metrics']['rmse'] = value
    return result


def worker_closure(files):
    """Only worker-reachable flat modules must match historical fits exactly."""
    pending, seen = ['automl_worker.py'], set()
    while pending:
        name = pending.pop()
        if name in seen: continue
        seen.add(name)
        for node in ast.walk(ast.parse(files[name])):
            modules = ([node.module] if isinstance(node, ast.ImportFrom) else
                       [a.name for a in node.names] if isinstance(node, ast.Import) else [])
            pending.extend(m+'.py' for m in modules if m and m+'.py' in files and m+'.py' not in seen)
    return sorted(seen)


def prediction(verifier, directory, rows, split, recipe=None):
    directory = Path(directory)
    record = json.loads((directory/'result.json').read_text())
    job = json.loads((directory/'job.json').read_text())
    if job['full_fit'] or job['threads'] != 2 or (recipe is not None and job['recipe'] != recipe):
        raise ValueError('Worker fitting contract differs')
    actual = verifier.split(job['split_path'])
    if not all(np.array_equal(a, b) for a, b in zip(actual, split)):
        raise ValueError('Worker used another fitting partition')
    checked = verify_predictions(record, directory, verifier.spec, verifier.train, rows)
    return pd.read_csv(directory/'validation_predictions.csv').y_pred.to_numpy(), checked


def summarize(report):
    complete = (len(report['cuts']) == 3 and all(c.get('complete_studies') and 'tpe' in c.get('outer', {}) for c in report['cuts']))
    mean = ({arm: float(np.mean([c['outer'][arm]['mixture_rmse'] for c in report['cuts']]))
             for arm in ['random', 'tpe']} if complete else None)
    return {'complete_screen': complete, 'mean': mean,
            'passed': bool(complete and all(c['tpe_improved_PIPE02'] for c in report['cuts']) and mean['tpe'] < mean['random'])}


def run(output):
    started = time.monotonic()
    deadline = started+5400
    files = build_files()
    old = json.loads(HPO.read_text())
    reference = verify_reference(FORWARD)
    if not reference['measured_cv_gate_passed']: raise ValueError('Strong reference verification failed')
    closure = worker_closure(files)
    if any(old['source_sha256'].get(n) != hashlib.sha256(files[n]).hexdigest() for n in closure):
        raise ValueError('Historical worker dependency bytes differ')
    frozen = output/'sources'; frozen.mkdir()
    for name, data in files.items(): (frozen/name).write_bytes(data)
    harness_names = ['benchmark_marginal_hpo.py', 'verify_marginal_hpo.py', 'summarize_research.py', 'verify_reg_blend_cv.py', 'build_submission.py']
    manifest = {'status': 'running', 'spec': old['spec'], 'input_sha256': old['input_sha256'],
        'source_sha256': {n: hashlib.sha256(b).hexdigest() for n, b in files.items()},
        'harness_sha256': {n: digest(ROOT/'tools'/n) for n in harness_names},
        'worker_historical_dependency_parity': closure, 'reference_manifest_sha256': digest(FORWARD),
        'old_hpo_manifest_sha256': digest(HPO), 'protocol_sha256': digest(ROOT/'docs/experiments/round01_protocol_20261023.md'),
        'limits': {'screen_seconds': 5400, 'study_seconds': 1800, 'worker_seconds': 600, 'threads': 2,
                   'memory_mib': 1536, 'trials': 8, 'seed': 137, 'startup': 3, 'host_fit_concurrency': 1},
        'objective': 'inner RMSE(.9*fresh-inner-V16-complete + .1*trial)',
        'comparison_control': 'PIPE02_COMPLETE', 'mixture_component_control': 'V16_COMPLETE',
        'scope': 'Reused public forward development screen; no official/private score or promotion', 'cuts': []}
    proposal = ROOT/'test-runs/autoresearch-rounds-20261023/round01/qwen-plan-repair'
    if not json.loads((proposal/'scientific-audit.json').read_text()).get('accepted'):
        raise ValueError('Qwen proposal has not passed scientific audit')
    manifest['qwen_proposal_sha256'] = digest(proposal/'proposal.json')
    manifest['identity'] = {'pid': os.getpid(), 'create_time': psutil.Process().create_time()}
    verifier = Verifier(manifest, frozen)
    train, spec = verifier.train, verifier.spec
    hashes = pd.util.hash_pandas_object(train[spec['features']], index=False).to_numpy(dtype='uint64')
    control = json.loads((ROOT/'docs/experiments/reg_blend01_candidates_20261023.json').read_text())[0]['recipe']
    forward = json.loads(FORWARD.read_text())
    path = output/'results.json'
    atomic_json(path, manifest)
    env = {k: v for k, v in os.environ.items() if not any(s in k.upper() for s in ['KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'AUTH', 'PROXY'])}
    env.update(AUTOML_THREADS='2', OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2', NUMEXPR_NUM_THREADS='2')

    def worker(task_spec, recipe, directory, split, timeout):
        directory = Path(directory); directory.mkdir(parents=True, exist_ok=False)
        job = {'spec': task_spec, 'recipe': recipe, 'output_dir': str(directory), 'split_path': str(split),
               'threads': 2, 'full_fit': False}
        atomic_json(directory/'job.json', job)
        tick = time.monotonic(); remaining = min(timeout, 600, deadline-time.monotonic()-60)
        if remaining < 1: return {'status': 'deadline'}
        peak, state, proc = 0, 'missing', None
        with (directory/'worker.log').open('x') as log:
            proc = subprocess.Popen([sys.executable, str(frozen/'automl_worker.py'), str(directory/'job.json')],
                cwd=spec['root'], env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            tree = ProcessTree(proc)
            try:
                while proc.poll() is None:
                    tree.refresh(); rss = 0
                    for member in list(tree.members.values()):
                        try: rss += member.memory_info().rss
                        except psutil.NoSuchProcess: pass
                    peak = max(peak, rss)
                    if rss > 1536*2**20: state = 'memory_limit'; break
                    if time.monotonic()-tick >= remaining: state = 'timeout'; break
                    time.sleep(.1)
                else: state = proc.returncode
            finally: tree.terminate()
        record = json.loads((directory/'result.json').read_text()) if state == 0 and (directory/'result.json').exists() else {'status': state}
        record.update(wall_seconds=round(time.monotonic()-tick, 3), peak_mib=round(peak/2**20, 2), directory=str(directory))
        atomic_json(directory/'execution.json', {k:record[k] for k in ['status','wall_seconds','peak_mib']})
        return record

    try:
        for cut in range(3):
            if deadline-time.monotonic() < 70: manifest['status'] = 'budget_exhausted'; break
            where = output/f'cut-{cut}'; where.mkdir()
            old_where = HPO.parent/f'cut-{cut}'
            outer = verifier.split(old_where/'outer-split.npz')
            np.savez(where/'outer-split.npz', train=outer[0], validation=outer[1])
            inner_tr, inner_va, inner_info = nested_partition(spec, train, hashes, outer[0], seed=137)
            inner = (inner_tr, inner_va); inner_subset(inner, outer[0])
            np.savez(where/'inner-split.npz', train=inner_tr, validation=inner_va)
            # Actual reference control and augmentation predictions were independently
            # checked above; additionally bind their jobs and partitions here.
            old_control_dir = Path(next(r for r in forward['results'] if r['seed'] == cut)['directory'])
            c_outer, _ = prediction(verifier, old_control_dir, outer[1], outer, control)
            a_outer, _ = prediction(verifier, old_where/'outer-tpe', outer[1], outer,
                                    old['cuts'][cut]['tpe']['selected_recipe'])
            truth = train[spec['target']].iloc[outer[1]].to_numpy()
            strong = mixed_rmse(truth, c_outer, a_outer)
            if not np.isclose(strong, reference['cuts'][cut]['blend_rmse'], atol=1e-10, rtol=1e-12):
                raise ValueError('Current PIPE02 reference differs')
            row = {'cut': cut, 'PIPE02_rmse': strong, 'inner_split': inner_info,
                   'outer_split_sha256': digest(where/'outer-split.npz'), 'studies': {}, 'outer': {}}
            manifest['cuts'].append(row); atomic_json(path, manifest)
            inner_record = worker(spec, control, where/'inner-control', where/'inner-split.npz', 600)
            if inner_record['status'] != 'ok': raise RuntimeError('Inner control worker failed')
            c_inner, row['inner_control'] = prediction(verifier, where/'inner-control', inner_va, inner, control)
            y_inner = train[spec['target']].iloc[inner_va].to_numpy()

            def marginal_worker(s, recipe, directory, split, timeout):
                actual = verifier.split(split)
                if not all(np.array_equal(a, b) for a, b in zip(actual, inner)):
                    raise ValueError('Objective requested another inner partition')
                native = worker(s, recipe, directory, split, timeout)
                if native['status'] != 'ok': return native
                values, check = prediction(verifier, directory, inner_va, inner, recipe)
                value = mixed_rmse(y_inner, c_inner, values)
                atomic_json(Path(directory)/'objective.json', {'objective': manifest['objective'],
                    'native_rmse': check['value'], 'mixture_rmse': value,
                    'inner_control_prediction_sha256': digest(where/'inner-control/validation_predictions.csv'),
                    'trial_prediction_sha256': check['prediction_sha256']})
                return objective_result(native, value)

            for sampler in ['random', 'tpe']:
                selected, study = optimize_recipe(spec, train, hashes, outer[0], old['control_recipe'],
                    where/sampler, marginal_worker, min(deadline-90, time.monotonic()+1800),
                    trials=8, seed=137, sampler=sampler, worker_timeout=600)
                study['objective_contract'] = manifest['objective']
                atomic_json(where/sampler/'hpo.json', study)
                row['studies'][sampler] = study
                atomic_json(path, manifest)
                if study.get('completed_trials') != 8: raise RuntimeError('Incomplete eight-trial study')
                native = worker(spec, selected, where/f'outer-{sampler}', where/'outer-split.npz', 600)
                if native['status'] != 'ok': raise RuntimeError('Selected outer worker failed')
                predictions, checked = prediction(verifier, where/f'outer-{sampler}', outer[1], outer, selected)
                row['outer'][sampler] = dict(checked, mixture_rmse=mixed_rmse(truth, c_outer, predictions),
                    execution={k:native[k] for k in ['wall_seconds','peak_mib']})
                print(json.dumps({'cut':cut, 'sampler':sampler, 'PIPE02_rmse':strong,
                    'candidate_rmse':row['outer'][sampler]['mixture_rmse'], 'completed_trials':study['completed_trials']}), flush=True)
                atomic_json(path, manifest)
            row['complete_studies'] = True
            row['tpe_improved_PIPE02'] = row['outer']['tpe']['mixture_rmse'] < strong
            atomic_json(path, manifest)
            if not row['tpe_improved_PIPE02']:
                manifest['status'] = 'rejected_futility'; break
        else: manifest['status'] = 'completed'
        manifest['summary'] = summarize(manifest)
        from verify_marginal_hpo import verify
        independent = verify(path, in_progress=manifest)
        atomic_json(output/'verification.json', independent)
        manifest['independent_verification_passed'] = True
    except BaseException as exc:
        manifest.update(status='failed', exception_type=type(exc).__name__, exception_detail=str(exc)[:240])
        raise
    finally:
        manifest.update(seconds=round(time.monotonic()-started, 3),
            source_unchanged=manifest['source_sha256'] == {n:hashlib.sha256(b).hexdigest() for n,b in build_files().items()},
            inputs_unchanged=manifest['input_sha256'] == {n:digest(p) for n,p in spec['paths'].items()},
            harness_unchanged=manifest['harness_sha256'] == {n:digest(ROOT/'tools'/n) for n in harness_names})
        atomic_json(path, manifest)
    if not all(manifest[k] for k in ['source_unchanged','inputs_unchanged','harness_unchanged']):
        raise RuntimeError('Frozen experiment changed')


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); output = args.output.resolve()
    if not output.is_relative_to((ROOT/'test-runs').resolve()): p.error('Keep artifacts ignored')
    def interrupted(signum, frame): raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM, interrupted)
    with (ROOT/'test-runs/.owned-research.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        output.mkdir(parents=True, exist_ok=False)
        lock.seek(0);lock.truncate();json.dump({'pid':os.getpid(),'create_time':psutil.Process().create_time()},lock);lock.flush()
        run(output)


if __name__ == '__main__': main()
