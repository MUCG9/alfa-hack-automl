"""Three owned fits/four logical requests: measure cache cost and prediction parity."""
from pathlib import Path
import argparse
import fcntl
import hashlib
import importlib
import importlib.metadata
import json
import os
import signal
import subprocess
import sys
import time
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tools'))
os.environ.setdefault('AUTOML_THREADS','2')
import numpy as np
import psutil
from automl.infrastructure.atomic import atomic_json
from build_submission import build_files
from summarize_research import Verifier,digest
from benchmark_marginal_hpo import HPO,worker_closure
from research_execution_cache import ExecutionCache
from verify_marginal_hpo import load


def run(output,plan_path):
    start=time.monotonic();deadline=start+2160
    plan=json.loads(plan_path.read_text())
    if not json.loads((plan_path.parent/'scientific-audit.json').read_text()).get('accepted'):raise ValueError('Scientific audit missing')
    old=json.loads(HPO.read_text());files=build_files();closure=worker_closure(files)
    if any(old['source_sha256'].get(n)!=hashlib.sha256(files[n]).hexdigest() for n in closure):raise ValueError('Historical training code differs')
    source=output/'sources';source.mkdir()
    for n,b in files.items():(source/n).write_bytes(b)
    hashes={n:hashlib.sha256(b).hexdigest() for n,b in files.items()}
    harness_names=['replay_execution_cache.py','verify_cache_replay.py','research_execution_cache.py','verify_marginal_hpo.py','summarize_research.py','build_submission.py']
    report={'status':'running','spec':old['spec'],'source_sha256':hashes,'input_sha256':old['input_sha256'],
        'harness_sha256':{n:digest(ROOT/'tools'/n) for n in harness_names},'protocol_sha256':digest(ROOT/'docs/experiments/round03_protocol_20261023.md'),
        'plan_path':str(plan_path),'plan_sha256':digest(plan_path),'recipe':plan['selected']['recipe'],
        'identity':{'pid':os.getpid(),'create_time':psutil.Process().create_time()},
        'limits':{'total_seconds':2160,'worker_seconds':600,'threads':2,'memory_mib_worker_and_parent':1536},
        'scope':'Efficiency/output-parity replay of a measured recipe, not a model-selection/complete-agent/private score gain',
        'requests':[],'worker_launches':[]}
    path=output/'results.json';atomic_json(path,report);v=Verifier(report,source)
    outer=v.split(HPO.parent/'cut-0/outer-split.npz');np.savez(output/'split.npz',train=outer[0],validation=outer[1])
    split=output/'split.npz';recipe=report['recipe'];spec=v.spec
    if digest(Path(plan['selected']['origin'])/'result.json')!=plan['selected']['result_sha256']:raise ValueError('Selected origin changed')
    _,original=load(v,plan['selected']['origin'],outer,recipe)
    report['original_native_rmse']=original['value']
    sys.path.insert(0,str(source));frozen=importlib.import_module('automl_runner')
    if Path(frozen.__file__).resolve()!=source/'automl_runner.py' or Path(frozen.worker_entrypoint()).resolve()!=source/'automl_worker.py' or frozen.THREADS!=2:
        raise ValueError('Frozen runner identity differs')
    def observed_popen(*args,**kwargs):
        process=subprocess.Popen(*args,**kwargs)
        report['worker_launches'].append({'pid':process.pid,'create_time':psutil.Process(process.pid).create_time(),
            'command':args[0],'started_after_seconds':round(time.monotonic()-start,3)})
        return process
    frozen.subprocess=SimpleNamespace(Popen=observed_popen)
    libraries={n:importlib.metadata.version(n) for n in ['numpy','pandas','scikit-learn','lightgbm','catboost','xgboost','optuna']}

    def context():
        current_source={n:hashlib.sha256(b).hexdigest() for n,b in build_files().items()}
        current_inputs={n:digest(p) for n,p in spec['paths'].items()}
        if current_source!=hashes or current_inputs!=report['input_sha256']:raise ValueError('Source/input changed before request')
        actual=v.split(split)
        if not all(np.array_equal(a,b) for a,b in zip(actual,outer)):raise ValueError('Saved rows changed')
        return {'source_sha256':current_source,'input_sha256':current_inputs,'spec':spec,'task_sha256':digest(spec['task_path']),
            'recipe':recipe,'split_rows_sha256':hashlib.sha256(actual[0].astype('<i8').tobytes()+actual[1].astype('<i8').tobytes()).hexdigest(),
            'threads':2,'full_fit':False,'fit_iterations':None,'python':sys.version,'libraries':libraries}

    def fit(directory):
        remaining=min(600,deadline-time.monotonic()-60)
        if remaining<1:raise RuntimeError('Deadline before worker')
        record=frozen.run_worker(spec,recipe,directory,split,remaining,memory_limit=1536*2**20)
        if record.get('status')!='ok':raise RuntimeError('Replay worker failed')
        return record

    cache=ExecutionCache(output/'cache',output)
    try:
        for name,cached in [('uncached-1',False),('uncached-2',False),('cached-cold',True),('cached-hit',True)]:
            tick=time.monotonic();ctx=context();directory=output/name;before=len(report['worker_launches'])
            result=cache.execute(ctx,directory,lambda:fit(directory)) if cached else fit(directory)
            seconds=time.monotonic()-tick
            origin=Path(result['output_dir'])
            _,checked=load(v,origin,outer,recipe)
            report['requests'].append({'name':name,'cache_enabled':cached,'cache_hit':result.get('cache_hit',False),
                'origin':str(origin),'requested_directory':str(directory),'seconds':seconds,
                'actual_worker_launches':len(report['worker_launches'])-before,'checked':checked,
                'origin_observed_total_peak_mb':result.get('observed_total_peak_mb'),'context':ctx})
            atomic_json(path,report)
            print(json.dumps({'request':name,'cache_hit':result.get('cache_hit',False),'seconds':round(seconds,3),
                'rmse':checked['value'],'launched':len(report['worker_launches'])-before}),flush=True)
        report['status']='completed';atomic_json(path,report)
        from verify_cache_replay import verify
        verified=verify(path);atomic_json(output/'verification.json',verified);report['verification']=verified
    except BaseException as exc:
        report.update(status='failed',exception_type=type(exc).__name__,exception_detail=str(exc)[:240]);raise
    finally:
        report.update(seconds=round(time.monotonic()-start,3),
            source_unchanged=hashes=={n:hashlib.sha256(b).hexdigest() for n,b in build_files().items()},
            inputs_unchanged=report['input_sha256']=={n:digest(p) for n,p in spec['paths'].items()},
            harness_unchanged=report['harness_sha256']=={n:digest(ROOT/'tools'/n) for n in harness_names},plan_unchanged=report['plan_sha256']==digest(plan_path))
        atomic_json(path,report)
    if not all(report[k] for k in ['source_unchanged','inputs_unchanged','harness_unchanged','plan_unchanged']):raise RuntimeError('Frozen context changed')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--plan',type=Path,required=True);args=parser.parse_args()
    output=args.output.resolve();plan=args.plan.resolve()
    if not all(p.is_relative_to((ROOT/'test-runs').resolve()) for p in [output,plan]):parser.error('Keep replay data ignored')
    def interrupted(signum,frame):raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM,interrupted)
    with (ROOT/'test-runs/.owned-research.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);output.mkdir(parents=True,exist_ok=False)
        lock.seek(0);lock.truncate();json.dump({'pid':os.getpid(),'create_time':psutil.Process().create_time()},lock);lock.flush()
        run(output,plan)


if __name__=='__main__':main()
