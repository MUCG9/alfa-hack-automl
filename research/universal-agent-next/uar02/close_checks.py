"""Root-only UAR02 post-exit closure; own30s stays inside original600s."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, math, time


def need(value, code):
    if not value:
        raise RuntimeError(code)


def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('private-manifest','private-manifest-sha256','driver-sha256','self-sha256','actual-tool-evidence'):
        p.add_argument('--'+key,required=True)
    p.add_argument('--actual-exec-session',type=int,default=None)
    p.add_argument('--actual-exit-code',type=int,required=True)
    a=p.parse_args();begin=time.monotonic()
    need(__debug__ and a.actual_tool_evidence.strip(),'actual_root_exit_evidence_required')
    path=Path(__file__).with_name('run_checks.py')
    need(hashlib.sha256(path.read_bytes()).hexdigest()==a.driver_sha256,'driver_changed')
    driver=imported('_uar02_closure_driver',path)
    cfg=driver.config(a.private_manifest,a.private_manifest_sha256,a.driver_sha256)
    need(cfg['files_sha256'].get(str(Path(__file__).resolve()))==a.self_sha256
         and driver.digest(__file__)==a.self_sha256,'closer_source_changed')
    out=Path(cfg['output']);c=driver.read(out/'campaign.json');campaign_sha=driver.digest(out/'campaign.json')
    destination=out/'terminal-root-closure.json';need(not destination.exists(),'exclusive_closure_no_rewrite')
    names=('start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic',
           'finished_unix','finished_monotonic')
    need(all(type(c.get(k)) in (int,float) and math.isfinite(c[k]) for k in names),'terminal_clock_required')
    need(c['common_seconds']==600 and c['absolute_deadline_unix']-c['start_unix']==600
         and c['common_deadline_monotonic']-c['start_monotonic']==600,'same_original600_required')
    def check():
        need(time.monotonic()-begin<30,'closure30_cap')
        need(time.time()<c['absolute_deadline_unix'] and time.monotonic()<c['common_deadline_monotonic'],
             'original600_deadline_exhausted')
        need(abs((c['absolute_deadline_unix']-time.time())-
                 (c['common_deadline_monotonic']-time.monotonic()))<=5,'clock_disagreement')
    check()
    modules={n:driver.imported('_uar02_close_'+n,cfg['helpers'][n]['path']) for n in driver.HELPERS}
    coor,owner=modules['coordinator'],modules['owner']
    known=driver.source_union(cfg,coor,check)
    known |= coor.identities([c['owned_root']]+c['coordinator_bootstrap_identities']
                             +c.get('owned_process_identities',[]))
    refs=c.get('supervisors',[]);artifacts={};sup_ok=len(refs)==1
    outer_cleanup=True;entry_started=False;uncertain=list(c.get('leaf_cleanup_uncertainty',[]))
    for index,ref in enumerate(refs):
        need(index==0 and ref['path']==coor.relative(out/'focused.json'),'exact_single_supervisor_required')
        path=Path(cfg['work_root'])/ref['path']
        need(driver.digest(path,check)==ref['sha256'],'terminal_supervisor_changed')
        artifacts[str(path)]=ref['sha256'];sup=driver.read(path)
        entry_started |= bool(sup.get('owned_root'))
        outer_cleanup &= (sup.get('cleanup_confirmed') is True
            and sup.get('cleanup_observation',{}).get('unresolved')==[]
            and sup.get('cleanup_observation',{}).get('denial_count')==0)
        for item in sup.get('cleanup_observation',{}).get('unresolved',[]):
            uncertain.append(dict(action='saved_outer_cleanup_uncertainty',receipt=item))
        known |= coor.identities(sup.get('owned_process_identities',[])+sup.get('observed_worker_roots',[]))
        if sup.get('owned_root'):known |= coor.identities([sup['owned_root']])
        sup_ok &= (sup.get('kind')=='focused' and sup.get('status')=='ok' and sup.get('exit_code')==0
            and sup.get('cleanup_confirmed') is True and sup.get('cleanup_observation',{}).get('unresolved')==[]
            and not sup.get('error_history') and sup.get('parent_cap_seconds')==500
            and sup.get('child_cap_seconds')==450 and sup.get('solver_budget_seconds') is None)
    focused_ok=False;artifact_error_type=None
    raw=out/'focused-results.json'
    if raw.exists():
        artifacts[str(raw)]=driver.digest(raw,check)
        detail=driver.read(raw)
        for row in detail.get('suites',[]):
            if row.get('owned_root'):known |= coor.identities([row['owned_root']])
            known |= coor.identities(row.get('owned_process_identities',[]))
        try:
            unused,saved=driver.focused_results(cfg,out,check);artifacts.update(saved);focused_ok=True
        except (OSError,KeyError,ValueError,RuntimeError) as exc:
            artifact_error_type=type(exc).__name__
    for name in ('focused.log','io02.log','run02.log'):
        path=out/name
        if path.exists():artifacts[str(path)]=driver.digest(path,check)
    leaf_ok,leaf_uncertain=driver.leaf_cleanup_status(out,entry_started)
    for item in leaf_uncertain:
        if item not in uncertain:uncertain.append(item)
    cleanup_ok=(c.get('cleanup_confirmed') is True and outer_cleanup and leaf_ok and not uncertain)
    if not cleanup_ok and not uncertain:
        uncertain.append(dict(action='saved_cleanup_receipts',reason='parent_or_outer_cleanup_unconfirmed'))
    driver.absence(owner,known)
    with modules['lock'].ResearchLock(cfg['lock_path']):
        driver.absence(owner,known);driver.frozen(cfg,check)
        need(driver.digest(out/'campaign.json',check)==campaign_sha,'terminal_campaign_changed')
        need(driver.digest(a.private_manifest,check)==a.private_manifest_sha256==c['private_manifest_sha256'],
             'private_manifest_changed')
        for path,expected in artifacts.items():need(driver.digest(path,check)==expected,'focused_artifact_changed')
        passed=(a.actual_exit_code==0 and c.get('status')=='tests_completed_pending_root'
            and c.get('suite_procedure_passed') is True and c.get('checks_observed')==29
            and cleanup_ok and c.get('source_unchanged') is True
            and not c.get('error_history') and c.get('active_supervisor') is None and sup_ok and focused_ok
            and c.get('model_fits')==c.get('API_calls')==0
            and c.get('awake_guard',{}).get('release_API_verified') is True
            and c['finished_unix']<c['absolute_deadline_unix']
            and c['finished_monotonic']<c['final_deadline_monotonic']
            and c['final_deadline_monotonic']<=c['final_start_monotonic']+70
            and c['final_deadline_monotonic']<=c['common_deadline_monotonic']-30)
        import psutil
        me=psutil.Process();preparers=[dict(pid=me.pid,create_time=me.create_time())];parent=me.parent()
        while parent is not None:
            birth=parent.create_time()
            if not any(Path(v).resolve()==Path(__file__).resolve()
                       for v in parent.cmdline() if v and not v.startswith('-')):break
            need(parent.create_time()==birth,'closer_bootstrap_identity_changed')
            preparers.append(dict(pid=parent.pid,create_time=birth));parent=parent.parent()
        result=dict(schema='uar02-root-closure-v1',status='technical_pass' if passed else 'failed_or_unqualified',
            technical_procedure_passed=bool(passed),actual_exec_session=a.actual_exec_session,
            actual_exec_exit_code_observed_by_root=a.actual_exit_code,actual_tool_evidence=a.actual_tool_evidence,
            cleanup_confirmed=bool(cleanup_ok),source_unchanged=True,active_owned_processes=[],uncertain_owned=uncertain,
            leaf_cleanup_confirmed=bool(leaf_ok),leaf_cleanup_uncertainty=leaf_uncertain,
            owned_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],closure_preparer_identities=preparers,
            qualified_checks=29 if passed else None,original_common_seconds=600,
            original_start_unix=c['start_unix'],original_deadline_unix=c['absolute_deadline_unix'],
            campaign_sha256=campaign_sha,private_manifest_sha256=a.private_manifest_sha256,
            suite_artifact_refs=artifacts,focused_artifact_error_type=artifact_error_type,
            first_failure=c.get('first_failure'),error_history=c.get('error_history',[]),
            focused_raw_first_failure=c.get('focused_raw_first_failure'),model_fits=0,API_calls=0,
            quality_metric=None,promotion=False,submit=False,
            own_actual_exec_exit_and_fresh_preparer_absence_required=True)
        driver.absence(owner,known);check();coor.save(destination,result,True)
        driver.absence(owner,known);check()
    check()
    print(json.dumps(dict(status=result['status'],technical_procedure_passed=bool(passed),
                          qualified_checks=result['qualified_checks'])))
    return 0 if passed else 1


if __name__=='__main__':
    raise SystemExit(main())
