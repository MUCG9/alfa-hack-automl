"""Prospective fixed six-component caller; no job ID or model approval assigned.

Future primary must pin this source, execution map and claim context. Default is
inspection only. This source task never invokes the execution branch.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,platform,sys
QUEUE_SHA='d42cb979db953eeffabfa65ee2a40d8763dfd835f91ce35149327f3d181e4c49'
EXECUTION = {
 'portable_harness.py':'ceec298c13f6f91621f5abafd257d64de02b8590a105a3620c50186a7e5f633e',
 'experiment_driver.py':'e0b0458cd6aeb7bdb7fe00dd29e248d7c7605c179c69ef5b6ca27340ba3c63f3',
 'component_audit.py':'befcca2f8e630b9fb8e1bca81ce46b4d08f6f17773c65a38f133a56c277d2ffd',
 'pure_contracts.py':'783830691e558748b4437a734d27cd4cb332c6731f683c3058cd21ea18597286',
}
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(value,code):
    if not value:raise RuntimeError(code)
def invoke(repo,queue,root,prepared,context):
    """No network until local original-clock bootstrap; no arbitrary model argv."""
    need(__debug__ and platform.system()=='Linux','nonoptimized_linux_required')
    repo=Path(repo).resolve();root=Path(root).resolve();queue=Path(queue).resolve()
    need(queue==repo/'research/remote-experiments/queue/remote_queue.py' and digest(queue)==QUEUE_SHA,'exact_queue_source')
    need(len(EXECUTION)==4,'unassigned_execution_sources')
    for n,pin in EXECUTION.items():need(digest(root/'execution-r3'/n)==pin,'exact_execution_source')
    sys.path.insert(0,str(root/'execution-r3'))
    import portable_harness as h
    clock=h.bootstrap_clock(context,initialize=True)
    failure=None
    try:
        claim,job,binding=h.queue_admission(str(repo),str(queue),QUEUE_SHA,context['job_id'],context['worker_id'],context['claim_sha'],clock)
        source_relative=str(Path(__file__).resolve().relative_to(repo))
        refs={v['path']:v['sha256'] for v in job['source_refs']}
        h.need(source_relative in refs and digest(__file__)==refs[source_relative],'future_caller_actual_job_source_pin')
        h.need(binding['execution_sha256']==EXECUTION,'future_exact_execution_binding')
        import experiment_driver as d
        return d.execute(str(repo),str(queue),context['job_id'],context['worker_id'],context['claim_sha'],str(root),str(prepared),context['clock_path'],clock,context)
    except Exception as exc:
        failure=exc;raise
    finally:
        # Private numeric command telemetry is not an independent quality receipt.
        try:
            with (root/'git-admission-observations.json').open('x') as f:json.dump(clock.telemetry,f,sort_keys=True)
            clock.tick()
        except Exception:
            if failure is None:raise
def main():
    if len(sys.argv)==1:
        print(json.dumps(dict(mode='inspection_only',future_job=None,approval=False,model_processes=0)));return 0
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('repo','queue-file','root','prepared-authority','local-claim','local-claim-sha256','claim-sha','expected-dispatch-sha','job-id','clock-path'):
        p.add_argument('--'+n,required=True)
    a=p.parse_args()
    context=dict(local_claim_path=str(Path(a.local_claim).resolve()),local_claim_sha256=a.local_claim_sha256,claim_sha=a.claim_sha,
                 job_id=a.job_id,worker_id='remote-worker-f7dd39e0',dispatch_sha=a.expected_dispatch_sha,wall_seconds=5400,clock_path=str(Path(a.clock_path).resolve()))
    result=invoke(a.repo,a.queue_file,a.root,a.prepared_authority,context)
    print(json.dumps({k:result.get(k) for k in ('status','actual_learner_fits','api_calls','full_refit','promotion')}))
    return 0 if result.get('status')=='component_complete' else 1
if __name__=='__main__':raise SystemExit(main())
