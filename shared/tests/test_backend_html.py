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


class TestLoginPage:
    def test_get_login_page_returns_200(self, client):
        test_client, module = client
        response = test_client.get("/login")
        assert response.status_code == 200
        assert b"form" in response.data.lower()

    def test_login_html_correct_credentials_redirects_to_home(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response(
                {"patient_id": 5, "first_name": "Jane", "role": "patient"}, status=200
            )
            response = test_client.post("/login/html", data={
                "email_address": "jane@example.com", "password": "Correct1!"
            })
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/home")

    def test_login_html_sets_cookie_on_success(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response(
                {"patient_id": 5, "first_name": "Jane", "role": "patient"}, status=200
            )
            response = test_client.post("/login/html", data={
                "email_address": "jane@example.com", "password": "Correct1!"
            })
        set_cookie_header = response.headers.get("Set-Cookie", "")
        assert "session_token" in set_cookie_header

    def test_login_html_wrong_credentials_rerenders_with_error(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response({"error": "Invalid credentials"}, status=401)
            response = test_client.post("/login/html", data={
                "email_address": "jane@example.com", "password": "Wrong1!"
            })
        assert response.status_code == 401
        assert b"invalid" in response.data.lower() or b"incorrect" in response.data.lower()

    def test_login_html_missing_fields_rerenders_with_error(self, client):
        test_client, module = client
        response = test_client.post("/login/html", data={"email_address": "jane@example.com"})
        assert response.status_code == 400


class TestRegisterPage:
    def test_get_register_page_returns_200(self, client):
        test_client, module = client
        response = test_client.get("/register")
        assert response.status_code == 200
        assert b"form" in response.data.lower()

    def test_register_html_success_redirects_to_home(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response(
                {"patient_id": 9, "first_name": "New", "email_address": "new@example.com"},
                status=201,
            )
            response = test_client.post("/register/html", data={
                "first_name": "New", "last_name": "Patient", "address": "1 St",
                "email_address": "new@example.com", "password": "Pass123!",
                "phone_number": "0400000000", "emergency_contact_number": "0400000001",
            })
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/home")

    def test_register_html_sets_cookie_on_success(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response(
                {"patient_id": 9, "first_name": "New", "email_address": "new@example.com"},
                status=201,
            )
            response = test_client.post("/register/html", data={
                "first_name": "New", "last_name": "Patient", "address": "1 St",
                "email_address": "new@example.com", "password": "Pass123!",
                "phone_number": "0400000000", "emergency_contact_number": "0400000001",
            })
        assert "session_token" in response.headers.get("Set-Cookie", "")

    def test_register_html_missing_field_rerenders_with_error(self, client):
        test_client, module = client
        response = test_client.post("/register/html", data={"first_name": "Incomplete"})
        assert response.status_code == 400

    def test_register_html_duplicate_email_rerenders_with_error(self, client):
        test_client, module = client
        with patch("requests.post") as mock_post:
            mock_post.return_value = fake_response({"error": "Email address already registered"}, status=409)
            response = test_client.post("/register/html", data={
                "first_name": "Dupe", "last_name": "Patient", "address": "1 St",
                "email_address": "dupe@example.com", "password": "Pass123!",
                "phone_number": "0400000000", "emergency_contact_number": "0400000001",
            })
        assert response.status_code == 409


class TestHomePage:
    def test_home_without_cookie_redirects_to_login(self, client):
        test_client, module = client
        response = test_client.get("/home")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_home_with_invalid_cookie_redirects_to_login(self, client):
        test_client, module = client
        test_client.set_cookie("session_token", "does-not-exist", domain="localhost")
        response = test_client.get("/home")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")

    def test_home_with_valid_patient_cookie_renders_patient_view(self, client):
        test_client, module = client
        module.SESSIONS["valid-patient-token"] = {"patient_id": 1, "role": "patient", "first_name": "Jane"}
        test_client.set_cookie("session_token", "valid-patient-token", domain="localhost")
        response = test_client.get("/home")
        assert response.status_code == 200

    def test_home_with_valid_admin_cookie_renders_admin_view(self, client):
        test_client, module = client
        module.SESSIONS["valid-admin-token"] = {"patient_id": 2, "role": "admin", "first_name": "Grace"}
        test_client.set_cookie("session_token", "valid-admin-token", domain="localhost")
        response = test_client.get("/home")
        assert response.status_code == 200

    def test_home_admin_view_includes_token_in_feature_links(self, client):
        test_client, module = client
        module.SESSIONS["valid-admin-token"] = {"patient_id": 2, "role": "admin", "first_name": "Grace"}
        test_client.set_cookie("session_token", "valid-admin-token", domain="localhost")
        response = test_client.get("/home")
        assert b"token=valid-admin-token" in response.data

    def test_home_patient_view_includes_token_in_feature_links(self, client):
        test_client, module = client
        module.SESSIONS["valid-patient-token"] = {"patient_id": 1, "role": "patient", "first_name": "Jane"}
        test_client.set_cookie("session_token", "valid-patient-token", domain="localhost")
        response = test_client.get("/home")
        assert b"token=valid-patient-token" in response.data


class TestLogoutPage:
    def test_logout_html_clears_session_and_redirects(self, client):
        test_client, module = client
        module.SESSIONS["some-token"] = {"patient_id": 3, "role": "admin", "first_name": "Bob"}
        test_client.set_cookie("session_token", "some-token", domain="localhost")
        response = test_client.get("/logout/html")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/login")
        assert "some-token" not in module.SESSIONS