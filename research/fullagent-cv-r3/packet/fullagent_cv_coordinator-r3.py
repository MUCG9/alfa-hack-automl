"""Prepare only by default; explicitly reviewed Stage0/Stage1 launches only.

External research supervisor. No alternative ML runner, Stage2 or promotion.
Source/data/clock/ownership omissions fail closed. No command runs at import.
"""
from pathlib import Path
import argparse
import ast
import hashlib
import importlib.util
import importlib.metadata
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import zipfile

sys.dont_write_bytecode = True
CONTROL_SHA = '88dac47a9a815b98b5d00c44e5650518f84db5197c9eac56b79fb1ce465c92a0'
FOLD_MANIFEST_SHA = 'f8a0b9ad5b3e9e403aa9a567234ba203c8537c19eee78dd6257d9d8259bb4910'
FOLD_BUNDLE_SHA = '9883c8fe781be541dbbeefe831ea73a3b939628aea09a470e155ee1e1fac1224'
R3_SHA = '5b2164c3721c84b8e6eb85c0dec7571474316b2e956d6ecdeee235d0193addcb'
OWNER_SHA = '8e9e3abe72c19029a0342cb1b169bc0299f167bab983d8a5bc0b3a17f65fedf8'
AWAKE_SHA = '8d4bd4212867787552b7785e8ec6d33a8025ca315f018c1d2d4c39616982d27a'
GATE_INPUTS_SHA = '7c25b6640954acb39c60cddbb76a949d7ad3dab4c547b205ae1f3c212da7f377'
TASK_FILES = ('task.md', 'train.csv', 'test.csv', 'sample_submission.csv', 'data_dictionary.csv')
SLOTS = ((0, 'a'), (0, 'b'), (1, 'b'), (1, 'a'), (2, 'a'), (2, 'b'))
LIMITS = {'stage0': 3600, 'stage1': 64800, 'parent': 10200,
          'solver': 9900, 'arm_audit': 120, 'final_audit': 1200}


class IntegrityError(RuntimeError):
    pass


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            value.update(block)
    return value.hexdigest()


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def write(path, obj, exclusive=False):
    content = (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    if exclusive:
        with Path(path).open('xb') as stream:
            stream.write(content)
    else:
        pending = Path(path).with_name(Path(path).name + '.pending')
        pending.write_bytes(content)
        os.replace(pending, path)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def configure(path, packet):
    global WORK, REPO, PACKET, OUTPUT, FOLDS
    WORK = Path(path).expanduser().resolve()
    REPO = WORK / 'alfa-hack-automl'
    PACKET = resolve(packet)
    OUTPUT = WORK / 'f3'
    FOLDS = WORK / 'fullagent-cv-stage1-plan-r1'
    if not (REPO / 'src/automl').is_dir():
        raise ValueError('Use --work-root pointing to task work')


def resolve(name):
    path = (WORK / name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to(WORK):
        raise IntegrityError('Manifest reference escapes task work')
    return path


def relative(path):
    return Path(path).resolve().relative_to(WORK).as_posix()


def safe_child(root, name):
    value = Path(name)
    target = (root / value).resolve()
    if value.is_absolute() or not target.is_relative_to(root.resolve()) or '..' in value.parts:
        raise IntegrityError('Unsafe source/archive member')
    return target


def hashed_files(root, folders=None):
    paths = root.rglob('*') if folders is None else (
        p for folder in folders for p in (root / folder).rglob('*'))
    return {p.relative_to(root).as_posix(): digest(p) for p in sorted(paths) if p.is_file()}


def registry(source):
    tree = ast.parse((source / 'tools/run_checks.py').read_text(encoding='utf-8'))
    values = [ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == 'CHECKS' for t in n.targets)]
    if len(values) != 1 or not values[0] or any(type(v) is not int or v <= 0 for v in values[0].values()):
        raise IntegrityError('Expected one positive frozen check registry')
    return values[0]


def archive_files(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise IntegrityError('Duplicate flat archive entries')
        if any(Path(n).name != n or not n.endswith(('.py', '.txt')) for n in names):
            raise IntegrityError('Archive must contain flat code/requirements only')
        files = {n: archive.read(n) for n in names}
    if 'solution.py' not in files or 'requirements.txt' not in files:
        raise IntegrityError('Incomplete flat runtime')
    return files


def dependency_inventory():
    result = {}
    for name in ['numpy', 'pandas', 'scipy', 'joblib', 'scikit-learn', 'lightgbm', 'catboost',
                 'xgboost', 'optuna', 'psutil', 'threadpoolctl']:
        distribution = importlib.metadata.distribution(name)
        records = {Path(p).name: digest(distribution.locate_file(p))
                   for p in distribution.files or []
                   if Path(p).name in {'METADATA', 'RECORD'}}
        if set(records) != {'METADATA', 'RECORD'}:
            raise IntegrityError('Missing dependency distribution inventory: ' + name)
        result[name] = {'version': distribution.version, 'distribution_metadata_sha256': records}
    return result


def clocks(deadline, unix):
    if abs((deadline - time.monotonic()) - (unix - time.time())) > 5:
        raise IntegrityError('Absolute and monotonic stage clocks disagree')
    if time.monotonic() >= deadline:
        raise TimeoutError('Original stage deadline exhausted')


def paths_audit(arms):
    """Finite source-derived producer graph; gate-fixture proof is separate."""
    def function(path, name):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    def render(node, values):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            parts = []
            for item in node.values:
                if isinstance(item, ast.Constant):
                    parts.append(item.value)
                elif isinstance(item, ast.FormattedValue) and isinstance(item.value, ast.Name) and item.value.id in values:
                    spec = render(item.format_spec, values) if item.format_spec else ''
                    parts.append(format(values[item.value.id], spec))
                elif (isinstance(item, ast.FormattedValue) and isinstance(item.value, ast.Call)
                      and isinstance(item.value.func, ast.Name) and item.value.func.id == 'len'
                      and len(item.value.args) == 1 and isinstance(item.value.args[0], ast.Name)):
                    # len(list) is bounded by Py_ssize_t, not a guessed trial count.
                    parts.append(str(sys.maxsize))
                else:
                    raise IntegrityError('Unbounded runtime path expression')
            return ''.join(parts)
        raise IntegrityError('Unmapped runtime directory producer')
    coverage, paths = {}, []
    random_names = next(n for n in ast.parse(Path(tempfile.__file__).read_text(encoding='utf-8')).body
                        if isinstance(n, ast.ClassDef) and n.name == '_RandomNameSequence')
    entropy = [k.value.value for n in ast.walk(random_names) if isinstance(n, ast.Call)
               for k in n.keywords if k.arg == 'k' and isinstance(k.value, ast.Constant)]
    if entropy != [8]:
        raise IntegrityError('CPython tempfile suffix bound changed')
    for arm, declared in arms.items():
        source = resolve(declared['source_root'])
        runner = source / 'src/automl/search/runner.py'
        worker = source / 'src/automl/execution/worker.py'
        views = source / 'src/automl/execution/feature_views.py'
        caches = source / 'src/automl/execution/ensembles.py'
        publishing = source / 'src/automl/publishing/service.py'
        atomic = source / 'src/automl/infrastructure/atomic.py'
        run_budget = source / 'src/automl/infrastructure/run_budget.py'
        solve = function(runner, 'solve_single')
        main = function(runner, '_main')
        run_name = next(k.value.value for node in ast.walk(main)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == 'add_argument' and node.args and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == '--run-name' for k in node.keywords if k.arg == 'default')
        require_run_name = run_name == 'run-v2'
        if not require_run_name:
            raise IntegrityError('Default run directory changed')
        roots, cached = set(), set()
        for node in ast.walk(solve):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            position = 2 if node.func.id == 'run_worker' else 3 if node.func.id == 'materialize' else None
            if position is None:
                continue
            expr = node.args[position]
            if not (isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Div)
                    and isinstance(expr.left, ast.Name) and expr.left.id == 'runs'):
                raise IntegrityError('Runtime output root has an unreviewed producer')
            destination = roots if node.func.id == 'run_worker' else cached
            for iteration in range(12):
                for index in range(3):
                    destination.add(render(expr.right, {'iteration': iteration, 'index': index}))
        ensemble = function(worker, 'run_ensemble')
        normalized = ast.unparse(ensemble)
        if "c.get('engine') == 'ensemble'" not in normalized or '2 <= len(components) <= 3' not in normalized:
            raise IntegrityError('Ordinary global ensemble depth/width guard changed')
        factory = function(views, 'feature_view_components')
        width = max(len(n.value.elts) for n in ast.walk(factory)
                    if isinstance(n, ast.Return) and isinstance(n.value, ast.List))
        if width not in (2, 4):
            raise IntegrityError('Feature-view maximum width changed')
        component = next(n.right for n in ast.walk(ensemble)
            if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)
            and isinstance(n.left, ast.Name) and n.left.id == 'output' and isinstance(n.right, ast.JoinedStr))
        parts = [render(component, {'index': i}) for i in range(width)]
        # A global parent can contain a feature-view child, whose leaves remove
        # feature_views and cannot be explicit global ensembles: maximum depth2.
        nodes = [Path('')] + [Path(render(component, {'index': i})) for i in range(max(width, 3))]
        nodes += [Path(render(component, {'index': i})) / child for i in range(3) for child in parts]
        producer_files, dynamic_bounds = set(), []
        for path in [runner, worker, caches, publishing, atomic, run_budget]:
            for item in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(item, ast.Constant) and isinstance(item.value, str):
                    name = item.value
                    if Path(name).name == name and not name.startswith('.') and name.endswith(('.csv', '.json', '.npz', '.tsv', '.txt')):
                        producer_files.add(name)
                if (isinstance(item, ast.JoinedStr) and item.values and isinstance(item.values[-1], ast.Constant)
                        and isinstance(item.values[-1].value, str)
                        and item.values[-1].value.endswith(('.csv', '.json', '.npz', '.tsv', '.txt'))):
                    bound = render(item, {})
                    producer_files.add(bound)
                    dynamic_bounds.append({'source_expression': ast.unparse(item),
                        'maximum_filename_bound': bound, 'integer_bound': sys.maxsize,
                        'proof': 'Nonnegative Python container length cannot exceed Py_ssize_t/sys.maxsize on the frozen interpreter'})
        if not {'validation_probabilities.npz', 'test_probabilities.npz', 'result.json', 'submission.csv'} <= producer_files:
            raise IntegrityError('Mandatory producer basename inventory changed')
        if "'.tmp'" not in atomic.read_text(encoding='utf-8') or "'.csv.tmp'" not in publishing.read_text(encoding='utf-8'):
            raise IntegrityError('Atomic suffix producer changed')
        names = sorted(producer_files | {p + '.tmp' for p in producer_files if p.endswith('.json')}
                       | {p[:-4] + '.csv.tmp' for p in producer_files if p.endswith('.csv')})
        for slot in [str(f) + a for f, a in SLOTS if a == arm]:
            base = OUTPUT / slot
            for root in roots:
                for node in nodes:
                    for name in names:
                        paths.append(base / 'automl_runs' / run_name / root / node / name)
            for root in cached:
                paths.extend(base / 'automl_runs' / run_name / root / name for name in names)
            paths.extend(base / 'automl_runs' / run_name / name for name in names)
            paths.extend(base / name for name in declared['compiled_sha256'])
            # CPython frozen interpreter's random tempfile suffix has8 characters.
            # RunBudget uses mkdtemp(prefix='run-budget-',dir='automl_runs').
            text = run_budget.read_text(encoding='utf-8')
            if "prefix='run-budget-'" not in text:
                raise IntegrityError('RunBudget directory producer changed')
            paths.extend(base / 'automl_runs' / ('run-budget-' + 'x' * 8) / name
                         for name in ['report.json', 'report.json.tmp'])
        coverage[arm] = {'source_sha256': {relative(p): digest(p) for p in [runner, worker, views, caches, publishing, atomic, run_budget]},
            'run_name_default_from_parser': run_name, 'worker_output_roots_from_calls': sorted(roots),
            'cache_materialization_roots_from_calls': sorted(cached), 'producer_basenames': names,
            'dynamic_basename_bounds': dynamic_bounds,
            'ordinary_global_maximum_children': 3, 'feature_view_maximum_children': width,
            'maximum_component_directory_depth': 2,
            'calibration_directory_depth': 0,
            'calibration_scope_proof': 'Existing worker.run calibration/inner fitting calls fit_on_rows in process and writes only final leaf output; no calibration path/mkdir producer exists.',
            'cache_scope_proof': 'ensembles.read_cache reads existing worker artifacts; materialize writes only the two source-derived named blend roots.',
            'fresh_run_directory_invariant': 'Five-file+flat allowlist and unique once-only arm directory exclude run-name collision/time_ns suffix; HPO0 and single target exclude inner-hpo/multitarget runtime branches.',
            'pycache_not_written': 'clean_env forces PYTHONDONTWRITEBYTECODE=1, passes no PYTHONPYCACHEPREFIX/PYTHONOPTIMIZE; source gates preserve this env.',
            'overapproximation': 'All source-derived basenames at every allowed component node; includes impossible combinations conservatively.'}
    fixture = WORK / 'fullagent-cv-supervisor-plan-r1/fixture-path-proof-r2.json'
    if not fixture.is_file():
        raise IntegrityError('Independent source/exact-unpacked fixture path proof pending')
    fixture_data = load(fixture)
    if fixture_data.get('status') != 'static_fixture_path_coverage_pass':
        raise IntegrityError('Fixture path proof is incomplete')
    if fixture_data.get('output_root') != relative(OUTPUT) or fixture_data.get('output_root_absolute_characters') != len(str(OUTPUT)):
        raise IntegrityError('Fixture path proof belongs to another output prefix')
    for name, expected in fixture_data['source_sha256'].items():
        if digest(resolve(name)) != expected:
            raise IntegrityError('Fixture source/harness proof is stale')
    if fixture_data['maximum_file_characters'] > 259 or fixture_data['maximum_directory_characters'] > 247:
        raise IntegrityError('Derived Windows fixture path exceeds MAX_PATH')
    # These paths are constructed from the owned absolute prefix + validated
    # source AST parts; lexical relative_to avoids 43k unnecessary FS resolutions.
    rows = [{'path': p.relative_to(WORK).as_posix(), 'file_characters': len(str(p)),
             'directory_characters': len(str(p.parent))} for p in paths]
    violations = [r for r in rows if r['file_characters'] > 259 or r['directory_characters'] > 247]
    if violations:
        raise IntegrityError('Derived Windows runtime path exceeds MAX_PATH')
    return {'status': 'derived_runtime_and_separately_bound_fixture_path_proof',
        'runtime': coverage, 'runtime_paths_enumerated': len(rows),
        'runtime_maximum_file': max(rows, key=lambda r: r['file_characters']),
        'runtime_maximum_directory': max(rows, key=lambda r: r['directory_characters']),
        'fixtures': {'path': relative(fixture), 'sha256': digest(fixture), 'proof': fixture_data},
        'tempfile_random_suffix_characters_from_stdlib_AST': entropy[0],
        'stdlib_tempfile_sha256': digest(tempfile.__file__),
        'limits': {'file': 259, 'directory': 247}, 'violations': []}



def prepare(binding_path):
    """Root supplies a prospective source/publication binding; no child launch."""
    if PACKET.exists():
        raise FileExistsError('Preserve old packet; select a new explicit revision')
    binding = load(binding_path)
    missing = [name for name in ['source_publication_receipt', 'source_publication_receipt_sha256',
        'coordinator_publication_receipt', 'coordinator_publication_receipt_sha256',
        'independent_verifier_path', 'independent_verifier_sha256'] if not binding.get(name)]
    if any(not value for value in binding.get('tm1_completion', {}).get('sha256', {}).values()):
        missing.append('actual terminal tm1 receipt/campaign hashes')
    if missing:
        raise IntegrityError('Preparation blocked on missing root bindings: ' + ', '.join(missing))
    if binding.get('root_approved_source_factor') != 'A_exact88dac_B_backend_plus_default_lastslot_only':
        raise IntegrityError('Actual source factor has not been root-bound')
    if binding.get('root_approved_r3') is not True:
        raise IntegrityError('Formal r3 root approval/publication remains missing')
    if digest(resolve(binding['r3_protocol'])) != R3_SHA:
        raise IntegrityError('Approved r3 differs')
    publication = resolve(binding['publication_receipt'])
    if digest(publication) != binding['publication_receipt_sha256']:
        raise IntegrityError('Publication receipt changed')
    published = load(publication)
    if (published.get('root_protocol_reviewed') is not True or published.get('remote_sha_verified') is not True
            or published.get('protocol_sha256') != R3_SHA or published.get('launch_authorized') is not False):
        raise IntegrityError('Receipt does not prove reviewed published prospective r3')
    if digest(FOLDS / 'manifest.json') != FOLD_MANIFEST_SHA or digest(FOLDS / 'frozen-files.json') != FOLD_BUNDLE_SHA:
        raise IntegrityError('Frozen outer assignments changed')
    fold_receipt = load(FOLDS / 'frozen-files.json')
    immutable = {relative(FOLDS / n): v for n, v in fold_receipt['files_sha256'].items()}
    immutable.update({relative(FOLDS / 'frozen-files.json'): FOLD_BUNDLE_SHA,
                      relative(resolve(binding['r3_protocol'])): R3_SHA,
                      relative(publication): binding['publication_receipt_sha256']})
    immutable.update(load(FOLDS / 'manifest.json')['pristine_input_sha256'])
    fold_r3 = resolve(binding['fold_r3_binding'])
    if digest(fold_r3) != binding['fold_r3_binding_sha256']:
        raise IntegrityError('Root r3 input binding changed')
    bound_folds = load(fold_r3)
    if (bound_folds.get('r3_protocol_sha256') != R3_SHA or bound_folds.get('input_manifest_sha256') != FOLD_MANIFEST_SHA
            or bound_folds.get('frozen_files_sha256') != FOLD_BUNDLE_SHA
            or bound_folds.get('folds_and_gates_unchanged') is not True
            or bound_folds.get('within_fold_order') != 'AB/BA/AB'):
        raise IntegrityError('Root r3 binding does not preserve exact frozen folds/gates/order')
    immutable[relative(fold_r3)] = digest(fold_r3)
    author_manifest = resolve(binding['integration_author_manifest'])
    if digest(author_manifest) != binding['integration_author_manifest_sha256']:
        raise IntegrityError('Integration author source/contract manifest differs')
    immutable[relative(author_manifest)] = digest(author_manifest)
    gate_inputs = WORK / 'four-leaf-default-plan-r1/public-input-staging-r1.json'
    if digest(gate_inputs) != GATE_INPUTS_SHA:
        raise IntegrityError('Ten gate-only pristine fixture receipt differs')
    fixtures = {}
    for row in load(gate_inputs)['files']:
        parts = Path(row['source']).parts
        name = Path(*parts[parts.index('public_tasks'):]).as_posix()
        fixtures[name] = row['sha256']
    if len(fixtures) != 10:
        raise IntegrityError('Exactly ten gate-only public fixtures are required')
    immutable[relative(gate_inputs)] = GATE_INPUTS_SHA
    arms = {}
    for arm in ['a', 'b']:
        item = binding['arms'][arm]
        archive = resolve(item['archive'])
        if digest(archive) != item['archive_sha256'] or arm == 'a' and digest(archive) != CONTROL_SHA:
            raise IntegrityError('Actual A/B archive identity differs')
        source = resolve(item['source_root'])
        code = item['source_files_sha256']
        if {n: code.get(n) for n in fixtures} != fixtures:
            raise IntegrityError('Missing gate-only public inputs in actual A/B deployment inventory')
        required = ['requirements.txt', 'solution.py', 'tools/build_submission.py',
                    'tools/run_checks.py', 'tools/verify_release.py', 'tools/module_map.json']
        if any(n not in code for n in required):
            raise IntegrityError('Incomplete A/B source harness inventory')
        actual_python = sorted(p.relative_to(source).as_posix()
            for folder in ['src', 'tools', 'tests'] for p in (source / folder).rglob('*.py'))
        if actual_python != sorted(n for n in code if n.endswith('.py') and n.split('/')[0] in {'src', 'tools', 'tests'}):
            raise IntegrityError('Unbound source Python file')
        for name, expected in code.items():
            if digest(safe_child(source, name)) != expected:
                raise IntegrityError('A/B frozen source differs')
            immutable[relative(source / name)] = expected
        checks = registry(source)
        if item['expected_source_checks'] != sum(checks.values()):
            raise IntegrityError('Expected source registry count differs')
        # AST compiler only; no learner or test module is imported/executed.
        builder = module('_cv_ast_builder_' + arm, source / 'tools/build_submission.py')
        built = builder.build_files()
        packed = archive_files(archive)
        if built != packed:
            raise IntegrityError('Source build and frozen archive differ')
        immutable[relative(archive)] = digest(archive)
        arms[arm] = dict(item, registry=checks,
            compiled_sha256={n: hashlib.sha256(b).hexdigest() for n, b in packed.items()})
    source_publication = resolve(binding['source_publication_receipt'])
    if digest(source_publication) != binding['source_publication_receipt_sha256']:
        raise IntegrityError('Source publication receipt differs')
    published_source = load(source_publication)
    if (published_source.get('root_source_reviewed') is not True or published_source.get('remote_sha_verified') is not True
            or published_source.get('archive_sha256') != {a: item['archive_sha256'] for a, item in arms.items()}):
        raise IntegrityError('Exact A/B source publication is missing')
    immutable[relative(source_publication)] = digest(source_publication)
    coordinator_publication = resolve(binding['coordinator_publication_receipt'])
    if digest(coordinator_publication) != binding['coordinator_publication_receipt_sha256']:
        raise IntegrityError('Coordinator publication receipt differs')
    published_coordinator = load(coordinator_publication)
    if (published_coordinator.get('root_source_reviewed') is not True or published_coordinator.get('remote_sha_verified') is not True
            or published_coordinator.get('coordinator_source_sha256') != digest(__file__)
            or published_coordinator.get('independent_verifier_sha256') != binding['independent_verifier_sha256']):
        raise IntegrityError('Exact coordinator/verifier source publication is missing')
    immutable[relative(coordinator_publication)] = digest(coordinator_publication)
    lib_sources = {'ownership.py': WORK / 'support_component_coordinator.py',
                   'awake.py': WORK / 'hpo_campaign_coordinator.py',
                   'processes.py': REPO / 'src/automl/infrastructure/processes.py',
                   'research_lock.py': REPO / 'tools/research_lock.py',
                   'verification.py': WORK / 'fullagent-cv-supervisor-plan-r1/verification.py',
                   'independent_verifier.py': resolve(binding['independent_verifier_path'])}
    if digest(lib_sources['ownership.py']) != OWNER_SHA or digest(lib_sources['awake.py']) != AWAKE_SHA:
        raise IntegrityError('Reviewed ownership/awake library changed')
    for name, path in lib_sources.items():
        expected = (binding['independent_verifier_sha256'] if name == 'independent_verifier.py'
                    else binding['supervisor_library_sha256'][name])
        if digest(path) != expected:
            raise IntegrityError('Supervisor library not explicitly frozen')
    fixture_proof = WORK / 'fullagent-cv-supervisor-plan-r1/fixture-path-proof-r2.json'
    immutable[relative(fixture_proof)] = digest(fixture_proof)
    predecessor = binding['tm1_completion']
    for name in [predecessor['receipt'], predecessor['campaign']]:
        expected = predecessor['sha256'][name]
        if digest(resolve(name)) != expected:
            raise IntegrityError('Actual tm1 terminal proof differs')
        immutable[name] = expected
    PACKET.mkdir()
    for name, path in lib_sources.items():
        shutil.copyfile(path, PACKET / name)
        immutable[relative(PACKET / name)] = digest(PACKET / name)
    shutil.copyfile(binding_path, PACKET / 'source-binding.json')
    immutable[relative(PACKET / 'source-binding.json')] = digest(PACKET / 'source-binding.json')
    manifest = {'status': 'prepared_not_launched', 'coordinator_sha256': digest(__file__),
        'source_binding_sha256': digest(binding_path), 'immutable_files': immutable,
        'arms': arms, 'tm1_completion': predecessor,
        'limits': LIMITS, 'r3_sha256': R3_SHA, 'outer_manifest_sha256': FOLD_MANIFEST_SHA,
        'slots': [{'fold': f, 'arm': a, 'directory': str(f) + a} for f, a in SLOTS],
        'windows_paths': paths_audit(arms), 'python': relative(Path(sys.executable)),
        'python_sha256': digest(sys.executable),
        'stdlib_tempfile_sha256': digest(tempfile.__file__),
        'dependency_inventory': dependency_inventory(),
        'solver_cli': ['-u', 'solution.py', 'task.md', '--offline', '--max-llm-calls', '0'],
        'stage0_gate_order': ['a_source', 'b_source', 'a_exact', 'b_exact'],
        'stage0_caps': {'a_source': 900, 'b_source': 900, 'a_exact': 480, 'b_exact': 480},
        'stage0_mock_allowance': 300, 'stage0_overhead_reserve': 540,
        'stage1_initial_margin': 2400, 'stage1_final_audit_reserve': 1200,
        'API_limit': 0, 'private_environment_forwarded': False,
        'independent_verifier_sha256': binding['independent_verifier_sha256'],
        'independently_closed_private_API_ledger_claimed': False,
        'deadline_assigned': False, 'new_children': 0, 'fits': 0, 'api_calls': 0,
        'root_review_required': True, 'promotion': False}
    write(PACKET / 'manifest.json', manifest, exclusive=True)
    guard(manifest)
    print(json.dumps({'status': manifest['status'], 'manifest_sha256': digest(PACKET / 'manifest.json'),
                      'new_children': 0, 'deadline_assigned': False}))


def guard(manifest):
    if digest(__file__) != manifest['coordinator_sha256'] or digest(sys.executable) != manifest['python_sha256']:
        raise IntegrityError('Executing reviewed supervisor/interpreter bytes differ')
    if dependency_inventory() != manifest['dependency_inventory']:
        raise IntegrityError('Dependency versions/distribution metadata changed')
    if digest(tempfile.__file__) != manifest['stdlib_tempfile_sha256']:
        raise IntegrityError('CPython tempfile name/bounds source changed')
    for name, expected in manifest['immutable_files'].items():
        if digest(resolve(name)) != expected:
            raise IntegrityError('Frozen source/input/library/publication differs: ' + name)
    for arm in manifest['arms'].values():
        source = resolve(arm['source_root'])
        actual = sorted(p.relative_to(source).as_posix()
            for folder in ['src', 'tools', 'tests'] for p in (source / folder).rglob('*.py'))
        expected = sorted(n for n in arm['source_files_sha256']
            if n.endswith('.py') and n.split('/')[0] in {'src', 'tools', 'tests'})
        if actual != expected:
            raise IntegrityError('Source Python inventory changed')


def identities(value):
    found = set()
    if isinstance(value, dict):
        if 'pid' in value and 'create_time' in value:
            pid, created = value['pid'], value['create_time']
            if type(pid) is not int or pid <= 0 or isinstance(created, bool) or not isinstance(created, (int, float)) or not math.isfinite(created) or created <= 0:
                raise IntegrityError('Unverified predecessor process identity')
            found.add((pid, float(created)))
        for child in value.values():
            found.update(identities(child))
    elif isinstance(value, list):
        for child in value:
            found.update(identities(child))
    return found


def predecessor_check(manifest, owner):
    import psutil
    binding = manifest['tm1_completion']
    proof, campaign = load(resolve(binding['receipt'])), load(resolve(binding['campaign']))
    if (proof.get('cleanup_confirmed') is not True or proof.get('active_owned_processes') != []
            or not proof.get('launcher_identities') or not proof.get('tracked_identities')
            or proof.get('campaign_receipt_sha256') != digest(resolve(binding['campaign']))):
        raise IntegrityError('tm1 terminal launcher/descendant completion proof incomplete')
    if (campaign.get('status', '').startswith('running') or campaign.get('cleanup_confirmed') is not True
            or campaign.get('source_unchanged') is not True):
        raise IntegrityError('tm1 active or source/cleanup unconfirmed')
    roots = identities(proof) | identities(campaign)
    mandatory = {(8148, 1792724976.640077), (1488, 1792724976.6293917), (24548, 1792724980.8335724)}
    if not mandatory <= roots or not identities(proof['launcher_identities']) <= identities(proof['tracked_identities']):
        raise IntegrityError('Known tm1 root/bootstrap/solver or launcher tracking missing')
    observer = owner.StrictOwnedObserver()
    observer.remember(roots)
    live = observer.observe()
    # Read-only orphan discovery; never signal predecessors or reused PIDs.
    entries = list(psutil.process_iter(['pid', 'ppid', 'create_time', 'status']))
    changed = True
    while changed:
        changed = False
        for process in entries:
            info = process.info
            if info['status'] in {psutil.STATUS_DEAD, psutil.STATUS_ZOMBIE}:
                continue
            for pid, created in tuple(observer.seen):
                if info['ppid'] != pid:
                    continue
                if info['create_time'] is None:
                    observer.denied(info['pid'], None, 'predecessor_orphan_identity', 'AccessDenied')
                    continue
                if info['create_time'] < created or (info['pid'], info['create_time']) in observer.seen:
                    continue
                try:
                    actual_parent = psutil.Process(pid).create_time()
                    if actual_parent != created and info['create_time'] >= actual_parent:
                        continue
                except psutil.NoSuchProcess:
                    pass
                except psutil.AccessDenied:
                    observer.denied(pid, created, 'predecessor_orphan_parent', 'AccessDenied')
                    continue
                observer.remember([(info['pid'], info['create_time'])])
                changed = True
    live = observer.observe()
    if observer.denials or live:
        raise IntegrityError('Owned predecessor/descendant live or observation denied')
    return {'active': [], 'cleanup_confirmed': True, 'no_predecessor_signalled': True,
            'receipt_sha256': digest(resolve(binding['receipt'])),
            'tracked': [{'pid': p, 'create_time': c} for p, c in sorted(observer.seen)]}


def clean_env(directory, threads):
    allowed = {'PATH', 'SystemRoot', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'ComSpec',
               'PATHEXT', 'PROCESSOR_ARCHITECTURE', 'NUMBER_OF_PROCESSORS'}
    env = {k: v for k, v in os.environ.items() if k in allowed}
    for name in ['tmp', 'mpl']:
        (directory / name).mkdir(exist_ok=True)
    env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1',
               AUTOML_THREADS=str(threads), TMPDIR=str(directory / 'tmp'),
               TMP=str(directory / 'tmp'), TEMP=str(directory / 'tmp'),
               MPLCONFIGDIR=str(directory / 'mpl'))
    for key in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
        env[key] = str(threads)
    return env


def supervise(command, cwd, receipt, process_deadline, deadline, unix, manifest, owner,
              processes, save_stage, stage1=False, admission_reserve=0):
    import psutil
    tick = time.monotonic()
    observer = owner.StrictOwnedObserver()
    child = tree = None
    verified = False
    result = {'status': 'starting', 'cleanup_confirmed': False, 'start_unix': time.time(),
              'start_monotonic': tick, 'owned_process_identities': [], 'observed_workers': [],
              'maximum_logical_worker_jobs': 0, 'peak_owned_tree_rss_mib': 0., 'API_limit': 0}
    write(receipt, result, exclusive=True)
    last_guard = last_heartbeat = tick
    try:
        clocks(deadline, unix)
        guard(manifest)
        if process_deadline <= time.monotonic() or stage1 and process_deadline - time.monotonic() < LIMITS['solver']:
            raise TimeoutError('Prelaunch I/O consumed protected full allocation')
        env = clean_env(cwd, 2 if stage1 else 1)
        if deadline - time.monotonic() < admission_reserve:
            raise TimeoutError('Prelaunch setup consumed remaining full-stage admission reserve')
        with receipt.with_suffix('.log').open('x', encoding='utf-8') as log:
            clocks(deadline, unix)
            if (deadline - time.monotonic() < admission_reserve or
                    stage1 and process_deadline - time.monotonic() < LIMITS['solver']):
                raise TimeoutError('Final pre-Popen setup consumed full declared allocation')
            child = subprocess.Popen(command, cwd=cwd, env=env,
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            root = psutil.Process(child.pid)
            identity = root.pid, root.create_time()
            observer.remember([identity])
            result['owned_root'] = {'pid': identity[0], 'create_time': identity[1]}
            tree = processes.ProcessTree(child)
            observer.remember(tree.members)
            verified = identity in tree.members
            if not verified:
                raise IntegrityError('Exact child root not observed')
            result['status'] = 'running'
            write(receipt, result)
            save_stage()
            while child.poll() is None:
                live = observer.observe()
                tree.members.update(live)
                if observer.denials:
                    raise IntegrityError('Owned traversal/identity observation denied')
                total = psutil.Process().memory_info().rss
                parents, roles = {}, {}
                for identity, process in live.items():
                    try:
                        current = psutil.Process(identity[0])
                        if current.create_time() != identity[1]:
                            continue
                        total += current.memory_info().rss
                        parents[identity[0]] = current.ppid()
                        argv = current.cmdline()  # Exact owned processes only; never persisted.
                        if any(Path(a).name in {'automl_worker.py', 'agent_worker.py'} for a in argv):
                            job = Path(argv[-1]).resolve()
                            allowed_job_root = cwd.resolve() if stage1 else OUTPUT.resolve()
                            if job.name != 'job.json' or not job.is_relative_to(allowed_job_root):
                                raise IntegrityError('Unexpected owned worker job path')
                            roles[identity] = job
                    except psutil.NoSuchProcess:
                        continue
                    except psutil.AccessDenied:
                        observer.denied(*identity, 'role_memory_identity', 'AccessDenied')
                        raise IntegrityError('Owned role/memory observation denied') from None
                role_pids = {key[0] for key in roles}
                top_roles = []
                for identity, job in roles.items():
                    pid, ancestors, cursor = identity[0], set(), parents.get(identity[0])
                    while cursor is not None and cursor not in ancestors:
                        ancestors.add(cursor)
                        cursor = parents.get(cursor)
                    if not ancestors & role_pids:
                        top_roles.append((identity, job))
                # Parent/child venv redirectors share one job; distinct topmost roots do not.
                logical = {(str(job), identity) for identity, job in top_roles}
                result['maximum_logical_worker_jobs'] = max(result['maximum_logical_worker_jobs'], len(logical))
                if len(logical) > 1:
                    raise IntegrityError('More than one logical model worker is live')
                for identity, job_path in top_roles:
                    try:
                        current = psutil.Process(identity[0])
                        if current.create_time() != identity[1]:
                            continue
                        worker_rss = 0
                        # Only already strictly observed identities can contribute;
                        # never adopt descendants from a reopened/reused root PID.
                        for member_identity in live:
                            cursor, ancestors = member_identity[0], set()
                            while cursor is not None and cursor not in ancestors:
                                ancestors.add(cursor)
                                cursor = parents.get(cursor)
                            if identity[0] not in ancestors:
                                continue
                            member = psutil.Process(member_identity[0])
                            if member.create_time() == member_identity[1]:
                                worker_rss += member.memory_info().rss
                        if worker_rss > 1.5 * 2**30:
                            raise MemoryError('Owned worker subtree exceeds1.5GiB')
                        if stage1:
                            job = load(job_path)
                            if job.get('threads') != 2:
                                raise IntegrityError('Actual worker thread limit differs')
                            for value in job.get('spec', {}).get('paths', {}).values():
                                if Path(value).resolve().parent != cwd.resolve() or Path(value).name not in TASK_FILES:
                                    raise IntegrityError('Worker spec references non-deployed input')
                        item = {'pid': identity[0], 'create_time': identity[1], 'job': relative(job_path)}
                        if item not in result['observed_workers']:
                            result['observed_workers'].append(item)
                    except psutil.NoSuchProcess:
                        continue
                    except psutil.AccessDenied:
                        observer.denied(*identity, 'worker_subtree', 'AccessDenied')
                        raise IntegrityError('Worker descendant memory observation denied') from None
                result['peak_owned_tree_rss_mib'] = max(result['peak_owned_tree_rss_mib'], total / 2**20)
                if total > 2 * 2**30:
                    raise MemoryError('Supervisor plus owned tree exceeds2GiB')
                clocks(deadline, unix)
                if time.monotonic() >= process_deadline:
                    raise TimeoutError('Declared parent/process allocation exhausted')
                if time.monotonic() - last_guard >= 30:
                    guard(manifest)
                    last_guard = time.monotonic()
                if time.monotonic() - last_heartbeat >= 2:
                    result.update(heartbeat_unix=time.time(), owned_process_identities=[
                        {'pid': p, 'create_time': c} for p, c in sorted(observer.seen)])
                    write(receipt, result)
                    save_stage()
                    last_heartbeat = time.monotonic()
                time.sleep(.1)
            result.update(status='ok' if child.returncode == 0 else 'failed', exit_code=child.returncode)
    except BaseException as exc:
        result.update(status='technical_failure', exception_type=type(exc).__name__)
    finally:
        result.update(owner.cleanup_owned(child, tree, observer, verified, processes.ProcessTree))
        result.update(seconds=time.monotonic() - tick, end_unix=time.time())
        write(receipt, result)
        save_stage()
    if not result['cleanup_confirmed']:
        raise IntegrityError('Owned cleanup uncertain; no further admission permitted')
    guard(manifest)
    return result


def source_gate(receipt, arm, directory):
    data = load(directory / 'results.json')
    if (receipt['status'] != 'ok' or data.get('passed') is not True or
            data.get('source_unchanged') is not True or data.get('fixture_cleanup_confirmed') is not True
            or data.get('unique_checks_passed') != arm['expected_source_checks'] or data.get('unique_checks_skipped') != 0
            or data.get('source_sha256') != arm['compiled_sha256']):
        raise IntegrityError('Complete zero-skip source gate failed')
    rows = {r['script']: r for r in data['checks']}
    if set(rows) != set(arm['registry']):
        raise IntegrityError('Source registry coverage differs')
    for name, expected in arm['registry'].items():
        row = rows[name]
        if not row['passed'] or row['observed_checks'] != expected or row['skipped_checks'] != 0:
            raise IntegrityError('Source test count/skip mismatch')
    return {'passed': True, 'source_receipt_sha256': digest(directory / 'results.json')}


def exact_gate(receipt, arm, path):
    data = load(path)
    if receipt['status'] != 'ok' or data.get('passed') is not True or data['sha256'] != arm['archive_sha256'] or data.get('matches_current_source') is not True:
        raise IntegrityError('Exact-unpacked source/archive gate failed')
    checks = data.get('checks', [])
    if [r['script'] for r in checks] != ['test_v2.py', 'test_resilience.py', 'smoke.py']:
        raise IntegrityError('Exact-unpacked required scripts missing')
    for row in checks:
        output = row.get('stdout', '') + '\n' + row.get('stderr', '')
        if row['exit_code'] != 0 or re.search(r'\bskipped\s*=\s*[1-9]', output):
            raise IntegrityError('Exact-unpacked skip/exit failure')
        if row['script'] == 'smoke.py':
            cases = json.loads(row['stdout'])
            if len(cases) != 5 or any(c.get('status') != 'passed' for c in cases):
                raise IntegrityError('Exact-unpacked smoke coverage failed')
        else:
            counts = re.findall(r'Ran (\d+) tests? in ', output)
            if not counts or int(counts[-1]) != arm['registry'][row['script']]:
                raise IntegrityError('Exact-unpacked test count failed')
    return {'passed': True, 'exact_receipt_sha256': digest(path)}


def deploy_source(arm, directory):
    source = resolve(arm['source_root'])
    directory.mkdir()
    for name, expected in arm['source_files_sha256'].items():
        target = safe_child(directory, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(safe_child(source, name), target)
        if digest(target) != expected:
            raise IntegrityError('Gate source copying changed bytes')


def run_stage0(report, manifest, deadline, unix, libraries, save):
    owner, processes, verification, independent = libraries
    roots = {}
    for arm in ['a', 'b']:
        root = OUTPUT / ('s' + arm)
        deploy_source(manifest['arms'][arm], root)
        roots[arm] = root
    for index, name in enumerate(manifest['stage0_gate_order']):
        guard(manifest)
        predecessor_check(manifest, owner)
        clocks(deadline, unix)
        remaining_caps = sum(manifest['stage0_caps'][n] for n in manifest['stage0_gate_order'][index:])
        if deadline - time.monotonic() < remaining_caps + manifest['stage0_mock_allowance']:
            raise TimeoutError('Cannot preserve remaining complete Stage0 gates')
        arm, kind = name.split('_')
        source = roots[arm]
        output = OUTPUT / 'gates' / name
        output.parent.mkdir(exist_ok=True)
        cap = manifest['stage0_caps'][name]
        if kind == 'source':
            command = [sys.executable, '-B', str(source / 'tools/run_checks.py'), '--output', str(output)]
        else:
            command = [sys.executable, '-B', str(source / 'tools/verify_release.py'),
                '--archive', str(resolve(manifest['arms'][arm]['archive'])), '--output', str(output.with_suffix('.json')),
                '--timeout', '150', '--memory-gb', '1.5']
        tick = time.monotonic()
        record = supervise(command, source, OUTPUT / ('gate-' + name + '.json'), tick + cap - 10,
            deadline, unix, manifest, owner, processes, save,
            admission_reserve=remaining_caps + manifest['stage0_mock_allowance'])
        if kind == 'source':
            proof = source_gate(record, manifest['arms'][arm], output)
        else:
            proof = exact_gate(record, manifest['arms'][arm], output.with_suffix('.json'))
        for filename, expected in manifest['arms'][arm]['source_files_sha256'].items():
            if digest(safe_child(source, filename)) != expected:
                raise IntegrityError('Deployed gate source/harness changed')
        if time.monotonic() > tick + cap:
            raise TimeoutError('Gate cleanup/proof exceeded original individual parent cap')
        clocks(deadline, unix)
        report['gates'].append({'name': name, 'supervisor': record, 'proof': proof,
                              'parent_seconds_including_cleanup_and_proof': time.monotonic() - tick,
                              'parent_cap_seconds': cap})
        save()
    guard(manifest)
    clocks(deadline, unix)
    report.update(status='completed_stage0_pass', gates_passed=True)


def seal(root):
    files = {}
    for parent, directories, names in os.walk(root):
        # Do not enter or read a private API ledger directory at all.
        directories[:] = sorted(d for d in directories if not d.startswith('run-budget-'))
        for name in sorted(names):
            path = Path(parent) / name
            if path.suffix in {'.json', '.npz', '.csv', '.py', '.txt', '.tsv', '.md'}:
                files[path.relative_to(root).as_posix()] = digest(path)
    return {'root': relative(root), 'files_sha256': files, 'sealed_unix': time.time(),
            'private_ledger_not_read_or_sealed': True}


def check_seal(value):
    root = resolve(value['root'])
    for name, expected in value['files_sha256'].items():
        if digest(safe_child(root, name)) != expected:
            raise IntegrityError('Sealed source/prediction/recipe artifact changed')


def invalidate_cv_completion(report):
    """A later technical failure invalidates every live aggregate qualification."""
    report.update(complete_CV=False, OOF_complete=False, final_CV=None,
                  full_three_fold_macro_f1_mean=None, full_pooled_macro_f1=None)
    if report.get('final_CV_audit_receipt'):
        report['final_CV_audit_qualification'] = 'unqualified_due_to_technical_failure'


def technical_rejection_receipt(report, manifest):
    """Append-only technical evidence, never an inferred inferior ML score."""
    current = report.get('current_declared_slot', report.get('running_slot'))
    slot = next((s for s in report['arms'] if s['directory'] == current), None)
    if slot is not None and slot['status'] != 'not_attempted' and not slot.get('independent_pair_audited'):
        slot.update(status='technical_failure', metrics=None,
                    outer_predictions_sha256=None, final_refit_status=None, final_csv_sha256=None)
    receipts = {}
    for item in report['arms']:
        name = item.get('supervisor_receipt_path')
        if name and resolve(name).is_file():
            receipts[item['directory']] = {'path': name, 'sha256': digest(resolve(name))}
    record = {'status': 'technical_failure', 'fold': slot['fold'] if slot else 0,
        'slot': current, 'exception_type': report.get('exception_type'),
        'failure_code': report.get('failure_code'),
        'source_unchanged': report.get('source_unchanged'),
        'cleanup_confirmed': report.get('cleanup_confirmed'),
        'stage_clock_exception': report.get('stage_clock_exception'),
        'supervisor_receipts': receipts, 'metrics': None,
        'inferior_model_quality_inferred': False,
        'bindings': {'protocol_sha256': R3_SHA, 'fold_manifest_sha256': FOLD_MANIFEST_SHA,
            'archives_sha256': {a: r['archive_sha256'] for a, r in manifest['arms'].items()},
            'supervisor_manifest_sha256': report['manifest_sha256'],
            'common_absolute_deadline_unix': report['absolute_deadline_unix'],
            'common_deadline_monotonic': report['deadline_monotonic']},
        'Stage2_launched': False, 'promotion': False}
    index = 0
    while (OUTPUT / ('technical-rejection-' + str(index).zfill(2) + '.json')).exists():
        index += 1
    path = OUTPUT / ('technical-rejection-' + str(index).zfill(2) + '.json')
    write(path, record, exclusive=True)
    report['prior_gate_audit'] = {'path': relative(path), 'sha256': digest(path)}
    return report['prior_gate_audit']


def run_stage1(report, manifest, deadline, unix, libraries, save):
    owner, processes, verification, independent = libraries
    verification_plan = {'manifest': manifest, 'manifest_path': relative(PACKET / 'manifest.json'),
        'manifest_sha256': report['manifest_sha256'],
        'r3_protocol': {'path': 'fullagent-fixed-half-plan-r3/protocol.json', 'sha256': R3_SHA},
        'publication_receipt': {'path': load(PACKET / 'source-binding.json')['publication_receipt'],
            'sha256': load(PACKET / 'source-binding.json')['publication_receipt_sha256']},
        'source_publication_receipt': {'path': load(PACKET / 'source-binding.json')['source_publication_receipt'],
            'sha256': load(PACKET / 'source-binding.json')['source_publication_receipt_sha256']},
        'stage_receipt_path': relative(OUTPUT / 'stage1.json'),
        'common_absolute_deadline_unix': unix, 'common_deadline_monotonic': deadline,
        'archives': {a: {'path': r['archive'], 'sha256': r['archive_sha256']} for a, r in manifest['arms'].items()},
        'verifier_source_sha256': manifest['independent_verifier_sha256']}
    folds = load(FOLDS / 'manifest.json')
    archives = {a: archive_files(resolve(v['archive'])) for a, v in manifest['arms'].items()}
    for index, slot in enumerate(report['arms']):
        report['current_declared_slot'] = slot['directory']
        guard(manifest)
        predecessor_check(manifest, owner)
        for previous in report['arms']:
            if previous.get('seal'):
                check_seal(previous['seal'])
        clocks(deadline, unix)
        remaining_caps = (len(report['arms']) - index) * LIMITS['parent']
        if deadline - time.monotonic() < remaining_caps + LIMITS['final_audit']:
            raise TimeoutError('Remaining complete paired allocations unavailable')
        fold, arm = slot['fold'], slot['arm']
        directory = OUTPUT / slot['directory']
        tick = time.monotonic()
        directory.mkdir()
        template = FOLDS / 'tasks' / ('f' + str(fold))
        for name in TASK_FILES:
            shutil.copyfile(template / name, directory / name)
        for name, content in archives[arm].items():
            (directory / name).write_bytes(content)
        verification.check_deployment(directory, folds['folds'][fold], manifest['arms'][arm], TASK_FILES)
        if deadline - time.monotonic() < remaining_caps + LIMITS['final_audit']:
            raise TimeoutError('Copying consumed remaining complete paired allocations')
        command = [sys.executable, *manifest['solver_cli']]
        slot.update(output_dir=relative(directory), report_path=relative(directory / 'automl_runs/run-v2/report.json'),
                    source_archive_sha256=manifest['arms'][arm]['archive_sha256'],
                    command=['<same_python>', *manifest['solver_cli']], cleanup_confirmed=False)
        slot['status'] = 'admitted_not_yet_started'
        slot['supervisor_receipt_path'] = relative(OUTPUT / (slot['directory'] + '-supervisor.json'))
        report['running_slot'] = slot['directory']
        save()
        record = supervise(command, directory, OUTPUT / (slot['directory'] + '-supervisor.json'),
            tick + LIMITS['parent'] - LIMITS['arm_audit'], deadline, unix, manifest,
            owner, processes, save, stage1=True,
            admission_reserve=remaining_caps + LIMITS['final_audit'])
        slot['supervisor'] = record
        slot['supervisor_sha256'] = canonical_sha(record)
        slot['supervisor_receipt_sha256'] = digest(resolve(slot['supervisor_receipt_path']))
        slot['exit_code'] = record.get('exit_code')
        slot['cleanup_confirmed'] = record['cleanup_confirmed']
        slot.update(status='process_complete_unverified' if record.get('owned_root') else 'admission_failure_without_process',
                    execution_started=bool(record.get('owned_root')))
        save()
        if record['status'] != 'ok':
            slot['status'] = 'technical_failure'
            raise IntegrityError('Full selection/refit solver failed or timed out')
        audit_deadline = min(time.monotonic() + LIMITS['arm_audit'],
                             tick + LIMITS['parent'], deadline - LIMITS['final_audit'])
        arm_proof = verification.audit_arm(directory, folds['folds'][fold], manifest['arms'][arm], audit_deadline)
        slot.update(status='sealed_complete', final_refit_status='ok',
                    final_csv_sha256=arm_proof['final_csv_sha256'], arm_proof=arm_proof)
        slot['seal'] = seal(directory)
        slot['sealed'] = dict(slot['seal']['files_sha256'])
        check_seal(slot['seal'])
        if time.monotonic() > audit_deadline:
            raise TimeoutError('Arm audit/sealing exceeded fixed120-second verification cap')
        slot['seal_sha256'] = canonical_sha(slot['seal'])
        save()
        clocks(deadline, unix)
        if time.monotonic() > tick + LIMITS['parent']:
            raise TimeoutError('Arm verification exceeded fixed parent cap')
        pair = [s for s in report['arms'] if s['fold'] == fold]
        if all(s['status'] == 'sealed_complete' for s in pair):
            for member in pair:
                check_seal(member['seal'])
            # No outer truth is loaded before both complete arms are sealed.
            pair_deadline = min(time.monotonic() + 120, deadline - LIMITS['final_audit'])
            audit = independent.audit_pair(WORK, verification_plan, pair, folds, pair_deadline)
            for member in pair:
                check_seal(member['seal'])
            audit.setdefault('bindings', {}).update(
                supervisor_manifest_sha256=report['manifest_sha256'],
                common_absolute_deadline_unix=unix, common_deadline_monotonic=deadline)
            path = OUTPUT / ('pair-' + str(fold) + '-audit.json')
            write(path, audit, exclusive=True)
            if time.monotonic() > pair_deadline:
                raise TimeoutError('Paired audit/seal rechecks exceeded original120-second cap')
            report['pairs'].append({'fold': fold, 'path': relative(path), 'sha256': digest(path), **audit})
            for member in pair:
                member.update(status='sealed_complete', independent_pair_audited=True,
                              metrics=audit['arms'][member['arm']],
                              outer_predictions_sha256=member['arm_proof']['final_probabilities_sha256'])
            save()
            if not audit['mandatory_fold_gates_passed']:
                report.update(status='rejected_early_incomplete_CV', rejection_kind='quality_gate_failure',
                    decisive_audit_sha256=digest(path), violated_gates=audit['violated_gates'],
                    prior_gate_audit={'path': relative(path), 'sha256': digest(path)})
                return
    if not all(s['status'] == 'sealed_complete' and s.get('independent_pair_audited') is True for s in report['arms']):
        raise IntegrityError('Incomplete six-arm matrix cannot qualify')
    guard(manifest)
    for slot in report['arms']:
        check_seal(slot['seal'])
    clocks(deadline, unix)
    final_deadline = min(time.monotonic() + LIMITS['final_audit'], deadline)
    final = independent.audit_complete_oof(WORK, verification_plan, report['arms'], folds, final_deadline)
    final_path = OUTPUT / 'final-oof-audit.json'
    write(final_path, final, exclusive=True)
    report['final_CV_audit_receipt'] = {'path': relative(final_path), 'sha256': digest(final_path)}
    report['final_CV_audit_qualification'] = 'pending_terminal_technical_gates'
    guard(manifest)
    clocks(deadline, unix)
    if time.monotonic() > final_deadline:
        raise TimeoutError('Final OOF audit/receipt/guard exceeded original1200-second cap')
    report['final_CV'] = final
    if final.get('complete_CV') is not True or final.get('OOF_complete') is not True:
        raise IntegrityError('Independent verifier did not establish full six-arm OOF completion')
    report.update(status='completed_stage1_pass' if final['all_gates_passed'] else 'completed_stage1_FAIL',
        complete_CV=True, OOF_complete=True, full_three_fold_macro_f1_mean=final['fold_mean'],
        full_pooled_macro_f1=final['pooled_macro_f1'])
    report['final_CV_audit_qualification'] = 'subject_to_terminal_technical_gates'


def launch(args):
    import psutil
    path = PACKET / 'manifest.json'
    if not args.manifest_sha256 or digest(path) != args.manifest_sha256:
        raise IntegrityError('Explicit root-reviewed exact manifest SHA required')
    manifest = load(path)
    guard(manifest)
    review = load(PACKET / 'review.json')
    if (review.get('source_sha256') != digest(__file__) or review.get('manifest_sha256') != args.manifest_sha256
            or review.get('root_launch_reviewed') is not True):
        raise IntegrityError('Exact root launch review is missing')
    stage = args.stage
    cap = LIMITS[stage]
    utc, tick = time.time(), time.monotonic()
    if args.deadline_unix is None or not math.isfinite(args.deadline_unix):
        raise ValueError('Root must assign this new prospective stage absolute deadline')
    remaining = args.deadline_unix - utc
    if not cap - 100 <= remaining <= cap:
        raise ValueError('Fresh stage deadline must retain declared stage envelope')
    deadline = tick + remaining
    owner = module('_fullagent_cv_owner', PACKET / 'ownership.py')
    processes = module('_fullagent_cv_processes', PACKET / 'processes.py')
    awake = module('_fullagent_cv_awake', PACKET / 'awake.py')
    lock_module = module('_fullagent_cv_lock', PACKET / 'research_lock.py')
    verification = module('_fullagent_cv_verification', PACKET / 'verification.py')
    independent = module('_fullagent_cv_independent_verifier', PACKET / 'independent_verifier.py')
    predecessor = predecessor_check(manifest, owner)
    stage0_path = OUTPUT / 'stage0.json'
    if stage == 'stage1':
        stage0 = load(stage0_path)
        if (stage0.get('status') != 'completed_stage0_pass' or stage0.get('cleanup_confirmed') is not True
                or stage0.get('manifest_sha256') != args.manifest_sha256
                or stage0.get('source_unchanged') is not True):
            raise IntegrityError('Exact A/B Stage0 gates and cleanup have not passed')
        previous_observer = owner.StrictOwnedObserver()
        previous_observer.remember(identities(stage0))
        if previous_observer.observe() or previous_observer.denials:
            raise IntegrityError('Stage0 owned identity/descendant remains or is uncertain')
        if any(not row.get('proof', {}).get('passed') for row in stage0.get('gates', [])) or len(stage0.get('gates', [])) != 4:
            raise IntegrityError('Stage0 does not contain all four actual A/B gates')
        if stage0.get('seconds', float('inf')) > LIMITS['stage0']:
            raise IntegrityError('Stage0 exceeded its original common envelope')
        for gate in stage0['gates']:
            arm, kind = gate['name'].split('_')
            if kind == 'source':
                proof = source_gate(gate['supervisor'], manifest['arms'][arm], OUTPUT / 'gates' / gate['name'])
            else:
                proof = exact_gate(gate['supervisor'], manifest['arms'][arm], (OUTPUT / 'gates' / gate['name']).with_suffix('.json'))
            if proof != gate['proof']:
                raise IntegrityError('Saved Stage0 exact gate receipt changed before Stage1')
    receipt = OUTPUT / (stage + '.json')
    if receipt.exists() or stage == 'stage0' and OUTPUT.exists():
        raise FileExistsError('Preserve prior attempts; no automatic retry/resume or clock reset')
    with lock_module.ResearchLock(REPO / 'test-runs/.owned-research.lock') as lock:
        lock.write_identity({'pid': os.getpid(), 'create_time': psutil.Process().create_time()})
        predecessor = predecessor_check(manifest, owner)
        guard(manifest)
        clocks(deadline, args.deadline_unix)
        OUTPUT.mkdir(exist_ok=stage == 'stage1')
        report = {'status': 'running', 'stage': stage, 'manifest_sha256': args.manifest_sha256,
            'start_unix': utc, 'start_monotonic': tick, 'absolute_deadline_unix': args.deadline_unix,
            'deadline_monotonic': deadline, 'stage_cap_seconds': cap,
            'common_absolute_deadline_unix': args.deadline_unix, 'common_deadline_monotonic': deadline,
            'common_start_unix': args.deadline_unix - cap,
            'common_start_monotonic': deadline - cap, 'common_seconds': cap,
            'owned_root': {'pid': os.getpid(), 'create_time': psutil.Process().create_time()},
            'predecessor': predecessor, 'cleanup_confirmed': False, 'source_unchanged': False,
            'gates': [], 'pairs': [], 'complete_CV': False, 'OOF_complete': False, 'final_CV': None,
            'full_three_fold_macro_f1_mean': None, 'full_pooled_macro_f1': None,
            'stage2_started': False, 'promotion': False, 'API_limit': 0,
            'arms': [dict(s, status='not_attempted', metrics=None, outer_predictions_sha256=None,
                          final_refit_status=None, final_csv_sha256=None) for s in manifest['slots']]}
        def save():
            write(receipt, report)
        def interrupted(signum, frame):
            raise SystemExit(128 + signum)
        previous_signals = {sig: signal.signal(sig, interrupted) for sig in [signal.SIGINT, signal.SIGTERM]}
        report['scoped_awake_requested'] = awake.scoped_awake(True)
        save()
        try:
            if stage == 'stage0':
                run_stage0(report, manifest, deadline, args.deadline_unix, (owner, processes, verification, independent), save)
            else:
                run_stage1(report, manifest, deadline, args.deadline_unix, (owner, processes, verification, independent), save)
        except BaseException as exc:
            report.update(status='rejected_early_incomplete_CV' if stage == 'stage1' else 'failed_stage0',
                          rejection_kind='technical_failure', exception_type=type(exc).__name__)
            text = str(exc)
            if re.fullmatch(r'[A-Za-z0-9_.:-]{1,180}', text):
                report['failure_code'] = text
        finally:
            try:
                guard(manifest)
                report['source_unchanged'] = True
            except BaseException as exc:
                report.update(source_unchanged=False, integrity_exception=type(exc).__name__)
            try:
                children = [load(p) for p in OUTPUT.glob('*-supervisor.json')] if stage == 'stage1' else [load(p) for p in OUTPUT.glob('gate-*.json')]
                final_observer = owner.StrictOwnedObserver()
                for child in children:
                    final_observer.remember(identities(child))
                report['final_owned_recheck'] = final_observer.final_check()
                report['cleanup_confirmed'] = (all(c.get('cleanup_confirmed') is True for c in children)
                    and not report['final_owned_recheck']['unresolved'])
            except BaseException as exc:
                report.update(cleanup_confirmed=False, cleanup_recheck_exception=type(exc).__name__)
            try:
                clocks(deadline, args.deadline_unix)
            except BaseException as exc:
                report.update(status='rejected_early_incomplete_CV' if stage == 'stage1' else 'failed_stage0',
                    rejection_kind='technical_failure', stage_clock_exception=type(exc).__name__)
            if stage == 'stage1' and report['status'] != 'completed_stage1_pass':
                report['qualification'] = 'FAIL'
                if report.get('rejection_kind') == 'technical_failure':
                    invalidate_cv_completion(report)
            report.update(end_unix=time.time(), seconds=time.monotonic() - tick,
                          scoped_awake_released=awake.scoped_awake(False))
            if not report['cleanup_confirmed'] or not report['source_unchanged']:
                report.update(status='fatal_cleanup_or_integrity_failure', qualification='FAIL', rejection_kind='technical_failure')
                if stage == 'stage1':
                    invalidate_cv_completion(report)
            if stage == 'stage1' and report.get('rejection_kind') == 'technical_failure':
                technical_rejection_receipt(report, manifest)
            if stage == 'stage1' and report['status'] != 'completed_stage1_pass':
                for slot in report['arms']:
                    if slot['status'] == 'not_attempted':
                        slot.update(status='not_attempted_due_prior_gate_failure',
                            prior_gate_audit=report.get('prior_gate_audit'),
                            reason=report.get('rejection_kind'))
            save()
            # The terminal write is part of the original stage envelope too.
            if time.monotonic() > deadline or time.time() > args.deadline_unix:
                report.update(status='rejected_early_incomplete_CV' if stage == 'stage1' else 'failed_stage0',
                    qualification='FAIL', rejection_kind='technical_failure',
                    stage_clock_exception='terminal_write_exceeded_original_deadline',
                    end_unix=time.time(), seconds=time.monotonic() - tick)
                if stage == 'stage1':
                    invalidate_cv_completion(report)
                    reference = technical_rejection_receipt(report, manifest)
                    for slot in report['arms']:
                        if slot['status'] == 'not_attempted_due_prior_gate_failure':
                            slot['prior_gate_audit'] = reference
                save()
            for sig, old in previous_signals.items():
                signal.signal(sig, old)
    if report['status'] not in {'completed_stage0_pass', 'completed_stage1_pass'}:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--packet', default='fullagent-cv-launch-r1')
    parser.add_argument('--binding', type=Path)
    parser.add_argument('--launch', action='store_true')
    parser.add_argument('--stage', choices=['stage0', 'stage1'])
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--deadline-unix', type=float)
    args = parser.parse_args()
    configure(args.work_root, args.packet)
    if args.launch:
        if not args.stage:
            parser.error('--stage required for an explicit reviewed launch')
        launch(args)
    else:
        if args.stage or args.deadline_unix is not None:
            parser.error('Prepare-only never assigns/uses stage clocks')
        if args.binding is None:
            print(json.dumps({'status': 'blocked_prepare_only', 'missing': [
                'Root-approved/published r3 binding, exact A/B source archives/inventories, terminal tm1 ownership proof and library hashes'],
                'new_children': 0, 'fits': 0, 'api_calls': 0, 'deadline_assigned': False}))
            return
        prepare(args.binding.resolve())


if __name__ == '__main__':
    main()
