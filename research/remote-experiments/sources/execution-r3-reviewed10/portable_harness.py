"""Opt-in Linux source wrapper. No learner is invoked by this source-only CLI.

Future model entry requires independently reviewed queue approval and exact seals.
RSS is sampled (not a cgroup/OS security boundary); uncertainty fails closed.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import hashlib, io, json, os, platform, subprocess, sys, tempfile, time, zipfile, selectors
import psutil

class Blocked(RuntimeError): pass
def need(value, code):
    if not value: raise Blocked(code)
def sha(path, tick=lambda: None):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(2**20),b''): h.update(chunk);tick()
    return h.hexdigest()
def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def load(path): return json.loads(Path(path).read_text())
def write_new(path, value):
    with Path(path).open('x') as f: json.dump(value,f,sort_keys=True,allow_nan=False)

@dataclass
class Clock:
    wall_start: float
    mono_start: float
    wall_deadline: float
    mono_deadline: float
    last: float
    evidence_path: object = None
    origin: object = None
    context: object = None
    telemetry: object = None
    active_parent_deadline: object = None
    @classmethod
    def retained(cls, claim, path, initialize=False):
        w,m=time.time(),time.monotonic();path=Path(path)
        seal=path.with_name(path.name+'.origin.json')
        need(not path.is_symlink() and not seal.is_symlink(),'clock_symlink')
        if path.exists():
            v=load(path)
            origin=load(seal)
            need(v['origin_sha256']==canonical(origin),'clock_origin_changed')
            need(origin['claim_canonical_sha256']==canonical(claim),'clock_claim_changed')
            need(origin['start']==claim['claimed_at_unix'] and origin['deadline']==claim['deadline_unix'],'clock_reset')
            need(abs((w-m)-origin['offset'])<5,'clock_discontinuity')
            need(0<=m-v['last']<=10,'observation_gap_over_10s')
            need(origin['mono_deadline']==origin['mono']+origin['deadline']-origin['wall'],'clock_origin_arithmetic')
        else:
            need(initialize and not seal.exists(),'missing_retained_clock_evidence')
            origin=dict(start=claim['claimed_at_unix'],deadline=claim['deadline_unix'],wall=w,mono=m,offset=w-m,
                        mono_deadline=m+claim['deadline_unix']-w,claim_mono_start=None,claim_canonical_sha256=canonical(claim))
            write_new(seal,origin);v=dict(origin_sha256=canonical(origin),last=m)
            write_new(path,v)
        c=cls(origin['wall'],origin['mono'],origin['deadline'],origin['mono_deadline'],v['last'],path,origin,None,[])
        c.tick();return c
    def snapshot(self, parent_deadline=None):
        self.tick()
        return dict(origin=self.origin,last=self.last,context=self.context,active_parent_deadline=parent_deadline)
    @classmethod
    def from_snapshot(cls, snapshot, expected_sha, claim):
        need(canonical(snapshot)==expected_sha,'clock_handoff_sha')
        origin=snapshot['origin'];m=time.monotonic();w=time.time()
        need(origin['claim_canonical_sha256']==canonical(claim) and origin['start']==claim['claimed_at_unix'] and origin['deadline']==claim['deadline_unix'],'clock_handoff_claim')
        need(origin['mono_deadline']==origin['mono']+origin['deadline']-origin['wall'],'clock_handoff_origin')
        need(abs((w-m)-origin['offset'])<5 and 0<=m-snapshot['last']<=10,'clock_handoff_gap_or_epoch')
        c=cls(origin['wall'],origin['mono'],origin['deadline'],origin['mono_deadline'],snapshot['last'],None,origin,snapshot['context'],[])
        c.active_parent_deadline=snapshot['active_parent_deadline']
        need(c.active_parent_deadline is None or m<c.active_parent_deadline<=c.mono_deadline,'clock_handoff_parent')
        c.tick();return c
    def tick(self, allocation=0):
        w,m=time.time(),time.monotonic()
        need(0<=m-self.last<=10,'observation_gap_over_10s')
        need(abs((w-m)-(self.wall_start-self.mono_start))<5,'clock_discontinuity')
        need(w+allocation<self.wall_deadline and m+allocation<self.mono_deadline,'deadline_or_full_allocation')
        need(self.active_parent_deadline is None or m+allocation<self.active_parent_deadline,'active_parent_deadline')
        if self.evidence_path is not None:
            path=Path(self.evidence_path);saved=load(path)
            need(saved==dict(origin_sha256=canonical(self.origin),last=self.last),'clock_last_sample_changed')
            need(load(path.with_name(path.name+'.origin.json'))==self.origin,'clock_origin_changed')
            tmp=path.with_name(path.name+'.pending')
            with tmp.open('x') as f:json.dump(dict(origin_sha256=canonical(self.origin),last=m),f,sort_keys=True)
            os.replace(tmp,path)
        self.last=m

def local_claim(context):
    """Local byte-canonical immutable claim evidence is never admission/approval."""
    need(set(context)=={'local_claim_path','local_claim_sha256','claim_sha','job_id','worker_id','dispatch_sha','wall_seconds','clock_path'},'clock_context_fields')
    with Path(context['local_claim_path']).open('rb') as stream:raw=stream.read(32769)
    need(len(raw)<=32768 and hashlib.sha256(raw).hexdigest()==context['local_claim_sha256'],'local_claim_byte_pin')
    claim=json.loads(raw)
    exact=(json.dumps(claim,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()
    need(raw==exact,'local_claim_not_canonical')
    need(set(claim)=={'schema','job_id','job_sha256','dispatch_sha','worker_id','claimed_at_unix','deadline_unix','nonce'} and claim['schema']==1,'local_claim_schema')
    for key in ('job_id','worker_id','dispatch_sha'):need(claim[key]==context[key],'local_claim_expected_identity')
    need(type(context['wall_seconds']) is int and context['wall_seconds']>0 and claim['deadline_unix']==claim['claimed_at_unix']+context['wall_seconds'],'local_original_deadline')
    need(type(claim['claimed_at_unix']) in (int,float) and claim['claimed_at_unix']<=time.time()<claim['deadline_unix'],'local_claim_expired')
    import re
    need(re.fullmatch('[0-9a-f]{40}',context['claim_sha']) is not None and re.fullmatch('[0-9a-f]{40}',claim['dispatch_sha']) is not None,'local_claim_oid')
    return claim

def bootstrap_clock(context, initialize=False, handoff=None, handoff_sha=None):
    claim=local_claim(context)
    path=Path(context['clock_path'])
    anchor=Path(context['local_claim_path']).with_name(Path(context['local_claim_path']).name+'.clock-binding.json')
    need(not anchor.is_symlink(),'clock_anchor_symlink')
    fresh=not anchor.exists()
    if fresh:
        need(initialize and handoff is None and not path.exists() and not path.with_name(path.name+'.origin.json').exists(),'missing_claim_clock_binding')
        write_new(anchor,dict(context_sha256=canonical(context),origin_sha256=None))
    else:
        pinned=load(anchor)
        need(pinned['context_sha256']==canonical(context),'claim_clock_context_changed')
        need(pinned['origin_sha256'] is not None and path.exists(),'missing_retained_clock_evidence')
        need(canonical(load(path.with_name(path.name+'.origin.json')))==pinned['origin_sha256'],'clock_origin_changed')
    if handoff is None:clock=Clock.retained(claim,context['clock_path'],initialize=initialize)
    else:
        clock=Clock.from_snapshot(handoff,handoff_sha,claim)
        need(clock.context==context,'clock_handoff_context')
        path=Path(context['clock_path']);origin=load(path.with_name(path.name+'.origin.json'));current=load(path)
        need(origin==clock.origin and current['origin_sha256']==canonical(origin),'clock_handoff_retained_origin')
        need(handoff['last']<=current['last']<=time.monotonic() and time.monotonic()-current['last']<=10,'clock_handoff_retained_sample')
    if fresh:
        pending=anchor.with_name(anchor.name+'.pending')
        write_new(pending,dict(context_sha256=canonical(context),origin_sha256=canonical(clock.origin)));os.replace(pending,anchor)
    clock.context=dict(context);clock.tick();return clock

def inventory(root, tick=lambda:None):
    root=Path(root).resolve();out={}
    for p in sorted(root.rglob('*')):
        need(not p.is_symlink(),'inventory_symlink')
        if p.is_file():out[str(p.relative_to(root))]=sha(p,tick)
        tick()
    return out
def check_inventory(root, expected, tick=lambda:None):
    need(inventory(root,tick)==expected,'inventory_changed')

def native_split(path, cut, n, groups=None, times=None):
    """Conjunctive native/container/member/value checks; arrays never rewritten."""
    import numpy as np
    need(platform.system()=='Linux','Linux_only');profile=cut['native_profiles']['Linux']
    need(sha(path)==profile['raw_npz_sha256'],'native_raw_sha')
    arrays=[];parts=[]
    with zipfile.ZipFile(path) as z:
        need(z.namelist()==['train.npy','validation.npy'],'native_member_order')
        for info,expected in zip(z.infolist(),profile['members']):
            raw=z.read(info.filename)
            need(info.create_system==profile['zip_creator_system'] and info.filename==expected['name'],'native_creator_name')
            need(hashlib.sha256(raw).hexdigest()==expected['npy_sha256'],'native_member_sha')
            f=io.BytesIO(raw);version=np.lib.format.read_magic(f)
            need(version==(1,0),'native_header_version')
            shape,fortran,dtype=np.lib.format.read_array_header_1_0(f)
            need(list(shape)==expected['shape'] and fortran is expected['fortran_order'] and dtype.str==expected['dtype'],'native_header')
            a=np.load(io.BytesIO(raw),allow_pickle=False)
            need(a.ndim==1 and a.dtype.kind in 'iu' and len(a)>0 and a.min()>=0 and a.max()<n and len(np.unique(a))==len(a),'native_indices')
            # Canonical comparison ONLY, never replace arrays used by the solver.
            values=a.astype('<i8').tobytes()
            need(hashlib.sha256(values).hexdigest()==expected['canonical_ordered_values_sha256'],'native_member_values')
            arrays.append(a);parts.append(values)
    tr,va=arrays
    need(not np.intersect1d(tr,va).size,'native_overlap')
    need(hashlib.sha256(b''.join(parts)).hexdigest()==cut['canonical_concat_train_validation_sha256'],'native_concat_values')
    if cut['kind']=='classification':
        need(groups is not None and not np.intersect1d(groups[tr],groups[va]).size,'native_group_overlap')
    else:
        need(times is not None and times[tr].max()<times[va].min(),'native_chronology')
    return tr,va

def clean_environment(temp, threads=2):
    temp=str(Path(temp).resolve());need(temp.isascii(),'ascii_temp')
    env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ('KEY','TOKEN','SECRET','AUTH','PASSWORD','PASSWD','PROXY','COOKIE'))
         and not k.upper().startswith(('OPENAI_','QWEN_','ANTHROPIC_','HF_','HUGGINGFACE_'))}
    for k in ('PYTHONPATH','PYTHONHOME','PYTHONSTARTUP'):env.pop(k,None)
    env.update(TMP=temp,TEMP=temp,TMPDIR=temp,JOBLIB_TEMP_FOLDER=temp,PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',
               OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',AUTOML_THREADS=str(threads))
    return env

@contextmanager
def host_lock(path):
    path=Path(path);p=psutil.Process();identity=dict(pid=p.pid,create_time=p.create_time())
    try:write_new(path,identity)
    except FileExistsError:raise Blocked('host_lock_occupied_no_reclaim')
    try:yield identity
    finally:
        need(load(path)==identity,'host_lock_identity_changed');path.unlink()

class OwnedTree:
    """Strict identity union; denial/replacement/traversal failures remain sticky."""
    def __init__(self,pid):
        p=psutil.Process(pid);self.root=(p.pid,p.create_time());self.known={self.root};self.errors=[]
    def fail(self,exc):
        self.errors.append(type(exc).__name__);raise Blocked('owned_observation_'+type(exc).__name__)
    def verified(self,identity):
        try:
            p=psutil.Process(identity[0])
            need(p.create_time()==identity[1],'owned_identity_replaced')
            return p
        except psutil.NoSuchProcess:return None
        except Exception as e:self.fail(e)
    def sample(self):
        total=0
        try:
            for identity in list(self.known):
                p=self.verified(identity)
                if p is None:continue
                # Direct traversal per known member discovers full recursive union;
                # never suppress AccessDenied as the old frozen helper did.
                for child in p.children(recursive=True):self.known.add((child.pid,child.create_time()))
            for identity in list(self.known):
                p=self.verified(identity)
                if p is not None:total+=p.memory_info().rss
        except Exception as e:self.fail(e)
        need(not self.errors,'sticky_owned_failure');return total
    def cleanup(self,tick):
        confirmed=False
        try:
            self.sample()
            for identity in sorted(self.known,reverse=True):
                tick();p=self.verified(identity)
                if p is not None and p.status() not in (psutil.STATUS_ZOMBIE,psutil.STATUS_DEAD):p.terminate()
            end=time.monotonic()+2
            while time.monotonic()<end:
                tick();alive=[]
                for identity in self.known:
                    p=self.verified(identity)
                    if p is not None and p.status() not in (psutil.STATUS_ZOMBIE,psutil.STATUS_DEAD):alive.append(identity)
                if not alive:break
                time.sleep(.02)
            for identity in self.known:
                tick();p=self.verified(identity)
                if p is not None and p.status() not in (psutil.STATUS_ZOMBIE,psutil.STATUS_DEAD):p.kill()
            # Caller reaps direct Popen; final fresh absence is checked afterwards.
        except Exception as e:self.errors.append(type(e).__name__)
        return confirmed
    def absent(self):
        try:
            for identity in self.known:
                # Exact fresh absence, zombie is not accepted as absent.
                need(self.verified(identity) is None,'owned_identity_not_absent')
            return not self.errors
        except Exception as e:self.errors.append(type(e).__name__);return False

def terminal_poll(process, child_deadline):
    """Exit observation itself must be strictly before the original child end."""
    code=process.poll();observed=time.monotonic()
    if observed>=child_deadline:
        exc=Blocked('child_deadline');exc.observed_monotonic=observed;exc.terminal_code=code;raise exc
    return code,observed

def supervise(command, cwd, env, frozen, clock, receipt, parent_seconds=480, child_seconds=450, parent_deadline=None, phase='worker'):
    """Private guarded primitive, not a public arbitrary-argv model CLI."""
    maximum=600 if phase=='audit' else 480
    need(phase in ('worker','audit') and 0<child_seconds and child_seconds+5<=parent_seconds<=maximum,'full_parent_allocation')
    need(child_seconds<=(570 if phase=='audit' else 450),'fixed_child_profile')
    clock.tick(parent_seconds);start_w,start_m=time.time(),time.monotonic()
    parent_end=start_m+parent_seconds if parent_deadline is None else min(start_m+parent_seconds,parent_deadline)
    def tick(allocation=0):
        clock.tick(allocation);need(time.monotonic()+allocation<parent_end,'parent_deadline')
    before=inventory(frozen,tick)
    # Hashing cost does not silently steal a declared full child allocation.
    tick(child_seconds+5);p=None;tree=None;errors=[];status='blocked';peaks=[0,0];clean=False
    child_start_w=child_start_m=child_observed_end=None
    owned_parent=OwnedTree(os.getpid())
    with Path(receipt).with_suffix('.log').open('xb') as log:
        try:
            tick(child_seconds+5)
            need(platform.system()=='Linux','Linux_supervisor_only')
            allowed=sorted(os.sched_getaffinity(0))[:2];need(allowed,'CPU_affinity_unavailable')
            tick(child_seconds+5)
            child_start_w,child_start_m=time.time(),time.monotonic();child_end=child_start_m+child_seconds
            p=subprocess.Popen(command,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
                               preexec_fn=lambda:os.sched_setaffinity(0,allowed))
            tree=OwnedTree(p.pid)
            write_new(Path(receipt).with_suffix('.identity.json'),dict(pid=tree.root[0],create_time=tree.root[1],original_deadline=clock.wall_deadline))
            while True:
                tick();worker=tree.sample();whole=owned_parent.sample()
                peaks=[max(peaks[0],worker),max(peaks[1],whole)]
                need(worker<=1536*2**20 and whole<=2048*2**20,'RSS_cap')
                code,observed=terminal_poll(p,child_end)
                if code is not None:child_observed_end=observed;break
                time.sleep(.05)
            status='completed' if p.returncode==0 else 'failed'
            if status=='failed':errors.append(dict(code='nonzero_child_exit',detail='Owned child returned nonzero; raw private log retained.'))
        except Exception as e:
            if getattr(e,'terminal_code',None) is not None:child_observed_end=e.observed_monotonic
            errors.append(dict(code=type(e).__name__,detail=str(e)));status='blocked'
        finally:
            if tree:
                tree.cleanup(tick)
                try:
                    p.wait(timeout=2)
                    if child_observed_end is None:child_observed_end=time.monotonic()
                except Exception as e:tree.errors.append(type(e).__name__)
                clean=tree.absent()
                if tree.errors:errors.extend(dict(code=e,detail='sticky owned observation or cleanup failure') for e in tree.errors)
                if not clean or owned_parent.errors:status='blocked';clean=False
    try:
        tick();check_inventory(frozen,before,tick);tick()
    except Exception as e:errors.append(dict(code=type(e).__name__,detail=str(e)));status='blocked';clean=False
    result=dict(status=status,exit_code=p.returncode if p else None,cleanup_confirmed=clean,
                first_error=errors[0] if errors else None,secondary_errors=errors[1:],
                start_unix=start_w,start_monotonic=start_m,original_deadline=clock.wall_deadline,parent_deadline_monotonic=parent_end,
                child_start_unix=child_start_w,child_start_monotonic=child_start_m,child_deadline_monotonic=child_start_m+child_seconds if child_start_m else None,
                child_terminal_observed_monotonic=child_observed_end,child_elapsed_seconds=child_observed_end-child_start_m if child_observed_end is not None else None,
                finished_unix=time.time(),wall_seconds=time.monotonic()-start_m,
                peak_worker_subtree_rss_mib=peaks[0]/2**20,peak_whole_owned_rss_mib=peaks[1]/2**20,
                identities=sorted(tree.known) if tree else [],frozen_sha256=before,cpu_threads_cap=2)
    # Receipt finalization is inside, never beyond, the same parent/common envelope.
    try:tick();write_new(receipt,result);tick()
    except Exception as e:
        result.update(status='blocked',cleanup_confirmed=False,finalization_error=type(e).__name__)
        # Returned state is authoritative on write/late errors; never publish old PASS.
        Path(receipt).write_text(json.dumps(result,sort_keys=True))
    return result

def expand_native_references(binding, native):
    """Typed references to immutable metadata; transport depth remains unchanged.

    The caller must verify the native document against the job's exact source pin
    before calling this function. No opaque JSON strings or arbitrary lookups.
    """
    need(binding.get('binding_schema')=='native-cut-references-v1','native_binding_schema')
    need(set(binding)=={'binding_schema','native_contract_ref','components','entrypoint','execution_sha256',
        'job_id','manifest_canonical_sha256','prepared_authority_sha256','spec_canonical_sha256','worker_id'},
        'native_binding_fields')
    need(binding['native_contract_ref']==dict(path='research/remote-experiments/sources/native-cut-contract-v3-r2.json',
        sha256='f5ad8c55aec198b689abf4bd8cf4ed0caf967fcd9f0d9f6db12f70513e1a60e5'),'native_contract_reference')
    rows=binding['components'];need(type(rows) is list and len(rows)==6,'native_six_components')
    expected=[(cut,arm) for cut in (42,43) for arm in ('strong','linear','rbf')]
    fields={'arm','cut','full_fit','job_relative','key','native_cut_canonical_sha256','output_relative',
            'private_job_sha256','recipe','spec_canonical_sha256','split_relative','threads'}
    expanded=[]
    for row,(cut,arm) in zip(rows,expected):
        need(type(row) is dict and set(row)==fields,'compact_component_fields')
        need(row['cut']==cut and row['arm']==arm and row['key']==f'classification{cut}-{arm}',
             'compact_component_order')
        matches=[v for v in native['cuts'] if canonical(v)==row['native_cut_canonical_sha256']]
        need(len(matches)==1 and matches[0]['kind']=='classification' and matches[0]['cut']==cut,
             'exact_native_cut_reference')
        item=dict(row);item.pop('native_cut_canonical_sha256');item['native_cut']=matches[0]
        expanded.append(item)
    result=dict(binding);result.pop('binding_schema');result.pop('native_contract_ref')
    result['components']=expanded
    return result

def cooperative_git(q, repo, clock, parent_deadline=None):
    """Instance-only Git.run override; protected queue methods remain inherited."""
    need(clock is not None and clock.context is not None,'explicit_original_clock_required')
    if clock.active_parent_deadline is not None:
        parent_deadline=min(parent_deadline,clock.active_parent_deadline) if parent_deadline is not None else clock.active_parent_deadline
    class CooperativeGit(q.Git):
        def run(self,*args,data=None,ok=True):
            return _cooperative_git_run(self,q,clock,parent_deadline,args,data,ok)
    return CooperativeGit(repo)

def _cooperative_git_run(g,q,clock,parent_deadline,args,data,ok):
    """Bounded main-thread pipes, exact Git argv and strict owned cleanup."""
    limit=4*1024*1024
    need(data is None or isinstance(data,bytes) and len(data)<=limit,'git_input_cap')
    start=time.monotonic();last=start;polls=0;maximum_gap=0.;phase='setup';proc=None;tree=None
    sticky=[];output=bytearray();stderr=bytearray();failure=None;code=None;error_phase=None
    def tick():
        nonlocal last,polls,maximum_gap
        now=time.monotonic();maximum_gap=max(maximum_gap,now-last)
        clock.tick();need(parent_deadline is None or now<parent_deadline,'git_parent_deadline')
        polls+=1;last=now
    def cleanup_tick():
        try:tick()
        except Exception as exc:sticky.append(type(exc).__name__+':'+str(exc))
    try:
        tick()
        with tempfile.TemporaryDirectory(prefix='remote-queue-hooks-') as hooks:
            env=clean_environment(hooks)
            for key in list(env):
                if key.startswith('GIT_'):env.pop(key,None)
            env.update(GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='Never',GIT_NO_REPLACE_OBJECTS='1',
                       GIT_AUTHOR_NAME='Remote Queue',GIT_AUTHOR_EMAIL='queue@local.invalid',
                       GIT_COMMITTER_NAME='Remote Queue',GIT_COMMITTER_EMAIL='queue@local.invalid')
            argv=['git','-C',str(g.repo),'-c','core.hooksPath='+hooks,'-c','protocol.ext.allow=never',*args]
            tick();parent_tree=OwnedTree(os.getpid());phase='spawn';began=time.monotonic()
            end=min(began+45,clock.mono_deadline,parent_deadline if parent_deadline is not None else float('inf'))
            with selectors.DefaultSelector() as selector:
                try:
                    proc=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,shell=False,start_new_session=True)
                    tree=OwnedTree(proc.pid);tick();phase='poll';offset=0
                    for stream,label in ((proc.stdout,'out'),(proc.stderr,'err')):
                        os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,label)
                    if data:
                        os.set_blocking(proc.stdin.fileno(),False);selector.register(proc.stdin,selectors.EVENT_WRITE,'in')
                    else:proc.stdin.close()
                    while True:
                        tick();q.need(time.monotonic()<end,'git_operation_timeout')
                        need(tree.sample()<=1536*2**20 and parent_tree.sample()<=2048*2**20,'git_RSS_cap')
                        for key,_ in selector.select(timeout=min(.1,max(0,end-time.monotonic()))):
                            tick();stream=key.fileobj
                            if key.data=='in':
                                try:sent=os.write(stream.fileno(),data[offset:offset+65536]);offset+=sent
                                except BrokenPipeError:offset=len(data)
                                if offset==len(data):selector.unregister(stream);stream.close()
                            else:
                                try:chunk=os.read(stream.fileno(),65536)
                                except BlockingIOError:continue
                                if chunk:
                                    target=output if key.data=='out' else stderr
                                    need(len(target)+len(chunk)<=limit,'git_output_cap' if key.data=='out' else 'git_stderr_cap');target.extend(chunk)
                                else:selector.unregister(stream);stream.close()
                        tick();code,observed=terminal_poll(proc,end)
                        if code is not None and not selector.get_map():break
                    phase='terminal';tick()
                except Exception as exc:failure=exc;error_phase=phase
                finally:
                    phase='cleanup'
                    if tree is not None:
                        tree.cleanup(cleanup_tick)
                    if proc is not None:
                        for stream in (proc.stdin,proc.stdout,proc.stderr):
                            if stream is not None and not stream.closed:stream.close()
                        try:proc.wait(timeout=2)
                        except Exception as exc:sticky.append(type(exc).__name__)
                    if tree is not None and (not tree.absent() or tree.errors):sticky.extend(tree.errors or ['git_identity_not_absent'])
                    elif proc is not None and tree is None:sticky.append('missing_owned_identity')
                    cleanup_tick()
            phase='temporary_cleanup';tick()
        phase='output_validation';tick();need(not sticky,'git_cleanup_or_observation_failed')
        if failure is not None:raise failure
        q.need(time.monotonic()<end,'git_operation_timeout')
        need(code is not None,'missing_git_terminal')
        result=subprocess.CompletedProcess(argv,code,bytes(output),bytes(stderr))
        if code:
            auth=bytes(stderr).lower()
            q.need(not any(x in auth for x in (b'authentication failed',b'could not read username',b'could not read password',b'terminal prompts disabled',b'permission denied (publickey)',b'cannot prompt',b'interactivity has been disabled')),'git_authentication_blocked')
            if ok:raise q.QueueError('git_operation_failed')
        tick();q.need(time.monotonic()<end,'git_operation_timeout');return result.stdout if ok else result
    except Exception as exc:
        if failure is None:failure=exc;error_phase=phase
        raise
    finally:
        # Numeric-only diagnostics: never argv, environment, raw output or refs.
        if clock.telemetry is not None:
            clock.telemetry.append(dict(seconds=time.monotonic()-start,ticks=polls,max_gap_seconds=maximum_gap,
                                        phase=phase,error_phase=error_phase,error=type(failure).__name__ if failure is not None else ('cleanup_failure' if sticky else None),cleanup_confirmed=tree is not None and not sticky))

def queue_admission(repo, queue_file, queue_sha, job_id, worker, claim_sha, clock, parent_deadline=None):
    """Verify actual immutable Git packets + pinned primary approval, not a bool."""
    import importlib.util
    need(sha(queue_file)==queue_sha,'queue_source_pin')
    spec=importlib.util.spec_from_file_location('_pinned_queue',queue_file);q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
    need(clock.context is not None,'explicit_original_clock_context')
    local=local_claim(clock.context);clock.tick()
    g=cooperative_git(q,repo,clock,parent_deadline);oid,claim,job,packet=q.read_claim(g,job_id)
    need(claim==local and oid==clock.context['claim_sha'] and claim_sha==oid,'remote_local_claim_mismatch')
    need(packet['claim.json']==Path(clock.context['local_claim_path']).read_bytes(),'remote_local_claim_bytes')
    need(oid==claim_sha and claim['worker_id']==worker and job['id']==job_id,'queue_identity_binding')
    need(job['kind']=='bounded_experiment' and job['caps']['max_fits']>0,'source_only_fit_refused')
    q.jobs(g,claim['dispatch_sha']);q.bounded_admission(g,claim['dispatch_sha'],job,worker)
    need(time.time()<claim['deadline_unix'],'queue_expired')
    refs={r['path']:r['sha256'] for r in job['source_refs']}
    binding_path='research/remote-experiments/sources/'+job_id+'-execution-binding.json'
    need(binding_path in refs,'typed_execution_binding_required')
    raw=g.blob(claim['dispatch_sha'],binding_path);need(q.digest(raw)==refs[binding_path],'execution_binding_pin')
    binding=q.decode(raw)
    need(binding['job_id']==job_id and binding['worker_id']==worker,'execution_binding_identity')
    if 'binding_schema' in binding or 'native_contract_ref' in binding:
        reference=binding.get('native_contract_ref')
        need(type(reference) is dict and set(reference)=={'path','sha256'},'typed_native_source_reference')
        need(reference['path'] in refs and refs[reference['path']]==reference['sha256'],
             'native_reference_must_be_job_source')
        native_raw=g.blob(claim['dispatch_sha'],reference['path'])
        need(q.digest(native_raw)==reference['sha256'],'native_reference_source_changed')
        binding=expand_native_references(binding,q.decode(native_raw))
    return claim,job,binding

def driver_finalize(raw, clock, parent_end, receipt, errors):
    """Called only AFTER temp removal and lock release (or held-lock check)."""
    errors=list(errors);raw_errors=([raw['first_error']] if raw and raw.get('first_error') else [])+(raw.get('secondary_errors',[]) if raw else [])
    try:
        clock.tick();need(time.monotonic()<parent_end,'driver_parent_deadline')
    except Exception as exc:errors.append(dict(code=type(exc).__name__,detail=str(exc)))
    all_errors=raw_errors+errors
    result=dict(status=raw['status'] if raw and not errors else 'blocked',cleanup_confirmed=bool(raw and raw['cleanup_confirmed'] and not errors),
                raw_supervisor_sha256=sha(receipt) if Path(receipt).exists() else None,original_deadline=clock.wall_deadline,
                parent_deadline_monotonic=parent_end,finished_unix=time.time(),
                first_error=all_errors[0] if all_errors else None,secondary_errors=all_errors[1:])
    final=Path(receipt).with_name(Path(receipt).stem+'.driver.json')
    try:
        clock.tick();need(time.monotonic()<parent_end,'driver_parent_deadline');write_new(final,result)
        clock.tick();need(time.monotonic()<parent_end,'driver_parent_deadline')
    except Exception as exc:
        err=dict(code=type(exc).__name__,detail=str(exc));all_errors.append(err)
        result.update(status='blocked',cleanup_confirmed=False,first_error=all_errors[0],secondary_errors=all_errors[1:],finished_unix=time.time())
        final.write_text(json.dumps(result,sort_keys=True))
    return result

@contextmanager
def selected_lock(path, held=None):
    if held is None:
        with host_lock(path) as identity:yield identity
    else:
        current=psutil.Process();expected=dict(pid=current.pid,create_time=current.create_time())
        need(held==expected and load(path)==expected,'already_held_lock_identity')
        yield held
        need(load(path)==expected,'already_held_lock_release_check')

def model_driver(repo,queue_file,queue_sha,job_id,worker,claim_sha,bundle,manifest,private_job,private_job_sha,clock_path,lock_path,receipt,held_lock=None,common_clock=None,parent_deadline=None):
    """Prospective entrypoint. This source job never invokes it."""
    parent_start=time.monotonic();parent_end=parent_start+480 if parent_deadline is None else min(parent_start+480,parent_deadline)
    need(common_clock is not None,'explicit_model_common_clock_required')
    clock=common_clock;clock.tick()
    claim,job,binding=queue_admission(repo,queue_file,queue_sha,job_id,worker,claim_sha,clock,parent_end)
    if 'components' in binding:
        matches=[v for v in binding['components'] if v['private_job_sha256']==private_job_sha]
        need(len(matches)==1,'exact_one_matrix_leaf_binding')
        binding=dict(binding,**matches[0])
    need(job['caps']['cpu_threads']==2 and job['caps']['worker_memory_mib']==1536
         and job['caps']['whole_memory_mib']==2048,'driver_exact_approved_resource_profile')
    need(manifest['source_archive_sha256']=='ca8a0898af84a4ddb8039343f94edc73aa7360005f215125907a34427a3c6d5c','algorithm_archive_pin')
    # Manifest itself must be one of this future immutable job's primary pins.
    need(binding['manifest_canonical_sha256']==canonical(manifest),'manifest_binding')
    need(Path(clock_path).resolve()==Path(clock.context['clock_path']).resolve(),'model_clock_path_changed')
    need(clock.wall_deadline==claim['deadline_unix'],'driver_common_clock_binding')
    need(sha(private_job,clock.tick)==private_job_sha,'private_job_seal')
    leaf=load(private_job)
    need(leaf['threads']==2 and leaf['full_fit'] is False and leaf['recipe'] and leaf['spec'],'typed_component_job')
    need(binding['private_job_sha256']==private_job_sha and binding['entrypoint']=='automl_worker.py','private_job_dispatch_binding')
    need(binding['recipe']==leaf['recipe'] and binding['spec_canonical_sha256']==canonical(leaf['spec']),'private_recipe_spec_binding')
    check_inventory(bundle,manifest['flat_files_sha256'],clock.tick)
    shared_lock=Path(repo).resolve().parent/'remote-research-state'/'experiment.lock'
    need(Path(lock_path).resolve()==shared_lock,'shared_host_lock_path_required')
    raw=None;errors=[]
    try:
        with selected_lock(lock_path,held_lock):
            with tempfile.TemporaryDirectory(prefix='automl-source-') as temp:
                env=clean_environment(temp);clock.tick(480)
                raw=supervise([sys.executable,str(Path(bundle).resolve()/'automl_worker.py'),str(Path(private_job).resolve())],bundle,env,bundle,clock,receipt,parent_deadline=parent_end)
        check_inventory(bundle,manifest['flat_files_sha256'],clock.tick)
    except Exception as exc:
        errors.append(dict(code=type(exc).__name__,detail=str(exc)))
        if raw is None:raise
    return driver_finalize(raw,clock,parent_end,receipt,errors)

if __name__=='__main__':
    raise SystemExit('source-only wrapper: learner execution refused; no model CLI enabled')
