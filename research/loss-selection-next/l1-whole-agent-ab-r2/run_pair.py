"""SOURCE-ONLY until reviewed/published; future serial L1 seed whole-agent A/B.
ONE recovery under original LA1 10800s wall/monotonic clocks; setup900 includes
firstfailure, fix/publication and all preparation. Four fixed parents900/900/3600/3600,
audit600 and cleanup/root300. No clocks, copying, imports or children at preparation.
Both arms use one identical tested future source; only B regression enables L1.
Research evaluation; not official-default ready (flags/external JSON remain).
"""
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
import re
import signal
import sys
import time
import zipfile

sys.dont_write_bytecode = True
WORK = Path(__file__).resolve().parents[1]
OUTPUT = WORK/'la2'
BASE, BASE_SHA = 'm4packet/manifest.json', '8faf33cd81c0e864bcf338828c34447000111eda85bc719b8f43312d2babae9a'
COORDINATOR, COORDINATOR_SHA = 'run_lean_mvp_r2.py', '43be86ece6c453641afdcc6f8eccef02d713986e2ac8bf3314756f0bb78e0818'
R4, R4_SHA = 'repaired-mvp-r1-dev/evaluator_r4.py', 'c08e9f0be13a708d67b3266518381d6f1be3b0f43c384ef6425634160d7e2783'
CHAMPION, CHAMPION_SHA = 'champion-seed-next-dev/champion-t5-regression.json', '914880505ed751da9fd0a38d7f1724dd860c20d98456ff3efd16a195a0709ad4'
LINEAGE, LINEAGE_SHA = 'champion-seed-next-dev/champion-t5-lineage.json', '408d24be5c884152531552bb0016611eb55b9123aadb4c1a361396d3f7115cf3'
SEED, SEED_SHA = 'loss-agent-seed-next-dev/fixed-l1-seed-template.json', 'be704f101ae26938a786f4b8989b39dd2fe92258131a3e923b8fc48df4a9e2e5'
SEED_SIGNATURE = 'f06008802b5f6d3cfd130e4cd4c921781404560afac3cf3ddcbb58b1509295e4'
CHAMPION_SIGNATURE = '959a9b8fed203d71bafbbd4770b6bfb5b6aa5da79d08ee568b93979d7f795421'
OVERLAY_HANDOFF = '00a41c5c9d9bb4363e58e7c5a98ebd6356b86bbf107a23065249c2958edf2086'
COMMON, SETUP, AUDIT, CLEANUP = 10800, 900, 600, 300
PREVIOUS_CAMPAIGN = ('la1/campaign.json', 'dd078763bdc5c8f1831ae231c387b2dfe06c606b8b3ac3f1814ead0e2252a5be')
PREVIOUS_ROOT = ('la1/terminal-root-closure.json', '312f21c33afaa479d25483883c7a96e6d3fb5af9736ba5d9268255b4f4c4a07d')
ORIGINAL_CLOCK = (1792790233.8414314, 49238.875, 1792801033.8414314, 60038.875)

CAPS = {'regression': dict(parent=900, child=870, solver=810, hpo=300),
        'classification': dict(parent=3600, child=3570, solver=3510, hpo=900)}
ORDER = [('A','regression','r'),('B','regression','r'),('A','classification','c'),('B','classification','c')]
FAILURE_TYPE = RuntimeError
RETAINED_TERMINAL = {'kern-prep-r2-exec/terminal-root-closure.json': ('2042c250fefd526acee4ac40cd4d68fc3690220f6d3021bc691b885b5e3ae37e', 56393, 0), 'loss0/terminal-root-closure.json': ('c4916f2e7c7bd38e394bcb2ab33a51daf7a472a2aec8e08ff4b8a79a8fd5ba69', 99080, 0), 'kern-checks/terminal-root-closure.json': ('fef1f0342a991a76c6d1e99ed408d4660f738b11b31726ac78f991757d69f0f0', None, 0), 'queue-checks/terminal-root-closure.json': ('4006102127dd971c97843642754a748fc97199e20505c037f1688a80b8e12d27', None, 1), 'queue-checks-r2/terminal-root-closure.json': ('887a4b82614ca18d4589102a9f385d513e96ff5562dcb56ca3d2f95b6a186c34', None, 0), 'meth03l/terminal-root-closure.json': ('e02fd31162f1db27342895901ebb52764b140d59f9cd7651c9be447283bd3b9d', 63424, 0), 'meth02b/terminal-root-closure.json': ('fe00067cb099fdd4fdcd036861f5c3d55cd1c9ee0ee75bcddf488cfc035fe7f7', 38041, 0), 'meth02/terminal-root-closure.json': ('220e7c93f56eaa4a9c2e09ce70aa3ba406d864686cc68520bf69eace4ed75361', None, 1), 'meth03/terminal-root-closure.json': ('901f3c928d95d992800aef808ff70f84768a456bc23235e0ae63fd539fe159bf', 33253, 0), 'meth01/terminal-root-closure.json': ('2c67361da8f95875b35d124ac6c19d6cccba28c899f1e20dada88f3bec4ea283', 3417, 0), 'cp1/terminal-root-closure.json': ('96f5d956fa235cfd0904d55f67aeeaae8c93a083391fe8b370836f6e39ba309d', 43472, 0), 'cs0/terminal-root-closure.json': ('06d20ce5b1bfd51ceefc924f8d09eb06b4022e9998bcef4d36343cb58669fba8', 79591, 0), 'm4packet/terminal-root-closure.json': ('d19648a53253c0b070fe12068d6eafef5569e2d51332d9b212ef44cc828b9ddc', 65008, 0), 'loss01/terminal-root-closure.json': ('ce6accf1ec6b6f1e0c14dbb0c8913b55538f6a460450cbb2705ae36a37d3bcf3', 68631, 0)}


def need(value, code):
    if not value:
        raise FAILURE_TYPE(code)


def local(name):
    target = (WORK/name).resolve()
    need(not Path(name).is_absolute() and target.is_relative_to(WORK), 'reference_outside_work')
    return target


def sha(path, checkpoint=None):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            if checkpoint is not None:
                checkpoint()
            block = stream.read(2**20)
            if not block:
                break
            digest.update(block)
    if checkpoint is not None:
        checkpoint()
    return digest.hexdigest()


def load(path):
    return json.loads(Path(path).read_text('utf-8'))


def imported(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def merge(pins, name, digest):
    local(name)
    need(isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest), 'invalid_sha256')
    need(name not in pins or pins[name] == digest, 'conflicting_input_pin')
    pins[name] = digest


def solver_argv(arm, kind):
    cfg=CAPS[kind]
    argv=[sys.executable,'-B','-X','utf8','-u','solution.py','task.md',
        '--four-stage','--preserve-anchor','--protect-original-features',
        '--control-recipe','protected_control.json','--max-experiments','9',
        '--max-planner-calls','2','--max-llm-calls','4','--hpo-trials','8',
        '--hpo-budget',str(cfg['hpo']),'--hpo-sampler','tpe','--validation-strategy','auto',
        '--feature-selection-top-k','32','--planner-mode','staged','--run-name','repair4',
        '--time-budget',str(cfg['solver'])]
    if kind=='regression':
        argv+=['--champion-recipe','champion_recipe_input.json']
        if arm=='B':argv+=['--loss-seed-l1']
    return argv


def session(value):
    if value=='null':return None
    need(value.isdecimal() and int(value)>0,'actual_session_or_explicit_null_required')
    return int(value)



def inherited_clock(args):
    need((args.previous_campaign,args.previous_campaign_sha256)==PREVIOUS_CAMPAIGN
         and (args.previous_root_closure,args.previous_root_closure_sha256)==PREVIOUS_ROOT,
         'exact_original_failed_LA1_bindings_required')
    need(sha(local(PREVIOUS_CAMPAIGN[0]))==PREVIOUS_CAMPAIGN[1]
         and sha(local(PREVIOUS_ROOT[0]))==PREVIOUS_ROOT[1], 'original_failure_receipt_changed')
    previous,proof=load(local(PREVIOUS_CAMPAIGN[0])),load(local(PREVIOUS_ROOT[0]))
    fields=['start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic']
    need(all(type(previous.get(k)) in [int,float] and math.isfinite(previous[k]) for k in fields)
         and tuple(previous[k] for k in fields)==ORIGINAL_CLOCK and previous['common_seconds']==COMMON,
         'only_original_LA1_common_clock_allowed_no_reset')
    attempt_unix,attempt_mono=time.time(),time.monotonic()
    need(previous.get('status')=='technical_failure' and previous.get('qualification')=='FAIL'
         and previous.get('cleanup_confirmed') is True and previous.get('source_unchanged') is True
         and previous.get('arms')==[] and previous.get('independent_audit') is None
         and previous.get('first_failure',{}).get('code')=='authorized_API_environment_missing'
         and previous.get('finished_unix',float('inf'))<=attempt_unix
         and previous.get('finished_monotonic',float('inf'))<=attempt_mono,
         'only_closed_pre_model_API_environment_failure_recovery_allowed')
    need(proof.get('actual_exec_session')==25252 and proof.get('actual_exec_exit_code_observed_by_root')==1
         and proof.get('cleanup_confirmed') is True and proof.get('source_unchanged') is True
         and proof.get('technical_procedure_passed') is False
         and proof.get('original_common_seconds')==COMMON
         and proof.get('original_start_unix')==ORIGINAL_CLOCK[0]
         and proof.get('original_deadline_unix')==ORIGINAL_CLOCK[2]
         and proof.get('first_failure')==previous['first_failure']
         and proof.get('error_history')==previous['error_history']
         and proof.get('owned_identities') and proof.get('closure_preparer_identities')
         and proof.get('active_owned_processes',[])==[] and proof.get('uncertain_owned',[])==[],
         'actual_failed_25252_clean_root_proof_required')
    need(attempt_unix<ORIGINAL_CLOCK[0]+SETUP and attempt_mono<ORIGINAL_CLOCK[1]+SETUP,
         'original_setup900_exhausted_no_reset')
    need(abs((ORIGINAL_CLOCK[2]-attempt_unix)-(ORIGINAL_CLOCK[3]-attempt_mono))<=5,
         'wall_monotonic_clock_disagreement')
    reference=dict(campaign=dict(path=PREVIOUS_CAMPAIGN[0],sha256=PREVIOUS_CAMPAIGN[1]),
        root_closure=dict(path=PREVIOUS_ROOT[0],sha256=PREVIOUS_ROOT[1]),
        actual_exec_session=25252,actual_exec_exit_code_observed_by_root=1,
        original_status='FAIL_preserved',only_ONE_recovery=True,
        first_failure=previous['first_failure'],error_history=previous['error_history'])
    return (*ORIGINAL_CLOCK,attempt_unix,attempt_mono,reference)


def main():
    global FAILURE_TYPE
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--launch',action='store_true')
    for name in ['self-sha256','auditor-sha256','closer-sha256','prepared-manifest','prepared-manifest-sha256',
                 'source-archive','source-archive-sha256','stage0-campaign','stage0-campaign-sha256',
                 'stage0-root-closure','stage0-root-closure-sha256','stage0-exec-session']:
        p.add_argument('--'+name)
    for name in ['previous-campaign','previous-campaign-sha256','previous-root-closure','previous-root-closure-sha256']:
        p.add_argument('--'+name)
    p.add_argument('--bootstrap-launcher');p.add_argument('--bootstrap-launcher-sha256')
    p.add_argument('--extra-terminal-receipt',action='append',default=[],metavar='WORK_REL_PATH=SHA256')
    args=p.parse_args()
    if not args.launch:
        print(json.dumps(dict(status='inspection_only_no_clock_no_copy_no_import_no_children',
            common_seconds=COMMON,caps=CAPS,order=ORDER,research_only=True,official_default_ready=False)))
        return
    need(all(getattr(args,n.replace('-','_')) is not None for n in
        ['self-sha256','auditor-sha256','closer-sha256','prepared-manifest','prepared-manifest-sha256',
         'source-archive','source-archive-sha256','stage0-campaign','stage0-campaign-sha256',
         'stage0-root-closure','stage0-root-closure-sha256','stage0-exec-session',
         'previous-campaign','previous-campaign-sha256','previous-root-closure','previous-root-closure-sha256']), 'actual_dynamic_Stage0_bindings_required')
    actual_stage0_session=session(args.stage0_exec_session)
    need(sys.flags.optimize==0 and not OUTPUT.exists(),'new_unoptimized_pair_required_no_resume')
    start_unix,start_mono,unix,deadline,attempt_unix,attempt_mono,failed_reference=inherited_clock(args)
    OUTPUT.mkdir()
    import psutil
    state=dict(status='starting',qualification='PENDING',start_unix=start_unix,start_monotonic=start_mono,
        common_deadline_monotonic=deadline,absolute_deadline_unix=unix,common_seconds=COMMON,
        attempt_start_unix=attempt_unix,attempt_start_monotonic=attempt_mono,
        original_failed_attempt=failed_reference,
        allocations=dict(setup=SETUP,A_regression=900,B_regression=900,A_classification=3600,B_classification=3600,
                         independent_pair_audit=AUDIT,final_cleanup=CLEANUP),
        owned_root=dict(pid=os.getpid(),create_time=psutil.Process().create_time()),
        coordinator_bootstrap_identities=[],supervisors=[],active_supervisor=None,arms=[],
        slot_matrix={a+c:dict(arm=a,kind=k,code=c,status='not_attempted',quality_metric=None) for a,k,c in ORDER},
        cleanup_confirmed=False,source_unchanged=False,pair_artifact_checks_passed=False,
        independent_audit=None,descriptive_retention_win=None,error_history=[],quality_metric=None,
        root_actual_exec_qualification='pending_root_observed_actual_exec_and_fresh_closure',
        root_confirmation_required_before_unix=unix,promotion=False,submit=False,official_score=None,
        official_default_ready=False,scope='LA2 recovery under original LA1 clock; original LA1 FAIL preserved. Equal-budget whole-agent L1 admission A/B; adaptive reused public, not blind/private or default-release qualification')
    pins,deployment,known,finished={},{},set(),set()
    coor=owner=processes=awake=None;final_end=None
    auditor='loss-seed-whole-agent-ab-r2-next-dev/audit_pair.py'
    closer='loss-seed-whole-agent-ab-r2-next-dev/close_pair.py'
    manifest_path,plan_path=OUTPUT/'manifest.json',OUTPUT/'verification-plan.json'
    def persist():
        data = {k: v for k, v in state.items() if not k.startswith('_')}
        if coor is None:
            with (OUTPUT/'campaign.json').open('x', encoding='utf-8') as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        else:
            coor.save(OUTPUT/'campaign.json', data)
    def error(exc, phase):
        code = str(exc) if isinstance(exc, RuntimeError) and re.fullmatch('[A-Za-z0-9_:+.-]{1,200}', str(exc)) else 'pair_'+type(exc).__name__
        entry = dict(code=code, phase=phase, unix=time.time(), monotonic=time.monotonic(),
            exception_type=type(exc).__name__, errno=getattr(exc, 'errno', None), winerror=getattr(exc, 'winerror', None))
        state.setdefault('first_failure', entry)
        state['error_history'].append(entry)
        state.update(status='technical_failure', qualification='FAIL', pair_artifact_checks_passed=False,
            descriptive_retention_win=None, quality_metric=None)
        active=state.get('active_arm')
        if active in state.get('slot_matrix',{}):
            state['slot_matrix'][active].update(status='technical_failure',quality_metric=None,failure_ref='campaign.first_failure')
        if isinstance(state.get('independent_audit'),dict):
            state['independent_audit'].update(explicitly_unqualified=True,qualified_result=None)
    def checkpoint(parent_end=None, code='pair_parent_cap_exhausted'):
        if awake is not None and awake.handle is not None:
            coor.cooperative_checkpoint(awake, deadline, unix, parent_end, code)
        else:
            need(time.monotonic() < deadline and time.time() < unix, 'pair_common_clock_exhausted')
            need(abs((deadline-time.monotonic())-(unix-time.time())) <= 5, 'wall_monotonic_clock_disagreement')
            if parent_end is not None:
                need(time.monotonic() < parent_end, code)
        rss = psutil.Process().memory_info().rss
        for saved in state['coordinator_bootstrap_identities']:
            try:
                proc = psutil.Process(saved['pid'])
                if proc.create_time() == saved['create_time']:
                    rss += proc.memory_info().rss
            except psutil.NoSuchProcess:
                pass
        need(rss <= 2*2**30, 'pair_parent_bootstrap_memory_limit')
    def frozen(parent_end=None, code='pair_parent_cap_exhausted'):
        check = lambda: checkpoint(parent_end, code)
        check()
        for name, digest in {**pins, **deployment}.items():
            need(sha(local(name), check) == digest, 'pair_frozen_source_input_or_seal_changed')
        check()
    def absence():
        history = coor.predecessor(owner, finished, base.get('extra_predecessor_receipts', []),
                                   base['terminal_predecessor_receipts'])
        known.update(coor.identities(history))
        observer = owner.StrictOwnedObserver()
        observer.remember(known | finished)
        need(not observer.observe() and not observer.denials and not observer.final_check()['unresolved'],
             'pair_closed_predecessor_or_prior_child_live_or_denied')
        state['fresh_predecessor_identity_count'] = len(observer.seen)
    try:
        setup_end=start_mono+SETUP
        check=lambda:checkpoint(setup_end,'pair_setup_cap_exhausted')
        explicit={BASE:BASE_SHA,COORDINATOR:COORDINATOR_SHA,R4:R4_SHA,CHAMPION:CHAMPION_SHA,
            LINEAGE:LINEAGE_SHA,SEED:SEED_SHA,auditor:args.auditor_sha256,closer:args.closer_sha256,
            Path(__file__).resolve().relative_to(WORK).as_posix():args.self_sha256,
            args.prepared_manifest:args.prepared_manifest_sha256,args.source_archive:args.source_archive_sha256,
            args.stage0_campaign:args.stage0_campaign_sha256,
            PREVIOUS_CAMPAIGN[0]:PREVIOUS_CAMPAIGN[1],PREVIOUS_ROOT[0]:PREVIOUS_ROOT[1]}
        for name,digest in explicit.items():
            need(sha(local(name),check)==digest,'pair_explicit_source_binding_failed');merge(pins,name,digest)
        need(bool(args.bootstrap_launcher)==bool(args.bootstrap_launcher_sha256),'paired_bootstrap_path_SHA_required')
        if args.bootstrap_launcher:
            need(sha(local(args.bootstrap_launcher),check)==args.bootstrap_launcher_sha256,'bootstrap_pin_failed')
            merge(pins,args.bootstrap_launcher,args.bootstrap_launcher_sha256)
        coor=imported('_L1_pair_proven_coordinator',local(COORDINATOR));FAILURE_TYPE=coor.TechnicalFailure
        base,prepared,lineage=load(local(BASE)),load(local(args.prepared_manifest)),load(local(LINEAGE))
        need(prepared['base_manifest_sha256']=='319d6035162f46e6a1272a833d5f8668c731294b443eeae2dd8fc8c897dabfdc'
             and prepared['overlay_handoff_sha256']==OVERLAY_HANDOFF
             and prepared['source_expected_checks']==499 and sum(prepared['registry'].values())==499
             and prepared['source_skipped_expected']==0 and len(prepared['registry'])==51
             and prepared['exact_repeated_expected_checks']==23 and prepared['exact_flat_combined_checks']==28
             and prepared['changed_flat_modules']==['automl_runner.py','automl_search_stages.py'],
             'actual_reviewed_L1_Stage0_prepared_source_required')
        need(prepared['archive']==args.source_archive and prepared['archive_sha256']==args.source_archive_sha256,
             'same_actual_L1_archive_must_be_used_by_all_four_slots')
        for name,digest in base['immutable_files'].items():merge(pins,name,digest)
        for name,digest in prepared['source_files_sha256'].items():merge(pins,prepared['source_root']+'/'+name,digest)
        compiled=prepared['compiled_sha256'];need(len(compiled)==68,'flat68_required')
        with zipfile.ZipFile(local(args.source_archive)) as archive:
            need(len(archive.namelist())==len(set(archive.namelist()))==68 and set(archive.namelist())==set(compiled),
                 'pair_archive_inventory_changed')
            need(all(Path(n).name==n and (n.endswith('.py') or n=='requirements.txt')
                     and hashlib.sha256(archive.read(n)).hexdigest()==h for n,h in compiled.items()),'pair_flat_archive_member_changed')
        need(compiled['requirements.txt']=='9173b0388532fbd2a709e4f4b3029e3b9ccab685fce43a85261ffa1ba95efbe6','original_requirements_required')
        for name in [*coor.LIBS.values(),coor.AWAKE]:need(name in pins,'pair_runtime_dependency_unbound')
        frozen(setup_end,'pair_setup_cap_exhausted')
        owner=imported('_L1_pair_owner',local(coor.LIBS['owner']))
        processes=imported('_L1_pair_processes',local(coor.LIBS['processes']))
        locker=imported('_L1_pair_lock',local(coor.LIBS['lock']))
        awake=imported('_L1_pair_awake',local(coor.AWAKE)).PowerRequestGuard('Alfa L1 paired agent pid'+str(os.getpid()),10)
        parent=psutil.Process().parent();own_paths={Path(__file__).resolve()}
        if args.bootstrap_launcher:own_paths.add(local(args.bootstrap_launcher))
        while parent is not None:
            birth=parent.create_time()
            if not any(Path(v).resolve() in own_paths for v in parent.cmdline() if not v.startswith('-')):break
            need(parent.create_time()==birth,'pair_bootstrap_identity_changed')
            state['coordinator_bootstrap_identities'].append(dict(pid=parent.pid,create_time=birth));parent=parent.parent()
        refs=[(args.stage0_root_closure,args.stage0_root_closure_sha256,actual_stage0_session,0),
              (PREVIOUS_ROOT[0],PREVIOUS_ROOT[1],25252,1)]
        refs += [(n,h,s,e) for n,(h,s,e) in RETAINED_TERMINAL.items()]
        for value in args.extra_terminal_receipt:
            n,h=value.rsplit('=',1);refs.append((n,h,'saved',None))
        for index,(name,digest,sess,exitcode) in enumerate(refs):
            need(sha(local(name),check)==digest,'pair_terminal_closure_pin_failed');proof=load(local(name))
            need(proof.get('cleanup_confirmed') is True and proof.get('source_unchanged') is True
                 and proof.get('active_owned_processes',[])==[] and proof.get('uncertain_owned',[])==[]
                 and proof.get('owned_identities') and proof.get('closure_preparer_identities'), 'complete_terminal_closure_required')
            if sess!='saved':
                need(proof.get('actual_exec_session')==sess and proof.get('actual_exec_exit_code_observed_by_root')==exitcode,
                     'actual_predecessor_exec_lineage_changed')
            if index==0:
                stage0_proof=proof
                need(proof.get('technical_procedure_passed') is True and proof.get('source_checks')==499
                     and proof.get('source_skipped')==0 and proof.get('exact_default_repeated')==23
                     and proof.get('exact_flat_same_LOSS_contracts')==16 and proof.get('exact_flat_seed_contracts')==12
                     and proof.get('exact_flat_combined_contracts')==28 and proof.get('prepared_manifest_sha256')==args.prepared_manifest_sha256
                     and proof.get('original_common_seconds')==900 and 0<=proof['raw_parent_elapsed_seconds']<900,
                     'actual_L1_Stage0_success_required')
            known.update(coor.identities(proof['owned_identities']));known.update(coor.identities(proof['closure_preparer_identities']))
            merge(pins,name,digest)
        stage0=load(local(args.stage0_campaign))
        need(stage0.get('technical_checks_passed') is True and stage0.get('cleanup_confirmed') is True
             and stage0.get('source_unchanged') is True and not stage0.get('error_history')
             and stage0['prepared_manifest_sha256']==args.prepared_manifest_sha256
             and stage0['start_unix']==stage0_proof['original_start_unix']
             and stage0['absolute_deadline_unix']==stage0_proof['original_deadline_unix']
             and stage0['start_unix']<=stage0['finished_unix']<stage0['absolute_deadline_unix']
             and math.isclose(stage0['elapsed_common_seconds'],stage0_proof['raw_parent_elapsed_seconds'],rel_tol=0,abs_tol=.01),
             'actual_Stage0_manifest_clock_lineage_required')
        gate_counts={g['name']:g['checks'] for g in stage0['gates'] if g.get('passed') is True}
        need(gate_counts=={'source':499,'exact-default':23,'exact-optin':28},'complete_actual_Stage0_gate_counts_required')
        for name,digest in stage0['immutable_files'].items():merge(pins,name,digest)
        # Required terminal maps are explicit; historical FAIL is retained, never a positive-ML prerequisite.
        for ref in stage0.get('terminal_predecessor_receipts',[]):
            need(sha(local(ref['path']),check)==ref['sha256'],'Stage0_predecessor_ref_changed')
            proof=load(local(ref['path']))
            need(proof['cleanup_confirmed'] is True and proof['source_unchanged'] is True,'Stage0_predecessor_not_closed')
            known.update(coor.identities(proof['owned_identities']));known.update(coor.identities(proof['closure_preparer_identities']))
            merge(pins,ref['path'],ref['sha256'])
        for ref in stage0['supervisors']:
            need(sha(local(ref['path']),check)==ref['sha256'],'Stage0_supervisor_changed');terminal=load(local(ref['path']))
            need(terminal.get('status')=='ok' and terminal.get('exit_code')==0 and terminal.get('cleanup_confirmed') is True,'Stage0_child_not_clean')
            need(coor.identities(terminal['owned_process_identities'])<=known,'Stage0_child_missing_from_closure')
            merge(pins,ref['path'],ref['sha256'])
        tasks=copy.deepcopy(base['tasks']);need({t['kind'] for t in tasks}==set(CAPS) and len(tasks)==2,'two_frozen_tasks_required')
        reg=next(t for t in tasks if t['kind']=='regression');need(reg['files']==lineage['raw_task_input_sha256'],'same_five_regression_inputs_required')
        arms={a:dict(archive=args.source_archive,archive_sha256=args.source_archive_sha256,compiled_sha256=compiled,
                     source_root=prepared['source_root'],tasks=tasks) for a in ['A','B']}
        slots={a+c:dict(arm=a,kind=k,code=c,argv=solver_argv(a,k),caps=CAPS[k]) for a,k,c in ORDER}
        manifest=dict(schema='L1-whole-agent-pair-v1',output_root='la2',original_failed_attempt=failed_reference,immutable_files=pins,arms=arms,tasks=tasks,slots=slots,
            archive=args.source_archive,archive_sha256=args.source_archive_sha256,compiled_sha256=compiled,
            common_seconds=COMMON,caps=CAPS,order=[a+c for a,k,c in ORDER],maximum_experiments=9,hpo_trials=8,
            champion=dict(path=CHAMPION,sha256=CHAMPION_SHA,signature=CHAMPION_SIGNATURE),
            fixed_L1=dict(path=SEED,sha256=SEED_SHA,signature=SEED_SIGNATURE),
            prepared_manifest=dict(path=args.prepared_manifest,sha256=args.prepared_manifest_sha256),
            stage0_root_closure=dict(path=args.stage0_root_closure,sha256=args.stage0_root_closure_sha256),
            max_planner_calls=2,gateway_call_limit=4,threads=2,worker_memory_GiB=1.5,whole_tree_memory_GiB=2,
            interpreter_path=sys.executable,interpreter_sha256=sha(sys.executable,check),interpreter_version=sys.version,
            requested_model=base['requested_model'],reasoning_effort=base['reasoning_effort'],official_default_ready=False)
        plan=copy.deepcopy(base['verification_plan_template'])
        plan.update(verifier_source_sha256=args.auditor_sha256,manual_metric_verifier_path=R4,manual_metric_verifier_sha256=R4_SHA,
            original_common_start_unix=start_unix,original_absolute_deadline_unix=unix,common_seconds=COMMON,
            original_failed_attempt=failed_reference,
            hpo_requested_budget_seconds={k:v['hpo'] for k,v in CAPS.items()},
            expected_regression_splits=copy.deepcopy(lineage['split_fingerprints']),T5_cut_floors=copy.deepcopy(lineage['selected_independently_verified_metrics']),
            reproduction_absolute_tolerance=1e-9,expected_champion_signature=CHAMPION_SIGNATURE,
            expected_champion_input_sha256=CHAMPION_SHA,expected_loss_seed_signature=SEED_SIGNATURE,
            pair_order=[a+c for a,k,c in ORDER],official_default_ready=False)
        state.update(_manifest=base,_pulse=lambda:checkpoint(),awake_guard=awake.record,
            stage0_root_closure=dict(path=args.stage0_root_closure,sha256=args.stage0_root_closure_sha256))
        with awake:
            absence();frozen(setup_end,'pair_setup_cap_exhausted')
            with locker.ResearchLock(WORK/'alfa-hack-automl/test-runs/.owned-research.lock') as lock:
                lock.write_identity(state['owned_root']);absence();frozen(setup_end,'pair_setup_cap_exhausted')
                coor.save(manifest_path,manifest,True);state['manifest_sha256']=sha(manifest_path,check)
                plan['execution_manifest_sha256']=state['manifest_sha256'];coor.save(plan_path,plan,True)
                deployment[coor.relative(manifest_path)]=state['manifest_sha256']
                deployment[coor.relative(plan_path)]=sha(plan_path,check)
                state['verification_plan_sha256']=deployment[coor.relative(plan_path)]
                checkpoint(setup_end,'pair_setup_cap_exhausted');state['setup_seconds']=time.monotonic()-start_mono
                previous={}
                def interrupted(signum,frame):raise SystemExit(128+signum)
                for sig in [signal.SIGINT,signal.SIGTERM]:previous[sig]=signal.signal(sig,interrupted)
                persist()
                try:
                    for index,(arm,kind,code) in enumerate(ORDER):
                        key=arm+code;cfg=CAPS[kind];tick=time.monotonic()
                        future=sum(CAPS[k]['parent'] for a,k,c in ORDER[index+1:])+AUDIT+CLEANUP
                        need(deadline-tick>=cfg['parent']+future,'full_fixed_remaining_allocations_unavailable')
                        absence();frozen(tick+cfg['parent'],'task_materialization_over_parent_cap')
                        (OUTPUT/arm).mkdir(exist_ok=True);directory=OUTPUT/arm/code
                        task=next(t for t in tasks if t['kind']==kind)
                        coor.materialize(task,directory,{**arms[arm],'immutable_files':pins},deployment)
                        if kind=='regression':
                            target=directory/'champion_recipe_input.json';target.write_bytes(local(CHAMPION).read_bytes())
                            need(sha(target)==CHAMPION_SHA,'champion_deployment_changed');deployment[coor.relative(target)]=CHAMPION_SHA
                        argv=list(slots[key]['argv']);state.update(status='running',active_arm=key)
                        state.setdefault('actual_arm_argv',{})[key]=argv
                        state['slot_matrix'][key].update(status='admitted',admitted_monotonic=tick,quality_metric=None);persist()
                        sup=coor.supervise(argv,directory,directory/'supervisor.json',kind+'-'+arm,
                            tick,cfg['parent'],cfg['child'],deadline,unix,cfg['parent']+future,
                            state,persist,frozen,owner,processes,state['coordinator_bootstrap_identities'],cfg['solver'],cfg['hpo'])
                        coor.child_errors(state,sup);finished.update(coor.identities(sup.get('owned_process_identities',[])))
                        need(sup.get('cleanup_confirmed') is True and sup.get('status') in {'ok','child_failed'},'arm_systemic_or_ownership_failure')
                        arm_check=lambda:checkpoint(tick+cfg['parent'],'arm_metadata_seal_over_cap')
                        frozen(tick+cfg['parent'],'arm_metadata_seal_over_cap')
                        proof=coor.task_proof(directory,arm_check);core=coor.core_seal(directory,arm_check)
                        seal_path=OUTPUT/(key+'-seal.json')
                        coor.save(seal_path,dict(slot=key,arm=arm,kind=kind,files_sha256=core,cleanup_confirmed=True,
                            source_unchanged=True,sealed_before_independent_label_scoring=True),True)
                        seal_sha=sha(seal_path,arm_check);deployment[coor.relative(seal_path)]=seal_sha;deployment.update(core)
                        entry=dict(sup,slot=key,arm=arm,kind=kind,code=code,proof=proof,
                            supervisor_path=coor.relative(directory/'supervisor.json'),supervisor_sha256=sha(directory/'supervisor.json',arm_check),
                            seal=dict(path=coor.relative(seal_path),sha256=seal_sha),task_allocation_seconds=cfg['parent'],
                            qualified=False,measurement_status='pending_independent_saved_artifact_audit')
                        state['arms'].append(entry);state['slot_matrix'][key].update(status='sealed',quality_metric=None)
                        state['active_arm']=None;persist();arm_check()
                    tick=time.monotonic();need(deadline-tick>=AUDIT+CLEANUP,'audit_cleanup_reserve_unavailable')
                    absence();frozen();state.update(status='verifying',cleanup_confirmed=True,source_unchanged=True);persist()
                    audit_argv=[sys.executable,'-B','-X','utf8',str(local(auditor)),
                        '--work-root',str(WORK),'--pair-root','la2','--manifest','la2/manifest.json',
                        '--manifest-sha256',state['manifest_sha256'],'--plan','la2/verification-plan.json',
                        '--plan-sha256',state['verification_plan_sha256'],'--self-sha256',args.auditor_sha256,
                        '--output','la2/independent-audit.json']
                    sup=coor.supervise(audit_argv,WORK,OUTPUT/'audit-supervisor.json','pair-audit',tick,AUDIT,AUDIT-30,
                        deadline,unix,AUDIT+CLEANUP,state,persist,frozen,owner,processes,state['coordinator_bootstrap_identities'])
                    coor.child_errors(state,sup);finished.update(coor.identities(sup.get('owned_process_identities',[])))
                    need(sup.get('status')=='ok' and sup.get('exit_code')==0 and sup.get('cleanup_confirmed') is True,'independent_auditor_process_failed')
                    audit_path=OUTPUT/'independent-audit.json';audit=load(audit_path)
                    state['independent_audit']=dict(path=coor.relative(audit_path),sha256=sha(audit_path),raw_result=audit,
                                                  qualification='pending_terminal_gates')
                    need(audit.get('artifact_procedure_checks_passed') is True and audit.get('audit_within_original_common_clock') is True
                         and audit.get('parent_exec_terminal_qualification_required') is True,'independent_artifact_contract_failed')
                    state.update(status='completed_pair_pending_root_exec_and_closure',qualification='PENDING_ROOT',
                        pair_artifact_checks_passed=True,descriptive_retention_win=audit.get('descriptive_retention_win'))
                except BaseException as exc:
                    error(exc, 'pair_procedure')
                finally:
                    final_end = min(time.monotonic()+CLEANUP, deadline-10)
                    state['finalization_deadline_monotonic'] = final_end
                    try:
                        frozen(final_end, 'pair_final_cleanup_cap_exhausted')
                        absence()
                        need(all(r['cleanup_confirmed'] is True for r in state['supervisors']), 'pair_child_cleanup_unknown')
                        state.update(cleanup_confirmed=True, source_unchanged=True)
                        checkpoint(final_end)
                        persist()
                    except BaseException as exc:
                        error(exc, 'pair_terminal_source_cleanup')
                        state.update(cleanup_confirmed=False, source_unchanged=False)
                    finally:
                        for sig, handler in previous.items():
                            signal.signal(sig, handler)
        need(awake.record.get('release_API_verified') is True, 'pair_power_release_unverified')
        last = awake.record['last_heartbeat']
        checkpoint(final_end, 'pair_terminal_export_cap_exhausted')
        need(max(time.time()-last['unix'], time.monotonic()-last['monotonic']) <= 10,
             'pair_terminal_heartbeat_gap_over10s')
        absence()
    except BaseException as exc:
        error(exc, 'pair_parent')
        state.update(cleanup_confirmed=False, source_unchanged=False)
    finally:
        if awake is not None:
            state['awake_guard'] = awake.record
            if awake.handle is not None:
                try:
                    awake.close()
                except BaseException as exc:
                    error(exc, 'pair_power_release')
        state.update(finished_unix=time.time(), finished_monotonic=time.monotonic(),
            elapsed_common_seconds=time.monotonic()-start_mono,
            owned_process_identities=[dict(pid=pid, create_time=birth) for pid, birth in sorted(finished)])
        if time.monotonic() >= min(deadline-10, final_end if final_end is not None else deadline) or time.time() >= unix-10:
            error(RuntimeError('pair_terminal_export_over_cap'), 'pair_terminal_export')
        persist()
        if time.monotonic() >= min(deadline-10, final_end if final_end is not None else deadline):
            error(RuntimeError('pair_terminal_receipt_write_over_cap'), 'pair_terminal_export')
            persist()
    print(json.dumps({k: state[k] for k in ['status', 'qualification', 'pair_artifact_checks_passed',
        'cleanup_confirmed', 'source_unchanged', 'elapsed_common_seconds', 'root_actual_exec_qualification']}))
    raise SystemExit(0 if state['pair_artifact_checks_passed'] and state['cleanup_confirmed']
                     and state['source_unchanged'] and not state['error_history'] else 1)


if __name__ == '__main__':
    main()
