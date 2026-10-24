"""Freeze two test-helper sources using only SHA/AST metadata, never tests."""
from pathlib import Path
import ast
import copy
import difflib
import hashlib
import json

HERE=Path(__file__).resolve().parent; WORK=HERE.parent
BASE=WORK/'fitting-context-selector-combined-next-dev'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(v):return ast.dump(v,include_attributes=False)
def save(name,value):
    p=HERE/name
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
replacements={}
proof={}
for filename,oldsha,newsha,helper in [
 ('test_uar_hpo_fair_reserve.py','8bfe59fa6bd0114c3867e1ef426f1f155cd83fbe3ba90709a332046b903d5643','b51ce05a2533515647ec04f521828c6c23e223bf3d4dbbfc287191f05eaa7252','_composed_runner_off'),
 ('test_uar_loss_backend.py','b882f673692ef758f3505c456a98d5883d25a37a2d75f3e611c3958b9aa58a7f','2240cef09e932130cd3d5350b02e2f5260b90f5b54259168695aa0936cced787','_composed_worker_off')]:
    rel='tests/'+filename
    before=BASE/'candidate'/rel; after=HERE/'candidate'/rel
    assert sha(before)==oldsha and sha(after)==newsha
    prior=HERE/'source-evidence/base'/filename
    prior.parent.mkdir(parents=True,exist_ok=True);prior.write_bytes(before.read_bytes())
    old=ast.parse(before.read_bytes()); new=ast.parse(after.read_bytes()); reverse=copy.deepcopy(new)
    assert len([n for n in reverse.body if isinstance(n,ast.FunctionDef) and n.name==helper])==1
    reverse.body=[n for n in reverse.body if not(isinstance(n,ast.FunctionDef) and n.name==helper)]
    if filename.startswith('test_uar_hpo'):
        target=next(n for n in reverse.body if isinstance(n,ast.FunctionDef) and n.name=='projected_ast')
        expected=ast.parse('if is_runner:tree = _composed_runner_off(tree)').body[0]
        assert dump(target.body[1])==dump(expected);target.body.pop(1)
    else:
        target=next(n for n in reverse.body if isinstance(n,ast.ClassDef) and n.name=='LegacyOffProjection')
        extra=[n for n in target.body if isinstance(n,ast.FunctionDef) and n.name=='visit_Module']
        expected=ast.parse('def visit_Module(self,node):\n return self.generic_visit(_composed_worker_off(node))').body[0]
        assert len(extra)==1 and dump(extra[0])==dump(expected)
        target.body=[n for n in target.body if n not in extra]
    assert dump(reverse)==dump(old),'whole_old_test_module_inverse_failed'
    methods=lambda t:{c.name+'.'+n.name:hashlib.sha256(dump(n).encode()).hexdigest() for c in t.body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')}
    assert methods(old)==methods(new)
    defs=[n for n in new.body if isinstance(n,ast.FunctionDef) and n.name==helper]
    defs += [n for n in new.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in {'projected_ast','LegacyOffProjection'}]
    namespace={'ast':ast,'hashlib':hashlib}
    # ONLY pure source-AST definitions: no imports, test methods, candidate code.
    exec(compile(ast.Module(body=defs,type_ignores=[]),'<pure-source-AST-projection>','exec'),namespace)
    if filename.startswith('test_uar_hpo'):
        source=(BASE/'candidate/src/automl/search/runner.py').read_text('utf-8-sig')
        golden=hashlib.sha256(namespace['projected_ast'](source,True).encode()).hexdigest()
        assert golden=='877b5cd74b661d921cb1a12bca0b0b554caf943ee1c2e9b80adcb5e467097f7c'
    else:
        source=(BASE/'candidate/src/automl/execution/worker.py').read_text('utf-8-sig')
        golden=hashlib.sha256(dump(namespace['LegacyOffProjection']().visit(ast.parse(source))).encode()).hexdigest()
        assert golden=='ea1ba7f6270ced919a4f04ef50b80725af86068722a38573ab3a61fb3b9b324e'
    compile(after.read_bytes(),str(after),'exec')
    replacements[rel]={'before_sha256':oldsha,'after_sha256':newsha,'candidate_path':'candidate/'+rel}
    proof[rel]={'whole_old_module_AST_restored_by_removing_only_new_helper_and_hook':True,
        'old_methods_assertions_and_literal_witnesses_AST_exact':True,'method_count':len(methods(new)),
        'methods_AST_sha256':methods(new),'unchanged_independent_golden_after_composed_OFF_inverse':golden}
    (HERE/(filename+'.patch')).write_text(''.join(difflib.unified_diff(before.read_text('utf-8-sig').splitlines(True),after.read_text('utf-8-sig').splitlines(True),fromfile=rel,tofile=rel)),encoding='utf-8')
assert sum(v['method_count'] for v in proof.values())==35
save('source-proof.json',{'schema':'combined-legacy-test-compatibility-proof-v1','status':'SOURCE_ONLY_NOT_EXECUTED','tests':proof,
    'unittest_methods_executed':0,'candidate_imports':0,'runtime_files_changed':0,'pure_AST_metadata_only':True,
    'normalizer_negative_source_cases':'normalizer-source-proof.json','counts':{'source_scripts':66,'source_checks':704,'canonical_python':183,'flat_members':78,'exact':23,'mapped':174}})
save('protocol.json',{'schema':'combined-legacy-test-compatibility-protocol-v1','status':'SOURCE_ONLY_FROZEN_NOT_READY',
    'scope':'Exactly two test helpers normalize fingerprinted reviewed context/selector layers before unchanged independent old golden proofs.',
    'strictness':'Private AST projection checks exact consumed-node SHA/counts. Modified, duplicate or partial recognized layers reject. Unknown and numerical changes survive for unchanged witnesses to reject.',
    'runtime_delta':None,'new_test_methods':0,'old_method_count':35,'old_assertions_and_literals_retained':True,
    'no_skip_no_new_exclusion_no_new_golden':True,'actual_clock':None,'runtime_executions':0})
(HERE/'README.txt').write_text('SOURCE ONLY. Exactly two existing test helpers; all 35 original test methods, assertions and literal golden witnesses remain AST exact. No runtime files changed. Exact consumed-node shape/count validation protects the composed OFF inverse. Source-AST metadata checks are not unittest execution. Root must integrate only these two files and instantiate the exact reviewed UAR10 R3 overlay; READY and actual clock are not assigned here. Counts remain 66/704 source, 183 canonical Python, 78 flat, 23 exact and 174 mapped. Historical preparation errors remain in source-evidence.\n',encoding='utf-8')
refs=[
 'fitting-context-selector-combined-next-dev/source-handoff.json',
 'fitting-context-selector-combined-independent-review-r1.json',
 'fitting-context-selector-combined-next-dev/prepare_source.py',
 'fitting-context-selector-combined-next-dev/composition-proof.json',
 'selector-cache-current-port-next-dev/prepare_source.py',
 'selector-cache-current-port-next-dev/source-delta-proof.json',
 'fit-context-gateway-next-dev/source-evidence/base/runner.py',
 'fitting-context-selector-root-integration-r1/before/src/automl/execution/worker.py',
 'combined-source-legacy-AST-compatibility-finding-r1.json',
 'combined-source-legacy-AST-independent-confirmation-r1.json',
 'uar10-context-selector-gate-next-dev-r2/source-handoff.json',
 'uar10-context-selector-gate-independent-review-r2.json']
external={r:sha(WORK/r) for r in refs}
files={p.relative_to(HERE).as_posix():sha(p) for p in sorted(HERE.rglob('*')) if p.is_file() and p.name!='source-handoff.json'}
save('source-handoff.json',{'schema':'combined-legacy-test-compatibility-source-handoff-v1','status':'SOURCE_ONLY_FROZEN_NOT_READY',
    'canonical_replacements':replacements,'files_sha256':files,'external_refs_sha256':external,
    'runtime_changes':0,'prepared_methods':35,'unittest_methods_executed':0,'new_clock':None,'no_READY_grant':True})
print(json.dumps({'handoff_sha256':sha(HERE/'source-handoff.json'),'canonical_replacements':replacements,'local_pins':len(files),'external_pins':len(external),'runtime':False}))
