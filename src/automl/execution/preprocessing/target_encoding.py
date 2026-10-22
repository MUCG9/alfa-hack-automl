"""Smoothed categorical statistics with group-disjoint cross-fitting on fit rows."""
import numpy as np
import pandas as pd
from itertools import combinations
from sklearn.model_selection import GroupKFold


def context_key(frame,columns):
    canonical=frame[columns].copy()
    for column in columns:
        canonical[column]=canonical[column].astype('float64') if pd.api.types.is_numeric_dtype(canonical[column]) else canonical[column].fillna('__MISSING__').astype(str)
    return pd.util.hash_pandas_object(canonical,index=False).astype(str)


def infer_history_groups(train_x,rows,time_column,categorical,refine=False,static_numeric=None):
    """Find recurring contexts across *training* periods, without y or test X."""
    if time_column not in train_x: raise ValueError('Automatic history encoding requires an observation period')
    fit=train_x.iloc[rows]
    periods=pd.to_numeric(fit[time_column],errors='coerce')
    if periods.isna().any() or periods.nunique()<2: return []
    older=fit.loc[periods<periods.max()]; recent=fit.loc[periods==periods.max()]
    declared=[c for c in categorical if c in fit and c!=time_column]
    inferred=[c for c in fit if c!=time_column and not pd.api.types.is_numeric_dtype(fit[c])]
    categories=list(dict.fromkeys(declared+inferred))[:6]
    numeric=[c for c in fit if c!=time_column and pd.api.types.is_numeric_dtype(fit[c])
             and max(20,len(fit)*.02)<=fit[c].nunique()<=len(fit)*.9 and fit[c].isna().mean()<.5]
    numeric=sorted(numeric,key=lambda c:fit[c].nunique(),reverse=True)[:8]
    proposals=[]
    for number in numeric:
        for width in [1,2]:
            for cats in combinations(categories,width):
                columns=list(cats)+[number]
                history=context_key(older,columns); held=context_key(recent,columns)
                coverage=float(held.isin(set(history)).mean())
                diversity=float(history.nunique()/max(1,len(older)))
                if coverage<.25 or diversity<.02: continue
                score=coverage*np.sqrt(min(diversity,.75))*(.97**len(columns))
                proposals.append((score,columns))
    chosen=[]
    for _,columns in sorted(proposals,key=lambda x:(-x[0],x[1])):
        if any(set(columns)<=set(old) or set(old)<=set(columns) for old in chosen): continue
        chosen.append(columns)
        if len(chosen)==2: break
    if chosen and static_numeric:
        base=chosen[0].copy()
        for column in categories:
            if column not in base and len(base)<5: base.append(column)
        def coverage(columns):
            return float(context_key(recent,columns).isin(set(context_key(older,columns))).mean())
        if coverage(base)>=.25:
            for column in static_numeric:
                if column in fit and column not in base and column!=time_column and fit[column].nunique()>=2:
                    finer=base+[column]
                    if coverage(finer)>=.25: return [base,finer]
    if refine and chosen:
        base=chosen[0]; base_count=context_key(older,base).nunique()
        base_coverage=context_key(recent,base).isin(set(context_key(older,base))).mean()
        for _,columns in sorted(proposals,key=lambda x:(-x[0],x[1])):
            if not set(base)<set(columns): continue
            history=context_key(older,columns)
            coverage=context_key(recent,columns).isin(set(history)).mean()
            if history.nunique()>base_count*1.02 and coverage>=base_coverage*.65:
                return [base,columns]
    return chosen


def target_encode_frames(train_x,test_x,y,rows,hashes,classes=None,smoothing=20.,groups=None,add_counts=False,half_life=0,time_column=None):
    rows=np.asarray(rows,dtype=int)
    categorical=[c for c in train_x if not pd.api.types.is_numeric_dtype(train_x[c])][:8]
    if groups is None: groups=[]
    if not isinstance(groups,list) or len(groups)>3: raise ValueError('At most three target-encoding feature groups')
    for group in groups:
        if not isinstance(group,list) or not 2<=len(group)<=6 or any(c not in train_x for c in group):
            raise ValueError('Target-encoding groups require 2..6 available feature columns')
    if not categorical and not groups: return train_x,test_x
    time_values=None
    if half_life:
        if time_column not in train_x: raise ValueError('Recency encoding requires a detected observation period')
        time_values=pd.to_numeric(train_x[time_column].iloc[rows],errors='raise').to_numpy(dtype=float)
        if not np.isfinite(time_values).all() or not 0<half_life<=10: raise ValueError('Invalid recency encoding period or half-life')
    local_groups=np.asarray(hashes)[rows]
    folds=min(3,len(np.unique(local_groups)))
    if folds<2: raise ValueError('Target encoding requires at least two independent feature groups')
    if classes is None:
        targets=np.asarray(y.iloc[rows],dtype=float).reshape(-1,1)
    else:
        targets=(np.asarray(y.iloc[rows],dtype=str)[:,None]==np.asarray(classes,dtype=str)[None,:]).astype(float)
    splits=list(GroupKFold(folds).split(rows,groups=local_groups))
    train_x=train_x.copy(); test_x=test_x.copy()
    all_keys=[(train_x[c].fillna('__MISSING__').astype(str),test_x[c].fillna('__MISSING__').astype(str)) for c in categorical]
    all_keys.extend((context_key(train_x,g),context_key(test_x,g)) for g in groups)
    for number,(train_key,test_key) in enumerate(all_keys):
        keys=train_key.iloc[rows].reset_index(drop=True)
        if add_counts:
            counts=train_key.map(keys.value_counts()).fillna(0).to_numpy(dtype=float)
            for fit,held in splits:
                counts[rows[held]]=keys.iloc[held].map(keys.iloc[fit].value_counts()).fillna(0).to_numpy()
            name=f'__te_count_{number}'
            if name in train_x: raise ValueError('Target encoding count feature collision')
            train_x[name]=np.log1p(counts).astype('float32')
            test_x[name]=np.log1p(test_key.map(keys.value_counts()).fillna(0).to_numpy(dtype=float)).astype('float32')
        def encode(indices,query,channel):
            values=targets[indices,channel]
            if time_values is not None:
                periods=time_values[indices]
                ranks=np.searchsorted(np.sort(np.unique(periods)),periods)
                weights=np.exp2((ranks-ranks.max())/half_life); weights/=weights.mean()
                prior=float(np.average(values,weights=weights))
                stats=pd.DataFrame({'key':keys.iloc[indices].to_numpy(),'sum':values*weights,'count':weights}).groupby('key')[['sum','count']].sum()
            else:
                prior=float(values.mean())
                stats=pd.DataFrame({'key':keys.iloc[indices].to_numpy(),'y':values}).groupby('key')['y'].agg(['sum','count'])
            mapping=(stats['sum']+smoothing*prior)/(stats['count']+smoothing)
            return query.map(mapping).fillna(prior).to_numpy(dtype='float32')
        for channel in range(targets.shape[1]):
            name=f'__te_{number}_{channel}'
            if name in train_x: raise ValueError('Target encoding feature collision')
            all_indices=np.arange(len(rows))
            encoded=encode(all_indices,train_key,channel)
            test_x[name]=encode(all_indices,test_key,channel)
            for fit,held in splits:
                encoded[rows[held]]=encode(fit,keys.iloc[held],channel)
            train_x[name]=encoded
    return train_x,test_x
