"""Compare validated blends without retraining models whose predictions exist."""
from pathlib import Path
import time
import numpy as np
import pandas as pd
from agent_core import atomic_json,evaluate,save_submission

def read_cache(spec,record,train):
    root=Path(record['submission']).parent
    validation=pd.read_csv(root/'validation_predictions.csv')
    rows=validation['row_position'].to_numpy(dtype=int)
    truth=train[spec['target']].iloc[rows].to_numpy()
    if spec['kind']=='classification':
        truth=truth.astype(str); aligned=[]
        for name in ['validation_probabilities.npz','test_probabilities.npz']:
            stored=np.load(root/name)
            if name.startswith('validation'): assert np.array_equal(stored['row_position'],rows)
            order=[list(stored['classes'].astype(str)).index(c) for c in spec['classes']]
            aligned.append(stored['probabilities'][:,order])
        val,test=aligned
    else:
        val=validation['y_pred'].to_numpy(dtype=float)
        test=pd.read_csv(record['submission'])[spec['output_columns'][0]].to_numpy(dtype=float)
    return {'record':record,'rows':rows,'truth':truth,'validation':val,'test':test}

def combine(spec,caches,weights):
    weights=np.asarray(weights,dtype=float)
    if len(weights)!=len(caches) or (weights<=0).any() or not np.isfinite(weights).all(): raise ValueError('Invalid cached blend weights')
    weights=weights/weights.sum()
    for cache in caches[1:]:
        if not np.array_equal(cache['rows'],caches[0]['rows']) or not np.array_equal(cache['truth'],caches[0]['truth']): raise ValueError('Cannot blend different validation rows')
    val=sum(weight*cache['validation'] for weight,cache in zip(weights,caches))
    test=sum(weight*cache['test'] for weight,cache in zip(weights,caches))
    pred=np.asarray(spec['classes'])[val.argmax(axis=1)] if spec['kind']=='classification' else val
    metrics=evaluate(caches[0]['truth'],pred,spec['kind'],spec['metric'],val if spec['kind']=='classification' else None,spec['classes'])
    return metrics,val,test,pred

def materialize(spec,caches,weights,output,sample,test_frame):
    started=time.monotonic(); output=Path(output); output.mkdir(parents=True,exist_ok=False)
    metrics,val,test,pred=combine(spec,caches,weights)
    weights=np.asarray(weights,dtype=float); weights=weights/weights.sum()
    recipe={'engine':'ensemble','hypothesis':'Validated cached-prediction blend','params':{},
            'components':[c['record']['recipe'] for c in caches],'weights':weights.tolist()}
    if spec['kind']=='classification':
        classes=np.asarray(spec['classes'])
        np.savez_compressed(output/'validation_probabilities.npz',probabilities=val,classes=classes,row_position=caches[0]['rows'])
        np.savez_compressed(output/'test_probabilities.npz',probabilities=test,classes=classes)
        if spec['prediction_type']=='probability_matrix': values=test[:,[list(classes).index(c) for c in spec['output_columns']]]
        elif spec['prediction_type']=='probability': values=test[:,1]
        else: values=classes[test.argmax(axis=1)]
    else: values=test
    save_submission(spec,sample,test_frame,values,output/'submission.csv')
    pd.DataFrame({'row_position':caches[0]['rows'],'y_true':caches[0]['truth'],'y_pred':pred}).to_csv(output/'validation_predictions.csv',index=False)
    record={'status':'ok','recipe':recipe,'metrics':metrics,'fit_iterations':[c['record']['fit_iterations'] for c in caches],
            'feature_count':sum(c['record'].get('feature_count',0) for c in caches),'submission':str(output/'submission.csv'),
            'output_dir':str(output),'full_fit':False,'training_reused':True,'wall_seconds':round(time.monotonic()-started,3)}
    atomic_json(output/'result.json',record)
    return record
