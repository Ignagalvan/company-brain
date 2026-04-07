import asyncio

from src.services import answer_service


class _FakeCompletions:
    async def create(self, **kwargs):
        class _Msg:
            content = '{"can_answer": false, "coverage": "none", "answer": "", "supported_points": [], "missing_points": [], "relevant_chunk_indexes": []}'

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()


class _FakeChat:
    completions = _FakeCompletions()


class _FakeClient:
    chat = _FakeChat()


def test_generate_answer_accepts_direct_negative_evidence(monkeypatch):
    monkeypatch.setattr(answer_service, "_get_client", lambda: _FakeClient())

    chunks = [
        {
            "filename": "politicas.txt",
            "chunk_index": 0,
            "content": "[REEMBOLSOS]\nNo se realizan reembolsos.",
            "distance": 0.61,
            "document_id": "doc-1",
        }
    ]

    result = asyncio.run(answer_service.generate_answer("¿Hay reembolsos?", chunks))

    assert result["can_answer"] is True
    assert result["coverage"] == "full"
    assert "No se realizan reembolsos" in result["answer"]
    assert result["evidence_indexes"] == [0]


def test_generate_answer_accepts_single_line_direct_fact(monkeypatch):
    monkeypatch.setattr(answer_service, "_get_client", lambda: _FakeClient())

    chunks = [
        {
            "filename": "planes.txt",
            "chunk_index": 2,
            "content": "[PLAN PROFESIONAL]\nEl plan profesional incluye acceso multiusuario, soporte prioritario y exportacion de reportes.",
            "distance": 0.58,
            "document_id": "doc-2",
        }
    ]

    result = asyncio.run(answer_service.generate_answer("¿Qué incluye el plan profesional?", chunks))

    assert result["can_answer"] is True
    assert result["coverage"] == "full"
    assert "acceso multiusuario" in result["answer"].lower()
    assert result["evidence_indexes"] == [0]


def test_generate_answer_still_rejects_irrelevant_chunk(monkeypatch):
    monkeypatch.setattr(answer_service, "_get_client", lambda: _FakeClient())

    chunks = [
        {
            "filename": "general.txt",
            "chunk_index": 0,
            "content": "[RESUMEN]\nLa plataforma centraliza conocimiento y mejora procesos internos.",
            "distance": 0.6,
            "document_id": "doc-3",
        }
    ]

    result = asyncio.run(answer_service.generate_answer("¿Hay reembolsos?", chunks))

    assert result == answer_service._FALLBACK_RESULT


def test_generate_answer_accepts_direct_phone_support_fact(monkeypatch):
    monkeypatch.setattr(answer_service, "_get_client", lambda: _FakeClient())

    chunks = [
        {
            "filename": "soporte.txt",
            "chunk_index": 1,
            "content": "[CONTACTO DE SOPORTE]\nLa atencion telefonica funciona de lunes a viernes de 9 a 18 horas.",
            "distance": 0.6,
            "document_id": "doc-4",
        }
    ]

    result = asyncio.run(answer_service.generate_answer("Hay atencion telefonica?", chunks))

    assert result["can_answer"] is True
    assert result["coverage"] == "full"
    assert "atencion telefonica" in result["answer"].lower()
    assert result["evidence_indexes"] == [0]


def test_generate_answer_rewrites_affirmative_attribute_as_yes_no(monkeypatch):
    monkeypatch.setattr(answer_service, "_get_client", lambda: _FakeClient())

    chunks = [
        {
            "filename": "politicas.txt",
            "chunk_index": 0,
            "content": "[CONFIDENCIALIDAD]\nToda la informacion de la empresa es confidencial.",
            "distance": 0.59,
            "document_id": "doc-5",
        }
    ]

    result = asyncio.run(answer_service.generate_answer("La informacion es confidencial?", chunks))

    assert result["can_answer"] is True
    assert result["coverage"] == "full"
    assert result["answer"].startswith("Si,")
    assert "confidencial" in result["answer"].lower()
    assert result["supported_points"] == ["Toda la informacion de la empresa es confidencial."]


def test_generate_answer_rewrites_frequency_answer(monkeypatch):
    monkeypatch.setattr(answer_service, "_get_client", lambda: _FakeClient())

    chunks = [
        {
            "filename": "rrhh.txt",
            "chunk_index": 1,
            "content": "[DESEMPENO]\nSe realizan evaluaciones semestrales.",
            "distance": 0.58,
            "document_id": "doc-6",
        }
    ]

    result = asyncio.run(answer_service.generate_answer("Cada cuanto se evalua el desempeno?", chunks))

    assert result["can_answer"] is True
    assert result["coverage"] == "full"
    assert result["answer"] == "Se evalua semestralmente."
    assert result["supported_points"] == ["Se realizan evaluaciones semestrales."]
