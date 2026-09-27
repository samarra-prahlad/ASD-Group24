import json
from rag_pipeline import append_audit, AUDIT_PATH


def test_append_audit_writes_jsonl_line(tmp_path, monkeypatch):
    audit_path = tmp_path / "rag-audit.jsonl"
    monkeypatch.setattr("rag_pipeline.AUDIT_PATH", audit_path)

    append_audit(
        query="what is the late fee",
        status="ok",
        retrieval_mode="vector",
        confidence_category="High",
        duration_ms=42.5,
    )

    lines = audit_path.read_text().strip().split("\n")
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["query"] == "what is the late fee"
    assert record["status"] == "ok"
    assert record["retrieval_mode"] == "vector"
    assert record["confidence_category"] == "High"
    assert record["duration_ms"] == 42.5
    assert "timestamp" in record


def test_append_audit_appends_multiple_calls(tmp_path, monkeypatch):
    audit_path = tmp_path / "rag-audit.jsonl"
    monkeypatch.setattr("rag_pipeline.AUDIT_PATH", audit_path)

    append_audit(query="q1", status="ok", retrieval_mode="vector", confidence_category="High", duration_ms=10)
    append_audit(query="q2", status="insufficient_context", retrieval_mode="lexical", confidence_category="Insufficient", duration_ms=5)

    lines = audit_path.read_text().strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["query"] == "q1"
    assert json.loads(lines[1])["query"] == "q2"


def test_append_audit_creates_parent_dir(tmp_path, monkeypatch):
    audit_path = tmp_path / "nested" / "rag-audit.jsonl"
    monkeypatch.setattr("rag_pipeline.AUDIT_PATH", audit_path)

    append_audit(query="q", status="ok", retrieval_mode="vector", confidence_category="Medium", duration_ms=1)
    assert audit_path.exists()