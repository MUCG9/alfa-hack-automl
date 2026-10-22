"""Small CPU end-to-end checks from standalone compiled modules, not source shims."""
from pathlib import Path
import json,os,subprocess,sys,tempfile,unittest
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'tools'))
from build_submission import build_files


class ContractLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.compiled=build_files()

    def run_case(self,kind,metric,no_id=False,reorder=False,separator=',',probabilities=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name,data in self.compiled.items(): (root/name).write_bytes(data)
            rng=np.random.default_rng(117); n=180; x=rng.normal(size=n)
            truth=2+np.abs(x)*3 if kind=='regression' else np.where(x>0,'yes','no')
            train=pd.DataFrame({'signal':x,'answer':truth})
            test=pd.DataFrame({'signal':[-1.,.2,1.4,-.4,2.,-2.]})
            if not no_id:
                train.insert(0,'record',range(n)); test.insert(0,'record',[600,601,602,603,604,605])
            if probabilities:
                sample=pd.DataFrame({'yes':[.5]*6,'no':[.5]*6})
            else:
                sample=pd.DataFrame({'forecast':[0.]*6 if kind=='regression' else ['yes']*6})
            if not no_id: sample.insert(0,'record',test.record)
            if reorder: sample=sample.iloc[[2,0,5,3,1,4]].reset_index(drop=True)
            extension='tsv' if separator=='\t' else 'csv'
            names=[f'fitting.{extension}',f'evaluation.{extension}',f'example.{extension}']
            for frame,name in zip([train,test,sample],names): frame.to_csv(root/name,index=False,sep=separator)
            (root/'task.md').write_text(f'{kind}. Primary metric: {metric}. Files: '+ ' '.join(names))
            env={k:v for k,v in os.environ.items() if not k.startswith('OPENAI_')}
            env.update(AUTOML_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
            result=subprocess.run([sys.executable,'solution.py','task.md','--offline','--max-experiments','1','--time-budget','300'],cwd=root,env=env,capture_output=True,text=True,timeout=120)
            self.assertEqual(result.returncode,0,result.stderr[-2500:]+'\n'+result.stdout[-2500:])
            report=json.loads((root/'automl_runs/run-v2/report.json').read_text())
            output=pd.read_csv(root/'submission.csv')
            self.assertEqual(report['spec']['metric'],metric)
            self.assertEqual(report['final_fit_status'],'ok')
            self.assertTrue(report['integrity_ok']); self.assertIsNotNone(report['best_validation'])
            self.assertEqual(output.columns.tolist(),sample.columns.tolist())
            self.assertEqual(len(output),len(test)); self.assertFalse(output.isna().any().any())
            if no_id: self.assertIsNone(report['spec']['id'])
            else: self.assertEqual(output.record.tolist(),sample.record.tolist())
            if probabilities:
                self.assertTrue(np.allclose(output.sum(axis=1),1))
                self.assertTrue(((output>=0)&(output<=1)).all().all())
            return report

    def test_mape_tsv_without_dictionary_or_identifier(self):
        result=self.run_case('regression','mape',no_id=True,separator='\t')
        self.assertFalse(result['spec']['greater_is_better'])

    def test_balanced_accuracy_semicolon_csv_with_reordered_ids(self):
        result=self.run_case('classification','balanced_accuracy',reorder=True,separator=';')
        self.assertTrue(result['spec']['greater_is_better'])
        self.assertEqual(result['spec']['sample_test_positions'],[2,0,5,3,1,4])

    def test_probability_matrix_without_identifier(self):
        self.run_case('classification','log_loss',no_id=True,probabilities=True)

    def test_rmsle_lifecycle_uses_requested_objective(self):
        self.run_case('regression','rmsle',no_id=True)


if __name__=='__main__': unittest.main(verbosity=2)
