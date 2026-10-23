"""Source-only AST/compile/hash/patch receipt builder. Never imports the overlay."""
import ast
import copy
import difflib
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent;WORK=HERE.parent
REVISION='r3'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(value):return ast.dump(value,include_attributes=False)
def write(name,value):
    path=HERE/(Path(name).stem+'-'+REVISION+Path(name).suffix)
    with path.open('x',encoding='utf-8',newline='\n') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    return sha(path)

files=['src/automl/search/class_support.py','src/automl/search/class_support_screen.py','src/automl/search/runner.py','tests/test_class_support_bounded.py']
inputs=[p.relative_to(WORK).as_posix() for p in sorted((WORK/'class-support-bounded-next-dev').rglob('*')) if p.is_file()]
inputs+=['m3dev/src/automl/search/runner.py','m3dev/src/automl/search/policy.py','m3dev/src/automl/infrastructure/llm_gateway.py']
input_hashes={name:sha(WORK/name) for name in inputs}
source_hashes={name:sha(HERE/name) for name in files}
trees={name:ast.parse((HERE/name).read_text(encoding='utf-8')) for name in files}
for name in files:compile((HERE/name).read_text(encoding='utf-8'),str(HERE/name),'exec')
old=ast.parse((WORK/'m3dev/src/automl/search/runner.py').read_text(encoding='utf-8'))
new=trees['src/automl/search/runner.py']
old_funcs={n.name:n for n in old.body if isinstance(n,ast.FunctionDef)}
new_funcs={n.name:n for n in new.body if isinstance(n,ast.FunctionDef)}
changed=[name for name,node in old_funcs.items() if dump(node)!=dump(new_funcs[name])]
assert set(changed)=={'planner_context','llm_plan','_main','solve_single'},changed
unchanged=[name for name in old_funcs if name not in changed]
old_llm_call=next(n for n in ast.walk(old_funcs['solve_single']) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='llm_plan')
old_timeout=next(k.value for k in old_llm_call.keywords if k.arg=='timeout')

class DefaultOffProjection(ast.NodeTransformer):
    """Remove only declared opt-in hooks, then compare the entire runner AST."""
    def visit_ImportFrom(self,node):
        return None if node.module=='automl.search.class_support' else node
    def visit_FunctionDef(self,node):
        if node.name=='bounded_context_request':return None
        if node.name=='planner_context':
            # New context assignment is the exact old returned dict, followed
            # solely by opt-in guard and return. Do not replace unchecked code.
            assert isinstance(node.body[-1],ast.Return) and isinstance(node.body[-1].value,ast.Name) and node.body[-1].value.id=='context'
            assert isinstance(node.body[-2],ast.If) and dump(node.body[-2].test)==dump(ast.parse('class_support is not None',mode='eval').body)
            assign=node.body[-3];assert isinstance(assign,ast.Assign) and assign.targets[0].id=='context'
            node.body=node.body[:-3]+[ast.Return(value=assign.value)]
            assert len(node.args.args)==len(old_funcs[node.name].args.args)+5
            node.args=copy.deepcopy(old_funcs[node.name].args)
            return node
        if node.name=='llm_plan':
            guard=node.body[2];assert isinstance(guard,ast.If) and dump(guard.test)==dump(ast.parse('class_support_budget is None',mode='eval').body)
            node.body=node.body[:2]+guard.body+node.body[3:]
            node.args=copy.deepcopy(old_funcs[node.name].args)
            return node
        return self.generic_visit(node)
    def visit_Assign(self,node):
        names={n.id for n in node.targets if isinstance(n,ast.Name)}
        if names & {'class_support','protected_signature','protected_artifact','context_budget','planner_timeout'}:return None
        return self.generic_visit(node)
    def visit_If(self,node):
        if dump(node.test)==dump(ast.parse("getattr(args,'class_support_context',False)",mode='eval').body):return None
        if dump(node.test)==dump(ast.parse('context_budget is None',mode='eval').body):return [self.visit(n) for n in node.body]
        return self.generic_visit(node)
    def visit_Expr(self,node):
        if isinstance(node.value,ast.Call) and node.value.args and isinstance(node.value.args[0],ast.Constant) and node.value.args[0].value=='--class-support-context':return None
        return self.generic_visit(node)
    def visit_Call(self,node):
        if isinstance(node.func,ast.Name):
            if node.func.id=='planner_context':
                node.keywords=[k for k in node.keywords if k.arg not in {'class_support','primary_context_paths','protected_control_signature','support_preparation_budget','context_receipt_path'}]
            elif node.func.id=='llm_plan':
                node.keywords=[k for k in node.keywords if k.arg!='class_support_budget']
                for item in node.keywords:
                    if item.arg=='timeout' and isinstance(item.value,ast.Name) and item.value.id=='planner_timeout':item.value=copy.deepcopy(old_timeout)
        return self.generic_visit(node)

projected=DefaultOffProjection().visit(copy.deepcopy(new));ast.fix_missing_locations(projected)
assert dump(projected)==dump(old),'Projected default-OFF runner differs outside declared hooks'

# Static invariants only: candidate modules and test methods are never imported.
previous=WORK/'class-support-bounded-next-dev'
old_helper=ast.parse((previous/files[0]).read_text(encoding='utf-8'))
new_helper=trees[files[0]]
def without_support_validation(tree):
    return ast.Module(body=[n for n in tree.body if not isinstance(n,ast.FunctionDef) or n.name not in {'add_support_context','validate_support_packet'}],type_ignores=[])
assert dump(without_support_validation(old_helper))==dump(without_support_validation(new_helper))
assert (previous/files[2]).read_bytes()==(HERE/files[2]).read_bytes()
old_screen=ast.parse((previous/files[1]).read_text(encoding='utf-8'))
def views_segment(tree):
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='prepare_generation_pair')
    start=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='off_receipt')
    return ast.Module(body=fn.body[start:-1],type_ignores=[])
assert dump(views_segment(old_screen))==dump(views_segment(trees[files[1]]))
old_test_text=(previous/files[-1]).read_text(encoding='utf-8');new_test_text=(HERE/files[-1]).read_text(encoding='utf-8')
old_methods={n.name:ast.get_source_segment(old_test_text,n) for n in ast.walk(ast.parse(old_test_text)) if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')}
new_methods={n.name:ast.get_source_segment(new_test_text,n) for n in ast.walk(trees[files[-1]]) if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')}
assert len(old_methods)==19 and len(new_methods)==24
assert all(new_methods.get(name)==body for name,body in old_methods.items())
new_methods_names=sorted(set(new_methods)-set(old_methods))
patch=[];incremental=[]
for name in files:
    baseline=WORK/'m3dev'/name
    before=baseline.read_text(encoding='utf-8').splitlines(keepends=True) if name==files[2] else []
    after=(HERE/name).read_text(encoding='utf-8').splitlines(keepends=True)
    patch.extend(difflib.unified_diff(before,after,fromfile='a/'+name if before else '/dev/null',tofile='b/'+name))
    incremental.extend(difflib.unified_diff((previous/name).read_text(encoding='utf-8').splitlines(keepends=True),after,fromfile='a/'+name,tofile='b/'+name))
patch_path=HERE/'bounded-class-support-r3.patch';delta_path=HERE/'r2-to-r3.patch'
for path,lines in [(patch_path,patch),(delta_path,incremental)]:
    with path.open('x',encoding='utf-8',newline='\n') as stream:stream.writelines(lines)
protocol=copy.deepcopy(json.loads((previous/'protocol-r2.json').read_text(encoding='utf-8')))
protocol.update(revision='r3',status='prospective_source_only_no_clock_or_calls',
    source_basis='Exact actual m3 runner, byte-identical to bounded R2 runner; only shared external-packet validation and screen budget scope revised.',
    supersedes_source_only_R2_protocol_sha256=sha(previous/'protocol-r2.json'),
    source_review_trigger={'path':'class-support-bounded-next-dev/independent-review-r2.json','sha256':sha(previous/'independent-review-r2.json')},
    repair='Exact native type/cardinality checks of10-field support, K-count maps and <=K class lists before support sum/set/any, bounded JSON before packet copy; one validator shared by screen/helper. Valid packet view construction unchanged.')
protocol['resource_meaning'].update(
    preparation_budget_scope='prepare_generation_pair accepts an optional same PreparationBudget used before screen for support and capture. If omitted, local receipt explicitly covers only screen entry onward. Earlier support/capture still belongs to the same future30s parent/600s clock; no free5s reset or inferred IO charge.',
    future_preparation_parent_enforcement='The future harness must independently own/enforce30s/512MiB/1thread and account support/capture/hashes/rechecks/serialization/receipts/failed preparation. Shared5s/64MiB helper checks are cooperative and do not replace the parent.')
matched=protocol['matched_generation'];matched.pop('output_tokens_each',None)
matched.update(max_output_tokens_per_HTTP_attempt=8192,maximum_HTTP_attempts_per_logical_call=3,
    nominal_completion_token_ceiling_per_arm_across_attempts=24576,
    token_accounting='8192 is per HTTP attempt, not aggregate per logical call. Retry usage may be unavailable; preserve unknown usage, never impute zero. No new aggregate provider-token budget is invented.',
    timeout_accounting='120s is one logical request window shared by all existing retry attempts; it is not3*120s.',
    runtime_flag_defaults_are_not_screen_limits={'initial_max_output_tokens':8192,'initial_timeout_seconds':240,'followup_max_output_tokens':16384,'followup_timeout_seconds':300,'existing_parse_plans_candidate_bound':3},
    future_screen_harness_must_explicitly_enforce={'one_logical_call_each':1,'max_output_tokens_each_HTTP_attempt':8192,'logical_request_timeout_seconds_each':120,'HTTP_attempt_cap_each':3,'admitted_candidates_each':2,'pair_parent_seconds':600},
    future_harness_implemented_here=False,
    common_accounting='30s shared preparation including all prior support/capture +240s maximum logical requests +330s setup/audit/cleanup reserve=600s; actual total remains authoritative. No reset or borrowed old time.')
matched['freeze_before_first_call'][0]='Actual current T7 exec65008/source733 terminal plus fresh exact owned/bootstrap/preparer closure and canonical lock proof; older T6 closure is insufficient.'
protocol['current_restrictions']=dict(actual_current_T7_exec_session=65008,active_T7_immutable_count=733,
    actual_T7_sources_or_artifacts_modified=False,active_T7_data_or_outcomes_loaded=False,
    new_research_clock_assigned=False,tests_prepared=24,tests_executed=0,runtime_imports=0,fits=0,API_calls=0)
protocol['input_sources_sha256']=input_hashes;protocol['new_sources_sha256']=source_hashes
protocol_sha=write('protocol.json',protocol)
proof_sha=write('static-proof.json',dict(status='AST_and_compile_only_not_test_execution',builder_sha256=sha(Path(__file__)),
    sources_sha256=source_hashes,input_sources_sha256=input_hashes,compiled_sources=files,
    original19test_methods_preserved_verbatim=True,additional_test_methods_prepared_not_run=new_methods_names,
    test_methods_count=24,tests_executed=0,runtime_imports=0,fits=0,API_calls=0,
    runner_byte_identical_to_R2=True,unchanged_original_functions_AST=unchanged,
    changed_original_functions=changed,entire_runner_AST_equals_actual_m3_after_removing_only_declared_optin_hooks=True,
    original_prompt_literals_and_all_other_global_AST_unchanged=True,
    helper_AST_except_add_support_context_and_new_validator_unchanged=True,
    valid_input_screen_view_construction_AST_unchanged=True,
    limits='Static structural proof only. No actual helper call, test, runtime import, request, fit or gate was executed; valid-input equality is source evidence, not a dynamic parity pass.'))
for name,digest in input_hashes.items():assert sha(WORK/name)==digest,'An input changed during source preparation'
handoff=write('source-handoff.json',dict(status='source_frozen_for_root_review_not_executed',revision='r3',
    new_sources_sha256=source_hashes,protocol_sha256=protocol_sha,static_proof_sha256=proof_sha,
    cumulative_patch_sha256=sha(patch_path),R2_incremental_patch_sha256=sha(delta_path),builder_sha256=sha(Path(__file__)),
    input_sources_sha256=input_hashes,tests_prepared=24,original19_preserved_verbatim=True,
    tests_executed=0,runtime_imports=0,fits=0,API_calls=0,active_T7_inputs_or_outcomes_read=False,
    existing_R2_files_unchanged=True,active_T7_source733_unchanged=True,next_clock_assigned=False,
    ready_for_execution=False,next_execution_prerequisite='Root source review/publication, separately bounded technical checks, actual current T7 terminal/fresh ownership+lock closure and an explicitly reviewed future screen harness/call config. No actual future clock assigned.'))
print(json.dumps(dict(handoff_sha256=handoff,protocol_sha256=protocol_sha,proof_sha256=proof_sha,
    cumulative_patch_sha256=sha(patch_path),R2_incremental_patch_sha256=sha(delta_path),source_sha256=source_hashes,
    test_methods_prepared_not_run=24),ensure_ascii=False))
