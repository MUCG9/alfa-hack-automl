"""One4800-second task leaf for the reviewed outer10800 controller.

This entry never creates an overall clock, input discovery, split or evaluator.
The outer C5 caller must admit the exact tasks/sources after the archive repair,
prepare both frozen cuts, and supply the original actual admission tuple.
"""
from pathlib import Path
from contextlib import contextmanager
from contextvars import ContextVar
import argparse
import hashlib
import importlib.util
import json
import math
import os
import sys
import time

HERE=Path(__file__).resolve().parent
COOR_SHA='bd864b13460d31176d57e1dbddbe179ad8e6911163b117e3f9698228c5540f76'
OWNER_SHA='8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8'
PROCESS_SHA='fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d'


def need(value,code):
    if not value:raise RuntimeError(code)


def sha(path,check=lambda:None):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            check();block=stream.read(2**20)
            if not block:break
            h.update(block)
    check();return h.hexdigest()


def save(path,value):
    path=Path(path);temporary=path.with_name(path.name+'.pending')
    with temporary.open('x',encoding='utf-8') as stream:json.dump(value,stream,indent=2,ensure_ascii=False,allow_nan=False)
    os.replace(temporary,path)


def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


@contextmanager
def worker_origin_scope(runtime):
    """Trusted caller only; reuse existing additive parent facts, no worker change."""
    marker=getattr(runtime,'_HPO_FAIR_RESERVE_PROVENANCE',None)
    need(type(marker) is ContextVar,'typed_existing_worker_origin_marker_required')
    token=marker.set(True)
    try:yield
    finally:marker.reset(token)


def canonical_metadata(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
        separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()


def persist_parent_callback(result,folder,index,phase,cut,*,task_manifest,source_union,spec,recipe,check):
    """Save the exact returned parent record, separate from child result.json."""
    need(type(result) is dict and type(index) is int and index>0
         and type(phase) is str and phase,'typed_actual_parent_callback_required')
    folder=Path(folder).resolve();need(folder.is_absolute(),'absolute_callback_folder_required')
    def actual_ref(path):
        check()
        return dict(path=str(path),sha256=sha(path,check)) if path.is_file() else None
    record=dict(schema='qwen-three-hour-parent-result-v1',callback_index=index,phase=phase,
        task_manifest=dict(task_manifest),cut=dict(cut),
        source_union_canonical_sha256=canonical_metadata(source_union),
        spec_canonical_sha256=canonical_metadata(spec),recipe_canonical_sha256=canonical_metadata(recipe),
        raw_job=actual_ref(folder/'job.json'),raw_result=actual_ref(folder/'result.json'),result=result)
    target=folder/'parent-result.json';check();save(target,record);check()
    return dict(path=str(target),sha256=sha(target,check))


def run(a):
    need(Path(a.manifest).is_absolute() and sha(__file__)==a.self_sha256,'fixed_task_entry_source_required')
    manifest=Path(a.manifest);need(manifest.stat().st_size<=2**20 and sha(manifest)==a.manifest_sha256,'exact_private_task_manifest_required')
    cfg=json.loads(manifest.read_text('utf-8'))
    need(cfg.get('schema')=='qwen-three-hour-task-private-v1'
         and cfg.get('readiness')=='READY_SOURCE_REVIEWED_FROZEN' and cfg.get('missing_bindings')==[],
         'NOT_READY_archive_repair_outer_source_root_approval_and_actual_clock_required')
    timing=cfg['clock']
    def original_clock_only():
        now=time.monotonic();wall=time.time()
        need(all(type(v) in (int,float) and math.isfinite(v) for v in (*timing.values(),now,wall)),'finite_clock_required')
        need(timing['common_deadline_monotonic']==timing['start_monotonic']+10800
             and timing['absolute_deadline_unix']==timing['start_unix']+10800
             and timing['task_deadline_monotonic']==timing['task_start_monotonic']+4800
             and timing['task_deadline_unix']==timing['task_start_unix']+4800,'assigned_original_common_and_equal_task_required')
        need(now<min(timing['task_deadline_monotonic'],timing['common_deadline_monotonic'])
             and wall<min(timing['task_deadline_unix'],timing['absolute_deadline_unix']),'original_task_common_deadline')
        need(abs((timing['common_deadline_monotonic']-now)-(timing['absolute_deadline_unix']-wall))<=5,'common_wall_mono_disagreement')
    original_clock_only()
    root=Path(cfg['canonical_root']);output=Path(cfg['output'])
    need(root.is_absolute() and output.is_absolute() and not output.exists(),'exclusive_absolute_bound_task_root_required')
    pins=cfg['immutable_files'];need(type(pins) is dict and pins,'complete_immutable_source_input_split_union_required')
    for path,expected in pins.items():need(Path(path).is_absolute() and sha(path,original_clock_only)==expected,'source_input_or_split_pin_changed')
    need(pins.get(cfg['python'])=='d59c9a894b319828d023f3aa83d9a3488d2339f9e27e60e49b02abb0d53cf538',
         'exact_previously_qualified_python_launcher_required')
    need(pins.get(str(Path(__file__).resolve()))==a.self_sha256,'self_in_full_immutable_union_required')
    for name in ['research_loop.py','r5_worker_runtime.py','r5_resources.py','verified_sampling.py','gateway_child.py','provider_environment.py']:
        need(str(HERE/name) in pins,'all_fixed_researcher_dependencies_required')
    for key,expected in [('coordinator',COOR_SHA),('owner',OWNER_SHA),('processes',PROCESS_SHA)]:
        ref=cfg['helpers'][key];need(pins.get(ref['path'])==ref['sha256']==expected,'exact_qualified_helper_required')
    need(pins.get(str(root/'agent_worker.py')) is not None
         and pins.get(str(root/'src/automl/infrastructure/processes.py'))=='9f84f64199b63dc4cef095e026d23084e338f1e42a97d5b4bd083e10f687bdb3',
         'candidate_current_processes_distinct_from_historical_guard')
    need(cfg['task']['source_unchanged'] is True and cfg['task']['authority_resolved'] is True
         and cfg['task']['context_flag'] is False and cfg['task']['selector_cache_flag'] is False,
         'explicit_qualified_strong_task_authority_and_factors_required')
    need(cfg['spec']['kind']==cfg['task']['kind'] and cfg['spec']['metric']==cfg['task']['metric']
         and cfg['spec']['greater_is_better']==cfg['task']['greater_is_better']
         and cfg['spec']['features']==cfg['task']['features']
         and not set(cfg['task']['features'])&set(cfg['spec'].get('all_targets',[cfg['spec']['target']])+[cfg['spec'].get('id')]),
         'exact_shared_MetricSpec_features_and_protected_roles_required')
    if cfg['task']['kind']=='classification':
        need(cfg['spec']['classes']==cfg['task']['classes'] and all(type(c) is str for c in cfg['task']['classes']),
             'exact_lexical_class_order_required')
    strong=cfg['strong_authority']
    need(pins.get(strong['path'])==strong['sha256'],'strong_recipe_actual_source_ref_required')
    authority=json.loads(Path(strong['path']).read_text('utf-8'))
    need(authority.get('schema')=='qwen-three-hour-strong-recipe-authority-v1'
         and authority.get('kind')==cfg['task']['kind'] and authority.get('metric')==cfg['task']['metric']
         and authority.get('recipe')==cfg['task']['strong_recipe'],'exact_reviewed_strong_complete_recipe_required')
    for cut in cfg['task']['cuts']:
        need(Path(cut['path']).is_absolute() and pins.get(cut['path'])==cut['sha256'],'fixed_actual_cut_byte_binding_required')
    # Numerical/task/worker imports occur only AFTER the entire admitted union.
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS'):
        os.environ[name]='2'
    os.environ['AUTOML_THREADS']='2';sys.dont_write_bytecode=True
    sys.path.insert(0,str(HERE));sys.path.insert(0,str(root/'src'))
    import research_loop as policy
    import r5_worker_runtime as runtime
    from provider_environment import provider_credentials
    from automl.search.policy import normalize,signature
    from automl.infrastructure.run_budget import current_budget
    need(current_budget() is None,'legacy_RunBudget_cap_and_clock_must_not_wrap_task')
    need(signature(cfg['task']['strong_recipe'])==authority['recipe_signature'],'strong_raw_executable_signature_changed')
    compiler_ref=cfg['trusted_DSL_compiler'];need(pins.get(compiler_ref['path'])==compiler_ref['sha256'],'trusted_DSL_compiler_required')
    compiler=imported('_three_hour_trusted_DSL',compiler_ref['path']).compile_features
    coor=imported('_three_hour_verified_coordinator',cfg['helpers']['coordinator']['path'])
    owner=imported('_three_hour_known_owner',cfg['helpers']['owner']['path'])
    processes=imported('_three_hour_historical_process_guard',cfg['helpers']['processes']['path'])
    output.mkdir();clock=runtime.ReleaseClock(4800,output,origin=(timing['task_start_unix'],timing['task_start_monotonic']))
    class View:
        def check(self):original_clock_only();clock.check();original_clock_only()
        def remaining(self):self.check();return clock.remaining()
        def common_remaining(self):self.check();return min(timing['common_deadline_monotonic']-time.monotonic(),timing['absolute_deadline_unix']-time.time())
    view=View()
    def frozen(parent_end=None,code='source_or_phase_changed'):
        for path,expected in pins.items():
            need(sha(path,view.check)==expected,'immutable_union_changed')
            if parent_end is not None:need(time.monotonic()<parent_end,code)
        need(sha(manifest,view.check)==a.manifest_sha256,'task_binding_changed')
    state={'supervisors':[],'active_supervisor':None,'error_history':[],'_manifest':cfg,
        '_pulse':view.check,'_resource_checkpoint':clock._resource_checkpoint}
    def persist_supervision():save(output/'supervision.json',{k:v for k,v in state.items() if not k.startswith('_')})
    provider_count=0;worker_count=0
    def gateway(prompt,context,timeout):
        nonlocal provider_count
        view.check();provider_count+=1;need(provider_count<=64,'gateway64_hardcap')
        start=time.monotonic();folder=output/('gateway-'+str(provider_count));folder.mkdir()
        request=folder/'request.json';result=folder/'result.json'
        provider_clock={k:timing[k] for k in ('start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic','task_deadline_monotonic')}
        provider_clock['provider_deadline_monotonic']=start+timeout
        save(request,dict(schema='qwen-three-hour-single-gateway-v1',call_number=provider_count,
            clock=provider_clock,source_files={p:h for p,h in pins.items() if Path(p).suffix=='.py'},
            canonical_root=str(root),output=str(result),timeout=timeout,prompt=prompt,context=context))
        request_sha=sha(request,view.check)
        argv=[cfg['python'],'-B','-X','utf8',str(HERE/'gateway_child.py'),'--request',str(request),
            '--request-sha256',request_sha,'--self-sha256',pins[str(HERE/'gateway_child.py')]]
        receipt=folder/'supervisor.json'
        with provider_credentials(coor):
            observed=coor.supervise(argv,output,receipt,'provider-'+str(provider_count),start,timeout+10,timeout+5,
                timing['task_deadline_monotonic'],timing['task_deadline_unix'],0,state,persist_supervision,
                frozen,owner,processes,[],solver_seconds=None)
        view.check()
        need(observed.get('status')=='ok' and observed.get('exit_code')==0
             and observed.get('cleanup_confirmed') is True and not observed.get('error_history'),
             'provider_owned_supervision_or_cleanup_failed')
        need(result.stat().st_size<=65536 and sha(request,view.check)==request_sha,'bounded_provider_request_result_required')
        row=json.loads(result.read_text('utf-8'))
        need(row.get('schema')=='qwen-three-hour-single-gateway-result-v1'
             and row.get('request_sha256')==request_sha and row.get('call_number')==provider_count,'provider_actual_request_binding_failed')
        return row['content'],row['call']
    def worker(recipe,cut,timeout,phase,fit_iterations=None):
        nonlocal worker_count
        worker_count+=1;view.check();frozen()
        need(sha(cut['path'],view.check)==cut['sha256'],'cut_changed_before_worker')
        with worker_origin_scope(runtime):
            result=runtime.run_release_worker(cfg['spec'],recipe,output/('worker-'+str(worker_count)),cut['path'],timeout,
                clock=clock,full_fit=phase=='full-refit',fit_iterations=fit_iterations)
        view.check();frozen();need(sha(cut['path'],view.check)==cut['sha256'],'cut_changed_after_worker')
        result['split_sha256']=cut['sha256']
        result['parent_callback_receipt']=persist_parent_callback(result,output/('worker-'+str(worker_count)),
            worker_count,phase,cut,task_manifest=dict(path=str(manifest),sha256=a.manifest_sha256),
            source_union=pins,spec=cfg['spec'],recipe=recipe,check=view.check)
        return result
    report=policy.run_task(cfg['task'],view,gateway,worker,normalize,signature,compiler,
        lambda row:save(output/'report.json',row))
    # Full outer all-task seal+independent rescore remains required. This process
    # cannot issue global quality/promotion/root-cleanup approval.
    view.check();frozen();save(output/'task-terminal.json',dict(schema='qwen-three-hour-task-terminal-v1',
        status=report['status'],original_clock=clock.receipt(),manifest_sha256=a.manifest_sha256,
        independently_qualified=False,promotion=False,whole_campaign_root_pending=True))
    view.check();return 0


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',required=True);parser.add_argument('--manifest-sha256',required=True);parser.add_argument('--self-sha256',required=True)
    raise SystemExit(run(parser.parse_args()))
