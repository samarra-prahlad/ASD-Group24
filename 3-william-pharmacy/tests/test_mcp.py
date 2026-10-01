import os
import sys
from types import SimpleNamespace

import pytest
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(HERE, "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND_DIR))

import app as flask_app  # <-- change to your Flask file's name
import mcp_client
import rag_client


# ---------------------------------------------------------------------------
# _extract_result (same logic in mcp_client and rag_client)
# ---------------------------------------------------------------------------

def fake_result(text=None, is_error=False):
    content = [SimpleNamespace(text=text)] if text is not None else []
    return SimpleNamespace(isError=is_error, content=content)


@pytest.mark.parametrize("module", [mcp_client, rag_client])
def test_extract_result_parses_json(module):
    out = module._extract_result(fake_result('{"in_stock": true, "quantity": 12}'))
    assert out == {"in_stock": True, "quantity": 12}


@pytest.mark.parametrize("module", [mcp_client, rag_client])
def test_extract_result_returns_plain_text(module):
    assert module._extract_result(fake_result("not json")) == "not json"


@pytest.mark.parametrize("module", [mcp_client, rag_client])
def test_extract_result_raises_on_error(module):
    with pytest.raises(RuntimeError):
        module._extract_result(fake_result("boom", is_error=True))


@pytest.mark.parametrize("module", [mcp_client, rag_client])
def test_extract_result_empty_content_returns_none(module):
    assert module._extract_result(fake_result(None)) is None


# ---------------------------------------------------------------------------
# find_medication_in_question (database call mocked)
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_meds(monkeypatch):
    class Resp:
        def raise_for_status(self): pass
        def json(self): return [{"name": "Amoxicillin 500mg"}, {"name": "Paracetamol 500mg"}]
    monkeypatch.setattr(flask_app.requests, "get", lambda *a, **k: Resp())


def test_find_medication_exact_match(fake_meds):
    assert flask_app.find_medication_in_question("is amoxicillin in stock?") == "Amoxicillin 500mg"


def test_find_medication_fuzzy_typo(fake_meds):
    assert flask_app.find_medication_in_question("do you have amoxicilin") == "Amoxicillin 500mg"


def test_find_medication_not_found(fake_meds):
    assert flask_app.find_medication_in_question("what time do you open") is None


def test_find_medication_database_down(monkeypatch):
    def boom(*a, **k): raise requests.RequestException("down")
    monkeypatch.setattr(flask_app.requests, "get", boom)
    assert flask_app.find_medication_in_question("amoxicillin") is None


# ---------------------------------------------------------------------------
# /ask-mcp route
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    flask_app.app.config["TESTING"] = True
    return flask_app.app.test_client()


def test_ask_mcp_requires_question(client):
    res = client.post("/ask-mcp", data={"question": "  "})
    assert res.status_code == 400


def test_ask_mcp_no_medication_found(client, monkeypatch):
    monkeypatch.setattr(flask_app, "find_medication_in_question", lambda q: None)
    res = client.post("/ask-mcp", data={"question": "hello"})
    assert res.status_code == 400
    assert b"drug name" in res.data


def test_ask_mcp_server_unreachable(client, monkeypatch):
    monkeypatch.setattr(flask_app, "find_medication_in_question", lambda q: "Amoxicillin 500mg")
    def boom(name): raise ConnectionError("refused")
    monkeypatch.setattr(flask_app, "call_check_stock", boom)
    res = client.post("/ask-mcp", data={"question": "amoxicillin in stock?"})
    assert res.status_code == 503


def test_ask_mcp_tool_reports_error(client, monkeypatch):
    monkeypatch.setattr(flask_app, "find_medication_in_question", lambda q: "Amoxicillin 500mg")
    monkeypatch.setattr(flask_app, "call_check_stock", lambda name: {"error": "not found"})
    res = client.post("/ask-mcp", data={"question": "amoxicillin in stock?"})
    assert res.status_code == 404
    assert b"not found" in res.data


def test_ask_mcp_happy_path(client, monkeypatch):
    monkeypatch.setattr(flask_app, "find_medication_in_question", lambda q: "Amoxicillin 500mg")
    monkeypatch.setattr(flask_app, "call_check_stock", lambda name: {"name": name, "quantity": 12})
    monkeypatch.setattr(flask_app, "load_prompt", lambda f: "system prompt")

    seen = {}
    def fake_create(**kwargs):
        seen.update(kwargs)
        msg = SimpleNamespace(content="Amoxicillin 500mg is in stock (12 units).")
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])
    monkeypatch.setattr(flask_app.client.chat.completions, "create", fake_create)

    res = client.post("/ask-mcp", data={"question": "is amoxicillin in stock?"})
    assert res.status_code == 200
    assert b"in stock" in res.data
    # the verified stock data must be passed to the LLM
    assert "quantity" in seen["messages"][1]["content"]


# ---------------------------------------------------------------------------
# /ask-rag route (RAG client mocked)
# ---------------------------------------------------------------------------

def test_ask_rag_requires_question(client):
    assert client.post("/ask-rag", data={}).status_code == 400


def test_ask_rag_insufficient_context(client, monkeypatch):
    monkeypatch.setattr(flask_app, "call_answer_question", lambda q: {
        "status": "insufficient_context",
        "answer": "Not enough information.",
        "confidence_category": "Insufficient",
        "citations": [],
    })
    res = client.post("/ask-rag", data={"question": "capital of France"})
    assert res.status_code == 200
    assert b"Insufficient" in res.data


def test_ask_rag_ok_shows_citations(client, monkeypatch):
    monkeypatch.setattr(flask_app, "call_answer_question", lambda q: {
        "status": "ok",
        "answer": "No refunds on dispensed prescriptions.",
        "confidence_category": "High",
        "citations": [{"source_id": "refund/refund.md", "chunk_id": "abc"}],
    })
    res = client.post("/ask-rag", data={"question": "refund policy"})
    assert b"refund/refund.md" in res.data
    assert b"High" in res.data


def test_ask_rag_server_down(client, monkeypatch):
    def boom(q): raise ConnectionError("refused")
    monkeypatch.setattr(flask_app, "call_answer_question", boom)
    assert client.post("/ask-rag", data={"question": "x"}).status_code == 503


# ---------------------------------------------------------------------------
# Live test against the real MCP server
# ---------------------------------------------------------------------------

@pytest.mark.live
def test_live_check_stock_returns_a_result():
    try:
        out = mcp_client.call_check_stock("Amoxicillin")
    except Exception as exc:
        pytest.skip(f"MCP server not reachable: {exc}")
    assert isinstance(out, (dict, str))