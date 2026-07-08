"""app.py — reflect-revise Streamlit demo.

Pick a seed draft, run the reflection loop, and watch the SLOP INDEX fall across
passes on a live curve, with side-by-side draft diffs. Offline by default
(no key); a sidebar toggle enables LIVE mode if ANTHROPIC_API_KEY is set.

Run:  streamlit run app.py
"""

import difflib
import os
import sys

import streamlit as st

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from reflect.loop import run_reflection, THRESHOLD, MIN_DELTA, MAX_ITERS  # noqa: E402

SEED_DIR = os.path.join(_ROOT, "data", "seed_drafts")

st.set_page_config(page_title="reflect-revise", page_icon="🔁", layout="wide")

st.title("reflect-revise")
st.caption("An agent that critiques itself — and proves it got better. "
           "The SLOP INDEX (lower is better) gates the loop.")


def load_seeds():
    if not os.path.isdir(SEED_DIR):
        return {}
    return {
        f: open(os.path.join(SEED_DIR, f), encoding="utf-8").read()
        for f in sorted(os.listdir(SEED_DIR)) if f.endswith(".md")
    }


seeds = load_seeds()

with st.sidebar:
    st.header("Run")
    seed_name = st.selectbox("Seed draft", list(seeds.keys()))
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    mode = st.radio(
        "Mode",
        ["offline (deterministic, no key)", "live (Claude author+critic)"],
        index=0,
        help="Offline = stdlib rule-based reviser, fully reproducible. "
             "Live = Claude haiku author+critic (needs ANTHROPIC_API_KEY).",
    )
    live = mode.startswith("live")
    if live and not has_key:
        st.warning("ANTHROPIC_API_KEY not set — live mode will fail. "
                   "Falling back to offline is recommended.")
    st.markdown("---")
    st.markdown(
        f"**Stop conditions**\n\n"
        f"- threshold: slop < {THRESHOLD}\n"
        f"- no-progress: |delta| < {MIN_DELTA}\n"
        f"- budget: max {MAX_ITERS} revisions"
    )
    run_btn = st.button("Run reflection loop", type="primary")

if not seeds:
    st.error("No seed drafts found in data/seed_drafts/.")
    st.stop()

seed_text = seeds[seed_name]

st.subheader("Seed draft")
with st.expander("Show seed text", expanded=False):
    st.code(seed_text, language="markdown")

if run_btn:
    with st.spinner("Reflecting (draft -> score -> critique -> revise -> re-score)..."):
        res = run_reflection(seed_text, mode="live" if live else "offline")

    curve = res["curve"]
    its = res["iterations"]

    # --- headline row -----------------------------------------------------
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Initial SLOP", curve[0])
    c2.metric("Final SLOP", curve[-1], delta=res["total_delta"],
              delta_color="inverse")
    c3.metric("Revisions", res["n_revisions"])
    c4.metric("Stop reason", res["stop_reason"])

    # --- the live curve ---------------------------------------------------
    st.subheader("Improvement curve — SLOP INDEX per pass")
    st.line_chart(
        {"SLOP INDEX": curve, "threshold": [THRESHOLD] * len(curve)},
    )

    # cost / latency
    cc1, cc2 = st.columns(2)
    cc1.metric("Est. cost", f"${res['total_cost_usd']:.4f}")
    cc2.metric("Est. latency", f"{res['total_latency_s']:.2f}s")

    if res["improved"] and curve[-1] < THRESHOLD:
        st.success(f"Reflection drove SLOP {curve[0]} -> {curve[-1]} "
                   f"(below CLEAN threshold {THRESHOLD}) in {res['n_revisions']} pass(es).")
    elif res["stop_reason"] == "no_progress":
        st.info(f"Halted on **no-progress**: the loop is gated on measured gain, "
                f"so it stopped at SLOP {curve[-1]} rather than burning budget. "
                f"This is the discipline — reflection isn't free.")
    else:
        st.info(f"Budget exhausted at SLOP {curve[-1]}.")

    # --- per-pass detail + critiques --------------------------------------
    st.subheader("Per-pass log")
    for it in its:
        d = it["delta"]
        dtxt = "—" if d is None else f"{d:+d}"
        with st.expander(
            f"Pass {it['iteration']} — SLOP {it['slop_index']} "
            f"(delta {dtxt}) — {it['verdict']}",
            expanded=(it["iteration"] in (0, len(its) - 1)),
        ):
            st.markdown(f"**Critique:** {it['critique']}")

    # --- side-by-side diff: seed vs final --------------------------------
    st.subheader("Side-by-side: seed vs final revision")
    left, right = st.columns(2)
    with left:
        st.markdown(f"**Seed** (SLOP {curve[0]})")
        st.code(its[0]["draft"], language="markdown")
    with right:
        st.markdown(f"**Final** (SLOP {curve[-1]})")
        st.code(its[-1]["draft"], language="markdown")

    # unified diff
    st.subheader("Unified diff (seed -> final)")
    diff = difflib.unified_diff(
        its[0]["draft"].splitlines(),
        its[-1]["draft"].splitlines(),
        fromfile="seed", tofile="final", lineterm="",
    )
    st.code("\n".join(diff) or "(no change)", language="diff")
else:
    st.info("Pick a seed draft and click **Run reflection loop** in the sidebar.")

st.markdown("---")
st.caption(
    "Sibling project: **slop-scanner** (the scorer is vendored from it). "
    "reflect-revise autonomously reproduces the 81→3 story — the SLOP INDEX "
    "gates the loop.  •  Christian Macion — AI / Agent Engineer"
)
