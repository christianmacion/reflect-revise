"""loop.py — the reflection loop: draft -> score -> critique -> revise -> re-score.

The SLOP INDEX (from slop_engine, lower is better) is the quality metric and it
GATES the loop. Reflection is not free, so the loop is disciplined:

STOP CONDITIONS (whichever fires first):
  1. threshold reached  : slop_index < THRESHOLD            -> "threshold"
  2. no progress        : improvement < MIN_DELTA            -> "no_progress"
  3. budget exhausted   : MAX_ITERS revisions completed      -> "max_iters"

Each iteration logs slop_index, the score DELTA vs the previous pass, and an
est. cost/latency. Offline cost/latency are deterministic synthetic estimates
(so the curve and the cost-per-quality-point metric are reproducible with no
key); live cost/latency come from real token usage + wall-clock.

Pure stdlib on the offline path (no anthropic import).
"""

import time

from . import author, critic
from .scorer import score as score_text

# --- Tunables (the discipline knobs) --------------------------------------
THRESHOLD = 15      # CLEAN tier in slop_engine; loop's success target
MIN_DELTA = 2       # below this much improvement we declare "no progress"
MAX_ITERS = 3       # hard budget: at most 3 revision passes

# Synthetic offline cost model (so cost-per-quality-point is reproducible).
# Mirrors the order of magnitude of a haiku author+critic round-trip.
_OFFLINE_COST_USD = 0.0009     # est. $/iteration (author+critic tokens)
_OFFLINE_LATENCY_S = 1.4       # est. wall-seconds/iteration


def _iter_record(i, slop, delta, verdict, critique, cost, latency, draft):
    return {
        "iteration": i,
        "slop_index": slop,
        "delta": delta,                # negative = improved (slop fell)
        "verdict": verdict,
        "critique": critique,
        "est_cost_usd": round(cost, 6),
        "est_latency_s": round(latency, 3),
        "draft": draft,
    }


def run_reflection(seed_text, mode="offline", threshold=THRESHOLD,
                   min_delta=MIN_DELTA, max_iters=MAX_ITERS):
    """Run the reflection loop over a single seed draft.

    Returns a dict:
      {mode, threshold, min_delta, max_iters, stop_reason,
       initial_slop, final_slop, iterations:[...], curve:[slop per pass],
       total_cost_usd, total_latency_s}
    The `iterations` list includes the initial draft as iteration 0 (no revision).
    """
    live = (mode == "live")

    # --- iteration 0: the raw seed draft, scored, not yet revised ---------
    current = seed_text
    sc = score_text(current)
    crit, _ = critic.critique_offline(sc)
    records = [_iter_record(0, sc["slop_index"], None, sc["verdict"], crit, 0.0, 0.0, current)]
    curve = [sc["slop_index"]]
    total_cost = 0.0
    total_latency = 0.0
    stop_reason = "max_iters"

    if sc["slop_index"] < threshold:
        return _finish(mode, threshold, min_delta, max_iters, "threshold",
                       records, curve, total_cost, total_latency)

    prev_slop = sc["slop_index"]

    for i in range(1, max_iters + 1):
        t0 = time.time()

        # --- critique the current draft (the self-reflection step) -------
        if live:
            crit_text, crit_usage = critic.critique_live(current, sc)
        else:
            crit_text, _ = critic.critique_offline(sc)
            crit_usage = None

        # --- revise -------------------------------------------------------
        if live:
            current, rev_usage = author.revise_live(current, crit_text)
            cost = _live_cost(crit_usage, rev_usage)
            latency = time.time() - t0
        else:
            current = author.revise_offline(current, pass_index=i - 1, critique=crit_text)
            cost = _OFFLINE_COST_USD
            latency = _OFFLINE_LATENCY_S

        # --- re-score -----------------------------------------------------
        sc = score_text(current)
        slop = sc["slop_index"]
        delta = slop - prev_slop          # negative = improvement
        next_crit, _ = critic.critique_offline(sc)

        total_cost += cost
        total_latency += latency
        records.append(_iter_record(i, slop, delta, sc["verdict"], next_crit,
                                    cost, latency, current))
        curve.append(slop)

        # --- stop conditions ---------------------------------------------
        if slop < threshold:
            stop_reason = "threshold"
            break
        if abs(delta) < min_delta or delta >= 0:
            # no meaningful gain (or it got worse) -> halt, don't burn budget
            stop_reason = "no_progress"
            break
        prev_slop = slop
    else:
        stop_reason = "max_iters"

    return _finish(mode, threshold, min_delta, max_iters, stop_reason,
                   records, curve, total_cost, total_latency)


def _finish(mode, threshold, min_delta, max_iters, stop_reason,
            records, curve, total_cost, total_latency):
    return {
        "mode": mode,
        "threshold": threshold,
        "min_delta": min_delta,
        "max_iters": max_iters,
        "stop_reason": stop_reason,
        "initial_slop": curve[0],
        "final_slop": curve[-1],
        "total_delta": curve[-1] - curve[0],
        "n_revisions": len(records) - 1,
        "improved": curve[-1] < curve[0],
        "iterations": records,
        "curve": curve,
        "total_cost_usd": round(total_cost, 6),
        "total_latency_s": round(total_latency, 3),
    }


# Haiku 4.5 pricing (USD per token): $1.00 / MTok in, $5.00 / MTok out.
_IN_RATE = 1.00 / 1_000_000
_OUT_RATE = 5.00 / 1_000_000


def _live_cost(crit_usage, rev_usage):
    cost = 0.0
    for u in (crit_usage, rev_usage):
        if u:
            cost += u["input_tokens"] * _IN_RATE + u["output_tokens"] * _OUT_RATE
    return cost
