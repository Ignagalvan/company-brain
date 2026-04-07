"""
document_draft_service.py

Deterministic, LLM-free template engine for document drafts.

Rules:
- No empty bullet lines (every bullet has real content)
- Minimum 4 substantive bullet points per template
- All templates include a "Notas importantes" footer
- Topics are classified via normalized keyword matching (accent-insensitive)
"""

import unicodedata


def _normalize(text: str) -> str:
    """Lowercase + strip accents. Mirrors expansion_service._normalize."""
    return unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()


# ─── Templates ────────────────────────────────────────────────────────────────

_TEMPLATE_PAYMENT = """\
Métodos de pago del servicio

Tarjetas aceptadas:
- Visa
- Mastercard
- American Express

Otros métodos disponibles:
- Transferencia bancaria (disponible para planes Pro y Enterprise)
- PayPal (disponible para todos los planes)
- Débito automático en cuenta bancaria

Frecuencia de facturación:
- Mensual: cobro al inicio de cada mes
- Anual: cobro único con descuento del 20% sobre el precio mensual

Proceso de cobro:
El cobro se realiza automáticamente al inicio de cada período. Se envía
un comprobante al email registrado en la cuenta. Los pagos fallidos se
reintentan hasta tres veces antes de suspender el acceso.

Cancelación y reembolsos:
- Se puede cancelar en cualquier momento desde el panel de usuario
- No hay cargos por cancelación anticipada
- Los planes anuales tienen reembolso proporcional si se cancelan antes de los 6 meses
- Los pagos del mes en curso no son reembolsables

Notas importantes:
- Los precios no incluyen impuestos locales (IVA u otros según jurisdicción)
- Para facturación empresarial con número de CUIT/RFC, contactar al área de ventas
- Los datos de pago se almacenan en forma segura y nunca se guardan en nuestros servidores
"""

_TEMPLATE_TRIAL = """\
Período de prueba gratuita

Disponibilidad:
Company Brain ofrece un período de prueba gratuita sin necesidad de tarjeta
de crédito. La prueba comienza automáticamente al crear una cuenta nueva.

Duración y condiciones:
- Duración: 14 días calendario desde la activación de la cuenta
- Sin tarjeta de crédito requerida para comenzar
- Sin límite de documentos ni consultas durante la prueba
- Los datos cargados se conservan al contratar un plan pago

Qué incluye la prueba:
- Acceso completo a todas las funcionalidades del plan Pro
- Carga y procesamiento de documentos ilimitada
- Búsqueda semántica y respuestas con evidencia
- Soporte técnico por email incluido
- Panel de administración completo

Al finalizar la prueba:
Si no se contrata ningún plan, la cuenta pasa a modo inactivo: los datos
se conservan por 30 días adicionales antes de ser eliminados. Se envía un
recordatorio por email 3 días antes del vencimiento.

Cómo activar la prueba:
1. Registrarse en el sitio web con un email válido
2. Confirmar el email de verificación
3. La prueba comienza de forma inmediata, sin pasos adicionales

Notas importantes:
- Solo disponible para cuentas nuevas (una prueba por organización)
- Para equipos de más de 10 usuarios, consultar el plan Enterprise con prueba extendida
- Los documentos cargados durante la prueba cuentan para los límites del plan que se contrate
"""

_TEMPLATE_PRICING = """\
Planes y precios del servicio

Resumen de planes:
- Plan Básico: acceso esencial para pequeños equipos (hasta 5 usuarios)
- Plan Pro: funcionalidades completas para equipos medianos (hasta 20 usuarios)
- Plan Enterprise: personalizado para grandes organizaciones (usuarios ilimitados)

Precios mensuales:
- Plan Básico: USD 29/mes por organización
- Plan Pro: USD 79/mes por organización
- Plan Enterprise: precio personalizado según volumen

Descuentos disponibles:
- Pago anual: 20% de descuento sobre el precio mensual
- Organizaciones sin fines de lucro: descuento del 30% (sujeto a verificación)
- Startups en etapa inicial: programa especial disponible, consultar ventas

Diferencias entre planes:
- Básico: hasta 50 documentos, 500 consultas/mes, soporte por email
- Pro: documentos ilimitados, consultas ilimitadas, soporte prioritario, API access
- Enterprise: todo el plan Pro más SLA garantizado, SSO, y soporte dedicado

Cambios de plan:
- Se puede cambiar de plan en cualquier momento desde el panel
- Los upgrades aplican inmediatamente con cobro proporcional
- Los downgrades aplican al inicio del siguiente período de facturación

Notas importantes:
- Todos los precios en USD sin impuestos incluidos
- Los precios pueden cambiar con 30 días de aviso previo a los clientes activos
- Los planes incluyen actualizaciones de funcionalidades sin costo adicional
"""

_TEMPLATE_CONTACT = """\
Información de contacto y soporte

Canales de contacto disponibles:
- Email de soporte: soporte@companybrain.com (respuesta en menos de 24h hábiles)
- Chat en vivo: disponible en el panel de usuario (lunes a viernes, 9h-18h UTC-3)
- Teléfono: +54 351 000 0000 (solo para planes Pro y Enterprise)
- Portal de soporte: https://soporte.companybrain.com

Horarios de atención:
- Soporte por email: 24/7 con respuesta garantizada en 24h hábiles
- Chat en vivo: lunes a viernes de 9:00 a 18:00 hs (Argentina, UTC-3)
- Teléfono: lunes a viernes de 9:00 a 17:00 hs
- Guardias de emergencia (Enterprise): disponibles 24/7 para incidentes críticos

Tiempo de respuesta por plan:
- Plan Básico: respuesta en 24h hábiles por email
- Plan Pro: respuesta en 8h hábiles, acceso a chat en vivo
- Plan Enterprise: SLA de 2h para incidentes críticos, gerente de cuenta asignado

Para reportar un problema:
1. Describir el problema con el mayor detalle posible
2. Incluir capturas de pantalla si es relevante
3. Indicar el plan y la cantidad de usuarios afectados
4. Enviar a soporte@companybrain.com con asunto claro

Notas importantes:
- Para integraciones y API, existe documentación técnica en docs.companybrain.com
- Los incidentes de seguridad se deben reportar a seguridad@companybrain.com
- Para solicitudes de facturación o cambios de plan, contactar a ventas@companybrain.com
"""

_TEMPLATE_TECH = """\
Stack tecnológico y arquitectura del sistema

Backend:
- Lenguaje principal: Python 3.12
- Framework web: FastAPI
- Base de datos relacional: PostgreSQL 15
- Búsqueda vectorial: pgvector (extensión de PostgreSQL)
- ORM: SQLAlchemy con soporte async

Inteligencia artificial y embeddings:
- Modelo de embeddings: OpenAI text-embedding-3-small
- Dimensiones del vector: 1536
- Modelo de respuestas: GPT-4o (configurable por plan)
- Chunking: algoritmo jerárquico propio (sección → párrafo → oración)

Frontend:
- Framework: Next.js 16 con App Router
- Lenguaje: TypeScript
- Estilos: Tailwind CSS
- Despliegue: compatible con Vercel, Netlify o servidor propio

Infraestructura y operaciones:
- Contenedores: Docker + Docker Compose para desarrollo local
- CI/CD: GitHub Actions
- Almacenamiento de archivos: sistema de archivos local (configurable para S3)
- Monitoreo: logs estructurados compatibles con Datadog y CloudWatch

Integraciones disponibles:
- REST API documentada con OpenAPI/Swagger
- Autenticación: API key por organización (OAuth2 en roadmap)
- Exportación: JSON, CSV para datos de consultas y documentos

Notas importantes:
- El sistema es multi-tenant: cada organización tiene aislamiento completo de datos
- Los embeddings se regeneran automáticamente si se actualiza el modelo
- El código fuente del core es privado; la API es pública y estable
"""

_TEMPLATE_PRODUCT = """\
Descripción del producto y propuesta de valor

Qué es Company Brain:
Company Brain es una plataforma SaaS de gestión del conocimiento empresarial.
Permite a los equipos centralizar su documentación interna y consultarla en
lenguaje natural, obteniendo respuestas respaldadas por evidencia verificable.

Problema que resuelve:
- Conocimiento fragmentado en múltiples herramientas (emails, docs, Notion, Drive)
- Dependencia de personas clave que concentran información crítica
- Tiempo perdido buscando respuestas que ya están documentadas en algún lado
- Riesgo de pérdida de conocimiento ante rotación de personal
- Respuestas inconsistentes según quién responde la consulta

Solución:
- Centralización de documentos en un único repositorio con búsqueda semántica
- Respuestas en lenguaje natural con cita exacta del fragmento fuente
- Sistema anti-alucinación: si la información no está, lo dice explícitamente
- Detección automática de gaps de conocimiento no documentado
- Loop de mejora: el sistema sugiere qué documentar primero

Casos de uso principales:
- Onboarding de nuevos empleados (reducción del 60% en tiempo de ramp-up)
- Soporte interno: respuestas consistentes sin depender de expertos disponibles
- Auditorías y compliance: trazabilidad completa de cada respuesta
- Gestión del conocimiento en equipos distribuidos o remotos

Diferenciadores clave:
- Respuestas con evidencia: cada respuesta cita el fragmento exacto que la respalda
- Multi-tenant seguro: aislamiento completo entre organizaciones
- Mejora continua: el sistema aprende de las consultas sin respuesta

Notas importantes:
- No es un chatbot genérico: solo responde con información de tus documentos
- No almacena las consultas para entrenar modelos de terceros
- Compatible con documentos en español e inglés
"""

_TEMPLATE_GENERIC = """\
Documentación sobre: {topic}

Descripción general:
Esta sección documenta información sobre {topic} para uso interno del equipo.
Completar con los detalles específicos de la organización.

Información principal:
- Definición o descripción del concepto
- Alcance y aplicabilidad dentro de la organización
- Responsable o equipo a cargo
- Vigencia o fecha de última actualización

Procedimiento o pasos relevantes:
1. Identificar el caso de uso o situación aplicable
2. Consultar con el responsable designado si hay dudas
3. Documentar cualquier excepción o caso especial
4. Actualizar este documento si hay cambios en el proceso

Referencias y recursos:
- Documento relacionado 1: [agregar enlace]
- Documento relacionado 2: [agregar enlace]
- Contacto responsable: [agregar nombre y email]

Preguntas frecuentes sobre este tema:
- ¿Cuál es el proceso estándar? [completar]
- ¿Quién es el responsable? [completar]
- ¿Con qué frecuencia se actualiza? [completar]
- ¿Dónde se puede consultar más información? [completar]

Notas importantes:
- Este documento es un borrador inicial generado automáticamente
- Debe ser revisado y completado por el equipo responsable antes de publicarse
- Última actualización: pendiente de completar
"""


# ─── Classification ───────────────────────────────────────────────────────────

# Ordered list: first match wins. More specific rules come first.
_RULES: list[tuple[list[str], str]] = [
    (["paga", "pago", "cobro", "factura", "facturacion", "cobrar", "abonar"], "payment"),
    (["prueba", "gratis", "trial", "gratuito", "free", "demo gratuita"], "trial"),
    (["precio", "cuesta", "costo", "plan basico", "plan pro", "plan enterprise", "tarifa"], "pricing"),
    (["telefono", "contacto", "email", "soporte", "atencion al cliente", "horario"], "contact"),
    (["tecnologia", "tecnologias", "stack", "backend", "frontend", "infraestructura", "framework", "arquitectura"], "technical"),
    (["problema", "resuelve", "solucion", "producto", "propuesta de valor", "que es"], "product"),
]


def _classify(topic: str) -> str:
    """Return draft_type for topic using normalized keyword matching. No LLM."""
    t = _normalize(topic)
    for keywords, draft_type in _RULES:
        if any(kw in t for kw in keywords):
            return draft_type
    return "generic"


# ─── Template dispatch ────────────────────────────────────────────────────────

_TEMPLATES: dict[str, str] = {
    "payment":   _TEMPLATE_PAYMENT,
    "trial":     _TEMPLATE_TRIAL,
    "pricing":   _TEMPLATE_PRICING,
    "contact":   _TEMPLATE_CONTACT,
    "technical": _TEMPLATE_TECH,
    "product":   _TEMPLATE_PRODUCT,
}


def _match_template(topic: str) -> tuple[str, str]:
    """Return (template_content, draft_type) for the given topic."""
    draft_type = _classify(topic)
    if draft_type == "generic":
        # Truncate long topics so they don't repeat verbatim and hurt readability
        display_topic = topic if len(topic) <= 60 else topic[:57] + "..."
        return _TEMPLATE_GENERIC.format(topic=display_topic), "generic"
    return _TEMPLATES[draft_type], draft_type


# ─── Public API (unchanged contracts) ────────────────────────────────────────

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
    title_topic = topic if len(topic) <= 60 else topic[:57] + "..."
    return {
        "draft_content": content,
        "draft_type": draft_type,
        "draft_title": f"Borrador: {title_topic}",
    }
