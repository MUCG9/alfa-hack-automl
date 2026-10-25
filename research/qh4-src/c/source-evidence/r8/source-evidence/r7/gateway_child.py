"""One fixed supervised provider request. The caller owns clocks/resources.

No shell payload, learner, input loader or new budget. Credentials are supplied
only through the existing authorized private gateway environment.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import sys
import time


def need(value,code):
    if not value:raise RuntimeError(code)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(a):
    need(Path(a.request).is_absolute() and sha(__file__)==a.self_sha256,'fixed_gateway_source_required')
    request=Path(a.request);need(request.stat().st_size<=131072 and sha(request)==a.request_sha256,'bounded_exact_gateway_request_required')
    cfg=json.loads(request.read_text('utf-8'))
    need(cfg.get('schema')=='qwen-three-hour-single-gateway-v1' and type(cfg.get('call_number')) is int
         and 1<=cfg['call_number']<=4800,'bounded_time_admitted_provider_request_required')
    clock=cfg['clock']
    def check():
        now=time.monotonic();wall=time.time()
        need(all(type(v) in (int,float) and math.isfinite(v) for v in (now,wall,*clock.values())),'finite_original_clock_required')
        need(clock['common_deadline_monotonic']==clock['start_monotonic']+10800
             and clock['absolute_deadline_unix']==clock['start_unix']+10800,'same_original10800_required')
        need(now<min(clock['common_deadline_monotonic'],clock['task_deadline_monotonic'],clock['provider_deadline_monotonic'])
             and wall<clock['absolute_deadline_unix'],'original_provider_task_common_deadline')
    check()
    need(type(cfg['source_files']) is dict and cfg['source_files'],'pinned_gateway_dependencies_required')
    for path,expected in cfg['source_files'].items():
        need(Path(path).is_absolute() and sha(path)==expected,'gateway_dependency_changed');check()
    root=Path(cfg['canonical_root']);need(root.is_absolute(),'absolute_bound_canonical_source_required')
    need(str(root/'src/automl/infrastructure/llm_gateway.py') in cfg['source_files']
         and str(root/'src/automl/infrastructure/run_budget.py') in cfg['source_files'],'gateway_and_legacy_budget_sources_bound')
    output=Path(cfg['output']);need(output.is_absolute() and not output.exists(),'one_exclusive_gateway_output_required')
    sys.dont_write_bytecode=True;sys.path.insert(0,str(root/'src'))
    from automl.infrastructure.run_budget import current_budget
    need(current_budget() is None,'legacy16call_RunBudget_must_not_wrap_iterative_gateway')
    from automl.infrastructure.llm_gateway import request_json
    check();timeout=min(cfg['timeout'],clock['provider_deadline_monotonic']-time.monotonic())
    need(type(timeout) in (int,float) and 5<=timeout<=180,'bounded_provider_timeout_required')
    content,usage=request_json(cfg['prompt'],cfg['context'],max_output=8192,timeout=timeout,purpose='iterative_research')
    check();need(content is None or type(content) is str and len(content.encode('utf-8'))<=32768,'provider_output_too_large')
    safe={k:usage.get(k) for k in ('status','attempts','usage','usage_complete','finish_reason',
        'reasoning_effort_requested','response_model','reasoning_tokens_reported','wall_seconds','exception_type')}
    # No provider error text, credential, environment, reasoning text or URL.
    with output.open('x',encoding='utf-8') as stream:
        json.dump({'schema':'qwen-three-hour-single-gateway-result-v1','content':content,'call':safe,
            'request_sha256':a.request_sha256,'call_number':cfg['call_number']},stream,allow_nan=False,ensure_ascii=False)
    check();return 0


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--request',required=True);p.add_argument('--request-sha256',required=True);p.add_argument('--self-sha256',required=True)
    raise SystemExit(run(p.parse_args()))
