import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

# Each group: terms that are semantically equivalent for retrieval purposes.
# Order matters — first match in a group triggers replacements with the others.
_SYNONYM_GROUPS: list[list[str]] = [
    ["cuánto cuesta", "precio", "costo"],
    ["teléfono", "contacto", "número"],
    ["servicio", "plataforma", "sistema"],
]


def _normalize(text: str) -> str:
    """Lowercase and strip accents for matching purposes."""
    return unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()


# Fixes for awkward phrases produced after noun replacement of verb phrases.
# e.g. "precio el servicio" → "precio del servicio"
_PHRASE_FIXES: list[tuple[str, str]] = [
    (r"\bprecio\s+el\b", "precio del"),
    (r"\bcosto\s+el\b", "costo del"),
    (r"\bprecio\s+la\b", "precio de la"),
    (r"\bcosto\s+la\b", "costo de la"),
]


def _fix_phrase(text: str) -> str:
    for pattern, replacement in _PHRASE_FIXES:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _generate_variants(query: str) -> list[str]:
    q_norm = _normalize(query)
    variants: list[str] = []

    for group in _SYNONYM_GROUPS:
        matched_term = next((t for t in group if _normalize(t) in q_norm), None)
        if matched_term is None:
            continue
        # Locate span in normalized query — positions align with original (NFC accents = 1 char each)
        match = re.search(re.escape(_normalize(matched_term)), q_norm, flags=re.IGNORECASE)
        if not match:
            continue
        start, end = match.span()

        for replacement in group:
            if replacement == matched_term:
                continue
            variant = _fix_phrase(query[:start] + replacement + query[end:])
            if variant != query and variant not in variants:
                variants.append(variant)
            if len(variants) == 2:
                return variants

    return variants


async def expand_query(query: str) -> list[str]:
    variants = _generate_variants(query)
    logger.debug("Query expansion: original=%r variants=%r", query, variants)
    return [query] + variants
