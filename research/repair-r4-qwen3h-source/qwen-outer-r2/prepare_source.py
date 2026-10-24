"""SOURCE-only Q3O01 repair: two PS option literals and one cross-script mock."""
from pathlib import Path
import ast,hashlib,json,difflib
P=Path(__file__).resolve().parent;W=P.parent;B=W/'qwen-three-hour-outer-next-dev'
OLD='a2c6f587f44557a754bafbd3e7d5a9ffc36ca8ca0a930ccb65cf3177608ee36a'
PEER='4587ce12d2f40aaf92f8b9c4dc4168df30153ecbcabb1ad287c7d256c055f8f6'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def dump(n):return ast.dump(n,include_attributes=False)
def tree(p):return ast.parse(Path(p).read_text('utf-8-sig'))
def methods(p):
    return {c.name+'.'+n.name:hashlib.sha256(dump(n).encode()).hexdigest()
        for c in tree(p).body if isinstance(c,ast.ClassDef)
        for n in c.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')}
assert not (P/'source-handoff.json').exists()
assert sha(B/'source-handoff.json')==OLD
assert sha(W/'qwen-three-hour-outer-independent-source-review-r1.json')==PEER
old=read(B/'source-handoff.json')
for rel,h in old['files_sha256'].items():assert sha(B/rel)==h,rel
for rel,h in old['external_refs_sha256'].items():assert sha(W/rel)==h,rel
for name in ['run_campaign.py','close_controller.py','run_root.py','test_broker_contracts.py']:
    (P/name).write_bytes((B/name).read_bytes())
ps=(B/'close_child.ps1').read_text('utf-8-sig')
assert ps.count("'--private-manifest'")==ps.count("'--private-manifest-sha256'")==1
ps=ps.replace("'--private-manifest'","'--manifest'").replace("'--private-manifest-sha256'","'--manifest-sha256'")
(P/'close_child.ps1').write_text(ps,encoding='utf-8',newline='\n')
test=(B/'test_atomic_root.py').read_text('utf-8-sig')
test=test.replace('import importlib.util','import argparse,ast,contextlib,copy,importlib.util,io,re',1)
addition='''    def test_real_child_script_argv_is_accepted_by_exact_closer_parser_without_starting_it(self):
        # Execute only the original argparse construction AST, never closer main.
        source=ast.parse(Path(__file__).with_name('close_controller.py').read_text('utf-8'))
        main=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        body=[]
        for node in main.body:
            if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='a' for t in node.targets):break
            body.append(copy.deepcopy(node))
        body.append(ast.Return(value=ast.Name(id='p',ctx=ast.Load())))
        factory=ast.FunctionDef(name='parser_factory',args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]),
            body=body,decorator_list=[])
        namespace={'argparse':argparse,'__doc__':'synthetic cross-script parser'}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[factory],type_ignores=[])),'<actual-closer-parser-only>','exec'),namespace)
        parser=namespace['parser_factory']()
        script=Path(__file__).with_name('close_child.ps1').read_text('utf-8')
        block=re.search(r"\\$nativeArgs = @\\((.*?)\\)\\r?\\nif \\(\\$ActualSession",script,re.S).group(1)
        block=block.replace('.ToString([System.Globalization.CultureInfo]::InvariantCulture)','')
        tokens=list(re.finditer(r"'([^']*)'|\\$([A-Za-z_][A-Za-z0-9_]*)",block))
        residue=re.sub(r"'([^']*)'|\\$([A-Za-z_][A-Za-z0-9_]*)",'',block)
        self.assertFalse(residue.replace(',','').strip())
        values=dict(Closer=str(Path(__file__).with_name('close_controller.py')),Manifest='synthetic-private.json',
            ManifestSha='a'*64,CloserSha='b'*64,DriverSha='c'*64,CampaignSha='d'*64,ActualTool='actual-tool',ActualExit='0',PID='123',birthText='1000.25')
        argv=[m.group(1) if m.group(1) is not None else values[m.group(2)] for m in tokens]
        self.assertEqual(argv[:4],['-B','-X','utf8',values['Closer']])
        parsed=parser.parse_args(argv[4:])
        self.assertEqual(parsed.manifest,values['Manifest']);self.assertEqual(parsed.manifest_sha256,'a'*64)
        self.assertEqual(parsed.launch_parent_pid,123);self.assertEqual(parsed.launch_parent_create_time,1000.25)
        self.assertEqual(parsed.actual_exit_code,0);self.assertIsNone(parsed.actual_exec_session)
        self.assertIn("$nativeArgs += @('--actual-exec-session', $ActualSession)",script)
        self.assertEqual(parser.parse_args(argv[4:]+['--actual-exec-session','456']).actual_exec_session,456)
        old=[x.replace('--manifest','--private-manifest') if x.startswith('--manifest') else x for x in argv[4:]]
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as denied:parser.parse_args(old)
        self.assertEqual(denied.exception.code,2)

'''
anchor="if __name__=='__main__':unittest.main(verbosity=2)"
assert test.count(anchor)==1;test=test.replace(anchor,addition+anchor)
(P/'test_atomic_root.py').write_text(test,encoding='utf-8',newline='\n')
for p in P.glob('*.py'):compile(p.read_text('utf-8-sig'),str(p),'exec')
before=methods(B/'test_atomic_root.py');after=methods(P/'test_atomic_root.py')
assert len(before)==3 and len(after)==4 and all(after[k]==h for k,h in before.items())
assert ps.replace("'--manifest'","'--private-manifest'").replace("'--manifest-sha256'","'--private-manifest-sha256'")==(B/'close_child.ps1').read_text('utf-8-sig')
for name in ['run_campaign.py','close_controller.py','run_root.py','test_broker_contracts.py']:
    assert (P/name).read_bytes()==(B/name).read_bytes(),name
cfg=read(B/'binding.template.NOT_READY.json')
for row in cfg['contracts']:
    if row['path'].startswith(B.name+'/'):row['path']=P.name+row['path'][len(B.name):]
    if row['name']=='outer-atomic-contracts':row.update(sha256=sha(P/'test_atomic_root.py'),methods=after,expected=4)
cfg['missing_bindings']=[s.replace('independent outer source peer','independent outer R2 source peer') for s in cfg['missing_bindings']]
assert sum(r['expected'] for r in cfg['contracts'])==48
save(P/'binding.template.NOT_READY.json',cfg)
atomic=read(B/'atomic-binding.template.NOT_READY.json');atomic['child_script_sha256']=sha(P/'close_child.ps1')
for name,file in [('driver','run_campaign.py'),('closer','close_controller.py')]:atomic[name]=dict(path=P.name+'/'+file,sha256=sha(P/file))
save(P/'atomic-binding.template.NOT_READY.json',atomic)
(P/'strong-authority.template.NOT_READY.json').write_bytes((B/'strong-authority.template.NOT_READY.json').read_bytes())
protocol=read(B/'protocol.json');protocol.update(source_revision='Q3O01_R2_TWO_CHILD_ARGV_LITERALS_ONLY',prepared_contract_executions=48)
protocol['exact_contracts'][-1]['expected']=4
save(P/'protocol.json',protocol)
proof=read(B/'source-proof.json');proof.update(source_revision='Q3O01_R2',previous_handoff_sha256=OLD,
 original_three_runtime_and_broker_test_raw_bytes_exact=True,PS_two_option_inverse_raw_text_exact=True,
 previous_all47_test_method_AST_sha256_unchanged=True,new_cross_script_contracts=1,prepared_contract_executions=48)
old_key=B.name+'/test_atomic_root.py';proof['contract_methods'][P.name+'/test_atomic_root.py']=after
proof['contract_methods'].pop(old_key,None)
broker_key=B.name+'/test_broker_contracts.py';proof['contract_methods'][P.name+'/test_broker_contracts.py']=proof['contract_methods'].pop(broker_key)
save(P/'source-proof.json',proof)
readme=(B/'README.txt').read_text('utf-8').replace('slots47','slots48')
readme+='\nR2 Q3O01: exactly two child-Python argv option literals now match the existing closer parser. All three runtime Python sources byte-exact R1; old47 method/assertion ASTs preserved plus one real cross-script parser mock (48future,0run). R1a2c6/blockedpeer4587 preserved; qh1 was never executed.\n'
(P/'README.txt').write_text(readme,encoding='utf-8',newline='\n')
(P/'Q3O01-source-only.patch').write_text(''.join(difflib.unified_diff((B/'close_child.ps1').read_text('utf-8').splitlines(True),ps.splitlines(True),fromfile='frozen-R1/close_child.ps1',tofile='new-R2/close_child.ps1')),encoding='utf-8',newline='\n')
external=dict(old['external_refs_sha256']);external[B.name+'/source-handoff.json']=OLD
for rel,h in old['files_sha256'].items():external[B.name+'/'+rel]=h
external['qwen-three-hour-outer-independent-source-review-r1.json']=PEER
for rel,h in external.items():assert sha(W/rel)==h,rel
files={p.relative_to(P).as_posix():sha(p) for p in sorted(P.rglob('*')) if p.is_file() and p!=P/'source-handoff.json'}
save(P/'source-handoff.json',dict(schema='qwen-three-hour-outer-source-handoff-v2',status='FROZEN_SOURCE_ONLY_NOT_READY_PENDING_R2_PEER',
 files_sha256=files,external_refs_sha256=external,previous_handoff_sha256=OLD,
 prepared_contract_executions=48,actual_contract_executions=0,actual_qualified_archive_root_refs=None,
 actual_clock=None,actual_metrics=None,private_READY=None,candidate_imports_tests_fits_API_data_PID_Git_clock_by_author=0,promotion=False,submit=False))
print(json.dumps(dict(handoff=sha(P/'source-handoff.json'),child_script=sha(P/'close_child.ps1'),atomic_test=sha(P/'test_atomic_root.py'),local=len(files),external=len(external),prepared=48,executed=0)))
