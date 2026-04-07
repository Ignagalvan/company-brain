import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

# Maximum chunks to send to the LLM judge after scoring.
_TOP_K_AFTER_SCORING = 5

# Scoring weights — must sum to 1.0
_WEIGHT_SIMILARITY = 0.60   # most important: how close the chunk is to the query
_WEIGHT_LENGTH     = 0.25   # rewards substantive chunks, penalizes too short/too long
_WEIGHT_POSITION   = 0.15   # tiebreaker: original retrieval rank

# Re-ranking weights (vector + keyword hybrid)
_WEIGHT_VECTOR  = 0.50
_WEIGHT_KEYWORD = 0.20
_WEIGHT_LENGTH_R  = 0.20
_WEIGHT_POSITION_R = 0.10
_TOKEN_RE = re.compile(r"[a-z0-9@._+-]+")
_STOPWORDS = {
    "que", "cual", "cuales", "cada", "cuanto", "cuantos", "dias", "hay", "dar",
    "para", "por", "con", "sin", "del", "de", "la", "el", "los", "las", "una",
    "uno", "unos", "unas", "es", "se", "ya", "mas", "menos", "informacion",
}


def _normalize_token(text: str) -> str:
    return unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(_normalize_token(text)))


def _content_tokens(text: str) -> set[str]:
    return {token for token in _tokenize(text) if len(token) >= 4 and token not in _STOPWORDS}


def _tokens_match(left: str, right: str) -> bool:
    if left == right:
        return True
    shorter, longer = sorted((left, right), key=len)
    return len(shorter) >= 5 and longer.startswith(shorter)


def _match_count(query_tokens: set[str], content_tokens: set[str]) -> int:
    hits = 0
    remaining = set(content_tokens)
    for query_token in query_tokens:
        match = next((token for token in remaining if _tokens_match(query_token, token)), None)
        if match is not None:
            hits += 1
            remaining.remove(match)
    return hits


def _similarity_score(distance: float) -> float:
    """
    Converts cosine distance [0, 2] to a similarity score in [0, 1].
    Lower distance → higher score.
    """
    return max(0.0, 1.0 - distance)


def _length_score(content: str) -> float:
    """
    Rewards chunks of substantive length.

    < 20 words  : scaled linearly from 0 to 1  (too short, low information)
    20–300 words: ideal range, score = 1.0
    > 300 words : slow decay, floor at 0.5     (too long, may be unfocused)
    """
    words = len(content.split())
    if words < 20:
        return words / 20.0
    if words <= 300:
        return 1.0
    return max(0.5, 1.0 - (words - 300) / 1000.0)


def _keyword_score(content: str, query: str) -> float:
    """
    Fraction of unique query words that appear in the chunk content.
    Case-insensitive exact-word match. Returns a value in [0, 1].
    """
    query_words = _content_tokens(query)
    if not query_words:
        return 0.0
    content_words = _content_tokens(content)
    hits = _match_count(query_words, content_words)
    return hits / len(query_words)


def _position_score(rank: int, total: int) -> float:
    """
    Rewards chunks that ranked higher in the original retrieval order.
    rank=0 → 1.0, rank=total-1 → ~0.0.
    """
    if total <= 1:
        return 1.0
    return 1.0 - (rank / total)


def score_chunks(chunks: list[dict], subquery: str) -> list[dict]:
    """
    Scores and selects the best chunks for a given subquery.

    Scoring is deterministic — no LLM, no randomness.

    Factors:
        Similarity (60%): 1 - cosine_distance → rewards semantic closeness
        Length     (25%): rewards 20-300 word chunks, penalizes very short/long
        Position   (15%): rewards original retrieval rank as a tiebreaker

    Returns up to _TOP_K_AFTER_SCORING chunks, sorted by score descending.
    Each chunk dict gets a "score" key added (float, 0-1 range).

    Note on cross-subquery bonus: not applied here because scoring runs
    per-subquery before cross-subquery state is available. The dedup in
    _merge_chunks already captures the signal (chunk that appears across
    multiple variants has the lowest distance assigned).
    """
    if not chunks:
        return []

    total = len(chunks)
    scored: list[dict] = []

    for rank, chunk in enumerate(chunks):
        content = chunk.get("content", "")
        vec = _similarity_score(chunk.get("distance", 1.0))
        kw  = _keyword_score(content, subquery)
        lng = _length_score(content)
        pos = _position_score(rank, total)

        final = (
            _WEIGHT_VECTOR    * vec
            + _WEIGHT_KEYWORD   * kw
            + _WEIGHT_LENGTH_R  * lng
            + _WEIGHT_POSITION_R * pos
        )

        scored.append({**chunk, "score": round(final, 4)})

    scored.sort(key=lambda c: c["score"], reverse=True)
    selected = scored[:_TOP_K_AFTER_SCORING]

    logger.debug(
        "Evidence scoring | subquery=%r | input=%d chunks → selected=%d | scores=%s",
        subquery[:50], total, len(selected),
        [c["score"] for c in selected],
    )

    return selected
