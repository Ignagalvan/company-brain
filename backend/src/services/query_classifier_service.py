import unicodedata

_GENERIC_SIGNALS = frozenset([
    "contame algo",
    "decime algo",
    "algo interesante",
    "todo",
    "que podes hacer",
])

_OUT_OF_SCOPE_SIGNALS = frozenset([
    "capital",
    "mundial",
    "historia",
    "einstein",
    "iphone",
    "luna",
])


def _normalize(text: str) -> str:
    """Lowercase and strip accents for matching purposes."""
    return unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()


def classify_query(query: str) -> str:
    """
    Classifies a query without LLM or ML.

    Returns:
        "generic"      — vague/exploratory queries with no specific intent
        "out_of_scope" — queries about topics clearly outside the knowledge base
        "in_scope"     — everything else (assumed relevant to the system)
    """
    q = _normalize(query)

    for signal in _GENERIC_SIGNALS:
        if _normalize(signal) in q:
            return "generic"

    for signal in _OUT_OF_SCOPE_SIGNALS:
        if _normalize(signal) in q:
            return "out_of_scope"

    return "in_scope"
