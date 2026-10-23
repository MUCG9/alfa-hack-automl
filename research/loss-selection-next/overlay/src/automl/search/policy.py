"""Task-independent search policy, planner validation and deterministic fallbacks."""
from __future__ import annotations
import hashlib,json
from automl.contracts.messages import DataPolicy,validate_loss_profiles
from automl.execution.api import effective_parameters,CAPABILITIES,validate_feature_view,validate_target_smearing
from automl.evaluation.api import validate_decision_optimizer

ENGINES=set(CAPABILITIES)
PARAMETERS={'iterations','depth','max_depth','learning_rate','num_leaves','min_child_samples',
 'reg_lambda','reg_alpha','l2_leaf_reg','random_strength','class_weights','class_weight_power','feature_views','decision_optimizer','target_smearing','target_smearing_method',
 'subsample','subsample_freq','colsample_bytree','seed','log_target','generic_features','calibrate',
 'min_samples_leaf','max_features','text_alpha','text_char_features','text_svd_components','text_classifier','text_C','min_iterations','min_child_weight','gamma','max_bin','categorical_from_dictionary','multiclass_strategy','target_encoding','calibration_folds','target_encoding_groups','target_encoding_smoothing','target_encoding_auto_groups','target_encoding_refine_groups','target_encoding_counts','target_encoding_half_life','target_encoding_hierarchical','pair_refinement','history_asof','history_min_periods','feature_selection_top_k','feature_selection_protect_original'}

PARAMETERS.add('loss_profile_id')

def signature(recipe):
    validate_loss_profiles(recipe)
    actual={k:recipe.get(k) for k in ['engine','params','feature_code','components','weights','data_policy'] if k in recipe}
    if recipe.get('engine') in CAPABILITIES: actual['params']=effective_parameters(recipe['engine'],recipe.get('params',{}))
    policy=DataPolicy.parse(recipe.get('data_policy'))
    if policy.is_noop: actual.pop('data_policy',None)
    else: actual['data_policy']=policy.to_dict()
    # JSON distinguishes 5 from 5.0 although adapters execute the same value.
    # Keep equivalent HPO anchors from consuming another full outer fit.
    def numeric(value):
        if type(value) is float and value.is_integer(): return int(value)
        if isinstance(value,dict): return {k:numeric(v) for k,v in value.items()}
        if isinstance(value,(list,tuple)): return [numeric(v) for v in value]
        return value
    return hashlib.sha256(json.dumps(numeric(actual),sort_keys=True,default=str).encode()).hexdigest()

def normalize(candidate,best=None):
    if not isinstance(candidate,dict) or candidate.get('engine') not in ENGINES:
        raise ValueError('Unsupported planner recipe')
    params=candidate.get('params',{})
    if not isinstance(params,dict): raise ValueError('params must be an object')
    validate_loss_profiles(candidate)
    if 'feature_views' in params and candidate['engine']!='lightgbm':
        raise ValueError('Unsupported feature-view learner')
    if 'history_asof' in params and not isinstance(params['history_asof'],bool):
        raise ValueError('history_asof must be a boolean')
    if params.get('target_encoding_hierarchical'):
        if params.get('target_encoding_auto_groups') is False or params.get('target_encoding_groups'):
            raise ValueError('Hierarchical contexts require automatic groups')
        params=dict(params,target_encoding_auto_groups=True)
    inherited=best.get('params',{}).copy() if best and best['engine']==candidate['engine'] else {}
    if 'loss_profile_id' in inherited or 'loss_profile_id' in params:
        validate_loss_profiles(dict(candidate,params={**inherited,**params}))
    inherited.update({k:v for k,v in params.items() if k in PARAMETERS})
    if 'feature_views' in params and params['feature_views'] is None:
        inherited.pop('feature_views',None)
    if 'target_smearing' in params and params['target_smearing'] is False:
        if 'target_smearing_method' in params:raise ValueError('Disable correction without a method override')
        inherited.pop('target_smearing',None)
        inherited.pop('target_smearing_method',None)
    if params.get('target_encoding_groups') or params.get('target_encoding_auto_groups'):
        if params.get('target_encoding') is False: raise ValueError('Encoding groups require target_encoding')
        inherited['target_encoding']=True
    if params.get('target_encoding_groups') and 'target_encoding_auto_groups' not in params:
        inherited['target_encoding_auto_groups']=False
        inherited['target_encoding_hierarchical']=False
    if params.get('target_encoding_auto_groups') and 'target_encoding_groups' not in params:
        inherited.pop('target_encoding_groups',None)
    if inherited.get('target_encoding_groups') and inherited.get('target_encoding_auto_groups'):
        raise ValueError('Choose explicit or automatic encoding groups')
    if 'target_encoding_groups' in inherited:
        groups=inherited['target_encoding_groups']
        if not isinstance(groups,list) or len(groups)>3 or any(not isinstance(g,list) or not 2<=len(g)<=6 or any(not isinstance(c,str) for c in g) for g in groups):
            raise ValueError('Invalid target encoding feature groups')
    if 'class_weights' in params and 'class_weight_power' not in params:
        inherited['class_weight_power']=1. if params['class_weights'] else 0.
        inherited.pop('class_weights',None)
    if candidate['engine']=='lightgbm':
        if inherited.get('multiclass_strategy','softmax') not in {'softmax','ova'}: raise ValueError('Unsupported multiclass strategy')
        if 'depth' in params and 'max_depth' not in params: inherited['max_depth']=params['depth']
        inherited.pop('depth',None)
        if 'subsample' in params and 'subsample_freq' not in params:
            inherited['subsample_freq']=1 if float(params['subsample'])<1 else 0
    inherited.update(early_metric='primary',nested_stopping=True)
    inherited.setdefault('min_iterations',100)
    code=candidate.get('feature_code',best.get('feature_code','') if best else '')
    if not isinstance(code,str) or len(code)>12000: raise ValueError('Invalid feature code')
    inherited=effective_parameters(candidate['engine'],inherited)
    generic=inherited.get('generic_features','none')
    if type(generic) is not str or generic not in {'none','missing','skew','both','broad'}:
        raise ValueError('Unsupported generic_features mode')
    selection=inherited.get('feature_selection_top_k',0)
    if type(selection) is not int or not 0<=selection<=512:
        raise ValueError('Invalid feature selection size')
    protect=inherited.get('feature_selection_protect_original',False)
    if type(protect) is not bool:
        raise ValueError('feature_selection_protect_original must be a boolean')
    if protect and not selection:
        raise ValueError('Protected original selection requires positive feature_selection_top_k')
    if selection and candidate['engine']=='linear_text':
        raise ValueError('Feature selection is unsupported for text recipes')
    if inherited.get('history_asof') and (candidate['engine']=='linear_text' or not inherited.get('target_encoding') or not (inherited.get('target_encoding_groups') or inherited.get('target_encoding_auto_groups'))):
        raise ValueError('As-of history requires regression context encoding')
    if 'history_min_periods' in inherited:
        minimum=inherited['history_min_periods']
        if type(minimum) is not int or not 2<=minimum<=10: raise ValueError('history_min_periods must be an integer from2to10')
        if not inherited.get('history_asof'):
            if 'history_min_periods' in params: raise ValueError('Minimum history requires history_asof')
            inherited.pop('history_min_periods')
    policy=DataPolicy.parse(candidate.get('data_policy',best.get('data_policy') if best and best['engine']==candidate['engine'] else None))
    if candidate['engine']=='linear_text' and not policy.is_noop: raise ValueError('Text recipes require noop data policy')
    if candidate['engine']=='linear_text' and inherited.get('target_encoding'): raise ValueError('Target encoding for text recipes is not supported')
    result={'hypothesis':str(candidate.get('hypothesis','Planner hypothesis'))[:1000],
            'engine':candidate['engine'],'params':inherited,'feature_code':code}
    if not policy.is_noop: result['data_policy']=policy.to_dict()
    validate_feature_view(result)
    validate_decision_optimizer(result)
    validate_target_smearing(result)
    return result

def parse_plans(content,best=None):
    decoder=json.JSONDecoder()
    value=None
    for index,char in enumerate(content):
        if char not in '{[': continue
        try:
            value,_=decoder.raw_decode(content[index:]); break
        except json.JSONDecodeError: continue
    if value is None: raise ValueError('No valid planner JSON')
    candidates=value.get('candidates',[value]) if isinstance(value,dict) else value
    if not isinstance(candidates,list): raise ValueError('candidates must be a list')
    result=[]
    for candidate in candidates[:3]:
        try: result.append(normalize(candidate,best))
        except (ValueError,TypeError): continue
    if not result: raise ValueError('No supported planner candidates')
    return result

def portfolio(spec):
    common={'iterations':1200,'learning_rate':.04,'num_leaves':63,'max_depth':-1,
            'min_child_samples':25,'reg_lambda':5,'subsample':1,'colsample_bytree':.9}
    if spec['text_features'] and spec.get('task_family')!='pointwise_ranking':
        return [normalize({'engine':'linear_text','hypothesis':'Bounded TF-IDF baseline','params':{'class_weight_power':.5,'text_alpha':1e-5}}),
                normalize({'engine':'linear_text','hypothesis':'Character n-gram robustness','params':{'class_weight_power':.5,'text_char_features':True,'text_alpha':3e-5}})]
    if spec['kind']=='regression':
        recipes=[normalize({'engine':'lightgbm','hypothesis':'Stronger regularized CPU baseline','params':dict(common,iterations=1600,learning_rate=.035,num_leaves=127,reg_lambda=8,generic_features='missing')}),
                normalize({'engine':'lightgbm','hypothesis':'Higher-leaf capacity with fixed regularization','params':dict(common,iterations=1600,learning_rate=.035,num_leaves=255,reg_lambda=8,generic_features='missing')}),
                normalize({'engine':'xgboost','hypothesis':'Independent histogram-boosting family','params':{'iterations':1800,'learning_rate':.035,'max_depth':8,'min_child_weight':3,'subsample':.85,'colsample_bytree':.9,'reg_lambda':8,'reg_alpha':.1}}),
                normalize({'engine':'catboost','hypothesis':'Bounded native-category pilot','params':{'iterations':600,'depth':6,'learning_rate':.07,'l2_leaf_reg':5}}),
                normalize({'engine':'xgboost','hypothesis':'Controlled deeper histogram capacity; no data augmentation','params':{'iterations':2200,'learning_rate':.03,'max_depth':10,'min_child_weight':2,'subsample':.85,'colsample_bytree':.9,'reg_lambda':6,'reg_alpha':.1,'seed':48}}),
                normalize({'engine':'xgboost','hypothesis':'Paired missingness robustness trial; selection must beat unchanged fitting rows','params':{'iterations':2200,'learning_rate':.03,'max_depth':10,'min_child_weight':2,'subsample':.85,'colsample_bytree':.9,'reg_lambda':6,'reg_alpha':.1,'seed':48},'data_policy':{'augmentation':'mask','copy_fraction':.25,'mask_probability':.15,'synthetic_weight':.5}})]
        if spec.get('validation_strategy')=='time':
            history=dict(recipes[0],params=dict(recipes[0]['params'],target_encoding=True,target_encoding_auto_groups=True,target_encoding_smoothing=2),
                         hypothesis='Recurring training contexts transfer to the next observation period; verify forward backtests')
            history_log=dict(history,params=dict(history['params'],log_target=True),
                             hypothesis='Log-target history model is a separate candidate; compare both forward backtests')
            conservative=dict(recipes[0],params=dict(recipes[0]['params'],num_leaves=31,min_child_samples=100,reg_lambda=15),
                              hypothesis='Reduce capacity under a documented future-period shift')
            semantic=dict(history_log,params=dict(history_log['params'],target_encoding_hierarchical=True),
                          hypothesis='Refine recurring contexts with categorical attributes and schema-described static properties')
            numeric_history=(spec.get('time_candidate') or {}).get('representation','numeric')=='numeric' and (spec.get('time_candidate') or {}).get('split_mode','period')=='period'
            history_recipes=[normalize(history),normalize(history_log)] if numeric_history else []
            if numeric_history and spec.get('static_numeric_features'):
                history_recipes.append(normalize(semantic))
                if spec.get('task_family')!='pointwise_ranking':
                    asof=dict(semantic,params=dict(semantic['params'],history_asof=True,history_min_periods=3),
                              hypothesis='Strictly earlier context values and trends after three fitting periods; compare the unchanged schema-history control')
                    history_recipes.append(normalize(asof))
            recipes=history_recipes+[normalize(conservative)]+recipes
        return recipes
    recipes=[normalize({'engine':'lightgbm','hypothesis':'Higher-capacity mild-weight model','params':dict(common,class_weight_power=.5)}),
            normalize({'engine':'lightgbm','hypothesis':'Iteration-matched inner decision calibration','params':dict(common,class_weight_power=.5,calibrate=True)}),
            normalize({'engine':'xgboost','hypothesis':'Independent histogram-boosting family','params':{'iterations':1800,'learning_rate':.035,'max_depth':6,'min_child_weight':3,'subsample':.85,'colsample_bytree':.9,'reg_lambda':8,'reg_alpha':.1,'class_weight_power':.5,'min_iterations':50}}),
            normalize({'engine':'catboost','hypothesis':'Bounded native-category pilot','params':{'iterations':350,'depth':6,'learning_rate':.07,'class_weight_power':.5}})]
    if spec.get('metric')=='macro_f1':
        recipes.insert(3,normalize(dict(recipes[2],params=dict(recipes[2]['params'],calibrate=True),
            hypothesis='Optional training-only XGBoost decision calibration; retain the uncalibrated control')))
        declared=set(spec.get('categorical_features') or [])
        if spec.get('task_family')!='pointwise_ranking' and len([c for c in spec.get('features',[]) if c in declared])>=2:
            recipes.insert(2,normalize(dict(recipes[1],params=dict(recipes[1]['params'],feature_views='categorical_te_pair'),
                hypothesis='Fixed equal-weight original and cross-fitted categorical feature views; compare full procedure')))
    return recipes

def fallback(spec,number,best):
    candidate=dict(best or portfolio(spec)[0])
    candidate['params']=dict(candidate['params'])
    candidate['hypothesis']='Controlled deterministic alternative'
    if spec['kind']=='classification':
        if candidate['engine']=='xgboost':
            params=candidate['params']; axis=number%4
            depth=max(3,min(12,int(float(params.get('max_depth',6)))))
            if axis==0:
                params['max_depth']=max(3,depth-2) if depth>3 else 5
            elif axis==1:
                params['max_depth']=min(12,depth+2) if depth<12 else 10
            elif axis==2:
                current=max(1,min(50,float(params.get('min_child_weight',3))))
                params['min_child_weight']=min(50,current*2) if current<50 else 25
            else:
                current=max(0,min(100,float(params.get('reg_lambda',8))))
                params['reg_lambda']=min(100,max(1,current*2)) if current<100 else 50
            candidate['hypothesis']='Explore XGBoost capacity at incumbent class weights; vary model seed independently'
        elif number%3==0 and candidate['engine']=='lightgbm': candidate['params']['calibrate']=True
        else: candidate['params']['class_weight_power']=[.35,.65,1.][number%3]
    elif candidate['engine']=='xgboost':
        candidate['params']['max_depth']=[6,8,10][number%3]
        candidate['params']['min_child_weight']=[2,5,10][(number//3)%3]
        candidate['params']['reg_lambda']=[4,8,12][number%3]
    elif candidate['engine']=='catboost':
        candidate['params']['depth']=[5,6,7][number%3]
        candidate['params']['l2_leaf_reg']=[3,6,12][number%3]
    elif candidate['engine']=='lightgbm':
        candidate['params']['num_leaves']=[63,127,255][number%3]
        candidate['params']['subsample']=.85
        candidate['params']['subsample_freq']=1
    candidate['params']['seed']=42+number
    return normalize(candidate)
