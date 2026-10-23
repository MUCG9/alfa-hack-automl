"""One preregistered fitting-only meta procedure, with reusable native controls."""
from pathlib import Path
import argparse,fcntl,hashlib,importlib,json,os,signal,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT/'tools'))
os.environ.setdefault('AUTOML_THREADS','2')
import numpy as np
import pandas as pd
import psutil
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.processes import ProcessTree
from automl.search.hpo import nested_partition
from build_submission import build_files
from benchmark_marginal_hpo import worker_closure
from summarize_research import Verifier,digest,verify_predictions,paired_gate
from verify_marginal_hpo import load
from verify_profile_campaign import same_recipe
from verify_joint_calibration import fitting_leaves,measured
from replay_blend01 import aligned_probabilities

BASE=ROOT/'test-runs/qwen-optuna-20261022/pipe02-20261023'
REPORT=BASE/'task-01/automl_runs/pipe02/report.json'
REUSE=ROOT/'test-runs/autoresearch-rounds-20261023/round06/screen-attempt2'


def component_matrix(directory,record,rows,spec,train):
    components=record.get('components',[])
    if len(components)!=3:raise ValueError('Expected three global components')
    arrays=[];references=[]
    for i,child in enumerate(components):
        where=Path(child['submission']).parent
        if where!=Path(directory)/f'component-{i}':raise ValueError('Global component path differs')
        verify_predictions(child,where,spec,train,rows);probs=aligned_probabilities(where,rows,spec['classes']);arrays.append(probs)
        references.append({'directory':str(where),'probability_sha256':digest(where/'validation_probabilities.npz'),'prediction_sha256':digest(where/'validation_predictions.csv')})
    native=aligned_probabilities(directory,rows,spec['classes'])
    if not np.allclose(native,np.mean(arrays,axis=0),atol=1e-12,rtol=1e-12):raise ValueError('Not the fixed equal-component ensemble')
    return np.concatenate([np.log(np.maximum(a,1e-6)) for a in arrays],axis=1),references


def meta_worker(data,where,C,seconds):
    where.mkdir();env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ['TOKEN','PASSWORD','API_KEY','SECRET','CREDENTIAL'])}
    for k in ['AUTOML_THREADS','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:env[k]='2'
    start=time.monotonic();peak=0
    with (where/'worker.log').open('w') as log:
        args=[str(ROOT/'.venv/bin/python'),str(ROOT/'tools/fit_probability_stacker.py'),'--data',str(data),'--output',str(where),'--C',str(C)]
        process=subprocess.Popen(args,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT);tree=ProcessTree(process)
        try:
            while process.poll() is None:
                tree.refresh();rss=psutil.Process().memory_info().rss
                for member in tree.members.values():
                    try:rss+=member.memory_info().rss
                    except psutil.NoSuchProcess:pass
                peak=max(peak,rss)
                if rss>1536*2**20:raise MemoryError('Meta worker+parent guard')
                if time.monotonic()-start>=seconds:raise TimeoutError('Meta fitting/common deadline')
                time.sleep(.1)
            if process.returncode:raise RuntimeError('Meta worker failed; preserve worker.log')
        finally:tree.terminate()
    return {'status':'ok','seconds':round(time.monotonic()-start,3),'peak_worker_and_parent_mib':round(peak/2**20,3),'returncode':process.returncode,'new_meta_fit':True}


def run(out,plan_path):
    start=time.monotonic();deadline=start+1800;plan=json.loads(plan_path.read_text())
    if not json.loads((plan_path.parent/'scientific-audit.json').read_text()).get('accepted'):raise ValueError('Qwen scientific audit missing')
    if plan['C']!={'LOGIT_STACK_C01':.1,'LOGIT_STACK_C1':1.}.get(plan['operation_id']) or plan['comparison_control']!='COMPLETE_CLASS_CONTROL' or plan['mixture_base']!='COMPLETE_CLASS_CONTROL':raise ValueError('Meta policy changed')
    old=json.loads(REPORT.read_text());campaign=json.loads((BASE/'campaign.json').read_text());spec=old['spec'];task=next(t for t in campaign['tasks'] if t['kind']=='classification');inputs={k:v for k,v in task['input_sha256'].items() if k!='task'}
    Verifier({'spec':spec,'source_sha256':campaign['source_sha256'],'input_sha256':inputs},REPORT.parent.parents[1])
    files=build_files();source=out/'sources';source.mkdir()
    for n,b in files.items():(source/n).write_bytes(b)
    hashes={n:hashlib.sha256(b).hexdigest() for n,b in files.items()};closure=worker_closure(files)
    if any(hashes[n]!=campaign['source_sha256'][n] for n in closure):raise ValueError('Historical worker changed')
    qualified=json.loads((ROOT/'docs/experiments/blend01_candidates_20261023.json').read_text())[0]['recipe'];control=old['profile_controls'][0]['recipe']
    if not all(same_recipe(c['recipe'],qualified) for c in old['profile_controls']):raise ValueError('Not the qualified whole class control')
    harness=['benchmark_probability_stacker.py','fit_probability_stacker.py','verify_probability_stacker.py','summarize_research.py','verify_marginal_hpo.py','verify_joint_calibration.py','verify_profile_campaign.py','replay_blend01.py','build_submission.py']
    m={'status':'running','spec':spec,'source_sha256':hashes,'input_sha256':inputs,'worker_dependency_parity':closure,'control_recipe':control,'comparison_control':'COMPLETE_CLASS_CONTROL',
        'control_report_sha256':digest(REPORT),'campaign_sha256':digest(BASE/'campaign.json'),'plan_path':str(plan_path),'plan_sha256':digest(plan_path),'C':plan['C'],'operation_id':plan['operation_id'],
        'harness_sha256':{n:digest(ROOT/'tools'/n) for n in harness},'protocol_sha256':digest(ROOT/'docs/experiments/round07_protocol_20261023.md'),
        'limits':{'total_seconds':1800,'complete_worker_seconds':900,'meta_worker_seconds':120,'worker_and_parent_mib':1536,'threads':2},
        'identity':{'pid':os.getpid(),'create_time':psutil.Process().create_time()},'weights':[.9,.1],'cuts':[]}
    path=out/'results.json';atomic_json(path,m);v=Verifier(m,source);truth=v.train[spec['target']].astype(str).to_numpy();classes=spec['classes']
    sys.path.insert(0,str(source));frozen=importlib.import_module('automl_runner')
    if Path(frozen.__file__).resolve()!=source/'automl_runner.py' or frozen.THREADS!=2:raise ValueError('Wrong frozen runner')
    try:
        for cut in range(2):
            if deadline-time.monotonic()<180:raise TimeoutError('Insufficient common verification/fitting budget')
            where=out/f'cut-{cut}';where.mkdir();outer=v.split(REPORT.parent/('split.npz' if cut==0 else 'confirmation_split.npz'))
            np.savez(where/'outer-split.npz',train=outer[0],validation=outer[1]);tr,va,info=nested_partition(spec,v.train,v.hashes,outer[0],seed=137);inner=(tr,va)
            np.savez(where/'inner-split.npz',train=tr,validation=va)
            reference=old['profile_controls'][cut];origin=Path(reference['submission']).parent;_,checked=load(v,origin,outer,reference['recipe'])
            if fitting_leaves(json.loads((origin/'result.json').read_text()),outer[0])!=5:raise ValueError('Outer complete-control lineage differs')
            row={'cut':cut,'control_origin':str(origin),'control':checked,'inner_split':info};m['cuts'].append(row);atomic_json(path,m)
            if cut==0:
                from verify_joint_calibration import verify
                verified=verify(REUSE/'results.json');reused=json.loads((REUSE/'results.json').read_text())
                if verified['status']!='verified' or reused['source_sha256']!=hashes or reused['input_sha256']!=inputs:raise ValueError('Reuse context differs')
                prior=v.split(REUSE/'cut-0/inner-split.npz')
                if not all(np.array_equal(a,b) for a,b in zip(prior,inner)):raise ValueError('Reused inner partition differs')
                inner_origin=REUSE/'cut-0/inner-control';row['inner_execution']={'status':'reused_verified','new_model_fit':False,'origin_manifest_sha256':digest(REUSE/'results.json')}
            else:
                inner_origin=where/'inner-control';tick=time.monotonic();record=frozen.run_worker(spec,control,inner_origin,where/'inner-split.npz',min(900,deadline-time.monotonic()-180),memory_limit=1536*2**20)
                row['inner_execution']={'status':record.get('status'),'seconds':round(time.monotonic()-tick,3),'peak_worker_and_parent_mib':record.get('observed_total_peak_mb'),'new_model_fit':True}
                if record.get('status')!='ok':raise RuntimeError('New complete-inner worker failed')
            row['inner_origin']=str(inner_origin);_,row['inner_checked']=load(v,inner_origin,inner,control);inner_record=json.loads((inner_origin/'result.json').read_text())
            if fitting_leaves(inner_record,tr)!=5:raise ValueError('Incomplete inner control lineage')
            X,row['inner_components']=component_matrix(inner_origin,inner_record,va,spec,v.train)
            Z,row['outer_components']=component_matrix(origin,json.loads((origin/'result.json').read_text()),outer[1],spec,v.train)
            data=where/'meta-input.npz';np.savez_compressed(data,X=X,y=np.asarray(truth[va],dtype=str),Z=Z,classes=np.asarray(classes),fit_rows=va,outer_rows=outer[1])
            row['meta_input_sha256']=digest(data);atomic_json(path,m);row['meta_execution']=meta_worker(data,where/'meta',plan['C'],min(120,deadline-time.monotonic()-60))
            with np.load(where/'meta/meta_probabilities.npz',allow_pickle=False) as a:meta=a['probabilities']
            probs=.9*aligned_probabilities(origin,outer[1],classes)+.1*meta;score=measured(truth[outer[1]],probs,classes);candidate=where/'outer-candidate';candidate.mkdir()
            pd.DataFrame({'row_position':outer[1],'y_true':truth[outer[1]],'y_pred':np.asarray(classes)[probs.argmax(axis=1)]}).to_csv(candidate/'validation_predictions.csv',index=False)
            np.savez_compressed(candidate/'validation_probabilities.npz',probabilities=probs,row_position=outer[1],classes=np.asarray(classes))
            atomic_json(candidate/'result.json',{'status':'ok','new_base_fit':False,'metrics':{'macro_f1':score['value'],'per_class_f1':score['per_class_f1']},'meta_fit_origin':str(where/'meta'),'control_origin':str(origin),'weights':[.9,.1]})
            row.update(candidate=score,gate=paired_gate(checked,score,spec,v.support(outer[0])));atomic_json(path,m)
            print(json.dumps({'cut':cut,'control':checked['value'],'candidate':score['value'],'gate':row['gate']['passed'],'new_base_fit':row['inner_execution']['new_model_fit']}),flush=True)
            if not row['gate']['passed']:m['status']='rejected_futility';break
        else:m['status']='completed'
        complete=len(m['cuts'])==2 and all('candidate' in c for c in m['cuts']);m['summary']={'complete_screen':complete,'mean':float(np.mean([r['candidate']['value'] for r in m['cuts']])) if complete else None,'passed':bool(complete and all(r['gate']['passed'] for r in m['cuts']))};atomic_json(path,m)
        from verify_probability_stacker import verify
        atomic_json(out/'verification.json',verify(path));m['independent_verification_passed']=True
    except BaseException as exc:m.update(status='failed',exception_type=type(exc).__name__,exception_detail=str(exc)[:240]);raise
    finally:
        m.update(seconds=round(time.monotonic()-start,3),source_unchanged=hashes=={n:hashlib.sha256(b).hexdigest() for n,b in build_files().items()},inputs_unchanged=inputs=={n:digest(p) for n,p in spec['paths'].items()},harness_unchanged=m['harness_sha256']=={n:digest(ROOT/'tools'/n) for n in harness},plan_unchanged=m['plan_sha256']==digest(plan_path));atomic_json(path,m)
    if not all(m[k] for k in ['source_unchanged','inputs_unchanged','harness_unchanged','plan_unchanged']):raise RuntimeError('Frozen experiment changed')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--plan',type=Path,required=True);a=p.parse_args();out=a.output.resolve();plan=a.plan.resolve()
    if not out.is_relative_to(ROOT/'test-runs') or not plan.is_relative_to(ROOT/'test-runs'):raise ValueError('Keep private artifacts ignored')
    signal.signal(signal.SIGTERM,lambda n,f:sys.exit(128+n))
    with (ROOT/'test-runs/.owned-research.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);out.mkdir(parents=True,exist_ok=False);lock.seek(0);lock.truncate();json.dump({'pid':os.getpid(),'create_time':psutil.Process().create_time()},lock);lock.flush();run(out,plan)
