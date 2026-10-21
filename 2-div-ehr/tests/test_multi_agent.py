import os
import sys
import importlib.util
from unittest.mock import patch, MagicMock

import pytest
import requests

FEATURE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(FEATURE_ROOT, "backend")
sys.path.insert(0, BACKEND_DIR)

spec = importlib.util.spec_from_file_location("ehr_backend_app_ma", os.path.join(BACKEND_DIR, "app.py"))
ehr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ehr)

# check_session returns (patient_id, role, error_response)
ADMIN = (None, "admin", None)
PATIENT = (3, "patient", None)

RECORDS = [
    {"id": 11, "patient_id": 1, "visit_date": "2026-03-01", "diagnosis": "Asthma",
     "doctor_name": "Dr Lee", "treatment": "Inhaler", "allergies": "Penicillin",
     "notes": "should not be sent"},
    {"id": 12, "patient_id": 1, "visit_date": "2026-05-10", "diagnosis": "Flu",
     "doctor_name": "Dr Kim", "treatment": "Rest", "allergies": None,
     "notes": "private note"},
]

WORKFLOW_ID = "wf-abc123def456"

WORKFLOW = {
    "workflow_id": WORKFLOW_ID,
    "status": "awaiting_human_review",
    "evidence_count": 2,
    "steps": {
        "planner": {"status": "completed", "model": "qwen2.5:0.5b", "output": "Objective: summarise records"},
        "worker": {"status": "completed", "model": "qwen2.5:0.5b", "output": "Patient has asthma"},
        "reviewer": {"status": "completed", "model": "llama3.1:8b", "output": "Risk: LOW",
                     "risk_level": "LOW", "recommendation": "APPROVE", "governance_notes": []},
    },
}


def fake_response(json_data, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    response.raise_for_status.side_effect = (
        None if status_code < 400
        else requests.exceptions.HTTPError(response=response)
    )
    return response


@pytest.fixture
def client():
    ehr.app.config["TESTING"] = True
    with ehr.app.test_client() as test_client:
        yield test_client


def start(client, **body):
    payload = {"token": "t", "patient_id": 1, "user_request": "Summarise this patient's history"}
    payload.update(body)
    return client.post("/multi-agent/workflow", json=payload)


class TestRecordEvidence:

    def test_maps_only_needed_fields(self):
        evidence = ehr.medical_record_evidence(RECORDS)
        assert evidence[0]["record_id"] == 11
        assert evidence[0]["diagnosis"] == "Asthma"
        assert evidence[0]["allergies"] == "Penicillin"
        assert "notes" not in evidence[0]
        assert "patient_id" not in evidence[0]
        assert evidence[1]["allergies"] == "None recorded"


class TestStartWorkflow:

    def test_requires_token(self, client):
        resp = client.post("/multi-agent/workflow", json={"user_request": "x", "patient_id": 1})
        assert resp.status_code == 400  # check_session: "token is required"

    @patch.object(ehr, "check_session", return_value=(None, None, ({"error": "Invalid or expired session"}, 401)))
    def test_invalid_token_returns_401(self, _session, client):
        assert start(client).status_code == 401

    @patch.object(ehr, "check_session", return_value=PATIENT)
    def test_patients_cannot_run_agents(self, _session, client):
        assert start(client).status_code == 403

    @patch.object(ehr, "MULTI_AGENT_ENABLED", False)
    @patch.object(ehr, "check_session", return_value=ADMIN)
    def test_disabled_flag_returns_503(self, _session, client):
        resp = start(client)
        assert resp.status_code == 503
        assert resp.get_json()["status"] == "disabled"

    @patch.object(ehr, "check_session", return_value=ADMIN)
    def test_request_is_required(self, _session, client):
        assert start(client, user_request="  ").status_code == 400

    @patch.object(ehr, "check_session", return_value=ADMIN)
    def test_patient_id_is_required(self, _session, client):
        assert start(client, patient_id=None).status_code == 400

    @patch.object(ehr, "check_session", return_value=ADMIN)
    def test_patient_id_must_be_number(self, _session, client):
        assert start(client, patient_id="abc").status_code == 400

    @patch.object(ehr, "check_session", return_value=ADMIN)
    @patch("requests.post")
    @patch("requests.get")
    def test_runs_workflow_with_record_evidence(self, mock_get, mock_post, _session, client):
        mock_get.return_value = fake_response(RECORDS)
        mock_post.return_value = fake_response(WORKFLOW, 201)

        resp = start(client, patient_id=1)

        assert resp.status_code == 200
        assert mock_get.call_args[0][0].endswith("/records/1")
        sent = mock_post.call_args.kwargs["json"]
        assert sent["feature"] == "ehr"
        assert sent["evidence"][1]["record_id"] == 12
        assert "notes" not in sent["evidence"][0]
        assert "Patient ID: 1" in sent["user_request"]
        assert "token" not in sent
        data = resp.get_json()
        assert data["workflow_id"] == WORKFLOW_ID
        assert data["steps"]["worker"]["output"] == "Patient has asthma"
        assert data["steps"]["reviewer"]["risk_level"] == "LOW"

    @patch.object(ehr, "check_session", return_value=ADMIN)
    @patch("requests.get")
    def test_database_down_returns_503(self, mock_get, _session, client):
        mock_get.side_effect = requests.exceptions.ConnectionError()
        resp = start(client)
        assert resp.status_code == 503
        assert "EHR Database unavailable" in resp.get_json()["error"]

    @patch.object(ehr, "check_session", return_value=ADMIN)
    @patch("requests.post")
    @patch("requests.get")
    def test_multi_agent_server_down_returns_503(self, mock_get, mock_post, _session, client):
        mock_get.return_value = fake_response(RECORDS)
        mock_post.side_effect = requests.exceptions.ConnectionError()
        resp = start(client)
        assert resp.status_code == 503
        assert "unavailable" in resp.get_json()["error"]

    @patch.object(ehr, "check_session", return_value=ADMIN)
    @patch("requests.post")
    @patch("requests.get")
    def test_failed_workflow_passes_through_503(self, mock_get, mock_post, _session, client):
        failed = {**WORKFLOW, "status": "failed", "steps": {
            "planner": {"status": "failed", "model": "qwen2.5:0.5b", "error": "LLM unreachable"}}}
        mock_get.return_value = fake_response(RECORDS)
        mock_post.return_value = fake_response(failed, 503)
        resp = start(client)
        assert resp.status_code == 503
        assert resp.get_json()["status"] == "failed"
        assert resp.get_json()["steps"]["planner"]["error"] == "LLM unreachable"


class TestReviewWorkflow:

    URL = f"/multi-agent/workflow/{WORKFLOW_ID}/review"

    def review(self, client, **body):
        payload = {"token": "t", "decision": "approve"}
        payload.update(body)
        return client.post(self.URL, json=payload)

    @patch.object(ehr, "check_session", return_value=PATIENT)
    def test_patients_cannot_review(self, _session, client):
        assert self.review(client).status_code == 403

    @patch.object(ehr, "MULTI_AGENT_ENABLED", False)
    @patch.object(ehr, "check_session", return_value=ADMIN)
    def test_disabled_flag_returns_503(self, _session, client):
        resp = self.review(client)
        assert resp.status_code == 503
        assert resp.get_json()["status"] == "disabled"

    @patch.object(ehr, "check_session", return_value=ADMIN)
    def test_invalid_workflow_id(self, _session, client):
        resp = client.post("/multi-agent/workflow/not-an-id/review", json={"token": "t", "decision": "approve"})
        assert resp.status_code == 400

    @patch.object(ehr, "check_session", return_value=ADMIN)
    def test_invalid_decision(self, _session, client):
        assert self.review(client, decision="maybe").status_code == 400

    @patch.object(ehr, "check_session", return_value=ADMIN)
    def test_correct_requires_correction(self, _session, client):
        assert self.review(client, decision="correct", correction=" ").status_code == 400

    @patch.object(ehr, "check_session", return_value=ADMIN)
    @patch("requests.post")
    def test_approve_records_decision(self, mock_post, _session, client):
        mock_post.return_value = fake_response(
            {**WORKFLOW, "status": "approved", "final_output": "Patient has asthma"}, 200)

        resp = self.review(client, decision="approve", notes="checked")

        assert resp.status_code == 200
        sent = mock_post.call_args.kwargs["json"]
        assert sent == {"decision": "approve", "reviewer": "EHR staff (admin)",
                        "notes": "checked", "correction": None}
        assert resp.get_json()["status"] == "approved"

    @pytest.mark.parametrize("decision", ["partially_accept", "reject"])
    @patch.object(ehr, "check_session", return_value=ADMIN)
    @patch("requests.post")
    def test_other_decisions_are_forwarded(self, mock_post, _session, decision, client):
        mock_post.return_value = fake_response({**WORKFLOW, "status": decision}, 200)
        resp = self.review(client, decision=decision)
        assert resp.status_code == 200
        assert mock_post.call_args.kwargs["json"]["decision"] == decision

    @patch.object(ehr, "check_session", return_value=ADMIN)
    @patch("requests.post")
    def test_correct_sends_correction(self, mock_post, _session, client):
        mock_post.return_value = fake_response(
            {**WORKFLOW, "status": "corrected", "final_output": "Asthma, penicillin allergy"}, 200)
        resp = self.review(client, decision="correct", correction="Asthma, penicillin allergy")
        assert resp.status_code == 200
        assert mock_post.call_args.kwargs["json"]["correction"] == "Asthma, penicillin allergy"

    @patch.object(ehr, "check_session", return_value=ADMIN)
    @patch("requests.post")
    def test_already_reviewed_passes_through_409(self, mock_post, _session, client):
        mock_post.return_value = fake_response(
            {"error": "workflow is 'approved', not awaiting human review"}, 409)
        resp = self.review(client, decision="reject")
        assert resp.status_code == 409
        assert "not awaiting human review" in resp.get_json()["error"]

    @patch.object(ehr, "check_session", return_value=ADMIN)
    @patch("requests.post")
    def test_server_down_returns_503(self, mock_post, _session, client):
        mock_post.side_effect = requests.exceptions.ConnectionError()
        assert self.review(client).status_code == 503


class TestHistory:

    @patch.object(ehr, "check_session", return_value=PATIENT)
    def test_patients_cannot_view_history(self, _session, client):
        assert client.get("/multi-agent/history?token=t").status_code == 403

    @patch.object(ehr, "MULTI_AGENT_ENABLED", False)
    @patch.object(ehr, "check_session", return_value=ADMIN)
    def test_disabled_flag_returns_503(self, _session, client):
        resp = client.get("/multi-agent/history?token=t")
        assert resp.status_code == 503
        assert resp.get_json()["status"] == "disabled"

    @patch.object(ehr, "check_session", return_value=ADMIN)
    @patch("requests.get")
    def test_lists_recent_ehr_workflows(self, mock_get, _session, client):
        reviewed = {**WORKFLOW, "status": "approved", "user_request": "Summarise",
                    "human_review": {"reviewer": "EHR staff (admin)"}}
        mock_get.return_value = fake_response({"workflows": [reviewed]})
        resp = client.get("/multi-agent/history?token=t")
        assert resp.status_code == 200
        assert mock_get.call_args.kwargs["params"] == {"feature": "ehr", "limit": 5}
        assert resp.get_json()["workflows"][0]["workflow_id"] == WORKFLOW_ID

    @patch.object(ehr, "check_session", return_value=ADMIN)
    @patch("requests.get")
    def test_server_down_returns_503(self, mock_get, _session, client):
        mock_get.side_effect = requests.exceptions.ConnectionError()
        resp = client.get("/multi-agent/history?token=t")
        assert resp.status_code == 503
        assert resp.get_json()["workflows"] == []