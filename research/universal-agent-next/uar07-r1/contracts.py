"""Fixed UAR technical-gate artifact contracts. No candidate imports at module load."""
from pathlib import Path
import ast, copy, hashlib, json, re, zipfile

REQUIREMENTS_SHA='9173b0388532fbd2a709e4f4b3029e3b9ccab685fce43a85261ffa1ba95efbe6'
SOLUTION=b'from automl_runner import THREADS,llm_plan,main,run_worker\nif __name__ == "__main__": main()\n'
PHASES=('parser','mapped')
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
    """Require a unique anchored summary and terminal successful unittest status.

    JSON telemetry containing skip/error/failure keys is ordinary output. Only
    unittest-shaped status/progress/detail lines count as failed/skipped tests.
    This bool never replaces the saved actual exit or frozen source/AST checks.
    """
    if type(text) is not str or type(expected) is not int or expected<1:
        return False
    lines=text.replace('\r\n','\n').replace('\r','\n').splitlines()
    summaries=[]
    for index,line in enumerate(lines):
        match=re.fullmatch(r'Ran ([0-9]+) tests? in [0-9]+(?:\.[0-9]+)?s[ \t]*',line)
        if match is not None:
            summaries.append((index,match.group(1)))
    if len(summaries)!=1 or summaries[0][1]!=str(expected):
        return False
    index,unused=summaries[0]
    terminal=[line.strip() for line in lines[index+1:] if line.strip()]
    if terminal not in (['OK'],['OK (skipped=0)']):
        return False
    for line in lines:
        # Real verbose result or its second doc-description line. JSON object,
        # array and quoted-string lines are telemetry, not unittest statuses.
        if re.match(r'^\s*[^\s{\["][^\r\n]*\s\.\.\.\s+'
                    r'(?:skipped\b|expected failure\b|unexpected success\b|FAIL\b|ERROR\b)',line):
            return False
        if re.match(r'^\s*(?:FAIL|ERROR|UNEXPECTED SUCCESS):\s',line):
            return False
        if re.fullmatch(r'\s*(?:FAILED|FAILURE|ERROR)(?:\s*\([^\r\n]*\))?\s*',line):
            return False
        # Verbosity-one progress uses s/x/u/F/E, never JSON key names.
        progress=line.strip()
        if re.fullmatch(r'[.sxuFE]+',progress) and re.search(r'[sxuFE]',progress):
            return False
    return True

def temporary_binding(cfg,out):
    record=read(Path(out)/'temporary-root.json')
    need(type(record) is dict and type(record.get('root')) is str,'typed_temporary_root_receipt_required')
    root=Path(record['root'])
    need(record.get('schema')==1 and record.get('run_id')=='UAR07'
         and record.get('scope')=='exclusive_shallow_leaf_environment'
         and root.is_absolute() and root.resolve()==root
         and root.parent.resolve()==(Path(cfg['work_root'])/'t').resolve()
         and re.fullmatch(r'u7-[a-z0-9_]{8}',root.name) and not root.is_symlink(),
         'exclusive_temporary_root_binding_failed')
    return root

def temporary_status(cfg,out,expected_root):
    try:
        record=read(Path(out)/'temporary-cleanup.json')
        need(type(record) is dict and record.get('schema')==1 and record.get('cleanup_confirmed') is True,
             'temporary_cleanup_receipt_unconfirmed')
        if expected_root is None:
            need(record.get('root') is None and record.get('created') is False
                 and not (Path(out)/'temporary-root.json').exists(),'unexpected_temporary_root')
        else:
            root=temporary_binding(cfg,out)
            need(str(root)==expected_root==record.get('root') and record.get('created') is True
                 and not root.exists(),'temporary_root_cleanup_unconfirmed')
        return True,[]
    except (OSError,ValueError,KeyError,TypeError,RuntimeError) as exc:
        return False,[dict(action='temporary_root_cleanup',reason='missing_unreadable_or_unconfirmed',
                           error_type=type(exc).__name__)]


def cleanup_status(cfg,out,entry_started):
    """Missing phase evidence or saved denials remain sticky after PID absence."""
    out=Path(out);uncertain=[]
    for phase in PHASES:
        supervisor=out/(phase+'-supervisor.json');path=out/(phase+'-results.json')
        started=supervisor.exists() and bool(read(supervisor).get('owned_root'))
        if not path.exists():
            if started:uncertain.append(dict(action='leaf_cleanup_receipts',id=phase,reason='missing_after_entry_started'))
            continue
        try:
            rows=read(path)['leaves'];need(type(rows) is list and len(rows)<=5,'malformed_phase_receipts')
            allowed=['parser'] if phase=='parser' else [s['id'] for s in cfg['mapped_suites']]
            need([r['id'] for r in rows]==allowed[:len(rows)],'malformed_phase_order')
            for row in rows:
                ob=row.get('cleanup_observation',{})
                if row.get('cleanup_confirmed') is not True or ob.get('denial_count')!=0 or ob.get('unresolved')!=[]:
                    uncertain.append(dict(action='saved_leaf_cleanup_unconfirmed',id=row.get('id'),
                        owned_root=row.get('owned_root'),observation=ob))
        except (OSError,ValueError,KeyError,TypeError,RuntimeError,IndexError) as exc:
            uncertain.append(dict(action='leaf_cleanup_receipts',id=phase,reason='unreadable_or_malformed',
                                  error_type=type(exc).__name__))
    return not uncertain,uncertain


def artifact_checks(cfg,out,pulse=lambda:None):
    """Explicit historical source/build/exact + fresh parser16/mapped75; no old full PASS."""
    out=Path(out);reused,refs=reuse_checks(cfg,pulse)
    def record(path):refs[str(path)]=sha(path,pulse);return read(path)
    temporary_root=temporary_binding(cfg,out);record(out/'temporary-root.json')
    leaf_ok,unused=cleanup_status(cfg,out,True);need(leaf_ok,'saved_leaf_cleanup_unconfirmed')
    built=archive(cfg,out,pulse)
    need(built['sha256']==reused['archive_sha256'],'new_archive_must_be_exact_reused_bytes')
    refs[str(out/'candidate.zip')]=built['sha256'];record(out/'candidate.manifest.json')
    parser=record(out/'parser-results.json')
    need(parser.get('status')=='passed' and parser.get('first_failure') is None
         and len(parser['leaves'])==1 and parser['leaves'][0]['id']=='parser','fresh_parser_receipt_required')
    row=parser['leaves'][0]
    text=(out/'parser.log').read_text('utf-8',errors='replace')
    need(row.get('exit_code')==0 and row.get('passed') is True and counts(text,16)
         and row.get('source_test_sha256')==cfg['files_sha256'][cfg['parser_test']]
         and row.get('parser_sha256')==cfg['files_sha256'][cfg['parser_source']],
         'fresh_exact_parser16_required')
    mapped=record(out/'mapped-results.json')
    for detail in (parser,mapped):
        need(detail.get('temporary_root')==str(temporary_root) and
             all(r.get('temporary_root')==str(temporary_root) for r in detail['leaves']),
             'fresh_leaf_temporary_environment_binding_failed')
    need(mapped.get('status')=='passed' and mapped.get('first_failure') is None
         and mapped.get('archive_sha256')==built['sha256']
         and [r['id'] for r in mapped['leaves']]==[s['id'] for s in cfg['mapped_suites']],
         'all_five_fresh_mapped_suites_required')
    for row,suite in zip(mapped['leaves'],cfg['mapped_suites']):
        text=(out/(row['id']+'.log')).read_text('utf-8',errors='replace')
        expected,proof=adapted_test(cfg,suite);target=out/'unpacked/tests'/(suite['id']+'.py')
        need(row.get('exit_code')==0 and row.get('passed') is True and counts(text,suite['expected_tests'])
             and row.get('source_test_sha256')==cfg['files_sha256'][suite['test']]
             and row.get('method_AST_projection_equal') is True and row.get('selected_methods')==suite['selected_methods']
             and row.get('excluded_methods')==suite['excluded_methods']
             and target.read_bytes()==expected and row.get('adapted_test_sha256')==sha(target,pulse),
             'mapped_assertion_or_counts_failed')
        refs[str(target)]=proof['adapted_test_sha256']
    with zipfile.ZipFile(out/'candidate.zip') as stream:
        for name in cfg['flat_inventory']:
            need((out/'unpacked'/name).read_bytes()==stream.read(name),'deployed_flat_runtime_changed');pulse()
    allowed=set(cfg['flat_inventory'])|{'tests/'+s['id']+'.py' for s in cfg['mapped_suites']}
    need({p.relative_to(out/'unpacked').as_posix() for p in (out/'unpacked').rglob('*') if p.is_file()}==allowed,
         'unpacked_inventory_changed_no_source_sidecars')
    for name in ('parser-supervisor.log','mapped-supervisor.log','parser.log')+tuple(s['id']+'.log' for s in cfg['mapped_suites']):
        refs[str(out/name)]=sha(out/name,pulse)
    summary=dict(schema='uar-composite-qualified-checks-v1',qualification_mode='explicit_composite',
        archive_sha256=built['sha256'],flat_members=73,
        reused_phases=reused['phases'],new_phases=[
            dict(id='parser',mode='new_execution',checks=16),dict(id='mapped',mode='new_execution',checks=75)],
        reused_source_scripts=57,reused_source_unique_checks=604,reused_exact_repeated_checks=23,
        newly_executed_source_checks=0,newly_executed_builds=0,newly_executed_exact_checks=0,
        newly_executed_parser_checks=16,newly_executed_mapped_checks=75,
        original_UAR06_status='FAIL_PERMANENT',original_UAR06_retroqualified=False,
        fixture_learner_fits=None,declared_mapped_tiny_learner_fits=9,
        fixture_fit_count_reason='synthetic LOSS fits declared; aggregate actual fit counter unavailable',
        external_API_calls=None,external_API_usage_reason='provider env stripped; actual independent usage counter unavailable',
        public_experiment_fits=0,quality_metric=None,official_default_ready=False)
    return summary,refs


def reuse_checks(cfg,pulse=lambda:None):
    """Read-only fresh verification of completed leaves, never UAR06 parent success."""
    reuse=cfg['reuse'];refs={}
    def record(path,expected=None):
        path=Path(path);observed=sha(path,pulse)
        if expected is not None:need(observed==expected,'reused_evidence_changed')
        refs[str(path)]=observed;return read(path)
    old=record(reuse['private_manifest']['path'],reuse['private_manifest']['sha256'])
    need(old.get('readiness')=='READY_FROZEN_SOURCE_REVIEWED' and old.get('run_id')=='UAR06',
         'exact_original_UAR06_manifest_required')
    for field in ('work_root','canonical_root','python','lock_path','candidate_process_sha256',
                  'canonical_python_inventory','registry','flat_inventory','mapped_suites','helpers'):
        need(cfg[field]==old[field],'reused_source_or_method_contract_changed')
    need(len(old['canonical_python_inventory'])==169 and len(old['registry'])==57
         and sum(old['registry'].values())==604 and len(old['flat_inventory'])==73,
         'exact_UAR06_inventory_required')
    need(all(cfg['files_sha256'].get(path)==expected for path,expected in old['files_sha256'].items()),
         'all_original_source_helper_input_pins_mandatory')
    frozen(old,pulse)
    old_out=Path(old['output']);evidence=record(reuse['evidence']['path'],reuse['evidence']['sha256'])
    names={'campaign.json','technical.json','technical-results.json','mapped-results.json','source/results.json',
           'exact.json','candidate.zip','candidate.manifest.json','technical.log','source.log','build.log','exact.log','mapped.log'}
    need(set(evidence['files_sha256'])==names,'complete_fixed_reused_evidence_required')
    for name,expected in evidence['files_sha256'].items():
        path=old_out/name;need(sha(path,pulse)==expected,'reused_receipt_or_archive_changed');refs[str(path)]=expected
    c=read(old_out/'campaign.json');sup=read(old_out/'technical.json');detail=read(old_out/'technical-results.json')
    need(c.get('status')=='technical_failure' and c.get('technical_procedure_passed') is False
         and c.get('common_seconds')==1200 and c['absolute_deadline_unix']==c['start_unix']+1200
         and c['common_deadline_monotonic']==c['start_monotonic']+1200,'old_FAIL_and_original_clock_must_be_preserved')
    need(c['private_manifest_sha256']==reuse['private_manifest']['sha256'],'old_campaign_manifest_binding_failed')
    ob=sup.get('cleanup_observation',{})
    need(sup.get('kind')=='technical' and sup.get('exit_code')==1 and sup.get('cleanup_confirmed') is True
         and ob.get('denial_count')==0 and ob.get('unresolved')==[]
         and sup.get('parent_cap_seconds')==900 and sup.get('child_cap_seconds')==840
         and sup.get('start_monotonic')==c['start_monotonic']
         and c['start_unix']<=sup['start_unix']<=sup['end_unix']<c['absolute_deadline_unix']
         and sup['end_unix']<c['start_unix']+900 and sup['seconds']<840,
         'old_actual_parent_cleanup_and_completed_leaf_clock_required')
    rows=detail['leaves'];need([r['id'] for r in rows]==['source','build','exact','mapped'],
                              'old_phase_order_required')
    starts=[r['owned_root']['create_time'] for r in rows]
    need(sup['start_unix']<=starts[0]<starts[1]<starts[2]<starts[3]<=sup['end_unix'],
         'saved_ordered_leaf_identity_clock_bounds_required')
    phases=[]
    for index,row in enumerate(rows[:3]):
        ob=row.get('cleanup_observation',{})
        need(row.get('status')=='passed' and row.get('exit_code')==0 and row.get('cleanup_confirmed') is True
             and ob.get('denial_count')==0 and ob.get('unresolved')==[],'reused_leaf_exit_or_cleanup_failed')
        phases.append(dict(id=row['id'],mode='reused_completed_leaf',exit_code=0,cleanup_confirmed=True,
            parent_receipt_sha256=evidence['files_sha256']['technical.json'],
            phase_receipt_sha256=evidence['files_sha256']['technical-results.json'],
            phase_clock=dict(bound_kind='saved_parent_clock_and_ordered_leaf_birth_bounds',
                begin_unix_lower_bound=starts[index],end_unix_upper_bound=starts[index+1],
                exact_phase_monotonic_start=None,exact_phase_monotonic_end=None,
                parent_start_monotonic=c['start_monotonic'],parent_cap_seconds=900,shared_child_cap_seconds=840)))
    source=read(old_out/'source/results.json');reg=cfg['registry'];checks=source['checks']
    need(source.get('passed') is True and source.get('source_unchanged') is True
         and source.get('fixture_cleanup_confirmed') is True and [r['script'] for r in checks]==list(reg)
         and source.get('unique_checks_passed')==604 and source.get('unique_checks_skipped')==0
         and not Path(source['fixture_root']).exists(),'reused_source_counts_or_fixture_cleanup_failed')
    for row in checks:
        need(row.get('passed') is True and row.get('status')==0 and row.get('skipped_checks')==0
             and row.get('observed_checks')==row.get('expected_checks')==reg[row['script']],
             'reused_source_script_exit_or_count_failed')
    need(source.get('test_script_sha256')=={k:cfg['files_sha256'][str((Path(cfg['canonical_root'])/'tests'/k).resolve())]
                                           for k in reg},'reused_test_source_hashes_failed')
    built=archive(old,old_out,pulse)
    need(built['sha256']==evidence['files_sha256']['candidate.zip']
         and source['source_sha256']==built['files'],'reused_source_build_parity_failed')
    exact=read(old_out/'exact.json')
    need(exact.get('passed') is True and exact.get('matches_current_source') is True
         and exact.get('compiled_files')==73 and exact.get('sha256')==built['sha256']
         and [r['script'] for r in exact['checks']]==list(EXACT),'reused_exact_inventory_failed')
    for row in exact['checks']:
        text=row.get('stdout','')+'\n'+row.get('stderr','');found=re.findall(r'Ran (\d+) tests? in ',text)
        observed=int(found[-1]) if found else 5 if row['script']=='smoke.py' and row.get('exit_code')==0 else None
        need(row.get('exit_code')==0 and observed==EXACT[row['script']]
             and re.search(r'\bskipped=([1-9]\d*)',text) is None,'reused_exact23_count_or_exit_failed')
    observation,negative_refs=negative_checks(cfg,pulse);refs.update(negative_refs)
    need(observation['original_campaign']=={k:c.get(k) for k in observation['original_campaign']},
         'late_observation_original_failed_campaign_binding')
    phases[0].update(checks=604,scripts=57);phases[1].update(flat_members=73);phases[2].update(checks=23)
    return dict(schema='uar-reused-completed-phases-v1',phases=phases,archive_sha256=built['sha256'],
        old_parent_status='FAIL_PERMANENT',old_parent_cleanup_at_finish=False,
        later_root_scope='fresh_source_and_cleanup_at_observation_not_retroactive_gate_PASS'),refs


def negative_checks(cfg,pulse=lambda:None):
    """Exact typed late observation: historical false flags stay false forever."""
    binding=cfg['negative_predecessor'];refs={}
    values={}
    for key in ('late_observation','root_fresh_absence'):
        ref=binding[key];need(sha(ref['path'],pulse)==ref['sha256'],'late_negative_evidence_changed')
        refs[ref['path']]=ref['sha256'];values[key]=read(ref['path'])
    audit=values['late_observation'];root=values['root_fresh_absence']
    need(audit.get('schema')=='UAR06-late-negative-observation-v1'
         and audit.get('status')=='late_negative_observation_completed_original_UAR06_FAIL'
         and audit.get('technical_procedure_passed') is False and audit.get('qualified_checks') is None
         and audit.get('cleanup_confirmed') is False and audit.get('source_unchanged') is False
         and audit.get('original_UAR06_remains_failed') is True and audit.get('original_deadline_extended') is False
         and audit.get('late_current_observation_only') is True
         and audit.get('current_known_absence_confirmed') is True
         and audit.get('current_source_pin_check_completed') is True and audit.get('current_source_pins_match') is True
         and audit.get('source_pin_count')==235 and audit.get('current_changed_source_or_input')==[]
         and audit.get('temporary_late_cleanup_confirmed') is True and audit.get('error') is None
         and audit.get('audit_guard_sticky_error') is None and audit.get('actual_exec_session')==36525
         and audit.get('actual_exec_exit_code_observed_by_root')==1 and audit.get('actual_tool_evidence')=='48e37c',
         'exact_completed_late_observation_not_old_gate_PASS_required')
    observation=audit.get('current_observation',{})
    need(observation.get('denial_count')==0 and observation.get('unresolved')==[]
         and audit['audit_deadline_unix']==audit['audit_start_unix']+120
         and audit['audit_deadline_monotonic']==audit['audit_start_monotonic']+120
         and audit['audit_finished_unix']<audit['audit_deadline_unix']
         and audit['audit_finished_monotonic']<audit['audit_deadline_monotonic']
         and audit['audit_maximum_observed_gap_seconds']<=10,
         'actual_late_observation_clock_and_denial_bounds_required')
    need(root.get('schema')==1 and root.get('late_audit_sha256')==binding['late_observation']['sha256']
         and root.get('late_audit_actual_session')==79044 and root.get('late_audit_actual_exit')==0
         and root.get('late_audit_actual_tool')=='5a1aee' and root.get('known_count')==6178
         and root.get('known_exact_live')==[] and root.get('uncertain')==[]
         and root.get('original_UAR06_FAIL_preserved') is True
         and root.get('original_cleanup_or_source_posthash_retroqualified') is False
         and root['checked_unix']>=audit['audit_finished_unix'],
         'actual_late_audit_exec0_and_root_fresh_absence_required')
    need(audit.get('prior_unknown_preparer_identity') is None
         and audit.get('prior_unknown_preparer_retroqualified') is False
         and root.get('old_unknown_preparer_identity') is None,'no_unknown_historical_PID_grant')
    return audit,refs


def negative_union(cfg,coor,pulse=lambda:None):
    """Use the same reviewed identity parser/observer; never a new PID-only scan."""
    audit,unused=negative_checks(cfg,pulse)
    known=coor.identities(audit['owned_identities']+audit['closure_preparer_identities']+audit['owned_process_identities'])
    need(len(known)==6178,'exact_late_observation_known_and_preparer_union_required')
    return known
