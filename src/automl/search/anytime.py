"""Opt-in deadline search; retain a trained baseline until final refit succeeds."""
from copy import copy
from pathlib import Path
import hashlib
import itertools
import math
import time
import numpy as np
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.run_budget import constrain_deadline,budget_metadata
from automl.search.runner import (discover,source_files,file_fingerprints,solve_single,
    median_iterations,planner_context,llm_plan,run_worker,ordered,journal)
from automl.search.policy import signature,fallback
from automl.execution.api import read_cache,combine,materialize
from automl.publishing.api import checkpoint


def baseline_budget(total,reserve):
    if (not isinstance(total,(int,float)) or not math.isfinite(total)
            or not isinstance(reserve,(int,float)) or not math.isfinite(reserve)
            or reserve<10 or total<=reserve+60):
        raise ValueError('Anytime budget must exceed its finite reserve plus60seconds; reserve>=10')
    return max(1,int(min(total/2,total-reserve-30)))


def better(first,second,spec):
    return first>second if spec['greater_is_better'] else first<second


def eligible(search,confirmation,incumbent,floor,spec):
    if not all(math.isfinite(v) for v in [search,confirmation]):return False
    score=(search+confirmation)/2
    return (better(score,incumbent['mean'],spec)
            and not better(floor['search'],search,spec)
            and not better(floor['confirmation'],confirmation,spec))


def pair(primary,confirmation,spec):
    metric=spec['metric']
    return {'primary':primary,'confirmation_record':confirmation,
            'search':primary['metrics'][metric],
            'confirmation':confirmation['metrics'][metric],
            'mean':float(np.mean([primary['metrics'][metric],confirmation['metrics'][metric]])),
            'fit_iterations':median_iterations(primary['fit_iterations'],confirmation['fit_iterations'])}


def baseline_pairs(report):
    records={signature(r['recipe']):r for r in report['experiments'] if r['status']=='ok'}
    result=[]
    for r in report['confirmations']:
        key=signature(r['recipe'])
        if r['status']=='ok' and key in records:result.append(pair(records[key],r,report['spec']))
    return result


def baseline_champion(report,pairs):
    if report.get('ensemble'):
        e=report['ensemble'];return pair(e['primary'],e['confirmation'],report['spec'])
    return next((p for p in pairs if signature(p['primary']['recipe'])==signature(report['selected_recipe'])),None)


def configurations(count):
    result=[]
    for indices in itertools.combinations(range(count),2):
        for w in [.5,.25,.75,.1,.9]:result.append((list(indices),[w,1-w]))
    if count==3:
        result.extend([([0,1,2],[1/3]*3),([0,1,2],[.5,.25,.25]),
                       ([0,1,2],[.25,.5,.25]),([0,1,2],[.25,.25,.5])])
    return result


def shortlist(pairs,spec):
    ranked=sorted(pairs,key=lambda p:p['mean'],reverse=spec['greater_is_better'])
    top=ranked[:2]
    if len(ranked)>2:
        families={p['primary']['recipe']['engine'] for p in top}
        extra=next((p for p in ranked[2:] if p['primary']['recipe']['engine'] not in families),ranked[2]) if len(families)==1 else ranked[2]
        top.append(extra)
    return top


def promote(pairs,incumbent,floor,spec,train,sample,test,runs,index,cutoff):
    """Existing fixed blend grid; never blend an ensemble as a nested component."""
    top=shortlist(pairs,spec)
    chosen=incumbent
    for p in top:
        if eligible(p['search'],p['confirmation'],chosen,floor,spec):chosen=p
    if len(top)<2 or time.monotonic()>=cutoff-5:return chosen
    try:
        a=[read_cache(spec,p['primary'],train) for p in top]
        b=[read_cache(spec,p['confirmation_record'],train) for p in top]
        winner=None
        for indices,weights in configurations(len(top)):
            if time.monotonic()>=cutoff-5:break
            x=combine(spec,[a[i] for i in indices],weights)[0][spec['metric']]
            y=combine(spec,[b[i] for i in indices],weights)[0][spec['metric']]
            if eligible(x,y,chosen,floor,spec):
                # Only the scalar threshold changes during the grid; records remain untouched.
                chosen=dict(chosen,mean=float((x+y)/2))
                winner=(indices,weights)
        if winner:
            indices,weights=winner
            primary=materialize(spec,[a[i] for i in indices],weights,runs/f'blend-{index}-search',sample,test)
            confirmation=materialize(spec,[b[i] for i in indices],weights,runs/f'blend-{index}-confirmation',sample,test)
            return pair(primary,confirmation,spec)
    except Exception as exc:
        atomic_json(runs/f'blend-{index}-failure.json',{'exception_type':type(exc).__name__})
        # Do not retain a hypothetical scalar winner when materialization failed.
        candidates=[p for p in top if eligible(p['search'],p['confirmation'],incumbent,floor,spec)]
        return sorted(candidates,key=lambda p:p['mean'],reverse=spec['greater_is_better'])[0] if candidates else incumbent
    return chosen


def solve_anytime(args,task_data=None,output_root=None):
    started=time.monotonic();deadline=constrain_deadline(started+args.time_budget)
    reserve=args.finalization_reserve;initial_seconds=baseline_budget(args.time_budget,reserve)
    cutoff=deadline-reserve
    data=discover(args.task) if task_data is None else task_data
    _,_,train,test,sample,_,_=data
    root=Path(data[0]['root']) if output_root is None else Path(output_root)
    runs=root/'automl_runs'/args.run_name
    if runs.exists() and any(runs.iterdir()):runs=runs.with_name(runs.name+'-'+str(time.time_ns()))
    runs.mkdir(parents=True,exist_ok=True);output=root/'submission.csv'
    atomic_json(runs/'anytime_state.json',{'phase':'baseline','wall_budget':args.time_budget,'reserve':reserve})
    initial=copy(args);initial.search_until_deadline=False;initial.time_budget=initial_seconds
    initial.max_experiments=min(12,max(1,args.max_experiments));initial.run_name=runs.name+'-baseline'
    baseline=solve_single(initial,data,output_root)
    pairs=baseline_pairs(baseline);champion=baseline_champion(baseline,pairs)
    if baseline.get('final_fit_status')!='ok' or champion is None:
        report=dict(baseline,anytime={'enabled':True,'stop_reason':'baseline_not_confirmed_and_refitted',
                                     'wall_budget':args.time_budget,'reserve':reserve})
        atomic_json(runs/'report.json',report);return report
    spec=baseline['spec'];floor=dict(champion)
    checkpoint({'submission':str(output)},runs/'baseline-full.csv')
    baseline_sha=hashlib.sha256(output.read_bytes()).hexdigest()
    baseline_runs=Path(baseline['journal_path']).parent
    split=baseline_runs/'split.npz';confirmation_split=baseline_runs/'confirmation_split.npz'
    protected={**{'input:'+k:v for k,v in spec['paths'].items()},'task':spec['task_path'],
               **{'source:'+str(p):str(p) for p in source_files()}}
    fingerprints=file_fingerprints(protected)
    atomic_json(runs/'provenance.json',{'sha256':fingerprints,'baseline_csv_sha256':baseline_sha})
    records=list(baseline['experiments']);calls=list(baseline['llm_calls']);seen={signature(r['recipe']) for r in records}
    best=ordered(records,spec)[0];queue=[];promotions=[];attempts=0;failures=0
    stop='search_deadline';final_status='preserved_trained_baseline';exported=floor

    def state(phase):
        value={'phase':phase,'elapsed_seconds':round(time.monotonic()-started,3),
               'remaining_seconds':round(max(0,deadline-time.monotonic()),3),
               'search_remaining_seconds':round(max(0,cutoff-time.monotonic()),3),
               'extended_attempts':attempts,'best_confirmed_mean':champion['mean'],
               'search':champion['search'],'confirmation':champion['confirmation'],
               'baseline_mean':floor['mean'],'baseline_csv_sha256':baseline_sha,
               'exported_csv_still_baseline':hashlib.sha256(output.read_bytes()).hexdigest()==baseline_sha}
        atomic_json(runs/'anytime_state.json',value)
        atomic_json(runs/'best_found.json',{'recipe':champion['primary']['recipe'],
                    'fit_iterations':champion['fit_iterations'],**value})
        atomic_json(runs/'progress.json',{'experiments':records,'calls':calls,'best':best,
                                         'confirmed':len(pairs),'best_confirmed_mean':champion['mean']})
    state('exploration')
    try:
        for number in range(getattr(args,'max_extended_experiments',1000)):
            if time.monotonic()>=cutoff-5:break
            index=len(baseline['experiments'])+number
            if not queue and not args.offline and len(calls)<max(0,min(args.max_planner_calls,8)) and cutoff-time.monotonic()>90:
                context=planner_context(spec,data[1],data[5],baseline['split'],records,best,
                                               cutoff-time.monotonic(),len(calls)+1)
                plans,usage=llm_plan(context,runs,timeout=min(300,max(5,cutoff-time.monotonic()-5)))
                calls.append(usage);atomic_json(runs/f'planner-{len(calls)}.json',{'plans':plans,'call':usage})
                queue.extend(p for p in plans if signature(p) not in seen)
            while queue and signature(queue[0]) in seen:queue.pop(0)
            recipe=queue.pop(0) if queue else fallback(spec,index,best['recipe'])
            if signature(recipe) in seen:continue
            seen.add(signature(recipe));attempts+=1
            result=run_worker(spec,recipe,runs/f'experiment-{index:04d}',split,min(900,max(1,cutoff-time.monotonic()-3)))
            result['experiment_index']=index;records.append(result)
            journal(runs,'extended_search',result,spec['metric'],'private_candidate_only')
            ranked=ordered(records,spec);best=ranked[0]
            if result['status']!='ok':
                failures+=1;state('exploration')
                if failures>=8:stop='consecutive_worker_failures';break
                continue
            failures=0
            top=shortlist(pairs,spec)
            threshold=top[-1]['search']
            if not better(threshold,result['metrics'][spec['metric']],spec) and cutoff-time.monotonic()>10:
                confirm=run_worker(spec,recipe,runs/f'confirmation-{index:04d}',confirmation_split,
                                          min(900,max(1,cutoff-time.monotonic()-3)))
                journal(runs,'extended_confirmation',confirm,spec['metric'],'compare_same_two_cuts')
                if confirm['status']=='ok':
                    pairs.append(pair(result,confirm,spec))
                    chosen=promote(pairs,champion,floor,spec,train,sample,test,runs,index,cutoff)
                    if better(chosen['mean'],champion['mean'],spec):
                        champion=chosen;promotions.append({'index':index,'mean':champion['mean'],
                            'search':champion['search'],'confirmation':champion['confirmation']})
            state('exploration')
        else:stop='extended_attempt_guard'
        state('finalization')
        if better(champion['mean'],floor['mean'],spec) and deadline-time.monotonic()>30:
            final=run_worker(spec,champion['primary']['recipe'],runs/'final-fit',split,
                    max(1,deadline-time.monotonic()-30),full_fit=True,fit_iterations=champion['fit_iterations'])
            final_status=final['status']
            journal(runs,'anytime_full_refit',final,spec['metric'],'export' if final_status=='ok' else 'preserve_trained_baseline')
            if final_status=='ok':checkpoint(final,output);exported=champion
        integrity=file_fingerprints(protected)==fingerprints
        report={'version':'long-01-anytime','spec':spec,'split':baseline['split'],'experiments':records,
                'llm_calls':calls,'baseline_report':str(baseline_runs/'report.json'),
                'baseline':{'mean':floor['mean'],'search':floor['search'],'confirmation':floor['confirmation'],
                            'submission_sha256':baseline_sha},
                'best_validation':exported['primary']['metrics'],'selected_recipe':exported['primary']['recipe'],
                'final_fit_iterations':exported['fit_iterations'],'final_fit_status':final_status,
                'exported_full_fit_ok':True,'exported_mean':exported['mean'],
                'best_observed_mean':champion['mean'],'best_observed_recipe':champion['primary']['recipe'],
                'confirmation_metric':exported['confirmation'],'promotions':promotions,
                'anytime':{'wall_budget':args.time_budget,'finalization_reserve':reserve,'extended_attempts':attempts,
                           'stop_reason':stop,'legacy_baseline_trials':len(baseline['experiments'])},
                'elapsed_seconds':round(time.monotonic()-started,3),'submission_path':str(output),
                'submission_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'integrity_ok':integrity,
                'provenance_path':str(runs/'provenance.json'),
                'score_scope':'Adaptive reused-public search and confirmation; not independent/private/platform score',
                **budget_metadata()}
        atomic_json(runs/'report.json',report);state('completed')
        if not integrity:raise RuntimeError('Inputs or code changed during anytime search')
        return report
    except BaseException as exc:
        state('interrupted' if isinstance(exc,(SystemExit,KeyboardInterrupt)) else 'failed')
        raise
