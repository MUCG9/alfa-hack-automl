"""SOURCE-only final helper path/count rebind. Old4e8 packet is immutable."""
from pathlib import Path
import argparse,ast,hashlib,json,copy,difflib
P=Path(__file__).resolve().parent;W=P.parent;B=W/'last-submission-repair-qualification-next-dev-r4';H=W/'rq4-root-helpers-next-dev-r3'
OLD='4e8b071b9405cf6961d91b41ac6605a6b5133996c679ed5f6e14b59f0ba65c55'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def tree(p):return ast.parse(Path(p).read_text('utf-8-sig'))
def dump(n):return ast.dump(n,include_attributes=False)
def methods(p):return {c.name+'.'+n.name:hashlib.sha256(dump(n).encode()).hexdigest() for c in tree(p).body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')}
parser=argparse.ArgumentParser();parser.add_argument('--root-helper-handoff-sha256',required=True);a=parser.parse_args()
assert not (P/'source-handoff.json').exists()
assert sha(B/'source-handoff.json')==OLD and sha(H/'source-handoff-final.json')==a.root_helper_handoff_sha256
old=read(B/'source-handoff.json');helper=read(H/'source-handoff-final.json')
for rel,h in old['files_sha256'].items():assert sha(B/rel)==h,rel
for rel,h in helper['files_sha256'].items():assert sha(H/rel)==h,rel
assert len(methods(H/'test_helpers.py'))==11
old_helper='afb067181e60b610bea2153b7fb377176e22fc26d34b801b71096ff28bf5e83e'
for name in ['run_controller.py','artifact_audit.py','close_controller.py','run_root.py','close_child.ps1','technical_entry.py',
 'test_controller_contracts.py','test_atomic_root.py','test_observation_reader.py','framed_reader.py.txt']:
    raw=(B/name).read_bytes()
    if name not in ('run_controller.py','close_controller.py'):(P/name).write_bytes(raw);continue
    source=raw.decode('utf-8-sig')
    if name=='run_controller.py':
        source=source.replace(old_helper,a.root_helper_handoff_sha256)
        source=source.replace('rq4-root-helpers-next-dev/source-handoff.json','rq4-root-helpers-next-dev-r3/source-handoff-final.json')
        source=source.replace('rq4-root-helpers-next-dev/','rq4-root-helpers-next-dev-r3/')
        source=source.replace("len(helper_tests['methods'])==10","len(helper_tests['methods'])==11").replace('exact_reviewed_root_helper10','exact_reviewed_root_helper11')
        source=source.replace("('root-helper-contracts',Path(cfg['root_helper_contracts']['test']),30,20,10)","('root-helper-contracts',Path(cfg['root_helper_contracts']['test']),30,20,11)")
        inverse=source.replace(a.root_helper_handoff_sha256,old_helper)
        inverse=inverse.replace('rq4-root-helpers-next-dev-r3/source-handoff-final.json','rq4-root-helpers-next-dev/source-handoff.json')
        inverse=inverse.replace('rq4-root-helpers-next-dev-r3/','rq4-root-helpers-next-dev/')
        inverse=inverse.replace("len(helper_tests['methods'])==11","len(helper_tests['methods'])==10").replace('exact_reviewed_root_helper11','exact_reviewed_root_helper10')
        inverse=inverse.replace("('root-helper-contracts',Path(cfg['root_helper_contracts']['test']),30,20,11)","('root-helper-contracts',Path(cfg['root_helper_contracts']['test']),30,20,10)")
    else:
        source=source.replace("('root-helper-contracts',10)","('root-helper-contracts',11)")
        inverse=source.replace("('root-helper-contracts',11)","('root-helper-contracts',10)")
    assert dump(ast.parse(inverse))==dump(tree(B/name)),name
    compile(source,str(P/name),'exec');(P/name).write_text(source,encoding='utf-8',newline='\n')
for p in P.glob('*.py'):compile(p.read_text('utf-8-sig'),str(p),'exec')
cfg=read(B/'binding.template.NOT_READY.json')
cfg['technical_entry']=dict(path=P.name+'/technical_entry.py',sha256=sha(P/'technical_entry.py'))
cfg['root_helper_contracts']=dict(handoff=dict(path=H.name+'/source-handoff-final.json',sha256=a.root_helper_handoff_sha256),
    test=H.name+'/test_helpers.py',methods=methods(H/'test_helpers.py'))
cfg['missing_bindings']=['root absolute final private RQ4 instantiation','final qualifier/helper source peers and root publication',
 'complete known7890+late3+actual later metadata preparers fresh before/under lock','one actual new6000 only future launch']
save(P/'binding.template.NOT_READY.json',cfg)
atomic=read(B/'atomic-binding.template.NOT_READY.json')
for key,name in [('driver','run_controller.py'),('closer','close_controller.py')]:atomic[key]=dict(path=P.name+'/'+name,sha256=sha(P/name))
save(P/'atomic-binding.template.NOT_READY.json',atomic)
protocol=read(B/'protocol.json');protocol.update(source_revision='RQ4_FINAL_HELPER_R3_PATH_AND11_COUNT',planned_contract_executions=110,
 prepared_contracts_by_slot=[24,24,18,12,15,4,2,11],root_helper_handoff_sha256=a.root_helper_handoff_sha256,clock=None)
save(P/'protocol.json',protocol)
proof=read(B/'source-proof.json');proof.update(source_revision='RQ4_FINAL_HELPER_R3_PATH_AND11_COUNT',previous_unissued_handoff_sha256=OLD,
 prepared_contract_methods_by_slot=[24,24,18,12,15,4,2,11],prepared_executions=110,
 root_helper_handoff_sha256=a.root_helper_handoff_sha256,all_other_runtime_test_source_raw_exact_unissued_R1=True,
 final_driver_and_closer_whole_AST_inverse_exact=True)
save(P/'source-proof.json',proof)
(P/'README.txt').write_text((B/'README.txt').read_text('utf-8').replace('109 future','110 future').replace('10roothelper','11roothelper')+
 '\nFinal helper source is rq4-root-helpers-next-dev-r3 (R2crossschemafix plus sole fixedPACKET path to this -r4-r2). Oldunissued4e8/R1helperafb remain byte-exact/unexecuted. Alloldguard/audit/methodassertions unchanged; only helper references/count change.\n',encoding='utf-8',newline='\n')
external=dict(old['external_refs_sha256']);external[B.name+'/source-handoff.json']=OLD
for rel,h in old['files_sha256'].items():external[B.name+'/'+rel]=h
external[H.name+'/source-handoff-final.json']=a.root_helper_handoff_sha256
for rel,h in helper['files_sha256'].items():external[H.name+'/'+rel]=h
for ref in helper.get('external_refs_sha256',{}).items():
    rel,h=ref;rel=Path(rel).relative_to(W).as_posix() if Path(rel).is_absolute() else rel
    external[rel]=h
for rel,h in external.items():assert sha(W/rel)==h,rel
patch=''.join(''.join(difflib.unified_diff((B/n).read_text('utf-8-sig').splitlines(True),(P/n).read_text('utf-8-sig').splitlines(True),fromfile='unissued4e8/'+n,tofile='finalRQ4/'+n)) for n in ['run_controller.py','close_controller.py'])
(P/'RQ4-final-helper-rebind.patch').write_text(patch,encoding='utf-8',newline='\n')
files={p.relative_to(P).as_posix():sha(p) for p in sorted(P.rglob('*')) if p.is_file() and p!=P/'source-handoff.json'}
save(P/'source-handoff.json',dict(schema='standard-repair-qualification-source-handoff-v4-r2',status='FROZEN_SOURCE_ONLY_NOT_READY_PENDING_PEER',
 files_sha256=files,external_refs_sha256=external,previous_unissued_handoff_sha256=OLD,prepared_contract_executions=110,
 actual_contract_executions=0,archive_sha256=old['archive_sha256'],candidate_handoff_sha256=old['candidate_handoff_sha256'],
 actual_clock=None,actual_metrics=None,approval=None))
print(json.dumps(dict(handoff=sha(P/'source-handoff.json'),local=len(files),external=len(external),planned=110,executed=0)))
