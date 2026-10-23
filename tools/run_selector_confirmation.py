"""One immutable, guarded SEL confirmation; never enable the runtime selector."""
from dataclasses import replace
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
from automl.contracts.messages import canonical_hash,PredictionBundle
from automl.error_analysis.api import ErrorAnalysisRequest,ErrorAnalysisProtocol,ModelPredictionRef
from automl.error_analysis.preparation import artifact
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.processes import wait_owned
from automl.infrastructure.runtime import source_files
from build_submission import build_files
from prepare_selector_confirmation import long_run_ready,sha


def validate(plan,output,baseline,search_request):
    """Fail BEFORE any child/fit/output if frozen scope or artifacts changed."""
    if plan.get('experiment')!='SEL-01-one-confirmation-screen':
        raise ValueError('Wrong experiment')
    if plan.get('budget')!={'timeout_seconds':900,'threads':2,'whole_tree_memory_gib':1.7}:
        raise ValueError('Budget differs from predeclared single-recipe screen')
    if 'model-'+canonical_hash(plan['recipe'])[:20]!=plan['candidate_id']:
        raise ValueError('Candidate recipe identity changed')
    output=Path(output).resolve()
    if output.exists(): raise FileExistsError('Never overwrite or automatically retry a fit')
    if output.is_relative_to(Path(plan['long_run']).resolve()):
        raise ValueError('Never write inside LONG-01')
    protected=plan['protected_artifacts_sha256']
    if str(Path(search_request).resolve()) not in protected:
        raise ValueError('Search request is not predeclared evidence')
    for path,expected in protected.items():
        if output==Path(path).resolve() or Path(path).resolve().is_relative_to(output):
            raise ValueError('Output would contain protected evidence')
        if sha(path)!=expected: raise ValueError('Frozen artifact changed: '+Path(path).name)
    if sha(plan['original_confirmation_split']['path'])!=plan['original_confirmation_split']['sha256']:
        raise ValueError('Original split changed')
    compiled={n:hashlib.sha256(b).hexdigest() for n,b in build_files().items()}
    if compiled!=plan['compiled_source_sha256']:
        raise ValueError('Compiled source changed since predeclared plan')
    if not long_run_ready(plan['long_run']):
        raise ValueError('LONG-01 not complete; overlapping fits forbidden')
    baseline=Path(baseline).resolve()
    closed=json.loads(baseline.read_text())
    inventory_path=baseline.parent/'baseline_inventory.json'
    if (str(inventory_path) not in protected
            or closed.get('inventory_sha256')!=sha(inventory_path)
            or closed.get('baseline_complete') is not True or len(closed.get('original_runs',[]))!=4):
        raise ValueError('Verified local BASE-01 closure required')
    expected_runs={(v,k) for v in ('v11-featureviews1','v16-mean1') for k in ('classification','regression')}
    if {(r['version'],r['kind']) for r in closed['original_runs']}!=expected_runs:
        raise ValueError('Missing original BASE run')
    for record in closed['original_runs']:
        if len(record['scopes'])!=2 or {s['scope'] for s in record['scopes']}!={'search','confirmation'}:
            raise ValueError('Missing original BASE scope')
        for scope in record['scopes']:
            if sha(scope['path'])!=scope['profile_sha256']:
                raise ValueError('BASE passport changed')
    inventory=json.loads(inventory_path.read_text())
    for kind,files in inventory['inputs'].items():
        for name,ref in files.items():
            if sha(Path(inventory['data_root'])/kind/name)!=ref['expected_sha256']:
                raise ValueError('Original public input changed')
    return compiled


def worker(plan,output,task):
    # Set this before importing runner, whose resource setting is import-time.
    os.environ['AUTOML_THREADS']='2'
    from automl.search.runner import run_worker,discover,load_inputs
    report=json.loads(Path(plan['original_report']).read_text())
    original=report['spec']
    spec=discover(task,loaded=load_inputs(task,allow_llm=False))[0]
    for key in ('features','classes','n_train','n_test','id','target','kind','metric','greater_is_better'):
        if spec.get(key)!=original.get(key): raise ValueError('Original task differs: '+key)
    expected=ErrorAnalysisRequest.from_json(Path(plan['original_confirmation_request']).read_text()).dataset.sha256
    if sha(spec['paths']['train'])!=expected: raise ValueError('Training input differs')
    spec['root']=str(output.resolve())
    result=run_worker(spec,plan['recipe'],output/'candidate',
                      Path(plan['original_confirmation_split']['path']),895,full_fit=False)
    atomic_json(output/'evaluation.json',result)
    return 0 if result.get('status')=='ok' else 2


def extend_request(plan,output,manifest,baseline,search_request,plan_path):
    """Add new provenance, never relabel a new prediction as historical V11."""
    request=ErrorAnalysisRequest.from_json(Path(plan['original_confirmation_request']).read_text())
    if any(p.model_id==plan['candidate_id'] for p in request.predictions):
        raise ValueError('Candidate already has confirmation; no new evaluation needed')
    result=json.loads((output/'evaluation.json').read_text())
    if result.get('status')!='ok' or result.get('full_fit') is not False:
        raise ValueError('Successful held-out candidate required')
    reference=request.predictions[0]
    directory=output/'candidate'
    source=output/'compiled-source.json'
    atomic_json(source,manifest)
    predictions=directory/'validation_predictions.csv'
    probability=directory/'validation_probabilities.npz'
    new=ModelPredictionRef(plan['candidate_id'],'confirmation',canonical_hash(plan['recipe']),canonical_hash(manifest),
        PredictionBundle(str(predictions.resolve()),reference.predictions.rows,reference.predictions.columns,
                         reference.predictions.classes,reference.predictions.split_sha256),
        sha(predictions),reference.row_positions_sha256,reference.split,
        probabilities=artifact(probability),probability_kind='raw',recorded_result=artifact(output/'evaluation.json'))
    old=ErrorAnalysisProtocol.from_json(Path(request.protocol.path).read_text())
    protocol=replace(old,protocol_id='SEL-01-one-confirmation-with-frozen-controls',
                     evidence=old.evidence+tuple(artifact(p) for p in (source,baseline,plan_path,output/'fit-receipt.json')))
    protocol_path=output/'protocol.json'
    atomic_json(protocol_path,protocol.to_dict())
    new_request=replace(request,request_id='SEL-01-augmented-confirmation',protocol_id=protocol.protocol_id,
                        protocol=artifact(protocol_path),predictions=request.predictions+(new,),output_dir=str(output/'passport'))
    request_path=output/'request.json'
    atomic_json(request_path,new_request.to_dict())
    from replay_marginal_selection import replay
    return replay(Path(search_request),request_path,Path(plan['original_report']),output/'replay.json')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--search-request',type=Path,required=True)
    parser.add_argument('--task',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    plan=json.loads(args.plan.read_text())
    if args.worker: return worker(plan,args.output,args.task)
    manifest=validate(plan,args.output,args.baseline,args.search_request)
    source_before={str(p.resolve()):sha(p) for p in source_files()}
    args.output=args.output.resolve()
    args.output.mkdir(parents=True,exist_ok=False)
    plan_sha=sha(args.plan)
    env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ('KEY','TOKEN','SECRET','AUTH','PASSWORD','PROXY'))}
    env.update(AUTOML_THREADS='2',OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2')
    started=time.monotonic()
    command=[sys.executable,'-u',str(Path(__file__).resolve()),*sys.argv[1:],'--worker']
    with (args.output/'process.log').open('w') as stream:
        process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        try: status=wait_owned(process,900,int(1.7*2**30))
        except subprocess.TimeoutExpired: status='timeout'
        except MemoryError: status='memory_limit'
    protected_ok=all(sha(p)==expected for p,expected in plan['protected_artifacts_sha256'].items())
    source_ok=(manifest=={n:hashlib.sha256(b).hexdigest() for n,b in build_files().items()}
               and source_before=={str(p.resolve()):sha(p) for p in source_files()})
    receipt={'experiment':plan['experiment'],'exit_code':status,'elapsed_seconds':time.monotonic()-started,
             'plan_sha256':plan_sha,'plan_unchanged':sha(args.plan)==plan_sha,'frozen_artifacts_unchanged':protected_ok,
             'compiled_source_unchanged':source_ok,'new_recipe_evaluations':1,'budget':plan['budget'],
             'canonical_source_sha256':source_before,
             'executor_sha256':sha(__file__),'runtime_selector_enabled':False}
    atomic_json(args.output/'fit-receipt.json',receipt)
    if status!=0 or not all((protected_ok,source_ok,receipt['plan_unchanged'])):
        print(json.dumps(receipt));return 2
    result=extend_request(plan,args.output,manifest,args.baseline,args.search_request,args.plan)
    print(json.dumps({k:result[k] for k in ('recommendation','control','candidate','both_cached_cuts_strictly_improve')}))
    return 0


if __name__=='__main__': raise SystemExit(main())
