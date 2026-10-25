"""Conservative whole-run guard, not an OS security sandbox."""
from dataclasses import dataclass
from pathlib import Path
import os, shutil, sys, time
import psutil
try:
    import resource
except ImportError:
    resource = None

def peak_rss_mb():
    """Return this process's lifetime peak resident memory in MiB."""
    if sys.platform == 'win32':
        return psutil.Process(os.getpid()).memory_info().peak_wset / 2 ** 20
    if resource is None:
        raise RuntimeError('Peak resident memory requires resource on this platform')
    scale = 2 ** 20 if sys.platform == 'darwin' else 2 ** 10
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / scale

@dataclass
class ResourceBudget:
    memory_limit: int = 28 * 2 ** 30
    artifact_limit: int = 20 * 2 ** 30
    minimum_free: int = 512 * 2 ** 20
    last_disk_check: float = 0.0
    disk_status: str | None = None

    def inspect(self, worker_pid, root):
        verified = getattr(self, '_verified_sampling', None)
        if verified is not None:
            return self._inspect_verified(worker_pid, root, verified)
        worker = psutil.Process(worker_pid)
        processes = [worker] + worker.children(recursive=True)
        rss = sum((p.memory_info().rss for p in processes if p.is_running()))
        total = rss + psutil.Process(os.getpid()).memory_info().rss
        if total > self.memory_limit:
            return ('memory_limit', rss, total)
        now = time.monotonic()
        if now - self.last_disk_check > 15:
            self.last_disk_check = now
            if shutil.disk_usage(root).free < self.minimum_free:
                self.disk_status = 'disk_space_limit'
        return (self.disk_status, rss, total)

    def _inspect_verified(self, worker_pid, root, configuration):
        """Fixed-release opt-in only; the original inspect branch stays intact."""
        sampler = configuration['sampler']
        checkpoint = configuration['checkpoint']
        own = configuration['self_identity']
        worker = configuration['root_identity']
        checkpoint()
        if type(worker_pid) is not int or worker_pid != worker[0]:
            raise RuntimeError('verified_resource_root_mismatch')
        provider = configuration.get('known_provider')
        if provider is not None:
            if not callable(provider):
                raise RuntimeError('verified_resource_known_provider_untyped')
            sampler.remember(provider())
            checkpoint()
        sampler.remember([own, worker])
        sampler.discover_owned_tree(worker, checkpoint=checkpoint)
        sample = sampler.sample(list(sampler.known), required=[own], checkpoint=checkpoint)
        rows = {(row['pid'], row['create_time']): row['rss_bytes'] for row in sample['sampled']}
        # Preserve the base scope: worker subtree + caller RSS.  If the worker
        # is self this intentionally remains a conservative self double-count.
        rss = sum(value for identity, value in rows.items()
                  if worker == own or identity != own)
        total = rss + rows[own]
        self.last_verified_sample = sample
        if total > self.memory_limit:
            return ('memory_limit', rss, total)
        checkpoint()
        now = time.monotonic()
        if now - self.last_disk_check > 15:
            self.last_disk_check = now
            if shutil.disk_usage(root).free < self.minimum_free:
                self.disk_status = 'disk_space_limit'
        checkpoint()
        return (self.disk_status, rss, total)

    def inspect_artifacts(self, path):
        size = sum((p.stat().st_size for p in Path(path).rglob('*') if p.is_file()))
        if size > self.artifact_limit:
            raise RuntimeError('Run artifact budget exceeded')
        return size
