"""Run the complete offline suite sequentially with auditable counts and ownership."""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess,sys,tempfile,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from automl.infrastructure.atomic import atomic_json
from automl.infrastructure.processes import wait_owned
from build_submission import build_files

CHECKS={'test_v2.py':11,'test_resilience.py':7,'smoke.py':5,
        'test_data_policy.py':11,'test_architecture.py':7,'test_quality.py':18,
        'test_task_metrics.py':8,'test_task_inputs.py':8,
        'test_output_contract.py':6,'test_contract_lifecycle.py':6,'test_validation_contract.py':12,
        'test_multitarget.py':13,'test_ranking.py':13,'test_search_choices.py':8,'test_binary_probability.py':9,
        'test_semantic_inputs.py':16,'test_run_budget.py':15,'test_gateway_http.py':2,
        'test_history.py':13,'test_history_worker.py':8,'test_diversity.py':19,'test_release_verifier.py':3,'test_class_te.py':3,
        'test_feature_views.py':11,'test_postprocessor.py':14,'test_target_smearing.py':14,
        'test_error_analysis_contracts.py':20,'test_error_analysis.py':39,'test_error_preparation.py':16,
        'test_hpo.py':7,'test_feature_selection.py':5,
        'test_resource_portability.py':3,'test_reasoning_settings.py':3,
        'test_planner_isolation.py':1,'test_broad_features.py':8,
        'test_hpo_anchor.py':14,'test_protected_selector_runtime.py':12,
        'test_process_identity.py':9,'test_cleanup_failure.py':11,'test_four_stage.py':16,
        'test_preflight_candidates.py':8,
        'test_owned_research.py':4,'test_protected_selection.py':3,
        'test_feature_dsl.py':4,'test_research_summary.py':4,'test_planner_comparison.py':4}
CHECKS.update({'test_uar_fallback_writer.py':12, 'test_uar_model_routing.py':12,
               'test_uar_process_observation.py':12, 'test_uar_metric_contract.py':12,
               'test_uar_early_output.py':15, 'test_uar_runtime_optin.py':14,
               'test_uar_early_declaration.py':14, 'test_uar_vertical_contract.py':14,
               'test_uar_loss_backend.py':17, 'test_uar_strong_retention.py':15,
               'test_uar_metric_contrast.py':16,
               'test_uar_task_checkpoint_cadence.py':12, 'test_uar_hpo_fair_reserve.py':18})

CHECKS.update({'test_uar_fitting_context_builder.py': 12, 'test_uar_fitting_extractor.py': 16, 'test_uar_fitting_frame.py': 10, 'test_uar_fitting_context_initial.py': 14, 'test_teacher_importance_cache.py': 12, 'test_selector_cache_consumer.py': 4, 'test_uar_fitting_selector_combined.py': 2})

def source_hashes():
    return {n:hashlib.sha256(b).hexdigest() for n,b in build_files().items()}


def run_checks(root,fixture_root):
    """Keep real fixture trees shallow enough for Windows child processes."""
    before=source_hashes(); started=time.monotonic(); results=[]
    env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ['KEY','TOKEN','SECRET','AUTH','PASSWORD','PROXY'])}
    env.update(AUTOML_THREADS='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',
               TMPDIR=str(fixture_root),MPLCONFIGDIR=str(root/'mpl'),PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
    for script,expected in CHECKS.items():
        log=root/(script+'.log'); tick=time.monotonic()
        with log.open('w') as stream:
            process=subprocess.Popen([sys.executable,str(ROOT/'tests'/script)],cwd=ROOT,env=env,
                                     stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            try: status=wait_owned(process,timeout=300,memory_bytes=int(1.2*2**30))
            except subprocess.TimeoutExpired: status='timeout'
            except MemoryError: status='memory_limit'
        content=log.read_text(encoding='utf-8')
        observed=re.findall(r'Ran (\d+) tests? in ',content)
        count=int(observed[-1]) if observed else 5 if script=='smoke.py' and status==0 else None
        skipped_matches=re.findall(r'^(?:OK|FAILED) \([^\n]*\bskipped=(\d+)[^\n]*\)$',content,re.MULTILINE)
        skipped=int(skipped_matches[-1]) if skipped_matches else 0
        passed=status==0 and count==expected and skipped==0
        row={'script':script,'status':status,'passed':passed,'expected_checks':expected,
             'observed_checks':count,'skipped_checks':skipped,
             'seconds':round(time.monotonic()-tick,3),'log':str(log)}
        results.append(row); print(json.dumps(row),flush=True)
        atomic_json(root/'progress.json',{'checks':results})
    result={'python':sys.version,'source_sha256':before,'source_unchanged':source_hashes()==before,
            'test_script_sha256':{s:hashlib.sha256((ROOT/'tests'/s).read_bytes()).hexdigest() for s in CHECKS},
            'fixture_root':str(fixture_root),'fixture_path_policy':'Unique owned shallow workspace fixture root; original test assertions/counts unchanged',
            'checks':results,'unique_checks_passed':sum(r['observed_checks'] or 0 for r in results if r['passed']),
            'unique_checks_skipped':sum(r['skipped_checks'] for r in results),
            'seconds':round(time.monotonic()-started,3),'passed':all(r['passed'] for r in results)}
    result['passed']=result['passed'] and result['source_unchanged']
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); root=args.output.resolve(); root.mkdir(parents=True,exist_ok=False)
    (root/'mpl').mkdir()
    # A gate's output path can already be long. Multi-target/reporting fixtures
    # add nested directories, exceeding Windows MAX_PATH before any fit. Keep
    # temporary fixtures local and unique, independently of log/output nesting.
    fixture_parent=ROOT.parent/'t'; fixture_parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ck-',dir=fixture_parent) as fixture:
        result=run_checks(root,Path(fixture))
    result['fixture_cleanup_confirmed']=True
    atomic_json(root/'results.json',result)
    if not result['passed']: raise SystemExit(1)


if __name__=='__main__': main()
