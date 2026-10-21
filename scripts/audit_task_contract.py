"""Offline contract diagnostics against the exact submitted v2 source snapshot.

Synthetic scenarios illustrate absent guarantees discussed in the webinar. They
are NOT revealed private tasks, nor a model-quality benchmark or private score.
"""
from pathlib import Path
import argparse,hashlib,json,sys,zipfile
BASE=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=BASE/'test-runs/contract-audit')
args=parser.parse_args()
ROOT=args.output.resolve()
ROOT.mkdir(parents=True,exist_ok=False)
SOURCE=ROOT/'frozen-source'
archive_path=BASE/'release/solution-v2.zip'
if hashlib.sha256(archive_path.read_bytes()).hexdigest()!='b429f04a231b5fa7f5fb52d8008aa019dbc6c53cc6e5f81a6ff06999edc1602a':
    raise ValueError('Frozen v2 archive changed')
with zipfile.ZipFile(archive_path) as archive:
    if any('/' in n or '\\' in n for n in archive.namelist()):
        raise ValueError('Unexpected archive path')
    archive.extractall(SOURCE)
sys.path.insert(0,str(SOURCE))
import numpy as np,pandas as pd
from agent_core import discover,make_split
cases=[
 ('standard_regression','regression','rmse','Regression. RMSE.'),
 ('standard_classification','classification','macro_f1','Classification. Macro F1.'),
 ('different_filenames','regression','rmse','Regression. RMSE. Fit using fitting.csv and predict evaluation.csv; example.csv describes the output. Schema: schema.csv.'),
 ('no_dictionary','regression','rmse','Regression. RMSE. train.csv contains target answer; predict answer for test.csv using sample_submission.csv.'),
 ('no_id_output','regression','rmse','Regression. RMSE. Output one answer column in the same row order as test.csv; no ID column in the output.'),
 ('multiple_targets','regression','rmse','Regression. Predict BOTH answer and cost. Return two target columns plus record as in sample_submission.csv.'),
 ('ranking','ranking','ndcg','Rank documents within each query. Metric NDCG@10 averaged across queries. query identifies the ranking group; answer is relevance.'),
 ('temporal_validation','regression','rmse','Regression. RMSE. Forecast future demand from date; evaluate on later dates, never train on future dates to validate earlier observations.'),
 ('entity_validation','classification','macro_f1','Classification. Macro F1. Predict churn for previously unseen clients. All rows from one client must remain in the same validation fold; client is the group key.'),
 ('mape','regression','mape','Regression. Metric MAPE (mean absolute percentage error); minimize it.'),
 ('balanced_accuracy','classification','balanced_accuracy','Classification. Metric: balanced accuracy. Classes are imbalanced.'),
 ('binary_probability','classification','roc_auc','Classification. ROC AUC. Output the probability of class c1.'),
 ('different_output_name','regression','rmse','Regression. RMSE. Train target answer; save prediction column as in sample_submission.csv.'),
 ('sample_id_order','regression','rmse','Regression. RMSE. Output rows must follow sample_submission.csv ID order, which differs from test.csv order. Align by record.'),
]
records=[]
for name,kind,metric,text in cases:
    directory=ROOT/'contract-audit'/name; directory.mkdir(parents=True,exist_ok=False)
    n=200; positions=np.arange(n)
    classification=kind=='classification'
    train=pd.DataFrame({'record':positions,'x':positions*.1,'answer':np.where(positions%2==0,'c0','c1') if classification else 10+positions*.5})
    test=pd.DataFrame({'record':np.arange(20)+1000,'x':np.arange(20)*.1})
    sample=pd.DataFrame({'record':test.record,'answer':'c0' if classification else 0.})
    dictionary=pd.DataFrame({'feature':['record','x','answer'],'role':['id','feature','target']})
    if name=='multiple_targets':
        train['cost']=20+positions*.3; sample['cost']=0.
        dictionary=pd.concat([dictionary,pd.DataFrame({'feature':['cost'],'role':['target']})],ignore_index=True)
    if name=='no_id_output': sample=sample[['answer']]
    if name=='ranking':
        train['query']=positions//10; train['answer']=positions%3; test['query']=np.arange(20)//10
        dictionary=pd.concat([dictionary,pd.DataFrame({'feature':['query'],'role':['group']})],ignore_index=True)
    if name=='temporal_validation':
        train['date']=pd.date_range('2024-01-01',periods=n).astype(str); test['date']=pd.date_range('2025-01-01',periods=20).astype(str)
        dictionary=pd.concat([dictionary,pd.DataFrame({'feature':['date'],'role':['feature']})],ignore_index=True)
    if name=='entity_validation':
        train['client']=positions//10; test['client']=np.arange(20)//10+50
        dictionary=pd.concat([dictionary,pd.DataFrame({'feature':['client'],'role':['group']})],ignore_index=True)
    if name=='binary_probability': sample['answer']=.5
    if name=='different_output_name': sample=sample.rename(columns={'answer':'prediction'})
    if name=='sample_id_order': sample=sample.iloc[::-1].reset_index(drop=True)
    filenames=['train.csv','test.csv','sample_submission.csv','data_dictionary.csv']
    if name=='different_filenames': filenames=['fitting.csv','evaluation.csv','example.csv','schema.csv']
    for frame,filename in zip([train,test,sample,dictionary],filenames):
        if name=='no_dictionary' and filename=='data_dictionary.csv': continue
        frame.to_csv(directory/filename,index=False)
    if name!='different_filenames': text+=' Files: train.csv test.csv sample_submission.csv'+(' data_dictionary.csv' if name!='no_dictionary' else '')
    (directory/'task.md').write_text(text,encoding='utf-8')
    row={'scenario':name,'expected_kind':kind,'expected_metric':metric,'synthetic':True,'training_performed':False}
    try:
        spec,_,data,_,_,_,hashes=discover(directory/'task.md')
        row.update(detected_kind=spec['kind'],detected_metric=spec['metric'])
        passed=spec['kind']==kind and spec['metric']==metric
        if name=='temporal_validation':
            tr,va,split=make_split(spec,data,hashes)
            row.update(split=split['method'],last_training_date=str(data['date'].iloc[tr].max()),first_validation_date=str(data['date'].iloc[va].min()))
            passed=passed and data['date'].iloc[tr].max()<data['date'].iloc[va].min()
        if name=='entity_validation':
            tr,va,split=make_split(spec,data,hashes)
            overlap=len(set(data['client'].iloc[tr])&set(data['client'].iloc[va]))
            row.update(split=split['method'],shared_clients=overlap); passed=passed and overlap==0
        row['status']='satisfies_synthetic_contract' if passed else 'wrong_contract_or_validation'
    except Exception as exc:
        row.update(status='rejected_before_llm_planning',error=f'{type(exc).__name__}: {exc}')
    records.append(row)
result={'submitted_zip_sha256':hashlib.sha256(archive_path.read_bytes()).hexdigest(),
 'source_snapshot':'release6','scope':'14 synthetic loader/validation diagnostics only, not private tasks or ML quality evaluation',
 'cases':records,'passed':sum(r['status']=='satisfies_synthetic_contract' for r in records),'total':len(records)}
destination=ROOT/'v2_contract_audit.json'
destination.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
