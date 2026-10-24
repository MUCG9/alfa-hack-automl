"""Stdlib source/AST/SHA census only; does not import candidate or config()."""
from pathlib import Path
import ast,copy,difflib,hashlib,json,zipfile

PACKET=Path(__file__).resolve().parent;WORK=PACKET.parents[1];OLD=PACKET.parent/'controller-r4'
CANDIDATE=WORK/'br-standard-release-next-dev-r5';SAMPLER=WORK/'verified-resource-sampling-next-dev'
HANDOFF='92cfd41804ca162ba5ec4aeff53a3cb45e6b0c798b93e0c36c1cbb969fdfef08'
ZIP='c7b54a8996e36dfaaf582b104d1f38ecca71d91d4f38362ed50775381f42f930'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text('utf-8'))
def save(n,v):(PACKET/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def methods(p):
    result={}
    for cls in ast.parse(Path(p).read_text('utf-8-sig')).body:
        if isinstance(cls,ast.ClassDef):
            for node in cls.body:
                if isinstance(node,ast.FunctionDef) and node.name.startswith('test_'):
                    key=cls.name+'.'+node.name;assert key not in result
                    result[key]=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()
    return result
def whole(p):return ast.parse(Path(p).read_text('utf-8-sig'))
def dump(n):return ast.dump(n,include_attributes=False)
def name(n):return n.name if isinstance(n,(ast.FunctionDef,ast.ClassDef)) else None
assert sha(OLD/'source-handoff.json')=='027a20423d733716155ca93d5fc1eaedcb16e3a5f52a2483b995b9b31bf37ad3'
assert sha(CANDIDATE/'source-handoff.json')==HANDOFF
handoff=read(CANDIDATE/'source-handoff.json')
assert all(sha(CANDIDATE/p)==h for p,h in handoff['files_sha256'].items())
members={Path(p).name:h for p,h in handoff['files_sha256'].items() if p.startswith('candidate/')}
assert len(members)==74 and handoff['archive']['sha256']==ZIP and sha(CANDIDATE/'solution-br-fixed-candidate.zip')==ZIP
with zipfile.ZipFile(CANDIDATE/'solution-br-fixed-candidate.zip') as z:
    assert len(z.namelist())==len(set(z.namelist()))==len(members) and set(z.namelist())==set(members)
    assert all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in members.items())
    assert z.read('automl_verified_resource_sampling.py')==(SAMPLER/'verified_sampling.py').read_bytes()
contracts=methods(CANDIDATE/'tests/test_fixed_release.py');consumer=methods(CANDIDATE/'tests/test_sampling_checkpoint_consumer.py')
sampler_methods=methods(SAMPLER/'test_verified_sampling.py');caller=methods(PACKET/'test_controller_contracts.py')
old_caller=methods(OLD/'test_controller_contracts.py')
assert len(contracts)==18 and len(consumer)==1 and len(sampler_methods)==14 and len(caller)==15
assert all(caller[k]==h for k,h in old_caller.items()) and len(old_caller)==10
raw=(SAMPLER/'test_verified_sampling.py').read_text('utf-8')
old_import='from verified_sampling import ResourceSamplingError, VerifiedResourceSampler'
new_import='from automl_verified_resource_sampling import ResourceSamplingError, VerifiedResourceSampler'
assert raw.count(old_import)==1
projected=raw.replace(old_import,new_import)
tree=ast.parse(projected)
for cls in tree.body:
    if isinstance(cls,ast.ClassDef):
        for node in cls.body:
            if isinstance(node,ast.FunctionDef) and node.name.startswith('test_'):
                assert hashlib.sha256(dump(node).encode()).hexdigest()==sampler_methods[cls.name+'.'+node.name]
runtime=['run_controller.py','artifact_audit.py','close_controller.py','test_controller_contracts.py']
for n in runtime:compile((PACKET/n).read_text('utf-8-sig'),str(PACKET/n),'exec')
changed={}
for n in runtime[:3]:
    base,new=whole(OLD/n),whole(PACKET/n)
    a={name(v):dump(v) for v in base.body if name(v)};b={name(v):dump(v) for v in new.body if name(v)}
    changed[n]=[key for key in b if a.get(key)!=b[key]]
    for key in set(a)&set(b):
        if key not in changed[n]:assert a[key]==b[key]
    (PACKET/(n+'.patch')).write_text(''.join(difflib.unified_diff((OLD/n).read_text('utf-8-sig').splitlines(True),
        (PACKET/n).read_text('utf-8-sig').splitlines(True),fromfile='frozen-controller-r4/'+n,tofile='controller-r5/'+n)),encoding='utf-8')
assert changed['run_controller.py']==['guard','config','predecessor','main']
assert changed['artifact_audit.py']==['verified_terminal','main']
assert changed['close_controller.py']==['main']
# Reversible whole-module AST boundary; no numerical/helper/capture edits.
before,new=whole(OLD/'run_controller.py'),whole(PACKET/'run_controller.py')
names={'guard','config','predecessor','main'};witness={name(v):v for v in before.body if name(v) in names}
constants={'OUT','HELPERS','EXECUTOR_HANDOFF_SHA','ARCHIVE_SHA'}
def assigned(n):return n.targets[0].id if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) else None
values={assigned(v):v for v in before.body if assigned(v) in constants}
new.body=[copy.deepcopy(witness[name(v)]) if name(v) in names else copy.deepcopy(values[assigned(v)]) if assigned(v) in constants
          else v for v in new.body if assigned(v)!='NEGATIVE_CURRENT']
assert dump(new)==dump(before)
before,new=whole(OLD/'close_controller.py'),whole(PACKET/'close_controller.py')
for n in new.body:
    if assigned(n)=='OUT':n.value=ast.parse("WORK/'brq2'",mode='eval').body
class RestoreContracts(ast.NodeTransformer):
    def visit_Compare(self,n):
        if (isinstance(n.left,ast.Call) and isinstance(n.left.func,ast.Name) and n.left.func.id=='len'
            and len(n.left.args)==1 and isinstance(n.left.args[0],ast.Call) and isinstance(n.left.args[0].func,ast.Attribute)
            and n.left.args[0].func.attr=='get' and n.left.args[0].args and isinstance(n.left.args[0].args[0],ast.Constant)
            and n.left.args[0].args[0].value=='contracts' and len(n.comparators)==1 and isinstance(n.comparators[0],ast.Constant)
            and n.comparators[0].value==7):n.comparators[0].value=3
        return self.generic_visit(n)
new=RestoreContracts().visit(new);assert dump(new)==dump(before)
before,new=whole(OLD/'artifact_audit.py'),whole(PACKET/'artifact_audit.py')
new.body=[v for v in new.body if name(v)!='verified_terminal']
for n in new.body:
    if assigned(n)=='OUT':n.value=ast.parse("WORK/'brq2'",mode='eval').body
class RestoreTerminal(ast.NodeTransformer):
    def visit_Call(self,n):
        if isinstance(n.func,ast.Name) and n.func.id=='verified_terminal':
            return ast.parse("terminal.get('status') in {'sampled_before_terminal_acceptance','root_absent_after_observed_exit'}",mode='eval').body
        return self.generic_visit(n)
new=RestoreTerminal().visit(new);assert dump(new)==dump(before)
slots=[('source-contracts',18,150,120),('flat-contracts',18,150,120),('caller-contracts',15,60,45),
       ('sampler-source-contracts',14,45,30),('sampler-flat-contracts',14,45,30),
       ('consumer-source-contracts',1,30,20),('consumer-flat-contracts',1,30,20)]
assert sum(v[2] for v in slots)<=600
save('source-proof.json',dict(schema='br-C5-verified-sampling-source-proof-v1',compiled_AST_only=True,
    changed_existing_or_added_functions=changed,whole_AST_reversible_to_frozen_R4=True,capture_all_function_AST_unchanged=True,
    old10caller_methods_AST_exact=True,executor18methods_source_and_actual_unpacked=True,
    sampler14method_assertion_AST_exact_under_single_import_alias=True,worker_consumer_fixture_source_and_actual_unpacked_byte_exact=True,
    root_approved_terminal_bridge_only=True,registry_derived=dict(executor=18,sampler=14,worker_consumer=1,caller=len(caller),
        actual_flat_members=len(members),future_unique_methods=len(contracts)+len(consumer)+len(sampler_methods)+len(caller),
        future_test_executions=sum(v[1] for v in slots)),contract_slots=slots,
    all_other_runtime_caps_helpers_parser_model_and_numerical_logic_unchanged=True,actual_imports_tests_fits_API_PIDscans_clock=0))
base_handoff=read(OLD/'source-handoff.json')
save('R4-preservation.json',dict(schema='br-controller-R4-preservation-v1',source_handoff_sha256=sha(OLD/'source-handoff.json'),
    files_sha256={n:sha(OLD/n) for n in base_handoff['files_sha256']},original_BRQ2_flags_and_FAIL_unchanged=True,
    qualification_cannot_inherit_archive6af_or_b56e=True))
template=read(OLD/'binding.template.NOT_READY.json')
template['readiness']='NOT_READY';template['missing_bindings']=['root_private_instantiation_and_review','final_C5_source_peer',
    'current_UQ3_plus_all_negative_preparers_fresh_observation','root_sole_actual_new6000_launch']
template['output']='brq3';template['executor'].update(handoff=dict(path='br-standard-release-next-dev-r5/source-handoff.json',sha256=HANDOFF),
    archive=dict(path='br-standard-release-next-dev-r5/solution-br-fixed-candidate.zip',sha256=ZIP),members_sha256=members,
    test='br-standard-release-next-dev-r5/tests/test_fixed_release.py',test_count=len(contracts),test_methods=contracts,
    recipe_fixture='br-standard-release-next-dev-r5/tests/fixtures/recipes.json',base_inventory='br-standard-release-next-dev-r5/base-inventory.json')
template['candidate_source_review']=dict(path='br-standard-release-independent-source-review-r5.json',sha256='15c8e64b9b8fe0a646e694afe1929d8849e1bcb804ba372d809097cfc9971eb4')
template['caller_contract_count']=len(caller);template['caller_test_methods']=caller
template['sampler_contracts']=dict(test='verified-resource-sampling-next-dev/test_verified_sampling.py',source_sha256=sha(SAMPLER/'test_verified_sampling.py'),
    count=len(sampler_methods),methods=sampler_methods,flat_module='automl_verified_resource_sampling')
template['consumer_contracts']=dict(test='br-standard-release-next-dev-r5/tests/test_sampling_checkpoint_consumer.py',count=len(consumer),methods=consumer)
helpers=dict(template['helpers'])
helpers['coordinator']=dict(path='verified-supervision-next-dev-r2/coordinator.py',sha256='bd864b13460d31176d57e1dbddbe179ad8e6911163b117e3f9698228c5540f76')
helpers['sampling']=dict(path='verified-resource-sampling-next-dev/verified_sampling.py',sha256='d65ee39eb80c9fc4590cbbf474ee6c09e84cb65abe2d2c367ebcfa415a390cf0')
template['helpers']=helpers
negative={
 'BRQ1':('brq1/terminal-root-closure.json','243782d116baa00df12e87ec6ff99e2f48e611bef1b77f24ec1227b9284b8db6'),
 'BRQ2':('brq2/terminal-root-closure.json','2d259e647a64f2f1e48d06e450f6fd877d4dc07bac3363df9743d78fecb890a0'),
 'campaign':('brq2/campaign.json','fd85c8317ff187ffc37986613ea5169c4dbd1e9512545e51127469750416ae24'),
 'current_root':('brq2-negative-closure-r1/terminal-root-closure.json','0a2f2dae7962892a596a98b7d51d1135f1017358a6326abe31ff2e986b7b5ade'),
 'fresh':('brq2-negative-closure-r1/root-confirmation.json','a5f5d57f7137ea6159db0cb43e760cbae8cb7674172624199e3479b399eed325')}
template['brq2_negative_current']={k:dict(path=p,sha256=h) for k,(p,h) in negative.items()}
pins={p:h for p,h in template['immutable_files'].items() if not p.startswith('br-standard-release-next-dev-r3/')
      and not p.startswith('br-standard-release-qualification-next-dev/controller-r4/') and p!='run_lean_mvp_r2.py'}
pins.update({'br-standard-release-next-dev-r5/'+p:h for p,h in handoff['files_sha256'].items()});pins['br-standard-release-next-dev-r5/source-handoff.json']=HANDOFF
refs={
 'candidate_R5_peer':('br-standard-release-independent-source-review-r5.json','15c8e64b9b8fe0a646e694afe1929d8849e1bcb804ba372d809097cfc9971eb4'),
 'root_scope':('brq2-verified-sampling-batch-root-scope-r1.json','a00ea96ff2455ad80d640f20f7da071288dffd7f18401058a6f14e35d4458f0e'),
 'coordinator_handoff':('verified-supervision-next-dev-r2/source-handoff.json','e794d8c1ed44a213ef3622111a3cbd577d1d4f79aed584228e2e6118d927d104'),
 'coordinator_peer':('verified-supervision-independent-review-r2.json','93402ed1f0613e72770e294401515f4e7ff06d885fa373a05da0ac0ce9e1dae3'),
 'coordinator_root_acceptance':('verified-supervision-root-source-acceptance-r2.json','2715c5b0ffda72519f833f59e30343f77b0f4da3ea076cf2683bbce259ce588d'),
 'sampler_handoff':('verified-resource-sampling-next-dev/source-handoff.json','86859fe9596d672373e76edc56d6fc89c88c956952c2ed88ded15a6ea7e0076c'),
 'sampler_peer':('verified-resource-sampling-independent-review-r1.json','c61e4f028b7a06c0e6b17e02f8a567d08fd31804554e1a908e1dffb49bb418d6'),
 'sampler_root_acceptance':('verified-resource-sampling-root-source-acceptance-r1.json','dc3b92829c0e33fc1ada8af529b681cb7e58a1fd63f45bbdabe675fb415fd535'),
 'negative_helper_peer':('brq2-negative-closure-independent-review-r1.json','42f5003450bc3cd3647475c2a0f474354d1a16570cd25dbed2ff8df8d9cc4a9a')}
refs.update({k:(p,h) for k,(p,h) in negative.items()})
for key,(p,h) in refs.items():assert sha(WORK/p)==h,(key,p);pins[p]=h
for d in [WORK/'verified-supervision-next-dev-r2',SAMPLER]:
    dh=read(d/'source-handoff.json')
    pins.update({str((d/p).relative_to(WORK)).replace('\\','/'):h for p,h in dh['files_sha256'].items()})
for n in runtime:pins['br-standard-release-qualification-next-dev/controller-r5/'+n]=sha(PACKET/n)
template['immutable_files']=pins;template['actual_clock']=None;template['actual_quality_metric']=None;template['actual_root']=None
template['expected_total_contract_executions']=sum(v[1] for v in slots)
save('binding.template.NOT_READY.json',template)
save('protocol.json',dict(schema='br-C5-verified-resource-qualification-protocol-v1',readiness='SOURCE_ONLY_NOT_READY',
    common_seconds=6000,caps=dict(setup=600,regression=[900,870],classification=[3600,3570],audit=[600,570],final=240,root=60),
    strict_serial=True,technical_threads=1,learner_threads=2,BLAS_launcher_threads=1,worker_memory_mib=1536,whole_memory_mib=2048,
    new_archive=dict(sha256=ZIP,members=len(members),prior_metrics_inherited=False),
    source_contract_executions=slots,expected_test_executions=sum(v[1] for v in slots),all_counts_AST_derived=True,
    samplers_source14_and_actual_flat14_required=True,consumer_source1_and_actual_flat1_required=True,
    old10caller_assertion_AST_preserved=True,caller_prepared_count=len(caller),
    actual_candidate_imports_tests_fits_API_data_PIDscans=0,actual_new_clock=None,actual_new_metrics=None,actual_ready=None,
    original_BRQ1_BRQ2_FAIL_and_false_flags_retained=True,mandatory_UQ3_positive_and_separate_current_negative=True,
    new_grant_scope='Current complete known identity absence/source/temp only; neither old gate becomes PASS',
    root_only_PRIVATE_READY_publication_fresh_actual_launch_required=True,promotion=False,submit=False))
(PACKET/'README.txt').write_text('SOURCE ONLY / NOT_READY. New C5, output work/brq3.\n'
    'Original C4/BRQ2 and all source/history hashes remain unchanged; neither old failure is requalified.\n'
    'Same two standard calls and6000=600+900+3600+600+240+60; source+flat tests all inside setup600.\n'
    'Frozen candidateR5 archive74; old18 executor contracts remain exact. Shared14 contracts run source+actual-unpacked with one import alias only.\n'
    'New worker consumer1 is byte-exact source+actual-unpacked. Caller15 are old10 AST-exact plus5 meaningful consumer/admission mocks.\n'
    'Clock-only state._resource_checkpoint never advances successful sampling; outer state._pulse keeps full guard, resources and Power.\n'
    'New departed-root receipt requires exact captured root, fresh absent/reused nullRSS, stable mandatoryself, parentexit0 and full strict cleanup.\n'
    'Mandatory positive UQ3 and BRQ1/BRQ2 failed histories plus typed current-negative0a2f/fresha5f5 all7267 identities remain freshly checked before/under lock.\n'
    'No tests/build/imports/models/data/API/PID observations or actual clocks executed by this author.\n'
    'Root must instantiate private absolute paths/current fresh binding, inspect and publish frozen pins before one new launch.\n'
    'NOT RUN command: python -B -X utf8 run_controller.py --launch --manifest <ABSOLUTE_READY> --manifest-sha256 <SHA> --self-sha256 <DRIVER_SHA> --launch-parent-pid <SHELL_PID> --launch-parent-create-time <ACTUAL_SHELL_UNIX_BIRTH>\n'
    'NOT RUN closer: python -B -X utf8 close_controller.py --manifest <ABSOLUTE_READY> --manifest-sha256 <SHA> --self-sha256 <CLOSER_SHA> --driver-sha256 <DRIVER_SHA> --campaign-sha256 <ACTUAL_CAMPAIGN_SHA> --actual-exit-code <ACTUAL> --actual-tool-evidence <ACTUAL_TOOL> [--actual-exec-session <ACTUAL_SESSION>] --launch-parent-pid <SHELL_PID> --launch-parent-create-time <ACTUAL_SHELL_UNIX_BIRTH>\n',encoding='utf-8')
save('prepeer-preservation.json',dict(schema='C5-source-only-prepeer-metadata-preservation-v1',runtime_unchanged=True,
    files_sha256={n:sha(PACKET/n) for n in ['source-handoff.prepeer.json','binding.template.prepeer.json','prepare_metadata.prepeer.py']},
    prior_source_only_handoff_sha256='d6314131e53a2316058df22c8b95e628d6baf44eb670722d650ad7ca5668b7d1',
    delta='CandidateR5 independent peer exact reference filled; no runtime changes or execution.'))
assert sha(PACKET/'source-handoff.prepeer.json')=='d6314131e53a2316058df22c8b95e628d6baf44eb670722d650ad7ca5668b7d1'
names=runtime+['prepare_metadata.py','source-proof.json','R4-preservation.json','binding.template.NOT_READY.json','protocol.json','README.txt','prepeer-preservation.json']+[n+'.patch' for n in runtime[:3]]
save('source-handoff.json',dict(schema='br-standard-controller-source-handoff-v5',readiness='FROZEN_SOURCE_ONLY_PENDING_PEER_NOT_READY',
    files_sha256={n:sha(PACKET/n) for n in names},external_source_refs={k:dict(path=p,sha256=h) for k,(p,h) in refs.items()},
    executor_handoff=dict(path='br-standard-release-next-dev-r5/source-handoff.json',sha256=HANDOFF),
    executor_archive_sha256=ZIP,executor_flat_members=len(members),source_only_AST_compile=True,
    old10_caller_AST_equal=True,prepared_executor_source_methods=len(contracts),prepared_executor_flat_methods=len(contracts),
    prepared_sampler_source_methods=len(sampler_methods),prepared_sampler_flat_methods=len(sampler_methods),
    prepared_worker_consumer_source_methods=len(consumer),prepared_worker_consumer_flat_methods=len(consumer),
    prepared_caller_methods=len(caller),future_test_executions=sum(v[1] for v in slots),
    actual_candidate_imports_tests_fits_API_data_PIDscans_clock=0,actual_private_manifest=None,actual_metrics=None,actual_clock=None,
    candidate_R5_peer_required=True,controller_C5_peer_required=True,root_publication_actual_fresh_and_launch_required=True,promotion=False,submit=False))
print(json.dumps(dict(handoff_sha256=sha(PACKET/'source-handoff.json'),driver_sha256=sha(PACKET/'run_controller.py'),
    caller_methods=len(caller),future_test_executions=sum(v[1] for v in slots),NOT_READY=True)))
