"""Bounded post-terminal saved-artifact audit; no training and no API calls."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
import psutil

W = Path(__file__).resolve().parent
R = W / 'alfa-hack-automl'
OUT = W / 'tm1-classification-audit-guard-r1'
sys.dont_write_bytecode = True
def sha(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
def load(path):
    return json.loads(path.read_text('utf-8'))
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value
def write(value):
    pending = OUT / 'supervisor.json.pending'
    pending.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8'))
    pending.replace(OUT / 'supervisor.json')
def main():
    assert not OUT.exists(), 'Preserve prior audit attempts'
    source = W / 'verify_true_mvp_tm1.py'
    assert sha(source) == '161a55202d7824f21f954d66455e8449de4056d24fb5912c79a316ac7dca6355'
    plan = W / 'tm1-independent-verification-plan-r3.json'
    assert sha(plan) == '662b348fb2b4f04a0ea538615804f7f5e0d8a3ed5c7f8343c623ceddc3093f4c'
    proof = load(W / 'true-mvp-completion-ownership.json')
    campaign = W / 'alfa-hack-automl/test-runs/tm1/campaign.json'
    assert proof['cleanup_confirmed'] is True and not proof['active_owned_processes']
    assert proof['campaign_receipt_sha256'] == sha(campaign) and proof['exec_result_verified'] is True
    assert not (W / 'true-four-stage-classification-independent-tm1.json').exists()
    owner_path = W / 'support_component_coordinator.py'
    assert sha(owner_path) == '8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8'
    owner = module('_tm1_audit_owner', owner_path)
    processes = module('_tm1_audit_processes', R / 'src/automl/infrastructure/processes.py')
    lock = module('_tm1_audit_lock', R / 'tools/research_lock.py')
    identities = [*proof['launcher_identities'], *proof['tracked_identities']]
    before = owner.predecessor_snapshot(identities)
    assert before['cleanup_confirmed'] and not before['active']
    with lock.ResearchLock(R / 'test-runs/.owned-research.lock'):
        before = owner.predecessor_snapshot([*identities, *before['tracked']])
        assert before['cleanup_confirmed'] and not before['active']
        OUT.mkdir()
        for name in ('tmp', 'mpl'):
            (OUT / name).mkdir()
        allowed = {'PATH', 'SystemRoot', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'ComSpec',
                   'PATHEXT', 'PROCESSOR_ARCHITECTURE', 'NUMBER_OF_PROCESSORS'}
        env = {k: v for k, v in os.environ.items() if k in allowed}
        env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1',
            TEMP=str(OUT / 'tmp'), TMP=str(OUT / 'tmp'), TMPDIR=str(OUT / 'tmp'), MPLCONFIGDIR=str(OUT / 'mpl'))
        for name in ('AUTOML_THREADS', 'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
            env[name] = '1'
        tick = time.monotonic()
        record = {'status': 'starting', 'start_unix': time.time(), 'start_monotonic': tick,
            'max_seconds': 300, 'max_memory_mib': 1024, 'threads': 1, 'cleanup_confirmed': False,
            'scope': 'Execute classification-only saved-artifact audit, not ML procedure qualification.',
            'source_sha256': sha(source), 'plan_sha256': sha(plan),
            'guard_source_sha256': sha(Path(__file__)), 'regression_denied_ledger_retry': False,
            'new_fits': 0, 'API_calls': 0,
            'owned_root': {'pid': os.getpid(), 'create_time': psutil.Process().create_time()}}
        write(record)
        child = tree = None
        verified = False
        observer = owner.StrictOwnedObserver()
        peak = 0.
        try:
            with (OUT / 'audit.log').open('x', encoding='utf-8') as log:
                child = subprocess.Popen([sys.executable, '-B', str(source), '--task', 'classification'],
                    cwd=W, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    start_new_session=True)
                exact = psutil.Process(child.pid)
                identity = child.pid, exact.create_time()
                observer.remember([identity])
                tree = processes.ProcessTree(child)
                observer.remember(tree.members)
                verified = identity in tree.members
                assert verified
                record.update(status='running', child_root={'pid': identity[0], 'create_time': identity[1]})
                write(record)
                last = tick
                while child.poll() is None:
                    live = observer.observe()
                    tree.members.update(live)
                    assert not observer.denials
                    rss = 0
                    for ident in live:
                        try:
                            p = psutil.Process(ident[0])
                            if p.create_time() == ident[1]:
                                rss += p.memory_info().rss
                        except psutil.NoSuchProcess:
                            pass
                    peak = max(peak, rss / 2**20)
                    if rss > 1024 * 2**20:
                        raise MemoryError('Saved-artifact audit memory cap')
                    if time.monotonic() - tick >= 300:
                        raise TimeoutError('Saved-artifact audit wall cap')
                    if time.monotonic() - last >= 2:
                        record.update(heartbeat_unix=time.time(), observed_owned_identities=[
                            {'pid': p, 'create_time': c} for p, c in sorted(observer.seen)])
                        write(record)
                        last = time.monotonic()
                    time.sleep(.1)
                record.update(status='PASS' if child.returncode == 0 else 'FAIL', exit_code=child.returncode)
        except BaseException as exc:
            record.update(status='FAIL', exception_type=type(exc).__name__)
        finally:
            record.update(owner.cleanup_owned(child, tree, observer, verified, processes.ProcessTree))
            record.update(seconds=time.monotonic() - tick, finished_unix=time.time(),
                peak_owned_rss_mib=peak, source_unchanged=sha(source) == record['source_sha256']
                    and sha(plan) == record['plan_sha256']
                    and sha(Path(__file__)) == record['guard_source_sha256'])
            if not record['cleanup_confirmed'] or not record['source_unchanged'] or record['seconds'] > 300:
                record['status'] = 'FAIL'
            write(record)
        print(json.dumps({k: record[k] for k in ('status', 'exit_code', 'cleanup_confirmed', 'seconds', 'peak_owned_rss_mib') if k in record}))
        raise SystemExit(0 if record['status'] == 'PASS' else 1)
if __name__ == '__main__':
    main()
