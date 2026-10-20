import os
import sys
from types import SimpleNamespace

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
RAG_DIR = os.path.join(HERE, "..", "...", "rag-server")
sys.path.insert(0, os.path.abspath(RAG_DIR))

import rag_pipeline as rag


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REFUND_TEXT = (
    "Pharmacy Refund Policy Prescription medications cannot be returned or "
    "refunded once dispensed unless dispensed in error by pharmacy staff"
)


def chunk(text=REFUND_TEXT, tier="tier_1"):
    return {
        "chunk_id": "abc",
        "source_id": "refund/refund.md",
        "authority_tier": tier,
        "text": text,
    }


# ---------------------------------------------------------------------------
# confidence_from_results (pure logic, no server needed)
# ---------------------------------------------------------------------------

def test_no_results_is_insufficient():
    assert rag.confidence_from_results([], "refund policy") == "Insufficient"


def test_query_of_only_stopwords_is_insufficient():
    assert rag.confidence_from_results([chunk()], "what is the") == "Insufficient"


def test_off_topic_query_is_insufficient():
    # shares only stopwords with the chunk, which are ignored
    assert rag.confidence_from_results([chunk()], "what is the capital of France") == "Insufficient"


def test_full_overlap_is_high():
    # tokens: refund, policy -> 2/2 = 1.0
    assert rag.confidence_from_results([chunk()], "refund policy") == "High"


def test_partial_overlap_is_medium():
    # tokens: refund, policy, cough, syrup -> 2/4 = 0.5
    assert rag.confidence_from_results([chunk()], "refund policy cough syrup") == "Medium"


def test_small_overlap_is_low():
    # tokens: refund, cough, syrup, returns, tablets -> 1/5 = 0.2
    assert rag.confidence_from_results([chunk()], "refund cough syrup returns tablets") == "Low"


def test_lower_authority_tier_reduces_confidence():
    # full overlap (1.0) x tier_3 weight (0.4) = 0.4 -> Low
    assert rag.confidence_from_results([chunk(tier="tier_3")], "refund policy") == "Low"


def test_only_top_result_is_scored():
    good, bad = chunk(), chunk(text="storage disposal contractor")
    assert rag.confidence_from_results([bad, good], "refund policy") == "Insufficient"



# ---------------------------------------------------------------------------
# Chunking and embeddings
# ---------------------------------------------------------------------------

def test_chunk_text_splits_by_word_count():
    text = " ".join(f"w{i}" for i in range(170))
    chunks = rag._chunk_text(text, chunk_size=80)
    assert len(chunks) == 3
    assert len(chunks[0].split()) == 80
    assert len(chunks[2].split()) == 10


def test_chunk_text_empty():
    assert rag._chunk_text("   ") == []


def test_embeddings_have_right_size_and_are_normalised():
    vec = rag.embed_texts(["refund policy"])[0]
    assert len(vec) == rag.EMBED_VECTOR_SIZE
    assert abs(sum(v * v for v in vec) ** 0.5 - 1.0) < 1e-6


def test_embeddings_are_deterministic():
    assert rag.embed_texts(["refund"]) == rag.embed_texts(["refund"])


def test_empty_text_embeds_to_zero_vector():
    assert set(rag.embed_texts([""])[0]) == {0.0}


# ---------------------------------------------------------------------------
# answer_question: insufficient path (no Ollama needed)
# ---------------------------------------------------------------------------

def test_answer_question_refuses_when_no_results(monkeypatch, tmp_path):
    monkeypatch.setattr(rag, "AUDIT_PATH", tmp_path / "audit.jsonl")
    monkeypatch.setattr(
        rag, "retrieve_context", lambda q, k=5: {"retrieval_mode": "vector", "results": []}
    )
    out = rag.answer_question("anything")
    assert out["status"] == "insufficient_context"
    assert out["citations"] == []
    assert (tmp_path / "audit.jsonl").exists()


def test_answer_question_ok_path_with_mocked_llm(monkeypatch, tmp_path):
    monkeypatch.setattr(rag, "AUDIT_PATH", tmp_path / "audit.jsonl")
    monkeypatch.setattr(
        rag, "retrieve_context",
        lambda q, k=5: {"retrieval_mode": "vector", "results": [{**chunk(), "score": 0.5}]},
    )
    monkeypatch.setattr(rag, "generate_with_ollama", lambda prompt: "Prescriptions cannot be refunded.")
    out = rag.answer_question("refund policy")
    assert out["status"] == "ok"
    assert out["confidence_category"] == "High"
    assert out["citations"][0]["source_id"] == "refund/refund.md"


# ---------------------------------------------------------------------------
# Live tests against the running RAG MCP server (via your rag_client)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def live_rag():
    import rag_client
    try:
        rag_client.call_answer_question("refund policy")
    except Exception as exc:
        pytest.skip(f"RAG server not reachable: {exc}")
    return rag_client