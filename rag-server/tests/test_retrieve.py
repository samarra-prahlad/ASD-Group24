from rag_pipeline import refresh_corpus, retrieve_context, write_corpus


def _setup_knowledge(tmp_path, monkeypatch):
    knowledge_dir = tmp_path / "knowledge"
    billing_dir = knowledge_dir / "billing"
    billing_dir.mkdir(parents=True)
    (billing_dir / "late_fee.md").write_text(
        "Late payments incur a five percent fee after thirty days overdue."
    )
    (billing_dir / "refunds.md").write_text(
        "Refunds are processed within ten business days of an approved request."
    )
    monkeypatch.setattr("rag_pipeline.KNOWLEDGE_DIR", knowledge_dir)
    monkeypatch.setattr("rag_pipeline.CORPUS_PATH", tmp_path / "corpus" / "corpus.jsonl")
    monkeypatch.setattr("rag_pipeline.CHROMA_DIR", tmp_path / "chroma")


def test_retrieve_context_returns_vector_results_after_refresh(tmp_path, monkeypatch):
    _setup_knowledge(tmp_path, monkeypatch)
    refresh_corpus()

    result = retrieve_context("what is the late payment fee", top_k=5)
    assert result["retrieval_mode"] == "vector"
    assert len(result["results"]) >= 1
    top_texts = " ".join(r["text"].lower() for r in result["results"])
    assert "fee" in top_texts


def test_retrieve_context_respects_top_k(tmp_path, monkeypatch):
    _setup_knowledge(tmp_path, monkeypatch)
    refresh_corpus()

    result = retrieve_context("payment", top_k=1)
    assert len(result["results"]) <= 1


def test_retrieve_context_falls_back_to_lexical_when_no_index(tmp_path, monkeypatch):
    _setup_knowledge(tmp_path, monkeypatch)
    from rag_pipeline import build_corpus
    write_corpus(build_corpus())

    result = retrieve_context("refunds", top_k=5)
    assert result["retrieval_mode"] == "lexical"
    assert len(result["results"]) >= 1
    assert "refund" in result["results"][0]["text"].lower()


def test_retrieve_context_with_no_data_returns_empty(tmp_path, monkeypatch):
    empty_dir = tmp_path / "knowledge"
    empty_dir.mkdir()
    monkeypatch.setattr("rag_pipeline.KNOWLEDGE_DIR", empty_dir)
    monkeypatch.setattr("rag_pipeline.CORPUS_PATH", tmp_path / "corpus" / "corpus.jsonl")
    monkeypatch.setattr("rag_pipeline.CHROMA_DIR", tmp_path / "chroma")

    result = retrieve_context("anything", top_k=5)
    assert result["results"] == []