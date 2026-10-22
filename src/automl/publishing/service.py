from pathlib import Path
import shutil
import re,json,hashlib
import numpy as np
import pandas as pd
def save_submission(spec, sample, test, predictions, path):
    result=sample.copy()
    if len(predictions)!=len(test):
        raise ValueError('Wrong prediction length')
    prediction_type=spec.get('prediction_type','value')
    output_columns=spec.get('output_columns',[spec['target']])
    if prediction_type=='probability_matrix':
        values=np.asarray(predictions,dtype=float)
        if values.shape!=(len(test),len(output_columns)) or not np.isfinite(values).all() or (values<0).any() or (values>1).any() or not np.allclose(values.sum(axis=1),1,atol=1e-5):
            raise ValueError('Invalid probability matrix')
        result[output_columns]=values
    else:
        result[output_columns[0]]=np.asarray(predictions).reshape(-1)
        if spec['kind']=='regression' and spec.get('metric')=='rmsle':
            result[output_columns[0]]=np.maximum(result[output_columns[0]],0)
    if result.isna().any().any():
        raise ValueError('Null submission values')
    if spec['kind']=='regression' and not np.isfinite(pd.to_numeric(result[output_columns[0]],errors='coerce')).all():
        raise ValueError('Non-finite regression predictions')
    if spec['kind']=='classification':
        if prediction_type=='probability':
            values=pd.to_numeric(result[output_columns[0]],errors='coerce').to_numpy(dtype=float)
            if not np.isfinite(values).all() or (values<0).any() or (values>1).any():
                raise ValueError('Invalid probability predictions')
        elif prediction_type=='value' and spec.get('classes') and set(result[output_columns[0]].astype(str))-set(spec['classes']):
            raise ValueError('Unknown predicted classification labels')
    if list(result.columns)!=list(sample.columns) or result[spec['id']].tolist()!=test[spec['id']].tolist():
        raise ValueError('Submission contract violation')
    temp=path.with_suffix('.csv.tmp')
    result.to_csv(temp,index=False,encoding='utf-8')
    temp.replace(path)


def dummy_predictions(spec, train, n):
    y=train[spec['target']]
    if spec.get('prediction_type')=='probability':
        return np.repeat(float((y.astype(str)==spec['classes'][1]).mean()),n)
    if spec.get('prediction_type')=='probability_matrix':
        frequencies=y.astype(str).value_counts(normalize=True)
        return np.tile([frequencies.get(str(c),0) for c in spec['output_columns']],(n,1))
    value=float(y.mean()) if spec['kind']=='regression' else y.mode().iloc[0]
    return np.repeat(value,n)


def checkpoint(record,output):
    temporary=output.with_suffix('.csv.tmp')
    shutil.copyfile(record['submission'],temporary); temporary.replace(output)
