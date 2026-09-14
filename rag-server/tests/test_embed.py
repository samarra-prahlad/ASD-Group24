from rag_pipeline import embed_texts, EMBED_VECTOR_SIZE


def test_embed_texts_returns_correct_dimension():
    vectors = embed_texts(["hello world"])
    assert len(vectors) == 1
    assert len(vectors[0]) == EMBED_VECTOR_SIZE


def test_embed_texts_is_deterministic():
    v1 = embed_texts(["billing policy"])
    v2 = embed_texts(["billing policy"])
    assert v1 == v2


def test_embed_texts_different_inputs_differ():
    v1 = embed_texts(["billing policy"])
    v2 = embed_texts(["appointment schedule"])
    assert v1 != v2


def test_embed_empty_string_returns_zero_vector():
    vectors = embed_texts([""])
    assert vectors[0] == [0.0] * EMBED_VECTOR_SIZE