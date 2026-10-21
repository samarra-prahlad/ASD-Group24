"""
Post-commit endpoint tests for the Appointments backend (Release 2).

Endpoint functions under test:
  1. POST /multi-agent/workflow/html               -> multi_agent_workflow_html()
  2. POST /multi-agent/workflow/<id>/review/html   -> multi_agent_review_html()

All outbound HTTP (shared-backend session check, appointments-database and
the Multi-Agent Server) is replaced with fakes, so these tests run in CI
without Ollama, MCP, RAG or the Multi-Agent Server.
"""
import os
import sys

import pytest
import requests

BACKEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import app  # noqa: E402
from routes import multi_agent  # noqa: E402

WORKFLOW_ID = "wf-0123456789ab"

APPOINTMENTS = [
    {"id": 11, "patient_id": 1, "doctor_id": 3, "doctor_name": "Dr Lee", "doctor_specialty": "Cardiology",
     "date": "2026-10-22", "time": "09:00", "status": "scheduled"},
    {"id": 12, "patient_id": 2, "doctor_id": 3, "doctor_name": "Dr Lee", "doctor_specialty": "Cardiology",
     "date": "2026-10-22", "time": "09:30", "status": "scheduled"},
]
CHANGES = [
    {"id": 5, "appointment_id": 11, "patient_id": 1, "doctor_name": "Dr Lee", "doctor_specialty": "Cardiology",
     "current_date": "2026-10-22", "current_time": "09:00",
     "requested_date": "2026-10-23", "requested_time": "10:00", "status": "pending"},
]


def awaiting_workflow(evidence_count=3):
    return {
        "workflow_id": WORKFLOW_ID,
        "feature": "appointments",
        "status": "awaiting_human_review",
        "evidence_count": evidence_count,
        "steps": {
            "planner": {"status": "completed", "model": "qwen2.5:0.5b", "output": "1. List appointments."},
            "worker": {"status": "completed", "model": "qwen2.5:0.5b",
                       "output": "Appointment 11 has a pending change. Evidence Used: 11, 5"},
            "reviewer": {"status": "completed", "model": "llama3.1:8b", "output": "Risk level: LOW",
                         "risk_level": "LOW", "recommendation": "APPROVE",
                         "grounding": {"evidence_ids_available": 6, "evidence_ids_cited": 2},
                         "governance_notes": []},
        },
        "human_review": None,
        "final_output": None,
    }


class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body

    def json(self):
        if self._body is None:
            raise ValueError("no JSON body")
        return self._body


class FakeServices:
    """Routes requests.get / requests.post calls made by routes.multi_agent to canned responses."""

    def __init__(self, role="admin"):
        self.role = role
        self.calls = []
        self.workflow_response = FakeResponse(201, awaiting_workflow())
        self.review_response = None
        self.multi_agent_down = False
        self.database_down = False

    def post(self, url, json=None, timeout=None, **kwargs):
        self.calls.append(("POST", url, json))
        if url.endswith("/session/verify"):
            if json.get("token") != "good-token":
                return FakeResponse(401, {"error": "invalid"})
            return FakeResponse(200, {"role": self.role, "patient_id": 1, "first_name": "Kathrynna"})
        if self.multi_agent_down:
            raise requests.ConnectionError("multi-agent server down")
        if url.endswith("/workflow"):
            return self.workflow_response
        if url.endswith("/review"):
            return self.review_response or FakeResponse(200, {
                **awaiting_workflow(),
                "status": "approved",
                "final_output": awaiting_workflow()["steps"]["worker"]["output"],
                "human_review": {"decision": json["decision"], "reviewer": json["reviewer"]},
            })
        raise AssertionError(f"unexpected POST {url}")

    def get(self, url, params=None, timeout=None, **kwargs):
        self.calls.append(("GET", url, params))
        if self.database_down:
            raise requests.ConnectionError("database down")
        if url.endswith("/appointment-changes"):
            return FakeResponse(200, CHANGES)
        if "/appointments/patient/" in url:
            pid = int(url.rsplit("/", 1)[1])
            return FakeResponse(200, [a for a in APPOINTMENTS if a["patient_id"] == pid])
        if "/appointments/date/" in url:
            day = url.rsplit("/", 1)[1]
            return FakeResponse(200, [a for a in APPOINTMENTS if a["date"] == day])
        if url.endswith("/appointments"):
            return FakeResponse(200, APPOINTMENTS)
        if url.endswith("/workflows"):
            return FakeResponse(200, {"workflows": [awaiting_workflow()]})
        raise AssertionError(f"unexpected GET {url}")

    def posted(self, suffix):
        return [payload for method, url, payload in self.calls if method == "POST" and url.endswith(suffix)]


@pytest.fixture
def services(monkeypatch):
    fake = FakeServices()
    monkeypatch.setattr(multi_agent.requests, "post", fake.post)
    monkeypatch.setattr(multi_agent.requests, "get", fake.get)
    monkeypatch.setattr(multi_agent, "MULTI_AGENT_ENABLED", True)
    return fake


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


ADMIN = {"X-Session-Token": "good-token"}


# ---------------------------------------------------------------------------
# Endpoint 1: POST /multi-agent/workflow/html
# ---------------------------------------------------------------------------

class TestStartWorkflow:
    def test_admin_runs_planner_worker_reviewer_and_gets_review_form(self, client, services):
        response = client.post("/multi-agent/workflow/html", headers=ADMIN,
                               data={"user_request": "Summarise appointments and flag conflicts"})
        html = response.get_data(as_text=True)

        assert response.status_code == 200
        assert response.headers["HX-Trigger"] == "multiAgentChanged"
        for agent in ("Planner", "Worker", "Reviewer"):
            assert agent in html
        assert "awaiting_human_review" in html
        assert f'id="agent-review-{WORKFLOW_ID}"' in html
        for decision in ("approve", "partially_accept", "correct", "reject"):
            assert f"value='{decision}'" in html
        assert "good-token" not in html  # token never leaks into rendered HTML

    def test_sends_appointment_evidence_to_multi_agent_server(self, client, services):
        client.post("/multi-agent/workflow/html", headers=ADMIN,
                    data={"user_request": "Check patient 1", "patient_id": "1"})

        payload = services.posted("/workflow")[0]
        assert payload["feature"] == "appointments"
        assert payload["user_request"] == "Check patient 1 (Patient ID: 1)"
        assert payload["requested_by"] == "Kathrynna (admin)"
        types = sorted(r["record_type"] for r in payload["evidence"])
        assert types == ["appointment", "change_request"]
        assert all(r["patient_id"] == 1 for r in payload["evidence"])

    def test_can_exclude_change_requests(self, client, services):
        client.post("/multi-agent/workflow/html", headers=ADMIN,
                    data={"user_request": "Appointments only", "include_changes": "off"})

        evidence = services.posted("/workflow")[0]["evidence"]
        assert len(evidence) == 2
        assert {r["record_type"] for r in evidence} == {"appointment"}

    def test_missing_token_is_401(self, client, services):
        response = client.post("/multi-agent/workflow/html", data={"user_request": "x"})
        assert response.status_code == 401
        assert services.posted("/workflow") == []

    def test_patient_role_is_403(self, client, services):
        services.role = "patient"
        response = client.post("/multi-agent/workflow/html", headers=ADMIN, data={"user_request": "x"})
        assert response.status_code == 403
        assert services.posted("/workflow") == []

    @pytest.mark.parametrize("form, message", [
        ({"user_request": ""}, "Enter a request"),
        ({"user_request": "x", "patient_id": "abc"}, "Patient ID must be a number"),
        ({"user_request": "x", "date": "22/10/2026"}, "YYYY-MM-DD"),
    ])
    def test_invalid_input_is_400(self, client, services, form, message):
        response = client.post("/multi-agent/workflow/html", headers=ADMIN, data=form)
        assert response.status_code == 400
        assert message in response.get_data(as_text=True)

    def test_disabled_by_config_is_503(self, client, services, monkeypatch):
        monkeypatch.setattr(multi_agent, "MULTI_AGENT_ENABLED", False)
        response = client.post("/multi-agent/workflow/html", headers=ADMIN, data={"user_request": "x"})
        assert response.status_code == 503
        assert "disabled" in response.get_data(as_text=True)

    def test_multi_agent_server_down_is_503(self, client, services):
        services.multi_agent_down = True
        response = client.post("/multi-agent/workflow/html", headers=ADMIN, data={"user_request": "x"})
        assert response.status_code == 503
        assert "unavailable" in response.get_data(as_text=True)

    def test_database_down_is_503(self, client, services):
        services.database_down = True
        response = client.post("/multi-agent/workflow/html", headers=ADMIN, data={"user_request": "x"})
        assert response.status_code == 503
        assert services.posted("/workflow") == []

    def test_failed_agent_shows_error_and_no_review_form(self, client, services):
        failed = awaiting_workflow()
        failed["status"] = "failed"
        failed["steps"]["worker"] = {"status": "failed", "model": "qwen2.5:0.5b", "error": "LLM unreachable"}
        services.workflow_response = FakeResponse(503, failed)

        response = client.post("/multi-agent/workflow/html", headers=ADMIN, data={"user_request": "x"})
        html = response.get_data(as_text=True)
        assert response.status_code == 503
        assert "LLM unreachable" in html
        assert "agent-review-" not in html

    def test_agent_output_is_html_escaped(self, client, services):
        wf = awaiting_workflow()
        wf["steps"]["worker"]["output"] = "<script>alert(1)</script>"
        services.workflow_response = FakeResponse(201, wf)

        html = client.post("/multi-agent/workflow/html", headers=ADMIN,
                           data={"user_request": "x"}).get_data(as_text=True)
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html


# ---------------------------------------------------------------------------
# Endpoint 2: POST /multi-agent/workflow/<workflow_id>/review/html
# ---------------------------------------------------------------------------

class TestReviewWorkflow:
    def url(self, workflow_id=WORKFLOW_ID):
        return f"/multi-agent/workflow/{workflow_id}/review/html"

    def test_approve_records_decision_and_releases_output(self, client, services):
        response = client.post(self.url(), headers=ADMIN, data={"decision": "approve", "notes": "Looks right"})
        html = response.get_data(as_text=True)

        assert response.status_code == 200
        assert "Decision recorded" in html and "Approve" in html
        assert "approved" in html
        assert "Appointment 11 has a pending change" in html
        assert f"id='agent-review-{WORKFLOW_ID}' hx-swap-oob='true'" in html  # buttons removed

        payload = services.posted("/review")[0]
        assert payload == {"decision": "approve", "reviewer": "Kathrynna (admin)",
                           "notes": "Looks right", "correction": None}

    def test_correct_sends_correction(self, client, services):
        services.review_response = FakeResponse(200, {
            **awaiting_workflow(), "status": "corrected", "final_output": "Fixed summary"})
        response = client.post(self.url(), headers=ADMIN,
                               data={"decision": "correct", "correction": "Fixed summary"})

        assert response.status_code == 200
        assert "Fixed summary" in response.get_data(as_text=True)
        assert services.posted("/review")[0]["correction"] == "Fixed summary"

    def test_reject_releases_nothing(self, client, services):
        services.review_response = FakeResponse(200, {
            **awaiting_workflow(), "status": "rejected", "final_output": None})
        html = client.post(self.url(), headers=ADMIN, data={"decision": "reject"}).get_data(as_text=True)
        assert "No output released" in html

    def test_correct_without_correction_is_400(self, client, services):
        response = client.post(self.url(), headers=ADMIN, data={"decision": "correct"})
        assert response.status_code == 400
        assert services.posted("/review") == []

    def test_unknown_decision_is_400(self, client, services):
        response = client.post(self.url(), headers=ADMIN, data={"decision": "maybe"})
        assert response.status_code == 400

    def test_malformed_workflow_id_is_400(self, client, services):
        response = client.post(self.url("not-a-workflow"), headers=ADMIN, data={"decision": "approve"})
        assert response.status_code == 400
        assert services.posted("/review") == []

    def test_patient_cannot_review(self, client, services):
        services.role = "patient"
        response = client.post(self.url(), headers=ADMIN, data={"decision": "approve"})
        assert response.status_code == 403
        assert services.posted("/review") == []

    def test_already_reviewed_conflict_is_relayed(self, client, services):
        services.review_response = FakeResponse(
            409, {"error": "workflow is 'approved', not awaiting human review"})
        response = client.post(self.url(), headers=ADMIN, data={"decision": "approve"})
        assert response.status_code == 409
        assert "not awaiting human review" in response.get_data(as_text=True)

    def test_multi_agent_server_down_is_503(self, client, services):
        services.multi_agent_down = True
        response = client.post(self.url(), headers=ADMIN, data={"decision": "approve"})
        assert response.status_code == 503


# ---------------------------------------------------------------------------
# Supporting: history panel and evidence shaping
# ---------------------------------------------------------------------------

def test_history_lists_appointment_workflows(client, services):
    response = client.get("/multi-agent/history/html", headers=ADMIN)
    assert response.status_code == 200
    assert WORKFLOW_ID in response.get_data(as_text=True)
    get_calls = [(url, params) for method, url, params in services.calls if method == "GET"]
    assert get_calls[-1][1] == {"feature": "appointments", "limit": 5}


def test_evidence_keeps_only_whitelisted_fields():
    record = dict(APPOINTMENTS[0], notes="free text", phone="0400 000 000")
    evidence = multi_agent.appointment_evidence([record])[0]
    assert "notes" not in evidence and "phone" not in evidence
    assert evidence["appointment_id"] == 11