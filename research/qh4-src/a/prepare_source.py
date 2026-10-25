"""Stdlib source preparation only; never imports or executes candidate/tests."""
from pathlib import Path
import ast
import copy
import difflib
import hashlib
import json

WORK = Path(__file__).resolve().parent
OLD = WORK / 'qwen-three-hour-independent-audit-next-dev-r5'
NEW = WORK / 'qwen-three-hour-independent-audit-next-dev-r6'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(node):
    return ast.dump(node, include_attributes=False)

def write_json(path, value):
    path.write_bytes((json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8'))

old_hand_path = OLD / 'source-handoff.json'
assert sha(old_hand_path) == '9b125b77d9bab42b32cda96f42ac3379968dfdd80f0e7e59a153942024d217f8'
old_hand = json.loads(old_hand_path.read_text(encoding='utf-8'))
assert not NEW.exists(), 'new isolated source directory must not exist'
for rel, expected in old_hand['files_sha256'].items():
    assert sha(OLD / rel) == expected, rel
for rel, expected in old_hand['external_refs_sha256'].items():
    assert not rel.startswith('work/') and sha(WORK / rel) == expected, rel
NEW.mkdir()
for rel in old_hand['files_sha256']:
    target = NEW / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((OLD / rel).read_bytes())

preserved = {}
for index, (rel, expected) in enumerate(list(old_hand['files_sha256'].items()) + [('source-handoff.json', sha(old_hand_path))]):
    flat = 'r5-preserved/%03d.bin' % index
    target = NEW / flat
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((OLD / rel).read_bytes())
    assert sha(target) == expected
    preserved[rel] = dict(path=flat, sha256=expected)
write_json(NEW / 'R5-preservation.json', dict(schema='source-snapshot-preservation-v1', original=str(OLD), files=preserved))

old_source = (OLD / 'audit_final.py').read_text(encoding='utf-8')
new_source = old_source.replace('CORE_FILES_LIMIT=20000\n', 'CORE_FILES_LIMIT=20000\nTASK_ADMISSION_MARGIN=180+10+60+10+2*5\n', 1)
old_bounds = "and 0<remaining<=85 and 4715<=elapsed<4800\n         and end>=timing['task_deadline_unix']-85,"
new_bounds = "and 0<remaining<=TASK_ADMISSION_MARGIN and 4800-TASK_ADMISSION_MARGIN<=elapsed<4800\n         and end>=timing['task_deadline_unix']-TASK_ADMISSION_MARGIN,"
assert old_source.count(old_bounds) == 1
new_source = new_source.replace(old_bounds, new_bounds, 1)
(NEW / 'audit_final.py').write_bytes(new_source.encode('utf-8'))

old_tests = (OLD / 'test_audit_contracts.py').read_text(encoding='utf-8')
old_case = 'for change in [dict(remaining_task_seconds_at_stop=100.),dict(elapsed_task_seconds_at_stop=40.),dict(stop_reason=\'gateway64_cap\')]:'
new_case = 'for change in [dict(remaining_task_seconds_at_stop=271.),dict(elapsed_task_seconds_at_stop=40.),dict(stop_reason=\'gateway64_cap\')]:'
assert old_tests.count(old_case) == 1
new_tests = old_tests.replace(old_case, new_case, 1)
new_method = '''    def test_full_provider_margin_exact_boundary_and_too_early_or_invalid_stops(self):
        report=dict(schema='qwen-iterative-task-v2-anytime',stop_reason='original_task_time_admission_margin',
            gateway_safety_upper=4800,callback_safety_upper=19204,
            remaining_task_seconds_at_stop=270.,elapsed_task_seconds_at_stop=4530.)
        timing=dict(task_deadline_unix=5800.)
        boundary=A.anytime_time_goal(report,timing,dict(end_unix=5530.))
        self.assertEqual(boundary['admission_stop_remaining_seconds'],270.)
        self.assertEqual(boundary['admission_stop_elapsed_seconds'],4530.)
        later=A.anytime_time_goal(dict(report,remaining_task_seconds_at_stop=269.75,
            elapsed_task_seconds_at_stop=4530.25),timing,dict(end_unix=5530.25))
        self.assertEqual(later['observed_supervisor_end_unix'],5530.25)
        changes=[dict(remaining_task_seconds_at_stop=270.000001),
            dict(remaining_task_seconds_at_stop=0.),dict(remaining_task_seconds_at_stop=-1.),
            dict(remaining_task_seconds_at_stop=True),dict(remaining_task_seconds_at_stop=float('nan')),
            dict(elapsed_task_seconds_at_stop=4529.999999),dict(elapsed_task_seconds_at_stop=4800.),
            dict(elapsed_task_seconds_at_stop=float('inf'))]
        for change in changes:
            with self.subTest(change=change),self.assertRaises(A.AuditStop):
                A.anytime_time_goal(dict(report,**change),timing,dict(end_unix=5530.))
        with self.assertRaisesRegex(A.AuditStop,'observed_exit'):
            A.anytime_time_goal(report,timing,dict(end_unix=5529.999999))

'''
insert_before = '    def test_actual_semantic_counts_above_64_256_remain_finite_without_file_capacity_claim(self):'
assert new_tests.count(insert_before) == 1
new_tests = new_tests.replace(insert_before, new_method + insert_before, 1)
(NEW / 'test_audit_contracts.py').write_bytes(new_tests.encode('utf-8'))

old_tree = ast.parse(old_source)
new_tree = ast.parse(new_source)
old_func = next(n for n in old_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'anytime_time_goal')
new_func = next(n for n in new_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'anytime_time_goal')
expected_func = ast.parse(ast.get_source_segment(old_source, old_func).replace(old_bounds, new_bounds)).body[0]
assert dump(new_func) == dump(expected_func), 'only exact declared time bounds may differ'
expected_constant = ast.parse('TASK_ADMISSION_MARGIN=180+10+60+10+2*5').body[0]
constants = [n for n in new_tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'TASK_ADMISSION_MARGIN' for t in n.targets)]
assert len(constants) == 1 and dump(constants[0]) == dump(expected_constant)
inverse = copy.deepcopy(new_tree)
inverse.body = [n for n in inverse.body if not (isinstance(n, ast.Assign) and dump(n) == dump(expected_constant))]
for index, node in enumerate(inverse.body):
    if isinstance(node, ast.FunctionDef) and node.name == 'anytime_time_goal':
        inverse.body[index] = copy.deepcopy(old_func)
assert dump(inverse) == dump(old_tree), 'whole R5 module inverse must be exact'

def methods(text):
    result = {}
    for node in ast.parse(text).body:
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name.startswith('test_'):
                    result[node.name + '.' + child.name] = child
    return result

old_methods = methods(old_tests)
new_methods = methods(new_tests)
rebased = 'AnytimeAuditContracts.test_time_goal_requires_original_margin_and_observed_supervisor_end'
new_name = 'AnytimeAuditContracts.test_full_provider_margin_exact_boundary_and_too_early_or_invalid_stops'
assert set(new_methods) == set(old_methods) | {new_name}
assert all(dump(new_methods[name]) == dump(node) for name, node in old_methods.items() if name != rebased)
old_rebased = ast.get_source_segment(old_tests, old_methods[rebased])
new_rebased = ast.get_source_segment(new_tests, new_methods[rebased])
assert new_rebased.replace('remaining_task_seconds_at_stop=271.', 'remaining_task_seconds_at_stop=100.', 1) == old_rebased
def asserts(node):
    return [dump(n) for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr.startswith('assert')]
assert asserts(new_methods[rebased]) == asserts(old_methods[rebased]), 'all old assertion ASTs must remain exact'
test_inverse = copy.deepcopy(ast.parse(new_tests))
for cls in test_inverse.body:
    if isinstance(cls, ast.ClassDef):
        cls.body = [n for n in cls.body if not (isinstance(n, ast.FunctionDef) and cls.name + '.' + n.name == new_name)]
        for index, node in enumerate(cls.body):
            if isinstance(node, ast.FunctionDef) and cls.name + '.' + node.name == rebased:
                cls.body[index] = copy.deepcopy(old_methods[rebased])
assert dump(test_inverse) == dump(ast.parse(old_tests)), 'whole test-module inverse must be exact'
csv_methods = methods((NEW / 'test_csv_role_contracts.py').read_text(encoding='utf-8'))
all_methods = {name: hashlib.sha256(dump(node).encode()).hexdigest() for name, node in {**new_methods, **csv_methods}.items()}
assert len(all_methods) == 30 and len(new_methods) == 28 and len(csv_methods) == 2

patch = ''.join(difflib.unified_diff(old_source.splitlines(True), new_source.splitlines(True), fromfile='R5/audit_final.py', tofile='R6/audit_final.py'))
patch += ''.join(difflib.unified_diff(old_tests.splitlines(True), new_tests.splitlines(True), fromfile='R5/test_audit_contracts.py', tofile='R6/test_audit_contracts.py'))
(NEW / 'R6-time-admission-only.patch').write_bytes(patch.encode('utf-8'))
(NEW / 'prepare_source.py').write_bytes(Path(__file__).read_bytes())

proof = dict(schema='QH-auditor-R6-exact-source-proof-v1', whole_R5_module_inverse_exact=True,
    exact_added_constant='TASK_ADMISSION_MARGIN=180+10+60+10+2*5', derived_margin_seconds=270,
    changed_runtime_function='anytime_time_goal', changed_bounds=['0<remaining<=270','4800-270<=elapsed<4800','observed_end>=task_deadline-270'],
    other_runtime_functions_classes_AST_exact=True, whole_test_module_inverse_exact=True,
    old_method_count=29, old28_method_AST_exact=True, authorized_rebased_method=rebased,
    rebase='only invalid remaining fixture100->271; all old assertion ASTs exact', new_method=new_name,
    old_csv_test_bytes_exact=sha(NEW/'test_csv_role_contracts.py')==sha(OLD/'test_csv_role_contracts.py'),
    primitive_bytes_exact=sha(NEW/'r4_primitives.py')==sha(OLD/'r4_primitives.py'),
    prepared_method_count=30, methods_sha256=all_methods,
    unchanged_gates=['all recorded gateway calls statusok','known HTTP attempts','complete token usage','source and both complete core seals before truth','independent R4 formulas','checkpoint/fresh median/CSV','resource origin, cleanup, caps, original clocks'],
    executed_tests=0, candidate_imports=0, model_fits=0, API=0, PID_scans=0, data_truth_prediction_reads=0,
    actual_READY=None, actual_clock=None)
write_json(NEW/'source-proof.json', proof)
protocol = json.loads((OLD/'protocol.json').read_text(encoding='utf-8'))
protocol.update(schema='QH-auditor-R6-full-provider-window-time-protocol-v1', revision='R6 timing predicate only',
    prepared_method_count=30, actual_tests=0, actual_experiment_clock=None,
    task_seconds=4800, common_seconds=10800, admission_margin_expression='180+10+60+10+2*5', admission_margin_seconds=270,
    notes='Only new prospective full-provider-window timing predicate; no padding, time borrowing, current QH3 salvage, or usage relaxation. Historical evidence is immutable; current30 prepared methods, same2 entrypoints.')
write_json(NEW/'protocol.json', protocol)
(NEW/'README.txt').write_bytes(b'R6 SOURCE ONLY, NOT READY.\nDerived270-second full-provider-window stop bound; original4800/task and10800 common.\nStrict status/attempt/completeusage and every source/quality/resource gate unchanged.\n30 prepared methods across the same2 entrypoints; zero author executions/imports/models/API.\nOriginalR5 exact snapshot plus whole runtime/test inverse proof retained.\n')

external = dict(old_hand['external_refs_sha256'])
extra = {
    'qwen-three-hour-independent-audit-next-dev-r5/source-handoff.json': '9b125b77d9bab42b32cda96f42ac3379968dfdd80f0e7e59a153942024d217f8',
    'qwen-three-hour-independent-audit-next-dev-r5/audit_final.py': '1d882d01078a40f02a0229ea5498c3c295e0f7df9b2b232a7a6b3f93997c0d96',
    'qwen-three-hour-independent-audit-next-dev-r5/test_audit_contracts.py': '9b05641f68fbdabd4887ac8e55a25033e5834957f1a841db8bf3a013e2ab4fab',
    'qwen-three-hour-independent-audit-source-review-r5.json': 'b6281b8dfd3226f9e787b8a98b1f0683a3e37b7e6755b9f74d663dd393453521',
    'qh3-terminal-budget-independent-review-next-dev/source-handoff-final.json': '3674b885a3a48fcf621c7ecd8b6bbc2b6d6ff3ca1743daefa1d7167ce578f419',
    'qh3-terminal-budget-independent-review-next-dev/root-option-B-scope-r1.json': 'a459f5d95159b02d96ddcaf714c7cf65c48598bbef28b904c74ad4f88927ea96',
    'qh3-terminal-budget-independent-review-next-dev/root-option-B-handoff-r1.json': '44506676d84f18fa16344cde4e55855e419a8828d4b7d2716ac87dd1af48ae31',
    'qh4-provider-window-root-source-decision-r1.json': 'a3c150f9ab1fc0eed4a7b6e5ab0bfcfcef3fc3d7d08c74028564421e7a793eb6',
}
for rel, expected in extra.items():
    assert sha(WORK/rel) == expected, rel
    assert rel not in external or external[rel] == expected
    external[rel] = expected
for path in NEW.rglob('*.py'):
    ast.parse(path.read_text(encoding='utf-8'))
files = {p.relative_to(NEW).as_posix(): sha(p) for p in sorted(NEW.rglob('*')) if p.is_file()}
handoff = dict(schema='qwen-three-hour-independent-audit-R6-source-handoff-v1',
    status='FROZEN_SOURCE_ONLY_NOT_READY_PENDING_INDEPENDENT_PEER', revision=6,
    files_sha256=files, external_refs_sha256=external, external_refs_origin='WORK-relative; normalized, no leading work prefix',
    runtime='audit_final.py', test_entrypoints=['test_audit_contracts.py','test_csv_role_contracts.py'],
    prepared_method_count=30, prepared_method_counts_by_entrypoint=[28,2], prepared_methods=all_methods,
    old28_method_AST_exact=True, old_remaining_method_only_invalid_fixture_rebased=True,
    all_old_assertion_AST_exact=True, whole_R5_module_inverse_exact=True, whole_test_module_inverse_exact=True,
    numerical_R4_CSV_ANYTIME_formulas_changed=False, HTTP_usage_source_resource_or_quality_gates_weakened=False,
    task_seconds_each=4800, common_seconds=10800, derived_task_admission_margin_seconds=270,
    actual_imports=0, actual_tests=0, actual_fits=0, actual_API=0, actual_data_truth_prediction_reads=0,
    actual_PID_scans=0, actual_experiment_clock=None, actual_READY=None)
write_json(NEW/'source-handoff.json', handoff)
for rel, expected in old_hand['files_sha256'].items():
    assert sha(OLD/rel) == expected
print(json.dumps(dict(handoff=str(NEW/'source-handoff.json'), handoff_sha256=sha(NEW/'source-handoff.json'),
    runtime_sha256=sha(NEW/'audit_final.py'), test_sha256=sha(NEW/'test_audit_contracts.py'),
    local_pins=len(files), external_pins=len(external), prepared=30, executed=0)))
