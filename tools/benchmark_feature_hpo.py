"""Paired feature-only change to complete PIPE02, with inner TPE repeated per cut."""
from pathlib import Path
import argparse
import fcntl
import hashlib
import importlib
import json
import os
import signal
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tools'))
os.environ.setdefault('AUTOML_THREADS','2')
import numpy as np
import pandas as pd
import psutil
from automl.infrastructure.atomic import atomic_json
from automl.search.hpo import optimize_recipe
from build_submission import build_files
from benchmark_marginal_hpo import HPO,FORWARD,worker_closure
from summarize_research import Verifier,digest
from verify_marginal_hpo import load
from verify_reg_blend_cv import verify as verify_reference


def feature_only(base,candidate):
    clean=lambda r:{k:v for k,v in r.items() if k not in ['feature_code','hypothesis']}
    if clean(base)!=clean(candidate) or not candidate.get('feature_code'):raise ValueError('Candidate changed more than feature_code')


def run(output,plan_path):
    started=time.monotonic();deadline=started+5400
    plan=json.loads(plan_path.read_text());audit=json.loads((plan_path.parent/'scientific-audit.json').read_text())
    if not plan.get('generation_valid') or not audit.get('accepted'):raise ValueError('Feature proposal audit missing')
    old=json.loads(HPO.read_text());forward=json.loads(FORWARD.read_text());reference=verify_reference(FORWARD)
    if not reference['measured_cv_gate_passed']:raise ValueError('Reference is not qualified')
    candidate=plan['recipe'];feature_only(old['control_recipe'],candidate)
    files=build_files();closure=worker_closure(files)
    if any(old['source_sha256'].get(n)!=hashlib.sha256(files[n]).hexdigest() for n in closure):raise ValueError('Historical worker differs')
    source=output/'sources';source.mkdir()
    for name,data in files.items():(source/name).write_bytes(data)
    sys.path.insert(0,str(source));frozen=importlib.import_module('automl_runner')
    if Path(frozen.__file__).resolve()!=source/'automl_runner.py' or frozen.THREADS!=2:raise ValueError('Incorrect frozen runner/threads')
    if Path(frozen.worker_entrypoint()).resolve()!=source/'automl_worker.py':raise ValueError('Incorrect frozen worker')
    harness=['benchmark_feature_hpo.py','verify_feature_hpo.py','benchmark_marginal_hpo.py','verify_marginal_hpo.py','summarize_research.py','verify_reg_blend_cv.py','propose_residual_features.py','propose_feature_dsl.py','build_submission.py']
    report={'status':'running','spec':old['spec'],'input_sha256':old['input_sha256'],
        'source_sha256':{n:hashlib.sha256(b).hexdigest() for n,b in files.items()},
        'harness_sha256':{n:digest(ROOT/'tools'/n) for n in harness},
        'worker_historical_dependency_parity':closure,'candidate_recipe':candidate,'qwen_features':plan['features'],
        'plan_path':str(plan_path),'plan_sha256':digest(plan_path),'reference_manifest_sha256':digest(FORWARD),'old_hpo_manifest_sha256':digest(HPO),
        'protocol_sha256':digest(ROOT/'docs/experiments/round02_protocol_20261023.md'),
        'comparison_control':'PIPE02_COMPLETE','identity':{'pid':os.getpid(),'create_time':psutil.Process().create_time()},
        'limits':{'screen_seconds':5400,'study_seconds':1800,'worker_seconds':600,'threads':2,'memory_mib_worker_and_parent':1536,'trials':8,'seed':137,'startup':3},
        'scope':'Feature-only adaptive-procedure development on reused public forward cuts, not private/official score','cuts':[]}
    path=output/'results.json';atomic_json(path,report);v=Verifier(report,source);spec=v.spec;train=v.train
    hashes=pd.util.hash_pandas_object(train[spec['features']],index=False).to_numpy(dtype='uint64')
    control=json.loads((ROOT/'docs/experiments/reg_blend01_candidates_20261023.json').read_text())[0]['recipe']

    def worker(s,recipe,directory,split,timeout):
        directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
        remaining=min(600,timeout,deadline-time.monotonic()-60)
        if remaining<1:return {'status':'deadline'}
        tick=time.monotonic()
        result=frozen.run_worker(s,recipe,directory,split,remaining,memory_limit=1536*2**20)
        result['wall_seconds']=round(time.monotonic()-tick,3)
        atomic_json(directory/'execution.json',{k:result.get(k) for k in ['status','wall_seconds','observed_process_tree_peak_mb','observed_total_peak_mb']})
        return result

    try:
        for cut in range(3):
            if deadline-time.monotonic()<70:report['status']='budget_exhausted';break
            where=output/f'cut-{cut}';where.mkdir();outer=v.split(HPO.parent/f'cut-{cut}/outer-split.npz')
            np.savez(where/'outer-split.npz',train=outer[0],validation=outer[1])
            c,_=load(v,next(r['directory'] for r in forward['results'] if r['seed']==cut),outer,control)
            a,_=load(v,HPO.parent/f'cut-{cut}/outer-tpe',outer,old['cuts'][cut]['tpe']['selected_recipe'])
            truth=train[spec['target']].iloc[outer[1]].to_numpy(dtype=float)
            strong=float(np.sqrt(np.mean((truth-(.9*c+.1*a))**2)))
            if not np.isclose(strong,reference['cuts'][cut]['blend_rmse'],atol=1e-10,rtol=1e-12):raise ValueError('Strong reference differs')
            row={'cut':cut,'PIPE02_rmse':strong};report['cuts'].append(row);atomic_json(path,report)
            selected,study=optimize_recipe(spec,train,hashes,outer[0],candidate,where/'tpe',worker,
                min(deadline-90,time.monotonic()+1800),trials=8,seed=137,sampler='tpe',worker_timeout=600)
            row['study']=study;atomic_json(path,report)
            if study.get('completed_trials')!=8:raise RuntimeError('Eight successful trials required')
            result=worker(spec,selected,where/'outer-tpe',where/'outer-split.npz',600)
            if result['status']!='ok':raise RuntimeError('Selected outer worker failed')
            pred,checked=load(v,where/'outer-tpe',outer,selected)
            row.update(native=checked,mixture_rmse=float(np.sqrt(np.mean((truth-(.9*c+.1*pred))**2))))
            row['improved_PIPE02']=row['mixture_rmse']<strong;atomic_json(path,report)
            print(json.dumps({'cut':cut,'PIPE02_rmse':strong,'candidate_rmse':row['mixture_rmse'],'improved':row['improved_PIPE02'],'completed_trials':study['completed_trials']}),flush=True)
            if not row['improved_PIPE02']:report['status']='rejected_futility';break
        else:report['status']='completed'
        complete=len(report['cuts'])==3 and all('mixture_rmse' in r for r in report['cuts'])
        report['summary']={'complete_screen':complete,'mean':float(np.mean([r['mixture_rmse'] for r in report['cuts']])) if complete else None,
            'passed':bool(complete and all(r['improved_PIPE02'] for r in report['cuts']))}
        atomic_json(path,report)
        from verify_feature_hpo import verify
        atomic_json(output/'verification.json',verify(path))
        report['independent_verification_passed']=True
    except BaseException as exc:
        report.update(status='failed',exception_type=type(exc).__name__,exception_detail=str(exc)[:240]);raise
    finally:
        report.update(seconds=round(time.monotonic()-started,3),
            source_unchanged=report['source_sha256']=={n:hashlib.sha256(b).hexdigest() for n,b in build_files().items()},
            inputs_unchanged=report['input_sha256']=={n:digest(p) for n,p in spec['paths'].items()},
            harness_unchanged=report['harness_sha256']=={n:digest(ROOT/'tools'/n) for n in harness},plan_unchanged=report['plan_sha256']==digest(plan_path))
        atomic_json(path,report)
    if not all(report[k] for k in ['source_unchanged','inputs_unchanged','harness_unchanged','plan_unchanged']):raise RuntimeError('Frozen inputs changed')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);args=p.parse_args()
    output=args.output.resolve();plan=args.plan.resolve()
    if not all(path.is_relative_to((ROOT/'test-runs').resolve()) for path in [output,plan]):p.error('Artifacts must stay ignored')
    def interrupted(signum,frame):raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM,interrupted)
    with (ROOT/'test-runs/.owned-research.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);output.mkdir(parents=True,exist_ok=False)
        lock.seek(0);lock.truncate();json.dump({'pid':os.getpid(),'create_time':psutil.Process().create_time()},lock);lock.flush()
        run(output,plan)


if __name__=='__main__':main()
