"""Two test-helper projections only. Pure source/AST metadata, never test/model imports."""
from pathlib import Path
import ast
import copy
import difflib
import hashlib
import json

HERE=Path(__file__).resolve().parent;WORK=HERE.parent;BASE=WORK/'alfa-hack-automl'


def dump(node):return ast.dump(node,include_attributes=False)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def node_sha(node):return hashlib.sha256(dump(node).encode()).hexdigest()
def write(name,text):
    path=HERE/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')


def patches_between(old,current):
    """Generate fixed reviewed node patches, descending existing definitions.

    This generator is metadata only. The emitted helper knows only fixed paths,
    exact fingerprints and statement replacements; it cannot learn a new diff.
    """
    result=[]
    def patch(path,before,after):
        assert isinstance(after,ast.AST)
        if before is not None:assert isinstance(before,ast.stmt),('nonstatement replacement',path)
        result.append(dict(path=list(path),expected=node_sha(after),replacement=None if before is None else ast.unparse(before)))
    def walk(a,b,path=()):
        if dump(a)==dump(b) if isinstance(a,ast.AST) and isinstance(b,ast.AST) else a==b:return
        if isinstance(a,ast.AST) and isinstance(b,ast.AST):
            if type(a) is not type(b):patch(path,a,b);return
            for field in a._fields:walk(getattr(a,field),getattr(b,field),path+(field,))
        elif type(a) is list and type(b) is list:
            keys=lambda rows:[dump(n) if isinstance(n,ast.AST) else repr(n) for n in rows]
            for tag,i,j,k,l in difflib.SequenceMatcher(None,keys(a),keys(b),autojunk=False).get_opcodes():
                if tag=='equal':continue
                if tag=='insert':
                    for index in range(k,l):patch(path+(index,),None,b[index])
                elif tag=='replace' and j-i==l-k:
                    for left,right in zip(range(i,j),range(k,l)):walk(a[left],b[right],path+(right,))
                elif tag=='replace' and j-i==1 and l-k>1:
                    old=a[i]
                    def same_anchor(n):
                        if type(n) is not type(old):return False
                        if isinstance(n,ast.Assign):return [dump(x) for x in n.targets]==[dump(x) for x in old.targets]
                        if isinstance(n,(ast.FunctionDef,ast.ClassDef)):return n.name==old.name
                        if isinstance(n,ast.If):return dump(n.test)==dump(old.test)
                        return True
                    choices=[index for index in range(k,l) if same_anchor(b[index])]
                    if not choices:choices=[index for index in range(k,l) if any(dump(n)==dump(old) for n in ast.walk(b[index]))]
                    assert len(choices)==1,('ambiguous reviewed statement expansion',path,choices)
                    for index in range(k,l):
                        if index==choices[0]:walk(old,b[index],path+(index,))
                        else:patch(path+(index,),None,b[index])
                else:raise ValueError(('unexpected deletion/list replacement',path,tag,j-i,l-k))
        else:raise ValueError(('unexpected preexisting scalar edit',path,a,b))
    walk(old,current)
    assert result and len({tuple(r['path']) for r in result})==len(result)
    for row in result:
        assert not (row['replacement'] is not None and isinstance(resolve(current,row['path']),(ast.FunctionDef,ast.ClassDef))),row
    return result


def resolve(node,path):
    for step in path:node=node[step] if type(step) is int else getattr(node,step)
    return node


def helper(name,patches,markers):
    constant='_'+name.upper()+'_PATCHES'
    return '\n'+constant+'='+repr(patches)+'\n\n'+f'''def _{name}(tree):
    """Inverse only exact reviewed additions; old golden assertion stays independent."""
    markers={set(markers)!r}
    def names(node):
        return {{value for n in ast.walk(node) for value in
            ([n.id] if isinstance(n,ast.Name) else [n.name] if isinstance(n,(ast.FunctionDef,ast.ClassDef,ast.alias))
             else [n.arg] if isinstance(n,(ast.arg,ast.keyword)) else [])}}
    if not names(tree)&markers:return tree
    patches={constant}
    # Validate EVERY original path before changing any node. A known helper,
    # branch, argument or hook with a changed body cannot be silently removed.
    for row in patches:
        node=tree
        try:
            for step in row['path']:node=node[step] if type(step) is int else getattr(node,step)
        except (AttributeError,IndexError,TypeError) as exc:
            raise ValueError('reviewed_composed_AST_shape_changed') from exc
        if hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()!=row['expected']:
            raise ValueError('reviewed_composed_AST_node_changed')
    lookup={{tuple(row['path']):row for row in patches}}
    def rewrite(node,path=()):
        row=lookup.get(path)
        if row is not None:
            return [] if row['replacement'] is None else ast.parse(row['replacement']).body
        if isinstance(node,ast.AST):
            for field,value in ast.iter_fields(node):
                if type(value) is list:
                    output=[]
                    for index,item in enumerate(value):
                        changed=rewrite(item,path+(field,index))
                        output.extend(changed) if type(changed) is list else output.append(changed)
                    setattr(node,field,output)
                elif isinstance(value,ast.AST):
                    changed=rewrite(value,path+(field,))
                    if type(changed) is list:raise ValueError('unexpected_scalar_AST_patch')
                    setattr(node,field,changed)
        return node
    result=rewrite(tree)
    if names(result)&markers:raise ValueError('unreviewed_or_duplicate_composed_AST_scaffold')
    return result

'''


pairs={
 'composed_runner_off':dict(base=WORK/'fit-context-gateway-next-dev/source-evidence/base/runner.py',
     current=WORK/'fitting-context-selector-combined-next-dev/candidate/src/automl/search/runner.py',
     base_sha='12091e5a3eb30744fb135fbd47d7a70ceddcf6c48c57fa9074def27e9cd4a4df',
     current_sha='7f98647af4dc720f3895fb551edc25efb6f18ab53c4b87bd0d7f854c09a4af96',
     markers=['_FITTING_INITIAL_AUTHORITY','_fitting_context_initial_options','prepared_fitting','_SELECTOR_IMPORTANCE_CACHE','_selector_cache_job']),
 'composed_worker_off':dict(base=WORK/'fitting-context-selector-root-integration-r1/before/src/automl/execution/worker.py',
     current=WORK/'fitting-context-selector-combined-next-dev/candidate/src/automl/execution/worker.py',
     base_sha='de75742f1cdbe18bf1a1280d16637116cdf76f53a12cab53496df75f3fefb477',
     current_sha='e6625c7dfb707ca76aa04b77d80602800700d98f748c605cf8a06137cd2397ac',
     markers=['TeacherImportanceCache','cache_enabled','importance_cache','cache_scope'])}
reports={};generated={}
for name,row in pairs.items():
    assert sha(row['base'])==row['base_sha'] and sha(row['current'])==row['current_sha']
    old=ast.parse(row['base'].read_bytes());current=ast.parse(row['current'].read_bytes())
    patches=patches_between(old,current);generated[name]=helper(name,patches,row['markers'])
    # Evaluate ONLY pure AST helper definitions as metadata, no candidate module
    # or test class/method is imported, constructed or invoked.
    namespace=dict(ast=ast,hashlib=hashlib)
    exec(compile(generated[name],'<pure-AST-helper-metadata>','exec'),namespace)
    normalized=namespace['_'+name](copy.deepcopy(current))
    assert dump(normalized)==dump(old)
    assert dump(namespace['_'+name](copy.deepcopy(old)))==dump(old)
    checks=[]
    def rejected(tree,label):
        try:ok=dump(namespace['_'+name](tree))==dump(old)
        except (ValueError,AttributeError,IndexError,TypeError):ok=False
        assert not ok,label
        checks.append(label)
    modified=copy.deepcopy(current);target=resolve(modified,patches[0]['path'])
    if isinstance(target,ast.FunctionDef):target.name+='__unexpected'
    elif isinstance(target,ast.Assign):target.value=ast.Constant('unexpected')
    elif isinstance(target,ast.ImportFrom):target.module+='.__unexpected'
    else:raise ValueError(('negative scaffold fixture needs explicit mutation',type(target).__name__))
    rejected(modified,'modified_recognized_scaffold_rejected')
    partial=copy.deepcopy(current);path=patches[0]['path'];container=resolve(partial,path[:-1]);assert type(path[-1]) is int
    del container[path[-1]];rejected(partial,'partial_scaffold_rejected')
    duplicate=copy.deepcopy(current);duplicate.body.append(copy.deepcopy(resolve(current,patches[0]['path'])))
    rejected(duplicate,'duplicate_scaffold_rejected')
    unknown=copy.deepcopy(current);unknown.body.extend(ast.parse('def unreviewed_extra():\n    return 17\n').body)
    rejected(unknown,'unreviewed_extra_not_hidden_by_old_witness')
    numerical=copy.deepcopy(current)
    if name=='composed_runner_off':
        assignment=next(n for n in numerical.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='THREADS' for t in n.targets))
        number=next(n for n in ast.walk(assignment) if isinstance(n,ast.Constant) and type(n.value) is int and n.value>1)
    else:number=next(n for n in ast.walk(numerical) if isinstance(n,ast.Constant) and type(n.value) is int and n.value==73)
    number.value+=1;rejected(numerical,'preexisting_numerical_change_not_hidden_by_old_witness')
    reports[name]=dict(base_path=row['base'].relative_to(WORK).as_posix(),base_sha256=row['base_sha'],
        current_path=row['current'].relative_to(WORK).as_posix(),current_sha256=row['current_sha'],patches=patches,
        whole_module_AST_inverse_equal=True,original_base_unchanged=True,negative_source_metadata_fixtures=checks,
        numerical_function_body_replacement=False)

hpo_path=BASE/'tests/test_uar_hpo_fair_reserve.py';loss_path=BASE/'tests/test_uar_loss_backend.py'
hpo=hpo_path.read_text('utf-8-sig');loss=loss_path.read_text('utf-8-sig')
assert sha(hpo_path)=='8bfe59fa6bd0114c3867e1ef426f1f155cd83fbe3ba90709a332046b903d5643'
assert sha(loss_path)=='b882f673692ef758f3505c456a98d5883d25a37a2d75f3e611c3958b9aa58a7f'
assert hpo.count('    tree = ast.parse(text)')==1
hpo=hpo.replace('def projected_ast(text, is_runner):',generated['composed_runner_off']+'def projected_ast(text, is_runner):',1)
hpo=hpo.replace('    tree = ast.parse(text)','    tree = ast.parse(text)\n    if is_runner:tree = _composed_runner_off(tree)',1)
loss=loss.replace('class LegacyOffProjection(ast.NodeTransformer):',generated['composed_worker_off']+'class LegacyOffProjection(ast.NodeTransformer):',1)
anchor="    loss_names={'LossProfile','LOSS_PROFILES','loss_profile_catalog','resolve_loss_profile',\n                'validate_loss_profiles','loss_profile_fit_receipt'}"
assert loss.count(anchor)==1
loss=loss.replace(anchor,anchor+"\n    def visit_Module(self,node):\n        return self.generic_visit(_composed_worker_off(node))",1)
write('candidate/tests/test_uar_hpo_fair_reserve.py',hpo)
write('candidate/tests/test_uar_loss_backend.py',loss)
for text in [hpo,loss]:compile(text,'<test-helper-source-only>','exec')
write('normalizer-source-proof.json',json.dumps(dict(schema='composed-legacy-test-helper-source-proof-v1',status='SOURCE_ONLY_NOT_EXECUTED',
    projections=reports,pure_AST_metadata_evaluation_only=True,unittest_methods_executed=0,candidate_imports=0,
    fits=0,API_calls=0,data_arrays_PID_Git_clock=0),indent=2)+'\n')
print(json.dumps(dict(source_prepared=True,tests={p.name:sha(p) for p in (HERE/'candidate/tests').glob('*.py')},runtime=False)))
