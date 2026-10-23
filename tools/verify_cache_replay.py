"""Artifact-only verification of efficiency replay; never launch workers."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from summarize_research import Verifier,digest
from verify_marginal_hpo import load,close


def verify(path):
    path=Path(path);m=json.loads(path.read_text());v=Verifier(m,path.parent/'sources')
    if not v.source_matches_current or m['status']!='completed':raise ValueError('Replay incomplete/source changed')
    rows=v.split(path.parent/'split.npz');requests=m['requests']
    expected=['uncached-1','uncached-2','cached-cold','cached-hit']
    if [r['name'] for r in requests]!=expected or [r['actual_worker_launches'] for r in requests]!=[1,1,1,0]:raise ValueError('Logical/physical execution count mismatch')
    if len(m['worker_launches'])!=3 or len({(r['pid'],r['create_time']) for r in m['worker_launches']})!=3:raise ValueError('Expected three distinct worker identities')
    predictions=[];scores=[]
    for request in requests:
        values,checked=load(v,request['origin'],rows,m['recipe']);close(checked['value'],request['checked']['value'])
        predictions.append(values);scores.append(checked['value'])
        if request['context']['source_sha256']!=m['source_sha256'] or request['context']['input_sha256']!=m['input_sha256'] or request['context']['spec']!=m['spec']:
            raise ValueError('Request cache context differs from frozen manifest')
    if any(not np.array_equal(predictions[0],p) for p in predictions[1:]):raise ValueError('Actual prediction arrays differ')
    for value in scores:close(value,m['original_native_rmse'])
    if any(r['context']!=requests[0]['context'] for r in requests[1:]):raise ValueError('Replay contexts differ')
    hit=requests[-1];where=Path(hit['requested_directory']);receipt=json.loads((where/'cache_reuse.json').read_text())
    if not hit['cache_hit'] or receipt['actual_worker_launched'] or receipt['origin']!=requests[-2]['origin'] or (where/'job.json').exists() or (where/'result.json').exists():
        raise ValueError('Cache hit must explicitly reference an existing fit')
    ctx=json.loads(json.dumps(hit['context']));ctx['recipe'].pop('hypothesis',None)
    fingerprint=hashlib.sha256(json.dumps(ctx,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    if receipt['cache_key']!=fingerprint:raise ValueError('Cache key differs from complete training context')
    entry=json.loads((path.parent/'cache/index.json').read_text())[fingerprint]
    origin=Path(entry['origin']);artifacts={str(p.relative_to(origin)):digest(p) for p in origin.rglob('*') if p.is_file()}
    if artifacts!=entry['artifacts']:raise ValueError('Cache origin artifact hashes changed')
    uncached=sum(r['seconds'] for r in requests[:2]);cached=sum(r['seconds'] for r in requests[2:])
    return {'status':'verified','logical_requests':4,'uncached_worker_launches':2,'cached_worker_launches':1,'hit_worker_launches':0,
        'prediction_array_parity':'exact','native_rmse':scores[0],'complete_agent_metric_gain_claim':False,
        'uncached_pair_seconds':uncached,'cached_pair_seconds':cached,'hit_seconds':hit['seconds'],
        'observed_pair_speedup':uncached/cached,'observed_speed_benefit':cached<uncached,
        'source_sha256':m['source_sha256'],'input_sha256':m['input_sha256'],'verifier_sha256':digest(__file__),
        'qualified_release_changed':False,'official_submission':False}
