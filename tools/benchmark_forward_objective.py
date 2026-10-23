"""Up-to-two-period marginal HPO with exact-context native execution reuse."""
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
from automl.evaluation.api import make_time_split
from automl.search.hpo import nested_partition,optimize_recipe
from build_submission import build_files
from benchmark_marginal_hpo import HPO,FORWARD,worker_closure
from replay_execution_cache import library_identity,ObservedSubprocess
from research_execution_cache import ExecutionCache
from summarize_research import Verifier,digest
from verify_marginal_hpo import load
from verify_reg_blend_cv import verify as verify_reference


def forward_folds(spec,train,hashes,outer_rows):
    outer_rows=np.asarray(outer_rows,dtype=np.int64);folds=[];unavailable=[]
    latest=nested_partition(spec,train,hashes,outer_rows,seed=137)[:2]
    subset=train.iloc[outer_rows].reset_index(drop=True)
    for offset in [0,1]:
        try:
            tr,va,info=make_time_split(spec,subset,offset=offset)
        except ValueError as exc:
            unavailable.append({'offset':offset,'reason':str(exc)[:180]});continue
        tr,va=outer_rows[tr],outer_rows[va]
        if not np.isin(np.concatenate([tr,va]),outer_rows).all() or np.intersect1d(tr,va).size:raise ValueError('Inner fold escaped fitting prefix')
        if offset==0 and not all(np.array_equal(a,b) for a,b in zip((tr,va),latest)):raise ValueError('Latest fold differs from nested_partition')
        folds.append((tr,va,dict(info,scope='outer fitting prefix only')))
    if not folds:raise ValueError('No usable inner fold')
    return folds,unavailable


def aggregate(values,operator):
    values=np.asarray(values,dtype=float)
    if values.ndim!=1 or not len(values) or not np.isfinite(values).all():raise ValueError('Finite fold objectives required')
    if operator=='FORWARD_MEAN':return float(np.mean(values))
    if operator=='FORWARD_WORST':return float(np.max(values))
    raise ValueError('Unknown objective operator')


def run(output,plan_path):
    start=time.monotonic();deadline=start+5400;plan=json.loads(plan_path.read_text())
    if not json.loads((plan_path.parent/'scientific-audit.json').read_text()).get('accepted'):raise ValueError('Plan audit missing')
    operator=plan['objective_id'];aggregate([1.],operator)
    if plan['control_id']!='PIPE02_COMPLETE' or plan['component_id']!='V16_COMPLETE':raise ValueError('Wrong control identities')
    files=build_files();source=output/'sources';source.mkdir()
    for n,b in files.items():(source/n).write_bytes(b)
    hashes_source={n:hashlib.sha256(b).hexdigest() for n,b in files.items()};old=json.loads(HPO.read_text());forward=json.loads(FORWARD.read_text())
    closure=worker_closure(files)
    if any(old['source_sha256'].get(n)!=hashes_source[n] for n in closure):raise ValueError('Historical worker changed')
    reference=verify_reference(FORWARD)
    if not reference['measured_cv_gate_passed']:raise ValueError('Unqualified reference')
    harness=['benchmark_forward_objective.py','verify_forward_objective.py','research_execution_cache.py','replay_execution_cache.py','verify_marginal_hpo.py','summarize_research.py','verify_reg_blend_cv.py','build_submission.py']
    m={'status':'running','spec':old['spec'],'source_sha256':hashes_source,'input_sha256':old['input_sha256'],
        'harness_sha256':{n:digest(ROOT/'tools'/n) for n in harness},'objective_id':operator,
        'comparison_control':'PIPE02_COMPLETE','component_control':'V16_COMPLETE','worker_dependency_parity':closure,
        'protocol_sha256':digest(ROOT/'docs/experiments/round04_protocol_20261023.md'),'plan_path':str(plan_path),'plan_sha256':digest(plan_path),
        'reference_manifest_sha256':digest(FORWARD),'old_hpo_manifest_sha256':digest(HPO),
        'identity':{'pid':os.getpid(),'create_time':psutil.Process().create_time()},
        'limits':{'total_seconds':5400,'study_seconds':1800,'worker_seconds':600,'threads':2,'memory_mib_worker_and_parent':1536,'trials':8,'seed':137,'startup':3},
        'scope':'Up-to-two-inner-period development HPO on reused public forward cuts, not private/official performance','cuts':[],'worker_launches':[]}
    path=output/'results.json';atomic_json(path,m);v=Verifier(m,source);spec=v.spec;train=v.train
    groups=pd.util.hash_pandas_object(train[spec['features']],index=False).to_numpy(dtype='uint64')
    control=json.loads((ROOT/'docs/experiments/reg_blend01_candidates_20261023.json').read_text())[0]['recipe']
    sys.path.insert(0,str(source));frozen=importlib.import_module('automl_runner')
    if Path(frozen.__file__).resolve()!=source/'automl_runner.py' or frozen.THREADS!=2 or Path(frozen.worker_entrypoint()).resolve()!=source/'automl_worker.py':raise ValueError('Frozen worker differs')
    import subprocess
    def spawn(*args,**kwargs):
        p=subprocess.Popen(*args,**kwargs);m['worker_launches'].append({'pid':p.pid,'create_time':psutil.Process(p.pid).create_time(),'command':args[0]});return p
    frozen.subprocess=ObservedSubprocess(spawn)
    libraries={n:library_identity(n) for n in ['numpy','pandas','scikit-learn','lightgbm','catboost','xgboost','optuna']}
    cache=ExecutionCache(output/'native-cache',output)

    def context(recipe,split):
        current={n:hashlib.sha256(b).hexdigest() for n,b in build_files().items()};inputs={n:digest(p) for n,p in spec['paths'].items()}
        if current!=hashes_source or inputs!=m['input_sha256']:raise ValueError('Source/input changed before native request')
        tr,va=v.split(split)
        return {'source_sha256':current,'input_sha256':inputs,'spec':spec,'task_sha256':digest(spec['task_path']),'recipe':recipe,
            'split_rows_sha256':hashlib.sha256(tr.astype('<i8').tobytes()+va.astype('<i8').tobytes()).hexdigest(),
            'threads':2,'full_fit':False,'fit_iterations':None,'python':sys.version,'libraries':libraries}

    def native(recipe,directory,split,timeout):
        tick=time.monotonic();remaining=min(timeout,600,deadline-time.monotonic()-90)
        if remaining<1:raise RuntimeError('Common deadline before worker')
        record=frozen.run_worker(spec,recipe,directory,split,remaining,memory_limit=1536*2**20)
        record['wall_seconds']=round(time.monotonic()-tick,3)
        if record.get('status')!='ok':
            atomic_json(Path(directory)/'execution-failure.json',record);raise RuntimeError('Native worker failed')
        return record

    try:
        for cut in range(3):
            if deadline-time.monotonic()<100:m['status']='budget_exhausted';break
            where=output/f'cut-{cut}';where.mkdir();outer=v.split(HPO.parent/f'cut-{cut}/outer-split.npz')
            np.savez(where/'outer-split.npz',train=outer[0],validation=outer[1])
            folds,unavailable=forward_folds(spec,train,groups,outer[0]);row={'cut':cut,'folds':[],'unavailable_inner_folds':unavailable,'studies':{},'outer':{}}
            m['cuts'].append(row);atomic_json(path,m);controls=[]
            for number,(tr,va,info) in enumerate(folds):
                split=where/f'inner-{number}.npz';np.savez(split,train=tr,validation=va)
                record=native(control,where/f'inner-control-{number}',split,600)
                values,checked=load(v,record['output_dir'],(tr,va),control);controls.append(values)
                row['folds'].append({'number':number,'split':info,'control':checked,'control_execution':{'seconds':record['wall_seconds'],'peak_total_mib':record.get('observed_total_peak_mb')}})
                atomic_json(path,m)
            c_outer,_=load(v,next(r['directory'] for r in forward['results'] if r['seed']==cut),outer,control)
            a_old,_=load(v,HPO.parent/f'cut-{cut}/outer-tpe',outer,old['cuts'][cut]['tpe']['selected_recipe'])
            truth=train[spec['target']].to_numpy(dtype=float);strong=float(np.sqrt(np.mean((truth[outer[1]]-(.9*c_outer+.1*a_old))**2)))
            if not np.isclose(strong,reference['cuts'][cut]['blend_rmse'],atol=1e-10,rtol=1e-12):raise ValueError('PIPE02 reference differs')
            row['PIPE02_rmse']=strong;atomic_json(path,m)

            def objective(s,recipe,directory,requested_split,timeout):
                directory=Path(directory);directory.mkdir(parents=True,exist_ok=False);tick=time.monotonic();fold_records=[];values=[];latest_iterations=None
                primary=v.split(requested_split)
                if not all(np.array_equal(a,b) for a,b in zip(primary,folds[0][:2])):raise ValueError('Study primary split differs')
                for number,(tr,va,_) in enumerate(folds):
                    split=where/f'inner-{number}.npz';ctx=context(recipe,split);fold_dir=directory/f'fold-{number}'
                    remaining=min(timeout-(time.monotonic()-tick),deadline-time.monotonic()-90)
                    if remaining<1:return {'status':'deadline','metrics':None,'wall_seconds':time.monotonic()-tick}
                    record=cache.execute(ctx,fold_dir,lambda:native(recipe,fold_dir,split,remaining))
                    predictions,checked=load(v,record['output_dir'],(tr,va),recipe)
                    value=float(np.sqrt(np.mean((truth[va]-(.9*controls[number]+.1*predictions))**2)));values.append(value)
                    fold_records.append({'number':number,'origin':record['output_dir'],'requested_directory':str(fold_dir),'cache_hit':record['cache_hit'],
                        'native_rmse':checked['value'],'mixture_rmse':value,'cache_context':ctx})
                    if number==0:latest_iterations=record['fit_iterations']
                value=aggregate(values,operator)
                atomic_json(directory/'objective.json',{'objective_id':operator,'value':value,'folds':fold_records,'latest_fold_iterations':latest_iterations,'recipe':recipe})
                return {'status':'ok','metrics':{'rmse':value},'fit_iterations':latest_iterations,'wall_seconds':round(time.monotonic()-tick,3)}

            for sampler in ['random','tpe']:
                selected,study=optimize_recipe(spec,train,groups,outer[0],old['control_recipe'],where/sampler,objective,
                    min(deadline-120,time.monotonic()+1800),trials=8,seed=137,sampler=sampler,worker_timeout=600)
                study['objective_contract']=operator;atomic_json(where/sampler/'hpo.json',study);row['studies'][sampler]=study;atomic_json(path,m)
                if study.get('completed_trials')!=8:raise RuntimeError('Incomplete equal-cap study')
                result=native(selected,where/f'outer-{sampler}',where/'outer-split.npz',600)
                predictions,checked=load(v,result['output_dir'],outer,selected)
                value=float(np.sqrt(np.mean((truth[outer[1]]-(.9*c_outer+.1*predictions))**2)))
                row['outer'][sampler]={'native':checked,'mixture_rmse':value,'seconds':result['wall_seconds'],'peak_total_mib':result.get('observed_total_peak_mb')}
                atomic_json(path,m);print(json.dumps({'cut':cut,'sampler':sampler,'inner_folds':len(folds),'PIPE02':strong,'candidate':value,'actual_worker_launches':len(m['worker_launches'])}),flush=True)
            row['improved_PIPE02']=row['outer']['tpe']['mixture_rmse']<strong;atomic_json(path,m)
            if not row['improved_PIPE02']:m['status']='rejected_futility';break
        else:m['status']='completed'
        complete=len(m['cuts'])==3 and all('tpe' in r['outer'] for r in m['cuts'])
        means={name:float(np.mean([r['outer'][name]['mixture_rmse'] for r in m['cuts']])) for name in ['random','tpe']} if complete else None
        m['summary']={'complete_screen':complete,'mean':means,'passed':bool(complete and all(r['improved_PIPE02'] for r in m['cuts']) and means['tpe']<means['random'])}
        atomic_json(path,m)
        from verify_forward_objective import verify
        atomic_json(output/'verification.json',verify(path));m['independent_verification_passed']=True
    except BaseException as exc:
        m.update(status='failed',exception_type=type(exc).__name__,exception_detail=str(exc)[:240]);raise
    finally:
        m.update(seconds=round(time.monotonic()-start,3),source_unchanged=hashes_source=={n:hashlib.sha256(b).hexdigest() for n,b in build_files().items()},
            inputs_unchanged=m['input_sha256']=={n:digest(p) for n,p in spec['paths'].items()},
            harness_unchanged=m['harness_sha256']=={n:digest(ROOT/'tools'/n) for n in harness},plan_unchanged=m['plan_sha256']==digest(plan_path))
        atomic_json(path,m)
    if not all(m[k] for k in ['source_unchanged','inputs_unchanged','harness_unchanged','plan_unchanged']):raise RuntimeError('Frozen context changed')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);args=p.parse_args()
    output=args.output.resolve();plan=args.plan.resolve()
    if not all(p.is_relative_to((ROOT/'test-runs').resolve()) for p in [output,plan]):raise ValueError('Keep raw artifacts ignored')
    def interrupted(signum,frame):raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM,interrupted)
    with (ROOT/'test-runs/.owned-research.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);output.mkdir(parents=True,exist_ok=False)
        lock.seek(0);lock.truncate();json.dump({'pid':os.getpid(),'create_time':psutil.Process().create_time()},lock);lock.flush()
        run(output,plan)


if __name__=='__main__':main()
