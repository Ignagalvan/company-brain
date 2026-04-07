import asyncio

from src.services import expansion_service
from src.services import retrieval_service


def test_keyword_overlap_normalizes_accents_and_punctuation():
    query = "¿Cuál es el email de soporte?"
    content = "[CONTACTO DE SOPORTE]\nEl correo de soporte es soporte@companybrain.ai."

    score = retrieval_service._keyword_overlap(query, content)

    assert score > 0.4


def test_hybrid_score_rewards_matching_section_heading():
    query = "¿Qué medios de pago aceptan?"
    generic_chunk = {
        "content": "[RESUMEN GENERAL]\nLa plataforma ofrece funcionalidades para empresas y operaciones.",
        "distance": 0.42,
    }
    payment_chunk = {
        "content": "[FORMAS DE PAGO]\nAceptamos tarjetas de credito, transferencia bancaria y Mercado Pago.",
        "distance": 0.45,
    }

    generic_score = retrieval_service._hybrid_score(query, generic_chunk)
    payment_score = retrieval_service._hybrid_score(query, payment_chunk)

    assert payment_score > generic_score


def test_expand_query_keeps_words_well_formed_with_accents():
    variants = asyncio.run(expansion_service.expand_query("¿Qué medios de pago aceptan?"))

    assert "¿Qué formas de pago aceptan?" in variants
    assert "¿Qué metodos de pago aceptan?" in variants


def test_keyword_overlap_matches_semantic_variants_by_prefix():
    query = "¿Cada cuánto se evalúa el desempeño?"
    content = "[DESEMPENO]\nLas evaluaciones de desempeno son semestrales."

    score = retrieval_service._keyword_overlap(query, content)

    assert score > 0.3


def test_expand_query_adds_renuncia_and_anticipacion_variants():
    variants = asyncio.run(
        expansion_service.expand_query("¿Cuántos días de aviso hay que dar para renunciar?")
    )

    assert any("anticipacion" in variant.lower() for variant in variants)
    assert any("renuncia" in variant.lower() for variant in variants)


def test_hybrid_score_preserves_strong_vector_match():
    query = "¿La información es confidencial?"
    close_semantic_chunk = {
        "content": "[CONFIDENCIALIDAD]\nToda la informacion es confidencial y no puede compartirse fuera de la empresa.",
        "distance": 0.27,
    }
    weaker_but_related_chunk = {
        "content": "[NORMAS GENERALES]\nLa informacion debe manejarse con cuidado, proteccion y procesos internos.",
        "distance": 0.41,
    }

    close_score = retrieval_service._hybrid_score(query, close_semantic_chunk)
    weaker_score = retrieval_service._hybrid_score(query, weaker_but_related_chunk)

    assert close_score > weaker_score
