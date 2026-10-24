"""Same-process provider bootstrap for one prospective UAR Qwen pair.
Inspection/preflight creates no experiment clock. Actual --launch assigns ONE original10800 origin before publication/provider setup; API calls occur only inside the coordinator.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import os
import re
import runpy
import subprocess
import sys
import time

WORK = Path(__file__).resolve().parents[1]
DIRECTORY = WORK/'uar-qwen-pair-bootstrap-repair-next-dev'
BASE_URL = 'https://changellenge.up.railway.app/v1'
RESERVED = {'--launch','--self-sha256','--auditor-sha256','--closer-sha256',
            '--bootstrap-launcher','--bootstrap-launcher-sha256','--start-unix','--start-monotonic',
            '--absolute-deadline-unix','--common-deadline-monotonic'}


RECOVERY_ORIGIN = (1792826068.8239975, 85073.953, 1792836868.8239975, 95873.953)
FAILED_PINS = {'uq1/campaign.json': '365dc8f0cccab4091193d75ddcbf1819c3d1a762e29113a66dac58878275bd04', 'uq1/terminal-root-closure.json': 'c880e6625dfa1a52af9aab9847adbb9c1c519493e3e3d678d591237266bded15', 'uq1/root-preparer-identity.json': 'c8da7c953f6f3dfa536fb4a192a8333e9c2753d55a4d6d1315f5c60248f5d399', 'uq1-current-known-observation-r1.json': 'ff874842f05dcf2ffb1426d346d43e99a7a3f7ac5902a3eed285eec22cc2d817', 'uar-qwen-pair-composite-next-dev/source-handoff-r3.json': 'b5a11bb65f87aaab8c15f6b8af8aa5750848312cb1bf1c20f01e81af2c3c1617', 'uar-qwen-pair-composite-next-dev/binding.ready-root-r1.json': 'fa8df18b80d49930bf7cace3faff2f3863d41d538fb64c2f31aa5a96b966f3ce'}

def need(value, code):
    if not value:
        raise RuntimeError(code)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def provider_environment():
    # Runtime-only read; values never enter argv, receipts or error output.
    cfg = json.loads((WORK/'private/qwen.json').read_text('utf-8'))
    need(isinstance(cfg,dict),'authorized_private_environment_unavailable')
    key = next((cfg[n] for n in ['api_key','key','token','OPENAI_API_KEY'] if cfg.get(n)),None)
    base = next((cfg[n] for n in ['base_url','api_base','OPENAI_BASE_URL'] if cfg.get(n)),BASE_URL)
    need(isinstance(key,str) and bool(key) and isinstance(base,str)
         and base.rstrip('/') == BASE_URL,'authorized_private_environment_unavailable')
    os.environ.update(OPENAI_API_KEY=key,OPENAI_BASE_URL=base,
        OPENAI_MODEL='qwen/qwen3.8-27b',AUTOML_REASONING_EFFORT='off',
        PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',
        MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
    del cfg,key


def preflight_metadata(name, ready):
    import psutil
    target = (WORK/name).resolve()
    need(not Path(name).is_absolute() and target.is_relative_to(WORK)
         and target.parent.is_dir() and not target.exists(),'exclusive_work_metadata_path_required')
    me = psutil.Process()
    identities = [{'pid':me.pid,'create_time':me.create_time()}]
    parent = me.parent()
    while parent is not None:
        birth = parent.create_time()
        if not any(Path(v).resolve()==Path(__file__).resolve()
                   for v in parent.cmdline() if not v.startswith('-')):
            break
        need(parent.create_time()==birth,'preflight_bootstrap_identity_changed')
        identities.append({'pid':parent.pid,'create_time':birth})
        parent = parent.parent()
    record = {'schema':'UAR-Qwen-provider-preflight-v1',
        'authorized_private_environment_ready':ready,'API_calls':0,
        'launcher_sha256':sha(__file__),'preflight_identities':identities,
        'experiment_clock_assigned':False,'private_values_emitted':False}
    with target.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(record,stream,ensure_ascii=False,indent=2)
        stream.write('\n')


def bootstrap_failure():
    """Only the exact pre-API failed bootstrap may consume its remaining clock."""
    docs={}
    for name,expected in FAILED_PINS.items():
        path=(WORK/name).resolve()
        need(path.is_relative_to(WORK) and path.is_file() and path.stat().st_size<=2**21,
             'exact_failed_bootstrap_input_required')
        raw=path.read_bytes();need(hashlib.sha256(raw).hexdigest()==expected,'failed_bootstrap_evidence_changed')
        docs[name]=json.loads(raw.decode('utf-8'))
    c=docs['uq1/campaign.json'];negative=docs['uq1/terminal-root-closure.json']
    current=docs['uq1-current-known-observation-r1.json']
    fields=('start_unix','start_monotonic','absolute_deadline_unix','common_deadline_monotonic')
    need(tuple(c[k] for k in fields)==RECOVERY_ORIGIN and c['common_seconds']==10800
         and c.get('status')=='technical_failure' and c.get('qualification')=='FAIL'
         and c.get('cleanup_confirmed') is False and c.get('source_unchanged') is False
         and c.get('pair_artifact_checks_passed') is False and c.get('independent_audit') is None
         and c.get('arms')==[] and c.get('supervisors')==[] and c.get('active_supervisor') is None
         and c.get('owned_process_identities')==[] and c.get('coordinator_bootstrap_identities')==[]
         and not c.get('actual_arm_argv') and not c.get('manifest_sha256') and not c.get('verification_plan_sha256')
         and set(c['slot_matrix'])=={'Ar','Br','Ac','Bc'}
         and all(v['status']=='not_attempted' and v['quality_metric'] is None for v in c['slot_matrix'].values())
         and len(c['error_history'])==1 and c['first_failure']==c['error_history'][0]
         and c['first_failure']['code']=='conflicting_input_pin' and c['first_failure']['phase']=='pair_parent',
         'only_exact_before_arm_API_manifest_failure_may_recover')
    need(negative.get('technical_procedure_passed') is False
         and negative.get('cleanup_confirmed') is False and negative.get('source_unchanged') is False
         and negative.get('actual_exec_session') is None and negative.get('actual_exec_exit_code_observed_by_root')==1
         and negative.get('actual_tool_evidence')=='94cc24' and negative.get('first_failure')==c['first_failure']
         and negative.get('changed_source_or_core')==['missing-pair-manifest']
         and negative.get('uncertain_owned')==[dict(scope='campaign',reason='saved_cleanup_not_confirmed')]
         and negative.get('active_owned_processes')==[] and negative.get('independent_audit') is None
         and docs['uq1/root-preparer-identity.json']['identities']==negative['closure_preparer_identities'],
         'original_failed_negative_flags_must_be_preserved')
    need(current.get('schema')=='uq1-preAPI-failure-current-observation-v1'
         and current.get('first_campaign_sha256')==FAILED_PINS['uq1/campaign.json']
         and current.get('first_negative_root_sha256')==FAILED_PINS['uq1/terminal-root-closure.json']
         and current.get('first_preparers_sha256')==FAILED_PINS['uq1/root-preparer-identity.json']
         and current.get('prior_root_sha256')=='03b9f83e4a3658e8728375b61bafb697428b772b585064c853726bba90b97615'
         and current.get('driver_actual_exec_session') is None and current.get('driver_actual_exit')==1
         and current.get('driver_actual_tool')=='94cc24' and current.get('negative_closer_actual_exec_session') is None
         and current.get('negative_closer_actual_exit')==1 and current.get('negative_closer_actual_tool')=='615b0e'
         and current.get('first_failure')=='conflicting_input_pin' and current.get('known_count')==6203
         and current.get('known_exact_live')==[] and current.get('uncertain')==[]
         and current.get('observed_arms')==0 and current.get('observed_supervisors')==0
         and current.get('new_model_fits')==0 and current.get('new_API_calls')==0
         and current.get('old_cleanup_false_preserved') is True and current.get('old_source_flag_false_preserved') is True
         and current.get('old_unknown_launcher_bootstrap_identity') is None
         and current.get('retrospective_qualification') is False
         and (current['original_start_unix'],current['original_start_monotonic'],current['original_deadline_unix'],
              current['original_deadline_monotonic'])==RECOVERY_ORIGIN
         and c['finished_unix']<=current['checked_unix']<RECOVERY_ORIGIN[0]+900,
         'actual_current_known_absence_not_old_cleanup_PASS_required')
    ids=current['known_identities']
    need(type(ids) is list and len(ids)==6203 and all(type(v) is dict and set(v)=={'pid','create_time'}
         and type(v['pid']) is int and v['pid']>0 and type(v['create_time']) in (int,float)
         and 0<v['create_time']<float('inf') for v in ids)
         and len({(v['pid'],v['create_time']) for v in ids})==6203
         and all(v in ids for v in negative['owned_identities']+negative['closure_preparer_identities']),
         'exact_known_union_including_old_preparers_required')
    need(not any((WORK/'uq1'/n).exists() for n in ('manifest.json','verification-plan.json','independent-audit.json')),
         'no_recovery_after_manifest_audit_or_partial_work')
    need(RECOVERY_ORIGIN[0]<=time.time()<RECOVERY_ORIGIN[0]+900
         and RECOVERY_ORIGIN[1]<=time.monotonic()<RECOVERY_ORIGIN[1]+900,'original_setup900_exhausted')
    return c,negative,current


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--launch',action='store_true')
    mode.add_argument('--preflight-env',action='store_true')
    for name in ['self-sha256','coordinator-sha256','auditor-sha256','closer-sha256',
                 'r4-adapter-sha256','expected-commit','published-root']:
        parser.add_argument('--'+name)
    parser.add_argument('--metadata-output',help='Exclusive WORK-relative preflight-only JSON path')
    parser.add_argument('coordinator_args',nargs=argparse.REMAINDER,
                        help='Actual coordinator bindings after --; no secrets')
    args = parser.parse_args()
    if args.self_sha256 is not None:
        need(sha(__file__)==args.self_sha256,'launcher_source_changed')
    if args.preflight_env:
        need(not args.coordinator_args,'preflight_has_no_coordinator_arguments')
        ready = False
        try:
            provider_environment()
            ready = True
        except Exception:
            pass
        if args.metadata_output:
            preflight_metadata(args.metadata_output,ready)
        print(json.dumps({'authorized_private_environment_ready':ready,'API_calls':0}))
        return 0 if ready else 1
    failed_campaign,failed_negative,failed_current=bootstrap_failure()
    start_unix,start_monotonic,absolute_deadline_unix,common_deadline_monotonic=RECOVERY_ORIGIN
    need(args.metadata_output is None,'metadata_output_is_preflight_only')
    need(all(getattr(args,n.replace('-','_')) for n in
         ['self-sha256','coordinator-sha256','auditor-sha256','closer-sha256',
          'r4-adapter-sha256','expected-commit','published-root']),'explicit_publication_bindings_required')
    need(all(re.fullmatch('[0-9a-f]{64}',value) for value in
         [args.self_sha256,args.coordinator_sha256,args.auditor_sha256,args.closer_sha256,args.r4_adapter_sha256])
         and re.fullmatch('[0-9a-f]{40}',args.expected_commit),'invalid_source_or_commit_digest')
    prefix = PurePosixPath(args.published_root)
    need(not prefix.is_absolute() and prefix.parts and prefix.parts[0]=='research'
         and '..' not in prefix.parts and '\\' not in args.published_root,
         'published_research_root_required')
    coordinator,auditor,closer = [DIRECTORY/n for n in ['run_pair.py','audit_pair.py','close_pair.py']]
    files = [('run_pair.py',coordinator,args.coordinator_sha256),
             ('audit_pair.py',auditor,args.auditor_sha256),
             ('close_pair.py',closer,args.closer_sha256),
             ('launcher.py',Path(__file__),args.self_sha256),
             ('r4_adapter.py',DIRECTORY/'r4_adapter.py',args.r4_adapter_sha256)]
    need(all(sha(path)==digest for _,path,digest in files),'local_reviewed_source_changed')
    git = ['git','--no-optional-locks','-c','safe.directory='+(WORK/'alfa-hack-automl').as_posix(),
           '-C',str(WORK/'alfa-hack-automl')]
    head = subprocess.check_output(git+['rev-parse','HEAD'],text=True,stderr=subprocess.PIPE,timeout=30).strip()
    need(head==args.expected_commit,'publication_commit_changed')
    for basename,path,digest in files:
        published = subprocess.check_output(git+['show','HEAD:'+prefix.as_posix()+'/'+basename],
                                            stderr=subprocess.PIPE,timeout=30)
        need(hashlib.sha256(published).hexdigest()==digest==sha(path),'published_source_changed')
    passthrough = args.coordinator_args
    if passthrough[:1]==['--']:
        passthrough=passthrough[1:]
    need(bool(passthrough) and not any(v.split('=',1)[0] in RESERVED for v in passthrough),
         'reserved_or_missing_coordinator_arguments')
    need(not (WORK/'uq2').exists(),'new_prospective_output_required_no_resume')
    provider_environment()
    bootstrap = Path(__file__).resolve().relative_to(WORK).as_posix()
    sys.argv = [str(coordinator),'--launch','--self-sha256',args.coordinator_sha256,
        '--auditor-sha256',args.auditor_sha256,'--closer-sha256',args.closer_sha256,
        '--bootstrap-launcher',bootstrap,'--bootstrap-launcher-sha256',args.self_sha256,
        '--start-unix',repr(start_unix),'--start-monotonic',repr(start_monotonic),
        '--absolute-deadline-unix',repr(absolute_deadline_unix),'--common-deadline-monotonic',repr(common_deadline_monotonic),
        *passthrough]
    # No subprocess hop/reset: the exact assigned origin charges all launch setup.
    runpy.run_path(str(coordinator),run_name='__main__')
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:
        if '--preflight-env' in sys.argv:
            print(json.dumps({'authorized_private_environment_ready':False,'API_calls':0}))
        else:
            print(json.dumps({'status':'uar_qwen_same_process_bootstrap_failed',
                'exception_type':type(exc).__name__,'errno':getattr(exc,'errno',None),
                'winerror':getattr(exc,'winerror',None),'private_values_emitted':False}))
        raise SystemExit(1) from None
