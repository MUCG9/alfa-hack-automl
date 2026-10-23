"""One compact typed Qwen choice; contracts are tool-owned and cannot be edited."""
from pathlib import Path
import argparse,json,os,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tools'))
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.llm_gateway import reasoning_options
from automl.infrastructure.run_budget import RunBudget
from research_llm_config import configure
from summarize_research import digest
from plan_probability_stacker import OPERATORS


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve()
    if not out.is_relative_to(ROOT/'test-runs'):raise ValueError('Keep final response private')
    out.mkdir(parents=True,exist_ok=False);configure()
    original=ROOT/'test-runs/autoresearch-rounds-20261023/round07/qwen-plan-xhigh';prior=json.loads((original/'response.json').read_text())
    if (original/'plan.json').exists() or prior['call'].get('finish_reason')!='length':raise ValueError('Expected preserved truncated original proposal, no accepted plan')
    ctx=json.loads((original/'context.json').read_text());ctx.pop('profile',None)
    prompt='Choose a predeclared operator for this experiment. Return ONLY one JSON object with exactly operation_id (LOGIT_STACK_C01 or LOGIT_STACK_C1) and evidence_ids (nonempty array of exact keys in facts). All controls, fitting rows, mixture, gates and budgets are fixed by the tool; do not reproduce them or give prose.'
    atomic_json(out/'context.json',ctx)
    from openai import OpenAI
    options,requested,effort=reasoning_options();start=time.monotonic();call={'status':'error','reasoning_requested':requested,'reasoning_effort_requested':effort,'max_tokens_combined':32768,'attempts':0,'compatibility_retry':False};content=None
    with RunBudget(360,1,out) as budget:
        timeout,denied=budget.authorize(300,'compact_typed_stacker_choice')
        if denied is not None:raise RuntimeError('Compact call denied before request')
        try:
            call['attempts']=1
            response=OpenAI(max_retries=0,timeout=timeout).chat.completions.create(model=os.environ['OPENAI_MODEL'],messages=[{'role':'system','content':prompt},{'role':'user','content':json.dumps(ctx,ensure_ascii=False)}],temperature=0,max_tokens=32768,response_format={'type':'json_object'},**options)
            usage=response.usage.model_dump() if response.usage else {};content=response.choices[0].message.content or ''
            call.update(status='ok',usage=usage,finish_reason=response.choices[0].finish_reason,reasoning_tokens_reported=(usage.get('completion_tokens_details') or {}).get('reasoning_tokens'),usage_complete=all(type(usage.get(k)) is int for k in ['prompt_tokens','completion_tokens']))
        except Exception as exc:call.update(exception_type=type(exc).__name__,status_code=getattr(exc,'status_code',None))
        finally:
            call['wall_seconds']=round(time.monotonic()-start,3);budget.record(call,'compact_typed_stacker_choice',reserved=True);atomic_json(out/'response.json',{'content':content,'call':call})
    if call['status']!='ok' or call.get('finish_reason')!='stop':raise RuntimeError('Compact proposal unavailable/truncated; no further repair')
    d=json.loads(content)
    if not isinstance(d,dict) or set(d)!={'operation_id','evidence_ids'} or d['operation_id'] not in OPERATORS or not isinstance(d['evidence_ids'],list) or not d['evidence_ids'] or any(not isinstance(k,str) or k not in ctx['facts'] for k in d['evidence_ids']):raise ValueError('Invalid compact choice; no further repair')
    plan=dict(d,C=OPERATORS[d['operation_id']],comparison_control='COMPLETE_CLASS_CONTROL',mixture_base='COMPLETE_CLASS_CONTROL',
        hypothesis='If component reliability is class-dependent, the fixed regularized fitting-only log-probability stacker may improve the complete-control mixture.',
        falsification=ctx['gates'],leakage_guard=ctx['fit_contract'],context_sha256=digest(out/'context.json'),planner_sha256=digest(__file__),
        proposal_format='compact typed choice plus immutable tool contracts',temperature=0,original_failed_response_sha256=digest(original/'response.json'))
    atomic_json(out/'plan.json',plan);print(json.dumps({'operation_id':d['operation_id'],'reasoning_tokens':call['reasoning_tokens_reported'],'seconds':call['wall_seconds'],'attempts':1}),flush=True)


if __name__=='__main__':main()
