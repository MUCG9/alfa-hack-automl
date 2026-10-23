"""Bounded fixed CPU-embedding screen vs verified strong saved predictions."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from automl.contracts.messages import TaskSpec,canonical_hash
from automl.contracts.embeddings import EmbeddingRequest
from automl.execution.embeddings_api import fit_predict_embeddings
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.processes import wait_owned
from automl.infrastructure.runtime import source_files
from prepare_selector_confirmation import sha


def case(args):
    import numpy as np
    import pandas as pd
    from automl.task_understanding.api import discover,load_inputs
    from automl.evaluation.api import evaluate,make_split
    from automl.publishing.api import save_submission
    kind,scope=args.case.split(':')
    index=0 if scope=='search' else 1
    inventory=json.loads(args.inventory.read_text())
    entry=next(e for e in inventory['cache_inventory'] if e['kind']==kind and e['version']=='v11-featureviews1')
    original=json.loads((Path(entry['run_dir'])/'report.json').read_text())
    request_path=Path(next(r['path'] for r in entry['requests'] if r['scope']==scope))
    old_request=json.loads(request_path.read_text())
    spec,_,train,test,sample,_,hashes=discover(args.class_task if kind=='classification' else args.reg_task,
        loaded=load_inputs(args.class_task if kind=='classification' else args.reg_task,allow_llm=False))
    if sha(spec['paths']['train'])!=old_request['dataset']['sha256']:raise ValueError('Original train differs')
    split=Path(entry['run_dir'])/('split.npz' if scope=='search' else 'confirmation_split.npz')
    with np.load(split,allow_pickle=False) as stored:fitting,held=stored['train'],stored['validation']
    spec['validation_strategy']=original['spec'].get('validation_strategy','auto')
    subset=train.iloc[fitting].reset_index(drop=True)
    inner_a,inner_b,_=make_split(spec,subset,np.asarray(hashes)[fitting],seed=73)
    a,b=fitting[inner_a],fitting[inner_b]
    if spec['validation_strategy']=='time':
        from automl.infrastructure.observation_time import observation_values
        column=original['split']['time_column'];values=observation_values(train[column])[0].to_numpy()
        if not max(values[a])<min(values[b]) or not max(values[fitting])<min(values[held]):raise ValueError('Forward isolation violated')
    elif set(np.asarray(hashes)[a])&set(np.asarray(hashes)[b]):raise ValueError('Inner feature groups overlap')
    classes=tuple(spec.get('classes') or [])
    if kind=='classification':
        ref=next(p for p in old_request['predictions'] if p['model_id']==old_request['control_model_id'])
        control_csv=Path(ref['predictions']['path']);control_prob=Path(ref['probabilities']['path'])
        if sha(control_csv)!=ref['predictions_sha256'] or sha(control_prob)!=ref['probabilities']['sha256']:raise ValueError('Control artifacts changed')
        with np.load(control_prob,allow_pickle=False) as cache:
            if not np.array_equal(cache['row_position'],held):raise ValueError('Control probability rows differ')
            order=cache['classes'].astype(str).tolist()
            probs=cache['probabilities'][:,[order.index(c) for c in classes]]
        control_pred=np.asarray(classes)[probs.argmax(axis=1)]
        expected=original['ensemble']['primary' if scope=='search' else 'confirmation']['metrics'][spec['metric']]
    else:
        long=json.loads(args.long_report.read_text())
        promotion=long['promotions'][-1]['index']
        directory=args.long_report.parent/f'blend-{promotion}-{scope}'
        result=json.loads((directory/'result.json').read_text())
        if canonical_hash(result['recipe'])!=canonical_hash(long['selected_recipe']):raise ValueError('Wrong LONG winner')
        control_csv=directory/'validation_predictions.csv';control_prob=None;probs=None
        control_pred=pd.read_csv(control_csv).y_pred.to_numpy()
        expected=long['best_validation'][spec['metric']] if scope=='search' else long['confirmation_metric']
    control=pd.read_csv(control_csv)
    if not np.array_equal(control.row_position.to_numpy(),held):raise ValueError('Control rows differ')
    truth=train[spec['target']].iloc[held].to_numpy()
    if not np.array_equal(control.y_true.astype(str).to_numpy(),truth.astype(str)):
        if kind!='regression' or not np.allclose(control.y_true.to_numpy(dtype=float),truth.astype(float),rtol=0,atol=1e-9):raise ValueError('Control truth differs')
    before={str(p):sha(p) for p in [request_path,split,control_csv]+([control_prob] if control_prob else [])}
    measured=evaluate(truth,control_pred,kind,spec['metric'],probs,list(classes) or None)[spec['metric']]
    if not np.isclose(measured,expected,rtol=0,atol=1e-10):raise ValueError('Strong control metric differs')
    request=EmbeddingRequest(TaskSpec.from_legacy(spec),tuple(spec.get('categorical_features') or []),classes,
        tuple(map(int,fitting)),tuple(map(int,a)),tuple(map(int,b)),tuple(map(int,held)),seconds=165,epochs=20,threads=2)
    result=fit_predict_embeddings(request,train,test)
    if not result.full_fit_ok:raise ValueError('No complete embedding refit')
    values={}
    for weight in (1.,.1,.25):
        probability=(weight*result.evaluation_probabilities+(1-weight)*probs) if kind=='classification' else None
        prediction=np.asarray(classes)[probability.argmax(axis=1)] if kind=='classification' else weight*result.evaluation_prediction+(1-weight)*control_pred
        values[str(weight)]=evaluate(truth,prediction,kind,spec['metric'],probability,list(classes) or None)[spec['metric']]
    save_submission(spec,sample,test,result.test_prediction,args.output/'submission.csv')
    pd.DataFrame({'row_position':held,'y_true':truth,'y_pred':result.evaluation_prediction}).to_csv(args.output/'validation_predictions.csv',index=False)
    if result.evaluation_probabilities is not None:
        np.savez_compressed(args.output/'validation_probabilities.npz',row_position=held,classes=np.asarray(classes),probabilities=result.evaluation_probabilities)
    if any(sha(p)!=expected_sha for p,expected_sha in before.items()):raise ValueError('Frozen control changed')
    receipt={'kind':kind,'scope':scope,'status':'ok','control':measured,'scores_by_embedding_weight':values,
             'seconds':result.seconds,'best_epoch':result.best_epoch,'full_fit_ok':result.full_fit_ok,
             'submission_sha256':sha(args.output/'submission.csv'),'frozen_evidence_sha256':before,
             'source_sha256':{str(p):sha(p) for p in source_files()},'metadata':result.metadata,
             'evaluation_scope':'fixed candidate/mixes on reused public,not independent/private score'}
    atomic_json(args.output/'case.json',receipt)
    print(json.dumps({k:receipt[k] for k in ('kind','scope','control','scores_by_embedding_weight','seconds')}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--class-task',type=Path,required=True)
    parser.add_argument('--reg-task',type=Path,required=True)
    parser.add_argument('--inventory',type=Path,required=True)
    parser.add_argument('--long-report',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',choices=('classification:search','classification:confirmation','regression:search','regression:confirmation'),help=argparse.SUPPRESS)
    args=parser.parse_args();args.output=args.output.resolve()
    if args.case:return case(args)
    args.output.mkdir(parents=True,exist_ok=False)
    source={str(p):sha(p) for p in source_files()};results=[]
    env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ('KEY','TOKEN','AUTH','SECRET','PASSWORD','PROXY'))}
    env.update(AUTOML_THREADS='2',OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
    for label in ('classification:search','classification:confirmation','regression:search','regression:confirmation'):
        out=args.output/label.replace(':','-');out.mkdir()
        command=[sys.executable,'-u',str(Path(__file__).resolve()),*sys.argv[1:],'--output',str(out),'--case',label]
        started=time.monotonic()
        with (out/'process.log').open('w') as log:
            process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:status=wait_owned(process,180,int(1.7*2**30))
            except subprocess.TimeoutExpired:status='timeout'
            except MemoryError:status='memory_limit'
        row={'case':label,'exit_code':status,'elapsed_seconds':time.monotonic()-started}
        if status==0:row['result']=json.loads((out/'case.json').read_text())
        results.append(row);atomic_json(args.output/'progress.json',{'cases':results})
        print(json.dumps({k:v for k,v in row.items() if k!='result'}),flush=True)
    gates={}
    for kind in ('classification','regression'):
        records=[r['result'] for r in results if r['case'].startswith(kind) and r['exit_code']==0]
        gates[kind]={str(w):len(records)==2 and all((r['scores_by_embedding_weight'][str(w)]>r['control'] if kind=='classification' else r['scores_by_embedding_weight'][str(w)]<r['control']) for r in records) for w in (.1,.25)}
    unchanged=source=={str(p):sha(p) for p in source_files()}
    summary={'cases':results,'same_fixed_mix_improves_both_cuts':gates,'source_unchanged':unchanged,
             'runtime_enabled':False,'promising_screen':unchanged and any(v for g in gates.values() for v in g.values())}
    atomic_json(args.output/'result.json',summary)
    print(json.dumps({k:summary[k] for k in ('same_fixed_mix_improves_both_cuts','source_unchanged','promising_screen')}))
    return 0 if unchanged and all(r['exit_code']==0 for r in results) else 2


if __name__=='__main__':raise SystemExit(main())
