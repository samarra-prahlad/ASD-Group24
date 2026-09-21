import rag_pipeline
from rag_pipeline import answer_question, refresh_corpus


def _setup_knowledge(tmp_path, monkeypatch):
    knowledge_dir = tmp_path / "knowledge"
    billing_dir = knowledge_dir / "billing"
    billing_dir.mkdir(parents=True)
    (billing_dir / "late_fee.md").write_text(
        "Late payments incur a five percent fee after thirty days overdue."
    )
    monkeypatch.setattr("rag_pipeline.KNOWLEDGE_DIR", knowledge_dir)
    monkeypatch.setattr("rag_pipeline.CORPUS_PATH", tmp_path / "corpus" / "corpus.jsonl")
    monkeypatch.setattr("rag_pipeline.CHROMA_DIR", tmp_path / "chroma")


def _empty_knowledge(tmp_path, monkeypatch):
    empty_dir = tmp_path / "knowledge"
    empty_dir.mkdir()
    monkeypatch.setattr("rag_pipeline.KNOWLEDGE_DIR", empty_dir)
    monkeypatch.setattr("rag_pipeline.CORPUS_PATH", tmp_path / "corpus" / "corpus.jsonl")
    monkeypatch.setattr("rag_pipeline.CHROMA_DIR", tmp_path / "chroma")


def test_answer_question_returns_grounded_answer(tmp_path, monkeypatch):
    _setup_knowledge(tmp_path, monkeypatch)
    refresh_corpus()
    monkeypatch.setattr(
        rag_pipeline, "generate_with_ollama",
        lambda prompt: "Late fees are five percent after 30 days.",
    )

    result = answer_question("what is the late fee")
    assert result["status"] == "ok"
    assert result["query"] == "what is the late fee"
    assert "five percent" in result["answer"]
    assert len(result["citations"]) >= 1
    assert result["confidence_category"] in ("High", "Medium", "Low")
    assert "retrieval_summary" in result


def test_answer_question_returns_insufficient_when_no_context(tmp_path, monkeypatch):
    _empty_knowledge(tmp_path, monkeypatch)

    result = answer_question("anything")
    assert result["status"] == "insufficient_context"
    assert result["citations"] == []
    assert result["confidence_category"] == "Insufficient"


def test_answer_question_does_not_call_ollama_when_insufficient(tmp_path, monkeypatch):
    _empty_knowledge(tmp_path, monkeypatch)

    called = {"count": 0}
    def fake_generate(prompt):
        called["count"] += 1
        return "should not be called"
    monkeypatch.setattr(rag_pipeline, "generate_with_ollama", fake_generate)

    answer_question("anything")
    assert called["count"] == 0


def test_answer_question_includes_citation_source_ids(tmp_path, monkeypatch):
    _setup_knowledge(tmp_path, monkeypatch)
    refresh_corpus()
    monkeypatch.setattr(rag_pipeline, "generate_with_ollama", lambda prompt: "answer text")

    result = answer_question("late fee")
    source_ids = [c["source_id"] for c in result["citations"]]
    assert "billing/late_fee.md" in source_ids