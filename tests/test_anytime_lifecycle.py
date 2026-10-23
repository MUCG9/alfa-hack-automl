"""Small REAL source/flat CLI lifecycles; bounded attempts, not long-run scores."""
from pathlib import Path
import json,os,subprocess,sys,tempfile,unittest
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'));sys.path.insert(0,str(ROOT/'tools'))
from build_submission import build_files
from test_resilience import task


class AnytimeLifecycleTests(unittest.TestCase):
    def run_case(self,kind,flat):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);data=base/'data';data.mkdir();entry=ROOT/'solution.py'
            if flat:
                app=base/'app';app.mkdir()
                for name,content in build_files().items():(app/name).write_bytes(content)
                entry=app/'solution.py'
            if kind=='classification':path=task(data,3,'Log loss')
            else:
                rng=np.random.default_rng(218)
                train=pd.DataFrame({'id':np.arange(240),'x':rng.normal(size=240)})
                train['y']=5+3*train.x+rng.normal(size=240)*.2
                test=pd.DataFrame({'id':np.arange(20)+1000,'x':rng.normal(size=20)})
                train.to_csv(data/'train.csv',index=False);test.to_csv(data/'test.csv',index=False)
                pd.DataFrame({'id':test.id,'y':0.}).to_csv(data/'sample_submission.csv',index=False)
                pd.DataFrame({'feature':['id','x','y'],'role':['id','feature','target']}).to_csv(data/'data_dictionary.csv',index=False)
                path=data/'task.md';path.write_text('Regression. Target y. Metric RMSE. train.csv test.csv data_dictionary.csv sample_submission.csv')
            env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ['KEY','TOKEN','SECRET','PROXY','AUTH','PASSWORD'])}
            env.update(AUTOML_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
            result=subprocess.run([sys.executable,str(entry),str(path),'--offline','--search-until-deadline',
                '--time-budget','420','--finalization-reserve','60','--max-experiments','2',
                '--max-extended-experiments','2'],env=env,capture_output=True,text=True,timeout=120)
            self.assertEqual(result.returncode,0,result.stderr[-4000:]+result.stdout[-2000:])
            report=json.loads((data/'automl_runs/run-v2/report.json').read_text())
            self.assertTrue(report['integrity_ok']);self.assertTrue(report['exported_full_fit_ok'])
            self.assertEqual(report['anytime']['extended_attempts'],2)
            self.assertEqual(report['anytime']['legacy_baseline_trials'],2)
            output=pd.read_csv(data/'submission.csv');sample=pd.read_csv(data/'sample_submission.csv')
            self.assertEqual(output.columns.tolist(),sample.columns.tolist())
            self.assertEqual(output.iloc[:,0].tolist(),sample.iloc[:,0].tolist())
            self.assertTrue(np.isfinite(output.iloc[:,1:].to_numpy(dtype=float)).all())

    def test_source_classification(self):self.run_case('classification',False)
    def test_flat_classification(self):self.run_case('classification',True)
    def test_source_regression(self):self.run_case('regression',False)
    def test_flat_regression(self):self.run_case('regression',True)


if __name__=='__main__':unittest.main(verbosity=2)
