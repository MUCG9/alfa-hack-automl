"""Audit-only failed UAR04 closure repair; own60 inside SAME original1200."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, math, time

def need(value,code):
    if not value:raise RuntimeError(code)

def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module

def main():
    # Persist this auditor's exact identities before semantic validation can fail.
    begin=time.monotonic()
    import psutil
    me=psutil.Process();preparers=[dict(pid=me.pid,create_time=me.create_time())];parent=me.parent()
    while parent is not None:
        birth=parent.create_time()
        if not any(Path(v).resolve()==Path(__file__).resolve() for v in parent.cmdline() if v and not v.startswith('-')):break
        need(parent.create_time()==birth,'early_closer_bootstrap_identity_changed')
        preparers.append(dict(pid=parent.pid,create_time=birth));parent=parent.parent()
    early=Path(__file__).with_name('preparer-identity.json')
    with early.open('x',encoding='utf-8') as stream:
        json.dump(dict(schema=1,identities=preparers,scope='new_audit_only_closer_not_original_a1d203',
            captured_unix=time.time(),own_start_monotonic=begin),stream,indent=2,allow_nan=False)
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('private-manifest','private-manifest-sha256','driver-sha256','self-sha256','actual-tool-evidence',
                'original-closer-sha256','failure-monitor-sha256'):
        p.add_argument('--'+key,required=True)
    p.add_argument('--actual-exec-session',type=int,default=None)
    p.add_argument('--actual-exit-code',type=int,required=True)
    a=p.parse_args();a.private_manifest=str(Path(a.private_manifest).resolve())
    need(__debug__ and a.actual_tool_evidence.strip(),'actual_root_exit_evidence_required')
    work=Path(__file__).resolve().parents[1];packet=work/'uar-full-next-dev-r2'
    path=packet/'run_gate.py';original_closer=packet/'close_gate.py'
    need(hashlib.sha256(path.read_bytes()).hexdigest()==a.driver_sha256==
         'c9efc4030c7269cb94c43c757f896e563d9f553f559af0fbf00cddd5e0e8f9f3','original_driver_changed')
    need(hashlib.sha256(original_closer.read_bytes()).hexdigest()==a.original_closer_sha256==
         '4aaeddd54f4d35211cf3c1c3d39ffc0e0bd129731ee324442c9926211b909a94','original_closer_changed')
    need(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.self_sha256,'new_auditor_source_changed')
    need(a.private_manifest_sha256=='5535c1f5eb7e2b85cff646a11a82afa263435c0c3bcc5c0ed471dbbfa71f81b8'
         and a.actual_exec_session==66061 and a.actual_exit_code==1 and a.actual_tool_evidence=='0971f4',
         'only_actual_failed_UAR04_root_event_allowed')
    driver=imported('_uar04_closure_driver',path)
    cfg=driver.config(a.private_manifest,a.private_manifest_sha256,a.driver_sha256)
    need(cfg['files_sha256'].get(str(original_closer.resolve()))==a.original_closer_sha256,
         'original_manifest_still_pins_original_closer_not_new_auditor')
    out=Path(cfg['output']);c=driver.read(out/'campaign.json');campaign_sha=driver.digest(out/'campaign.json')
    dest=Path(__file__).with_name('terminal-root-closure.json');need(not dest.exists(),'exclusive_audit_repair_proof_no_rewrite')
    fields=('start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic','finished_unix','finished_monotonic')
    need(all(type(c.get(k)) in (int,float) and math.isfinite(c[k]) for k in fields),'actual_terminal_clocks_required')
    # Exactly repeat the assigned operation. No epsilon, new clock, or deadline extension.
    need(c['common_seconds']==1200 and c['absolute_deadline_unix']==c['start_unix']+1200
         and c['common_deadline_monotonic']==c['start_monotonic']+1200
         and c['start_unix']==1792806446.972887 and c['start_monotonic']==65452.093,
         'same_assigned_original1200_required')
    need(c['status']=='technical_failure' and c.get('technical_procedure_passed') is False,
         'original_gate_failure_must_remain_failure')
    def check():
        need(time.monotonic()-begin<60,'root_closure60_cap')
        need(time.time()<c['absolute_deadline_unix'] and time.monotonic()<c['common_deadline_monotonic'],
             'original1200_exhausted')
        need(abs((c['absolute_deadline_unix']-time.time())-
                 (c['common_deadline_monotonic']-time.monotonic()))<=5,'clock_disagreement')
    check()
    for key in ('contracts','focused_helper'):
        need(driver.digest(cfg[key],check)==cfg['files_sha256'][cfg[key]],'standalone_helper_changed')
    contract=driver.imported('_uar04_close_contracts',cfg['contracts'])
    base=driver.imported('_uar04_close_focused',cfg['focused_helper'])
    for name,expected in driver.HELPERS.items():
        need(driver.digest(cfg['helpers'][name]['path'],check)==expected,'proven_guard_changed')
    modules={n:driver.imported('_uar04_close_'+n,cfg['helpers'][n]['path']) for n in driver.HELPERS}
    coor,owner=modules['coordinator'],modules['owner']
    known=base.source_union(cfg,coor,check)
    monitor_path=work/'uar04-failure-fresh-monitor-r1.json'
    need(driver.digest(monitor_path,check)==a.failure_monitor_sha256==
         'c30a65ab571b82275a798e785c7160de0eff7421b51941d9581b6191f89cb998',
         'root_failure_monitor_changed')
    monitor=driver.read(monitor_path)
    need(monitor['actual_exec_session']==66061 and monitor['actual_exec_exit']==1
         and monitor['actual_exec_tool']=='0971f4' and monitor['live']==[] and monitor['uncertain']==[],
         'root_failure_monitor_not_same_closed_gate')
    known |= coor.identities(monitor['owned_identities'])
    known |= coor.identities([c['owned_root']]+c['coordinator_bootstrap_identities']+c.get('owned_process_identities',[]))
    refs=c.get('supervisors',[]);artifacts={};sup_ok=len(refs)==1;outer_cleanup=True;entry_started=False
    uncertain=list(c.get('leaf_cleanup_uncertainty',[]))
    for index,ref in enumerate(refs):
        need(index==0 and ref['path']==coor.relative(out/'technical.json'),'exact_single_supervisor_required')
        path=Path(cfg['work_root'])/ref['path'];need(driver.digest(path,check)==ref['sha256'],'terminal_supervisor_changed')
        artifacts[str(path)]=ref['sha256'];sup=driver.read(path);entry_started|=bool(sup.get('owned_root'))
        ob=sup.get('cleanup_observation',{})
        outer_cleanup &= sup.get('cleanup_confirmed') is True and ob.get('unresolved')==[] and ob.get('denial_count')==0
        if not outer_cleanup:uncertain.append(dict(action='saved_outer_cleanup_unconfirmed',observation=ob))
        known |= coor.identities(sup.get('owned_process_identities',[])+sup.get('observed_worker_roots',[]))
        if sup.get('owned_root'):known |= coor.identities([sup['owned_root']])
        sup_ok &= (sup.get('kind')=='technical' and sup.get('status')=='ok' and sup.get('exit_code')==0
            and sup.get('cleanup_confirmed') is True and not sup.get('error_history')
            and sup.get('parent_cap_seconds')==900 and sup.get('child_cap_seconds')==840
            and sup.get('solver_budget_seconds') is None)
    for name in ('technical-results.json','mapped-results.json'):
        if (out/name).exists():
            raw=driver.read(out/name);artifacts[str(out/name)]=driver.digest(out/name,check)
            for row in raw.get('leaves',[]):
                if row.get('owned_root'):known |= coor.identities([row['owned_root']])
                known |= coor.identities(row.get('owned_process_identities',[]))
    for name in ('source/results.json','source.log','technical.log'):
        if (out/name).exists():artifacts[str(out/name)]=driver.digest(out/name,check)
    artifacts[str(monitor_path)]=a.failure_monitor_sha256
    artifacts[str(early)]=driver.digest(early,check)
    leaf_ok,leaf_uncertain=contract.cleanup_status(cfg,out,entry_started)
    for item in leaf_uncertain:
        if item not in uncertain:uncertain.append(item)
    cleanup_ok=c.get('cleanup_confirmed') is True and outer_cleanup and leaf_ok and not uncertain
    if not cleanup_ok and not uncertain:uncertain.append(dict(action='saved_cleanup_unconfirmed',reason='parent_or_leaf'))
    technical_ok=False;summary={};artifact_error=None
    try:
        summary,saved=contract.artifact_checks(cfg,out,check);artifacts.update(saved);technical_ok=True
    except (OSError,ValueError,KeyError,RuntimeError,TypeError) as exc:
        artifact_error=dict(type=type(exc).__name__,code=str(exc) if isinstance(exc,RuntimeError) else 'technical_artifact_unqualified')
    base.absence(owner,known)
    with modules['lock'].ResearchLock(cfg['lock_path']):
        base.absence(owner,known);contract.frozen(cfg,check)
        need(driver.digest(out/'campaign.json',check)==campaign_sha,'terminal_campaign_changed')
        need(driver.digest(a.private_manifest,check)==a.private_manifest_sha256==c['private_manifest_sha256'],
             'private_manifest_changed')
        for name,expected in artifacts.items():need(driver.digest(name,check)==expected,'sealed_artifact_changed')
        passed=False # Audit-only repair can close ownership; it can NEVER promote the actual failed gate.
        result=dict(schema='uar-full-root-closure-v1',status='technical_pass' if passed else 'failed_or_unqualified',
            technical_procedure_passed=bool(passed),actual_exec_session=a.actual_exec_session,
            actual_exec_exit_code_observed_by_root=a.actual_exit_code,actual_tool_evidence=a.actual_tool_evidence,
            cleanup_confirmed=bool(cleanup_ok),source_unchanged=True,active_owned_processes=[],uncertain_owned=uncertain,
            leaf_cleanup_confirmed=bool(leaf_ok),leaf_cleanup_uncertainty=leaf_uncertain,
            owned_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],closure_preparer_identities=preparers,
            qualified_checks=summary if passed else None,original_common_seconds=1200,
            original_start_unix=c['start_unix'],original_deadline_unix=c['absolute_deadline_unix'],
            campaign_sha256=campaign_sha,private_manifest_sha256=a.private_manifest_sha256,
            technical_artifact_refs=artifacts,artifact_error=artifact_error,first_failure=c.get('first_failure'),
            error_history=c.get('error_history',[]),fixture_learner_fits=None,external_API_calls=None,
            counter_limit='legacy_fixture_fit_and_external_API_usage_uninstrumented_not_zero',
            public_experiment_fits=0,quality_metric=None,promotion=False,submit=False,
            audit_only_repair=True,external_auditor_source_sha256=a.self_sha256,
            original_driver_sha256=a.driver_sha256,original_closer_sha256=a.original_closer_sha256,
            original_gate_failure_permanent=True,known_identity_cleanup_scope_only=True,
            first_frozen_closer=dict(actual_tool_evidence='a1d203',actual_exit_code=1,PID_identity=None,
                preparer_identity_proof=None,retroactive_identity_qualification=False,
                raw_trace_file_sha256=None,source_failure_line=30,failure_code='same_original1200_required',
                source_prefix_scope='exact4aae line30 before later ownership-helper imports or any child/Popen/process creation; already imported driver contains module definitions only',
                limitation='Actual root tool terminal is observed; PID/create_time was not persisted. No synthetic identity or raw trace hash is claimed.'),
            own_actual_exec_exit_and_fresh_preparer_absence_required=True)
        base.absence(owner,known);check()
        need(driver.digest(__file__,check)==a.self_sha256,'external_auditor_source_changed')
        coor.save(dest,result,True);base.absence(owner,known);check()
        need(driver.digest(__file__,check)==a.self_sha256,'external_auditor_source_changed')
    check();print(json.dumps(dict(status=result['status'],technical_procedure_passed=bool(passed),
        qualified_checks=result['qualified_checks']),allow_nan=False));return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
