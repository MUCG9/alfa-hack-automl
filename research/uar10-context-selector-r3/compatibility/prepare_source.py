"""Two test-helper inverses. Pure AST metadata; no candidate imports or unittest."""
from pathlib import Path
import ast
import copy
import hashlib
import json
import textwrap

HERE=Path(__file__).resolve().parent;WORK=HERE.parent;BASE=WORK/'alfa-hack-automl'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(node):return ast.dump(node,include_attributes=False)
def write(name,text):
    path=HERE/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')

RECORDER='''class _Recorded(ast.NodeTransformer):
    def __init__(self):self.consumed={}
    def record(self,node):
        key=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
        self.consumed[key]=self.consumed.get(key,0)+1
    def visit(self,node):
        before=ast.parse(ast.unparse(node)).body[0] if isinstance(node,ast.stmt) else node
        key=hashlib.sha256(ast.dump(before,include_attributes=False).encode()).hexdigest()
        result=super().visit(node)
        if result is None or type(result) is list:self.consumed[key]=self.consumed.get(key,0)+1
        return result
'''
RUNNER='''class _Selector(_Recorded):
    def visit_FunctionDef(self,node):
        if node.name=='_selector_cache_job':return None
        return self.generic_visit(node)
    def visit_Assign(self,node):
        if any(isinstance(n,ast.Name) and n.id in {'_SELECTOR_IMPORTANCE_CACHE','cache_token'} for n in node.targets):return None
        return self.generic_visit(node)
    def visit_Expr(self,node):
        call=node.value
        if isinstance(call,ast.Call):
            if isinstance(call.func,ast.Name) and call.func.id=='_selector_cache_job':return None
            if isinstance(call.func,ast.Attribute):
                if isinstance(call.func.value,ast.Name) and call.func.value.id=='_SELECTOR_IMPORTANCE_CACHE' and call.func.attr=='reset':return None
                if call.func.attr=='add_argument' and call.args and isinstance(call.args[0],ast.Constant) and call.args[0].value=='--selector-importance-cache':return None
        return self.generic_visit(node)
'''
WORKER='''class _Selector(_Recorded):
    def visit_ImportFrom(self,node):
        if node.module=='automl.execution.feature_engineering.importance_cache':return None
        return self.generic_visit(node)
    def visit_Assign(self,node):
        if any(isinstance(n,ast.Name) and n.id in {'cache_enabled','importance_cache'} for n in node.targets):return None
        return self.generic_visit(node)
    def visit_If(self,node):
        if ast.unparse(node.test) in {'type(cache_enabled) is not bool','importance_cache is not None'}:return None
        return self.generic_visit(node)
    def visit_FunctionDef(self,node):
        if node.name=='fit_on_rows' and node.args.args and node.args.args[-1].arg=='cache_scope':
            self.record(node.args)
            node.args.args.pop();node.args.defaults.pop()
        return self.generic_visit(node)
    def visit_Call(self,node):
        if isinstance(node.func,ast.Name) and node.func.id=='fit_on_rows':
            for keyword in list(node.keywords):
                if keyword.arg=='cache_scope':self.record(keyword);node.keywords.remove(keyword)
        return self.generic_visit(node)
'''
reviewed=WORK/'fitting-context-selector-combined-next-dev/prepare_source.py'
assert sha(reviewed)=='cf8cdb8761607310d4194924258ee48f55ca02a25b818c0a80ee560646720878'
reviewed_text=reviewed.read_text('utf-8-sig')
context_node=next(n for n in ast.parse(reviewed_text).body if isinstance(n,ast.ClassDef) and n.name=='ContextOff')
CONTEXT=ast.get_source_segment(reviewed_text,context_node)


def helper(name,kind,markers,expected=None):
    source=RECORDER+'\n'+(RUNNER if kind=='runner' else WORKER)
    if kind=='runner':source+='\n'+CONTEXT+'\nclass _Context(_Recorded,ContextOff):pass\n'
    action="context=_Context();result=context.visit(result);counts={'selector':selector.consumed,'context':context.consumed}" if kind=='runner' else "counts={'selector':selector.consumed}"
    body=f'''def _{name}(tree):
    """Normalize exact reviewed independent layers before the OLD golden proof.

    Work on a private AST; validate every consumed shape/count before returning.
    A modified same-name helper/If/args/hook cannot be silently discarded.
    Unrelated nodes remain for the unchanged independent old witness to reject.
    """
    markers={set(markers)!r}
    def names(node):
        return {{v for n in ast.walk(node) for v in ([n.id] if isinstance(n,ast.Name)
            else [n.name] if isinstance(n,(ast.FunctionDef,ast.ClassDef,ast.alias))
            else [n.arg] if isinstance(n,(ast.arg,ast.keyword)) else [])}}
    if not names(tree)&markers:return tree
'''+textwrap.indent(source,'    ')+f'''
    result=ast.parse(ast.unparse(tree))
    selector=_Selector();result=selector.visit(result)
    {action}
'''
    if expected is None:return body+'    return result,counts\n'
    return body+f'''    if counts!={expected!r}:raise ValueError('reviewed_composed_AST_shape_or_count_changed')
    if names(result)&markers:raise ValueError('unreviewed_or_duplicate_composed_AST_scaffold')
    return result
'''


pairs={
 'composed_runner_off':dict(kind='runner',base=WORK/'fit-context-gateway-next-dev/source-evidence/base/runner.py',
     current=WORK/'fitting-context-selector-combined-next-dev/candidate/src/automl/search/runner.py',
     base_sha='12091e5a3eb30744fb135fbd47d7a70ceddcf6c48c57fa9074def27e9cd4a4df',
     current_sha='7f98647af4dc720f3895fb551edc25efb6f18ab53c4b87bd0d7f854c09a4af96',
     markers=['_FITTING_INITIAL_AUTHORITY','_fitting_context_initial_options','prepared_fitting','_SELECTOR_IMPORTANCE_CACHE','_selector_cache_job']),
 'composed_worker_off':dict(kind='worker',base=WORK/'fitting-context-selector-root-integration-r1/before/src/automl/execution/worker.py',
     current=WORK/'fitting-context-selector-combined-next-dev/candidate/src/automl/execution/worker.py',
     base_sha='de75742f1cdbe18bf1a1280d16637116cdf76f53a12cab53496df75f3fefb477',
     current_sha='e6625c7dfb707ca76aa04b77d80602800700d98f748c605cf8a06137cd2397ac',
     markers=['TeacherImportanceCache','cache_enabled','importance_cache','cache_scope'])}
generated={};reports={}
for name,row in pairs.items():
    assert sha(row['base'])==row['base_sha'] and sha(row['current'])==row['current_sha']
    old=ast.parse(row['base'].read_bytes());current=ast.parse(row['current'].read_bytes())
    namespace=dict(ast=ast,hashlib=hashlib)
    # ONLY pure AST helper definitions are evaluated, like independent721bae.
    exec(compile(helper(name,row['kind'],row['markers']),'<AST-metadata-discovery>','exec'),namespace)
    result,counts=namespace['_'+name](copy.deepcopy(current));assert dump(result)==dump(old)
    generated[name]=helper(name,row['kind'],row['markers'],counts)
    exec(compile(generated[name],'<AST-metadata-strict-validation>','exec'),namespace)
    normalize=namespace['_'+name]
    assert dump(normalize(copy.deepcopy(current)))==dump(old)
    assert dump(normalize(copy.deepcopy(old)))==dump(old)
    negatives=[]
    def rejected(value,label):
        try:accepted=dump(normalize(value))==dump(old)
        except (ValueError,AttributeError,IndexError,TypeError):accepted=False
        assert not accepted,label
        negatives.append(label)
    altered=copy.deepcopy(current)
    if row['kind']=='runner':
        target=next(n for n in altered.body if isinstance(n,ast.FunctionDef) and n.name=='_selector_cache_job')
        target.body.append(ast.Pass())
    else:
        target=next(n for n in ast.walk(altered) if isinstance(n,ast.If) and ast.unparse(n.test)=='type(cache_enabled) is not bool')
        target.body.append(ast.Pass())
    rejected(altered,'modified_recognized_scaffold_rejected')
    duplicate=copy.deepcopy(current)
    target=next(n for n in duplicate.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_SELECTOR_IMPORTANCE_CACHE' for t in n.targets)) if row['kind']=='runner' else next(n for n in duplicate.body if isinstance(n,ast.ImportFrom) and n.module=='automl.execution.feature_engineering.importance_cache')
    duplicate.body.append(copy.deepcopy(target));rejected(duplicate,'duplicate_scaffold_rejected')
    partial=copy.deepcopy(current)
    if row['kind']=='runner':partial.body=[n for n in partial.body if not (isinstance(n,ast.FunctionDef) and n.name=='_selector_cache_job')]
    else:partial.body=[n for n in partial.body if not (isinstance(n,ast.ImportFrom) and n.module=='automl.execution.feature_engineering.importance_cache')]
    rejected(partial,'partial_scaffold_rejected')
    unknown=copy.deepcopy(current);unknown.body.extend(ast.parse('def unrelated_unreviewed():\n    return 19\n').body)
    rejected(unknown,'unknown_addition_not_hidden_from_old_witness')
    numerical=copy.deepcopy(current)
    if row['kind']=='runner':
        target=next(n for n in numerical.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='THREADS' for t in n.targets))
        number=next(n for n in ast.walk(target) if isinstance(n,ast.Constant) and type(n.value) is int and n.value>1)
    else:number=next(n for n in ast.walk(numerical) if isinstance(n,ast.Constant) and type(n.value) is int and n.value==73)
    number.value+=1;rejected(numerical,'numerical_change_not_hidden_from_old_witness')
    reports[name]=dict(base_path=row['base'].relative_to(WORK).as_posix(),base_sha256=row['base_sha'],current_sha256=row['current_sha'],
        strict_consumed_AST_shape_counts=counts,whole_module_AST_restores_original=True,original_base_unchanged=True,
        numerical_functions_not_replaced=True,private_AST_only_until_all_shapes_validated=True,negative_source_metadata_fixtures=negatives)

hpo_path=BASE/'tests/test_uar_hpo_fair_reserve.py';loss_path=BASE/'tests/test_uar_loss_backend.py'
hpo=hpo_path.read_text('utf-8-sig');loss=loss_path.read_text('utf-8-sig')
assert sha(hpo_path)=='8bfe59fa6bd0114c3867e1ef426f1f155cd83fbe3ba90709a332046b903d5643'
assert sha(loss_path)=='b882f673692ef758f3505c456a98d5883d25a37a2d75f3e611c3958b9aa58a7f'
assert hpo.count('    tree = ast.parse(text)')==1
hpo=hpo.replace('def projected_ast(text, is_runner):',generated['composed_runner_off']+'\n\ndef projected_ast(text, is_runner):',1)
hpo=hpo.replace('    tree = ast.parse(text)','    tree = ast.parse(text)\n    if is_runner:tree = _composed_runner_off(tree)',1)
loss=loss.replace('class LegacyOffProjection(ast.NodeTransformer):',generated['composed_worker_off']+'\n\nclass LegacyOffProjection(ast.NodeTransformer):',1)
anchor="    loss_names={'LossProfile','LOSS_PROFILES','loss_profile_catalog','resolve_loss_profile',\n                'validate_loss_profiles','loss_profile_fit_receipt'}"
assert loss.count(anchor)==1
loss=loss.replace(anchor,anchor+"\n    def visit_Module(self,node):\n        return self.generic_visit(_composed_worker_off(node))",1)
write('candidate/tests/test_uar_hpo_fair_reserve.py',hpo);write('candidate/tests/test_uar_loss_backend.py',loss)
for text in [hpo,loss]:compile(text,'<test-helper-source-only>','exec')
write('normalizer-source-proof.json',json.dumps(dict(schema='composed-legacy-test-helper-source-proof-v1',status='SOURCE_ONLY_NOT_EXECUTED',
    projections=reports,ContextOff_body_exact_reviewed_cf8=True,pure_AST_metadata_evaluation_only=True,
    unittest_methods_executed=0,candidate_imports=0,fits=0,API_calls=0,data_arrays_PID_Git_clock=0),indent=2)+'\n')
print(json.dumps(dict(source_prepared=True,tests={p.name:sha(p) for p in (HERE/'candidate/tests').glob('*.py')},runtime=False)))
