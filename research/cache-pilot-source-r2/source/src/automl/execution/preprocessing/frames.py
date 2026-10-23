import numpy as np
import pandas as pd
from automl.execution.model_adapters.registry import CAPABILITIES
def prepare_frames(train_x,test_x,engine,fit_rows=None):
    train_x=train_x.copy()
    test_x=test_x.copy()
    cat_cols=[]
    for c in train_x:
        if not pd.api.types.is_numeric_dtype(train_x[c]) or not pd.api.types.is_numeric_dtype(test_x[c]):
            cat_cols.append(c)
            for frame in [train_x,test_x]:
                frame[c]=frame[c].fillna('__MISSING__').astype(str)
            if CAPABILITIES[engine]['category_strategy']=='pandas':
                categories=sorted(set(train_x[c].iloc[fit_rows] if fit_rows is not None else train_x[c]))
                for frame in [train_x,test_x]:
                    frame[c]=pd.Categorical(frame[c],categories=categories)
            elif CAPABILITIES[engine]['category_strategy']=='frequency':
                fit=train_x[c].iloc[fit_rows] if fit_rows is not None else train_x[c]
                frequencies=fit.value_counts(normalize=True)
                for frame in [train_x,test_x]: frame[c]=frame[c].map(frequencies).fillna(0).astype('float32')
        else:
            for frame in [train_x,test_x]:
                frame[c]=pd.to_numeric(frame[c],errors='coerce').replace([np.inf,-np.inf],np.nan).astype('float32')
            if CAPABILITIES[engine]['category_strategy']=='frequency':
                fit=train_x[c].iloc[fit_rows] if fit_rows is not None else train_x[c]
                median=float(fit.median()) if fit.notna().any() else 0.
                for frame in [train_x,test_x]: frame[c]=frame[c].fillna(median)
    return train_x,test_x,cat_cols
