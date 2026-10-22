"""Track only descendants of an owned Popen, including detached sessions."""
import time
import psutil


class ProcessTree:
    def __init__(self, process):
        self.process = process
        self.members = {}
        try:
            root=psutil.Process(process.pid)
            self.members[(root.pid,root.create_time())]=root
        except psutil.NoSuchProcess:
            pass
        self.refresh()

    def refresh(self):
        roots = list(self.members.values())
        for root in roots:
            try:
                if not root.is_running():
                    continue
                for child in [root] + root.children(recursive=True):
                    self.members[(child.pid, child.create_time())] = child
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    def terminate(self, grace=3):
        self.refresh()
        # psutil checks process identity before sending signals (PID reuse).
        members = list(self.members.values())
        for member in reversed(members):
            try:
                member.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(members, timeout=grace)
        for member in alive:
            try:
                member.kill()
            except psutil.NoSuchProcess:
                pass
        psutil.wait_procs(alive, timeout=grace)
        self.process.wait(timeout=grace)


def wait_owned(process, timeout, memory_bytes=None):
    tree = ProcessTree(process)
    deadline = time.monotonic() + timeout
    try:
        while process.poll() is None:
            tree.refresh()
            if memory_bytes is not None:
                rss=0
                for member in list(tree.members.values()):
                    try: rss+=member.memory_info().rss
                    except psutil.NoSuchProcess: pass
                if rss>memory_bytes: raise MemoryError('Local benchmark memory limit')
            if time.monotonic() >= deadline:
                import subprocess
                raise subprocess.TimeoutExpired(process.args, timeout)
            time.sleep(.1)
        return process.returncode
    finally:
        tree.terminate()
