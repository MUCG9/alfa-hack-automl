from pathlib import Path
import importlib.abc
import importlib.util
import json
import runpy
import sys
sys.dont_write_bytecode = True
DENIED = {'automl', 'agent', 'lightgbm', 'catboost', 'xgboost', 'optuna',
          'torch', 'tensorflow', 'openai', 'litellm', 'requests', 'httpx',
          'aiohttp', 'urllib3', 'websocket', 'websockets'}
class NoRuntimeOrNetwork(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split('.', 1)[0]
        if root in DENIED or root.startswith(('automl_', 'agent_')):
            print(json.dumps({'tripwire': 'import_root_denied', 'root_code': root if root in DENIED else 'automl_or_agent_prefix'}), flush=True)
            raise RuntimeError('nofit_model_runtime_or_network_import_forbidden')
        return None
def audit(event, args):
    if event.startswith('socket.') or event in {'subprocess.Popen', 'os.system',
            'os.exec', 'os.posix_spawn', 'os.fork', 'os.forkpty'}:
        code = 'socket_event' if event.startswith('socket.') else 'process_event'
        exact = event if event in {'socket.__new__', 'socket.gethostname', 'socket.getaddrinfo', 'socket.connect', 'socket.bind', 'subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn', 'os.fork', 'os.forkpty'} else code
        print(json.dumps({'tripwire': code, 'event_code': exact}), flush=True)
        raise RuntimeError('nofit_network_or_process_operation_forbidden')
    if event == 'open' and args and isinstance(args[0], (str, bytes)):
        path = Path(args[0].decode() if isinstance(args[0], bytes) else args[0])
        if any(p.lower() == 'private' or p.lower().startswith('run-budget-') for p in path.parts):
            print(json.dumps({'tripwire': 'private_read_denied'}), flush=True)
            raise RuntimeError('nofit_private_config_or_ledger_read_forbidden')
sys.meta_path.insert(0, NoRuntimeOrNetwork())
sys.addaudithook(audit)

versions = {}
phase = 'numpy_import'
try:
    import numpy
    versions['numpy'] = numpy.__version__
    phase = 'pandas_import'
    import pandas
    versions['pandas'] = pandas.__version__
    phase = 'psutil_import'
    import psutil
    versions['psutil'] = psutil.__version__
    phase = 'sklearn_import'
    import sklearn
    versions['sklearn'] = sklearn.__version__
    phase = 'sklearn_model_selection_import'
    from sklearn.model_selection import StratifiedGroupKFold, train_test_split
except BaseException as exc:
    print(json.dumps({'status': 'import_only_failed', 'phase': phase,
          'exception_code': type(exc).__name__, 'versions': versions}), flush=True)
    raise SystemExit(2)
print(json.dumps({'status': 'import_only_passed', 'versions': versions}), flush=True)
