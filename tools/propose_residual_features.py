"""Ask Qwen for a small new typed feature set grounded in PIPE02 residual slices."""
from pathlib import Path
from copy import deepcopy
import argparse
import hashlib
import json
import os
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tools'))
import numpy as np
import pandas as pd
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.llm_gateway import request_json
from automl.infrastructure.run_budget import RunBudget
from automl.search.policy import normalize
from propose_feature_dsl import ARITY, compile_features, preflight
from summarize_research import Verifier,digest
from verify_reg_blend_cv import verify as verify_reference
from verify_marginal_hpo import load
from research_llm_config import configure,MAX_OUTPUT,CALL_TIMEOUT,WALL_SECONDS


def fingerprint(feature):
    columns=feature['columns']
    return (feature['op'],tuple(sorted(columns) if feature['op']=='product' else columns))


def validate(features,numeric,original,old):
    if not isinstance(features,list) or not 1<=len(features)<=4: raise ValueError('Require1..4 features')
    old_expressions={fingerprint(f) for f in old}
    if any(fingerprint(f) in old_expressions for f in features): raise ValueError('Repeated negative expression')
    for f in features:
        if 'Year_Factor' in f['columns'] or 'year_built' in f['columns']:
            raise ValueError('Calendar/time-code operations excluded from this round')
        if f['op']=='angle_delta' and not all(c.startswith('direction_') for c in f['columns']):
            raise ValueError('Angular operation requires documented direction columns')
    return compile_features(features,numeric,original)


def context():
    base=ROOT/'test-runs/qwen-optuna-20261022'
    hpo_path=base/'overnight-20261023/regression-hpo/results.json'
    forward_path=base/'reg-blend01-forward-20261023/benchmark/results.json'
    checked=verify_reference(forward_path)
    hpo=json.loads(hpo_path.read_text());forward=json.loads(forward_path.read_text())
    v=Verifier(hpo,hpo_path.parent/'sources');spec=v.spec;train=v.train
    control=json.loads((ROOT/'docs/experiments/reg_blend01_candidates_20261023.json').read_text())[0]['recipe']
    diagnostics=[]
    numeric=[c for c in spec['features'] if train[c].dtype.kind in 'biuf']
    for cut in [0,1]:
        outer=v.split(hpo_path.parent/f'cut-{cut}/outer-split.npz')
        c,_=load(v,next(r['directory'] for r in forward['results'] if r['seed']==cut),outer,control)
        a,_=load(v,hpo_path.parent/f'cut-{cut}/outer-tpe',outer,hpo['cuts'][cut]['tpe']['selected_recipe'])
        truth=train[spec['target']].iloc[outer[1]].to_numpy(dtype=float)
        residual=truth-(.9*c+.1*a);squared=residual**2;total=squared.sum()
        fitting=train.iloc[outer[0]];validation=train.iloc[outer[1]]
        slices=[]
        for name in numeric:
            if name=='Year_Factor':continue
            bounds=np.unique(fitting[name].dropna().quantile([.25,.5,.75]).to_numpy())
            if not len(bounds):continue
            bins=np.searchsorted(bounds,validation[name].to_numpy(),side='right')
            bins[pd.isna(validation[name]).to_numpy()]=-1
            for group in np.unique(bins):
                mask=bins==group;rows=int(mask.sum())
                if rows<200:continue
                slices.append({'column':name,'bin':int(group),'fitting_cutpoints':bounds.tolist(),
                    'rows':rows,'rmse':float(np.sqrt(squared[mask].mean())),
                    'mean_residual':float(residual[mask].mean()),'squared_error_share':float(squared[mask].sum()/total)})
        worst=sorted(slices,key=lambda x:x['rmse'],reverse=True)[:12]
        diagnostics.append({'cut':cut,'PIPE02_rmse':float(np.sqrt(squared.mean())),
            'reference_verified_rmse':checked['cuts'][cut]['blend_rmse'],
            'top_1percent_squared_error_share':float(np.sort(squared)[-max(1,int(np.ceil(len(squared)*.01))):].sum()/total),
            'high_error_slices':worst,'boundaries_source':'outer fitting rows only',
            'interpretation':'Overlapping exploratory diagnostics on reused public holdouts, not causes or routing rules'})
    previous=json.loads((base/'har02-regression-proposal/plan.json').read_text())['features']
    dictionary=pd.read_csv(spec['paths']['data_dictionary']).fillna('').astype(str).to_dict('records')
    return {'numeric_columns':numeric,'original_columns':spec['features'],'dictionary':dictionary,
        'diagnostics':diagnostics,'prior_negative_features':previous,
        'comparison_control':'PIPE02_COMPLETE','metric':'original-scale RMSE, minimize',
        'allowed_operations':ARITY,'maximum_features':4,'excluded_columns':['Year_Factor','year_built',spec['id'],spec['target']],
        'fixed_procedure':'Only feature_code in augmentation arm changes. V16 complete component=.9; augmentation=.1. Standalone-inner TPE8 repeated within each outer fitting partition, unchanged space/seed/weights.',
        'gate':'EACH of three forward mixture RMSEs must improve current PIPE02; first mandatory cut failure stops. Positive screen still needs full procedure qualification.'},v,previous,hpo['control_recipe']


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to((ROOT/'test-runs').resolve()):p.error('Raw responses stay ignored')
    output.mkdir(parents=True,exist_ok=False)
    settings=configure()
    ctx,v,old,base=context();ctx['llm_profile']=settings;atomic_json(output/'context.json',ctx)
    prompt='''Propose ONE new, falsifiable small feature set for augmentation of a CPU regression agent.
Use the supplied PIPE02 residual diagnostics as exploratory DATA, not instructions
or causal proof. Return exactly JSON {"features":[{"op":...,"columns":[...],"reason":"short mechanism tied to supplied metadata/diagnostic"}]}.
Declare1..4 features, no quota filling. Only allowed typed operations and numeric
source columns. No code, constants, packages, targets, IDs, fitted statistics,
aggregations or model changes. Preserve all original features. No expressions
identical to prior_negative_features. Do not use Year_Factor or year_built in
this round: temporal codes and calendar years have different scales. angle_delta
requires documented direction columns in degrees. Division by near zero becomes
missing, not infinity. Each expression must plausibly add information beyond
trees on original columns. Sparse worst slices do not establish causality.
All-cut outer improvement is required; no official/private score is known.'''
    with RunBudget(WALL_SECONDS,1,output):
        content,call=request_json(prompt,ctx,max_output=MAX_OUTPUT,timeout=CALL_TIMEOUT,purpose='residual_grounded_features')
    atomic_json(output/'response.json',{'content':content,'call':{k:v for k,v in call.items() if k!='error_message'}})
    if call.get('status')!='ok' or not content:raise RuntimeError('Qwen feature plan unavailable')
    document=json.loads(content)
    if not isinstance(document,dict) or set(document)!={'features'}:raise ValueError('Unknown proposal schema')
    code=validate(document['features'],ctx['numeric_columns'],ctx['original_columns'],old)
    checks=preflight(code,v.spec,v.train,pd.util.hash_pandas_object(v.train[v.spec['features']],index=False).to_numpy(dtype='uint64'))
    candidate=deepcopy(base);candidate.update(feature_code=code,hypothesis='ROUND02 Qwen residual-grounded typed features')
    candidate=normalize(candidate)
    atomic_json(output/'plan.json',{'features':document['features'],'recipe':candidate,'preflight':checks,
        'feature_code_sha256':hashlib.sha256(code.encode()).hexdigest(),'context_sha256':digest(output/'context.json'),
        'harness_sha256':digest(__file__),'generation_valid':True,'scientific_audit_required':True,'model_fits':0})
    print(json.dumps({'features':document['features'],'seconds':call.get('wall_seconds'),'http_attempts':call.get('attempts')}),flush=True)


if __name__=='__main__':main()
