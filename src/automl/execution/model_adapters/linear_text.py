import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from automl.execution.weighting.classes import sample_weights
from automl.evaluation.api import evaluate
def linear_text_fit(spec,recipe,train_x,test_x,y,tr,va,full,threads):
    from sklearn.compose import ColumnTransformer
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge,SGDClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import OneHotEncoder,StandardScaler
    text_columns=[c for c in spec.get('text_features',[]) if c in train_x]
    numeric=[c for c in train_x if pd.api.types.is_numeric_dtype(train_x[c]) and c not in text_columns]
    categorical=[c for c in train_x if c not in text_columns+numeric]
    for frame in [train_x,test_x]:
        for column in text_columns+categorical:
            frame[column]=frame[column].fillna('').astype(str)
        for column in numeric:
            frame[column]=pd.to_numeric(frame[column],errors='coerce').replace([np.inf,-np.inf],np.nan)
    transforms=[]
    if numeric:
        transforms.append(('numeric',make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),StandardScaler(with_mean=False)),numeric))
    if categorical:
        transforms.append(('category',OneHotEncoder(handle_unknown='ignore',min_frequency=3,sparse_output=True),categorical))
    for index,column in enumerate(text_columns):
        transforms.append((f'text{index}',TfidfVectorizer(max_features=30000,ngram_range=(1,2),min_df=1,sublinear_tf=True),column))
        if recipe.get('params',{}).get('text_char_features',False):
            transforms.append((f'char{index}',TfidfVectorizer(analyzer='char_wb',max_features=15000,ngram_range=(3,5),min_df=2,sublinear_tf=True),column))
    processor=ColumnTransformer(transforms,sparse_threshold=1.0)
    params=recipe.get('params',{})
    if spec['kind']=='classification':
        estimator=SGDClassifier(loss='log_loss',alpha=float(np.clip(params.get('text_alpha',1e-5),1e-7,1e-2)),max_iter=1000,tol=1e-4,
                                random_state=42,class_weight='balanced' if params.get('class_weights') else None,n_jobs=threads)
    else:
        estimator=Ridge(alpha=10,solver='lsqr')
    model=make_pipeline(processor,estimator)
    rows=np.arange(len(train_x)) if full else tr
    with threadpool_limits(limits=threads):
        kwargs={}
        weights=sample_weights(y.iloc[rows],params) if spec['kind']=='classification' else None
        if weights is not None: kwargs[model.steps[-1][0]+'__sample_weight']=weights
        model.fit(train_x.iloc[rows],y.iloc[rows],**kwargs)
        predictions=model.predict(test_x)
        metrics=None
        val_pred=None; proba=None
        if not full:
            val_pred=model.predict(train_x.iloc[va])
            proba=model.predict_proba(train_x.iloc[va]) if spec['kind']=='classification' else None
            metrics=evaluate(y.iloc[va],val_pred,spec['kind'],spec['metric'],proba,getattr(model,'classes_',None))
    if spec.get('prediction_type')=='probability_matrix':
        indices=[list(map(str,model.classes_)).index(str(c)) for c in spec['output_columns']]
        predictions=model.predict_proba(test_x)[:,indices]
    elif spec.get('prediction_type')=='probability':
        predictions=model.predict_proba(test_x)[:,1]
    return predictions,val_pred,metrics,model.predict_proba(test_x) if spec['kind']=='classification' else None,proba,getattr(model,'classes_',None)

