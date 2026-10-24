"""Separate UAR07 saved-artifact audit; new own30 inside unchanged original600.
Original closer19230/exit1 remains failed; no tests or children are launched.
"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, math, os, time

def need(value,code):
    if not value:raise RuntimeError(code)

def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module

ORIGINAL_PACKET=Path(__file__).resolve().parents[1]/'uar07-composite-next-dev'
ORIGINAL_PINS={'original_driver': 'fe2f6cae227d7b0ab8345aad460905c2fa87a4d88622cfa2eb785e5147d4bb81', 'original_closer': '1b3bfc4091426febdc49665e99cc6da2c98e06efd804ef7dc86648eb9bd3bfc5', 'private_manifest': 'b8dae322501349622326313f94430042729e2cb1310ecdd32d09796812cf797d', 'campaign': '6ce7a1723b7b8a8edf7c895522ad90a24f601eda48f862e2f008b82ead1aa2c1', 'failed_preparer_receipt': '0d79d0d94f5a51c98fbe06643f5ab8d33d0b7cc589341bcb42e2c6b60f81c79e'}
RESOURCE_SAMPLE_SECONDS=0.25

def main():
    # Capture exact current auditor/preparers before validation can fail.
    begin=time.monotonic()
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS',
                'VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS'):
        os.environ[key]='1'
    import psutil
    me=psutil.Process();preparers=[dict(pid=me.pid,create_time=me.create_time())];parent=me.parent()
    while parent is not None:
        birth=parent.create_time()
        if not any(Path(v).resolve()==Path(__file__).resolve() for v in parent.cmdline() if v and not v.startswith('-')):break
        need(parent.create_time()==birth,'early_closer_bootstrap_identity_changed')
        preparers.append(dict(pid=parent.pid,create_time=birth));parent=parent.parent()
    audit_observer=None;last_sample=begin;maximum_gap=0.;peak_rss=0;sticky_error=None;c=None;resource_samples=0
    def check(force=False):
        nonlocal last_sample,maximum_gap,peak_rss,sticky_error,resource_samples
        if sticky_error is not None:raise RuntimeError(sticky_error)
        try:
            observed=time.monotonic();maximum_gap=max(maximum_gap,observed-last_sample)
            need(observed-last_sample<=10,'root_closer_observation_gap10')
            need(observed-begin<30,'root_closure30_cap')
            if c is not None:
                need(time.time()<c['absolute_deadline_unix'] and observed<c['common_deadline_monotonic'],
                     'original600_exhausted')
            # Every call checks clocks and gap from the last ACTUAL resource observation.
            # Only successful resource observations advance last_sample; skipped hash
            # callbacks cannot reset a denial or hide a scheduling gap.
            if c is not None:
                need(abs((c['absolute_deadline_unix']-time.time())-(c['common_deadline_monotonic']-observed))<=5,
                     'clock_disagreement')
            if not force and observed-last_sample<RESOURCE_SAMPLE_SECONDS:return
            if audit_observer is None:
                live={}
                for saved in preparers:
                    try:
                        obj=psutil.Process(saved['pid'])
                        if obj.create_time()==saved['create_time']:live[(saved['pid'],saved['create_time'])]=obj
                    except psutil.NoSuchProcess:pass
                need((preparers[0]['pid'],preparers[0]['create_time']) in live,'root_closer_self_identity_unconfirmed')
            else:
                live=audit_observer.observe();need(not audit_observer.denials,'root_closer_resource_observation_denied')
            rss=0
            for identity,obj in live.items():
                try:
                    need(obj.create_time()==identity[1],'root_closer_resource_identity_changed')
                    amount=obj.memory_info().rss
                    need(obj.create_time()==identity[1],'root_closer_resource_identity_changed');rss+=amount
                except psutil.NoSuchProcess:pass
            peak_rss=max(peak_rss,rss);need(rss<=2048*2**20,'root_closer_owned_memory_limit')
            sampled=time.monotonic();maximum_gap=max(maximum_gap,sampled-last_sample)
            need(sampled-last_sample<=10,'root_closer_observation_gap10')
            need(sampled-begin<30,'root_closure30_cap')
            if c is not None:
                need(time.time()<c['absolute_deadline_unix'] and sampled<c['common_deadline_monotonic'],
                     'original600_exhausted')
                need(abs((c['absolute_deadline_unix']-time.time())-(c['common_deadline_monotonic']-sampled))<=5,
                     'clock_disagreement')
            last_sample=sampled;resource_samples+=1
        except Exception as exc:
            sticky_error=str(exc) if isinstance(exc,RuntimeError) else 'root_closer_resource_observation_unconfirmed'
            raise RuntimeError(sticky_error) from exc
    early=Path(__file__).with_name('preparer-identity.json')
    with early.open('x',encoding='utf-8') as stream:
        json.dump(dict(schema=1,identities=preparers,scope='new_separate_UAR07_audit_repair_only',
            captured_unix=time.time(),own_start_monotonic=begin),stream,indent=2,allow_nan=False)
    check(force=True)
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('private-manifest','private-manifest-sha256','driver-sha256','self-sha256','actual-tool-evidence'):
        p.add_argument('--'+key,required=True)
    p.add_argument('--actual-exec-session',type=int,default=None)
    p.add_argument('--actual-exit-code',type=int,required=True)
    a=p.parse_args();a.private_manifest=str(Path(a.private_manifest).resolve())
    check();need(__debug__ and a.actual_tool_evidence.strip(),'actual_root_exit_evidence_required')
    need(a.driver_sha256==ORIGINAL_PINS['original_driver'] and a.private_manifest_sha256==ORIGINAL_PINS['private_manifest'],
         'exact_original_packet_required')
    need(a.actual_exec_session==78888 and a.actual_exit_code==0 and a.actual_tool_evidence=='8a9663',
         'exact_original_driver_exit_required')
    path=ORIGINAL_PACKET/'run_gate.py'
    check();need(hashlib.sha256(path.read_bytes()).hexdigest()==a.driver_sha256,'driver_changed');check()
    driver=imported('_uar04_closure_driver',path)
    cfg=driver.config(a.private_manifest,a.private_manifest_sha256,a.driver_sha256);check()
    need(driver.digest(__file__,check)==a.self_sha256,'external_auditor_source_changed')
    original_closer=ORIGINAL_PACKET/'close_gate.py'
    failed_preparers=ORIGINAL_PACKET/'preparer-identity.json'
    need(cfg['files_sha256'].get(str(original_closer))==ORIGINAL_PINS['original_closer']
         and driver.digest(original_closer,check)==ORIGINAL_PINS['original_closer'],
         'original_failed_closer_source_changed')
    need(driver.digest(failed_preparers,check)==ORIGINAL_PINS['failed_preparer_receipt'],
         'original_failed_closer_identity_receipt_changed')
    failed=driver.read(failed_preparers)
    need(failed.get('schema')==1 and failed.get('identities')==[
        dict(pid=27264,create_time=1792825407.5485268),dict(pid=26980,create_time=1792825407.5320556)],
        'exact_failed_closer_known_identities_required')
    out=Path(cfg['output']);c=driver.read(out/'campaign.json');check();campaign_sha=driver.digest(out/'campaign.json',check)
    need(campaign_sha==ORIGINAL_PINS['campaign'],'exact_original_terminal_campaign_required')
    need(not (out/'terminal-root-closure.json').exists(),'original_missing_root_must_not_be_forged')
    dest=Path(__file__).with_name('terminal-audit-root-closure.json')
    need(not dest.exists(),'exclusive_separate_audit_proof_no_rewrite')
    fields=('start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic','finished_unix','finished_monotonic')
    need(all(type(c.get(k)) in (int,float) and math.isfinite(c[k]) for k in fields),'actual_terminal_clocks_required')
    # Repeat the exact assigned operation: no epsilon or extension from subtraction.
    need(c['common_seconds']==600 and c['absolute_deadline_unix']==c['start_unix']+600
         and c['common_deadline_monotonic']==c['start_monotonic']+600,'same_assigned_original600_required')
    check()
    for key in ('contracts','focused_helper'):
        need(driver.digest(cfg[key],check)==cfg['files_sha256'][cfg[key]],'standalone_helper_changed')
    contract=driver.imported('_uar04_close_contracts',cfg['contracts'])
    base=driver.imported('_uar04_close_focused',cfg['focused_helper'])
    for name,expected in driver.HELPERS.items():
        need(driver.digest(cfg['helpers'][name]['path'],check)==expected,'proven_guard_changed')
    modules={n:driver.imported('_uar04_close_'+n,cfg['helpers'][n]['path']) for n in driver.HELPERS}
    coor,owner=modules['coordinator'],modules['owner']
    audit_observer=owner.StrictOwnedObserver();audit_observer.remember(coor.identities(preparers));check(force=True)
    known=base.source_union(cfg,coor,check)|contract.negative_union(cfg,coor,check)
    known |= coor.identities(failed['identities'])
    known |= coor.identities([c['owned_root']]+c['coordinator_bootstrap_identities']+c.get('owned_process_identities',[]))
    refs=c.get('supervisors',[]);artifacts={str(early):driver.digest(early,check),str(failed_preparers):ORIGINAL_PINS['failed_preparer_receipt']}
    sup_ok=len(refs)==2;outer_cleanup=True;entry_started=False
    uncertain=list(c.get('leaf_cleanup_uncertainty',[]))
    for index,ref in enumerate(refs):
        need(index<2 and ref['path']==coor.relative(out/('parser-supervisor.json' if index==0 else 'mapped-supervisor.json')),'exact_two_serial_supervisors_required')
        path=Path(cfg['work_root'])/ref['path'];need(driver.digest(path,check)==ref['sha256'],'terminal_supervisor_changed')
        artifacts[str(path)]=ref['sha256'];sup=driver.read(path);entry_started|=bool(sup.get('owned_root'))
        ob=sup.get('cleanup_observation',{})
        outer_cleanup &= sup.get('cleanup_confirmed') is True and ob.get('unresolved')==[] and ob.get('denial_count')==0
        if not outer_cleanup:uncertain.append(dict(action='saved_outer_cleanup_unconfirmed',observation=ob))
        known |= coor.identities(sup.get('owned_process_identities',[])+sup.get('observed_worker_roots',[]))
        if sup.get('owned_root'):known |= coor.identities([sup['owned_root']])
        sup_ok &= (sup.get('kind')==('parser' if index==0 else 'mapped') and sup.get('status')=='ok' and sup.get('exit_code')==0
            and sup.get('cleanup_confirmed') is True and not sup.get('error_history')
            and sup.get('parent_cap_seconds')==(60 if index==0 else 300) and sup.get('child_cap_seconds')==(45 if index==0 else 270)
            and sup.get('solver_budget_seconds') is None)
    for name in ('parser-results.json','mapped-results.json'):
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
        need(driver.digest(__file__,check)==a.self_sha256,'external_auditor_source_changed')
        check(force=True)
        passed=(sticky_error is None and a.actual_exit_code==0 and c.get('status')=='technical_completed_pending_root'
            and c.get('technical_procedure_passed') is True and c.get('source_unchanged') is True and cleanup_ok
            and not c.get('error_history') and c.get('active_supervisor') is None and sup_ok and technical_ok
            and c.get('awake_guard',{}).get('release_API_verified') is True
            and c['finished_unix']<c['absolute_deadline_unix'] and c['finished_monotonic']<c['final_deadline_monotonic']
            and c['final_deadline_monotonic']<=c['final_start_monotonic']+120
            and c['final_deadline_monotonic']<=c['common_deadline_monotonic']-30)
        result=dict(schema='uar-composite-audit-repair-root-closure-v1',
            status='separate_saved_artifact_audit_pass_pending_root_exec' if passed else 'failed_or_unqualified',
            qualification_scope='separate_saved_artifact_audit_only',
            original_closer_status='FAILED_root_closure30_cap',original_closer_exec_session=19230,
            original_closer_actual_exit_code=1,original_closer_actual_tool_evidence='617a23',
            original_closer_source_sha256=ORIGINAL_PINS['original_closer'],
            original_closer_preparer_receipt_sha256=ORIGINAL_PINS['failed_preparer_receipt'],
            original_closer_retroqualified=False,original_full_procedure_passed=False,
            original_procedure_first_failure=dict(scope='original_closer',code='root_closure30_cap',
                actual_exec_session=19230,actual_exit_code=1,actual_tool_evidence='617a23'),
            original_closer_raw_trace_saved=False,
            original_closer_failure_evidence_scope='root_observed_exit_and_source_line177_no_synthetic_trace',
            external_auditor_source_sha256=a.self_sha256,external_auditor_original_pins=ORIGINAL_PINS,
            separate_audit_actual_exec_confirmation_pending=True,
            audit_start_monotonic=begin,audit_reported_before_save_monotonic=time.monotonic(),
            audit_reported_before_save_unix=time.time(),audit_own_cap_seconds=30,
            technical_procedure_passed=bool(passed),actual_exec_session=a.actual_exec_session,
            actual_exec_exit_code_observed_by_root=a.actual_exit_code,actual_tool_evidence=a.actual_tool_evidence,
            cleanup_confirmed=bool(cleanup_ok),source_unchanged=True,active_owned_processes=[],uncertain_owned=uncertain,
            leaf_cleanup_confirmed=bool(leaf_ok),leaf_cleanup_uncertainty=leaf_uncertain,
            temporary_cleanup_confirmed=bool(temp_ok),temporary_cleanup_uncertainty=temp_uncertain,
            owned_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],closure_preparer_identities=preparers,
            early_preparer_identity_receipt_sha256=artifacts[str(early)],
            prior_UAR06_late_negative_sha256=cfg['negative_predecessor']['late_observation']['sha256'],
            prior_UAR06_actual_root_fresh_absence_sha256=cfg['negative_predecessor']['root_fresh_absence']['sha256'],
            original_UAR06_status='FAIL_PERMANENT',original_UAR06_retroqualified=False,
            prior_UAR05_closed_failure_sha256='f6beea92100db555853da7bd7990308f5d667fe1b2f60ffa9e69b36eabd5faf6',
            prior_UAR05_failure_preserved=True,
            prior_UAR04_closed_failure_sha256='cd6c4e73bc0f5f6145ec11dbdd36160f96ba6f39dad09027496b177b60f0b10b',
            prior_UAR04_failure_preserved=True,prior_a1d203_helper_PID_identity=None,
            prior_a1d203_identity_retroqualified=False,
            qualified_checks=summary if passed else None,original_common_seconds=600,
            original_start_unix=c['start_unix'],original_deadline_unix=c['absolute_deadline_unix'],
            campaign_sha256=campaign_sha,private_manifest_sha256=a.private_manifest_sha256,
            technical_artifact_refs=artifacts,artifact_error=artifact_error,first_failure=c.get('first_failure'),
            error_history=c.get('error_history',[]),fixture_learner_fits=None,external_API_calls=None,
            counter_limit='legacy_fixture_fit_and_external_API_usage_uninstrumented_not_zero',
            public_experiment_fits=0,quality_metric=None,promotion=False,submit=False,
            root_guard_sticky_error=sticky_error,root_maximum_observed_gap_seconds=maximum_gap,
            root_peak_owned_rss_mib=peak_rss/2**20,root_resource_limit_mib=2048,
            root_resource_sampling_interval_seconds=RESOURCE_SAMPLE_SECONDS,root_actual_resource_samples=resource_samples,
            root_resource_sampling_scope='main_thread_due_callbacks_and_forced_boundaries_not_OS_preemption',
            own_actual_exec_exit_and_fresh_preparer_absence_required=True)
        base.absence(owner,known);check(force=True);coor.save(dest,result,True)
        base.absence(owner,known);check(force=True)
    check(force=True);print(json.dumps(dict(status=result['status'],technical_procedure_passed=bool(passed),
        qualified_checks=result['qualified_checks']),allow_nan=False));return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())
