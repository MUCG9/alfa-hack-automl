"""Fixed QH4 current-negative finite observation; never qualification/reset."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,time
P=Path(__file__).resolve().parent;WORK=P.parent;OUT=WORK/'qh4'
LOCK=WORK/'alfa-hack-automl/test-runs/.owned-research.lock'
BASE=WORK/'br-standard-release-qualification-next-dev/controller-r5/run_controller.py'
BASE_SHA='d5f41cad6de2168cd520e442223428285dd3714854079d9305dd1b34938abd7d'
REFS={'manifest': ('private/qh4-manifest.ready-r1.json', 'c0d9b83d6627695b16921b3f54d5f0343bdd05ef54c475df661b8d24e610013d'), 'campaign': ('qh4/campaign.json', '8515132488dcc97bd8b4f188281b22c6d7a8b56dddf68036988e87c98dbc9836'), 'root': ('qh4/terminal-root-closure.json', '0176814e986e7c0e5dcfaa310227441f62e2824e4e9a8274790a82d584d5e469'), 'preparers': ('qh4/preparer-identity.json', '1dd1ba973dced787387f3d037f43498313b81a38085031bb6c7f6f4aa3fbcf90'), 'root_preparers': ('qh4/root-preparer-identity.json', '6306215c984bed7f0e21fb0cfb1d79595cb0fce1926b9f6eb55c44a30b68f964'), 'task_manifest': ('qh4/regression-task-manifest.json', 'dfd57efd1913b09505ac2fd612e0a679cede07948382d35dd29183dee621bfa0'), 'terminal_tools': ('private/qh4-actual-terminal-tools-r1.json', 'b6d067236551178e4e387b0c7d351dbba33e02942a1ffc8126839c0691238160'), 'negative_tools': ('private/qh4-negative-closure-actual-tools-r1.json', '762467ee5040feea651ba6fe9befdb50bbd06550db564c6071f8f9669e2aa79f'), 'diagnostic': ('qh4/first-negative-closer-post-exit-observation.json', 'ab1e7db661e5494a8c47261a0e2c3a9d28f8964b4861abaada1f72ced70ff71e'), 'diagnostic_exit': ('qh4/diagnostic-observer-exit-confirmation.json', '6d7c762baf43c072225a95adf0c8b47b1c8beb84ee8fdcf879d9ff01fd2bdd21'), 'prior_negative': ('qh3/current-negative-closure-r2.json', '8149c1921bd57cfe676555af494cbaf62b1d20e4ec95caff8c6606d18584d6ee'), 'prior_post': ('qh3/current-negative-post-tool-confirmation-r2.json', 'abd0a5d94940414727c9beed5f3c9c6c43e05b2b3eb0e67d8a36ee3d70373dcd'), 'prior_tools': ('private/qh3-current-negative-r2-actual-tools.json', 'bdce0f654861b2ec2244ba4bad8c068990550d37a46893123c357a1949fc5dd5'), 'qualification_root': ('ra2/terminal-root-closure.json', '750f2195266b6b5f87492bed95a6ad1b27fac58c18cfb1b80361e3fa8f974982'), 'qualification_confirmation': ('ra2/root-confirmation.json', '3ef9a0ddf7faa11509f83a381da98f458b3a80cd10a27b39812ba7e09bd9359a'), 'qualification_post_tool': ('ra2/actual-wrapper-exit-confirmation.json', '3f1daf1780d9115fe3c3d4babc5c49c48dbdf059da54def349b3b3fc185d389b'), 'qualification_qualification_manifest': ('private/ra2-manifest.ready-r2.json', '62d3d5152e51c6d5be557f3a671aeff021fa1d599ed86c0a90583385a4da9690'), 'metadata_0': ('private/qh1-metadata-contract-preparer-r1.json', 'b9e906e074b2db2c6e00e935b262cb70fff2b88e74d175db8e6a542c7b7eb4a5'), 'metadata_1': ('private/qh1-binding-metadata-preparers-r1.json', '1afa2e0fded33a4eee6d3c7aad02df6b19ed2240dc5e9d836daa36ff09160263'), 'metadata_2': ('private/qh1-exact-preflight-preparer-r1.json', '8f830f2bca515aa38f9502a01c735804892d69f59d1b37849ca5613390e305f2'), 'metadata_3': ('private/qh2-root-predecessor-identities-r1.json', 'b283c60b5afb85ddb10e0dacdb10af16ae428682b483ba65b2e2de47f119d1cc'), 'metadata_4': ('private/qh2-entrypoint-contract-preparer-r1.json', 'e5d305fbfd0ab2ccb6e1dffdb1786ff3461ef4dd65fca348f6d89b564b6f5dab'), 'metadata_5': ('private/qh2-exact-preflight-preparer-r1.json', '7a99c026a8786391112370cf78714d4899e92a480fc3a314ca01a6af0ca002aa'), 'metadata_6': ('private/qh3-root-predecessor-identities-r1.json', '683e9b4d5cfce14574deeeb5a91802c607e429949c5cc14491b835e1fc14fa49'), 'metadata_7': ('private/qh3-closure-delta-contract-preparer-r1.json', 'ae31cbeea4b936f888ac0872f33e01e1a42b0713bbbe5c05891599f28d74c736'), 'metadata_8': ('private/qh3-delta-resource-identities-supplement-r1.json', 'f5b2b14cceb963579438cffcc2f0ec47a1d06c59151a15e76429c21ada184210'), 'metadata_9': ('private/qh3-bounded-admission-resource-supplement-r1.json', '96e347470948f13a8ea1400c8ce1401b0a9f7090656c4dfdf69fb9716073da20'), 'metadata_10': ('private/qh3-exact-preflight-preparer-r1.json', 'cb614ad8e710336901a949542fcffc3ed4443618f891c7788aaa5e29be48e311'), 'metadata_11': ('private/qh4-root-predecessor-identities-r1.json', '0d9c33e8a38f97d95e2d388c090f29f818a21baf7191ac1b31ec5f8e8568fd33'), 'metadata_12': ('private/qh4-observed-resource-identities-supplement-r1.json', '145b1e9c1114ed58e272622b438e4b1b21d2f956da313402aca8db1e31d2309b'), 'metadata_13': ('private/qh4-metadata-preflight-preparer-r1.json', '9ecbdd627587ca4208048f6a943d96b4fc1bac3da0b38053da7f6b8d52595ea9'), 'supervisor_0': ('qh4/supervisors/core-parent-ledger.json', '8f158e59f75116d1be354b5b8b9b920cbf61d64d925fac84a83775d9d08cdab5'), 'log_0': ('qh4/supervisors/core-parent-ledger.log', '74da57a7abbe641df922184e461b0d6612bb8762e9e4841b4b8aff1cdf409174'), 'supervisor_1': ('qh4/supervisors/core-provider-environment.json', '442db4e21bc2196330a24128adafac263f92c5561ad8ed55e629d61b0791c7c0'), 'log_1': ('qh4/supervisors/core-provider-environment.log', '2d93268cd37db0a04ca7932eb11e2e64dad2b50bb2ed012497a2f26af5938751'), 'supervisor_2': ('qh4/supervisors/core-worker-consumer.json', '2b8baf486766608a31570219433dec82a42be721e797e4ca9f0af9a3d8bc59cb'), 'log_2': ('qh4/supervisors/core-worker-consumer.log', 'd3d2e4ec09c3bd02858c01e24956791f2b845dc8df601c3dec78d491006380f7'), 'supervisor_3': ('qh4/supervisors/core-iterative-policy.json', 'cf2edee672ca2aa7a811585e6e179bffc4ff11abb082892f82247ce89a55136f'), 'log_3': ('qh4/supervisors/core-iterative-policy.log', '3e2a09294303a89e0e44c0da8fc58dfe005caade7a5f9b5b04a3c8a7481ed54c'), 'supervisor_4': ('qh4/supervisors/core-resource-origin.json', '805f63ba12b7fbd196d875c1c9ab9317109555ca6b63be5c9e6f777c61c1556d'), 'log_4': ('qh4/supervisors/core-resource-origin.log', '8066b1ddf31e766689defebede96bd5719bcf77b5db4cc7144d229734b201316'), 'supervisor_5': ('qh4/supervisors/independent-audit-contracts.json', '0e9d20e79f9b1ad9028ed3ccdf0be267cfa2312a06073ca43e513267d96f651b'), 'log_5': ('qh4/supervisors/independent-audit-contracts.log', '41e071485c06db3a2733864f8279e7858d09c4372dab387d6c7c78391a74da00'), 'supervisor_6': ('qh4/supervisors/audit-CSV-role-contracts.json', 'f46bf40b319c32e5880e2440c79bab667e308ec7ed038d7adaeec2ec91fcfe6d'), 'log_6': ('qh4/supervisors/audit-CSV-role-contracts.log', '215f753f8c21490c0a9ae21136d480f39cc427b13167c3dccff8c0eaaaea8b4a'), 'supervisor_7': ('qh4/supervisors/outer-broker-authority-contracts.json', '3dffa02a5f1fc14e8c0f5f1ced3447cd7af8db01a5ac3e31e796336e38d85f08'), 'log_7': ('qh4/supervisors/outer-broker-authority-contracts.log', 'fa4767624ec40b3b09d173a8cc000dee41864bf90296681d999c3dcef82102f2'), 'supervisor_8': ('qh4/supervisors/outer-atomic-contracts.json', '95eda21bfa3c60774fa8edf1b4438feedf5a31e6b1d50eed5c401a00b520899f'), 'log_8': ('qh4/supervisors/outer-atomic-contracts.log', 'fdf5137cd9038f6bb90dc5feeafe195add3eb35d40aa6c6bc778015d1b70bd12'), 'supervisor_9': ('qh4/supervisors/regression.json', '208bc3897eb6ba1520e03bd39676d33f659785e6f870db65591484b3fcfe9874'), 'log_9': ('qh4/supervisors/regression.log', '7ccd03d50de28e2230c12ca9779bc23b4200ba70e86041c81ce5efa424dcd7be'), 'worker_1': ('qh4/r/worker-1/parent-result.json', '32fa9c39cd99a8e424cc4a43454784415f7bf68fa62bdca31d695ea507e2631c'), 'worker_2': ('qh4/r/worker-2/parent-result.json', '71994962535f60002d5349c63e42695aa0c4f8730c2aa028e43035f110f9b685'), 'worker_3': ('qh4/r/worker-3/parent-result.json', 'ce7dbc8572ef2f0090c31f18941518dc4922c9c98ddbbdb5c4209a19671e8c34'), 'worker_4': ('qh4/r/worker-4/parent-result.json', '3d6f19e6604c71b196671dcc1388c7e73cf91b7efa39a2542cd7c573ebe47c2a'), 'worker_5': ('qh4/r/worker-5/parent-result.json', '3ff6ef22fd66a241bc08a6cf8d3f3b2e7ddd039863d85fd356018ac1ca121c9b'), 'worker_6': ('qh4/r/worker-6/parent-result.json', '8245c906907b339b4b2ddd6cea80a5c1731b7dca7cc972809efe51e34edbdade'), 'worker_7': ('qh4/r/worker-7/parent-result.json', '37977c5187087c9061528d1d593344a05050e1b7728d4a58e5ba2e4c73316552'), 'worker_8': ('qh4/r/worker-8/parent-result.json', 'bda037131e03ad502e3df0c34a2223495c741ea8799c58df7993fc0bcd2d5529'), 'worker_9': ('qh4/r/worker-9/parent-result.json', '2c5d2f6934c01095d9393ec85f5ea2f7ab500f9802f18b522b1bc1afcf4de347'), 'worker_10': ('qh4/r/worker-10/parent-result.json', '192cdc88ddcb0c6186f9b797d4123b8f2ab9205c37e0ca6dc7c540855bdab735'), 'gateway_1': ('qh4/r/gateway-1/supervisor.json', '4871652dda69351cd2db2267a15541f068fd7af9de8c7f9111a6c6a2fd61da6c'), 'gateway_2': ('qh4/r/gateway-2/supervisor.json', '8f9566a18d93e84f1ab4ed76aa00397f26bd974b355265a0b05acb7780766e4a'), 'gateway_3': ('qh4/r/gateway-3/supervisor.json', '67e9ded96fa46a1c094e01d40688d37c92fcf357da4667789b2f1f9eb3e161c8'), 'gateway_4': ('qh4/r/gateway-4/supervisor.json', '23528c1f78bd7eee36e298f9443d3eb2e6dcbb2cc6b1c837c16bd4cf3595874e')}
SUPERVISORS=[{'key': 'supervisor_0', 'status': 'ok', 'exit_code': 0, 'worker_count': 0, 'max_workers': 0}, {'key': 'supervisor_1', 'status': 'ok', 'exit_code': 0, 'worker_count': 0, 'max_workers': 0}, {'key': 'supervisor_2', 'status': 'ok', 'exit_code': 0, 'worker_count': 0, 'max_workers': 0}, {'key': 'supervisor_3', 'status': 'ok', 'exit_code': 0, 'worker_count': 0, 'max_workers': 0}, {'key': 'supervisor_4', 'status': 'ok', 'exit_code': 0, 'worker_count': 0, 'max_workers': 0}, {'key': 'supervisor_5', 'status': 'ok', 'exit_code': 0, 'worker_count': 0, 'max_workers': 0}, {'key': 'supervisor_6', 'status': 'ok', 'exit_code': 0, 'worker_count': 0, 'max_workers': 0}, {'key': 'supervisor_7', 'status': 'ok', 'exit_code': 0, 'worker_count': 0, 'max_workers': 0}, {'key': 'supervisor_8', 'status': 'ok', 'exit_code': 0, 'worker_count': 0, 'max_workers': 0}, {'key': 'supervisor_9', 'status': 'child_failed', 'exit_code': 1, 'worker_count': 10, 'max_workers': 1}]
METADATA_ACTUAL=[{'exit_code': 0, 'tool': '26f309'}, {'exit_code': 0, 'tool': '222d32'}, {'exit_code': 0, 'tool': 'd9cb33'}, {'exit_code': 0, 'tool': '6a35ef'}, {'exit_code': 0, 'tool': '67e275'}, {'exit_code': 0, 'tool': '1656e9'}, {'exit_code': 0, 'tool': '70ab3a'}, {'exit_code': 0, 'tool': '1ffd1d'}, {'exit_code': 0, 'tool': '1ffd1d'}, {'exit_code': 0, 'tool': '70ab3a'}, {'exit_code': 0, 'tool': '8e1c38'}, {'exit_code': 0, 'tool': 'aaaca3'}, {'exit_code': 0, 'tool': 'aaaca3'}, {'exit_code': 0, 'tool': '8fc79a'}]
ARCHIVE_SHA='eb85becbff8da0be93b97a8dafff108e426cdbed07476ed4f1dc0fb95e73c6fc'
OBSERVER_SHA='a88736ac62581eb5327ed0cace40202a8a626f37944af5bb6650ec45c93f1774'
WORKERS=[{'key': 'worker_1', 'index': 1}, {'key': 'worker_2', 'index': 2}, {'key': 'worker_3', 'index': 3}, {'key': 'worker_4', 'index': 4}, {'key': 'worker_5', 'index': 5}, {'key': 'worker_6', 'index': 6}, {'key': 'worker_7', 'index': 7}, {'key': 'worker_8', 'index': 8}, {'key': 'worker_9', 'index': 9}, {'key': 'worker_10', 'index': 10}]
GATEWAYS=[{'key': 'gateway_1', 'status': 'ok', 'exit_code': 0}, {'key': 'gateway_2', 'status': 'ok', 'exit_code': 0}, {'key': 'gateway_3', 'status': 'ok', 'exit_code': 0}, {'key': 'gateway_4', 'status': 'child_failed', 'exit_code': 1}]
HEARTBEATS=[]

def need(v,code):
    if not v:raise RuntimeError(code)

def read(p):return json.loads(Path(p).read_text('utf-8'))

def sha(p,check=lambda:None):
    h=hashlib.sha256()
    with Path(p).open('rb') as stream:
        while True:
            check();block=stream.read(2**20)
            if not block:break
            h.update(block)
    check();return h.hexdigest()

def imported(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def main(post=False):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--self-sha256',required=True)
    p.add_argument('--launch-parent-pid',required=True,type=int);p.add_argument('--launch-parent-create-time',required=True,type=float)
    if post:p.add_argument('--negative-sha256',required=True);p.add_argument('--negative-tool',required=True)
    a=p.parse_args();start_wall,start_mono=time.time(),time.monotonic()
    need(__debug__ and sha(BASE)==BASE_SHA,'qualified_C5_changed');base=imported('_qh4_current_C5',BASE)
    import psutil
    preparers,chain=base.capture(psutil,a.launch_parent_pid,a.launch_parent_create_time)
    early=OUT/('current-negative-post-tool-preparer-identity.json' if post else 'current-negative-preparer-identity.json')
    need(not early.exists(),'exclusive_new_current_observer');base.save(early,dict(identities=preparers,launch_parent_observation=chain))
    need(chain.get('verified') is True and sha(__file__)==a.self_sha256,'actual_observer_source_or_chain_unconfirmed')
    expected={str(Path(__file__).resolve()):a.self_sha256,str(BASE):BASE_SHA,str(early):sha(early),**{str(WORK/r):h for r,h in REFS.values()}}
    for path,h in expected.items():need(sha(path)==h,'fixed_current_metadata_changed')
    cfg=read(WORK/REFS['manifest'][0]);state=read(WORK/REFS['campaign'][0]);root=read(WORK/REFS['root'][0])
    need(state['start_unix']==1792891947.93135 and state['start_monotonic']==150953.328
        and state['absolute_deadline_unix']==state['start_unix']+10800 and state['common_deadline_monotonic']==state['start_monotonic']+10800,'same_original_QH1_10800_required')
    need(state.get('schema')=='qwen-three-hour-campaign-v1' and state.get('status')=='failed'
        and len(state.get('contracts',[]))==9 and sum(v['expected'] for v in state['contracts'])==77
        and [(r['name'],r['expected']) for r in state['contracts']]==[(r['name'],r['expected']) for r in cfg['contracts']]
        and state.get('active_supervisor') is None and state.get('failure_code')=='child_nonzero_exit'
        and state.get('first_failure',{}).get('child_kind')=='regression' and state.get('tasks')==[]
        and len(state.get('supervisors',[]))==10 and state.get('artifact_procedure_passed') is False
        and state.get('quality_metric') is None and state.get('independent_audit') is None
        and not (OUT/'independent-audit.json').exists(),'actual_QH1_failed_REG_entry_after77_contracts_required')
    need(root.get('schema')=='qwen-three-hour-root-closure-v1' and root.get('technical_procedure_passed') is False
        and root.get('actual_exec_session')==92878 and root.get('actual_exec_exit_code_observed_by_root')==1
        and root.get('actual_tool_evidence')=='11434a' and root.get('manifest_sha256')==REFS['manifest'][1]
        and root.get('qualified_ML_metrics') is None and root.get('independent_audit') is None
        and root.get('source_qualified_archive_sha256')==cfg['source_qualification']['archive']['sha256']==ARCHIVE_SHA
        and root.get('active_owned_processes')==root.get('uncertain_owned')==root.get('changed_source_or_core')==root.get('root_errors')==[]
        and all(root.get(k) is True and state.get(k) is True for k in ('cleanup_confirmed','source_unchanged','temporary_cleanup_confirmed')),'typed_clean_negative_QH1_root_never_PASS')
    need(len(cfg['immutable_files'])==3322 and all(Path(path).is_absolute() for path in cfg['immutable_files']),'exact_absolute3322_sourcepins_required')
    tools=read(WORK/REFS['terminal_tools'][0]);terminal=tools['main']['result']
    need(tools.get('schema')=='qh4-actual-terminal-tool-results-v1' and tools['launch']['session_id']==92878
        and terminal.get('exit_code')==1 and terminal.get('chunk_id')=='11434a'
        and tools.get('negative_closer') is None and tools.get('wrapper') is None and tools.get('post') is None
        and tools.get('collector_error')=='collector_tool_or_metadata_error','exact_failed_collector_before_any_closer_required')
    actual=read(WORK/REFS['negative_tools'][0]);diagnostic=read(WORK/REFS['diagnostic'][0]);diagnostic_exit=read(WORK/REFS['diagnostic_exit'][0])
    need(actual.get('schema')=='qh4-first-negative-closer-and-unqualified-observer-tools-v1'
        and actual['closer']['exit_code']==1 and actual['closer']['chunk_id']=='5c82cc'
        and actual['diagnostic_observer']['exit_code']==0 and actual['diagnostic_observer']['chunk_id']=='4c4173'
        and actual.get('observation_is_not_independently_qualified_guarded_closure') is True,
        'first_negative_closer_and_limited_diagnostic_actual_tools_required')
    need(diagnostic.get('schema')=='qh4-first-negative-closer-post-exit-finite-observation-v1'
        and diagnostic.get('root_sha256')==REFS['root'][1] and diagnostic.get('actual_closer_exit_code')==1
        and diagnostic.get('actual_closer_tool')=='5c82cc' and diagnostic.get('technical_procedure_passed') is False
        and diagnostic.get('qualified_ML_metrics') is None and diagnostic.get('known_identity_count')==8527
        and diagnostic.get('same_birth_live')==diagnostic.get('uncertain')==[],
        'unguarded_diagnostic_preserved_without_qualification')
    need(diagnostic_exit.get('schema')=='qh4-diagnostic-observer-exit-confirmation-v1'
        and diagnostic_exit.get('observer_receipt_sha256')==REFS['diagnostic'][1]
        and diagnostic_exit.get('actual_observer_tool')=='4c4173' and diagnostic_exit.get('actual_observer_exit_code')==0
        and diagnostic_exit.get('original_observer_absent_or_reused') is True and diagnostic_exit.get('uncertain') is None
        and diagnostic_exit.get('technical_qualification') is False
        and len(base.ids(diagnostic_exit['capture_chain_for_next_finite_union']))==3,
        'actual_limited_diagnostic_exit_and_metadata3_required')
    supervisors=[]
    for index,row in enumerate(SUPERVISORS):
        actual=state['supervisors'][index];ref=REFS[row['key']];sup=read(WORK/ref[0]);ob=sup.get('cleanup_observation',{})
        need(actual['sha256']==ref[1] and actual['path']==ref[0] and sup.get('status')==row['status'] and sup.get('exit_code')==row['exit_code']
            and sup.get('cleanup_confirmed') is True and ob.get('unresolved')==[] and ob.get('denial_count')==0
            and sup.get('maximum_observed_concurrent_worker_jobs')==row['max_workers']
            and len(sup.get('observed_worker_roots',[]))==row['worker_count'],'all_actual_no_model_supervisors_cleanly_terminal_required');supervisors.append(sup)
    for path,h in cfg['immutable_files'].items():
        need(path not in expected or expected[path]==h,'immutable_source_pin_collision');expected[path]=h
    modules={}
    for name in ('owner','sampling','lock','awake'):
        rel,h=base.HELPERS[name];need(expected.get(str(WORK/rel))==h and sha(WORK/rel)==h,'qualified_current_helper_changed');modules[name]=imported('_qh4_current_'+name,WORK/rel)
    stats={};pulse=base.guard(start_mono,min(start_mono+30,state['common_deadline_monotonic']),
        min(start_wall+30,state['absolute_deadline_unix']),modules['owner'],preparers,stats,sampling=modules['sampling'])
    def check():pulse()
    pulse(force=True)
    qualified=read(WORK/REFS['qualification_root'][0]);fresh=read(WORK/REFS['qualification_confirmation'][0]);oldpost=read(WORK/REFS['qualification_post_tool'][0])
    need(qualified.get('technical_procedure_passed') is True and qualified.get('archive_sha256')==ARCHIVE_SHA
        and all(qualified.get(k) is True for k in ('source_unchanged','cleanup_confirmed','temporary_cleanup_confirmed'))
        and qualified.get('manifest_sha256')==REFS['qualification_qualification_manifest'][1]
        and fresh.get('technical_procedure_passed') is True and fresh.get('root_sha256')==REFS['qualification_root'][1]
        and oldpost.get('post_tool_confirmed') is True and oldpost.get('root_sha256')==REFS['qualification_root'][1]
        and oldpost.get('root_confirmation_sha256')==REFS['qualification_confirmation'][1]
        and oldpost.get('actual_wrapper')==cfg['source_qualification']['wrapper_actual']
        and cfg['source_qualification']['post_tool_actual']==dict(exit_code=0,tool='bf9346')
        and all(oldpost.get(k) is True for k in ('source_unchanged','current_temporary_absent','current_cleanup_confirmed'))
        and oldpost.get('known_exact_live')==oldpost.get('uncertain')==[],'existing_archive_qualification_must_remain_unchanged')
    known=base.ids(oldpost['known_identities']);oldobserver=base.ids(oldpost['post_tool_preparer_identities'])
    need(len(known)==len(oldpost['known_identities'])==oldpost['known_count']==8068
        and known==base.ids(fresh['known_identities']+fresh['wrapper_preparer_identities']) and len(oldobserver)==3 and not known&oldobserver,'exact_qualified8071_scope_required')
    known|=oldobserver;need(len(known)==8071,'qualified8071_required')
    prior=read(WORK/REFS['prior_negative'][0]);priorpost=read(WORK/REFS['prior_post'][0])
    need(prior.get('schema')=='qh3-separate-current-negative-closure-v1' and prior.get('technical_procedure_passed') is False
        and prior.get('original_QH3_FAIL_preserved') is True and priorpost.get('schema')=='qh3-current-negative-post-tool-confirmation-v1'
        and priorpost.get('technical_procedure_passed') is False and priorpost.get('original_QH3_FAIL_preserved') is True
        and priorpost.get('post_tool_current_confirmation') is True and priorpost.get('negative_closure_sha256')==REFS['prior_negative'][1]
        and priorpost.get('actual_negative_observer')==dict(exit_code=0,tool='20b674')
        and priorpost.get('known_exact_live')==priorpost.get('uncertain')==[]
        and all(priorpost.get(k) is True for k in ('current_source_unchanged','current_cleanup_confirmed','current_temporary_absent','inside_original10800')),
        'unchanged_actual_failed_QH3_current_proof_required')
    prior_ids=base.ids(priorpost['known_identities']);prior_own=base.ids(priorpost['observer_preparer_identities'])
    need(len(prior_ids)==priorpost['known_count']==8464 and len(prior_own)==3 and not prior_ids&prior_own
        and prior_ids==base.ids(prior['known_identities']+prior['observer_preparer_identities']),'exact_failed_QH3_post_union_required')
    need(len(cfg['launch_preparer_receipts'])==len(METADATA_ACTUAL)==14,'all_fourteen_actual_QH_metadata_receipts_required')
    prelaunch=set()
    for i,actual in enumerate(METADATA_ACTUAL):
        ref=cfg['launch_preparer_receipts'][i];rel,h=REFS['metadata_'+str(i)];metadata=read(WORK/rel);own=base.ids(metadata['identities'])
        need(ref==dict(path=str(WORK/rel),sha256=h,actual_tool=actual) and actual['exit_code']==0 and actual['tool'],
            'exact_pinned_actual_metadata_ref_required')
        if i==11:
            need(metadata.get('schema')=='qh4-root-verified-failed-predecessor-identity-projection-v1'
                and metadata.get('technical_procedure_passed') is False and metadata.get('original_QH3_FAIL_preserved') is True
                and metadata.get('source_negative')==dict(path='work/'+REFS['prior_negative'][0],sha256=REFS['prior_negative'][1],actual_tool=dict(exit_code=0,tool='20b674'))
                and metadata.get('source_post')==dict(path='work/'+REFS['prior_post'][0],sha256=REFS['prior_post'][1],actual_tool=dict(exit_code=0,tool='69cba3'))
                and metadata.get('actual_tools')==dict(path='work/'+REFS['prior_tools'][0],sha256=REFS['prior_tools'][1])
                and own==prior_ids|prior_own and len(own)==metadata['known_count']==8467,
                'exact_hosted_failed_QH3_8467_projection_required')
        if i==12:
            need(metadata.get('schema')=='qh4-exact-observed-resource-identities-supplement-v1'
                and metadata.get('ownership_adopted') is False and len(own)==metadata['known_count']==2,
                'exact_UNKNOWN_resource_only_supplement_required')
        prelaunch|=own
    need(len(prelaunch)==8473 and known<=prelaunch and prior_ids|prior_own<=prelaunch,
        'exact_actual_QH4_prelaunch8473_scope_required');known|=prelaunch
    known|=base.ids(state['owned_process_identities']+[state['owned_root']]+state['coordinator_bootstrap_identities'])
    known|=base.ids(root['owned_identities']+root['closure_preparer_identities'])
    for sup in supervisors:known|=base.ids(sup['owned_process_identities']+[sup['owned_root']])
    def resource_ids(record):
        sample=record.get('verified_resource_sample') or {};terminal=record.get('terminal_resource_observation') or {}
        return base.ids(sample.get('sampled',[])+sample.get('departed',[])+record.get('departed_known_resource_identities',[])+terminal.get('departed',[]))
    observed_resources=resource_ids(state)|resource_ids(root['root_resource_observation'])
    for sup in supervisors:observed_resources|=resource_ids(sup)
    for row in WORKERS:
        parent=read(WORK/REFS[row['key']][0]);record=parent['result'];sample=record.get('verified_resource_sample')
        need(parent.get('schema')=='qwen-three-hour-parent-result-v1' and parent.get('callback_index')==row['index']
            and record.get('status')=='ok' and record.get('cleanup_confirmed') is True
            and record.get('parent_observed_worker_exit_code')==0 and type(sample) is dict,'actual_saved_parent_callbacks_required')
        worker=base.ids([record['worker_resource_root'],record['worker_resource_self']])
        need(worker<=base.ids(supervisors[-1]['owned_process_identities']+[supervisors[-1]['owned_root']]),'actual_worker_roots_and_sampler_self_within_owned_supervisor_required')
        known|=worker;observed_resources|=resource_ids(record)
    for row in GATEWAYS:
        record=read(WORK/REFS[row['key']][0]);ob=record.get('cleanup_observation',{})
        need(record.get('status')==row['status'] and record.get('exit_code')==row['exit_code'] and record.get('cleanup_confirmed') is True
            and ob.get('unresolved')==[] and ob.get('denial_count')==0,'all_actual_gateway_supervisors_terminal_cleanup_required')
        known|=base.ids(record['owned_process_identities']+[record['owned_root']]);observed_resources|=resource_ids(record)
    # Guard telemetry remains UNKNOWN/read-only, never owned or a worker grant.
    known|=observed_resources
    main_preps=read(WORK/REFS['preparers'][0])['identities'];root_preps=read(WORK/REFS['root_preparers'][0])['identities']
    need(len(base.ids(main_preps))==len(base.ids(root_preps))==3 and base.ids(root_preps)==base.ids(root['closure_preparer_identities']),
        'exact_actual_main_and_closer_preparers')
    known|=base.ids(main_preps+root_preps)
    diagnostic_ids=base.ids([diagnostic['observer_identity']]+diagnostic_exit['capture_chain_for_next_finite_union'])
    need(len(diagnostic_ids)==4,'exact_limited_diagnostic_and_confirmation4_required');known|=diagnostic_ids
    need(len(known)==8533 and len(observed_resources)==56,'exact_current_QH4_finite_observation_union')
    if post:
        previous=OUT/'current-negative-closure.json';previous_preparers=OUT/'current-negative-preparer-identity.json'
        need(len(a.negative_sha256)==64 and all(c in '0123456789abcdef' for c in a.negative_sha256) and bool(a.negative_tool.strip()),'actual_negative_hash_and_exit0_tool_required')
        expected.update({str(previous):a.negative_sha256,str(previous_preparers):sha(previous_preparers),str(P/'observe_current.py'):OBSERVER_SHA})
        for path,h in expected.items():need(sha(path,check)==h,'actual_negative_output_source_changed')
        old=read(previous);prior=base.ids(old['known_identities']);own=base.ids(old['observer_preparer_identities'])
        need(old.get('schema')=='qh4-separate-current-negative-closure-v1' and old.get('technical_procedure_passed') is False
            and old.get('original_QH4_FAIL_preserved') is True and old.get('root60_requalified') is False
            and old.get('original_negative_root_sha256')==REFS['root'][1] and old.get('source_pins_checked')==3322 and old.get('new_metrics') is None
            and all(old.get(k) is True for k in ('current_source_unchanged','current_cleanup_confirmed','current_temporary_absent','inside_original10800'))
            and old.get('known_exact_live')==old.get('uncertain')==[] and prior==known and len(prior)==old['known_count']==8533
            and own==base.ids(read(previous_preparers)['identities']) and len(own)==3 and not known&own,'exact_prior8152_and_distinct_observer3_required')
        known|=own;need(len(known)==8536,'complete_post_current8155_required')
    need(not known&base.ids(preparers),'current_observer_never_old_absence_exclusion')
    need(LOCK.is_absolute() and LOCK.parent.is_dir() and not LOCK.parent.is_symlink(),'qualified_absolute_lock_parent_required')
    temp=Path(state['temporary_root'])
    def absent_temp():
        check();need(temp.is_absolute() and temp.parent==(WORK/'t').resolve() and temp.name=='qh-iug8fi48' and not temp.is_symlink() and not temp.exists(),'exact_receipt_owned_temp_must_remain_absent')
    def frozen():
        for path,h in expected.items():need(sha(path,check)==h,'current_source_or_failure_metadata_changed')
    lease=awake=None;primary=None;secondary=[]
    try:
        base.absent(modules['owner'],known,check);lease=modules['lock'].ResearchLock(LOCK);lease.__enter__();lease.write_identity(preparers[0])
        base.absent(modules['owner'],known,check);awake=modules['awake'].PowerRequestGuard('QH4 separate current negative only');awake.__enter__();stats['_awake']=awake
        absent_temp();frozen();base.absent(modules['owner'],known,check);absent_temp();frozen();pulse(force=True)
    except BaseException as exc:primary=exc
    finally:
        try:
            if awake is not None:awake.close();need(awake.record.get('release_API_verified') is True,'current_Power_release_unconfirmed')
        except BaseException as exc:
            if primary is None:primary=exc
            else:secondary.append(dict(phase='Power_release',type=type(exc).__name__))
        try:
            if lease is not None:lease.__exit__(None,None,None)
        except BaseException as exc:
            if primary is None:primary=exc
            else:secondary.append(dict(phase='lock_release',type=type(exc).__name__))
    if primary is not None:
        print(json.dumps(dict(current_negative_only=True,technical_procedure_passed=False,primary_exception_type=type(primary).__name__,secondary_errors=secondary)))
        raise primary
    pulse(force=True)
    result=dict(schema='qh4-current-negative-post-tool-confirmation-v1' if post else 'qh4-separate-current-negative-closure-v1',technical_procedure_passed=False,
        source_revision='r1',original_QH4_FAIL_preserved=True,collector_parse_failure_preserved=True,
        limited_diagnostic_not_qualified=True,limited_diagnostic_identity=diagnostic['observer_identity'],
        limited_confirmation_preparers=diagnostic_exit['capture_chain_for_next_finite_union'],
        original_QH3_FAIL_preserved=True,original_QH2_FAIL_preserved=True,original_QH1_FAIL_preserved=True,original_archive_qualification_changed=False,source_qualified_archive_sha256=ARCHIVE_SHA,
        actual_failed_driver=dict(session=92878,exit_code=1,tool='11434a'),actual_failed_frozen_closer=dict(exit_code=1,tool='5c82cc'),
        original_campaign_sha256=REFS['campaign'][1],original_negative_root_sha256=REFS['root'][1],original_manifest_sha256=REFS['manifest'][1],
        original_campaign_flags={k:state[k] for k in ('cleanup_confirmed','source_unchanged','temporary_cleanup_confirmed')},
        first_failure=state['first_failure'],error_history=state['error_history'],frozen_root60_missed=time.time()>=root_preps[0]['create_time']+60,root60_requalified=False,
        current_source_unchanged=True,current_cleanup_confirmed=True,current_temporary_absent=True,temporary_root=str(temp),no_temp_deleted=True,sealed_core_requalification_claimed=False,
        original_contracts_observed=77,original_worker_callback_receipts_observed=10,original_nested_gateway_supervisors_observed=4,heartbeat_receipts_observed=0,source_pins_checked=3322,known_count=len(known),known_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],known_exact_live=[],uncertain=[],
        observer_preparer_identities=preparers,launch_parent_observation=chain,own_parent_seconds=30,
        finite_observation_scope='read_only_exact_known_PID_birth_absence_not_ownership_or_worker_adoption',
        unknown_resource_observations=[dict(pid=p,create_time=b,role='UNKNOWN') for p,b in sorted(observed_resources)],
        original_closer_resource_scope_only=True,primary_exception_type=None,secondary_errors=[],
        asserted_resource_process_roles=None,resource_only_identity_ownership_adopted=False,inside_original10800=True,
        inside_saved_driver_final240=time.monotonic()<state['final_deadline_monotonic'],new_qualification=False,old_clock_reset=False,
        actual_tests=0,new_model_fits=0,API_calls=0,new_metrics=None,promotion=False,submit=False,observation_seconds=time.monotonic()-start_mono,
        resource_observation={k:v for k,v in stats.items() if not k.startswith('_')},actual_helper_exit_and_later_preparer_absence_required=True,post_tool_current_confirmation=post)
    if post:result.update(negative_closure_sha256=a.negative_sha256,actual_negative_observer=dict(exit_code=0,tool=a.negative_tool))
    target=OUT/('current-negative-post-tool-confirmation.json' if post else 'current-negative-closure.json');need(not target.exists(),'exclusive_new_current_result');check();base.save(target,result)
    try:pulse(force=True)
    except BaseException as primary:
        result.update(current_source_unchanged=False,current_cleanup_confirmed=False,current_temporary_absent=False,inside_original10800=False,post_tool_current_confirmation=False)
        secondary=[]
        try:base.save(target,result)
        except BaseException as exc:secondary.append(dict(phase='negative_flag_revocation',type=type(exc).__name__))
        print(json.dumps(dict(current_negative_only=True,technical_procedure_passed=False,primary_exception_type=type(primary).__name__,secondary_errors=secondary)))
        raise primary
    print(json.dumps(dict(current_negative_only=True,known_count=len(known),source_pins=3322,technical_procedure_passed=False)));return 0


if __name__=='__main__':raise SystemExit(main(True))
