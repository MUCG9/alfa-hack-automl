"""Qualify closed cp1 receipts after the root observes its actual exec exit."""
from pathlib import Path
import argparse,hashlib,json,time,psutil

w=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text('utf-8'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--actual-exec-session',required=True,type=int)
    ap.add_argument('--actual-exit-code',required=True,type=int)
    ap.add_argument('--actual-tool-evidence',required=True)
    a=ap.parse_args();begin=time.monotonic();root=w/'cp1';c=read(root/'campaign.json')
    assert c.get('finished_unix') is not None and c.get('finished_monotonic') is not None
    assert c['common_seconds']==5400 and abs(c['absolute_deadline_unix']-c['start_unix']-5400)<1e-6
    assert abs(c['common_deadline_monotonic']-c['start_monotonic']-5400)<1e-6
    out=root/'terminal-root-closure.json';assert not out.exists()
    def check():
        assert time.monotonic()-begin<30,'Root closure30s exhausted'
        assert time.time()<c['absolute_deadline_unix'] and time.monotonic()<c['common_deadline_monotonic'],'Original pair clock exhausted'
    def sha(p):
        h=hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda:f.read(2**20),b''):check();h.update(b)
        check();return h.hexdigest()
    def local(n):
        p=(w/n).resolve();assert p.is_relative_to(w);return p
    known={(x['pid'],x['create_time']) for x in [c['owned_root']]+c.get('coordinator_bootstrap_identities',[])+c.get('owned_process_identities',[])}
    for ref in c.get('supervisors',[]):
        p=local(ref['path']);assert sha(p)==ref['sha256'];r=read(p)
        for x in r.get('owned_process_identities',[])+r.get('observed_worker_roots',[]):known.add((x['pid'],x['create_time']))
        if r.get('owned_root'):x=r['owned_root'];known.add((x['pid'],x['create_time']))
    live=[];uncertain=[]
    for pid,birth in sorted(known):
        try:
            if psutil.Process(pid).create_time()==birth:live.append(dict(pid=pid,create_time=birth))
        except psutil.NoSuchProcess:pass
        except (psutil.AccessDenied,OSError):uncertain.append(dict(pid=pid,create_time=birth))
    bad=[];checked=0;manifest=None;audit=None
    manifest_path=root/'manifest.json'
    if manifest_path.exists():
        assert sha(manifest_path)==c['manifest_sha256'];manifest=read(manifest_path)
        expected=dict(manifest['immutable_files']);expected['cp1/verification-plan.json']=c['verification_plan_sha256']
        for arm,meta in manifest['arms'].items():
            prefix='cp1/'+arm+'/r/'
            expected.update({prefix+n:h for n,h in meta['compiled_sha256'].items()})
            expected.update({prefix+n:h for n,h in manifest['task']['files'].items()})
            expected[prefix+'protected_control.json']=manifest['task']['control_recipe']['sha256']
            if arm=='B':expected[prefix+'champion_recipe_input.json']=manifest['champion']['sha256']
        for arm in c.get('arms',[]):
            seal=local(arm['seal']['path']);assert sha(seal)==arm['seal']['sha256']
            expected.update(read(seal)['files_sha256'])
        for n,h in expected.items():
            p=local(n);checked+=1
            if not p.is_file() or sha(p)!=h:bad.append(n)
    else:bad.append('missing-pair-manifest')
    if c.get('independent_audit'):
        p=local(c['independent_audit']['path']);assert sha(p)==c['independent_audit']['sha256'];audit=read(p)
    passed=(a.actual_exit_code==0 and c.get('pair_artifact_checks_passed') is True
        and c.get('cleanup_confirmed') is True and c.get('source_unchanged') is True
        and not c.get('error_history') and c.get('awake_guard',{}).get('release_API_verified') is True
        and not bad and not live and not uncertain and audit is not None
        and audit.get('artifact_procedure_checks_passed') is True and audit.get('audit_within_original_common_clock') is True)
    me=psutil.Process();preparers=[dict(pid=me.pid,create_time=me.create_time())];parent=me.parent()
    while parent is not None:
        birth=parent.create_time()
        if not any(Path(v).resolve()==Path(__file__).resolve() for v in parent.cmdline() if v and not v.startswith('-')):break
        preparers.append(dict(pid=parent.pid,create_time=birth));parent=parent.parent()
    result=dict(status='whole_regression_pair_verified' if passed else 'whole_regression_pair_failed_or_unqualified',
        actual_exec_session=a.actual_exec_session,actual_exec_exit_code_observed_by_root=a.actual_exit_code,
        actual_tool_evidence=a.actual_tool_evidence,cleanup_confirmed=not live and not uncertain,source_unchanged=not bad,
        owned_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],closure_preparer_identities=preparers,
        active_owned_processes=live,uncertain_owned=uncertain,changed_source_or_core=bad,immutable_and_core_refs_rehashed=checked,
        original_start_unix=c['start_unix'],original_deadline_unix=c['absolute_deadline_unix'],original_common_seconds=5400,
        raw_parent_elapsed_seconds=c['elapsed_common_seconds'],technical_procedure_passed=passed,
        first_failure=c.get('first_failure'),error_history=c.get('error_history',[]),
        independent_audit=c.get('independent_audit'),qualified_ML_metrics=audit.get('quality_metric') if passed else None,
        descriptive_retention_win=audit.get('descriptive_retention_win') if passed else None,
        strong_regression_control_RMSE=35.44723155783769,retained_T5_regression_RMSE=34.86622087872278,
        promotion=False,submit=False,official_score=None,new_model_fits=0,API_calls=0,
        scope='Whole regression-agent A/B only; reused public, confirmation overlaps HPO. No two-task default promotion or blind/private claim.',
        own_actual_exec_exit_and_fresh_preparer_absence_required=True)
    check();write(out,result);check();result['root_closure_sha256']=sha(out)
    write(w.parent/'outputs/champion-pair-results.json',result)
    (w.parent/'outputs/champion-pair-results.txt').write_text(
        f"Champion whole regression-agent A/B: {result['status']}; actual exec{a.actual_exec_session} exit{a.actual_exit_code}.\n"
        +f"Metrics: {result['qualified_ML_metrics']}; V16=35.4472315578, T5=34.8662208787.\n"
        +f"Descriptive retention criterion: {result['descriptive_retention_win']}; elapsed{c['elapsed_common_seconds']:.3f}s / original5400s.\n"
        +'Reused public; confirmation overlaps HPO. No default promotion/official score/submit.\n',encoding='utf-8')
    state=w/'SESSION_STATE.json';s=read(state);s['active_queue']=None
    s['champion_pair']=dict(status=result['status'],exec_session=a.actual_exec_session,actual_exec_exit_code=a.actual_exit_code,
        technical_procedure_passed=passed,root_closure='work/cp1/terminal-root-closure.json',root_closure_sha256=sha(out),
        metrics=result['qualified_ML_metrics'],descriptive_retention_win=result['descriptive_retention_win'],promotion=False,
        original_common_seconds=5400,original_deadline_unix=c['absolute_deadline_unix'])
    s['next'][0]='Champion pair terminal: read actual audit/rootclosure/tool exit and fresh root/preparer absence. Retain V11/V16/T5 until quality gates. Then priority ready measured class context or METH01 components; source-only packets are not executed ML evidence.'
    s['updated_epoch']=time.time();tmp=state.with_suffix('.pending');write(tmp,s);tmp.replace(state)
    check()
    print(json.dumps({k:result[k] for k in ['status','actual_exec_exit_code_observed_by_root','technical_procedure_passed','qualified_ML_metrics','descriptive_retention_win','root_closure_sha256']}))
    return 0 if not bad and not live and not uncertain else 1

if __name__=='__main__':raise SystemExit(main())
