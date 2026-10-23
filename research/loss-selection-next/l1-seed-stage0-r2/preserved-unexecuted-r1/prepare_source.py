"""Future source-only LOSS seed preparation from the actually tested LOSS tree.

No candidate-runtime import/test/fit/API/experiment clock is performed here.
The copied, pinned build_submission tool is an AST compiler using stdlib only.
"""
from pathlib import Path
import argparse,ast,hashlib,importlib.util,json,re,sys,time,zipfile
sys.dont_write_bytecode=True
BASE_REF='loss-stage0-packet/manifest.json'
BASE_SHA='319d6035162f46e6a1272a833d5f8668c731294b443eeae2dd8fc8c897dabfdc'
BASE_ARCHIVE='037f88de1d547a18ff63e300c81b4ecd9e36935d2ddc32a0ba3fe304b105439d'
HANDOFF='00a41c5c9d9bb4363e58e7c5a98ebd6356b86bbf107a23065249c2958edf2086'


def read(path):return json.loads(path.read_text('utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def hash_map(value):
    assert type(value) is dict and value
    for name,digest in value.items():
        assert type(name) is str and not Path(name).is_absolute() and '..' not in Path(name).parts
        assert type(digest) is str and re.fullmatch('[0-9a-f]{64}',digest)
    return value
def registry(path):
    nodes=[n for n in ast.parse(path.read_text('utf-8')).body if isinstance(n,ast.Assign)
           and any(isinstance(t,ast.Name) and t.id=='CHECKS' for t in n.targets)]
    assert len(nodes)==1
    result=ast.literal_eval(nodes[0].value)
    assert type(result) is dict and all(type(k) is str and type(v) is int and v>0 for k,v in result.items())
    return result
def methods(path):
    return [n.name for c in ast.parse(path.read_text('utf-8')).body if isinstance(c,ast.ClassDef)
            for n in c.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-sha256',required=True)
    args=parser.parse_args();started=time.monotonic();this=Path(__file__).resolve();work=this.parents[1]
    assert __debug__ and sha(this)==args.self_sha256
    overlay=work/'loss-agent-seed-next-dev';source=work/'loss00';dest=work/'lsdev';packet=work/'ls-stage0-packet'
    assert sha(work/BASE_REF)==BASE_SHA and sha(overlay/'source-handoff.json')==HANDOFF
    base=read(work/BASE_REF);handoff=read(overlay/'source-handoff.json')
    assert type(base) is dict and type(handoff) is dict
    copied=hash_map(base['source_files_sha256']);compiled=hash_map(base['compiled_sha256'])
    assert base['source_root']=='loss00' and len(copied)==694 and len(compiled)==68
    assert type(base['registry']) is dict and all(type(n) is str and type(c) is int and c>0 for n,c in base['registry'].items())
    assert base['source_expected_checks']==487 and sum(base['registry'].values())==487 and base['source_skipped_expected']==0
    assert base['archive_sha256']==BASE_ARCHIVE and sha(work/base['archive'])==BASE_ARCHIVE
    assert handoff['prepared_methods']==12 and handoff['defaultOFF_scheduler2_AST_equal_CP1'] is True
    handoff_files=hash_map(handoff['files_sha256'])
    for name,digest in handoff_files.items():assert sha(overlay/name)==digest
    proof=read(overlay/'flat-mapping-static-proof.json');closure=read(overlay/'fixture-inventory-closure.json')
    assert type(proof) is dict and type(closure) is dict
    assert type(proof['changed_vs_tested_LOSS']) is dict and set(proof['changed_vs_tested_LOSS'])=={'automl_runner.py','automl_search_stages.py'}
    assert proof['candidate_members']==68 and proof['unchanged_vs_tested_LOSS']==66
    assert closure['base_manifest_sha256']==BASE_SHA and closure['path_intersection']==[]
    additions=hash_map(closure['new_test_fixture_sha256'])
    assert set(additions)=={'tests/test_loss_seed.py','tests/fixtures/cp1_champion_regression.json',
        'tests/fixtures/cp1_stages.py','tests/fixtures/fixed_l1_seed_template.json',
        'tests/fixtures/loss_seed_cp1_fixture_sha.json','tests/fixtures/protected_control_regression.json'}
    assert not set(additions)&set(copied),'New fixture must not overwrite any existing LOSS file'
    schedulers=handoff['scheduler_modified_paths']
    assert type(schedulers) is list and set(schedulers)=={'src/automl/search/stages.py','src/automl/search/runner.py'} and len(schedulers)==2
    replacements={name:handoff_files[name] for name in schedulers}
    assert set(replacements)<=set(copied)
    # Only copy the two scheduler overlays; six tested backend modules stay base.
    backend=handoff['backend6_copied_byteexact_tested']
    assert type(backend) is list and len(backend)==len(set(backend))==6
    for name in backend:
        assert name in copied and sha(overlay/name)==copied[name]
    new_files={**replacements,**additions}
    assert all(sha(overlay/name)==digest for name,digest in new_files.items())
    expected_union=set(copied)|set(new_files)
    assert not dest.exists() and not packet.exists(),'Exclusive new source/packet required; no resume/overwrite'
    def cap():assert time.monotonic()-started<60,'Source preparation60s cap'
    def target(name):
        path=(dest/name).resolve()
        assert not Path(name).is_absolute() and path.is_relative_to(dest.resolve())
        return path
    for name,digest in copied.items():
        cap();original=source/name;assert sha(original)==digest
        out=target(name);out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(original.read_bytes());assert sha(out)==digest
    assert registry(dest/'tools/run_checks.py')==base['registry']
    for name,digest in new_files.items():
        out=target(name);out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes((overlay/name).read_bytes());assert sha(out)==digest;cap()
    added_methods=methods(dest/'tests/test_loss_seed.py');assert len(added_methods)==len(set(added_methods))==12
    gate=dest/'tools/run_checks.py';text=gate.read_text('utf-8');marker="'test_loss_profiles.py':16}"
    assert text.count(marker)==1
    gate.write_text(text.replace(marker,"'test_loss_profiles.py':16,'test_loss_seed.py':12}"),encoding='utf-8')
    expected_registry={**base['registry'],'test_loss_seed.py':12}
    assert registry(gate)==expected_registry and sum(expected_registry.values())==499
    builder=dest/'tools/build_submission.py';assert sha(builder)==copied['tools/build_submission.py']
    spec=importlib.util.spec_from_file_location('_loss_seed_stdlib_AST_builder',builder)
    tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
    files=tool.build_files();assert type(files) is dict and len(files)==68 and set(files)==set(compiled)
    with zipfile.ZipFile(work/base['archive']) as archive:
        assert len(archive.namelist())==len(set(archive.namelist()))==68
        prior={name:archive.read(name) for name in archive.namelist()}
    assert all(hashlib.sha256(data).hexdigest()==compiled[name] for name,data in prior.items())
    changed=sorted(name for name in files if files[name]!=prior[name])
    assert changed==sorted(proof['changed_vs_tested_LOSS'])
    assert all(hashlib.sha256(files[name]).hexdigest()==proof['changed_vs_tested_LOSS'][name]['candidate_sha256'] for name in changed)
    assert files['requirements.txt']==prior['requirements.txt']
    actual={f.relative_to(dest).as_posix():sha(f) for f in dest.rglob('*') if f.is_file()}
    assert set(actual)==expected_union and len(actual)==len(expected_union)
    changed_source=sorted(name for name in copied if actual[name]!=copied[name])
    assert changed_source==sorted(schedulers+['tools/run_checks.py'])
    assert set(actual)-set(copied)==set(additions)
    assert actual['tests/fixtures/cp1_fixture_sha.json']==copied['tests/fixtures/cp1_fixture_sha.json']
    packet.mkdir();archive=packet/'loss-seed-source.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as out:
        for name,data in sorted(files.items()):
            assert Path(name).name==name
            entry=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;out.writestr(entry,data)
    assert all(sha(source/name)==digest for name,digest in copied.items())
    assert all(sha(overlay/name)==digest for name,digest in handoff_files.items())
    assert sha(work/BASE_REF)==BASE_SHA and sha(overlay/'source-handoff.json')==HANDOFF
    manifest=dict(status='source_prepared_only_no_gates_or_jobs',source_root='lsdev',archive='ls-stage0-packet/loss-seed-source.zip',
        archive_sha256=sha(archive),base_manifest=BASE_REF,base_manifest_sha256=BASE_SHA,base_archive_sha256=BASE_ARCHIVE,
        base_source_file_count=len(copied),source_union_count=len(expected_union),source_files_sha256=actual,
        overlay_handoff_sha256=HANDOFF,overlay_files_sha256=new_files,added_source_files=sorted(additions),changed_copied_source=changed_source,
        registry=expected_registry,source_expected_checks=499,source_skipped_expected=0,
        compiled_sha256={name:hashlib.sha256(data).hexdigest() for name,data in files.items()},changed_flat_modules=changed,
        unchanged_flat_members=len(files)-len(changed),exact_repeated_expected_checks=23,exact_flat_loss_checks=16,
        exact_flat_seed_checks=12,exact_flat_combined_checks=28,prepared_seed_methods=added_methods,
        original_loss_test_sha256=actual['tests/test_loss_profiles.py'],original_seed_test_sha256=actual['tests/test_loss_seed.py'],
        self_sha256=sha(this),preparation_seconds=time.monotonic()-started,source_compiler_only_imported=True,
        candidate_runtime_imports=0,source_gates_executed=0,exact_gates_executed=0,model_fits=0,API_calls=0,clock_assigned=False,launch_ready=False)
    (packet/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    cap();print(json.dumps({k:manifest[k] for k in ['status','source_union_count','archive_sha256','source_expected_checks','preparation_seconds','model_fits','API_calls','clock_assigned']}))


if __name__=='__main__':main()
