"""Run the complete offline suite sequentially with auditable counts and ownership."""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.processes import wait_owned
from build_submission import build_files

CHECKS={'test_v2.py':11,'test_resilience.py':7,'smoke.py':5,
        'test_data_policy.py':11,'test_architecture.py':7,'test_quality.py':18,
        'test_task_metrics.py':8,'test_task_inputs.py':8,
        'test_output_contract.py':6,'test_contract_lifecycle.py':6,'test_validation_contract.py':12,
        'test_multitarget.py':12,'test_ranking.py':13,'test_search_choices.py':8,'test_binary_probability.py':9,
        'test_semantic_inputs.py':16,'test_run_budget.py':14,'test_gateway_http.py':2,
        'test_history.py':13,'test_history_worker.py':8,'test_diversity.py':19,'test_release_verifier.py':3,'test_class_te.py':3,
        'test_feature_views.py':11,'test_postprocessor.py':14,'test_target_smearing.py':14,
        'test_anytime.py':25,'test_anytime_lifecycle.py':4,
        'test_error_analysis_contracts.py':20,'test_error_analysis.py':39,'test_error_preparation.py':16,
        'test_marginal_selection.py':15,'test_local_error_preparation.py':7,'test_marginal_replay.py':3,
        'test_confirmation_readiness.py':11,'test_long_submission.py':5,'test_selector_confirmation.py':6}


def source_hashes():
    return {n:hashlib.sha256(b).hexdigest() for n,b in build_files().items()}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); root=args.output.resolve(); root.mkdir(parents=True,exist_ok=False)
    for name in ['tmp','mpl']: (root/name).mkdir()
    before=source_hashes(); started=time.monotonic(); results=[]
    env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ['KEY','TOKEN','SECRET','AUTH','PASSWORD','PROXY'])}
    env.update(AUTOML_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',
               TMPDIR=str(root/'tmp'),MPLCONFIGDIR=str(root/'mpl'))
    for script,expected in CHECKS.items():
        log=root/(script+'.log'); tick=time.monotonic()
        with log.open('w') as stream:
            process=subprocess.Popen([sys.executable,str(ROOT/'tests'/script)],cwd=ROOT,env=env,
                                     stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            try: status=wait_owned(process,timeout=300,memory_bytes=int(1.2*2**30))
            except subprocess.TimeoutExpired: status='timeout'
            except MemoryError: status='memory_limit'
        content=log.read_text()
        observed=re.findall(r'Ran (\d+) tests? in ',content)
        count=int(observed[-1]) if observed else 5 if script=='smoke.py' and status==0 else None
        passed=status==0 and count==expected
        row={'script':script,'status':status,'passed':passed,'expected_checks':expected,
             'observed_checks':count,'seconds':round(time.monotonic()-tick,3),'log':str(log)}
        results.append(row); print(json.dumps(row),flush=True)
        atomic_json(root/'progress.json',{'checks':results})
    result={'python':sys.version,'source_sha256':before,'source_unchanged':source_hashes()==before,
            'test_script_sha256':{s:hashlib.sha256((ROOT/'tests'/s).read_bytes()).hexdigest() for s in CHECKS},
            'checks':results,'unique_checks_passed':sum(r['observed_checks'] or 0 for r in results if r['passed']),
            'seconds':round(time.monotonic()-started,3),'passed':all(r['passed'] for r in results)}
    result['passed']=result['passed'] and result['source_unchanged']
    atomic_json(root/'results.json',result)
    if not result['passed']: raise SystemExit(1)


if __name__=='__main__': main()
