from src.services.knowledge_gap_service import _build_visible_gap_label, _canonical_topic_label


def test_company_name_gap_uses_internal_topic_and_human_label():
    queries = ["¿Cómo se llama la empresa?", "como se llama la empesa"]
    topic = _canonical_topic_label(queries)
    label = _build_visible_gap_label(queries, topic)

    assert topic == "nombre empresa"
    assert label == "¿Cómo se llama la empresa?"


def test_bonus_gap_merges_to_bono_with_clear_label():
    queries = ["hay bono anual", "dan bonus"]
    topic = _canonical_topic_label(queries)
    label = _build_visible_gap_label(queries, topic)

    assert topic == "bono"
    assert label == "¿La empresa ofrece bono anual?"


def test_vacations_gap_uses_clear_question_label():
    queries = ["vacaciones cuntos dias"]
    topic = _canonical_topic_label(queries)
    label = _build_visible_gap_label(queries, topic)

    assert topic == "vacaciones"
    assert label == "¿Cuántos días de vacaciones tienen los empleados?"
