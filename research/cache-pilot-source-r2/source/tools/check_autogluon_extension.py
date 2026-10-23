"""Optional synthetic isolation check for the dev-only pinned framework study."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tests'))
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.processes import wait_owned
from build_submission import build_files
from test_feature_views import fixture


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=args.output.resolve();root.mkdir(parents=True,exist_ok=False)
    data=root/'synthetic';data.mkdir();spec,train=fixture(data)
    files=build_files();extension=(ROOT/'tools/autogluon_worker.py').read_bytes()
    source=root/'sources';source.mkdir()
    for name,payload in dict(files,**{'research_worker.py':extension}).items():
        (source/name).write_bytes(payload)
    before={n:hashlib.sha256(v).hexdigest() for n,v in files.items()}
    env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ['KEY','TOKEN','SECRET','AUTH','PASSWORD','PROXY'])}
    env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',AUTOML_THREADS='1')
    records=[];exports=[];probabilities=[]
    input_sha=[]
    for number in range(2):
        output=root/f'worker-{number}';output.mkdir()
        job={'spec':spec,'recipe':{'engine':'autogluon','params':{'seed':42},'feature_code':''},
            'split_path':str(data/'split.npz'),'output_dir':str(output),'threads':1}
        atomic_json(output/'job.json',job)
        input_sha.append(hashlib.sha256(Path(spec['paths']['train']).read_bytes()).hexdigest())
        with (output/'worker.log').open('w') as log:
            process=subprocess.Popen([sys.executable,str(source/'research_worker.py'),str(output/'job.json')],
                cwd=data,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:status=wait_owned(process,timeout=180,memory_bytes=int(1.7*2**30))
            except subprocess.TimeoutExpired:status='watchdog_timeout'
            except MemoryError:status='memory_limit'
        record=json.loads((output/'result.json').read_text()) if (output/'result.json').exists() else {}
        records.append({'exit_code':status,**record})
        if status!=0 or record.get('status')!='ok':
            atomic_json(root/'receipt.json',{'passed':False,'records':records,'scope':'optional synthetic framework check'})
            raise SystemExit(1)
        exports.append((output/'submission.csv').read_bytes())
        with np.load(output/'test_probabilities.npz') as stored:
            probabilities.append(stored['probabilities'].copy())
            if stored['classes'].astype(str).tolist()!=spec['classes']:raise ValueError('Class alignment failed')
        train.loc[288:,'answer']=np.tile(['A','M','Z'],24)
        train.to_csv(spec['paths']['train'],index=False)
    predictions=pd.read_csv(root/'worker-0/submission.csv')
    checks={
        'both_fit_refit_export_pass':all(r.get('full_refit_map') and r['calibration_status']=='inner_holdout_before_full_refit_not_oof' for r in records),
        'outer_label_poisoning_invariant':exports[0]==exports[1] and records[0]['class_factors']==records[1]['class_factors'] and input_sha[0]!=input_sha[1],
        'probability_id_contract':np.isfinite(probabilities).all() and np.allclose(np.sum(probabilities,axis=2),1.) and predictions.record.tolist()==list(range(1000,1012)),
        'source_unchanged':before=={n:hashlib.sha256(v).hexdigest() for n,v in build_files().items()},
        'frozen_extension_unchanged':extension==(ROOT/'tools/autogluon_worker.py').read_bytes()}
    result={'passed':all(checks.values()),'checks':checks,'records':records,'source_sha256':before,
        'extension_sha256':hashlib.sha256(extension).hexdigest(),'fixture_train_sha256':input_sha,
        'scope':'Optional synthetic lifecycle/isolation, not public quality or core unique-check count'}
    atomic_json(root/'receipt.json',result)
    print(json.dumps({'passed':result['passed'],'checks':checks}),flush=True)
    if not result['passed']:raise SystemExit(1)


if __name__=='__main__':main()
