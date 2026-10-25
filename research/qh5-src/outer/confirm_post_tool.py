"""Finite actual-wrapper-exit proof inside the original QH1/root windows.

Narrow RQ6 post-tool/C5 projection. Hosted atomic binding has no local binder PID.
This helper never rewrites the original main/root and cannot grant another clock.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,math,os,sys,time

PACKET=Path(__file__).resolve().parent
WORK=PACKET.parent
OUT=WORK/'qh5'
BASE=WORK/'br-standard-release-qualification-next-dev/controller-r5/run_controller.py'
BASE_SHA='d5f41cad6de2168cd520e442223428285dd3714854079d9305dd1b34938abd7d'
ROLE_FLAGS=('post_tool_confirmed','technical_procedure_passed','source_unchanged',
    'current_temporary_absent','current_cleanup_confirmed','inside_original10800',
    'inside_saved_driver_final240','inside_actual_closer_birth60')

def need(value,code):
    if not value:raise RuntimeError(code)

def read(path):return json.loads(Path(path).read_text('utf-8-sig'))

def sha(path,check=lambda:None):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            check();block=stream.read(2**20)
            if not block:break
            h.update(block)
    check();return h.hexdigest()

def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module

def exact_union(original,later):
    need(all(later.get(path)==value for path,value in original.items()),'original_frozen_pin_missing_or_rebound')
    return dict(later)

def window(state,now_unix,now_monotonic,*,reserve=0,begin=None,closer_birth=None):
    values=[state[k] for k in ('start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic','final_deadline_monotonic')]
    need(all(type(v) in (int,float) and math.isfinite(v) for v in values+[now_unix,now_monotonic]),'finite_inherited_clock_required')
    start,initial,wall,end,final=values
    need(wall==start+10800 and end==initial+10800,'original10800_assignment_required')
    need(initial<=now_monotonic and start<=now_unix and final<=end-60,'original_origin_and_saved_final_required')
    need(abs((now_unix-start)-(now_monotonic-initial))<=5,'original_wall_monotonic_disagreement')
    need(now_monotonic+reserve<min(end,final) and now_unix+reserve<min(wall,start+final-initial),
        'original_common_final_reserve_expired')
    if begin is not None:
        need(type(begin) in (int,float) and math.isfinite(begin) and begin<=now_monotonic<begin+30,'posttool_observer30_expired')
    if closer_birth is not None:
        need(type(closer_birth) in (int,float) and math.isfinite(closer_birth) and now_unix<closer_birth+60,'actual_closer_birth60_expired')

def actual_wrapper(exit_code,tool):
    need(type(exit_code) is int and exit_code==0 and type(tool) is str and tool
         and 'PENDING' not in tool,'actual_wrapper_exit0_required')
    return dict(exit_code=exit_code,tool=tool)

def full_known_union(fresh,root,preparers,ids):
    known=ids(fresh['known_identities'])
    need(len(known)==fresh['known_count']==len(fresh['known_identities']),'exact_saved_atomic_known_array_required')
    need(ids(root['owned_identities']+root['closure_preparer_identities'])<=known,'complete_root_closer_union_required')
    known|=ids(fresh['wrapper_preparer_identities'])
    need(not (known&ids(preparers)),'no_live_current_observer_in_prior_absence_scope')
    return known

def revoked(value,error):
    answer=dict(value)
    for key in ROLE_FLAGS:answer[key]=False
    for key in ('metrics','quality_metric','qualified_ML_metrics'):answer[key]=None
    if 'readiness' in answer:
        answer['readiness']='NOT_READY';answer['missing_bindings']=list(answer.get('missing_bindings',[]))+['terminal_helper_failure']
    answer.update(helper_failed=True,primary_exception_type=type(error).__name__,secondary_exception_type=getattr(error,'helper_secondary_exception_type',None))
    return answer

def publish_checked(value,write,check):
    """Revoke this helper's own output if any post-publication check fails."""
    try:
        check();write(value,True);check()
    except BaseException as primary:
        negative=revoked(value,primary)
        try:write(negative,False)
        except BaseException as secondary:
            try:primary.helper_secondary_exception_type=type(secondary).__name__
            except BaseException:pass
        raise

def save_json(path,value,exclusive):
    path=Path(path)
    if exclusive:need(not path.exists(),'exclusive_new_helper_output_required')
    pending=path.with_name(path.name+'.pending')
    with pending.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(pending,path)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('binding','binding-sha256','self-sha256','wrapper-tool'):parser.add_argument('--'+key,required=True)
    parser.add_argument('--wrapper-exit-code',type=int,required=True)
    parser.add_argument('--launch-parent-pid',type=int,required=True)
    parser.add_argument('--launch-parent-create-time',type=float,required=True)
    args=parser.parse_args();begin=time.monotonic();destination=OUT/'actual-wrapper-exit-confirmation.json'
    result=dict(schema='qwen-three-hour-actual-wrapper-exit-confirmation-v1',post_tool_confirmed=False)
    try:
        need(sha(BASE)==BASE_SHA,'C5_changed');base=imported('_qh1_post_C5',BASE)
        import psutil
        preparers,chain=base.capture(psutil,args.launch_parent_pid,args.launch_parent_create_time)
        early=OUT/'post-tool-preparer-identity.json'
        save_json(early,dict(identities=preparers,launch_parent_observation=chain),True)
        need(chain.get('verified') is True,'actual_posttool_chain_unconfirmed')
        wrapper=actual_wrapper(args.wrapper_exit_code,args.wrapper_tool)
        need(Path(args.binding).is_absolute() and sha(args.binding)==args.binding_sha256
             and sha(__file__)==args.self_sha256,'exact_atomic_binding_and_post_source_required')
        binding=read(args.binding)
        need(binding.get('schema')=='qwen-three-hour-atomic-root-private-v1'
             and binding.get('readiness')=='READY_REVIEWED_FROZEN' and binding.get('missing_bindings')==[]
             and binding.get('output')==str(OUT),'actual_atomic_binding_NOT_READY')
        manifest=Path(binding['manifest']['path'])
        need(manifest.is_absolute() and sha(manifest)==binding['manifest']['sha256'],'actual_main_manifest_changed')
        cfg=read(manifest);pins=exact_union(cfg['immutable_files'],binding['immutable_files'])
        need(pins.get(str(Path(__file__).resolve()))==args.self_sha256 and pins.get(str(BASE))==BASE_SHA,'post_helper_in_frozen_source_union_required')
        need(binding.get('post_tool')==dict(path=str(Path(__file__).resolve()),sha256=args.self_sha256),'exact_hosted_binding_post_helper_required')
        fresh_path=OUT/'root-confirmation.json';root_path=OUT/'terminal-root-closure.json';campaign=OUT/'campaign.json'
        fresh,root,state=read(fresh_path),read(root_path),read(campaign)
        need(binding['campaign']==dict(path=str(campaign),sha256=sha(campaign)),'actual_terminal_campaign_changed')
        need(fresh.get('schema')=='qwen-three-hour-atomic-root-confirmation-v1'
             and fresh.get('root_sha256')==sha(root_path) and fresh.get('technical_procedure_passed') is True
             and fresh.get('actual_closer_exit')==0 and fresh.get('known_exact_live')==fresh.get('uncertain')==fresh.get('errors')==[],
             'positive_atomic_root_required')
        need(all(fresh.get(k) is True for k in ('source_unchanged','current_temporary_absent','current_cleanup_confirmed',
             'inside_actual_closer_birth60','inside_original10800','inside_existing_driver_final240')),'atomic_flags_required')
        need(root.get('schema')=='qwen-three-hour-root-closure-v1' and root.get('manifest_sha256')==binding['manifest']['sha256']
             and root.get('technical_procedure_passed') is True and all(root.get(k) is True for k in
             ('cleanup_confirmed','source_unchanged','temporary_cleanup_confirmed'))
             and root.get('uncertain_owned')==root.get('changed_source_or_core')==[],'qualified_root_flags_required')
        actual=fresh['actual_driver']
        need(root.get('actual_exec_session')==actual['session'] and actual['exit_code']==0
             and root.get('actual_exec_exit_code_observed_by_root')==0 and root.get('actual_tool_evidence')==actual['tool'],
             'actual_driver_root_lineage_changed')
        modules={}
        for key in ('owner','sampling'):
            relative,expected=base.HELPERS[key]
            need(pins.get(str(WORK/relative))==expected and sha(WORK/relative)==expected,'qualified_helper_changed')
            modules[key]=imported('_qh1_post_'+key,WORK/relative)
        statistics={};pulse=base.guard(begin,state['common_deadline_monotonic'],state['absolute_deadline_unix'],
            modules['owner'],preparers,statistics,sampling=modules['sampling'])
        def check():
            window(state,time.time(),time.monotonic(),begin=begin,closer_birth=fresh['actual_closer_birth']);pulse()
        pulse(force=True);check();known=full_known_union(fresh,root,preparers,base.ids)
        driver_ref=binding['driver'];need(pins.get(driver_ref['path'])==driver_ref['sha256'] and sha(driver_ref['path'])==driver_ref['sha256'],'frozen_main_source_changed')
        need(Path(driver_ref['path'])==PACKET/'run_campaign.py','fixed_current_outer_driver_required')
        driver=imported('_qh1_post_source_driver',driver_ref['path']);inherited=driver.predecessor(cfg,check)
        need(inherited<=known,'complete_inherited_and_later_preparer_union_required')
        bound={str(manifest):binding['manifest']['sha256'],str(Path(args.binding)):args.binding_sha256,
            str(root_path):sha(root_path),str(fresh_path):sha(fresh_path),str(campaign):binding['campaign']['sha256'],str(early):sha(early)}
        for path,expected in bound.items():
            need(path not in pins or pins[path]==expected,'proof_or_source_pin_collision');pins[path]=expected
        def frozen():
            for path,expected in pins.items():need(sha(path,check)==expected,'saved_source_input_changed')
            check()
        base.absent(modules['owner'],known,check);frozen()
        temp=state.get('temporary_root');need(temp is None or not Path(temp).exists(),'owned_temporary_root_remains')
        base.absent(modules['owner'],known,check);pulse(force=True);check()
        result=dict(schema='qwen-three-hour-actual-wrapper-exit-confirmation-v1',root_sha256=sha(root_path),
            root_confirmation_sha256=sha(fresh_path),actual_driver=actual,actual_wrapper=wrapper,
            known_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],known_count=len(known),
            known_exact_live=[],uncertain=[],source_unchanged=True,current_temporary_absent=True,current_cleanup_confirmed=True,
            post_tool_confirmed=True,inside_original10800=True,inside_saved_driver_final240=True,inside_actual_closer_birth60=True,
            observation_seconds=time.monotonic()-begin,post_tool_preparer_identities=preparers,launch_parent_observation=chain,
            resource_observation={k:v for k,v in statistics.items() if not k.startswith('_')},actual_observer_tool_exit_pending=True,
            promotion=False,submit=False)
        def terminal():frozen();base.absent(modules['owner'],known,check);pulse(force=True);check()
        publish_checked(result,lambda value,exclusive:save_json(destination,value,exclusive),terminal)
        print(json.dumps(dict(post_tool_confirmed=True,known_count=len(known),receipt_sha256=sha(destination))));check();return 0
    except BaseException as primary:
        try:save_json(destination,revoked(result,primary),False)
        except BaseException as secondary:
            try:primary.helper_secondary_exception_type=type(secondary).__name__
            except BaseException:pass
        raise

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        print(json.dumps(dict(post_tool_confirmed=False,error_type=type(error).__name__,
            secondary_exception_type=getattr(error,'helper_secondary_exception_type',None))));raise SystemExit(1)
