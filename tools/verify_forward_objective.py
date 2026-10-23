"""Artifact-only independent audit of multi-period marginal search and cache lineage."""
from pathlib import Path
import hashlib
import json
import numpy as np
from summarize_research import Verifier,digest
from verify_marginal_hpo import load,close
from verify_reg_blend_cv import verify as verify_reference

ROOT=Path(__file__).resolve().parents[1]


def verify(path):
    path=Path(path);m=json.loads(path.read_text());v=Verifier(m,path.parent/'sources')
    if not v.source_matches_current or m['comparison_control']!='PIPE02_COMPLETE' or m['component_control']!='V16_COMPLETE':raise ValueError('Source/control differs')
    operator=m['objective_id']
    if operator not in ['FORWARD_MEAN','FORWARD_WORST']:raise ValueError('Unknown objective')
    base=ROOT/'test-runs/qwen-optuna-20261022';hpo_path=base/'overnight-20261023/regression-hpo/results.json';forward_path=base/'reg-blend01-forward-20261023/benchmark/results.json'
    if digest(hpo_path)!=m['old_hpo_manifest_sha256'] or digest(forward_path)!=m['reference_manifest_sha256']:raise ValueError('Reference changed')
    old=json.loads(hpo_path.read_text());forward=json.loads(forward_path.read_text());reference=verify_reference(forward_path)
    if old['input_sha256']!=m['input_sha256']:raise ValueError('Historical inputs differ')
    if any(old['source_sha256'][n]!=m['source_sha256'][n] for n in m['worker_dependency_parity']):raise ValueError('Historical training source differs')
    if digest(m['plan_path'])!=m['plan_sha256']:raise ValueError('Qwen plan changed')
    plan=json.loads(Path(m['plan_path']).read_text())
    if plan['objective_id']!=operator or plan['control_id']!=m['comparison_control'] or plan['component_id']!=m['component_control']:raise ValueError('Plan contract differs')
    control=json.loads((ROOT/'docs/experiments/reg_blend01_candidates_20261023.json').read_text())[0]['recipe']
    cache=json.loads((path.parent/'native-cache/index.json').read_text());truth=v.train[v.spec['target']].to_numpy(dtype=float)
    periods=v.train[v.spec['time_column']].to_numpy();cuts=[];logical=hits=controls_count=outer_count=objectives=0
    for row in m['cuts']:
        cut=row['cut'];where=path.parent/f'cut-{cut}';outer=v.split(where/'outer-split.npz');historical=v.split(hpo_path.parent/f'cut-{cut}/outer-split.npz')
        if not all(np.array_equal(a,b) for a,b in zip(outer,historical)):raise ValueError('Outer split differs')
        levels=np.sort(np.unique(periods[outer[0]]));expected=min(2,len(levels)-1)
        if len(row['folds'])!=expected:raise ValueError('Available period coverage differs')
        folds=[];inner_controls=[]
        for number,fold in enumerate(row['folds']):
            inner=v.split(where/f'inner-{number}.npz');tr,va=inner
            if not np.isin(np.concatenate(inner),outer[0]).all():raise ValueError('Inner fold escaped outer fitting rows')
            level=levels[-1-number]
            expected_tr=outer[0][periods[outer[0]]<level];expected_va=outer[0][periods[outer[0]]==level]
            if not np.array_equal(tr,expected_tr) or not np.array_equal(va,expected_va):raise ValueError('Saved inner period differs from declared fitting-only prefix')
            values,_=load(v,where/f'inner-control-{number}',inner,control);inner_controls.append(values);folds.append(inner);controls_count+=1
        c_outer,_=load(v,next(r['directory'] for r in forward['results'] if r['seed']==cut),outer,control)
        a_old,_=load(v,hpo_path.parent/f'cut-{cut}/outer-tpe',outer,old['cuts'][cut]['tpe']['selected_recipe'])
        strong=float(np.sqrt(np.mean((truth[outer[1]]-(.9*c_outer+.1*a_old))**2)));close(strong,row['PIPE02_rmse']);close(strong,reference['cuts'][cut]['blend_rmse'])
        checked_row={'cut':cut,'inner_periods':len(folds),'PIPE02_rmse':strong,'studies':{},'outer':{}}
        for sampler in ['random','tpe']:
            study=json.loads((where/sampler/'hpo.json').read_text())
            if study!=row['studies'][sampler] or study['objective_contract']!=operator:raise ValueError('Study ledger copies/contract differ')
            if study['seed']!=137 or study['startup_trials']!=3 or study['maximum_trials']!=8 or study['sampler']!=sampler or study['control_recipe']!=old['control_recipe']:
                raise ValueError('Study parameter/budget contract differs')
            primary=v.split(where/sampler/'split.npz')
            if not all(np.array_equal(a,b) for a,b in zip(primary,folds[0])):raise ValueError('Primary study fold differs')
            values=[];local_hits=0
            for trial in study['trials']:
                if trial.get('value') is None:continue
                directory=where/sampler/f'trial-{trial["number"]:02d}';objective=json.loads((directory/'objective.json').read_text())
                if objective['objective_id']!=operator or objective['recipe']!=trial['recipe'] or len(objective['folds'])!=len(folds):raise ValueError('Trial objective contract differs')
                fold_values=[]
                for number,item in enumerate(objective['folds']):
                    if item['number']!=number:raise ValueError('Fold order changed')
                    inner=folds[number];pred,native=load(v,item['origin'],inner,trial['recipe']);close(native['value'],item['native_rmse'])
                    value=float(np.sqrt(np.mean((truth[inner[1]]-(.9*inner_controls[number]+.1*pred))**2)));close(value,item['mixture_rmse']);fold_values.append(value)
                    ctx=item['cache_context'];expected_rows_sha=hashlib.sha256(inner[0].astype('<i8').tobytes()+inner[1].astype('<i8').tobytes()).hexdigest()
                    if (ctx['source_sha256']!=m['source_sha256'] or ctx['input_sha256']!=m['input_sha256'] or ctx['spec']!=m['spec'] or ctx['recipe']!=trial['recipe']
                            or ctx['split_rows_sha256']!=expected_rows_sha or ctx['threads']!=2 or ctx['full_fit'] or ctx['fit_iterations'] is not None or ctx['task_sha256']!=digest(v.spec['task_path'])):
                        raise ValueError('Cache context does not describe the actual fitting job')
                    payload=json.loads(json.dumps(ctx));payload['recipe'].pop('hypothesis',None)
                    key=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
                    if key not in cache or cache[key]['origin']!=item['origin']:raise ValueError('Cache lineage differs')
                    requested=Path(item['requested_directory']);logical+=1
                    if item['cache_hit']:
                        receipt=json.loads((requested/'cache_reuse.json').read_text());hits+=1;local_hits+=1
                        if receipt['cache_key']!=key or receipt['origin']!=item['origin'] or receipt['actual_worker_launched'] or (requested/'job.json').exists():raise ValueError('Hit incorrectly describes a new fit')
                    elif str(requested)!=item['origin']:raise ValueError('Cache miss must train in requested directory')
                    if number==0:
                        iterations=json.loads((Path(item['origin'])/'result.json').read_text())['fit_iterations']
                        if iterations!=trial['fit_iterations'] or iterations!=objective['latest_fold_iterations']:raise ValueError('Latest-fold iteration provenance differs')
                aggregate=float(np.mean(fold_values)) if operator=='FORWARD_MEAN' else float(np.max(fold_values))
                close(aggregate,objective['value']);close(aggregate,trial['value']);values.append((aggregate,trial['recipe']));objectives+=1
            if len(values)!=8 or len(values)!=study['completed_trials']:raise ValueError('Expected eight successful aggregate objectives')
            best=min(values,key=lambda item:item[0]);close(best[0],study['best_inner_value'])
            if best[1]!=study['selected_recipe']:raise ValueError('Selected recipe does not minimize declared aggregate')
            pred,native=load(v,where/f'outer-{sampler}',outer,best[1]);outer_count+=1
            value=float(np.sqrt(np.mean((truth[outer[1]]-(.9*c_outer+.1*pred))**2)));close(value,row['outer'][sampler]['mixture_rmse'])
            checked_row['studies'][sampler]={'completed_trials':len(values),'successful_after_startup':5,'fold_native_requests':len(values)*len(folds),'cache_hits':local_hits,'best_inner_aggregate':best[0],'seconds':study['seconds']}
            checked_row['outer'][sampler]={'native_rmse':native['value'],'mixture_rmse':value,'gain':strong-value}
        checked_row['improved_PIPE02']=checked_row['outer']['tpe']['mixture_rmse']<strong
        if checked_row['improved_PIPE02']!=row['improved_PIPE02']:raise ValueError('Cut gate differs')
        cuts.append(checked_row)
    for entry in cache.values():
        origin=Path(entry['origin']);actual={str(p.relative_to(origin)):digest(p) for p in origin.rglob('*') if p.is_file()}
        if actual!=entry['artifacts']:raise ValueError('Successful cached origin artifacts changed')
    expected_launches=controls_count+logical-hits+outer_count
    if len(m['worker_launches'])!=expected_launches or len({(r['pid'],r['create_time']) for r in m['worker_launches']})!=expected_launches:raise ValueError('Logical/physical worker counts differ')
    complete=len(cuts)==3 and [c['cut'] for c in cuts]==[0,1,2]
    mean={name:float(np.mean([r['outer'][name]['mixture_rmse'] for r in cuts])) for name in ['random','tpe']} if complete else None
    summary={'complete_screen':complete,'mean':mean,'passed':bool(complete and all(r['improved_PIPE02'] for r in cuts) and mean['tpe']<mean['random'])}
    if summary!=m['summary']:raise ValueError('Invalid completion/mean/gate')
    if m['status']=='rejected_futility' and (not cuts or cuts[-1]['improved_PIPE02']):raise ValueError('Unsupported futility stop')
    return {'status':'verified','objective_id':operator,'cuts':cuts,'summary':summary,'aggregate_objectives':objectives,
        'logical_native_trial_requests':logical,'cache_hits':hits,'actual_native_trial_fits':logical-hits,
        'control_fits':controls_count,'outer_fits':outer_count,'total_worker_launches':expected_launches,
        'source_sha256':m['source_sha256'],'input_sha256':m['input_sha256'],'verifier_sha256':digest(__file__),
        'qualified_release_changed':False,'official_submission':False}
