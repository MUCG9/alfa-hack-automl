"""Independent artifact audit of fitting-only joint class factors and every trial."""
from pathlib import Path
import hashlib
import json
import numpy as np
from sklearn.metrics import f1_score
from summarize_research import Verifier,digest,verify_predictions,paired_gate
from verify_marginal_hpo import load,close
from verify_profile_campaign import same_recipe
from replay_blend01 import aligned_probabilities

ROOT=Path(__file__).resolve().parents[1]


def fitting_leaves(record,rows):
    if record.get('status')!='ok' or record.get('full_fit'):raise ValueError('Expected successful validation worker')
    if record.get('components'):return sum(fitting_leaves(child,rows) for child in record['components'])
    runs=record.get('data_policy_runs') or []
    expected=hashlib.sha256(json.dumps(np.asarray(rows).tolist(),sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    if not runs or runs[-1]['source_rows']!=len(rows) or runs[-1]['source_parent_sha256']!=expected:
        raise ValueError('A leaf fitted different rows from the inner training prefix')
    return 1


def measured(truth,probs,classes):
    values=f1_score(truth,np.asarray(classes)[probs.argmax(axis=1)],labels=classes,average=None,zero_division=0)
    return {'value':float(values.mean()),'per_class_f1':dict(zip(classes,map(float,values)))}


def audit_selection(selection,truth,probs,classes,support,spec,grid):
    if selection['classes']!=classes or selection['grid']!=grid or selection['independent_inner_fitting_groups']!=support or selection['calibration_rows']!=len(truth):raise ValueError('Calibration input/schema/support differs')
    base=measured(truth,probs,classes);state=np.ones(len(classes));objective=base['value'];steps=selection['history']
    for c in classes:close(base['per_class_f1'][c],selection['baseline_per_class_f1'][c])
    if len(steps) not in [len(classes),2*len(classes)]:raise ValueError('Unexpected coordinate pass count')
    rare=min(classes,key=lambda c:support[c])
    for n,step in enumerate(steps):
        column=n%len(classes)
        if step['pass']!=n//len(classes) or step['column']!=classes[column] or step['starting_factors']!=state.tolist() or len(step['candidates'])!=len(grid):raise ValueError('Coordinate schedule/state changed')
        chosen=state.copy();chosen_objective=objective
        for value,trial in zip(grid,step['candidates']):
            if trial['factor']!=value:raise ValueError('Undeclared class multiplier')
            factors=state.copy();factors[column]=value;score=measured(truth,probs*factors,classes)
            actual=float(score['value']-.004*np.square(np.log(factors)).mean());close(actual,trial['objective'])
            for c in classes:close(score['per_class_f1'][c],trial['per_class_f1'][c])
            gate=paired_gate(base,score,spec,support)
            if gate['passed']!=trial['gate']['passed'] or trial['gate']['rarest_position']!=classes.index(rare):raise ValueError('Inner class-safety gate differs')
            close(gate['oriented_gain'],trial['gate']['oriented_gain']);close(gate['gain_without_rarest_class'],trial['gate']['gain_without_rarest'])
            if gate['passed'] and actual>chosen_objective:chosen=factors;chosen_objective=actual
        if chosen_objective>objective+.0005:state=chosen;objective=chosen_objective
        if step['selected_factors']!=state.tolist():raise ValueError('Factors did not follow maximum safe objective')
        close(objective,step['selected_objective'])
    expected=np.asarray([selection['factors'][c] for c in classes])
    if not np.array_equal(state,expected) or any(v not in grid for v in state):raise ValueError('Final factors changed or left bounds')
    close(objective,selection['regularized_inner_value']);selected=measured(truth,probs*state,classes)
    for c in classes:close(selected['per_class_f1'][c],selection['selected_per_class_f1'][c])
    status='identity' if np.array_equal(state,np.ones(len(classes))) else 'learned'
    if selection['status']!=status:raise ValueError('Identity/learned status differs')
    return {'status':'verified','coordinate_steps':len(steps),'objective_evaluations':len(steps)*len(grid),
        'baseline_f1':base['value'],'selected_f1':selected['value'],'factors':selection['factors'],'selection_status':status}


def verify(path):
    path=Path(path);m=json.loads(path.read_text());v=Verifier(m,path.parent/'sources')
    if not v.source_matches_current or m['comparison_control']!='PIPE02_COMPLETE':raise ValueError('Source/comparison control changed')
    base=ROOT/'test-runs/qwen-optuna-20261022/pipe02-20261023';campaign_path=base/'campaign.json';report_path=base/'task-01/automl_runs/pipe02/report.json'
    if digest(campaign_path)!=m['campaign_sha256'] or digest(report_path)!=m['control_report_sha256']:raise ValueError('Reference manifests changed')
    campaign=json.loads(campaign_path.read_text());old=json.loads(report_path.read_text());spec=v.spec;classes=spec['classes'];truth=v.train[spec['target']].astype(str).to_numpy()
    task=next(t for t in campaign['tasks'] if t['kind']=='classification');inputs={k:val for k,val in task['input_sha256'].items() if k!='task'}
    Verifier({'spec':old['spec'],'source_sha256':campaign['source_sha256'],'input_sha256':inputs},report_path.parent.parents[1])
    if inputs!=m['input_sha256'] or old['spec']!=spec:raise ValueError('Reference task/input differs')
    if any(campaign['source_sha256'][n]!=m['source_sha256'][n] for n in m['worker_dependency_parity']):raise ValueError('Historical training dependency differs')
    if digest(m['plan_path'])!=m['plan_sha256']:raise ValueError('Qwen plan changed')
    plan=json.loads(Path(m['plan_path']).read_text());grids={'JOINT_TIGHT':[.95,1.,1.05],'JOINT_NARROW':[.9,.95,1.,1.05,1.1]}
    if m['grid']!=grids.get(m['operation_id']) or plan['grid']!=m['grid'] or plan['operation_id']!=m['operation_id']:raise ValueError('Declared grid differs')
    qualified=json.loads((ROOT/'docs/experiments/blend01_candidates_20261023.json').read_text())[0]['recipe']
    if not same_recipe(m['control_recipe'],qualified):raise ValueError('Not the complete qualified control')
    cuts=[]
    for row in m['cuts']:
        cut=row['cut'];where=path.parent/f'cut-{cut}';outer=v.split(where/'outer-split.npz');inner=v.split(where/'inner-split.npz')
        historical=v.split(report_path.parent/('split.npz' if cut==0 else 'confirmation_split.npz'))
        if not all(np.array_equal(a,b) for a,b in zip(outer,historical)):raise ValueError('Outer validation partition changed')
        if not np.isin(np.concatenate(inner),outer[0]).all():raise ValueError('Inner calibration escaped outer fitting rows')
        record=old['profile_controls'][cut];origin=Path(record['submission']).parent
        if str(origin)!=row['control_origin'] or not same_recipe(record['recipe'],qualified):raise ValueError('Wrong outer control origin/recipe')
        _,control=load(v,origin,outer,record['recipe']);outer_probs=aligned_probabilities(origin,outer[1],classes)
        inner_dir=where/'inner-control';_,inner_checked=load(v,inner_dir,inner,m['control_recipe']);inner_probs=aligned_probabilities(inner_dir,inner[1],classes)
        leaves=fitting_leaves(json.loads((inner_dir/'result.json').read_text()),inner[0])
        if leaves!=5:raise ValueError('Entire five-leaf control was not refit inside inner training')
        selection=json.loads((where/'selection.json').read_text())
        learned=audit_selection(selection,truth[inner[1]],inner_probs,classes,v.support(inner[0]),spec,m['grid'])
        factors=np.asarray([selection['factors'][c] for c in classes]);expected=outer_probs*factors;expected/=expected.sum(axis=1,keepdims=True)
        directory=where/'outer-candidate';derived=json.loads((directory/'result.json').read_text())
        if derived['new_model_fit'] or derived['derived_from_outer_control']!=str(origin) or derived['selection_path']!=str(where/'selection.json'):raise ValueError('Derived decision rule provenance differs')
        actual=aligned_probabilities(directory,outer[1],classes)
        if not np.allclose(expected,actual,atol=1e-15,rtol=0):raise ValueError('Outer decision probabilities changed')
        candidate=verify_predictions(derived,directory,spec,v.train,outer[1]);gate=paired_gate(control,candidate,spec,v.support(outer[0]))
        close(control['value'],row['control']['value']);close(candidate['value'],row['candidate']['value'])
        if gate!=row['gate']:raise ValueError('Outer safety gate differs')
        cuts.append({'cut':cut,'control':control,'candidate':candidate,'gate':gate,'selection':learned,'inner_control':inner_checked,
            'inner_leaf_learners':leaves,'inner_subset_and_group_disjoint_verified':True,'outer_split_sha256':digest(where/'outer-split.npz'),'inner_split_sha256':digest(where/'inner-split.npz')})
    complete=len(cuts)==2 and [c['cut'] for c in cuts]==[0,1]
    summary={'complete_screen':complete,'candidate_mean':float(np.mean([c['candidate']['value'] for c in cuts])) if complete else None,
        'passed':bool(complete and all(c['gate']['passed'] for c in cuts))}
    if summary!=m['summary']:raise ValueError('Invalid completeness/mean/gates')
    if m['status']=='rejected_futility' and (not cuts or cuts[-1]['gate']['passed']):raise ValueError('Unsupported futility stop')
    return {'status':'verified','operation_id':m['operation_id'],'cuts':cuts,'summary':summary,'new_complete_inner_workers':len(cuts),
        'coverage':'reused public hash holdouts, not exactly-once OOF; grouped procedure CV required for advancement',
        'source_sha256':m['source_sha256'],'input_sha256':m['input_sha256'],'verifier_sha256':digest(__file__),
        'qualified_release_changed':False,'official_submission':False}
