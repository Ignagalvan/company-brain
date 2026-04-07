import uuid
import re

from sqlalchemy.ext.asyncio import AsyncSession

from src.services.document_service import get_documents_overview
from src.services.knowledge_gap_service import get_knowledge_insights, get_org_action_suggestions


def _normalize_topic_ref(topic: str) -> str:
    return topic.strip().lower().replace(" ", "_")[:80]


def _display_document_name(filename: str) -> str:
    match = re.match(r"^[0-9a-f-]{36}_(.+)$", filename, re.IGNORECASE)
    cleaned = match.group(1) if match else filename
    draft_match = re.match(r"^draft_[0-9a-f]{8}_(.+)$", cleaned, re.IGNORECASE)
    return draft_match.group(1) if draft_match else cleaned


def _gap_effort_estimate(item: dict) -> str:
    """
    Heuristic:
      low    -> draft already exists OR impact <= 12 min OR occurrences <= 4
      medium -> everything else
    """
    if item.get("has_existing_draft"):
        return "low"
    if item["estimated_time_saved_if_resolved_minutes"] <= 12:
        return "low"
    if item["occurrences"] <= 4:
        return "low"
    return "medium"


def _document_effort_estimate(item: dict) -> str:
    """
    Heuristic:
      low    -> document has <= 3 chunks or no visible usage and no gap relation
      medium -> documents related to gaps or larger docs that need review
    """
    if item["chunks_count"] <= 3:
        return "low"
    if item["usage_count"] == 0 and item["related_active_gaps_count"] == 0:
        return "low"
    return "medium"


def _make_gap_action(item: dict, action_type: str, title: str, description: str, reason: str) -> dict:
    topic = item["topic"]
    return {
        "id": f"{action_type}:gap:{_normalize_topic_ref(topic)}",
        "type": action_type,
        "title": title,
        "description": description,
        "impact_minutes": item["estimated_time_saved_if_resolved_minutes"],
        "impact_occurrences": item["occurrences"],
        "effort_estimate": _gap_effort_estimate(item),
        "reason": reason,
        "target_type": "gap",
        "target_id": None,
        "target_topic": topic,
        "cta_label": "Ver gap",
        "cta_href": "/dashboard/improvement",
    }


def _make_document_action(
    item: dict,
    *,
    action_type: str,
    title: str,
    description: str,
    reason: str,
    impact_minutes: int,
    impact_occurrences: int,
) -> dict:
    return {
        "id": f"{action_type}:document:{item['id']}",
        "type": action_type,
        "title": title,
        "description": description,
        "impact_minutes": impact_minutes,
        "impact_occurrences": impact_occurrences,
        "effort_estimate": _document_effort_estimate(item),
        "reason": reason,
        "target_type": "document",
        "target_id": str(item["id"]),
        "target_topic": None,
        "cta_label": "Abrir documento",
        "cta_href": f"/documents/{item['id']}",
    }


async def get_optimize_recommendations(
    db: AsyncSession,
    organization_id: uuid.UUID,
) -> dict:
    gap_data = await get_org_action_suggestions(db, organization_id)
    insights = await get_knowledge_insights(db, organization_id)
    documents = await get_documents_overview(db, organization_id)

    gap_items = [
        item for item in gap_data["suggestions"]
        if item["quality"] != "low_quality"
    ]
    gap_by_topic = {item["topic"]: item for item in gap_items}

    gap_actions: list[dict] = []
    seen_gap_topics: set[str] = set()

    def _pick_gap(candidates: list[dict]) -> dict | None:
        for candidate in candidates:
            if candidate["topic"] not in seen_gap_topics:
                return candidate
        return None

    if gap_items:
        by_impact = sorted(
            gap_items,
            key=lambda item: (
                item["estimated_time_saved_if_resolved_minutes"],
                item["priority_score"],
                item["occurrences"],
            ),
            reverse=True,
        )
        top_impact = _pick_gap(by_impact)
        gap_actions.append(_make_gap_action(
            top_impact,
            "resolve_gap",
            f"Resolver gap: {top_impact['topic']}",
            f"Resolver este gap podría mejorar {top_impact['occurrences']} consultas.",
            f"Hoy concentra ~{top_impact['estimated_time_saved_if_resolved_minutes']} min de pérdida estimada.",
        ))
        seen_gap_topics.add(top_impact["topic"])

        most_repeated = _pick_gap(sorted(
            gap_items,
            key=lambda item: (
                item["occurrences"],
                item["estimated_time_saved_if_resolved_minutes"],
                item["priority_score"],
            ),
            reverse=True,
        ))
        if most_repeated is not None:
            gap_actions.append(_make_gap_action(
                most_repeated,
                "resolve_gap",
                f"Atacar gap repetido: {most_repeated['topic']}",
                f"Este gap se repite en {most_repeated['occurrences']} consultas.",
                "Reduciría preguntas repetidas que hoy vuelven a aparecer.",
            ))
            seen_gap_topics.add(most_repeated["topic"])

        worst_coverage = _pick_gap(sorted(
            gap_items,
            key=lambda item: (
                1 if item["coverage_type"] == "none" else 0,
                item["estimated_time_saved_if_resolved_minutes"],
                item["occurrences"],
            ),
            reverse=True,
        ))
        if worst_coverage is not None:
            gap_actions.append(_make_gap_action(
                worst_coverage,
                "resolve_gap",
                f"Mejorar cobertura: {worst_coverage['topic']}",
                "La cobertura actual es la más débil entre los gaps activos más relevantes.",
                f"Hoy deja sin buena respuesta a {worst_coverage['occurrences']} consultas.",
            ))
            seen_gap_topics.add(worst_coverage["topic"])

    document_actions: list[dict] = []
    for item in documents["documents"]:
        related_gap_minutes = sum(
            gap_by_topic[topic]["estimated_time_saved_if_resolved_minutes"]
            for topic in item["related_gap_topics"]
            if topic in gap_by_topic
        )
        related_gap_occurrences = sum(
            gap_by_topic[topic]["occurrences"]
            for topic in item["related_gap_topics"]
            if topic in gap_by_topic
        )

        if item["related_active_gaps_count"] > 0 and not item["is_helping"]:
            document_actions.append(_make_document_action(
                item,
                action_type="review_document_related_to_gap",
                title=f"Revisar documento: {_display_document_name(item['filename'])}",
                description=(
                    f"Este documento aparece relacionado con {item['related_active_gaps_count']} gaps, "
                    "pero todavía no aporta valor visible."
                ),
                reason="Conviene revisar si el contenido es claro, completo o si necesita mejor estructura.",
                impact_minutes=related_gap_minutes,
                impact_occurrences=related_gap_occurrences,
            ))
        elif item["chunks_count"] > 0 and item["usage_count"] == 0 and item["related_active_gaps_count"] == 0:
            document_actions.append(_make_document_action(
                item,
                action_type="review_unused_document",
                title=f"Revisar documento sin uso: {_display_document_name(item['filename'])}",
                description="Tiene contenido procesado, pero no fue usado en respuestas ni aparece conectado a gaps.",
                reason="Puede necesitar mejor contenido, mejor naming o limpieza si ya no aporta valor.",
                impact_minutes=0,
                impact_occurrences=0,
            ))
        elif item["chunks_count"] == 0:
            document_actions.append(_make_document_action(
                item,
                action_type="cleanup_document",
                title=f"Limpiar o reprocesar: {_display_document_name(item['filename'])}",
                description="Este documento no muestra chunks procesados y hoy no puede aportar valor de retrieval.",
                reason="Conviene revisar el archivo o volver a cargarlo con mejor contenido.",
                impact_minutes=0,
                impact_occurrences=0,
            ))

    document_actions.sort(
        key=lambda item: (
            item["impact_minutes"],
            item["impact_occurrences"],
            1 if item["effort_estimate"] == "low" else 0,
        ),
        reverse=True,
    )

    top_actions = sorted(
        [*gap_actions, *document_actions],
        key=lambda item: (
            item["impact_minutes"],
            item["impact_occurrences"],
            1 if item["effort_estimate"] == "low" else 0,
        ),
        reverse=True,
    )[:5]

    quick_wins = [
        action for action in top_actions
        if action["effort_estimate"] == "low" and action["impact_minutes"] >= 6
    ]

    if len(quick_wins) < 3:
        extra_quick_wins = sorted(
            [
                action for action in [*gap_actions, *document_actions]
                if (
                    action["effort_estimate"] == "low"
                    and action["impact_minutes"] > 0
                    and action["id"] not in {item["id"] for item in quick_wins}
                )
            ],
            key=lambda item: (item["impact_minutes"], item["impact_occurrences"]),
            reverse=True,
        )
        quick_wins.extend(extra_quick_wins[: max(0, 3 - len(quick_wins))])

    estimated_time_saved_if_top_actions_completed = sum(
        action["impact_minutes"] for action in top_actions[:3]
    )

    return {
        "summary": {
            "estimated_time_lost_current_minutes": insights["estimated_time_lost_current_minutes"],
            "estimated_time_saved_if_top_actions_completed": estimated_time_saved_if_top_actions_completed,
            "active_gaps_count": insights["active_gaps"],
            "unused_documents_count": documents["insights"]["unused_documents_count"],
            "documents_helping_count": documents["insights"]["documents_helping_count"],
            "coverage_rate_7d": insights["coverage_rate_7d"],
            "knowledge_health_score": insights["knowledge_health_score"],
        },
        "top_actions": top_actions,
        "quick_wins": quick_wins[:3],
        "document_actions": document_actions[:5],
        "gap_actions": gap_actions[:5],
    }
