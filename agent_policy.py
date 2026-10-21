"""Task-independent search policy, planner validation and deterministic fallbacks."""
from __future__ import annotations
import hashlib,json

ENGINES={'lightgbm','catboost','xgboost','extra_trees','linear_text'}
PARAMETERS={'iterations','depth','max_depth','learning_rate','num_leaves','min_child_samples',
 'reg_lambda','reg_alpha','l2_leaf_reg','random_strength','class_weights','class_weight_power',
 'subsample','subsample_freq','colsample_bytree','seed','log_target','generic_features','calibrate',
 'min_samples_leaf','max_features','text_alpha','text_char_features','min_iterations','min_child_weight','gamma','max_bin'}

def signature(recipe):
    actual={k:recipe.get(k) for k in ['engine','params','feature_code','components','weights'] if k in recipe}
    return hashlib.sha256(json.dumps(actual,sort_keys=True,default=str).encode()).hexdigest()

def normalize(candidate,best=None):
    if not isinstance(candidate,dict) or candidate.get('engine') not in ENGINES:
        raise ValueError('Unsupported planner recipe')
    params=candidate.get('params',{})
    if not isinstance(params,dict): raise ValueError('params must be an object')
    inherited=best.get('params',{}).copy() if best and best['engine']==candidate['engine'] else {}
    inherited.update({k:v for k,v in params.items() if k in PARAMETERS})
    if 'class_weights' in params and 'class_weight_power' not in params:
        inherited['class_weight_power']=1. if params['class_weights'] else 0.
        inherited.pop('class_weights',None)
    if candidate['engine']=='lightgbm':
        if 'depth' in params and 'max_depth' not in params: inherited['max_depth']=params['depth']
        inherited.pop('depth',None)
        if 'subsample' in params and 'subsample_freq' not in params:
            inherited['subsample_freq']=1 if float(params['subsample'])<1 else 0
    inherited.update(early_metric='primary',nested_stopping=True)
    inherited.setdefault('min_iterations',100)
    code=candidate.get('feature_code',best.get('feature_code','') if best else '')
    if not isinstance(code,str) or len(code)>12000: raise ValueError('Invalid feature code')
    return {'hypothesis':str(candidate.get('hypothesis','Planner hypothesis'))[:1000],
            'engine':candidate['engine'],'params':inherited,'feature_code':code}

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
    if spec['text_features']:
        return [normalize({'engine':'linear_text','hypothesis':'Bounded TF-IDF baseline','params':{'class_weight_power':.5,'text_alpha':1e-5}}),
                normalize({'engine':'linear_text','hypothesis':'Character n-gram robustness','params':{'class_weight_power':.5,'text_char_features':True,'text_alpha':3e-5}})]
    if spec['kind']=='regression':
        return [normalize({'engine':'lightgbm','hypothesis':'Stronger regularized CPU baseline','params':dict(common,iterations=1600,learning_rate=.035,num_leaves=127,reg_lambda=8,generic_features='missing')}),
                normalize({'engine':'lightgbm','hypothesis':'Higher-leaf capacity with fixed regularization','params':dict(common,iterations=1600,learning_rate=.035,num_leaves=255,reg_lambda=8,generic_features='missing')}),
                normalize({'engine':'xgboost','hypothesis':'Independent histogram-boosting family','params':{'iterations':1800,'learning_rate':.035,'max_depth':8,'min_child_weight':3,'subsample':.85,'colsample_bytree':.9,'reg_lambda':8,'reg_alpha':.1}}),
                normalize({'engine':'catboost','hypothesis':'Bounded native-category pilot','params':{'iterations':600,'depth':6,'learning_rate':.07,'l2_leaf_reg':5}})]
    return [normalize({'engine':'lightgbm','hypothesis':'Higher-capacity mild-weight model','params':dict(common,class_weight_power=.5)}),
            normalize({'engine':'lightgbm','hypothesis':'Iteration-matched inner decision calibration','params':dict(common,class_weight_power=.5,calibrate=True)}),
            normalize({'engine':'xgboost','hypothesis':'Independent histogram-boosting family','params':{'iterations':1800,'learning_rate':.035,'max_depth':6,'min_child_weight':3,'subsample':.85,'colsample_bytree':.9,'reg_lambda':8,'reg_alpha':.1,'class_weight_power':.5,'min_iterations':50}}),
            normalize({'engine':'catboost','hypothesis':'Bounded native-category pilot','params':{'iterations':350,'depth':6,'learning_rate':.07,'class_weight_power':.5}})]

def fallback(spec,number,best):
    candidate=dict(best or portfolio(spec)[0])
    candidate['params']=dict(candidate['params'])
    candidate['hypothesis']='Controlled deterministic alternative'
    if spec['kind']=='classification':
        if number%3==0 and candidate['engine']=='lightgbm': candidate['params']['calibrate']=True
        else: candidate['params']['class_weight_power']=[.35,.65,1.][number%3]
    else:
        candidate['params']['num_leaves']=[63,127,255][number%3]
        candidate['params']['subsample']=.85
        candidate['params']['subsample_freq']=1
    candidate['params']['seed']=42+number
    return candidate
