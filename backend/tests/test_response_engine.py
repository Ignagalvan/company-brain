#!/usr/bin/env python3
"""
test_response_engine.py
━━━━━━━━━━━━━━━━━━━━━━━
Evaluador de confiabilidad del motor de respuestas de Company Brain.
Envía preguntas al endpoint real y valida el comportamiento esperado.

Cómo correrlo:
    python backend/tests/test_response_engine.py
    python backend/tests/test_response_engine.py <org-id>   # con documentos reales

    El segundo modo testea casos positivos contra una org que ya tenga documentos.

Requiere:
    - backend corriendo en BASE_URL (default: http://localhost:8000)
    - pip install httpx  (si no está instalado)

Para testear con documentos reales:
    1. Subí un documento via POST /documents/upload con un X-Organization-Id fijo
    2. Anotá ese org-id
    3. Corré: python backend/tests/test_response_engine.py <ese-org-id>
    4. Descomentá y completá los casos marcados con [CONFIGURAR] al final de CASES
"""

import sys
import uuid

# Windows cp1252 fix: force UTF-8 so box-drawing chars and accents render correctly
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import httpx
except ImportError:
    print("ERROR: httpx no está instalado. Corré: pip install httpx")
    sys.exit(1)


# ─── Configuración ────────────────────────────────────────────────────────────

BASE_URL = "http://localhost:8000"
ENDPOINT = f"{BASE_URL}/conversations/messages"
TIMEOUT_SECONDS = 45  # cada request puede tardar por expansion + LLM judge

# Pasá un org-id como argumento o editá esta constante para testear con docs reales.
# Con una UUID nueva (default), solo los casos negativos son verificables.
ORG_ID = sys.argv[1] if len(sys.argv) > 1 else str(uuid.uuid4())

# Texto presente en todas las respuestas sin evidencia
FALLBACK_TEXT = "No se encontró información en los documentos disponibles"


# ─── Casos de prueba ──────────────────────────────────────────────────────────
# expected : "full" | "partial" | "none"
# skip     : True → el caso se omite (marcalo como skip hasta tener docs reales)
# note     : describe qué valida y por qué

CASES = [
    # ── 1. Negativos universales ───────────────────────────────────────────────
    # No necesitan documentos. SIEMPRE deben retornar "none".
    # Si alguno falla → alucinación.
    {
        "question": "¿Cuánto mide la luna en kilómetros?",
        "expected": "none",
        "note": "astronomía — fuera de cualquier base de conocimiento empresarial",
    },
    {
        "question": "¿Cuál es la capital de Francia?",
        "expected": "none",
        "note": "geografía general — no debería aparecer en docs internos",
    },
    {
        "question": "¿Quién ganó el Mundial de Fútbol 2022?",
        "expected": "none",
        "note": "evento deportivo externo — fuera de contexto",
    },
    {
        "question": "Explicame la teoría de la relatividad de Einstein",
        "expected": "none",
        "note": "física — el sistema no debe inventar información científica",
    },
    {
        "question": "¿Cuánto cuesta un iPhone 15 Pro Max?",
        "expected": "none",
        "note": "producto de consumo externo — no debe estar en docs internos",
    },
    # ── 2. Borderline — no deben alucinarse ───────────────────────────────────
    # Sin documentos relevantes → "none". Validan que el sistema no improvise.
    {
        "question": "Dame un resumen completo de todo lo que sabés",
        "expected": "none",
        "note": "query vaga y abierta — no debe generar respuesta inventada",
    },
    {
        "question": "¿Qué podés hacer vos?",
        "expected": "none",
        "note": "meta-pregunta sobre el sistema — no debe responderse con docs",
    },
    {
        "question": "Contame algo interesante",
        "expected": "none",
        "note": "pedido abierto sin contexto — no debe alucinarse",
    },
    # ── 3. Full — respuesta completa esperada ─────────────────────────────────
    # Preguntas directas sobre contenido documentado en org 00000000-0000-0000-0000-000000000001.
    # Deben retornar coverage="full" con citations.
    # Correr con: python test_response_engine.py 00000000-0000-0000-0000-000000000001
    {
        "question": "¿Cuál es el objetivo de Company Brain?",
        "expected": "full",
        "note": "pregunta directa — objetivo/propósito explícito en el doc",
    },
    {
        "question": "¿Qué tecnologías usa el backend?",
        "expected": "full",
        "note": "sección de arquitectura técnica — vocabulario directo del doc",
    },
    {
        "question": "¿Qué debe responder el sistema cuando no existe evidencia suficiente?",
        "expected": "full",
        "note": "comportamiento ante falta de evidencia — documentado explícitamente",
    },
    # ── 4. Semánticos / reformulados ──────────────────────────────────────────
    # Vocabulario distinto al del doc. Validan que query expansion encuentre la evidencia.
    # Si fallan → la expansión no genera la reformulación correcta o el threshold es alto.
    {
        "question": "¿Para qué sirve esta plataforma?",
        "expected": "full",
        "note": "reformulación del objetivo — valida expansion con sinónimos de 'Company Brain'",
    },
    {
        "question": "¿Qué problema resuelve Company Brain en las organizaciones?",
        "expected": "full",
        "note": "ángulo 'problema' — puede no estar textual, valida expansión semántica",
    },
    {
        "question": "¿Cómo ayuda este sistema a centralizar el conocimiento interno?",
        "expected": "full",
        "note": "reformulación de capacidades — vocabulario alternativo al documento",
    },
    # ── 5. Parciales — una parte tiene evidencia, la otra no ──────────────────
    # Diseño: parte A claramente en el doc + parte B claramente ausente.
    # El juez LLM debe devolver coverage="partial".
    # Si retorna "full" → sobreconfianza (el LLM inventó la parte B).
    # Si retorna "none" → falso negativo (no encontró la parte A).
    {
        "question": "¿Cuál es el objetivo de Company Brain y cuál es su número de teléfono de soporte?",
        "expected": "partial",
        "note": "objetivo: en doc / teléfono: no existe en doc — caso parcial claro",
    },
    {
        "question": "¿Qué tecnologías usa el backend y cuánto cuesta suscribirse al servicio?",
        "expected": "partial",
        "note": "stack técnico: en doc / precio de suscripción: no documentado",
    },
    {
        "question": "¿Qué problema resuelve la plataforma y cuál es su número de teléfono de contacto?",
        "expected": "partial",
        "note": "problema/propósito: en doc / teléfono: no existe en doc — parte ausente con embedding neutro",
    },
]


# ─── Lógica de detección ──────────────────────────────────────────────────────

def detect_coverage(data: dict) -> str:
    """
    Infiere coverage a partir de la respuesta del endpoint.

    Prioridad:
      1. debug.coverage  — autoritativo, disponible si el backend corre con DEBUG=true
      2. has_sufficient_evidence → "full"
      3. is_partial_answer       → "partial"
      4. sources_count == 0      → "none"
      5. sources > 0 sin flags   → "partial" (tiene evidencia pero no full)
    """
    debug = data.get("debug") or {}
    if "coverage" in debug:
        return debug["coverage"]

    if data.get("has_sufficient_evidence"):
        return "full"
    if data.get("is_partial_answer"):
        return "partial"
    if data.get("sources_count", 0) == 0:
        return "none"
    return "partial"


def classify_error(expected: str, actual: str) -> str:
    """Clasifica el tipo de falla para diagnóstico."""
    if expected == "none" and actual in ("full", "partial"):
        return "ALUCINACION — respondió sin evidencia real"
    if expected in ("full", "partial") and actual == "none":
        return "FALSO NEGATIVO — no respondió cuando había evidencia"
    if expected == "full" and actual == "partial":
        return "COBERTURA BAJA — respondió parcial cuando debía ser completo"
    if expected == "partial" and actual == "full":
        return "SOBRECONFIANZA — marcó evidencia completa en respuesta parcial"
    return f"MISMATCH — esperado={expected} actual={actual}"


# ─── Ejecución ────────────────────────────────────────────────────────────────

def run_case(client: httpx.Client, case: dict) -> dict:
    """Envía una pregunta al endpoint y retorna el resultado del test."""
    question = case["question"]
    expected = case["expected"]

    try:
        response = client.post(
            ENDPOINT,
            json={"content": question},
            headers={"X-Organization-Id": ORG_ID},
            timeout=TIMEOUT_SECONDS,
        )
    except httpx.ConnectError:
        return {
            "status": "ERROR",
            "error": f"no se pudo conectar a {BASE_URL} — ¿está el backend corriendo?",
        }
    except httpx.TimeoutException:
        return {
            "status": "ERROR",
            "error": f"timeout después de {TIMEOUT_SECONDS}s",
        }
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

    if response.status_code != 201:
        snippet = response.text[:120].replace("\n", " ")
        return {
            "status": "ERROR",
            "error": f"HTTP {response.status_code}: {snippet}",
        }

    data = response.json()
    actual = detect_coverage(data)
    passed = actual == expected

    return {
        "status": "OK" if passed else "FAIL",
        "expected": expected,
        "actual": actual,
        "sources_count": data.get("sources_count", 0),
        "citations_count": len(data.get("citations", [])),
        "is_fallback": FALLBACK_TEXT in data.get("content", ""),
        "error_type": None if passed else classify_error(expected, actual),
        "content_preview": data.get("content", "")[:90].replace("\n", " "),
        "debug_coverage": (data.get("debug") or {}).get("coverage"),
        "debug_reformulations": (data.get("debug") or {}).get("reformulations"),
    }


# ─── Output ───────────────────────────────────────────────────────────────────

W = 74  # line width

def _pad(s: str, n: int) -> str:
    return s.ljust(n)


def print_header():
    print(f"\n{'━' * W}")
    print("  Company Brain — Test de confiabilidad del motor de respuestas")
    print(f"{'━' * W}")
    print(f"  Endpoint : {ENDPOINT}")
    print(f"  Org ID   : {ORG_ID}")
    active = sum(1 for c in CASES if not c.get("skip"))
    skipped = sum(1 for c in CASES if c.get("skip"))
    print(f"  Casos    : {active} activos, {skipped} omitidos")
    print(f"{'━' * W}\n")


def print_result_line(result: dict, question: str):
    status = _pad(result["status"], 5)
    if result["status"] == "ERROR":
        print(f"  {status} | {'ERROR':7} | {question[:52]}")
        print(f"          └─ {result['error']}")
        return

    actual   = _pad(result.get("actual", "?"), 7)
    expected = _pad(result["expected"], 7)
    q = question[:52]
    src = result.get("sources_count", 0)
    print(f"  {status} | actual={actual} expected={expected} | src={src} | {q}")

    if result["status"] == "FAIL":
        print(f"          └─ {result['error_type']}")
        print(f"          └─ respuesta: \"{result['content_preview']}\"")
        if result.get("debug_reformulations"):
            refs = ", ".join(f'"{r}"' for r in result["debug_reformulations"])
            print(f"          └─ reformulaciones: {refs}")


def print_summary(results: list[dict]):
    ok     = sum(1 for r in results if r["status"] == "OK")
    fail   = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")
    skipped = sum(1 for c in CASES if c.get("skip"))

    print(f"\n{'━' * W}")
    print(f"  Total: {len(results)} | ✓ OK: {ok} | ✗ FAIL: {fail} | ⚠ ERROR: {errors} | — SKIP: {skipped}")
    print(f"{'━' * W}")

    failures = [r for r in results if r["status"] == "FAIL"]
    if failures:
        print(f"\n  Fallas ({len(failures)}):")
        for r in failures:
            print(f"\n  • {r['error_type']}")
            print(f"    Pregunta : {r['question']}")
            print(f"    Esperado : {r['expected']}   Actual : {r['actual']}")
            print(f"    Nota     : {r['note']}")

    hallucinations = [r for r in results if "ALUCINACION" in (r.get("error_type") or "")]
    if hallucinations:
        print(f"\n  ⚠ ALERTA: {len(hallucinations)} alucinación(es) — el sistema respondió sin evidencia real.")

    false_negatives = [r for r in results if "FALSO NEGATIVO" in (r.get("error_type") or "")]
    if false_negatives:
        print(f"\n  ℹ {len(false_negatives)} falso(s) negativo(s) — el sistema no respondió cuando debía.")

    if ok == len(results) and len(results) > 0:
        print("\n  ✓ Todos los tests activos pasaron.\n")
    print()


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print_header()

    active_cases = [c for c in CASES if not c.get("skip")]
    results: list[dict] = []

    with httpx.Client() as client:
        for i, case in enumerate(active_cases, start=1):
            n = len(active_cases)
            print(f"  [{i:02d}/{n:02d}] {case['question'][:60]}")
            result = run_case(client, case)
            result["question"] = case["question"]
            result["note"] = case.get("note", "")
            results.append(result)
            print_result_line(result, case["question"])

            # Stop immediately if backend is unreachable
            if result["status"] == "ERROR" and "no se pudo conectar" in result.get("error", ""):
                print(f"\n  Backend no disponible. Abortando.\n")
                sys.exit(2)

    print_summary(results)

    has_failures = any(r["status"] in ("FAIL", "ERROR") for r in results)
    sys.exit(1 if has_failures else 0)


if __name__ == "__main__":
    main()
