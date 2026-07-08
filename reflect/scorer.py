"""scorer.py — thin wrapper over the vendored slop_engine.

The reflection loop's quality metric is the SLOP INDEX (lower is better). This
module is the only place the loop touches the scorer, so swapping the judge is
a one-file change. Pure stdlib, deterministic, fully offline.
"""

import sys
import os

# Make the repo root importable so `slop_engine` resolves whether this is run
# as a module (`python -m reflect.run_eval`) or as a script (`python eval/curve.py`).
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import slop_engine  # noqa: E402


def score(text):
    """Return the full structured score dict for `text`."""
    return slop_engine.score_text(text)


def slop_index(text):
    """Return just the scalar SLOP INDEX (lower is better)."""
    return slop_engine.score_text(text)["slop_index"]
