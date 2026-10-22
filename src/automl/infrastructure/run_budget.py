"""One coordinator-wide deadline and API ledger, shared across task phases/targets."""
from contextvars import ContextVar
from pathlib import Path
import math,time
from automl.infrastructure.atomic import atomic_json

_CURRENT=ContextVar('automl_run_budget',default=None)


def current_budget(): return _CURRENT.get()


def constrain_deadline(deadline):
    budget=current_budget()
    return min(deadline,budget.deadline) if budget is not None else deadline


def budget_metadata():
    budget=current_budget()
    return {'run_budget_trace':str(budget.trace),'run_budget':budget.snapshot()} if budget is not None else {}


class RunBudget:
    def __init__(self,seconds,max_calls,root,clock=None):
        if not isinstance(seconds,(int,float)) or not math.isfinite(seconds) or seconds<=0:
            raise ValueError('Run time budget must be finite and positive')
        if type(max_calls) is not int or not 0<=max_calls<=16:
            raise ValueError('Run gateway call limit must be an integer in0..16')
        self.clock=clock or time.monotonic; self.started=self.clock()
        self.deadline=self.started+seconds; self.seconds=seconds; self.max_calls=max_calls
        self.trace=Path(root)/'automl_runs'/('run-budget-'+str(time.time_ns()))/'report.json'
        self.calls_started=0; self.events=[]; self.status='running'; self.exception_type=None

    def remaining(self): return max(0.,self.deadline-self.clock())

    def authorize(self,timeout,purpose):
        allowed=min(float(timeout),self.remaining())
        if not math.isfinite(allowed) or allowed<5:
            return None,{'status':'run_deadline_exhausted','attempts':0,'usage_complete':True}
        if self.calls_started>=self.max_calls:
            return None,{'status':'run_call_limit','attempts':0,'usage_complete':True}
        self.calls_started+=1
        return allowed,None

    def record(self,call,purpose,reserved=False):
        # Do not store prompts, responses, errors, env, credentials or task rows.
        usage=call.get('usage') or {}
        def count(name,alias=None):
            value=usage.get(name,usage.get(alias,0))
            return int(value) if type(value) in (int,float) and math.isfinite(value) and value>=0 else 0
        attempts=call.get('attempts')
        attempts=attempts if type(attempts) is int and attempts>=0 else None
        no_network=not reserved and attempts in (None,0)
        event={'event':len(self.events)+1,'purpose':purpose,'status':call.get('status','unknown'),
               'reserved_gateway_call':bool(reserved),'http_attempts_known':attempts,
               'prompt_tokens_reported':count('prompt_tokens','input_tokens'),
               'completion_tokens_reported':count('completion_tokens','output_tokens'),
               'usage_complete':bool(no_network or call.get('usage_complete',False)),
               'elapsed_seconds':round(self.clock()-self.started,3)}
        self.events.append(event); self.flush()

    def snapshot(self):
        return {'schema_version':'1.0','status':self.status,'wall_limit_seconds':self.seconds,
                'elapsed_seconds':round(self.clock()-self.started,3),'remaining_seconds':round(self.remaining(),3),
                'gateway_call_limit':self.max_calls,'gateway_calls_started':self.calls_started,
                'http_attempts_reported':sum(e['http_attempts_known'] or 0 for e in self.events),
                'prompt_tokens_reported':sum(e['prompt_tokens_reported'] for e in self.events),
                'completion_tokens_reported':sum(e['completion_tokens_reported'] for e in self.events),
                'usage_complete':all(e['usage_complete'] for e in self.events) and sum(e['reserved_gateway_call'] for e in self.events)==self.calls_started,'events':list(self.events),
                'exception_type':self.exception_type,
                'scope':'One shared ledger; child snapshots are cumulative, not additive. Reported tokens exclude unknown retry usage; no currency/balance estimate.'}

    def flush(self): atomic_json(self.trace,self.snapshot())

    def __enter__(self):
        self.trace.parent.mkdir(parents=True,exist_ok=False)
        self.token=_CURRENT.set(self); self.flush()
        return self

    def __exit__(self,kind,value,traceback):
        self.status='completed' if kind is None else 'interrupted' if issubclass(kind,(SystemExit,KeyboardInterrupt)) else 'failed'
        self.exception_type=kind.__name__ if kind is not None else None
        try: self.flush()
        finally: _CURRENT.reset(self.token)
