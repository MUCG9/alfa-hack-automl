"""Standard positional fixed-recipe release entry; no research flags or JSON."""
import time
_ORIGINAL_ORIGIN = (time.time(), time.monotonic())
from automl_release_bootstrap import main
if __name__ == "__main__": raise SystemExit(main(origin=_ORIGINAL_ORIGIN))
