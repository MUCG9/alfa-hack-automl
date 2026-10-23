"""Training-only rare-class pair specialists with conservative probability blending."""
import numpy as np
from sklearn.metrics import f1_score


class PairSpecialists:
    def __init__(self,base):
        self.base=base
        self.models_=[]
        self.specialist_pairs_=[]

    def fit(self,x,y,sample_weight=None,**kwargs):
        self.models_=[]; self.specialist_pairs_=[]
        self.base.fit(x,y,sample_weight=sample_weight,**kwargs)
        classes=self.base.classes_; truth=np.asarray(y,dtype=str)
        if len(classes)<3: return self
        probabilities=self.base.predict_proba(x)
        predicted=classes[probabilities.argmax(axis=1)]
        quality=f1_score(truth,predicted,labels=classes,average=None,zero_division=0)
        counts=np.asarray([(truth==c).sum() for c in classes])
        candidates=[i for i in range(len(classes)) if 20<=counts[i]<len(truth)*.1]
        candidates.sort(key=lambda i:(quality[i],counts[i]))
        used=set()
        from lightgbm import LGBMClassifier
        for i in candidates:
            wrong=(truth==classes[i])&(predicted!=classes[i])
            if not wrong.any(): continue
            confusion=probabilities[wrong].mean(axis=0); confusion[i]=-1
            j=int(confusion.argmax()); pair=tuple(sorted((i,j)))
            if pair in used: continue
            used.add(pair)
            positions=np.flatnonzero(np.isin(truth,classes[list(pair)]))
            params=self.base.get_params().copy()
            params.update(objective='binary',class_weight=None,n_estimators=min(params['n_estimators'],300),
                          max_depth=4,num_leaves=15,min_child_samples=5,metric='None')
            estimator=LGBMClassifier(**params)
            weights=None if sample_weight is None else np.asarray(sample_weight)[positions]
            estimator.fit(x.iloc[positions],truth[positions],sample_weight=weights)
            self.models_.append((pair,estimator))
            self.specialist_pairs_.append({'classes':[str(classes[k]) for k in pair],'fit_rows':len(positions)})
            if len(self.models_)==3: break
        return self

    def predict_proba(self,x):
        original=np.asarray(self.base.predict_proba(x),dtype=float)
        original=original/np.maximum(original.sum(axis=1,keepdims=True),1e-15)
        result=original.copy()
        for (i,j),model in self.models_:
            mass=original[:,i]+original[:,j]
            order=[list(model.classes_).index(self.classes_[k]) for k in [i,j]]
            proposal=model.predict_proba(x)[:,order]*mass[:,None]
            active=mass>.35
            # Each specialist keeps pair mass; final normalization handles overlap.
            for channel,k in enumerate([i,j]): result[active,k]=.5*result[active,k]+.5*proposal[active,channel]
        return result/np.maximum(result.sum(axis=1,keepdims=True),1e-15)

    def predict(self,x): return self.classes_[self.predict_proba(x).argmax(axis=1)]
    @property
    def classes_(self): return self.base.classes_
    @property
    def best_iteration_(self): return getattr(self.base,'best_iteration_',0)
    @property
    def feature_importances_(self): return self.base.feature_importances_
