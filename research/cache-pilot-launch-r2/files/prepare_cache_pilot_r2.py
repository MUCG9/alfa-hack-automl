"""Inspect by default; --write freezes a new cache pilot packet, never starts it.

No task copies, worker jobs, tests, fits, API calls or experiment clock are made
by preparation. An external root-reviewed predecessor binding and source-derived
Windows fixture proof are mandatory inputs, rather than guessed future closure.
"""
from pathlib import Path
import argparse
import ast
import hashlib
import importlib.metadata
import importlib.util
import json
import platform
import sys
import zipfile

sys.dont_write_bytecode = True
PLAN_SHA = '132a1d797288a4a5f839fec3d9760764d3bc833540798de1535bb272a5f9ef1c'
FINAL_SHA = 'f83e57929928b2e31a114c18f44d1ed85a2d0e541dc7df12fdc9c9d7887c94ba'
ARCHIVES = {'baseline': '88dac47a9a815b98b5d00c44e5650518f84db5197c9eac56b79fb1ce465c92a0',
             'candidate': 'e0f57d148bab30c98d06c4ee933c0a7edcbd321e26b456feb588bfc78fdc04fa'}
LIBRARIES = ('numpy', 'pandas', 'scipy', 'joblib', 'scikit-learn', 'lightgbm',
             'catboost', 'xgboost', 'optuna', 'psutil', 'threadpoolctl')
SLOTS = [('c0o', 'c-trial00', False, 600, 630), ('c0n', 'c-trial00', True, 600, 630),
         ('c1n', 'c-trial01', True, 600, 630), ('c1o', 'c-trial01', False, 600, 630),
         ('r0o', 'r-trial00', False, 120, 150), ('r0n', 'r-trial00', True, 120, 150)]


def require(condition, code):
    if not condition:
        raise ValueError(code)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def path(work, name):
    p = (work / name).resolve()
    require(not Path(name).is_absolute() and p.is_relative_to(work), 'unsafe_packet_reference')
    return p


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        allow_nan=False).encode('utf-8')).hexdigest()


def dependencies():
    result = {'python': platform.python_version(), 'implementation': platform.python_implementation()}
    for name in LIBRARIES:
        dist = importlib.metadata.distribution(name)
        records = {Path(p).name: digest(dist.locate_file(p)) for p in dist.files or []
                   if Path(p).name in {'METADATA', 'RECORD'}}
        require(set(records) == {'METADATA', 'RECORD'}, 'dependency_metadata_missing')
        result[name] = {'version': dist.version, 'metadata': records}
    return result


def registry(root):
    tree = ast.parse((root / 'tools/run_checks.py').read_text(encoding='utf-8'))
    rows = [ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == 'CHECKS' for t in n.targets)]
    require(len(rows) == 1 and all(type(v) is int and v > 0 for v in rows[0].values()), 'registry_invalid')
    return rows[0]


def archive(pathname):
    with zipfile.ZipFile(pathname) as z:
        names = z.namelist()
        require(len(names) == len(set(names)) and all(Path(n).name == n and
                n.endswith(('.py', '.txt')) for n in names), 'archive_not_flat_unique')
        files = {n: z.read(n) for n in names}
    require({'automl_worker.py', 'solution.py', 'requirements.txt'} <= files.keys(), 'archive_incomplete')
    tree = ast.parse(files['automl_worker.py'].decode('utf-8'))
    require(any(isinstance(n, ast.If) and ast.unparse(n.test) == "__name__ == '__main__'"
                for n in tree.body), 'real_worker_entrypoint_missing')
    return {n: hashlib.sha256(b).hexdigest() for n, b in files.items()}


def runtime_paths(work, source, archive_files):
    """Enumerate the fixed callbacks' finite output graph from frozen producer AST.

    The separately bound fixture proof covers test-created graphs. Calibration
    lives in-process and has no directory producer in this worker. The fixed
    classification recipe has one 2-view level; regression has no components.
    """
    worker = source / 'src/automl/execution/worker.py'
    atomic = source / 'src/automl/infrastructure/atomic.py'
    publish = source / 'src/automl/publishing/service.py'
    probe = source / 'src/automl/execution/feature_engineering/teacher_probe.py'
    tree = ast.parse(worker.read_text(encoding='utf-8'))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_ensemble')
    producers = [ast.unparse(n) for n in ast.walk(fn) if isinstance(n, ast.BinOp)
                 and isinstance(n.op, ast.Div) and isinstance(n.left, ast.Name)
                 and n.left.id == 'output' and isinstance(n.right, ast.JoinedStr)]
    require(set(producers) == {"output / f'component-{index}'"}, 'worker_component_producer_changed')
    require("internal = dict(recipe, engine='ensemble', params={}, components=components, weights=[0.5, 0.5])"
            in ast.unparse(tree), 'two_view_procedure_changed')
    names = set()
    sources = [worker, atomic, publish, probe]
    for file in sources:
        for node in ast.walk(ast.parse(file.read_text(encoding='utf-8'))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                name = node.value
                if Path(name).name == name and name.endswith(('.json', '.csv', '.npz')):
                    names.add(name)
            if isinstance(node, ast.JoinedStr):
                value = ast.unparse(node)
                if 'fit-parents-' in value:
                    require(value == "f'fit-parents-{len(policy_records)}.npz'", 'dynamic_output_producer_changed')
                    names.add('fit-parents-' + str(sys.maxsize) + '.npz')
    require({'teacher-diagnostics.json', 'result.json', 'submission.csv',
             'validation_predictions.csv', 'validation_probabilities.npz', 'test_probabilities.npz'} <= names,
            'worker_artifact_inventory_missing')
    require("'.tmp'" in atomic.read_text(encoding='utf-8') and
            "'.csv.tmp'" in publish.read_text(encoding='utf-8'), 'atomic_suffix_changed')
    names |= {n + '.tmp' for n in names if n.endswith('.json')}
    names |= {n + '.tmp' for n in names if n.endswith('.csv')}
    paths = []
    for slot, anchor, _, _, _ in SLOTS:
        base = work / 'k1' / slot
        nodes = [base, base / 'component-0', base / 'component-1'] if anchor[0] == 'c' else [base]
        paths.extend(root / n for root in nodes for n in names)
    paths.extend(work / 'k1' / 'flat' / n for n in archive_files)
    rows = [{'path': p.relative_to(work).as_posix(), 'file_characters': len(str(p)),
             'directory_characters': len(str(p.parent))} for p in paths]
    require(all(r['file_characters'] <= 259 and r['directory_characters'] <= 247 for r in rows),
            'runtime_MAX_PATH_violation')
    return {'status': 'finite_fixed_callback_AST_graph', 'output_root': 'k1',
        'source_sha256': {p.relative_to(work).as_posix(): digest(p) for p in sources},
        'producer_basenames': sorted(names), 'component_depth': 1,
        'calibration_directory_depth': 0, 'cache_directory_depth': 0,
        'calibration_and_cache': 'In-process teacher cache and calibration; sidecar is a leaf file.',
        'maximum_file': max(rows, key=lambda r: r['file_characters']),
        'maximum_directory': max(rows, key=lambda r: r['directory_characters']),
        'paths_enumerated': len(rows), 'violations': []}


def inspect(work, predecessor, fixture):
    plan = work / 'cache-pilot-plan-r1'
    final = work / 'cache-pilot-dev/evidence/final-manifest-r2.json'
    require(digest(plan / 'manifest-r3.json') == PLAN_SHA and digest(final) == FINAL_SHA, 'frozen_authority_changed')
    manifest = load(plan / 'manifest-r3.json')
    immutable = {(plan / 'manifest-r3.json').relative_to(work).as_posix(): PLAN_SHA,
                 final.relative_to(work).as_posix(): FINAL_SHA}
    for n, sha in manifest['files_sha256'].items():
        require(digest(plan / n) == sha, 'plan_file_changed')
        immutable[(plan / n).relative_to(work).as_posix()] = sha
    for n, sha in load(final)['source_code_files_sha256'].items():
        require(digest(path(work, n)) == sha, 'candidate_source_changed')
        immutable[n] = sha
    for n in ['cache-pilot-independent-review-r3.json', 'cache-pilot-source-independent-review-r2.json',
              'cache-pilot-dev/evidence/schema-r1.json', 'cache-pilot-dev/evidence/technical-count-addendum-r1.json',
              'cache-pilot-dev/evidence/run_focused_mock_checks.py', 'cache-pilot-dev/evidence/pretest-manifest-r2.json',
              'support_component_coordinator.py', 'build_fullagent_cv_binding.py',
              'terminal_identity_fence_r1.py',
              'fullagent-cv-stage1-review-r4/stage0-terminal-ownership.json',
              'fullagent-cv-stage1-terminal-ownership-fenced-r1.json',
              'alfa-hack-automl/tools/research_lock.py', 'hpo_campaign_coordinator.py',
              'alfa-hack-automl/src/automl/infrastructure/processes.py',
              'fullagent_cv_coordinator_r4.py', 'prepare_cache_pilot_r2.py',
              'cache_pilot_coordinator_r2.py', 'verify_cache_pilot_r2.py']:
        immutable[n] = digest(path(work, n))
    require(immutable['terminal_identity_fence_r1.py'] ==
            'f6f112fc9eedce4e402e87a306dfae30bfedd75b457458b5ac5431f2f67757c8'
            and immutable['fullagent-cv-stage1-review-r4/stage0-terminal-ownership.json'] ==
            '39bb0dfbe944ecadb48f10196d57ab8c8c8def40aad284b96952d3072588b011'
            and immutable['fullagent-cv-stage1-terminal-ownership-fenced-r1.json'] ==
            'a09c58461ef19c509b68526367bc61c635852292f9fb22662c1d783d7612bf87',
            'reviewed_terminal_fence_or_closure_changed')
    require(digest(path(work, predecessor)) and digest(path(work, fixture)), 'external_proof_missing')
    pred = load(path(work, predecessor))
    require(pred.get('root_reviewed') is True and pred.get('scope_complete') is True and
            pred.get('cleanup_confirmed') is True and pred.get('source_unchanged') is True and
            pred.get('owned_identities') and pred.get('files_sha256') and pred.get('owned_receipt_paths')
            and set(pred['owned_receipt_paths']) <= set(pred['files_sha256']), 'predecessor_binding_incomplete')
    for n, sha in pred['files_sha256'].items():
        require(digest(path(work, n)) == sha, 'predecessor_reference_changed')
        immutable[n] = sha
    proof = load(path(work, fixture))
    require(proof.get('status') == 'static_fixture_path_coverage_pass' and proof.get('output_root') == 'k1'
            and proof.get('output_root_absolute_characters') == len(str(work / 'k1'))
            and proof.get('maximum_file_characters', 999) <= 259
            and proof.get('maximum_directory_characters', 999) <= 247
            and proof.get('source_sha256'), 'new_prefix_fixture_path_proof_missing')
    for n, sha in proof['source_sha256'].items():
        require(digest(path(work, n)) == sha, 'fixture_proof_source_changed')
        immutable[n] = sha
    immutable[predecessor] = digest(path(work, predecessor))
    immutable[fixture] = digest(path(work, fixture))
    require(digest(work / 'fullagent-cv-launch-r4/manifest.json') ==
            'a70f2a0cefb686dd04535c76b4c9e9e80073aba23d86fd7aad7e52fc7b9eee6a', 'baseline_inventory_authority_changed')
    immutable['fullagent-cv-launch-r4/manifest.json'] = digest(work / 'fullagent-cv-launch-r4/manifest.json')
    old = load(work / 'fullagent-cv-launch-r4/manifest.json')['arms']['a']
    technical = load(plan / 'technical-fixtures.json')
    roots = {'baseline': work / old['source_root'], 'candidate': work / 'cache-pilot-dev'}
    source_files = {'baseline': dict(old['source_files_sha256']), 'candidate': {
        n.removeprefix('cache-pilot-dev/'): sha for n, sha in load(final)['source_code_files_sha256'].items()
        if n.startswith('cache-pilot-dev/')}}
    wrappers = ('agent_core.py', 'agent_policy.py', 'agent_runner.py', 'agent_worker.py',
                'ensemble_cache.py', 'model_utils.py', 'solution.py')
    # Existing compatibility tests import these source-root wrappers. They were
    # absent from the candidate's179-file focused mock inventory, so freeze the
    # same original baseline wrapper bytes explicitly for this future gate.
    for n in wrappers:
        source_files['candidate'][n] = old['source_files_sha256'][n]
    common = dict(technical['required_metadata9_sha256'], **technical['required_public10_sha256'])
    arms = {}
    archives = {'baseline': old['archive'], 'candidate': 'cache-pilot-dev/evidence/candidate-r1.zip'}
    for name, root in roots.items():
        files = source_files[name]
        for n, sha in common.items():
            files[n] = sha
        refs = {}
        for n, sha in files.items():
            # Candidate technical metadata/public fixtures are sourced from the
            # same canonical pinned files; do not mutate candidate source tree.
            source = (roots['baseline'] / n if name == 'candidate' and n in wrappers else
                      root / n if (root / n).is_file() else roots['baseline'] / n)
            require(digest(source) == sha, 'technical_source_or_fixture_changed')
            refs[n] = source.relative_to(work).as_posix()
            immutable[refs[n]] = sha
        reg = registry(root)
        require(sum(reg.values()) == (451 if name == 'baseline' else 471)
                and len(reg) == (46 if name == 'baseline' else 48), 'prospective_registry_count_changed')
        arc = path(work, archives[name])
        require(digest(arc) == ARCHIVES[name], 'archive_changed')
        immutable[archives[name]] = ARCHIVES[name]
        arms[name] = {'source_files_sha256': files, 'source_refs': refs, 'registry': reg,
            'expected_source_checks': sum(reg.values()), 'declared_registry_scripts': len(reg),
            'archive': archives[name], 'archive_sha256': ARCHIVES[name], 'compiled_sha256': archive(arc)}
    fingerprints = load(plan / 'data-fingerprints.json')
    for task in fingerprints['tasks'].values():
        for n, sha in task['expected_files_sha256'].items():
            ref = task['pristine_source'] + '/' + n
            require(digest(path(work, ref)) == sha, 'pristine_input_changed')
            immutable[ref] = sha
    anchors = load(plan / 'anchors.json')['anchors']
    for anchor in anchors:
        for field in ['source_job', 'source_split']:
            require(digest(path(work, anchor[field])) == anchor[field + '_sha256'], 'anchor_bytes_changed')
            immutable[anchor[field]] = anchor[field + '_sha256']
        job = load(path(work, anchor['source_job']))
        require(canonical(job['recipe']) == anchor['recipe_sha256'] and
                canonical({k: v for k, v in job['spec'].items() if k not in {'root', 'task_path', 'paths'}})
                == anchor['spec_nonpath_semantics_sha256'], 'anchor_semantics_changed')
        require(job.get('threads') == 2 and job.get('full_fit') is False and 'fit_iterations' not in job,
                'anchor_fit_contract_changed')
    return {'status': 'prepared_not_launched_root_review_required', 'plan_manifest_sha256': PLAN_SHA,
        'candidate_final_manifest_sha256': FINAL_SHA, 'immutable_files': immutable,
        'arms': arms, 'anchors': anchors, 'input_fingerprints': fingerprints,
        'predecessor_binding': predecessor, 'fixture_path_proof': fixture,
        'runtime_paths': runtime_paths(work, roots['candidate'], arms['candidate']['compiled_sha256']),
        'dependencies': dependencies(), 'python': str(Path(sys.executable).resolve()),
        'python_sha256': digest(sys.executable), 'output': 'k1',
        'slots': [dict(id=s, anchor=a, enabled=e, worker_cap=w, parent_cap=p,
            status='not_attempted', metrics=None, timing=None) for s, a, e, w, p in SLOTS],
        'gates': [('nofit', 300), ('baseline_source', 900), ('candidate_source', 900),
                  ('baseline_exact', 480), ('candidate_exact', 480)],
        'total_seconds': 7200, 'final_audit_seconds': 600, 'threads': 2,
        'worker_memory_bytes': int(1.5 * 2**30), 'whole_memory_bytes': 2 * 2**30,
        'API_limit': 0, 'deadline_assigned': None, 'tests_run': 0, 'fits': 0,
        'launches': 0, 'root_review_required': True, 'promotion': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work-root', type=Path, default=Path(__file__).resolve().parent)
    p.add_argument('--predecessor-binding', required=True)
    p.add_argument('--fixture-path-proof', required=True)
    p.add_argument('--packet', default='cache-pilot-launch-r1')
    p.add_argument('--write', action='store_true')
    args = p.parse_args()
    work = args.work_root.resolve()
    result = inspect(work, args.predecessor_binding, args.fixture_path_proof)
    if args.write:
        packet = path(work, args.packet)
        packet.mkdir()
        (packet / 'manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2,
            allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'packet_written': args.write,
        'source_inputs_pinned': len(result['immutable_files']), 'clock_assigned': False,
        'tests_run': 0, 'fits': 0, 'API_calls': 0, 'jobs_materialized': 0}))


if __name__ == '__main__':
    main()
