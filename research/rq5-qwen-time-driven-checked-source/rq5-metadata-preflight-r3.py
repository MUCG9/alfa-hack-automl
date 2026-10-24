"""Run the reviewed controller's exact metadata predicate without importing it.

This checks a prospective private binding. It admits no runtime, launches no
children, creates no campaign clock, and does not import candidate/model code.
"""
import ast
import hashlib
import json
import importlib.util
import math
from pathlib import Path
import re
import sys
import time


def evaluate(controller, manifest, expected_controller, expected_manifest,
             check_predecessor=False):
    started = time.monotonic()
    controller = Path(controller).resolve(strict=True)
    manifest = Path(manifest).resolve(strict=True)
    if hashlib.sha256(controller.read_bytes()).hexdigest() != expected_controller:
        raise RuntimeError('metadata_controller_changed')
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != expected_manifest:
        raise RuntimeError('metadata_manifest_changed')
    tree = ast.parse(controller.read_text('utf-8-sig'))
    names = {'PACKET', 'WORK', 'OUT', 'CAPS', 'HELPERS',
             'EXECUTOR_HANDOFF_SHA', 'ARCHIVE_SHA', 'CASES_HANDOFF_SHA',
             'ROOT_HELPER_SHA', 'COUNTS_SHA', 'LAUNCHER_PATH', 'LAUNCHER_SHA'}
    functions = {'need', 'read', 'sha', 'methods', 'config'}
    if check_predecessor:
        names |= {'RQ4_NEGATIVE_SHA', 'RQ4_NEGATIVE_TOOL',
                  'RQ4_POST_SHA', 'RQ4_POST_TOOL'}
        functions |= {'ids', 'previous_admission', 'prior_current_admission',
                      'prior_RQ2_admission', 'prior_RQ3_admission', 'predecessor'}
    selected = []
    found_names, found_functions = set(), set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in names:
                selected.append(node)
                found_names.add(target.id)
        elif isinstance(node, ast.FunctionDef) and node.name in functions:
            selected.append(node)
            found_functions.add(node.name)
    if found_names != names or found_functions != functions:
        raise RuntimeError('metadata_exact_predicate_dependency_changed')
    # The source projection is closed: no module imports or runtime entrypoint.
    projected = ast.Module(body=selected, type_ignores=[])
    if any(isinstance(n, (ast.Import, ast.ImportFrom)) for n in ast.walk(projected)):
        raise RuntimeError('metadata_projection_import_forbidden')
    forbidden = {'imported', 'main', 'run', 'Popen', 'subprocess', 'exec',
                 'eval', '__import__', 'save', 'mkdir', 'unlink', 'replace'}
    if check_predecessor:
        forbidden.remove('imported')
    for node in ast.walk(projected):
        if isinstance(node, ast.Call):
            called = node.func
            name = called.id if isinstance(called, ast.Name) else (
                called.attr if isinstance(called, ast.Attribute) else None)
            if name in forbidden:
                raise RuntimeError('metadata_projection_runtime_call_forbidden')
    namespace = {'Path': Path, 'ast': ast, 'hashlib': hashlib, 'json': json,
                 'math': math,
                 're': re, 'sys': sys, '__file__': str(controller),
                 '__name__': '_closed_controller_metadata_projection'}
    exec(compile(projected, str(controller), 'exec'), namespace)
    def bounded_check():
        if time.monotonic() - started > 30:
            raise RuntimeError('metadata_preflight_30_seconds_exceeded')
    trusted_imports = []
    def trusted_metadata_helper(name, path):
        work = namespace['WORK']
        approved = {
            work / 'last-submission-class-cases-caller-next-dev/run_cases.py':
            'e3f3482d91ec2accddc35758a883505baee9b5e968334ff2c824ff06eaf24fce',
            work / 'br-standard-release-qualification-next-dev/controller-r5/run_controller.py':
            'd5f41cad6de2168cd520e442223428285dd3714854079d9305dd1b34938abd7d'}
        path = Path(path).resolve(strict=True)
        bounded_check()
        if path not in approved or hashlib.sha256(path.read_bytes()).hexdigest() != approved[path]:
            raise RuntimeError('metadata_unqualified_helper_import_forbidden')
        # Both exact previously qualified helpers have stdlib-only top levels;
        # their model execution entrypoints remain guarded and are never called.
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        trusted_imports.append(approved[path])
        return module
    namespace['imported'] = trusted_metadata_helper
    cfg = namespace['config'](str(manifest), expected_manifest, expected_controller)
    known = None
    if check_predecessor:
        known = namespace['predecessor'](cfg, bounded_check)
    elapsed = time.monotonic() - started
    if elapsed > 30:
        raise RuntimeError('metadata_preflight_30_seconds_exceeded')
    return {'exact_config_predicate_passed': True,
            'controller_sha256': expected_controller,
            'manifest_sha256': expected_manifest,
            'elapsed_seconds': elapsed, 'runtime_admitted': False,
            'exact_predecessor_predicate_passed': check_predecessor,
            'saved_known_identity_count': len(known) if known is not None else None,
            'qualified_metadata_helper_imports': len(trusted_imports),
            'candidate_imports': 0, 'models': 0, 'API': 0}


if __name__ == '__main__':
    try:
        if len(sys.argv) not in (5, 6) or (len(sys.argv) == 6 and sys.argv[5] != '--predecessor'):
            raise RuntimeError('metadata_exact_four_arguments_required')
        result = evaluate(*sys.argv[1:5], check_predecessor=len(sys.argv) == 6)
        print(json.dumps(result, sort_keys=True))
    except Exception as error:
        code = str(error) if isinstance(error, RuntimeError) else type(error).__name__
        # Only fixed diagnostic tokens may reach the public tool result.
        if not re.fullmatch('[A-Za-z0-9_]+', code):
            code = type(error).__name__
        print(json.dumps({'exact_config_predicate_passed': False, 'code': code}))
        raise SystemExit(1)
