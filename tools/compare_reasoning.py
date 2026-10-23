"""Matched ML-plan proposals: qualified fast mode versus explicit xhigh.

Development only. Same prompt/context/token ceiling and two proposals per mode.
This is generation evidence; downstream paired fits determine ML usefulness.
"""
from pathlib import Path
import argparse,hashlib,json,os,sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'tools'))
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.run_budget import RunBudget
from automl.search.policy import signature
from automl.search.runner import planner_context,llm_plan,ordered
import automl.search.runner as runner
from compare_planners import proposal_diagnostics
from automl.task_understanding.api import discover
from automl.evaluation.api import choose_validation,make_split
import numpy as np

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task',type=Path,required=True)
    parser.add_argument('--baseline-report',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--modes',nargs='+',choices=['off','default','low','medium','xhigh'],default=['off','xhigh'])
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    spec,profile,train,_,_,text,hashes=discover(args.task)
    spec=choose_validation(spec,train,'auto')
    tr,va,info=make_split(spec,train,hashes,42)
    report=json.loads(args.baseline_report.read_text(encoding='utf-8'))
    records=report['experiments'];best=ordered(records,spec)[0]
    if info['split_sha256']!=report['split']['split_sha256']:
        raise ValueError('Stored control and current source do not use the same search rows')
    context=planner_context(spec,profile,text,info,records,best,900,1)
    context['experimental_instruction']='Use exactly the same bounded staged decision for every comparison mode. Return at most two distinct candidates. Existing measured negative outcomes remain binding evidence. Do not change data, validation or evaluator. Native broad feature generation exists as params.generic_features="broad" (bounded128 additions), but a proposal remains a hypothesis. The two fixed categorical views may use broad; feature_code must be empty for that family. CatBoost top-k selection is not enabled in this prompt comparison.'
    atomic_json(out/'context.json',context)
    np.savez(out/'split.npz',train=tr,validation=va)
    common={'scope':'One matched proposal call per reasoning mode; reused public feedback, no model fitting or official score',
            'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'context_sha256':hashlib.sha256(json.dumps(context,sort_keys=True,default=str).encode()).hexdigest(),
            'baseline_report_sha256':hashlib.sha256(args.baseline_report.read_bytes()).hexdigest(),
            'input_sha256':{n:hashlib.sha256(Path(p).read_bytes()).hexdigest() for n,p in spec['paths'].items()},
            'modes':{},'prompt_mode':'staged','max_output_tokens':16384,'maximum_candidates_per_mode':2}
    previous=os.environ.get('AUTOML_REASONING_EFFORT')
    try:
        with RunBudget(240*len(args.modes)+30,len(args.modes),out):
            for mode in args.modes:
                os.environ['AUTOML_REASONING_EFFORT']=mode
                tick=time.monotonic()
                original=runner.request_json;captured={}
                def observe(*a,**kw):
                    content,call=original(*a,**kw)
                    captured['content']=content
                    atomic_json(out/(mode+'-raw.json'),{'content':content})
                    return content,call
                runner.request_json=observe
                try:
                    plans,call=llm_plan(context,out,max_output=16384,timeout=240,prompt_mode='staged')
                finally:
                    runner.request_json=original
                candidates=[{'name':'qualified-search-control','recipe':best['recipe']}]
                seen={signature(best['recipe'])};rejected=[]
                for number,plan in enumerate(plans):
                    if plan.get('params',{}).get('feature_selection_top_k',0):
                        rejected.append({'number':number,'reason':'selector_outside_matched_prompt_scope'});continue
                    fingerprint=signature(plan)
                    if fingerprint in seen or len(candidates)>=3:
                        rejected.append({'number':number,'reason':'duplicate_or_cap'});continue
                    seen.add(fingerprint);candidates.append({'name':mode+'-'+str(number+1),'recipe':plan})
                atomic_json(out/(mode+'-candidates.json'),candidates)
                common['modes'][mode]={'call':call,'accepted_novel_candidates':len(candidates)-1,
                                       'parser_diagnostics':proposal_diagnostics(captured.get('content'),best['recipe']),
                                       'rejected':rejected,'elapsed_seconds':round(time.monotonic()-tick,3)}
                atomic_json(out/'generation.json',common)
                print(json.dumps({'mode':mode,**common['modes'][mode]},ensure_ascii=False),flush=True)
    finally:
        if previous is None:os.environ.pop('AUTOML_REASONING_EFFORT',None)
        else:os.environ['AUTOML_REASONING_EFFORT']=previous
if __name__=='__main__':main()
