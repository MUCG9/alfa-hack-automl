"""Conservative whole-run guard, not an OS security sandbox."""
from dataclasses import dataclass
from pathlib import Path
import os,shutil,sys,time
import psutil

try:
    import resource
except ImportError:
    resource=None


def peak_rss_mb():
    """Return this process's lifetime peak resident memory in MiB."""
    if sys.platform=='win32':
        return psutil.Process(os.getpid()).memory_info().peak_wset/2**20
    if resource is None:
        raise RuntimeError('Peak resident memory requires resource on this platform')
    # Linux reports KiB; macOS reports bytes.
    scale=2**20 if sys.platform=='darwin' else 2**10
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/scale


@dataclass
class ResourceBudget:
    memory_limit:int=28*2**30
    artifact_limit:int=20*2**30
    minimum_free:int=512*2**20
    last_disk_check:float=0.
    disk_status:str|None=None
    def inspect(self,worker_pid,root):
        worker=psutil.Process(worker_pid)
        processes=[worker]+worker.children(recursive=True)
        rss=sum(p.memory_info().rss for p in processes if p.is_running())
        total=rss+psutil.Process(os.getpid()).memory_info().rss
        if total>self.memory_limit: return 'memory_limit',rss,total
        now=time.monotonic()
        if now-self.last_disk_check>15:
            self.last_disk_check=now
            if shutil.disk_usage(root).free<self.minimum_free: self.disk_status='disk_space_limit'
        return self.disk_status,rss,total
    def inspect_artifacts(self,path):
        size=sum(p.stat().st_size for p in Path(path).rglob('*') if p.is_file())
        if size>self.artifact_limit: raise RuntimeError('Run artifact budget exceeded')
        return size
