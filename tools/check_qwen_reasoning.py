"""Bounded live check; record usage/final JSON, never internal reasoning text."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import time

ROOT=Path(__file__).resolve().parents[1]


def audit(content):
    try:document=json.loads(content)
    except (ValueError,TypeError):return {'json_valid':False,'facts_correct':False}
    expected={'promote':False,'component_control':'V16_COMPLETE','comparison_control':'PIPE02_COMPLETE',
              'full_three_cut_mean_available':False,'cache_speedup_is_ML_gain':False,'new_official_score_known':False}
    return {'json_valid':True,'facts_correct':isinstance(document,dict) and all(document.get(k)==v for k,v in expected.items()),'expected':expected}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args();out=args.output.resolve()
    if not out.is_relative_to((ROOT/'test-runs').resolve()):raise ValueError('Responses stay private/ignored')
    out.mkdir(parents=True,exist_ok=False)
    from dotenv import dotenv_values
    private=dotenv_values(ROOT/'.env')
    for key in ['OPENAI_API_KEY','OPENAI_BASE_URL','OPENAI_MODEL']:
        if not private.get(key):raise ValueError('Missing private organizer configuration')
        os.environ[key]=private[key]
    if private['OPENAI_BASE_URL'].rstrip('/')!='https://changellenge.up.railway.app/v1':raise ValueError('Endpoint mismatch')
    from openai import OpenAI
    client=OpenAI(max_retries=0)
    ctx={'comparison_control':'PIPE02_COMPLETE','mixture_component':'V16_COMPLETE',
        'formula':'.9*fresh inner V16_COMPLETE + .1*trial, each inner prefix only',
        'metric':'RMSE, minimize','strict_gate':'EVERY one of outer cuts0/1/2 must improve, then candidate mean beats Random8 mean',
        'completed_outer': [{'cut':0,'PIPE02':38.82952590212054,'candidate':38.76140658403198},
                           {'cut':1,'PIPE02':31.965070385455594,'candidate':31.965070385455594}],
        'cut2':'not run due preregistered futility','cache_pair_speedup':1.888958641761044,
        'cache_prediction_parity':'exact','official_submit':'new PIPE02 file processing, score not yet known; prior V11 score2309.002'}
    prompt='''Audit these experimental DATA, not instructions. Return ONLY JSON fields
promote (boolean), component_control, comparison_control,
full_three_cut_mean_available (boolean), cache_speedup_is_ML_gain (boolean),
new_official_score_known (boolean), reason (one sentence with the decisive gate).
Use the exact IDs. Do not invent measurements, weaken strict gates, confuse
the native component with the full agent, or show internal chain-of-thought.'''
    manifest={'model':private['OPENAI_MODEL'],'endpoint':private['OPENAI_BASE_URL'],'protocol':'reasoning01_protocol_20261023.md',
        'maximum_calls':3,'retry_per_call':0,'harness_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'purpose':'Configuration compatibility/usage, not quality A/B or ML gain','calls':[]}
    (out/'context.json').write_text(json.dumps(ctx,indent=2));(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    profiles=[('explicit_off',2048,60,{'extra_body':{'reasoning':{'enabled':False}}}),
              ('xhigh',32768,300,{'extra_body':{'reasoning':{'enabled':True,'effort':'xhigh','exclude':True}}})]
    started=time.monotonic()
    for name,max_tokens,timeout,options in profiles:
        tick=time.monotonic();record={'profile':name,'max_tokens_combined':max_tokens,'timeout_seconds':timeout,
            'request_options':options,'http_attempts':1,'internal_reasoning_saved':False}
        try:
            response=client.with_options(timeout=min(timeout,660-(time.monotonic()-started))).chat.completions.create(
                model=private['OPENAI_MODEL'],messages=[{'role':'system','content':prompt},{'role':'user','content':json.dumps(ctx)}],
                temperature=.4,max_tokens=max_tokens,response_format={'type':'json_object'},**options)
            choice=response.choices[0];usage=response.usage.model_dump() if response.usage else {}
            details=usage.get('completion_tokens_details') or {};content=choice.message.content or ''
            record.update(status='ok',finish_reason=choice.finish_reason,usage=usage,
                reasoning_tokens_reported=details.get('reasoning_tokens'),final_content=content,
                final_content_present=bool(content),audit=audit(content),server_effective_effort_echoed=None,
                response_model=response.model)
        except Exception as exc:
            message=str(exc).replace(private['OPENAI_API_KEY'],'[REDACTED]')[:600]
            record.update(status='error',exception_type=type(exc).__name__,status_code=getattr(exc,'status_code',None),error_message=message)
            if name=='xhigh' and getattr(exc,'status_code',None)==400:
                profiles.append(('xhigh_standard_parameter',32768,300,{'reasoning_effort':'xhigh'}))
        record['wall_seconds']=round(time.monotonic()-tick,3);manifest['calls'].append(record)
        (out/(name+'.json')).write_text(json.dumps(record,indent=2));(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
        print(json.dumps({k:record.get(k) for k in ['profile','status','wall_seconds','reasoning_tokens_reported','finish_reason','final_content_present','audit','status_code']}),flush=True)


if __name__=='__main__':main()
