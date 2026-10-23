"""Compare fixed OOF predictions using a paired bootstrap of feature groups."""
from pathlib import Path
import argparse,hashlib,json,sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from agent_core import discover,atomic_json


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--task',type=Path,required=True)
    parser.add_argument('--results',type=Path,required=True)
    parser.add_argument('--control',required=True)
    parser.add_argument('--candidate',action='append',default=[])
    parser.add_argument('--blend-candidate',type=Path,help='Predeclared JSON {name, components: {recipe: weight}}')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--replicates',type=int,default=500)
    args=parser.parse_args()
    if args.output.exists(): raise ValueError('Use a new output path')
    if not 100<=args.replicates<=5000: raise ValueError('Use 100..5000 replicates')
    spec,_,train,_,_,_,hashes=discover(args.task)
    if spec['kind']!='classification' or spec['metric']!='macro_f1':
        raise ValueError('This comparison requires classification Macro F1')
    results=json.loads(args.results.read_text())
    actual={n:hashlib.sha256(Path(p).read_bytes()).hexdigest() for n,p in spec['paths'].items()}
    if actual!=results['inputs']: raise ValueError('Input fingerprints differ')
    blend=json.loads(args.blend_candidate.read_text()) if args.blend_candidate else None
    if not args.candidate and blend is None: raise ValueError('Provide candidates or a fixed blend')
    if blend is not None:
        weights=blend.get('components',{})
        if not isinstance(weights,dict) or not 1<=len(weights)<=3 or not isinstance(blend.get('name'),str):
            raise ValueError('A blend requires a name and 1..3 components')
        values=np.asarray(list(weights.values()),dtype=float)
        if not np.isfinite(values).all() or np.any(values<=0): raise ValueError('Invalid blend weights')
        blend['components']={k:float(v/values.sum()) for k,v in weights.items()}
        if blend['name'] in results.get('oof',{}): raise ValueError('Blend name collides with a fitted recipe')
    names=list(dict.fromkeys([args.control]+args.candidate+list(blend['components'] if blend else [])))
    classes=spec['classes']; count=len(classes)
    truth=np.asarray([classes.index(v) for v in train[spec['target']].astype(str)])
    loaded={}; reference=None
    for name in names:
        summary=results.get('oof',{}).get(name,{})
        if summary.get('coverage')!='exactly_once': raise ValueError('Incomplete OOF coverage')
        splits={r['seed']:r['split']['split_sha256'] for r in results['results'] if r['name']==name and r['status']=='ok'}
        if reference is not None and splits!=reference: raise ValueError('OOF splits differ')
        reference=splits
        with np.load(args.results.parent/name/'oof.npz') as data:
            if not np.array_equal(data['row_position'],np.arange(len(train))): raise ValueError('OOF row order differs')
            order=[list(data['classes'].astype(str)).index(c) for c in classes]
            probabilities=data['predictions'][:,order]
            if not np.isfinite(probabilities).all() or np.any(probabilities<0) or np.any(probabilities.sum(axis=1)<=0):
                raise ValueError('Invalid probabilities')
            loaded[name]=probabilities/probabilities.sum(axis=1,keepdims=True)
    _,groups=np.unique(hashes,return_inverse=True); group_count=int(groups.max())+1
    def score(predicted,weights=None):
        matrix=np.bincount(truth*count+predicted,weights=weights,minlength=count*count).reshape(count,count)
        denominator=matrix.sum(axis=0)+matrix.sum(axis=1)
        return float(np.divide(2*np.diag(matrix),denominator,out=np.zeros(count),where=denominator>0).mean())
    for name in names:
        point=score(loaded[name].argmax(axis=1))
        if not np.isclose(point,results['oof'][name]['pooled_oof']['macro_f1']): raise ValueError('Stored OOF score differs')
    comparisons_names=args.candidate.copy()
    if blend:
        loaded[blend['name']]=sum(weight*loaded[name] for name,weight in blend['components'].items())
        comparisons_names.append(blend['name'])
    predictions=[loaded[name].argmax(axis=1) for name in [args.control]+comparisons_names]
    points=np.asarray([score(p) for p in predictions])
    random=np.random.default_rng(2026); deltas=[]
    for _ in range(args.replicates):
        drawn=random.multinomial(group_count,np.full(group_count,1/group_count))
        weights=drawn[groups]; values=np.asarray([score(p,weights) for p in predictions])
        deltas.append(values[1:]-values[0])
    deltas=np.asarray(deltas)
    comparisons=[{'candidate':name,'macro_f1':float(points[i+1]),'delta':float(points[i+1]-points[0]),
                  'paired_group_bootstrap_95pct':np.percentile(deltas[:,i],[2.5,97.5]).tolist(),
                  'positive_delta_fraction':float((deltas[:,i]>0).mean())} for i,name in enumerate(comparisons_names)]
    report={'control':args.control,'control_macro_f1':float(points[0]),'comparisons':comparisons,
            'replicates':args.replicates,'seed':2026,'feature_groups':group_count,
            'results_sha256':hashlib.sha256(args.results.read_bytes()).hexdigest(),
            'fixed_blend':blend,'derived_predictions_only':bool(blend),
            'scope':'Fixed OOF predictions; conditional paired group bootstrap. Reused public data and fitted models; not a private-score interval or refit uncertainty.'}
    atomic_json(args.output,report);print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__': main()
