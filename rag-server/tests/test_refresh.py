import chromadb
from rag_pipeline import refresh_corpus, get_chroma_client


def _setup_knowledge(tmp_path, monkeypatch, text="Late fees apply after thirty days overdue."):
    feature_dir = tmp_path / "knowledge" / "billing"
    feature_dir.mkdir(parents=True)
    (feature_dir / "policy.md").write_text(text)
    monkeypatch.setattr("rag_pipeline.KNOWLEDGE_DIR", tmp_path / "knowledge")
    monkeypatch.setattr("rag_pipeline.CORPUS_PATH", tmp_path / "corpus" / "corpus.jsonl")
    monkeypatch.setattr("rag_pipeline.CHROMA_DIR", tmp_path / "chroma")


def test_refresh_corpus_indexes_chunks(tmp_path, monkeypatch):
    _setup_knowledge(tmp_path, monkeypatch)
    summary = refresh_corpus()
    assert summary["chunks_indexed"] >= 1
    assert summary["status"] == "ok"

    client = get_chroma_client()
    collection = client.get_collection("rag_corpus")
    assert collection.count() == summary["chunks_indexed"]


def test_refresh_corpus_with_no_knowledge_returns_zero(tmp_path, monkeypatch):
    empty_dir = tmp_path / "knowledge"
    empty_dir.mkdir()
    monkeypatch.setattr("rag_pipeline.KNOWLEDGE_DIR", empty_dir)
    monkeypatch.setattr("rag_pipeline.CORPUS_PATH", tmp_path / "corpus" / "corpus.jsonl")
    monkeypatch.setattr("rag_pipeline.CHROMA_DIR", tmp_path / "chroma")

    summary = refresh_corpus()
    assert summary["chunks_indexed"] == 0


def test_refresh_corpus_does_not_duplicate_on_second_call(tmp_path, monkeypatch):
    _setup_knowledge(tmp_path, monkeypatch)
    first = refresh_corpus()
    second = refresh_corpus()
    assert first["chunks_indexed"] == second["chunks_indexed"]

    client = get_chroma_client()
    collection = client.get_collection("rag_corpus")
    assert collection.count() == second["chunks_indexed"]


def test_refresh_corpus_stores_metadata(tmp_path, monkeypatch):
    _setup_knowledge(tmp_path, monkeypatch)
    refresh_corpus()

    client = get_chroma_client()
    collection = client.get_collection("rag_corpus")
    result = collection.get(limit=1)
    metadata = result["metadatas"][0]
    assert metadata["source_id"] == "billing/policy.md"
    assert metadata["authority_tier"] == "tier_1"