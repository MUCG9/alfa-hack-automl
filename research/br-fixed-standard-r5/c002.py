"""Fixed-artifact audit only: no model/project runtime imports or fitting."""
from pathlib import Path
import argparse, csv, hashlib, importlib.util, json, math, time

PACKET=Path(__file__).resolve().parent
WORK=PACKET.parents[1]
OUT=WORK/'brq3'
R4=('uq3-cadence-hpo-next-dev/candidate/r4_adapter.py','823d9629119bcd03560cafb62e8b240af8dea5b3f3ba63b4d196b96a62a518cd')
LOSS=('uq3-cadence-hpo-next-dev/candidate/audit_pair.py','f58a17c218ca89461c3c97c3498d197fa105b5a8ea0b240b26b232b12badf7ff')

def need(value,code):
    if not value:raise RuntimeError(code)

def load(p):return json.loads(Path(p).read_text('utf-8'))

def digest(p,check=lambda:None):
    h=hashlib.sha256()
    with Path(p).open('rb') as stream:
        for block in iter(lambda:stream.read(2**20),b''):check();h.update(block)
    check();return h.hexdigest()

def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module

def lexical_witness(path,columns):
    """Independent stdlib lexical authority; empty is distinct from NA and001."""
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream);need(reader.fieldnames is not None
            and len(reader.fieldnames)==len(set(reader.fieldnames)) and set(columns)<=set(reader.fieldnames),'lexical_header')
        values={c:[] for c in columns}
        for row in reader:
            need(None not in row and all(value is not None for value in row.values()),'lexical_row_width')
            for c in columns:values[c].append(row[c])
    return values

class DeclaredClassCSV:
    """Audit transport facade ONLY for explicit classification cell/path pairs."""
    def __init__(self,pandas,roles):self.pandas,self.roles=pandas,roles
    def __getattr__(self,name):return getattr(self.pandas,name)
    def read_csv(self,path,*args,**kwargs):
        columns=self.roles.get(str(Path(path).resolve()),())
        options=dict(kwargs);converters=dict(options.get('converters') or {})
        for name in columns:converters[name]=str
        if columns:options['converters']=converters
        frame=self.pandas.read_csv(path,*args,**options)
        if columns:
            witness=lexical_witness(path,columns)
            need(all(frame[c].tolist()==witness[c] for c in columns),'declared_class_lexical_drift')
        return frame

def verified_terminal(record):
    """Only the new exact-known departure variant needs this typed bridge.

    Original two statuses retain their existing predicate. The new branch is
    bound to parent-captured worker/self identities and completed strict cleanup.
    A departed old identity has unknown RSS, never a measured zero.
    """
    terminal=record.get('terminal_resource_observation',{})
    if terminal.get('status') in {'sampled_before_terminal_acceptance','root_absent_after_observed_exit'}:return True
    if terminal.get('status')!='fresh_known_root_departed_after_observed_exit':return False
    def identity(row):
        if (type(row) is not dict or type(row.get('pid')) is not int or row['pid']<=0
            or type(row.get('create_time')) not in (int,float) or not math.isfinite(row['create_time'])
            or row['create_time']<=0):return None
        return row['pid'],row['create_time']
    sample=record.get('verified_resource_sample');root=identity(record.get('worker_resource_root'));own=identity(record.get('worker_resource_self'))
    if (root is None or own is None or root==own or type(sample) is not dict
        or sample.get('schema')!='verified-known-resource-sample-v1'
        or type(sample.get('sampled')) is not list or type(sample.get('departed')) is not list
        or len(sample['sampled'])+len(sample['departed'])>30000
        or type(sample.get('required_count')) is not int or sample['required_count']!=1
        or type(sample.get('sampled_count')) is not int or sample['sampled_count']!=len(sample['sampled'])
        or type(sample.get('known_count')) is not int or sample['known_count']<len(sample['sampled'])+len(sample['departed'])
        or sample.get('scope')!='sampled_stable_known_RSS_not_OS_lifetime_peak'
        or record.get('parent_observed_worker_exit_code')!=0 or type(record.get('parent_observed_worker_exit_code')) is not int
        or record.get('cleanup_confirmed') is not True
        or terminal.get('worker_root_rss_bytes') is not None
        or terminal.get('remaining_owned_cleanup_still_required') is not True
        or terminal.get('departed')!=sample['departed']):return False
    sampled={};departed={}
    for row in sample['sampled']:
        key=identity(row)
        if key is None or key in sampled or type(row.get('rss_bytes')) is not int or row['rss_bytes']<0:return False
        sampled[key]=row['rss_bytes']
    for row in sample['departed']:
        key=identity(row)
        if key is None or key in departed or key in sampled or row.get('rss_bytes') is not None:return False
        replacement=row.get('replacement_create_time')
        if row.get('state')=='fresh_confirmed_absent':
            if replacement is not None:return False
        elif row.get('state')=='fresh_confirmed_reused':
            if type(replacement) not in (int,float) or not math.isfinite(replacement) or replacement<=0 or replacement==key[1]:return False
        else:return False
        departed[key]=row
    if root not in departed or root in sampled or own not in sampled:return False
    worker_rss=sum(value for key,value in sampled.items() if key!=own)
    return (type(terminal.get('sampled_known_worker_rss_bytes')) is int
        and terminal['sampled_known_worker_rss_bytes']==worker_rss
        and worker_rss<=1536*2**20 and worker_rss+sampled[own]<=2048*2**20)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','manifest-sha256','self-sha256'):p.add_argument('--'+name,required=True)
    a=p.parse_args();need(__debug__ and Path(a.manifest).is_absolute(),'bounded_explicit_audit_manifest')
    need(digest(a.manifest)==a.manifest_sha256 and digest(__file__)==a.self_sha256,'audit_source_or_manifest_changed')
    cfg=load(a.manifest);campaign=load(OUT/'campaign.json');barrier_ref=campaign['pretruth_barrier']
    need(digest(barrier_ref['path'])==barrier_ref['sha256'],'pretruth_barrier_changed')
    barrier=load(barrier_ref['path']);clock=barrier['clock']
    def check():
        need(time.monotonic()<clock['common_deadline_monotonic'] and time.time()<clock['absolute_deadline_unix'],
            'original_release_qualification_deadline')
    need(barrier['manifest_sha256']==a.manifest_sha256 and len(barrier['tasks'])==2
        and [e['kind'] for e in barrier['tasks']]==['regression','classification'], 'both_sealed_tasks_before_truth')
    need(clock['absolute_deadline_unix']==clock['start_unix']+6000
        and clock['common_deadline_monotonic']==clock['start_monotonic']+6000,'same_assigned6000')
    # ALL task cores and both saved terminal supervisors are rehashed before numerical/data imports.
    actual={str(Path(__file__).resolve()):a.self_sha256,str(Path(a.manifest).resolve()):a.manifest_sha256,
            barrier_ref['path']:barrier_ref['sha256']}
    for path,h in cfg['immutable_files'].items():need(digest(path,check)==h,'immutable_before_truth_changed')
    sealed={}
    for entry in barrier['tasks']:
        ref=entry['supervisor'];need(digest(ref['path'],check)==ref['sha256'],'closed_supervisor_changed')
        supervisor=load(ref['path']);need(supervisor==ref['record'],'inline_saved_terminal_mismatch')
        parent,child={'regression':(900,870),'classification':(3600,3570)}[entry['kind']]
        need(supervisor.get('parent_cap_seconds')==parent and supervisor.get('child_cap_seconds')==child
            and supervisor.get('solver_budget_seconds') is None and supervisor.get('status')=='ok' and supervisor.get('exit_code')==0
            and supervisor.get('cleanup_confirmed') is True and not supervisor.get('error_history')
            and supervisor['end_unix']<clock['absolute_deadline_unix']
            and supervisor['seconds']<parent
            and supervisor['end_unix']<supervisor['start_unix']+parent
            and supervisor.get('maximum_observed_concurrent_worker_jobs',0)<=1
            and supervisor.get('peak_owned_tree_rss_mib',float('inf'))<=2048,
            'actual_terminal_caps_or_cleanup_failed')
        actual[ref['path']]=ref['sha256'];seal=entry['seal']
        need(digest(seal['path'],check)==seal['sha256'],'core_seal_changed');actual[seal['path']]=seal['sha256']
        rows=load(seal['path'])['files_sha256'];need(type(rows) is dict and 1<=len(rows)<=20000,'bounded_sealed_core')
        for path,h in rows.items():need(digest(path,check)==h,'sealed_core_changed')
        sealed[entry['kind']]=rows;actual.update(rows)
    for relative,h in (R4,LOSS):need(digest(WORK/relative,check)==h,'manual_verifier_changed')
    # The first pristine target read occurs only below this barrier.
    r4=imported('_br_fixed_manual_R4',WORK/R4[0]);r4.WORK=WORK
    loss=imported('_br_fixed_loss_receipts',WORK/LOSS[0]);pd=r4.pd;rows={}
    for task,entry in zip(cfg['tasks'],barrier['tasks']):
        kind=task['kind'];directory=Path(entry['directory']);report=load(entry['report']);spec=report['spec']
        need(report.get('schema')=='fixed-recipe-standard-release-v1'
            and report.get('status')=='completed_pending_independent_qualification'
            and report.get('recipe')==task['expected_recipe'] and report.get('source_unchanged') is True
            and report.get('cleanup_confirmed') is True and report.get('first_failure') is None
            and report.get('secondary_failures')==[] and report.get('search_or_optimization_performed') is False
            and report.get('API_calls')==report.get('Qwen_calls')==report.get('HPO_trials')==0,
            'fixed_procedure_or_recipe_changed')
        need(spec['kind']==kind and spec['metric']==('rmse' if kind=='regression' else 'macro_f1'), 'metric_kind_changed')
        metric=report['metric'];need(metric.get('status')=='resolved' and metric.get('name')==spec['metric'],
            'strict_supported_metric_receipt_required')
        declared={**{'input:'+name:task['files'][filename] for name,filename in
            [('train','train.csv'),('test','test.csv'),('sample_submission','sample_submission.csv'),('data_dictionary','data_dictionary.csv')]},
            'task':task['files']['task.md'],**{'source:'+name:h for name,h in cfg['executor']['members_sha256'].items()}}
        need(report['source_and_input_sha256']==declared,'executor_protected_source_and_input_map_changed')
        identifier=spec.get('id');source=Path(task['source']);train_path=source/'train.csv'
        dictionary=lexical_witness(source/'data_dictionary.csv',['feature','role'])
        targets=[name for name,role in zip(dictionary['feature'],dictionary['role']) if role.strip().lower()=='target']
        identifiers=[name for name,role in zip(dictionary['feature'],dictionary['role']) if role.strip().lower()=='id']
        need(targets==[spec['target']] and len(identifiers)<=1 and len(set(targets+identifiers))==len(targets+identifiers)
            and identifier==(identifiers[0] if identifiers else None),'independent_explicit_dictionary_authority_mismatch')
        roles={}
        if kind=='classification':
            roles[str(train_path.resolve())]=[spec['target']]
            for path in sealed[kind]:
                path=Path(path)
                if path.name=='validation_predictions.csv':roles[str(path.resolve())]=['y_true','y_pred']
                elif path.name=='submission.csv':roles[str(path.resolve())]=[spec['output_columns'][0]]
        parser=DeclaredClassCSV(pd,roles);r4.pd=parser
        converters={identifier:str} if identifier is not None else {}
        train=parser.read_csv(train_path,converters=converters)
        test=parser.read_csv(source/'test.csv',converters=converters)
        sample=parser.read_csv(source/'sample_submission.csv',converters=converters)
        if identifier is not None:
            for frame,path in [(train,train_path),(test,source/'test.csv'),(sample,source/'sample_submission.csv')]:
                need(frame[identifier].tolist()==lexical_witness(path,[identifier])[identifier], 'independent_lexical_ID_drift')
        if kind=='classification':need(all(v!='' for v in train[spec['target']]),'empty_class_label_not_missing_NA')
        need(len(report['measurements'])==2,'two_actual_cut_records_required')
        run=Path(entry['report']).parent;verifier=r4.TaskVerifier(directory,dict(spec=spec),train,test,sample)
        intrinsic=report['original_clock'];sup=entry['supervisor']['record']
        need(intrinsic.get('actual_failure_type') is None and intrinsic['actual_resource_samples']>0
            and intrinsic['deadline_unix']==intrinsic['start_unix']+9900
            and intrinsic['deadline_monotonic']==intrinsic['start_monotonic']+9900
            and sup['start_monotonic']<=intrinsic['start_monotonic']
            and intrinsic['start_monotonic']<=sup['child_start_monotonic']+1
            and intrinsic['resource_limit_bytes']==2048*2**20
            and intrinsic['observed_parent_conservative_total_peak_bytes']<=2048*2**20
            and intrinsic['observation_gap_limit_seconds']==10 and intrinsic['resource_sample_cadence_seconds']==.25,
            'intrinsic_origin_mismatch_not_outer_entitlement')
        cuts={};parts={}
        for index,phase in enumerate(('primary','confirmation')):
            partition=run/(phase+'-split.npz');parts[phase]=partition
            record=report['measurements'][index];need(Path(record['output_dir']).resolve()==run/phase,'fixed_cut_directory')
            job=load(run/phase/'job.json');need('fit_iterations' not in job and job['threads']==2,'cut_iteration_override_or_threads')
            expected=r4.expected_partition(task,spec,train,phase,cfg['verification_plan'])
            observed=r4.split(partition,len(train))
            need(all(r4.np.array_equal(a,b) for a,b in zip(expected,observed)),'frozen_cut_rows_changed')
            verifier.verify(record,partition,phase,expected_recipe=task['expected_recipe'])
            cuts[phase]=r4.diagnostics(verifier,record,partition,phase)
        median=r4.median_iterations(*[v['fit_iterations'] for v in report['measurements']])
        full=report['full_refit'];need(report['actual_median_refit_iterations']==full['fit_iterations']==median,
            'fresh_actual_recursive_median_required')
        for record in report['measurements']+[full]:
            receipt=record.get('release_original_clock',{});terminal=record.get('terminal_resource_observation',{})
            need(record.get('cleanup_confirmed') is True and record.get('strict_runtime') is True
                and record.get('worker_memory_limit_bytes')==1536*2**20
                and record.get('whole_memory_limit_bytes')==2048*2**20
                and record.get('observed_worker_tree_peak_bytes',float('inf'))<=1536*2**20
                and record.get('observed_combined_peak_bytes',float('inf'))<=2048*2**20
                and verified_terminal(record)
                and all(receipt.get(key)==intrinsic[key] for key in
                    ('start_unix','start_monotonic','deadline_unix','deadline_monotonic'))
                and receipt.get('actual_failure_type') is None,'strict_worker_terminal_caps_cleanup_or_original_clock_failed')
        need(Path(full['output_dir']).resolve()==run/'final-fit','fresh_full_refit_directory')
        checked_full=verifier.verify(full,parts['confirmation'],'final',full=True,expected_recipe=task['expected_recipe'])
        need(digest(directory/'submission.csv')==report['submission_sha256'],'published_CSV_hash_changed')
        published=parser.read_csv(directory/'submission.csv',converters=converters)
        need(list(published)==list(sample) and len(published)==len(sample)
            and not published.isna().any().any(),'fullrefit_CSV_shape_or_missing')
        if identifier is not None:need(published[identifier].equals(sample[identifier]),'fullrefit_lexical_sample_order')
        column=spec['output_columns'][0]
        if kind=='classification':
            expected=r4.np.asarray(spec['classes'])[checked_full['test'].argmax(axis=1)][verifier.sample_positions]
            need(r4.np.array_equal(published[column].to_numpy(),expected),'published_class_values_not_actual_fullrefit')
        else:need(r4.np.allclose(published[column].to_numpy(dtype=float),checked_full['test'],atol=1e-12,rtol=1e-12),
            'published_numeric_values_not_actual_fullrefit')
        fitted=[]
        for (folder,phase,full_fit),verified in verifier.records.items():
            record=load(Path(folder)/'result.json');recipe=record['recipe']
            if record.get('components'):continue
            partition=parts['confirmation'] if phase=='confirmation' or full_fit else parts['primary']
            parent=r4.np.arange(len(train),dtype=r4.np.int64) if full_fit else r4.split(partition,len(train))[0]
            receipts=record.get('data_policy_runs');need(type(receipts) is list and receipts,'fitting_receipts_required')
            need(any(v.get('source_rows')==len(parent) and v.get('source_parent_sha256')==r4.canonical(parent.tolist())
                and v.get('synthetic_rows')==0 for v in receipts),'outer_or_full_fitting_lineage_changed')
            if not full_fit:
                need(record.get('early_stopping_source')=='inner_training_holdout'
                    and record.get('inner_split_error') is None,'fitting_only_nested_stopping_required')
            if recipe.get('params',{}).get('loss_profile_id'):
                loss.loss_telemetry(record,recipe,verifier,r4,partition)
            fitted.append(dict(path=str(Path(folder).relative_to(directory)),full_fit=full_fit,
                completed_policy_callbacks=len(receipts),actual_total_learner_fits=None))
        mean=sum(cuts[p]['value'] for p in ('primary','confirmation'))/2
        need(math.isfinite(mean),'nonfinite_metric')
        rows[kind]=dict(cuts=cuts,selected_cut_mean=mean,full_refit_iterations=median,
            full_CSV_sha256=report['submission_sha256'],fitting_receipts=fitted,
            reference_mean=task['reference_mean'],reference_mean_close=r4.close(mean,task['reference_mean']),
            scope='New independently recomputed reused-public two-cut fixed procedure; no hidden-test score')
        r4.pd=pd;check()
    for path,h in {**cfg['immutable_files'],**actual}.items():need(digest(path,check)==h,'posttruth_source_or_core_changed')
    result=dict(schema='br-standard-fixed-artifact-audit-v1',artifact_procedure_passed=True,
        quality_metric={k:r['selected_cut_mean'] for k,r in rows.items()},tasks=rows,
        original_common_seconds=6000,audit_within_original_common_clock=True,
        archive_sha256=cfg['executor']['archive']['sha256'],manifest_sha256=a.manifest_sha256,
        actual_artifact_sha256=actual,manual_R4_source_sha256=R4[1],loss_receipt_source_sha256=LOSS[1],
        audit_only_lexical_class_facade=True,manual_R4_source_bytes_unchanged=True,
        reported_API_calls=0,independent_external_API_measurement=None,new_model_fits=0,
        parent_actual_exit_and_root_closure_required=True,official_hidden_test_score=None,promotion=False,submit=False)
    output=OUT/'independent-audit.json';need(not output.exists(),'exclusive_audit_output');check()
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2,allow_nan=False)
    check();return 0

if __name__=='__main__':raise SystemExit(main())
