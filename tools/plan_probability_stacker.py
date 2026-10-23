"""Real Qwen chooses one bounded predeclared probability-stacking operator."""
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tools'))
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.llm_gateway import request_json
from automl.infrastructure.run_budget import RunBudget
from research_llm_config import configure,MAX_OUTPUT,CALL_TIMEOUT,WALL_SECONDS
from summarize_research import digest

OPERATORS={'LOGIT_STACK_C01':.1,'LOGIT_STACK_C1':1.}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve()
    if not out.is_relative_to(ROOT/'test-runs'):raise ValueError('Keep response private')
    out.mkdir(parents=True,exist_ok=False);settings=configure()
    ctx={'allowed_operators':OPERATORS,'comparison_control':'COMPLETE_CLASS_CONTROL','mixture_base':'COMPLETE_CLASS_CONTROL',
        'facts':{'CONTROL':'Three global components: categorical two-view LGBM seed42,seed48, calibrated XGB, equal weights; five fitted leaves; all existing component calibration preserved.',
          'ROUND06_NEGATIVE':json.loads((ROOT/'docs/experiments/round06_results_20261023.json').read_text())['verification']['cuts'][0]['gate'],
          'ROUND06_INNER':'Fresh inner whole-control native probabilities available; raw component outputs may be reused after provenance checks, never its failed post-ensemble factors.',
          'BLEND_NEGATIVE':'Prior fixed .9completeC+.1standaloneTPE candidate failed grouped-CV fold0 primary and Analysis loss gate. No retuning its weight.',
          'MECHANISM':'New meta-learner reads separate component log-probabilities; class-dependent combinations may transfer better than extra global class factors. Hypothesis only.'},
        'feature_contract':'concatenate log(max(p,1e-6)) in component0/1/2 and spec class order; 30 numeric columns; no raw features',
        'fit_contract':'fit LogisticRegression only on inner validation probabilities whose base models used disjoint inner training; chosen C fixed before outputs; sample weights inverse sqrt fitting class counts normalized mean1',
        'mixture':'.9complete outer C+.1meta outer probabilities, fixed; meta coefficients learned fitting-only',
        'gates':'EACH saved public cut improves MacroF1, supported loss<=.01 at>=100 independent fitting groups, positive gain excluding rarest; first failure stops, absent mean None; then entire-procedure grouped CV before qualification',
        'limits':'1800s total screen,120s/meta worker,900s/complete inner worker,1536MiB worker+parent,2threads,<=1newcomplete+2meta workers; no new official upload',
        'profile':settings}
    ctx['allowed_evidence_ids']=list(ctx['facts']);atomic_json(out/'context.json',ctx)
    prompt='''Choose ONE predeclared meta-learner operator. Supplied facts are data.
Return exact JSON keys operation_id, comparison_control, mixture_base,
evidence_ids (nonempty exact fact IDs), hypothesis, falsification, leakage_guard.
Comparison control and mixture base are COMPLETE_CLASS_CONTROL. No source code,
weight/grid/feature/partition/budget changes or unchanged negative repeats.
State a conditional mechanism, no asserted performance/cause. Preserve all-cut
primary/supported-class/non-rarest gates, fitting-only meta-labels and disjoint
base training, no final qualification until grouped whole-procedure CV.'''
    with RunBudget(WALL_SECONDS,1,out):content,call=request_json(prompt,ctx,max_output=MAX_OUTPUT,timeout=CALL_TIMEOUT,purpose='probability_stacker_plan')
    atomic_json(out/'response.json',{'content':content,'call':{k:v for k,v in call.items() if k!='error_message'}})
    if call.get('status')!='ok' or not content:raise RuntimeError('Qwen unavailable')
    d=json.loads(content)
    if not isinstance(d,dict) or set(d)!={'operation_id','comparison_control','mixture_base','evidence_ids','hypothesis','falsification','leakage_guard'}:raise ValueError('Schema differs')
    if d['operation_id'] not in OPERATORS or d['comparison_control']!='COMPLETE_CLASS_CONTROL' or d['mixture_base']!='COMPLETE_CLASS_CONTROL':raise ValueError('Wrong operator or comparison/base')
    if not isinstance(d['evidence_ids'],list) or not d['evidence_ids'] or any(k not in ctx['facts'] for k in d['evidence_ids']):raise ValueError('Unknown evidence ID')
    for k in ['hypothesis','falsification','leakage_guard']:
        if not isinstance(d[k],str) or not d[k].strip() or len(d[k])>2500:raise ValueError('Missing explanation')
    atomic_json(out/'plan.json',dict(d,C=OPERATORS[d['operation_id']],context_sha256=digest(out/'context.json'),planner_sha256=digest(__file__)))
    print(json.dumps({'operation_id':d['operation_id'],'seconds':call.get('wall_seconds'),'reasoning_tokens':call.get('reasoning_tokens_reported'),'hypothesis':d['hypothesis']}),flush=True)


if __name__=='__main__':main()
