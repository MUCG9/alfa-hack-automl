"""Portable strict owned-worker API with one explicitly forwarded caller clock.
Copied strict worker/cleanup semantics; only cooperative common checks are added.
No credentials, model changes, provider calls or background heartbeat.
"""
from pathlib import Path
from contextvars import ContextVar
import json, math, os, subprocess, sys, time
import numpy as np
import psutil
from automl_atomic import atomic_json
from automl_contracts_messages import ExperimentRequest
from automl_infrastructure_resources import ResourceBudget
from automl_infrastructure_processes import ProcessTree, ProcessCleanupError, ProcessObservationError
from automl_runtime import worker_entrypoint
from automl_verified_resource_sampling import VerifiedResourceSampler, ResourceSamplingError

THREADS = min(2, max(1, int(os.environ.get('AUTOML_THREADS', '2'))))
WORKER_MEMORY_LIMIT_BYTES = 1536 * 2**20
WHOLE_MEMORY_LIMIT_BYTES = 2048 * 2**20
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[name] = str(THREADS)
_HPO_FAIR_RESERVE_PROVENANCE = ContextVar('release_no_HPO_provenance', default=False)
_CALLER_CLOCK = ContextVar('release_original_caller_clock', default=None)

class ReleaseClock:
    """One all-inclusive wall+monotonic origin. Successful RSS samples alone tick.
    Resources inherit the base ResourceBudget; this is not an OS sandbox.
    """
    def __init__(self, seconds, root, *, origin=None):
        if type(seconds) not in (int,float) or not math.isfinite(seconds) or not 30 <= seconds <= 9900:
            raise ValueError('Release common budget must be finite30..9900 seconds')
        if origin is None:origin=(time.time(),time.monotonic())
        if type(origin) is not tuple or len(origin)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in origin):
            raise ValueError('Finite original wall/monotonic origin required')
        self.start_unix,self.start_monotonic=origin
        self.deadline_unix=self.start_unix+seconds;self.deadline_monotonic=self.start_monotonic+seconds
        self.root=Path(root);self.last=self.start_monotonic;self.previous=self.start_monotonic
        self.failure=None;self.resources=ResourceBudget(memory_limit=WHOLE_MEMORY_LIMIT_BYTES)
        self.samples=0;self.peak=0;self.peak_tree=0;self.last_resource_observation=None
        self._resource_checkpoint()
        own=psutil.Process(os.getpid());self.sampling_identity=(own.pid,own.create_time())
        self._resource_checkpoint()
        self.resources._verified_sampling=dict(sampler=VerifiedResourceSampler(),
            self_identity=self.sampling_identity,root_identity=self.sampling_identity,
            checkpoint=self._resource_checkpoint)
        self.check(force=True)
    def _resource_checkpoint(self):
        """Clock-only checks around every OS observation; never advance last."""
        if self.failure is not None:raise self.failure
        now=time.monotonic();wall=time.time()
        if not math.isfinite(now) or not math.isfinite(wall) or now < self.previous or wall<self.start_unix:
            raise RuntimeError('release_nonfinite_or_rollback')
        self.previous=now
        if now-self.last>10:raise RuntimeError('release_observation_gap_over10s')
        if now>=self.deadline_monotonic or wall>=self.deadline_unix:raise RuntimeError('release_original_common_deadline')
        if abs((self.deadline_unix-wall)-(self.deadline_monotonic-now))>5:raise RuntimeError('release_clock_disagreement')
        return now,wall
    def check(self, force=False):
        if self.failure is not None:raise self.failure
        try:
            now,wall=self._resource_checkpoint()
            if not force and now-self.last<.25:return
            limit,rss,total=self.resources.inspect(os.getpid(),self.root)
            self.last_resource_observation=dict(parent_tree_rss_bytes=rss,conservative_combined_bytes=total)
            self.peak=max(self.peak,total);self.peak_tree=max(self.peak_tree,rss)
            if total>WHOLE_MEMORY_LIMIT_BYTES:raise RuntimeError('release_whole_memory_limit')
            if limit:raise RuntimeError('release_'+limit)
            after,wall_after=self._resource_checkpoint()
            if not math.isfinite(after) or not math.isfinite(wall_after):raise RuntimeError('release_nonfinite_resource_observation')
            if after<now or after-self.last>10:raise RuntimeError('release_resource_inspection_gap_or_rollback')
            if after>=self.deadline_monotonic or wall_after>=self.deadline_unix:raise RuntimeError('release_original_common_deadline')
            if abs((self.deadline_unix-wall_after)-(self.deadline_monotonic-after))>5:raise RuntimeError('release_clock_disagreement')
            self.last=after;self.previous=after;self.samples+=1
            self.peak=max(self.peak,total);self.peak_tree=max(self.peak_tree,rss)
        except BaseException as exc:
            self.failure=exc;raise
    def remaining(self):
        self.check();return max(0.,min(self.deadline_unix-time.time(),self.deadline_monotonic-time.monotonic()))
    def receipt(self):
        return dict(start_unix=self.start_unix,start_monotonic=self.start_monotonic,
            deadline_unix=self.deadline_unix,deadline_monotonic=self.deadline_monotonic,
            actual_resource_samples=self.samples,
            observed_parent_tree_rss_peak_bytes=self.peak_tree,
            observed_parent_conservative_total_peak_bytes=self.peak,
            last_actual_resource_observation=self.last_resource_observation,
            last_verified_resource_sample=(self.resources.last_verified_sample
                if type(getattr(self.resources,'last_verified_sample',None)) is dict else None),
            parent_total_scope='inherited inspect(self) adds caller RSS twice; conservative, not exact OS-owned whole',
            observation_gap_limit_seconds=10,resource_sample_cadence_seconds=.25,
            resource_limit_bytes=self.resources.memory_limit,
            actual_failure_type=type(self.failure).__name__ if self.failure is not None else None)

def release_checkpoint():
    clock=_CALLER_CLOCK.get()
    if clock is None or not callable(getattr(clock,'check',None)):
        raise RuntimeError('Original release caller clock is required')
    clock.check()

def _strict_worker_cleanup(process,tree,primary):
    """Cleanup owned handles even when initial observation failed; never hide it."""
    if tree is not None:
        try:
            tree.terminate()
        except ProcessCleanupError as exc:
            if primary is not None:
                raise ProcessCleanupError(dict(exc.receipt,
                    prior_failure_type=type(primary).__name__)) from primary
            raise
        except BaseException as exc:
            # Unexpected cleanup errors also leave death unverified. Export
            # only safe failure types, never exception argv or credential text.
            raise ProcessCleanupError({'status':'cleanup_unconfirmed',
                'unresolved':[{'pid':process.pid,'create_time':None,
                    'action':'terminate_owned_tree','error':type(exc).__name__}],
                'actions':[],'prior_failure_type':type(primary).__name__ if primary is not None else None}) from exc
        return
    if process is None:
        return
    # Only the Popen-owned root handle remains after a constructor failure.
    # Never signal an unverified descendant or claim verified tree cleanup.
    receipt={'status':'observation_unconfirmed','unresolved':[{
        'pid':process.pid,'create_time':None,'action':'construct_owned_tree',
        'error':'TreeConstructionFailed'}],'actions':[]}
    try:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=3)
    except BaseException as exc:
        raise ProcessCleanupError(dict(receipt,
            cleanup_failure_type=type(exc).__name__,
            prior_failure_type=type(primary).__name__ if primary is not None else None)) from exc
    raise ProcessObservationError(receipt) from primary

def _run_worker_strict(spec,recipe,run_dir,split_path,timeout,full_fit=False,fit_iterations=None):
    """Same worker contract; one deadline includes discovery and final cleanup."""
    if type(timeout) not in (int,float) or not np.isfinite(timeout) or timeout<=0:
        raise ValueError('Strict worker timeout must be finite and positive')
    release_checkpoint()
    started=time.monotonic(); deadline=started+float(timeout)
    run_dir=Path(run_dir); run_dir.mkdir(parents=True,exist_ok=True)
    if (run_dir/'result.json').exists():
        return {'status':'error','error':'Existing result refused to prevent stale-checkpoint reuse',
                'recipe':recipe,'output_dir':str(run_dir),'strict_runtime':True}
    job={'spec':spec,'recipe':recipe,'output_dir':str(run_dir),'split_path':str(split_path),
         'threads':THREADS,'full_fit':full_fit}
    ExperimentRequest(run_dir.name,str(run_dir),str(split_path),recipe,THREADS).validate()
    if fit_iterations is not None: job['fit_iterations']=fit_iterations
    job_path=run_dir/'job.json'; atomic_json(job_path,job)
    release_checkpoint()
    env={k:v for k,v in os.environ.items() if not any(s in k.upper()
         for s in ['KEY','TOKEN','SECRET','PROXY','PASSWORD','PASSWD','AUTH'])}
    env.update(PYTHONIOENCODING='utf-8',PYTHONUTF8='1',MPLCONFIGDIR=str(run_dir/'mpl-cache'))
    process=tree=None; primary=None; killed=None; peak=peak_total=0
    budget=ResourceBudget(memory_limit=WHOLE_MEMORY_LIMIT_BYTES)
    parent=psutil.Process(os.getpid());sampling_self=(parent.pid,parent.create_time())
    sampling_previous=started
    def sampling_checkpoint():
        nonlocal sampling_previous
        release_checkpoint();now=time.monotonic()
        if not math.isfinite(now) or now<sampling_previous:
            raise RuntimeError('release_worker_resource_clock_rollback')
        sampling_previous=now
        if now>=deadline:raise TimeoutError('release_worker_resource_deadline')
    terminal_resource_observation=None
    result=None
    try:
        with (run_dir/'worker.log').open('w',encoding='utf-8') as log:
            if time.monotonic()>=deadline:
                killed='timeout'
            else:
                process=subprocess.Popen([sys.executable,'-u',str(worker_entrypoint()),str(job_path)],
                    cwd=spec['root'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                tree=ProcessTree(process,strict_observation=True)
                roots=[identity for identity in tree.members if identity[0]==process.pid]
                if len(roots)!=1:
                    raise ProcessObservationError({'status':'resource_observation_unconfirmed',
                        'unresolved':[{'pid':process.pid,'create_time':None,
                            'action':'bind_resource_root','error':'KnownRootIdentityRequired'}],'actions':[]})
                sampling_root=roots[0]
                budget._verified_sampling=dict(sampler=VerifiedResourceSampler(),
                    self_identity=sampling_self,root_identity=sampling_root,
                    known_provider=lambda:list(tree.members),checkpoint=sampling_checkpoint)
                while True:
                    release_checkpoint()
                    tree.refresh()
                    # Terminal observation is charged to the original deadline.
                    if time.monotonic()>=deadline:
                        killed='timeout'; break
                    terminal_before_sample=process.poll() is not None
                    try:
                        limit,rss,total=budget.inspect(process.pid,run_dir)
                        release_checkpoint()
                        peak=max(peak,rss); peak_total=max(peak_total,total)
                        observed=getattr(budget,'last_verified_sample',None)
                        if type(observed) is dict and not any((r['pid'],r['create_time'])==sampling_root for r in observed['sampled']):
                            if process.poll() is None:
                                raise ProcessObservationError({'status':'resource_observation_unconfirmed',
                                    'unresolved':[{'pid':process.pid,'create_time':sampling_root[1],
                                        'action':'verified_resource_root','error':'AbsentWithLivePopen'}],'actions':[]})
                            terminal_resource_observation=dict(status='fresh_known_root_departed_after_observed_exit',
                                worker_root_rss_bytes=None,sampled_known_worker_rss_bytes=rss,
                                departed=observed['departed'],remaining_owned_cleanup_still_required=True)
                        if terminal_before_sample:
                            if terminal_resource_observation is None:
                                terminal_resource_observation=dict(status='sampled_before_terminal_acceptance',
                                    worker_tree_rss_bytes=rss,combined_observed_bytes=total)
                        if limit: killed=limit
                        if total>WHOLE_MEMORY_LIMIT_BYTES:killed='whole_memory_limit'
                        if rss>WORKER_MEMORY_LIMIT_BYTES:killed='worker_memory_limit'
                    except ResourceSamplingError as exc:
                        raise ProcessObservationError({'status':'resource_observation_unconfirmed',
                            'unresolved':[{'pid':process.pid,'create_time':sampling_root[1],
                                'action':'verified_resource_sampling','error':exc.receipt['code']}],
                            'verified_sampling_failure':exc.receipt,'actions':[]}) from exc
                    except psutil.AccessDenied:
                        births=[c for pid,c in tree.members if pid==process.pid]
                        raise ProcessObservationError({'status':'resource_observation_unconfirmed',
                            'unresolved':[{'pid':process.pid,'create_time':births[0] if births else None,
                            'action':'inspect_resources','error':'AccessDenied'}],'actions':[]})
                    except psutil.NoSuchProcess:
                        # A vanished child is not evidence of an RSS=0 live
                        # tree. Only an already-terminal root resolves it.
                        tree.refresh()
                        if process.poll() is None:
                            raise ProcessObservationError({'status':'resource_observation_unconfirmed',
                                'unresolved':[{'pid':process.pid,'create_time':None,
                                'action':'inspect_resources','error':'NoSuchProcessWithLiveRoot'}],
                                'actions':[]})
                        terminal_resource_observation=dict(status='root_absent_after_observed_exit',
                            worker_tree_rss_bytes=None,combined_observed_bytes=None,
                            remaining_owned_cleanup_still_required=True)
                        break
                    if killed: break
                    if process.poll() is not None:break
                    time.sleep(.5)
        if killed:
            result={'status':killed}
        elif process.returncode==0 and (run_dir/'result.json').exists():
            result=json.loads((run_dir/'result.json').read_text(encoding='utf-8'))
        elif (run_dir/'result.json').exists():
            result=json.loads((run_dir/'result.json').read_text(encoding='utf-8'))
            result.update(status='error',exit_code=process.returncode)
        else:
            result={'status':'error','exit_code':process.returncode}
        try:
            result['artifact_bytes']=budget.inspect_artifacts(run_dir)
        except (psutil.AccessDenied,PermissionError) as exc:
            raise ProcessObservationError({'status':'resource_observation_unconfirmed',
                'unresolved':[{'pid':process.pid if process is not None else None,'create_time':None,
                    'action':'inspect_artifacts','error':type(exc).__name__}],'actions':[]}) from exc
    except ProcessCleanupError as exc:
        primary=exc
        raise
    except Exception as exc:
        primary=exc
        result={'status':'error','exception_type':type(exc).__name__}
    finally:
        # Keep exact resource-observed descendants available to the existing
        # strict cleanup tracker if a short-lived root has already departed.
        # Every eventual action still goes through ProcessTree's fresh birth
        # checks.  The caller itself is never adopted into a child cleanup.
        if tree is not None:
            caller_resources=getattr(_CALLER_CLOCK.get(),'resources',None)
            configurations=[getattr(budget,'_verified_sampling',None),
                getattr(caller_resources,'_verified_sampling',None)]
            for configuration in configurations:
                if type(configuration) is dict:
                    sampler=configuration.get('sampler')
                    for identity in getattr(sampler,'known',()):
                        if identity[0]!=sampling_self[0]:tree.members.setdefault(identity,None)
        cleanup_primary=primary
        if cleanup_primary is None and killed=='timeout':
            cleanup_primary=subprocess.TimeoutExpired('owned_worker',timeout)
        _strict_worker_cleanup(process,tree,cleanup_primary)
    # Cleanup, closing and result parsing cannot extend the worker allocation.
    if _HPO_FAIR_RESERVE_PROVENANCE.get():
        # Parent-owned control-plane facts, captured only AFTER confirmed cleanup.
        # Preserve the old late-timeout classification; do not launder its origin.
        fair_origin={'schema':'hpo-fair-reserve-worker-origin-v1','cleanup_confirmed':True,
            'coordinator_killed':killed,
            'primary_exception_type':type(primary).__name__ if primary is not None else None,
            'prior_result_status':result.get('status') if isinstance(result,dict) else None}
    finished=time.monotonic()
    if finished>=deadline:
        result={'status':'timeout'}
    if _HPO_FAIR_RESERVE_PROVENANCE.get():
        result['hpo_fair_reserve_provenance']=fair_origin
    result.update(recipe=recipe,output_dir=str(run_dir),strict_runtime=True,
        wall_seconds=round(finished-started,3),
        observed_process_tree_peak_mb=round(peak/2**20,1),
        observed_total_peak_mb=round(peak_total/2**20,1),
        observed_worker_tree_peak_bytes=peak,observed_combined_peak_bytes=peak_total,
        worker_memory_limit_bytes=WORKER_MEMORY_LIMIT_BYTES,
        whole_memory_limit_bytes=WHOLE_MEMORY_LIMIT_BYTES,
        verified_resource_sample=(budget.last_verified_sample
            if type(getattr(budget,'last_verified_sample',None)) is dict else None),
        terminal_resource_observation=terminal_resource_observation)
    return result

def run_release_worker(spec, recipe, run_dir, split_path, timeout, *, clock, full_fit=False, fit_iterations=None):
    """Public fixed-executor worker API; no independent common clock/fallback.
    Cleanup completes inside the copied strict wrapper before final caller check.
    Preserve a primary failure if the final clock/resource check also fails.
    """
    clock.check();allocation=min(float(timeout),clock.remaining())
    if not math.isfinite(allocation) or allocation<=0:raise RuntimeError('release_worker_not_admitted')
    token=_CALLER_CLOCK.set(clock)
    try:
        try:
            result=_run_worker_strict(spec,recipe,run_dir,split_path,allocation,
                full_fit=full_fit,fit_iterations=fit_iterations)
        except BaseException as primary:
            try:clock.check(force=True)
            except BaseException as secondary:
                try:primary.release_secondary_type=type(secondary).__name__
                except BaseException:pass
            raise
        clock.check(force=True)
        result['cleanup_confirmed']=True
        result['release_worker_allocation_seconds']=allocation
        result['release_original_clock']=clock.receipt()
        return result
    finally:
        _CALLER_CLOCK.reset(token)
