"""Opt-in bounded fitting-only tabular representation plus fixed linear heads.

The identity profile is a matched control for the RBF map, not the old linear
recipe. Each logical matrix is capped; total live buffer estimates are reported.
The external worker RSS/time guard covers simultaneous buffers/workspaces.
"""
import hashlib
import json
import numbers

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from automl.contracts.representations import validate_representation_recipe
from automl.execution.weighting.classes import sample_weights
from automl.evaluation.api import evaluate
from automl.publishing.api import positive_class_index


def matrix_budget(profile,rows,numeric,categorical):
    """Conservative pre-fit bound; no learned values or outer rows consulted."""
    if type(rows) is not int or not 1<=rows<=profile.maximum_rows:raise ValueError('Representation fitting-row cap')
    if type(numeric) is not int or type(categorical) is not int or min(numeric,categorical)<0 or not 1<=numeric+categorical<=profile.maximum_columns:
        raise ValueError('Representation raw-column cap')
    width=numeric+profile.maximum_categories*categorical
    if width>profile.maximum_prepared_columns:raise ValueError('Representation encoded-width cap')
    # Each logical allocation is bounded, including worst-case sparse nnz.
    # Simultaneous input/copies/output are charged as an estimate, not a false
    # guarantee that total process RSS is below the single-matrix limit.
    input_work=rows*(numeric*8*3+categorical*16*3+(numeric+categorical)*16*2)
    dimension=profile.components or width
    output_work=rows*dimension*8*2 if profile.components else rows*(numeric+categorical)*16
    projection=width*dimension*8 if profile.components else 0
    estimate=input_work+output_work+projection+64*dimension*8
    matrices={'numeric_dense':rows*numeric*8,'category_codes':rows*categorical*8,
              'prepared_CSR_upper_bound':rows*(numeric+categorical)*12+(rows+1)*4,
              'representation_dense':rows*dimension*8 if profile.components else 0,
              'random_projection':projection}
    if max(matrices.values())>profile.matrix_limit_bytes:raise ValueError('Representation matrix budget exceeded before preprocessing fit')
    return {'fitting_rows':rows,'numeric_columns':numeric,'categorical_columns':categorical,
            'maximum_encoded_columns':width,'estimated_live_matrix_bytes':estimate,
            'matrix_limit_bytes':profile.matrix_limit_bytes,'matrix_limit_scope':'each_logical_matrix',
            'matrix_bytes_upper_bounds':matrices,'process_RSS_requires_external_guard':True}


def matrix_bytes(value):
    from scipy import sparse
    if sparse.issparse(value):return int(value.data.nbytes+value.indices.nbytes+value.indptr.nbytes)
    return int(np.asarray(value).nbytes)


def _digest(value):
    if isinstance(value,np.ndarray):
        value=np.ascontiguousarray(value)
        return hashlib.sha256(str(value.dtype).encode()+str(value.shape).encode()+value.tobytes()).hexdigest()
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()


class BoundedTabularModel:
    def __init__(self,spec,recipe,threads):
        self.profile=validate_representation_recipe(recipe,spec)
        if self.profile is None:raise ValueError('Explicit representation_profile required')
        if type(threads) is not int or not 1<=threads<=2:raise ValueError('Representation requires one or two worker threads')
        self.spec=spec;self.recipe=recipe;self.threads=threads

    def _schema(self,x):
        if not 1<=len(x.columns)<=self.profile.maximum_columns:raise ValueError('Representation raw-column cap')
        names=list(x.columns)
        if not names or len(names)>self.profile.maximum_columns or len(names)!=len(set(names)) or any(type(c) is not str for c in names):
            raise ValueError('Representation requires bounded unique string feature names')
        forbidden=set(self.spec.get('all_targets',[self.spec.get('target')]))|{self.spec.get('id')}
        if forbidden.intersection(names):raise ValueError('Target/ID cannot enter representation features')
        return names

    def _clean(self,x,fitting=False):
        if list(x.columns)!=self.columns_:raise ValueError('Representation feature schema/order changed')
        result=x.copy()
        for name in self.numeric_:
            result[name]=pd.to_numeric(result[name],errors='coerce').replace([np.inf,-np.inf],np.nan)
        for name in self.categorical_:
            values=result[name].fillna('').astype(str)
            if values.str.len().gt(512).any():raise ValueError('Representation category text exceeds bounded cell size')
            if fitting and values.nunique(dropna=False)>self.profile.maximum_fitting_category_levels:
                raise ValueError('Representation fitting category vocabulary cap')
            result[name]=values
        return result

    def _check_matrix(self,x):
        from scipy import sparse
        size=matrix_bytes(x)
        if size>self.profile.matrix_limit_bytes:raise ValueError('Actual representation matrix budget exceeded')
        values=x.data if sparse.issparse(x) else np.asarray(x)
        if not np.isfinite(values).all():raise ValueError('Representation matrix is nonfinite')
        return size

    def fit(self,x,y):
        from sklearn.compose import ColumnTransformer
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import Ridge,LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import OneHotEncoder,StandardScaler
        self.columns_=self._schema(x)
        if len(y)!=len(x) or not len(x):raise ValueError('Representation fitting labels/rows mismatch')
        if len(x)>self.profile.maximum_rows:raise ValueError('Representation fitting-row cap')
        if self.spec['kind']=='classification':
            raw_classes=self.spec.get('classes',[])
            if not isinstance(raw_classes,list) or not 2<=len(raw_classes)<=64:
                raise ValueError('Representation canonical class-count cap')
            classes=list(map(str,raw_classes))
            fitting_classes=set(map(str,pd.unique(y)))
            if not 2<=len(classes)<=64 or len(classes)!=len(set(classes)) or fitting_classes!=set(classes):
                raise ValueError('Representation fitting classes must match canonical classes')
            targets=np.asarray(y,dtype=str)
        else:
            targets=np.asarray(y,dtype=float)
            if not np.isfinite(targets).all():raise ValueError('Representation fitting targets are nonfinite')
        # Infer types using fitting values only, including object-typed numeric
        # columns whose outer-only strings changed pandas' overall dtype.
        self.numeric_=[];self.categorical_=[]
        for name in self.columns_:
            values=x[name].dropna()
            numeric=all(isinstance(v,(numbers.Real,np.number,bool)) for v in values)
            (self.numeric_ if numeric else self.categorical_).append(name)
        self.budget_=matrix_budget(self.profile,int(len(x)),len(self.numeric_),len(self.categorical_))
        transforms=[]
        if self.numeric_:
            transforms.append(('numeric',make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),StandardScaler(with_mean=False)),self.numeric_))
        if self.categorical_:
            transforms.append(('category',OneHotEncoder(handle_unknown='ignore',min_frequency=3,
                max_categories=self.profile.maximum_categories,sparse_output=True,dtype=np.float64),self.categorical_))
        self.processor_=ColumnTransformer(transforms,sparse_threshold=1.0)
        with threadpool_limits(limits=self.threads):prepared=self.processor_.fit_transform(self._clean(x,fitting=True))
        raw_size=self._check_matrix(prepared)
        if not 1<=prepared.shape[1]<=self.profile.maximum_prepared_columns:raise ValueError('Actual encoded-width cap')
        self.mapper_=None;gamma=None
        if self.profile.transform=='rbf':
            from sklearn.kernel_approximation import RBFSampler
            gamma=1./prepared.shape[1]
            self.mapper_=RBFSampler(n_components=self.profile.components,gamma=gamma,random_state=self.profile.seed)
            with threadpool_limits(limits=self.threads):represented=self.mapper_.fit_transform(prepared)
            projection_bytes=int(self.mapper_.random_weights_.nbytes+self.mapper_.random_offset_.nbytes)
            represented_size=self._check_matrix(represented)
        else:
            represented=prepared;projection_bytes=0;represented_size=raw_size
        if self.spec['kind']=='classification':
            self.estimator_=LogisticRegression(C=1.,solver='lbfgs',max_iter=1000,tol=1e-4,
                random_state=42,n_jobs=self.threads)
            weights=sample_weights(pd.Series(np.asarray(y,dtype=str)),{'class_weight_power':.5})
            kwargs={'sample_weight':weights}
        else:
            self.estimator_=Ridge(alpha=10.,solver='lsqr');kwargs={}
        with threadpool_limits(limits=self.threads):self.estimator_.fit(represented,targets,**kwargs)
        self.classes_=np.asarray(self.spec.get('classes',[]),dtype=str) if self.spec['kind']=='classification' else None
        state={'columns':self.columns_,'numeric':self.numeric_,'categorical':self.categorical_}
        for name,transformer,_ in self.processor_.transformers_:
            if name=='numeric':
                state['imputer_sha256']=_digest(transformer.steps[0][1].statistics_)
                state['scaler_sha256']=_digest(transformer.steps[1][1].scale_)
            elif name=='category':state['categories_sha256']=_digest([list(map(str,c)) for c in transformer.categories_])
        if self.mapper_ is not None:
            state['random_weights_sha256']=_digest(self.mapper_.random_weights_)
            state['random_offset_sha256']=_digest(self.mapper_.random_offset_)
        self.diagnostics_={'representation_profile':self.profile.representation_profile,'fitting_state_sha256':_digest(state),
            'fitting_rows':len(x),'prepared_columns':int(prepared.shape[1]),'representation_columns':int(represented.shape[1]),
            'gamma':gamma,'seed':42,'numeric_columns':len(self.numeric_),'categorical_columns':len(self.categorical_),
            'actual_prepared_matrix_bytes':raw_size,'actual_representation_matrix_bytes':represented_size,
            'projection_bytes':projection_bytes,'budget':self.budget_,'threads':self.threads,
            'estimator':{'family':'LogisticRegression','C':1.,'solver':'lbfgs','class_weight_power':.5} if self.spec['kind']=='classification'
                else {'family':'Ridge','alpha':10.,'solver':'lsqr'},
            'classes':list(self.classes_) if self.classes_ is not None else [],'calibration':'disabled','log_target':False,
            'preprocessing_scope':'fitting_rows_only','representation_scope':'fitting_rows_only'}
        return self

    def _batches(self,x):
        if len(x)>self.profile.maximum_rows:raise ValueError('Representation inference-row cap')
        self._schema(x)
        for offset in range(0,len(x),self.profile.prediction_batch_rows):
            raw=self.processor_.transform(self._clean(x.iloc[offset:offset+self.profile.prediction_batch_rows]))
            size=self._check_matrix(raw)
            transformed=self.mapper_.transform(raw) if self.mapper_ is not None else raw
            self._check_matrix(transformed)
            yield transformed

    def predict_proba(self,x):
        if self.classes_ is None:raise ValueError('Regression representation has no probabilities')
        if len(x)>self.profile.maximum_rows or len(x)*len(self.classes_)*8*2>self.profile.matrix_limit_bytes:
            raise ValueError('Representation probability-output allocation cap')
        order=[list(map(str,self.estimator_.classes_)).index(c) for c in self.classes_]
        with threadpool_limits(limits=self.threads):
            chunks=[self.estimator_.predict_proba(value)[:,order] for value in self._batches(x)]
        result=np.concatenate(chunks) if chunks else np.empty((0,len(order)))
        if not np.isfinite(result).all() or (result<0).any() or not np.allclose(result.sum(axis=1),1.,atol=1e-8):
            raise ValueError('Representation probabilities violate finite/class-order contract')
        return result

    def predict(self,x):
        if self.classes_ is not None:return self.classes_[self.predict_proba(x).argmax(axis=1)]
        with threadpool_limits(limits=self.threads):chunks=[self.estimator_.predict(value) for value in self._batches(x)]
        result=np.concatenate(chunks) if chunks else np.empty(0)
        if not np.isfinite(result).all():raise ValueError('Representation predictions are nonfinite')
        return result


def tabular_representation_fit(spec,recipe,train_x,test_x,y,tr,va,full,threads,diagnostics):
    profile=validate_representation_recipe(recipe,spec)
    if profile is None:raise ValueError('Explicit representation_profile required')
    if len(train_x)>profile.maximum_rows or len(test_x)>profile.maximum_rows:raise ValueError('Representation input-row cap')
    if len(y)!=len(train_x):raise ValueError('Representation target row count changed')
    if not full:
        for values in [tr,va]:
            values=np.asarray(values)
            if (values.ndim!=1 or values.dtype.kind not in 'iu' or not len(values)
                    or values.min()<0 or values.max()>=len(train_x) or len(np.unique(values))!=len(values)):
                raise ValueError('Representation split row IDs must be unique bounded integers')
        if np.intersect1d(tr,va).size:raise ValueError('Representation fitting/validation rows overlap')
    rows=np.arange(len(train_x),dtype=np.int64) if full else np.asarray(tr,dtype=np.int64)
    model=BoundedTabularModel(spec,recipe,threads).fit(train_x.iloc[rows],y.iloc[rows])
    diagnostics.update(model.diagnostics_)
    diagnostics['fitting_row_order_sha256']=_digest(rows)
    test_proba=model.predict_proba(test_x) if spec['kind']=='classification' else None
    predictions=model.classes_[test_proba.argmax(axis=1)] if test_proba is not None else model.predict(test_x)
    val_pred=None;val_proba=None;metrics=None
    if not full:
        val_proba=model.predict_proba(train_x.iloc[va]) if spec['kind']=='classification' else None
        val_pred=model.classes_[val_proba.argmax(axis=1)] if val_proba is not None else model.predict(train_x.iloc[va])
        metrics=evaluate(y.iloc[va],val_pred,spec['kind'],spec['metric'],val_proba,model.classes_)
    if spec.get('prediction_type')=='probability_matrix':
        order=[list(model.classes_).index(str(c)) for c in spec['output_columns']];predictions=test_proba[:,order]
    elif spec.get('prediction_type')=='probability':predictions=test_proba[:,positive_class_index(spec,model.classes_)]
    return predictions,val_pred,metrics,test_proba,val_proba,model.classes_
