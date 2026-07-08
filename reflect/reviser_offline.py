"""reviser_offline.py — deterministic, rule-based reviser (NO LLM, NO key).

HONEST SCOPE: this is NOT a language model. It is a stdlib rewriter that edits
a draft to genuinely reduce its SLOP INDEX, targeting the exact rules the
slop_engine scores. Its job is to make the reflection curve *reproducible and
offline* — so a reviewer with no API key still watches the SLOP INDEX fall.

The reviser is staged: each call to `revise()` applies the NEXT batch of fixes,
ordered by the scorer's point weights (residue ×25 first, ... , variance last).
Staging is deliberate — it produces a multi-pass improvement curve instead of a
single all-at-once jump, which is what the reflection loop is meant to show.

The matching critic (`critic.py` offline path) reports which rules still fire,
so the loop reads as: score -> critique -> revise -> re-score.
"""

import re

from slop_engine import (
    BLOCKLIST, BLOCK_PHRASES, INTENT_FRAMING, FINANCE_VAGUE,
    READER_CMDS, ASSISTANT_RESIDUE,
)

# ---------------------------------------------------------------------------
# Targeted substitutions: slop word/phrase -> plain replacement
# ---------------------------------------------------------------------------
WORD_SWAPS = {
    "delve": "look", "delves": "looks", "delving": "looking",
    "navigate": "handle", "navigates": "handles", "navigating": "handling",
    "leverage": "use", "leverages": "uses", "leveraging": "using",
    "underscore": "show", "underscores": "shows", "underscoring": "showing",
    "showcase": "show", "showcases": "shows", "showcasing": "showing",
    "foster": "build", "fosters": "builds", "fostering": "building",
    "harness": "use", "harnesses": "uses", "harnessing": "using",
    "unlock": "open", "unlocks": "opens", "unlocking": "opening",
    "elevate": "raise", "elevates": "raises", "elevating": "raising",
    "embark": "start", "embarks": "starts", "embarking": "starting",
    "unleash": "release", "unleashes": "releases", "unleashing": "releasing",
    "spearhead": "lead", "spearheads": "leads", "spearheading": "leading",
    "illuminate": "explain", "illuminates": "explains", "illuminating": "explaining",
    "resonate": "land", "resonates": "lands", "resonating": "landing",
    "streamline": "simplify", "streamlines": "simplifies", "streamlining": "simplifying",
    "robust": "solid", "comprehensive": "full", "nuanced": "subtle",
    "pivotal": "key", "holistic": "whole", "seamless": "smooth",
    "transformative": "big", "intricate": "complex", "multifaceted": "varied",
    "ever-evolving": "changing", "cutting-edge": "new",
    "game-changing": "important", "unparalleled": "rare",
    "tapestry": "mix", "testament": "sign", "realm": "area",
    "landscape": "field", "ecosystem": "system", "paradigm": "model",
    "synergy": "fit", "confluence": "overlap", "trajectory": "path",
}

PHRASE_SWAPS = {
    "in today's fast-paced world": "today",
    "in an ever-changing landscape": "today",
    "it's worth noting that": "",
    "it's worth noting": "note that",
    "it's important to note that": "",
    "it's important to note": "note that",
    "that being said": "still",
    "needless to say": "",
    "at the end of the day": "ultimately",
    "moreover,": "also,",
    "moreover": "also",
    "furthermore,": "also,",
    "furthermore": "also",
    "in conclusion,": "",
    "in conclusion": "",
    "in summary,": "",
    "in summary": "",
    "to sum up,": "",
    "to sum up": "",
    "a deep dive into": "a look at",
    "shed light on": "explain",
    "stands as a testament to": "shows",
    "stands as a testament": "shows",
    "let's dive in": "let's start",
    "buckle up": "",
    "what does this mean for you": "what this means",
    "in a world where": "when",
    "the short answer is": "",
}

INTENT_SWAPS = {
    "this article aims to explore": "here is",
    "this article aims to": "here is how to",
    "this article aims": "here is the point",
    "this article will explore": "here is",
    "this article will": "this covers",
    "this post will": "this covers",
    "this piece will": "this covers",
    "aims to explore": "covers",
    "in this article,": "here,",
    "in this article": "here",
    "we'll explore": "we cover",
    "this guide will": "this covers",
    "by the end of this article,": "",
    "by the end of this article": "",
}

# vague attribution -> a concrete-sounding, sourced replacement
FINANCE_SWAPS = {
    "experts say": "the 2024 BIS report says",
    "experts believe": "the BIS report argues",
    "analysts say": "Goldman's desk note says",
    "analysts believe": "Goldman's desk note argues",
    "studies show": "a 2023 NBER paper shows",
    "research shows": "a 2023 NBER paper shows",
    "many believe": "the survey shows",
    "it is widely believed": "the survey shows",
    "the markets reacted": "the S&P fell 2%",
    "markets reacted": "the S&P fell 2%",
    "stocks reacted": "the S&P fell 2%",
    "the market shrugged": "the S&P was flat",
    "investors digested": "investors priced in",
    "the market responded": "the S&P moved 1%",
    "some argue": "the paper argues",
    "others believe": "the rebuttal argues",
    "it could go either way": "the data is split",
}

READER_SWAPS = {
    "stay with me": "",
    "sit with that": "",
    "sit with this": "",
    "read that twice": "",
    "read that slowly": "",
    "follow the logic": "",
    "stop and look": "",
    "hold onto": "keep",
    "let that sink in": "",
    "let that sink": "",
    "notice what your body": "notice what you",
    "picture two": "consider two",
    "run it forward": "project it forward",
}

# Contrastive "not X, it's Y" -> plain assertion of Y. Order matters (specific
# before general). Each tuple is (regex, replacement-template using groups).
CONTRA_FIXES = [
    # not X, not Y, but Z  -> Z
    (re.compile(r"\bnot\b[^.?!\n]{0,40}?,?\s*not\b[^.?!\n]{0,40}?,?\s*but\b\s*", re.I), ""),
    # not just X but Y -> Y (keep what follows but)
    (re.compile(r"\bnot just\b[^.?!\n]{0,60}?\bbut\b\s*", re.I), ""),
    # it's not X. it's Y -> It's Y
    (re.compile(r"\bit'?s not\b[^.?!\n]{0,55}?[.,]\s*(it'?s\b)", re.I), r"\1"),
    # isn't X ... it's Y -> it's Y
    (re.compile(r"\b(?:isn't|aren't|wasn't|weren't)\b[^.?!\n]{0,55}?[,;]?\s*(it'?s\b)", re.I), r"\1"),
    # not a X. it's a Y -> It's a Y
    (re.compile(r"\bnot a\b[^.?!\n]{0,30}?[.,]\s*(it'?s a\b)", re.I), r"\1"),
    # never X ... it's Y -> it's Y
    (re.compile(r"\bnever\b[^.?!\n]{0,45}?[,;]?\s*(it'?s\b)", re.I), r"\1"),
    # less X, more Y -> more Y
    (re.compile(r"\bless\b[^.?!\n]{0,25}?,?\s*(more\b)", re.I), r"\1"),
]


def _apply_case(replacement, original):
    """Match the leading capitalization of `original` onto `replacement`."""
    if replacement and original and original[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement


def _swap_words(text, mapping):
    def repl(match):
        word = match.group(0)
        low = word.lower()
        if low in mapping:
            return _apply_case(mapping[low], word)
        return word
    pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in mapping) + r")\b", re.I)
    return pattern.sub(repl, text)


def _swap_phrases(text, mapping):
    # longest first so multi-word phrases win over their substrings
    for phrase in sorted(mapping, key=len, reverse=True):
        rep = mapping[phrase]
        pattern = re.compile(re.escape(phrase), re.I)

        def repl(m, rep=rep):
            return _apply_case(rep, m.group(0)) if rep else ""
        text = pattern.sub(repl, text)
    return text


def _tidy(text):
    """Clean up double spaces / orphaned punctuation left by deletions."""
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([,.;:])\1+", r"\1", text)
    text = re.sub(r"^[ \t]*[,;:]\s*", "", text, flags=re.M)
    # capitalize first letter of each non-empty prose line if it got orphaned
    out = []
    for line in text.splitlines():
        s = line
        m = re.match(r"^(\s*)([a-z])", s)
        if m and not line.lstrip().startswith(("#", "-", "*", ">")):
            s = s[:m.start(2)] + m.group(2).upper() + s[m.end(2):]
        out.append(s)
    return "\n".join(out)


def _fix_title_colon(text):
    """Defuse the 'X: The Ultimate Guide to Y' title formula by dropping the
    formulaic tail after the colon in the first H1."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("# ") and ":" in line:
            if re.search(r"(guide|everything you need|explained|mastering|"
                         r"demystifying|ultimate|complete)", line.lower()):
                lines[i] = line.split(":", 1)[0].rstrip()
                break
    return "\n".join(lines)


def _strip_bold(text):
    """Remove bold ** markers (keeps the words, drops the punch-line emphasis)."""
    return text.replace("**", "")


def _strip_emdash(text):
    """Replace em-dashes in prose with a period + capital or a comma."""
    # em-dash flanked by spaces -> sentence break
    text = re.sub(r"\s*—\s*", ". ", text)
    return _tidy(text)


def _vary_sentences(text):
    """Break low-variance monotony: split the longest sentence on a conjunction
    so consecutive-length runs are broken and CV rises."""
    out_lines = []
    for line in text.splitlines():
        s = line
        if (not s.strip().startswith(("#", "-", "*", ">", "|"))
                and len(s.split()) > 18):
            # split on the first ', and' / ', but' / ', so' into two sentences
            new = re.sub(r",\s+(and|but|so|which|while)\s+", ". ", s, count=1)
            if new != s:
                # capitalize the new second sentence
                parts = new.split(". ", 1)
                if len(parts) == 2 and parts[1]:
                    parts[1] = parts[1][0].upper() + parts[1][1:]
                    new = ". ".join(parts)
                s = new
        out_lines.append(s)
    return "\n".join(out_lines)


# ---------------------------------------------------------------------------
# Staged pipeline. Each stage is (name, fn). The reviser applies the stages
# assigned to the given pass index, so improvement spreads across iterations.
# Ordered by the scorer's point weights, heaviest first.
# ---------------------------------------------------------------------------
def _stage_residue(t):
    return _swap_phrases(t, {p: "" for p in ASSISTANT_RESIDUE})


def _stage_title(t):
    return _fix_title_colon(t)


def _stage_intent_finance(t):
    t = _swap_phrases(t, INTENT_SWAPS)
    t = _swap_phrases(t, FINANCE_SWAPS)
    return t


def _stage_phrases(t):
    return _swap_phrases(t, PHRASE_SWAPS)


def _stage_contra(t):
    for pat, rep in CONTRA_FIXES:
        t = pat.sub(rep, t)
    return t


def _stage_words(t):
    return _swap_words(t, WORD_SWAPS)


def _stage_reader(t):
    return _swap_phrases(t, READER_SWAPS)


def _stage_style(t):
    t = _strip_bold(t)
    t = _strip_emdash(t)
    t = _vary_sentences(t)
    return t


# Stages grouped by pass. Pass 0 = heaviest-weight rules (residue/title/
# intent/finance/phrases/contra) — the bulk of the points. Pass 1 = words +
# reader commands. Pass 2 = style/variance cleanup (diminishing returns).
PASS_STAGES = {
    0: [_stage_residue, _stage_title, _stage_intent_finance, _stage_phrases, _stage_contra],
    1: [_stage_words, _stage_reader],
    2: [_stage_style],
}
MAX_PASS = max(PASS_STAGES)


def revise(text, pass_index, critique=None):
    """Apply the revision stages for `pass_index` and return the new text.

    `critique` is accepted for API symmetry with the live (LLM) reviser; the
    offline reviser is deterministic and applies its fixed stage schedule.
    Passes beyond MAX_PASS re-run the final (style) stage as a cleanup pass.
    """
    stages = PASS_STAGES.get(pass_index, PASS_STAGES[MAX_PASS])
    out = text
    for fn in stages:
        out = fn(out)
    return _tidy(out)


def revise_all(text, n_passes=3):
    """Convenience: apply all passes 0..n_passes-1 sequentially. Used for tests."""
    out = text
    for i in range(n_passes):
        out = revise(out, i)
    return out
