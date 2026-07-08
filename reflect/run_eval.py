"""python -m reflect.run_eval — alias for eval/curve.py (the honest metric)."""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# reuse the single source of truth
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "_curve", os.path.join(_ROOT, "eval", "curve.py"))
_curve = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_curve)

if __name__ == "__main__":
    _curve.run()
