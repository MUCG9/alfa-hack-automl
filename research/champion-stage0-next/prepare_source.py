"""Prepare isolated champion source/archive, not tests, fits or a run clock.
Only a future reviewed serial Stage0 may execute its registered contracts.
The source compiler imported below is stdlib-only; application is AST-compiled,
never imported or run. All old/frozen files are read-only inputs.
"""
from pathlib import Path
import argparse,ast,hashlib,importlib.util,json,time,zipfile

BASE_MANIFEST='8faf33cd81c0e864bcf338828c34447000111eda85bc719b8f43312d2babae9a'
OVERLAY_MANIFEST='bf577474788a6896f1724cf426e383830866fdcc3eb7a8063f76a24cef12df6b'
EXPECTED_OVERLAY={
 'src/automl/search/runner.py':'4807ba7609009e24899fcc5213fe44db4e2f6ad3d63e57ed2af3e20acdedad2f',
 'src/automl/search/stages.py':'d8e79f0cb36612849e0d48b2e486c20e773c09696c2d6e788832f19bee509133',
 'tests/test_champion_seed.py':'7641869fe8a3d59b91a410599e95570268da15e0c40fa5205d4ed050c622cf4c'}
ARCHIVE_A='16120391716fe43b7f0ec2b36f35eaea7511a08cba4f4108da01cd81dea314d0'
def read(p):return json.loads(p.read_text('utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def registry(p):
    node=next(n for n in ast.parse(p.read_text('utf-8')).body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='CHECKS' for t in n.targets))
    return ast.literal_eval(node.value)
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--self-sha256',required=True)
    ap.add_argument('--pinned-test-sha256',required=True)
    a=ap.parse_args();started=time.monotonic()
    this=Path(__file__).resolve();w=this.parent.parent;dest=w/'csdev';packet=w/'cs-stage0-packet'
    assert sha(this)==a.self_sha256 and sha(this.parent/'test_pinned_champion_seed.py')==a.pinned_test_sha256
    assert sha(w/'m4packet/manifest.json')==BASE_MANIFEST
    assert sha(w/'champion-seed-next-dev/manifest.json')==OVERLAY_MANIFEST
    m=read(w/'m4packet/manifest.json');assert m['source_root']=='m3dev' and sum(m['registry'].values())==458
    assert sha(w/m['archive'])==ARCHIVE_A
    assert not dest.exists() and not packet.exists(),'Exclusive new source preparation; never overwrite or resume'
    copied={}
    for name,digest in m['immutable_files'].items():
        if not name.startswith('m3dev/'):continue
        src=w/name;assert sha(src)==digest
        rel=name.removeprefix('m3dev/');target=dest/rel
        assert target.resolve().is_relative_to(dest.resolve())
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(src.read_bytes())
        assert sha(target)==digest;copied[rel]=digest
        assert time.monotonic()-started<60,'Source-only preparation wall60s exceeded'
    for name,digest in EXPECTED_OVERLAY.items():
        src=w/'champion-seed-next-dev'/name;assert sha(src)==digest
        target=dest/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(src.read_bytes())
    fixture=dest/'tests/fixtures/champion_seed';fixture.mkdir(parents=True)
    for src_name,target_name,digest in [
        ('champion-seed-next-dev/champion-t5-regression.json','champion.json','914880505ed751da9fd0a38d7f1724dd860c20d98456ff3efd16a195a0709ad4'),
        ('m2packet/control-r.json','protected_control.json','0480d5e60c6aa42be4a78e300c3baf7a0346d431707ce79cb6850c73d84adf1b')]:
        src=w/src_name;assert sha(src)==digest;(fixture/target_name).write_bytes(src.read_bytes())
    (dest/'tests/test_pinned_champion_seed.py').write_bytes((this.parent/'test_pinned_champion_seed.py').read_bytes())
    gate=dest/'tools/run_checks.py';text=gate.read_text('utf-8');marker="'test_preserved_anchor.py':7}"
    assert text.count(marker)==1
    gate.write_text(text.replace(marker,"'test_preserved_anchor.py':7,'test_champion_seed.py':12,'test_pinned_champion_seed.py':1}"),encoding='utf-8')
    expected={**m['registry'],'test_champion_seed.py':12,'test_pinned_champion_seed.py':1}
    assert registry(gate)==expected and sum(expected.values())==471
    # Import only the existing stdlib compiler. No application runtime imports.
    builder=dest/'tools/build_submission.py'
    spec=importlib.util.spec_from_file_location('_prepared_champion_ast_builder',builder)
    tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
    flat=tool.build_files();assert len(flat)==68 and len([n for n in flat if n.endswith('.py')])==67
    with zipfile.ZipFile(w/m['archive']) as old:
        prior={n:old.read(n) for n in old.namelist()}
    changed=[n for n in sorted(set(prior)|set(flat)) if prior.get(n)!=flat.get(n)]
    assert changed==['automl_runner.py','automl_search_stages.py'],'Only reviewed opt-in runtime modules may differ'
    packet.mkdir()
    archive=packet/'champion-source.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(flat.items()):
            entry=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(entry,data)
    actual={p.relative_to(dest).as_posix():sha(p) for p in dest.rglob('*') if p.is_file()}
    changed_source=sorted(n for n in copied if actual[n]!=copied[n])
    assert changed_source==['src/automl/search/runner.py','src/automl/search/stages.py','tools/run_checks.py']
    for name,digest in m['immutable_files'].items():
        if name.startswith('m3dev/'):assert sha(w/name)==digest,'Frozen source changed'
    manifest=dict(status='source_prepared_only_no_gates_or_jobs',source_root='csdev',
        archive='cs-stage0-packet/champion-source.zip',archive_sha256=sha(archive),
        base_manifest_sha256=BASE_MANIFEST,base_archive_sha256=ARCHIVE_A,
        overlay_manifest_sha256=OVERLAY_MANIFEST,source_files_sha256=actual,
        compiled_sha256={n:hashlib.sha256(b).hexdigest() for n,b in flat.items()},
        changed_flat_modules=changed,changed_copied_source=changed_source,
        registry=expected,source_expected_checks=471,source_skipped_expected=0,
        exact_repeated_expected_checks=23,preparation_seconds=time.monotonic()-started,
        source_compiler_only_imported=True,candidate_runtime_imports=0,
        source_gates_executed=0,exact_gates_executed=0,model_fits=0,API_calls=0,
        clock_assigned=False,launch_ready=False,
        next='Actual T7 terminal and fresh complete ownership/preparer/lock closure; independent prepared-source review and publication; then separately declared bounded serial Stage0 before any paired model run.',
        self_sha256=sha(this),pinned_test_sha256=a.pinned_test_sha256)
    (packet/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    assert time.monotonic()-started<60,'Source-only preparation wall60s exceeded'
    print(json.dumps({k:manifest[k] for k in ['status','archive_sha256','source_expected_checks','changed_flat_modules','preparation_seconds','clock_assigned','source_gates_executed','model_fits','API_calls']}))
if __name__=='__main__':main()
