"""Bounded real lifecycles of the exact release's default long-mode launcher."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
sys.path.insert(0,str(ROOT/'src'))
from automl.infrastructure.atomic import atomic_json
from build_submission import build_files
from verify_release import run_check
from test_resilience import task
import numpy as np
import pandas as pd


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    expected=build_files('long01-submit')
    with zipfile.ZipFile(args.archive) as archive:
        files={name:archive.read(name) for name in archive.namelist()}
    if files!=expected: raise ValueError('Archive source mismatch')
    args.output.mkdir(parents=True,exist_ok=False)
    results=[]
    env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in
         ('KEY','TOKEN','SECRET','AUTH','PASSWORD','PROXY'))}
    env.update(AUTOML_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    for kind in ('classification','regression'):
        out=args.output/kind
        out.mkdir()
        task(out,3,'Log loss')
        if kind=='regression':
            train=pd.read_csv(out/'train.csv')
            train['answer']=5+2*train['x']+train['signal']*.1
            train.to_csv(out/'train.csv',index=False)
            test=pd.read_csv(out/'test.csv')
            pd.DataFrame({'record':test.record,'answer':0.}).to_csv(out/'sample_submission.csv',index=False)
            (out/'task.md').write_text('Regression. Target answer. Metric RMSE. train.csv test.csv data_dictionary.csv sample_submission.csv')
        for name,content in files.items(): (out/name).write_bytes(content)
        # Override counts ONLY, not long mode/offline/deadline/reserve defaults.
        command=[sys.executable,'solution.py','task.md','--max-experiments','2','--max-extended-experiments','1']
        run=run_check(command,out.resolve(),env,150,int(1.2*2**30))
        row={'kind':kind,'command':command,'exit_code':run['exit_code'],'passed':False}
        atomic_json(out/'process.json',run)
        report_path=out/'automl_runs/run-v2/report.json'
        if run['exit_code']==0 and report_path.is_file():
            report=json.loads(report_path.read_text())
            actual=pd.read_csv(out/'submission.csv')
            sample=pd.read_csv(out/'sample_submission.csv')
            data=actual.iloc[:,1:].to_numpy(dtype=float)
            row.update({k:report.get(k) for k in ('version','integrity_ok','exported_full_fit_ok','final_fit_status','anytime')})
            row['passed']=(report.get('version')=='long-01-anytime'
                and report.get('integrity_ok') is True and report.get('exported_full_fit_ok') is True
                and report['anytime']['wall_budget']==10800 and report['anytime']['finalization_reserve']==1200
                and report['anytime']['legacy_baseline_trials']==2 and report['anytime']['extended_attempts']==1
                and not report.get('llm_calls')
                and actual.shape==sample.shape and actual.columns.tolist()==sample.columns.tolist()
                and actual.iloc[:,0].tolist()==sample.iloc[:,0].tolist() and np.isfinite(data).all()
                and hashlib.sha256((out/'submission.csv').read_bytes()).hexdigest()==report['submission_sha256']
                and all((out/name).read_bytes()==content for name,content in files.items()))
        results.append(row)
        print(json.dumps(row),flush=True)
    receipt={'archive_sha256':hashlib.sha256(args.archive.read_bytes()).hexdigest(),
             'scope':'Two bounded default-launcher fixture lifecycles; not new public quality runs',
             'results':results,'passed':all(r['passed'] for r in results)}
    atomic_json(args.output/'results.json',receipt)
    if not receipt['passed']: raise SystemExit(1)


if __name__=='__main__': main()
