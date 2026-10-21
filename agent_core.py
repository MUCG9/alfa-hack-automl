"""Development compatibility entry; canonical code is under src/automl."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/"src"))
from importlib import import_module
_module=import_module('automl.compat.core')
sys.modules[__name__]=_module
