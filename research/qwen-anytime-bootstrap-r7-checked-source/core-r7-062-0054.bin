"""Source-only import adaptation of the qualified R5 strict worker wrapper."""
from pathlib import Path
import ast
import hashlib
import json

HERE=Path(__file__).resolve().parent;WORK=HERE.parent
BASE=WORK/'br-standard-release-next-dev-r5'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(text):return ast.dump(ast.parse(text),include_attributes=False)
assert sha(BASE/'source-handoff.json')=='92cfd41804ca162ba5ec4aeff53a3cb45e6b0c798b93e0c36c1cbb969fdfef08'
source=BASE/'candidate/automl_release_runtime.py'
assert sha(source)=='ad6087fc12ca1c57c7b7764fe1033fc737ca8c067426578262b860a51c973fe4'
replacements={
 'from automl_atomic import atomic_json':'from automl.infrastructure.atomic import atomic_json',
 'from automl_contracts_messages import ExperimentRequest':'from automl.contracts.messages import ExperimentRequest',
 'from automl_infrastructure_resources import ResourceBudget':'from r5_resources import ResourceBudget',
 'from automl_infrastructure_processes import ProcessTree, ProcessCleanupError, ProcessObservationError':'from automl.infrastructure.processes import ProcessTree, ProcessCleanupError, ProcessObservationError',
 'from automl_runtime import worker_entrypoint':'from automl.infrastructure.runtime import worker_entrypoint',
 'from automl_verified_resource_sampling import VerifiedResourceSampler, ResourceSamplingError':'from verified_sampling import VerifiedResourceSampler, ResourceSamplingError'}
before=source.read_text('utf-8-sig');after=before
for original,current in replacements.items():
    assert after.count(original)==1
    after=after.replace(original,current)
inverse=after
for original,current in reversed(list(replacements.items())):
    assert inverse.count(current)==1
    inverse=inverse.replace(current,original)
assert dump(inverse)==dump(before)
for p in [source,BASE/'candidate/automl_infrastructure_resources.py',WORK/'verified-resource-sampling-next-dev/verified_sampling.py']:
    assert p.is_file()
assert sha(WORK/'verified-resource-sampling-next-dev/verified_sampling.py')=='d65ee39eb80c9fc4590cbbf474ee6c09e84cb65abe2d2c367ebcfa415a390cf0'
(HERE/'r5_worker_runtime.py').write_text(after,encoding='utf-8')
(HERE/'r5_resources.py').write_bytes((BASE/'candidate/automl_infrastructure_resources.py').read_bytes())
(HERE/'verified_sampling.py').write_bytes((WORK/'verified-resource-sampling-next-dev/verified_sampling.py').read_bytes())
test_source=BASE/'tests/test_sampling_checkpoint_consumer.py'
test_before=test_source.read_text('utf-8-sig')
test_after=test_before.replace('import automl_release_runtime as runtime','import r5_worker_runtime as runtime')
test_after=test_after.replace("candidate = Path(__file__).resolve().parents[1] / 'candidate'", "candidate = Path(__file__).resolve().parent\nsys.path.insert(0,str(candidate.parent/'alfa-hack-automl/src'))")
assert test_before!=test_after
old_methods=[dump(ast.unparse(n)) for n in ast.walk(ast.parse(test_before)) if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')]
new_methods=[dump(ast.unparse(n)) for n in ast.walk(ast.parse(test_after)) if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')]
assert old_methods==new_methods and len(new_methods)==1
(HERE/'test_r5_worker_consumer.py').write_text(test_after,encoding='utf-8')
for p in [HERE/'r5_worker_runtime.py',HERE/'r5_resources.py',HERE/'verified_sampling.py']:
    compile(p.read_bytes(),p.name,'exec')
proof={'schema':'three-hour-R5-worker-import-port-v1','status':'SOURCE_ONLY_NOT_EXECUTED',
    'R5_handoff_sha256':sha(BASE/'source-handoff.json'),'R5_runtime_sha256':sha(source),
    'only_six_import_paths_changed':replacements,'entire_AST_inverse_exact':True,
    'ReleaseClock_and_all_worker_cleanup_resource_function_ASTs_unchanged':True,
    'worker_entrypoint':'existing canonical automl.infrastructure.runtime.worker_entrypoint',
    'resources_byte_exact_R5':sha(HERE/'r5_resources.py'),
    'sampler_byte_exact_d65':sha(HERE/'verified_sampling.py'),
    'R5_consumer_fixture_import_path_only':{'original_sha256':sha(test_source),'candidate_sha256':sha(HERE/'test_r5_worker_consumer.py'),'sole_test_method_AST_exact':True},
    'future_transitive_canonical_process_messages_atomic_runtime_worker_model_evaluator_pins':None,
    'new_clocks_imports_tests_fits_API_data_PIDscans_Git':0}
(HERE/'worker-port-source-proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'source_only_port':True,'runtime_sha256':sha(HERE/'r5_worker_runtime.py'),'runtime':False}))
