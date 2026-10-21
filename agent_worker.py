"""Development compatibility entry; canonical code is under src/automl."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/"src"))
from importlib import import_module
_module=import_module('automl.execution.worker')
if __name__=="__main__":
    import json
    job=json.loads(Path(sys.argv[1]).read_text())
    try: _module.run(job)
    except Exception as exc:
        _module.atomic_json(Path(job["output_dir"])/"result.json",{"status":"error","error":f"{type(exc).__name__}: {exc}"})
        raise
else: sys.modules[__name__]=_module
