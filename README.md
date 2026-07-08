# reflect-revise

**An agent that critiques itself — and proves it got better.**

A reflection-loop agent: it **drafts → scores → self-critiques → revises** over
up to 3 passes, logging the quality-score **delta** each iteration, and **halts
on measured gain** (threshold reached / no-progress / max iterations). The
quality metric is the **SLOP INDEX** from the sibling
[slop-scanner](../../05_live_demo/slop-scanner) (lower is better), vendored here
as `slop_engine.py`. reflect-revise **autonomously reproduces the slop-scanner's
81→3 story** — the number gates the loop.

## TL;DR / headline metric

Offline, deterministic, over the 4 in-repo seed drafts:

> **mean SLOP 127.5 → 14.0** · reflection improved **3/4 drafts** ·
> **3/4 reached the CLEAN threshold (<15)** · **halts on no-progress (1/4)** ·
> avg **1.67 revisions** to threshold.

Per-draft curves (SLOP INDEX per pass):

| seed | curve | stop | improved |
|---|---|---|---|
| `01_fintech_heavy.md` | **239 → 98 → 5** | threshold | ✅ |
| `02_market_recap_heavy.md` | **214 → 66 → 0** | threshold | ✅ |
| `03_devtools_medium.md` | 18 → 12 | threshold | ✅ |
| `04_uniform_halt.md` | 39 → 39 | **no_progress** | ❌ (honest halt) |

The heavy drafts show a clear multi-pass drop; `04` is the deliberate
**diminishing-returns / halt** case (see *Honest scope* below).

## How a reviewer clicks it

```bash
# 1) the honest metric — one command, no key, pure stdlib
python3 eval/curve.py            # prints curves + deltas, writes scorecard.json
#   (equivalently: python3 -m reflect.run_eval)

# 2) the interactive demo
pip install -r requirements.txt
streamlit run app.py             # pick a seed, watch the SLOP INDEX fall live
```

A reviewer with **no API key** still gets the full curve and the live app — the
offline path never touches the network.

## What it does (the loop)

```
seed draft
   │  score (slop_engine → SLOP INDEX)
   ▼
 above threshold? ──no──▶ STOP (threshold)
   │ yes
   ▼
 critique  (which scorer rules still fire)
   ▼
 revise    (edit the draft to clear those rules)
   ▼
 re-score → delta vs previous pass
   ▼
 delta too small? ──yes──▶ STOP (no_progress)   ◀── the discipline
 3 passes used?   ──yes──▶ STOP (max_iters)
   └── else loop
```

Each iteration logs `slop_index`, the **delta**, and an est. **cost/latency**,
so the eval can report **cost per quality point**.

## Offline vs live

| | **offline** (default) | **live** |
|---|---|---|
| author + critic | deterministic, rule-based **stdlib** | Claude `claude-haiku-4-5-20251001` |
| key | **none** | `ANTHROPIC_API_KEY` |
| network | none | Anthropic API |
| reproducible | yes (the curve is fixed) | no (model output varies) |
| imports `anthropic`? | **never** | lazy, gated on the key |

- **Offline** is what makes the curve **reproducible and reviewable with no
  key**. Recorded runs land in `runs/recorded/*.json`.
- **Live** uses Claude in two roles — a copy-editor **critic** and a writer
  **author** — lazy-imported only when `ANTHROPIC_API_KEY` is set. The loop,
  stop conditions, scorer, and metrics are identical across modes; only the
  author/critic implementation swaps.

## Honest scope

- **The offline reviser is a deterministic rule-based editor, not an LLM.** It
  edits the draft to clear the exact rules `slop_engine` scores (swaps blocklist
  words/phrases, breaks `not X, it's Y` contrastive patterns, drops chatbot
  residue, replaces vague attributions with named sources, varies sentence
  length). Its job is to make the improvement **curve reproducible offline** —
  not to write beautifully. The revised prose is sometimes grammatically rough
  (e.g. an orphaned fragment after a deletion); the SLOP INDEX genuinely drops,
  which is the property being demonstrated. **Live mode uses Claude** for prose
  quality.
- **The point is the DISCIPLINE, not the rewriter.** Reflection isn't free —
  every pass costs tokens/latency — so the loop is **gated on measured gain**.
  It stops the moment a pass stops paying for itself (`no_progress`) instead of
  grinding to the iteration cap.
- **Negative cases (named, not hidden):**
  - `04_uniform_halt.md` — slop is **structural** (uniform sentence length,
    monotony run), which the early word/phrase passes don't touch, so the loop
    correctly sees a zero delta and **halts on no-progress at SLOP 39**, still
    above threshold. A real "reflection didn't help here" result.
  - `03_devtools_medium.md` — only a small amount of slop to remove (18 → 12);
    reflection helps but the headline drop is modest. Not every draft is an
    81→3 hero.
- Offline cost/latency are **synthetic deterministic estimates** (so
  cost-per-quality-point is reproducible); live cost/latency come from real
  token usage and wall-clock.

## Layout

```
reflect-revise/
├── app.py                      # Streamlit demo (curve + side-by-side diffs)
├── slop_engine.py              # vendored scorer (the JUDGE; lower = better)
├── reflect/
│   ├── loop.py                 # the reflection loop + stop conditions + cost
│   ├── scorer.py               # thin wrapper over slop_engine
│   ├── critic.py               # self-critique (offline rules / live Claude)
│   ├── author.py               # revise step (offline reviser / live Claude)
│   ├── reviser_offline.py      # deterministic stdlib reviser (no key)
│   └── run_eval.py             # `python -m reflect.run_eval`
├── eval/curve.py               # honest metric → prints curve + scorecard.json
├── data/seed_drafts/*.md       # 4 heavy-slop seed drafts
├── runs/recorded/*.json        # recorded offline runs
├── scorecard.json              # written by the eval
├── requirements.txt
└── .streamlit/config.toml
```

## Deploy (Streamlit Community Cloud)

Point Streamlit Cloud at this repo with `app.py` as the entrypoint. It runs
**offline** out of the box (no secrets). To enable live mode, add
`ANTHROPIC_API_KEY` to the app's Secrets.

---

One of five sibling projects in **Christian Macion**'s AI / Agent Engineer
portfolio. Sibling: **slop-scanner** — reflect-revise vendors its scorer and
autonomously reproduces its 81→3 story; the number gates the loop.

*Christian Macion — AI / Agent Engineer.*
