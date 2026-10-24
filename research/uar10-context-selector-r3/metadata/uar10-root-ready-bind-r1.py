"""Root-only exact JSON/source metadata binding; never imports candidate code."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import time

W = Path(__file__).resolve().parent
ROOT = W / 'alfa-hack-automl'
PACKET = W / 'uar10-context-selector-gate-next-dev-r3'
OVERLAY = W / 'combined-legacy-test-compatibility-next-dev'
BASE = W / 'fitting-context-selector-combined-next-dev'
PRIVATE = W / 'private'
MANIFEST = PRIVATE / 'uar10-manifest.r3.ready.json'
OLD_SHA = 'ac801e25c84719e7966290327d3c905c9f9e8491ce1326c30c2925a56ef90cab'

def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def save(p, value):
    with Path(p).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')

def ref(p):
    return dict(path=str(p.resolve()), sha256=sha(p))

def external(rel):
    p = Path(rel)
    return p if p.is_absolute() else (W.parent / p if p.parts[0] == 'work' else W / p)

def add(pins, p, expected=None):
    actual = sha(p)
    assert expected is None or actual == expected, 'frozen_metadata_pin_changed'
    pins[str(p.resolve())] = actual

def packet_pins(pins, packet, expected):
    add(pins, packet / 'source-handoff.json', expected)
    h = read(packet / 'source-handoff.json')
    for rel, expected in h['files_sha256'].items():
        add(pins, packet / rel, expected)
    for rel, expected in h.get('external_refs_sha256', {}).items():
        add(pins, external(rel), expected)
    return h

def prepare(a):
    assert not MANIFEST.exists(), 'exclusive_new_metadata_binding'
    import psutil
    me = psutil.Process(os.getpid())
    identities = []
    current = me
    for index in range(3):
        birth = current.create_time()
        identities.append(dict(pid=current.pid, create_time=birth))
        assert current.create_time() == birth
        if index < 2:
            current = current.parent()
            assert current is not None
    prep = PRIVATE / 'uar10-root-metadata-preparer-r1.json'
    save(prep, dict(identities=identities, metadata_only=True, clock=None))
    oldpath = W / 'uar09-full-next-dev/private-manifest-uar09-r1.json'
    assert sha(oldpath) == OLD_SHA
    old = read(oldpath)
    pins = dict(old['files_sha256'])
    for p, h in pins.items():
        if not Path(p).is_relative_to(ROOT):
            assert sha(p) == h, 'old_noncanonical_frozen_source_changed'
    composition = packet_pins(pins, BASE, '1e08cd7915e067dc264fce5bcbe46ca2a770760b04843479f74511df5a263acf')
    packet_pins(pins, OVERLAY, a.overlay_sha256)
    packet_pins(pins, PACKET, a.packet_sha256)
    # Only the separately reviewed two-test overlay may differ from composition.
    overlay = read(OVERLAY / 'source-handoff.json')
    replacements = overlay['canonical_replacements']
    assert set(replacements) == {'tests/test_uar_hpo_fair_reserve.py', 'tests/test_uar_loss_backend.py'}
    for rel, h in composition['files_sha256'].items():
        if not rel.startswith('candidate/'):
            continue
        target = rel[len('candidate/'):]
        expected = replacements[target]['after_sha256'] if target in replacements else h
        if target in replacements:
            assert replacements[target]['before_sha256'] == h
        add(pins, ROOT / target, expected)
    cfg = read(PACKET / 'private-manifest.template.json')
    census = read(BASE / 'source-census.json')
    inventory = sorted(str(p.resolve()) for folder in ['src', 'tests', 'tools'] for p in (ROOT / folder).rglob('*.py'))
    assert len(inventory) == 183
    assert {str(Path(p).relative_to(ROOT)).replace('\\', '/') for p in inventory} == set(census['canonical_python_inventory'])
    assert all(p in pins for p in inventory)
    cfg.update(readiness='READY_FROZEN_SOURCE_REVIEWED', missing_bindings=[],
        work_root=str(W), canonical_root=str(ROOT), python=old['python'],
        output=str(PACKET / 'attempt-r1'), lock_path=old['lock_path'],
        technical_entry=str(PACKET / 'technical_entry.py'), contracts=str(PACKET / 'contracts.py'),
        focused_helper=old['focused_helper'], canonical_python_inventory=inventory,
        flat_inventory=census['flat_inventory'], run_id='UAR10_CONTEXT_SELECTOR_R3')
    cfg['helpers'] = dict(old['helpers'])
    for key, rel in [('coordinator', 'verified-supervision-next-dev-r2/coordinator.py'),
                     ('sampling', 'verified-resource-sampling-next-dev/verified_sampling.py')]:
        cfg['helpers'][key] = ref(W / rel)
    cfg['predecessors'] = list(old['predecessors']) + [dict(id='cx2',
        **ref(W / 'cx2/terminal-root-closure.json'), actual_exec_session=72141,
        actual_exit_code=0, actual_tool_evidence='ea9a27')]
    for key in ['historical_failure_evidence', 'latest_UQ2_negative_audit', 'latest_UAR08_negative']:
        cfg[key] = old[key]
    cfg['latest_CX2'] = dict(fresh=ref(W / 'cx2/root-confirmation.json'),
        wrapper_exit=ref(W / 'cx2/actual-wrapper-exit-confirmation.json'),
        post_tool_confirmation_actual=dict(exit_code=0, tool='180656'))
    cfg['additional_preparer_receipts'] = [ref(prep)]
    review = external(a.review)
    overlay_review = external(a.overlay_review)
    add(pins, review, a.review_sha256)
    add(pins, overlay_review, a.overlay_review_sha256)
    for p in [Path(__file__), oldpath, prep, W / 'cx2/terminal-root-closure.json',
              W / 'cx2/root-confirmation.json', W / 'cx2/actual-wrapper-exit-confirmation.json',
              W / 'fitting-context-selector-combined-independent-review-r1.json',
              W / 'br-standard-release-qualification-next-dev/controller-r5/run_controller.py']:
        add(pins, p)
    for value in cfg['helpers'].values():
        add(pins, Path(value['path']), value['sha256'])
    whitelist = read(PACKET / 'mapped-method-whitelist.json')
    reviews = {sha(p):p for p in W.glob('*.json')}
    suites = []
    for row in whitelist['suites']:
        rel = row['test_relative_path']
        current_sha = sha(ROOT / rel)
        assert current_sha == row['source_test_sha256']
        source_review = overlay_review if rel in replacements else reviews[row['source_review_sha256']]
        add(pins, source_review)
        suites.append(dict(id=row['id'], test=str(ROOT / rel), test_relative_path=rel,
            expected_tests=len(row['selected_methods']), all_methods=row['all_methods'],
            selected_methods=row['selected_methods'], excluded_methods=row['excluded_methods'],
            exclusion_reason=row['exclusion_reason'], source_review_ref=ref(source_review)))
    cfg['mapped_suites'] = suites
    cfg['mapped_fixture_modules'] = [dict(test_relative_path='tests/test_feature_views.py',
        test=str(ROOT / 'tests/test_feature_views.py'), target='tests/test_feature_views.py',
        sha256=sha(ROOT / 'tests/test_feature_views.py'))]
    cfg['files_sha256'] = pins
    assert isinstance(a.publication, str) and len(a.publication) == 40
    assert all(c in '0123456789abcdef' for c in a.publication)
    cfg['canonical_commit'] = a.publication
    cfg['binding_hints'] = dict(new_UAR10=True, old_clocks_closed=True,
        source_scripts=66, source_checks=704, flat_members=78, mapped_checks=174,
        harness_checks_separate=6, actual_clock=None)
    for p, expected in pins.items():
        assert sha(p) == expected, 'current_binding_pin_changed'
    save(MANIFEST, cfg)
    print(json.dumps(dict(status='PRIVATE_METADATA_FROZEN_REVIEW_PENDING',
        manifest_sha256=sha(MANIFEST), source_pins=len(pins), canonical_python=183,
        no_candidate_imports=True, no_new_clock=True)))

def atomic(a):
    assert a.actual_exit_code == 0 and a.actual_exec_session > 0 and a.actual_tool_evidence
    assert sha(MANIFEST) == a.manifest_sha256
    driver = read(MANIFEST)
    campaign = PACKET / 'attempt-r1/campaign.json'
    state = read(campaign)
    assert state['status'] == 'technical_completed_pending_root'
    assert all(state[k] is True for k in ['cleanup_confirmed', 'source_unchanged', 'temporary_cleanup_confirmed'])
    assert time.monotonic() + 60 < min(state['common_deadline_monotonic'], state['final_deadline_monotonic'])
    cfg = read(PACKET / 'atomic-binding.template.json')
    pins = dict(driver['files_sha256'])
    cfg.update(readiness='READY_REVIEWED_FROZEN', missing_bindings=[], output=driver['output'])
    paths = dict(driver=PACKET / 'run_gate.py', closer=PACKET / 'close_gate.py',
        manifest=MANIFEST, campaign=campaign, python=W / 'venv/Scripts/python.exe',
        independent_source_review=external(a.review), future_UAR10_source_review=external(a.review))
    ps = read(W / 'private/class-cache-ps-policy-preflight-r1.json')
    paths['powershell'] = Path(ps['executable'])
    assert sha(paths['powershell']) == ps['executable_sha256'] == '362a356ce7f0940ec74f73a8fc2c990a2cc24a38a11c90bbd8eca947110ad139'
    for key, path in paths.items():
        actual = sha(path)
        if key not in ['campaign', 'manifest', 'powershell', 'python']:
            assert pins.get(str(path)) == actual, 'fixed_reference_not_previously_reviewed'
        if key == 'python':
            assert actual == 'd59c9a894b319828d023f3aa83d9a3488d2339f9e27e60e49b02abb0d53cf538'
        pins[str(path)] = actual
        cfg[key] = ref(path)
    cfg['child_script_sha256'] = sha(PACKET / 'close_child.ps1')
    cfg['immutable_files'] = pins
    cfg['actual_driver_execution'] = dict(session=a.actual_exec_session, exit_code=0, tool=a.actual_tool_evidence)
    for p, expected in pins.items():
        assert sha(p) == expected
    target = PRIVATE / 'uar10-atomic.r3.ready.json'
    save(target, cfg)
    print(json.dumps(dict(binding_sha256=sha(target), pins=len(pins), no_new_clock=True)))

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['prepare', 'atomic'])
    for key in ['packet-sha256', 'overlay-sha256', 'review', 'review-sha256',
                'overlay-review', 'overlay-review-sha256', 'manifest-sha256', 'actual-tool-evidence', 'publication']:
        p.add_argument('--' + key)
    p.add_argument('--actual-exec-session', type=int)
    p.add_argument('--actual-exit-code', type=int)
    args = p.parse_args()
    (prepare if args.mode == 'prepare' else atomic)(args)
