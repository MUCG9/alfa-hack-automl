"""Fixed typed tabular recipes: two honest cut measurements, median, full refit.

Standard positional execution, no planner/Qwen/HPO, external recipe or stored
predictions. Historical research scores are not asserted by this new procedure.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import os
import time

# Apply native CPU caps BEFORE importing numerical/task/worker libraries.
for _variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS',
                  'NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[_variable] = str(min(2, max(1, int(os.environ.get('AUTOML_THREADS','2')))))

import numpy as np
import pandas as pd
from automl_atomic import atomic_json
from automl_contracts_messages import TaskSpec, SplitPlan, validate_loss_profiles
from automl_evaluation_api import choose_validation, make_split, make_time_split
from automl_infrastructure_tables import read_input_table
from automl_publishing import prediction_row_order
from automl_publishing_api import save_submission
from automl_runtime import source_files
from automl_task_understanding_api import discover
from automl_task_understanding_inputs import resolve_inputs
from automl_task_understanding_role_validation import validate_role_tables
from automl_task_understanding_metric_contract import resolve_metric_spec
from automl_release_recipes import fixed_recipe, HISTORICAL_DEPLOYMENT_ITERATIONS
from automl_release_runtime import ReleaseClock, run_release_worker


def resolved_policy(text):
    """Only explicit supported objectives authorize a fixed family; no defaults."""
    candidates=[]
    for kind, name in [('regression','rmse'),('classification','macro_f1')]:
        metric=resolve_metric_spec(text,kind)
        if metric.status=='resolved' and metric.name==name:
            candidates.append((kind,metric))
    if len(candidates)!=1:
        raise ValueError('Unresolved, conflicting or unsupported fixed-release objective')
    return candidates[0]


def lexical_projection(path, columns, checkpoint):
    """Read only declared protected cells as lexical strings; do not alter features."""
    checkpoint()
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:
        preview=stream.read(8192);stream.seek(0)
        if Path(path).suffix.lower() in {'.tsv','.tab'}:delimiter='\t'
        else:
            try:delimiter=csv.Sniffer().sniff(preview,delimiters=',;\t|').delimiter
            except csv.Error:
                try:delimiter=csv.Sniffer().sniff(preview.splitlines()[0],delimiters=',;\t|').delimiter
                except csv.Error:delimiter=','
        reader=csv.reader(stream,delimiter=delimiter);header=next(reader)
        if len(header)!=len(set(header)) or any(column not in header for column in columns):
            raise ValueError('Protected projection header is missing or duplicated')
        positions=[header.index(column) for column in columns];values={column:[] for column in columns}
        for number,row in enumerate(reader):
            if number%1024==0:checkpoint()
            if len(row)!=len(header):raise ValueError('Protected projection row width changed')
            for column,position in zip(columns,positions):values[column].append(row[position])
    checkpoint();return values


def load_fixed_inputs(task, kind, clock):
    """Reuse deterministic input resolution. Trust explicit dictionary roles only."""
    task=Path(task).resolve();root=task.parent;clock.check()
    text=task.read_text(encoding='utf-8-sig');clock.check()
    paths=resolve_inputs(root,text,allow_llm=False)
    if set(paths)!={'train','test','sample_submission','data_dictionary'}:
        raise ValueError('Fixed release needs four resolved input roles including dictionary')
    tables={}
    for role,key in [('train','train'),('test','test'),('sample_submission','sample'),('data_dictionary','dictionary')]:
        clock.check();tables[key]=read_input_table(paths[role]);clock.check()
    dictionary=tables['dictionary']
    if not {'feature','role'}<=set(dictionary):raise ValueError('Explicit target/ID dictionary roles required')
    roles=dictionary['role'].astype(str).str.strip().str.lower()
    targets=dictionary.loc[roles.eq('target'),'feature'].tolist()
    identifiers=dictionary.loc[roles.eq('id'),'feature'].tolist()
    if len(targets)!=1 or len(identifiers)>1 or len(set(targets+identifiers))!=len(targets+identifiers):
        raise ValueError('Ambiguous or multiple protected target/ID roles')
    target=targets[0];identifier=identifiers[0] if identifiers else None
    if any(not isinstance(value,str) or not value.strip() for value in targets+identifiers):
        raise ValueError('Explicit protected roles need nonempty column names')
    if target not in tables['train'] or target in tables['test']:
        raise ValueError('Declared target must exist in fitting data and not in test')
    if identifier is not None and any(identifier not in tables[key] for key in ('train','test','sample')):
        raise ValueError('Declared ID must exist in fitting/test/sample tables')
    for role,key in [('train','train'),('test','test'),('sample_submission','sample')]:
        columns=[]
        if identifier is not None and identifier in tables[key]:columns.append(identifier)
        # Literal class strings are justified ONLY by declared MacroF1 family.
        # Numeric regression targets and every predictor retain base parsing.
        if role=='train' and kind=='classification':columns.append(target)
        if columns:
            values=lexical_projection(paths[role],columns,clock.check)
            if any(len(v)!=len(tables[key]) for v in values.values()):raise ValueError('Protected row count drift')
            for column,values_column in values.items():tables[key][column]=values_column
    validate_role_tables(tables);clock.check()
    if identifier is not None and any(value=='' for frame in (tables['test'],tables['sample']) for value in frame[identifier]):
        raise ValueError('Empty declared identifiers are not lexical NA strings')
    if kind=='classification' and any(value=='' for value in tables['train'][target]):
        raise ValueError('Empty literal classification labels are unsupported')
    return dict(root=root,task_path=task,text=text,paths=paths,**tables,
        declared_target=target,declared_identifier=identifier,
        file_role_resolution=dict(method='existing_deterministic_no_LLM_explicit_dictionary_roles',API_calls=0))


def fingerprints(paths, checkpoint):
    result={}
    for name,path in paths.items():
        checkpoint();value=hashlib.sha256()
        with Path(path).open('rb') as stream:
            for chunk in iter(lambda:stream.read(2**20),b''):checkpoint();value.update(chunk)
        checkpoint();result[name]=value.hexdigest()
    return result


def median_iterations(first,second):
    # Same recursive median rule as the preserved base runner.
    if isinstance(first,list) or isinstance(second,list):
        if not isinstance(first,list) or not isinstance(second,list) or len(first)!=len(second):
            raise ValueError('Mismatched fit iteration trees')
        return [median_iterations(a,b) for a,b in zip(first,second)]
    if type(first) is not int or type(second) is not int or min(first,second)<=0:
        raise ValueError('Invalid actual cut-local fit iterations')
    return max(30,int(np.median([first,second])))


def worker_allocation(clock, remaining_workers):
    remaining=clock.remaining()-30  # parent checks/publication/final cleanup remain charged
    if remaining_workers<1 or remaining<remaining_workers*5:
        raise RuntimeError('Insufficient original common budget for fixed stages')
    return remaining/remaining_workers


def validate_output_identity(output, protected):
    """Reject input/task/code aliases before any worker and before publication."""
    output=Path(output)
    if output.is_symlink():raise ValueError('Submission destination cannot be a symlink')
    resolved=output.resolve()
    for value in protected.values():
        path=Path(value)
        if resolved==path.resolve() or (output.exists() and path.exists() and output.samefile(path)):
            raise ValueError('Submission destination aliases protected input/task/source')


def publish_fresh_result(spec, loaded, full, output, run_dir, clock):
    """Publish only a fresh actual full-fit result, with lexical sample/test IDs."""
    clock.check();validate_output_identity(output,loaded['protected_files'])
    folder=Path(full['output_dir'])
    if folder.resolve()!=(run_dir/'final-fit').resolve() or full.get('status')!='ok' or full.get('full_fit') is not True:
        raise ValueError('Actual successful full-refit receipt required')
    if spec['kind']=='classification':
        with np.load(folder/'test_probabilities.npz',allow_pickle=False) as stored:
            classes=stored['classes'].astype(str).tolist();probabilities=stored['probabilities'].copy()
        if classes!=spec['classes'] or probabilities.shape!=(len(loaded['test']),len(classes)):
            raise ValueError('Canonical class/probability order mismatch')
        if not np.isfinite(probabilities).all() or (probabilities<0).any() or (probabilities>1).any() or not np.allclose(probabilities.sum(axis=1),1,atol=1e-5):
            raise ValueError('Invalid actual full-refit probabilities')
        if spec['prediction_type']=='probability_matrix':
            values=probabilities[:,[classes.index(str(c)) for c in spec['output_columns']]]
        elif spec['prediction_type']=='value':values=np.asarray(classes)[probabilities.argmax(axis=1)]
        else:raise ValueError('Fixed MacroF1 release requires labels or canonical probability matrix')
    else:
        frame=pd.read_csv(folder/'submission.csv')
        values=frame[spec['output_columns'][0]].to_numpy(dtype=float)
        if len(values)!=len(loaded['test']) or not np.isfinite(values).all():raise ValueError('Invalid full-refit regression predictions')
        values=values[np.argsort(prediction_row_order(spec,len(values)))]
    clock.check();temporary=run_dir/'validated-submission.csv'
    if temporary.exists():raise ValueError('Exclusive publication path required')
    save_submission(spec,loaded['sample'],loaded['test'],values,temporary)
    clock.check();validate_output_identity(output,loaded['protected_files'])
    os.replace(temporary,output);clock.check()


def execute(task, *, seconds=9900, origin=None):
    """No experiments are selected by observed score: one frozen recipe per family."""
    task=Path(task).resolve();clock=ReleaseClock(seconds,task.parent,origin=origin)
    run_dir=None;report=None
    try:
        text=task.read_text(encoding='utf-8-sig');kind,metric=resolved_policy(text);clock.check()
        loaded=load_fixed_inputs(task,kind,clock)
        spec,unused_profile,train,test,sample,unused_text,hashes=discover(task,loaded=loaded,allow_llm=False)
        if spec['target']!=loaded['declared_target'] or spec.get('id')!=loaded['declared_identifier']:
            raise ValueError('Discovery cannot replace explicit target/ID role authority')
        if spec['kind']!=kind or spec['metric']!=metric.name:
            raise ValueError('Task discovery disagrees with explicit strict objective')
        recipe=fixed_recipe(kind,metric.name,text_features=spec.get('text_features',()))
        if kind=='classification' and (spec.get('positive_class') is not None or spec['prediction_type']=='probability'):
            raise ValueError('Positive-class probability objective is outside fixed MacroF1 release')
        TaskSpec.from_legacy(spec);validate_loss_profiles(recipe,kind)
        spec=choose_validation(spec,train,'auto');clock.check()
        protected={**{'input:'+k:v for k,v in loaded['paths'].items()},'task':task,
                   **{'source:'+p.name:p for p in source_files()}}
        protected['source:requirements.txt']=Path(__file__).with_name('requirements.txt')
        validate_output_identity(task.parent/'submission.csv',protected)
        loaded['protected_files']=protected
        base=task.parent/'automl_runs';base.mkdir(exist_ok=True)
        run_dir=base/('fixed-release-'+str(time.time_ns()));run_dir.mkdir()
        before=fingerprints(protected,clock.check)
        report=dict(schema='fixed-recipe-standard-release-v1',status='running',
            policy='fixed_typed_recipe_two_cut_median_full_refit',spec=spec,metric=metric.to_dict(),
            recipe=recipe,historical_deployment_iterations_provenance_only=HISTORICAL_DEPLOYMENT_ITERATIONS[kind],
            historical_metric_claim=None,new_quality_metric=None,Qwen_calls=0,API_calls=0,HPO_trials=0,
            search_or_optimization_performed=False,source_and_input_sha256=before,
            measurements=[],full_refit=None,cleanup_confirmed=False,source_unchanged=False,
            original_clock=clock.receipt(),first_failure=None,secondary_failures=[],promotion=False,submit=False)
        atomic_json(run_dir/'report.json',report);actual=[]
        for index,seed in enumerate([42,43]):
            clock.check()
            tr,va,info=(make_time_split(spec,train,offset=index) if spec.get('validation_strategy')=='time'
                        else make_split(spec,train,hashes,seed=seed))
            SplitPlan(tuple(tr.tolist()),tuple(va.tolist())).validate(len(train))
            split=run_dir/('primary-split.npz' if index==0 else 'confirmation-split.npz')
            np.savez(split,train=tr,validation=va);atomic_json(split.with_suffix('.json'),info);clock.check()
            # Deliberately NO fit_iterations override on either validation call.
            result=run_release_worker(spec,recipe,run_dir/('primary' if index==0 else 'confirmation'),
                split,worker_allocation(clock,3-index),clock=clock)
            report['measurements'].append(result);atomic_json(run_dir/'report.json',report)
            if result.get('status')!='ok' or result.get('cleanup_confirmed') is not True:
                raise RuntimeError('Fixed-recipe cut failed; no refit/score imputation')
            actual.append(result['fit_iterations'])
        iterations=median_iterations(actual[0],actual[1]);report['actual_median_refit_iterations']=iterations
        full=run_release_worker(spec,recipe,run_dir/'final-fit',split,worker_allocation(clock,1),
            clock=clock,full_fit=True,fit_iterations=iterations)
        report['full_refit']=full;atomic_json(run_dir/'report.json',report)
        if full.get('status')!='ok' or full.get('cleanup_confirmed') is not True:raise RuntimeError('Fixed-recipe full refit failed')
        if fingerprints(protected,clock.check)!=before:raise RuntimeError('Protected source/input changed')
        report['source_unchanged']=True
        publish_fresh_result(spec,loaded,full,task.parent/'submission.csv',run_dir,clock)
        if fingerprints(protected,clock.check)!=before:raise RuntimeError('Protected source/input changed during publication')
        report['submission_path']=str(task.parent/'submission.csv')
        report['submission_sha256']=fingerprints({'submission':task.parent/'submission.csv'},clock.check)['submission']
        report['cleanup_confirmed']=True;report['status']='completed_pending_independent_qualification'
        report['original_clock']=clock.receipt();clock.check(force=True)
        atomic_json(run_dir/'report.json',report);clock.check(force=True)
        print(json.dumps(dict(status=report['status'],policy=report['policy'],quality_metric=None,
            actual_primary_and_confirmation=2,actual_full_refit=1,Qwen_calls=0,API_calls=0)))
        return 0
    except BaseException as primary:
        if report is not None:
            report['status']='failed';report['first_failure']=dict(type=type(primary).__name__)
            report['original_clock']=clock.receipt();report['new_quality_metric']=None
            try:atomic_json(run_dir/'report.json',report)
            except BaseException as secondary:report['secondary_failures'].append(dict(type=type(secondary).__name__))
        raise


def main(*, origin=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task',type=Path)
    parser.add_argument('--time-budget',type=int,default=9900)
    args=parser.parse_args()
    return execute(args.task,seconds=args.time_budget,origin=origin)


if __name__=='__main__':raise SystemExit(main())
