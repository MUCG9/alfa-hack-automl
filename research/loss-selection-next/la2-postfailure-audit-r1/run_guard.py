"""Single saved-artifact audit, within LA2's unchanged original clock; zero fits/API."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, os, sys, time

W = Path(__file__).resolve().parents[1]


def need(value, code):
    if not value:
        raise RuntimeError(code)


def load(path):
    return json.loads(path.read_text('utf-8'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--self-sha256', required=True)
    ap.add_argument('--manifest-sha256', required=True)
    a = ap.parse_args()
    start, mono = time.time(), time.monotonic()
    directory = W / 'la2-audit-repair-r1'
    need(not directory.exists(), 'exclusive_new_postfailure_audit_required')
    configuration = Path(__file__).with_name('guard-manifest.json')
    own_end, own_wall = mono + 300, start + 300

    def sha(path):
        h = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(2**20), b''):
                need(time.monotonic() < own_end and time.time() < own_wall, 'audit_guard_300s')
                h.update(block)
        return h.hexdigest()

    need(sha(Path(__file__)) == a.self_sha256 and sha(configuration) == a.manifest_sha256,
         'guard_source_pin')
    cfg = load(configuration)
    campaign = load(W / 'la2/campaign.json')
    need(campaign['status'] == 'technical_failure' and campaign['qualification'] == 'FAIL'
         and campaign['independent_audit'] is None and campaign['cleanup_confirmed'] is True,
         'original_failed_campaign_required')
    end, unix = campaign['common_deadline_monotonic'], campaign['absolute_deadline_unix']
    need(unix == 1792801033.8414314 and end == 60038.875, 'original_clock_only')
    need(min(unix - time.time(), end - time.monotonic()) > 330, 'original_audit_reserve330')
    pins = dict(cfg['pins'])
    need(all(sha(W / n) == h for n, h in pins.items()), 'preflight_source_pin')

    def imported(name, relative):
        spec = importlib.util.spec_from_file_location(name, W / relative)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    coor = imported('_la2_postfailure_coor', 'run_lean_mvp_r2.py')
    owner = imported('_la2_postfailure_owned', 'support_component_coordinator.py')
    proc = imported('_la2_postfailure_proc', 'alfa-hack-automl/src/automl/infrastructure/processes.py')
    locker = imported('_la2_postfailure_lock', 'alfa-hack-automl/tools/research_lock.py')
    awake_type = imported('_la2_postfailure_power', 'awake-next-dev/awake_guard.py').PowerRequestGuard
    import psutil
    me = psutil.Process()
    boot, parent = [], me.parent()
    while parent and any(Path(v).resolve() == Path(__file__).resolve()
                         for v in parent.cmdline() if v and not v.startswith('-')):
        boot.append(dict(pid=parent.pid, create_time=parent.create_time()))
        parent = parent.parent()
    proof = load(W / 'la2/terminal-root-closure.json')
    known = coor.identities(proof['owned_identities'] + proof['closure_preparer_identities'])

    def absent():
        observer = owner.StrictOwnedObserver()
        observer.remember(known)
        need(not observer.observe() and not observer.denials
             and not observer.final_check()['unresolved'], 'predecessor_identity_live_or_denied')

    state = dict(status='preflight', start_unix=start, start_monotonic=mono,
                 absolute_deadline_unix=unix, common_deadline_monotonic=end,
                 original_common_start_unix=1792790233.8414314, own_parent_seconds=300,
                 original_common_seconds=10800, primary_LA2_qualification='FAIL',
                 owned_root=dict(pid=me.pid, create_time=me.create_time()),
                 coordinator_bootstrap_identities=boot, supervisors=[], active_supervisor=None,
                 error_history=[], immutable_files=pins, model_fits=0, API_calls=0,
                 primary_campaign_modified=False, _manifest={})
    directory.mkdir()

    def persist():
        coor.save(directory / 'campaign.json', {k: v for k, v in state.items() if not k.startswith('_')})

    with awake_type('Saved artifact LA2 postfailure audit', 10) as awake:
        def checkpoint(parent_end=None, code='audit_phase_deadline'):
            coor.cooperative_checkpoint(awake, min(end, own_end), min(unix, own_wall), parent_end, code)

        def frozen(parent_end=None, code='audit_phase_deadline'):
            checkpoint(parent_end, code)
            for n, h in pins.items():
                need(sha(W / n) == h, 'postfailure_source_changed')
                checkpoint(parent_end, code)

        state['_pulse'] = checkpoint
        with locker.ResearchLock(W / 'alfa-hack-automl/test-runs/.owned-research.lock') as lease:
            lease.write_identity(state['owned_root'])
            absent()
            persist()
            cmd = [sys.executable, '-B', '-X', 'utf8', str(Path(__file__).with_name('audit_pair.py')),
                   *cfg['audit_arguments']]
            record = coor.supervise(cmd, W, directory / 'supervisor.json', 'saved-artifact-audit',
                                    mono, 300, 240, min(end, own_end), min(unix, own_wall),
                                    300, state, persist, frozen, owner, proc, boot)
            coor.child_errors(state, record)
            result = directory / 'independent-audit.json'
            state.update(status=record['status'], cleanup_confirmed=record['cleanup_confirmed'],
                         source_unchanged=all(sha(W / n) == h for n, h in pins.items()),
                         audit_sha256=sha(result) if result.exists() else None,
                         audit_artifact_checks_passed=load(result).get('artifact_procedure_checks_passed') if result.exists() else None,
                         owned_process_identities=record['owned_process_identities'])
            frozen()
            absent()
            persist()
    state.update(awake_guard=awake.record, finished_unix=time.time(), finished_monotonic=time.monotonic(),
                 elapsed_seconds=time.monotonic() - mono)
    persist()
    need(time.time() < min(unix, own_wall) and time.monotonic() < min(end, own_end), 'final_original_or_parent_clock')
    print(json.dumps({k: state[k] for k in ['status', 'cleanup_confirmed', 'source_unchanged',
                                           'audit_artifact_checks_passed', 'elapsed_seconds', 'model_fits', 'API_calls']}))
    return 0 if state['status'] == 'ok' and state['cleanup_confirmed'] and state['source_unchanged'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
