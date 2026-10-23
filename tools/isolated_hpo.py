"""Development-only isolated Optuna4.2.1 experiment; no runtime default changes.

Uses the reviewed colleague ask/tell/nested-partition pattern, narrowed to one
predeclared LightGBM regression control and strict forward fitting boundaries.
"""
from copy import deepcopy
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from automl.contracts.messages import canonical_hash
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.processes import wait_owned
from automl.infrastructure.runtime import source_files
from build_submission import build_files,REQUIREMENTS_SHA
from prepare_selector_confirmation import sha

SPACE={'num_leaves':('int',31,255),'reg_lambda':('log',2.,20.),'colsample_bytree':('float',.75,1.)}
ANCHOR_ID='model-049136473c313a8ac902'


def valid_metric(value):
    return type(value) in (int,float) and math.isfinite(value)


def forward_inside(spec,train,hashes,fitting):
    import numpy as np
    from automl.evaluation.api import make_time_split
    from automl.infrastructure.observation_time import observation_values
    rows=np.asarray(fitting)
    if rows.ndim!=1 or rows.dtype.kind not in 'iu' or not len(rows) or len(np.unique(rows))!=len(rows):
        raise ValueError('Unique integer fitting rows required')
    if rows.min()<0 or rows.max()>=len(train): raise ValueError('Fitting rows out of range')
    subset=train.iloc[rows].reset_index(drop=True)
    a,b,info=make_time_split(spec,subset)
    a,b=rows[a],rows[b]
    values=observation_values(train[info['time_column']])[0].to_numpy()
    if not max(values[a])<min(values[b]) or not set(a).isdisjoint(b):
        raise ValueError('Inner fitting is not strictly earlier')
    info=dict(info,scope='inside_outer_fitting_only',
              split_sha256=hashlib.sha256(a.astype('<i8').tobytes()+b.astype('<i8').tobytes()).hexdigest())
    return a,b,info


def effective_anchor(recipe):
    from automl.execution.model_adapters.lightgbm import create_model
    if recipe['engine']!='lightgbm': raise ValueError('One LightGBM family only')
    effective=create_model(recipe,'regression',2,100).get_params()
    result={name:effective[name] for name in SPACE}
    if any(not valid_metric(v) or not SPACE[n][1]<=v<=SPACE[n][2] for n,v in result.items()):
        raise ValueError('Effective anchor outside frozen space; never clip')
    return result


def optimize(spec,anchor,split,output,worker,deadline,sampler,trials=12):
    import optuna
    if optuna.__version__!='4.2.1': raise ValueError('Original Optuna4.2.1 required')
    if sampler not in ('random','tpe') or trials!=12:raise ValueError('Predeclared study only')
    params=effective_anchor(anchor)
    chooser=(optuna.samplers.RandomSampler(seed=137) if sampler=='random'
             else optuna.samplers.TPESampler(seed=137,n_startup_trials=3))
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study=optuna.create_study(direction='minimize',sampler=chooser)
    study.enqueue_trial(params)
    ledger=[];seen=set();best=None;selected=None
    for index in range(trials):
        if deadline-time.monotonic()<5:break
        complete=sum(t.state==optuna.trial.TrialState.COMPLETE for t in study.trials)
        phase='anchor' if index==0 else 'random' if sampler=='random' else 'startup' if complete<3 else 'guided'
        trial=study.ask()
        proposed={name:trial.suggest_int(name,low,high) if kind=='int'
                  else trial.suggest_float(name,low,high,log=kind=='log')
                  for name,(kind,low,high) in SPACE.items()}
        candidate=deepcopy(anchor);candidate['params'].update(proposed)
        fingerprint=canonical_hash(candidate)
        record={'number':index,'phase':phase,'recipe_sha256':fingerprint,'params':proposed,'valid':False}
        if fingerprint in seen:
            record['status']='duplicate'
            study.tell(trial,state=optuna.trial.TrialState.FAIL)
        else:
            seen.add(fingerprint)
            result=worker(spec,candidate,output/f'trial-{index:02d}',split,min(60,max(1,deadline-time.monotonic())))
            value=(result.get('metrics') or {}).get('rmse')
            valid=result.get('status')=='ok' and valid_metric(value)
            record.update(status=result.get('status'),valid=valid,value=value if valid else None,
                          seconds=result.get('wall_seconds'),iterations=result.get('fit_iterations'),
                          fitting_steps=len(result.get('data_policy_runs',[])))
            if valid:
                study.tell(trial,float(value))
                if best is None or value<best:best=float(value);selected=candidate
            else:study.tell(trial,state=optuna.trial.TrialState.FAIL)
        ledger.append(record)
        atomic_json(output/'study.json',{'sampler':sampler,'space':SPACE,'startup_trials':3,
                    'trials':ledger,'selected_recipe':selected,'best_inner_rmse':best,'planned_trials':12})
        if index==0 and not record['valid']:break
    result={'sampler':sampler,'space':SPACE,'startup_trials':3,'trials':ledger,'selected_recipe':selected,
            'best_inner_rmse':best,'planned_trials':12,'attempted_trials':len(ledger),'unattempted_trials':12-len(ledger),
            'completed_trials':sum(r['valid'] for r in ledger),
            'guided_successful':sum(r['valid'] and r['phase']=='guided' for r in ledger),
            'anchor_valid':bool(ledger and ledger[0]['valid']),
            'scope':'Only fitting-inner forward objective,not outer/private score'}
    atomic_json(output/'study.json',result)
    return result


def worker_main(args):
    import numpy as np
    os.environ['AUTOML_THREADS']='2'
    from automl.search.runner import discover,load_inputs,run_worker
    from automl.infrastructure.observation_time import observation_values
    if sha(ROOT/'requirements.txt')!=REQUIREMENTS_SHA:raise ValueError('Original requirements changed')
    original=json.loads(args.baseline_report.read_text())
    data=discover(args.task,loaded=load_inputs(args.task,allow_llm=False))
    spec,_,train,_,_,_,hashes=data
    for key in ('features','n_train','n_test','id','target','kind','metric','greater_is_better'):
        if spec.get(key)!=original['spec'].get(key):raise ValueError('Task differs: '+key)
    provenance=json.loads((args.baseline_report.parent/'provenance.json').read_text())['sha256']
    if any(sha(p)!=provenance['input:'+k] for k,p in spec['paths'].items()):raise ValueError('Original inputs differ')
    spec['validation_strategy']='time';spec['time_column']=original['split']['time_column']
    spec['root']=str(args.output.resolve())
    candidates=[r['recipe'] for r in original['experiments'] if 'model-'+canonical_hash(r['recipe'])[:20]==ANCHOR_ID]
    if len(candidates)!=1:raise ValueError('Original anchor missing')
    anchor=candidates[0];effective_anchor(anchor)
    metadata={'protocol_sha256':sha(ROOT/'docs/experiments/HPO-01_isolated_protocol_20261023.md'),
        'input_sha256':{k:sha(p) for k,p in spec['paths'].items()},'recipe':anchor,
        'compiled_source_sha256':{n:hashlib.sha256(b).hexdigest() for n,b in build_files().items()},
        'packages':{n:importlib.metadata.version(n) for n in ('optuna','numpy','pandas','scikit-learn','lightgbm','PyYAML','psutil')},
        'python':sys.version,'executor_sha256':sha(__file__)}
    atomic_json(args.output/'metadata.json',metadata)
    with np.load(args.baseline_report.parent/'split.npz',allow_pickle=False) as s:
        primary=s['train']
    if args.mode=='pilot':
        tr,va,info=forward_inside(spec,train,hashes,primary)
        split=args.output/'inner.npz';np.savez(split,train=tr,validation=va)
        result=run_worker(spec,anchor,args.output/'anchor',split,110)
        value=(result.get('metrics') or {}).get('rmse')
        cost=result.get('wall_seconds',float('inf'))
        receipt={'status':result.get('status'),'admitted':result.get('status')=='ok' and valid_metric(value) and cost<=20,
                 'inner_rmse':value,'seconds':cost,'inner_split':info,'fitting_steps':len(result.get('data_policy_runs',[])),
                 'scope':'Resource admission only,not external quality gain'}
        atomic_json(args.output/'pilot.json',receipt);print(json.dumps(receipt),flush=True)
        return 0 if result.get('status')=='ok' else 2
    pilot=json.loads(args.pilot.read_text())
    if pilot.get('admitted') is not True:raise ValueError('Successful resource admission required')
    pilot_meta=json.loads((args.pilot.parent/'metadata.json').read_text())
    for k in ('protocol_sha256','input_sha256','recipe','compiled_source_sha256','packages','executor_sha256'):
        if pilot_meta[k]!=metadata[k]:raise ValueError('Pilot/study evidence differs: '+k)
    arms=[]
    for scope,split_name in [('search','split.npz'),('confirmation','confirmation_split.npz')]:
        outer=args.baseline_report.parent/split_name
        with np.load(outer,allow_pickle=False) as stored:
            fitting,held=stored['train'],stored['validation']
        values=observation_values(train[spec['time_column']])[0].to_numpy()
        if not max(values[fitting])<min(values[held]):raise ValueError('Outer split is not forward')
        tr,va,info=forward_inside(spec,train,hashes,fitting)
        for sampler in ('random','tpe'):
            out=args.output/(scope+'-'+sampler);out.mkdir()
            started=time.monotonic();end=started+420
            split=out/'inner.npz';np.savez(split,train=tr,validation=va)
            study=optimize(spec,anchor,split,out,run_worker,started+300,sampler)
            record={'scope':scope,'sampler':sampler,'study':study,'inner_split':info,'outer_split_sha256':sha(outer),
                    'total_budget_seconds':420,'search_cap_seconds':300,'reserve_seconds':120,'status':'incomplete'}
            if study['anchor_valid'] and study['selected_recipe'] is not None:
                control=run_worker(spec,anchor,out/'outer-control',outer,min(55,max(1,end-time.monotonic())))
                selected=study['selected_recipe']
                candidate=(control if canonical_hash(selected)==canonical_hash(anchor) else
                           run_worker(spec,selected,out/'outer-selected',outer,min(55,max(1,end-time.monotonic()))))
                metrics=[(r.get('metrics') or {}).get('rmse') for r in (control,candidate)]
                if all(r.get('status')=='ok' for r in (control,candidate)) and all(valid_metric(v) for v in metrics) and time.monotonic()<=end:
                    record.update(status='ok',outer_control_rmse=metrics[0],outer_candidate_rmse=metrics[1])
            record['elapsed_seconds']=time.monotonic()-started
            arms.append(record);atomic_json(out/'arm.json',record)
            atomic_json(args.output/'progress.json',{'arms':arms})
            print(json.dumps({k:record.get(k) for k in ('scope','sampler','status','outer_control_rmse','outer_candidate_rmse','elapsed_seconds')}),flush=True)
    reference={'search':37.56014204464436,'confirmation':31.833700517297636}
    complete=len(arms)==4 and all(a['status']=='ok' for a in arms)
    keep=complete
    if complete:
        for scope in reference:
            random,tpe=[next(a for a in arms if a['scope']==scope and a['sampler']==sampler) for sampler in ('random','tpe')]
            keep=keep and tpe['study']['guided_successful']>0 and tpe['outer_candidate_rmse']<min(random['outer_candidate_rmse'],tpe['outer_control_rmse']) and tpe['outer_candidate_rmse']<=reference[scope]
        keep=keep and sum(a['outer_candidate_rmse'] for a in arms if a['sampler']=='tpe')/2<34.696921280971
    summary={'arms':arms,'complete':complete,'promising_screen':bool(keep),'runtime_enabled':False,
             'recommendation':'eligible_for_additional_forward_research' if keep else 'discard_or_inconclusive',
             'scope':'Reused public forward cuts;fitting-internal tuning,not independent/private/official score'}
    atomic_json(args.output/'result.json',summary);print(json.dumps({k:summary[k] for k in ('complete','promising_screen','recommendation')}))
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('pilot','study'),required=True)
    parser.add_argument('--task',type=Path,required=True)
    parser.add_argument('--baseline-report',type=Path,required=True)
    parser.add_argument('--pilot',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    args.output=args.output.resolve();args.task=args.task.resolve();args.baseline_report=args.baseline_report.resolve()
    if args.worker:return worker_main(args)
    if args.mode=='study' and args.pilot is None:parser.error('Original admission pilot required')
    args.output.mkdir(parents=True,exist_ok=False)
    source={str(p):sha(p) for p in source_files()}
    env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ('KEY','TOKEN','AUTH','SECRET','PASSWORD','PROXY'))}
    env.update(AUTOML_THREADS='2',OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
    command=[sys.executable,'-u',str(Path(__file__).resolve()),*sys.argv[1:],'--worker']
    start=time.monotonic()
    with (args.output/'process.log').open('w') as stream:
        child=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        try:status=wait_owned(child,120 if args.mode=='pilot' else 1700,int(1.7*2**30))
        except subprocess.TimeoutExpired:status='timeout'
        except MemoryError:status='memory_limit'
    unchanged=source=={str(p):sha(p) for p in source_files()}
    receipt={'mode':args.mode,'exit_code':status,'seconds':time.monotonic()-start,'canonical_source_unchanged':unchanged,
             'whole_tree_memory_gib':1.7,'threads':2}
    atomic_json(args.output/'process-receipt.json',receipt);print(json.dumps(receipt))
    return 0 if status==0 and unchanged else 2


if __name__=='__main__':raise SystemExit(main())
