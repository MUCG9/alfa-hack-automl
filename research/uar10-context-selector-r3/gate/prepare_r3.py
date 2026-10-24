"""SOURCE metadata only: exact two-test overlay; never config/import/test/run."""
from pathlib import Path
import argparse
import ast
import copy
import difflib
import hashlib
import json

HERE=Path(__file__).resolve().parent;WORK=HERE.parent
OLD=WORK/'uar10-context-selector-gate-next-dev-r2'
OVERLAY=WORK/'combined-legacy-test-compatibility-next-dev'
OVERLAY_SHA='83dcc7a5e69b7896339e6b5a4ddcd30b122af32ae32698090dd3b1a4d5f2699b'
REPLACEMENTS={
 'tests/test_uar_hpo_fair_reserve.py':{'before_sha256':'8bfe59fa6bd0114c3867e1ef426f1f155cd83fbe3ba90709a332046b903d5643','after_sha256':'b51ce05a2533515647ec04f521828c6c23e223bf3d4dbbfc287191f05eaa7252','candidate_path':'candidate/tests/test_uar_hpo_fair_reserve.py'},
 'tests/test_uar_loss_backend.py':{'before_sha256':'b882f673692ef758f3505c456a98d5883d25a37a2d75f3e611c3958b9aa58a7f','after_sha256':'2240cef09e932130cd3d5350b02e2f5260b90f5b54259168695aa0936cced787','candidate_path':'candidate/tests/test_uar_loss_backend.py'}}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def dump(n):return ast.dump(n,include_attributes=False)
def save(name,value):(HERE/name).write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')

p=argparse.ArgumentParser();p.add_argument('--compat-review-sha256',required=True);a=p.parse_args()
review=WORK/'combined-legacy-test-compatibility-independent-review-r1.json'
assert sha(review)==a.compat_review_sha256
assert sha(OVERLAY/'source-handoff.json')==OVERLAY_SHA
overlay=read(OVERLAY/'source-handoff.json');assert overlay['canonical_replacements']==REPLACEMENTS
assert sha(OLD/'source-handoff.json')=='26e0a7dd31291c2ab23ae79af76f1dbb0149a5861fb198fefb69b791b355017c'
old_handoff=read(OLD/'source-handoff.json')
for name,h in old_handoff['files_sha256'].items():assert sha(OLD/name)==h
for name,h in overlay['files_sha256'].items():assert sha(OVERLAY/name)==h
runtime=['run_gate.py','technical_entry.py','contracts.py','close_gate.py','run_root.py','close_child.ps1']
for name in runtime+['test_gate_plumbing.py','atomic-binding.template.json']:
    assert not (HERE/name).exists(),'new_packet_output_already_exists'
    (HERE/name).write_bytes((OLD/name).read_bytes())

before=(OLD/'run_gate.py').read_text('utf-8-sig')
constant="COMPOSITION_PEER_SHA='94b29ff1f4370f7167ffda71d27ec5316e85ee6698a88b2a41726088963c0961'"
addition="\nCOMPAT_HANDOFF_SHA="+repr(OVERLAY_SHA)+"\nCOMPAT_PEER_SHA="+repr(a.compat_review_sha256)+"\nCOMPAT_REPLACEMENTS="+repr(REPLACEMENTS)
assert before.count(constant)==1
old='''    composition=read(work/'fitting-context-selector-combined-next-dev/source-handoff.json')
    for relative,h in composition['files_sha256'].items():
        if relative.startswith('candidate/'):
            path=str(root/relative[len('candidate/'):])
            need(pins.get(path)==h and digest(path)==h,'actual_canonical_must_equal_reviewed_composition')
'''
new='''    # Exactly TWO reviewed test helpers may differ; every runtime/other test
    # stays byte bound to the immutable composition. No generic override map.
    compat_path=work/'combined-legacy-test-compatibility-next-dev/source-handoff.json'
    compat_peer=work/'combined-legacy-test-compatibility-independent-review-r1.json'
    for source,h in [(compat_path,COMPAT_HANDOFF_SHA),(compat_peer,COMPAT_PEER_SHA)]:
        need(pins.get(str(source))==h and digest(source)==h,'exact_two_test_overlay_and_peer_required')
    compat=read(compat_path)
    need(compat.get('canonical_replacements')==COMPAT_REPLACEMENTS
         and set(COMPAT_REPLACEMENTS)=={'tests/test_uar_hpo_fair_reserve.py','tests/test_uar_loss_backend.py'},
         'only_two_exact_reviewed_test_helper_replacements_allowed')
    composition=read(work/'fitting-context-selector-combined-next-dev/source-handoff.json')
    for relative,h in composition['files_sha256'].items():
        if relative.startswith('candidate/'):
            target=relative[len('candidate/'):];path=str(root/target)
            if target in COMPAT_REPLACEMENTS:
                replacement=COMPAT_REPLACEMENTS[target]
                need(replacement['before_sha256']==h,'overlay_original_test_pin_changed')
                candidate=compat_path.parent/replacement['candidate_path']
                h=replacement['after_sha256']
                need(pins.get(str(candidate))==h and digest(candidate)==h,
                     'exact_reviewed_test_helper_source_required')
            need(pins.get(path)==h and digest(path)==h,'actual_canonical_must_equal_reviewed_composition_or_two_exact_tests')
'''
assert before.count(old)==1
after=before.replace(constant,constant+addition).replace(old,new)
assert dump(ast.parse(after.replace(constant+addition,constant).replace(new,old)))==dump(ast.parse(before))
(HERE/'run_gate.py').write_text(after,encoding='utf-8')
for name in runtime[1:]:assert sha(HERE/name)==sha(OLD/name)
old_ast=ast.parse(before);new_ast=ast.parse(after)
old_defs={n.name:dump(n) for n in old_ast.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
new_defs={n.name:dump(n) for n in new_ast.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
assert old_defs.keys()==new_defs.keys()
assert all(v==new_defs[k] for k,v in old_defs.items() if k!='config')

whitelist=read(OLD/'mapped-method-whitelist.json');original=copy.deepcopy(whitelist)
changed=[]
for row in whitelist['suites']:
    key=row['test_relative_path']
    if key in REPLACEMENTS:
        assert row['source_test_sha256']==REPLACEMENTS[key]['before_sha256']
        row['source_test_sha256']=REPLACEMENTS[key]['after_sha256']
        row['source_review_sha256']=a.compat_review_sha256;changed.append(key)
assert set(changed)==set(REPLACEMENTS)
for oldrow,newrow in zip(original['suites'],whitelist['suites']):
    if oldrow['test_relative_path'] not in REPLACEMENTS:assert oldrow==newrow
    else:
        reverse=copy.deepcopy(newrow);reverse['source_test_sha256']=oldrow['source_test_sha256'];reverse['source_review_sha256']=oldrow['source_review_sha256']
        assert reverse==oldrow
assert len(whitelist['suites'])==14 and sum(len(s['selected_methods']) for s in whitelist['suites'])==174
save('mapped-method-whitelist.json',whitelist)
template=read(OLD/'private-manifest.template.json')
template['missing_bindings'][0]='Root integration of exact reviewed two-test helper overlay, actual canonical183 hash inventory and final source publication'
save('private-manifest.template.json',template)
protocol=read(OLD/'protocol.json');protocol['source_revision']='R3_EXACT_TWO_TEST_HELPER_OVERLAY'
protocol.pop('admission_hold')
protocol['two_test_overlay']={'handoff_sha256':OVERLAY_SHA,'independent_review_sha256':a.compat_review_sha256,
    'canonical_replacements':REPLACEMENTS,'all_other_composition_pins_exact':True,
    'runtime_unchanged':True,'old_35_test_methods_assertions_literals_unchanged':True,
    'actual_root_integration_and_PRIVATE_READY_pending':True}
save('protocol.json',protocol)
(HERE/'README.txt').write_text((OLD/'README.txt').read_text('utf-8-sig').split('R2 / U10P1 ONLY:')[0]+'''R3: preserves the R2 actual CX2 typed7340+3 predecessor fix and all five other runtime files byte exactly. Only config() and three fixed constants admit the separately reviewed EXACT two-test compatibility overlay. Both old tests retain every method/assertion/golden witness; every other composition byte remains exact. The mapped whitelist changes ONLY those two source SHA/review SHA pairs, with the other12 rows and all method lists unchanged. No generic override, numerical change, hidden exclusion, READY grant or assigned clock. Root must integrate the reviewed tests, freeze actual private pins, publish and freshly admit one new technical run.\n''',encoding='utf-8')
(HERE/'run_gate.py.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile=OLD.name+'/run_gate.py',tofile=HERE.name+'/run_gate.py')),encoding='utf-8')
for name in HERE.glob('*.py'):compile(name.read_bytes(),name.name,'exec')
save('r3-source-proof.json',{'schema':'uar10-exact-two-test-overlay-source-proof-v1','status':'SOURCE_ONLY_NOT_READY',
    'base_handoff_sha256':sha(OLD/'source-handoff.json'),'overlay_handoff_sha256':OVERLAY_SHA,
    'whole_driver_AST_inverse_exact':True,'changed_function_only':'config','three_fixed_overlay_constants_only':True,
    'five_other_runtime_modules_byte_exact':{n:sha(HERE/n) for n in runtime[1:]},
    'all_non_config_driver_functions_and_predicates_AST_exact':True,
    'whitelist_changed_rows':changed,'whitelist_changed_fields_only':['source_test_sha256','source_review_sha256'],
    'other12_rows_and_all14_method_lists_exact':True,'counts_unchanged':{'source_scripts':66,'source_checks':704,'canonical_python':183,'runtime_modules':72,'flat_members':78,'exact':23,'mapped':174,'suites':14,'gate_contracts_separate':6},
    'actual_runtime_config_import_tests_build_fits_API_data_PID_Git_clock':0,'clock':None,'private_READY':None})
external=dict(old_handoff['external_refs_sha256'])
for rel in ['uar10-context-selector-gate-next-dev-r2/source-handoff.json','uar10-context-selector-gate-independent-review-r2.json',
    'combined-legacy-test-compatibility-next-dev/source-handoff.json','combined-legacy-test-compatibility-independent-review-r1.json']:
    external[rel]=sha(WORK/rel)
for rel,h in overlay['external_refs_sha256'].items():
    assert rel not in external or external[rel]==h
    external[rel]=h
local={p.relative_to(HERE).as_posix():sha(p) for p in HERE.rglob('*') if p.is_file() and p.name!='source-handoff.json'}
handoff=dict(old_handoff);handoff.update(source_revision='R3_EXACT_TWO_TEST_HELPER_OVERLAY',
    previous_handoff_sha256=sha(OLD/'source-handoff.json'),previous_source_review_sha256=sha(WORK/'uar10-context-selector-gate-independent-review-r2.json'),
    files_sha256=local,external_refs_sha256=external,two_test_overlay_handoff_sha256=OVERLAY_SHA,
    two_test_overlay_review_sha256=a.compat_review_sha256,canonical_replacements=REPLACEMENTS)
handoff.pop('runtime_admission_blocker')
save('source-handoff.json',handoff)
print(json.dumps({'source_only_frozen':True,'handoff_sha256':sha(HERE/'source-handoff.json'),
    'driver_sha256':sha(HERE/'run_gate.py'),'local':len(local),'external':len(external),'runtime':False}))
