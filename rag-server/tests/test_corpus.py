import json
from rag_pipeline import build_corpus, write_corpus, CORPUS_PATH


def test_build_corpus_reads_knowledge_files(tmp_path, monkeypatch):
    feature_dir = tmp_path / "knowledge" / "billing"
    feature_dir.mkdir(parents=True)
    (feature_dir / "late_payment.md").write_text(
        "Late payments incur a five percent fee after thirty days overdue. "
        "Patients can set up a payment plan to avoid this fee."
    )
    monkeypatch.setattr("rag_pipeline.KNOWLEDGE_DIR", tmp_path / "knowledge")
    chunks = build_corpus()
    assert len(chunks) >= 1
    assert chunks[0]["source_id"] == "billing/late_payment.md"
    assert chunks[0]["authority_tier"] == "tier_1"
    assert "chunk_id" in chunks[0]
    assert "indexed_at" in chunks[0]
    assert "fee" in chunks[0]["text"].lower()


def test_build_corpus_chunks_long_text_into_blocks(tmp_path, monkeypatch):
    feature_dir = tmp_path / "knowledge" / "billing"
    feature_dir.mkdir(parents=True)
    long_text = " ".join(["word"] * 200)
    (feature_dir / "long.md").write_text(long_text)
    monkeypatch.setattr("rag_pipeline.KNOWLEDGE_DIR", tmp_path / "knowledge")
    chunks = build_corpus()
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk["text"].split()) <= 80


def test_build_corpus_with_no_files_returns_empty(tmp_path, monkeypatch):
    empty_dir = tmp_path / "knowledge"
    empty_dir.mkdir()
    monkeypatch.setattr("rag_pipeline.KNOWLEDGE_DIR", empty_dir)
    assert build_corpus() == []


def test_write_corpus_writes_jsonl(tmp_path, monkeypatch):
    corpus_path = tmp_path / "corpus.jsonl"
    monkeypatch.setattr("rag_pipeline.CORPUS_PATH", corpus_path)
    chunks = [{
        "chunk_id": "abc123",
        "source_id": "billing/x.md",
        "authority_tier": "tier_1",
        "text": "hello",
        "indexed_at": "2026-01-01T00:00:00",
    }]
    write_corpus(chunks)
    lines = corpus_path.read_text().strip().split("\n")
    assert len(lines) == 1
    assert json.loads(lines[0])["source_id"] == "billing/x.md"