"""Track only descendants of an owned Popen, including detached sessions."""
import json
import subprocess
import time
import psutil

class ProcessCleanupError(RuntimeError):
    """Fail closed with a safe receipt when owned cleanup is unconfirmed.

    The receipt is included in the exception text so existing coordinator error
    logs retain it. It contains identities/actions only, never argv or secrets.
    """

    def __init__(self, receipt):
        self.receipt = receipt
        super().__init__('Owned process cleanup could not be confirmed: ' + json.dumps(receipt, sort_keys=True))

class ProcessTree:

    def __init__(self, process):
        self.process = process
        self.members = {}
        self.cleanup_errors = []
        self._pending_cleanup = {}
        self._last_denial_at = None
        try:
            if process.poll() is None:
                root = psutil.Process(process.pid)
                identity = (root.pid, root.create_time())
                if process.poll() is None:
                    self.members[identity] = root
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        self.refresh()

    def _denied(self, identity, action):
        entry = {'pid': identity[0], 'create_time': identity[1], 'action': action, 'error': 'AccessDenied'}
        if entry not in self.cleanup_errors:
            self.cleanup_errors.append(entry)
        self._pending_cleanup[identity] = entry
        self._last_denial_at = time.monotonic()
        self.members.pop(identity, None)

    def _verified(self, identity):
        """Reopen a PID; a cached psutil object is not an identity guarantee."""
        pid, created = identity
        if pid == self.process.pid and self.process.poll() is not None:
            self.members.pop(identity, None)
            return None
        try:
            current = psutil.Process(pid)
            if current.create_time() != created:
                self.members.pop(identity, None)
                return None
            if pid == self.process.pid and self.process.poll() is not None:
                self.members.pop(identity, None)
                return None
        except psutil.NoSuchProcess:
            self.members.pop(identity, None)
            return None
        except psutil.AccessDenied:
            self._denied(identity, 'verify_identity')
            return None
        self.members[identity] = current
        return current

    def _verified_descendants(self, identities):
        members = []
        for identity in identities:
            if identity[0] == self.process.pid:
                continue
            member = self._verified(identity)
            if member is not None:
                members.append(member)
        return members

    def refresh(self):
        for identity in list(self.members):
            root = self._verified(identity)
            if root is None:
                continue
            try:
                for child in root.children(recursive=True):
                    try:
                        child_identity = (child.pid, child.create_time())
                    except psutil.NoSuchProcess:
                        continue
                    except psutil.AccessDenied:
                        self._denied((child.pid, None), 'discover_identity')
                        continue
                    if child_identity not in self._pending_cleanup:
                        self.members[child_identity] = child
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    def _confirm_pending_cleanup(self):
        unresolved = []
        for identity, entry in list(self._pending_cleanup.items()):
            pid, created = identity
            resolved = False
            try:
                if pid == self.process.pid and self.process.poll() is not None:
                    resolved = True
                else:
                    current = psutil.Process(pid)
                    actual_created = current.create_time()
                    if created is not None and actual_created != created:
                        resolved = True
                    elif not current.is_running() or current.status() in {psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD}:
                        resolved = True
                    else:
                        unresolved.append(dict(entry, reason='still_alive' if created is not None else 'ownership_unverified'))
            except psutil.NoSuchProcess:
                resolved = True
            except psutil.AccessDenied:
                unresolved.append(dict(entry, reason='identity_unverifiable'))
            if resolved:
                self._pending_cleanup.pop(identity, None)
                self.members.pop(identity, None)
        if unresolved:
            raise ProcessCleanupError({'status': 'cleanup_unconfirmed', 'unresolved': unresolved, 'actions': list(self.cleanup_errors)})

    def terminate(self, grace=3):
        recheck_at = time.monotonic() + max(0, grace)
        self.refresh()
        identities = [key for key in self.members if key[0] != self.process.pid]
        for identity in reversed(identities):
            member = self._verified(identity)
            if member is None:
                continue
            try:
                member.terminate()
            except psutil.NoSuchProcess:
                self.members.pop(identity, None)
            except psutil.AccessDenied:
                self._denied(identity, 'terminate')
        if self.process.poll() is None:
            self.process.terminate()
        members = self._verified_descendants([key for key in identities if key in self.members])
        _, alive = psutil.wait_procs(members, timeout=grace)
        try:
            self.process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            if self.process.poll() is None:
                self.process.kill()
        alive_identities = []
        for member in alive:
            identity = (member.pid, member.create_time())
            if identity not in self.members:
                continue
            current = self._verified(identity)
            if current is None:
                continue
            try:
                current.kill()
                alive_identities.append(identity)
            except psutil.NoSuchProcess:
                self.members.pop(identity, None)
            except psutil.AccessDenied:
                self._denied(identity, 'kill')
        psutil.wait_procs(self._verified_descendants(alive_identities), timeout=grace)
        self.process.wait(timeout=grace)
        if self._pending_cleanup:
            if self._last_denial_at is not None:
                recheck_at = max(recheck_at, self._last_denial_at + max(0, grace))
            remaining = recheck_at - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)
            self._confirm_pending_cleanup()

def wait_owned(process, timeout, memory_bytes=None):
    tree = ProcessTree(process)
    deadline = time.monotonic() + timeout
    try:
        while process.poll() is None:
            tree.refresh()
            if memory_bytes is not None:
                rss = 0
                for member in list(tree.members.values()):
                    try:
                        rss += member.memory_info().rss
                    except psutil.NoSuchProcess:
                        pass
                if rss > memory_bytes:
                    raise MemoryError('Local benchmark memory limit')
            if time.monotonic() >= deadline:
                import subprocess
                raise subprocess.TimeoutExpired(process.args, timeout)
            time.sleep(0.1)
        return process.returncode
    finally:
        tree.terminate()
