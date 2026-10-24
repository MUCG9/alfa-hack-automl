"""SOURCE generation/hash/AST only. Does NOT run prepare_binding or its helpers."""
from pathlib import Path
import ast, hashlib, json

HERE=Path(__file__).resolve().parent
WORK=HERE.parent

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text('utf-8'))
def write(path,value):Path(path).write_text(value,encoding='utf-8',newline='\n')
def saved(path,value):write(path,json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def ah(node):return hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
def named(path,names):
    result=[]
    for node in ast.parse(path.read_text('utf-8-sig')).body:
        if isinstance(node,(ast.FunctionDef,ast.ClassDef)) and node.name in names:result.append(node)
        elif isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in node.targets):result.append(node)
    assert len(result)==len(names),(path,names)
    return result

messages=WORK/'alfa-hack-automl/src/automl/contracts/messages.py'
registry=WORK/'alfa-hack-automl/src/automl/execution/model_adapters/registry.py'
policy=WORK/'alfa-hack-automl/src/automl/search/policy.py'
outer=WORK/'qwen-three-hour-outer-next-dev-r3/run_campaign.py'
parts=[(messages,['SCHEMA_VERSION','LossProfile','LOSS_PROFILES','resolve_loss_profile','validate_loss_profiles','DataPolicy']),
       (registry,['COMMON_PARAMETERS','MODEL_PARAMETERS','effective_parameters']),
       (policy,['signature'])]
nodes=[node for path,names in parts for node in named(path,names)]
model_parameters=next(n for n in nodes if isinstance(n,ast.Assign) and n.targets[0].id=='MODEL_PARAMETERS')
keys=set(ast.literal_eval(model_parameters.value))
regtree=ast.parse(registry.read_text('utf-8-sig'))
adapters=next(n for n in regtree.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='ADAPTERS')
adapter_keys={ast.literal_eval(k) for k in adapters.value.keys}
assert keys==adapter_keys|{'linear_text'}
signature_header='"""Exact stdlib-only metadata signature closure; no model imports. Generated SOURCE."""\nfrom dataclasses import dataclass,asdict\nimport math,hashlib,json\n'
signature_text=signature_header+'\n\n'.join(ast.unparse(n) for n in nodes)+'\n\nCAPABILITIES='+repr(dict.fromkeys(sorted(keys)))+'\n'
write(HERE/'metadata_signature.py',signature_text)
sigmap={n.name if isinstance(n,(ast.FunctionDef,ast.ClassDef)) else n.targets[0].id:ah(n) for n in nodes}
copied=ast.parse(signature_text)
for n in copied.body:
    key=n.name if isinstance(n,(ast.FunctionDef,ast.ClassDef)) else n.targets[0].id if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) else None
    if key in sigmap:assert ah(n)==sigmap[key]

validator_names=['need','read','sha','imported','qualified','predecessor','strong_authority']
validator_nodes=named(outer,validator_names)
validator_text='"""Exact SOURCE-projected outer metadata validators; no candidate/outer module import."""\nfrom pathlib import Path\nimport hashlib,importlib.util,json,sys\nWORK=BASE=BASE_SHA=None\n\n'+'\n\n'.join(ast.unparse(n) for n in validator_nodes)+'\n'
write(HERE/'metadata_validators.py',validator_text)
vmap={n.name:ah(n) for n in validator_nodes}
assert all(ah(n)==vmap[n.name] for n in ast.parse(validator_text).body if isinstance(n,ast.FunctionDef))

template=dict(schema='qwen-three-hour-binding-input-v1',readiness='NOT_READY',missing_bindings=[
    'Future actual positive RQ6 driver/root/atomic/final post-tool proof and actual exits.',
    'Final R7-compatible outer handoff and independent outer source peer.',
    'Root-selected requested provider model/reasoning; no credentials.'],
    reviewed_outer=None,outer_source_review=None,qualified_manifest=None,campaign=None,
    source_qualification=dict.fromkeys(['archive','root','confirmation','post_tool','driver_actual','wrapper_actual','post_tool_actual']),
    additional_preparer_receipts=[],requested_model=None,reasoning_effort=None,actual_clock=None,actual_metrics=None)
saved(HERE/'input-plan.template.NOT_READY.json',template)
write(HERE/'README.txt','''SOURCE ONLY / NOT EXECUTED. Root-only one-step metadata producer after actual RQ6 PASS.

CLI (all actual values supplied by root, no credentials):
python -B -X utf8 prepare_binding.py --plan ABS --plan-sha256 SHA --self-sha256 SHA --source-handoff-sha256 SHA --launch-parent-pid ACTUAL_PS_PID --launch-parent-create-time ACTUAL_PS_UNIX_BIRTH

Input plan: exact ABS refs for reviewed_outer, outer_source_review, qualified_manifest,
campaign and source_qualification archive/root/confirmation/post_tool, with actual
driver {session,exit_code,tool}, wrapper/post {exit_code,tool}. Final peer must bind
the selected outer handoff. No future actual values or clocks exist in this packet.
Root changes the input plan to ACTUAL_RQ6_METADATA_BOUND/missing_bindings=[] only
after all actual proof refs exist. Requested model/reasoning are names, never keys.

Outputs are exclusive private/qh1-manifest.draft-r1.json (ALWAYS NOT_READY), two
qh1-strong-<kind>-r1.json authorities, qh1-binding-metadata-preparers-r1.json and
qh1-binding-metadata-current-fresh-r1.json. One producer actual exit0 permits root
to replace its PENDING_ACTUAL_METADATA_EXIT tool tag; private peer/root admission
remain required. Source/clock preparation is not the actual10800 experience.

Uses the reviewed prepare-rq6-private.py one-capture/finite-known-absence pattern.
Only qualified C5 metadata capture plus local exact stdlib projections are loaded.
Parent chain/self births are captured early; no process enumeration/global scans.

Campaign tasks is the actual ordered LIST, keyed by row.kind after duplicate check.
Report locations come ONLY from actual task rows and independently audited hashes.
Raw selected recipes never contain fit_iterations anywhere. Signature preserves
policy.signature default-spaced JSON, executable keys, effective parameters and
DataPolicy semantics; it is NOT the different full canonical metadata hash.

Numeric witnesses read only SHA-bound data_dictionary.csv metadata role/dtype:
exact role=feature AND dtype=numeric, in qualified spec feature order. Binary or
unknown types are omitted, never guessed from not-categorical. No profile stats.
No train/test/NPZ/model/prediction/truth bytes are opened. Their existing exact
pin values come from actual qualified private/audit metadata. Later actual outer
rehashes all bytes before candidate imports. Missing/false proof fails closed.

Final core/auditor refs and contract counts derive from the independently reviewed
final outer template, preserving10800/300/4800/4800/600/300,9slots270 and all exact
method AST maps. No READY, actualclock, API, fit, publication, upload or promotion.
''')
proof=dict(schema='qwen-binding-preparation-source-projection-v1',status='SOURCE_ONLY_NOT_EXECUTED',
    signature_nodes_AST_sha256=sigmap,outer_validator_nodes_AST_sha256=vmap,
    CAPABILITIES_membership_keys=sorted(keys),CAPABILITIES_membership_equals_registry_ADAPTERS_plus_linear_text=True,
    signature_source_closure_exact=True,validator_functions_whole_AST_exact=True,
    signature_JSON='json.dumps(actual,sort_keys=True,default=str) defaults; NOT canonical compact metadata JSON',
    numeric_witness='exact declared feature/numeric dictionary metadata; unknown or binary omitted',
    actual_source_qualification=None,actual_outer_final_source=None,actual_clock=None,
    execution_imports_tests_fits_API_data_PID_observations=0)
saved(HERE/'source-proof.json',proof)
external={str(p.relative_to(WORK)).replace('\\','/'):sha(p) for p in [messages,registry,policy,outer,
    WORK/'prepare-rq6-private.py',WORK/'br-standard-release-qualification-next-dev/controller-r5/run_controller.py',
    WORK/'qwen-three-hour-outer-next-dev-r3/source-handoff.json',
    WORK/'qwen-three-hour-outer-independent-source-review-r3.json',
    WORK/'alfa-hack-automl/tools/propose_feature_dsl.py']}
for path in HERE.glob('*.py'):compile(path.read_text('utf-8'),str(path),'exec')
files={str(p.relative_to(HERE)).replace('\\','/'):sha(p) for p in HERE.iterdir() if p.is_file() and p.name!='source-handoff.json'}
handoff=dict(schema='qwen-three-hour-binding-preparation-source-handoff-v1',status='FROZEN_SOURCE_ONLY_NOT_EXECUTED',
    files_sha256=files,external_refs_sha256=external,DSL_compiler_sha256=sha(WORK/'alfa-hack-automl/tools/propose_feature_dsl.py'),
    parent_pattern='prepare-rq6-private.py; one qualified C5 capture plus finite known absence; pending actual exit patched only by root',
    final_outer_core_auditor_actual_bindings=None,actual_qualification=None,actual_clock=None,
    author_candidate_imports=0,author_tests=0,author_fits=0,author_API=0,author_data_reads=0,author_PID_observations=0)
saved(HERE/'source-handoff.json',handoff)
print(json.dumps(dict(handoff_sha256=sha(HERE/'source-handoff.json'),local=len(files),external=len(external),
    producer_sha256=sha(HERE/'prepare_binding.py'),producer_executed=False)))
