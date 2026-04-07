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
    ["medios de pago", "formas de pago", "metodos de pago"],
    ["email", "correo", "mail"],
    ["soporte", "ayuda"],
    ["plan profesional", "plan pro"],
    ["confidencialidad", "confidencial"],
    ["evalua el desempeno", "evaluacion de desempeno", "evaluaciones de desempeno"],
    ["desempeno", "evaluacion"],
    ["renunciar", "renuncia"],
    ["aviso", "anticipacion"],
]


def _normalize(text: str) -> str:
    """Lowercase and strip accents for matching purposes."""
    return unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()


def _normalize_with_index_map(text: str) -> tuple[str, list[int]]:
    """
    Returns (normalized_text, index_map) where each char in normalized_text maps
    back to the original string index that produced it.
    """
    normalized_chars: list[str] = []
    index_map: list[int] = []

    for original_index, char in enumerate(text):
        normalized = unicodedata.normalize("NFD", char).encode("ascii", "ignore").decode().lower()
        for normalized_char in normalized:
            normalized_chars.append(normalized_char)
            index_map.append(original_index)

    return "".join(normalized_chars), index_map


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
    q_norm, q_index_map = _normalize_with_index_map(query)
    variants: list[str] = []

    for group in _SYNONYM_GROUPS:
        matched_term = next((t for t in group if _normalize(t) in q_norm), None)
        if matched_term is None:
            continue
        # Locate span in normalized query — positions align with original (NFC accents = 1 char each)
        match = re.search(re.escape(_normalize(matched_term)), q_norm, flags=re.IGNORECASE)
        if not match:
            continue
        norm_start, norm_end = match.span()
        start = q_index_map[norm_start]
        end = q_index_map[norm_end - 1] + 1

        for replacement in group:
            if replacement == matched_term:
                continue
            variant = _fix_phrase(query[:start] + replacement + query[end:])
            if variant != query and variant not in variants:
                variants.append(variant)
            if len(variants) == 2:
                break

        if len(variants) == 2:
            return variants

    return variants


async def expand_query(query: str) -> list[str]:
    variants = _generate_variants(query)
    logger.debug("Query expansion: original=%r variants=%r", query, variants)
    return [query] + variants
