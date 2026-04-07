"""
Compare vector-only vs hybrid retrieval for common support / pricing queries.

Usage from backend/:
    python -m scripts.diagnose_retrieval
    python -m scripts.diagnose_retrieval --org-id <organization_id>

Without --org-id, the script seeds a temporary org with a deterministic demo
document that includes:
  - payment methods
  - support email
  - professional plan inclusions
"""

import argparse
import asyncio
import json
import os
import uuid

from sqlalchemy import select

from src.database import AsyncSessionLocal
from src.models.document import Document
from src.models.document_chunk import DocumentChunk
from src.services.document_service import ingest_text_as_document
from src.services.expansion_service import expand_query
from src.services.retrieval_service import search_chunks

_FILLER_PRODUCTO = " ".join(
    ["La plataforma mejora procesos internos, soporte operativo y seguimiento de equipos."] * 18
)
_FILLER_OPERATIVO = " ".join(
    ["El equipo revisa pagos, soporte, planes y configuracion durante la implementacion."] * 18
)
_FILLER_CLIENTES = " ".join(
    ["Los clientes usan la herramienta para consultas, adopcion y administracion del conocimiento."] * 18
)

DEMO_TEXT = f"""
RESUMEN GENERAL

Company Brain centraliza conocimiento interno, mejora la cobertura de respuestas y reduce consultas repetidas. {_FILLER_PRODUCTO}

OPERACION ADMINISTRATIVA

El equipo administrativo coordina planes, pagos, soporte y onboarding. {_FILLER_OPERATIVO}

PLAN PROFESIONAL

El plan profesional incluye acceso multiusuario, panel de analitica, integraciones con CRM, soporte prioritario y exportacion de reportes. {_FILLER_CLIENTES}

FORMAS DE PAGO

Aceptamos tarjetas de credito y debito, transferencia bancaria y Mercado Pago. {_FILLER_OPERATIVO}

CONTACTO DE SOPORTE

El email de soporte es soporte@companybrain.ai. Nuestro equipo responde de lunes a viernes. {_FILLER_PRODUCTO}
""".strip()

CASES = [
    {
        "query": "¿Qué medios de pago aceptan?",
        "expected_terms": ["mercado pago", "transferencia bancaria"],
    },
    {
        "query": "¿Cuál es el email de soporte?",
        "expected_terms": ["soporte@companybrain.ai"],
    },
    {
        "query": "¿Qué incluye el plan profesional?",
        "expected_terms": ["acceso multiusuario", "soporte prioritario"],
    },
]


def _hit_rank(rows: list[dict], expected_terms: list[str]) -> int | None:
    normalized_terms = [term.lower() for term in expected_terms]
    for index, row in enumerate(rows, start=1):
        content = row["content"].lower()
        if any(term in content for term in normalized_terms):
            return index
    return None


async def _ensure_demo_org() -> uuid.UUID:
    organization_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        await ingest_text_as_document(
            db,
            organization_id,
            "retrieval_demo.txt",
            DEMO_TEXT,
        )
    return organization_id


async def _print_chunking(org_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        docs = (await db.execute(select(Document).where(Document.organization_id == org_id))).scalars().all()
        chunks = (
            await db.execute(
                select(DocumentChunk)
                .where(DocumentChunk.organization_id == org_id)
                .order_by(DocumentChunk.chunk_index.asc())
            )
        ).scalars().all()

    print(f"ORG={org_id}")
    print(f"DOCUMENTS={len(docs)} CHUNKS={len(chunks)}")
    for chunk in chunks[:5]:
        preview = chunk.content[:220].replace("\n", " ")
        print(json.dumps({"chunk_index": chunk.chunk_index, "preview": preview}, ensure_ascii=False))


async def _run_case(org_id: uuid.UUID, query: str, expected_terms: list[str]) -> None:
    expanded_queries = await expand_query(query)
    async with AsyncSessionLocal() as db:
        vector_rows = await search_chunks(db, org_id, query, top_k=5, strategy="vector")
        hybrid_rows = await search_chunks(db, org_id, query, top_k=5, strategy="hybrid")

    print(f"\nQUERY={query}")
    print(
        json.dumps(
            {
                "expanded_queries": expanded_queries,
                "expected_terms": expected_terms,
                "vector_hit_rank": _hit_rank(vector_rows, expected_terms),
                "hybrid_hit_rank": _hit_rank(hybrid_rows, expected_terms),
            },
            ensure_ascii=False,
        )
    )

    print("VECTOR_TOP")
    for index, row in enumerate(vector_rows, start=1):
        print(
            json.dumps(
                {
                    "rank": index,
                    "chunk_index": row["chunk_index"],
                    "distance": row["distance"],
                    "preview": row["content"][:220],
                },
                ensure_ascii=False,
            )
        )

    print("HYBRID_TOP")
    for index, row in enumerate(hybrid_rows, start=1):
        print(
            json.dumps(
                {
                    "rank": index,
                    "chunk_index": row["chunk_index"],
                    "distance": row["distance"],
                    "hybrid_score": row.get("hybrid_score"),
                    "keyword_overlap": row.get("keyword_overlap"),
                    "section_match": row.get("section_match"),
                    "preview": row["content"][:220],
                },
                ensure_ascii=False,
            )
        )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose retrieval for real support / pricing queries.")
    parser.add_argument("--org-id", type=uuid.UUID, help="Existing organization UUID to inspect")
    args = parser.parse_args()

    os.environ.setdefault("DEBUG", "false")

    org_id = args.org_id if args.org_id else await _ensure_demo_org()
    await _print_chunking(org_id)

    for case in CASES:
        await _run_case(org_id, case["query"], case["expected_terms"])


if __name__ == "__main__":
    asyncio.run(main())
