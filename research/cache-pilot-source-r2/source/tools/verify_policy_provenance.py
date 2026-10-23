"""Audit saved parent-row artifacts against ORIGINAL search folds, without refitting."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--benchmark',type=Path,required=True); parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); value=json.loads(args.benchmark.read_text())
    rows=value if isinstance(value,list) else value.get('results',value.get('fixed_recipe_cases',[]))
    checked=[]; missing=[]
    for case in rows:
        root=Path(case['output_dir']).resolve()
        job=json.loads((root/'job.json').read_text())
        if job.get('full_fit'): raise ValueError('This audit expects search/confirmation cases, not full refit')
        split=np.load(job['split_path']); fitting=set(split['train'].tolist()); validation=set(split['validation'].tolist())
        result=json.loads((root/'result.json').read_text())
        for index,meta in enumerate(result.get('data_policy_runs',[])):
            if not meta.get('parent_rows_artifact'):
                policy=meta.get('policy',{})
                if policy.get('sampling','identity')!='identity' or policy.get('augmentation','noop')!='noop' or policy.get('duplicate_beta',0) or policy.get('class_weight_cap') is not None:
                    missing.append({'variant':case['variant'],'seed':case['seed'],'fit':index,'reason':'Earlier exploratory worker saved hashes only'})
                continue
            path=Path(meta['parent_rows_artifact']).resolve()
            if not path.is_relative_to(root): raise ValueError('Parent artifact escapes experiment directory')
            parents=np.load(path)['parent_rows']; actual=set(parents.tolist())
            if not actual<=fitting or actual&validation: raise ValueError('Foreign or validation parent in fitting data')
            digest=hashlib.sha256(json.dumps(parents.tolist(),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
            if digest!=meta['output_parent_sha256'] or len(parents)!=meta['output_rows']: raise ValueError('Parent artifact hash/length mismatch')
            checked.append({'variant':case['variant'],'seed':case['seed'],'fit':index,'output_rows':len(parents),
                            'validation_overlap':0,'parent_sha256':digest})
    proof={'passed':bool(checked) and not missing,'checked_artifacts_valid':bool(checked),'complete_coverage':not missing,
           'checked_fit_artifacts':len(checked),'missing_parent_artifacts':missing,'checks':checked,
           'scope':'Saved public search folds; verifies outer-fold lineage, not label-preservation semantics or private generalization'}
    args.output.write_text(json.dumps(proof,indent=2))
    print(json.dumps({k:v for k,v in proof.items() if k!='checks'}))
    if not proof['passed']: raise SystemExit(1)

if __name__=='__main__': main()
