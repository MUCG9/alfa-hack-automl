"""SOURCE/stdlib-only projection; never imports candidate or executes tests."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent
W = P.parent
B = W / 'qwen-three-hour-outer-next-dev-r9'
CORE = W / 'qwen-three-hour-autoresearch-next-dev-r10'
AUDITOR = W / 'qwen-three-hour-independent-audit-next-dev-r7'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text('utf-8'))


def save(name, value):
    (P / name).write_text(json.dumps(value, ensure_ascii=True, indent=2)+'\n', encoding='utf-8')


def dump(node):
    return ast.dump(node, include_attributes=False)


def methods(path):
    return {c.name+'.'+n.name:hashlib.sha256(dump(n).encode()).hexdigest()
        for c in ast.parse(path.read_text('utf-8')).body if isinstance(c,ast.ClassDef)
        for n in c.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')}


def assign(text, name, expression):
    rows = text.splitlines(keepends=True)
    node, = [n for n in ast.parse(text).body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id==name for t in n.targets)]
    return ''.join(rows[:node.lineno-1])+name+'='+expression+'\n'+''.join(rows[node.end_lineno:])


base_handoff = read(B / 'source-handoff-final.json')
assert sha(B/'source-handoff-final.json') == '0f11d7b9275638a73e6ce5222ffa2663704b75201c0a690047905d1259da2da5'
core_sha = sha(CORE/'source-handoff-final.json')
audit_sha = sha(AUDITOR/'source-handoff.json')
assert core_sha == '2ef1d62f1ad923dc00382502c9ece525df56c1304353dfa3d50ff31fa163c61c'
assert audit_sha == '6541fa8b590c4701a262b1f63f29040e80886287a7852f492462de9198684ce4'
reviews = {'core':('qh5-core-r10-audit-contract-source-review-r1.json',
    'cd4e6a47c77a498daa5a9af27d4e18ec42fa86e7ff623011706df222ec6e5fe7'),
    'auditor':('qwen-three-hour-independent-audit-source-review-r7.json',
    '6f5877bccdc310cf8bd2bc6153b6fac3ee71c78abb98075838ff233f98bd3c69')}
for rel,h in reviews.values():
    assert sha(W/rel)==h

runtime = ['run_campaign.py','close_controller.py','run_root.py','confirm_post_tool.py',
           'close_child.ps1','test_broker_contracts.py','test_atomic_root.py']
for name in runtime:
    raw = (B/name).read_bytes()
    assert sha(B/name)==base_handoff['files_sha256'][name]
    if name.endswith('.py') and name not in ('test_broker_contracts.py','test_atomic_root.py'):
        text=raw.decode('utf-8')
        assert text.count("OUT=WORK/'qh4'")==1
        text=text.replace("OUT=WORK/'qh4'", "OUT=WORK/'qh5'")
        if name=='run_campaign.py':
            for key,expr in {'CORE':"WORK/'qwen-three-hour-autoresearch-next-dev-r10'",
                'CORE_SHA':repr(core_sha),'AUDITOR':"WORK/'qwen-three-hour-independent-audit-next-dev-r7'",
                'AUDITOR_HANDOFF_SHA':repr(audit_sha),'SOURCE_REVIEWS':repr(reviews)}.items():
                text=assign(text,key,expr)
        (P/name).write_bytes(text.encode('utf-8'))
    else:
        (P/name).write_bytes(raw)

# The main module inverse restores only six approved global assignments. All
# function/class/module scaffold AST outside those exact nodes must remain.
oldtree=ast.parse((B/'run_campaign.py').read_text('utf-8'))
newtree=ast.parse((P/'run_campaign.py').read_text('utf-8'))
allowed={'OUT','CORE','CORE_SHA','AUDITOR','AUDITOR_HANDOFF_SHA','SOURCE_REVIEWS'}
oldassign={n.targets[0].id:n for n in oldtree.body if isinstance(n,ast.Assign)
    and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in allowed}
projection=deepcopy(newtree)
for i,n in enumerate(projection.body):
    if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in allowed:
        projection.body[i]=deepcopy(oldassign[n.targets[0].id])
assert set(oldassign)==allowed and dump(projection)==dump(oldtree)
for name in ('close_controller.py','run_root.py','confirm_post_tool.py'):
    assert (P/name).read_bytes().replace(b"OUT=WORK/'qh5'",b"OUT=WORK/'qh4'")==(B/name).read_bytes()
for name in ('close_child.ps1','test_broker_contracts.py','test_atomic_root.py'):
    assert (P/name).read_bytes()==(B/name).read_bytes()
for name in runtime:
    if name.endswith('.py'):
        text=(P/name).read_text('utf-8');compile(text,str(P/name),'exec')
        oldnodes={n.name:dump(n) for n in ast.parse((B/name).read_text('utf-8')).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        newnodes={n.name:dump(n) for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        assert oldnodes==newnodes

test_paths=[CORE/n for n in ['test_parent_callback_ledger.py','test_provider_environment.py',
    'test_r5_worker_consumer.py','test_research_loop.py','test_resource_origin.py']]
test_paths += [AUDITOR/'test_audit_contracts.py',AUDITOR/'test_csv_role_contracts.py',
              P/'test_broker_contracts.py',P/'test_atomic_root.py']
method_map={p.relative_to(W).as_posix():methods(p) for p in test_paths}
counts=[len(methods(p)) for p in test_paths]
assert counts==[2,8,4,23,4,30,2,4,6] and sum(counts)==83

template=read(B/'binding.template.NOT_READY.json')
template['core_handoff']={'path':(CORE/'source-handoff-final.json').relative_to(W).as_posix(),'sha256':core_sha}
template['auditor_handoff']={'path':(AUDITOR/'source-handoff.json').relative_to(W).as_posix(),'sha256':audit_sha}
template['auditor_entry']=(AUDITOR/'audit_final.py').relative_to(W).as_posix()
template['source_reviews']={k:{'path':r,'sha256':h} for k,(r,h) in reviews.items()}
for row,path in zip(template['contracts'],test_paths):
    row.update(path=path.relative_to(W).as_posix(),sha256=sha(path),methods=methods(path),expected=len(methods(path)))
template['native_closure_source']={'path':'qh5-closure-bootstrap-next-dev/source-handoff.json',
    'sha256':sha(W/'qh5-closure-bootstrap-next-dev/source-handoff.json')}
template['collector_source']={'path':'qh5-collector-next-dev/source-handoff.json',
    'sha256':sha(W/'qh5-collector-next-dev/source-handoff.json')}
assert template['readiness']=='NOT_READY'
save('binding.template.NOT_READY.json',template)

atomic=read(B/'atomic-binding.template.NOT_READY.json')
atomic.update(output=None,missing_bindings=['actual_root_hosted_source_roles_and_full_immutable_map','actual_campaign_sha256'],
    expected_output_work_relative='qh5')
for role,name in [('driver','run_campaign.py'),('closer','close_controller.py'),('post_tool','confirm_post_tool.py')]:
    atomic[role]={'path':(P/name).relative_to(W).as_posix(),'sha256':sha(P/name)}
save('atomic-binding.template.NOT_READY.json',atomic)
(P/'strong-authority.template.NOT_READY.json').write_bytes((B/'strong-authority.template.NOT_READY.json').read_bytes())

protocol=read(B/'protocol.json')
protocol.update(source_revision='OUTER_R10_QH5_CORE_R10_AUDITOR_R7',output_work_relative='qh5',
    prepared_contract_executions=83,contract_counts=counts,
    exact_contracts=[{k:r[k] for k in ('name','expected','parent','child')} for r in template['contracts']],
    completion_time_intent='Each task actual elapsed>=4530 and report remaining<=270 with actual supervisor end>=task deadline-270; source-defined incomplete cap/early exit cannot qualify.',
    original_QH4_FAIL_preserved=True,current_predecessor_complete_observed_baseline=8541,
    extra_native_startup_contract_executions=0,collector_mock_contracts=10,
    collector_mock_execution_scope='Separate root functions V8 injected-tools proof, not part of83mainstartup or actual OS/model/API work.',
    closure_transport='Reviewed native Close in existing execPS reads bounded campaign metadata/hash; samePS is captured by closer/wrapper. NEW execPS Post only after actual wholeClose0. No standalone reader/newpwsh/binder.',
    provider_timeout_boundary='CoreR10 uses SDK<=170 inside unchanged outer180; only actual existing clean supervisor-bound ordinary provider_timeout stays failedNULL/no-worker. Unknown/resource/cleanup/provenance/usage errors remain fatal or unauditable; statusok+completeusage unchanged.')
save('protocol.json',protocol)

launch=read(B/'launch-terminal-contract.json')
hash_replacement={sha(B/n):sha(P/n) for n in runtime}


def relocated(value):
    if isinstance(value,dict):return {k:relocated(v) for k,v in value.items()}
    if isinstance(value,list):return [relocated(v) for v in value]
    if isinstance(value,str):
        if value in hash_replacement:return hash_replacement[value]
        return value.replace('qwen-three-hour-outer-next-dev-r9','qwen-three-hour-outer-next-dev-r10').replace('QH4','QH5').replace('qh4','qh5')
    return value


launch=relocated(launch)
launch['schema']='qh5-exact-launch-terminal-contract-source-v1'
launch['authoritative_prospective_startup_counts']=counts
launch['native_transport']={'contract':'qh5-closure-bootstrap-next-dev/contract.json',
    'handoff':template['native_closure_source'],
    'close':'Existing execPS: & ABS/close_native.ps1 -Mode Close -Template ROOT_HOSTED_ABS -TemplateSha256 SHA -SelfSha256 NATIVE_SHA -ActualMainExit ACTUAL -ActualMainTool CHUNK [-ActualMainSession ACTUAL_SESSION]',
    'post':'NEW execPS only after wholeClose0: & ABS/close_native.ps1 -Mode Post -SelfSha256 NATIVE_SHA -ActualWrapperExit 0 -ActualWrapperTool ACTUAL_CLOSE_CHUNK',
    'underlying_Python_argv_reference_only':'Existing negative/atomic/post sections describe unchanged Python contracts. Collector selects exactly nativeClose, then nativePost ifeligible; never also invoke closer manually.',
    'template':'Root materializes complete ABS+exactsource atomic template NOT_READY, missing ONLY actual_campaign_sha256, null campaign SHA, no campaign pin; native positive Close alone publishes actual binding via CreateNew.',
    'binding_output':'ABS_WORK/private/qh5-atomic-root-binding-r1.json'}
launch['future_predecessor']='Actual QH4 FAIL/qualified-current pair remains unchanged; root hosted finite projection baseline8541 plus allactualnew preparers, including guard-only UNKNOWN witnesses; existing receipt ABI only.'
save('launch-terminal-contract.json',launch)

external={}


def pin(relative,expected):
    assert not relative.startswith('work/') and not Path(relative).is_absolute(), relative
    assert relative not in external or external[relative]==expected, ('source_pin_collision',relative)
    external[relative]=expected


for rel,h in base_handoff['external_refs_sha256'].items():pin(rel,h)
pin('qwen-three-hour-outer-next-dev-r9/source-handoff-final.json',sha(B/'source-handoff-final.json'))
for rel,h in base_handoff['files_sha256'].items():
    assert sha(B/rel)==h
    pin('qwen-three-hour-outer-next-dev-r9/'+rel,h)
for folder,hname in [(CORE,'source-handoff-final.json'),(AUDITOR,'source-handoff.json'),
    (W/'qh5-closure-bootstrap-next-dev','source-handoff.json'),(W/'qh5-collector-next-dev','source-handoff.json')]:
    hand=read(folder/hname);pin((folder/hname).relative_to(W).as_posix(),sha(folder/hname))
    for rel,h in hand['files_sha256'].items():
        assert sha(folder/rel)==h
        pin((folder/rel).relative_to(W).as_posix(),h)
    for rel,h in hand.get('external_refs_sha256',{}).items():pin(rel,h)
for rel,h in reviews.values():pin(rel,h)
for rel in ['qh5-native-closure-bootstrap-fm-independent-source-review-r1.json','qh5-collector-eo-independent-source-review-r1.json']:
    pin(rel,sha(W/rel))

proof={'schema':'qwen-QH5-outer-R10-source-proof-v1','status':'SOURCE_ONLY_NOT_READY',
    'source_R9_final_handoff_sha256':sha(B/'source-handoff-final.json'),
    'allowed_runtime_changes':['Four OUT literals qh4->qh5','Five main CORE/CORE_SHA/AUDITOR/AUDITOR_HANDOFF_SHA/SOURCE_REVIEWS assignments only'],
    'whole_main_module_inverse':True,'other_three_raw_OUT_inverses':True,'all_functions_and_classes_AST_exact':True,
    'genericPS_and_both_outer_tests_raw_exact':True,'original_R9_local_files_preserved_externally':len(base_handoff['files_sha256']),
    'recursive_source_copy':False,'component_core':template['core_handoff'],'component_auditor':template['auditor_handoff'],
    'source_reviews':template['source_reviews'],'methods':method_map,'counts':counts,'prepared_total':83,
    'setup9slots270':True,'actual_contract_executions':0,'caps_unchanged':template['caps'],
    'all_previous_failures_and_clocks_preserved':True,'new_QH5_clock':None,
    'metadata_preflight_R2_same9functions14globals':True,'native_bootstrap_source':template['native_closure_source'],
    'collector_source':template['collector_source'],'collector_cases_separate_from83':10,
    'current_predecessor_baseline_before_new_preparers':8541,
    'no_candidate_imports_tests_models_API_data_PID_Git_canonical_by_author':True}
save('source-proof.json',proof)
(P/'README.txt').write_text('SOURCE ONLY / NOT_READY. QH5 uses exact reviewed CoreR10 and AuditorR7 with83 prepared methods in9unchanged30/20slots (270setupmaximum); author executions0.\n'
    'Only4OUTliterals and5component/header assignments differ from exact frozen OuterR9. All functions/guards/clocks/resources/quality/identity predicates are unchanged; generic close_child.ps1 and both outer fixture files remain byteexact. Prior files are external original-path references, never recursively copied.\n'
    'The root collector085d and10pure injected-tool mocks are separately source-reviewed and root-executed; these are not83startup/model/API counts. Native bootstrap6114/peer efeb owns samePS native metadata/atomicbinding transport and NEWPSPost after actualwholeClose0. No standalone reader or extra binder process.\n'
    'See launch-terminal-contract.json and native contract for exact CLI/filenames/roles. Root owns all actual ABS private bindings, strict metadata preflight/current8541+newpreparer absence, publication, READY and one prospective10800 launch. AllQH1-QH4FAILs/metricsNULL remain preserved; archiveeb85qualification unchanged.\n',encoding='utf-8')
files={p.name:sha(p) for p in P.iterdir() if p.is_file() and p.name!='source-handoff.json'}
handoff={'schema':'qh5-outer-R10-source-handoff-v1','status':'FROZEN_SOURCE_ONLY_PENDING_PEER',
    'files_sha256':files,'external_refs_sha256':external,'prepared_contract_executions':83,
    'actual_contract_executions':0,'actual_experiment_clock':None,'actual_metrics':None,'READY':None,
    'current_predecessor_complete_observed_baseline':8541,'all_previous_FAILs_preserved':True,
    'native_and_collector_proofs_separate_from83':True,'recursive_source_copy':False}
save('source-handoff.json',handoff)
print(json.dumps({'handoff_sha256':sha(P/'source-handoff.json'),'driver_sha256':sha(P/'run_campaign.py'),
    'local':len(files),'external':len(external),'counts':counts,'total':sum(counts)}))
