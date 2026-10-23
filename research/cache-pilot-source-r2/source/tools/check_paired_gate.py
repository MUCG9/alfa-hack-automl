"""Verify predeclared paired MacroF1 direction/support gates from saved workers."""
from pathlib import Path
import argparse,hashlib,json,sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.tables import read_input_table
from automl.evaluation.api import evaluate


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--results',type=Path,required=True)
    parser.add_argument('--control',required=True);parser.add_argument('--candidate',required=True)
    parser.add_argument('--min-fitting-groups',type=int,default=100)
    parser.add_argument('--max-class-drop',type=float,default=.01)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=args.results.resolve().parent
    if args.output.exists():raise ValueError('Do not overwrite gate evidence')
    if args.min_fitting_groups<1 or not 0<=args.max_class_drop<=1:raise ValueError('Invalid gate thresholds')
    manifest=json.loads(args.results.read_text());spec=manifest['spec']
    if spec['kind']!='classification' or spec['metric']!='macro_f1':raise ValueError('MacroF1 only')
    for role,location in spec['paths'].items():
        if hashlib.sha256(Path(location).read_bytes()).hexdigest()!=manifest['inputs'][role]:
            raise ValueError('Original input changed')
    train=read_input_table(spec['paths']['train']);truth=train[spec['target']].astype(str).to_numpy()
    hashes=pd.util.hash_pandas_object(train[spec['features']],index=False).to_numpy(dtype='uint64')
    indexed={}
    for item in manifest['results']:
        key=(item['name'],item['seed'])
        if key in indexed:raise ValueError('Duplicate result key')
        indexed[key]=item
    seeds=sorted({seed for name,seed in indexed if name==args.control})
    if len(seeds)<2 or {seed for name,seed in indexed if name==args.candidate}!=set(seeds):
        raise ValueError('Incomplete paired runs')
    folds=[]
    def verified(item):
        if item['status']!='ok' or item.get('exit_code')!=0:raise ValueError('Worker failed')
        folder=Path(item['directory']).resolve()
        if not folder.is_relative_to(root):raise ValueError('Worker artifact escapes result root')
        split=np.load(folder/'split.npz');tr,va=split['train'],split['validation']
        if set(tr)&set(va) or set(hashes[tr])&set(hashes[va]):raise ValueError('Split leakage')
        values=pd.read_csv(folder/'validation_predictions.csv')
        stored=np.load(folder/'validation_probabilities.npz')
        if not np.array_equal(values.row_position,va) or not np.array_equal(stored['row_position'],va):
            raise ValueError('Validation row mismatch')
        order=[list(stored['classes'].astype(str)).index(c) for c in spec['classes']]
        probabilities=stored['probabilities'][:,order]
        predicted=np.asarray(spec['classes'])[probabilities.argmax(axis=1)]
        if not np.isfinite(probabilities).all() or not np.allclose(probabilities.sum(axis=1),1.,atol=1e-6):
            raise ValueError('Invalid probability matrix')
        if not np.array_equal(values.y_true.astype(str),truth[va]) or not np.array_equal(values.y_pred.astype(str),predicted):
            raise ValueError('Truth/prediction artifact mismatch')
        metrics=evaluate(truth[va],predicted,'classification','macro_f1',probabilities,spec['classes'])
        if abs(metrics['macro_f1']-item['metrics']['macro_f1'])>1e-12:raise ValueError('Stored metric does not reproduce')
        return tr,va,metrics,hashlib.sha256((folder/'split.npz').read_bytes()).hexdigest()
    for seed in seeds:
        a,b=indexed[(args.control,seed)],indexed[(args.candidate,seed)]
        tr,va,first,split_sha=verified(a);other_tr,other_va,second,other_sha=verified(b)
        if not np.array_equal(tr,other_tr) or not np.array_equal(va,other_va):raise ValueError('Paired split mismatch')
        support={c:len(np.unique(hashes[tr][truth[tr]==c])) for c in spec['classes']}
        supported=[c for c in spec['classes'] if support[c]>=args.min_fitting_groups]
        deltas={c:second['per_class_f1'][c]-first['per_class_f1'][c] for c in spec['classes']}
        folds.append({'seed':seed,'control_f1':first['macro_f1'],'candidate_f1':second['macro_f1'],
            'delta':second['macro_f1']-first['macro_f1'],'fitting_independent_feature_groups':support,
            'supported_classes':supported,'per_class_f1_delta':deltas,
            'supported_class_gate':all(deltas[c]>=-args.max_class_drop for c in supported),
            'split_file_sha256':{'control':split_sha,'candidate':other_sha}})
    checks={'all_cuts_improve':all(r['delta']>0 for r in folds),
        'mean_improves':float(np.mean([r['delta'] for r in folds]))>0,
        'supported_class_drop_within_bound':all(r['supported_class_gate'] for r in folds)}
    result={'scope':'Verified paired reused-public MacroF1 screen, not pooled overlapping OOF/private/official score',
        'control':args.control,'candidate':args.candidate,'folds':folds,
        'mean_control':float(np.mean([r['control_f1'] for r in folds])),
        'mean_candidate':float(np.mean([r['candidate_f1'] for r in folds])),
        'checks':checks,'gate_passed':all(checks.values()),
        'min_fitting_groups':args.min_fitting_groups,'max_class_drop':args.max_class_drop,
        'manifest_sha256':hashlib.sha256(args.results.read_bytes()).hexdigest(),
        'tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    atomic_json(args.output,result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['folds']},indent=2))


if __name__=='__main__':main()
