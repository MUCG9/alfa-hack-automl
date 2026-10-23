"""Future root-only post-exit qualifier; own30s within original10800, no reset.
No public exports/STATE/Git writes. Actual tool/exit/session evidence is mandatory;
a genuine directexec null session stays None. Failed research outcomes stay null.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,math,os,re,sys,time
WORK=Path(__file__).resolve().parents[1]
COOR='run_lean_mvp_r2.py';COOR_SHA='43be86ece6c453641afdcc6f8eccef02d713986e2ac8bf3314756f0bb78e0818'
OWNER='support_component_coordinator.py';OWNER_SHA='8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8'
LOCK='alfa-hack-automl/tools/research_lock.py';LOCK_SHA='78a0441bb3b9ea60197e9a1a6e1087f6e4cd0886593ec54bcfc4e41c9abe5a45'

def read(p):return json.loads(p.read_text('utf-8'))
def local(n):
    p=(WORK/n).resolve();assert not Path(n).is_absolute() and p.is_relative_to(WORK);return p

def imported(n,p):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--self-sha256',required=True)
    ap.add_argument('--actual-exec-session',type=int,default=None);ap.add_argument('--actual-exit-code',type=int,required=True)
    ap.add_argument('--actual-tool-evidence',required=True);a=ap.parse_args();begin=time.monotonic()
    assert __debug__ and a.actual_tool_evidence.strip()
    root=WORK/'la1';c=read(root/'campaign.json');out=root/'terminal-root-closure.json';assert not out.exists()
    assert all(type(c.get(k)) in (int,float) and math.isfinite(c[k]) for k in
        ['start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic','finished_unix','finished_monotonic'])
    assert c['common_seconds']==10800 and abs(c['absolute_deadline_unix']-c['start_unix']-10800)<1e-6
    assert abs(c['common_deadline_monotonic']-c['start_monotonic']-10800)<1e-6
    def check():
        assert time.monotonic()-begin<30,'Root closure30s exhausted'
        assert time.time()<c['absolute_deadline_unix'] and time.monotonic()<c['common_deadline_monotonic'],'Original common deadline'
        assert abs((c['common_deadline_monotonic']-time.monotonic())-(c['absolute_deadline_unix']-time.time()))<=5
    def sha(p):
        h=hashlib.sha256()
        with p.open('rb') as stream:
            for b in iter(lambda:stream.read(2**20),b''):check();h.update(b)
        check();return h.hexdigest()
    assert sha(Path(__file__))==a.self_sha256
    for n,h in [(COOR,COOR_SHA),(OWNER,OWNER_SHA),(LOCK,LOCK_SHA)]:assert sha(local(n))==h
    coor=imported('_L1_root_proven_coordinator',local(COOR));owner=imported('_L1_root_proven_owner',local(OWNER));locker=imported('_L1_root_proven_lock',local(LOCK))
    import psutil
    known=coor.identities([c['owned_root']]+c.get('coordinator_bootstrap_identities',[])+c.get('owned_process_identities',[]))
    expected={};bad=[];audit=None;checked=0
    for ref in c.get('supervisors',[]):
        p=local(ref['path']);assert sha(p)==ref['sha256'];r=read(p);expected[ref['path']]=ref['sha256']
        known|=coor.identities(r.get('owned_process_identities',[])+r.get('observed_worker_roots',[]))
        if r.get('owned_root'):known|=coor.identities([r['owned_root']])
    manifest_path=root/'manifest.json';m=None
    if manifest_path.is_file():
        assert sha(manifest_path)==c['manifest_sha256'];m=read(manifest_path)
        expected.update(m['immutable_files']);expected['la1/manifest.json']=c['manifest_sha256'];expected['la1/verification-plan.json']=c['verification_plan_sha256']
        for n,h in m['immutable_files'].items():
            if n.endswith('.json') and ('terminal-root-closure' in Path(n).name or n==m['stage0_root_closure']['path']):
                proof=read(local(n))
                if 'owned_identities' in proof and 'closure_preparer_identities' in proof:
                    assert proof['cleanup_confirmed'] is True and proof['source_unchanged'] is True
                    known|=coor.identities(proof['owned_identities']+proof['closure_preparer_identities'])
        for key,slot in m['slots'].items():
            task=next(t for t in m['tasks'] if t['kind']==slot['kind']);prefix='la1/'+slot['arm']+'/'+slot['code']+'/'
            if (root/slot['arm']/slot['code']).exists():
                expected.update({prefix+n:h for n,h in m['compiled_sha256'].items()});expected.update({prefix+n:h for n,h in task['files'].items()})
                expected[prefix+'protected_control.json']=task['control_recipe']['sha256']
                if slot['kind']=='regression':expected[prefix+'champion_recipe_input.json']=m['champion']['sha256']
        for entry in c['arms']:
            ref=entry['seal'];assert sha(local(ref['path']))==ref['sha256'];seal=read(local(ref['path']))
            expected[ref['path']]=ref['sha256'];expected.update(seal['files_sha256']);expected[entry['supervisor_path']]=entry['supervisor_sha256']
    else:bad.append('missing-pair-manifest')
    if c.get('independent_audit'):
        ref=c['independent_audit'];assert sha(local(ref['path']))==ref['sha256'];audit=read(local(ref['path']));expected[ref['path']]=ref['sha256']
    def absent():
        observer=owner.StrictOwnedObserver();observer.remember(known)
        assert not observer.observe() and not observer.denials and not observer.final_check()['unresolved'],'Known root/child/preparer live or denied'
        return observer
    absent()
    with locker.ResearchLock(WORK/'alfa-hack-automl/test-runs/.owned-research.lock'):
        absent()
        for n,h in expected.items():
            check();p=local(n);checked+=1
            if not p.is_file() or sha(p)!=h:bad.append(n)
        absent();check()
        passed=(a.actual_exit_code==0 and c['pair_artifact_checks_passed'] is True and c['cleanup_confirmed'] is True
            and c['source_unchanged'] is True and not c['error_history'] and not bad
            and c.get('awake_guard',{}).get('release_API_verified') is True and audit is not None
            and audit.get('artifact_procedure_checks_passed') is True and audit.get('audit_within_original_common_clock') is True
            and len(c['arms'])==4 and set(c['slot_matrix'])=={'Ar','Br','Ac','Bc'})
        me=psutil.Process();preparers=[dict(pid=me.pid,create_time=me.create_time())];parent=me.parent()
        while parent is not None:
            birth=parent.create_time()
            if not any(Path(v).resolve()==Path(__file__).resolve() for v in parent.cmdline() if v and not v.startswith('-')):break
            assert parent.create_time()==birth;preparers.append(dict(pid=parent.pid,create_time=birth));parent=parent.parent()
        result=dict(status='whole_agent_L1_pair_verified' if passed else 'whole_agent_L1_pair_failed_or_unqualified',
            actual_exec_session=a.actual_exec_session,actual_exec_exit_code_observed_by_root=a.actual_exit_code,actual_tool_evidence=a.actual_tool_evidence,
            cleanup_confirmed=True,source_unchanged=not bad,owned_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],
            closure_preparer_identities=preparers,active_owned_processes=[],uncertain_owned=[],changed_source_or_core=bad,
            immutable_and_core_refs_rehashed=checked,original_common_seconds=10800,original_start_unix=c['start_unix'],
            original_deadline_unix=c['absolute_deadline_unix'],raw_parent_elapsed_seconds=c['elapsed_common_seconds'],
            technical_procedure_passed=passed,first_failure=c.get('first_failure'),error_history=c['error_history'],
            independent_audit=c.get('independent_audit'),qualified_ML_metrics=audit.get('quality_metric') if passed else None,
            descriptive_retention_win=audit.get('descriptive_retention_win') if passed else None,
            official_default_ready=False,promotion=False,submit=False,official_score=None,new_model_fits=0,API_calls=0,
            own_actual_exec_exit_and_fresh_preparer_absence_required=True,
            scope='Research-only equal-budget four-task/arm L1 initial admission; standard platform invocation qualification still missing.')
        check()
        with out.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False)
        check();absent()
    check();print(json.dumps({k:result[k] for k in ['status','technical_procedure_passed','qualified_ML_metrics','descriptive_retention_win']}))
    return 0 if not bad else 1

if __name__=='__main__':raise SystemExit(main())
