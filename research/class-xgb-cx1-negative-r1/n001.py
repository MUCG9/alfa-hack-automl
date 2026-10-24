"""One current nonqualifying metadata closure. Never repairs CX1's missed root60."""
import hashlib
import json
import time
from pathlib import Path

WORK = Path(__file__).resolve().parent
OUT = WORK / 'cx1'


def main():
    import psutil
    begin, wall = time.monotonic(), time.time()
    last = begin
    observer = []
    proc = psutil.Process()
    for _ in range(3):
        birth = proc.create_time()
        observer.append(dict(pid=proc.pid, create_time=birth))
        assert psutil.Process(proc.pid).create_time() == birth
        parent = proc.parent()
        if parent is None:
            break
        proc = parent
    read = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
    root = read(OUT / 'terminal-root-closure.json')
    cfg = read(WORK / 'private/cx1-manifest.r3.ready.json')

    def check():
        nonlocal last
        now, current = time.monotonic(), time.time()
        assert now >= begin and current >= wall and now-last <= 10
        assert now-begin <= 30 and current-wall <= 30
        last = now

    def sha(path):
        h = hashlib.sha256()
        with Path(path).open('rb') as stream:
            while True:
                check()
                block = stream.read(2**20)
                if not block:
                    break
                h.update(block)
        return h.hexdigest()

    assert root['actual_exec_session'] == 77390
    assert root['actual_exec_exit_code_observed_by_root'] == 0
    assert root['actual_tool_evidence'] == '7b23cf'
    for path, expected in cfg['immutable_files'].items():
        assert sha(path) == expected
    state = read(OUT / 'campaign.json')
    if state.get('temporary_root'):
        assert not Path(state['temporary_root']).exists()
    known = {(int(x['pid']), float(x['create_time'])) for x in
             root['owned_identities'] + root['closure_preparer_identities']}
    for ref in cfg['additional_preparer_receipts']:
        known |= {(int(x['pid']), float(x['create_time'])) for x in read(ref['path'])['identities']}
    live, uncertain, absent, reused = [], [], 0, 0
    for pid, birth in sorted(known):
        check()
        try:
            observed = psutil.Process(pid).create_time()
            if observed == birth:
                if psutil.Process(pid).create_time() == birth:
                    live.append(dict(pid=pid, create_time=birth))
                else:
                    reused += 1
            else:
                reused += 1
        except psutil.NoSuchProcess:
            absent += 1
        except (psutil.AccessDenied, OSError) as exc:
            uncertain.append(dict(pid=pid, create_time=birth, exception_type=type(exc).__name__))
    check()
    assert not live and not uncertain
    result = dict(schema='cx1-separate-current-negative-metadata-closure-v1',
        original_CX1_status='FAIL_ROOT_FRESH60_MISSED', technical_procedure_passed=False,
        first_error=dict(code='actual_closer_birth_root60_expired', actual_tool='4ce534'),
        actual_driver=dict(session=77390, exit_code=0, tool='7b23cf'),
        actual_closer=dict(session=None, exit_code=0, tool='4566fc'),
        immutable_root_sha256=sha(OUT/'terminal-root-closure.json'),
        source_pins_verified=len(cfg['immutable_files']), current_source_unchanged=True,
        current_temporary_absent=True, current_known_cleanup_confirmed=True,
        known_count=len(known), known_identities=[dict(pid=p, create_time=b) for p,b in sorted(known)],
        known_exact_live=live, uncertain=uncertain, original_absent=absent, reused_original_absent=reused,
        observer_identities=observer, metadata_parent_cap_seconds=30,
        elapsed_metadata_seconds=time.monotonic()-begin,
        actual_closer_birth_elapsed=time.time()-root['closure_preparer_identities'][0]['create_time'],
        inside_original_common=time.monotonic() <= root['original_end_monotonic'] and time.time() <= root['original_deadline_unix'],
        root60_requalified=False, old_clock_reset=False, new_metrics=None,
        new_model_fits=0, API_calls=0, promotion=False, submit=False)
    target = OUT / 'current-negative-closure.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
    check()
    print(json.dumps(dict(status='CURRENT_CLEAN_NEGATIVE_ONLY', known_count=len(known),
                         source_pins=len(cfg['immutable_files']), technical_procedure_passed=False)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
