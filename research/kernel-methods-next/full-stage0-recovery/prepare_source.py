"""Future full KERN00 source/registry/AST archive preparation only.
Use exact CP1B690files plus the author's80-file inventory. No class seed,
runtime application import, test, fit, API or research clock is introduced.
"""
from pathlib import Path
import argparse,ast,hashlib,importlib.util,json,sys,time,zipfile
sys.dont_write_bytecode=True
BASE_MANIFEST='5160562be127dc6130a1f3349a21b552c8aac526ead484048982716b037aa1c1'
BASE_ARCHIVE='52627ac5b9da5ee47d8d40951f84edf9b9dede28cca4b4f90504be6bb4e672b8'
HANDOFF='3794521c315a93900d22df54472299fa6b71d2a36cda0e6b743784c31737fc55'
INVENTORY='2db7ad34129618cbd587c88fa95bc8269711b410866082192fdd0cf4ff0190af'
FLAT_PROOF='57c62766eaa0ef20318a401ea0d198e55aae96368605edaee8deaaea84321747'
TEST='40b466655c63e80ec1aaf6e06952183f0bec08f4d3bacf618d1878620835921c'
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
    dest=w/'kern00';packet=w/'kern-stage0-packet';overlay=w/'kernel-methods-next-dev'
    assert __debug__ and sha(this)==a.self_sha256
    pins={w/'cs-stage0-packet/manifest.json':BASE_MANIFEST,overlay/'source-handoff.json':HANDOFF,
        overlay/'materialization.json':INVENTORY,overlay/'flat-mapping-static-proof.json':FLAT_PROOF,
        overlay/'tests/test_kernel_profiles.py':TEST}
    assert all(sha(p)==h for p,h in pins.items())
    m=read(w/'cs-stage0-packet/manifest.json');handoff=read(overlay/'source-handoff.json')
    inventory=read(overlay/'materialization.json');proof=read(overlay/'flat-mapping-static-proof.json')
    assert m['source_root']=='csdev' and len(m['source_files_sha256'])==690
    assert sum(m['registry'].values())==471 and m['source_expected_checks']==471 and m['source_skipped_expected']==0
    assert sha(w/m['archive'])==BASE_ARCHIVE and len(m['compiled_sha256'])==68
    assert handoff['prepared_test_methods']==12 and handoff['default_OFF_AST_equal_all5'] is True
    assert inventory['base_archive_sha256']==BASE_ARCHIVE and len(inventory['files'])==80
    for field,handoff_field,count in [('changed_runtime_modules','changed_source_paths',5),
            ('new_runtime_modules','new_source_paths',2)]:
        paths=inventory[field];expected_paths=handoff[handoff_field]
        assert type(paths) is list and type(expected_paths) is list and len(paths)==len(expected_paths)==count
        assert all(type(name) is str for name in paths+expected_paths)
        assert len(set(paths))==len(set(expected_paths))==count and set(paths)==set(expected_paths)
    assert proof['base_members']==68 and proof['candidate_members']==70 and proof['unchanged_members']==63
    assert len(proof['changed_members'])==5 and len(proof['new_members'])==2
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
    tests=methods(dest/'tests/test_kernel_profiles.py');assert len(tests)==len(set(tests))==12
    gate=dest/'tools/run_checks.py';text=gate.read_text('utf-8');marker="'test_pinned_champion_seed.py':1}"
    assert text.count(marker)==1
    gate.write_text(text.replace(marker,"'test_pinned_champion_seed.py':1,'test_kernel_profiles.py':12}"),encoding='utf-8')
    expected={**m['registry'],'test_kernel_profiles.py':12}
    assert registry(gate)==expected and sum(expected.values())==483
    builder=dest/'tools/build_submission.py';assert sha(builder)==copied['tools/build_submission.py']
    spec=importlib.util.spec_from_file_location('_kernel_stdlib_ast_builder',builder)
    tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
    flat=tool.build_files();assert len(flat)==70 and sum(n.endswith('.py') for n in flat)==69
    with zipfile.ZipFile(w/m['archive']) as old:
        assert len(old.namelist())==len(set(old.namelist()))==68
        prior={n:old.read(n) for n in old.namelist()}
    assert set(prior)==set(m['compiled_sha256']) and set(prior)<set(flat)
    assert all(hashlib.sha256(data).hexdigest()==m['compiled_sha256'][n] for n,data in prior.items())
    changed=[n for n in sorted(prior) if flat[n]!=prior[n]]
    new_members=sorted(set(flat)-set(prior))
    assert new_members==sorted(proof['new_members'])
    assert all(hashlib.sha256(flat[n]).hexdigest()==proof['new_members'][n] for n in new_members)
    assert changed==sorted(proof['changed_members'])
    assert all(hashlib.sha256(flat[n]).hexdigest()==proof['changed_members'][n]['candidate_sha256'] for n in changed)
    assert flat['requirements.txt']==prior['requirements.txt']
    packet.mkdir();archive=packet/'kernel-source.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(flat.items()):
            assert Path(name).name==name
            entry=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(entry,data)
    actual={p.relative_to(dest).as_posix():sha(p) for p in dest.rglob('*') if p.is_file()}
    changed_source=sorted(n for n in copied if actual[n]!=copied[n])
    assert changed_source==sorted(handoff['changed_source_paths']+['tools/run_checks.py'])
    added=sorted(set(actual)-set(copied))
    assert added==['src/automl/contracts/representations.py',
        'src/automl/execution/model_adapters/kernel_tabular.py',
        'tests/fixtures/cp1_capabilities.json','tests/test_kernel_profiles.py'] and len(actual)==694
    assert all(sha(w/'csdev'/n)==h for n,h in copied.items())
    assert all(sha(p)==h for p,h in pins.items())
    manifest=dict(status='source_prepared_only_no_gates_or_jobs',source_root='kern00',
        archive='kern-stage0-packet/kernel-source.zip',archive_sha256=sha(archive),base_manifest_sha256=BASE_MANIFEST,
        base_archive_sha256=BASE_ARCHIVE,overlay_handoff_sha256=HANDOFF,materialization_inventory_sha256=INVENTORY,
        flat_mapping_proof_sha256=FLAT_PROOF,source_files_sha256=actual,
        compiled_sha256={n:hashlib.sha256(b).hexdigest() for n,b in flat.items()},changed_flat_modules=changed,
        unchanged_flat_members=63,new_flat_members=new_members,changed_copied_source=changed_source,added_source_files=added,
        registry=expected,prepared_kernel_methods=tests,source_expected_checks=483,source_skipped_expected=0,
        exact_repeated_expected_checks=23,exact_flat_kernel_checks=12,expected_kernel_tiny_fit_calls_per_suite=11,
        original_kernel_test_sha256=TEST,self_sha256=sha(this),preparation_seconds=time.monotonic()-started,
        source_compiler_only_imported=True,materializer_inventory_applied=True,standalone_tiny_materializer_executed=False,
        candidate_runtime_imports=0,source_gates_executed=0,exact_gates_executed=0,model_fits=0,API_calls=0,
        clock_assigned=False,launch_ready=False)
    (packet/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    cap();print(json.dumps({k:manifest[k] for k in ['status','archive_sha256','source_expected_checks',
        'changed_flat_modules','preparation_seconds','clock_assigned','source_gates_executed','model_fits','API_calls']}))
if __name__=='__main__':main()
