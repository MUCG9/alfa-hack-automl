"""Only the coordinator's gateway receives credentials; domain code gets JSON."""
import json,os,time
from automl.infrastructure.run_budget import current_budget

def request_json(system_prompt,context,max_output=16384,timeout=300,purpose='planner'):
    budget=current_budget()
    configured=all(os.environ.get(k) for k in ['OPENAI_API_KEY','OPENAI_BASE_URL'])
    reserved=False
    if budget is not None and configured:
        timeout,denied=budget.authorize(timeout,purpose)
        if denied is not None:
            budget.record(denied,purpose)
            return None,denied
        reserved=True
    content,call=_request_json(system_prompt,context,max_output,timeout)
    if budget is not None: budget.record(call,purpose,reserved=reserved)
    return content,call


def _request_json(system_prompt,context,max_output=16384,timeout=300):
    if not all(os.environ.get(k) for k in ['OPENAI_API_KEY','OPENAI_BASE_URL']): return None,{'status':'unconfigured'}
    from openai import OpenAI,BadRequestError,APIStatusError,APITimeoutError,APIConnectionError
    start=time.monotonic(); usage={}; finish=None; compatibility=False; attempts=0
    try:
        client=OpenAI(timeout=timeout,max_retries=0)
        request={'model':os.environ.get('OPENAI_MODEL','qwen/qwen3.8-27b'),
                 'messages':[{'role':'system','content':system_prompt},{'role':'user','content':json.dumps(context,ensure_ascii=False,default=str)}],
                 'temperature':.4,'max_tokens':max_output,'response_format':{'type':'json_object'}}
        for retry in range(3):
            remaining=timeout-(time.monotonic()-start)
            budget=current_budget()
            if budget is not None: remaining=min(remaining,budget.remaining())
            if remaining<5: raise TimeoutError('Gateway deadline')
            attempts+=1
            try:
                extra={} if compatibility else {'extra_body':{'reasoning':{'enabled':False}}}
                response=client.with_options(timeout=remaining).chat.completions.create(**request,**extra)
                break
            except BadRequestError:
                if compatibility or retry==2: raise
                compatibility=True
            except (APIStatusError,APITimeoutError,APIConnectionError) as exc:
                status=getattr(exc,'status_code',None)
                if status is not None and status!=429 and status<500: raise
                if retry==2: raise
                pause_left=timeout-(time.monotonic()-start)
                if budget is not None: pause_left=min(pause_left,budget.remaining())
                pause=min(2**retry,max(0,pause_left-5))
                if pause: time.sleep(pause)
        usage=response.usage.model_dump() if response.usage else {}; finish=response.choices[0].finish_reason
        return response.choices[0].message.content or '',{'status':'ok','wall_seconds':round(time.monotonic()-start,3),
            'usage':usage,'finish_reason':finish,'compatibility_retry':compatibility,'reasoning_requested':False,
            'attempts':attempts,'usage_complete':attempts==1 and all(type(usage.get(k)) is int and usage[k]>=0 for k in ['prompt_tokens','completion_tokens'])}
    except Exception as exc:
        message=str(exc).replace(os.environ.get('OPENAI_API_KEY','credential-unset'),'[REDACTED]')[:500]
        return None,{'status':'error','exception_type':type(exc).__name__,'wall_seconds':round(time.monotonic()-start,3),
                     'usage':usage,'finish_reason':finish,'compatibility_retry':compatibility,
                     'attempts':attempts,'status_code':getattr(exc,'status_code',None),'error_message':message}
