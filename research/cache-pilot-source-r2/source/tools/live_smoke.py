"""Bounded live CLI fixture; secret via private environment or hidden terminal input.

No original data, account balance assumptions, or official submissions. A model
fallback alone is NOT live-gateway success. Run only on a new ignored directory.
"""
from pathlib import Path
import argparse,getpass,hashlib,json,os,signal,subprocess,sys,time,zipfile
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src')); sys.path.insert(0,str(ROOT/'tools'))
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.processes import wait_owned
from build_submission import build_files


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--prompt-key',action='store_true')
    parser.add_argument('--time-budget',type=int,default=240)
    parser.add_argument('--endpoint',default='https://changellenge.up.railway.app/v1')
    parser.add_argument('--model',default='qwen/qwen3.8-27b')
    parser.add_argument('--hpo-trials',type=int,default=0)
    parser.add_argument('--selection-top-k',type=int,default=0)
    parser.add_argument('--planner-mode',choices=['baseline','staged'],default='baseline')
    parser.add_argument('--four-stage',action='store_true')
    args=parser.parse_args()
    if args.four_stage:
        args.hpo_trials=args.hpo_trials or 4
        args.selection_top_k=args.selection_top_k or 1
        args.planner_mode='staged'
    if not 180<=args.time_budget<=600: raise ValueError('Use a180..600s fixture budget')
    if not 0<=args.hpo_trials<=8 or not 0<=args.selection_top_k<=2: raise ValueError('Invalid fixture MVP options')
    endpoint=urlsplit(args.endpoint)
    local_mock=endpoint.hostname in {'127.0.0.1','localhost','::1'}
    if endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
        raise ValueError('Endpoint must not contain credentials, query or fragment')
    if not local_mock and args.endpoint.rstrip('/')!='https://changellenge.up.railway.app/v1':
        raise ValueError('Only the authorized organizer endpoint or a local mock is supported')
    out=args.output.resolve(); out.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy()
    if args.prompt_key:
        key=getpass.getpass('Qwen API key (hidden): ').strip()
        if not key: raise ValueError('No key entered')
        env['OPENAI_API_KEY']=key
    elif not env.get('OPENAI_API_KEY'):
        raise ValueError('Use a private API environment or --prompt-key; never argv')
    if local_mock and env['OPENAI_API_KEY']!='fixture-http-only':
        raise ValueError('Local mock accepts only the fixed non-secret fixture credential')
    env.update(OPENAI_BASE_URL=args.endpoint,OPENAI_MODEL=args.model,AUTOML_THREADS='1',
               OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    for name in ['tmp','mpl']: (out/name).mkdir()
    env.update(TMPDIR=str(out/'tmp'),MPLCONFIGDIR=str(out/'mpl'))
    with zipfile.ZipFile(args.archive) as packed:
        files={n:packed.read(n) for n in packed.namelist()}
    if files!=build_files(): raise ValueError('Fixture archive differs from current source')
    for name,data in files.items(): (out/name).write_bytes(data)
    import numpy as np
    import pandas as pd
    x=np.linspace(-2,2,180)
    train=pd.DataFrame({'record':range(len(x)),'measure':x,'category':np.where(x>0,'a','b'),
                        'answer':3*x+np.sin(x)})
    test=pd.DataFrame({'record':range(500,508),'measure':np.linspace(-1.7,1.7,8),
                       'category':['b']*4+['a']*4})
    sample=pd.DataFrame({'record':test.record.iloc[::-1].to_numpy(),'answer':0.})
    dictionary=pd.DataFrame({'feature':train.columns,'role':['id','feature','feature','target']})
    for frame,name in zip([train,test,sample,dictionary],['alpha.csv','beta.csv','gamma.csv','delta.csv']):
        frame.to_csv(out/name,index=False)
    (out/'task.md').write_text('Regression. Primary metric RMSE. alpha.csv is the fitting data; '
        'predict answers for beta.csv. gamma.csv is the required output format, including row order. '
        'delta.csv describes column roles. All rows are an artificial developer fixture, not public/private competition data.')
    initial={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ['task.md','alpha.csv','beta.csv','gamma.csv','delta.csv']}
    command=[sys.executable,'-u','solution.py','task.md','--max-experiments','10' if args.hpo_trials else '7',
             '--max-planner-calls','1','--time-budget',str(args.time_budget),
             '--hpo-trials',str(args.hpo_trials),'--hpo-budget','60',
             '--feature-selection-top-k',str(args.selection_top_k),'--planner-mode',args.planner_mode]
    if args.four_stage: command.append('--four-stage')
    started=time.monotonic()
    def interrupted(signum,frame): raise SystemExit(128+signum)
    previous=signal.signal(signal.SIGTERM,interrupted)
    try:
        with (out/'process.log').open('w') as stream:
            process=subprocess.Popen(command,cwd=out,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            try: status=wait_owned(process,args.time_budget+45,memory_bytes=int(.75*2**30))
            except subprocess.TimeoutExpired: status='watchdog_timeout'
            except MemoryError: status='memory_limit'
    finally: signal.signal(signal.SIGTERM,previous)
    report_path=out/'automl_runs/run-v2/report.json'
    report=json.loads(report_path.read_text()) if report_path.exists() else {}
    traces=list((out/'automl_runs').glob('task-contract-*/file-roles.json'))
    mappings=[json.loads(p.read_text()) for p in traces]
    semantic_calls=[a['call'] for m in mappings for a in m['attempts']]
    planner_calls=report.get('llm_calls',[])
    semantic_ok=any(m.get('validated') and any(a['call']['status']=='ok' for a in m['attempts']) for m in mappings)
    planner_ok=any(c['status']=='ok' for c in planner_calls)
    hpo=report.get('hpo') or {}
    selection_active=any(p.get('feature_selection',{}).get('status')=='selected'
        for r in report.get('experiments',[]) for p in r.get('data_policy_runs',[]))
    output_ok=False
    if (out/'submission.csv').exists():
        prediction=pd.read_csv(out/'submission.csv')
        output_ok=(list(prediction)==list(sample) and len(prediction)==len(sample)
                   and prediction.record.tolist()==sample.record.tolist() and np.isfinite(prediction.answer).all())
    unchanged=initial=={n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in initial}
    # Whitelist status/usage only; never include credential-bearing env or argv.
    keep={'status','usage','usage_complete','attempts','wall_seconds','finish_reason','compatibility_retry','exception_type','status_code'}
    calls=[{k:v for k,v in c.items() if k in keep} for c in semantic_calls+planner_calls]
    summary={'archive_sha256':hashlib.sha256(args.archive.read_bytes()).hexdigest(),
             'exit_code':status,'elapsed_seconds':round(time.monotonic()-started,3),
             'provider_scope':'local_mock_http' if local_mock else 'organizer_api',
             'semantic_http_ok':semantic_ok,'planner_http_ok':planner_ok,
             'semantic_live_ok':semantic_ok and not local_mock,'planner_live_ok':planner_ok and not local_mock,'calls':calls,
             'output_contract_ok':bool(output_ok),'inputs_unchanged':unchanged,
             'final_fit_status':report.get('final_fit_status'),'integrity_ok':report.get('integrity_ok'),
             'hpo_status':hpo.get('status'),'hpo_completed_trials':hpo.get('completed_trials'),
             'feature_selection_active':selection_active,'planner_mode':args.planner_mode,
             'four_stage_pipeline':report.get('pipeline'),
             'scope':'Artificial180-row regression fixture; local_mock_http is NOT live Qwen proof. No ML quality or official score claim.',
             'passed':bool(status==0 and semantic_ok and planner_ok and output_ok and unchanged and report.get('final_fit_status')=='ok' and report.get('integrity_ok')
                           and (not args.hpo_trials or hpo.get('status')=='ok') and (not args.selection_top_k or selection_active)
                           and (not args.four_stage or (report.get('pipeline',{}).get('mode')=='four_stage' and report['pipeline'].get('initial_data_assessment_before_fitting'))))}
    # Do not echo any artifacts if an upstream error unexpectedly included the key.
    credential=env['OPENAI_API_KEY'].encode()
    for path in out.rglob('*'):
        if path.is_file() and path.suffix in {'.json','.log','.py'}:
            content=path.read_bytes()
            if credential in content:
                path.write_bytes(content.replace(credential,b'[REDACTED]'))
                summary['credential_redaction_required']=True; summary['passed']=False
    atomic_json(out/'live-summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    if not summary['passed']: raise SystemExit(1)


if __name__=='__main__': main()
