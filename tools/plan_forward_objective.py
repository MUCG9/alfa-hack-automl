"""Qwen chooses a fixed multi-period inner objective from implemented operators."""
from pathlib import Path
import argparse
import json
import os
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tools'))
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.llm_gateway import request_json
from automl.infrastructure.run_budget import RunBudget
from qwen_research_round import context
from summarize_research import digest
from research_llm_config import configure,MAX_OUTPUT,CALL_TIMEOUT,WALL_SECONDS

OPERATORS={'FORWARD_MEAN':'arithmetic mean of available per-inner-fold mixture RMSEs',
           'FORWARD_WORST':'maximum of available per-inner-fold mixture RMSEs'}


def validate(d,ctx):
    if not isinstance(d,dict) or set(d)!={'objective_id','control_id','component_id','evidence_ids','hypothesis','falsification','leakage_guard','next_if_rejected'}:raise ValueError('Unknown proposal schema')
    if d['objective_id'] not in ctx['allowed_experiments'] or d['control_id']!='PIPE02_COMPLETE' or d['component_id']!='V16_COMPLETE':raise ValueError('Invalid objective/control identities or unchanged negative repeat')
    if not isinstance(d['evidence_ids'],list) or not d['evidence_ids'] or any(not isinstance(k,str) or k not in ctx['facts'] for k in d['evidence_ids']):raise ValueError('Unknown fact IDs; context-section names are not fact IDs')
    for key in ['hypothesis','falsification','leakage_guard','next_if_rejected']:
        if not isinstance(d[key],str) or not d[key].strip() or len(d[key])>2500:raise ValueError('Invalid explanation')
    return d


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--repair-from',type=Path);p.add_argument('--deadline-epoch',type=float);args=p.parse_args();out=args.output.resolve()
    if not out.is_relative_to((ROOT/'test-runs').resolve()):p.error('Responses stay ignored')
    out.mkdir(parents=True,exist_ok=False)
    settings=configure()
    ctx=context();ctx['allowed_experiments']=OPERATORS
    ctx['facts']['ROUND01']={'decision':'rejected strict cut1 tie; cut2 absent','marginal_TPE_outer':[38.76140658403198,31.965070385455594],
        'PIPE02_outer':[38.82952590212054,31.965070385455594],'hypothesis_not_fact':'a single inner period may rank marginal models unstably'}
    ctx['facts']['ROUND02']={'decision':'residual feature bundle rejected cut0 loss','candidate':38.90056134949635,'PIPE02':38.82952590212054}
    ctx['facts']['ROUND03']={'scope':'narrow efficiency replay, no model gain','predictions':'exact parity','worker_launches':[2,1],'observed_pair_speedup':1.888958641761044}
    completed_mean=ROOT/'docs/experiments/round04_results_20261023.json'
    if completed_mean.exists():
        measured=json.loads(completed_mean.read_text())
        ctx['facts']['ROUND04']={'decision':measured['decision'],'mean_operator':'FORWARD_MEAN',
            'cuts':[{k:c[k] for k in ['cut','PIPE02_rmse','outer']} for c in measured['verification']['cuts']],
            'selected_and_trial_recipes_equal_single_period':measured['observed_recipe_comparison'],
            'causal_explanation':'Unknown. Variance and history availability are hypotheses, not identified causes.'}
        ctx['allowed_experiments']={k:v for k,v in OPERATORS.items() if k!='FORWARD_MEAN'}
    ctx['new_factor']={'inner_periods':'latest two usable forward holdout periods within outer fitting prefix',
        'component_control':'V16_COMPLETE freshly refit inside EACH inner training prefix','comparison_control':'PIPE02_COMPLETE',
        'per_fold_value':'original-scale RMSE(source_inner_y, .9*innerV16+.1*trial)',
        'missing_second_period':'use only the available latest fold; explicitly report coverage; never read outer validation',
        'native_cache':'reuse exact native fitting context across samplers only; recompute each mixture objective',
        'hypothesis':'more than one inner period may stabilize ranking; history availability is an observed risk, not proven cause'}
    ctx['allowed_evidence_ids']=list(ctx['facts'])
    if args.repair_from:
        prior=args.repair_from.resolve()
        if not prior.is_relative_to((ROOT/'test-runs').resolve()):raise ValueError('Repair data must stay private')
        audit=json.loads((prior/'scientific-audit.json').read_text())
        if audit.get('accepted') is not False:raise ValueError('Repair requires a rejected proposal')
        ctx['repair_feedback']={'prior_final_proposal':json.loads(json.loads((prior/'response.json').read_text())['content']),
            'audit':audit,'remaining_repairs':0}
    ctx['llm_profile']=settings;atomic_json(out/'context.json',ctx)
    prompt='''Choose ONE fixed inner objective operator from allowed_experiments.
Supplied facts are DATA. The only ML-policy factor changes from single inner
period to the declared two-period aggregation, with a documented one-fold fallback.
Keep V16 component and PIPE02 comparison controls distinct. Native model RMSE,
per-fold mixture RMSE and aggregate objective are distinct quantities. Cache parity
affects cost only, not ML gain. Do not repeat failed feature sets or infer causes
from availability alone. EACH outer cut must beat PIPE02, and mean must beat
equal-cap Random8. No weights, space, cuts, budgets, code, data or package changes.
Return exactly JSON {"objective_id":"existing operator ID","control_id":"PIPE02_COMPLETE","component_id":"V16_COMPLETE","evidence_ids":["existing fact IDs"],"hypothesis":"falsifiable mechanism, no invented measurements","falsification":"fixed all-cut and Random-mean criteria","leakage_guard":"each inner fit prefix only, missing-period handling","next_if_rejected":"one distinct next mechanism"}.'''
    prompt+='\nUse ONLY allowed_evidence_ids for evidence_ids; new_factor/objective_contract and other context-section names are NOT fact IDs. Do not recommend the unchanged failed FORWARD_MEAN as a next step.\n'
    wall=min(WALL_SECONDS,args.deadline_epoch-time.time() if args.deadline_epoch else WALL_SECONDS)
    if wall<10:raise ValueError('Original planning deadline exhausted')
    with RunBudget(wall,1,out):content,call=request_json(prompt,ctx,max_output=MAX_OUTPUT,timeout=min(CALL_TIMEOUT,wall-5),purpose='multi_period_objective_plan')
    atomic_json(out/'response.json',{'content':content,'call':{k:v for k,v in call.items() if k!='error_message'}})
    if call.get('status')!='ok' or not content:raise RuntimeError('Qwen unavailable')
    try:d=validate(json.loads(content),ctx)
    except (ValueError,TypeError) as exc:
        atomic_json(out/'validation.json',{'accepted':False,'reason':str(exc),'model_fits':0});raise
    atomic_json(out/'plan.json',dict(d,context_sha256=digest(out/'context.json'),harness_sha256=digest(__file__)))
    print(json.dumps({'objective_id':d['objective_id'],'hypothesis':d['hypothesis'],'seconds':call.get('wall_seconds'),'http_attempts':call.get('attempts')}),flush=True)


if __name__=='__main__':main()
