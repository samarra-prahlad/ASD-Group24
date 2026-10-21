"""
Tests for the Billing multi-agent invoice review panel (Release 2).

The shared multi-agent server, billing-database and shared-backend are all
mocked, so these run without Ollama or any other service.

Run with:
    pytest tests/test_multi_agent_panel.py -v
"""

import os
import importlib.util
from unittest.mock import patch, MagicMock

import pytest
import requests

FEATURE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(FEATURE_ROOT, "backend")

spec = importlib.util.spec_from_file_location("billing_backend_app_ma", os.path.join(BACKEND_DIR, "app.py"))
billing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(billing)

ADMIN = ({"role": "admin", "first_name": "Samarra"}, None)
PATIENT = ({"role": "patient", "first_name": "Pat", "patient_id": 1}, None)

INVOICES = [
    {"id": 101, "patient_id": 1, "insurance_provider_name": "Medibank", "total_amount": 250.0,
     "insurance_covered_amount": 200.0, "patient_owed_amount": 50.0, "status": "pending",
     "notes": "should not be sent"},
    {"id": 102, "patient_id": 1, "insurance_provider_name": None, "total_amount": 480.0,
     "insurance_covered_amount": 0.0, "patient_owed_amount": 480.0, "status": "overdue"},
]

WORKFLOW = {
    "workflow_id": "wf-abc123def456",
    "status": "awaiting_human_review",
    "evidence_count": 2,
    "steps": {
        "planner": {"status": "completed", "model": "qwen2.5:0.5b", "output": "Objective: summarise invoices"},
        "worker": {"status": "completed", "model": "qwen2.5:0.5b", "output": "Invoice 102 is overdue"},
        "reviewer": {"status": "completed", "model": "llama3.1:8b", "output": "Risk: LOW",
                     "risk_level": "LOW", "recommendation": "APPROVE", "governance_notes": []},
    },
}


def fake_response(json_data, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    return response


@pytest.fixture
def client():
    billing.app.config["TESTING"] = True
    with billing.app.test_client() as test_client:
        yield test_client


def start(client, **form):
    data = {"user_request": "Summarise outstanding invoices"}
    data.update(form)
    return client.post("/multi-agent/workflow/html?token=t", data=data)


class TestInvoiceEvidence:

    def test_maps_only_needed_fields(self):
        evidence = billing.invoice_evidence(INVOICES)
        assert evidence[0]["invoice_id"] == 101
        assert evidence[0]["patient_owed_amount"] == 50.0
        assert "notes" not in evidence[0]
        assert evidence[1]["insurance_provider"] == "Self-pay"


class TestStartWorkflow:

    def test_requires_token(self, client):
        assert client.post("/multi-agent/workflow/html", data={"user_request": "x"}).status_code == 401

    @patch.object(billing, "verify_session", return_value=PATIENT)
    def test_patients_cannot_run_agents(self, _verify, client):
        assert start(client).status_code == 403

    @patch.object(billing, "MULTI_AGENT_ENABLED", False)
    @patch.object(billing, "verify_session", return_value=ADMIN)
    def test_disabled_flag_returns_503(self, _verify, client):
        resp = start(client)
        assert resp.status_code == 503
        assert b"disabled" in resp.data

    @patch.object(billing, "verify_session", return_value=ADMIN)
    def test_request_is_required(self, _verify, client):
        assert start(client, user_request="  ").status_code == 400

    @patch.object(billing, "verify_session", return_value=ADMIN)
    def test_patient_id_must_be_number(self, _verify, client):
        assert start(client, patient_id="abc").status_code == 400

    @patch.object(billing, "verify_session", return_value=ADMIN)
    @patch("requests.post")
    @patch("requests.get")
    def test_runs_workflow_with_patient_evidence(self, mock_get, mock_post, _verify, client):
        mock_get.return_value = fake_response(INVOICES)
        mock_post.return_value = fake_response(WORKFLOW, 201)

        resp = start(client, patient_id="1")

        assert resp.status_code == 200
        assert resp.headers["HX-Trigger"] == "multiAgentChanged"
        assert mock_get.call_args[0][0].endswith("/invoices/patient/1")
        sent = mock_post.call_args.kwargs["json"]
        assert sent["feature"] == "billing"
        assert sent["evidence"][1]["invoice_id"] == 102
        assert "Patient ID: 1" in sent["user_request"]
        body = resp.data.decode()
        assert "Invoice 102 is overdue" in body
        assert "confidence-high" in body
        for decision in ("approve", "partially_accept", "correct", "reject"):
            assert f"value='{decision}'" in body

    @patch.object(billing, "verify_session", return_value=ADMIN)
    @patch("requests.get")
    def test_database_down_returns_503(self, mock_get, _verify, client):
        mock_get.side_effect = requests.exceptions.ConnectionError()
        resp = start(client)
        assert resp.status_code == 503
        assert b"invoice evidence" in resp.data

    @patch.object(billing, "verify_session", return_value=ADMIN)
    @patch("requests.post")
    @patch("requests.get")
    def test_multi_agent_server_down_returns_503(self, mock_get, mock_post, _verify, client):
        mock_get.return_value = fake_response(INVOICES)
        mock_post.side_effect = requests.exceptions.ConnectionError()
        resp = start(client)
        assert resp.status_code == 503
        assert b"unavailable" in resp.data

    @patch.object(billing, "verify_session", return_value=ADMIN)
    @patch("requests.post")
    @patch("requests.get")
    def test_failed_workflow_shows_error_without_review_buttons(self, mock_get, mock_post, _verify, client):
        failed = {**WORKFLOW, "status": "failed", "steps": {
            "planner": {"status": "failed", "model": "qwen2.5:0.5b", "error": "LLM unreachable"}}}
        mock_get.return_value = fake_response(INVOICES)
        mock_post.return_value = fake_response(failed, 503)
        resp = start(client)
        assert resp.status_code == 503
        assert b"LLM unreachable" in resp.data
        assert b"name='decision'" not in resp.data

    @patch.object(billing, "verify_session", return_value=ADMIN)
    @patch("requests.post")
    @patch("requests.get")
    def test_agent_output_is_escaped(self, mock_get, mock_post, _verify, client):
        evil = {**WORKFLOW, "steps": {**WORKFLOW["steps"], "worker": {
            "status": "completed", "model": "m", "output": "<script>alert(1)</script>"}}}
        mock_get.return_value = fake_response(INVOICES)
        mock_post.return_value = fake_response(evil, 201)
        body = start(client).data.decode()
        assert "<script>alert(1)</script>" not in body
        assert "&lt;script&gt;" in body


class TestReviewWorkflow:

    URL = "/multi-agent/workflow/wf-abc123def456/review/html?token=t"

    @patch.object(billing, "verify_session", return_value=PATIENT)
    def test_patients_cannot_review(self, _verify, client):
        assert client.post(self.URL, data={"decision": "approve"}).status_code == 403

    @patch.object(billing, "verify_session", return_value=ADMIN)
    def test_invalid_workflow_id(self, _verify, client):
        resp = client.post("/multi-agent/workflow/not-an-id/review/html?token=t", data={"decision": "approve"})
        assert resp.status_code == 400

    @patch.object(billing, "verify_session", return_value=ADMIN)
    def test_invalid_decision(self, _verify, client):
        assert client.post(self.URL, data={"decision": "maybe"}).status_code == 400

    @patch.object(billing, "verify_session", return_value=ADMIN)
    def test_correct_requires_correction(self, _verify, client):
        assert client.post(self.URL, data={"decision": "correct", "correction": " "}).status_code == 400

    @patch.object(billing, "verify_session", return_value=ADMIN)
    @patch("requests.post")
    def test_approve_records_decision_and_removes_buttons(self, mock_post, _verify, client):
        mock_post.return_value = fake_response(
            {**WORKFLOW, "status": "approved", "final_output": "Invoice 102 is overdue"}, 200)

        resp = client.post(self.URL, data={"decision": "approve", "notes": "checked"})

        assert resp.status_code == 200
        assert resp.headers["HX-Trigger"] == "multiAgentChanged"
        sent = mock_post.call_args.kwargs["json"]
        assert sent == {"decision": "approve", "reviewer": "Samarra (admin)", "notes": "checked", "correction": None}
        body = resp.data.decode()
        assert "approved" in body
        assert "hx-swap-oob='true'" in body

    @patch.object(billing, "verify_session", return_value=ADMIN)
    @patch("requests.post")
    def test_correct_sends_correction(self, mock_post, _verify, client):
        mock_post.return_value = fake_response(
            {**WORKFLOW, "status": "corrected", "final_output": "Owed: 530.00"}, 200)
        resp = client.post(self.URL, data={"decision": "correct", "correction": "Owed: 530.00"})
        assert resp.status_code == 200
        assert mock_post.call_args.kwargs["json"]["correction"] == "Owed: 530.00"
        assert b"Owed: 530.00" in resp.data

    @patch.object(billing, "verify_session", return_value=ADMIN)
    @patch("requests.post")
    def test_already_reviewed_passes_through_409(self, mock_post, _verify, client):
        mock_post.return_value = fake_response({"error": "workflow is 'approved', not awaiting human review"}, 409)
        resp = client.post(self.URL, data={"decision": "reject"})
        assert resp.status_code == 409
        assert b"not awaiting human review" in resp.data


class TestHistory:

    @patch.object(billing, "verify_session", return_value=ADMIN)
    @patch("requests.get")
    def test_lists_recent_billing_workflows(self, mock_get, _verify, client):
        reviewed = {**WORKFLOW, "status": "approved", "user_request": "Summarise",
                    "human_review": {"reviewer": "Samarra (admin)"}}
        mock_get.return_value = fake_response({"workflows": [reviewed]})
        resp = client.get("/multi-agent/history/html?token=t")
        assert resp.status_code == 200
        assert mock_get.call_args.kwargs["params"] == {"feature": "billing", "limit": 5}
        body = resp.data.decode()
        assert "wf-abc123def456" in body and "approved" in body and "Samarra (admin)" in body

    @patch.object(billing, "verify_session", return_value=ADMIN)
    @patch("requests.get")
    def test_server_down_shows_message(self, mock_get, _verify, client):
        mock_get.side_effect = requests.exceptions.ConnectionError()
        resp = client.get("/multi-agent/history/html?token=t")
        assert resp.status_code == 200
        assert b"unavailable" in resp.data
