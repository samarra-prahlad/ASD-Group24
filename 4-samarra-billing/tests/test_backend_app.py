"""
Pytest suite for the Billing & Insurance backend business-logic tier (backend/app.py).

Mocks all outbound HTTP calls (to billing-database and to the other services'
backend APIs) so these tests run without any real services running.

Run with:
    pytest tests/test_backend_app.py -v
"""

import os
import importlib.util
from unittest.mock import patch, MagicMock

import pytest
import requests

FEATURE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(FEATURE_ROOT, "backend")


def _load_module(module_name, file_path):
    """
    Load a .py file as a module under an explicit unique name, rather than a
    plain `import app`. Both database/app.py and backend/app.py are named
    app.py - a plain import would collide in sys.modules if both test files
    run in the same pytest session, silently reusing whichever was imported
    first. Loading by explicit name avoids that entirely.
    """
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


billing_backend_app = _load_module("billing_backend_app", os.path.join(BACKEND_DIR, "app.py"))


def fake_response(json_data, status_code=200):
    """A minimal stand-in for requests.Response, just enough for our code paths."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    return response


@pytest.fixture
def client():
    billing_backend_app.app.config["TESTING"] = True
    with billing_backend_app.app.test_client() as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealth:

    def test_health_check_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_health_check_reports_service_name(self, client):
        response = client.get("/")
        data = response.get_json()
        assert data["service"] == "billing-backend"
        assert data["status"] == "running"


# ---------------------------------------------------------------------------
# Proxy routes to billing-database
# ---------------------------------------------------------------------------

class TestProxyRoutes:

    @patch("requests.get")
    def test_get_invoices_proxies_database_response(self, mock_get, client):
        mock_get.return_value = fake_response([{"id": 1}, {"id": 2}], 200)

        response = client.get("/invoices")

        assert response.status_code == 200
        assert response.get_json() == [{"id": 1}, {"id": 2}]

    @patch("requests.get")
    def test_get_invoices_passes_through_upstream_error_status(self, mock_get, client):
        mock_get.return_value = fake_response({"error": "Invoice not found"}, 404)

        response = client.get("/invoices/999999")

        assert response.status_code == 404
        assert response.get_json() == {"error": "Invoice not found"}

    @patch("requests.get")
    def test_get_invoices_returns_503_when_database_unreachable(self, mock_get, client):
        mock_get.side_effect = requests.exceptions.ConnectionError()

        response = client.get("/invoices")

        assert response.status_code == 503
        assert "error" in response.get_json()

    @patch("requests.get")
    def test_get_single_invoice_proxies_correctly(self, mock_get, client):
        mock_get.return_value = fake_response({"id": 3, "patient_id": 101}, 200)

        response = client.get("/invoices/3")

        assert response.status_code == 200
        assert response.get_json()["patient_id"] == 101

    @patch("requests.get")
    def test_get_invoices_by_patient_proxies_correctly(self, mock_get, client):
        mock_get.return_value = fake_response([{"id": 1, "patient_id": 101}], 200)

        response = client.get("/invoices/patient/101")

        assert response.status_code == 200
        assert len(response.get_json()) == 1

    @patch("requests.get")
    def test_get_insurance_providers_proxies_correctly(self, mock_get, client):
        mock_get.return_value = fake_response([{"id": 301, "name": "Medibank"}], 200)

        response = client.get("/insurance-providers")

        assert response.status_code == 200
        assert response.get_json()[0]["name"] == "Medibank"

    @patch("requests.get")
    def test_get_insurance_providers_returns_503_when_database_unreachable(self, mock_get, client):
        mock_get.side_effect = requests.exceptions.Timeout()

        response = client.get("/insurance-providers")

        assert response.status_code == 503


# ---------------------------------------------------------------------------
# Cost lookup functions (unit-level, not via the Flask client)
# ---------------------------------------------------------------------------

class TestGetAppointmentCost:

    def test_returns_zero_when_no_appointment_id(self):
        cost, source = billing_backend_app.get_appointment_cost(None)
        assert cost == 0.0
        assert source == "no_appointment"

    @patch("requests.get")
    def test_returns_live_cost_when_available(self, mock_get):
        mock_get.return_value = fake_response({"id": 1, "cost": 200.0}, 200)

        cost, source = billing_backend_app.get_appointment_cost(1)

        assert cost == 200.0
        assert source == "live"

    @patch("requests.get")
    def test_falls_back_to_mock_when_no_cost_field_present(self, mock_get):
        # Simulates the real current state: Appointments' schema has no cost field
        mock_get.return_value = fake_response({"id": 1, "patient_id": 101}, 200)

        cost, source = billing_backend_app.get_appointment_cost(1)

        assert source == "mock"
        assert cost > 0

    @patch("requests.get")
    def test_falls_back_to_mock_on_non_200_status(self, mock_get):
        mock_get.return_value = fake_response({"error": "not found"}, 404)

        cost, source = billing_backend_app.get_appointment_cost(999999)

        assert source == "mock"

    @patch("requests.get")
    def test_falls_back_to_mock_when_service_unreachable(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError()

        cost, source = billing_backend_app.get_appointment_cost(1)

        assert source == "mock"

    @patch("requests.get")
    def test_falls_back_to_mock_on_timeout(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout()

        cost, source = billing_backend_app.get_appointment_cost(1)

        assert source == "mock"


class TestGetMedicationCost:

    def test_returns_zero_when_no_patient_id(self):
        cost, source = billing_backend_app.get_medication_cost(None)
        assert cost == 0.0
        assert source == "no_patient"

    @patch("requests.get")
    def test_sums_live_medication_costs(self, mock_get):
        mock_get.return_value = fake_response(
            [{"cost": 20.0}, {"cost": 15.5}], 200
        )

        cost, source = billing_backend_app.get_medication_cost(101)

        assert cost == 35.5
        assert source == "live"

    @patch("requests.get")
    def test_falls_back_to_mock_when_service_unreachable(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError()

        cost, source = billing_backend_app.get_medication_cost(101)

        assert source == "mock"


class TestGetBedCharges:

    def test_returns_zero_when_no_patient_id(self):
        charges, source = billing_backend_app.get_bed_charges(None)
        assert charges == 0.0
        assert source == "no_patient"

    @patch("requests.get")
    def test_sums_live_bed_charges(self, mock_get):
        mock_get.return_value = fake_response(
            [{"charges": 400.0}, {"charges": 200.0}], 200
        )

        charges, source = billing_backend_app.get_bed_charges(101)

        assert charges == 600.0
        assert source == "live"

    @patch("requests.get")
    def test_falls_back_to_mock_when_service_unreachable(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError()

        charges, source = billing_backend_app.get_bed_charges(101)

        assert source == "mock"


# ---------------------------------------------------------------------------
# POST /invoices/generate
# ---------------------------------------------------------------------------

class TestGenerateInvoice:

    def test_generate_invoice_with_no_body_returns_400(self, client):
        response = client.post("/invoices/generate", data="", content_type="application/json")
        assert response.status_code == 400

    def test_generate_invoice_missing_patient_id_returns_400(self, client):
        response = client.post("/invoices/generate", json={"appointment_id": 1})
        assert response.status_code == 400
        assert "error" in response.get_json()

    @patch("requests.post")
    @patch("requests.get")
    def test_generate_invoice_succeeds_with_all_mock_costs(self, mock_get, mock_post, client):
        # All three dependent services unreachable -> every cost falls back to mock
        mock_get.side_effect = requests.exceptions.ConnectionError()
        mock_post.return_value = fake_response({
            "message": "Invoice created successfully",
            "invoice_id": 13,
            "total_amount": 150.0,
            "insurance_covered_amount": 127.5,
            "patient_owed_amount": 22.5,
        }, 201)

        response = client.post("/invoices/generate", json={
            "patient_id": 777,
            "appointment_id": 999,
            "insurance_provider_id": 302,
        })

        assert response.status_code == 201
        data = response.get_json()
        assert data["invoice_id"] == 13
        assert data["cost_sources"]["appointment_cost"] == "mock"
        assert data["cost_sources"]["medication_cost"] == "mock"
        assert data["cost_sources"]["bed_charges"] == "mock"

    @patch("requests.post")
    @patch("requests.get")
    def test_generate_invoice_forwards_database_validation_error(self, mock_get, mock_post, client):
        mock_get.side_effect = requests.exceptions.ConnectionError()
        mock_post.return_value = fake_response({"error": "Insurance provider not found"}, 404)

        response = client.post("/invoices/generate", json={
            "patient_id": 778,
            "insurance_provider_id": 999999,
        })

        assert response.status_code == 404
        assert response.get_json() == {"error": "Insurance provider not found"}

    @patch("requests.post")
    @patch("requests.get")
    def test_generate_invoice_returns_503_when_database_unreachable(self, mock_get, mock_post, client):
        mock_get.side_effect = requests.exceptions.ConnectionError()
        mock_post.side_effect = requests.exceptions.ConnectionError()

        response = client.post("/invoices/generate", json={"patient_id": 779})

        assert response.status_code == 503
        assert "error" in response.get_json()

    @patch("requests.post")
    @patch("requests.get")
    def test_generate_invoice_uses_live_appointment_cost_when_available(self, mock_get, mock_post, client):
        mock_get.return_value = fake_response({"id": 1, "cost": 200.0}, 200)
        mock_post.return_value = fake_response({
            "message": "Invoice created successfully",
            "invoice_id": 14,
            "total_amount": 200.0,
            "insurance_covered_amount": 0.0,
            "patient_owed_amount": 200.0,
        }, 201)

        response = client.post("/invoices/generate", json={
            "patient_id": 780,
            "appointment_id": 1,
        })

        assert response.status_code == 201
        assert response.get_json()["cost_sources"]["appointment_cost"] == "live"

        # Confirm the live cost was actually forwarded to billing-database
        posted_payload = mock_post.call_args.kwargs["json"]
        assert posted_payload["appointment_cost"] == 200.0