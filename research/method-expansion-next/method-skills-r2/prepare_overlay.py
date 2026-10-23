"""Create an opt-in source overlay and default-OFF AST proof; no imports/fits."""
from pathlib import Path
import ast,difflib,hashlib,json
w=Path(__file__).resolve().parent.parent;d=Path(__file__).resolve().parent
base=w/'m3dev/src/automl/search/runner.py'
original=base.read_text('utf-8')
assert hashlib.sha256(base.read_bytes()).hexdigest()=='e204a9eec98e7f3fa7799470cc453e8f4a3887247e8d102b5d0bb834f88c2ef3'
marker="    parser.add_argument('--planner-mode',choices=['baseline','staged'],default='baseline')"
assert original.count(marker)==1
changed=original.replace(marker,marker+"\n    parser.add_argument('--method-skills',action='store_true',help='Opt-in bounded instructions for implemented task-appropriate tools; does not change portfolio')")
for anchor,phase,remaining in [
    ('        content,usage=request_json(SYSTEM_PROMPT+STAGED_PROMPT,context,max_output=8192,','initial','deadline-time.monotonic()'),
    ("            plans,usage=llm_plan(context,runs,timeout=max(5,min(300,remaining-reserve-30)),prompt_mode=getattr(args,'planner_mode','baseline'))",'followup','deadline-time.monotonic()')]:
    assert changed.count(anchor)==1
    indent=anchor[:len(anchor)-len(anchor.lstrip())]
    block=indent+"if getattr(args,'method_skills',False):\n"+indent+"    from automl.search.method_skills import attach_method_skills\n"+indent+"    from automl.execution.api import CAPABILITIES\n"+indent+f"    context,knowledge_receipt=attach_method_skills(context,spec,CAPABILITIES,{remaining},reserve)\n"+indent+f"    atomic_json(runs/'method-skills-{phase}.json',knowledge_receipt)\n"
    changed=changed.replace(anchor,block+anchor)
class Off(ast.NodeTransformer):
    def visit_Expr(self,node):
        if isinstance(node.value,ast.Call) and node.value.args and isinstance(node.value.args[0],ast.Constant) and node.value.args[0].value=='--method-skills':return None
        return self.generic_visit(node)
    def visit_If(self,node):
        if ast.unparse(node.test)=="getattr(args, 'method_skills', False)":return []
        return self.generic_visit(node)
assert ast.dump(Off().visit(ast.parse(changed)),include_attributes=False)==ast.dump(ast.parse(original),include_attributes=False)
target=d/'src/automl/search/runner.py';assert not target.exists();target.parent.mkdir(parents=True,exist_ok=True);target.write_text(changed,encoding='utf-8')
for p in [target,d/'src/automl/search/method_skills.py',d/'tests/test_method_skills.py']:compile(p.read_text('utf-8'),p.name,'exec')
patch=''.join(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),fromfile='a/src/automl/search/runner.py',tofile='b/src/automl/search/runner.py'))
(d/'runner.patch').write_text(patch,encoding='utf-8')
pins={p.relative_to(d).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [target,d/'src/automl/search/method_skills.py',d/'tests/test_method_skills.py']}
(d/'source-handoff.json').write_text(json.dumps(dict(status='source_only_optin_overlay_not_executed',
    source_sha256=pins,default_OFF_AST_equal=True,tests_prepared=6,tests_executed=0,
    application_runtime_imports=0,fits=0,API_calls=0,archive_builds=0,clock_assigned=False,
    source_basis_sha256=hashlib.sha256(base.read_bytes()).hexdigest(),
    preserves='Metric/splits/portfolio/HPO/controls/workers/refit/CSV unchanged. New module is instruction retrieval only. No planned learner advertised as implemented.',
    future_matched_generation='Common complete-message preflight in BOTH arms, same context/config/caps; only added method_skills differs. No quality claim from valid proposals.',
    launch_ready=False),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'source_overlay_prepared':True,'default_OFF_AST_equal':True,'tests_executed':0,'fits':0,'API_calls':0}))
