"""Paired CPU ablation from frozen sources; organizer CSVs stay external to Git."""
from pathlib import Path
import argparse,copy,hashlib,json,os,subprocess,sys,time,zipfile
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from agent_core import discover,make_split,atomic_json
from build_submission import build_files

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--task',type=Path,action='append',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--baseline-zip',type=Path,default=ROOT/'release/solution-v2.zip')
    parser.add_argument('--threads',type=int,default=2,choices=range(1,9))
    parser.add_argument('--seeds',type=int,nargs='+',default=[42,43])
    args=parser.parse_args(); out=args.output.resolve(); out.mkdir(parents=True,exist_ok=False)
    frozen=out/'sources'; frozen.mkdir()
    for name,data in build_files().items(): (frozen/name).write_bytes(data)
    legacy=out/'baseline'; legacy.mkdir()
    with zipfile.ZipFile(args.baseline_zip) as archive:
        if any('/' in n or '\\' in n for n in archive.namelist()): raise ValueError('Only a trusted flat baseline archive is supported')
        archive.extractall(legacy)
    evidence=json.loads((ROOT/'docs/v2_results.json').read_text())
    manifest={'baseline_zip_sha256':hashlib.sha256(args.baseline_zip.read_bytes()).hexdigest(),
              'compiled_files':{n:hashlib.sha256(d).hexdigest() for n,d in build_files().items()},'results':[]}
    atomic_json(out/'results.json',manifest)
    for number,path in enumerate(args.task):
        spec,_,train,_,_,_,hashes=discover(path)
        known=next(t for t in evidence['tasks'] if t['task']==spec['kind'])
        selected=next(v for v in known['versions'] if v['version']=='v2')['selected_recipe']
        recipe=copy.deepcopy(selected['components'][0] if selected['engine']=='ensemble' else selected)
        recipe['params']['nested_stopping']=True
        variants=[('v2',{},True),('noop',{},False)]
        if spec['kind']=='classification':
            variants += [('duplicate-half',{'duplicate_beta':.5},False),('compress',{'sampling':'compress'},False),
                         ('under85',{'sampling':'under','majority_fraction':.85},False),
                         ('over150',{'sampling':'over','factor':1.5},False),('cap20',{'class_weight_cap':20},False)]
        else:
            variants += [('mask15',{'augmentation':'mask','copy_fraction':.15,'mask_probability':.1},False),
                         ('mask25',{'augmentation':'mask','copy_fraction':.25,'mask_probability':.15},False)]
        for name,policy,old in variants:
            for seed in args.seeds:
                directory=out/f'task-{number:02d}'/name/f'seed-{seed}'; directory.mkdir(parents=True)
                tr,va,split=make_split(spec,train,hashes,seed=seed)
                np.savez(directory/'split.npz',train=tr,validation=va)
                candidate=copy.deepcopy(recipe)
                if policy: candidate['data_policy']=policy
                atomic_json(directory/'job.json',{'spec':spec,'recipe':candidate,'output_dir':str(directory),
                    'split_path':str(directory/'split.npz'),'threads':args.threads,'full_fit':False})
                env={k:v for k,v in os.environ.items() if not any(part in k.upper() for part in ['KEY','TOKEN','SECRET','AUTH','PROXY','PASSWORD'])}
                for variable in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']: env[variable]=str(args.threads)
                started=time.monotonic()
                with (directory/'worker.log').open('w') as log:
                    proc=subprocess.run([sys.executable,str((legacy if old else frozen)/('agent_worker.py' if old else 'automl_worker.py')),str(directory/'job.json')],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=900)
                result=json.loads((directory/'result.json').read_text())
                row={'task':str(path.resolve()),'kind':spec['kind'],'variant':name,'seed':seed,'split':split,
                     'metric':spec['metric'],'value':result.get('metrics',{}).get(spec['metric']),'status':result['status'],
                     'seconds':round(time.monotonic()-started,3),'exit_code':proc.returncode,'recipe':candidate,
                     'data_policy_runs':result.get('data_policy_runs',[]),'output_dir':str(directory)}
                if name=='noop':
                    original=pd.read_csv(out/f'task-{number:02d}/v2/seed-{seed}/validation_predictions.csv')
                    current=pd.read_csv(directory/'validation_predictions.csv')
                    assert original.row_position.equals(current.row_position)
                    if spec['kind']=='classification': assert original.y_pred.equals(current.y_pred)
                    else: assert np.allclose(original.y_pred,current.y_pred,rtol=1e-6,atol=1e-8)
                    row['parity']=True
                manifest['results'].append(row); atomic_json(out/'results.json',manifest)
                print(json.dumps({k:row[k] for k in ['kind','variant','seed','metric','value','status','seconds']},ensure_ascii=False),flush=True)
                if proc.returncode or result['status']!='ok': raise RuntimeError('Experiment failed; inspect worker.log')

if __name__=='__main__': main()
