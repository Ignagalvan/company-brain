from src.services.knowledge_gap_service import _are_topics_similar, _normalize_topic, _topic_similarity


def test_gap_similarity_tolerates_small_typos():
    pairs = [
        ("empresa", "empesa"),
        ("vacaciones", "vacasiones"),
        ("bonus", "bonnus"),
        ("bono", "bonnus"),
        ("soporte", "soprote"),
    ]

    for left, right in pairs:
        score, _ = _topic_similarity(left, right)
        assert _normalize_topic(left)
        assert _normalize_topic(right)
        assert score > 0
        assert _are_topics_similar(left, right) is True


def test_gap_similarity_rejects_different_words():
    pairs = [
        ("empresa", "empresario"),
        ("vacaciones", "rotaciones"),
        ("bono", "abono"),
        ("soporte", "soporta"),
    ]

    for left, right in pairs:
        score, _ = _topic_similarity(left, right)
        assert score == 0.0
        assert _are_topics_similar(left, right) is False
