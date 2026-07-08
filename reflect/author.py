"""author.py — the draft/revise step.

OFFLINE: delegates to the deterministic `reviser_offline` (no LLM, no key).
LIVE: gated on ANTHROPIC_API_KEY; lazy-imports the Anthropic SDK and asks Claude
(claude-haiku-4-5-20251001) to rewrite the draft given the critic's feedback.
Never imported on the offline path.
"""

import os

from . import reviser_offline

MODEL = "claude-haiku-4-5-20251001"


def revise_offline(text, pass_index, critique=None):
    """Deterministic stdlib revision for the given pass index."""
    return reviser_offline.revise(text, pass_index, critique=critique)


def revise_live(draft, critique):
    """LIVE revision via Claude. Lazy-imports anthropic; requires ANTHROPIC_API_KEY."""
    import anthropic  # lazy: never imported on the offline path
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=(
            "You are a writer rewriting your own draft to remove AI-slop tells. "
            "Apply the editor's critique. Keep the meaning and the markdown "
            "structure. Use plain words, vary sentence length, cite concretely. "
            "Return ONLY the rewritten draft."
        ),
        messages=[{
            "role": "user",
            "content": f"EDITOR CRITIQUE:\n{critique}\n\nDRAFT:\n{draft}\n\nRewrite:",
        }],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
    usage = {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens}
    return text.strip(), usage
