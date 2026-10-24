"""UAR02 serial test entry: two fresh interpreters, no model/API work."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, math, os, re, subprocess, sys, time

sys.dont_write_bytecode = True


def need(value, code):
    if not value:
        raise RuntimeError(code)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--private-manifest', required=True)
    p.add_argument('--private-manifest-sha256', required=True)
    p.add_argument('--deadline-monotonic', type=float, required=True)
    p.add_argument('--deadline-unix', type=float, required=True)
    a = p.parse_args()
    need(__debug__ and all(math.isfinite(v) for v in (a.deadline_monotonic, a.deadline_unix)),
         'finite_original_child_deadlines_required')

    def clock():
        need(time.monotonic() < a.deadline_monotonic and time.time() < a.deadline_unix,
             'original_child_allocation_exhausted')
        need(abs((a.deadline_unix-time.time())-(a.deadline_monotonic-time.monotonic())) <= 5,
             'clock_disagreement')

    clock(); need(sha(a.private_manifest) == a.private_manifest_sha256, 'private_manifest_changed')
    cfg = json.loads(Path(a.private_manifest).read_text('utf-8'))
    need(cfg['schema'] == 'uar02-private-manifest-v1', 'private_manifest_schema')
    need(sha(__file__) == cfg['files_sha256'][str(Path(__file__).resolve())], 'entry_source_changed')
    ref = cfg['helpers']['processes']
    need(ref['sha256'] == 'fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d'
         and sha(ref['path']) == ref['sha256'], 'original_guard_process_source_required')
    spec = importlib.util.spec_from_file_location('_uar02_original_process_guard', ref['path'])
    proc = importlib.util.module_from_spec(spec); spec.loader.exec_module(proc)
    ownref = cfg['helpers']['owner']
    need(sha(ownref['path']) == ownref['sha256'] ==
         '8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8', 'strict_observer_source_required')
    spec = importlib.util.spec_from_file_location('_uar02_entry_owner', ownref['path'])
    owner = importlib.util.module_from_spec(spec); spec.loader.exec_module(owner)
    import psutil
    out = Path(cfg['output']); rows = []; first = None
    try:
        for suite in cfg['suites']:
            clock(); need(sha(suite['test']) == cfg['files_sha256'][suite['test']], 'test_source_changed')
            log_path = out/(suite['id']+'.log')
            row = dict(id=suite['id'], expected_tests=suite['expected_tests'], status='starting')
            rows.append(row)
            with log_path.open('x', encoding='utf-8') as log:
                clock()
                child = tree = None; observer = owner.StrictOwnedObserver(); verified = False
                try:
                    child = subprocess.Popen([cfg['python'], '-B', '-X', 'utf8', suite['test'], '-v'],
                        cwd=suite['root'], env=os.environ.copy(), stdin=subprocess.DEVNULL,
                        stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                    identity = psutil.Process(child.pid)
                    row['owned_root'] = dict(pid=identity.pid, create_time=identity.create_time())
                    observer.remember([(identity.pid, row['owned_root']['create_time'])])
                    tree = proc.ProcessTree(child); observer.remember(tree.members)
                    verified = (identity.pid, row['owned_root']['create_time']) in tree.members
                    need(verified, 'initial_leaf_identity_unknown')
                    while True:
                        clock(); live = observer.observe(); tree.members.update(live)
                        need(not observer.denials, 'leaf_owned_observation_denied'); rss = 0
                        for owned, obj in live.items():
                            try:
                                need(obj.create_time()==owned[1], 'leaf_identity_changed')
                                rss += obj.memory_info().rss
                            except psutil.NoSuchProcess:
                                pass
                        need(rss<=1536*2**20, 'leaf_subtree_memory_limit')
                        # Check original allocation before accepting even a terminal poll.
                        clock()
                        if child.poll() is not None:
                            row['exit_code'] = child.returncode; break
                        time.sleep(.05)
                finally:
                    row.update(owner.cleanup_owned(child, tree, observer, verified, proc.ProcessTree))
                clock(); need(row['cleanup_confirmed'] is True, 'leaf_cleanup_unconfirmed')
            clock()
            text = log_path.read_text('utf-8', errors='replace')
            counts = re.findall(r'Ran (\d+) tests?', text)
            row.update(log_sha256=sha(log_path), checks_observed=int(counts[0]) if len(counts)==1 else None,
                no_skips=re.search(r'\bskip(?:ped)?\b', text, re.I) is None)
            row['passed'] = (row['exit_code']==0 and counts==[str(suite['expected_tests'])]
                and row['no_skips'] and re.search(r'\nOK\s*$', text) is not None)
            row['status'] = 'passed' if row['passed'] else 'failed'
            need(row['passed'], 'mandatory_focused_suite_failed')
    except BaseException as exc:
        first = dict(type=type(exc).__name__, code=str(exc) if re.fullmatch('[A-Za-z0-9_]+', str(exc))
                     else 'suite_execution_or_cleanup_failed')
    passed = first is None and len(rows)==2 and all(r.get('passed') for r in rows)
    result = dict(schema='uar02-focused-results-v1', status='passed' if passed else 'failed',
        suites=rows, first_failure=first, checks_observed=29 if passed else None,
        model_fits=0, API_calls=0, quality_metric=None)
    with (out/'focused-results.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
    clock()
    print(json.dumps(dict(status=result['status'], checks_observed=result['checks_observed'])))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
