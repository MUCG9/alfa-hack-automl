"""Run only after root observes actual exec79591 terminal; no fitting/API."""
from pathlib import Path
import argparse,hashlib,json,math,re,time,psutil
w=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text('utf-8'))
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(p,check=lambda:None):
    h=hashlib.sha256()
    with p.open('rb') as stream:
        for b in iter(lambda:stream.read(2**20),b''):check();h.update(b)
    check();return h.hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--actual-exit-code',type=int,required=True);ap.add_argument('--actual-tool-evidence',required=True)
    a=ap.parse_args();begin=time.monotonic();c=read(w/'cs0/campaign.json')
    assert c.get('finished_unix') is not None and c.get('finished_monotonic') is not None
    assert c['absolute_deadline_unix']-c['start_unix']==900
    assert abs(c['common_deadline_monotonic']-c['start_monotonic']-900)<1e-6
    out=w/'cs0/terminal-root-closure.json';assert not out.exists()
    def check():
        assert time.monotonic()-begin<30,'Root closure30s exceeded'
        assert time.time()<c['absolute_deadline_unix'] and time.monotonic()<c['common_deadline_monotonic'],'Original Stage0 deadline'
        assert abs((c['common_deadline_monotonic']-time.monotonic())-(c['absolute_deadline_unix']-time.time()))<=5
    known={(x['pid'],x['create_time']) for x in [c['owned_root']]+c.get('coordinator_bootstrap_identities',[])}
    for ref in c.get('supervisors',[]):
        p=w/ref['path'];assert sha(p)==ref['sha256'];r=read(p)
        for x in r.get('owned_process_identities',[])+r.get('observed_worker_roots',[]):known.add((x['pid'],x['create_time']))
        if r.get('owned_root'):x=r['owned_root'];known.add((x['pid'],x['create_time']))
    live=[];uncertain=[]
    for pid,birth in sorted(known):
        try:
            if psutil.Process(pid).create_time()==birth:live.append(dict(pid=pid,create_time=birth))
        except psutil.NoSuchProcess:pass
        except (psutil.AccessDenied,OSError):uncertain.append(dict(pid=pid,create_time=birth))
    bad=[]
    for n,h in c['immutable_files'].items():
        p=(w/n).resolve();assert p.is_relative_to(w)
        if not p.is_file() or sha(p,check)!=h:bad.append(n)
    prepared=read(w/'cs-stage0-packet/manifest.json')
    assert sha(w/'cs-stage0-packet/manifest.json')=='5160562be127dc6130a1f3349a21b552c8aac526ead484048982716b037aa1c1'
    flat=w/'cs0/flat';flat_bad=[]
    if c.get('technical_checks_passed') is True:
        expected=set(prepared['compiled_sha256'])|{'tests/fixtures/champion_seed/champion.json','tests/fixtures/champion_seed/protected_control.json','tests/test_pinned_champion_seed.py'}
        actual={p.relative_to(flat).as_posix() for p in flat.rglob('*') if p.is_file()}
        if actual!=expected:flat_bad.append('inventory')
        for n,h in prepared['compiled_sha256'].items():
            if sha(flat/n,check)!=h:flat_bad.append(n)
        for n in ['champion.json','protected_control.json']:
            if sha(flat/'tests/fixtures/champion_seed'/n,check)!=sha(w/'csdev/tests/fixtures/champion_seed'/n,check):flat_bad.append(n)
        if sha(flat/'tests/test_pinned_champion_seed.py',check)!=c['flat_pinned_test_adaptation']['transformed_sha256']:flat_bad.append('flat-test')
    source_ok=not bad and not flat_bad;cleanup_ok=not live and not uncertain
    gates=c.get('gates',[]);counts={g['name']:g['checks'] for g in gates}
    source_counts_ok=False
    if (w/'cs0/source/results.json').exists():
        src=read(w/'cs0/source/results.json')
        source_counts_ok=(src.get('passed') is True and src.get('unique_checks_passed')==471
            and src.get('unique_checks_skipped')==0 and src.get('source_sha256')==prepared['compiled_sha256'])
    passed=(a.actual_exit_code==0 and c.get('technical_checks_passed') is True
        and c.get('cleanup_confirmed') is True and c.get('source_unchanged') is True
        and not c.get('error_history') and c.get('awake_guard',{}).get('release_API_verified') is True
        and source_ok and cleanup_ok and source_counts_ok
        and counts=={'source':471,'exact-default':23,'exact-optin':1})
    me=psutil.Process();preparers=[dict(pid=me.pid,create_time=me.create_time())];parent=me.parent()
    while parent is not None:
        birth=parent.create_time()
        if not any(Path(v).resolve()==Path(__file__).resolve() for v in parent.cmdline() if v and not v.startswith('-')):break
        assert parent.create_time()==birth;preparers.append(dict(pid=parent.pid,create_time=birth));parent=parent.parent()
    result=dict(status='technical_stage0_verified' if passed else 'technical_stage0_failed_or_unqualified',
        actual_exec_session=79591,actual_exec_exit_code_observed_by_root=a.actual_exit_code,
        actual_tool_evidence=a.actual_tool_evidence,cleanup_confirmed=cleanup_ok,source_unchanged=source_ok,
        active_owned_processes=live,uncertain_owned=uncertain,
        owned_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],closure_preparer_identities=preparers,
        original_common_seconds=900,original_start_unix=c['start_unix'],original_deadline_unix=c['absolute_deadline_unix'],
        raw_parent_elapsed_seconds=c['elapsed_common_seconds'],raw_parent_status=c['status'],
        raw_parent_first_failure=c.get('first_failure'),raw_parent_error_history=c.get('error_history',[]),
        immutable_refs_rehashed=len(c['immutable_files']),changed_source=bad,changed_flat=flat_bad,
        source_checks=471 if passed else None,source_skipped=0 if passed else None,
        exact_default_repeated=23 if passed else None,extra_exact_pinned_optin=1 if passed else None,
        source_compilation_matches_prepared_archive=source_counts_ok,
        technical_procedure_passed=passed,ML_quality_metric=None,promotion=False,submit=False,
        root_exporter_actual_exit_and_fresh_preparer_absence_required=True,root_new_fits=0,root_API_calls=0)
    check();write(out,result);check()
    result['root_closure_sha256']=sha(out)
    write(w.parent/'outputs/champion-stage0-results.json',result)
    (w.parent/'outputs/champion-stage0-results.txt').write_text(
        f"Champion Stage0: {result['status']}; actual exec79591 exit{a.actual_exit_code}.\n"
        +f"Source471/0skips; exact23 repeated +1pinned ON: {passed}. Исходный общий лимит900с, elapsed{c['elapsed_common_seconds']:.3f}с.\n"
        +'Это техническая проверка, без нового публичного ML-результата. Следующий полный A/B требует своего frozen protocol и clock.\n',encoding='utf-8')
    state=w/'SESSION_STATE.json';s=read(state)
    s['champion_stage0'].update(status=result['status'],actual_exec_exit_code=a.actual_exit_code,
        root_closure='work/cs0/terminal-root-closure.json',root_closure_sha256=sha(out),
        technical_procedure_passed=passed,public_ML_metric=None)
    s['active_queue']=None
    s['next'][0]='Champion Stage0 terminal: read cs0/terminal-root-closure.json and actual root-helper exit, fresh preparers absent before nextheavy. If technicalPASS, review/publish champion-pair-next-dev full regression-agent A/B and independent audit binding; assign its5400s once at actual launch only. User method-expansion METH01..06 registry also queued; no source-only MLgain. PreserveT5/V11/V16.'
    s['updated_epoch']=time.time();tmp=state.with_suffix('.pending');write(tmp,s);tmp.replace(state)
    print(json.dumps({k:result[k] for k in ['status','actual_exec_exit_code_observed_by_root','cleanup_confirmed','source_unchanged','technical_procedure_passed','raw_parent_elapsed_seconds','root_closure_sha256']}))
    return 0 if cleanup_ok and source_ok else 1
if __name__=='__main__':raise SystemExit(main())
