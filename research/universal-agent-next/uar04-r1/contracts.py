"""Fixed UAR technical-gate artifact contracts. No candidate imports at module load."""
from pathlib import Path
import ast, copy, hashlib, json, re, zipfile

REQUIREMENTS_SHA='9173b0388532fbd2a709e4f4b3029e3b9ccab685fce43a85261ffa1ba95efbe6'
SOLUTION=b'from automl_runner import THREADS,llm_plan,main,run_worker\nif __name__ == "__main__": main()\n'
PHASES=('source','build','exact','mapped')
EXACT={'test_v2.py':11,'test_resilience.py':7,'smoke.py':5}
ALIASES={'agent_runner':'automl_runner','agent_policy':'automl_policy',
         'agent_worker':'automl_worker','ensemble_cache':'automl_ensembles'}

def need(value,code):
    if not value:raise RuntimeError(code)

def read(path):return json.loads(Path(path).read_text('utf-8'))

def sha(path,pulse=lambda:None):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            pulse();block=stream.read(2**20)
            if not block:break
            h.update(block)
    pulse();return h.hexdigest()

def methods(source):
    result={}
    for cls in ast.parse(source).body:
        if isinstance(cls,ast.ClassDef):
            for node in cls.body:
                if isinstance(node,ast.FunctionDef) and node.name.startswith('test_'):
                    key=cls.name+'.'+node.name
                    need(key not in result,'duplicate_qualified_test_method')
                    result[key]=ast.dump(node,include_attributes=False)
    return result

def registry(root):
    result={};found=False
    for n in ast.parse((Path(root)/'tools/run_checks.py').read_bytes()).body:
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CHECKS' for t in n.targets):
            need(not found,'duplicate_registry_assignment');result=ast.literal_eval(n.value);found=True
        elif (isinstance(n,ast.Expr) and isinstance(n.value,ast.Call)
              and isinstance(n.value.func,ast.Attribute) and isinstance(n.value.func.value,ast.Name)
              and n.value.func.value.id=='CHECKS' and n.value.func.attr=='update'):
            need(found and len(n.value.args)==1 and not n.value.keywords,'unsupported_registry_update')
            extra=ast.literal_eval(n.value.args[0]);need(type(extra) is dict and not set(extra)&set(result),'duplicate_registry_script')
            result.update(extra)
    need(found and type(result) is dict and 1<=len(result)<=128,'bounded_literal_registry_required')
    need(all(type(k) is str and re.fullmatch(r'(?:test_[a-z0-9_]+|smoke)\.py',k)
             and type(v) is int and 1<=v<=256 for k,v in result.items()),'typed_registry_counts_required')
    return result

def mapping(root):
    root=Path(root);result=read(root/'tools/module_map.json')
    need(type(result) is dict,'typed_module_map_required')
    for path in (root/'src/automl').rglob('*.py'):
        if path.name!='__init__.py':
            module='.'.join(path.relative_to(root/'src').with_suffix('').parts)
            result.setdefault(module,module.replace('.','_'))
    need(all(type(k) is str and re.fullmatch(r'automl(?:\.[a-z_][a-z0-9_]*)+',k)
             and type(v) is str and re.fullmatch('[a-z_][a-z0-9_]*',v) for k,v in result.items())
         and len(result)==len(set(result.values())),'unique_typed_flat_mapping_required')
    return result

def flat_names(root):return sorted([v+'.py' for v in mapping(root).values()]+
                                  [v+'.py' for v in ALIASES]+['solution.py','requirements.txt'])

class FlatTestImports(ast.NodeTransformer):
    """Imports, mock module-name strings and only the top-level src sys.path hook."""
    def __init__(self,mp,inverse=False):self.mp=mp;self.inverse=inverse
    def visit_ImportFrom(self,node):
        if node.module in self.mp:
            return ast.copy_location(ast.ImportFrom(self.mp[node.module],node.names,0),node)
        if not self.inverse and node.module and node.module.startswith('automl.'):
            need(all(node.module+'.'+a.name in self.mp for a in node.names),'unmapped_project_test_import')
            return [ast.copy_location(ast.Import([ast.alias(self.mp[node.module+'.'+a.name],a.asname or a.name)]),node)
                    for a in node.names]
        return self.generic_visit(node)
    def visit_Import(self,node):
        if self.inverse and all(a.name in self.mp for a in node.names):
            return [ast.copy_location(ast.ImportFrom(self.mp[a.name].rsplit('.',1)[0],
                [ast.alias(self.mp[a.name].rsplit('.',1)[1],None if a.asname==self.mp[a.name].rsplit('.',1)[1] else a.asname)],0),node)
                for a in node.names]
        return node
    def visit_Constant(self,node):
        if isinstance(node.value,str):
            for old,new in sorted(self.mp.items(),key=lambda item:-len(item[0])):
                if node.value==old or node.value.startswith(old+'.'):
                    return ast.copy_location(ast.Constant(new+node.value[len(old):]),node)
        return node
    def visit_Call(self,node):
        # The source-side import path is replaced, never supplemented: no modular fallback.
        if (not self.inverse and isinstance(node.func,ast.Attribute) and node.func.attr=='insert'
            and isinstance(node.func.value,ast.Attribute) and isinstance(node.func.value.value,ast.Name)
            and node.func.value.value.id=='sys' and node.func.value.attr=='path' and len(node.args)==2):
            arg=node.args[1]
            if isinstance(arg,ast.Call) and isinstance(arg.func,ast.Name) and arg.func.id=='str' and len(arg.args)==1:
                value=arg.args[0]
                if (isinstance(value,ast.BinOp) and isinstance(value.op,ast.Div)
                    and isinstance(value.left,ast.Name) and value.left.id=='ROOT'
                    and isinstance(value.right,ast.Constant) and value.right.value=='src'):
                    node.args[1]=ast.Call(ast.Name('str',ast.Load()),[ast.Name('ROOT',ast.Load())],[])
        return self.generic_visit(node)

def adapted_test(cfg,suite):
    source=Path(suite['test']).read_bytes();mp=mapping(cfg['canonical_root'])
    tree=FlatTestImports(mp).visit(ast.parse(source));text=ast.unparse(ast.fix_missing_locations(tree))+'\n'
    inverse=FlatTestImports({v:k for k,v in mp.items()},True).visit(ast.parse(text))
    before=methods(source);after=methods(ast.unparse(ast.fix_missing_locations(inverse)))
    need(all(before[k]==after[k] for k in suite['selected_methods']),
         'selected_flat_assertion_AST_changed')
    need(not any(isinstance(n,ast.ImportFrom) and n.module and n.module.startswith('automl.')
                 for n in ast.walk(ast.parse(text))),'unmapped_modular_test_import')
    need(not any(isinstance(n,ast.Import) and any(a.name=='automl' or a.name.startswith('automl.') for a in n.names)
                 for n in ast.walk(ast.parse(text))),'unsupported_modular_namespace_import')
    return text.encode(),dict(source_test_sha256=hashlib.sha256(source).hexdigest(),
        adapted_test_sha256=hashlib.sha256(text.encode()).hexdigest(),method_AST_projection_equal=True,
        selected_methods=suite['selected_methods'],excluded_methods=suite['excluded_methods'])

def frozen(cfg,pulse=lambda:None):
    for path,expected in cfg['files_sha256'].items():need(sha(path,pulse)==expected,'frozen_input_changed')
    root=Path(cfg['canonical_root'])
    actual={str(p.resolve()) for folder in ('src','tests','tools') for p in (root/folder).rglob('*.py')}
    need(actual==set(cfg['canonical_python_inventory']),'canonical_python_inventory_changed')
    need(registry(root)==cfg['registry'] and flat_names(root)==cfg['flat_inventory'],'registry_or_flat_inventory_changed')
    for suite in cfg['mapped_suites']:
        observed=methods(Path(suite['test']).read_bytes())
        need(list(observed)==suite['all_methods'] and len(suite['selected_methods'])==suite['expected_tests']
             and set(suite['selected_methods'])|set(suite['excluded_methods'])==set(observed)
             and not set(suite['selected_methods'])&set(suite['excluded_methods']),
             'mapped_method_inventory_changed')
        pulse()

def archive(cfg,out,pulse=lambda:None):
    out=Path(out);path=out/'candidate.zip';manifest=read(out/'candidate.manifest.json')
    need(sha(path,pulse)==manifest['sha256'] and path.stat().st_size==manifest['bytes']<=100_000_000,
         'candidate_archive_hash_or_size_failed')
    need(sorted(manifest['files'])==cfg['flat_inventory'],'candidate_manifest_inventory_changed')
    with zipfile.ZipFile(path) as stream:
        infos=stream.infolist();names=[i.filename for i in infos]
        need(len(names)==len(set(names)) and sorted(names)==cfg['flat_inventory'],'exact_flat_inventory_required')
        for item in infos:
            pulse();need(Path(item.filename).name==item.filename and not item.is_dir()
                and (item.external_attr>>16)&0o170000!=0o120000,'flat_archive_path_or_symlink_denied')
            data=stream.read(item)
            need(hashlib.sha256(data).hexdigest()==manifest['files'][item.filename],'archive_member_changed')
        need(stream.read('solution.py')==SOLUTION,'original_platform_entrypoint_changed')
        need(hashlib.sha256(stream.read('requirements.txt')).hexdigest()==REQUIREMENTS_SHA,'platform_requirements_changed')
    return manifest

def counts(text,expected):
    return (re.findall(r'Ran (\d+) tests?',text)==[str(expected)]
            and re.search(r'\bskip(?:ped)?\b',text,re.I) is None
            and re.search(r'\nOK\s*$',text) is not None)

def cleanup_status(cfg,out,entry_started):
    """Saved phase and nested-leaf denials stay unresolved after exact PIDs vanish."""
    out=Path(out);uncertain=[];path=out/'technical-results.json'
    if not path.exists():return (not entry_started,[] if not entry_started else
        [dict(action='leaf_cleanup_receipts',reason='missing_after_entry_started')])
    try:
        rows=read(path)['leaves'];need(type(rows) is list and len(rows)<=4,'malformed_phase_receipts')
        for index,row in enumerate(rows):need(row['id']==PHASES[index],'malformed_phase_order')
        if any(r['id']=='mapped' for r in rows):
            nested=out/'mapped-results.json'
            if not nested.exists():uncertain.append(dict(action='mapped_cleanup_receipts',reason='missing_after_mapped_started'))
            else:rows=rows+read(nested)['leaves']
        for row in rows:
            ob=row.get('cleanup_observation',{})
            if row.get('cleanup_confirmed') is not True or ob.get('denial_count')!=0 or ob.get('unresolved')!=[]:
                uncertain.append(dict(action='saved_leaf_cleanup_unconfirmed',id=row.get('id'),
                    owned_root=row.get('owned_root'),observation=ob))
    except (OSError,ValueError,KeyError,TypeError,RuntimeError,IndexError) as exc:
        uncertain.append(dict(action='leaf_cleanup_receipts',reason='unreadable_or_malformed',error_type=type(exc).__name__))
    return not uncertain,uncertain

def artifact_checks(cfg,out,pulse=lambda:None):
    out=Path(out);refs={}
    def record(path):refs[str(path)]=sha(path,pulse);return read(path)
    detail=record(out/'technical-results.json')
    need(detail.get('status')=='passed' and [r['id'] for r in detail['leaves']]==list(PHASES)
         and all(r.get('exit_code')==0 for r in detail['leaves']) and not detail.get('first_failure'),
         'fixed_technical_phases_failed')
    leaf_ok,unused=cleanup_status(cfg,out,True);need(leaf_ok,'saved_leaf_cleanup_unconfirmed')
    source=record(out/'source/results.json');reg=cfg['registry'];rows=source['checks']
    need(source.get('passed') is True and source.get('source_unchanged') is True
         and source.get('fixture_cleanup_confirmed') is True and len(rows)==len(reg)
         and [r['script'] for r in rows]==list(reg)
         and source.get('unique_checks_passed')==sum(reg.values())
         and source.get('unique_checks_skipped')==0,'full_source_counts_or_cleanup_failed')
    for row in rows:
        script=row['script'];need(row.get('passed') is True and row.get('status')==0
            and row.get('observed_checks')==row.get('expected_checks')==reg[script]
            and row.get('skipped_checks')==0,'source_script_count_or_exit_failed')
    need(source.get('test_script_sha256')=={k:cfg['files_sha256'][str((Path(cfg['canonical_root'])/'tests'/k).resolve())]
                                           for k in reg},'source_test_byte_binding_failed')
    need(not Path(source['fixture_root']).exists(),'source_fixture_directory_not_cleaned')
    built=archive(cfg,out,pulse);refs[str(out/'candidate.zip')]=built['sha256']
    record(out/'candidate.manifest.json');need(source['source_sha256']==built['files'],'source_build_compiled_parity_failed')
    exact=record(out/'exact.json')
    need(exact.get('passed') is True and exact.get('matches_current_source') is True
         and exact.get('compiled_files')==len(cfg['flat_inventory']) and exact.get('sha256')==built['sha256']
         and [r['script'] for r in exact['checks']]==list(EXACT),'exact_release_inventory_failed')
    for row in exact['checks']:
        text=row.get('stdout','')+'\n'+row.get('stderr','');script=row['script']
        found=re.findall(r'Ran (\d+) tests? in ',text)
        observed=int(found[-1]) if found else 5 if script=='smoke.py' and row.get('exit_code')==0 else None
        need(row.get('exit_code')==0 and observed==EXACT[script]
             and re.search(r'\bskipped=([1-9]\d*)',text) is None,'exact23_count_or_exit_failed')
    mapped=record(out/'mapped-results.json')
    need(mapped.get('status')=='passed' and mapped.get('archive_sha256')==built['sha256']
         and [r['id'] for r in mapped['leaves']]==[s['id'] for s in cfg['mapped_suites']],
         'mapped_suite_inventory_failed')
    for row,suite in zip(mapped['leaves'],cfg['mapped_suites']):
        text=(out/(row['id']+'.log')).read_text('utf-8',errors='replace')
        expected,proof=adapted_test(cfg,suite)
        target=out/'unpacked/tests'/(suite['id']+'.py')
        need(row.get('exit_code')==0 and row.get('passed') is True and counts(text,suite['expected_tests'])
             and row.get('source_test_sha256')==cfg['files_sha256'][suite['test']]
             and row.get('method_AST_projection_equal') is True and row.get('selected_methods')==suite['selected_methods']
             and row.get('excluded_methods')==suite['excluded_methods']
             and target.read_bytes()==expected and row.get('adapted_test_sha256')==sha(target,pulse),
             'mapped_assertion_or_counts_failed')
        refs[str(target)]=proof['adapted_test_sha256']
    with zipfile.ZipFile(out/'candidate.zip') as stream:
        for name in cfg['flat_inventory']:
            need((out/'unpacked'/name).read_bytes()==stream.read(name),'deployed_flat_runtime_changed')
            pulse()
    allowed=set(cfg['flat_inventory'])|{'tests/'+s['id']+'.py' for s in cfg['mapped_suites']}
    need({p.relative_to(out/'unpacked').as_posix() for p in (out/'unpacked').rglob('*') if p.is_file()}==allowed,
         'unpacked_inventory_changed_no_source_sidecars')
    for name in ['technical.log']+[v+'.log' for v in PHASES]+[v['id']+'.log' for v in cfg['mapped_suites']]:
        refs[str(out/name)]=sha(out/name,pulse)
    return dict(source_scripts=len(reg),source_unique_checks=sum(reg.values()),exact_repeated_checks=23,
                mapped_repeated_checks=sum(v['expected_tests'] for v in cfg['mapped_suites']),
                flat_members=len(cfg['flat_inventory']),fixture_learner_fits=None,
                fixture_fit_count_reason='broad_legacy_fixtures_uninstrumented_not_zero',
                external_API_calls=None,external_API_usage_reason='no_external_calls_intended_not_independently_instrumented',
                local_mock_HTTP_permitted=True,public_experiment_fits=0,quality_metric=None),refs
