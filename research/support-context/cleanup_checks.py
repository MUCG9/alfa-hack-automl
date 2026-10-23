"""Synthetic ownership checks only: no subprocesses, API, files or model fits."""
import ast
import argparse
import importlib.util
from pathlib import Path
import sys
import types
from unittest.mock import patch


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--coordinator', type=Path,
                    default=Path(__file__).with_name('support_component_coordinator.py'))
path = parser.parse_args().coordinator.resolve()
ast.parse(path.read_text(encoding='utf-8'))
spec = importlib.util.spec_from_file_location('prepared_support_coordinator', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Gone(Exception):
    pass


class Denied(Exception):
    pass


class Process:
    def __init__(self, pid, created, descendants=(), denied=False):
        self.pid, self.created = pid, created
        self.descendants, self.denied = list(descendants), denied

    def create_time(self):
        return self.created

    def status(self):
        return 'running'

    def children(self, recursive=True):
        if self.denied:
            raise Denied()
        return list(self.descendants)


class RootHandle:
    pid = 11
    returncode = None

    def poll(self):
        return self.returncode

    def terminate(self):
        registry.pop(self.pid, None)
        self.returncode = -15

    kill = terminate

    def wait(self, timeout):
        return self.returncode


def process(pid):
    if pid not in registry:
        raise Gone()
    return registry[pid]


fake_psutil = types.SimpleNamespace(Process=process, NoSuchProcess=Gone,
    AccessDenied=Denied, STATUS_ZOMBIE='zombie', STATUS_DEAD='dead')


class Tree:
    def __init__(self, child, retain=False):
        self.members = {(11, 1.): registry[11]}
        self._pending_cleanup = {}
        self.cleanup_errors = []
        self.retain = retain

    def terminate(self):
        if not self.retain:
            for pid, created in self.members:
                if pid in registry and registry[pid].created == created:
                    registry.pop(pid)
        self.members = {}


passed = []
with patch.dict(sys.modules, {'psutil': fake_psutil}):
    # A descendant seen only by the strict observer is added to known-owned cleanup.
    registry = {22: Process(22, 2.)}
    registry[11] = Process(11, 1., [registry[22]])
    child, observer = RootHandle(), module.StrictOwnedObserver()
    tree = Tree(child)
    observer.remember(tree.members)
    result = module.cleanup_owned(child, tree, observer, True, Tree)
    assert result['cleanup_confirmed'] and not registry
    assert result['cleanup_observation']['observed_count'] == 2
    passed.append('fresh_observed_descendant_is_cleaned')

    # Inherited terminate may return while a descendant is still alive.
    registry = {11: Process(11, 1.), 22: Process(22, 2.)}
    child, observer = RootHandle(), module.StrictOwnedObserver()
    tree = Tree(child, retain=True)
    tree.members[(22, 2.)] = registry[22]
    result = module.cleanup_owned(child, tree, observer, True, Tree)
    assert not result['cleanup_confirmed']
    assert any(x['pid'] == 22 and x['reason'] == 'same_identity_alive'
               for x in result['cleanup_observation']['unresolved'])
    passed.append('final_alive_set_cannot_be_silenced')

    # An enumeration denial persists after the parent has gone.
    registry = {11: Process(11, 1., denied=True)}
    child, observer = RootHandle(), module.StrictOwnedObserver()
    tree = Tree(child)
    result = module.cleanup_owned(child, tree, observer, True, Tree)
    assert not registry and not result['cleanup_confirmed']
    assert any(x['action'] == 'enumerate_descendants'
               for x in result['cleanup_observation']['unresolved'])
    passed.append('historical_enumeration_denial_remains_unconfirmed')

    # A fresh reused PID must not be inserted into known-owned signalling.
    registry = {11: Process(11, 1.), 22: Process(22, 3.)}
    child, observer = RootHandle(), module.StrictOwnedObserver()
    tree = Tree(child)
    observer.remember([(22, 2.)])
    result = module.cleanup_owned(child, tree, observer, True, Tree)
    assert result['cleanup_confirmed'] and registry[22].created == 3.
    passed.append('reused_pid_is_not_signalled')

    # Successful retry/root termination cannot certify missed initial descendants.
    registry = {11: Process(11, 1.)}
    child, observer = RootHandle(), module.StrictOwnedObserver()
    result = module.cleanup_owned(child, None, observer, False, Tree)
    assert child.poll() is not None and not result['cleanup_confirmed']
    passed.append('failed_initial_tracking_stays_unconfirmed')

    # Errors in observer traversal still allow exact root-handle cleanup.
    registry = {11: Process(11, 1.)}
    child, observer = RootHandle(), module.StrictOwnedObserver()
    observer.observe = lambda: (_ for _ in ()).throw(RuntimeError('synthetic'))
    result = module.cleanup_owned(child, Tree(child), observer, True, Tree)
    assert child.poll() is not None and not result['cleanup_confirmed']
    passed.append('observation_failure_does_not_skip_root_cleanup')

print({'synthetic_no_fit_checks': len(passed), 'passed': passed,
       'real_processes_started_or_signalled': 0, 'api_calls': 0, 'model_fits': 0})
