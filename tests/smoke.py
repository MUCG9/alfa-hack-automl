from pathlib import Path
import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
SOLUTION=ROOT/'solution.py'
TMP=ROOT/'test-runs'
TMP.mkdir(exist_ok=True)
rng=np.random.default_rng(123)


def run_case(name,kind,text=False,numeric_labels=False):
    root=TMP/name
    root.mkdir(exist_ok=True)
    n=180
    x=rng.normal(size=n)
    cats=np.where(x>0,'positive','negative').astype(object)
    cats[::13]=None
    target=x*3+rng.normal(size=n)*.1 if kind=='regression' else (x>0).astype(int)
    if kind=='classification' and not numeric_labels:
        target=np.where(target,'yes','no')
    train=pd.DataFrame({'record_code':np.arange(n)+100,'feature_a':x,'category_z':cats,'outcome_value':target})
    test=pd.DataFrame({'record_code':np.arange(18)+999,'feature_a':rng.normal(size=18),'category_z':['new-category']*18})
    if text:
        train['review_text']=[('excellent reliable helpful positive experience ' if x[i]>0 else 'terrible broken disappointing negative experience ')+f' unique item number {i} with detailed customer feedback' for i in range(n)]
        test['review_text']=['excellent reliable helpful positive experience and detailed customer feedback']*9+['terrible broken disappointing negative experience and detailed customer feedback']*9
    train.to_csv(root/'train.csv',index=False)
    test.to_csv(root/'test.csv',index=False)
    sample=pd.DataFrame({'record_code':test['record_code'],'outcome_value':0 if kind=='regression' or numeric_labels else 'yes'})
    sample.to_csv(root/'sample_submission.csv',index=False)
    dictionary=pd.DataFrame({'feature':train.columns,'role':['id' if c=='record_code' else 'target' if c=='outcome_value' else 'feature' for c in train],
                              'dtype':[str(train[c].dtype) for c in train]})
    dictionary.to_csv(root/'data_dictionary.csv',index=False)
    (root/'task.md').write_text(f'Task: {kind}. Metric: '+('RMSE' if kind=='regression' else 'Macro F1')+'.\nTrain train.csv, test test.csv, data_dictionary.csv, sample_submission.csv. Save submission.csv.',encoding='utf-8')
    env={k:v for k,v in os.environ.items() if not k.startswith('OPENAI_')}
    run_name='smoke-'+str(time.time_ns())
    result=subprocess.run([sys.executable,str(SOLUTION),str(root/'task.md'),'--offline','--max-experiments','1','--time-budget','300','--run-name',run_name],env=env,capture_output=True,text=True,timeout=90)
    if result.returncode:
        raise AssertionError(f'{name} failed: {result.stderr[-3000:]}')
    report=json.loads((root/'automl_runs'/run_name/'report.json').read_text())
    submission=pd.read_csv(root/'submission.csv')
    assert submission.columns.tolist()==sample.columns.tolist()
    assert submission.record_code.tolist()==test.record_code.tolist()
    assert not submission.isna().any().any()
    assert report['best_validation'] is not None,report
    assert report['final_fit_status']=='ok',report
    assert report['integrity_ok'],report
    if kind=='classification':
        assert set(submission.outcome_value.astype(str))<=set(train.outcome_value.astype(str))
    if text:
        assert report['spec']['text_features']==['review_text']
        assert report['experiments'][0]['recipe']['engine']=='linear_text'
    return {'case':name,'status':'passed','metrics':report['best_validation'],
            'text_features':report['spec']['text_features'],'elapsed_seconds':report['elapsed_seconds']}


cases=[run_case('renamed_regression','regression'),
       run_case('numeric_binary_labels','classification',numeric_labels=True),
       run_case('unseen_categories','classification'),
       run_case('text_classification','classification',text=True)]
sys.path.insert(0,str(SOLUTION.parent))
from agent_worker import feature_transform
try:
    feature_transform('import os\ndef transform(df): return df',pd.DataFrame({'x':[1]}),pd.DataFrame({'x':[2]}))
except ValueError:
    cases.append({'case':'generated_code_import_rejected','status':'passed'})
else:
    raise AssertionError('Disallowed feature code was accepted')
(TMP/'synthetic_test_results.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2))
print(json.dumps(cases,ensure_ascii=False,indent=2))
