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