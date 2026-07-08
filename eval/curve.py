"""eval/curve.py — the honest metric, one CLI command.

Runs the reflection loop (OFFLINE, no key) over every seed draft in
data/seed_drafts/, prints the per-draft improvement curve + deltas, aggregates
the headline metrics, NAMES the negative cases, and writes scorecard.json.

Run:
    python3 eval/curve.py
    python3 -m reflect.run_eval     # same thing

Pure stdlib. Deterministic. No network.
"""

import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from reflect.loop import run_reflection  # noqa: E402

SEED_DIR = os.path.join(_ROOT, "data", "seed_drafts")
RUNS_DIR = os.path.join(_ROOT, "runs", "recorded")
SCORECARD = os.path.join(_ROOT, "scorecard.json")


def _load_seeds():
    files = sorted(f for f in os.listdir(SEED_DIR) if f.endswith(".md"))
    return [(f, open(os.path.join(SEED_DIR, f), encoding="utf-8").read()) for f in files]


def _curve_str(curve):
    return " -> ".join(str(c) for c in curve)


def run():
    seeds = _load_seeds()
    os.makedirs(RUNS_DIR, exist_ok=True)

    results = []
    print("=" * 72)
    print("reflect-revise — OFFLINE reflection loop over seed drafts")
    print("  metric: SLOP INDEX (slop_engine, lower is better)")
    print("  stop:   slop<15 (threshold) | delta<2 (no_progress) | 3 iters (budget)")
    print("=" * 72)

    for fname, text in seeds:
        res = run_reflection(text, mode="offline")
        res["seed"] = fname
        results.append(res)

        # record the run (strip drafts? keep them — useful for the app/audit)
        out_path = os.path.join(RUNS_DIR, fname.replace(".md", ".json"))
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2)

        deltas = [r["delta"] for r in res["iterations"][1:]]
        delta_str = ", ".join(f"{d:+d}" for d in deltas) if deltas else "(none)"
        print(f"\n{fname}")
        print(f"  curve  : {_curve_str(res['curve'])}   (SLOP INDEX per pass)")
        print(f"  deltas : {delta_str}")
        print(f"  result : {res['initial_slop']} -> {res['final_slop']} "
              f"in {res['n_revisions']} pass(es), stop={res['stop_reason']}, "
              f"improved={res['improved']}")
        print(f"  cost   : ${res['total_cost_usd']:.4f} est, "
              f"{res['total_latency_s']:.2f}s est")

    scorecard = _aggregate(results)
    _print_summary(scorecard)

    with open(SCORECARD, "w", encoding="utf-8") as fh:
        json.dump(scorecard, fh, indent=2)
    print(f"\nWrote scorecard.json and {len(results)} run records to runs/recorded/")
    return scorecard


def _aggregate(results):
    n = len(results)
    improved = [r for r in results if r["improved"]]
    reached = [r for r in results if r["stop_reason"] == "threshold"]
    halted = [r for r in results if r["stop_reason"] == "no_progress"]
    maxed = [r for r in results if r["stop_reason"] == "max_iters"]

    init_mean = round(sum(r["initial_slop"] for r in results) / n, 1)
    final_mean = round(sum(r["final_slop"] for r in results) / n, 1)

    # avg revisions among drafts that reached threshold
    avg_iters_to_thresh = (
        round(sum(r["n_revisions"] for r in reached) / len(reached), 2)
        if reached else None
    )

    # cost per quality point (per unit of slop removed), across drafts that improved
    total_cost = sum(r["total_cost_usd"] for r in improved)
    total_points = sum(r["initial_slop"] - r["final_slop"] for r in improved)
    cost_per_point = round(total_cost / total_points, 6) if total_points else None
    total_latency = sum(r["total_latency_s"] for r in improved)
    latency_per_point = round(total_latency / total_points, 4) if total_points else None

    # negative cases: no improvement, or stalled below threshold, or a pass that hurt
    negatives = []
    for r in results:
        reasons = []
        if not r["improved"]:
            reasons.append("no net improvement")
        if r["stop_reason"] == "no_progress" and r["final_slop"] >= r["threshold"]:
            reasons.append(f"halted on no-progress still above threshold "
                           f"(final {r['final_slop']})")
        if r["stop_reason"] == "max_iters" and r["final_slop"] >= r["threshold"]:
            reasons.append(f"exhausted budget still above threshold "
                           f"(final {r['final_slop']})")
        # any single pass that made it worse
        bad_passes = [it["iteration"] for it in r["iterations"][1:] if it["delta"] is not None and it["delta"] > 0]
        if bad_passes:
            reasons.append(f"pass(es) {bad_passes} did not help (delta >= 0)")
        if reasons:
            negatives.append({"seed": r["seed"], "reasons": reasons,
                              "curve": r["curve"], "stop_reason": r["stop_reason"]})

    return {
        "n_drafts": n,
        "mode": "offline",
        "threshold": results[0]["threshold"],
        "min_delta": results[0]["min_delta"],
        "max_iters": results[0]["max_iters"],
        "mean_initial_slop": init_mean,
        "mean_final_slop": final_mean,
        "pct_improved": round(100 * len(improved) / n, 1),
        "n_improved": len(improved),
        "n_reached_threshold": len(reached),
        "no_progress_halt_rate": round(100 * len(halted) / n, 1),
        "n_no_progress_halt": len(halted),
        "n_max_iters": len(maxed),
        "avg_revisions_to_threshold": avg_iters_to_thresh,
        "est_cost_per_quality_point_usd": cost_per_point,
        "est_latency_per_quality_point_s": latency_per_point,
        "negative_cases": negatives,
        "per_draft": [
            {
                "seed": r["seed"], "curve": r["curve"],
                "initial_slop": r["initial_slop"], "final_slop": r["final_slop"],
                "n_revisions": r["n_revisions"], "stop_reason": r["stop_reason"],
                "improved": r["improved"],
                "est_cost_usd": r["total_cost_usd"],
                "est_latency_s": r["total_latency_s"],
            }
            for r in results
        ],
    }


def _print_summary(s):
    print("\n" + "=" * 72)
    print("HEADLINE METRIC (offline, deterministic)")
    print("=" * 72)
    print(f"  drafts                     : {s['n_drafts']}")
    print(f"  mean SLOP INDEX            : {s['mean_initial_slop']} -> {s['mean_final_slop']}")
    print(f"  reflection improved        : {s['n_improved']}/{s['n_drafts']} "
          f"({s['pct_improved']}%)")
    print(f"  reached CLEAN threshold    : {s['n_reached_threshold']}/{s['n_drafts']}")
    print(f"  no-progress halt rate      : {s['no_progress_halt_rate']}% "
          f"({s['n_no_progress_halt']}/{s['n_drafts']})")
    print(f"  avg revisions to threshold : {s['avg_revisions_to_threshold']}")
    print(f"  est cost / quality point   : ${s['est_cost_per_quality_point_usd']}")
    print(f"  est latency / quality point: {s['est_latency_per_quality_point_s']}s")
    print("\n  NEGATIVE / HONEST CASES:")
    if not s["negative_cases"]:
        print("    (none — every draft improved and reached threshold)")
    for nc in s["negative_cases"]:
        print(f"    - {nc['seed']} [{nc['stop_reason']}]: {'; '.join(nc['reasons'])}")
        print(f"        curve {' -> '.join(str(c) for c in nc['curve'])}")


if __name__ == "__main__":
    run()
