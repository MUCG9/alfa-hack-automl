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

WORK = Path(__file__).resolve().parents[2]
DIRECTORY = WORK/'uq3-cadence-hpo-next-dev/candidate'
BASE_URL = 'https://changellenge.up.railway.app/v1'
RESERVED = {'--launch','--self-sha256','--auditor-sha256','--closer-sha256',
            '--bootstrap-launcher','--bootstrap-launcher-sha256','--start-unix','--start-monotonic',
            '--absolute-deadline-unix','--common-deadline-monotonic'}


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
    if args.launch:
        start_unix,start_monotonic=time.time(),time.monotonic()
        absolute_deadline_unix,common_deadline_monotonic=start_unix+10800,start_monotonic+10800
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
    need(not (WORK/'uq3').exists(),'new_prospective_output_required_no_resume')
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
