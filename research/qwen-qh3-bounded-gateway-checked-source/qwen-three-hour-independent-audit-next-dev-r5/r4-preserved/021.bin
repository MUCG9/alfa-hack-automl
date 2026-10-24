"""R2 source/AST/hash census only; no candidate imports or tests executed."""
from pathlib import Path
import ast
import copy
import difflib
import hashlib
import json

P=Path(__file__).resolve().parent
WORK=P.parent.parent
OLD=P/'source-evidence/r1'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ah(node):return hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
def save(name,value):(P/name).write_bytes((json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8'))
def ref(path):return dict(path=str(path.relative_to(WORK)).replace('\\','/'),sha256=sha(path))


def main():
    assert not (P/'source-handoff.json').exists(),'already_frozen_no_rewrite'
    old=json.loads((OLD/'source-handoff.json').read_text('utf-8'))
    preserved={name:sha(OLD/name) for name in old['files_sha256']}
    assert preserved==old['files_sha256']
    assert sha(OLD/'source-handoff.json')=='ca8f814393face3bcf27fedde2739be7ded3e3c56449b234cd112bb906c83709'
    assert sha(OLD/'independent-review-r1.json')=='4311ae2fd23ee2d33f529a975166a44b6509343076743ef4b1ec1fd601bc07a8'
    for name in ['r4_primitives.py','primitive-provenance.json','test_audit_contracts.py','binding.template.NOT_READY.json']:
        assert (P/name).read_bytes()==(OLD/name).read_bytes()
    before=ast.parse((OLD/'audit_final.py').read_text('utf-8'));after=ast.parse((P/'audit_final.py').read_text('utf-8'))
    previous={n.name:n for n in before.body if isinstance(n,(ast.ClassDef,ast.FunctionDef))}
    current={n.name:n for n in after.body if isinstance(n,(ast.ClassDef,ast.FunctionDef))}
    changed={name for name in previous if ah(previous[name])!=ah(current[name])}
    assert changed=={'LiteralCSV','verify_task'} and set(current)-set(previous)=={'exact_csv_roles'}
    inverse=copy.deepcopy(after);inverse.body=[copy.deepcopy(previous.get(n.name,n))
        if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in changed else n for n in inverse.body
        if not isinstance(n,ast.FunctionDef) or n.name!='exact_csv_roles']
    assert ah(inverse)==ah(before)
    sources={};methods={}
    for path in sorted(P.glob('*.py')):
        tree=ast.parse(path.read_text('utf-8'));compile(tree,str(path),'exec')
        sources[path.name]=dict(sha256=sha(path),AST_sha256=ah(tree))
        for cls in tree.body:
            if isinstance(cls,ast.ClassDef):
                methods.update({cls.name+'.'+n.name:ah(n) for n in cls.body
                    if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')})
    assert len(methods)==17
    old_methods=json.loads((OLD/'source-proof.json').read_text('utf-8'))['methods_AST_sha256']
    assert all(methods[name]==h for name,h in old_methods.items()) and len(old_methods)==15
    patch=''.join(difflib.unified_diff((OLD/'audit_final.py').read_text('utf-8').splitlines(True),
        (P/'audit_final.py').read_text('utf-8').splitlines(True),fromfile='frozen-r1/audit_final.py',tofile='r2/audit_final.py'))
    (P/'Q3A01-role-only.patch').write_bytes(patch.encode('utf-8'))
    save('r1-preservation.json',dict(schema='qwen-three-hour-auditor-R1-preservation-v1',
        handoff=ref(OLD/'source-handoff.json'),review=ref(OLD/'independent-review-r1.json'),
        all_nine_R1_files_sha256=preserved,original_directory_unchanged=True))
    proof=dict(schema='qwen-three-hour-auditor-Q3A01-R2-source-proof-v1',status='SOURCE_ONLY_NOT_EXECUTED',
        changed_existing_definitions=sorted(changed),new_definition='exact_csv_roles',
        whole_module_inverse_to_R1_AST_exact=True,R1_AST_sha256=ah(before),source_AST=sources,
        primitive_bytes_and_all_R4_formulas_assertions_exact=True,
        old15_test_source_bytes_and_methods_AST_exact=True,prepared_method_count=len(methods),methods_AST_sha256=methods,
        correction='exact resolved path+role converter map; pristine CLASS train target+ID only, test/sample ID only; sealed worker prediction roles get output or y_true/y_pred literals',
        new_fixtures=['native pandas numeric y_true/y_pred/output collision unchanged vs native baseline; lexical001/NA train/submission/validation preserved; numeric REG output remains native',
                      'mock unknown same-basename path rejected before parse; exact role converter set and extraneous numeric-predictor converter rejected'],
        actual_tests_executed=0,actual_candidate_imports=0,actual_data_or_array_reads=0,actual_fits=0,actual_API_calls=0,
        source_preparation='stdlib metadata/hash/AST/compile-as-text only',actual_ready_clock_root_archive=None)
    save('source-proof.json',proof)
    protocol=json.loads((OLD/'protocol.json').read_text('utf-8'))
    protocol.update(status='FROZEN_R2_SOURCE_ONLY_NOT_READY',prepared_contracts=17,actual_contracts_executed=0,
        Q3A01='exact path and role only; no blanket output/y_true/y_pred converters on pristine predictors')
    save('protocol.json',protocol)
    readme='''Q3A01 R2 source-only correction

R1 ca8f and peer4311 are preserved verbatim under source-evidence/r1 and the
original directory. Only LiteralCSV, its verify_task wiring, and one explicit
exact_csv_roles helper change runtime source. All R4/C5/LOSS primitives and
assertions remain byte-exact, as do the original fifteen test methods/file.

Roles are an exact resolved-path map: pristine CLASS train gets declared target
and ID literal converters; pristine test and sample get ID only. Regression
targets and all numeric predictors retain native parsing even when a predictor
is named y_true, y_pred or the output column. Saved prediction CSVs are identified
from the already sealed worker-result sibling paths inside actual parent callback
roots. Submission roles get declared CLASS output+ID; validation roles get CLASS
y_true/y_pred. Unknown paths/conflicting roles/extraneous converters STOP.
No suffix or column name by itself grants a role.

Two NEW prepared synthetic mock/native-fixture methods cover numeric-name
collisions and lexical001/NA, yielding seventeen prepared/zero executed methods.
No candidates/tests/data/arrays/models/API/PID observations/actual clock ran.
Main CLI, schema, pretruth barrier, source qualification, common10800/audit600
(child570), metrics/provenance/fresh-refit/class gates and NULL failure semantics
are unchanged. Future actual qualification/root/seals/clock remain NULL/NOT_READY.
The full original rationale remains in source-evidence/r1/README.txt.
'''
    (P/'README.txt').write_bytes(readme.encode('utf-8'))
    refs=old['external_source_refs']+[ref(OLD/'source-handoff.json'),ref(OLD/'independent-review-r1.json')]
    for item in refs:assert sha(WORK/item['path'])==item['sha256']
    files={str(q.relative_to(P)).replace('\\','/'):sha(q) for q in sorted(P.rglob('*')) if q.is_file()}
    save('source-handoff.json',dict(schema='qwen-three-hour-independent-artifact-audit-source-handoff-v1',
        revision='Q3A01_R2',status='FROZEN_SOURCE_ONLY_NOT_READY_PENDING_INDEPENDENT_PEER',
        files_sha256=files,external_source_refs=refs,prepared_method_count=17,actual_tests_executed=0,
        actual_candidate_imports=0,actual_fits=0,actual_API_calls=0,actual_metrics=None,
        actual_archive_root_outer_binding=None,actual_clock=None,
        requires='narrow independent R2 source peer then root actual source/qualification/outer admission; no runtime authorization from source freeze'))
    print(json.dumps(dict(handoff_sha256=sha(P/'source-handoff.json'),auditor_sha256=sha(P/'audit_final.py'),
        primitives_sha256=sha(P/'r4_primitives.py'),new_test_sha256=sha(P/'test_csv_role_contracts.py'),
        local_pins=len(files),external_pins=len(refs),prepared_methods=17,actual_executed=0)))


if __name__=='__main__':main()
