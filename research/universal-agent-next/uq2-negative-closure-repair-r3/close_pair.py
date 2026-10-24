"""Separate UQ2 clean-negative audit root; own60 inside original10800, no reset.
No public exports/STATE/Git writes. Actual tool/exit/session evidence is mandatory;
a genuine directexec null session stays None. Failed research outcomes stay null.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,math,os,re,sys,time
WORK=Path(__file__).resolve().parents[1]
COOR='run_lean_mvp_r2.py';COOR_SHA='43be86ece6c453641afdcc6f8eccef02d713986e2ac8bf3314756f0bb78e0818'
OWNER='support_component_coordinator.py';OWNER_SHA='8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8'
LOCK='alfa-hack-automl/tools/research_lock.py';LOCK_SHA='78a0441bb3b9ea60197e9a1a6e1087f6e4cd0886593ec54bcfc4e41c9abe5a45'
ORIGIN=(1792826068.8239975,85073.953,1792836868.8239975,95873.953)
ORIGINAL_CLOSER='uar-qwen-pair-bootstrap-repair-next-dev/close_pair.py'
ORIGINAL_CLOSER_SHA='078051c7741acfec8f552fa052f0025166a5db880daab8dc08498b6428a36f91'
CAMPAIGN_SHA='f5dcda611d626d1e35cea9d7d1b6388a8c778ad485c624e2fbd468db149cc57c'
OLD_PREPARERS_SHA='16c9e39ec22d6044e16813ffe41722eb159dcfdca5f61d504db1e4d848db69fd'
FAILURE='uq2-closer-failure-r1.json';FAILURE_SHA='b896fb6be5c4a46674010f7736a1811f92545ae342223dde3ffab2d82e795a3c'
CURRENT='uq2-postfailure-current-observation-r1.json';CURRENT_SHA='015eea291a16c61643ef835523dd2f0e503608dced2bb61b6d64648059072bf7'
LEGACY='uar02-next-dev/attempt-r1/terminal-root-closure.json'
LEGACY_SHA='87f691b5774ed6f604069d952041bdd6af6a6022f9ea1268ac77a8364180a106'
POSITIVE={
 'uar02-recovery-next-dev/attempt-r1/terminal-root-closure.json':'67694534b84604c02ec97545b8a6075f3b34b99855a3e7d6605ff69917b2b868',
 'uar-focused-gate-next-dev/attempt-uar03-r1/terminal-root-closure.json':'e86a151481b5b2849d9d0b6b4dc8ef6787a6ccf766dd97486b65de9d05cbf5d9',
 'uar07-audit-close-repair-r1/terminal-audit-root-closure.json':'03b9f83e4a3658e8728375b61bafb697428b772b585064c853726bba90b97615'}

RESOURCE_SAMPLE_SECONDS=0.25

def need(value,code):
    if not value:raise RuntimeError(code)

def read(p):return json.loads(p.read_text('utf-8'))
def local(n):
    p=(WORK/n).resolve();assert not Path(n).is_absolute() and p.is_relative_to(WORK);return p

def imported(n,p):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def main():
    begin=time.monotonic()
    import psutil
    me=psutil.Process();preparers=[dict(pid=me.pid,create_time=me.create_time())];parent=me.parent()
    while parent is not None:
        birth=parent.create_time()
        if not any(Path(v).resolve()==Path(__file__).resolve() for v in parent.cmdline() if v and not v.startswith('-')):break
        assert parent.create_time()==birth;preparers.append(dict(pid=parent.pid,create_time=birth));parent=parent.parent()
    audit_output=WORK/'uq2-audit-close-repair-r1';audit_output.mkdir(exist_ok=False)
    early=audit_output/'preparer-identity.json'
    with early.open('x',encoding='utf-8') as stream:json.dump(dict(schema=1,identities=preparers),stream,indent=2,allow_nan=False)
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--self-sha256',required=True)
    ap.add_argument('--actual-exec-session',type=int,default=None);ap.add_argument('--actual-exit-code',type=int,required=True)
    ap.add_argument('--actual-tool-evidence',required=True);a=ap.parse_args()
    assert __debug__ and a.actual_exec_session==3588 and a.actual_exit_code==1 and a.actual_tool_evidence=='d7f40a'
    root=WORK/'uq2';c=read(root/'campaign.json');out=audit_output/'terminal-root-closure.json';assert not out.exists()
    assert not (root/'terminal-root-closure.json').exists(),'Original failed closer must not be retroqualified'
    assert tuple(c[k] for k in ('start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic'))==ORIGIN
    assert c['qualification']=='FAIL' and c['status']=='technical_failure' and c['error_history']
    assert c['cleanup_confirmed'] is True and c['source_unchanged'] is True
    assert len(c['arms'])==4 and set(c['slot_matrix'])=={'Ar','Br','Ac','Bc'}
    assert c['finished_unix']<ORIGIN[2] and c['finished_monotonic']<ORIGIN[3]
    assert all(type(c.get(k)) in (int,float) and math.isfinite(c[k]) for k in
        ['start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic','finished_unix','finished_monotonic'])
    assert c['common_seconds']==10800 and c['absolute_deadline_unix']==c['start_unix']+10800
    assert c['common_deadline_monotonic']==c['start_monotonic']+10800

    audit_observer=None;last_sample=begin;maximum_gap=0.;peak_rss=0;sticky_error=None;resource_samples=0
    def check(force=False):
        nonlocal last_sample,maximum_gap,peak_rss,sticky_error,resource_samples
        if sticky_error is not None:raise RuntimeError(sticky_error)
        try:
            observed=time.monotonic();maximum_gap=max(maximum_gap,observed-last_sample)
            need(observed-last_sample<=10,'root_closer_observation_gap10')
            need(observed-begin<60,'root_closure60_cap')
            if c is not None:
                need(time.time()<c['absolute_deadline_unix'] and observed<c['common_deadline_monotonic'],
                     'original10800_exhausted')
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
            need(sampled-begin<60,'root_closure60_cap')
            if c is not None:
                need(time.time()<c['absolute_deadline_unix'] and sampled<c['common_deadline_monotonic'],
                     'original10800_exhausted')
                need(abs((c['absolute_deadline_unix']-time.time())-(c['common_deadline_monotonic']-sampled))<=5,
                     'clock_disagreement')
            last_sample=sampled;resource_samples+=1
        except Exception as exc:
            sticky_error=str(exc) if isinstance(exc,RuntimeError) else 'root_closer_resource_observation_unconfirmed'
            raise RuntimeError(sticky_error) from exc
    def sha(p):
        h=hashlib.sha256()
        with p.open('rb') as stream:
            for b in iter(lambda:stream.read(2**20),b''):check();h.update(b)
        check();return h.hexdigest()
    check(force=True)
    assert sha(Path(__file__))==a.self_sha256
    assert sha(root/'campaign.json')==CAMPAIGN_SHA and sha(local(ORIGINAL_CLOSER))==ORIGINAL_CLOSER_SHA
    assert sha(root/'root-preparer-identity.json')==OLD_PREPARERS_SHA
    assert sha(local(FAILURE))==FAILURE_SHA and sha(local(CURRENT))==CURRENT_SHA
    failure,current=read(local(FAILURE)),read(local(CURRENT))
    assert failure['schema']=='uq2-original-root-closer-failure-v1'
    assert (failure['campaign_actual_session'],failure['campaign_actual_exit'],failure['campaign_actual_tool'])==(3588,1,'d7f40a')
    assert failure['campaign_sha256']==CAMPAIGN_SHA and failure['original_closer_sha256']==ORIGINAL_CLOSER_SHA
    assert (failure['closer_actual_exit'],failure['closer_actual_tool'],failure['error_type'],failure['source_line'])==(1,'80def1','AssertionError',93)
    assert failure['raw_trace_sha256'] is None and failure['root_receipt_created'] is False
    assert failure['failed_closer_preparers_sha256']==OLD_PREPARERS_SHA and failure['first_campaign_failure']==c['first_failure']
    assert failure['rejected_exact_historical_ref']==dict(path=LEGACY,sha256=LEGACY_SHA,cleanup_confirmed=False,source_unchanged=True,technical_procedure_passed=False,evidence_only_not_current_ownership_authority=True)
    assert current['schema']=='uq2-postfailure-known-current-observation-v1'
    assert current['campaign_sha256']==CAMPAIGN_SHA and (current['actual_session'],current['actual_exit'],current['actual_tool'])==(3588,1,'d7f40a')
    assert current['failed_closer_preparers_sha256']==OLD_PREPARERS_SHA and (current['failed_closer_actual_exit'],current['failed_closer_tool'])==(1,'80def1')
    assert current['known_exact_live']==[] and current['uncertain']==[] and current['signals_sent']==0
    assert current['old87_false_flags_unchanged'] is True and current['old87_unknown_leaf_not_retroqualified'] is True
    assert current['new_current_observation_only'] is True and current['qualification_of_current_root'] is False
    for n,h in [(COOR,COOR_SHA),(OWNER,OWNER_SHA),(LOCK,LOCK_SHA)]:assert sha(local(n))==h
    coor=imported('_L1_root_proven_coordinator',local(COOR));owner=imported('_L1_root_proven_owner',local(OWNER));locker=imported('_L1_root_proven_lock',local(LOCK))
    audit_observer=owner.StrictOwnedObserver();audit_observer.remember(coor.identities(preparers));check(force=True)
    known=coor.identities([c['owned_root']]+c.get('coordinator_bootstrap_identities',[])+c.get('owned_process_identities',[]))
    old_preparers=read(root/'root-preparer-identity.json');assert old_preparers['schema']==1
    known |= coor.identities(old_preparers['identities'])
    assert len(coor.identities(current['known_identities']))==current['known_count']==6294
    known |= coor.identities(current['known_identities']+current['observer_identities'])
    positive_known=set();legacy_evidence=None;legacy_ids=set()
    expected={Path(__file__).resolve().relative_to(WORK).as_posix():a.self_sha256,
        early.relative_to(WORK).as_posix():sha(early),'uq2/root-preparer-identity.json':OLD_PREPARERS_SHA,
        'uq2/campaign.json':CAMPAIGN_SHA,ORIGINAL_CLOSER:ORIGINAL_CLOSER_SHA,FAILURE:FAILURE_SHA,CURRENT:CURRENT_SHA};bad=[];audit=None;checked=0
    uncertainty=[]
    def retained_cleanup_uncertainty(record,scope,supervisor=False):
        if record.get('cleanup_confirmed') is not True:
            uncertainty.append(dict(scope=scope,reason='saved_cleanup_not_confirmed'))
        for field in ('cleanup_uncertainty','leaf_cleanup_uncertainty','uncertain_owned'):
            if record.get(field):uncertainty.append(dict(scope=scope,reason='saved_'+field,evidence=record[field]))
        ob=record.get('cleanup_observation')
        if supervisor and (type(ob) is not dict or ob.get('unresolved')!=[] or ob.get('denial_count')!=0):
            uncertainty.append(dict(scope=scope,reason='saved_observation_denied_unresolved_or_missing',evidence=ob))
    retained_cleanup_uncertainty(c,'campaign')
    for ref in c.get('supervisors',[]):
        p=local(ref['path']);assert sha(p)==ref['sha256'];r=read(p);expected[ref['path']]=ref['sha256']
        retained_cleanup_uncertainty(r,ref['path'],True)
        known|=coor.identities(r.get('owned_process_identities',[])+r.get('observed_worker_roots',[]))
        if r.get('owned_root'):known|=coor.identities([r['owned_root']])
    manifest_path=root/'manifest.json';m=None
    if manifest_path.is_file():
        assert sha(manifest_path)==c['manifest_sha256'];m=read(manifest_path)
        expected.update(m['immutable_files']);expected['uq2/manifest.json']=c['manifest_sha256'];expected['uq2/verification-plan.json']=c['verification_plan_sha256']
        expected[m['authority_checkpoint']['path']]=m['authority_checkpoint']['sha256']
        for task in m['tasks']:
            expected.update({task['source']+'/'+n:h for n,h in task['files'].items()})
        for n,h in m['immutable_files'].items():
            if n.endswith('.json') and ('terminal-root-closure' in Path(n).name or n==m['stage0_root_closure']['path']):
                proof=read(local(n))
                if 'owned_identities' in proof and 'closure_preparer_identities' in proof:
                    if n=='uq1/terminal-root-closure.json':
                        # Exact historical pre-API failure: never a clean predecessor grant.
                        assert h=='c880e6625dfa1a52af9aab9847adbb9c1c519493e3e3d678d591237266bded15'
                        assert proof.get('cleanup_confirmed') is False and proof.get('source_unchanged') is False
                        assert proof.get('technical_procedure_passed') is False
                        assert proof.get('first_failure',{}).get('code')=='conflicting_input_pin'
                        assert proof.get('changed_source_or_core')==['missing-pair-manifest']
                        assert proof.get('uncertain_owned')==[dict(scope='campaign',reason='saved_cleanup_not_confirmed')]
                        assert c['bootstrap_recovery']['original_failure_preserved'] is True
                        assert c['bootstrap_recovery']['original_cleanup_confirmed'] is False
                        assert c['bootstrap_recovery']['original_source_unchanged'] is False
                        assert c['bootstrap_recovery']['evidence_sha256'][n]==h
                    elif n==LEGACY:
                        assert h==LEGACY_SHA and proof['schema']=='uar02-root-closure-v1'
                        assert proof['cleanup_confirmed'] is False and proof['source_unchanged'] is True
                        assert proof['technical_procedure_passed'] is False and proof['qualified_checks'] is None
                        assert proof['actual_exec_session'] is None and proof['actual_exec_exit_code_observed_by_root']==1
                        assert proof['actual_tool_evidence']=='ae1308' and proof['active_owned_processes']==[]
                        exact_uncertainty=[dict(action='leaf_cleanup_receipts',reason='missing_after_entry_started')]
                        assert proof['uncertain_owned']==proof['leaf_cleanup_uncertainty']==exact_uncertainty
                        assert proof['leaf_cleanup_confirmed'] is False and proof['first_failure']==proof['error_history'][0]
                        assert proof['first_failure']['code']=='child_nonzero_exit' and proof['first_failure']['phase']=='child_exit'
                        assert [v['code'] for v in proof['error_history']]==['child_nonzero_exit','mandatory_focused_child_failed','final_owned_cleanup_unconfirmed']
                        assert proof['model_fits']==proof['API_calls']==0
                        legacy_ids=coor.identities(proof['owned_identities']+proof['closure_preparer_identities'])
                        legacy_evidence=dict(path=n,sha256=h,cleanup_confirmed=False,source_unchanged=True,
                            technical_procedure_passed=False,uncertain_owned=proof['uncertain_owned'],
                            first_failure=proof['first_failure'],error_history=proof['error_history'],
                            scope='IMMUTABLE_EVIDENCE_ONLY_NOT_NEW_OWNERSHIP_AUTHORITY',unknown_leaf_retroqualified=False)
                        continue  # This exact false receipt contributes NO ownership authority.
                    else:
                        assert proof['cleanup_confirmed'] is True and proof['source_unchanged'] is True
                        if n in POSITIVE:
                            assert h==POSITIVE[n]
                            positive_known |= coor.identities(proof['owned_identities']+proof['closure_preparer_identities'])
                    known|=coor.identities(proof['owned_identities']+proof['closure_preparer_identities'])
        for key,slot in m['slots'].items():
            task=next(t for t in m['tasks'] if t['kind']==slot['kind']);prefix='uq2/'+slot['arm']+'/'+slot['code']+'/'
            if (root/slot['arm']/slot['code']).exists():
                expected.update({prefix+n:h for n,h in m['compiled_sha256'].items()});expected.update({prefix+n:h for n,h in task['files'].items()})
                expected[prefix+'protected_control.json']=task['control_recipe']['sha256']
                expected[prefix+'retention.json']=task['retention']['sha256']
                expected[prefix+'authority-checkpoint.json']=m['authority_checkpoint']['sha256']
        for entry in c['arms']:
            ref=entry['seal'];assert sha(local(ref['path']))==ref['sha256'];seal=read(local(ref['path']))
            expected[ref['path']]=ref['sha256'];expected.update(seal['files_sha256']);expected[entry['supervisor_path']]=entry['supervisor_sha256']
    else:bad.append('missing-pair-manifest')
    if c.get('independent_audit'):
        ref=c['independent_audit'];assert sha(local(ref['path']))==ref['sha256'];expected[ref['path']]=ref['sha256']
    assert legacy_evidence is not None and all(m['immutable_files'].get(n)==h for n,h in POSITIVE.items())
    assert legacy_ids<=positive_known,'Legacy87 exact IDs only observed through independently clean positive authority'
    def absent():
        check()
        observer=owner.StrictOwnedObserver();observer.remember(known)
        assert not observer.observe() and not observer.denials and not observer.final_check()['unresolved'],'Known root/child/preparer live or denied'
        check();return observer
    absent()
    with locker.ResearchLock(WORK/'alfa-hack-automl/test-runs/.owned-research.lock'):
        absent()
        for n,h in expected.items():
            check();p=local(n);checked+=1
            if not p.is_file() or sha(p)!=h:bad.append(n)
        absent();check()
        cleanup_ok=c.get('cleanup_confirmed') is True and not uncertainty
        passed=False  # FORCED: original UQ2 and original closer remain failed.
        result=dict(bootstrap_recovery=c.get('bootstrap_recovery'),schema='uq2-clean-negative-audit-root-closure-v1',status='UQ2_closed_clean_negative_audit_only',
            actual_exec_session=a.actual_exec_session,actual_exec_exit_code_observed_by_root=a.actual_exit_code,actual_tool_evidence=a.actual_tool_evidence,
            cleanup_confirmed=bool(cleanup_ok),source_unchanged=not bad,owned_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],
            closure_preparer_identities=preparers,early_preparer_receipt_sha256=expected[early.relative_to(WORK).as_posix()],active_owned_processes=[],uncertain_owned=uncertainty,changed_source_or_core=bad,
            audit_helper_source=dict(path=Path(__file__).resolve().relative_to(WORK).as_posix(),sha256=a.self_sha256),
            immutable_and_core_refs_rehashed=checked,original_common_seconds=10800,original_start_unix=c['start_unix'],
            original_deadline_unix=c['absolute_deadline_unix'],raw_parent_elapsed_seconds=c['elapsed_common_seconds'],
            technical_procedure_passed=False,original_full_procedure_passed=False,original_global_qualification='FAIL',
            first_failure=c.get('first_failure'),error_history=c['error_history'],
            original_failed_closer=dict(path=ORIGINAL_CLOSER,sha256=ORIGINAL_CLOSER_SHA,actual_exit=1,actual_tool='80def1',
                preparer_receipt_sha256=OLD_PREPARERS_SHA,preparer_identities=old_preparers['identities'],retroqualified=False,raw_trace_sha256=None),
            original_failed_closer_error_evidence=dict(path=FAILURE,sha256=FAILURE_SHA),
            prior_current_observation=dict(path=CURRENT,sha256=CURRENT_SHA,root_observed_tool='73ec8f',root_observed_exit=0,
                captured_observer_identities=current['observer_identities'],unknown_observer_shell_identity=None),
            exact_legacy87_evidence_only=legacy_evidence,legacy87_ids_already_covered_by_independent_positive_roots=True,
            own_cap_seconds=60,maximum_actual_resource_observation_gap_seconds=maximum_gap,
            peak_owned_tree_rss_mib=peak_rss/2**20,resource_observations=resource_samples,
            new_common_clock=False,original_clock=list(ORIGIN),
            independent_audit=c.get('independent_audit'),qualified_ML_metrics=audit.get('quality_metric') if passed else None,
            descriptive_retention_win=audit.get('descriptive_retention_win') if passed else None,
            official_default_ready=False,promotion=False,submit=False,official_score=None,new_model_fits=0,API_calls=0,
            own_actual_exec_exit_and_fresh_preparer_absence_required=True,
            scope='Known-owned clean-negative closure only; no scoring/qualification/new ownership from legacy87. Original UQ2/closer FAIL and unknown historical leaf remain unchanged.')
        check()
        with out.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False)
        check();absent();assert sha(Path(__file__))==a.self_sha256,'New audit helper changed after receipt write'
    check();print(json.dumps({k:result[k] for k in ['status','technical_procedure_passed','qualified_ML_metrics','descriptive_retention_win']}))
    return 0 if not bad and cleanup_ok else 1

if __name__=='__main__':raise SystemExit(main())
