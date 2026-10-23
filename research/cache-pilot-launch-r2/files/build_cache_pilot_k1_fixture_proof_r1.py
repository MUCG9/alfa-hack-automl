"""Static AST/path proof only. Never import an application or create fixtures."""
from pathlib import Path
import ast
import hashlib
import json
import re
import sys
import tempfile

W = Path(__file__).resolve().parent
OUT = W / 'cache-pilot-k1-fixture-path-proof-r1.json'
PRIOR = W / 'fullagent-cv-supervisor-plan-r4/fixture-path-proof-r3.json'
ROOTS = {'baseline': W / 'alfa-hack-automl', 'candidate': W / 'cache-pilot-dev'}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def text(p):
    return Path(p).read_text(encoding='utf-8')


def tree(p):
    return ast.parse(text(p))


def same_ast(a, b):
    return ast.dump(tree(a), include_attributes=False) == ast.dump(tree(b), include_attributes=False)


def registry(root):
    return ast.literal_eval(next(n.value for n in tree(root / 'tools/run_checks.py').body
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'CHECKS' for t in n.targets)))


def calls(p):
    """Inventory every explicit temp, mkdir, file-writer and path-div producer.

    Writer payloads are intentionally omitted; only their destination receiver
    or destination argument is saved. Read-only paths are listed as expressions
    too, because opening an existing fixture still requires a valid path.
    """
    found = []
    temps = {'TemporaryDirectory', 'TemporaryFile', 'NamedTemporaryFile', 'mkdtemp', 'mkstemp'}
    writers = {'mkdir', 'open', 'write_bytes', 'write_text', 'to_csv', 'savez', 'savez_compressed',
               'copyfile', 'copy2', 'copytree', 'replace', 'atomic_json'}
    for n in ast.walk(tree(p)):
        if isinstance(n, ast.Call):
            name = n.func.id if isinstance(n.func, ast.Name) else n.func.attr if isinstance(n.func, ast.Attribute) else None
            if name in temps:
                found.append({'line': n.lineno, 'kind': 'temporary_constructor', 'producer': name,
                    'arguments': [ast.unparse(a) for a in n.args],
                    'keywords': {k.arg or '**': ast.unparse(k.value) for k in n.keywords}})
            elif name in writers:
                dest = ast.unparse(n.func.value) if isinstance(n.func, ast.Attribute) and name in {
                    'mkdir', 'open', 'write_bytes', 'write_text', 'replace'} else ast.unparse(n.args[0]) if n.args else None
                if name in {'copyfile', 'copy2', 'copytree'} and len(n.args) >= 2:
                    dest = ast.unparse(n.args[1])
                found.append({'line': n.lineno, 'kind': 'file_or_directory_destination', 'producer': name,
                    'destination_expression': dest})
        elif isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div):
            # All path / expressions are retained, not inferred from a suffix
            # guess. Numeric division expressions are harmless extra inventory.
            found.append({'line': n.lineno, 'kind': 'path_div_expression', 'expression': ast.unparse(n)})
    return sorted(found, key=lambda n: (n['line'], n['kind']))


def main():
    assert not OUT.exists(), 'Preserve previous proofs'
    assert sha(PRIOR) == 'beadcc3dda740a14ef6c743dfaeadcbe728cfe522f779bced801b1b7ad19518d'
    assert sha(W / 'cache_pilot_coordinator_r2.py') == '5a2237a401c1ff65029cd7ed2fb463e9e7ac4b0ede98a39bfc9ad14e3f8d769d'
    assert sha(W / 'prepare_cache_pilot_r2.py') == '63de03622908b95e4aa16d1937f0fde03a2c2aa6f06fd984c4cb7fc32fe277a0'
    prior = load(PRIOR)
    regs = {name: registry(root) for name, root in ROOTS.items()}
    assert (sum(regs['baseline'].values()), len(regs['baseline'])) == (451, 46)
    assert (sum(regs['candidate'].values()), len(regs['candidate'])) == (471, 48)
    assert set(regs['candidate']) - set(regs['baseline']) == {'test_teacher_probe.py', 'test_teacher_importance_cache.py'}
    source_sha, inventory, inherited = {}, {}, []
    def bind(p):
        source_sha[p.relative_to(W).as_posix()] = sha(p)
    bind(Path(__file__))
    for p in [PRIOR, W / 'cache_pilot_coordinator_r2.py', W / 'prepare_cache_pilot_r2.py',
              W / 'cache-pilot-dev/evidence/run_focused_mock_checks.py',
              W / 'cache-pilot-coordinator-source-handoff-r2.json',
              W / 'cache-pilot-coordinator-independent-review-r2.json',
              W / 'cache-pilot-plan-r1/technical-fixtures.json',
              W / 'cache-pilot-dev/evidence/candidate-r1.manifest.json']:
        bind(p)
    # Every inherited script is checked against the already-proven baseline
    # graph. Record exact byte differences rather than calling them identical.
    for name in regs['baseline']:
        a, b = ROOTS['baseline'] / 'tests' / name, ROOTS['candidate'] / 'tests' / name
        assert same_ast(a, b), name
        assert sha(a) == prior['source_sha256'][a.relative_to(W).as_posix()], name
        inherited.append({'script': name, 'checks': regs['baseline'][name],
            'baseline_sha256': sha(a), 'candidate_sha256': sha(b), 'AST_identical': True,
            'bytes_identical': sha(a) == sha(b), 'producer_geometry': 'inherited_verified_R4_A_graph'})
    support = ['tools/run_checks.py', 'tools/verify_release.py', 'tools/build_submission.py',
        'tests/path_fixtures.py', 'tests/error_analysis_fixture.py',
        'src/automl/search/runner.py', 'src/automl/search/multitarget.py', 'src/automl/search/hpo.py',
        'src/automl/execution/worker.py', 'src/automl/execution/feature_views.py',
        'src/automl/infrastructure/atomic.py', 'src/automl/infrastructure/run_budget.py',
        'src/automl/publishing/service.py', 'src/automl/error_analysis/preparation.py',
        'src/automl/error_analysis/reporting.py']
    extra_candidate = ['src/automl/execution/feature_engineering/teacher_probe.py',
        'src/automl/execution/feature_engineering/selection.py',
        'src/automl/execution/feature_engineering/importance_cache.py',
        'tests/fixtures/teacher_selector_default_off.py']
    for arm, root in ROOTS.items():
        selected = ['tests/' + n for n in regs[arm]] + support + (extra_candidate if arm == 'candidate' else [])
        for name in sorted(set(selected)):
            p = root / name
            bind(p)
            inventory[p.relative_to(W).as_posix()] = {'sha256': sha(p), 'producers': calls(p)}
    # Transitive inherited directory producers remain equal to baseline. Worker
    # changes are separately bounded below: sidecar is a leaf file only.
    equal_support = [n for n in support if n not in {'tools/run_checks.py', 'src/automl/execution/worker.py'}]
    for n in equal_support:
        assert same_ast(ROOTS['baseline'] / n, ROOTS['candidate'] / n), n
    worker_ast = tree(ROOTS['candidate'] / 'src/automl/execution/worker.py')
    assert "output / f'component-{index}'" in ast.unparse(worker_ast)
    assert "output_dir / 'teacher-diagnostics.json'" in ast.unparse(worker_ast)
    probe_ast = ast.unparse(tree(ROOTS['candidate'] / 'src/automl/execution/feature_engineering/teacher_probe.py'))
    assert '.mkdir(' not in probe_ast
    coordinator = ast.unparse(tree(W / 'cache_pilot_coordinator_r2.py'))
    assert "output / 'e' / name" in coordinator and "directory / 't'" in coordinator and "directory / 'm'" in coordinator
    verify = text(ROOTS['baseline'] / 'tools/verify_release.py')
    assert "prefix='modular-verify-'" in verify
    run_checks = text(ROOTS['baseline'] / 'tools/run_checks.py')
    assert "fixture_parent=ROOT.parent/'t'" in run_checks and "prefix='ck-'" in run_checks
    stdlib = tree(tempfile.__file__)
    random_cls = next(n for n in stdlib.body if isinstance(n, ast.ClassDef) and n.name == '_RandomNameSequence')
    random_k = [k.value.value for n in ast.walk(random_cls) if isinstance(n, ast.Call) for k in n.keywords
                if k.arg == 'k' and isinstance(k.value, ast.Constant)]
    assert random_k == [8]
    graphs = []
    def add(path, category, refs, reason):
        p = W / path
        graphs.append({'relative_to_work': path, 'category': category,
            'file_characters': len(str(p)), 'directory_characters': len(str(p.parent)),
            'source_references': refs, 'derivation': reason})
    # Rebase every relevant previously verified category using the ACTUAL new
    # producer roots. The old B four-leaf-only categories are absent here.
    for row in prior['producer_categories']:
        old = row['relative_to_work']
        if row['category'] == 'new_B_mock':
            continue
        if old.startswith('f4/sa/tmp/'):
            suffix = old.removeprefix('f4/sa/tmp/')
            for arm in ['baseline', 'candidate']:
                add('k1/e/' + arm + '_exact/t/' + suffix, 'exact_unpacked_smoke', row['references'],
                    'verify_release inherits coordinator environment TMPDIR=k1/e/<gate>/t; modular-verify-8 then unchanged smoke graph')
        elif old.startswith('f4/sa/'):
            for arm in ['a', 'b']:
                add('k1/' + arm + '/' + old.removeprefix('f4/sa/'), row['category'], row['references'],
                    'k1/a or k1/b deployed source ROOT; inherited producer AST is identical')
        elif old.startswith('f4/t/ck-'):
            add('k1/' + old.removeprefix('f4/'), row['category'], row['references'],
                'run_checks source ROOT.parent/t/ck-8; child TMPDIR points to ck-8; inherited tmp8 graph')
        elif old.startswith('f4/gates/a_source/'):
            for arm in ['baseline', 'candidate']:
                add('k1/g/' + arm + '_source/' + old.removeprefix('f4/gates/a_source/'), row['category'], row['references'],
                    'run_checks output root is k1/g/<arm>_source; mpl and script logs are rooted there')
        else:
            raise AssertionError('Unmapped inherited producer category ' + old)
    compiled = load(W / 'cache-pilot-dev/evidence/candidate-r1.manifest.json')['files_sha256']
    # Longer new module names affect inherited standalone-copy fixtures, even
    # though the unchanged fixture code still copies only flat compiler names.
    for n in compiled:
        add('k1/t/ck-xxxxxxxx/tmpxxxxxxxx/компиляция/' + n, 'source_compiled_copy',
            ['tests/test_error_analysis.py:365-378', 'tools/build_submission.py:build_files'],
            'Exact70 flat candidate members copied by inherited fixture; no guessed module suffix')
        add('k1/e/candidate_exact/t/modular-verify-xxxxxxxx/' + n, 'exact_compiled_copy',
            ['tools/verify_release.py:TemporaryDirectory/extractall'], 'Exact70 archive member names under actual exact gate environment')
    # Inventory all deployed file paths, including the portable original selector
    # fixture and same original compatibility wrappers closed by R2 preparation.
    a_files = load(W / 'fullagent-cv-launch-r4/manifest.json')['arms']['a']['source_files_sha256']
    b_files = {n.removeprefix('cache-pilot-dev/'): h for n, h in
        load(W / 'cache-pilot-dev/evidence/final-manifest-r2.json')['source_code_files_sha256'].items()
        if n.startswith('cache-pilot-dev/')}
    tech = load(W / 'cache-pilot-plan-r1/technical-fixtures.json')
    for n in ['agent_core.py', 'agent_policy.py', 'agent_runner.py', 'agent_worker.py', 'ensemble_cache.py', 'model_utils.py', 'solution.py']:
        b_files[n] = a_files[n]
    b_files.update(tech['required_metadata9_sha256'])
    b_files.update(tech['required_public10_sha256'])
    for arm, names in [('a', a_files), ('b', b_files)]:
        for n in names:
            add('k1/' + arm + '/' + n, 'deployed_source_fixture', ['prepare_cache_pilot_r2.py:inspect'],
                'Exact frozen source/dependency inventory copied once, before gates')
    for gate in ['nofit', 'baseline_source', 'candidate_source', 'baseline_exact', 'candidate_exact']:
        for n in ['fontlist-v390.json', 'fontlist-v390.json.matplotlib-lock']:
            add('k1/e/' + gate + '/m/' + n, 'environment_library_cache',
                ['cache_pilot_coordinator_r2.py:environment', 'R4 verified library-cache producer category'],
                'Fixed Matplotlib cache/lock in explicit per-gate MPLCONFIGDIR; source run_checks further overrides to gate output/mpl')
        for n in ['checks.log', 'results.json', 'progress.json'] if gate == 'nofit' else [s + '.log' for s in regs['candidate']]:
            add('k1/g/' + gate + '/' + n, 'gate_output', ['tools/run_checks.py:run_checks',
                'cache-pilot-dev/evidence/run_focused_mock_checks.py:main'], 'Exact registry/runner output basename')
    leaf_files = sorted({n.value for n in ast.walk(worker_ast) if isinstance(n, ast.Constant) and isinstance(n.value, str)
        and re.fullmatch(r'[A-Za-z0-9_.-]+\.(json|npz|csv)', n.value)})
    leaf_files += [n + '.tmp' for n in leaf_files if n.endswith(('.json', '.csv'))]
    # Two new mocked test files have one defaultTemporaryDirectory each. The
    # cache test writes job-0..2; probe test writes off/on. Their fixture() creates
    # five task files plus split.npz; no generated ensemble/component child exists.
    for base, category in [('k1/t/ck-xxxxxxxx/tmpxxxxxxxx', 'source_new20_mocks'),
                           ('k1/e/nofit/t/tmpxxxxxxxx', 'nofit_new20_mocks')]:
        for child in ['job-0', 'job-1', 'job-2', 'off', 'on']:
            for n in leaf_files:
                add(base + '/' + child + '/' + n, category,
                    ['tests/test_teacher_importance_cache.py:test_leaf_worker_matching_inner_refit_hits_but_outer_refit_does_not',
                     'tests/test_teacher_probe.py:test_mock_worker_probe_has_same_inner_keys_outer_miss_and_exact_csv',
                     'tests/test_feature_views.py:fixture', 'src/automl/execution/worker.py:run'],
                    'Read exact fixed child literals and leaf artifact constants; teachers/students mocked; no recursion')
        for n in ['train.csv', 'test.csv', 'sample_submission.csv', 'data_dictionary.csv', 'task.md', 'split.npz']:
            add(base + '/' + n, category, ['tests/test_feature_views.py:fixture'], 'Exact synthetic fixture filenames')
    add('cache-pilot-dev/tests/fixtures/teacher_selector_default_off.py', 'nofit_readonly_portable_fixture',
        ['tests/test_teacher_probe.py:41'], 'Original nofit20 runner imports candidate tests directly; exact own-root read-only fixture path')
    violations = [r for r in graphs if r['file_characters'] > 259 or r['directory_characters'] > 247]
    assert not violations, violations[:1]
    # Recheck every inventoried source before saving the append-only proof.
    assert all(sha(W / n) == h for n, h in source_sha.items())
    proof = {'status': 'static_fixture_path_coverage_pass', 'output_root': 'k1',
        'output_root_absolute_characters': len(str(W / 'k1')),
        'maximum_file_characters': max(r['file_characters'] for r in graphs),
        'maximum_directory_characters': max(r['directory_characters'] for r in graphs),
        'largest_file_graph': max(graphs, key=lambda r: r['file_characters']),
        'largest_directory_graph': max(graphs, key=lambda r: r['directory_characters']),
        'source_sha256': source_sha, 'per_source_producer_inventory': inventory,
        'concrete_path_graphs': graphs, 'violations': [],
        'coverage': {'baseline': {'expected_checks': 451, 'scripts': 46},
            'candidate': {'expected_checks': 471, 'scripts': 48}, 'fresh_nofit': {'expected_checks': 20, 'scripts': 2},
            'exact_unpacked': {'repeated_checks_each': 23, 'scripts_each': ['test_v2.py', 'test_resilience.py', 'smoke.py']},
            'all46_inherited_AST_identical': True, 'inherited_scripts': inherited,
            'same_AST_transitive_directory_producers': equal_support,
            'new_module_archive_members': 70, 'new_probe_directory_producers': 0,
            'new20_default_temporary_roots': ['k1/t/ck-xxxxxxxx/tmpxxxxxxxx', 'k1/e/nofit/t/tmpxxxxxxxx'],
            'candidate_source_inventory_addition': 'Seven exact original compatibility wrappers plus mandatory metadata9/public10; no source/model/test edits'},
        'root_graphs': {'source': 'k1/a or k1/b; source run_checks reserves k1/t/ck-8 then unittest tmp8',
            'exact': 'k1/e/{baseline_exact,candidate_exact}/t/modular-verify-8; test-v2/resilience default tmp8 remains a sibling under that gate TMPDIR',
            'nofit': 'k1/e/nofit/t/tmp8, runner uses original cache-pilot-dev source tests and own-root portable read-only fixture',
            'gate_output': 'k1/g/{nofit,baseline_source,candidate_source,baseline_exact,candidate_exact}',
            'calibration_cache': 'Same worker process; no directory producers; teacher-diagnostics.json and .json.tmp are leaf files only'},
        'revision_lineage': {'parent_path': PRIOR.relative_to(W).as_posix(), 'parent_sha256': sha(PRIOR),
            'reuse_boundary': 'Only verified A451 producer categories reused after every inherited test AST/hash comparison. R4 B four-leaf-only categories excluded. Actual new coordinator environment prefixes rebased explicitly.'},
        'tempfile': {'stdlib_source_sha256': sha(tempfile.__file__), 'random_suffix_characters_from_AST': 8,
            'declared_time_ns_bound_decimal_digits': 20, 'basis': 'Same conservative2026 bound in verified R4 proof; no arbitrary user run names.'},
        'limits': {'file_characters': 259, 'directory_characters': 247},
        'scope': 'Static source-derived fixture/default-import geometry for declared source/nofit/exact-unpacked commands, not actual filesystem execution or arbitrary third-party I/O.',
        'assumptions': ['Actual work root length92; recalculate/refuse for any longer relocation.',
            'Source smoke/multitarget CLI fixes max-experiments1; no full search/ensemble depth is composed under the deepest smoke/multitarget paths.',
            'PYTHONDONTWRITEBYTECODE1 and explicit-B for isolated children prevent pycache path materialization.',
            'New mock tests import worker in process and create only fixed job-0..2/off/on leaf directories; cache/probe stores no disk data.',
            'Atomic JSON.tmp and CSV.tmp covered at leaf producers; direct NPZ writers do not invent .npz.tmp.',
            'Undocumented optional third-party files outside these frozen source producers are outside this static claim.'],
        'tests_run': 0, 'gates_run': 0, 'fits': 0, 'API_calls': 0, 'new_children': 0,
        'application_imports': 0, 'fixture_directories_created': 0, 'jobs_materialized': 0,
        'input_copies': 0, 'deadline_assigned': None, 'promotion': False}
    with OUT.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(proof, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'status': proof['status'], 'proof_sha256': sha(OUT),
        'source_files': len(source_sha), 'producer_inventory_files': len(inventory),
        'concrete_graphs': len(graphs), 'maximum_file_characters': proof['maximum_file_characters'],
        'maximum_directory_characters': proof['maximum_directory_characters'], 'tests_run': 0, 'fits': 0}))


if __name__ == '__main__':
    main()
