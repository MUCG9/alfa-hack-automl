from pathlib import Path
import shutil
import re,json,hashlib
import numpy as np
import pandas as pd


def positive_class_index(spec,classes):
    labels=list(map(str,classes))
    if len(labels)!=2: raise ValueError('Scalar probabilities require two model classes')
    declared=spec.get('classes')
    fallback=labels[-1] if declared is None or len(declared)==0 else str(declared[-1])
    positive=str(spec.get('positive_class',fallback))
    if positive not in labels: raise ValueError('Requested positive class is absent from model output')
    return labels.index(positive)


def prediction_row_order(spec,n):
    """Positions of test-order predictions in sample order; validate as a bijection."""
    values=np.asarray(spec.get('sample_test_positions',np.arange(n)))
    if values.shape!=(n,) or values.dtype.kind not in {'i','u'} or not np.array_equal(np.sort(values),np.arange(n)):
        raise ValueError('Invalid sample/test row mapping')
    return values


def read_submission_values(spec,path):
    """Convert a published prediction column back to test order for cached blends."""
    frame=pd.read_csv(path)
    columns=spec.get('output_columns',[spec['target']])
    values=frame[columns].to_numpy()
    values=values[np.argsort(prediction_row_order(spec,len(frame)))]
    return values if spec.get('prediction_type')=='probability_matrix' else values[:,0]


def save_submission(spec, sample, test, predictions, path):
    result=sample.copy()
    if len(predictions)!=len(test) or len(sample)!=len(test):
        raise ValueError('Wrong prediction length')
    order=prediction_row_order(spec,len(test))
    predictions=np.asarray(predictions)[order]
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
    if list(result.columns)!=list(sample.columns):
        raise ValueError('Submission contract violation')
    identifier=spec.get('id')
    if identifier is not None and (result[identifier].tolist()!=sample[identifier].tolist() or result[identifier].tolist()!=test[identifier].iloc[order].tolist()):
        raise ValueError('Submission ID contract violation')
    temp=path.with_suffix('.csv.tmp')
    result.to_csv(temp,index=False,encoding='utf-8')
    temp.replace(path)


def dummy_predictions(spec, train, n):
    y=train[spec['target']]
    if spec.get('prediction_type')=='probability':
        positive=spec['classes'][positive_class_index(spec,spec['classes'])]
        return np.repeat(float((y.astype(str)==positive).mean()),n)
    if spec.get('prediction_type')=='probability_matrix':
        frequencies=y.astype(str).value_counts(normalize=True)
        return np.tile([frequencies.get(str(c),0) for c in spec['output_columns']],(n,1))
    value=float(y.mean()) if spec['kind']=='regression' else y.mode().iloc[0]
    return np.repeat(value,n)


def checkpoint(record,output):
    temporary=output.with_suffix('.csv.tmp')
    shutil.copyfile(record['submission'],temporary); temporary.replace(output)


def publish_targets(parts,sample,path):
    """Combine already sample-ordered, validated single-target publications."""
    result=sample.copy(); seen=set()
    for spec,source in parts:
        target=spec['target']; columns=spec['output_columns']; frame=pd.read_csv(source)
        if target in seen or columns!=[target] or target not in sample:
            raise ValueError('Unsupported or duplicate multi-target output mapping')
        seen.add(target)
        if len(frame)!=len(sample) or list(frame.columns)!=spec['sample_columns']:
            raise ValueError('Child publication schema mismatch')
        identifier=spec.get('id')
        if identifier is not None and frame[identifier].tolist()!=sample[identifier].tolist():
            raise ValueError('Child publication ID order mismatch')
        values=frame[target]
        if values.isna().any(): raise ValueError('Missing child predictions')
        if spec['kind']=='regression':
            if not np.isfinite(pd.to_numeric(values,errors='coerce')).all(): raise ValueError('Non-finite child predictions')
        elif spec['prediction_type']=='probability':
            numbers=pd.to_numeric(values,errors='coerce')
            if not np.isfinite(numbers).all() or ((numbers<0)|(numbers>1)).any(): raise ValueError('Invalid child probabilities')
        elif set(values.astype(str))-set(spec['classes']): raise ValueError('Unknown child class labels')
        result[target]=values.to_numpy()
    if result.isna().any().any(): raise ValueError('Null multi-target publication values')
    temporary=path.with_suffix('.csv.tmp'); result.to_csv(temporary,index=False,encoding='utf-8'); temporary.replace(path)
