"""Generic UAR06 terminal closure; own60s inside its one original1200 clock."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, math, time

def need(value,code):
    if not value:raise RuntimeError(code)

def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module

def main():
    # Capture exact current auditor/preparers before validation can fail.
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
        json.dump(dict(schema=1,identities=preparers,scope='new_UAR06_root_closer_only',
            captured_unix=time.time(),own_start_monotonic=begin),stream,indent=2,allow_nan=False)
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('private-manifest','private-manifest-sha256','driver-sha256','self-sha256','actual-tool-evidence'):
        p.add_argument('--'+key,required=True)
    p.add_argument('--actual-exec-session',type=int,default=None)
    p.add_argument('--actual-exit-code',type=int,required=True)
    a=p.parse_args();a.private_manifest=str(Path(a.private_manifest).resolve())
    need(__debug__ and a.actual_tool_evidence.strip(),'actual_root_exit_evidence_required')
    path=Path(__file__).with_name('run_gate.py')
    need(hashlib.sha256(path.read_bytes()).hexdigest()==a.driver_sha256,'driver_changed')
    driver=imported('_uar04_closure_driver',path)
    cfg=driver.config(a.private_manifest,a.private_manifest_sha256,a.driver_sha256)
    need(cfg['files_sha256'].get(str(Path(__file__).resolve()))==a.self_sha256
         and driver.digest(__file__)==a.self_sha256,'closer_source_changed')
    out=Path(cfg['output']);c=driver.read(out/'campaign.json');campaign_sha=driver.digest(out/'campaign.json')
    dest=out/'terminal-root-closure.json';need(not dest.exists(),'exclusive_terminal_proof_no_rewrite')
    fields=('start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic','finished_unix','finished_monotonic')
    need(all(type(c.get(k)) in (int,float) and math.isfinite(c[k]) for k in fields),'actual_terminal_clocks_required')
    # Repeat the exact assigned operation: no epsilon or extension from subtraction.
    need(c['common_seconds']==1200 and c['absolute_deadline_unix']==c['start_unix']+1200
         and c['common_deadline_monotonic']==c['start_monotonic']+1200,'same_assigned_original1200_required')
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
    known |= coor.identities([c['owned_root']]+c['coordinator_bootstrap_identities']+c.get('owned_process_identities',[]))
    refs=c.get('supervisors',[]);artifacts={str(early):driver.digest(early,check)}
    sup_ok=len(refs)==1;outer_cleanup=True;entry_started=False
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
    leaf_ok,leaf_uncertain=contract.cleanup_status(cfg,out,entry_started)
    for item in leaf_uncertain:
        if item not in uncertain:uncertain.append(item)
    temp_ok,temp_uncertain=contract.temporary_status(cfg,out,c.get('temporary_root'))
    uncertain.extend(item for item in temp_uncertain if item not in uncertain)
    for name in ('temporary-root.json','temporary-cleanup.json'):
        if (out/name).exists():artifacts[str(out/name)]=driver.digest(out/name,check)
    cleanup_ok=(c.get('cleanup_confirmed') is True and c.get('temporary_cleanup_confirmed') is True
                and outer_cleanup and leaf_ok and temp_ok and not uncertain)
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
        passed=(a.actual_exit_code==0 and c.get('status')=='technical_completed_pending_root'
            and c.get('technical_procedure_passed') is True and c.get('source_unchanged') is True and cleanup_ok
            and not c.get('error_history') and c.get('active_supervisor') is None and sup_ok and technical_ok
            and c.get('awake_guard',{}).get('release_API_verified') is True
            and c['finished_unix']<c['absolute_deadline_unix'] and c['finished_monotonic']<c['final_deadline_monotonic']
            and c['final_deadline_monotonic']<=c['final_start_monotonic']+180
            and c['final_deadline_monotonic']<=c['common_deadline_monotonic']-60)
        result=dict(schema='uar-full-root-closure-v1',status='technical_pass' if passed else 'failed_or_unqualified',
            technical_procedure_passed=bool(passed),actual_exec_session=a.actual_exec_session,
            actual_exec_exit_code_observed_by_root=a.actual_exit_code,actual_tool_evidence=a.actual_tool_evidence,
            cleanup_confirmed=bool(cleanup_ok),source_unchanged=True,active_owned_processes=[],uncertain_owned=uncertain,
            leaf_cleanup_confirmed=bool(leaf_ok),leaf_cleanup_uncertainty=leaf_uncertain,
            temporary_cleanup_confirmed=bool(temp_ok),temporary_cleanup_uncertainty=temp_uncertain,
            owned_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],closure_preparer_identities=preparers,
            early_preparer_identity_receipt_sha256=artifacts[str(early)],
            prior_UAR05_closed_failure_sha256='f6beea92100db555853da7bd7990308f5d667fe1b2f60ffa9e69b36eabd5faf6',
            prior_UAR05_failure_preserved=True,
            prior_UAR04_closed_failure_sha256='cd6c4e73bc0f5f6145ec11dbdd36160f96ba6f39dad09027496b177b60f0b10b',
            prior_UAR04_failure_preserved=True,prior_a1d203_helper_PID_identity=None,
            prior_a1d203_identity_retroqualified=False,
            qualified_checks=summary if passed else None,original_common_seconds=1200,
            original_start_unix=c['start_unix'],original_deadline_unix=c['absolute_deadline_unix'],
            campaign_sha256=campaign_sha,private_manifest_sha256=a.private_manifest_sha256,
            technical_artifact_refs=artifacts,artifact_error=artifact_error,first_failure=c.get('first_failure'),
            error_history=c.get('error_history',[]),fixture_learner_fits=None,external_API_calls=None,
            counter_limit='legacy_fixture_fit_and_external_API_usage_uninstrumented_not_zero',
            public_experiment_fits=0,quality_metric=None,promotion=False,submit=False,
            own_actual_exec_exit_and_fresh_preparer_absence_required=True)
        base.absence(owner,known);check();coor.save(dest,result,True);base.absence(owner,known);check()
    check();print(json.dumps(dict(status=result['status'],technical_procedure_passed=bool(passed),
        qualified_checks=result['qualified_checks']),allow_nan=False));return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
