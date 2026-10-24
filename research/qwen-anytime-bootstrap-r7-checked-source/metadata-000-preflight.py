"""Exact QH metadata predicates; no controller/candidate import or campaign clock.

Opaque chunked hashes may read exact frozen paths, including CSV/NPZ. Text reads
are restricted to pinned JSON/Python metadata. No dataset/array decoder is used.
"""
import ast
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import re
import sys
import time


FUNCTIONS = frozenset({'need', 'read', 'sha', 'methods', 'qualified',
                       'strong_authority', 'config', 'predecessor'})
C5_SHA = 'd5f41cad6de2168cd520e442223428285dd3714854079d9305dd1b34938abd7d'
RUNTIME_CALLS = frozenset({'main', 'run', 'Popen', 'subprocess', 'exec', 'eval',
    '__import__', 'save', 'mkdir', 'unlink', 'replace', 'kill', 'terminate',
    'read_csv', 'load', 'read_bytes', 'glob', 'rglob', 'iterdir', 'walk'})


def need(value, code):
    if not value:
        raise RuntimeError(code)


def project(source, filename):
    """Copy complete source nodes; close over their original global assignments."""
    tree = ast.parse(source, filename=filename)
    definitions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    need(FUNCTIONS <= definitions.keys(), 'QH_exact_metadata_functions_missing')
    need(all(sum(isinstance(n, ast.FunctionDef) and n.name == key for n in tree.body) == 1
             for key in FUNCTIONS), 'QH_duplicate_metadata_function')
    assignments = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            key = node.targets[0].id
            need(key not in assignments, 'QH_duplicate_global_assignment')
            assignments[key] = node
    names = {v.id for key in FUNCTIONS for v in ast.walk(definitions[key])
             if isinstance(v, ast.Name) and isinstance(v.ctx, ast.Load) and v.id in assignments}
    while True:
        extra = {v.id for key in names for v in ast.walk(assignments[key])
                 if isinstance(v, ast.Name) and isinstance(v.ctx, ast.Load) and v.id in assignments}
        if extra <= names:
            break
        names |= extra
    selected = [n for n in tree.body if
        (isinstance(n, ast.FunctionDef) and n.name in FUNCTIONS) or
        (isinstance(n, ast.Assign) and len(n.targets) == 1
         and isinstance(n.targets[0], ast.Name) and n.targets[0].id in names)]
    module = ast.Module(body=selected, type_ignores=[])
    for node in ast.walk(module):
        need(not isinstance(node, (ast.Import, ast.ImportFrom)), 'QH_projected_import_forbidden')
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.id if isinstance(fn, ast.Name) else (fn.attr if isinstance(fn, ast.Attribute) else None)
            need(name not in RUNTIME_CALLS, 'QH_projected_runtime_call_forbidden')
            need(not (isinstance(fn, ast.Name) and fn.id == 'open'), 'QH_unbounded_open_forbidden')
    # Only sha owns opaque byte reads; only read/methods own JSON/source text.
    for key in FUNCTIONS:
        for node in ast.walk(definitions[key]):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr == 'open':
                need(key == 'sha' and len(node.args) == 1 and isinstance(node.args[0], ast.Constant)
                     and node.args[0].value == 'rb' and not node.keywords, 'QH_only_SHA_streaming_allowed')
            if node.func.attr == 'read_text':
                need(key in {'read', 'methods'}, 'QH_only_metadata_text_reads_allowed')
    return module, sorted(names)


def evaluate(controller, manifest, expected_controller, expected_manifest):
    started = time.monotonic()
    previous = started
    def check():
        nonlocal previous
        now = time.monotonic()
        need(math.isfinite(now) and now >= previous, 'QH_metadata_clock_rollback')
        previous = now
        need(now - started < 30, 'QH_metadata_preflight30_expired')
        return now - started
    def fixed_path(value):
        p = Path(value)
        need(p.is_absolute() and p.resolve(strict=True) == p and p.is_file(), 'QH_absolute_existing_path_required')
        return p
    controller, manifest = fixed_path(controller), fixed_path(manifest)
    need(controller.suffix == '.py' and manifest.suffix == '.json'
         and manifest.stat().st_size <= 2**20, 'QH_fixed_source_and_private_JSON_required')
    need(all(type(h) is str and re.fullmatch('[0-9a-f]{64}', h)
             for h in (expected_controller, expected_manifest)), 'QH_typed_SHA_required')
    stats = {'opaque_hash_bytes': 0, 'opaque_hash_streams': 0, 'metadata_text_reads': 0}
    allowed = {str(controller), str(manifest)}
    class HashStream:
        def __init__(self, path):
            check();need(str(path) in allowed and path.is_file(), 'QH_unpinned_opaque_read_forbidden')
            self.stream = io.open(str(path), 'rb');self.maximum = path.stat().st_size;self.count = 0
            stats['opaque_hash_streams'] += 1
        def __enter__(self): return self
        def __exit__(self, *args): self.stream.close()
        def read(self, size):
            check();need(type(size) is int and 0 < size <= 2**20, 'QH_bounded_hash_chunk_required')
            block = self.stream.read(size);self.count += len(block)
            need(self.count <= self.maximum, 'QH_file_grew_during_hash')
            stats['opaque_hash_bytes'] += len(block);check();return block
    def digest(path):
        h = hashlib.sha256()
        with HashStream(path) as stream:
            while True:
                block = stream.read(2**20)
                if not block: break
                h.update(block)
        check();return h.hexdigest()
    def text(path, encoding):
        check();need(str(path) in allowed and path.suffix in {'.json', '.py'}
                     and path.stat().st_size <= 32*2**20, 'QH_data_or_unbounded_text_read_forbidden')
        need(encoding in {'utf-8', 'utf-8-sig'}, 'QH_UTF8_metadata_required')
        with io.open(str(path), 'r', encoding=encoding) as stream: result = stream.read()
        stats['metadata_text_reads'] += 1;check();return result
    need(digest(controller) == expected_controller and digest(manifest) == expected_manifest,
         'QH_controller_or_private_SHA_changed')
    cfg_metadata = json.loads(text(manifest, 'utf-8'))
    pins = cfg_metadata.get('immutable_files')
    need(type(pins) is dict and 1 <= len(pins) <= 4096 and all(
        type(p) is str and Path(p).is_absolute() and type(h) is str and re.fullmatch('[0-9a-f]{64}', h)
        for p, h in pins.items()), 'QH_exact_frozen_path_allowlist_required')
    allowed.update(pins)
    class MetadataPath(type(Path())):
        def open(self, mode='r', *args, **kwargs):
            need(mode == 'rb' and not args and not kwargs, 'QH_only_opaque_hash_open_allowed')
            return HashStream(self)
        def read_text(self, encoding=None, errors=None, **kwargs):
            need(errors is None and not kwargs, 'QH_exact_metadata_text_mode_required')
            return text(self, encoding)
        def read_bytes(self):
            raise RuntimeError('QH_direct_payload_read_forbidden')
    module, names = project(text(controller, 'utf-8-sig'), str(controller))
    namespace = {'Path': MetadataPath, 'ast': ast, 'hashlib': hashlib, 'json': json,
        'math': math, 're': re, 'sys': sys, '__file__': str(controller),
        '__name__': '_exact_QH_metadata_projection'}
    exec(compile(module, str(controller), 'exec'), namespace)
    trusted_imports = []
    def trusted_helper(name, path):
        path = Path(path)
        expected_path = namespace['WORK']/'br-standard-release-qualification-next-dev/controller-r5/run_controller.py'
        need(path == expected_path and pins.get(str(path)) == C5_SHA and digest(path) == C5_SHA,
             'QH_only_exact_qualified_C5_metadata_helper_allowed')
        check();spec = importlib.util.spec_from_file_location(name, path)
        helper = importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
        trusted_imports.append(C5_SHA);check();return helper
    namespace['imported'] = trusted_helper
    cfg = namespace['config'](str(manifest), expected_manifest, expected_controller)
    known = namespace['predecessor'](cfg, check);elapsed = check()
    return dict(exact_config_predicate_passed=True, exact_predecessor_predicate_passed=True,
        controller_sha256=expected_controller, manifest_sha256=expected_manifest,
        saved_known_identity_count=len(known), qualified_metadata_helper_imports=len(trusted_imports),
        projected_global_assignments=names, elapsed_seconds=elapsed,
        opaque_SHA_streaming=stats, data_or_array_decodes=0, candidate_imports=0,
        controller_module_imports=0, models=0, API=0, runtime_admitted=False)


if __name__ == '__main__':
    try:
        need(len(sys.argv) == 5, 'QH_exact_four_arguments_required')
        print(json.dumps(evaluate(*sys.argv[1:5]), sort_keys=True))
    except Exception as error:
        code = str(error) if isinstance(error, RuntimeError) else type(error).__name__
        if not re.fullmatch('[A-Za-z0-9_]+', code): code = type(error).__name__
        print(json.dumps(dict(exact_config_predicate_passed=False,
            exact_predecessor_predicate_passed=False, code=code, runtime_admitted=False)))
        raise SystemExit(1)
