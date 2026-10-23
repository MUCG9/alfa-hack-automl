"""Actual postfailure audit terminal closure; the original LA2 remains FAIL."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, time

W = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--self-sha256', required=True)
    ap.add_argument('--actual-exec-session', type=int)
    ap.add_argument('--actual-exit-code', type=int, required=True)
    ap.add_argument('--actual-tool-evidence', required=True)
    a = ap.parse_args()
    start = time.monotonic()

    def tick():
        assert time.monotonic() - start < 30
        assert time.time() < 1792801033.8414314 and time.monotonic() < 60038.875

    def sha(path):
        h = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(2**20), b''):
                tick()
                h.update(block)
        return h.hexdigest()

    def load(path):
        return json.loads(path.read_text('utf-8'))

    tick()
    assert a.actual_tool_evidence and sha(Path(__file__)) == a.self_sha256
    directory = W / 'la2-audit-repair-r1'
    state = load(directory / 'campaign.json')
    original = load(W / 'la2/campaign.json')
    prior = load(W / 'la2/terminal-root-closure.json')
    assert original['qualification'] == 'FAIL' and original['status'] == 'technical_failure'
    assert prior['actual_exec_exit_code_observed_by_root'] == 1
    assert state['primary_LA2_qualification'] == 'FAIL'
    assert state['absolute_deadline_unix'] == 1792801033.8414314
    assert state['common_deadline_monotonic'] == 60038.875
    assert state['active_supervisor'] is None
    for path, expected in state['immutable_files'].items():
        assert sha(W / path) == expected
    assert sha(W / 'support_component_coordinator.py') == '8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8'
    spec = importlib.util.spec_from_file_location('_la2_postfailure_closure_owned', W / 'support_component_coordinator.py')
    owner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owner)
    rows = prior['owned_identities'] + prior['closure_preparer_identities']
    rows += [state['owned_root']] + state['coordinator_bootstrap_identities'] + state['owned_process_identities']
    known = {(r['pid'], r['create_time']) for r in rows}
    observer = owner.StrictOwnedObserver()
    observer.remember(known)
    assert not observer.observe() and not observer.denials and not observer.final_check()['unresolved']
    path = directory / 'independent-audit.json'
    audit = load(path) if path.exists() else None
    if audit is not None:
        assert sha(path) == state['audit_sha256']
    technical = (a.actual_exit_code == 0 and state['status'] == 'ok'
                 and state['cleanup_confirmed'] is True and state['source_unchanged'] is True
                 and not state['error_history']
                 and state.get('awake_guard', {}).get('release_API_verified') is True)
    complete = bool(technical and audit and audit['artifact_procedure_checks_passed'] is True
                    and audit['audit_within_original_common_clock'] is True)
    import psutil
    me = psutil.Process()
    preparers, parent = [dict(pid=me.pid, create_time=me.create_time())], me.parent()
    while parent and any(Path(v).resolve() == Path(__file__).resolve()
                         for v in parent.cmdline() if v and not v.startswith('-')):
        preparers.append(dict(pid=parent.pid, create_time=parent.create_time()))
        parent = parent.parent()
    result = dict(status='postfailure_audit_closed', original_LA2_status='FAIL',
                  actual_exec_session=a.actual_exec_session, actual_exec_exit_code_observed_by_root=a.actual_exit_code,
                  actual_tool_evidence=a.actual_tool_evidence, technical_audit_execution_passed=technical,
                  all_artifact_checks_passed=complete, cleanup_confirmed=True, source_unchanged=True,
                  audit_sha256=sha(path) if path.exists() else None,
                  qualified_ML_metrics=audit.get('quality_metric') if complete else None,
                  descriptive_retention_win=audit.get('descriptive_retention_win') if complete else None,
                  owned_identities=[dict(pid=p, create_time=b) for p, b in sorted(known)],
                  closure_preparer_identities=preparers, active_owned_processes=[], uncertain_owned=[],
                  original_deadline_unix=1792801033.8414314, new_model_fits=0, API_calls=0,
                  promotion=False, submit=False, original_campaign_modified=False)
    tick()
    with (directory / 'terminal-root-closure.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    tick()
    print(json.dumps({k: result[k] for k in ['technical_audit_execution_passed', 'all_artifact_checks_passed',
                                            'qualified_ML_metrics', 'original_LA2_status']}))


if __name__ == '__main__':
    main()
