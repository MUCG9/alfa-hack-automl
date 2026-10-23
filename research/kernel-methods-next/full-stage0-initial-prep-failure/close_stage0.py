"""Future root-only kern0 terminal closure, bounded30s inside original900.
Run only after root observes the actual Stage0 terminal exec. No STATE, public
report, model, API, clock reset, signals or arbitrary process scan occurs here.
"""
from pathlib import Path
import argparse,ast,hashlib,json,math,os,time,psutil

WORK=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text('utf-8'))
def sha(p,check=lambda:None):
    h=hashlib.sha256()
    with p.open('rb') as stream:
        for b in iter(lambda:stream.read(2**20),b''):check();h.update(b)
    check();return h.hexdigest()
def local(name):
    p=(WORK/name).resolve()
    assert not Path(name).is_absolute() and p.is_relative_to(WORK)
    return p
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--self-sha256',required=True)
    ap.add_argument('--prepared-manifest-sha256',required=True)
    ap.add_argument('--actual-exec-session',type=int,default=None)
    ap.add_argument('--actual-exit-code',type=int,required=True)
    ap.add_argument('--actual-tool-evidence',required=True)
    a=ap.parse_args();begin=time.monotonic()
    assert __debug__ and sha(Path(__file__))==a.self_sha256
    root=WORK/'kern0';c=read(root/'campaign.json')
    assert all(type(c.get(n)) in (int,float) and math.isfinite(c[n]) for n in
        ['start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic',
         'finished_unix','finished_monotonic'])
    assert c['absolute_deadline_unix']-c['start_unix']==900
    assert abs(c['common_deadline_monotonic']-c['start_monotonic']-900)<1e-6
    out=root/'terminal-root-closure.json';assert not out.exists()
    manifest=WORK/'kern-stage0-packet/manifest.json'
    assert sha(manifest)==a.prepared_manifest_sha256==c['prepared_manifest_sha256']
    prepared=read(manifest)
    assert prepared['source_root']=='kern00' and prepared['source_expected_checks']==483
    assert sum(prepared['registry'].values())==483 and len(prepared['compiled_sha256'])==70
    assert prepared['exact_repeated_expected_checks']==23
    assert prepared['exact_flat_kernel_checks']==12
    def check():
        assert time.monotonic()-begin<30,'Root closure30s exceeded'
        assert time.time()<c['absolute_deadline_unix'] and time.monotonic()<c['common_deadline_monotonic'],'Original Stage0 deadline'
        assert abs((c['common_deadline_monotonic']-time.monotonic())-(c['absolute_deadline_unix']-time.time()))<=5
    known={(x['pid'],x['create_time']) for x in [c['owned_root']]+c.get('coordinator_bootstrap_identities',[])
        +c.get('owned_process_identities',[])}
    supervisors_ok=True
    for ref in c.get('supervisors',[]):
        p=local(ref['path']);assert sha(p,check)==ref['sha256'];r=read(p)
        supervisors_ok &= r.get('status')=='ok' and r.get('exit_code')==0 and r.get('cleanup_confirmed') is True
        for x in r.get('owned_process_identities',[])+r.get('observed_worker_roots',[]):known.add((x['pid'],x['create_time']))
        if r.get('owned_root'):x=r['owned_root'];known.add((x['pid'],x['create_time']))
    def observe():
        live=[];uncertain=[]
        for pid,birth in sorted(known):
            check()
            try:
                if psutil.Process(pid).create_time()==birth:live.append(dict(pid=pid,create_time=birth))
            except psutil.NoSuchProcess:pass
            except (psutil.AccessDenied,OSError):uncertain.append(dict(pid=pid,create_time=birth))
        return live,uncertain
    live,uncertain=observe();bad=[];flat_bad=[]
    if not c.get('immutable_files'):bad.append('missing_immutable_input_map')
    for name,digest in c.get('immutable_files',{}).items():
        p=local(name)
        if not p.is_file() or sha(p,check)!=digest:bad.append(name)
    flat=root/'flat'
    if c.get('technical_checks_passed') is True:
        expected=set(prepared['compiled_sha256'])|{'tests/test_kernel_profiles.py','tests/fixtures/cp1_capabilities.json'}
        if {p.relative_to(flat).as_posix() for p in flat.rglob('*') if p.is_file()}!=expected:flat_bad.append('inventory')
        for name,digest in prepared['compiled_sha256'].items():
            if sha(flat/name,check)!=digest:flat_bad.append(name)
        deployed=c.get('flat_deployment_sha256',{})
        if set(deployed)!={'kern0/flat/'+name for name in expected}:flat_bad.append('deployment_inventory')
        for name,digest in deployed.items():
            if sha(local(name),check)!=digest:flat_bad.append(name)
        adaptation=c.get('flat_kernel_adaptation',{})
        if (adaptation.get('assertion_changes')!=0 or adaptation.get('assertions_AST_equal') is not True
                or adaptation.get('test_bodies_AST_equal_after_inverse_mock_module_resolution') is not True
                or adaptation.get('test_methods')!=12):flat_bad.append('adaptation_contract')
        mapping=read(WORK/'kernel-methods-next-dev/flat-mapping-static-proof.json')['module_map']
        def bodies(path,reverse=False):
            tree=ast.parse(path.read_text('utf-8'))
            if reverse:
                for node in ast.walk(tree):
                    if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='patch' and node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str):
                        for old,new in mapping.items():
                            if node.args[0].value.startswith(new+'.'):
                                node.args[0].value=old+node.args[0].value[len(new):];break
            return {n.name:ast.dump(n,include_attributes=False) for cls in tree.body if isinstance(cls,ast.ClassDef)
                for n in cls.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')}
        def assertions(path):
            return [ast.dump(n,include_attributes=False) for n in ast.walk(ast.parse(path.read_text('utf-8')))
                if isinstance(n,ast.Assert) or isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr.startswith('assert')]
        original=WORK/'kern00/tests/test_kernel_profiles.py';adapted=flat/'tests/test_kernel_profiles.py'
        if len(bodies(original))!=12 or bodies(original)!=bodies(adapted,True):flat_bad.append('test_bodies')
        if assertions(original)!=assertions(adapted):flat_bad.append('assertions')
        if sha(flat/'tests/fixtures/cp1_capabilities.json',check)!=sha(WORK/'kern00/tests/fixtures/cp1_capabilities.json',check):flat_bad.append('capabilities')
    counts={g['name']:g['checks'] for g in c.get('gates',[])}
    for gate in c.get('gates',[]):
        name=gate.get('result',gate.get('log'));assert name and sha(local(name),check)==gate['sha256']
    source_counts_ok=False
    if (root/'source/results.json').exists():
        src=read(root/'source/results.json')
        source_counts_ok=(src.get('passed') is True and src.get('unique_checks_passed')==483
            and src.get('unique_checks_skipped')==0 and src.get('source_sha256')==prepared['compiled_sha256'])
    live,uncertain=observe();source_ok=not bad and not flat_bad;cleanup_ok=not live and not uncertain
    passed=(a.actual_exit_code==0 and c.get('technical_checks_passed') is True
        and c.get('cleanup_confirmed') is True and c.get('source_unchanged') is True
        and not c.get('error_history') and c.get('awake_guard',{}).get('release_API_verified') is True
        and supervisors_ok and source_ok and cleanup_ok and source_counts_ok
        and counts=={'source':483,'exact-default':23,'exact-optin':12})
    me=psutil.Process();preparers=[dict(pid=me.pid,create_time=me.create_time())];parent=me.parent()
    while parent is not None:
        birth=parent.create_time()
        if not any(Path(v).resolve()==Path(__file__).resolve() for v in parent.cmdline() if v and not v.startswith('-')):break
        assert parent.create_time()==birth;preparers.append(dict(pid=parent.pid,create_time=birth));parent=parent.parent()
    result=dict(status='technical_stage0_verified' if passed else 'technical_stage0_failed_or_unqualified',
        actual_exec_session=a.actual_exec_session,actual_exec_exit_code_observed_by_root=a.actual_exit_code,
        actual_tool_evidence=a.actual_tool_evidence,cleanup_confirmed=cleanup_ok,source_unchanged=source_ok,
        active_owned_processes=live,uncertain_owned=uncertain,
        owned_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],closure_preparer_identities=preparers,
        prepared_manifest_sha256=a.prepared_manifest_sha256,closer_source_sha256=a.self_sha256,
        original_common_seconds=900,original_start_unix=c['start_unix'],original_deadline_unix=c['absolute_deadline_unix'],
        raw_parent_elapsed_seconds=c['elapsed_common_seconds'],raw_parent_status=c['status'],
        raw_parent_first_failure=c.get('first_failure'),raw_parent_error_history=c.get('error_history',[]),
        immutable_refs_rehashed=len(c.get('immutable_files',{})),changed_source=bad,changed_flat=flat_bad,
        source_checks=483 if passed else None,source_skipped=0 if passed else None,
        exact_default_repeated=23 if passed else None,exact_flat_same_KERN_contracts=12 if passed else None,source_compilation_matches_prepared_archive=source_counts_ok,
        technical_procedure_passed=passed,ML_quality_metric=None,promotion=False,submit=False,
        root_exporter_actual_exit_and_fresh_preparer_absence_required=True,root_new_fits=0,root_API_calls=0)
    check()
    with out.open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False)
    check()
    print(json.dumps({k:result[k] for k in ['status','actual_exec_exit_code_observed_by_root',
        'cleanup_confirmed','source_unchanged','technical_procedure_passed','raw_parent_elapsed_seconds']}))
    return 0 if cleanup_ok and source_ok else 1
if __name__=='__main__':raise SystemExit(main())
