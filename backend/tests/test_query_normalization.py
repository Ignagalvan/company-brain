from src.services.query_normalization import clean_query_text, normalized_query_key


def test_normalized_query_key_collapses_corrupted_and_clean_queries():
    clean = "¿Cuántos días de vacaciones hay?"
    corrupted = "?Cu?ntos d?as de vacaciones hay?"

    assert normalized_query_key(clean) == "cuantos dias de vacaciones hay"
    assert normalized_query_key(corrupted) == "cuantos dias de vacaciones hay"
    assert clean_query_text(corrupted) == "¿cuantos dias de vacaciones hay?"
