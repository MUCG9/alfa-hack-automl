"""Source-only future T7 launcher. Fresh10800 begins only at actual launch.
Exact m3 ML runtime is reused. Publication/private-env/terminal proof checks are
preflight; fresh source458/exact23 gates, both tasks and audit are inside10800.
Coordinator runs in this process; it must repeat predecessor absence underlock.
No SESSION_STATE mutation here; root records actual launch/terminal evidence.
"""
from pathlib import Path
import argparse,hashlib,json,math,os,runpy,subprocess,sys,time
import psutil

def need(value,code):
    if not value:raise RuntimeError(code)
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(2**20),b''):h.update(block)
    return h.hexdigest()
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def write(path,value,exclusive=False):
    raw=(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')
    if exclusive:
        with path.open('xb') as stream:stream.write(raw)
        return
    pending=path.with_name(path.name+'.pending')
    for attempt in range(21):
        try:pending.write_bytes(raw);os.replace(pending,path);return
        except PermissionError:
            if attempt==20:raise
            time.sleep(.05)
def identities(rows):
    result=set()
    for r in rows:
        p,b=r['pid'],r['create_time']
        need(type(p) is int and p>0 and type(b) in (int,float) and math.isfinite(b) and b>0,'invalid_predecessor_identity')
        result.add((p,float(b)))
    return result
def absent(known):
    for pid,birth in known:
        try:need(psutil.Process(pid).create_time()!=birth,'known_predecessor_still_live')
        except psutil.NoSuchProcess:pass

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--work-root',type=Path,required=True)
    ap.add_argument('--manifest-sha256');ap.add_argument('--expected-commit');ap.add_argument('--preflight-env',action='store_true')
    args=ap.parse_args();work=args.work_root.resolve();packet=work/'m4packet'
    def local(name):
        p=(work/name).resolve();need(not Path(name).is_absolute() and p.is_relative_to(work),'outside_work');return p
    # Values never enter argv, receipts, publication checks or stdout.
    cfg=load(work/'private/qwen.json')
    key=next((cfg[n] for n in ['api_key','key','token','OPENAI_API_KEY'] if cfg.get(n)),None)
    base=next((cfg[n] for n in ['base_url','api_base','OPENAI_BASE_URL'] if cfg.get(n)),'https://changellenge.up.railway.app/v1')
    need(isinstance(key,str) and key and str(base).rstrip('/')=='https://changellenge.up.railway.app/v1','authorized_private_environment_unavailable')
    if args.preflight_env:
        print(json.dumps(dict(authorized_private_environment_ready=True,API_calls=0,clock_assigned=False)));return 0
    need(args.manifest_sha256 and args.expected_commit and sha(packet/'manifest.json')==args.manifest_sha256,'manifest_binding_failed')
    m=load(packet/'manifest.json');coordinator=local('run_lean_mvp_r2.py')
    need(local(m['launcher'])==Path(__file__).resolve() and sha(Path(__file__))==m['launcher_sha256']
        and sha(coordinator)==m['coordinator_sha256'],'new_controller_or_launcher_source_changed')
    need(m['source_root']=='m3dev' and m['output_root']=='t7' and m['common_seconds']==10800
        and m['maximum_experiments']==9 and m['clock_assigned'] is False,'T7_contract_changed')
    need(not (packet/'launch.json').exists() and not (work/'t7').exists(),'no_resume_or_clock_reset')
    for name,h in m['immutable_files'].items():need(sha(local(name))==h,'immutable_ref_changed:'+name)
    known=set()
    for ref in m['terminal_predecessor_receipts']:
        need(sha(local(ref['path']))==ref['sha256'],'terminal_proof_changed')
        proof=load(local(ref['path']));need(proof['cleanup_confirmed'] is True and proof['source_unchanged'] is True,'predecessor_cleanup_unknown')
        if ref['schema']=='campaign_root_closure':
            need(proof['actual_exec_session']==88656 and proof['actual_exec_exit_code_observed_by_root']==1,'T6_failed_exec_binding')
        elif ref['schema']=='postfailure_audit_root_closure':
            need(proof['actual_exec_session']==43087 and proof['actual_exec_exit_code']==0,'class_audit_exec_binding')
        elif ref['schema']=='fresh_supervision_predecessor_closure':
            evidence=proof['actual_terminal_evidence']
            need(proof['status']=='fresh_prior_ownership_source_proof' and proof['active_owned_processes']==[]
                and proof['uncertain_owned']==[] and proof['source_refs_rehashed']==718
                and len(proof['owned_identities'])==468 and evidence['T6']['exit_code']==1
                and evidence['class_postfailure_audit']['exit_code']==0
                and evidence['supervision_contracts_r1']['exit_code']==1
                and evidence['supervision_contracts_r2']['exit_code']==0,'latest_supervision_cleanup_binding')
        else:raise RuntimeError('unknown_predecessor_schema')
        known|=identities(proof['owned_identities'])|identities(proof['closure_preparer_identities'])
    need({r['schema'] for r in m['terminal_predecessor_receipts']}=={'campaign_root_closure','postfailure_audit_root_closure','fresh_supervision_predecessor_closure'},'all_three_fresh_terminal_proofs_required')
    t5=load(local('m2packet/t5-terminal-closure.json'))
    need(t5['cleanup_confirmed'] is True and t5['source_unchanged'] is True,'retained_T5_cleanup_unknown')
    known|=identities(t5['owned_identities'])|identities(t5['closure_preparer_identities']);absent(known)
    git=['git','-c','safe.directory='+(work/'alfa-hack-automl').as_posix(),'-C',str(work/'alfa-hack-automl')]
    head=subprocess.check_output(git+['rev-parse','HEAD'],text=True).strip();need(head==args.expected_commit,'publication_commit_changed')
    prefix=m['publication_prefix']
    for public,path in [('launcher.py',Path(__file__)),('coordinator.py',coordinator),
        ('evaluator.py',local('repaired-mvp-r1-dev/evaluator_r4.py')),('lean-source.zip',local(m['archive']))]:
        need(hashlib.sha256(subprocess.check_output(git+['show','HEAD:'+prefix+'/'+public])).hexdigest()==sha(path),'published_source_changed:'+public)
    absent(known)  # Publication/preflight may take time; check again before clock.
    os.environ.update(OPENAI_API_KEY=key,OPENAI_BASE_URL=str(base),OPENAI_MODEL=m['requested_model'],
        AUTOML_REASONING_EFFORT=m['reasoning_effort'],PYTHONDONTWRITEBYTECODE='1')
    del cfg,key
    me=psutil.Process();launcher_ids=[dict(pid=me.pid,create_time=me.create_time())];parent=me.parent()
    while parent is not None:
        birth=parent.create_time()
        if not any(Path(v).resolve()==Path(__file__).resolve() for v in parent.cmdline() if not v.startswith('-')):break
        need(parent.create_time()==birth,'bootstrap_identity_changed');launcher_ids.append(dict(pid=parent.pid,create_time=birth));parent=parent.parent()
    start=time.time();deadline=start+10800
    r=dict(status='launching_new_T7',start_unix=start,absolute_deadline_unix=deadline,common_seconds=10800,
        launcher_identities=launcher_ids,manifest_sha256=args.manifest_sha256,git_commit=head,
        original_T6_failure_preserved=True,predecessor_exact_identity_count=len(known),promotion=False)
    write(packet/'launch.json',r,True)
    try:
        r.update(status='coordinator_running');write(packet/'launch.json',r)
        sys.argv=[str(coordinator),'--manifest',str(packet/'manifest.json'),'--manifest-sha256',args.manifest_sha256,
            '--launch','--common-start-unix',repr(start),'--deadline-unix',repr(deadline)]
        runpy.run_path(str(coordinator),run_name='__main__');r.update(status='coordinator_completed',coordinator_exit_code=0)
    except BaseException as exc:
        code=(0 if exc.code is None else exc.code if type(exc.code) is int else 1) if isinstance(exc,SystemExit) else 1
        r.update(status='coordinator_completed' if code==0 else 'coordinator_failed',coordinator_exit_code=code,exception_type=type(exc).__name__)
        raise
    finally:
        r.update(finished_unix=time.time(),elapsed_common_seconds=time.time()-start)
        if time.time()>=deadline:r.update(status='unqualified_common_deadline_exceeded',coordinator_exit_code=1)
        write(packet/'launch.json',r)
        if time.time()>=deadline:
            r.update(status='unqualified_terminal_write_over_common_deadline',coordinator_exit_code=1);write(packet/'launch.json',r);raise SystemExit(1)
    print(json.dumps(dict(status=r['status'],coordinator_exit_code=r['coordinator_exit_code'],elapsed_common_seconds=r['elapsed_common_seconds'])))
    return 0
if __name__=='__main__':raise SystemExit(main())
