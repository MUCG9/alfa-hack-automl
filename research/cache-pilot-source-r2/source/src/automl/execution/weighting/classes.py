import numpy as np
import pandas as pd
def number(params, name, default, low, high, integer=False):
    value=float(params.get(name,default))
    if not np.isfinite(value):
        raise ValueError(f'Non-finite parameter: {name}')
    value=float(np.clip(value,low,high))
    return int(value) if integer else value


def sample_weights(y, params):
    """Estimate imbalance weights on fitting rows only, never validation labels."""
    if 'class_weight_power' not in params:
        return None
    power=number(params,'class_weight_power',0,0,1)
    if not power:
        return None
    counts=pd.Series(np.asarray(y)).value_counts()
    weights=pd.Series(np.asarray(y)).map((len(y)/(len(counts)*counts))**power).to_numpy(dtype=float)
    return weights/weights.mean()

