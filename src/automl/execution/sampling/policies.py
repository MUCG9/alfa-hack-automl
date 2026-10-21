"""Fitting-only row policies. Validation arrays and labels are never accepted."""
import numpy as np
import pandas as pd
from automl.contracts.messages import DataPolicy,canonical_hash
from automl.execution.augmentation.masking import add_copies

def prepare_training(x,y,raw_y,weights,hashes,parent_rows,policy=None,kind='classification',engine='lightgbm'):
    policy=DataPolicy.parse(policy)
    n=len(x)
    if any(len(v)!=n for v in [y,raw_y,hashes,parent_rows]): raise ValueError('Training policy shape mismatch')
    if n==0: raise ValueError('Empty fitting partition')
    parents=np.asarray(parent_rows,dtype=np.int64)
    if len(np.unique(parents))!=n: raise ValueError('Fitting row IDs must be unique before resampling')
    metadata={'policy':policy.to_dict(),'source_rows':n,'source_parent_sha256':canonical_hash(parents.tolist()),
              'weights_source':'original fitting rows before resampling','synthetic_rows':0,'skipped':None}
    if policy.is_noop:
        metadata.update(output_rows=n,effective_weight_sum=float(n if weights is None else np.sum(weights)))
        return x,y,weights,parents,metadata
    rng=np.random.default_rng(policy.seed)
    labels=np.asarray(raw_y); hashes=np.asarray(hashes)
    w=np.ones(n,dtype=float) if weights is None else np.asarray(weights,dtype=float).copy()
    if not np.isfinite(w).all() or (w<=0).any(): raise ValueError('Invalid source sample weights')
    if policy.class_weight_cap is not None: w=np.minimum(w,w.min()*policy.class_weight_cap)
    if policy.duplicate_beta:
        multiplicities=pd.Series(hashes).map(pd.Series(hashes).value_counts()).to_numpy(dtype=float)
        w*=multiplicities**(-policy.duplicate_beta)
    positions=np.arange(n)
    if policy.sampling=='compress':
        groups=pd.DataFrame({'h':hashes,'y':labels.astype(str)}).groupby(['h','y'],sort=False).indices
        positions=np.array([p[0] for p in groups.values()],dtype=int)
        w=np.array([w[p].sum() for p in groups.values()])
    elif policy.sampling in {'over','under'}:
        if kind!='classification': raise ValueError('Class resampling requires classification')
        counts=pd.Series(labels).value_counts(); largest=int(counts.max()); additions=[]; keep=[]
        for label,count in counts.items():
            available=np.flatnonzero(labels==label)
            if policy.sampling=='under' and count>=largest*.5:
                desired=max(20,int(np.ceil(count*policy.majority_fraction)))
                # Prefer feature diversity before retaining extra copies of a group.
                shuffled=rng.permutation(available)
                _,first=np.unique(hashes[shuffled],return_index=True)
                unique=shuffled[np.sort(first)]
                chosen=rng.choice(unique,min(desired,len(unique)),replace=False)
                if len(chosen)<desired:
                    rest=np.setdiff1d(available,chosen); chosen=np.r_[chosen,rng.choice(rest,min(desired-len(chosen),len(rest)),replace=False)]
                keep.extend(chosen.tolist())
            else: keep.extend(available.tolist())
            if policy.sampling=='over' and count<largest*.1:
                desired=min(int(np.ceil(count*policy.factor)),int(largest*.1))
                representatives=pd.DataFrame({'p':available,'h':hashes[available]}).drop_duplicates('h').p.to_numpy()
                additions.extend(rng.choice(representatives,max(0,desired-count),replace=True).tolist())
        positions=np.asarray(sorted(keep),dtype=int)
        if additions:
            positions=np.r_[positions,np.asarray(additions[:int(n*policy.max_added_fraction)],dtype=int)]
        w=w[positions]
    else: w=w[positions]
    out_x=x.iloc[positions].copy(); out_y=y.iloc[positions].copy(); out_parents=parents[positions]
    if policy.augmentation=='mask':
        out_x,out_y,w,out_parents,mask_meta=add_copies(out_x,out_y,w,out_parents,x,policy,rng,engine,int(n*(1+policy.max_added_fraction)))
        metadata.update(mask_meta)
    if not set(out_parents)<=set(parents): raise ValueError('Foreign parent row entered fitting data')
    if len(out_x)!=len(out_y) or len(w)!=len(out_x) or not np.isfinite(w).all(): raise ValueError('Invalid policy output')
    w=w/w.mean()
    metadata.update(output_rows=len(out_x),unique_source_groups=int(pd.Series(hashes).nunique()),
                    output_parent_sha256=canonical_hash(out_parents.tolist()),effective_weight_sum=float(w.sum()),
                    class_counts_before=pd.Series(labels).value_counts().to_dict() if kind=='classification' else None,
                    class_counts_after=out_y.astype(str).value_counts().to_dict() if kind=='classification' else None)
    return out_x,out_y,w,out_parents,metadata
