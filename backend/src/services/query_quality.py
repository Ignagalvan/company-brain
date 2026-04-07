"""
query_quality.py

Deterministic, LLM-free classifier for query quality.

Three states:
- "invalid"     : hard reject — skip completely, never becomes a gap
- "low_quality" : becomes a gap but displayed in a separate, collapsed section
- "valid"       : normal flow — high/medium priority gap

Rules are conservative: only reject obvious garbage, not edge-case queries.
"""

from __future__ import annotations

# ─── Public API ───────────────────────────────────────────────────────────────

INVALID = "invalid"
LOW_QUALITY = "low_quality"
VALID = "valid"


def classify_query_quality(query: str) -> str:
    """
    Classify a raw query string into "invalid", "low_quality", or "valid".

    "invalid"     → discard completely; never surfaces as a knowledge gap
    "low_quality" → surfaces as a gap in a separate collapsed UI section
    "valid"       → normal high/medium priority gap flow
    """
    trimmed = query.strip()
    no_spaces = "".join(trimmed.split()).lower()

    # ── Hard-invalid rules ────────────────────────────────────────────────────

    # Rule 1: Trivially too short after stripping
    if len(trimmed) < 3 or len(no_spaces) == 0:
        return INVALID

    # Rule 2: One character dominates > 50% of non-space content
    #         e.g. "vvvvvvvv", "oooooo"
    char_counts: dict[str, int] = {}
    for c in no_spaces:
        char_counts[c] = char_counts.get(c, 0) + 1
    max_count = max(char_counts.values())
    if max_count / len(no_spaces) > 0.5:
        return INVALID

    # Rule 3: Single word, 5–30 chars, ≤ 4 distinct chars — keyboard mashing
    #         e.g. "asdfasdf" (a,s,d,f = 4), "hooolaaa" (h,o,l,a = 4)
    words = trimmed.split()
    if len(words) == 1 and 5 <= len(no_spaces) <= 30 and len(set(no_spaces)) <= 4:
        return INVALID

    # Rule 4: Any individual word exceeds 30 chars — garbage / repeated chars with spaces
    if any(len(w) > 30 for w in words):
        return INVALID

    # ── Low-quality rules ─────────────────────────────────────────────────────

    # Rule 5: Very short trimmed query — incomplete, greetings, filler
    #         e.g. "hola", "test", "ok", "¿?", "hi"
    if len(trimmed) <= 5:
        return LOW_QUALITY

    # Rule 6: No alphabetic characters at all — pure symbols, numbers, punctuation
    #         e.g. "12345", "¿¿??", "---"
    if not any(c.isalpha() for c in no_spaces):
        return LOW_QUALITY

    return VALID
