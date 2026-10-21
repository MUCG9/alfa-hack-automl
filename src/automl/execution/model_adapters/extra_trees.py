import numpy as np
from automl.execution.weighting.classes import number

def fit_options(spec,recipe,x,y,validation_rows,categorical,target_log): return {}
def create_model(recipe,kind,threads,iterations):
    params=recipe.get('params',{})
    depth=number(params,'depth',6,4,10,True)
    learning_rate=number(params,'learning_rate',.06,.01,.2)
    weighted=bool(params.get('class_weights',False)) and 'class_weight_power' not in params and kind=='classification'
    seed=number(params,'seed',42,0,2**31-1,True)
    from sklearn.ensemble import ExtraTreesClassifier,ExtraTreesRegressor
    common=dict(n_estimators=min(iterations,500),n_jobs=threads,random_state=seed,
                max_depth=number(params,'max_depth',24,6,40,True),
                min_samples_leaf=number(params,'min_samples_leaf',2,1,20,True),
                max_features=number(params,'max_features',.9,.4,1))
    return ExtraTreesRegressor(**common) if kind=='regression' else ExtraTreesClassifier(class_weight='balanced' if weighted else None,**common)
