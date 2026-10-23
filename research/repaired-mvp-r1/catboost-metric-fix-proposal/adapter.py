import numpy as np
from automl.execution.weighting.classes import number
from automl.contracts.messages import DataPolicy

def fit_options(spec,recipe,x,y,validation_rows,categorical,target_log):
    options={'cat_features':categorical}
    if validation_rows is not None: options.update(eval_set=(x.iloc[validation_rows],y.iloc[validation_rows]),early_stopping_rounds=100)
    return options
def create_model(recipe,kind,threads,iterations):
    params=recipe.get('params',{})
    depth=number(params,'depth',6,4,10,True)
    learning_rate=number(params,'learning_rate',.06,.01,.2)
    weighted=bool(params.get('class_weights',False)) and 'class_weight_power' not in params and kind=='classification'
    seed=number(params,'seed',42,0,2**31-1,True)
    from catboost import CatBoostClassifier,CatBoostRegressor
    common=dict(iterations=iterations,depth=depth,learning_rate=learning_rate,
                thread_count=threads,random_seed=seed,verbose=False,allow_writing_files=False,
                l2_leaf_reg=number(params,'l2_leaf_reg',5,1,100),
                random_strength=number(params,'random_strength',1,0,10))
    if kind=='regression':
        return CatBoostRegressor(loss_function='RMSE',**common)
    if params.get('early_metric','primary')=='primary':
        metric=recipe.get('metric','macro_f1')
        # CatBoost rejects explicit use_weights when no object-weight path exists.
        # Configured weighted paths keep their existing unweighted metric override.
        weight_path=(weighted or number(params,'class_weight_power',0,0,1)>0
                     or not DataPolicy.parse(recipe.get('data_policy')).is_noop)
        suffix=';use_weights=false' if weight_path else ''
        if metric=='macro_f1': common['eval_metric']='TotalF1:average=Macro'+suffix
        elif metric=='accuracy': common['eval_metric']='Accuracy'+suffix
    return CatBoostClassifier(loss_function='MultiClass',auto_class_weights='Balanced' if weighted else None,**common)
