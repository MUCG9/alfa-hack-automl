"""Fixed RA1 current-negative finite observation; never qualification/reset."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,time
P=Path(__file__).resolve().parent;WORK=P.parent;OUT=WORK/'ra1'
LOCK=WORK/'alfa-hack-automl/test-runs/.owned-research.lock'
BASE=WORK/'br-standard-release-qualification-next-dev/controller-r5/run_controller.py'
BASE_SHA='d5f41cad6de2168cd520e442223428285dd3714854079d9305dd1b34938abd7d'
REFS={'manifest': ('private/ra1-manifest.ready-r2.json', '84b93538b73d73e2636b0730ad4cd105b2901633990e4654ccf9463e724d63f3'), 'campaign': ('ra1/campaign.json', '20fb2e4f4251218e62f1e91126ce581dc2c4cfc6a692d004d4b1b6aad7585536'), 'root': ('ra1/terminal-root-closure.json', '94132c7d68a49e7e85ee795f648db724891b8ea6ba7f670dacb151ac63afc6ca'), 'preparers': ('ra1/preparer-identity.json', 'e8a853e8027c32cb3f7d70b6b4249916f58516e9c8d3e3537f63832b5afb76e0'), 'root_preparers': ('ra1/root-preparer-identity.json', '0828aa3b2ac4f2623d6eb2b7a7a16b7eea65cf47b9b28f1fbb7a053e0e6ce6b1'), 'repair_context': ('ra1/repair-context.json', '2fe9e38d594366c3766d4d25926d767b38d994adf5374128fcf258d74470f5b1'), 'rq6_manifest': ('private/rq6-manifest.ready-r1.json', 'f4eb5dca1e3560de66206c76937d0314a790047436bd80f218422c9324afd65a'), 'rq6_campaign': ('rq6/campaign.json', '60afb434d1e6f943d05be02c0761cdb255745fe3e543961ed407e559eaf38725'), 'rq6_root': ('rq6/terminal-root-closure.json', 'f9e26b3a9e9223fc903909aafd3172dbd0b4242b142d9d29cf8593a3379d9810'), 'rq6_negative': ('rq6/current-negative-closure.json', 'fe8941210806633144b53f2f1345daa3922f7099dc81148637da7240592ce0bc'), 'rq6_post': ('rq6/current-negative-post-tool-confirmation.json', '9ad55350293113fbf7c026762979e06cc40a350b948718c39b998b8dea316fdc'), 'rq6_barrier': ('rq6/pretruth-barrier.json', '1a1c52f62d0badc5e579437e3f90b376e6f3e8440ca6948afbc92e45c1d79781'), 'rq6_regression_seal': ('rq6/regression-core-seal.json', '53c6dde06429214624ad071349b6365e0ddd5f73f8a8f5080c8b0dfa81cc7a9d'), 'rq6_classification_seal': ('rq6/classification-core-seal.json', '6d9345942bcb8e3752cdf66ba35f13292ed3f0f3da64481c3418f63bea1652fd'), 'rq6_old_auditor': ('last-submission-repair-qualification-next-dev-r6/artifact_audit.py', '910f8c5374b147c1d665ed01cb93f9b492f17d5cee330621f0f23685854b7209'), 'metadata_0': ('private/ra1-root-readonly-preparer-r1.json', '813ddc65e7312f78636c1515557f46a29e3ef7184c8a180a28123d627c11a3e3'), 'metadata_1': ('private/ra1-final-readonly-preparer-r1.json', '7f12f00c5dc18a3fc8f1602bc0b117e11e39b1ccd12a440a572e2e1a6caee030'), 'metadata_2': ('private/ra1-reviewed-preflight-preparer-r1.json', '144d440d3ef3c3fc5e54dd33f8cb9695e9a9d42c17807d1ff1c94fce891c6be0'), 'supervisor_0': ('ra1/supervisors/auditor-contracts.json', 'fb8a8c08d5b473d0627e09d015b9dc58fc02a696b9d5433ead7c9cfcb789b318'), 'log_0': ('ra1/supervisors/auditor-contracts.log', 'f2bc5d5c1426d4ca104ffd9363b5f5df9418381d0f0f921951c0489d5875d6bf'), 'supervisor_1': ('ra1/supervisors/caller-contracts.json', '7ff4355cdff10286218c6bb5f693c4f8ca9303fb64894532a44a6aed64ed6593'), 'log_1': ('ra1/supervisors/caller-contracts.log', '79ec9ff1d33118813b8cb2f97271059be2ef8939f84d70bb02e1178732888b78'), 'supervisor_2': ('ra1/supervisors/atomic-root-contracts.json', '6826f572320dc6e95663973e752ab17cef8487f2d28be0d9ac882f8a45d0f1f7'), 'log_2': ('ra1/supervisors/atomic-root-contracts.log', '01446eeab3b12eb75d51c1cfe61b355a61f2530813b2be5b62e9af7c98546870'), 'supervisor_3': ('ra1/supervisors/saved-standard-artifact-audit.json', '1976a1111a2738a8793e43783f7ea146746815ddd85d2f9a29856bad9b8b30fb'), 'log_3': ('ra1/supervisors/saved-standard-artifact-audit.log', '5b8006fdc4872e45eca725fb8ab4aec2d4bc786af54780417341d3a57052e9fc')}
SUPERVISORS=[{'key': 'supervisor_0', 'status': 'ok', 'exit_code': 0}, {'key': 'supervisor_1', 'status': 'ok', 'exit_code': 0}, {'key': 'supervisor_2', 'status': 'ok', 'exit_code': 0}, {'key': 'supervisor_3', 'status': 'child_failed', 'exit_code': 1}]
METADATA_ACTUAL=[{'exit_code': 0, 'tool': '731cd5'}, {'exit_code': 0, 'tool': 'b50ff7'}, {'exit_code': 0, 'tool': '20089d'}]
OBSERVER_SHA='0a38c6f20f103a3a997d287041d5ba6a8f5a814e2c0a33164127f2301d101b16'

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
    need(__debug__ and sha(BASE)==BASE_SHA,'qualified_C5_changed');base=imported('_ra1_current_C5',BASE)
    import psutil
    preparers,chain=base.capture(psutil,a.launch_parent_pid,a.launch_parent_create_time)
    early=OUT/('current-negative-post-tool-preparer-identity.json' if post else 'current-negative-preparer-identity.json')
    need(not early.exists(),'exclusive_new_current_observer');base.save(early,dict(identities=preparers,launch_parent_observation=chain))
    need(chain.get('verified') is True and sha(__file__)==a.self_sha256,'actual_observer_source_or_chain_unconfirmed')
    expected={str(Path(__file__).resolve()):a.self_sha256,str(BASE):BASE_SHA,str(early):sha(early),**{str(WORK/r):h for r,h in REFS.values()}}
    for path,h in expected.items():need(sha(path)==h,'fixed_current_metadata_changed')
    cfg=read(WORK/REFS['manifest'][0]);state=read(WORK/REFS['campaign'][0]);root=read(WORK/REFS['root'][0])
    original=read(WORK/REFS['rq6_campaign'][0]);inherited=state['inherited_original_clock']
    need(state['absolute_deadline_unix']==state['start_unix']+600 and state['common_deadline_monotonic']==state['start_monotonic']+600
        and inherited=={k:original[k] for k in ('start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic')}
        and original['absolute_deadline_unix']==original['start_unix']+6000 and original['common_deadline_monotonic']==original['start_monotonic']+6000,'same_RA1_600_and_inherited_RQ6_6000_required')
    need(state.get('schema')=='postfailure-standard-artifact-qualification-campaign-v1' and state.get('status')=='failed'
        and len(state.get('contracts',[]))==3 and sum(v['expected'] for v in state['contracts'])==22
        and state.get('active_supervisor') is None and state.get('failure_code')=='child_nonzero_exit'
        and state.get('first_failure',{}).get('child_kind')=='saved-standard-artifact-audit'
        and len(state.get('supervisors',[]))==4 and state.get('artifact_procedure_passed') is False
        and state.get('quality_metric') is None and state.get('qualified_artifacts') is None
        and not (OUT/'independent-artifact-audit.json').exists(),'actual_RA1_failed_saved_audit_after22_contracts_required')
    need(root.get('schema')=='postfailure-standard-artifact-qualification-root-v1' and root.get('technical_procedure_passed') is False
        and root.get('actual_exec_session')==25644 and root.get('actual_exec_exit_code_observed_by_root')==1
        and root.get('actual_tool_evidence')=='19905f' and root.get('manifest_sha256')==REFS['manifest'][1]
        and root.get('quality_metric') is None and root.get('independent_audit') is None
        and root.get('original_RQ6_FAIL_preserved') is True and root.get('original_RQ6_procedure_requalified') is False
        and root.get('active_owned_processes')==root.get('uncertain_owned')==root.get('changed_source_or_core')==root.get('root_errors')==[]
        and all(root.get(k) is True and state.get(k) is True for k in ('cleanup_confirmed','source_unchanged','temporary_cleanup_confirmed')),'typed_clean_negative_RA1_root_never_PASS')
    need(len(cfg['immutable_files'])==1560 and all(Path(path).is_absolute() for path in cfg['immutable_files']),'exact_absolute1560_sourcepins_required')
    supervisors=[]
    for index,row in enumerate(SUPERVISORS):
        actual=state['supervisors'][index];ref=REFS[row['key']];sup=read(WORK/ref[0]);ob=sup.get('cleanup_observation',{})
        need(actual['sha256']==ref[1] and actual['path']==ref[0] and sup.get('status')==row['status'] and sup.get('exit_code')==row['exit_code']
            and sup.get('cleanup_confirmed') is True and ob.get('unresolved')==[] and ob.get('denial_count')==0
            and sup.get('maximum_observed_concurrent_worker_jobs')==0,'all_actual_no_model_supervisors_cleanly_terminal_required');supervisors.append(sup)
    for path,h in cfg['immutable_files'].items():
        need(path not in expected or expected[path]==h,'immutable_source_pin_collision');expected[path]=h
    modules={}
    for name in ('owner','sampling','lock','awake'):
        rel,h=base.HELPERS[name];need(expected.get(str(WORK/rel))==h and sha(WORK/rel)==h,'qualified_current_helper_changed');modules[name]=imported('_ra1_current_'+name,WORK/rel)
    stats={};pulse=base.guard(start_mono,min(start_mono+30,state['common_deadline_monotonic'],inherited['common_deadline_monotonic']),
        min(start_wall+30,state['absolute_deadline_unix'],inherited['absolute_deadline_unix']),modules['owner'],preparers,stats,sampling=modules['sampling'])
    def check():pulse()
    pulse(force=True)
    oldpost=read(WORK/REFS['rq6_post'][0]);oldnegative=read(WORK/REFS['rq6_negative'][0])
    known=base.ids(oldpost['known_identities']);oldobserver=base.ids(oldpost['observer_preparer_identities'])
    need(len(known)==oldpost['known_count']==8013 and len(oldobserver)==3 and not known&oldobserver
        and known==base.ids(oldnegative['known_identities']+oldnegative['observer_preparer_identities'])
        and oldpost.get('post_tool_current_confirmation') is True and oldpost.get('known_exact_live')==oldpost.get('uncertain')==[],'exact_original8016_known_scope_required')
    known|=oldobserver;need(len(known)==8016,'original8016_required')
    need(len(cfg['launch_preparer_receipts'])==len(METADATA_ACTUAL)==3,'all_three_actual_root_collectors_required')
    for i,actual in enumerate(METADATA_ACTUAL):
        ref=cfg['launch_preparer_receipts'][i];rel,h=REFS['metadata_'+str(i)];metadata=read(WORK/rel);own=base.ids(metadata['identities'])
        need(ref==dict(path=str(WORK/rel),sha256=h,actual_tool=actual) and metadata.get('actual_tool')==actual and actual['exit_code']==0
            and actual['tool'] and len(own)==3 and not known&own,'exact_actual_collector3_required');known|=own
    need(len(known)==8025,'original8016_plus_three_actual_collectors_required')
    known|=base.ids(state['owned_process_identities']+[state['owned_root']]+state['coordinator_bootstrap_identities'])
    known|=base.ids(root['owned_identities']+root['closure_preparer_identities'])
    for sup in supervisors:known|=base.ids(sup['owned_process_identities']+[sup['owned_root']])
    main_preps=read(WORK/REFS['preparers'][0])['identities'];root_preps=read(WORK/REFS['root_preparers'][0])['identities']
    need(len(base.ids(main_preps))==len(base.ids(root_preps))==3 and base.ids(root_preps)==base.ids(root['closure_preparer_identities']),'exact_actual_main_and_closer_preparers')
    known|=base.ids(main_preps+root_preps);need(len(known)==8039,'exact_current_RA1_known8039')
    if post:
        previous=OUT/'current-negative-closure.json';previous_preparers=OUT/'current-negative-preparer-identity.json'
        need(len(a.negative_sha256)==64 and all(c in '0123456789abcdef' for c in a.negative_sha256) and bool(a.negative_tool.strip()),'actual_negative_hash_and_exit0_tool_required')
        expected.update({str(previous):a.negative_sha256,str(previous_preparers):sha(previous_preparers),str(P/'observe_current.py'):OBSERVER_SHA})
        for path,h in expected.items():need(sha(path,check)==h,'actual_negative_output_source_changed')
        old=read(previous);prior=base.ids(old['known_identities']);own=base.ids(old['observer_preparer_identities'])
        need(old.get('schema')=='ra1-separate-current-negative-closure-v1' and old.get('technical_procedure_passed') is False
            and old.get('original_RA1_FAIL_preserved') is True and old.get('original_RQ6_FAIL_preserved') is True and old.get('root60_requalified') is False
            and old.get('original_negative_root_sha256')==REFS['root'][1] and old.get('source_pins_checked')==1560 and old.get('new_metrics') is None
            and all(old.get(k) is True for k in ('current_source_unchanged','current_cleanup_confirmed','current_temporary_absent','inside_original_RA1_common600','inside_inherited_RQ6_common6000'))
            and old.get('known_exact_live')==old.get('uncertain')==[] and prior==known and len(prior)==old['known_count']==8039
            and own==base.ids(read(previous_preparers)['identities']) and len(own)==3 and not known&own,'exact_prior8039_and_distinct_observer3_required')
        known|=own;need(len(known)==8042,'complete_post_current8042_required')
    need(not known&base.ids(preparers),'current_observer_never_old_absence_exclusion')
    need(LOCK.is_absolute() and LOCK.parent.is_dir() and not LOCK.parent.is_symlink(),'qualified_absolute_lock_parent_required')
    temp=Path(state['temporary_root'])
    def absent_temp():
        check();need(temp.is_absolute() and temp.parent==(WORK/'t').resolve() and temp.name=='ra-cu4p_oq1' and not temp.is_symlink() and not temp.exists(),'exact_receipt_owned_temp_must_remain_absent')
    def frozen():
        for path,h in expected.items():need(sha(path,check)==h,'current_source_or_failure_metadata_changed')
    lease=awake=None
    try:
        base.absent(modules['owner'],known,check);lease=modules['lock'].ResearchLock(LOCK);lease.__enter__();lease.write_identity(preparers[0])
        base.absent(modules['owner'],known,check);awake=modules['awake'].PowerRequestGuard('RA1 separate current negative only');awake.__enter__();stats['_awake']=awake
        absent_temp();frozen();base.absent(modules['owner'],known,check);absent_temp();frozen();pulse(force=True)
    finally:
        try:
            if awake is not None:awake.close();need(awake.record.get('release_API_verified') is True,'current_Power_release_unconfirmed')
        finally:
            if lease is not None:lease.__exit__(None,None,None)
    pulse(force=True)
    result=dict(schema='ra1-current-negative-post-tool-confirmation-v1' if post else 'ra1-separate-current-negative-closure-v1',technical_procedure_passed=False,
        original_RA1_FAIL_preserved=True,original_RQ6_FAIL_preserved=True,original_RQ6_procedure_requalified=False,
        actual_failed_driver=dict(session=25644,exit_code=1,tool='19905f'),actual_failed_frozen_closer=dict(exit_code=1,tool='8efa0b'),
        original_campaign_sha256=REFS['campaign'][1],original_negative_root_sha256=REFS['root'][1],original_manifest_sha256=REFS['manifest'][1],
        original_campaign_flags={k:state[k] for k in ('cleanup_confirmed','source_unchanged','temporary_cleanup_confirmed')},
        first_failure=state['first_failure'],error_history=state['error_history'],frozen_root60_missed=time.time()>=root_preps[0]['create_time']+60,root60_requalified=False,
        current_source_unchanged=True,current_cleanup_confirmed=True,current_temporary_absent=True,temporary_root=str(temp),no_temp_deleted=True,sealed_core_requalification_claimed=False,
        original_contracts_observed=22,source_pins_checked=1560,known_count=len(known),known_identities=[dict(pid=p,create_time=b) for p,b in sorted(known)],known_exact_live=[],uncertain=[],
        observer_preparer_identities=preparers,launch_parent_observation=chain,own_parent_seconds=30,inside_original_RA1_common600=True,inside_inherited_RQ6_common6000=True,
        inside_saved_driver_final240=time.monotonic()<state['final_deadline_monotonic'],new_qualification=False,old_clock_reset=False,
        actual_tests=0,new_model_fits=0,API_calls=0,new_metrics=None,promotion=False,submit=False,observation_seconds=time.monotonic()-start_mono,
        resource_observation={k:v for k,v in stats.items() if not k.startswith('_')},actual_helper_exit_and_later_preparer_absence_required=True,post_tool_current_confirmation=post)
    if post:result.update(negative_closure_sha256=a.negative_sha256,actual_negative_observer=dict(exit_code=0,tool=a.negative_tool))
    target=OUT/('current-negative-post-tool-confirmation.json' if post else 'current-negative-closure.json');need(not target.exists(),'exclusive_new_current_result');check();base.save(target,result)
    try:pulse(force=True)
    except BaseException:
        result.update(current_source_unchanged=False,current_cleanup_confirmed=False,current_temporary_absent=False,inside_original_RA1_common600=False,inside_inherited_RQ6_common6000=False,post_tool_current_confirmation=False)
        base.save(target,result);raise
    print(json.dumps(dict(current_negative_only=True,known_count=len(known),source_pins=1560,technical_procedure_passed=False)));return 0

if __name__=='__main__':raise SystemExit(main(True))
