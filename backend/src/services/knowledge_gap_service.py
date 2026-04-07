import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.document import Document
from src.models.knowledge_gap import KnowledgeGap
from src.models.query_log import QueryLog
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
    "con",
    "cual",
    "cuales",
    "cuanto",
    "cuantos",
    "da",
    "dan",
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
    t = topic.strip().lower()
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


def _topic_similarity(left_topic: str, right_topic: str) -> tuple[float, list[str]]:
    left_terms = _canonical_terms(left_topic)
    right_terms = _canonical_terms(right_topic)
    if not left_terms or not right_terms:
        return 0.0, []

    right_roots = [root for _, root in right_terms]
    matched_roots: list[str] = []
    for _, left_root in left_terms:
        match = next(
            (
                root
                for root in right_roots
                if root == left_root or (
                    min(len(root), len(left_root)) >= 5
                    and (root.startswith(left_root) or left_root.startswith(root))
                )
            ),
            None,
        )
        if match is not None and match not in matched_roots:
            matched_roots.append(match)

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
        return _normalize_topic(candidates[0])

    shared_roots: set[str] | None = None
    root_to_tokens: dict[str, set[str]] = {}
    for topic in candidates:
        terms = _canonical_terms(topic)
        topic_roots = {root for _, root in terms}
        shared_roots = topic_roots if shared_roots is None else shared_roots & topic_roots
        for token, root in terms:
            root_to_tokens.setdefault(root, set()).add(token)

    if shared_roots:
        ordered_terms = []
        for root in shared_roots:
            token = min(root_to_tokens[root], key=lambda value: (len(value), value))
            ordered_terms.append((token, root))
        ordered_terms.sort(key=lambda item: (-len(item[1]), item[0]))
        label = " ".join(token for token, _ in ordered_terms[:3]).strip()
        if label:
            return label

    return min(
        (_normalize_topic(topic) for topic in candidates),
        key=lambda value: (len(_canonical_terms(value)) or 99, len(value), value),
    )


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
    existing["topic"] = _canonical_topic_label([existing["topic"], incoming["topic"]])
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


def _format_gap_metrics(
    gap: KnowledgeGap,
    *,
    has_existing_draft: bool = False,
) -> dict:
    estimated_time_lost_minutes = _estimated_time_lost_minutes(gap.occurrences, gap.coverage_type)
    return {
        "topic": gap.topic,
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
    """Read unanswered and weak queries from QueryLog."""
    unanswered_stmt = (
        select(
            QueryLog.query,
            func.count().label("count"),
            func.avg(QueryLog.coverage_score).label("avg_score"),
        )
        .where(QueryLog.coverage == "none", QueryLog.organization_id == organization_id)
        .group_by(QueryLog.query)
        .order_by(func.count().desc())
        .limit(limit)
    )

    weak_stmt = (
        select(
            QueryLog.query,
            func.count().label("count"),
            func.avg(QueryLog.coverage_score).label("avg_score"),
        )
        .where(
            and_(
                QueryLog.organization_id == organization_id,
                QueryLog.coverage != "none",
                or_(QueryLog.coverage == "partial", QueryLog.coverage_score <= max_score),
            )
        )
        .group_by(QueryLog.query)
        .order_by(func.avg(QueryLog.coverage_score).asc(), func.count().desc())
        .limit(limit)
    )

    unanswered_rows = (await db.execute(unanswered_stmt)).fetchall()
    weak_rows = (await db.execute(weak_stmt)).fetchall()

    raw: list[dict] = []
    seen: set[str] = set()

    for row in unanswered_rows:
        seen.add(row.query)
        raw.append({
            "topic": row.query,
            "coverage_type": "none",
            "occurrences": row.count,
            "avg_score": round(row.avg_score, 4),
            "suggested_action": "create_document",
        })

    for row in weak_rows:
        if row.query in seen:
            continue
        seen.add(row.query)
        raw.append({
            "topic": row.query,
            "coverage_type": "partial",
            "occurrences": row.count,
            "avg_score": round(row.avg_score, 4),
            "suggested_action": "improve_document",
        })

    return raw


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
                if gap.normalized_topic == normalized or _are_topics_similar(gap.topic, raw["topic"])
            ),
            None,
        )

        score = _compute_priority_score(raw["occurrences"], raw["avg_score"], now)
        priority = _score_to_priority(score, quality)

        if existing is not None:
            existing.topic = _canonical_topic_label([existing.topic, raw["topic"]])
            existing.normalized_topic = _normalize_topic(existing.topic)
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
            canonical_topic = _canonical_topic_label([raw["topic"]])
            gap = KnowledgeGap(
                organization_id=organization_id,
                topic=canonical_topic,
                normalized_topic=_normalize_topic(canonical_topic),
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
        _format_gap_metrics(g, has_existing_draft=_has_draft(g.topic))
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
            "topic": g.topic,
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
                "topic": g.topic,
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
