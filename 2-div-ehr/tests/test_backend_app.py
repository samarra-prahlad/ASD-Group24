import os
import sys
import importlib.util
from unittest.mock import patch, MagicMock
import pytest
import requests

FEATURE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(FEATURE_ROOT, "backend")
sys.path.insert(0, BACKEND_DIR)  # so app.py's `from mcp_client import ...` / `from rag_client import ...` resolve


def _load_module(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ehr_backend_app = _load_module("ehr_backend_app", os.path.join(BACKEND_DIR, "app.py"))


def fake_response(json_data, status_code=200):
    """A minimal stand-in for requests.Response, just enough for our code paths."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    response.raise_for_status.side_effect = (
        None if status_code < 400
        else requests.exceptions.HTTPError(response=response)
    )
    return response


def fake_session(patient_id=3, role="patient"):
    return {"valid": True, "patient_id": patient_id, "role": role, "first_name": "Test"}


@pytest.fixture
def client():
    ehr_backend_app.app.config["TESTING"] = True
    with ehr_backend_app.app.test_client() as test_client:
        yield test_client

class TestHealth:

    def test_health_check_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_health_check_reports_service_name(self, client):
        response = client.get("/")
        data = response.get_json()
        assert data["service"] == "ehr-backend"
        assert data["status"] == "running"

class TestWhoami:

    def test_whoami_without_token_returns_400(self, client):
        response = client.get("/whoami")
        assert response.status_code == 400

    @patch("requests.post")
    def test_whoami_with_valid_token_returns_identity(self, mock_post, client):
        mock_post.return_value = fake_response(fake_session(patient_id=3, role="patient"), 200)

        response = client.get("/whoami?token=good-token")

        assert response.status_code == 200
        data = response.get_json()
        assert data["patient_id"] == 3
        assert data["role"] == "patient"

    @patch("requests.post")
    def test_whoami_with_invalid_token_returns_401(self, mock_post, client):
        mock_post.return_value = fake_response({"valid": False}, 401)

        response = client.get("/whoami?token=bad-token")
        assert response.status_code == 401

    @patch("requests.post")
    def test_whoami_when_shared_backend_unreachable_returns_503(self, mock_post, client):
        mock_post.side_effect = requests.exceptions.ConnectionError()

        response = client.get("/whoami?token=any-token")
        assert response.status_code == 503

class TestPatientsRoute:

    def test_patients_without_token_returns_400(self, client):
        response = client.get("/patients")
        assert response.status_code == 400

    @patch("requests.post")
    def test_patients_as_patient_role_returns_403(self, mock_post, client):
        mock_post.return_value = fake_response(fake_session(role="patient"), 200)

        response = client.get("/patients?token=patient-token")
        assert response.status_code == 403

    @patch("requests.get")
    @patch("requests.post")
    def test_patients_as_admin_returns_list(self, mock_post, mock_get, client):
        mock_post.return_value = fake_response(fake_session(role="admin"), 200)
        mock_get.return_value = fake_response([{"patient_id": 3, "first_name": "John"}], 200)

        response = client.get("/patients?token=admin-token")

        assert response.status_code == 200
        assert response.get_json() == [{"patient_id": 3, "first_name": "John"}]

    @patch("requests.get")
    @patch("requests.post")
    def test_patients_when_shared_database_unreachable_returns_503(self, mock_post, mock_get, client):
        mock_post.return_value = fake_response(fake_session(role="admin"), 200)
        mock_get.side_effect = requests.exceptions.ConnectionError()

        response = client.get("/patients?token=admin-token")
        assert response.status_code == 503

class TestGetRecords:

    @patch("requests.get")
    @patch("requests.post")
    def test_patient_can_view_own_records(self, mock_post, mock_get, client):
        mock_post.return_value = fake_response(fake_session(patient_id=3, role="patient"), 200)
        mock_get.return_value = fake_response([{"id": 1, "patient_id": 3}], 200)

        response = client.get("/records/3?token=patient-token")

        assert response.status_code == 200
        assert response.get_json() == [{"id": 1, "patient_id": 3}]

    @patch("requests.post")
    def test_patient_cannot_view_others_records(self, mock_post, client):
        mock_post.return_value = fake_response(fake_session(patient_id=3, role="patient"), 200)

        response = client.get("/records/4?token=patient-token")
        assert response.status_code == 403

    @patch("requests.get")
    @patch("requests.post")
    def test_admin_can_view_any_patients_records(self, mock_post, mock_get, client):
        mock_post.return_value = fake_response(fake_session(role="admin"), 200)
        mock_get.return_value = fake_response([{"id": 5, "patient_id": 9}], 200)

        response = client.get("/records/9?token=admin-token")
        assert response.status_code == 200

    @patch("requests.get")
    @patch("requests.post")
    def test_records_when_ehr_database_unreachable_returns_503(self, mock_post, mock_get, client):
        mock_post.return_value = fake_response(fake_session(role="admin"), 200)
        mock_get.side_effect = requests.exceptions.ConnectionError()

        response = client.get("/records/3?token=admin-token")
        assert response.status_code == 503

class TestRecordsWriteRoutes:

    @patch("requests.post")
    def test_create_record_as_patient_returns_403(self, mock_post, client):
        mock_post.return_value = fake_response(fake_session(role="patient"), 200)

        response = client.post("/records", json={"token": "patient-token", "patient_id": 3})
        assert response.status_code == 403

    @patch("requests.post")
    def test_create_record_as_admin_succeeds(self, mock_post, client):
        mock_post.side_effect = [
            fake_response(fake_session(role="admin"), 200),  
            fake_response({"id": 42}, 201),                    
        ]

        response = client.post("/records", json={
            "token": "admin-token", "patient_id": 3, "diagnosis": "Test",
        })
        assert response.status_code == 201
        assert response.get_json() == {"id": 42}

    @patch("requests.put")
    @patch("requests.post")
    def test_update_record_as_admin_succeeds(self, mock_post, mock_put, client):
        mock_post.return_value = fake_response(fake_session(role="admin"), 200)
        mock_put.return_value = fake_response({"message": "Record updated successfully"}, 200)

        response = client.put("/records/1", json={"token": "admin-token", "diagnosis": "Updated"})
        assert response.status_code == 200

    @patch("requests.post")
    def test_update_record_as_patient_returns_403(self, mock_post, client):
        mock_post.return_value = fake_response(fake_session(role="patient"), 200)

        response = client.put("/records/1", json={"token": "patient-token", "diagnosis": "Hacked"})
        assert response.status_code == 403

    @patch("requests.delete")
    @patch("requests.post")
    def test_delete_record_as_admin_succeeds(self, mock_post, mock_delete, client):
        mock_post.return_value = fake_response(fake_session(role="admin"), 200)
        mock_delete.return_value = fake_response({"message": "Record deleted successfully"}, 200)

        response = client.delete("/records/1?token=admin-token")
        assert response.status_code == 200

    @patch("requests.post")
    def test_delete_record_as_patient_returns_403(self, mock_post, client):
        mock_post.return_value = fake_response(fake_session(role="patient"), 200)

        response = client.delete("/records/1?token=patient-token")
        assert response.status_code == 403

class TestDiagnosisRoute:

    @patch("requests.get")
    def test_diagnosis_requires_no_token(self, mock_get, client):
        mock_get.return_value = fake_response(
            [{"diagnosis": "Type 2 Diabetes", "allergies": "Penicillin"}], 200
        )

        response = client.get("/diagnosis/3")
        assert response.status_code == 200
        data = response.get_json()
        assert data["diagnosis"] == "Type 2 Diabetes"
        assert data["allergies"] == "Penicillin"

    @patch("requests.get")
    def test_diagnosis_for_patient_with_no_records_returns_404(self, mock_get, client):
        mock_get.return_value = fake_response([], 200)

        response = client.get("/diagnosis/999999")
        assert response.status_code == 404

    @patch("requests.get")
    def test_diagnosis_when_ehr_database_unreachable_returns_503(self, mock_get, client):
        mock_get.side_effect = requests.exceptions.ConnectionError()

        response = client.get("/diagnosis/3")
        assert response.status_code == 503

class TestChangeRequestsRoutes:

    @patch("requests.post")
    def test_get_all_change_requests_as_patient_returns_403(self, mock_post, client):
        mock_post.return_value = fake_response(fake_session(role="patient"), 200)

        response = client.get("/change_requests?token=patient-token")
        assert response.status_code == 403

    @patch("requests.get")
    @patch("requests.post")
    def test_get_all_change_requests_as_admin_succeeds(self, mock_post, mock_get, client):
        mock_post.return_value = fake_response(fake_session(role="admin"), 200)
        mock_get.return_value = fake_response([{"id": 1, "status": "pending"}], 200)

        response = client.get("/change_requests?token=admin-token")
        assert response.status_code == 200

    @patch("requests.post")
    def test_patient_can_only_submit_request_for_self(self, mock_post, client):
        mock_post.return_value = fake_response(fake_session(patient_id=3, role="patient"), 200)

        response = client.post("/change_requests", json={
            "token": "patient-token", "patient_id": 4, "request_type": "Other",
        })
        assert response.status_code == 403

    @patch("requests.post")
    def test_patient_can_submit_request_for_self(self, mock_post, client):
        mock_post.side_effect = [
            fake_response(fake_session(patient_id=3, role="patient"), 200),  
            fake_response({"id": 7}, 201),                                   
        ]

        response = client.post("/change_requests", json={
            "token": "patient-token", "patient_id": 3, "request_type": "Update Allergies",
        })
        assert response.status_code == 201

    @patch("requests.post")
    def test_only_admin_can_approve_change_request(self, mock_post, client):
        mock_post.return_value = fake_response(fake_session(role="patient"), 200)

        response = client.put("/change_requests/1", json={"token": "patient-token", "status": "approved"})
        assert response.status_code == 403

    @patch("requests.put")
    @patch("requests.post")
    def test_admin_can_approve_change_request(self, mock_post, mock_put, client):
        mock_post.return_value = fake_response(fake_session(role="admin"), 200)
        mock_put.return_value = fake_response({"message": "Change request updated successfully"}, 200)

        response = client.put("/change_requests/1", json={"token": "admin-token", "status": "approved"})
        assert response.status_code == 200

    @patch("requests.delete")
    @patch("requests.post")
    def test_delete_change_request_as_admin_succeeds(self, mock_post, mock_delete, client):
        mock_post.return_value = fake_response(fake_session(role="admin"), 200)
        mock_delete.return_value = fake_response({"message": "Change request deleted successfully"}, 200)

        response = client.delete("/change_requests/1?token=admin-token")
        assert response.status_code == 200

    @patch("requests.post")
    def test_delete_change_request_as_patient_returns_403(self, mock_post, client):
        mock_post.return_value = fake_response(fake_session(role="patient"), 200)

        response = client.delete("/change_requests/1?token=patient-token")
        assert response.status_code == 403

class TestSummarizeRoute:

    @patch("requests.post")
    def test_patient_cannot_summarize_someone_elses_history(self, mock_post, client):
        mock_post.return_value = fake_response(fake_session(patient_id=3, role="patient"), 200)

        response = client.post("/summarize", json={
            "token": "patient-token", "patient_id": 4, "question": "Summarize",
        })
        assert response.status_code == 403

    @patch("requests.get")
    @patch("requests.post")
    def test_summarize_with_no_history_skips_ai_call(self, mock_post, mock_get, client):
        mock_post.return_value = fake_response(fake_session(patient_id=3, role="patient"), 200)
        mock_get.return_value = fake_response([], 200)

        response = client.post("/summarize", json={
            "token": "patient-token", "patient_id": 3, "question": "",
        })
        assert response.status_code == 200
        assert "No medical history found" in response.get_json()["reply"]

    @patch("requests.get")
    @patch("requests.post")
    def test_summarize_with_history_calls_ai_and_returns_reply(self, mock_post, mock_get, client, monkeypatch):
        mock_post.return_value = fake_response(fake_session(patient_id=3, role="patient"), 200)
        mock_get.return_value = fake_response([{
            "visit_date": "2026-06-10", "diagnosis": "Type 2 Diabetes",
            "treatment": "Metformin", "notes": "Stable", "allergies": "Penicillin",
        }], 200)

        fake_completion = MagicMock()
        fake_completion.choices[0].message.content = "Patient has stable Type 2 Diabetes."
        monkeypatch.setattr(
            ehr_backend_app.client.chat.completions, "create",
            lambda **kwargs: fake_completion,
        )

        response = client.post("/summarize", json={
            "token": "patient-token", "patient_id": 3, "question": "Summarize this",
        })
        assert response.status_code == 200
        assert "Type 2 Diabetes" in response.get_json()["reply"]

    @patch("requests.get")
    @patch("requests.post")
    def test_summarize_when_ai_fails_returns_503(self, mock_post, mock_get, client, monkeypatch):
        mock_post.return_value = fake_response(fake_session(patient_id=3, role="patient"), 200)
        mock_get.return_value = fake_response([{
            "visit_date": "2026-06-10", "diagnosis": "Test", "treatment": "N/A",
            "notes": "N/A", "allergies": "N/A",
        }], 200)

        def raise_error(**kwargs):
            raise RuntimeError("Ollama not reachable")
        monkeypatch.setattr(ehr_backend_app.client.chat.completions, "create", raise_error)

        response = client.post("/summarize", json={
            "token": "patient-token", "patient_id": 3, "question": "Summarize",
        })
        assert response.status_code == 503

    @patch("requests.get")
    @patch("requests.post")
    def test_summarize_when_ehr_database_unreachable_returns_503(self, mock_post, mock_get, client):
        mock_post.return_value = fake_response(fake_session(patient_id=3, role="patient"), 200)
        mock_get.side_effect = requests.exceptions.ConnectionError()

        response = client.post("/summarize", json={
            "token": "patient-token", "patient_id": 3, "question": "Summarize",
        })
        assert response.status_code == 503

class TestMcpStatusRoute:

    @patch.object(ehr_backend_app, "call_get_change_request_status")
    @patch("requests.post")
    def test_mcp_status_returns_result_on_success(self, mock_post, mock_call, client):
        mock_post.return_value = fake_response(fake_session(role="admin"), 200)
        mock_call.return_value = {
            "request_id": 7, "status": "approved", "patient_id": 3, "request_type": "Update Allergies",
        }

        response = client.get("/change_requests/mcp-status/7?token=admin-token")

        assert response.status_code == 200
        assert response.get_json()["status"] == "approved"

    @patch.object(ehr_backend_app, "call_get_change_request_status")
    @patch("requests.post")
    def test_mcp_status_tool_reported_error_returns_404(self, mock_post, mock_call, client):
        mock_post.return_value = fake_response(fake_session(role="admin"), 200)
        mock_call.return_value = {"error": "Change request not found", "request_id": 999}

        response = client.get("/change_requests/mcp-status/999?token=admin-token")

        assert response.status_code == 404

    @patch.object(ehr_backend_app, "call_get_change_request_status")
    @patch("requests.post")
    def test_mcp_status_server_unreachable_returns_503(self, mock_post, mock_call, client):
        mock_post.return_value = fake_response(fake_session(role="admin"), 200)
        mock_call.side_effect = RuntimeError("MCP server unavailable")

        response = client.get("/change_requests/mcp-status/1?token=admin-token")

        assert response.status_code == 503

    @patch.object(ehr_backend_app, "MCP_ENABLED", False)
    @patch("requests.post")
    def test_mcp_status_returns_503_when_disabled(self, mock_post, client):
        mock_post.return_value = fake_response(fake_session(role="admin"), 200)

        response = client.get("/change_requests/mcp-status/1?token=admin-token")

        assert response.status_code == 503


class TestAskRagRoute:

    @patch.object(ehr_backend_app, "call_answer_question")
    @patch("requests.post")
    def test_ask_rag_returns_answer_on_success(self, mock_post, mock_call, client):
        mock_post.return_value = fake_response(fake_session(role="patient"), 200)
        mock_call.return_value = {
            "status": "ok",
            "answer": "Change requests are reviewed within 5 business days.",
            "citations": [{"source_id": "ehr/change_request_policy.md"}],
            "confidence_category": "High",
        }

        response = client.post("/ask-rag", json={
            "token": "patient-token", "question": "How long do change requests take?",
        })

        assert response.status_code == 200
        assert response.get_json()["confidence_category"] == "High"

    @patch("requests.post")
    def test_ask_rag_missing_question_returns_400(self, mock_post, client):
        mock_post.return_value = fake_response(fake_session(role="patient"), 200)

        response = client.post("/ask-rag", json={"token": "patient-token", "question": ""})

        assert response.status_code == 400

    @patch.object(ehr_backend_app, "call_answer_question")
    @patch("requests.post")
    def test_ask_rag_server_unreachable_returns_503(self, mock_post, mock_call, client):
        mock_post.return_value = fake_response(fake_session(role="patient"), 200)
        mock_call.side_effect = RuntimeError("RAG server unavailable")

        response = client.post("/ask-rag", json={"token": "patient-token", "question": "test"})

        assert response.status_code == 503

    @patch.object(ehr_backend_app, "RAG_ENABLED", False)
    @patch("requests.post")
    def test_ask_rag_returns_503_when_disabled(self, mock_post, client):
        mock_post.return_value = fake_response(fake_session(role="patient"), 200)

        response = client.post("/ask-rag", json={"token": "patient-token", "question": "test"})

        assert response.status_code == 503