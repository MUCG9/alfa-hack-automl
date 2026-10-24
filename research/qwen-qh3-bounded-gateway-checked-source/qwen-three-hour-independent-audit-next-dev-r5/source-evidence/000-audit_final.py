"""Two-task saved-artifact audit; no learner, gateway or candidate imports.

ALL immutable input/source and BOTH complete task-output seals are checked
before the numerical R4 primitives are imported or independent truth is read.
The existing outer supervisor owns process/resource observations and cleanup.
"""
from pathlib import Path
import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
import time

KINDS=('regression','classification')
PRIMITIVES=Path(__file__).with_name('r4_primitives.py')
GATEWAY_LIMIT=4800
CALLBACK_LIMIT=19204
CORE_FILES_LIMIT=20000


class AuditStop(RuntimeError):pass


def need(value,code):
    if not value:raise AuditStop(code)


def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
        separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()


def sha(path,check=lambda:None):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            check();part=stream.read(2**20)
            if not part:break
            value.update(part)
    check();return value.hexdigest()


def load(path,check=lambda:None,maximum=32*2**20):
    check();path=Path(path)
    need(path.is_file() and not path.is_symlink() and 0<path.stat().st_size<=maximum,'bounded_regular_JSON_required')
    def pairs(items):
        result={}
        for key,value in items:
            need(key not in result,'duplicate_JSON_key');result[key]=value
        return result
    def nonfinite(_):raise AuditStop('nonfinite_JSON')
    value=json.loads(path.read_text('utf-8'),object_pairs_hook=pairs,parse_constant=nonfinite)
    check();return value


def valid_hash(value):
    return type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value)


def ref_check(ref,check=lambda:None,pins=None):
    need(type(ref) is dict and set(ref)=={'path','sha256'} and Path(ref['path']).is_absolute()
         and valid_hash(ref['sha256']),'exact_absolute_ref_required')
    if pins is not None:need(pins.get(ref['path'])==ref['sha256'],'ref_outside_immutable_union')
    need(sha(ref['path'],check)==ref['sha256'],'ref_SHA_changed')
    return Path(ref['path'])


def verify_all_seals(cfg,check):
    """Stdlib byte barrier only. Never load a task report, truth or predictions."""
    pins=cfg['immutable_files']
    need(type(pins) is dict and pins and len(pins)<=10000,'complete_immutable_union_required')
    for path,h in pins.items():ref_check(dict(path=path,sha256=h),check)
    rows=cfg['tasks'];need(type(rows) is list and [r['kind'] for r in rows]==list(KINDS),'exact_two_ordered_tasks_required')
    seals=[]
    for row in rows:
        required={'kind','task_manifest','spec','output','report','terminal','supervisor','seal'}
        need(type(row) is dict and set(row)==required,'closed_task_authority_fields_required')
        ref_check(row['task_manifest'],check,pins)
        seal_path=ref_check(row['seal'],check)
        seal=load(seal_path,check)
        need(seal.get('schema')=='qwen-three-hour-task-core-seal-v1' and seal.get('kind')==row['kind']
             and seal.get('task_manifest')==row['task_manifest'] and seal.get('output')==row['output']
             and seal.get('immutable_files_sha256')==pins,'all_source_input_and_task_binding_seal_required')
        output=Path(row['output']);need(output.is_absolute() and output.resolve()==output and output.is_dir()
            and not output.is_symlink(),'absolute_task_output_required')
        files=seal['files_sha256'];need(type(files) is dict and 1<=len(files)<=CORE_FILES_LIMIT,'complete_bounded_core_inventory_required')
        actual={str(p.resolve()) for p in output.rglob('*') if p.is_file() and p.resolve()!=seal_path.resolve()}
        need(actual==set(files),'entire_task_tree_must_be_sealed')
        for path,h in files.items():
            p=Path(path);need(p.is_absolute() and p.resolve().is_relative_to(output)
                and not p.is_symlink(),'core_path_escape_or_symlink')
            ref_check(dict(path=path,sha256=h),check)
        for role in ('report','terminal'):
            need(files.get(row[role]['path'])==row[role]['sha256'],'mandatory_core_role_not_sealed')
        sup=row['supervisor'];need(set(sup)=={'path','sha256','record'},'actual_supervisor_binding_required')
        ref_check({k:sup[k] for k in ('path','sha256')},check)
        need(load(sup['path'],check)==sup['record'],'actual_supervisor_record_changed')
        saved=sup['record'];ob=saved.get('cleanup_observation',{})
        need(saved.get('status')=='ok' and saved.get('exit_code')==0 and saved.get('cleanup_confirmed') is True
             and saved.get('error_history')==[] and ob.get('denial_count')==0 and ob.get('unresolved')==[],
             'actual_task_exit_or_cleanup_unqualified')
        seals.append(seal)
    check();return seals


def numerical_primitives(expected):
    need(sha(PRIMITIVES)==expected,'R4_primitive_source_changed')
    sys.dont_write_bytecode=True
    spec=importlib.util.spec_from_file_location('_three_hour_R4_primitives',PRIMITIVES)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


class LiteralCSV:
    """Preserve independent labels/IDs; leave all numeric predictor parsing alone."""
    def __init__(self,pandas,spec,csv_roles):
        self.pandas=pandas;self.spec=spec;self.csv_roles=dict(csv_roles)
    def __getattr__(self,name):return getattr(self.pandas,name)
    def read_csv(self,path,*args,**kwargs):
        role=self.csv_roles.get(str(Path(path).resolve()))
        need(role in {'train','test','sample_submission','submission','validation_predictions'},
             'exact_CSV_path_and_role_required')
        literal=set()
        identifier=self.spec.get('id')
        if identifier is not None and role!='validation_predictions':literal.add(identifier)
        if self.spec['kind']=='classification':
            if role=='train':literal.add(self.spec['target'])
            elif role=='submission':literal.update(self.spec['output_columns'])
            elif role=='validation_predictions':literal.update(('y_true','y_pred'))
        requested=dict(kwargs.get('converters') or {})
        need(all((name in literal or name is None and identifier is None) and converter is str
             for name,converter in requested.items()),'CSV_converter_outside_exact_declared_role')
        kwargs['converters']={name:str for name in literal}
        frame=self.pandas.read_csv(path,*args,**kwargs)
        declared=[name for name in literal if name in frame]
        if declared:
            with Path(path).open(encoding='utf-8-sig',newline='') as stream:
                reader=csv.DictReader(stream)
                need(reader.fieldnames is not None and len(reader.fieldnames)==len(set(reader.fieldnames)),
                     'literal_CSV_header_ambiguous')
                witness={name:[] for name in declared}
                for row in reader:
                    need(None not in row and all(v is not None for v in row.values()),'literal_CSV_row_width')
                    for name in declared:witness[name].append(row[name])
            need(all(frame[name].tolist()==witness[name] for name in declared),'literal_class_or_ID_drift')
        return frame


def exact_csv_roles(spec,parents,seal):
    """Bind pristine roles and sealed worker-result sibling prediction paths."""
    roles={}
    def add(path,role):
        resolved=str(Path(path).resolve())
        need(Path(path).is_absolute() and (resolved not in roles or roles[resolved]==role),
             'CSV_role_paths_must_be_absolute_and_nonconflicting')
        roles[resolved]=role
    for role in ('train','test','sample_submission'):add(spec['paths'][role],role)
    roots={Path(parent['result']['output_dir']).resolve() for parent in parents}
    for path in seal['files_sha256']:
        result=Path(path)
        if result.name!='result.json' or not roots.intersection(result.resolve().parents):continue
        folder=result.parent
        for name,role in [('submission.csv','submission'),('validation_predictions.csv','validation_predictions')]:
            prediction=str(folder/name)
            if prediction in seal['files_sha256']:add(prediction,role)
    return roles


def parent_records(row,report,taskcfg,seal,check,terminal_check):
    refs=report.get('callback_ledger_refs');count=report.get('worker_calls_attempted')
    need(type(refs) is list and type(count) is int and 1<=count==len(refs)<=CALLBACK_LIMIT,'all_actual_callback_receipts_required')
    seen=set();records=[]
    for index,ref in enumerate(refs,1):
        need(ref['path'] not in seen and seal['files_sha256'].get(ref['path'])==ref['sha256'],'duplicate_or_unsealed_parent_receipt')
        seen.add(ref['path']);path=ref_check(ref,check);parent=load(path,check)
        need(parent.get('schema')=='qwen-three-hour-parent-result-v1' and parent.get('callback_index')==index
             and parent.get('task_manifest')==row['task_manifest']
             and parent.get('source_union_canonical_sha256')==canonical(taskcfg['immutable_files'])
             and parent.get('spec_canonical_sha256')==canonical(taskcfg['spec']),'parent_source_spec_or_index_changed')
        result=parent['result'];need(type(result) is dict and result.get('cleanup_confirmed') is True
             and result.get('strict_runtime') is True,'parent_cleanup_or_strict_receipt_missing')
        folder=Path(row['output'])/('worker-'+str(index))
        need(Path(result['output_dir']).resolve()==folder.resolve(),'actual_callback_output_folder_changed')
        origin=result.get('hpo_fair_reserve_provenance')
        need(type(origin) is dict and set(origin)=={'schema','cleanup_confirmed','coordinator_killed','primary_exception_type','prior_result_status'}
             and origin['schema']=='hpo-fair-reserve-worker-origin-v1' and origin['cleanup_confirmed'] is True
             and origin['coordinator_killed'] in (None,'timeout') and origin['primary_exception_type'] is None,
             'parent_resource_or_technical_origin_STOP')
        need(origin['prior_result_status'] in ('ok','timeout','error') and result.get('status') in ('ok','timeout','error'),
             'unknown_parent_status')
        need(parent['recipe_canonical_sha256']==canonical(result['recipe']),'actual_parent_recipe_changed')
        cut=parent['cut'];need(cut in taskcfg['task']['cuts'] and result.get('split_sha256')==cut['sha256'],'parent_cut_changed')
        for role in ('raw_job','raw_result'):
            ref2=parent.get(role)
            if ref2 is None:need(result['status']!='ok','successful_callback_raw_evidence_missing');continue
            need(ref2['path']==str(folder/('job.json' if role=='raw_job' else 'result.json')),
                 'raw_callback_role_path_changed')
            need(seal['files_sha256'].get(ref2['path'])==ref2['sha256'],'raw_callback_evidence_not_sealed')
            ref_check(ref2,check)
        if parent.get('raw_job') is not None:
            job=load(parent['raw_job']['path'],check)
            full=parent['phase']=='full-refit'
            need(job.get('spec')==taskcfg['spec'] and job.get('recipe')==result['recipe']
                 and type(job.get('threads')) is int and job['threads']==2
                 and job.get('full_fit') is full and Path(job['output_dir']).resolve()==folder.resolve()
                 and Path(job['split_path']).resolve()==Path(cut['path']).resolve(),
                 'actual_worker_job_spec_recipe_cut_threads_changed')
            if not full:need(job.get('fit_iterations') is None,'cut_fit_iterations_must_be_fresh_not_transferred')
        need(type(result.get('release_worker_allocation_seconds')) in (int,float)
             and 0<result['release_worker_allocation_seconds']<=900
             and result.get('worker_memory_limit_bytes')==1536*2**20
             and result.get('whole_memory_limit_bytes')==2048*2**20,'callback_allocations_or_caps_changed')
        for key,limit in [('observed_worker_tree_peak_bytes',1536*2**20),('observed_combined_peak_bytes',2048*2**20)]:
            value=result.get(key);need(type(value) is int and 0<=value<=limit,'actual_callback_resource_peak_unqualified')
        clock=result.get('release_original_clock',{});timing=taskcfg['clock']
        need(all(clock.get(k)==timing[v] for k,v in [('start_unix','task_start_unix'),('start_monotonic','task_start_monotonic'),
            ('deadline_unix','task_deadline_unix'),('deadline_monotonic','task_deadline_monotonic')])
            and clock.get('actual_failure_type') is None and type(clock.get('actual_resource_samples')) is int
            and clock['actual_resource_samples']>0
            and clock.get('resource_limit_bytes')==2048*2**20
            and clock.get('observation_gap_limit_seconds')==10 and clock.get('resource_sample_cadence_seconds')==.25,
            'parent_original_clock_or_actual_resource_receipt_missing')
        if result['status']=='ok':
            need(terminal_check(result) and type(result.get('parent_observed_worker_exit_code')) is int
                and result['parent_observed_worker_exit_code']==0,'typed_terminal_resource_and_actual_exit_missing')
        records.append(parent)
    need(report.get('worker_calls_succeeded')==sum(p['result']['status']=='ok' for p in records),'callback_status_accounting_changed')
    need(report.get('actual_learner_fit_calls') is None,'callback_count_is_not_learner_fit_count')
    return records


def usage_summary(rows,report):
    need(type(report.get('gateway_calls')) is int and len(rows)==report.get('gateway_calls')==len(report.get('usage',[]))
         and 1<=len(rows)<=GATEWAY_LIMIT,'actual_gateway_count_mismatch')
    attempts=0;totals={'prompt_tokens':0,'completion_tokens':0};complete=True
    for index,(row,saved) in enumerate(zip(rows,report['usage']),1):
        call=row['call'];number=call.get('attempts')
        need(row.get('call_number')==index and call.get('status')=='ok' and type(number) is int and 1<=number<=3,
             'actual_HTTP_attempts_missing_or_provider_failed')
        need(type(saved) is dict and set(saved)=={'status','attempts','usage','usage_complete','finish_reason',
             'reasoning_effort_requested','response_model'} and {k:call.get(k) for k in saved}==saved,
             'reported_usage_not_actual_gateway_receipt')
        attempts+=number;complete &= call.get('usage_complete') is True
        usage=call.get('usage') or {}
        for key in totals:
            v=usage.get(key);need(type(v) is int and v>=0,'actual_token_usage_missing');totals[key]+=v
    need(report.get('http_attempts_reported')==attempts and report.get('http_attempts_complete') is True
         and report.get('usage_complete') is complete and complete,'incomplete_actual_usage_STOP')
    return dict(gateway_calls=len(rows),HTTP_attempts=attempts,reported_tokens=totals,
        usage_complete=True,requested_reasoning=[r['call'].get('reasoning_effort_requested') for r in rows],
        response_models_reported=[r['call'].get('response_model') for r in rows],
        reasoning_token_counts_reported=[r['call'].get('reasoning_tokens_reported') for r in rows],
        requested_reasoning_is_backend_attestation=False)


def iteration_accounting(report,parents):
    rows=report.get('records');need(type(rows) is list and len(rows)==report['gateway_calls'],'all_adaptive_rounds_required')
    actual={}
    for parent in parents:
        match=re.fullmatch(r'round-(\d+)-([01])',parent['phase'])
        if match:actual.setdefault(int(match[1]),[]).append(parent)
        else:need(parent['phase'] in {'control-0','control-1','selected-confirmation','full-refit'},'unknown_callback_phase')
    attempted=0
    for number,row in enumerate(rows,1):
        need(row.get('round')==number and row.get('status') in {'invalid','duplicate','completed','failed'},'round_sequence_or_status_changed')
        callbacks=actual.get(number,[])
        if row['status'] in {'invalid','duplicate'}:
            need(not callbacks and row.get('scores') is None and row.get('decision')=='discard','unattempted_or_duplicate_is_not_a_fit')
        else:
            attempted+=1;need(1<=len(callbacks)<=2,'actual_attempted_round_callbacks_missing')
            if row['status']=='failed':need(row.get('scores') is None and row.get('decision')=='discard','failed_objective_must_be_NULL')
            else:
                need(len(callbacks)==2 and all(p['result']['status']=='ok' for p in callbacks)
                     and type(row.get('scores')) is list and len(row['scores'])==2
                     and all(type(v) in (int,float) and math.isfinite(v) for v in row['scores']),
                     'completed_round_requires_two_valid_callbacks')
    need(not set(actual)-set(range(1,len(rows)+1)) and report.get('executed_Qwen_candidates')==attempted and attempted>=1,
         'adaptive_callback_attempt_counter_changed')
    return dict(actual_candidate_recipe_attempts=attempted,actual_candidate_worker_callbacks=sum(map(len,actual.values())),all_rounds=len(rows),
        failed_objectives_are_NULL=True,learner_fit_count=None)


def anytime_time_goal(report,timing,supervisor):
    """Actual admission stop and observed task exit, never a callback time proxy."""
    remaining=report.get('remaining_task_seconds_at_stop');elapsed=report.get('elapsed_task_seconds_at_stop')
    end=supervisor.get('end_unix')
    need(report.get('schema')=='qwen-iterative-task-v2-anytime'
         and report.get('stop_reason')=='original_task_time_admission_margin'
         and report.get('gateway_safety_upper')==GATEWAY_LIMIT
         and report.get('callback_safety_upper')==CALLBACK_LIMIT,
         'time_driven_schema_or_safety_ceiling_changed')
    need(all(type(v) in (int,float) and math.isfinite(v) for v in (remaining,elapsed,end))
         and 0<remaining<=85 and 4715<=elapsed<4800
         and end>=timing['task_deadline_unix']-85,
         'actual_task_time_goal_or_observed_exit_missing')
    return dict(admission_stop_remaining_seconds=remaining,admission_stop_elapsed_seconds=elapsed,
        observed_supervisor_end_unix=end,scope='actual original4800 admission margin; no counted-time or padding claim')


def anytime_accounting(report,parents,task,median,strong_signature):
    """Bind every actual callback and atomic completed-checkpoint selection."""
    refs=report.get('callback_ledger_refs');rows=report.get('records');items=report.get('checkpoints')
    need(report.get('schema')=='qwen-iterative-task-v2-anytime'
         and type(refs) is list and len(refs)==len(parents)
         and type(rows) is list and type(report.get('gateway_calls')) is int
         and 1<=len(rows)==report.get('gateway_calls')<=GATEWAY_LIMIT
         and type(items) is list and 1<=len(items)<=len(rows)+1,'bounded_anytime_rows_and_checkpoints_required')
    def key(ref):
        need(type(ref) is dict and set(ref)=={'path','sha256'} and type(ref['path']) is str
             and ref['path'] and valid_hash(ref['sha256']),'exact_checkpoint_parent_ref_required')
        return (ref['path'],ref['sha256'])
    indexed={key(ref):(i,parent,ref) for i,(parent,ref) in enumerate(zip(parents,refs),1)}
    need(len(indexed)==len(parents),'duplicate_checkpoint_parent_ref')
    used=set();rounds={};finalizers=set()
    for ref,parent in zip(refs,parents):
        phase=parent['phase'];match=re.fullmatch(r'round-(\d+)-([01])',phase)
        if match:
            slot=(int(match[1]),int(match[2]));need(slot not in rounds,'duplicate_round_callback_phase')
            rounds[slot]=(ref,parent)
        else:
            need(phase in {'control-0','control-1','selected-confirmation','full-refit'},'unknown_anytime_callback_phase')
            if phase in {'selected-confirmation','full-refit'}:finalizers.add(key(ref))
    def lookup(ref,phase,cut):
        k=key(ref);need(k in indexed,'checkpoint_parent_ref_not_actual')
        index,parent,_=indexed[k]
        need(parent['phase']==phase and parent['cut']==task['cuts'][cut],'checkpoint_phase_or_cut_changed')
        used.add(k);return index,parent
    def returned(parent,ref):return dict(parent['result'],parent_callback_receipt=copy.deepcopy(ref))
    def scores(pair):
        values=[p['result'].get('metrics',{}).get(task['metric']) for p in pair]
        need(all(type(v) in (int,float) and math.isfinite(v) for v in values),'checkpoint_actual_finite_scores_required')
        return values
    need(len(parents)>=4 and [p['phase'] for p in parents[:2]]==['control-0','control-1'],
         'initial_control_pair_before_checkpoints_required')
    control=[]
    for i in (0,1):
        _,p=lookup(refs[i],'control-'+str(i),i);control.append(returned(p,refs[i]))
        need(p['result']['status']=='ok' and p['result']['recipe']==task['strong_recipe'],'actual_strong_control_pair_changed')
    need(report.get('strong_control_cuts')==control,'reported_strong_control_not_exact_actual_pair')
    attempted=0
    for number,row in enumerate(rows,1):
        need(type(row) is dict and type(row.get('round')) is int and row.get('round')==number
             and row.get('status') in {'invalid','duplicate','unattempted_budget','completed','failed'},'anytime_round_sequence_or_status_changed')
        actual=[rounds[(number,i)] for i in (0,1) if (number,i) in rounds]
        for ref,parent in actual:
            used.add(key(ref));need(parent['cut']==task['cuts'][int(parent['phase'][-1])],'round_actual_cut_order_changed')
        if row['status'] in {'invalid','duplicate','unattempted_budget'}:
            need(not actual and row.get('scores') is None and row.get('decision')=='discard'
                 and row.get('checkpoint') is None,'unattempted_or_duplicate_is_not_actual_callback')
        else:
            attempted+=1
            need(1<=len(actual)<=2 and (number,0) in rounds,'attempted_round_callback_missing')
            if row['status']=='failed':
                need(row.get('scores') is None and row.get('decision')=='discard' and row.get('checkpoint') is None,
                     'failed_anytime_objective_must_be_NULL')
            else:
                need(len(actual)==2 and all(p['result']['status']=='ok' for _,p in actual)
                     and actual[0][1]['result']['recipe']==actual[1][1]['result']['recipe']
                     and row.get('scores')==scores([p for _,p in actual]),'completed_round_requires_exact_two_actual_scores')
                need(row.get('decision') in {'discard','keep_completed_checkpoint','eligible_unfinalized'},'unknown_anytime_round_decision')
    need(not {n for n,_ in rounds}-set(range(1,len(rows)+1))
         and type(report.get('executed_Qwen_candidates')) is int
         and report.get('executed_Qwen_candidates')==attempted and attempted>=1,'anytime_actual_attempt_counter_changed')
    required={'index','round','signature','status','scores','primary_ref','confirmation_ref','full_refit_ref',
              'confirmation_lease_seconds','refit_lease_seconds'}
    complete=[];linked_finalizers=set();linked_rounds=set();complete_signatures=set();selected=None
    for index,item in enumerate(items,1):
        need(type(item) is dict and set(item) in (required,required|{'reason'})
             and type(item.get('index')) is int and item.get('index')==index
             and valid_hash(item.get('signature')) and item.get('status') in {'completed','unfinalized_budget',
                 'unfinalized_timeout','unfinalized_invalid','unfinalized_quality'},'closed_completed_or_unfinalized_checkpoint_required')
        number=item['round'];need(type(number) is int and 0<=number<=len(rows),'checkpoint_round_changed')
        if index==1:need(number==0 and item['signature']==strong_signature and item['status']=='completed','complete_initial_strong_checkpoint_required')
        else:
            need(number>0 and number not in linked_rounds and rows[number-1].get('checkpoint')==index
                 and rows[number-1]['status']=='completed' and rows[number-1].get('signature')==item['signature'],
                 'checkpoint_not_bound_to_eligible_actual_round')
            linked_rounds.add(number)
        a,primary=lookup(item['primary_ref'],'control-0' if number==0 else 'round-'+str(number)+'-0',0)
        need(primary['result']['status']=='ok','checkpoint_primary_not_successful')
        confirmation=full=None;b=d=None
        for role,phase,limit in [('confirmation','selected-confirmation',600),('full_refit','full-refit',900)]:
            ref=item[role+'_ref'];lease=item['confirmation_lease_seconds' if role=='confirmation' else 'refit_lease_seconds']
            if ref is None:need(lease is None,'unused_checkpoint_lease_must_be_NULL');continue
            need(type(lease) in (int,float) and math.isfinite(lease) and 5<=lease<=limit,'checkpoint_soft_lease_cap_changed')
            k=key(ref);need(k not in linked_finalizers,'checkpoint_finalizer_reused');linked_finalizers.add(k)
            order,parent=lookup(ref,phase,1)
            need(parent['result']['recipe']==primary['result']['recipe']
                 and parent['result']['release_worker_allocation_seconds']<=lease,'checkpoint_recipe_or_actual_lease_changed')
            if role=='confirmation':b,confirmation=order,parent
            else:d,full=order,parent
        need((b is None or a<b) and (d is None or b is not None and b<d),'checkpoint_callback_order_changed')
        if item['status']=='completed':
            need(confirmation is not None and full is not None and confirmation['result']['status']==full['result']['status']=='ok'
                 and full['result'].get('full_fit') is True and type(full['result'].get('submission')) is str
                 and item['scores']==scores([primary,confirmation])
                 and full['result'].get('fit_iterations')==median(primary['result']['fit_iterations'],confirmation['result']['fit_iterations']),
                 'completed_checkpoint_fresh_confirmation_median_full_required')
            need(item['signature'] not in complete_signatures,'unchanged_completed_checkpoint_refitted')
            complete_signatures.add(item['signature']);complete.append(index)
            if number:need(rows[number-1]['decision']=='keep_completed_checkpoint','completed_checkpoint_decision_changed')
            selected=(item,primary,confirmation,full)
        else:
            need(item['scores'] is None and type(item.get('reason')) is str and item['reason'],'unfinalized_checkpoint_objective_must_be_NULL')
            if number:need(rows[number-1]['decision']=='eligible_unfinalized','unfinalized_checkpoint_cannot_select')
            status=item['status']
            if status=='unfinalized_timeout':
                need(confirmation is not None and (confirmation['result']['status']=='timeout' and full is None
                     or confirmation['result']['status']=='ok' and full is not None and full['result']['status']=='timeout'),
                     'unfinalized_timeout_requires_actual_confirmed_timeout')
            else:
                need(full is None and (status=='unfinalized_budget' or confirmation is not None)
                     and (confirmation is None or confirmation['result']['status']=='ok'),
                     'unfinalized_checkpoint_role_status_changed')
    need(complete and type(report.get('selected_checkpoint')) is int
         and report.get('selected_checkpoint')==complete[-1] and selected is not None,'selected_checkpoint_must_be_last_completed')
    item,primary,confirmation,full=selected
    need(report.get('selected_recipe')==primary['result']['recipe']
         and report.get('selected_cuts')==[returned(primary,item['primary_ref']),returned(confirmation,item['confirmation_ref'])]
         and report.get('final_confirmation')==returned(confirmation,item['confirmation_ref'])
         and report.get('full_refit')==returned(full,item['full_refit_ref']),'selected_outputs_not_atomic_completed_checkpoint')
    need(linked_finalizers==finalizers and used==set(indexed),'unlinked_actual_checkpoint_callback')
    for number,row in enumerate(rows,1):
        need((row.get('checkpoint') is None)==(number not in linked_rounds),'round_checkpoint_link_changed')
        if number not in linked_rounds:need(row.get('decision')=='discard','unlinked_round_cannot_claim_selection')
    return dict(actual_candidate_recipe_attempts=attempted,actual_candidate_worker_callbacks=len(rounds),
        all_rounds=len(rows),completed_checkpoints=len(complete),unfinalized_checkpoints=len(items)-len(complete),
        selected_checkpoint=complete[-1],failed_objectives_are_NULL=True,learner_fit_count=None)


def verify_usage(row,report,seal,taskcfg,check):
    output=Path(row['output']);rows=[]
    for index in range(1,report['gateway_calls']+1):
        folder=output/('gateway-'+str(index));request=folder/'request.json';response=folder/'result.json';supervisor=folder/'supervisor.json'
        for path in (request,response,supervisor):need(seal['files_sha256'].get(str(path))==sha(path,check),'provider_evidence_not_pretruth_sealed')
        req=load(request,check);res=load(response,check);sup=load(supervisor,check)
        need(res.get('schema')=='qwen-three-hour-single-gateway-result-v1' and res.get('request_sha256')==sha(request,check)
             and res.get('call_number')==index and req.get('call_number')==index,'actual_response_request_binding_changed')
        need(sup.get('status')=='ok' and sup.get('exit_code')==0 and sup.get('cleanup_confirmed') is True
             and sup.get('error_history')==[] and sup.get('solver_budget_seconds') is None
             and sup.get('cleanup_observation',{}).get('denial_count')==0
             and sup.get('cleanup_observation',{}).get('unresolved')==[],
             'provider_parent_or_technical_environment_unqualified')
        need(all(req['clock'][k]==taskcfg['clock'][k] for k in ('start_unix','start_monotonic',
             'absolute_deadline_unix','common_deadline_monotonic','task_deadline_monotonic')),
             'provider_original_clock_changed')
        need(req.get('schema')=='qwen-three-hour-single-gateway-v1'
             and req.get('source_files')=={p:h for p,h in taskcfg['immutable_files'].items() if Path(p).suffix=='.py'}
             and req.get('canonical_root')==taskcfg['canonical_root'] and req.get('output')==str(response)
             and type(req.get('timeout')) in (int,float) and 5<=req['timeout']<=180,
             'actual_provider_source_output_or_timeout_changed')
        actual_user=json.dumps(req['context'],ensure_ascii=False)
        need(len(req['prompt'].encode('utf-8'))+len(actual_user.encode('utf-8'))<=65536,'actual_complete_message_byte_cap')
        need(req['context']['actual_resources']==dict(learner_threads=2,worker_RSS_MiB=1536,whole_RSS_MiB=2048),
             'provider_context_resource_entitlement_changed')
        rows.append(res)
    return usage_summary(rows,report)


def verify_task(row,seal,cfg,r4,check):
    taskcfg=load(row['task_manifest']['path'],check)
    need(taskcfg.get('schema')=='qwen-three-hour-task-private-v1' and taskcfg.get('readiness')=='READY_SOURCE_REVIEWED_FROZEN'
         and taskcfg.get('missing_bindings')==[] and taskcfg['spec']==row['spec'] and taskcfg['output']==row['output'],
         'task_authority_or_spec_changed')
    for path,h in taskcfg['immutable_files'].items():need(cfg['immutable_files'].get(path)==h,'task_source_input_union_not_frozen')
    spec=taskcfg['spec'];task=taskcfg['task'];timing=taskcfg['clock']
    need(spec['kind']==row['kind']==task['kind'] and spec['metric']==task['metric']==('rmse' if row['kind']=='regression' else 'macro_f1')
         and spec['greater_is_better']==task['greater_is_better']==(row['kind']=='classification')
         and task['context_flag'] is False and task['selector_cache_flag'] is False,'metric_kind_or_scientific_factors_changed')
    need(spec['features']==task['features'] and not set(spec['features'])&set(spec.get('all_targets',[spec['target']])+[spec.get('id')])
         and (row['kind']!='classification' or spec['classes']==task['classes'] and all(type(c) is str for c in spec['classes'])),
         'predictor_roles_or_lexical_class_authority_changed')
    need(timing['task_deadline_monotonic']==timing['task_start_monotonic']+4800
         and timing['task_deadline_unix']==timing['task_start_unix']+4800
         and all(timing[k]==cfg['clock'][k] for k in ('start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic')),
         'actual_equal_task_or_common_clock_changed')
    authority=load(ref_check(taskcfg['strong_authority'],check,cfg['immutable_files']),check)
    need(authority.get('schema')=='qwen-three-hour-strong-recipe-authority-v1' and authority.get('kind')==row['kind']
         and authority.get('metric')==spec['metric'] and authority.get('recipe')==task['strong_recipe'],'strong_raw_authority_changed')
    report=load(row['report']['path'],check);terminal=load(row['terminal']['path'],check)
    need(report.get('status')=='cores_ready_pending_all_task_seals_and_independent_audit'
         and report.get('first_failure') is None and report.get('secondary_failures')==[]
         and report.get('quality_qualified') is False and report.get('promotion') is False,'complete_task_core_required')
    need(terminal.get('schema')=='qwen-three-hour-task-terminal-v1' and terminal.get('status')==report['status']
         and terminal.get('manifest_sha256')==row['task_manifest']['sha256']
         and terminal.get('independently_qualified') is False,'actual_terminal_binding_missing')
    parents=parent_records(row,report,taskcfg,seal,check,r4.verified_terminal)
    time_goal=anytime_time_goal(report,timing,row['supervisor']['record'])
    accounting=anytime_accounting(report,parents,task,r4.median_iterations,authority['recipe_signature'])
    need([p['phase'] for p in parents[:2]]==['control-0','control-1']
         and all(p['result']['recipe']==task['strong_recipe'] for p in parents[:2]),'fresh_strong_control_pair_missing')
    def parent(record):
        ref=record.get('parent_callback_receipt');found=[p for p,ref2 in zip(parents,report['callback_ledger_refs']) if ref==ref2]
        need(len(found)==1,'record_missing_actual_parent_ledger_ref')
        stripped={k:v for k,v in record.items() if k!='parent_callback_receipt'}
        need(found[0]['result']==stripped,'reported_record_not_exact_parent_return');return found[0]
    control=report.get('strong_control_cuts');selected=report.get('selected_cuts');full=report.get('full_refit')
    need(type(control) is list and type(selected) is list and len(control)==len(selected)==2 and type(full) is dict,
         'all_final_control_selected_and_refit_records_required')
    for record in control+selected+[full]:parent(record)
    need(all(r['recipe']==task['strong_recipe'] for r in control)
         and all(r['recipe']==report['selected_recipe'] for r in selected+[full]),'selected_or_control_raw_recipe_changed')
    roles=spec['paths'];required={'train','test','sample_submission'}
    need(required<=set(roles),'explicit_input_roles_required')
    for role in required:need(roles[role] in cfg['immutable_files'],'independent_truth_role_not_pretruth_bound')
    csv_roles=exact_csv_roles(spec,parents,seal)
    parser=LiteralCSV(r4.pd,spec,csv_roles)
    train=parser.read_csv(roles['train'])
    test=parser.read_csv(roles['test'])
    sample=parser.read_csv(roles['sample_submission'])
    if spec['kind']=='classification':need(all(value!='' for value in train[spec['target']]),'empty_class_not_supported')
    check();actual_pd=r4.pd;r4.pd=parser
    try:
        verifier=r4.TaskVerifier(Path(row['output']),dict(spec=spec),train,test,sample)
        cuts={};controls={}
        need([c['seed'] for c in task['cuts']]==[42,43],'original_two_cut_order_required')
        for index,phase in enumerate(('primary','confirmation')):
            cut=task['cuts'][index];ref_check({k:cut[k] for k in ('path','sha256')},check,cfg['immutable_files'])
            need(parent(control[index])['cut']==cut and parent(selected[index])['cut']==cut,'selected_control_cut_assignment_changed')
            controls[phase]=r4.diagnostics(verifier,control[index],Path(cut['path']),phase)
            cuts[phase]=r4.diagnostics(verifier,selected[index],Path(cut['path']),phase);check()
            if row['kind']=='classification':
                need(cut['independent_fitting_groups']==controls[phase]['independent_fitting_groups']
                     and cut['rarest_fitting_class']==controls[phase]['rarest_fitting_class'],
                     'predeclared_class_support_not_actual_fitting_groups')
        need(report['final_confirmation']==selected[1] and parent(selected[1])['phase']=='selected-confirmation','fresh_final_confirmation_missing')
        expected=r4.median_iterations(selected[0]['fit_iterations'],selected[1]['fit_iterations'])
        need(full.get('fit_iterations')==expected and full.get('full_fit') is True and parent(full)['phase']=='full-refit',
             'fresh_recursive_median_or_full_refit_missing')
        final=verifier.verify(full,Path(task['cuts'][1]['path']),'final',True,report['selected_recipe']);check()
        fitting=[]
        for (folder,phase,full_fit),verified in verifier.records.items():
            stored=load(Path(folder)/'result.json',check);recipe=stored['recipe']
            job=Path(folder)/'job.json'
            if job.is_file() and not full_fit:
                need(load(job,check).get('fit_iterations') is None,'cut_fit_iterations_must_be_fresh_not_transferred')
            if stored.get('components'):continue
            partition=Path(task['cuts'][1 if phase=='confirmation' or full_fit else 0]['path'])
            fitting_parent=r4.np.arange(len(train),dtype=r4.np.int64) if full_fit else r4.split(partition,len(train))[0]
            receipts=stored.get('data_policy_runs')
            need(type(receipts) is list and receipts and any(v.get('source_rows')==len(fitting_parent)
                 and v.get('source_parent_sha256')==r4.canonical(fitting_parent.tolist()) and v.get('synthetic_rows')==0
                 for v in receipts),'actual_fitting_parent_lineage_required')
            if not full_fit:
                need(stored.get('early_stopping_source')=='inner_training_holdout' and stored.get('inner_split_error') is None,
                     'fitting_only_nested_stopping_required')
            if recipe.get('params',{}).get('loss_profile_id'):r4.loss_telemetry(stored,recipe,verifier,r4,partition)
            fitting.append(dict(phase=phase,full_fit=full_fit,completed_policy_callbacks=len(receipts),actual_learner_fits=None))
        comparison=r4.matched_control_comparison(cuts,controls,row['kind'])
        same=report['selected_recipe']==task['strong_recipe']
        quality=(not same and comparison['each_cut_primary_gate_passed'] and comparison['class_each_cut_gate_passed'])
        return dict(kind=row['kind'],metric=spec['metric'],selected_recipe_sha256=canonical(report['selected_recipe']),
            strong_recipe_sha256=canonical(task['strong_recipe']),cuts=cuts,control_cuts=controls,
            matched_control=comparison,strict_improvement_on_both_cuts_and_mean=quality,
            selected_cut_mean=sum(cuts[p]['value'] for p in ('primary','confirmation'))/2,
            retained_unchanged_strong_recipe=same,final_CSV_sha256=sha(final['folder']/'submission.csv',check),
            actual_worker_callbacks=len(parents),actual_learner_fit_count=None,iteration_accounting=accounting,
            anytime_time_goal=time_goal,
            fitting_receipts=fitting,resource_scope='sampled stable known RSS; not OS lifetime peak',
            usage=verify_usage(row,report,seal,taskcfg,check),
            validation_scope='adaptive reused public validation; independently rescored after all-core seals, not blind/official')
    finally:r4.pd=actual_pd


def check_clock(timing,previous,now,wall):
    need(all(type(v) in (int,float) and math.isfinite(v) for v in (*timing.values(),now,wall)),
         'finite_original_audit_clock_required')
    need(timing['common_deadline_monotonic']==timing['start_monotonic']+10800
         and timing['absolute_deadline_unix']==timing['start_unix']+10800
         and timing['audit_deadline_monotonic']==timing['audit_start_monotonic']+600
         and timing['audit_deadline_unix']==timing['audit_start_unix']+600,'original_common_and_audit_assignment_required')
    need(now>=previous and wall>=timing['audit_start_unix']
         and timing['audit_start_monotonic']>=timing['start_monotonic']
         and now<min(timing['audit_deadline_monotonic']-30,timing['common_deadline_monotonic']-300)
         and wall<min(timing['audit_deadline_unix']-30,timing['absolute_deadline_unix']-300),
         'original_audit570_common_cleanup_reserve_or_rollback')
    need(abs((timing['common_deadline_monotonic']-now)-(timing['absolute_deadline_unix']-wall))<=5,
         'wall_monotonic_disagreement')
    return now


def source_qualification(cfg,check):
    qualification=cfg['source_qualification']
    need(type(qualification) is dict and set(qualification)=={'archive','root','confirmation'},'exact_archive_qualification_refs_required')
    for ref in qualification.values():ref_check(ref,check,cfg['immutable_files'])
    qroot=load(qualification['root']['path'],check)
    need(qroot.get('schema')=='standard-repair-qualification-root-closure-v1'
         and qroot.get('archive_sha256')==qualification['archive']['sha256']
         and type(qroot.get('actual_exec_exit_code_observed_by_root')) is int
         and qroot['actual_exec_exit_code_observed_by_root']==0
         and type(qroot.get('actual_tool_evidence')) is str and qroot['actual_tool_evidence']
         and all(qroot.get(k) is True for k in ('technical_procedure_passed','source_unchanged','cleanup_confirmed','temporary_cleanup_confirmed')),
         'actual_archive_source_qualification_required')
    confirmation=load(qualification['confirmation']['path'],check);actual=confirmation.get('actual_wrapper',{})
    need(confirmation.get('root_sha256')==qualification['root']['sha256']
         and confirmation.get('post_tool_confirmed') is True and confirmation.get('source_unchanged') is True
         and confirmation.get('known_exact_live')==[] and confirmation.get('uncertain')==[]
         and type(actual.get('exit_code')) is int and actual['exit_code']==0
         and type(actual.get('tool')) is str and actual['tool'],
         'actual_source_qualification_whole_wrapper_exit_and_fresh_missing')
    return qualification


def main(a):
    state=dict(schema='qwen-three-hour-independent-audit-v1',technical_procedure_passed=False,artifact_procedure_passed=False,
        metrics=None,quality_metric=None,task_results=None,quality_both_tasks=False,quality_gate_passed=False,
        promotion=False,submit=False,first_failure=None,manifest_sha256=a.manifest_sha256,
        audit_within_original_common_clock=False,new_model_fits=0,API_calls=0)
    output=Path(a.output);need(output.is_absolute() and not output.exists(),'exclusive_absolute_audit_output_required')
    try:
        need(__debug__ and sha(__file__)==a.self_sha256 and sha(a.manifest)==a.manifest_sha256,'nonoptimized_pinned_auditor_and_binding_required')
        cfg=load(a.manifest);need(cfg.get('schema')=='qwen-three-hour-independent-audit-private-v1'
            and cfg.get('readiness')=='READY_SOURCE_REVIEWED_FROZEN' and cfg.get('missing_bindings')==[],
            'NOT_READY_actual_qualification_seals_outer_clock_required')
        timing=cfg['clock'];previous=[timing['audit_start_monotonic']]
        def check():
            previous[0]=check_clock(timing,previous[0],time.monotonic(),time.time())
        check();need(cfg['immutable_files'].get(str(Path(__file__).resolve()))==a.self_sha256,'auditor_not_pretruth_pinned')
        seals=verify_all_seals(cfg,check)
        source_qualification(cfg,check)
        need(sha(a.manifest,check)==a.manifest_sha256,'audit_binding_changed')
        # The all-task byte barrier above is the sole route to numerical imports.
        r4=numerical_primitives(cfg['immutable_files'][str(PRIMITIVES.resolve())])
        results=[verify_task(row,seal,cfg,r4,check) for row,seal in zip(cfg['tasks'],seals)]
        verify_all_seals(cfg,check);need(sha(a.manifest,check)==a.manifest_sha256,'post_audit_binding_changed');check()
        state.update(technical_procedure_passed=True,artifact_procedure_passed=True,
            metrics={r['kind']:{p:r['cuts'][p]['value'] for p in ('primary','confirmation')} for r in results},
            quality_metric={r['kind']:r['selected_cut_mean'] for r in results},
            task_results=results,quality_both_tasks=all(r['strict_improvement_on_both_cuts_and_mean'] for r in results),
            quality_gate_passed=all(r['strict_improvement_on_both_cuts_and_mean'] for r in results),
            all_core_source_input_usage_barrier_before_truth=True,source_and_artifacts_unchanged=True,
            audit_within_original_common_clock=True,
            original_common_clock=timing,actual_outer_root_exit_and_fresh_confirmation_pending=True)
        check()
    except BaseException as error:
        state.update(technical_procedure_passed=False,artifact_procedure_passed=False,metrics=None,quality_metric=None,
            task_results=None,quality_both_tasks=False,quality_gate_passed=False,
            audit_within_original_common_clock=False,
            first_failure=dict(type=type(error).__name__,code=str(error) if isinstance(error,AuditStop) else None))
    temporary=output.with_name(output.name+'.pending')
    with temporary.open('x',encoding='utf-8') as stream:json.dump(state,stream,ensure_ascii=False,indent=2,allow_nan=False)
    os.replace(temporary,output)
    if state['technical_procedure_passed']:
        try:check()
        except BaseException as error:
            state.update(technical_procedure_passed=False,artifact_procedure_passed=False,metrics=None,quality_metric=None,
                task_results=None,quality_both_tasks=False,quality_gate_passed=False,
                audit_within_original_common_clock=False,
                first_failure=dict(type=type(error).__name__,code=str(error) if isinstance(error,AuditStop) else None))
            with temporary.open('x',encoding='utf-8') as stream:json.dump(state,stream,ensure_ascii=False,indent=2,allow_nan=False)
            os.replace(temporary,output)
    return 0 if state['technical_procedure_passed'] else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--manifest-sha256',required=True)
    p.add_argument('--self-sha256',required=True);p.add_argument('--output',required=True)
    raise SystemExit(main(p.parse_args()))
