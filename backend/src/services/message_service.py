import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.exceptions import MessageProcessingError
from src.models.citation import Citation
from src.models.conversation import Conversation
from src.models.message import Message
from src.models.query_log import QueryLog
from src.services import answer_service, evidence_scoring, expansion_service, query_decomposition, retrieval_service
from src.services.query_classifier_service import classify_query

logger = logging.getLogger(__name__)

# Maximum chunks sent to the LLM judge after merge+dedup across all query variants.
_MAX_CHUNKS_TO_JUDGE = 10


def _derive_title(content: str) -> str:
    title = " ".join(content.split())[:80]
    return title or "Nueva conversación"


def _merge_chunks(all_results: list[list[dict]]) -> list[dict]:
    """
    Merges chunk lists from multiple query variants.
    Deduplicates by chunk_id, keeping the lowest distance per chunk.
    Returns sorted by distance, limited to _MAX_CHUNKS_TO_JUDGE.
    """
    seen: dict[str, dict] = {}
    for chunks in all_results:
        for chunk in chunks:
            cid = str(chunk["chunk_id"])
            if cid not in seen or chunk["distance"] < seen[cid]["distance"]:
                seen[cid] = chunk
    merged = sorted(seen.values(), key=lambda c: c["distance"])
    return merged[:_MAX_CHUNKS_TO_JUDGE]


def _format_answer(answer: str, coverage: str, missing_points: list[str]) -> str:
    """
    Formats the final answer text.
    For partial coverage, appends a clear section listing what was not found.
    """
    if coverage == "partial" and missing_points:
        missing_text = "\n".join(f"- {p}" for p in missing_points)
        return f"{answer}\n\nNo encontré información sobre:\n{missing_text}"
    return answer


async def _run_single_query(
    db: AsyncSession,
    organization_id: uuid.UUID,
    subquery: str,
) -> dict:
    """
    Runs the full expansion → retrieval → judge pipeline for one query.

    Returns:
        subquery         : the query that was run
        result           : raw output from generate_answer
        evidence_chunks  : resolved chunk dicts (not indexes) for the cited evidence
        reformulations   : expansion variants (without original)
        chunks_before    : total chunks before dedup
        chunks_after     : chunks sent to the judge
        all_chunks       : merged chunk list (for debug distances)
    """
    queries = await expansion_service.expand_query(subquery)
    all_results = await asyncio.gather(
        *[
            retrieval_service.search_chunks(
                db=db,
                organization_id=organization_id,
                query=q,
            )
            for q in queries
        ]
    )
    chunks_before = sum(len(r) for r in all_results)
    chunks = _merge_chunks(list(all_results))
    chunks = evidence_scoring.score_chunks(chunks, subquery)

    result = await answer_service.generate_answer(query=subquery, chunks=chunks)

    evidence_chunks = (
        [chunks[i] for i in result["evidence_indexes"] if i < len(chunks)]
        if result["can_answer"]
        else []
    )

    scores = [c["score"] for c in chunks if "score" in c]
    coverage_score = round(sum(scores) / len(scores), 4) if scores else 0.0

    return {
        "subquery": subquery,
        "result": result,
        "evidence_chunks": evidence_chunks,
        "reformulations": queries[1:],
        "chunks_before": chunks_before,
        "chunks_after": len(chunks),
        "all_chunks": chunks,
        "coverage_score": coverage_score,
    }


def _aggregate_sub_results(subs: list[dict]) -> dict:
    """
    Combines results from multiple independent subquery pipelines.

    Coverage rules:
        ALL full  → "full"
        ≥1 has evidence (full or partial) → "partial"
        NONE has evidence → "none" (caller should use fallback)

    Returns:
        can_answer      : bool
        coverage        : "full" | "partial" | "none"
        answer          : combined answer text (already includes missing sections)
        evidence_chunks : deduplicated union of evidence across subqueries
        supported_points: union of all supported_points
        missing_points  : subquery texts that had no evidence (for metadata)
    """
    answered = [s for s in subs if s["result"]["can_answer"]]
    unanswered = [s for s in subs if not s["result"]["can_answer"]]

    if not answered:
        return {
            "can_answer": False,
            "coverage": "none",
            "coverage_score": 0.0,
            "answer": answer_service.NO_CONTEXT_ANSWER,
            "evidence_chunks": [],
            "supported_points": [],
            "missing_points": [s["subquery"] for s in subs],
        }

    all_full = all(s["result"]["coverage"] == "full" for s in subs)
    coverage = "full" if all_full else "partial"

    # Build combined answer: inline the "not found" message for unanswered parts
    parts = []
    for s in subs:
        if s["result"]["can_answer"] and s["result"]["answer"]:
            parts.append(s["result"]["answer"])
        else:
            parts.append(f"No encontré información sobre: {s['subquery']}")
    combined_answer = "\n\n".join(parts)

    # Dedup evidence chunks across subqueries (keep lowest distance per chunk_id)
    seen: dict[str, dict] = {}
    for s in answered:
        for chunk in s["evidence_chunks"]:
            cid = str(chunk["chunk_id"])
            if cid not in seen or chunk["distance"] < seen[cid]["distance"]:
                seen[cid] = chunk
    all_evidence = list(seen.values())

    sub_scores = [s["coverage_score"] for s in answered if s.get("coverage_score") is not None]
    agg_coverage_score = round(sum(sub_scores) / len(sub_scores), 4) if sub_scores else 0.0

    return {
        "can_answer": True,
        "coverage": coverage,
        "answer": combined_answer,
        "evidence_chunks": all_evidence,
        "supported_points": [pt for s in answered for pt in s["result"]["supported_points"]],
        "missing_points": [s["subquery"] for s in unanswered],
        "coverage_score": agg_coverage_score,
    }


async def send_message(
    db: AsyncSession,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    content: str,
) -> dict | None:
    # — paso 1: verificar o crear conversación —
    if conversation_id is None:
        conversation = Conversation(
            organization_id=organization_id,
            title=_derive_title(content),
        )
        db.add(conversation)
        await db.flush()
        conversation_id = conversation.id
    else:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.organization_id == organization_id,
            )
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            return None
        conversation.updated_at = datetime.now(timezone.utc)

    # — paso 2: guardar mensaje user (commit 1) —
    user_message = Message(
        conversation_id=conversation_id,
        organization_id=organization_id,
        role="user",
        content=content,
    )
    db.add(user_message)
    await db.commit()

    # — paso 2.5: clasificación de query — cortocircuito antes del pipeline —
    classification = classify_query(content)
    if classification in ("out_of_scope", "generic"):
        _EARLY_RESPONSES = {
            "out_of_scope": "No tengo información sobre ese tema en los documentos disponibles.",
            "generic": "Podés hacer preguntas específicas sobre la información cargada en el sistema.",
        }
        early_answer = _EARLY_RESPONSES[classification]

        assistant_message = Message(
            conversation_id=conversation_id,
            organization_id=organization_id,
            role="assistant",
            content=early_answer,
            model_used=settings.chat_model,
        )
        db.add(assistant_message)
        await db.commit()
        await db.refresh(assistant_message)

        logger.info("Query clasificada como %r — pipeline omitido.", classification)

        return {
            "id": assistant_message.id,
            "conversation_id": assistant_message.conversation_id,
            "organization_id": assistant_message.organization_id,
            "role": "assistant",
            "content": assistant_message.content,
            "model_used": assistant_message.model_used,
            "created_at": assistant_message.created_at,
            "sources_count": 0,
            "documents_count": 0,
            "has_sufficient_evidence": False,
            "is_partial_answer": False,
            "debug": None,
            "citations": [],
        }

    # — paso 3+4: descomposición → expansion → retrieval → juez LLM —
    subqueries = query_decomposition.decompose_query(content)
    logger.info(
        "Query decomposition: %d subqueries from %r",
        len(subqueries), content[:60],
    )

    try:
        if len(subqueries) == 1:
            sub = await _run_single_query(db, organization_id, content)

            can_answer = sub["result"]["can_answer"]
            coverage = sub["result"]["coverage"]
            supported_points = sub["result"]["supported_points"]
            missing_points = sub["result"]["missing_points"]
            evidence_chunks = sub["evidence_chunks"]
            answer = _format_answer(sub["result"]["answer"], coverage, missing_points)

            coverage_score = sub["coverage_score"]

            # Debug metadata
            reformulations = sub["reformulations"]
            chunks_before_dedup = sub["chunks_before"]
            chunks_after_dedup = sub["chunks_after"]
            debug_distances = [
                {"chunk_index": c.get("chunk_index"), "distance": round(c.get("distance", 0), 4), "score": c.get("score")}
                for c in sub["all_chunks"]
            ]
            debug_sub_results = None

        else:
            subs: list[dict] = []
            for sq in subqueries:
                try:
                    subs.append(await _run_single_query(db, organization_id, sq))
                except Exception as e:
                    logger.error("Error en subquery %r: %s", sq, e)
                    # Treat as unanswered rather than raising
                    subs.append({
                        "subquery": sq,
                        "result": {
                            "can_answer": False, "coverage": "none",
                            "answer": "", "supported_points": [], "missing_points": [],
                            "evidence_indexes": [],
                        },
                        "evidence_chunks": [],
                        "reformulations": [],
                        "chunks_before": 0,
                        "chunks_after": 0,
                        "all_chunks": [],
                        "coverage_score": 0.0,
                    })

            agg = _aggregate_sub_results(subs)

            can_answer = agg["can_answer"]
            coverage = agg["coverage"]
            coverage_score = agg.get("coverage_score", 0.0)
            supported_points = agg["supported_points"]
            missing_points = agg["missing_points"]
            evidence_chunks = agg["evidence_chunks"]
            answer = agg["answer"]  # already includes inline missing sections

            # Debug metadata
            reformulations = [r for s in subs for r in s["reformulations"]]
            chunks_before_dedup = sum(s["chunks_before"] for s in subs)
            chunks_after_dedup = sum(s["chunks_after"] for s in subs)
            debug_distances = []  # omit per-chunk distances for multi-query (too verbose)
            debug_sub_results = [
                {
                    "subquery": s["subquery"],
                    "coverage": s["result"]["coverage"],
                    "coverage_score": s.get("coverage_score", 0.0),
                    "supported_points": s["result"]["supported_points"],
                    "missing_points": s["result"]["missing_points"],
                }
                for s in subs
            ]

    except Exception as e:
        logger.error("Error al generar respuesta para conversación %s: %s", conversation_id, e)
        raise MessageProcessingError("Error al generar la respuesta del asistente") from e

    logger.info(
        "Retrieval summary: subqueries=%d chunks_before_dedup=%d chunks_after_dedup=%d coverage=%s",
        len(subqueries), chunks_before_dedup, chunks_after_dedup, coverage,
    )

    # — paso 5: guardar mensaje assistant + citations (commit 2) —
    assistant_message = Message(
        conversation_id=conversation_id,
        organization_id=organization_id,
        role="assistant",
        content=answer,
        model_used=settings.chat_model,
    )
    db.add(assistant_message)
    await db.flush()

    citations: list[Citation] = []
    for chunk in evidence_chunks:
        citation = Citation(
            message_id=assistant_message.id,
            chunk_id=chunk["chunk_id"],
            document_id=chunk["document_id"],
            organization_id=organization_id,
            content=chunk["content"],
            chunk_index=chunk["chunk_index"],
            distance=chunk["distance"],
        )
        db.add(citation)
        citations.append(citation)

    await db.commit()
    await db.refresh(assistant_message)
    for citation in citations:
        await db.refresh(citation)

    # — paso 6: registrar query log (producto) —
    try:
        query_log = QueryLog(
            organization_id=organization_id,
            query=content,
            coverage=coverage,
            coverage_score=coverage_score,
        )
        db.add(query_log)
        await db.commit()
    except Exception as e:
        logger.error("Error al guardar query log: %s", e)

    sources_count = len(citations)
    documents_count = len({c.document_id for c in citations})

    debug = None
    if settings.debug:
        debug = {
            # Decomposition
            "query_original": content,
            "decomposed_queries": subqueries,
            "reformulations": reformulations,
            # Retrieval
            "chunks_before_dedup": chunks_before_dedup,
            "chunks_after_dedup": chunks_after_dedup,
            "distances": debug_distances,
            # Judge decision
            "coverage": coverage,
            "coverage_score": coverage_score,
            "supported_points": supported_points,
            "missing_points": missing_points,
            "relevant_chunks_count": len(evidence_chunks),
            # Per-subquery detail (multi-query only)
            "sub_results": debug_sub_results,
            # Fallback info
            "fallback": not can_answer,
            "fallback_reason": (
                "no_relevant_chunks" if not evidence_chunks and not can_answer
                else ("llm_judge_none" if not can_answer else None)
            ),
        }

    return {
        "id": assistant_message.id,
        "conversation_id": assistant_message.conversation_id,
        "organization_id": assistant_message.organization_id,
        "role": "assistant",
        "content": assistant_message.content,
        "model_used": assistant_message.model_used,
        "created_at": assistant_message.created_at,
        "sources_count": sources_count,
        "documents_count": documents_count,
        "has_sufficient_evidence": coverage == "full",
        "is_partial_answer": coverage == "partial",
        "debug": debug,
        "citations": [
            {
                "id": c.id,
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "filename": evidence_chunks[i].get("filename"),
                "content": c.content,
                "chunk_index": c.chunk_index,
                "distance": c.distance,
                "created_at": c.created_at,
            }
            for i, c in enumerate(citations)
        ],
    }


async def add_message(
    db: AsyncSession,
    organization_id: uuid.UUID,
    conversation_id: uuid.UUID,
    content: str,
    role: Literal["user", "assistant"],
    model_used: str | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation_id,
        organization_id=organization_id,
        role=role,
        content=content,
        model_used=model_used,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message
