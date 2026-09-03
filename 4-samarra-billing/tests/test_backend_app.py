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

    @patch.object(billing_backend_app, "verify_session")
    @patch("requests.get")
    def test_get_invoices_proxies_database_response(self, mock_get, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)
        mock_get.return_value = fake_response([{"id": 1}, {"id": 2}], 200)

        response = client.get("/invoices?token=fake-token")

        assert response.status_code == 200
        assert response.get_json() == [{"id": 1}, {"id": 2}]

    @patch.object(billing_backend_app, "verify_session")
    @patch("requests.get")
    def test_get_invoices_passes_through_upstream_error_status(self, mock_get, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)
        mock_get.return_value = fake_response({"error": "Invoice not found"}, 404)

        response = client.get("/invoices/999999?token=fake-token")

        assert response.status_code == 404
        assert response.get_json() == {"error": "Invoice not found"}

    @patch.object(billing_backend_app, "verify_session")
    @patch("requests.get")
    def test_get_invoices_returns_503_when_database_unreachable(self, mock_get, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)
        mock_get.side_effect = requests.exceptions.ConnectionError()

        response = client.get("/invoices?token=fake-token")

        assert response.status_code == 503
        assert "error" in response.get_json()

    @patch.object(billing_backend_app, "verify_session")
    @patch("requests.get")
    def test_get_single_invoice_proxies_correctly(self, mock_get, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)
        mock_get.return_value = fake_response({"id": 3, "patient_id": 101}, 200)

        response = client.get("/invoices/3?token=fake-token")

        assert response.status_code == 200
        assert response.get_json()["patient_id"] == 101

    @patch.object(billing_backend_app, "verify_session")
    @patch("requests.get")
    def test_get_invoices_by_patient_proxies_correctly(self, mock_get, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)
        mock_get.return_value = fake_response([{"id": 1, "patient_id": 101}], 200)

        response = client.get("/invoices/patient/101?token=fake-token")

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

    @patch.object(billing_backend_app, "verify_session")
    def test_generate_invoice_with_no_body_returns_400(self, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)

        response = client.post("/invoices/generate?token=fake-token", data="", content_type="application/json")
        assert response.status_code == 400

    @patch.object(billing_backend_app, "verify_session")
    def test_generate_invoice_missing_patient_id_returns_400(self, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)

        response = client.post("/invoices/generate?token=fake-token", json={"appointment_id": 1})
        assert response.status_code == 400
        assert "error" in response.get_json()

    @patch.object(billing_backend_app, "verify_session")
    @patch("requests.post")
    @patch("requests.get")
    def test_generate_invoice_succeeds_with_all_mock_costs(self, mock_get, mock_post, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)
        # All three dependent services unreachable -> every cost falls back to mock
        mock_get.side_effect = requests.exceptions.ConnectionError()
        mock_post.return_value = fake_response({
            "message": "Invoice created successfully",
            "invoice_id": 13,
            "total_amount": 150.0,
            "insurance_covered_amount": 127.5,
            "patient_owed_amount": 22.5,
        }, 201)

        response = client.post("/invoices/generate?token=fake-token", json={
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

    @patch.object(billing_backend_app, "verify_session")
    @patch("requests.post")
    @patch("requests.get")
    def test_generate_invoice_forwards_database_validation_error(self, mock_get, mock_post, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)
        mock_get.side_effect = requests.exceptions.ConnectionError()
        mock_post.return_value = fake_response({"error": "Insurance provider not found"}, 404)

        response = client.post("/invoices/generate?token=fake-token", json={
            "patient_id": 778,
            "insurance_provider_id": 999999,
        })

        assert response.status_code == 404
        assert response.get_json() == {"error": "Insurance provider not found"}

    @patch.object(billing_backend_app, "verify_session")
    @patch("requests.post")
    @patch("requests.get")
    def test_generate_invoice_returns_503_when_database_unreachable(self, mock_get, mock_post, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)
        mock_get.side_effect = requests.exceptions.ConnectionError()
        mock_post.side_effect = requests.exceptions.ConnectionError()

        response = client.post("/invoices/generate?token=fake-token", json={"patient_id": 779})

        assert response.status_code == 503
        assert "error" in response.get_json()

    @patch.object(billing_backend_app, "verify_session")
    @patch("requests.post")
    @patch("requests.get")
    def test_generate_invoice_uses_live_appointment_cost_when_available(self, mock_get, mock_post, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)
        mock_get.return_value = fake_response({"id": 1, "cost": 200.0}, 200)
        mock_post.return_value = fake_response({
            "message": "Invoice created successfully",
            "invoice_id": 14,
            "total_amount": 200.0,
            "insurance_covered_amount": 0.0,
            "patient_owed_amount": 200.0,
        }, 201)

        response = client.post("/invoices/generate?token=fake-token", json={
            "patient_id": 780,
            "appointment_id": 1,
        })

        assert response.status_code == 201
        assert response.get_json()["cost_sources"]["appointment_cost"] == "live"

        # Confirm the live cost was actually forwarded to billing-database
        posted_payload = mock_post.call_args.kwargs["json"]
        assert posted_payload["appointment_cost"] == 200.0


# ---------------------------------------------------------------------------
# POST /invoices/create/html - admin-only HTMX form endpoint for manually
# creating an invoice with directly-entered cost values (not derived via
# appointment_id like /invoices/generate).
# ---------------------------------------------------------------------------

class TestCreateInvoiceHtml:

    def test_create_invoice_html_requires_token(self, client):
        response = client.post("/invoices/create/html", data={
            "patient_id": "3",
            "appointment_cost": "100",
            "medication_cost": "0",
            "bed_charges": "0",
        })

        assert response.status_code == 401

    @patch.object(billing_backend_app, "verify_session")
    def test_create_invoice_html_requires_admin(self, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "patient", "patient_id": 3}, None)

        response = client.post("/invoices/create/html?token=fake-token", data={
            "patient_id": "3",
            "appointment_cost": "100",
            "medication_cost": "0",
            "bed_charges": "0",
        })

        assert response.status_code == 403

    @patch.object(billing_backend_app, "verify_session")
    @patch("requests.post")
    def test_create_invoice_html_success(self, mock_post, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)
        mock_post.return_value = fake_response({
            "message": "Invoice created successfully",
            "invoice_id": 20,
            "total_amount": 250.0,
            "insurance_covered_amount": 0.0,
            "patient_owed_amount": 250.0,
        }, 201)

        response = client.post("/invoices/create/html?token=fake-token", data={
            "patient_id": "3",
            "insurance_provider_id": "",
            "appointment_cost": "150",
            "medication_cost": "50",
            "bed_charges": "50",
            "status": "pending",
        })

        assert response.status_code == 201
        assert b"created" in response.data.lower()

    @patch.object(billing_backend_app, "verify_session")
    @patch("requests.post")
    def test_create_invoice_html_invalid_provider(self, mock_post, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)
        mock_post.return_value = fake_response({"error": "Insurance provider not found"}, 404)

        response = client.post("/invoices/create/html?token=fake-token", data={
            "patient_id": "3",
            "insurance_provider_id": "999999",
            "appointment_cost": "150",
            "medication_cost": "0",
            "bed_charges": "0",
        })

        assert response.status_code == 404
        assert b"not found" in response.data.lower()

    @patch.object(billing_backend_app, "verify_session")
    @patch("requests.post")
    def test_create_invoice_html_database_unreachable(self, mock_post, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)
        mock_post.side_effect = requests.exceptions.ConnectionError()

        response = client.post("/invoices/create/html?token=fake-token", data={
            "patient_id": "3",
            "appointment_cost": "150",
            "medication_cost": "0",
            "bed_charges": "0",
        })

        assert response.status_code == 503

    @patch.object(billing_backend_app, "verify_session")
    def test_create_invoice_html_missing_patient_id(self, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)

        response = client.post("/invoices/create/html?token=fake-token", data={
            "appointment_cost": "150",
        })

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# PUT /invoices/<invoice_id>/html - admin-only HTMX form endpoint for editing
# an existing invoice's fields. Proxies to the database tier's existing
# PUT /invoices/<id>.
# ---------------------------------------------------------------------------

class TestUpdateInvoiceHtml:

    def test_update_invoice_html_requires_token(self, client):
        response = client.put("/invoices/1/html", data={"status": "paid"})

        assert response.status_code == 401

    @patch.object(billing_backend_app, "verify_session")
    def test_update_invoice_html_requires_admin(self, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "patient", "patient_id": 3}, None)

        response = client.put("/invoices/1/html?token=fake-token", data={"status": "paid"})

        assert response.status_code == 403

    @patch.object(billing_backend_app, "verify_session")
    @patch("requests.put")
    def test_update_invoice_html_success(self, mock_put, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)
        mock_put.return_value = fake_response({
            "message": "Invoice updated",
            "invoice_id": 1,
            "total_amount": 200.0,
            "insurance_covered_amount": 100.0,
            "patient_owed_amount": 100.0,
        }, 200)

        response = client.put("/invoices/1/html?token=fake-token", data={
            "status": "paid",
        })

        assert response.status_code == 200
        assert b"updated" in response.data.lower()

    @patch.object(billing_backend_app, "verify_session")
    @patch("requests.put")
    def test_update_invoice_html_invoice_not_found(self, mock_put, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)
        mock_put.return_value = fake_response({"error": "Invoice not found"}, 404)

        response = client.put("/invoices/999999/html?token=fake-token", data={
            "status": "paid",
        })

        assert response.status_code == 404
        assert b"not found" in response.data.lower()

    @patch.object(billing_backend_app, "verify_session")
    @patch("requests.put")
    def test_update_invoice_html_database_unreachable(self, mock_put, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)
        mock_put.side_effect = requests.exceptions.ConnectionError()

        response = client.put("/invoices/1/html?token=fake-token", data={
            "status": "paid",
        })

        assert response.status_code == 503


# ---------------------------------------------------------------------------
# GET /invoices/<invoice_id>/print - printable invoice page opened in a new
# tab after creating/editing an invoice. Admins can view any invoice;
# patients only their own (same rule as GET /invoices/<id>).
# ---------------------------------------------------------------------------

class TestPrintInvoice:

    def test_print_invoice_requires_token(self, client):
        response = client.get("/invoices/1/print")

        assert response.status_code == 401

    @patch.object(billing_backend_app, "verify_session")
    @patch("requests.get")
    def test_print_invoice_admin_can_view_any(self, mock_get, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)
        mock_get.return_value = fake_response({
            "id": 5,
            "patient_id": 101,
            "insurance_provider_name": "HCF",
            "appointment_cost": 150.0,
            "medication_cost": 0.0,
            "bed_charges": 400.0,
            "total_amount": 550.0,
            "insurance_covered_amount": 385.0,
            "patient_owed_amount": 165.0,
            "status": "partially_paid",
            "date": "2026-09-19",
        }, 200)

        response = client.get("/invoices/5/print?token=fake-token")

        assert response.status_code == 200
        assert b"Invoice #5" in response.data
        assert b"165.00" in response.data

    @patch.object(billing_backend_app, "verify_session")
    @patch("requests.get")
    def test_print_invoice_patient_cannot_view_others(self, mock_get, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "patient", "patient_id": 3}, None)
        mock_get.return_value = fake_response({"id": 5, "patient_id": 101}, 200)

        response = client.get("/invoices/5/print?token=fake-token")

        assert response.status_code == 403

    @patch.object(billing_backend_app, "verify_session")
    @patch("requests.get")
    def test_print_invoice_not_found(self, mock_get, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)
        mock_get.return_value = fake_response({"error": "Invoice not found"}, 404)

        response = client.get("/invoices/999999/print?token=fake-token")

        assert response.status_code == 404

    @patch.object(billing_backend_app, "verify_session")
    @patch("requests.get")
    def test_print_invoice_database_unreachable(self, mock_get, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)
        mock_get.side_effect = requests.exceptions.ConnectionError()

        response = client.get("/invoices/5/print?token=fake-token")

        assert response.status_code == 503


# ---------------------------------------------------------------------------
# filter_and_sort_invoices - unit-level tests for the search/filter/sort
# logic used by GET /invoices/html. Filtering is done in Python since the
# database tier doesn't support these query params directly.
# ---------------------------------------------------------------------------

SAMPLE_INVOICES = [
    {
        "id": 1, "patient_id": 101, "insurance_provider_id": 301, "insurance_provider_name": "Medibank",
        "appointment_cost": 150.0, "medication_cost": 45.0, "bed_charges": 0.0,
        "total_amount": 195.0, "insurance_covered_amount": 117.0, "patient_owed_amount": 78.0,
        "status": "pending",
    },
    {
        "id": 2, "patient_id": 102, "insurance_provider_id": 303, "insurance_provider_name": "Bupa",
        "appointment_cost": 120.0, "medication_cost": 0.0, "bed_charges": 0.0,
        "total_amount": 120.0, "insurance_covered_amount": 78.0, "patient_owed_amount": 42.0,
        "status": "paid",
    },
    {
        "id": 4, "patient_id": 102, "insurance_provider_id": None, "insurance_provider_name": None,
        "appointment_cost": 180.0, "medication_cost": 30.0, "bed_charges": 0.0,
        "total_amount": 210.0, "insurance_covered_amount": 0.0, "patient_owed_amount": 210.0,
        "status": "pending",
    },
]


class TestFilterAndSortInvoices:

    def test_no_filters_returns_all_unchanged(self):
        result = billing_backend_app.filter_and_sort_invoices(SAMPLE_INVOICES)
        assert len(result) == 3

    def test_filters_by_invoice_id(self):
        result = billing_backend_app.filter_and_sort_invoices(SAMPLE_INVOICES, invoice_id="2")
        assert len(result) == 1
        assert result[0]["id"] == 2

    def test_filters_by_status(self):
        result = billing_backend_app.filter_and_sort_invoices(SAMPLE_INVOICES, status="pending")
        assert len(result) == 2
        assert all(inv["status"] == "pending" for inv in result)

    def test_filters_by_status_case_insensitive(self):
        result = billing_backend_app.filter_and_sort_invoices(SAMPLE_INVOICES, status="PAID")
        assert len(result) == 1
        assert result[0]["id"] == 2

    def test_filters_by_named_insurance_provider(self):
        result = billing_backend_app.filter_and_sort_invoices(SAMPLE_INVOICES, insurance="bupa")
        assert len(result) == 1
        assert result[0]["id"] == 2

    def test_filters_by_self_pay(self):
        result = billing_backend_app.filter_and_sort_invoices(SAMPLE_INVOICES, insurance="Self-pay")
        assert len(result) == 1
        assert result[0]["id"] == 4

    def test_combines_multiple_filters(self):
        result = billing_backend_app.filter_and_sort_invoices(
            SAMPLE_INVOICES, status="pending", insurance="Medibank"
        )
        assert len(result) == 1
        assert result[0]["id"] == 1

    def test_sorts_by_total_amount_ascending(self):
        result = billing_backend_app.filter_and_sort_invoices(
            SAMPLE_INVOICES, sort_by="total_amount", sort_dir="asc"
        )
        assert [inv["id"] for inv in result] == [2, 1, 4]

    def test_sorts_by_total_amount_descending(self):
        result = billing_backend_app.filter_and_sort_invoices(
            SAMPLE_INVOICES, sort_by="total_amount", sort_dir="desc"
        )
        assert [inv["id"] for inv in result] == [4, 1, 2]

    def test_sorts_by_patient_id(self):
        result = billing_backend_app.filter_and_sort_invoices(
            SAMPLE_INVOICES, sort_by="patient_id", sort_dir="asc"
        )
        assert [inv["id"] for inv in result] == [1, 2, 4]

    def test_no_matches_returns_empty_list(self):
        result = billing_backend_app.filter_and_sort_invoices(SAMPLE_INVOICES, invoice_id="999999")
        assert result == []


# ---------------------------------------------------------------------------
# GET /invoices/html - confirms the new query params (invoice_id, status,
# insurance, sort_by, sort_dir) actually flow through to the rendered table.
# ---------------------------------------------------------------------------

class TestInvoicesHtmlFiltering:

    @patch.object(billing_backend_app, "verify_session")
    @patch("requests.get")
    def test_filters_by_invoice_id_via_query_param(self, mock_get, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)
        mock_get.return_value = fake_response(SAMPLE_INVOICES, 200)

        response = client.get("/invoices/html?token=fake-token&invoice_id=2")

        assert response.status_code == 200
        assert b">2<" in response.data
        assert b">1<" not in response.data

    @patch.object(billing_backend_app, "verify_session")
    @patch("requests.get")
    def test_filters_by_status_via_query_param(self, mock_get, mock_verify_session, client):
        mock_verify_session.return_value = ({"role": "admin", "first_name": "Admin"}, None)
        mock_get.return_value = fake_response(SAMPLE_INVOICES, 200)

        response = client.get("/invoices/html?token=fake-token&status=paid")

        assert response.status_code == 200
        assert response.data.count(b"invoice-row-") == 1