"""Root qualification after actual METH03 terminal; no model or API imports."""
from pathlib import Path
import argparse,hashlib,json,time,psutil

w=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text('utf-8'))
def write(p,j):p.write_text(json.dumps(j,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--actual-exec-session',required=True,type=int)
    ap.add_argument('--actual-exit-code',required=True,type=int)
    ap.add_argument('--actual-tool-evidence',required=True)
    a=ap.parse_args();begin=time.monotonic();root=w/'meth03';c=read(root/'campaign.json')
    out=root/'terminal-root-closure.json';assert not out.exists()
    assert c.get('finished_unix') is not None and c.get('finished_monotonic') is not None
    assert c['common_seconds']==720 and abs(c['absolute_deadline_unix']-c['start_unix']-720)<1e-6
    assert abs(c['common_deadline_monotonic']-c['start_monotonic']-720)<1e-6
    def check():
        assert time.monotonic()-begin<30,'Root closure30s exhausted'
        assert time.time()<c['absolute_deadline_unix'] and time.monotonic()<c['common_deadline_monotonic'],'Original METH03 deadline exhausted'
    def local(n):
        p=(w/n).resolve();assert not Path(n).is_absolute() and p.is_relative_to(w);return p
    def sha(p):
        h=hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda:f.read(2**20),b''):check();h.update(b)
        check();return h.hexdigest()
    known={(x['pid'],x['create_time']) for x in [c['owned_root']]+c.get('coordinator_bootstrap_identities',[])+c.get('owned_process_identities',[])}
    bad=[];expected={};audit=None
    def merge(n,h):
        if n in expected and expected[n]!=h:bad.append('conflicting_pin:'+n)
        else:expected[n]=h
    for ref in c.get('supervisors',[]):
        p=local(ref['path']);assert sha(p)==ref['sha256'];sup=read(p);merge(ref['path'],ref['sha256'])
        for x in sup.get('owned_process_identities',[])+sup.get('observed_worker_roots',[]):known.add((x['pid'],x['create_time']))
        if sup.get('owned_root'):x=sup['owned_root'];known.add((x['pid'],x['create_time']))
    manifest=root/'manifest.json'
    if manifest.exists():
        assert sha(manifest)==c['manifest_sha256'];m=read(manifest)
        assert m['common_seconds']==720 and m['weights']=={'strong_control':.9,'new_component':.1} and m['model_fits']==0
        assert m['method_terminal_exec']['root_closure_sha256']=='2c67361da8f95875b35d124ac6c19d6cccba28c899f1e20dada88f3bec4ea283'
        for n,h in m['immutable_files'].items():merge(n,h)
    else:bad.append('missing-manifest')
    if c.get('independent_audit'):
        ref=c['independent_audit'];p=local(ref['path']);assert sha(p)==ref['sha256'];audit=read(p)
        assert audit['manifest_sha256']==c['manifest_sha256']
        for n,h in audit.get('generated_validation_artifacts_sha256',{}).items():merge(n,h)
    for n,h in expected.items():
        p=local(n)
        if not p.is_file() or sha(p)!=h:bad.append(n)
    live=[];uncertain=[]
    for pid,birth in sorted(known):
        try:
            if psutil.Process(pid).create_time()==birth:live.append(dict(pid=pid,create_time=birth))
        except psutil.NoSuchProcess:pass
        except (psutil.AccessDenied,OSError):uncertain.append(dict(pid=pid,create_time=birth))
    artifact_ok=(audit is not None and audit.get('artifact_integrity_checks_passed') is True
        and audit.get('audit_within_original_common_clock') is True and audit.get('all_five_cuts_complete') is True
        and audit.get('model_fits')==0 and audit.get('API_calls')==0)
    passed=(a.actual_exit_code==0 and c.get('status')=='completed_fixed_blend_pending_root_exec_and_closure'
        and c.get('cleanup_confirmed') is True and c.get('source_unchanged') is True and not c.get('error_history')
        and c.get('awake_guard',{}).get('release_API_verified') is True and not bad and not live and not uncertain and artifact_ok)
    me=psutil.Process();preparers=[dict(pid=me.pid,create_time=me.create_time())];parent=me.parent()
    while parent is not None:
        birth=parent.create_time()
        if not any(Path(v).resolve()==Path(__file__).resolve() for v in parent.cmdline() if v and not v.startswith('-')):break
        preparers.append(dict(pid=parent.pid,create_time=birth));parent=parent.parent()
    result=dict(status='fixed_component_blend_verified' if passed else 'fixed_component_blend_failed_or_unqualified',
        actual_exec_session=a.actual_exec_session,actual_exec_exit_code_observed_by_root=a.actual_exit_code,
        actual_tool_evidence=a.actual_tool_evidence,technical_procedure_passed=passed,
        original_common_seconds=720,original_start_unix=c['start_unix'],original_deadline_unix=c['absolute_deadline_unix'],
        raw_parent_elapsed_seconds=c['elapsed_common_seconds'],cleanup_confirmed=not live and not uncertain,source_unchanged=not bad,
        changed_or_conflicting_pins=bad,immutable_and_generated_refs_rehashed=len(expected),
        owned_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],closure_preparer_identities=preparers,
        active_owned_processes=live,uncertain_owned=uncertain,independent_artifact_integrity=artifact_ok,
        independent_audit={k:c['independent_audit'][k] for k in ['path','sha256']} if c.get('independent_audit') else None,
        first_failure=c.get('first_failure'),error_history=c.get('error_history',[]),
        qualified_ML_metrics=audit['quality_metric'] if passed else None,
        candidate_gates=audit['candidate_gates'] if passed else None,
        component_quality_gates_passed=audit['component_quality_gates_passed'] if passed else None,
        weights=dict(strong_control=.9,new_component=.1),model_fits=0,API_calls=0,full_refit=False,
        promotion=False,submit=False,official_score=None,own_actual_exec_exit_and_fresh_preparer_absence_required=True,
        scope='Predeclared validation-only blend of same METH01 protected SINGLE and ExtraTrees on five reused public cuts; no weight search, whole-agent promotion or new full refit.')
    check();write(out,result);digest=sha(out)
    write(w.parent/'outputs/method-blend-results.json',dict(result,root_closure_sha256=digest))
    (w.parent/'outputs/method-blend-results.txt').write_text(f"METH03: {result['status']}. Metrics: {result['qualified_ML_metrics']}. Quality gates: {result['component_quality_gates_passed']}. Original720s, no fits/API/fullrefit/default promotion.\n",encoding='utf-8')
    s=read(w/'SESSION_STATE.json')
    s['active_queue']=None if not live and not uncertain else dict(experiment='METH03_cleanup_unconfirmed',active_owned=live,uncertain_owned=uncertain,no_new_fits=True)
    s['method_fixed_blend']=dict(status=result['status'],exec_session=a.actual_exec_session,actual_exec_exit_code=a.actual_exit_code,
        root_closure='work/meth03/terminal-root-closure.json',root_closure_sha256=digest,technical_procedure_passed=passed,
        metrics=result['qualified_ML_metrics'],candidate_gates=result['candidate_gates'],promotion=False,
        original_common_seconds=720,original_deadline_unix=c['absolute_deadline_unix'])
    s['updated_epoch']=time.time();write(w/'SESSION_STATE.json',s);check()
    print(json.dumps({k:result[k] for k in ['status','technical_procedure_passed','qualified_ML_metrics','component_quality_gates_passed']}))
    return 0 if not bad and not live and not uncertain else 1

if __name__=='__main__':raise SystemExit(main())
