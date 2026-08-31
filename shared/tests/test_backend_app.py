import os
import importlib.util
from unittest.mock import patch, MagicMock
import pytest

os.environ["DATABASE_SERVICE_URL"] = "http://shared-database:6000"


@pytest.fixture
def client():
    spec = importlib.util.spec_from_file_location(
        "shared_backend_app",
        os.path.join(os.path.dirname(__file__), "..", "backend", "app.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SESSIONS.clear()
    with module.app.test_client() as test_client:
        yield test_client, module


def fake_response(json_data, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_data
    return r


class TestRegister:
    def test_register_forwards_to_database_and_returns_201(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response(
                {"patient_id": 1, "first_name": "New", "email_address": "new@example.com"},
                status=201,
            )
            response = test_client.post("/register", json={
                "first_name": "New", "last_name": "Patient", "address": "1 St",
                "email_address": "new@example.com", "password": "Pass123!",
                "phone_number": "0400000000", "emergency_contact_number": "0400000001",
            })
        assert response.status_code == 201
        assert "password" not in response.get_json()

    def test_register_missing_field_returns_400(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response({"error": "Missing required fields: password"}, status=400)
            response = test_client.post("/register", json={"first_name": "Incomplete"})
        assert response.status_code == 400

    def test_register_duplicate_email_returns_409(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response({"error": "Email address already registered"}, status=409)
            response = test_client.post("/register", json={
                "first_name": "Dupe", "last_name": "Patient", "address": "1 St",
                "email_address": "dupe@example.com", "password": "Pass123!",
                "phone_number": "0400000000", "emergency_contact_number": "0400000001",
            })
        assert response.status_code == 409

    def test_register_database_unreachable_returns_503(self, client):
        test_client, module = client
        import requests as req_mod
        with patch("requests.post") as mock_post:
            mock_post.side_effect = req_mod.exceptions.ConnectionError()
            response = test_client.post("/register", json={
                "first_name": "New", "last_name": "Patient", "address": "1 St",
                "email_address": "new@example.com", "password": "Pass123!",
                "phone_number": "0400000000", "emergency_contact_number": "0400000001",
            })
        assert response.status_code == 503


class TestLogin:
    def test_login_correct_credentials_returns_200_with_token(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response(
                {"patient_id": 5, "first_name": "Jane", "role": "patient"}, status=200
            )
            response = test_client.post("/login", json={
                "email_address": "jane@example.com", "password": "Correct1!"
            })
        assert response.status_code == 200
        data = response.get_json()
        assert "token" in data
        assert data["role"] == "patient"
        assert data["patient_id"] == 5

    def test_login_admin_email_returns_admin_role(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response(
                {"patient_id": 1, "first_name": "Admin", "role": "admin"}, status=200
            )
            response = test_client.post("/login", json={
                "email_address": "staff@admin.com", "password": "AdminPass1!"
            })
        assert response.get_json()["role"] == "admin"

    def test_login_wrong_credentials_returns_401(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response({"error": "Invalid credentials"}, status=401)
            response = test_client.post("/login", json={
                "email_address": "jane@example.com", "password": "Wrong1!"
            })
        assert response.status_code == 401

    def test_login_missing_fields_returns_400(self, client):
        test_client, module = client
        response = test_client.post("/login", json={"email_address": "jane@example.com"})
        assert response.status_code == 400

    def test_login_database_unreachable_returns_503(self, client):
        test_client, module = client
        import requests as req_mod
        with patch("requests.post") as mock_post:
            mock_post.side_effect = req_mod.exceptions.ConnectionError()
            response = test_client.post("/login", json={
                "email_address": "jane@example.com", "password": "Correct1!"
            })
        assert response.status_code == 503

    def test_successful_login_creates_session_entry(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response(
                {"patient_id": 5, "first_name": "Jane", "role": "patient"}, status=200
            )
            response = test_client.post("/login", json={
                "email_address": "jane@example.com", "password": "Correct1!"
            })
        token = response.get_json()["token"]
        assert token in module.SESSIONS
        assert module.SESSIONS[token]["patient_id"] == 5
        assert module.SESSIONS[token]["role"] == "patient"


class TestSessionVerify:
    def test_verify_valid_token_returns_200(self, client):
        test_client, module = client
        module.SESSIONS["abc123"] = {"patient_id": 7, "role": "patient", "first_name": "Sam"}
        response = test_client.post("/session/verify", json={"token": "abc123"})
        assert response.status_code == 200
        data = response.get_json()
        assert data["valid"] is True
        assert data["patient_id"] == 7
        assert data["role"] == "patient"

    def test_verify_invalid_token_returns_401(self, client):
        test_client, module = client
        response = test_client.post("/session/verify", json={"token": "does-not-exist"})
        assert response.status_code == 401
        assert response.get_json()["valid"] is False

    def test_verify_missing_token_returns_400(self, client):
        test_client, module = client
        response = test_client.post("/session/verify", json={})
        assert response.status_code == 400


class TestLogout:
    def test_logout_removes_session(self, client):
        test_client, module = client
        module.SESSIONS["xyz789"] = {"patient_id": 3, "role": "admin", "first_name": "Bob"}
        response = test_client.post("/logout", json={"token": "xyz789"})
        assert response.status_code == 200
        assert "xyz789" not in module.SESSIONS

    def test_logout_unknown_token_still_returns_200(self, client):
        test_client, module = client
        response = test_client.post("/logout", json={"token": "never-existed"})
        assert response.status_code == 200