"""SOURCE-only QHPOST01 pre-import original-pin repair. Never runs the outer."""
from pathlib import Path
import ast,difflib,hashlib,json
P=Path(__file__).resolve().parent;W=P.parent;B=W/'qwen-three-hour-outer-next-dev-r4'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text('utf-8'))
def save(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def dump(value):return ast.dump(value,include_attributes=False)
def methods(path):return {c.name+'.'+n.name:hashlib.sha256(dump(n).encode()).hexdigest() for c in ast.parse(path.read_text('utf-8-sig')).body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')}
assert not (P/'source-handoff.json').exists()
assert sha(B/'source-handoff.json')=='22151643df72f68b94d303725375b113e056b4851c7952d107cb912c14ad2b0c'
old=read(B/'source-handoff.json')
for rel,h in old['files_sha256'].items():assert sha(B/rel)==h,rel
for name in ('run_campaign.py','close_controller.py','run_root.py','close_child.ps1','test_broker_contracts.py'):(P/name).write_bytes((B/name).read_bytes())
before="need(sha(driver_ref['path'])==driver_ref['sha256'],'frozen_main_source_changed')"
after="need(pins.get(driver_ref['path'])==driver_ref['sha256'] and sha(driver_ref['path'])==driver_ref['sha256'],'frozen_main_source_changed')"
source=(B/'confirm_post_tool.py').read_text('utf-8');assert source.count(before)==1
source=source.replace(before,after);(P/'confirm_post_tool.py').write_text(source,encoding='utf-8',newline='\n')
assert dump(ast.parse(source.replace(after,before)))==dump(ast.parse((B/'confirm_post_tool.py').read_text('utf-8')))
tests=(B/'test_atomic_root.py').read_text('utf-8')
anchor="        with self.assertRaises(RuntimeError):post.full_known_union(fresh,root,[row(4)],ids)\n"
assert tests.count(anchor)==1
extra='''        # Execute ONLY the actual producer's pre-import guard AST with a mock
        # importer: changed bytes+ref cannot bypass the ORIGINAL frozen value.
        main=next(n for n in ast.parse(Path(post.__file__).read_text('utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='main')
        guarded=next(n for n in main.body if isinstance(n,ast.Try)).body
        first=next(i for i,n in enumerate(guarded) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='driver_ref' for t in n.targets))
        last=next(i for i,n in enumerate(guarded[first:],first) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='driver' for t in n.targets))
        only_guards=compile(ast.fix_missing_locations(ast.Module(body=copy.deepcopy(guarded[first:last+1]),type_ignores=[])),'<actual-post-preimport-guards>','exec')
        path=str(post.PACKET/'run_campaign.py');actual='b'*64
        for frozen in (actual,'a'*64,None):
            importer=Mock(return_value=object())
            namespace=dict(binding={'driver':{'path':path,'sha256':actual}},pins={} if frozen is None else {path:frozen},
                sha=Mock(return_value=actual),need=post.need,Path=Path,PACKET=post.PACKET,imported=importer)
            if frozen==actual:
                exec(only_guards,namespace);importer.assert_called_once()
            else:
                with self.assertRaisesRegex(RuntimeError,'frozen_main_source_changed'):exec(only_guards,namespace)
                importer.assert_not_called()
'''
tests=tests.replace(anchor,anchor+extra);(P/'test_atomic_root.py').write_text(tests,encoding='utf-8',newline='\n')
oldmaps=methods(B/'test_atomic_root.py');newmaps=methods(P/'test_atomic_root.py')
changed=[k for k,v in oldmaps.items() if newmaps[k]!=v]
assert changed==['PostToolContracts.test_full_known_union_keeps_wrapper_and_closer_preparers_and_denies_missing_or_live_scope']
assert len(newmaps)==len(oldmaps)==6
cfg=read(B/'binding.template.NOT_READY.json')
for row in cfg['contracts']:
    if row['path'].startswith(B.name+'/'):row['path']=P.name+row['path'][len(B.name):]
    path=W/row['path'];row.update(sha256=sha(path),methods=methods(path),expected=len(methods(path)))
assert [row['expected'] for row in cfg['contracts']]==[2,1,4,18,4,23,2,3,6]
assert sum(row['expected'] for row in cfg['contracts'])==63 and sum(row['parent'] for row in cfg['contracts'])==270
save(P/'binding.template.NOT_READY.json',cfg)
atomic=read(B/'atomic-binding.template.NOT_READY.json')
for key,name in [('driver','run_campaign.py'),('closer','close_controller.py'),('post_tool','confirm_post_tool.py')]:atomic[key]=dict(path=P.name+'/'+name,sha256=sha(P/name))
save(P/'atomic-binding.template.NOT_READY.json',atomic)
(P/'strong-authority.template.NOT_READY.json').write_bytes((B/'strong-authority.template.NOT_READY.json').read_bytes())
protocol=read(B/'protocol.json');protocol['source_revision']='R5_ORIGINAL_IMMUTABLE_PIN_BEFORE_POST_DRIVER_IMPORT';save(P/'protocol.json',protocol)
proof=dict(schema='qwen-outer-post-preimport-pin-source-proof-v1',previous_handoff_sha256=sha(B/'source-handoff.json'),
    sole_runtime_delta='Require original immutable driver pin equals ref SHA BEFORE actual SHA/path/import; exact conjunction inverse wholepost AST.',
    whole_post_AST_inverse_exact=True,other_five_runtime_files_raw_exact=True,
    only_one_new_post_test_method_expanded=changed,old_four_atomic_and_other_new_time_method_AST_exact=True,
    prepared_counts=[r['expected'] for r in cfg['contracts']],prepared_contract_executions=63,slots=9,parent_maxima270=True,
    actual_tests=0,actual_clock=None,actual_source_qualification=None,all_caps_clocks_resources_ownership_numerical_predicates_unchanged=True)
save(P/'source-proof.json',proof)
(P/'README.txt').write_text((B/'README.txt').read_text('utf-8')+'\nR5 QHPOST01: original immutable driver equality is checked before import. One actual guard-AST/mock case rejects changedbytes+ref and absent originalpin;63 methods unchanged count.\n',encoding='utf-8',newline='\n')
(P/'QHPOST01.patch').write_text(''.join(difflib.unified_diff((B/'confirm_post_tool.py').read_text('utf-8').splitlines(True),source.splitlines(True),fromfile='frozenR4/post',tofile='R5/post')),encoding='utf-8',newline='\n')
external=dict(old['external_refs_sha256']);external[B.name+'/source-handoff.json']=sha(B/'source-handoff.json')
for rel,h in old['files_sha256'].items():external[B.name+'/'+rel]=h
peer=W/'qwen-three-hour-outer-independent-source-review-r4.json'
assert peer.is_file();external[peer.name]=sha(peer)
for rel,h in external.items():assert sha(W/rel)==h,rel
for path in P.glob('*.py'):compile(path.read_text('utf-8'),str(path),'exec')
files={path.relative_to(P).as_posix():sha(path) for path in P.iterdir() if path.is_file() and path.name!='source-handoff.json'}
save(P/'source-handoff.json',dict(schema='qwen-three-hour-outer-original-post-pin-source-handoff-v5',status='FROZEN_SOURCE_ONLY_NOT_READY_PENDING_PEER',
    files_sha256=files,external_refs_sha256=external,prepared_contract_executions=63,actual_contract_executions=0,
    actual_clock=None,actual_metrics=None,source_qualification=None,approval=None))
print(json.dumps(dict(handoff_sha256=sha(P/'source-handoff.json'),local=len(files),external=len(external),prepared=63,executed=0)))
