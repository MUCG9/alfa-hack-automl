"""Sequential paired experiments from frozen source bytes, never official submits."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys,time,zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from agent_core import discover,make_split,atomic_json
from automl.infrastructure.processes import ProcessTree
from automl.evaluation.api import make_folds,make_time_split,evaluate
from build_submission import build_files
import numpy as np
import psutil


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--task',type=Path,required=True)
    parser.add_argument('--candidates',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--archive',type=Path)
    parser.add_argument('--seeds',nargs='+',type=int,default=[42,43])
    parser.add_argument('--threads',type=int,default=2)
    parser.add_argument('--timeout',type=int,default=1200)
    parser.add_argument('--memory-gb',type=float,default=2)
    parser.add_argument('--full-fit',action='store_true')
    parser.add_argument('--folds',type=int,default=0)
    parser.add_argument('--time-backtests',nargs='+',type=int)
    args=parser.parse_args()
    out=args.output.resolve(); out.mkdir(parents=True,exist_ok=False)
    source=out/'sources'; source.mkdir()
    if args.archive:
        with zipfile.ZipFile(args.archive) as archive:
            if any('/' in n or '\\' in n for n in archive.namelist()): raise ValueError('Expected flat archive')
            files={n:archive.read(n) for n in archive.namelist()}
    else: files=build_files()
    for name,data in files.items(): (source/name).write_bytes(data)
    spec,profile,train,_,_,_,hashes=discover(args.task)
    if args.time_backtests is not None:
        if not spec.get('time_candidate'): raise ValueError('No unambiguous documented future-period column')
        if args.folds: raise ValueError('Use either forward backtests or full OOF')
        spec['validation_strategy']='time'; spec['time_column']=spec['time_candidate']['column']
    candidates=json.loads(args.candidates.read_text())
    harness=['tools/benchmark_candidates.py','src/automl/task_understanding/service.py',
             'src/automl/evaluation/service.py','src/automl/infrastructure/processes.py']
    manifest={'source':{n:hashlib.sha256(v).hexdigest() for n,v in files.items()},
              'harness':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in harness},'python':sys.version,
              'inputs':{n:hashlib.sha256(Path(p).read_bytes()).hexdigest() for n,p in spec['paths'].items()},
              'task_sha256':hashlib.sha256(args.task.read_bytes()).hexdigest(),
              'spec':spec,'candidates':candidates,'results':[]}
    atomic_json(out/'results.json',manifest)
    if args.folds and args.full_fit: raise ValueError('OOF and full-fit are separate runs')
    partitions=[make_time_split(spec,train,offset=o) for o in args.time_backtests] if args.time_backtests is not None else make_folds(spec,train,hashes,args.folds,args.seeds[0]) if args.folds else [make_split(spec,train,hashes,seed=s) for s in args.seeds]
    for candidate in candidates:
        oof=np.zeros((len(train),len(spec['classes']))) if spec['kind']=='classification' else np.zeros(len(train))
        coverage=np.zeros(len(train),dtype=int); scores=[]
        for number,(tr,va,info) in enumerate(partitions):
            seed=args.time_backtests[number] if args.time_backtests is not None else number if args.folds else args.seeds[number]
            directory=out/candidate['name']/f'seed-{seed}'; directory.mkdir(parents=True)
            split=directory/'split.npz'; np.savez(split,train=tr,validation=va)
            job={'spec':spec,'recipe':candidate['recipe'],'output_dir':str(directory),'split_path':str(split),
                 'threads':args.threads,'full_fit':args.full_fit}
            atomic_json(directory/'job.json',job)
            env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ['KEY','TOKEN','SECRET','PROXY','AUTH','PASSWORD'])}
            for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']: env[k]=str(args.threads)
            started=time.monotonic(); peak=0; stopped=None
            with (directory/'worker.log').open('w') as log:
                worker='automl_worker.py' if (source/'automl_worker.py').exists() else 'agent_worker.py'
                proc=subprocess.Popen([sys.executable,str(source/worker),str(directory/'job.json')],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                tree=ProcessTree(proc)
                try:
                    while proc.poll() is None:
                        tree.refresh()
                        rss=0
                        for p in list(tree.members.values()):
                            try: rss+=p.memory_info().rss
                            except psutil.NoSuchProcess: pass
                        peak=max(peak,rss)
                        if rss>args.memory_gb*2**30: stopped='memory_limit'; break
                        if time.monotonic()-started>args.timeout: stopped='timeout'; break
                        time.sleep(.2)
                finally: tree.terminate()
            result_path=directory/'result.json'
            result=json.loads(result_path.read_text()) if result_path.exists() and not stopped else {'status':stopped or 'error'}
            if proc.returncode!=0 and result.get('status')=='ok':
                result={'status':'worker_exit_error'}
            row={'name':candidate['name'],'seed':seed,'status':result['status'],'metrics':result.get('metrics'),
                 'seconds':round(time.monotonic()-started,3),'peak_mb':round(peak/2**20,1),'split':info,
                 'fit_iterations':result.get('fit_iterations'),'directory':str(directory),'exit_code':proc.returncode}
            manifest['results'].append(row); atomic_json(out/'results.json',manifest)
            print(json.dumps(row,ensure_ascii=False),flush=True)
            if args.folds and result['status']=='ok':
                if spec['kind']=='classification':
                    with np.load(directory/'validation_probabilities.npz') as stored:
                        order=[list(stored['classes'].astype(str)).index(c) for c in spec['classes']]
                        assert np.array_equal(stored['row_position'],va)
                        oof[va]=stored['probabilities'][:,order]
                else:
                    import pandas as pd
                    frame=pd.read_csv(directory/'validation_predictions.csv')
                    assert np.array_equal(frame.row_position,va)
                    oof[va]=frame.y_pred.to_numpy()
                coverage[va]+=1; scores.append(result['metrics'][spec['metric']])
        if args.folds and np.all(coverage==1):
            y=train[spec['target']]
            if spec['kind']=='classification':
                y=y.astype(str); predictions=np.asarray(spec['classes'])[oof.argmax(axis=1)]
            else: predictions=oof
            metrics=evaluate(y,predictions,spec['kind'],spec['metric'],oof if spec['kind']=='classification' else None,spec['classes'])
            np.savez_compressed(out/candidate['name']/'oof.npz',predictions=oof,row_position=np.arange(len(train)),classes=np.asarray(spec['classes'] or []))
            summary={'fold_mean':float(np.mean(scores)),'fold_std':float(np.std(scores)),'pooled_oof':metrics,'coverage':'exactly_once','scope':'fixed recipe full CV; no post-OOF tuning'}
            manifest.setdefault('oof',{})[candidate['name']]=summary
            atomic_json(out/'results.json',manifest); print(json.dumps(summary),flush=True)


if __name__=='__main__': main()
