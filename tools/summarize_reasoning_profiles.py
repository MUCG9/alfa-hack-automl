"""Independently recompute paired structured decisions and reported resource use."""
from pathlib import Path
import argparse
import hashlib
import json
import math
ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(directory):
    directory=Path(directory);m=json.loads((directory/'manifest.json').read_text())
    if m['status']!='completed' or not m['frozen_unchanged']:raise ValueError('Incomplete or changed paired experiment')
    if any(sha(ROOT/p)!=h for p,h in m['frozen_sha256'].items()):raise ValueError('Frozen source/context/protocol differs')
    cases=json.loads((ROOT/'docs/experiments/reasoning02_cases_20261023.json').read_text())
    if len(m['calls'])!=6:raise ValueError('Expected exactly six responses, failures included')
    order=[(c['id'],p) for i,c in enumerate(cases) for p in (['off','xhigh'] if i%2==0 else ['xhigh','off'])]
    if [(r['case_id'],r['profile']) for r in m['calls']]!=order:raise ValueError('Pair ordering or coverage changed')
    result={'status':'independently_verified','model':m['model'],'combined_token_cap_each':32768,'timeout_cap_each':300,
        'cases':[],'profiles':{},'comparison':'Three fixed paired agent decisions, one sample each; no significance/general-quality/ML-gain claim',
        'internal_reasoning_saved':False,'source_sha256':m['frozen_sha256'],'manifest_sha256':sha(directory/'manifest.json'),'verifier_sha256':sha(__file__)}
    totals={p:{'responses':0,'json_valid':0,'schema_valid':0,'scientific_correct':0,'wall_seconds':0.,
        'reasoning_tokens_reported':0,'completion_tokens_reported':0,'prompt_tokens_reported':0,'HTTP_attempts_reported':0,'usage_complete':True} for p in ['off','xhigh']}
    for case in cases:
        context=json.loads((directory/(case['id']+'-context.json')).read_text())
        if context!={k:v for k,v in case.items() if k not in ['expected','required_evidence_id']}:raise ValueError('Context differs or golden answer leaked')
        pair=[r for r in m['calls'] if r['case_id']==case['id']]
        if pair[0]['messages_sha256']!=pair[1]['messages_sha256']:raise ValueError('Unequal paired messages')
        checked={}
        for record in pair:
            profile=record['profile'];call=record['call'];expected=case['expected']
            try:answer=json.loads(record['final_content']);valid=True
            except (TypeError,ValueError):answer=None;valid=False
            schema=valid and isinstance(answer,dict) and set(answer)==set(expected)|{'reason','evidence_ids'}
            if schema:
                schema=(isinstance(answer['reason'],str) and bool(answer['reason'].strip()) and isinstance(answer['evidence_ids'],list)
                    and bool(answer['evidence_ids']) and all(isinstance(k,str) and k in case['facts'] for k in answer['evidence_ids'])
                    and isinstance(answer['allowed_next_operator_ids'],list) and all(isinstance(k,str) for k in answer['allowed_next_operator_ids'])
                    and all(type(answer[k]) is bool for k,v in expected.items() if type(v) is bool))
            wrong=[]
            if schema:
                for key,value in expected.items():
                    if key=='allowed_next_operator_ids':
                        if sorted(answer[key])!=sorted(value):wrong.append(key)
                    elif answer[key]!=value:wrong.append(key)
                if case['required_evidence_id'] not in answer['evidence_ids']:wrong.append('required_evidence_id')
            correct=bool(schema and not wrong)
            actual={'json_valid':bool(valid),'schema_valid':bool(schema),'scientific_correct':correct}
            if any(record['audit'].get(k)!=v for k,v in actual.items()):raise ValueError('Recorded audit disagrees with independent structured evaluation')
            if schema and wrong!=record['audit']['incorrect_fields']:raise ValueError('Mismatch fields disagree')
            if call.get('reasoning_effort_requested')!=profile or call.get('max_tokens_combined')!=32768:raise ValueError('Profile/token cap differs')
            if call.get('compatibility_retry'):raise ValueError('Paired profile silently changed on wire')
            total=totals[profile];total['responses']+=1
            for key,value in actual.items():total[key]+=int(value)
            wall=call.get('wall_seconds');attempts=call.get('attempts')
            if wall is not None and (not isinstance(wall,(int,float)) or not math.isfinite(wall) or wall<0):raise ValueError('Invalid elapsed')
            total['wall_seconds']+=wall or 0;total['HTTP_attempts_reported']+=attempts or 0;total['usage_complete']&=call.get('usage_complete',False)
            usage=call.get('usage') or {}
            for dest,key in [('completion_tokens_reported','completion_tokens'),('prompt_tokens_reported','prompt_tokens')]:total[dest]+=usage.get(key) or 0
            total['reasoning_tokens_reported']+=call.get('reasoning_tokens_reported') or 0
            checked[profile]=dict(actual,incorrect_fields=wrong,seconds=wall,reasoning_tokens_reported=call.get('reasoning_tokens_reported'),
                finish_reason=call.get('finish_reason'),HTTP_attempts=attempts,status=call.get('status'),final_decisive_sentence=answer.get('reason') if schema else None)
        result['cases'].append({'id':case['id'],'profiles':checked,'paired_messages_sha256':pair[0]['messages_sha256']})
    for total in totals.values():total['wall_seconds']=round(total['wall_seconds'],3)
    result['profiles']=totals;result['scientific_correctness_difference_xhigh_minus_off']=totals['xhigh']['scientific_correct']-totals['off']['scientific_correct']
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    result=verify(args.directory);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'profiles':result['profiles'],'difference':result['scientific_correctness_difference_xhigh_minus_off']}))
