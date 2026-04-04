import re

# Conjunctions that may connect independent sub-questions in a compound query.
# Surrounded by whitespace to avoid splitting inside words (e.g., "Uruguay").
_SEP_RE = re.compile(r"\s+(?:y|e|además|también)\s+", re.IGNORECASE)

# Minimum number of words a fragment must have to be considered a valid sub-query.
# Fragments shorter than this are likely noun phrases, not standalone questions.
_MIN_WORDS = 4


def decompose_query(query: str) -> list[str]:
    """
    Splits a compound query into independent sub-queries by conjunctions.

    Examples:
        "¿Qué tecnologías usa el backend y cuánto cuesta el servicio?"
            → ["¿Qué tecnologías usa el backend", "cuánto cuesta el servicio?"]

        "FastAPI y PostgreSQL"      # fragments too short → original kept
            → ["FastAPI y PostgreSQL"]

        "¿Cuál es el objetivo de Company Brain?"    # no separator
            → ["¿Cuál es el objetivo de Company Brain?"]

    Returns the original query (in a list) if fewer than 2 valid fragments result.
    """
    parts = _SEP_RE.split(query.strip())

    # Keep only fragments with at least _MIN_WORDS words
    valid = [p.strip() for p in parts if len(p.strip().split()) >= _MIN_WORDS]

    if len(valid) < 2:
        return [query]

    return valid
