import os
import importlib.util
from unittest.mock import patch, MagicMock
import pytest

os.environ["SHARED_ACCESS_API_URL"] = "http://shared-backend:5000"


@pytest.fixture
def client():
    spec = importlib.util.spec_from_file_location(
        "billing_backend_app",
        os.path.join(os.path.dirname(__file__), "..", "backend", "app.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with module.app.test_client() as test_client:
        yield test_client, module


def fake_response(json_data, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_data
    return r


class TestViewRoute:
    def test_view_without_token_redirects_to_shared_login(self, client):
        test_client, module = client
        response = test_client.get("/view")
        assert response.status_code == 302
        assert "localhost:5000/login" in response.headers["Location"]

    def test_view_with_invalid_token_redirects_to_shared_login(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response({"valid": False}, status=401)
            response = test_client.get("/view?token=bad-token")
        assert response.status_code == 302
        assert "localhost:5000/login" in response.headers["Location"]

    def test_view_with_valid_admin_token_shows_admin_view(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response(
                {"valid": True, "patient_id": 2, "role": "admin", "first_name": "Grace"}, status=200
            )
            response = test_client.get("/view?token=admin-token")
        assert response.status_code == 200
        assert b"Admin" in response.data

    def test_view_with_valid_patient_token_shows_patient_view(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response(
                {"valid": True, "patient_id": 5, "role": "patient", "first_name": "John"}, status=200
            )
            response = test_client.get("/view?token=patient-token")
        assert response.status_code == 200
        assert b"My Invoices" in response.data

    def test_view_shared_service_unreachable_redirects_to_login(self, client):
        test_client, module = client
        import requests as req_mod
        with patch("requests.post") as mock_post:
            mock_post.side_effect = req_mod.exceptions.ConnectionError()
            response = test_client.get("/view?token=some-token")
        assert response.status_code == 302
        assert "localhost:5000/login" in response.headers["Location"]


class TestGenerateInvoicePermissions:
    def test_generate_without_token_returns_401(self, client):
        test_client, module = client
        response = test_client.post("/invoices/generate", json={"patient_id": 1})
        assert response.status_code == 401

    def test_generate_with_patient_token_returns_403(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response(
                {"valid": True, "patient_id": 5, "role": "patient", "first_name": "John"}, status=200
            )
            response = test_client.post(
                "/invoices/generate?token=patient-token", json={"patient_id": 5}
            )
        assert response.status_code == 403

    def test_generate_with_invalid_token_returns_401(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response({"valid": False}, status=401)
            response = test_client.post(
                "/invoices/generate?token=bad-token", json={"patient_id": 5}
            )
        assert response.status_code == 401

    def test_generate_with_admin_token_succeeds(self, client):
        test_client, module = client

        def side_effect(url, **kwargs):
            if "session/verify" in url:
                return fake_response(
                    {"valid": True, "patient_id": 2, "role": "admin", "first_name": "Grace"}, status=200
                )
            return fake_response(
                {"id": 10, "patient_id": 5, "total_amount": 150.0}, status=201
            )

        with patch("requests.post", side_effect=side_effect):
            with patch("requests.get") as mock_get:
                mock_get.side_effect = __import__("requests").exceptions.ConnectionError()
                response = test_client.post(
                    "/invoices/generate?token=admin-token", json={"patient_id": 5}
                )
        assert response.status_code == 201


class TestInvoiceReadPermissions:
    def test_get_all_invoices_without_token_returns_401(self, client):
        test_client, module = client
        response = test_client.get("/invoices")
        assert response.status_code == 401

    def test_get_all_invoices_with_patient_token_returns_403(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response(
                {"valid": True, "patient_id": 3, "role": "patient", "first_name": "John"}, status=200
            )
            response = test_client.get("/invoices?token=patient-token")
        assert response.status_code == 403

    def test_get_all_invoices_with_admin_token_returns_200(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response(
                {"valid": True, "patient_id": 2, "role": "admin", "first_name": "Grace"}, status=200
            )
            with patch("requests.get") as mock_get:
                mock_get.return_value = fake_response([{"id": 1, "patient_id": 3}], status=200)
                response = test_client.get("/invoices?token=admin-token")
        assert response.status_code == 200

    def test_get_single_invoice_patient_owns_it_returns_200(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response(
                {"valid": True, "patient_id": 3, "role": "patient", "first_name": "John"}, status=200
            )
            with patch("requests.get") as mock_get:
                mock_get.return_value = fake_response({"id": 5, "patient_id": 3}, status=200)
                response = test_client.get("/invoices/5?token=patient-token")
        assert response.status_code == 200

    def test_get_single_invoice_patient_does_not_own_it_returns_403(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response(
                {"valid": True, "patient_id": 3, "role": "patient", "first_name": "John"}, status=200
            )
            with patch("requests.get") as mock_get:
                mock_get.return_value = fake_response({"id": 5, "patient_id": 999}, status=200)
                response = test_client.get("/invoices/5?token=patient-token")
        assert response.status_code == 403

    def test_get_single_invoice_admin_can_view_any(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response(
                {"valid": True, "patient_id": 2, "role": "admin", "first_name": "Grace"}, status=200
            )
            with patch("requests.get") as mock_get:
                mock_get.return_value = fake_response({"id": 5, "patient_id": 999}, status=200)
                response = test_client.get("/invoices/5?token=admin-token")
        assert response.status_code == 200

    def test_get_single_invoice_without_token_returns_401(self, client):
        test_client, module = client
        response = test_client.get("/invoices/5")
        assert response.status_code == 401

    def test_get_invoices_by_patient_matching_own_id_returns_200(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response(
                {"valid": True, "patient_id": 3, "role": "patient", "first_name": "John"}, status=200
            )
            with patch("requests.get") as mock_get:
                mock_get.return_value = fake_response([{"id": 1, "patient_id": 3}], status=200)
                response = test_client.get("/invoices/patient/3?token=patient-token")
        assert response.status_code == 200

    def test_get_invoices_by_patient_different_id_returns_403(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response(
                {"valid": True, "patient_id": 3, "role": "patient", "first_name": "John"}, status=200
            )
            response = test_client.get("/invoices/patient/999?token=patient-token")
        assert response.status_code == 403

    def test_get_invoices_by_patient_admin_can_view_any(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response(
                {"valid": True, "patient_id": 2, "role": "admin", "first_name": "Grace"}, status=200
            )
            with patch("requests.get") as mock_get:
                mock_get.return_value = fake_response([{"id": 1, "patient_id": 999}], status=200)
                response = test_client.get("/invoices/patient/999?token=admin-token")
        assert response.status_code == 200

    def test_invoices_html_patient_ignores_supplied_patient_id(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response(
                {"valid": True, "patient_id": 3, "role": "patient", "first_name": "John"}, status=200
            )
            with patch("requests.get") as mock_get:
                mock_get.return_value = fake_response([{"id": 1, "patient_id": 3, "insurance_provider_name": "Bupa",
                                                          "total_amount": 100.0, "insurance_covered_amount": 50.0,
                                                          "patient_owed_amount": 50.0, "status": "pending"}], status=200)
                response = test_client.get("/invoices/html?token=patient-token&patient_id=999")
        mock_get.assert_called_with(
            "http://billing-database:6004/invoices/patient/3", timeout=module.REQUEST_TIMEOUT
        )
        assert response.status_code == 200

    def test_invoices_html_admin_can_filter_by_any_patient_id(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response(
                {"valid": True, "patient_id": 2, "role": "admin", "first_name": "Grace"}, status=200
            )
            with patch("requests.get") as mock_get:
                mock_get.return_value = fake_response([], status=200)
                response = test_client.get("/invoices/html?token=admin-token&patient_id=999")
        mock_get.assert_called_with(
            "http://billing-database:6004/invoices/patient/999", timeout=module.REQUEST_TIMEOUT
        )
        assert response.status_code == 200

    def test_invoices_html_without_token_returns_401(self, client):
        test_client, module = client
        response = test_client.get("/invoices/html")
        assert response.status_code == 401

class TestInvoiceHtmlFilteringAndSorting:
    def _admin_session(self, mock_post):
        mock_post.return_value = fake_response(
            {"valid": True, "patient_id": 2, "role": "admin", "first_name": "Grace"}, status=200
        )

    def test_filter_by_status(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            self._admin_session(mock_post)
            with patch("requests.get") as mock_get:
                mock_get.return_value = fake_response([
                    {"id": 1, "patient_id": 3, "insurance_provider_name": "Bupa", "total_amount": 100.0,
                     "insurance_covered_amount": 50.0, "patient_owed_amount": 50.0, "status": "paid"},
                    {"id": 2, "patient_id": 4, "insurance_provider_name": "NIB", "total_amount": 200.0,
                     "insurance_covered_amount": 0.0, "patient_owed_amount": 200.0, "status": "pending"},
                ], status=200)
                response = test_client.get("/invoices/html?token=admin-token&status=pending")
        assert b"NIB" in response.data
        assert b"Bupa" not in response.data

    def test_filter_by_insurance_provider(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            self._admin_session(mock_post)
            with patch("requests.get") as mock_get:
                mock_get.return_value = fake_response([
                    {"id": 1, "patient_id": 3, "insurance_provider_name": "Bupa", "total_amount": 100.0,
                     "insurance_covered_amount": 50.0, "patient_owed_amount": 50.0, "status": "paid"},
                    {"id": 2, "patient_id": 4, "insurance_provider_name": "NIB", "total_amount": 200.0,
                     "insurance_covered_amount": 0.0, "patient_owed_amount": 200.0, "status": "pending"},
                ], status=200)
                response = test_client.get("/invoices/html?token=admin-token&insurance=NIB")
        assert b"NIB" in response.data
        assert b"Bupa" not in response.data

    def test_sort_by_total_amount_ascending(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            self._admin_session(mock_post)
            with patch("requests.get") as mock_get:
                mock_get.return_value = fake_response([
                    {"id": 1, "patient_id": 3, "insurance_provider_name": "Bupa", "total_amount": 300.0,
                     "insurance_covered_amount": 0.0, "patient_owed_amount": 300.0, "status": "pending"},
                    {"id": 2, "patient_id": 4, "insurance_provider_name": "NIB", "total_amount": 100.0,
                     "insurance_covered_amount": 0.0, "patient_owed_amount": 100.0, "status": "pending"},
                ], status=200)
                response = test_client.get("/invoices/html?token=admin-token&sort_by=total_amount&sort_dir=asc")
        body = response.data.decode()
        assert body.index("100.00") < body.index("300.00")

    def test_sort_by_total_amount_descending(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            self._admin_session(mock_post)
            with patch("requests.get") as mock_get:
                mock_get.return_value = fake_response([
                    {"id": 1, "patient_id": 3, "insurance_provider_name": "Bupa", "total_amount": 100.0,
                     "insurance_covered_amount": 0.0, "patient_owed_amount": 100.0, "status": "pending"},
                    {"id": 2, "patient_id": 4, "insurance_provider_name": "NIB", "total_amount": 300.0,
                     "insurance_covered_amount": 0.0, "patient_owed_amount": 300.0, "status": "pending"},
                ], status=200)
                response = test_client.get("/invoices/html?token=admin-token&sort_by=total_amount&sort_dir=desc")
        body = response.data.decode()
        assert body.index("300.00") < body.index("100.00")

    def test_sort_by_status(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            self._admin_session(mock_post)
            with patch("requests.get") as mock_get:
                mock_get.return_value = fake_response([
                    {"id": 1, "patient_id": 3, "insurance_provider_name": "Bupa", "total_amount": 100.0,
                     "insurance_covered_amount": 0.0, "patient_owed_amount": 100.0, "status": "pending"},
                    {"id": 2, "patient_id": 4, "insurance_provider_name": "NIB", "total_amount": 200.0,
                     "insurance_covered_amount": 0.0, "patient_owed_amount": 200.0, "status": "paid"},
                ], status=200)
                response = test_client.get("/invoices/html?token=admin-token&sort_by=status&sort_dir=asc")
        body = response.data.decode()
        assert body.index(">paid<") < body.index(">pending<")

    def test_patient_cannot_use_status_filter_to_see_others(self, client):
        # Patients are always scoped to their own patient_id regardless of any other filter params
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response(
                {"valid": True, "patient_id": 3, "role": "patient", "first_name": "John"}, status=200
            )
            with patch("requests.get") as mock_get:
                mock_get.return_value = fake_response([
                    {"id": 1, "patient_id": 3, "insurance_provider_name": "Bupa", "total_amount": 100.0,
                     "insurance_covered_amount": 0.0, "patient_owed_amount": 100.0, "status": "pending"}
                ], status=200)
                response = test_client.get("/invoices/html?token=patient-token&status=paid")
        mock_get.assert_called_with(
            "http://billing-database:6004/invoices/patient/3", timeout=module.REQUEST_TIMEOUT
        )