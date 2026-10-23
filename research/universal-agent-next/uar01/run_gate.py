"""UAR01: one1200s source/build integration gate. No launch during preparation."""
from pathlib import Path
import argparse, ast, hashlib, importlib.util, json, sys, time, zipfile

COMMON, SOURCE_PARENT, SOURCE_CHILD, BUILD_PARENT, BUILD_CHILD = 1200, 850, 800, 120, 90
FINAL, ROOT_CLOSE, SETUP = 200, 30, 30
ORIGINAL_PROC = 'fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d'
REQUIREMENTS = '9173b0388532fbd2a709e4f4b3029e3b9ccab685fce43a85261ffa1ba95efbe6'
UAR00_HELPER = 'a75adab8cbcf2bafb22cee633f28f697eb5dc4005db90bd0003dffc8e6097d56'
PROVEN = {'coordinator':'43be86ece6c453641afdcc6f8eccef02d713986e2ac8bf3314756f0bb78e0818',
          'owner':'8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8',
          'lock':'78a0441bb3b9ea60197e9a1a6e1087f6e4cd0886593ec54bcfc4e41c9abe5a45',
          'awake':'9a0bae0acb6ddb37e638420c52ad1e587a9180fbd7ef68ebc6e1a3c43e4bfc9b'}
sys.dont_write_bytecode = True


def need(value, code):
    if not value:
        raise RuntimeError(code)


def digest(path, pulse=lambda: None):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            pulse(); block = stream.read(2**20)
            if not block:
                break
            h.update(block)
    pulse(); return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text('utf-8'))


def imported(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def registry(path):
    checks = {}
    for n in ast.parse(Path(path).read_bytes()).body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'CHECKS' for t in n.targets):
            need(not checks, 'duplicate_registry_assignment'); checks.update(ast.literal_eval(n.value))
        elif isinstance(n, ast.Expr) and isinstance(n.value, ast.Call):
            call = n.value
            if (isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
                and call.func.value.id == 'CHECKS' and call.func.attr == 'update'):
                need(len(call.args) == 1 and not call.keywords, 'typed_registry_update')
                delta = ast.literal_eval(call.args[0]); need(not set(checks) & set(delta), 'duplicate_registry_script')
                checks.update(delta)
    need(len(checks) == 50 and sum(checks.values()) == 499
         and all(type(k) is str and type(v) is int and v > 0 for k,v in checks.items()),
         'registered499_checks50_scripts_required')
    return checks


def frozen(cfg, pulse=lambda: None):
    for path, expected in cfg['files_sha256'].items():
        need(digest(path, pulse) == expected, 'immutable_source_or_fixture_changed')
    repo = Path(cfg['repo'])
    for folder, expected in cfg['python_inventory'].items():
        actual = {str(p.resolve()) for p in (repo/folder).rglob('*.py')}
        need(actual == set(expected), 'canonical_python_inventory_changed')
    need(registry(repo/'tools/run_checks.py') == cfg['checks'], 'registered_checks_changed')
    pulse()


def config(path, expected, self_sha, pulse=lambda: None):
    need(digest(path, pulse) == expected, 'private_manifest_changed'); cfg = read(path)
    need(cfg['schema'] == 'uar01-private-manifest-v1', 'private_manifest_schema')
    need(cfg['files_sha256'].get(str(Path(__file__).resolve())) == self_sha
         and digest(__file__, pulse) == self_sha, 'coordinator_changed')
    need(cfg['helpers']['processes']['sha256'] == ORIGINAL_PROC, 'original_fac3_guard_required')
    need(Path(cfg['helpers']['processes']['path']).resolve()
         != (Path(cfg['repo'])/'src/automl/infrastructure/processes.py').resolve(), 'under_test_process_cannot_guard_itself')
    for ref in cfg['helpers'].values():
        need(cfg['files_sha256'].get(ref['path']) == ref['sha256'], 'unbound_guard_dependency')
    need(all(cfg['helpers'][n]['sha256']==h for n,h in PROVEN.items()), 'proven_supervision_versions_required')
    need(cfg['helpers']['uar00']['sha256'] == UAR00_HELPER, 'reviewed_UAR00_reuse_required')
    frozen(cfg, pulse); return cfg


def prior_union(cfg, coor, pulse=lambda: None):
    known = set()
    need(set(cfg['predecessors']) == {'UAR00','LA2_postfailure_audit','LA2_original'}, 'exact_terminal_predecessors')
    for name, ref in cfg['predecessors'].items():
        need(digest(ref['path'], pulse) == ref['sha256'], 'terminal_predecessor_changed')
        proof = read(ref['path'])
        need(proof.get('cleanup_confirmed') is True and proof.get('source_unchanged') is True
             and proof.get('active_owned_processes') == [] and not proof.get('uncertain_owned')
             and proof.get('actual_exec_exit_code_observed_by_root') == ref['actual_exit_code']
             and proof.get('actual_exec_session') == ref['actual_exec_session']
             and proof.get('actual_tool_evidence') == ref['actual_tool_evidence'],
             'actual_terminal_exit_or_cleanup_unknown')
        if name == 'UAR00':
            need(proof.get('technical_procedure_passed') is True and proof.get('qualified_checks') == 48,
                 'actual_UAR00_48_PASS_required')
        known |= coor.identities(proof['owned_identities'] + proof['closure_preparer_identities'])
    return known


def inspect_artifacts(cfg, pulse=lambda: None):
    out = Path(cfg['output']); rows = read(out/'source/results.json'); checks = cfg['checks']
    need(rows.get('passed') is True and rows.get('source_unchanged') is True
         and rows.get('fixture_cleanup_confirmed') is True
         and rows.get('unique_checks_passed') == 499 and rows.get('unique_checks_skipped') == 0,
         'full_source_result_not_passed499_noskips_clean')
    need(len(rows['checks']) == 50 and [r['script'] for r in rows['checks']] == list(checks), 'exact50_script_order')
    refs = {}
    for row in rows['checks']:
        need(row['status'] == 0 and row['passed'] is True and row['expected_checks'] == checks[row['script']]
             and row['observed_checks'] == checks[row['script']] and row['skipped_checks'] == 0,
             'registered_script_result_mismatch')
        path = Path(row['log']).resolve(); need(path.parent == (out/'source').resolve(), 'source_log_outside_attempt')
        refs[str(path)] = digest(path, pulse)
    expected_tests = {name:cfg['files_sha256'][str((Path(cfg['repo'])/'tests'/name).resolve())] for name in checks}
    need(rows['test_script_sha256'] == expected_tests, 'source_result_test_hashes_mismatch')
    fixture = Path(rows['fixture_root']).resolve()
    need(fixture.is_relative_to(Path(cfg['fixture_parent']).resolve()) and not fixture.exists(), 'source_fixture_not_removed')
    build = read(out/'candidate.manifest.json'); archive = out/'candidate.zip'
    need(digest(archive, pulse) == build['sha256'] and archive.stat().st_size == build['bytes']
         and build['bytes'] <= 100000000, 'built_archive_sha_or_size_mismatch')
    need(build['files'] == rows['source_sha256'], 'build_differs_from_source_gate_flat_snapshot')
    need(set(build['files']) == set(cfg['expected_flat_members']), 'current_source_flat_member_mapping_mismatch')
    with zipfile.ZipFile(archive) as z:
        names = z.namelist(); need(len(names) == len(set(names)) and set(names) == set(build['files']), 'archive_member_inventory')
        for name in names:
            need(Path(name).name == name and name.endswith(('.py','.txt')), 'nonflat_archive_member')
            raw = z.read(name); need(hashlib.sha256(raw).hexdigest() == build['files'][name], 'archive_member_hash')
            if name.endswith('.py'):
                compile(ast.parse(raw, filename=name), name, 'exec')
            pulse()
        need(hashlib.sha256(z.read('requirements.txt')).hexdigest() == REQUIREMENTS, 'original_requirements_required')
        need(z.read('solution.py') == b'from automl_runner import THREADS,llm_plan,main,run_worker\nif __name__ == "__main__": main()\n', 'root_solution_entrypoint_changed')
    for path in [out/'source/results.json', out/'candidate.manifest.json', archive]:
        refs[str(path)] = digest(path, pulse)
    return dict(status='integration_artifacts_verified_not_release', checks_passed=499, scripts_passed=50,
                archive_sha256=build['sha256'], flat_members=len(build['files']), artifact_refs=refs,
                model_quality=None, release_qualified=False, promotion=False, submit=False)


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--launch', action='store_true', required=True)
    p.add_argument('--private-manifest', required=True); p.add_argument('--private-manifest-sha256', required=True)
    p.add_argument('--self-sha256', required=True); a = p.parse_args()
    start, mono = time.time(), time.monotonic(); unix, end = start+COMMON, mono+COMMON
    def clock():
        need(time.time() < unix and time.monotonic() < end, 'original1200_deadline_exhausted')
        need(abs((unix-time.time())-(end-time.monotonic())) <= 5, 'clock_disagreement')
    cfg = config(a.private_manifest, a.private_manifest_sha256, a.self_sha256, clock)
    need(__debug__ and Path(cfg['python']).resolve() == Path(sys.executable).resolve(), 'pinned_nonoptimized_interpreter')
    m = {n:imported('_uar01_'+n, r['path']) for n,r in cfg['helpers'].items()}
    coor, owner, reuse = m['coordinator'], m['owner'], m['uar00']
    need(coor.WORK.resolve() == Path(cfg['work_root']).resolve(), 'proven_supervisor_work_root_mismatch')
    import psutil
    known = prior_union(cfg, coor, clock); reuse.absence(owner, known)
    out = Path(cfg['output']); need(not out.exists(), 'exclusive_attempt_no_retry'); out.mkdir()
    me = psutil.Process(); root = dict(pid=me.pid, create_time=me.create_time()); boot=[]; parent=me.parent()
    while parent is not None:
        birth = parent.create_time()
        if not any(Path(v).resolve() == Path(__file__).resolve() for v in parent.cmdline() if v and not v.startswith('-')):
            break
        need(parent.create_time() == birth, 'bootstrap_identity_changed')
        boot.append(dict(pid=parent.pid, create_time=birth)); parent=parent.parent()
    state = dict(schema='uar01-campaign-v1', status='starting', start_unix=start, start_monotonic=mono,
        absolute_deadline_unix=unix, common_deadline_monotonic=end, common_seconds=COMMON,
        private_manifest_sha256=a.private_manifest_sha256, owned_root=root, coordinator_bootstrap_identities=boot,
        supervisors=[], active_supervisor=None, owned_process_identities=[], error_history=[],
        cleanup_confirmed=False, source_unchanged=False, API_calls=0, model_quality=None,
        fixture_model_fits=None, fixture_fit_scope='existing offline fixtures only; actual count not invented',
        integration_artifacts_passed=False, root_actual_exec_confirmation_pending=True, _manifest={})
    children=set(); ob=None; awake=None; final_end=None
    def persist(): coor.save(out/'campaign.json', {k:v for k,v in state.items() if not k.startswith('_')})
    def pulse():
        coor.cooperative_checkpoint(awake, end, unix)
        if state.get('active_supervisor') and ob is not None:
            sup=read(Path(cfg['work_root'])/state['active_supervisor'])
            if sup.get('owned_root'): ob.remember(coor.identities([sup['owned_root']]))
            live=ob.observe(); need(not ob.denials, 'owned_suite_observation_denied'); rss=0
            for identity,obj in live.items():
                try:
                    need(obj.create_time() == identity[1], 'owned_identity_changed'); rss += obj.memory_info().rss
                except psutil.NoSuchProcess: pass
            children.update(ob.seen); need(rss <= 1536*2**20, 'suite_subtree_memory_limit')
    def guard(parent_end=None, code='parent_cap_exhausted'):
        coor.cooperative_checkpoint(awake,end,unix,parent_end,code)
        need(digest(a.private_manifest,pulse)==a.private_manifest_sha256,'private_manifest_changed'); frozen(cfg,pulse)
    state['_pulse']=pulse
    try:
        with m['awake'].PowerRequestGuard('UAR01 source build integration gate',10) as awake:
            with m['lock'].ResearchLock(cfg['lock_path']) as lease:
                lease.write_identity(root); reuse.absence(owner,known); guard(); persist()
                need(time.monotonic()-mono <= SETUP,'setup30_exhausted')
                commands=[('source',[cfg['python'],'-B','-X','utf8',str(Path(cfg['repo'])/'tools/run_checks.py'),'--output',str(out/'source')],mono,SOURCE_PARENT,SOURCE_CHILD),
                          ('build',[cfg['python'],'-B','-X','utf8',str(Path(cfg['repo'])/'tools/build_submission.py'),'--output',str(out/'candidate.zip')],None,BUILD_PARENT,BUILD_CHILD)]
                for name,command,parent_start,cap,childcap in commands:
                    guard(); reuse.absence(owner,known|children); ob=owner.StrictOwnedObserver()
                    parent_start=mono if name=='source' else time.monotonic()
                    reserve=COMMON if name=='source' else BUILD_PARENT+FINAL+ROOT_CLOSE
                    need(end-time.monotonic() >= reserve-(time.monotonic()-parent_start),'remaining_declared_reserve')
                    sup=coor.supervise(command,Path(cfg['repo']),out/(name+'.json'),name,parent_start,cap,childcap,
                        end,unix,reserve,state,persist,guard,owner,m['processes'],boot)
                    coor.child_errors(state,sup); children |= coor.identities(sup.get('owned_process_identities',[]))
                    if sup.get('owned_root'):children |= coor.identities([sup['owned_root']])
                    need(sup['status']=='ok' and sup['exit_code']==0 and sup['cleanup_confirmed'] and not sup.get('error_history'), 'mandatory_integration_stage_failed')
                    if name=='source':need(sup['child_start_monotonic']-mono <= SETUP,'actual_source_setup_over30')
                audit_start=time.monotonic()
                final_end=min(audit_start+FINAL,end-ROOT_CLOSE)
                def audit_pulse():
                    coor.cooperative_checkpoint(awake,end,unix,final_end,'final_audit200_cap')
                audit=inspect_artifacts(cfg,audit_pulse); guard(); reuse.absence(owner,known|children)
                coor.save(out/'artifact-audit.json',audit,True)
                state.update(status='integration_complete_pending_root',integration_artifacts_passed=True,
                    artifact_audit_sha256=digest(out/'artifact-audit.json',audit_pulse),archive_sha256=audit['archive_sha256'])
                persist(); audit_pulse()
        state['awake_guard']=awake.record; need(awake.record.get('release_API_verified') is True,'power_guard_cleanup')
    except BaseException as exc:
        coor.error(state,str(exc) if isinstance(exc,RuntimeError) else 'integration_operation_failed','integration',exc)
        state.update(status='technical_failure',integration_artifacts_passed=False)
    finally:
        if awake is not None:state['awake_guard']=awake.record
        state['owned_process_identities']=[dict(pid=p,create_time=c) for p,c in sorted(children)]
        try:
            reuse.absence(owner,known|children)
            need(state['active_supervisor'] is None and all(r['cleanup_confirmed'] is True for r in state['supervisors']),'supervisor_cleanup_unconfirmed')
            state['cleanup_confirmed']=True
        except BaseException as exc:
            coor.error(state,'terminal_cleanup_unconfirmed','terminal',exc);state['cleanup_confirmed']=False
        try:
            frozen(cfg,clock); need(digest(a.private_manifest,clock)==a.private_manifest_sha256,'private_manifest_changed')
            state['source_unchanged']=True;need(end-time.monotonic() >= ROOT_CLOSE,'rootclose30_reserve_missing')
            if final_end is not None:need(time.monotonic()<final_end,'final_audit_and_finalization200_cap')
        except BaseException as exc:
            coor.error(state,'terminal_source_or_clock_unconfirmed','terminal',exc);state['source_unchanged']=False
        if state['error_history']:state.update(status='technical_failure',integration_artifacts_passed=False)
        state.update(finished_unix=time.time(),finished_monotonic=time.monotonic(),elapsed_common_seconds=time.monotonic()-mono);persist()
        if time.time()>=unix or time.monotonic()>=end-ROOT_CLOSE or (final_end is not None and time.monotonic()>=final_end):
            coor.error(state,'terminal_save_exhausted_original_or_root_reserve','terminal_save')
            state.update(status='technical_failure',integration_artifacts_passed=False);persist()
    passed=state['integration_artifacts_passed'] and state['cleanup_confirmed'] and state['source_unchanged'] and not state['error_history']
    print(json.dumps({k:state.get(k) for k in ['status','integration_artifacts_passed','cleanup_confirmed','source_unchanged','elapsed_common_seconds']}))
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
