"""Opt-in Linux source wrapper. No learner is invoked by this source-only CLI.

Future model entry requires independently reviewed queue approval and exact seals.
RSS is sampled (not a cgroup/OS security boundary); uncertainty fails closed.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import hashlib, io, json, os, platform, subprocess, sys, tempfile, time, zipfile
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
    @classmethod
    def retained(cls, claim, path):
        w,m=time.time(),time.monotonic();path=Path(path)
        if path.exists():
            v=load(path)
            need(v['start']==claim['claimed_at_unix'] and v['deadline']==claim['deadline_unix'],'clock_reset')
            need(abs((w-m)-v['offset'])<5,'clock_discontinuity')
        else:
            v=dict(start=claim['claimed_at_unix'],deadline=claim['deadline_unix'],wall=w,mono=m,offset=w-m,
                   mono_deadline=m+claim['deadline_unix']-w,claim_mono_start=None)
            write_new(path,v)
        c=cls(v['wall'],v['mono'],v['deadline'],v['mono_deadline'],m);c.tick();return c
    def tick(self, allocation=0):
        w,m=time.time(),time.monotonic()
        need(m-self.last<=10,'observation_gap_over_10s');self.last=m
        need(abs((w-m)-(self.wall_start-self.mono_start))<5,'clock_discontinuity')
        need(w+allocation<self.wall_deadline and m+allocation<self.mono_deadline,'deadline_or_full_allocation')

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

def supervise(command, cwd, env, frozen, clock, receipt, parent_seconds=480, child_seconds=450):
    """Private guarded primitive, not a public arbitrary-argv model CLI."""
    need(0<child_seconds and child_seconds+5<=parent_seconds<=480,'full_parent_allocation')
    clock.tick(parent_seconds);start_w,start_m=time.time(),time.monotonic()
    parent_end=start_m+parent_seconds
    def tick(allocation=0):
        clock.tick(allocation);need(time.monotonic()+allocation<parent_end,'parent_deadline')
    before=inventory(frozen,tick)
    # Hashing cost does not silently steal a declared full child allocation.
    tick(child_seconds+5);p=None;tree=None;errors=[];status='blocked';peaks=[0,0];clean=False
    owned_parent=OwnedTree(os.getpid())
    with Path(receipt).with_suffix('.log').open('xb') as log:
        try:
            tick(child_seconds+5)
            need(platform.system()=='Linux','Linux_supervisor_only')
            allowed=sorted(os.sched_getaffinity(0))[:2];need(allowed,'CPU_affinity_unavailable')
            tick(child_seconds+5)
            p=subprocess.Popen(command,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
                               preexec_fn=lambda:os.sched_setaffinity(0,allowed))
            child_end=time.monotonic()+child_seconds
            tree=OwnedTree(p.pid)
            write_new(Path(receipt).with_suffix('.identity.json'),dict(pid=tree.root[0],create_time=tree.root[1],original_deadline=clock.wall_deadline))
            while True:
                tick();worker=tree.sample();whole=owned_parent.sample()
                peaks=[max(peaks[0],worker),max(peaks[1],whole)]
                need(worker<=1536*2**20 and whole<=2048*2**20,'RSS_cap')
                if p.poll() is not None:break
                need(time.monotonic()<child_end,'child_deadline');time.sleep(.05)
            status='completed' if p.returncode==0 else 'failed'
            if status=='failed':errors.append(dict(code='nonzero_child_exit',detail='Owned child returned nonzero; raw private log retained.'))
        except Exception as e:errors.append(dict(code=type(e).__name__,detail=str(e)));status='blocked'
        finally:
            if tree:
                tree.cleanup(tick)
                try:p.wait(timeout=2)
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

def queue_admission(repo, queue_file, queue_sha, job_id, worker, claim_sha):
    """Verify actual immutable Git packets + pinned primary approval, not a bool."""
    import importlib.util
    need(sha(queue_file)==queue_sha,'queue_source_pin')
    spec=importlib.util.spec_from_file_location('_pinned_queue',queue_file);q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
    g=q.Git(repo);oid,claim,job,_=q.read_claim(g,job_id)
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
    return claim,job,binding

def model_driver(repo,queue_file,queue_sha,job_id,worker,claim_sha,bundle,manifest,private_job,private_job_sha,clock_path,lock_path,receipt):
    """Prospective entrypoint. This source job never invokes it."""
    claim,job,binding=queue_admission(repo,queue_file,queue_sha,job_id,worker,claim_sha)
    need(job['caps']['cpu_threads']==2 and job['caps']['worker_memory_mib']==1536
         and job['caps']['whole_memory_mib']==2048,'driver_exact_approved_resource_profile')
    need(manifest['source_archive_sha256']=='ca8a0898af84a4ddb8039343f94edc73aa7360005f215125907a34427a3c6d5c','algorithm_archive_pin')
    # Manifest itself must be one of this future immutable job's primary pins.
    need(binding['manifest_canonical_sha256']==canonical(manifest),'manifest_binding')
    clock=Clock.retained(claim,clock_path)
    need(sha(private_job,clock.tick)==private_job_sha,'private_job_seal')
    leaf=load(private_job)
    need(leaf['threads']==2 and leaf['full_fit'] is False and leaf['recipe'] and leaf['spec'],'typed_component_job')
    need(binding['private_job_sha256']==private_job_sha and binding['entrypoint']=='automl_worker.py','private_job_dispatch_binding')
    need(binding['recipe']==leaf['recipe'] and binding['spec_canonical_sha256']==canonical(leaf['spec']),'private_recipe_spec_binding')
    check_inventory(bundle,manifest['flat_files_sha256'],clock.tick)
    shared_lock=Path(repo).resolve().parent/'remote-research-state'/'experiment.lock'
    need(Path(lock_path).resolve()==shared_lock,'shared_host_lock_path_required')
    with host_lock(lock_path):
        with tempfile.TemporaryDirectory(prefix='automl-source-') as temp:
            env=clean_environment(temp);clock.tick(480)
            return supervise([sys.executable,str(Path(bundle).resolve()/'automl_worker.py'),str(Path(private_job).resolve())],bundle,env,bundle,clock,receipt)

if __name__=='__main__':
    raise SystemExit('source-only wrapper: learner execution refused; no model CLI enabled')
