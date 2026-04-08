import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.citation import Citation
from src.models.document import Document
from src.models.knowledge_gap import KnowledgeGap
from src.models.message import Message
from src.models.query_log import QueryLog
from src.services.query_normalization import clean_query_text, normalized_query_key
from src.services.query_quality import INVALID, LOW_QUALITY, classify_query_quality


TIME_LOST_MINUTES_BY_COVERAGE = {
    "none": 3,
    "partial": 2,
}
_TOPIC_TOKEN_RE = re.compile(r"[a-z0-9]+")
_TOPIC_STOPWORDS = {
    "a",
    "al",
    "ano",
    "cada",
    "como",
    "con",
    "cual",
    "cuanta",
    "cuantas",
    "cual",
    "cuales",
    "cuanto",
    "cuanta",
    "cuanto",
    "cuantos",
    "cuntos",
    "cul",
    "da",
    "dan",
    "dia",
    "dias",
    "das",
    "de",
    "del",
    "el",
    "en",
    "es",
    "esta",
    "este",
    "existe",
    "existen",
    "hay",
    "la",
    "las",
    "lo",
    "los",
    "me",
    "mi",
    "mis",
    "para",
    "por",
    "puede",
    "pueden",
    "que",
    "se",
    "su",
    "sus",
    "tiene",
    "tienen",
    "un",
    "una",
    "unas",
    "unos",
    "y",
}
_TOPIC_DISPLAY_BY_ROOT = {
    "bon": "bono",
    "bonu": "bono",
    "llam": "nombre",
    "nombr": "nombre",
    "empres": "empresa",
    "empes": "empresa",
    "salari": "salario",
    "mnim": "minimo",
    "minim": "minimo",
    "vacacion": "vacaciones",
    "trabaj": "trabajo",
    "trabajar": "trabajo",
    "remot": "remoto",
}
_TOPIC_WEAK_MODIFIERS = {"anual", "fin", "ano", "vigente", "mensual"}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _normalize_topic(topic: str) -> str:
    """
    Canonical dedup key for a query topic.

    Steps:
      1. Strip leading/trailing whitespace, lowercase
      2. Remove accents (NFD + ASCII encode)
      3. Strip characters that create spurious variants:
         ¿?¡! (question/exclamation), _ (trailing underscores used as noise)
      4. Collapse internal whitespace

    Examples:
      "¿Cuánto cuesta el servicio?"  → "cuanto cuesta el servicio"
      "Cuanto cuesta el servicio"    → "cuanto cuesta el servicio"
      "cuanto cuesta el servicio_"   → "cuanto cuesta el servicio"
      "¿Cuál es el teléfono?"        → "cual es el telefono"
    """
    t = clean_query_text(topic).strip().lower()
    t = unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode()
    t = re.sub(r"[¿?¡!_]", "", t)
    return " ".join(t.split())


def _topic_tokens(topic: str) -> list[str]:
    return [token for token in _TOPIC_TOKEN_RE.findall(_normalize_topic(topic)) if token]


def _singularize_token(token: str) -> str:
    if len(token) > 5 and token.endswith("ies"):
        return f"{token[:-3]}y"
    if len(token) > 4 and token.endswith("es") and not token.endswith(("aes", "ees", "oes")):
        return token[:-2]
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token


def _token_root(token: str) -> str:
    root = _singularize_token(token)
    for suffix, replacement in (
        ("aciones", "acion"),
        ("iciones", "icion"),
        ("idades", "idad"),
        ("mente", ""),
        ("idad", "idad"),
    ):
        if root.endswith(suffix) and len(root) > len(suffix) + 2:
            root = f"{root[:-len(suffix)]}{replacement}"
            break
    if len(root) >= 4 and root[-1] in "aeiou":
        root = root[:-1]
    return root


def _edit_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    rows = len(left) + 1
    cols = len(right) + 1
    dp = [[0] * cols for _ in range(rows)]

    for i in range(rows):
        dp[i][0] = i
    for j in range(cols):
        dp[0][j] = j

    for i in range(1, rows):
        for j in range(1, cols):
            cost = 0 if left[i - 1] == right[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost,
            )
            if (
                i > 1
                and j > 1
                and left[i - 1] == right[j - 2]
                and left[i - 2] == right[j - 1]
            ):
                dp[i][j] = min(dp[i][j], dp[i - 2][j - 2] + 1)

    return dp[-1][-1]


def _is_terminal_morph_variant(left: str, right: str) -> bool:
    if len(left) != len(right) or len(left) < 5:
        return False
    return left[:-1] == right[:-1] and left[-1] != right[-1]


def _is_typo_similar(left: str, right: str) -> bool:
    left = left.strip().lower()
    right = right.strip().lower()
    if left == right:
        return True
    if min(len(left), len(right)) < 3:
        return False
    if _is_terminal_morph_variant(left, right):
        return False

    distance = _edit_distance(left, right)
    max_len = max(len(left), len(right))
    if distance == 1:
        if abs(len(left) - len(right)) == 1:
            longer, shorter = (left, right) if len(left) > len(right) else (right, left)
            if longer.endswith(shorter):
                return False
            if len(shorter) >= 4 and longer.startswith(shorter):
                return False
        return True
    if distance == 2 and max_len >= 8 and distance / max_len <= 0.2:
        return True
    return False


def _canonical_terms(topic: str) -> list[tuple[str, str]]:
    terms: list[tuple[str, str]] = []
    seen_roots: set[str] = set()
    for token in _topic_tokens(topic):
        if token in _TOPIC_STOPWORDS:
            continue
        root = _token_root(token)
        if len(root) < 3 or root in seen_roots:
            continue
        seen_roots.add(root)
        terms.append((token, root))
    return terms


def _canonical_display_terms(topic: str) -> list[str]:
    display_terms: list[str] = []
    seen_terms: set[str] = set()
    for token, root in _canonical_terms(topic):
        display = _TOPIC_DISPLAY_BY_ROOT.get(root, token)
        if display in seen_terms:
            continue
        seen_terms.add(display)
        display_terms.append(display)

    if len(display_terms) > 1:
        strong_terms = [term for term in display_terms if term not in _TOPIC_WEAK_MODIFIERS]
        if strong_terms:
            display_terms = strong_terms

    return display_terms


def _roots_match(left_root: str, right_root: str) -> bool:
    return left_root != right_root and _is_typo_similar(left_root, right_root)


def _topic_similarity(left_topic: str, right_topic: str) -> tuple[float, list[str]]:
    left_terms = _canonical_terms(left_topic)
    right_terms = _canonical_terms(right_topic)
    if not left_terms or not right_terms:
        return 0.0, []

    unmatched_right = list(right_terms)
    matched_roots: list[str] = []
    for left_token, left_root in left_terms:
        match = next(
            (
                (right_token, right_root)
                for right_token, right_root in unmatched_right
                if (
                    left_root == right_root
                    and not _is_terminal_morph_variant(left_token, right_token)
                )
                or _is_typo_similar(left_token, right_token)
                or _roots_match(left_root, right_root)
            ),
            None,
        )
        if match is not None and match[1] not in matched_roots:
            matched_roots.append(match[1])
            unmatched_right.remove(match)

    if not matched_roots:
        return 0.0, []

    match_count = len(matched_roots)
    smaller_overlap = match_count / min(len(left_terms), len(right_terms))
    larger_overlap = match_count / max(len(left_terms), len(right_terms))
    score = round(smaller_overlap * 0.7 + larger_overlap * 0.3, 4)
    return score, matched_roots


def _are_topics_similar(left_topic: str, right_topic: str) -> bool:
    score, matched_roots = _topic_similarity(left_topic, right_topic)
    if not matched_roots:
        return False
    if score >= 0.78:
        return True
    return len(matched_roots) >= 2 and score >= 0.64


def _canonical_topic_label(topics: list[str]) -> str:
    candidates = [topic for topic in topics if topic and topic.strip()]
    if not candidates:
        return ""
    if len(candidates) == 1:
        display_terms = _canonical_display_terms(candidates[0])
        if display_terms:
            return " ".join(display_terms[:2])
        return _normalize_topic(candidates[0])

    root_to_tokens: dict[str, set[str]] = {}
    candidate_terms = [_canonical_terms(topic) for topic in candidates]
    shared_roots: list[str] = []
    if candidate_terms:
        base_terms = candidate_terms[0]
        for _, base_root in base_terms:
            matched_everywhere = True
            for terms in candidate_terms[1:]:
                match = next((root for _, root in terms if root == base_root or _roots_match(base_root, root)), None)
                if match is None:
                    matched_everywhere = False
                    break
                for token, root in terms:
                    if root == base_root or _roots_match(base_root, root):
                        root_to_tokens.setdefault(base_root, set()).add(token)
            if matched_everywhere:
                for terms in candidate_terms:
                    for token, root in terms:
                        if root == base_root or _roots_match(base_root, root):
                            root_to_tokens.setdefault(base_root, set()).add(token)
                if base_root not in shared_roots:
                    shared_roots.append(base_root)

    if shared_roots:
        ordered_terms = []
        for root in shared_roots:
            display = _TOPIC_DISPLAY_BY_ROOT.get(root)
            if display is None:
                display = min(root_to_tokens[root], key=lambda value: (len(value), value))
            ordered_terms.append((display, root))
        ordered_terms.sort(key=lambda item: (0 if item[0] == "nombre" else 1, -len(item[1]), item[0]))
        label = " ".join(token for token, _ in ordered_terms[:3]).strip()
        if label:
            return label

    return min(
        (_normalize_topic(topic) for topic in candidates),
        key=lambda value: (len(_canonical_terms(value)) or 99, len(value), value),
    )


def _capitalize_question(label: str) -> str:
    if not label:
        return label
    if label.startswith("¿") and len(label) > 1:
        return f"¿{label[1:2].upper()}{label[2:]}"
    return f"{label[:1].upper()}{label[1:]}"


def _humanize_query_label(query: str) -> str:
    cleaned = clean_query_text(query)
    if not cleaned:
        return ""
    plain = cleaned.strip().strip("?").strip()
    if not plain:
        return ""
    label = plain
    question_tokens = {"como", "cual", "cuanto", "cuantos", "cuanta", "cuantas", "hay", "se", "que"}
    normalized_tokens = set(_topic_tokens(plain))
    if normalized_tokens & question_tokens or " " in plain:
        label = f"¿{plain.rstrip('?')}?"
    return _capitalize_question(label)


def _build_visible_gap_label(queries: list[str], internal_topic: str) -> str:
    cleaned_queries = [clean_query_text(query) for query in queries if query and clean_query_text(query)]
    topic_terms = set(_canonical_display_terms(internal_topic))
    query_tokens = {
        token
        for query in cleaned_queries
        for token in _topic_tokens(query)
    }

    if internal_topic == "nombre empresa" or ({"nombre", "empresa"} <= topic_terms):
        return "¿Cómo se llama la empresa?"
    if "vacaciones" in topic_terms and {"cuanto", "cuantos", "dia", "dias"} & query_tokens:
        return "¿Cuántos días de vacaciones tienen los empleados?"
    if topic_terms == {"bono"}:
        if {"anual", "ano", "fin"} & query_tokens:
            return "¿La empresa ofrece bono anual?"
        return "¿La empresa ofrece bono?"

    scored_candidates: list[tuple[int, int, str]] = []
    for query in cleaned_queries:
        normalized = _normalize_topic(query)
        score = 0
        if query.startswith("¿") or query.endswith("?"):
            score += 3
        if len(_topic_tokens(query)) >= 3:
            score += 2
        if topic_terms and topic_terms <= set(_canonical_display_terms(query)):
            score += 2
        scored_candidates.append((score, len(query), query))

    if scored_candidates:
        _, _, best = max(scored_candidates)
        humanized = _humanize_query_label(best)
        if humanized:
            return humanized

    fallback_topic = internal_topic if internal_topic else "este tema"
    return _capitalize_question(f"¿Hay información sobre {fallback_topic}?")


def _merge_raw_gap_entry(existing: dict, incoming: dict) -> dict:
    total_occurrences = existing["occurrences"] + incoming["occurrences"]
    existing["avg_score"] = round(
        (existing["avg_score"] * existing["occurrences"] + incoming["avg_score"] * incoming["occurrences"])
        / total_occurrences,
        4,
    )
    existing["occurrences"] = total_occurrences
    if incoming["coverage_type"] == "none":
        existing["coverage_type"] = "none"
    if incoming["suggested_action"] == "create_document":
        existing["suggested_action"] = "create_document"
    existing_quality_topic = existing.get("quality_topic", existing["topic"])
    incoming_quality_topic = incoming.get("quality_topic", incoming["topic"])
    if len(_normalize_topic(incoming_quality_topic)) > len(_normalize_topic(existing_quality_topic)):
        existing["quality_topic"] = incoming_quality_topic
    existing.setdefault("observed_queries", [])
    existing["observed_queries"].extend(incoming.get("observed_queries", []))
    existing.setdefault("evidence_snippets", [])
    existing.setdefault("evidence_documents", [])
    existing.setdefault("evidence_document_ids", [])
    for snippet in incoming.get("evidence_snippets", []):
        if snippet not in existing["evidence_snippets"] and len(existing["evidence_snippets"]) < 2:
            existing["evidence_snippets"].append(snippet)
    for document in incoming.get("evidence_documents", []):
        if document not in existing["evidence_documents"] and len(existing["evidence_documents"]) < 2:
            existing["evidence_documents"].append(document)
    for document_id in incoming.get("evidence_document_ids", []):
        if document_id not in existing["evidence_document_ids"] and len(existing["evidence_document_ids"]) < 2:
            existing["evidence_document_ids"].append(document_id)
    existing["topic"] = _canonical_topic_label(existing["observed_queries"] or [existing["topic"], incoming["topic"]])
    existing["display_label"] = _build_visible_gap_label(existing["observed_queries"], existing["topic"])
    return existing


def _find_similar_gap_entry(items: list[dict], topic: str) -> dict | None:
    best_item: dict | None = None
    best_score = 0.0
    for item in items:
        score, _ = _topic_similarity(item["topic"], topic)
        if score > best_score and _are_topics_similar(item["topic"], topic):
            best_item = item
            best_score = score
    return best_item


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _compute_priority_score(
    occurrences: int,
    avg_coverage_score: float,
    last_seen_at: datetime,
) -> float:
    """
    Deterministic priority score. Higher = more urgent.

    Components:
      occurrences × 0.5          — frequency signal
      (1 − coverage_score) × 2.0 — gap severity signal
      recency_factor             — decays slowly over days (max 1.0)

    Mapping:
      score ≥ 4.0  → "high"
      score ≥ 2.0  → "medium"
      otherwise    → "medium" (valid gaps are at least medium)
    """
    days_old = max(0, (_now() - last_seen_at).days)
    recency = 1.0 / (1.0 + days_old * 0.1)
    score = occurrences * 0.5 + (1.0 - avg_coverage_score) * 2.0 + recency
    return round(score, 3)


def _score_to_priority(score: float, quality: str) -> str:
    if quality == LOW_QUALITY:
        return "low_quality"
    if score >= 4.0:
        return "high"
    return "medium"


def _minutes_lost_per_occurrence(coverage_type: str) -> int:
    return TIME_LOST_MINUTES_BY_COVERAGE.get(coverage_type, 2)


def _estimated_time_lost_minutes(occurrences: int, coverage_type: str) -> int:
    return occurrences * _minutes_lost_per_occurrence(coverage_type)


def _truncate_snippet(text: str, max_chars: int = 200) -> str:
    compact = " ".join((text or "").split()).strip()
    if len(compact) <= max_chars:
        return compact
    return f"{compact[:max_chars].rstrip()}..."


async def _get_partial_evidence_by_query(
    db: AsyncSession,
    organization_id: uuid.UUID,
    queries: list[str],
) -> dict[str, dict[str, list[str]]]:
    evidence: dict[str, dict[str, list[str]]] = {}
    cleaned_queries = [clean_query_text(query) for query in queries if clean_query_text(query)]
    seen_queries: set[str] = set()
    user_rows = (
        await db.execute(
            select(Message.id, Message.content, Message.conversation_id, Message.created_at)
            .where(
                Message.organization_id == organization_id,
                Message.role == "user",
            )
            .order_by(Message.created_at.desc())
            .limit(250)
        )
    ).all()

    for query in cleaned_queries:
        normalized_query = normalized_query_key(query)
        if not normalized_query or normalized_query in seen_queries:
            continue
        seen_queries.add(normalized_query)

        snippets: list[str] = []
        documents: list[str] = []
        document_ids: list[str] = []
        matching_user_rows = [
            (message_id, conversation_id, created_at)
            for message_id, content, conversation_id, created_at in user_rows
            if normalized_query_key(content or "") == normalized_query
        ][:5]

        for user_id, conversation_id, user_created_at in matching_user_rows:
            assistant_stmt = (
                select(Message.id)
                .where(
                    Message.organization_id == organization_id,
                    Message.conversation_id == conversation_id,
                    Message.role == "assistant",
                    Message.coverage == "partial",
                    Message.created_at >= user_created_at,
                )
                .order_by(Message.created_at.asc())
                .limit(1)
            )
            assistant_id = (await db.execute(assistant_stmt)).scalar_one_or_none()
            if assistant_id is None:
                continue

            citation_stmt = (
                select(Citation.content, Document.id, Document.filename)
                .join(Document, Document.id == Citation.document_id)
                .where(
                    Citation.organization_id == organization_id,
                    Citation.message_id == assistant_id,
                )
                .order_by(Citation.created_at.asc())
                .limit(2)
            )
            citation_rows = (await db.execute(citation_stmt)).all()
            for content, document_id, filename in citation_rows:
                snippet = _truncate_snippet(content or "")
                source = filename or "Documento"
                if snippet and snippet not in snippets:
                    snippets.append(snippet)
                    documents.append(source)
                    document_ids.append(str(document_id))
                if len(snippets) >= 2:
                    break
            if len(snippets) >= 2:
                break

        evidence[normalized_query] = {
            "evidence_snippets": snippets[:2],
            "evidence_documents": documents[:2],
            "evidence_document_ids": document_ids[:2],
        }

    return evidence


def _format_gap_metrics(
    gap: KnowledgeGap,
    *,
    has_existing_draft: bool = False,
    evidence_snippets: list[str] | None = None,
    evidence_documents: list[str] | None = None,
    evidence_document_ids: list[str] | None = None,
) -> dict:
    estimated_time_lost_minutes = _estimated_time_lost_minutes(gap.occurrences, gap.coverage_type)
    return {
        "topic": gap.normalized_topic,
        "display_label": gap.topic,
        "status": gap.status,
        "coverage_type": gap.coverage_type,
        "priority": gap.priority,
        "priority_score": gap.priority_score,
        "quality": gap.quality,
        "occurrences": gap.occurrences,
        "avg_coverage_score": gap.avg_coverage_score,
        "suggested_action": gap.suggested_action,
        "has_existing_draft": has_existing_draft,
        "ready_for_draft": gap.quality != LOW_QUALITY,
        "draft_content": gap.draft_content,
        "last_seen_at": gap.last_seen_at.isoformat(),
        "evidence_snippets": evidence_snippets or [],
        "evidence_documents": evidence_documents or [],
        "evidence_document_ids": evidence_document_ids or [],
        "minutes_lost_per_occurrence": _minutes_lost_per_occurrence(gap.coverage_type),
        "estimated_time_lost_minutes": estimated_time_lost_minutes,
        "estimated_time_saved_if_resolved_minutes": estimated_time_lost_minutes,
    }


def _quick_win_summary(item: dict) -> str:
    saved = item["estimated_time_saved_if_resolved_minutes"]
    occurrences = item["occurrences"]
    queries_label = "consulta" if occurrences == 1 else "consultas"
    return (
        f"Resolver este gap podria ahorrar ~{saved} min y mejorar "
        f"{occurrences} {queries_label}"
    )


def _build_quick_wins(suggestions: list[dict], limit: int = 3) -> list[dict]:
    actionable = [s for s in suggestions if s["quality"] != LOW_QUALITY]
    actionable.sort(
        key=lambda s: (
            s["estimated_time_saved_if_resolved_minutes"],
            s["priority_score"],
            s["occurrences"],
        ),
        reverse=True,
    )
    return [
        {
            "topic": item["topic"],
            "display_label": item.get("display_label", item["topic"]),
            "coverage_type": item["coverage_type"],
            "priority": item["priority"],
            "priority_score": item["priority_score"],
            "occurrences": item["occurrences"],
            "estimated_time_saved_if_resolved_minutes": item["estimated_time_saved_if_resolved_minutes"],
            "summary": _quick_win_summary(item),
        }
        for item in actionable[:limit]
    ]


def _build_recommendations(suggestions: list[dict]) -> list[dict]:
    actionable = [s for s in suggestions if s["quality"] != LOW_QUALITY]
    if not actionable:
        return []

    def _append(kind: str, title: str, item: dict, reason: str, seen: set[str], out: list[dict]) -> None:
        out.append({
            "kind": kind,
            "title": title,
            "topic": item["topic"],
            "display_label": item.get("display_label", item["topic"]),
            "reason": reason,
            "estimated_time_saved_if_resolved_minutes": item["estimated_time_saved_if_resolved_minutes"],
            "occurrences": item["occurrences"],
            "coverage_type": item["coverage_type"],
            "priority": item["priority"],
        })
        seen.add(item["topic"])

    def _pick(candidates: list[dict], seen: set[str]) -> dict | None:
        for item in candidates:
            if item["topic"] not in seen:
                return item
        return None

    recommendations: list[dict] = []
    seen_topics: set[str] = set()

    highest_impact = _pick(sorted(
        actionable,
        key=lambda s: (
            s["estimated_time_saved_if_resolved_minutes"],
            s["priority_score"],
            s["occurrences"],
        ),
        reverse=True,
    ), seen_topics)
    _append(
        "highest_impact",
        "Mayor impacto",
        highest_impact,
        f"Afecta {highest_impact['occurrences']} consultas y concentra ~{highest_impact['estimated_time_saved_if_resolved_minutes']} min evitables.",
        seen_topics,
        recommendations,
    )

    most_repeated = _pick(sorted(
        actionable,
        key=lambda s: (
            s["occurrences"],
            s["estimated_time_saved_if_resolved_minutes"],
            s["priority_score"],
        ),
        reverse=True,
    ), seen_topics)
    if most_repeated is not None:
        _append(
            "most_repeated",
            "Mas repetido",
            most_repeated,
            f"Es el gap que mas se repite ({most_repeated['occurrences']} consultas).",
            seen_topics,
            recommendations,
        )

    worst_coverage = _pick(sorted(
        actionable,
        key=lambda s: (
            1 if s["coverage_type"] == "none" else 0,
            -s["avg_coverage_score"],
            s["occurrences"],
        ),
        reverse=True,
    ), seen_topics)
    if worst_coverage is not None:
        _append(
            "worst_coverage",
            "Peor cobertura",
            worst_coverage,
            "Tiene cobertura nula o la senal mas debil entre los gaps activos.",
            seen_topics,
            recommendations,
        )

    quick_gain_pool = [s for s in actionable if s["has_existing_draft"]]
    if quick_gain_pool:
        quick_gain = _pick(sorted(
            quick_gain_pool,
            key=lambda s: (
                s["estimated_time_saved_if_resolved_minutes"],
                s["priority_score"],
                s["occurrences"],
            ),
            reverse=True,
        ), seen_topics)
        if quick_gain is not None:
            quick_gain_reason = (
                f"Ya tiene borrador y podria recuperar ~{quick_gain['estimated_time_saved_if_resolved_minutes']} min rapido."
            )
    else:
        quick_gain = _pick(sorted(
            actionable,
            key=lambda s: (
                1 if s["priority"] == "high" else 0,
                s["estimated_time_saved_if_resolved_minutes"],
                s["occurrences"],
            ),
            reverse=True,
        ), seen_topics)
        if quick_gain is not None:
            quick_gain_reason = (
                f"Es prioritario y podria recuperar ~{quick_gain['estimated_time_saved_if_resolved_minutes']} min con una sola accion."
            )
    if quick_gain is not None:
        _append(
            "quick_gain",
            "Ganancia rapida",
            quick_gain,
            quick_gain_reason,
            seen_topics,
            recommendations,
        )

    return recommendations


def _knowledge_health_score(
    *,
    coverage_rate_7d: float,
    active_gaps: int,
    resolved_gaps: int,
    estimated_time_lost_current_minutes: int,
    estimated_time_saved_recent_minutes: int,
) -> int:
    """
    Knowledge health score (0-100).

    Formula:
      50% recent coverage quality:
        coverage_rate_7d * 100
      30% backlog resolution:
        resolved_gaps / (resolved_gaps + active_gaps)
      20% time-loss reduction:
        estimated_time_saved_recent_minutes /
        (estimated_time_saved_recent_minutes + estimated_time_lost_current_minutes)

    If a denominator is 0, that component is treated as 1.0 so "no backlog/no loss"
    does not penalize the score.
    """
    resolved_ratio_denominator = resolved_gaps + active_gaps
    resolved_ratio = (
        resolved_gaps / resolved_ratio_denominator
        if resolved_ratio_denominator > 0 else 1.0
    )
    time_reduction_denominator = (
        estimated_time_saved_recent_minutes + estimated_time_lost_current_minutes
    )
    time_reduction_ratio = (
        estimated_time_saved_recent_minutes / time_reduction_denominator
        if time_reduction_denominator > 0 else 1.0
    )

    score = (
        coverage_rate_7d * 100 * 0.5
        + resolved_ratio * 100 * 0.3
        + time_reduction_ratio * 100 * 0.2
    )
    return round(score)


# ─── Raw QueryLog analysis ────────────────────────────────────────────────────

async def _get_raw_from_logs(
    db: AsyncSession,
    organization_id: uuid.UUID,
    limit: int,
    max_score: float,
) -> list[dict]:
    """
    Read currently-active unanswered and weak queries from QueryLog.

    Only the latest outcome per exact query is considered active. Historical
    "none"/"partial" rows are ignored once the same query is later answered
    with strong coverage.
    """
    latest_logs_stmt = (
        select(
            QueryLog.query,
            QueryLog.coverage,
            QueryLog.coverage_score,
            QueryLog.created_at,
        )
        .where(QueryLog.organization_id == organization_id)
        .order_by(QueryLog.created_at.asc())
    )
    rows = (await db.execute(latest_logs_stmt)).fetchall()

    latest_rows_by_query: dict[str, object] = {}
    for row in rows:
        normalized_query = normalized_query_key(row.query or "")
        if not normalized_query:
            continue
        latest_rows_by_query[normalized_query] = row
    latest_rows = list(latest_rows_by_query.values())
    partial_evidence_by_query = await _get_partial_evidence_by_query(
        db,
        organization_id,
        [clean_query_text(row.query or "") for row in latest_rows if row.coverage == "partial"],
    )

    resolved_topics: list[str] = []
    latest_rows_with_topics: list[tuple[object, str, str]] = []
    for row in latest_rows:
        query = clean_query_text(row.query or "")
        normalized_query = normalized_query_key(query)
        if not normalized_query:
            continue
        internal_topic = _canonical_topic_label([query])
        latest_rows_with_topics.append((row, query, internal_topic))

        is_none = row.coverage == "none"
        is_partial = row.coverage == "partial" or (
            row.coverage != "none" and float(row.coverage_score or 0.0) <= max_score
        )
        if not is_none and not is_partial and internal_topic:
            if not any(
                _are_topics_similar(existing_topic, internal_topic)
                for existing_topic in resolved_topics
            ):
                resolved_topics.append(internal_topic)

    grouped: dict[str, dict] = {}
    for row, query, internal_topic in latest_rows_with_topics:
        is_none = row.coverage == "none"
        is_partial = row.coverage == "partial" or (
            row.coverage != "none" and float(row.coverage_score or 0.0) <= max_score
        )
        if not is_none and not is_partial:
            continue
        if any(
            _are_topics_similar(resolved_topic, internal_topic)
            for resolved_topic in resolved_topics
        ):
            continue

        normalized_query = normalized_query_key(query)
        entry = grouped.setdefault(
            normalized_query,
            {
                "topic": internal_topic,
                "display_label": _build_visible_gap_label([query], internal_topic),
                "coverage_type": "none" if is_none else "partial",
                "occurrences": 0,
                "avg_score_total": 0.0,
                "suggested_action": "create_document" if is_none else "improve_document",
                "observed_queries": [query],
                "evidence_snippets": partial_evidence_by_query.get(normalized_query, {}).get("evidence_snippets", []),
                "evidence_documents": partial_evidence_by_query.get(normalized_query, {}).get("evidence_documents", []),
                "evidence_document_ids": partial_evidence_by_query.get(normalized_query, {}).get("evidence_document_ids", []),
            },
        )
        entry["occurrences"] += 1
        entry["avg_score_total"] += float(row.coverage_score or 0.0)
        if is_none:
            entry["coverage_type"] = "none"
            entry["suggested_action"] = "create_document"

    raw: list[dict] = []
    for entry in grouped.values():
        raw.append(
            {
                "topic": entry["topic"],
                "display_label": entry["display_label"],
                "coverage_type": entry["coverage_type"],
                "occurrences": entry["occurrences"],
                "avg_score": round(entry["avg_score_total"] / entry["occurrences"], 4),
                "suggested_action": entry["suggested_action"],
                "observed_queries": entry["observed_queries"],
                "evidence_snippets": entry.get("evidence_snippets", []),
                "evidence_documents": entry.get("evidence_documents", []),
                "evidence_document_ids": entry.get("evidence_document_ids", []),
            }
        )

    raw.sort(
        key=lambda item: (
            1 if item["coverage_type"] == "none" else 0,
            item["occurrences"],
            -item["avg_score"],
        ),
        reverse=True,
    )
    return raw[:limit]


# ─── Sync + main query ────────────────────────────────────────────────────────

async def get_org_action_suggestions(
    db: AsyncSession,
    organization_id: uuid.UUID,
    limit: int = 20,
    max_score: float = 0.6,
) -> dict:
    """
    Sync QueryLogs → knowledge_gaps, then return active suggestions and
    recently applied items.

    Returns (suggestions, recently_applied).
    Gaps with status "ignored" or "promoted" are never resurrected.
    """
    raw_gaps = await _get_raw_from_logs(db, organization_id, limit, max_score)
    for raw in raw_gaps:
        raw["quality_topic"] = raw["topic"]

    # ── Pre-aggregate by normalized_topic ────────────────────────────────────
    # Multiple exact queries can normalize to the same topic (e.g. "¿Cuánto
    # cuesta?" and "Cuanto cuesta"). We merge them before upserting so occurrences
    # reflect the total signal, not just the last query's count.
    aggregated: list[dict] = []
    for raw in raw_gaps:
        existing_agg = _find_similar_gap_entry(aggregated, raw["topic"])
        if existing_agg is not None:
            _merge_raw_gap_entry(existing_agg, raw)
        else:
            aggregated.append(dict(raw))
    consolidated: list[dict] = []
    for raw in aggregated:
        existing_agg = _find_similar_gap_entry(consolidated, raw["topic"])
        if existing_agg is not None:
            _merge_raw_gap_entry(existing_agg, raw)
        else:
            consolidated.append(dict(raw))
    raw_gaps = consolidated
    raw_gap_evidence: dict[str, dict[str, list[str]]] = {
        raw["topic"]: {
            "evidence_snippets": raw.get("evidence_snippets", []),
            "evidence_documents": raw.get("evidence_documents", []),
            "evidence_document_ids": raw.get("evidence_document_ids", []),
        }
        for raw in raw_gaps
    }

    draft_stmt = select(Document.filename).where(
        Document.organization_id == organization_id,
        Document.filename.like("draft_%"),
    )
    draft_filenames: set[str] = {
        r[0] for r in (await db.execute(draft_stmt)).fetchall()
    }

    def _has_draft(topic: str) -> bool:
        slug = topic.lower().replace(" ", "_")[:40]
        return any(slug in fname for fname in draft_filenames)

    now = _now()
    existing_gaps = (
        await db.execute(
            select(KnowledgeGap).where(KnowledgeGap.organization_id == organization_id)
        )
    ).scalars().all()

    # ── Upsert gaps ───────────────────────────────────────────────────────────
    for raw in raw_gaps:
        quality = classify_query_quality(raw.get("quality_topic", raw["topic"]))
        if quality == INVALID:
            continue

        normalized = _normalize_topic(raw["topic"])
        existing = next(
            (
                gap for gap in existing_gaps
                if gap.normalized_topic == normalized or _are_topics_similar(gap.normalized_topic, raw["topic"])
            ),
            None,
        )

        score = _compute_priority_score(raw["occurrences"], raw["avg_score"], now)
        priority = _score_to_priority(score, quality)

        if existing is not None:
            existing.topic = raw.get("display_label") or _build_visible_gap_label(
                raw.get("observed_queries", [raw["topic"]]),
                raw["topic"],
            )
            existing.normalized_topic = normalized
            existing.occurrences = raw["occurrences"]
            existing.avg_coverage_score = raw["avg_score"]
            existing.coverage_type = raw["coverage_type"]
            existing.priority = priority
            existing.priority_score = score
            existing.quality = quality
            existing.suggested_action = raw["suggested_action"]
            existing.last_seen_at = now
            existing.updated_at = now
        else:
            gap = KnowledgeGap(
                organization_id=organization_id,
                topic=raw.get("display_label") or _build_visible_gap_label(
                    raw.get("observed_queries", [raw["topic"]]),
                    raw["topic"],
                ),
                normalized_topic=normalized,
                status="pending",
                quality=quality,
                priority=priority,
                priority_score=score,
                coverage_type=raw["coverage_type"],
                occurrences=raw["occurrences"],
                avg_coverage_score=raw["avg_score"],
                suggested_action=raw["suggested_action"],
                created_at=now,
                updated_at=now,
                last_seen_at=now,
            )
            db.add(gap)
            existing_gaps.append(gap)

    for gap in existing_gaps:
        if gap.status not in ("pending", "conflict", "resolved"):
            continue
        still_active = any(
            gap.normalized_topic == _normalize_topic(raw["topic"])
            or _are_topics_similar(gap.normalized_topic, raw["topic"])
            for raw in raw_gaps
        )
        if still_active:
            if gap.status == "resolved":
                gap.status = "pending"
                gap.updated_at = now
            continue
        if gap.status in ("pending", "conflict"):
            gap.status = "resolved"
            gap.updated_at = now

    await db.commit()

    # ── Active suggestions ────────────────────────────────────────────────────
    active_stmt = (
        select(KnowledgeGap)
        .where(
            KnowledgeGap.organization_id == organization_id,
            KnowledgeGap.status.in_(["pending", "conflict"]),
        )
        .order_by(KnowledgeGap.priority_score.desc())
    )
    active_gaps = (await db.execute(active_stmt)).scalars().all()

    suggestions = [
        _format_gap_metrics(
            g,
            has_existing_draft=_has_draft(g.normalized_topic),
            evidence_snippets=next(
                (
                    payload.get("evidence_snippets", [])
                    for topic, payload in raw_gap_evidence.items()
                    if g.normalized_topic == _normalize_topic(topic) or _are_topics_similar(g.normalized_topic, topic)
                ),
                [],
            ),
            evidence_documents=next(
                (
                    payload.get("evidence_documents", [])
                    for topic, payload in raw_gap_evidence.items()
                    if g.normalized_topic == _normalize_topic(topic) or _are_topics_similar(g.normalized_topic, topic)
                ),
                [],
            ),
            evidence_document_ids=next(
                (
                    payload.get("evidence_document_ids", [])
                    for topic, payload in raw_gap_evidence.items()
                    if g.normalized_topic == _normalize_topic(topic) or _are_topics_similar(g.normalized_topic, topic)
                ),
                [],
            ),
        )
        for g in active_gaps
    ]

    # ── Recently applied ──────────────────────────────────────────────────────
    promoted_stmt = (
        select(KnowledgeGap)
        .where(
            KnowledgeGap.organization_id == organization_id,
            KnowledgeGap.status == "promoted",
        )
        .order_by(KnowledgeGap.updated_at.desc())
        .limit(5)
    )
    promoted_gaps = (await db.execute(promoted_stmt)).scalars().all()

    recently_applied = []
    for g in promoted_gaps:
        estimated_saved = _estimated_time_lost_minutes(g.occurrences, g.coverage_type)
        recently_applied.append({
            "topic": g.normalized_topic,
            "display_label": g.topic,
            "coverage_type": g.coverage_type,
            "chunks_created": g.promoted_chunks or 0,
            "promoted_at": g.updated_at.isoformat(),
            "occurrences": g.occurrences,
            "estimated_time_saved_if_resolved_minutes": estimated_saved,
        })

    return {
        "suggestions": suggestions,
        "recently_applied": recently_applied,
        "quick_wins": _build_quick_wins(suggestions),
        "recommendations": _build_recommendations(suggestions),
    }


# ─── Gap mutations ────────────────────────────────────────────────────────────

async def get_gap_by_topic(
    db: AsyncSession,
    organization_id: uuid.UUID,
    topic: str,
) -> KnowledgeGap | None:
    normalized = _normalize_topic(topic)
    stmt = select(KnowledgeGap).where(
        KnowledgeGap.organization_id == organization_id,
        KnowledgeGap.normalized_topic == normalized,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def mark_gap_ignored(
    db: AsyncSession,
    organization_id: uuid.UUID,
    topic: str,
    reason: str | None = None,
) -> bool:
    gap = await get_gap_by_topic(db, organization_id, topic)
    if gap is None:
        return False
    gap.status = "ignored"
    gap.action_reason = reason
    gap.updated_at = _now()
    await db.commit()
    return True


async def mark_gap_undo(
    db: AsyncSession,
    organization_id: uuid.UUID,
    topic: str,
) -> str | None:
    """
    Undo an ignored gap: move it back to pending.
    Returns the new status if the gap was found, None otherwise.
    Only "ignored" gaps can be undone.
    """
    gap = await get_gap_by_topic(db, organization_id, topic)
    if gap is None:
        return None
    if gap.status != "ignored":
        return gap.status  # already in a non-ignored state, no-op
    gap.status = "pending"
    gap.action_reason = None
    gap.updated_at = _now()
    await db.commit()
    return "pending"


async def save_gap_draft(
    db: AsyncSession,
    organization_id: uuid.UUID,
    topic: str,
    draft_content: str,
) -> None:
    gap = await get_gap_by_topic(db, organization_id, topic)
    if gap is not None:
        gap.draft_content = draft_content
        gap.updated_at = _now()
        await db.commit()


async def mark_gap_promoted(
    db: AsyncSession,
    organization_id: uuid.UUID,
    topic: str,
    chunks_created: int,
) -> dict | None:
    gap = await get_gap_by_topic(db, organization_id, topic)
    if gap is not None:
        coverage_before = gap.coverage_type
        estimated_saved = _estimated_time_lost_minutes(gap.occurrences, gap.coverage_type)
        gap.status = "promoted"
        gap.promoted_chunks = chunks_created
        gap.updated_at = _now()
        await db.commit()
        return {
            "topic": gap.topic,
            "coverage_before": coverage_before,
            "coverage_after": "full",
            "affected_occurrences": gap.occurrences,
            "estimated_time_saved_if_resolved_minutes": estimated_saved,
            "message": (
                f"Ahora este gap podria dejar de afectar {gap.occurrences} "
                f"{'consulta' if gap.occurrences == 1 else 'consultas'} "
                f"(~{estimated_saved} min ahorrables)"
            ),
        }
    return None


async def mark_gap_conflict(
    db: AsyncSession,
    organization_id: uuid.UUID,
    topic: str,
) -> None:
    gap = await get_gap_by_topic(db, organization_id, topic)
    if gap is not None:
        gap.status = "conflict"
        gap.updated_at = _now()
        await db.commit()


# ─── Insights ─────────────────────────────────────────────────────────────────

async def get_knowledge_insights(
    db: AsyncSession,
    organization_id: uuid.UUID,
) -> dict:
    """
    Aggregated insights for the knowledge gaps dashboard.
    All queries are read-only and scoped to the organization.
    """
    # Active gaps counts
    counts_stmt = select(
        KnowledgeGap.priority,
        func.count().label("n"),
    ).where(
        KnowledgeGap.organization_id == organization_id,
        KnowledgeGap.status.in_(["pending", "conflict"]),
    ).group_by(KnowledgeGap.priority)

    counts_rows = (await db.execute(counts_stmt)).fetchall()
    # Exclude low_quality from active gap counts — they have their own collapsed section
    total_active = sum(r.n for r in counts_rows if r.priority != LOW_QUALITY)
    high_count = sum(r.n for r in counts_rows if r.priority == "high")

    # Resolved totals / recent
    cutoff_24h = _now() - timedelta(hours=24)
    cutoff_7d = _now() - timedelta(days=7)
    resolved_stmt = select(func.count()).where(
        KnowledgeGap.organization_id == organization_id,
        KnowledgeGap.status == "promoted",
    )
    resolved_gaps: int = (await db.execute(resolved_stmt)).scalar_one() or 0
    recently_resolved_stmt = select(func.count()).where(
        KnowledgeGap.organization_id == organization_id,
        KnowledgeGap.status == "promoted",
        KnowledgeGap.updated_at >= cutoff_24h,
    )
    recently_resolved: int = (await db.execute(recently_resolved_stmt)).scalar_one() or 0

    # Coverage rate from QueryLog (last 7 days)
    total_recent_stmt = select(func.count()).where(
        QueryLog.organization_id == organization_id,
        QueryLog.created_at >= cutoff_7d,
    )
    covered_recent_stmt = select(func.count()).where(
        QueryLog.organization_id == organization_id,
        QueryLog.created_at >= cutoff_7d,
        QueryLog.coverage == "full",
    )
    total_recent: int = (await db.execute(total_recent_stmt)).scalar_one() or 0
    covered_recent: int = (await db.execute(covered_recent_stmt)).scalar_one() or 0
    coverage_rate = round(covered_recent / total_recent, 3) if total_recent > 0 else 0.0

    active_gaps_stmt = (
        select(KnowledgeGap)
        .where(
            KnowledgeGap.organization_id == organization_id,
            KnowledgeGap.status.in_(["pending", "conflict"]),
            KnowledgeGap.quality != LOW_QUALITY,
        )
    )
    active_gaps = (await db.execute(active_gaps_stmt)).scalars().all()
    estimated_time_lost_current_minutes = sum(
        _estimated_time_lost_minutes(g.occurrences, g.coverage_type)
        for g in active_gaps
    )

    recent_promoted_stmt = (
        select(KnowledgeGap)
        .where(
            KnowledgeGap.organization_id == organization_id,
            KnowledgeGap.status == "promoted",
            KnowledgeGap.updated_at >= cutoff_7d,
        )
    )
    recent_promoted_gaps = (await db.execute(recent_promoted_stmt)).scalars().all()
    estimated_time_saved_recent_minutes = sum(
        _estimated_time_lost_minutes(g.occurrences, g.coverage_type)
        for g in recent_promoted_gaps
    )

    # Top 5 gaps by priority_score — exclude low_quality (noise, not actionable)
    top_stmt = (
        select(KnowledgeGap)
        .where(
            KnowledgeGap.organization_id == organization_id,
            KnowledgeGap.status.in_(["pending", "conflict"]),
            KnowledgeGap.quality != LOW_QUALITY,
        )
        .order_by(KnowledgeGap.priority_score.desc())
        .limit(5)
    )
    top_gaps = (await db.execute(top_stmt)).scalars().all()

    knowledge_health_score = _knowledge_health_score(
        coverage_rate_7d=coverage_rate,
        active_gaps=total_active,
        resolved_gaps=resolved_gaps,
        estimated_time_lost_current_minutes=estimated_time_lost_current_minutes,
        estimated_time_saved_recent_minutes=estimated_time_saved_recent_minutes,
    )

    return {
        "total_active_gaps": total_active,
        "high_priority_count": high_count,
        "coverage_rate": coverage_rate,
        "recently_resolved": recently_resolved,
        "total_queries_analyzed": total_recent,
        "active_gaps": total_active,
        "resolved_gaps": resolved_gaps,
        "coverage_rate_7d": coverage_rate,
        "estimated_time_lost_current_minutes": estimated_time_lost_current_minutes,
        "estimated_time_saved_recent_minutes": estimated_time_saved_recent_minutes,
        "knowledge_health_score": knowledge_health_score,
        "top_topics": [
            {
                "topic": g.normalized_topic,
                "display_label": g.topic,
                "coverage_type": g.coverage_type,
                "occurrences": g.occurrences,
                "priority_score": g.priority_score,
                "priority": g.priority,
                "estimated_time_saved_if_resolved_minutes": _estimated_time_lost_minutes(
                    g.occurrences, g.coverage_type
                ),
            }
            for g in top_gaps
        ],
    }


# ─── Legacy helpers ───────────────────────────────────────────────────────────

async def get_top_unanswered_queries(
    db: AsyncSession,
    organization_id: uuid.UUID,
    limit: int = 20,
) -> list[dict]:
    stmt = (
        select(
            QueryLog.query,
            func.count().label("count"),
            func.avg(QueryLog.coverage_score).label("avg_coverage_score"),
        )
        .where(QueryLog.coverage == "none", QueryLog.organization_id == organization_id)
        .group_by(QueryLog.query)
        .order_by(func.count().desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        {
            "query": row.query,
            "count": row.count,
            "avg_coverage_score": round(row.avg_coverage_score, 4),
        }
        for row in result.all()
    ]


async def get_top_weak_queries(
    db: AsyncSession,
    organization_id: uuid.UUID,
    limit: int = 20,
    max_score: float = 0.6,
) -> list[dict]:
    stmt = (
        select(
            QueryLog.query,
            func.count().label("count"),
            func.avg(QueryLog.coverage_score).label("avg_coverage_score"),
        )
        .where(
            and_(
                QueryLog.organization_id == organization_id,
                QueryLog.coverage != "none",
                or_(
                    QueryLog.coverage == "partial",
                    QueryLog.coverage_score <= max_score,
                ),
            )
        )
        .group_by(QueryLog.query)
        .order_by(func.avg(QueryLog.coverage_score).asc(), func.count().desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [
        {
            "query": row.query,
            "count": row.count,
            "avg_coverage_score": round(row.avg_coverage_score, 4),
        }
        for row in result.all()
    ]


async def get_knowledge_gap_summary(
    db: AsyncSession,
    organization_id: uuid.UUID,
    limit: int = 10,
    max_score: float = 0.6,
) -> dict:
    top_unanswered = await get_top_unanswered_queries(db, organization_id, limit)
    top_weak = await get_top_weak_queries(db, organization_id, limit, max_score)
    return {
        "top_unanswered": top_unanswered,
        "top_weak": top_weak,
    }
