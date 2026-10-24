import numpy as np
from automl.evaluation.api import lgbm_metric
from automl.execution.weighting.classes import number
from automl.contracts.messages import resolve_loss_profile

def fit_options(spec,recipe,x,y,validation_rows,categorical,target_log):
    resolve_loss_profile(recipe.get('engine','lightgbm'),recipe.get('params',{}),spec['kind'])
    if validation_rows is None: return {}
    from lightgbm import early_stopping,log_evaluation
    options={'eval_set':[(x.iloc[validation_rows],y.iloc[validation_rows])],
             'callbacks':[early_stopping(100,first_metric_only=True,verbose=False),log_evaluation(0)]}
    if recipe.get('params',{}).get('early_metric','primary')=='primary': options['eval_metric']=lgbm_metric(spec,target_log)
    return options
def create_model(recipe,kind,threads,iterations):
    params=recipe.get('params',{})
    loss_profile=resolve_loss_profile(recipe.get('engine','lightgbm'),params,kind)
    depth=number(params,'depth',6,4,10,True)
    learning_rate=number(params,'learning_rate',.06,.01,.2)
    weighted=bool(params.get('class_weights',False)) and 'class_weight_power' not in params and kind=='classification'
    seed=number(params,'seed',42,0,2**31-1,True)
    from lightgbm import LGBMClassifier,LGBMRegressor
    max_depth=int(params.get('max_depth',params.get('depth',-1)))
    max_depth=-1 if max_depth<=0 else int(np.clip(max_depth,3,14))
    subsample=number(params,'subsample',1,.5,1)
    common=dict(n_estimators=iterations,learning_rate=learning_rate,
                num_leaves=number(params,'num_leaves',31,15,255,True),max_depth=max_depth,
                reg_lambda=number(params,'reg_lambda',3,0,100),reg_alpha=number(params,'reg_alpha',0,0,20),
                n_jobs=threads,random_state=seed,verbosity=-1,
                colsample_bytree=number(params,'colsample_bytree',.9,.5,1),subsample=subsample,
                subsample_freq=int(params.get('subsample_freq',1 if subsample<1 else 0)),
                min_child_samples=number(params,'min_child_samples',30,5,150,True))
    if params.get('early_metric','primary')=='primary':
        common['metric']='None'
    if loss_profile is not None:
        common.update(loss_profile.parameters())
    if kind=='regression': return LGBMRegressor(**common)
    strategy=params.get('multiclass_strategy','softmax')
    if strategy not in {'softmax','ova'}: raise ValueError('Unsupported multiclass strategy')
    if strategy=='ova' and recipe.get('n_classes',3)>2: common['objective']='multiclassova'
    model=LGBMClassifier(class_weight='balanced' if weighted else None,**common)
    if params.get('pair_refinement',False):
        from automl.execution.model_adapters.specialists import PairSpecialists
        model=PairSpecialists(model)
    return model

def loss_profile_fit_receipt(recipe,kind,model):
    """Certify actual post-fit Booster params; no constructor/default fallback."""
    profile=resolve_loss_profile(recipe.get('engine','lightgbm'),recipe.get('params',{}),kind)
    if profile is None: return None
    booster=getattr(model,'booster_',None)
    actual=getattr(booster,'params',None)
    if not isinstance(actual,dict): raise ValueError('Fitted Booster params are unavailable for loss-profile verification')
    objective=actual.get('objective')
    metric=actual.get('metric')
    if isinstance(metric,str):
        effective_metric=metric
        metric_values=[metric]
    elif isinstance(metric,list) and all(isinstance(item,str) for item in metric):
        effective_metric=list(metric)
        metric_values=metric
    else:
        raise ValueError('Fitted Booster metric is unavailable or not JSON-safe')
    if not metric_values or any(item.lower() not in {'none','na','null','custom'} for item in metric_values):
        raise ValueError('Fitted Booster default loss metric was not disabled')
    alpha=actual.get('alpha')
    if alpha is not None:
        if isinstance(alpha,bool) or not isinstance(alpha,(int,float)) or not np.isfinite(alpha):
            raise ValueError('Fitted Booster alpha is unavailable or nonfinite')
        alpha=float(alpha)
    if objective!=profile.objective or (profile.alpha is not None and alpha!=profile.alpha):
        raise ValueError('Fitted Booster loss does not match requested fixed profile')
    from lightgbm import __version__
    return {'loss_profile_id':profile.loss_profile_id,'requested_objective':profile.objective,
            'requested_alpha':profile.alpha,'effective_objective':objective,'effective_alpha':alpha,
            'requested_metric':'None','effective_metric':effective_metric,
            'evidence_source':'fitted_booster.params','verified':True,'library':'lightgbm','library_version':__version__}
