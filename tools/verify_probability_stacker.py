"""Artifact-only audit of fitting-only stacker provenance and numerical inference."""
from pathlib import Path
import json
import numpy as np
from summarize_research import Verifier,digest,verify_predictions,paired_gate
from verify_marginal_hpo import load,close
from verify_joint_calibration import fitting_leaves
from verify_profile_campaign import same_recipe
from replay_blend01 import aligned_probabilities
ROOT=Path(__file__).resolve().parents[1]


def matrix(directory,rows,v,references):
    record=json.loads((directory/'result.json').read_text());children=record.get('components',[])
    if len(children)!=3 or len(references)!=3:raise ValueError('Not all three global components')
    columns=[];probabilities=[]
    for i,(child,reference) in enumerate(zip(children,references)):
        where=Path(child['submission']).parent
        if where!=directory/f'component-{i}' or reference['directory']!=str(where):raise ValueError('Global component origin mismatch')
        if reference['prediction_sha256']!=digest(where/'validation_predictions.csv') or reference['probability_sha256']!=digest(where/'validation_probabilities.npz'):raise ValueError('Component artifacts changed')
        verify_predictions(child,where,v.spec,v.train,rows);p=aligned_probabilities(where,rows,v.spec['classes']);probabilities.append(p)
        columns.extend([np.log(np.clip(p[:,k],1e-6,None)) for k in range(len(v.spec['classes']))])
    if not np.allclose(np.mean(probabilities,axis=0),aligned_probabilities(directory,rows,v.spec['classes']),atol=1e-12,rtol=1e-12):raise ValueError('Complete control weights changed')
    return np.column_stack(columns)


def numerical_meta(where,truth,classes,inner_rows,outer_rows,C):
    with np.load(where/'meta-input.npz',allow_pickle=False) as d:
        X,Z,y,stored_classes,fit_rows,stored_outer=[d[k] for k in ['X','Z','y','classes','fit_rows','outer_rows']]
    if stored_classes.astype(str).tolist()!=classes or not np.array_equal(fit_rows,inner_rows) or not np.array_equal(stored_outer,outer_rows) or not np.array_equal(y,truth[inner_rows]):raise ValueError('Meta fitting labels/rows/classes differ from source')
    record=json.loads((where/'meta/result.json').read_text());expected_params={'C':C,'solver':'lbfgs','max_iter':1200,'tol':1e-4,'fit_intercept':True,'random_state':137,'class_weight':None}
    if record['status']!='ok' or any(record['parameters'][k]!=value for k,value in expected_params.items()) or record['C']!=C or record['classes']!=classes or record['fit_rows']!=len(inner_rows):raise ValueError('Meta fitting policy changed')
    if record['input_sha256']!=digest(where/'meta-input.npz') or record['coefficient_sha256']!=digest(where/'meta/coefficients.npz'):raise ValueError('Meta worker provenance changed')
    counts={c:int(np.sum(truth[inner_rows]==c)) for c in classes}
    if not all(counts.values()) or record['class_counts']!=counts:raise ValueError('Meta class coverage/count differs')
    expected_weight=np.array([1/np.sqrt(counts[c]) for c in truth[inner_rows]]);expected_weight/=expected_weight.mean()
    with np.load(where/'meta/coefficients.npz',allow_pickle=False) as d:coef,intercept,model_classes,saved_weights,saved_rows=[d[k] for k in ['coef','intercept','model_classes','sample_weight','fit_rows']]
    model_classes=model_classes.astype(str).tolist()
    if len(set(model_classes))!=len(classes) or set(model_classes)!=set(classes) or coef.shape!=(len(classes),3*len(classes)) or intercept.shape!=(len(classes),):raise ValueError('Coefficient schema differs')
    if not np.isfinite(coef).all() or not np.isfinite(intercept).all() or not np.array_equal(saved_rows,inner_rows) or not np.allclose(saved_weights,expected_weight,atol=1e-12,rtol=1e-12):raise ValueError('Meta fitting weights/rows/coefficients invalid')
    logits=Z@coef.T+intercept;logits-=logits.max(axis=1,keepdims=True);p=np.exp(logits);p/=p.sum(axis=1,keepdims=True);p=p[:,[model_classes.index(c) for c in classes]]
    with np.load(where/'meta/meta_probabilities.npz',allow_pickle=False) as d:
        if not np.array_equal(d['row_position'],outer_rows) or d['classes'].astype(str).tolist()!=classes or not np.allclose(d['probabilities'],p,atol=1e-10,rtol=1e-10):raise ValueError('Saved meta probabilities differ from independent softmax')
    return X,Z,p,{'status':'verified','fitting_rows':len(inner_rows),'features':X.shape[1],'coefficient_sha256':record['coefficient_sha256'],'class_counts':counts,'iterations':record['iterations'],'sample_weight_fitting_only':True}


def verify(path):
    path=Path(path);m=json.loads(path.read_text());v=Verifier(m,path.parent/'sources');spec=v.spec;classes=spec['classes'];truth=v.train[spec['target']].astype(str).to_numpy()
    if not v.source_matches_current or m['comparison_control']!='COMPLETE_CLASS_CONTROL' or m['weights']!=[.9,.1]:raise ValueError('Source/comparison/base weights changed')
    for n,h in m['harness_sha256'].items():
        if digest(ROOT/'tools'/n)!=h:raise ValueError('Frozen harness changed')
    report=ROOT/'test-runs/qwen-optuna-20261022/pipe02-20261023/task-01/automl_runs/pipe02/report.json';campaign=report.parent.parents[2]/'campaign.json'
    if digest(report)!=m['control_report_sha256'] or digest(campaign)!=m['campaign_sha256']:raise ValueError('Reference manifest changed')
    old=json.loads(report.read_text());historical=json.loads(campaign.read_text());task=next(t for t in historical['tasks'] if t['kind']=='classification');inputs={k:value for k,value in task['input_sha256'].items() if k!='task'}
    Verifier({'spec':old['spec'],'source_sha256':historical['source_sha256'],'input_sha256':inputs},report.parent.parents[1])
    if old['spec']!=spec or inputs!=m['input_sha256'] or any(historical['source_sha256'][n]!=m['source_sha256'][n] for n in m['worker_dependency_parity']):raise ValueError('Historical task/worker differs')
    plan=json.loads(Path(m['plan_path']).read_text())
    if digest(m['plan_path'])!=m['plan_sha256'] or plan['operation_id']!=m['operation_id'] or plan['C']!=m['C'] or m['C']!={'LOGIT_STACK_C01':.1,'LOGIT_STACK_C1':1.}.get(m['operation_id']):raise ValueError('Chosen operator changed')
    qualified=json.loads((ROOT/'docs/experiments/blend01_candidates_20261023.json').read_text())[0]['recipe']
    if not same_recipe(m['control_recipe'],qualified):raise ValueError('Wrong complete fitting control')
    cuts=[]
    for row in m['cuts']:
        cut=row['cut'];where=path.parent/f'cut-{cut}';outer=v.split(where/'outer-split.npz');inner=v.split(where/'inner-split.npz');historical_split=v.split(report.parent/('split.npz' if cut==0 else 'confirmation_split.npz'))
        if not all(np.array_equal(a,b) for a,b in zip(outer,historical_split)) or not np.isin(np.concatenate(inner),outer[0]).all():raise ValueError('Outer/inner partition changed or escaped fitting')
        origin=Path(old['profile_controls'][cut]['submission']).parent;inner_origin=Path(row['inner_origin'])
        if row['control_origin']!=str(origin):raise ValueError('Outer control origin differs')
        _,control=load(v,origin,outer,old['profile_controls'][cut]['recipe']);_,inner_checked=load(v,inner_origin,inner,m['control_recipe'])
        if fitting_leaves(json.loads((origin/'result.json').read_text()),outer[0])!=5 or fitting_leaves(json.loads((inner_origin/'result.json').read_text()),inner[0])!=5:raise ValueError('Control fitting lineage differs')
        if cut==0:
            prior=ROOT/'test-runs/autoresearch-rounds-20261023/round06/screen-attempt2'
            if inner_origin!=prior/'cut-0/inner-control' or row['inner_execution']['new_model_fit'] or row['inner_execution']['origin_manifest_sha256']!=digest(prior/'results.json'):raise ValueError('Reused native origin misreported')
            old_split=v.split(prior/'cut-0/inner-split.npz')
            if not all(np.array_equal(a,b) for a,b in zip(inner,old_split)):raise ValueError('Reused split differs')
        elif inner_origin!=where/'inner-control' or not row['inner_execution']['new_model_fit']:raise ValueError('Missing fresh cut1 control')
        X=matrix(inner_origin,inner[1],v,row['inner_components']);Z=matrix(origin,outer[1],v,row['outer_components'])
        xx,zz,meta,meta_checked=numerical_meta(where,truth,classes,inner[1],outer[1],m['C'])
        if not np.array_equal(X,xx) or not np.array_equal(Z,zz) or row['meta_input_sha256']!=digest(where/'meta-input.npz'):raise ValueError('Fitting/inference feature matrix differs')
        expected=.9*aligned_probabilities(origin,outer[1],classes)+.1*meta;directory=where/'outer-candidate';actual=aligned_probabilities(directory,outer[1],classes)
        if not np.allclose(expected,actual,atol=1e-10,rtol=1e-10):raise ValueError('Final fixed mixture differs')
        derived=json.loads((directory/'result.json').read_text())
        if derived['weights']!=[.9,.1] or derived['control_origin']!=str(origin) or derived['meta_fit_origin']!=str(where/'meta') or derived['new_base_fit']:raise ValueError('Derived output provenance differs')
        candidate=verify_predictions(derived,directory,spec,v.train,outer[1]);gate=paired_gate(control,candidate,spec,v.support(outer[0]));close(candidate['value'],row['candidate']['value']);close(control['value'],row['control']['value'])
        if gate!=row['gate']:raise ValueError('Class gate mismatch')
        cuts.append({'cut':cut,'control':control,'candidate':candidate,'gate':gate,'meta':meta_checked,'inner_control':inner_checked,'base_fit_reused':cut==0,
            'actual_group_disjoint_inner_and_outer_verified':True,'inner_split_sha256':digest(where/'inner-split.npz'),'outer_split_sha256':digest(where/'outer-split.npz')})
    complete=len(cuts)==2 and [c['cut'] for c in cuts]==[0,1];summary={'complete_screen':complete,'mean':float(np.mean([c['candidate']['value'] for c in cuts])) if complete else None,'passed':bool(complete and all(c['gate']['passed'] for c in cuts))}
    if summary!=m['summary'] or (m['status']=='rejected_futility' and (not cuts or cuts[-1]['gate']['passed'])):raise ValueError('Invalid completeness/futility/mean')
    return {'status':'verified','operation_id':m['operation_id'],'C':m['C'],'cuts':cuts,'summary':summary,'new_complete_inner_workers':sum(c['cut']==1 for c in cuts),'new_meta_fits':len(cuts),'full_procedure_qualification':False,'official_submission':False}
