"""Independently verify the complete mixture after a feature-only nested study."""
from pathlib import Path
import json
import numpy as np
from summarize_research import Verifier,digest,verify_study
from verify_marginal_hpo import load,close
from verify_reg_blend_cv import verify as verify_reference

ROOT=Path(__file__).resolve().parents[1]


def feature_contract(base,candidate):
    for key in set(base)|set(candidate):
        if key not in ['feature_code','hypothesis'] and base.get(key)!=candidate.get(key):raise ValueError('Non-feature change')
    if not candidate.get('feature_code'):raise ValueError('Missing feature intervention')


def verify(path):
    path=Path(path);m=json.loads(path.read_text());v=Verifier(m,path.parent/'sources')
    if not v.source_matches_current or m['comparison_control']!='PIPE02_COMPLETE':raise ValueError('Source or control changed')
    base=ROOT/'test-runs/qwen-optuna-20261022';hpo_path=base/'overnight-20261023/regression-hpo/results.json'
    forward_path=base/'reg-blend01-forward-20261023/benchmark/results.json'
    if digest(hpo_path)!=m['old_hpo_manifest_sha256'] or digest(forward_path)!=m['reference_manifest_sha256']:raise ValueError('Reference manifest changed')
    old=json.loads(hpo_path.read_text());forward=json.loads(forward_path.read_text());reference=verify_reference(forward_path)
    feature_contract(old['control_recipe'],m['candidate_recipe'])
    if m['input_sha256']!=old['input_sha256']:raise ValueError('Reference input differs')
    for name in m['worker_historical_dependency_parity']:
        if m['source_sha256'][name]!=old['source_sha256'][name]:raise ValueError('Historical worker dependency differs')
    plan=Path(m['plan_path'])
    if digest(plan)!=m['plan_sha256']:raise ValueError('Qwen plan changed')
    if json.loads(plan.read_text())['recipe']!=m['candidate_recipe']:raise ValueError('Feature plan does not match candidate')
    control=json.loads((ROOT/'docs/experiments/reg_blend01_candidates_20261023.json').read_text())[0]['recipe']
    cuts=[]
    for row in m['cuts']:
        cut=row['cut'];where=path.parent/f'cut-{cut}';outer=v.split(where/'outer-split.npz');historical=v.split(hpo_path.parent/f'cut-{cut}/outer-split.npz')
        if not all(np.array_equal(a,b) for a,b in zip(outer,historical)):raise ValueError('Outer partition changed')
        study=row['study']
        if study!=json.loads((where/'tpe/hpo.json').read_text()):raise ValueError('Ledger copies differ')
        if (study['sampler']!='tpe' or study['seed']!=137 or study['startup_trials']!=3 or study['maximum_trials']!=8
                or study['control_recipe']!=m['candidate_recipe']):raise ValueError('Study contract changed')
        checked=verify_study(where/'tpe',study,outer[0],v)
        if checked['completed_trials']!=8:raise ValueError('Incomplete study')
        inner=v.split(where/'tpe/split.npz')
        for trial in study['trials']:
            if trial.get('value') is not None:load(v,where/'tpe'/f'trial-{trial["number"]:02d}',inner,trial['recipe'])
        c,_=load(v,next(r['directory'] for r in forward['results'] if r['seed']==cut),outer,control)
        old_a,_=load(v,hpo_path.parent/f'cut-{cut}/outer-tpe',outer,old['cuts'][cut]['tpe']['selected_recipe'])
        candidate,checked_outer=load(v,where/'outer-tpe',outer,study['selected_recipe'])
        truth=v.train[v.spec['target']].iloc[outer[1]].to_numpy(dtype=float)
        strong=float(np.sqrt(np.mean((truth-(.9*c+.1*old_a))**2)))
        value=float(np.sqrt(np.mean((truth-(.9*c+.1*candidate))**2)))
        close(strong,row['PIPE02_rmse']);close(strong,reference['cuts'][cut]['blend_rmse']);close(value,row['mixture_rmse'])
        if row['improved_PIPE02']!=(value<strong):raise ValueError('Gate mismatch')
        cuts.append({'cut':cut,'PIPE02_rmse':strong,'mixture_rmse':value,'gain':strong-value,'improved':value<strong,
            'native_rmse':checked_outer['value'],'study':checked,'split_sha256':digest(where/'outer-split.npz')})
    complete=len(cuts)==3 and [c['cut'] for c in cuts]==[0,1,2]
    summary={'complete_screen':complete,'mean':float(np.mean([c['mixture_rmse'] for c in cuts])) if complete else None,
        'passed':bool(complete and all(c['improved'] for c in cuts))}
    if summary!=m['summary']:raise ValueError('Invalid mean/completeness/gate')
    if m['status']=='rejected_futility' and (not cuts or cuts[-1]['improved']):raise ValueError('Unsupported futility stop')
    return {'status':'verified','cuts':cuts,'summary':summary,'qwen_features':m['qwen_features'],
        'source_sha256':m['source_sha256'],'input_sha256':m['input_sha256'],'verifier_sha256':digest(__file__),
        'qualified_release_changed':False,'official_submission':False}
