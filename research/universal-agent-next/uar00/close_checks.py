"""Root-only post-exit UAR00 closure; own30s lies within original600s."""
from pathlib import Path
import argparse, importlib.util, json, math, time


def need(value, code):
    if not value:
        raise RuntimeError(code)


def imported(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--private-manifest', required=True)
    p.add_argument('--private-manifest-sha256', required=True)
    p.add_argument('--driver-sha256', required=True)
    p.add_argument('--self-sha256', required=True)
    p.add_argument('--actual-exec-session', type=int, default=None)
    p.add_argument('--actual-exit-code', type=int, required=True)
    p.add_argument('--actual-tool-evidence', required=True)
    a = p.parse_args(); begin = time.monotonic()
    need(__debug__ and a.actual_tool_evidence.strip(), 'actual_root_exit_evidence_required')
    # Load only the reviewed sibling driver, after hashing with stdlib.
    import hashlib
    driver_path = Path(__file__).with_name('run_checks.py')
    need(hashlib.sha256(driver_path.read_bytes()).hexdigest() == a.driver_sha256, 'driver_changed')
    driver = imported('_uar00_closure_driver', driver_path)
    cfg = driver.config(a.private_manifest, a.private_manifest_sha256, a.driver_sha256)
    need(cfg['files_sha256'].get(str(Path(__file__).resolve())) == a.self_sha256
         and driver.digest(__file__) == a.self_sha256, 'closer_source_changed')
    out = Path(cfg['output']); c = driver.read(out/'campaign.json')
    campaign_sha = driver.digest(out/'campaign.json')
    driver.bind_extra(cfg, c['extra_closure_args'])
    destination = out/'terminal-root-closure.json'
    need(not destination.exists(), 'exclusive_closure_no_rewrite')
    names = ('start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic',
             'finished_unix','finished_monotonic')
    need(all(type(c.get(k)) in (int,float) and math.isfinite(c[k]) for k in names), 'terminal_clock_required')
    need(c['common_seconds'] == 600 and c['absolute_deadline_unix']-c['start_unix'] == 600
         and c['common_deadline_monotonic']-c['start_monotonic'] == 600, 'same_original600_required')
    def check():
        need(time.monotonic()-begin < 30, 'closure30_cap')
        need(time.time() < c['absolute_deadline_unix']
             and time.monotonic() < c['common_deadline_monotonic'], 'original600_deadline_exhausted')
        need(abs((c['absolute_deadline_unix']-time.time())
                 -(c['common_deadline_monotonic']-time.monotonic())) <= 5, 'clock_disagreement')
    check()
    modules = {n: driver.imported('_uar00_close_'+n, cfg['helpers'][n]['path']) for n in driver.HELPERS}
    coor, owner = modules['coordinator'], modules['owner']
    known, prior = driver.source_union(cfg, cfg['la2_closure'], coor, check)
    need(driver.digest(cfg['la2_closure'], check) == c['la2_closure_sha256'], 'LA2_closure_changed')
    need(prior.get('actual_exec_session') == c['la2_actual_exec_session']
         and prior.get('actual_exec_exit_code_observed_by_root') == c['la2_actual_exit_code']
         and prior.get('actual_tool_evidence') == c['la2_actual_tool_evidence'], 'LA2_actual_exit_binding')
    known |= coor.identities([c['owned_root']] + c['coordinator_bootstrap_identities']
                             + c.get('owned_process_identities', []))
    artifacts = {}; suites_ok = len(c['supervisors']) == 4
    for index, ref in enumerate(c['supervisors']):
        need(index < 4 and ref['path'] == coor.relative(out/(driver.SUITES[index]+'.json')),
             'exact_ordered_four_supervisors_required')
        path = Path(cfg['work_root'])/ref['path']
        need(driver.digest(path, check) == ref['sha256'], 'terminal_supervisor_changed')
        artifacts[str(path)] = ref['sha256']; sup = driver.read(path)
        known |= coor.identities(sup.get('owned_process_identities', []))
        if sup.get('owned_root'):
            known |= coor.identities([sup['owned_root']])
        suites_ok &= (sup.get('kind') == driver.SUITES[index]
            and sup.get('status') == 'ok' and sup.get('exit_code') == 0
            and sup.get('cleanup_confirmed') is True
            and sup.get('cleanup_observation', {}).get('unresolved') == []
            and not sup.get('error_history') and sup.get('parent_cap_seconds') == 100
            and sup.get('child_cap_seconds') == 75 and sup.get('solver_budget_seconds') is None)
    for name in driver.SUITES:
        log = out/(name+'.log')
        if log.exists():
            artifacts[str(log)] = driver.digest(log, check)
            suites_ok &= driver.log_counts(log)['log_passed']
        else:
            suites_ok = False
    driver.absence(owner, known)
    with modules['lock'].ResearchLock(cfg['lock_path']):
        driver.absence(owner, known); driver.frozen(cfg, check)
        need(driver.digest(out/'campaign.json', check) == campaign_sha, 'terminal_campaign_changed')
        need(driver.digest(a.private_manifest, check) == a.private_manifest_sha256
             == c['private_manifest_sha256'], 'private_manifest_changed')
        for path, expected in artifacts.items():
            need(driver.digest(path, check) == expected, 'suite_artifact_changed')
        passed = (a.actual_exit_code == 0 and c['status'] == 'tests_completed_pending_root'
            and c.get('suite_procedure_passed') is True and c.get('checks_observed') == 48
            and c.get('cleanup_confirmed') is True and c.get('source_unchanged') is True
            and not c.get('error_history') and c.get('active_supervisor') is None and suites_ok
            and c.get('model_fits') == 0 and c.get('API_calls') == 0
            and c.get('awake_guard', {}).get('release_API_verified') is True
            and tuple(row['id'] for row in c['suites']) == driver.SUITES
            and all(row.get('checks_observed') == 12 and row.get('log_passed') is True
                    and row.get('cleanup_confirmed') is True for row in c['suites'])
            and c['finished_unix'] < c['absolute_deadline_unix']
            and c['finished_monotonic'] < c['common_deadline_monotonic'])
        import psutil
        me = psutil.Process(); preparers = [dict(pid=me.pid, create_time=me.create_time())]
        parent = me.parent()
        while parent is not None:
            birth = parent.create_time()
            if not any(Path(v).resolve() == Path(__file__).resolve()
                       for v in parent.cmdline() if v and not v.startswith('-')):
                break
            need(parent.create_time() == birth, 'closer_bootstrap_identity_changed')
            preparers.append(dict(pid=parent.pid, create_time=birth)); parent = parent.parent()
        result = dict(schema='uar00-root-closure-v1', status='technical_pass' if passed else 'failed_or_unqualified',
            technical_procedure_passed=bool(passed), actual_exec_session=a.actual_exec_session,
            actual_exec_exit_code_observed_by_root=a.actual_exit_code, actual_tool_evidence=a.actual_tool_evidence,
            cleanup_confirmed=True, source_unchanged=True, active_owned_processes=[], uncertain_owned=[],
            owned_identities=[dict(pid=p, create_time=b) for p,b in sorted(known)],
            closure_preparer_identities=preparers, qualified_checks=48 if passed else None,
            original_common_seconds=600, original_start_unix=c['start_unix'],
            original_deadline_unix=c['absolute_deadline_unix'],
            campaign_sha256=driver.digest(out/'campaign.json', check),
            private_manifest_sha256=a.private_manifest_sha256, suite_artifact_refs=artifacts,
            la2_closure_sha256=c['la2_closure_sha256'], error_history=c.get('error_history', []),
            first_failure=c.get('first_failure'), model_fits=0, API_calls=0, quality_metric=None,
            promotion=False, submit=False, own_actual_exec_exit_and_fresh_preparer_absence_required=True)
        driver.absence(owner, known); check()
        coor.save(destination, result, True)
        driver.absence(owner, known); check()
    check()
    print(json.dumps(dict(status=result['status'], technical_procedure_passed=bool(passed),
                          qualified_checks=result['qualified_checks'])))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
