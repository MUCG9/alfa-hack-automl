"""PROPOSAL: one SHA-bound historical identity fence; no CLI or signalling.

Only the historical gate-a_source identity (16936, 1792736162.1905231)
may use the pinned Stage0 strict terminal absence proof. All other identities
retain the previous conservative orphan policy. The caller must hold the
canonical research lock, pin this source, and guard all campaign inputs.
This module alone is neither a cleanup receipt nor permission to launch.
"""
from pathlib import Path
import hashlib
import json
import math

PARENT = (16936, 1792736162.1905231)
CLOSURE_SHA256 = '39bb0dfbe944ecadb48f10196d57ab8c8c8def40aad284b96952d3072588b011'
FENCE_EPOCH = 1792736704.863943


class Blocked(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise Blocked(code)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def verified_fence(closure_path):
    raw = Path(closure_path).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == CLOSURE_SHA256,
            'historical_absence_proof_changed')
    proof = json.loads(raw.decode('utf-8'))
    require(proof.get('status') == 'completed_Stage0_terminal_owned_absence_confirmed'
            and proof.get('cleanup_confirmed') is True
            and proof.get('active_owned_processes') == []
            and proof.get('fresh_absence_before_and_inside_canonical_lock') is True
            and proof.get('strict_known_parent_orphan_scan') is True
            and proof.get('no_process_signalled') is True
            and proof.get('source_unchanged') is True
            and proof.get('recorded_epoch') == FENCE_EPOCH,
            'historical_absence_proof_incomplete')
    tracked = {(v['pid'], float(v['create_time']))
               for v in proof['tracked_identities']}
    require(PARENT in tracked, 'historical_parent_not_covered_by_proof')
    return {'identity': PARENT, 'not_alive_by_epoch': FENCE_EPOCH,
            'closure_sha256': CLOSURE_SHA256}


def strict_orphan_check_with_one_fence(owner, known, closure_path,
                                     psutil_module=None):
    """Read exact identities and PPID inventory, never argv/env or process names.

    A direct child born strictly after a SHA-bound proof that its historical
    parent identity was already absent cannot descend from that identity.
    AccessDenied, missing birth times and live exact identities still block.
    """
    if psutil_module is None:
        import psutil as psutil_module
    psutil = psutil_module
    fence = verified_fence(closure_path)
    observer = owner.StrictOwnedObserver()
    observer.remember((v['pid'], v['create_time']) for v in known)
    require(PARENT in observer.seen, 'one_fence_parent_not_in_known_union')
    require(not observer.observe() and not observer.denials,
            'strict_owned_identity_or_traversal_unresolved')
    try:
        entries = list(psutil.process_iter(['pid', 'ppid', 'create_time', 'status'],
                                          ad_value=None))
    except psutil.AccessDenied:
        raise Blocked('orphan_inventory_enumeration_denied') from None
    excluded = {}
    changed = True
    while changed:
        changed = False
        for process in entries:
            info = process.info
            for parent_pid, parent_created in tuple(observer.seen):
                if info.get('ppid') != parent_pid:
                    continue
                pid, created = info.get('pid', process.pid), info.get('create_time')
                require(type(pid) is int and pid > 0, 'known_parent_child_pid_unknown')
                if not finite(created) or created <= 0:
                    observer.denied(pid, None, 'known_parent_orphan_identity',
                                    'AccessDenied_or_unknown_birth_time')
                    raise Blocked('known_parent_orphan_birth_time_unverifiable')
                if created < parent_created or (pid, created) in observer.seen:
                    continue
                parent_absent = False
                try:
                    actual_parent = psutil.Process(parent_pid).create_time()
                    require(finite(actual_parent) and actual_parent > 0,
                            'known_parent_birth_time_unknown')
                    require(actual_parent != parent_created,
                            'exact_historical_parent_alive')
                    if created >= actual_parent:
                        continue  # Existing reviewed live-parent PID-reuse exclusion.
                except psutil.NoSuchProcess:
                    parent_absent = True
                except psutil.AccessDenied:
                    observer.denied(parent_pid, parent_created,
                                    'known_parent_orphan_parent', 'AccessDenied')
                    raise Blocked('known_parent_orphan_parent_unverifiable') from None
                try:
                    current = psutil.Process(pid)
                    if current.create_time() != created or current.ppid() != parent_pid:
                        continue
                    current.status()
                except psutil.NoSuchProcess:
                    continue
                except psutil.AccessDenied:
                    observer.denied(pid, created, 'known_parent_orphan_reverify',
                                    'AccessDenied')
                    raise Blocked('known_parent_orphan_reverification_denied') from None
                if (parent_absent and (parent_pid, parent_created) == PARENT
                        and created > fence['not_alive_by_epoch']):
                    excluded[(pid, created)] = {
                        'pid': pid, 'create_time': created, 'ppid': parent_pid,
                        'historical_parent_create_time': parent_created,
                        'historical_parent_absence_no_later_than_epoch': FENCE_EPOCH,
                        'proof_sha256': CLOSURE_SHA256,
                        'reason': 'child_born_after_proven_historical_parent_absence'}
                    continue
                observer.remember([(pid, created)])
                changed = True
    require(not observer.final_check()['unresolved'],
            'strict_owned_orphan_denied_or_live')
    return {'tracked_identities': [{'pid': p, 'create_time': c}
                                  for p, c in sorted(observer.seen)],
            'excluded_impossible_parent_edges': [excluded[k] for k in sorted(excluded)],
            'fence': fence, 'no_signals': True}
