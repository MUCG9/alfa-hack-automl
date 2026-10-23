"""PROPOSED: explicit reviewed launch of one saved-artifact pair0 diagnostic.

Prepare/review/publish this source before --execute. It cannot resume the CV,
start learners, call providers, qualify a release, or submit. This guard itself
has not been executed during source preparation.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import time

import psutil

sys.dont_write_bytecode = True
STAGE_SHA = 'd2e5f64276e639fd6f20b315014701bb12352b2f2c65b3294ced04a9ccd7c456'
MANIFEST_SHA = 'a70f2a0cefb686dd04535c76b4c9e9e80073aba23d86fd7aad7e52fc7b9eee6a'
VERIFIER_SHA = 'f58ae5b865eea672a8904d6ba96a5381f112f71c46bdf42919b9b46525ddd426'
OWNER_SHA = '8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8'
LOCK_SHA = '78a0441bb3b9ea60197e9a1a6e1087f6e4cd0886593ec54bcfc4e41c9abe5a45'
CLOSURE_SHA = 'a09c58461ef19c509b68526367bc61c635852292f9fb22662c1d783d7612bf87'
FENCE_SHA = 'f6f112fc9eedce4e402e87a306dfae30bfedd75b457458b5ac5431f2f67757c8'
PROCESSES_SHA = 'fac3a54ba91958576b913585f1e567460201af2bc09d18a46c87e80a8545482d'
SCOPE = 'posthoc_pair0_saved_artifact_diagnostic_only'
PARENT_SECONDS, CHILD_SECONDS, CLEANUP_GUARD_RESERVE = 180, 120, 30
MEMORY_BYTES = 1024 * 2**20

# Inline bytes are covered by this guard's published SHA. No user code is run.
CHILD_BOOTSTRAP = r'''from pathlib import Path
import importlib.abc
import importlib.util
import json
import runpy
import sys
sys.dont_write_bytecode = True
DENIED = {'automl', 'agent', 'lightgbm', 'catboost', 'xgboost', 'optuna',
          'torch', 'tensorflow', 'openai', 'litellm', 'requests', 'httpx',
          'aiohttp', 'urllib3', 'websocket', 'websockets'}
class NoRuntimeOrNetwork(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split('.', 1)[0]
        if root in DENIED or root.startswith(('automl_', 'agent_')):
            raise RuntimeError('nofit_model_runtime_or_network_import_forbidden')
        return None
def audit(event, args):
    if event.startswith('socket.') or event in {'subprocess.Popen', 'os.system',
            'os.exec', 'os.posix_spawn', 'os.fork', 'os.forkpty'}:
        raise RuntimeError('nofit_network_or_process_operation_forbidden')
    if event == 'open' and args and isinstance(args[0], (str, bytes)):
        path = Path(args[0].decode() if isinstance(args[0], bytes) else args[0])
        if any(p.lower() == 'private' or p.lower().startswith('run-budget-') for p in path.parts):
            raise RuntimeError('nofit_private_config_or_ledger_read_forbidden')
sys.meta_path.insert(0, NoRuntimeOrNetwork())
sys.addaudithook(audit)
verifier, *arguments = sys.argv[1:]
sys.argv = [verifier] + arguments
runpy.run_path(verifier, run_name='__main__')
'''


class Blocked(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise Blocked(code)


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            value.update(block)
    return value.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value, exclusive=True):
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    if exclusive:
        with Path(path).open('xb') as stream:
            stream.write(raw)
    else:
        pending = Path(path).with_name(Path(path).name + '.pending')
        pending.write_bytes(raw)
        pending.replace(path)


def path(work, relative):
    require(isinstance(relative, str) and relative, 'bound_path_missing')
    value = Path(relative)
    require(not value.is_absolute(), 'relative_work_path_required')
    value = (work / value).resolve()
    require(value.is_relative_to(work), 'bound_path_outside_work')
    return value


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def identity(value):
    require(isinstance(value, dict), 'identity_object_required')
    pid, born = value.get('pid'), value.get('create_time')
    require(type(pid) is int and pid > 0 and type(born) in (float, int)
            and math.isfinite(born) and born > 0, 'exact_identity_required')
    return {'pid': pid, 'create_time': float(born)}


def identities(values):
    result = {(v['pid'], v['create_time']): v for v in map(identity, values)}
    return [result[key] for key in sorted(result)]


def clean_environment(output):
    env = {name: os.environ[name] for name in ['SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATH', 'TEMP', 'TMP']
           if name in os.environ}
    env.update(PYTHONIOENCODING='utf-8', PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1',
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
               NUMEXPR_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1',
               BLIS_NUM_THREADS='1', MPLCONFIGDIR=str(output / 'mpl-cache'))
    require(not any(any(s in name.upper() for s in ['KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'AUTH']) for name in env),
            'clean_environment_secret_named_variable')
    return env


def main():
    start, tick = time.time(), time.monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--work-root', type=Path, required=True)
    for item in ['root-review', 'verifier', 'closure', 'publication']:
        parser.add_argument('--' + item, required=True)
        parser.add_argument('--' + item + '-sha256', required=True)
    for item in ['guard', 'owner', 'fence', 'processes']:
        parser.add_argument('--' + item + '-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    require(args.execute, 'explicit_execute_required_no_implicit_launch')
    work = args.work_root.resolve()
    repo = work / 'alfa-hack-automl'
    output = path(work, args.output)
    require(output != work and output.parent == work and not output.exists(), 'new_top_level_output_required')
    root_review_path = path(work, args.root_review)
    verifier_path = path(work, args.verifier)
    closure_path = path(work, args.closure)
    publication_path = path(work, args.publication)
    owner_path = work / 'fullagent-cv-launch-r4/ownership.py'
    lock_path = work / 'fullagent-cv-launch-r4/research_lock.py'
    fence_path = work / 'terminal_identity_fence_r1.py'
    fence_proof = work / 'fullagent-cv-stage1-review-r4/stage0-terminal-ownership.json'
    processes_path = repo / 'src/automl/infrastructure/processes.py'
    stage_path = work / 'f4/stage1.json'
    manifest_path = work / 'fullagent-cv-launch-r4/manifest.json'
    binding_path = work / 'fullagent-cv-launch-r4/source-binding.json'
    require(sha(Path(__file__)) == args.guard_sha256, 'guard_source_not_explicitly_pinned')
    require(args.verifier_sha256 == VERIFIER_SHA and sha(verifier_path) == VERIFIER_SHA, 'verifier_source_changed')
    require(args.owner_sha256 == OWNER_SHA and sha(owner_path) == OWNER_SHA, 'owner_source_changed')
    require(sha(lock_path) == LOCK_SHA and args.fence_sha256 == FENCE_SHA and sha(fence_path) == FENCE_SHA
            and args.processes_sha256 == PROCESSES_SHA and sha(processes_path) == PROCESSES_SHA,
            'ownership_dependency_changed')
    require(sha(stage_path) == STAGE_SHA and sha(manifest_path) == MANIFEST_SHA, 'original_stage_or_manifest_changed')
    require(sha(root_review_path) == args.root_review_sha256 and args.closure_sha256 == CLOSURE_SHA
            and sha(closure_path) == CLOSURE_SHA
            and sha(publication_path) == args.publication_sha256, 'explicit_root_evidence_changed')
    review, closure, publication = load(root_review_path), load(closure_path), load(publication_path)
    require(review.get('scope') == SCOPE and review.get('root_reviewed') is True
            and review.get('execution_authorized') is True and review.get('output_directory') == args.output
            and review.get('guard_sha256') == args.guard_sha256
            and review.get('verifier_sha256') == VERIFIER_SHA
            and review.get('terminal_closure_sha256') == args.closure_sha256
            and review.get('fence_sha256') == args.fence_sha256
            and review.get('processes_sha256') == args.processes_sha256
            and review.get('owner_sha256') == OWNER_SHA
            and review.get('parent_seconds') == PARENT_SECONDS and review.get('child_seconds') == CHILD_SECONDS
            and review.get('memory_mib') == 1024 and review.get('threads') == 1
            and review.get('fits_allowed') is False and review.get('api_calls_allowed') is False
            and review.get('full_CV_or_qualification_allowed') is False, 'root_review_contract_wrong')
    require(publication.get('remote_sha_verified') is True
            and publication.get('root_review_sha256') == args.root_review_sha256,
            'reviewed_source_publication_unconfirmed')
    commit = publication.get('commit')
    require(isinstance(commit, str) and len(commit) == 40 and all(c in '0123456789abcdef' for c in commit),
            'published_commit_wrong')
    published = publication.get('files')
    require(isinstance(published, dict), 'published_source_inventory_missing')
    for filename in [Path(__file__).resolve(), verifier_path, root_review_path, fence_path]:
        relative = filename.relative_to(work).as_posix()
        record = published.get(relative) or {}
        require(record.get('sha256') == sha(filename) and isinstance(record.get('git_path'), str),
                'required_source_not_in_publication')
        data = subprocess.check_output(['git', '-c', 'safe.directory=' + repo.as_posix(), '-C', str(repo),
                                        'show', commit + ':' + record['git_path']], timeout=5)
        require(hashlib.sha256(data).hexdigest() == record['sha256'], 'published_git_bytes_differ')
    require(closure.get('stage_receipt_sha256') == STAGE_SHA
            and closure.get('cleanup_confirmed') is True and closure.get('source_unchanged') is True
            and closure.get('immutable_files_rehashed') == 430 and closure.get('active_owned_processes') == []
            and closure.get('fresh_absence_before_and_inside_canonical_lock') is True
            and closure.get('strict_known_parent_orphan_scan') is True
            and closure.get('exec_exit_code_observed_by_root') == 1, 'terminal_closure_incomplete')
    preparers = review.get('closure_preparer_identities')
    require(isinstance(preparers, list) and preparers, 'explicit_closure_preparer_identities_required')
    prior = []
    for field in ['tracked_identities', 'launcher_identities', 'review_preparer_identities',
                  'closure_preparer_identities', 'preparer_identities']:
        value = closure.get(field, [])
        require(isinstance(value, list), 'closure_identity_field_wrong')
        prior.extend(value)
    prior = identities(prior + preparers)
    require(prior, 'terminal_identity_union_empty')
    manifest, stage, binding = load(manifest_path), load(stage_path), load(binding_path)
    require(len(manifest['immutable_files']) == 430, 'original_430_inventory_wrong')
    fixed = {path(work, name): expected for name, expected in manifest['immutable_files'].items()}
    for filename, expected in [(Path(__file__).resolve(), args.guard_sha256), (verifier_path, VERIFIER_SHA),
                               (root_review_path, args.root_review_sha256), (closure_path, args.closure_sha256),
                               (publication_path, args.publication_sha256), (fence_path, args.fence_sha256),
                               (processes_path, args.processes_sha256), (stage_path, STAGE_SHA),
                               (manifest_path, MANIFEST_SHA)]:
        require(filename not in fixed or fixed[filename] == expected, 'source_registry_conflict')
        fixed[filename] = expected
    # The source-binding and fixed historical fence proof are separately pinned too.
    fixed[binding_path] = sha(binding_path)
    fixed[fence_proof] = '39bb0dfbe944ecadb48f10196d57ab8c8c8def40aad284b96952d3072588b011'
    for relative, expected in closure['evidence_sha256'].items():
        filename = path(work, relative)
        require(filename not in fixed or fixed[filename] == expected, 'closure_evidence_registry_conflict')
        fixed[filename] = expected
    generated = {}
    parent_deadline = min(tick + PARENT_SECONDS, stage['common_deadline_monotonic'])
    parent_absolute = min(start + PARENT_SECONDS, stage['common_absolute_deadline_unix'])

    def guard():
        require(time.monotonic() <= parent_deadline and time.time() <= parent_absolute, 'parent_or_original_clock_exhausted')
        require(psutil.Process().memory_info().rss <= MEMORY_BYTES, 'parent_memory_limit')
        for filename, expected in {**fixed, **generated}.items():
            require(sha(filename) == expected, 'source_or_declaration_binding_changed')

    guard()
    owner = module('_posthoc_nofit_owner', owner_path)
    locks = module('_posthoc_nofit_lock', lock_path)
    fence = module('_posthoc_nofit_fence', fence_path)
    processes = module('_posthoc_nofit_processes', processes_path)
    before = fence.strict_orphan_check_with_one_fence(owner, prior, fence_proof)
    child, tree, verified = None, None, False
    observer = owner.StrictOwnedObserver()
    result = {'scope': SCOPE, 'status': 'preparing_bounded_nofit_diagnostic',
              'start_unix': start, 'start_monotonic': tick, 'parent_seconds': PARENT_SECONDS,
              'child_seconds': CHILD_SECONDS, 'memory_mib': 1024, 'threads': 1,
              'guard_sha256': args.guard_sha256, 'verifier_sha256': VERIFIER_SHA,
              'root_review_sha256': args.root_review_sha256, 'closure_sha256': args.closure_sha256,
              'publication_sha256': args.publication_sha256, 'publication_commit': commit,
              'original_stage_sha256': STAGE_SHA, 'original_manifest_sha256': MANIFEST_SHA,
              'complete_CV': False, 'OOF_complete': False, 'final_CV': None,
              'promotion': False, 'official_submission': False, 'quality_qualification': None,
              'metrics_trusted': False, 'metrics': None, 'gain_claims': None,
              'source_unchanged': None, 'global_terminal_fenced_check_passed': False,
              'fits_started': 0, 'API_calls_started': 0,
              'parent_identity': identity({'pid': psutil.Process().pid, 'create_time': psutil.Process().create_time()})}
    with locks.ResearchLock(repo / 'test-runs/.owned-research.lock') as lock:
        lock.write_identity(result['parent_identity'])
        guard()
        inside = fence.strict_orphan_check_with_one_fence(owner, identities(prior + before['tracked_identities']), fence_proof)
        prior = identities(prior + inside['tracked_identities'])
        output.mkdir(exist_ok=False)
        receipt_path = output / 'parent-receipt.json'
        save(receipt_path, result)
        try:
            require(parent_deadline - time.monotonic() >= CHILD_SECONDS + CLEANUP_GUARD_RESERVE,
                    'complete_child_cleanup_guard_reserve_unavailable')
            child_start = time.monotonic()
            child_deadline = child_start + CHILD_SECONDS
            declaration = {'scope': SCOPE, 'root_reviewed': True, 'execution_authorized': True,
                'original_stage_sha256': STAGE_SHA, 'original_manifest_sha256': MANIFEST_SHA,
                'original_verifier_sha256': manifest['independent_verifier_sha256'],
                'posthoc_verifier_sha256': VERIFIER_SHA,
                'fits_allowed': False, 'api_calls_allowed': False, 'full_CV_or_qualification_allowed': False,
                'audit_start_monotonic': child_start, 'audit_cap_seconds': CHILD_SECONDS,
                'root_review': {'path': args.root_review, 'sha256': args.root_review_sha256},
                'terminal_ownership': {'path': args.closure, 'sha256': args.closure_sha256}}
            declaration_path = output / 'declaration.json'
            save(declaration_path, declaration)
            plan = {'manifest': manifest, 'manifest_path': 'fullagent-cv-launch-r4/manifest.json',
                'manifest_sha256': MANIFEST_SHA,
                'r3_protocol': {'path': 'fullagent-fixed-half-plan-r3/protocol.json',
                    'sha256': '5b2164c3721c84b8e6eb85c0dec7571474316b2e956d6ecdeee235d0193addcb'},
                'publication_receipt': {'path': binding['publication_receipt'], 'sha256': binding['publication_receipt_sha256']},
                'source_publication_receipt': {'path': binding['source_publication_receipt'], 'sha256': binding['source_publication_receipt_sha256']},
                'stage_receipt_path': 'f4/stage1.json',
                'common_absolute_deadline_unix': stage['common_absolute_deadline_unix'],
                'common_deadline_monotonic': stage['common_deadline_monotonic'],
                'archives': {a: {'path': r['archive'], 'sha256': r['archive_sha256']} for a, r in manifest['arms'].items()},
                'verifier_source_sha256': manifest['independent_verifier_sha256'],
                'posthoc_declaration': {'path': declaration_path.relative_to(work).as_posix(), 'sha256': sha(declaration_path)}}
            plan_path, slots_path, boot_path = output / 'plan.json', output / 'slots.json', output / 'child_bootstrap.py'
            save(plan_path, plan)
            save(slots_path, stage['arms'])  # Original 0b technical_failure is retained byte-for-object.
            with boot_path.open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(CHILD_BOOTSTRAP)
            generated.update({p: sha(p) for p in [declaration_path, plan_path, slots_path, boot_path]})
            guard()
            fence.strict_orphan_check_with_one_fence(owner, prior, fence_proof)
            require(parent_deadline - time.monotonic() >= CHILD_SECONDS + CLEANUP_GUARD_RESERVE
                    and time.monotonic() <= child_deadline - 1, 'prelaunch_complete_reserves_exhausted')
            command = [sys.executable, '-X', 'utf8', '-u', str(boot_path), str(verifier_path),
                '--work', str(work), '--plan', str(plan_path), '--slots', str(slots_path),
                '--fold-manifest', str(work / 'fullagent-cv-stage1-plan-r1/manifest.json'),
                '--output', str(output / 'audit.json'), '--pair', '0',
                '--audit-deadline-monotonic', str(child_deadline)]
            with (output / 'child.log').open('xb') as log:
                child = subprocess.Popen(command, cwd=output, env=clean_environment(output),
                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    start_new_session=True)
                root = psutil.Process(child.pid)
                root_identity = root.pid, root.create_time()
                observer.remember([root_identity])
                result['owned_root'] = {'pid': root_identity[0], 'create_time': root_identity[1]}
                tree = processes.ProcessTree(child)
                observer.remember(tree.members)
                verified = root_identity in tree.members
                require(verified, 'child_initial_owned_root_not_verified')
                result['status'] = 'running_nofit_diagnostic'
                save(receipt_path, result, exclusive=False)
                while child.poll() is None:
                    live = observer.observe()
                    require(not observer.denials, 'child_owned_identity_or_traversal_denied')
                    tree.members.update(live)
                    total = psutil.Process().memory_info().rss
                    for process in live.values():
                        try:
                            total += process.memory_info().rss
                        except psutil.NoSuchProcess:
                            continue
                    result['peak_parent_and_owned_rss_mib'] = max(result.get('peak_parent_and_owned_rss_mib', 0), total / 2**20)
                    require(total <= MEMORY_BYTES, 'whole_owned_memory_limit')
                    require(time.monotonic() <= child_deadline and time.monotonic() <= parent_deadline - CLEANUP_GUARD_RESERVE
                            and time.time() <= parent_absolute, 'child_or_common_deadline_exhausted')
                    time.sleep(.1)
            result['child_exit_code'] = child.returncode
            require(child.returncode == 0, 'child_diagnostic_nonzero_exit')
        except BaseException as exc:
            result.update(status='technical_failure', exception_type=type(exc).__name__,
                          failure_code=str(exc) if isinstance(exc, Blocked) else 'guard_operation_failed')
        finally:
            try:
                result.update(owner.cleanup_owned(child, tree, observer, verified, processes.ProcessTree))
            except BaseException as exc:
                result.update(status='technical_failure', cleanup_confirmed=False,
                              exception_type=type(exc).__name__, failure_code='canonical_child_cleanup_failed')
                # Popen owns the exact root handle; this is never a predecessor PID signal.
                if child is not None and child.poll() is None:
                    try:
                        child.terminate()
                        child.wait(timeout=3)
                    except BaseException:
                        try:
                            child.kill()
                            child.wait(timeout=3)
                        except BaseException:
                            pass
            if child is not None:
                result['child_exit_code'] = child.poll()
        try:
            require(result.get('cleanup_confirmed') is True, 'child_cleanup_unconfirmed')
            after = fence.strict_orphan_check_with_one_fence(owner,
                identities(prior + result.get('owned_process_identities', [])), fence_proof)
            result['terminal_fenced_observer'] = after
            guard()
            require(result.get('status') != 'technical_failure' and result.get('child_exit_code') == 0,
                    'failed_child_or_cleanup_cannot_trust_diagnostic')
            audit_path = output / 'audit.json'
            audited = load(audit_path)
            require(audited.get('status') == 'posthoc_pair0_diagnostic_audited'
                    and audited.get('scope') == SCOPE and audited.get('fold') == 0
                    and audited.get('complete_CV') is False and audited.get('OOF_complete') is False
                    and audited.get('promotion') is False and audited.get('final_CV') is None
                    and audited.get('stage2_quality_prerequisite_passed') is False,
                    'diagnostic_output_scope_wrong')
            generated[audit_path] = sha(audit_path)
            guard()
            result.update(status='saved_pair0_diagnostic_completed', metrics_trusted=True,
                audit={'path': audit_path.relative_to(work).as_posix(), 'sha256': sha(audit_path)},
                source_unchanged=True, global_terminal_fenced_check_passed=True,
                original_technical_CV_status_preserved=True)
        except BaseException as exc:
            result.update(status='technical_failure', exception_type=type(exc).__name__,
                failure_code=str(exc) if isinstance(exc, Blocked) else 'post_audit_guard_failed',
                metrics_trusted=False, metrics=None, gain_claims=None, audit=None,
                source_unchanged=None, global_terminal_fenced_check_passed=False)
        result.update(seconds=time.monotonic() - tick, end_unix=time.time())
        save(receipt_path, result, exclusive=False)
        # A late clock/hash/ownership/write failure invalidates the written success receipt.
        try:
            guard()
            fence.strict_orphan_check_with_one_fence(owner,
                identities(prior + result.get('owned_process_identities', [])), fence_proof)
            require(result['status'] == 'saved_pair0_diagnostic_completed', 'diagnostic_failed')
        except BaseException as exc:
            result.update(status='technical_failure', metrics_trusted=False, metrics=None,
                gain_claims=None, audit=None, exception_type=type(exc).__name__,
                failure_code=str(exc) if isinstance(exc, Blocked) else 'late_final_guard_failed',
                source_unchanged=None, global_terminal_fenced_check_passed=False,
                seconds=time.monotonic() - tick, end_unix=time.time())
            save(receipt_path, result, exclusive=False)
            raise
    print(json.dumps({'status': result['status'], 'scope': SCOPE,
                      'metrics_trusted': result['metrics_trusted'], 'promotion': False}))


if __name__ == '__main__':
    main()
