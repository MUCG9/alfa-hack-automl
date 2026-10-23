"""Root post-exit qualification of KERN01; no fits or model/API imports."""
from pathlib import Path
import argparse,hashlib,json,time,psutil

w=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text('utf-8'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--self-sha256',required=True)
    ap.add_argument('--actual-exec-session',type=int,default=None)
    ap.add_argument('--actual-exit-code',required=True,type=int)
    ap.add_argument('--actual-tool-evidence',required=True)
    a=ap.parse_args();begin=time.monotonic()
    assert __debug__ and hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.self_sha256
    root=w/'kern01';c=read(root/'campaign.json')
    assert c.get('finished_unix') is not None and c.get('finished_monotonic') is not None
    assert c['common_seconds']==10800 and abs(c['absolute_deadline_unix']-c['start_unix']-10800)<1e-6
    assert abs(c['common_deadline_monotonic']-c['start_monotonic']-10800)<1e-6
    out=root/'terminal-root-closure.json';assert not out.exists()
    def check():
        assert time.monotonic()-begin<30,'Root closure30s exhausted'
        assert time.time()<c['absolute_deadline_unix'] and time.monotonic()<c['common_deadline_monotonic'],'Original KERN01 clock exhausted'
    def local(n):
        p=(w/n).resolve();assert p.is_relative_to(w);return p
    def sha(p):
        h=hashlib.sha256()
        with p.open('rb') as f:
            for b in iter(lambda:f.read(2**20),b''):check();h.update(b)
        check();return h.hexdigest()
    known={(x['pid'],x['create_time']) for x in [c['owned_root']]+c.get('coordinator_bootstrap_identities',[])+c.get('owned_process_identities',[])}
    for ref in c.get('supervisors',[]):
        p=local(ref['path']);assert sha(p)==ref['sha256'];r=read(p)
        for x in r.get('owned_process_identities',[])+r.get('observed_worker_roots',[]):known.add((x['pid'],x['create_time']))
        if r.get('owned_root'):x=r['owned_root'];known.add((x['pid'],x['create_time']))
    live=[];uncertain=[]
    for pid,birth in sorted(known):
        check()
        try:
            if psutil.Process(pid).create_time()==birth:live.append(dict(pid=pid,create_time=birth))
        except psutil.NoSuchProcess:pass
        except (psutil.AccessDenied,OSError):uncertain.append(dict(pid=pid,create_time=birth))
    bad=[];expected={};audit=None
    def merge(n,h):
        if n in expected and expected[n]!=h:bad.append('conflicting_pin:'+n)
        else:expected[n]=h
    manifest=root/'manifest.json'
    if manifest.exists():
        assert sha(manifest)==c['manifest_sha256'];m=read(manifest)
        for n,h in list(m['immutable_files'].items())+list(m['setup_deployment_sha256'].items()):merge(n,h)
        merge('kern01/verification-plan.json',c['verification_plan_sha256'])
        for row in c.get('workers',[]):
            merge(row['supervisor_path'],row['supervisor_sha256'])
            p=local(row['seal']['path']);assert sha(p)==row['seal']['sha256'];merge(row['seal']['path'],row['seal']['sha256'])
            for n,h in read(p)['files_sha256'].items():merge(n,h)
        for n,h in expected.items():
            p=local(n)
            if not p.is_file() or sha(p)!=h:bad.append(n)
    else:bad.append('missing-manifest')
    if c.get('independent_audit'):
        p=local(c['independent_audit']['path']);assert sha(p)==c['independent_audit']['sha256'];audit=read(p)
    artifact_ok=(audit is not None and audit.get('artifact_integrity_checks_passed') is True
        and audit.get('audit_within_original_common_clock') is True)
    passed=(a.actual_exit_code==0 and c.get('component_procedure_passed') is True
        and c.get('cleanup_confirmed') is True and c.get('source_unchanged') is True
        and not c.get('error_history') and c.get('awake_guard',{}).get('release_API_verified') is True
        and not bad and not live and not uncertain and artifact_ok and audit.get('all_workers_succeeded') is True)
    me=psutil.Process();preparers=[dict(pid=me.pid,create_time=me.create_time())];parent=me.parent()
    while parent is not None:
        birth=parent.create_time()
        if not any(Path(v).resolve()==Path(__file__).resolve() for v in parent.cmdline() if v and not v.startswith('-')):break
        preparers.append(dict(pid=parent.pid,create_time=birth));parent=parent.parent()
    result=dict(status='component_screen_verified' if passed else 'component_screen_failed_or_unqualified',
        actual_exec_session=a.actual_exec_session,actual_exec_exit_code_observed_by_root=a.actual_exit_code,
        actual_tool_evidence=a.actual_tool_evidence,cleanup_confirmed=not live and not uncertain,source_unchanged=not bad,
        owned_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],closure_preparer_identities=preparers,
        active_owned_processes=live,uncertain_owned=uncertain,changed_or_conflicting_pins=bad,immutable_and_core_refs_rehashed=len(expected),
        original_start_unix=c['start_unix'],original_deadline_unix=c['absolute_deadline_unix'],original_common_seconds=10800,
        raw_parent_elapsed_seconds=c['elapsed_common_seconds'],technical_procedure_passed=passed,
        independent_artifact_integrity=artifact_ok,first_failure=c.get('first_failure'),error_history=c.get('error_history',[]),
        independent_audit=c.get('independent_audit'),qualified_ML_metrics=audit.get('quality_metric') if passed else None,
        candidate_gates=audit.get('registered_component_decisions') if passed else None,
        component_quality_gates_passed=audit.get('component_quality_gates_passed') if passed else None,
        promotion=False,full_refit=False,submit=False,official_score=None,new_model_fits=0,API_calls=0,
        own_actual_exec_exit_and_fresh_preparer_absence_required=True,
        scope='Fixed strong/matchedidentity/RBF component screen on reused public cuts. Strong-vs-new is a complete recipe package; matchedidentity-vs-RBF isolates representation. No wholeagent/refit/official qualification.')
    # Root still must observe this helper terminal and its exact preparers absent.
    check()
    with out.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False)
    check()
    print(json.dumps({k:result[k] for k in ['status','actual_exec_exit_code_observed_by_root',
        'technical_procedure_passed','cleanup_confirmed','source_unchanged','raw_parent_elapsed_seconds']}))
    return 0 if not bad and not live and not uncertain else 1
if __name__=='__main__':raise SystemExit(main())
