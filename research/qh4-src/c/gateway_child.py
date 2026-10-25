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


GATEWAY_SOURCE_RELATIVE=(
    'src/automl/__init__.py',
    'src/automl/infrastructure/__init__.py',
    'src/automl/infrastructure/llm_gateway.py',
    'src/automl/infrastructure/run_budget.py',
    'src/automl/infrastructure/atomic.py',
)


def need(value,code):
    if not value:raise RuntimeError(code)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verified_gateway_sources(cfg,check):
    """Require the exact five-file local import closure, all actual bytes bound."""
    root=Path(cfg['canonical_root']);sources=cfg.get('source_files')
    need(root.is_absolute(),'absolute_bound_canonical_source_required')
    paths={str(root/relative) for relative in GATEWAY_SOURCE_RELATIVE}
    need(type(sources) is dict and set(sources)==paths,'exact_gateway_source_closure_required')
    for path,expected in sources.items():
        need(Path(path).is_absolute() and type(expected) is str and len(expected)==64
            and all(c in '0123456789abcdef' for c in expected) and sha(path)==expected,
            'gateway_dependency_changed')
        check()
    return dict(sources)


def run(a):
    need(Path(a.request).is_absolute() and sha(__file__)==a.self_sha256,'fixed_gateway_source_required')
    request=Path(a.request);need(request.stat().st_size<=131072 and sha(request)==a.request_sha256,'bounded_exact_gateway_request_required')
    cfg=json.loads(request.read_text('utf-8'))
    need(cfg.get('schema')=='qwen-three-hour-single-gateway-v1' and type(cfg.get('call_number')) is int
         and 1<=cfg['call_number']<=4800,'bounded_time_admitted_provider_request_required')
    clock=cfg['clock']
    def check(provider=True):
        now=time.monotonic();wall=time.time()
        need(all(type(v) in (int,float) and math.isfinite(v) for v in (now,wall,*clock.values())),'finite_original_clock_required')
        need(clock['common_deadline_monotonic']==clock['start_monotonic']+10800
             and clock['absolute_deadline_unix']==clock['start_unix']+10800,'same_original10800_required')
        need(now<min(clock['common_deadline_monotonic'],clock['task_deadline_monotonic'])
             and wall<clock['absolute_deadline_unix'],'original_task_common_deadline')
        if provider:need(now<clock['provider_deadline_monotonic'],'original_provider_task_common_deadline')
    check()
    verified_gateway_sources(cfg,check)
    root=Path(cfg['canonical_root'])
    output=Path(cfg['output']);need(output.is_absolute() and not output.exists(),'one_exclusive_gateway_output_required')
    sys.dont_write_bytecode=True;sys.path.insert(0,str(root/'src'))
    from automl.infrastructure.run_budget import current_budget
    need(current_budget() is None,'legacy16call_RunBudget_must_not_wrap_iterative_gateway')
    from automl.infrastructure.llm_gateway import request_json
    check();timeout=min(cfg['timeout'],clock['provider_deadline_monotonic']-time.monotonic())
    need(type(timeout) in (int,float) and 5<=timeout<=180,'bounded_provider_timeout_required')
    content,usage=request_json(cfg['prompt'],cfg['context'],max_output=8192,timeout=timeout,purpose='iterative_research')
    # Preserve a bounded safe SDK outcome before the provider-only postcheck.
    # Hard task/common expiry still stops before publication. A provider overrun
    # still exits nonzero AFTER this diagnostic write; the parent rejects it.
    check(provider=False)
    need(content is None or type(content) is str and len(content.encode('utf-8'))<=32768,'provider_output_too_large')
    need(type(usage) is dict,'actual_gateway_usage_receipt_required')
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
