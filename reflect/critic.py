"""critic.py — the self-critique step.

OFFLINE: reads the scorer's flagged rules and emits a concrete, deterministic
critique ("3 blocklist words still fire: delve, robust, ...; 2 contrastive
'not X it's Y' patterns; ..."). No LLM, no key.

LIVE: gated on ANTHROPIC_API_KEY; lazy-imports the Anthropic SDK and asks Claude
(claude-haiku-4-5-20251001) to critique the draft as an editor. Never imported
on the offline path.
"""

import os

MODEL = "claude-haiku-4-5-20251001"

# Map each scorer hit-group / metric to a plain editorial instruction.
_HIT_ADVICE = {
    "Assistant residue": "delete chatbot residue (e.g. 'certainly!', 'here's a breakdown')",
    "Title colon-formula": "drop the 'X: The Ultimate Guide' title formula",
    "Intent framing": "stop announcing intent ('this article will explore') — just assert",
    "Finance vagueness / unattributed": "replace vague attributions ('experts say') with a named source",
    "Blocklist phrases": "cut filler phrases ('moreover', \"it's worth noting\")",
    "Contrastive / False Reframe": "break the 'not X, it's Y' reframe into a plain statement",
    "Blocklist words": "swap AI-tell words (delve/robust/tapestry) for plain ones",
    "Reader commands": "remove reader commands ('sit with this', 'stay with me')",
}


def critique_offline(score_dict):
    """Build a deterministic critique string from a scorer result.

    Returns (critique_text, n_issues). Ordered by the scorer's point weights so
    the critique reads like a prioritized editorial pass.
    """
    hits = score_dict.get("hits", {})
    m = score_dict.get("metrics", {})
    issues = []

    # Priority order mirrors the slop_index weights.
    order = [
        "Assistant residue", "Title colon-formula", "Intent framing",
        "Finance vagueness / unattributed", "Blocklist phrases",
        "Contrastive / False Reframe", "Blocklist words", "Reader commands",
    ]
    for group in order:
        if group == "Title colon-formula":
            if m.get("title_colon"):
                issues.append(_HIT_ADVICE[group])
            continue
        rows = hits.get(group)
        if rows:
            sample = ", ".join(sorted({r[1] for r in rows})[:4])
            issues.append(f"{_HIT_ADVICE[group]} [{len(rows)}: {sample}]")

    # Style flags (no hit-rows, read from metrics).
    if m.get("cv") and m["cv"] < 0.4:
        issues.append("vary sentence length — variance is too uniform (CV<0.4)")
    if m.get("longest_run", 0) > 3:
        issues.append(f"break the monotony run of {m['longest_run']} same-length sentences")
    if m.get("part_pct", 0) > 6:
        issues.append(f"reduce -ing sentence openers ({m['part_pct']}%)")
    if m.get("bold_per1k", 0) > 5:
        issues.append("cut bolded punch-lines")
    if m.get("emdash_per1k", 0) > 5:
        issues.append("reduce em-dashes")

    if not issues:
        return "No issues found — the draft is clean.", 0

    body = "; ".join(issues)
    return f"SLOP INDEX {score_dict['slop_index']} ({score_dict['verdict']}). Fix: {body}.", len(issues)


def critique_live(draft, score_dict):
    """LIVE critique via Claude. Lazy-imports anthropic; requires ANTHROPIC_API_KEY."""
    import anthropic  # lazy: never imported on the offline path
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    rules = critique_offline(score_dict)[0]
    msg = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=(
            "You are a ruthless copy editor. The draft scores poorly on an "
            "AI-slop linter. Give a SHORT, concrete critique: list the specific "
            "phrases to cut or rewrite. Do not rewrite the draft yourself."
        ),
        messages=[{
            "role": "user",
            "content": f"Linter says: {rules}\n\nDRAFT:\n{draft}\n\nCritique (bullet list):",
        }],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    usage = {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens}
    return text, usage
