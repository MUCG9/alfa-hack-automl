"""Fit a constrained decision rule on fresh inner FULL-ensemble predictions."""
from pathlib import Path
import argparse
import fcntl
import hashlib
import importlib
import json
import os
import signal
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tools'))
os.environ.setdefault('AUTOML_THREADS','2')
import numpy as np
import pandas as pd
import psutil
from sklearn.metrics import f1_score
from automl.infrastructure.atomic import atomic_json
from automl.search.hpo import nested_partition
from build_submission import build_files
from benchmark_marginal_hpo import worker_closure
from summarize_research import Verifier,digest,paired_gate
from verify_marginal_hpo import load
from verify_profile_campaign import same_recipe
from replay_blend01 import aligned_probabilities
from joint_decision import fit_factors,GRIDS

BASE=ROOT/'test-runs/qwen-optuna-20261022/pipe02-20261023'
CAMPAIGN=BASE/'campaign.json'
CONTROL_REPORT=BASE/'task-01/automl_runs/pipe02/report.json'


def run(output,plan_path,deadline_epoch=None):
    start=time.monotonic();remaining=3000 if deadline_epoch is None else min(3000,deadline_epoch-time.time())
    if remaining<=60:raise ValueError('Original common deadline leaves no verification reserve')
    deadline=start+remaining
    plan=json.loads(plan_path.read_text())
    if not json.loads((plan_path.parent/'scientific-audit.json').read_text()).get('accepted'):raise ValueError('Scientific audit missing')
    operation=plan['operation_id']
    if plan['grid']!=GRIDS.get(operation) or plan['comparison_control']!='PIPE02_COMPLETE' or plan['fit_control']!='COMPLETE_CLASS_CONTROL_INNER':raise ValueError('Decision procedure contract differs')
    campaign=json.loads(CAMPAIGN.read_text());old=json.loads(CONTROL_REPORT.read_text());spec=old['spec']
    task=next(t for t in campaign['tasks'] if t['kind']=='classification')
    inputs={n:v for n,v in task['input_sha256'].items() if n!='task'}
    if campaign['status']!='completed' or not task['complete']:raise ValueError('Reference incomplete')
    historical=Verifier({'spec':spec,'source_sha256':campaign['source_sha256'],'input_sha256':inputs},CONTROL_REPORT.parent.parents[1])
    files=build_files();source=output/'sources';source.mkdir()
    for n,b in files.items():(source/n).write_bytes(b)
    hashes_source={n:hashlib.sha256(b).hexdigest() for n,b in files.items()};closure=worker_closure(files)
    if any(campaign['source_sha256'].get(n)!=hashes_source[n] for n in closure):raise ValueError('Historical training worker changed')
    control=old['profile_controls'][0]['recipe'];qualified=json.loads((ROOT/'docs/experiments/blend01_candidates_20261023.json').read_text())[0]['recipe']
    if not all(same_recipe(r['recipe'],qualified) for r in old['profile_controls']):raise ValueError('Not the complete qualified control')
    harness=['benchmark_joint_calibration.py','joint_decision.py','verify_joint_calibration.py','summarize_research.py','verify_marginal_hpo.py','verify_profile_campaign.py','replay_blend01.py','build_submission.py']
    m={'status':'running','spec':spec,'source_sha256':hashes_source,'input_sha256':inputs,'worker_dependency_parity':closure,
        'harness_sha256':{n:digest(ROOT/'tools'/n) for n in harness},'protocol_sha256':digest(ROOT/'docs/experiments/round06_protocol_20261023.md'),
        'plan_path':str(plan_path),'plan_sha256':digest(plan_path),'campaign_sha256':digest(CAMPAIGN),'control_report_sha256':digest(CONTROL_REPORT),
        'operation_id':operation,'grid':GRIDS[operation],'comparison_control':'PIPE02_COMPLETE','control_recipe':control,
        'identity':{'pid':os.getpid(),'create_time':psutil.Process().create_time()},'limits':{'total_seconds':3000,'worker_seconds':900,'threads':2,'memory_mib_worker_and_parent':1536,'maximum_new_complete_control_workers':2,
            'original_deadline_epoch':deadline_epoch,'remaining_seconds_at_start':remaining},
        'scope':'Global ensemble decision-rule screen with fresh inner ensemble fitting; reused-public outer controls, not private/official score','cuts':[]}
    path=output/'results.json';atomic_json(path,m);v=Verifier(m,source);train=v.train;classes=spec['classes'];truth=train[spec['target']].astype(str).to_numpy()
    sys.path.insert(0,str(source));frozen=importlib.import_module('automl_runner')
    if Path(frozen.__file__).resolve()!=source/'automl_runner.py' or frozen.THREADS!=2 or Path(frozen.worker_entrypoint()).resolve()!=source/'automl_worker.py':raise ValueError('Incorrect frozen runner/worker')
    expected=json.loads((ROOT/'release/qwen-incumbent-mix1/full-procedure.json').read_text());expected=next(t for t in expected['tasks'] if t['kind']=='classification')
    try:
        for cut in range(2):
            if deadline-time.monotonic()<70:m['status']='budget_exhausted';break
            where=output/f'cut-{cut}';where.mkdir()
            original_split=CONTROL_REPORT.parent/('split.npz' if cut==0 else 'confirmation_split.npz');outer=v.split(original_split)
            np.savez(where/'outer-split.npz',train=outer[0],validation=outer[1])
            reference=old['profile_controls'][cut];origin=Path(reference['submission']).parent
            _,checked=load(v,origin,outer,reference['recipe']);outer_probs=aligned_probabilities(origin,outer[1],classes)
            if not np.isclose(checked['value'],expected['cuts'][cut]['control']['value'],atol=1e-12,rtol=1e-12):raise ValueError('Qualified control score differs')
            tr,va,info=nested_partition(spec,train,v.hashes,outer[0],seed=137)
            np.savez(where/'inner-split.npz',train=tr,validation=va)
            row={'cut':cut,'control_origin':str(origin),'control':checked,'inner_split':info};m['cuts'].append(row);atomic_json(path,m)
            tick=time.monotonic();remaining=min(900,deadline-time.monotonic()-60)
            if remaining<1:raise RuntimeError('Common deadline before complete inner worker')
            record=frozen.run_worker(spec,control,where/'inner-control',where/'inner-split.npz',remaining,memory_limit=1536*2**20)
            row['inner_execution']={'status':record.get('status'),'seconds':round(time.monotonic()-tick,3),'peak_worker_and_parent_mib':record.get('observed_total_peak_mb')}
            atomic_json(path,m)
            if record.get('status')!='ok':raise RuntimeError('Complete inner control worker failed')
            _,row['inner_control']=load(v,where/'inner-control',(tr,va),control)
            inner_probs=aligned_probabilities(where/'inner-control',va,classes)
            selection=fit_factors(truth[va],inner_probs,classes,v.support(tr),operation);atomic_json(where/'selection.json',selection)
            factors=np.asarray([selection['factors'][c] for c in classes]);candidate_probs=outer_probs*factors;candidate_probs/=candidate_probs.sum(axis=1,keepdims=True)
            labels=np.asarray(classes)[candidate_probs.argmax(axis=1)];per_class=f1_score(truth[outer[1]],labels,labels=classes,average=None,zero_division=0)
            metrics={'macro_f1':float(per_class.mean()),'per_class_f1':dict(zip(classes,map(float,per_class)))}
            candidate=where/'outer-candidate';candidate.mkdir()
            pd.DataFrame({'row_position':outer[1],'y_true':truth[outer[1]],'y_pred':labels}).to_csv(candidate/'validation_predictions.csv',index=False)
            np.savez_compressed(candidate/'validation_probabilities.npz',row_position=outer[1],classes=np.asarray(classes),probabilities=candidate_probs)
            derived={'status':'ok','metrics':metrics,'full_fit':False,'new_model_fit':False,'derived_from_outer_control':str(origin),
                'selection_path':str(where/'selection.json'),'fitting_only_calibration':True,'operation_id':operation}
            atomic_json(candidate/'result.json',derived)
            measured={'value':metrics['macro_f1'],'per_class_f1':metrics['per_class_f1']};gate=paired_gate(checked,measured,spec,v.support(outer[0]))
            row.update(candidate=measured,gate=gate,selection_status=selection['status'],selected_factors=selection['factors']);atomic_json(path,m)
            print(json.dumps({'cut':cut,'control_f1':checked['value'],'candidate_f1':measured['value'],'gate':gate['passed'],'selection':selection['status'],'inner_worker_seconds':row['inner_execution']['seconds']}),flush=True)
            if not gate['passed']:m['status']='rejected_futility';break
        else:m['status']='completed'
        complete=len(m['cuts'])==2 and all('candidate' in c for c in m['cuts'])
        m['summary']={'complete_screen':complete,'candidate_mean':float(np.mean([c['candidate']['value'] for c in m['cuts']])) if complete else None,
            'passed':bool(complete and all(c['gate']['passed'] for c in m['cuts']))};atomic_json(path,m)
        from verify_joint_calibration import verify
        atomic_json(output/'verification.json',verify(path));m['independent_verification_passed']=True
    except BaseException as exc:
        m.update(status='failed',exception_type=type(exc).__name__,exception_detail=str(exc)[:240]);raise
    finally:
        m.update(seconds=round(time.monotonic()-start,3),source_unchanged=hashes_source=={n:hashlib.sha256(b).hexdigest() for n,b in build_files().items()},
            inputs_unchanged=inputs=={n:digest(p) for n,p in spec['paths'].items()},harness_unchanged=m['harness_sha256']=={n:digest(ROOT/'tools'/n) for n in harness},
            plan_unchanged=m['plan_sha256']==digest(plan_path));atomic_json(path,m)
    if not all(m[k] for k in ['source_unchanged','inputs_unchanged','harness_unchanged','plan_unchanged']):raise RuntimeError('Frozen source/input/harness/plan changed')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);p.add_argument('--deadline-epoch',type=float);args=p.parse_args();output=args.output.resolve();plan=args.plan.resolve()
    if not all(p.is_relative_to(ROOT/'test-runs') for p in [output,plan]):raise ValueError('Keep raw artifacts ignored')
    def interrupted(signum,frame):raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM,interrupted)
    with (ROOT/'test-runs/.owned-research.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);output.mkdir(parents=True,exist_ok=False)
        lock.seek(0);lock.truncate();json.dump({'pid':os.getpid(),'create_time':psutil.Process().create_time()},lock);lock.flush()
        run(output,plan,args.deadline_epoch)


if __name__=='__main__':main()
