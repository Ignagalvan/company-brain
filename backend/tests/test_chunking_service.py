from src.services.chunking_service import chunk_text_with_sections


def test_chunking_keeps_section_boundaries_intact():
    text = """
PLAN PROFESIONAL

El plan profesional incluye acceso multiusuario, panel de analitica y soporte prioritario.

FORMAS DE PAGO

Aceptamos tarjetas de credito, transferencia bancaria y Mercado Pago.

CONTACTO DE SOPORTE

El email de soporte es soporte@companybrain.ai. La atencion telefonica funciona de lunes a viernes.
""".strip()

    chunks = chunk_text_with_sections(text, chunk_size=220, overlap=80)

    assert len(chunks) == 3
    assert chunks[0]["section"] == "PLAN PROFESIONAL"
    assert "Mercado Pago" not in chunks[0]["content"]
    assert chunks[1]["section"] == "FORMAS DE PAGO"
    assert "soporte@companybrain.ai" not in chunks[1]["content"]
    assert chunks[2]["section"] == "CONTACTO DE SOPORTE"


def test_chunking_keeps_support_email_and_phone_together():
    text = """
CONTACTO DE SOPORTE

El email de soporte es soporte@companybrain.ai.
La atencion telefonica funciona de lunes a viernes de 9 a 18 horas.
""".strip()

    chunks = chunk_text_with_sections(text, chunk_size=220, overlap=80)

    assert len(chunks) == 1
    assert "soporte@companybrain.ai" in chunks[0]["content"]
    assert "atencion telefonica" in chunks[0]["content"]
