"""Post-exit UAR01 qualifier; own30s remains inside its same original1200s."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, math, time


def need(v,c):
    if not v:raise RuntimeError(c)


def imported(n,p):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ['private-manifest','private-manifest-sha256','driver-sha256','self-sha256','actual-tool-evidence']:
        p.add_argument('--'+flag,required=True)
    p.add_argument('--actual-exec-session',type=int,default=None)
    p.add_argument('--actual-exit-code',type=int,required=True);a=p.parse_args();begin=time.monotonic()
    driver_path=Path(__file__).with_name('run_gate.py')
    need(__debug__ and a.actual_tool_evidence.strip(),'actual_nonoptimized_root_exit_required')
    need(hashlib.sha256(driver_path.read_bytes()).hexdigest()==a.driver_sha256,'driver_changed')
    d=imported('_uar01_closure_driver',driver_path)
    cfg=d.config(a.private_manifest,a.private_manifest_sha256,a.driver_sha256)
    need(cfg['files_sha256'].get(str(Path(__file__).resolve()))==a.self_sha256 and d.digest(__file__)==a.self_sha256,'closer_changed')
    out=Path(cfg['output']);c=d.read(out/'campaign.json');campaign_sha=d.digest(out/'campaign.json')
    destination=out/'terminal-root-closure.json';need(not destination.exists(),'exclusive_closure_no_rewrite')
    names=['start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic','finished_unix','finished_monotonic']
    need(all(type(c.get(k)) in (int,float) and math.isfinite(c[k]) for k in names),'actual_terminal_clocks_required')
    need(c['common_seconds']==1200 and c['absolute_deadline_unix']-c['start_unix']==1200
         and c['common_deadline_monotonic']-c['start_monotonic']==1200,'original1200_required')
    need((c['start_unix'],c['start_monotonic'],c['absolute_deadline_unix'],c['common_deadline_monotonic'])
         ==(1792798524.6611674,57529.75,1792799724.6611674,58729.75),'exact_inherited_clocks_required')
    need(c['original_failed_attempt']['status']=='FAIL_preserved','originalFAIL_must_remain')
    def check():
        need(time.monotonic()-begin<30,'root_closure30_cap')
        need(time.time()<c['absolute_deadline_unix'] and time.monotonic()<c['common_deadline_monotonic'],'original1200_deadline_exhausted')
        need(abs((c['absolute_deadline_unix']-time.time())-(c['common_deadline_monotonic']-time.monotonic()))<=5,'clock_disagreement')
    check();m={n:d.imported('_uar01_close_'+n,r['path']) for n,r in cfg['helpers'].items()}
    coor,owner,reuse=m['coordinator'],m['owner'],m['uar00']
    known=d.prior_union(cfg,coor,check)|coor.identities([c['owned_root']]+c['coordinator_bootstrap_identities']+c.get('owned_process_identities',[]))
    artifacts={};supervisors=[]
    for index,ref in enumerate(c['supervisors']):
        need(index<2 and ref['path']==coor.relative(out/(('source','build')[index]+'.json')),'exact_ordered_supervisor_paths')
        path=Path(cfg['work_root'])/ref['path'];need(d.digest(path,check)==ref['sha256'],'supervisor_changed')
        artifacts[str(path)]=ref['sha256'];r=d.read(path);supervisors.append(r)
        known|=coor.identities(r.get('owned_process_identities',[])+r.get('observed_worker_roots',[]))
        if r.get('owned_root'):known|=coor.identities([r['owned_root']])
    reuse.absence(owner,known)
    with m['lock'].ResearchLock(cfg['lock_path']):
        reuse.absence(owner,known);d.frozen(cfg,check)
        need(d.digest(a.private_manifest,check)==a.private_manifest_sha256==c['private_manifest_sha256'],'private_manifest_changed')
        need(d.digest(out/'campaign.json',check)==campaign_sha,'terminal_campaign_changed')
        sup_ok=len(supervisors)==2
        for r,name,cap,childcap in zip(supervisors,['source','build'],[350,60],[320,30]):
            sup_ok &= (r.get('kind')==name and r.get('status')=='ok' and r.get('exit_code')==0
                and r.get('cleanup_confirmed') is True and r.get('cleanup_observation',{}).get('unresolved')==[]
                and not r.get('error_history') and r.get('parent_cap_seconds')==cap and r.get('child_cap_seconds')==childcap
                and r.get('solver_budget_seconds') is None)
        if supervisors:sup_ok &= supervisors[0].get('child_start_monotonic',float('inf'))-c['attempt_start_monotonic']<=30
        audit=None
        if c.get('integration_artifacts_passed') is True:
            need(d.digest(out/'artifact-audit.json',check)==c['artifact_audit_sha256'],'saved_artifact_audit_changed')
            audit=d.inspect_artifacts(cfg,check);saved=d.read(out/'artifact-audit.json')
            need(audit==saved,'independent_artifact_audit_mismatch');artifacts.update(audit['artifact_refs'])
            artifacts[str(out/'artifact-audit.json')]=c['artifact_audit_sha256']
        passed=(a.actual_exit_code==0 and c['status']=='integration_complete_pending_root'
            and c.get('integration_artifacts_passed') is True and c.get('cleanup_confirmed') is True
            and c.get('source_unchanged') is True and not c.get('error_history') and c.get('active_supervisor') is None
            and sup_ok and audit is not None and c.get('API_calls')==0
            and c.get('awake_guard',{}).get('release_API_verified') is True
            and c['finished_unix']<c['absolute_deadline_unix'] and c['finished_monotonic']<c['common_deadline_monotonic'])
        import psutil
        me=psutil.Process();preparers=[dict(pid=me.pid,create_time=me.create_time())];parent=me.parent()
        while parent is not None:
            birth=parent.create_time()
            if not any(Path(v).resolve()==Path(__file__).resolve() for v in parent.cmdline() if v and not v.startswith('-')):break
            need(parent.create_time()==birth,'closer_bootstrap_identity_changed');preparers.append(dict(pid=parent.pid,create_time=birth));parent=parent.parent()
        result=dict(schema='uar01r2-terminal-root-closure-v1',status='integration_technical_pass_not_release' if passed else 'failed_or_unqualified',
            technical_procedure_passed=bool(passed),actual_exec_session=a.actual_exec_session,
            actual_exec_exit_code_observed_by_root=a.actual_exit_code,actual_tool_evidence=a.actual_tool_evidence,
            cleanup_confirmed=True,source_unchanged=True,active_owned_processes=[],uncertain_owned=[],
            owned_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],closure_preparer_identities=preparers,
            original_common_seconds=1200,original_start_unix=c['start_unix'],original_deadline_unix=c['absolute_deadline_unix'],
            campaign_sha256=campaign_sha,private_manifest_sha256=a.private_manifest_sha256,
            qualified_source_checks=499 if passed else None,qualified_source_scripts=50 if passed else None,
            archive_sha256=audit['archive_sha256'] if passed else None,artifact_refs=artifacts,
            error_history=c.get('error_history',[]),first_failure=c.get('first_failure'),model_quality=None,original_failed_attempt=c['original_failed_attempt'],
            fixture_model_fits=None,API_calls=0,release_qualified=False,promotion=False,submit=False,
            own_actual_exec_exit_and_fresh_preparer_absence_required=True)
        reuse.absence(owner,known);check();coor.save(destination,result,True);check();reuse.absence(owner,known)
    check();print(json.dumps({k:result[k] for k in ['status','technical_procedure_passed','qualified_source_checks','qualified_source_scripts','archive_sha256']}))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
