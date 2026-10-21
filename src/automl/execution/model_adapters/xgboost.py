import numpy as np
from automl.evaluation.api import lgbm_metric
from automl.execution.weighting.classes import number

def fit_options(spec,recipe,x,y,validation_rows,categorical,target_log):
    if validation_rows is None: return {}
    evaluator=lgbm_metric(spec,target_log)
    def primary_loss(truth,predictions):
        _,value,higher=evaluator(truth,predictions)
        return 1-value if higher else value
    return {'eval_set':[(x.iloc[validation_rows],y.iloc[validation_rows])],'eval_metric':primary_loss}
class CPUXGBoost:
    """Adapter preserving original string labels with the pinned XGBoost 2.1 API."""
    def __init__(self,kind,params):
        self.kind=kind; self.params=params; self.model=None; self.encoder=None

    def fit(self,x,y,sample_weight=None,eval_set=None,eval_metric=None):
        from xgboost import XGBClassifier,XGBRegressor
        from sklearn.preprocessing import LabelEncoder
        values=np.asarray(y)
        evaluation=eval_set
        if self.kind=='classification':
            self.encoder=LabelEncoder(); values=self.encoder.fit_transform(values.astype(str))
            if eval_set is not None:
                evaluation=[(frame,self.encoder.transform(np.asarray(target).astype(str))) for frame,target in eval_set]
        options=dict(self.params)
        if eval_set is not None:
            options['early_stopping_rounds']=100
            if eval_metric is not None: options['eval_metric']=eval_metric
        cls=XGBClassifier if self.kind=='classification' else XGBRegressor
        self.model=cls(**options)
        self.model.fit(x,values,sample_weight=sample_weight,eval_set=evaluation,verbose=False)
        return self

    def predict(self,x):
        values=self.model.predict(x)
        return self.encoder.inverse_transform(values.astype(int)) if self.encoder is not None else values

    def predict_proba(self,x): return self.model.predict_proba(x)

    @property
    def classes_(self):
        if self.encoder is None: raise AttributeError('Regression has no classes')
        return self.encoder.classes_

    @property
    def best_iteration_(self):
        try: return int(self.model.best_iteration)+1
        except AttributeError: return 0

    @property
    def feature_importances_(self): return self.model.feature_importances_


def create_model(recipe,kind,threads,iterations):
    params=recipe.get('params',{})
    depth=number(params,'depth',6,4,10,True)
    learning_rate=number(params,'learning_rate',.06,.01,.2)
    weighted=bool(params.get('class_weights',False)) and 'class_weight_power' not in params and kind=='classification'
    seed=number(params,'seed',42,0,2**31-1,True)
    options=dict(n_estimators=iterations,learning_rate=learning_rate,
        max_depth=number(params,'max_depth',params.get('depth',8),3,12,True),
        min_child_weight=number(params,'min_child_weight',3,1,50),
        subsample=number(params,'subsample',.85,.5,1),colsample_bytree=number(params,'colsample_bytree',.9,.5,1),
        reg_lambda=number(params,'reg_lambda',8,0,100),reg_alpha=number(params,'reg_alpha',.1,0,20),
        gamma=number(params,'gamma',0,0,10),max_bin=number(params,'max_bin',256,64,512,True),
        tree_method='hist',device='cpu',enable_categorical=True,max_cat_to_onehot=8,
        n_jobs=threads,random_state=seed)
    return CPUXGBoost(kind,options)
