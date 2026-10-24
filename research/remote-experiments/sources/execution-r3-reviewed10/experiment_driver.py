"""Opt-in, fixed six-classification component caller. DEFAULT INSPECTION ONLY.

SOURCE_ONLY jobs always denied. This source task never invokes execute(). Future
prepared authority/bindings must be independently pinned by the primary first.
"""
from pathlib import Path
import copy,json,os,sys,time
import portable_harness as h
import component_audit as audit

PROTOCOL_SHA='81cd9df5566f5453600117a5cb902f8ca7d37dbee3c9ee2347ff5100a9baff46'
SOURCE_SHA='0ed0e74706b6620ffc1b29216a8f2c00ab40771ef7ebaecb0cc61092f78c4bae'
INPUT_SHA='247ecf4d3ce8670be0573ed0808b0cfce9352babb78ca7cc02c9103ca3bee4c7'
NATIVE_SHA='f5ad8c55aec198b689abf4bd8cf4ed0caf967fcd9f0d9f6db12f70513e1a60e5'
CONTROL_SHA='118ba895201bef8149fdd6bb88464bb2e02b23985a34629a47d52df5e5536f46'
QUEUE_SHA='d42cb979db953eeffabfa65ee2a40d8763dfd835f91ce35149327f3d181e4c49'
ORDER=[(cut,arm) for cut in (42,43) for arm in ('strong','linear','rbf')]
KEYS=[f'classification{cut}-{arm}' for cut,arm in ORDER]
def inspect_plan():
    return dict(mode='inspection_only',keys=KEYS,model_processes=0,learner_fits=0,api_calls=0,
                future_common_seconds=5400,static_fit_cap=16,requires_separate_bounded_READY_job=True)
def local(root,relative):
    p=Path(relative);result=(Path(root)/p).resolve()
    h.need(not p.is_absolute() and '\\' not in str(p) and '..' not in p.parts and result.is_relative_to(Path(root).resolve()),'native_relative_path_required')
    return result
def reserve(clock,index):
    h.need(type(index) is int and 0<=index<6,'fixed_slot_index')
    # Includes THIS full parent, all future fixed parents, audit, cleanup and spare.
    clock.tick((6-index)*480+600+300+1020)

def validate_matrix(authority, protocol, native, source, inputs, control):
    """Pure structural checks BEFORE Popen or label-bearing CSV parsing."""
    h.need(protocol['cuts']==[42,43] and protocol['task_kind']=='classification','fixed_class_protocol')
    h.need(protocol['budget']['common_seconds']==5400 and protocol['budget']['maximum_learner_fit_calls']==16,'fixed_budget')
    h.need(source['source_archive_sha256']=='ca8a0898af84a4ddb8039343f94edc73aa7360005f215125907a34427a3c6d5c'
           and len(source['flat_files_sha256'])==70,'fixed_original_source')
    h.need(authority['source_manifest']==source,'authority_source_binding')
    h.need(protocol['recipes']['strong']==control['classification'],'protected_first_SINGLE')
    components=authority['components'];h.need(len(components)==6,'exact_six_components')
    h.need([v['key'] for v in components]==KEYS and len({v['output_relative'] for v in components})==6,'unique_key_folder_order')
    spec=authority['spec']
    h.need(spec['kind']=='classification' and spec['metric']=='macro_f1' and spec['prediction_type']=='value','classification_value_spec')
    roles=authority['roles'];audit.native_roles(spec,roles)
    h.need(set(roles)=={'train','test','sample_submission','data_dictionary'},'exact_four_roles')
    approved={v['name']:v['sha256'] for v in inputs['files'] if v['task']=='multiclass'}
    h.need(authority['input_sha256']=={r:approved[r+'.csv'] for r in roles},'approved_exact_input_hashes')
    h.need(authority['task_sha256']==approved['task.md'],'approved_task_hash')
    for index,(entry,(cut,arm)) in enumerate(zip(components,ORDER)):
        expected_cut=next(v for v in native['cuts'] if v['kind']=='classification' and v['cut']==cut)
        h.need(entry['native_cut']==expected_cut and entry['arm']==arm and entry['cut']==cut,'exact_native_cut_arm')
        h.need(entry['recipe']==protocol['recipes'][arm],'exact_raw_recipe')
        h.need(entry['output_relative']=='cores/'+KEYS[index] and entry['split_relative']==f'splits/classification-{cut}.npz','fixed_component_paths')
        h.need(entry['job_relative']=='jobs/'+KEYS[index]+'.json' and entry['spec_canonical_sha256']==h.canonical(spec),'fixed_job_spec')
        h.need(entry['threads']==2 and entry['full_fit'] is False,'fixed_leaf_caps')
    expected={name:dict(candidate={'primary':f'classification42-{candidate}','confirmation':f'classification43-{candidate}'},
                             control={'primary':f'classification42-{reference}','confirmation':f'classification43-{reference}'})
              for name,candidate,reference in [('rbf_vs_fresh_strong','rbf','strong'),('linear_vs_fresh_strong','linear','strong'),('rbf_vs_matched_linear','rbf','linear')]}
    h.need(authority['comparisons']==expected,'fixed_three_contrasts_cut_mapping')
    return True

def fixed_fit_count(folder,arm):
    """Only successful sealed results permit exact actual learner-call counts."""
    folder=Path(folder);record=h.load(folder/'result.json')
    if record.get('status')!='ok':return None
    if arm in ('linear','rbf'):
        h.need(record.get('fit_iterations')==1 and record.get('representation'),'successful_fixed_head_required')
        return 1
    h.need(arm=='strong' and record['recipe']['params']['feature_views']=='categorical_te_pair','fixed_strong_count')
    total=0;seen=set()
    for index in (0,1):
        leaf=(folder/f'component-{index}').resolve();h.need(leaf not in seen,'unique_actual_view_leaf');seen.add(leaf)
        v=h.load(leaf/'result.json');h.need(v['status']=='ok','successful_actual_view_leaf')
        runs=v.get('data_policy_runs');h.need(isinstance(runs,list) and 1<=len(runs)<=3 and all(isinstance(r,dict) for r in runs),'successful_fit_policy_list_bound')
        total+=len(runs)
    h.need(2<=total<=6,'strong_actual_fit_count_cap');return total

def verify_prepared(root, authority, binding, clock):
    h.need(h.canonical(authority)==binding['prepared_authority_sha256'],'independent_prepared_authority_pin')
    spec=authority['spec'];audit.native_roles(spec,authority['roles'])
    h.need(h.canonical(spec)==binding['spec_canonical_sha256'],'pinned_native_spec')
    execution=authority['source_inventories'][authority['execution_relative']]
    h.need(execution==binding['execution_sha256'] and set(execution)=={'portable_harness.py','component_audit.py','experiment_driver.py','pure_contracts.py'},'complete_four_source_binding')
    h.need(authority['source_inventories'][authority['library_relative']]==audit.LIBRARIES,'complete_two_library_binding')
    for role,path in authority['roles'].items():
        h.need(Path(path).resolve()==local(root,'inputs/'+role+'.csv'),'native_role_expected_location')
        h.need(h.sha(path,clock.tick)==authority['input_sha256'][role],'input_bytes_changed')
    h.need(Path(spec['task_path']).resolve()==local(root,'inputs/task.md') and Path(spec['root']).resolve()==local(root,'inputs'),'native_task_spec_paths')
    h.need(h.sha(local(root,'inputs/task.md'),clock.tick)==authority['task_sha256'],'task_bytes_changed')
    for prefix,seals in authority['source_inventories'].items():h.check_inventory(local(root,prefix),seals,clock.tick)
    for item in authority['components']:
        p=local(root,item['job_relative']);h.need(h.sha(p,clock.tick)==item['private_job_sha256'],'private_job_changed')
        leaf=h.load(p)
        h.need(leaf['spec']==spec and leaf['recipe']==item['recipe'] and leaf['threads']==2 and leaf['full_fit'] is False,'exact_native_leaf')
        h.need(Path(leaf['output_dir']).resolve()==local(root,item['output_relative']) and Path(leaf['split_path']).resolve()==local(root,item['split_relative']),'exact_native_leaf_paths')
        h.need(h.sha(local(root,item['split_relative']),clock.tick)==item['native_cut']['native_profiles']['Linux']['raw_npz_sha256'],'native_raw_split_changed')
    h.need(binding['components']==authority['components'],'all_six_independently_bound')

def audit_matrix(root, authority, binding, terminal_slots, libroot, clock):
    """No label parsing for missing/failed/unattempted slots or unqualified driver."""
    h.need([s['key'] for s in terminal_slots]==KEYS,'all_six_terminal_slots')
    if any(s['status']!='completed' or s['fits'] is None for s in terminal_slots):
        return dict(status='incomplete_matrix',qualified=False,metrics=None,slots=terminal_slots)
    actual=copy.deepcopy(authority)
    for item,slot in zip(actual['components'],terminal_slots):
        final=local(root,slot['driver_relative']);raw=local(root,slot['terminal_relative'])
        h.need(h.sha(final,clock.tick)==slot['driver_sha256'] and h.sha(raw,clock.tick)==slot['terminal_sha256'],'parent_terminal_seals')
        final_value=h.load(final)
        h.need(final_value['status']=='completed' and final_value['cleanup_confirmed'] is True and final_value['original_deadline']==clock.wall_deadline,'final_driver_qualification')
        h.need(final_value['raw_supervisor_sha256']==slot['terminal_sha256'],'raw_final_driver_binding')
        item.update(core_sha256=slot['core_sha256'],terminal_relative=slot['terminal_relative'],terminal_sha256=slot['terminal_sha256'])
        h.check_inventory(local(root,item['output_relative']),slot['core_sha256'],clock.tick)
    # Actual terminal inventories are sealed by the owned parent, not model output.
    # A separately pinned parent journal authority binds their canonical hash.
    journal=local(root,'terminal-journal.json');h.need(h.load(journal)==terminal_slots,'sealed_parent_terminal_journal')
    sealed=h.canonical(actual)
    return audit.audit(root,actual,sealed,libroot,clock)

def execute(repo,queue_file,job_id,worker,claim_sha,root,prepared_path,clock_path,common_clock,clock_context):
    """Prepared prospective caller; never used in05. No arbitrary recipes/argv."""
    clock=common_clock
    h.need(clock is not None and clock.context==clock_context,'explicit_execute_original_clock')
    h.need(Path(clock_path).resolve()==Path(clock_context['clock_path']).resolve(),'execute_clock_path')
    clock.tick()
    claim,job,binding=h.queue_admission(repo,queue_file,QUEUE_SHA,job_id,worker,claim_sha,clock)
    h.need(job['kind']=='bounded_experiment' and job['readiness']=='ready','separate_bounded_READY_required')
    h.need(job['caps']==dict(wall_seconds=5400,cpu_threads=2,worker_memory_mib=1536,whole_memory_mib=2048,max_fits=16,max_api_calls=0),'exact_future06_caps')
    root=Path(root).resolve();clock.tick()
    h.need(clock.wall_deadline==claim['deadline_unix'],'execute_original_deadline')
    # Immutable primary-pinned metadata copied to the prepared root before claim.
    refs={'protocol.json':PROTOCOL_SHA,'source-manifest.json':SOURCE_SHA,'approved-input-manifest.json':INPUT_SHA,
          'native-cut-contract-v3-r2.json':NATIVE_SHA,'protected-single-controls.json':CONTROL_SHA}
    docs={}
    for name,pin in refs.items():
        p=local(root,'metadata/'+name);h.need(h.sha(p,clock.tick)==pin,'exact_protocol_manifest_pin');docs[name]=h.load(p)
    authority=h.load(prepared_path)
    validate_matrix(authority,docs['protocol.json'],docs['native-cut-contract-v3-r2.json'],docs['source-manifest.json'],docs['approved-input-manifest.json'],docs['protected-single-controls.json'])
    verify_prepared(root,authority,binding,clock)
    h.need(time.time()<claim['claimed_at_unix']+600,'original_setup600_exceeded')
    slots=[];systemic=False;total_fits=0;shared=Path(repo).resolve().parent/'remote-research-state/experiment.lock'
    root_identity=dict(pid=os.getpid(),create_time=h.psutil.Process().create_time())
    with h.host_lock(shared) as held:
        for index,item in enumerate(authority['components']):
            if systemic:
                slots.append(dict(key=item['key'],status='not_attempted_due_prior_technical_failure',fits=None,metric=None));continue
            try:
                reserve(clock,index);slot_parent_end=time.monotonic()+480;slot_fits=None
                verify_prepared(root,authority,binding,clock)
                output=local(root,item['output_relative']);h.need(not output.exists(),'fresh_component_folder_required');output.mkdir(parents=True)
                # Original worker/R4 requires the exact top job beside core results.
                import shutil
                shutil.copyfile(local(root,item['job_relative']),output/'job.json')
                receipt=local(root,'terminal/'+item['key']+'.json');receipt.parent.mkdir(exist_ok=True)
                final=h.model_driver(repo,queue_file,QUEUE_SHA,job_id,worker,claim_sha,local(root,authority['algorithm_relative']),docs['source-manifest.json'],
                                     local(root,item['job_relative']),item['private_job_sha256'],clock_path,shared,receipt,held_lock=held,common_clock=clock,parent_deadline=slot_parent_end)
                raw=h.load(receipt);driver=receipt.with_name(receipt.stem+'.driver.json')
                clean_failed=final['status']=='failed' and final['cleanup_confirmed'] is True and raw.get('exit_code') not in (0,None)
                if final['status']!='completed':
                    failed=dict(key=item['key'],status=final['status'],fits=None,metric=None,first_error=final.get('first_error'),secondary_errors=final.get('secondary_errors',[]),
                                core_sha256=h.inventory(output,clock.tick),terminal_relative=str(receipt.relative_to(root)),terminal_sha256=h.sha(receipt,clock.tick),
                                driver_relative=str(driver.relative_to(root)),driver_sha256=h.sha(driver,clock.tick))
                    clock.tick();h.need(time.monotonic()<slot_parent_end,'failed_core_seal_parent480_exceeded');slots.append(failed)
                    if not clean_failed:systemic=True
                    continue
                fits=fixed_fit_count(output,item['arm']);slot_fits=fits;total_fits+=fits;h.need(total_fits<=16,'actual_learner_fit_cap')
                slot=dict(key=item['key'],status='completed',fits=fits,metric=None,core_sha256=h.inventory(output,clock.tick),
                                  terminal_relative=str(receipt.relative_to(root)),terminal_sha256=h.sha(receipt,clock.tick),
                                  driver_relative=str(driver.relative_to(root)),driver_sha256=h.sha(driver,clock.tick))
                clock.tick();h.need(time.monotonic()<slot_parent_end,'core_seal_parent480_exceeded')
                slot['core_seal_finished_unix']=time.time();slot['parent_deadline_monotonic']=slot_parent_end;slots.append(slot)
            except Exception as exc:
                systemic=True;slots.append(dict(key=item['key'],status='blocked',fits=slot_fits,metric=None,first_error=dict(code=type(exc).__name__,detail=str(exc))))
        h.write_new(root/'terminal-journal.json',slots);verify_prepared(root,authority,binding,clock);clock.tick(600+300+1020)
        all_complete=all(s['status']=='completed' for s in slots)
        audit_result=None;audit_receipt=None
        if all_complete:
            handoff=clock.snapshot(parent_deadline=min(clock.mono_deadline,time.monotonic()+570))
            request=dict(repo=str(Path(repo).resolve()),queue_file=str(Path(queue_file).resolve()),job_id=job_id,worker=worker,claim_sha=claim_sha,
                         root=str(root),prepared_path=str(Path(prepared_path).resolve()),clock_path=str(Path(clock_path).resolve()),
                         terminal_journal_sha256=h.sha(root/'terminal-journal.json',clock.tick),clock_context=clock_context,
                         clock_handoff=handoff,clock_handoff_sha256=h.canonical(handoff))
            request_path=root/'audit-request.json';h.write_new(request_path,request);request_sha=h.sha(request_path,clock.tick)
            with h.tempfile.TemporaryDirectory(prefix='automl-audit-') as temp:
                audit_parent_end=time.monotonic()+600
                audit_receipt=h.supervise([sys.executable,str(local(root,authority['execution_relative'])/'experiment_driver.py'),'--audit',str(request_path),request_sha],
                                         root,h.clean_environment(temp),local(root,authority['execution_relative']),clock,root/'audit-supervisor.json',
                                         parent_seconds=600,child_seconds=570,parent_deadline=audit_parent_end,phase='audit')
            clock.tick();h.need(time.monotonic()<audit_parent_end,'audit_context_parent600_exceeded')
            h.need(audit_receipt['status']=='completed' and audit_receipt['cleanup_confirmed'] is True,'independent_audit_child_failed')
            audit_result=h.load(root/'component-audit.json')
            verify_prepared(root,authority,binding,clock)
        else:audit_result=dict(status='incomplete_matrix',qualified=False,metrics=None)
        cleanup_start=time.monotonic();clock.tick(300+1020)
    # Shared-lock release is explicitly before final common/gap qualification.
    clock.tick();h.need(time.monotonic()<cleanup_start+300,'root_cleanup300_exceeded')
    verify_prepared(root,authority,binding,clock)
    campaign=dict(status='component_complete' if all_complete else 'incomplete_matrix',root_identity=root_identity,
                  original_start_unix=claim['claimed_at_unix'],original_deadline_unix=claim['deadline_unix'],
                  slots=slots,actual_learner_fits=total_fits if all_complete else None,
                  audit=audit_result,api_calls=0,finished_unix=time.time(),full_refit=False,promotion=False)
    h.write_new(root/'campaign.json',campaign)
    try:
        clock.tick();h.need(time.monotonic()<cleanup_start+300,'root_final_receipt_cleanup300_exceeded')
    except Exception as exc:
        campaign.update(status='blocked',actual_learner_fits=None,first_error=dict(code=type(exc).__name__,detail=str(exc)),finished_unix=time.time())
        (root/'campaign.json').write_text(json.dumps(campaign,sort_keys=True));raise
    return campaign

def audit_child(request_path,request_sha):
    """Separate no-fit process: original queue+primary pins checked before truth."""
    h.need(h.sha(request_path)==request_sha,'audit_request_seal')
    request=h.load(request_path)
    clock=h.bootstrap_clock(request['clock_context'],handoff=request['clock_handoff'],handoff_sha=request['clock_handoff_sha256'])
    h.need(Path(request['clock_path']).resolve()==Path(clock.context['clock_path']).resolve(),'audit_original_clock_path')
    claim,job,binding=h.queue_admission(request['repo'],request['queue_file'],QUEUE_SHA,request['job_id'],request['worker'],request['claim_sha'],clock)
    h.need(job['kind']=='bounded_experiment' and job['caps']['wall_seconds']==5400,'audit_original_bounded_authority')
    root=Path(request['root']).resolve();clock.tick()
    authority=h.load(request['prepared_path']);verify_prepared(root,authority,binding,clock)
    docs={}
    for name,pin in {'protocol.json':PROTOCOL_SHA,'source-manifest.json':SOURCE_SHA,'approved-input-manifest.json':INPUT_SHA,'native-cut-contract-v3-r2.json':NATIVE_SHA,'protected-single-controls.json':CONTROL_SHA}.items():
        p=local(root,'metadata/'+name);h.need(h.sha(p,clock.tick)==pin,'audit_metadata_pin');docs[name]=h.load(p)
    validate_matrix(authority,docs['protocol.json'],docs['native-cut-contract-v3-r2.json'],docs['source-manifest.json'],docs['approved-input-manifest.json'],docs['protected-single-controls.json'])
    journal=root/'terminal-journal.json';h.need(h.sha(journal,clock.tick)==request['terminal_journal_sha256'],'all_terminal_journal_seal')
    result=audit_matrix(root,authority,binding,h.load(journal),local(root,authority['library_relative']),clock)
    verify_prepared(root,authority,binding,clock);h.need(h.sha(request_path,clock.tick)==request_sha and h.sha(journal,clock.tick)==request['terminal_journal_sha256'],'audit_post_seals')
    h.write_new(root/'component-audit.json',result);clock.tick()

if __name__=='__main__':
    if len(sys.argv)==4 and sys.argv[1]=='--audit':audit_child(sys.argv[2],sys.argv[3])
    elif len(sys.argv)==1:print(json.dumps(inspect_plan(),sort_keys=True))
    else:raise SystemExit('inspection only; execute requires separately reviewed immutable bounded job')
