"""Future full LOSS00 source/registry/AST archive preparation only.
Use exact CP1B690files plus the author's80-file inventory. No class seed,
runtime application import, test, fit, API or research clock is introduced.
"""
from pathlib import Path
import argparse,ast,hashlib,importlib.util,json,sys,time,zipfile
sys.dont_write_bytecode=True
BASE_MANIFEST='5160562be127dc6130a1f3349a21b552c8aac526ead484048982716b037aa1c1'
BASE_ARCHIVE='52627ac5b9da5ee47d8d40951f84edf9b9dede28cca4b4f90504be6bb4e672b8'
HANDOFF='d17be204be34fa53ecbabe40eef819db214ca6ab03929f3a0ce3e52e99e9417c'
INVENTORY='0db7dee20d28f24edc9824f8f43622dd3eaf945ecf9cc4db5f60caf8786e5277'
FLAT_PROOF='4abc51f36ce96a6537ee4e16d6784e7bcaf819fcfa4a9157af1feeee22256b21'
IMPORT_MAP='b0ecbff853bf2c9c9f0621ac8fdaa14a86acecdff4ec9942ad1b2433d592dd69'
TEST='5c26ac47d7ca1299bad73baa64ce7bfbd9793c99fffad60ad971bc9ff9a4dc14'
def read(p):return json.loads(p.read_text('utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def registry(p):
    nodes=[n for n in ast.parse(p.read_text('utf-8')).body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='CHECKS' for t in n.targets)]
    assert len(nodes)==1;return ast.literal_eval(nodes[0].value)
def methods(p):
    return [n.name for c in ast.parse(p.read_text('utf-8')).body if isinstance(c,ast.ClassDef)
        for n in c.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')]
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--self-sha256',required=True)
    a=ap.parse_args();started=time.monotonic();this=Path(__file__).resolve();w=this.parent.parent
    dest=w/'loss00';packet=w/'loss-stage0-packet';overlay=w/'loss-selection-next-dev'
    assert __debug__ and sha(this)==a.self_sha256
    pins={w/'cs-stage0-packet/manifest.json':BASE_MANIFEST,overlay/'source-handoff.json':HANDOFF,
        overlay/'materialization.json':INVENTORY,overlay/'flat-mapping-static-proof.json':FLAT_PROOF,
        overlay/'flat-test-import-map.json':IMPORT_MAP,overlay/'tests/test_loss_profiles.py':TEST}
    assert all(sha(p)==h for p,h in pins.items())
    m=read(w/'cs-stage0-packet/manifest.json');handoff=read(overlay/'source-handoff.json')
    inventory=read(overlay/'materialization.json');proof=read(overlay/'flat-mapping-static-proof.json')
    assert m['source_root']=='csdev' and len(m['source_files_sha256'])==690
    assert sum(m['registry'].values())==471 and m['source_expected_checks']==471 and m['source_skipped_expected']==0
    assert sha(w/m['archive'])==BASE_ARCHIVE and len(m['compiled_sha256'])==68
    assert handoff['prepared_methods']==16 and handoff['default_OFF_AST_equal_all6'] is True
    assert inventory['base_CP1_archive_sha256']==BASE_ARCHIVE and len(inventory['files'])==80
    assert proof['base_members']==proof['candidate_members']==68 and proof['unchanged_members']==62
    assert len(proof['changed_members'])==6
    assert not dest.exists() and not packet.exists(),'Exclusive new source tree and packet required'
    copied={}
    def target(name):
        p=(dest/name).resolve();assert not Path(name).is_absolute() and p.is_relative_to(dest.resolve())
        return p
    def cap():assert time.monotonic()-started<60,'Source preparation wall60s exceeded'
    for name,digest in m['source_files_sha256'].items():
        source=w/'csdev'/name;assert sha(source)==digest
        p=target(name);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(source.read_bytes())
        assert sha(p)==digest;copied[name]=digest;cap()
    assert registry(dest/'tools/run_checks.py')==m['registry']
    # Apply the exact author's materializer inventory, retaining full CP1 fixtures/tools.
    # Calling its standalone tiny80-file materializer here would lose those690 refs.
    for name,entry in inventory['files'].items():
        source=(w/entry['path']).resolve();assert source.is_relative_to(w.resolve()) and sha(source)==entry['sha256']
        p=target(name);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(source.read_bytes())
        assert sha(p)==entry['sha256'];cap()
    tests=methods(dest/'tests/test_loss_profiles.py');assert len(tests)==len(set(tests))==16
    gate=dest/'tools/run_checks.py';text=gate.read_text('utf-8');marker="'test_pinned_champion_seed.py':1}"
    assert text.count(marker)==1
    gate.write_text(text.replace(marker,"'test_pinned_champion_seed.py':1,'test_loss_profiles.py':16}"),encoding='utf-8')
    expected={**m['registry'],'test_loss_profiles.py':16}
    assert registry(gate)==expected and sum(expected.values())==487
    builder=dest/'tools/build_submission.py';assert sha(builder)==copied['tools/build_submission.py']
    spec=importlib.util.spec_from_file_location('_loss_stdlib_ast_builder',builder)
    tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
    flat=tool.build_files();assert len(flat)==68 and sum(n.endswith('.py') for n in flat)==67
    with zipfile.ZipFile(w/m['archive']) as old:
        assert len(old.namelist())==len(set(old.namelist()))==68
        prior={n:old.read(n) for n in old.namelist()}
    assert set(prior)==set(flat)==set(m['compiled_sha256'])
    assert all(hashlib.sha256(data).hexdigest()==m['compiled_sha256'][n] for n,data in prior.items())
    changed=[n for n in sorted(flat) if flat[n]!=prior[n]]
    assert changed==sorted(proof['changed_members'])
    assert all(hashlib.sha256(flat[n]).hexdigest()==proof['changed_members'][n]['candidate_sha256'] for n in changed)
    assert flat['requirements.txt']==prior['requirements.txt']
    packet.mkdir();archive=packet/'loss-source.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(flat.items()):
            assert Path(name).name==name
            entry=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(entry,data)
    actual={p.relative_to(dest).as_posix():sha(p) for p in dest.rglob('*') if p.is_file()}
    changed_source=sorted(n for n in copied if actual[n]!=copied[n])
    assert changed_source==sorted(handoff['changed_source_paths']+['tools/run_checks.py'])
    added=sorted(set(actual)-set(copied))
    assert added==['tests/fixtures/cp1_capabilities.json','tests/fixtures/cp1_fixture_sha.json',
        'tests/fixtures/cp1_lightgbm.py','tests/test_loss_profiles.py'] and len(actual)==694
    assert all(sha(w/'csdev'/n)==h for n,h in copied.items())
    assert all(sha(p)==h for p,h in pins.items())
    manifest=dict(status='source_prepared_only_no_gates_or_jobs',source_root='loss00',
        archive='loss-stage0-packet/loss-source.zip',archive_sha256=sha(archive),base_manifest_sha256=BASE_MANIFEST,
        base_archive_sha256=BASE_ARCHIVE,overlay_handoff_sha256=HANDOFF,materialization_inventory_sha256=INVENTORY,
        flat_mapping_proof_sha256=FLAT_PROOF,flat_import_map_sha256=IMPORT_MAP,source_files_sha256=actual,
        compiled_sha256={n:hashlib.sha256(b).hexdigest() for n,b in flat.items()},changed_flat_modules=changed,
        unchanged_flat_members=62,changed_copied_source=changed_source,added_source_files=added,
        registry=expected,prepared_loss_methods=tests,source_expected_checks=487,source_skipped_expected=0,
        exact_repeated_expected_checks=23,exact_flat_loss_checks=16,expected_loss_tiny_fit_calls_per_suite=9,
        original_loss_test_sha256=TEST,self_sha256=sha(this),preparation_seconds=time.monotonic()-started,
        source_compiler_only_imported=True,materializer_inventory_applied=True,standalone_tiny_materializer_executed=False,
        candidate_runtime_imports=0,source_gates_executed=0,exact_gates_executed=0,model_fits=0,API_calls=0,
        clock_assigned=False,launch_ready=False)
    (packet/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    cap();print(json.dumps({k:manifest[k] for k in ['status','archive_sha256','source_expected_checks',
        'changed_flat_modules','preparation_seconds','clock_assigned','source_gates_executed','model_fits','API_calls']}))
if __name__=='__main__':main()
