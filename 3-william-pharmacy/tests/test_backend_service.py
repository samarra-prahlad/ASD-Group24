"""
Tests for backend_service.py

Strategy: this service is a thin proxy in front of the database service, plus
two endpoints that call an OpenAI-compatible client. Neither the database
service nor Ollama need to be running for these tests — we monkeypatch
`requests.request` and `client.chat.completions.create` so every test is
fully isolated and fast.
"""
import types
import pytest
import requests as requests_module

import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "backend_service", Path(__file__).parent.parent / "backend" / "app.py"
)
backend_service = importlib.util.module_from_spec(_spec)
sys.modules["backend_service"] = backend_service
_spec.loader.exec_module(backend_service)


@pytest.fixture
def client():
    backend_service.app.config["TESTING"] = True
    return backend_service.app.test_client()


class FakeResponse:
    """Minimal stand-in for requests.Response."""
    def __init__(self, json_body, status_code):
        self._json_body = json_body
        self.status_code = status_code

    def json(self):
        return self._json_body


@pytest.fixture
def fake_upstream(monkeypatch):
    """
    Patch backend_service.requests.request. Returns a call recorder + a way
    to set the next response, so tests can assert both what was sent to the
    database service and what came back through the proxy.
    """
    calls = []

    state = {"response": FakeResponse({}, 200), "raise": None}

    def fake_request(method, url, timeout=None, **kwargs):
        calls.append({"method": method, "url": url, "timeout": timeout, **kwargs})
        if state["raise"] is not None:
            raise state["raise"]
        return state["response"]

    monkeypatch.setattr(backend_service.requests, "request", fake_request)

    def set_response(json_body, status_code):
        state["response"] = FakeResponse(json_body, status_code)

    def set_exception(exc):
        state["raise"] = exc

    return types.SimpleNamespace(calls=calls, set_response=set_response, set_exception=set_exception)


# ---------------------------------------------------------------------------
# proxy() forwarding behaviour, exercised via the read endpoints
# ---------------------------------------------------------------------------

def test_get_medications_forwards_to_database_service(client, fake_upstream):
    fake_upstream.set_response([{"id": 1, "name": "Amoxicillin"}], 200)

    resp = client.get("/medications")

    assert resp.status_code == 200
    assert resp.get_json() == [{"id": 1, "name": "Amoxicillin"}]
    assert fake_upstream.calls[0]["method"] == "GET"
    assert fake_upstream.calls[0]["url"] == f"{backend_service.DATABASE_URL}/medications"


def test_get_prescriptions_forwards_patient_id_in_path(client, fake_upstream):
    fake_upstream.set_response([], 200)

    client.get("/prescriptions/101")

    assert fake_upstream.calls[0]["url"] == f"{backend_service.DATABASE_URL}/prescriptions/101"


def test_proxy_forwards_non_200_status_code_from_upstream(client, fake_upstream):
    """A 404 from the database service must reach the caller as a 404, not a 200."""
    fake_upstream.set_response({"error": "Medication not found"}, 404)

    resp = client.delete("/admin/medications/9999")

    assert resp.status_code == 404
    assert resp.get_json() == {"error": "Medication not found"}


def test_proxy_returns_502_when_database_service_unreachable(client, fake_upstream):
    fake_upstream.set_exception(requests_module.ConnectionError("connection refused"))

    resp = client.get("/medications")

    assert resp.status_code == 502
    assert "error" in resp.get_json()


def test_proxy_returns_502_on_timeout(client, fake_upstream):
    fake_upstream.set_exception(requests_module.Timeout("timed out"))

    resp = client.get("/medications")

    assert resp.status_code == 502


def test_proxy_handles_non_json_upstream_body(client, fake_upstream):
    class BadJsonResponse:
        status_code = 500

        def json(self):
            raise ValueError("not JSON")

    def fake_request(method, url, timeout=None, **kwargs):
        return BadJsonResponse()

    backend_service.requests.request = fake_request

    resp = client.get("/medications")
    assert resp.status_code == 500
    assert "error" in resp.get_json()


# ---------------------------------------------------------------------------
# admin: medications — method, path, and body forwarding
# ---------------------------------------------------------------------------

def test_add_medication_forwards_post_with_trailing_slash_and_body(client, fake_upstream):
    fake_upstream.set_response({"id": 11, "name": "New Drug", "stock": 5, "unit_price": 2.5}, 201)

    resp = client.post(
        "/admin/medications",
        json={"name": "New Drug", "stock": 5, "unit_price": 2.5},
    )

    assert resp.status_code == 201
    call = fake_upstream.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == f"{backend_service.DATABASE_URL}/admin/medications/"
    assert call["json"] == {"name": "New Drug", "stock": 5, "unit_price": 2.5}


def test_add_medication_with_missing_body_forwards_empty_dict(client, fake_upstream):
    fake_upstream.set_response({"error": "name and unit_price are required"}, 400)

    resp = client.post("/admin/medications", content_type="application/json", data="")

    assert resp.status_code == 400
    assert fake_upstream.calls[0]["json"] == {}


def test_update_medication_forwards_put_with_id_in_path(client, fake_upstream):
    fake_upstream.set_response({"updated": 1}, 200)

    resp = client.put("/admin/medications/7", json={"stock": 50})

    assert resp.status_code == 200
    call = fake_upstream.calls[0]
    assert call["method"] == "PUT"
    assert call["url"] == f"{backend_service.DATABASE_URL}/admin/medications/7"
    assert call["json"] == {"stock": 50}


def test_delete_medication_forwards_delete(client, fake_upstream):
    fake_upstream.set_response({"deleted": 1}, 200)

    resp = client.delete("/admin/medications/7")

    assert resp.status_code == 200
    assert fake_upstream.calls[0]["method"] == "DELETE"
    assert fake_upstream.calls[0]["url"] == f"{backend_service.DATABASE_URL}/admin/medications/7"


# ---------------------------------------------------------------------------
# admin: prescriptions — method, path, and body forwarding
# ---------------------------------------------------------------------------

def test_create_prescription_forwards_post(client, fake_upstream):
    payload = {
        "patient_id": 101,
        "medication_id": 1,
        "dosage": "500mg twice daily",
        "prescribing_doctor": "Dr. Sarah Chen",
    }
    fake_upstream.set_response({"id": 5, **payload}, 201)

    resp = client.post("/admin/prescriptions", json=payload)

    assert resp.status_code == 201
    call = fake_upstream.calls[0]
    assert call["url"] == f"{backend_service.DATABASE_URL}/admin/prescriptions"
    assert call["json"] == payload


def test_update_prescription_forwards_put(client, fake_upstream):
    fake_upstream.set_response({"updated": 1}, 200)

    resp = client.put("/admin/prescriptions/5", json={"status": "completed"})

    assert resp.status_code == 200
    call = fake_upstream.calls[0]
    assert call["url"] == f"{backend_service.DATABASE_URL}/admin/prescriptions/5"
    assert call["json"] == {"status": "completed"}


def test_delete_prescription_forwards_delete(client, fake_upstream):
    fake_upstream.set_response({"deleted": 1}, 200)

    resp = client.delete("/admin/prescriptions/5")

    assert resp.status_code == 200
    assert fake_upstream.calls[0]["method"] == "DELETE"
    assert fake_upstream.calls[0]["url"] == f"{backend_service.DATABASE_URL}/admin/prescriptions/5"


# ---------------------------------------------------------------------------
# /ask
# ---------------------------------------------------------------------------

def _fake_completion(answer_text):
    """Builds an object shaped like an OpenAI ChatCompletion response."""
    message = types.SimpleNamespace(content=answer_text)
    choice = types.SimpleNamespace(message=message)
    return types.SimpleNamespace(choices=[choice])


def test_ask_requires_question(client):
    resp = client.post("/ask", data={})
    assert resp.status_code == 400


def test_ask_returns_model_answer(client, monkeypatch):
    monkeypatch.setattr(
        backend_service.client.chat.completions,
        "create",
        lambda **kwargs: _fake_completion("Take two tablets daily."),
    )

    resp = client.post("/ask", data={"question": "How is ibuprofen dosed?"})

    assert resp.status_code == 200
    assert "Take two tablets daily." in resp.get_data(as_text=True)


def test_ask_returns_503_when_model_call_fails(client, monkeypatch):
    def raise_error(**kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(backend_service.client.chat.completions, "create", raise_error)

    resp = client.post("/ask", data={"question": "How is ibuprofen dosed?"})

    assert resp.status_code == 503
    assert "Local AI agent request failed" in resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# /ask-with-context
# ---------------------------------------------------------------------------

def test_ask_with_context_requires_question(client):
    resp = client.post("/ask-with-context", data={})
    assert resp.status_code == 400

def test_ask_with_context_returns_model_answer(client, monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured["messages"] = kwargs["messages"]
        return _fake_completion("Context-aware answer.")

    monkeypatch.setattr(backend_service.client.chat.completions, "create", fake_create)

    resp = client.post("/ask-with-context", data={"question": "What is the stock of X?"})

    assert resp.status_code == 200
    assert "Context-aware answer." in resp.get_data(as_text=True)

    # confirm a real system prompt was loaded and passed through (not empty/missing)
    assert len(captured["messages"][0]["content"]) > 0
    assert captured["messages"][0]["role"] == "system"
    assert "What is the stock of X?" in captured["messages"][1]["content"]

def test_ask_with_context_returns_503_when_model_call_fails(client, monkeypatch):
    def raise_error(**kwargs):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(backend_service.client.chat.completions, "create", raise_error)

    resp = client.post("/ask-with-context", data={"question": "anything"})

    assert resp.status_code == 503
