"""Private, offline bounded meta-fitting subprocess; save numerical coefficients."""
from pathlib import Path
import argparse,json,time,warnings,hashlib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.exceptions import ConvergenceWarning


def fit(data_path,output,C):
    if C not in [.1,1.]:raise ValueError('Undeclared C')
    with np.load(data_path,allow_pickle=False) as d:
        X,y,Z,classes,rows,outer_rows=[d[k] for k in ['X','y','Z','classes','fit_rows','outer_rows']]
    labels=classes.astype(str).tolist()
    if len(labels)<3 or len(set(labels))!=len(labels) or set(y.astype(str))!=set(labels):raise ValueError('Every meta-fitting class required')
    if X.shape!=(len(y),3*len(classes)) or Z.shape!=(len(outer_rows),X.shape[1]) or not np.isfinite(X).all() or not np.isfinite(Z).all():raise ValueError('Invalid log probability matrix')
    if len(rows)!=len(y) or len(np.unique(rows))!=len(rows) or np.intersect1d(rows,outer_rows).size:raise ValueError('Meta fitting/outer rows overlap')
    counts={c:int(np.sum(y==c)) for c in labels};weight=np.asarray([counts[c]**-.5 for c in y]);weight/=weight.mean()
    model=LogisticRegression(C=C,solver='lbfgs',max_iter=1200,tol=1e-4,fit_intercept=True,random_state=137)
    start=time.monotonic()
    with warnings.catch_warnings():
        warnings.simplefilter('error',ConvergenceWarning);model.fit(X,y,sample_weight=weight)
    probability=model.predict_proba(Z)[:,[list(model.classes_).index(c) for c in labels]]
    np.savez_compressed(output/'coefficients.npz',coef=model.coef_,intercept=model.intercept_,model_classes=model.classes_,sample_weight=weight,fit_rows=rows)
    np.savez_compressed(output/'meta_probabilities.npz',probabilities=probability,row_position=outer_rows,classes=classes)
    receipt={'status':'ok','C':C,'parameters':model.get_params(),'classes':labels,'fit_rows':len(rows),'class_counts':counts,
        'input_sha256':hashlib.sha256(data_path.read_bytes()).hexdigest(),'iterations':model.n_iter_.tolist(),'seconds':round(time.monotonic()-start,3),
        'coefficient_sha256':hashlib.sha256((output/'coefficients.npz').read_bytes()).hexdigest()}
    (output/'result.json').write_text(json.dumps(receipt,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--C',type=float,required=True);a=p.parse_args();fit(a.data,a.output,a.C)
