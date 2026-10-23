"""Fit-free early rejection of a predeclared pool/shortlist proposal."""
from pathlib import Path
import argparse,hashlib,itertools,json,sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.tables import read_input_table
from automl.execution.api import read_cache,combine
from automl.search.policy import signature


def load(path):
    path=path.resolve();report=json.loads(path.read_text())
    if not report.get('integrity_ok') or report.get('final_fit_status')!='ok':
        raise ValueError('Only completed integrity-passing full reports may be replayed')
    spec=report['spec']
    if spec['kind']!='classification' or spec['metric']!='macro_f1':
        raise ValueError('This proposal is only MacroF1 classification')
    task_root=path.parent.parent.parent
    fingerprints=json.loads((path.parent/'provenance.json').read_text())['sha256']
    hashes={}
    for role,location in spec['paths'].items():
        source=Path(location).resolve()
        if not source.is_relative_to(task_root):raise ValueError('Input escapes frozen task copy')
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        if digest!=fingerprints['input:'+role]:raise ValueError('Frozen input fingerprint mismatch')
        hashes[role]=digest
    return report,hashes,path


def replay(spec,records,pool,cache):
    ranked=sorted((r for r in records if r['status']=='ok'),
                  key=lambda r:r['metrics']['macro_f1'],reverse=True)
    candidates=ranked[:2]
    if len(ranked)>2:
        families={r['recipe']['engine'] for r in candidates}
        extra=next((r for r in ranked[2:] if r['recipe']['engine'] not in families),ranked[2]) if len(families)==1 else ranked[2]
        candidates.append(extra)
    selection=[]
    for first in candidates:
        key=signature(first['recipe'])
        if key not in pool:
            return {'status':'needs_fit','missing_confirmation_recipe':key}
        second=pool[key]
        selection.append({'first':first,'second':second,
            'mean':float(np.mean([first['metrics']['macro_f1'],second['metrics']['macro_f1']]))})
    selection.sort(key=lambda s:s['mean'],reverse=True)
    winner=selection[0]
    result={'status':'ok','search':winner['first']['metrics']['macro_f1'],
        'confirmation':winner['second']['metrics']['macro_f1'],'mean':winner['mean'],
        'recipes':[signature(winner['first']['recipe'])],'weights':[1.]}
    first=[cache(s['first']) for s in selection];second=[cache(s['second']) for s in selection]
    configurations=[]
    for pair in itertools.combinations(range(len(selection)),2):
        for weight in [.5,.25,.75,.1,.9]:configurations.append((list(pair),[weight,1-weight]))
    if len(selection)==3:
        configurations.extend([([0,1,2],[1/3]*3),([0,1,2],[.5,.25,.25]),
            ([0,1,2],[.25,.5,.25]),([0,1,2],[.25,.25,.5])])
    for indices,weights in configurations:
        a=combine(spec,[first[i] for i in indices],weights)[0]['macro_f1']
        b=combine(spec,[second[i] for i in indices],weights)[0]['macro_f1']
        mean=float(np.mean([a,b]))
        if mean>result['mean']:
            result.update(search=a,confirmation=b,mean=mean,weights=weights,
                recipes=[signature(selection[i]['first']['recipe']) for i in indices])
    return result


def expected(report):
    ensemble=report.get('ensemble')
    if ensemble:
        return [ensemble['primary']['metrics']['macro_f1'],ensemble['confirmation']['metrics']['macro_f1'],ensemble['mean']]
    chosen=signature(report['selected_recipe'])
    first=next(r for r in report['experiments'] if signature(r['recipe'])==chosen)
    second=next(r for r in report['confirmations'] if signature(r['recipe'])==chosen)
    return [first['metrics']['macro_f1'],second['metrics']['macro_f1'],float(np.mean([first['metrics']['macro_f1'],second['metrics']['macro_f1']]))]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--control',type=Path,required=True)
    parser.add_argument('--views',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('Do not overwrite earlier replay evidence')
    control,inputs,control_path=load(args.control);views,other,view_path=load(args.views)
    if inputs!=other:raise ValueError('Cannot replay different inputs')
    spec=control['spec']
    for key in ['features','classes','id','target','prediction_type']:
        if spec.get(key)!=views['spec'].get(key):raise ValueError('Task/class alignment mismatch')
    train=read_input_table(spec['paths']['train']);loaded={};artifacts={}
    def cache(record):
        directory=Path(record['submission']).resolve().parent
        if not any(directory.is_relative_to(p.parent) for p in [control_path,view_path]):
            raise ValueError('Record escapes known frozen report directories')
        if str(directory) not in loaded:
            value=read_cache(spec,record,train)
            for key in ['validation','test']:
                matrix=value[key]
                if not np.isfinite(matrix).all() or (matrix<0).any() or not np.allclose(matrix.sum(axis=1),1.,atol=1e-6):
                    raise ValueError('Invalid cached probabilities')
            loaded[str(directory)]=value
            for name in ['validation_probabilities.npz','test_probabilities.npz','validation_predictions.csv']:
                p=directory/name;artifacts[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
        return loaded[str(directory)]
    pool={}
    for record in control['confirmations']+views['confirmations']:
        if record['status']!='ok':continue
        key=signature(record['recipe'])
        if key in pool:
            a,b=cache(pool[key]),cache(record)
            if not all(np.array_equal(a[k],b[k]) for k in ['rows','truth','validation','test']):
                raise ValueError('Same-recipe confirmation replicas disagree')
        else:pool[key]=record
    base=replay(spec,control['experiments'],pool,cache)
    actual=replay(spec,views['experiments'],pool,cache)
    for value,report in [(base,control),(actual,views)]:
        if value['status']!='ok' or not np.allclose([value[k] for k in ['search','confirmation','mean']],expected(report),rtol=0,atol=1e-14):
            raise ValueError('Replay failed to reproduce actual selection/blend procedure')
    ordinary=control['experiments']
    if len(ordinary)!=12 or any(r['recipe'].get('params',{}).get('feature_views') for r in ordinary):
        raise ValueError('Expected exact12ordinary baseline records')
    strong=ordinary[1]['recipe']
    fixed=dict(strong,params=dict(strong['params'],feature_views='categorical_te_pair'))
    matches=[r for r in views['experiments'] if signature(r['recipe'])==signature(fixed)]
    if len(matches)!=1:raise ValueError('Expected the predeclared fixed view, not posthoc best variant')
    proposal=replay(spec,ordinary[:2]+matches+ordinary[2:],pool,cache)
    gate={}
    if proposal['status']=='ok':
        gate={k:proposal[k]>base[k] for k in ['search','confirmation']}
        if all(actual[k]>base[k] for k in ['search','confirmation']):
            gate.update({f'preserves_v11_{k}':proposal[k]>=actual[k] for k in ['search','confirmation','mean']})
    result={'scope':'FIT-FREE hypothetical fixed13trial replay, reused public data; not actual new runtime or private score',
        'baseline_replay':base,'v11_replay':actual,'proposal':proposal,'checks':gate,
        'recommendation':'needs_fit' if proposal['status']!='ok' else 'eligible_for_implementation_only' if all(gate.values()) else 'reject_without_fits',
        'new_model_fits':0,'inputs_sha256':inputs,'cache_artifact_sha256':artifacts,
        'report_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [control_path,view_path]},
        'tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    atomic_json(args.output,result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['inputs_sha256','cache_artifact_sha256','report_sha256','tool_sha256']},indent=2))


if __name__=='__main__':main()
