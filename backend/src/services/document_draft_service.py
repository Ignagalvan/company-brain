_TEMPLATE_PRICING = """\
Información sobre precios del servicio

Planes:
- Básico:
- Pro:
- Enterprise:

Precios:
- Básico: $
- Pro: $
- Enterprise: $

Condiciones:
- Facturación:
- Período de prueba:
- Política de reembolso:
"""

_TEMPLATE_CONTACT = """\
Información de contacto

Teléfono:
Email:
Horario de atención:

Canales de soporte:
- Chat:
- Email:
- Teléfono:

Tiempo de respuesta estimado:
"""

_TEMPLATE_TECH = """\
Stack tecnológico

Lenguajes y frameworks:
-
-

Infraestructura:
-
-

Integraciones disponibles:
-
-

Requisitos técnicos:
-
"""

_TEMPLATE_PROBLEM = """\
Descripción del producto / problema que resuelve

Problema:

Solución:

Beneficios principales:
-
-
-

Casos de uso:
-
-
"""

_TEMPLATE_GENERIC = """\
Documentación sobre: {topic}

Descripción:

Detalles:
-
-

Información adicional:
"""


def _match_template(topic: str) -> tuple[str, str]:
    """Return (template_content, draft_type) for the given topic."""
    t = topic.lower()

    if "precio" in t or "cuesta" in t:
        return _TEMPLATE_PRICING, "pricing"

    if "teléfono" in t or "telefono" in t or "contacto" in t:
        return _TEMPLATE_CONTACT, "contact"

    if "tecnología" in t or "tecnologia" in t or "tecnologías" in t or "tecnologias" in t:
        return _TEMPLATE_TECH, "technical"

    if "problema" in t:
        return _TEMPLATE_PROBLEM, "product"

    return _TEMPLATE_GENERIC.format(topic=topic), "generic"


def generate_draft(topic: str) -> str:
    """
    Returns a documentation template for the given topic.
    Matching is keyword-based — no NLP, no LLM, no external dependencies.
    """
    content, _ = _match_template(topic)
    return content


def generate_draft_with_metadata(topic: str) -> dict:
    """
    Returns a dict with draft content, type, and a suggested title.
    Used by the Action Layer to build structured responses.
    """
    content, draft_type = _match_template(topic)
    return {
        "draft_content": content,
        "draft_type": draft_type,
        "draft_title": f"Borrador: {topic}",
    }
