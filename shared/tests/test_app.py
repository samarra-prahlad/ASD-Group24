import os
import sqlite3
import importlib.util
import pytest
from werkzeug.security import generate_password_hash

TEST_DB_DIR = os.path.join(os.path.dirname(__file__), ".test_data_app")
TEST_DB_PATH = os.path.join(TEST_DB_DIR, "shared.db")


@pytest.fixture
def client():
    os.environ["DB_DATA_DIR"] = TEST_DB_DIR
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    spec = importlib.util.spec_from_file_location(
        "shared_database_app",
        os.path.join(os.path.dirname(__file__), "..", "database", "app.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module.init_db()

    with module.app.test_client() as test_client:
        yield test_client, module

    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


def seed_one_patient(module, email="jane.doe@example.com", password="TestPass123!"):
    conn = sqlite3.connect(TEST_DB_PATH)
    conn.execute(
        """
        INSERT INTO patients
        (first_name, last_name, address, email_address, password, phone_number, emergency_contact_number)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("Jane", "Doe", "1 Test St", email, generate_password_hash(password), "0400000000", "0400000001"),
    )
    conn.commit()
    patient_id = conn.execute("SELECT patient_id FROM patients WHERE email_address = ?", (email,)).fetchone()[0]
    conn.close()
    return patient_id


class TestGetPatients:
    def test_get_all_patients_returns_200(self, client):
        test_client, module = client
        response = test_client.get("/patients")
        assert response.status_code == 200

    def test_get_all_patients_excludes_password(self, client):
        test_client, module = client
        seed_one_patient(module)
        response = test_client.get("/patients")
        data = response.get_json()
        assert len(data) >= 1
        for patient in data:
            assert "password" not in patient

    def test_get_single_patient_by_id(self, client):
        test_client, module = client
        patient_id = seed_one_patient(module)
        response = test_client.get(f"/patients/{patient_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["email_address"] == "jane.doe@example.com"
        assert "password" not in data

    def test_get_nonexistent_patient_returns_404(self, client):
        test_client, module = client
        response = test_client.get("/patients/99999")
        assert response.status_code == 404


class TestCreatePatient:
    def test_create_patient_returns_201(self, client):
        test_client, module = client
        response = test_client.post("/patients", json={
            "first_name": "New",
            "last_name": "Patient",
            "address": "5 New St",
            "email_address": "new.patient@example.com",
            "password": "NewPass123!",
            "phone_number": "0400000010",
            "emergency_contact_number": "0400000011",
        })
        assert response.status_code == 201

    def test_create_patient_hashes_password(self, client):
        test_client, module = client
        test_client.post("/patients", json={
            "first_name": "New",
            "last_name": "Patient",
            "address": "5 New St",
            "email_address": "hash.check@example.com",
            "password": "PlainPassword1!",
            "phone_number": "0400000010",
            "emergency_contact_number": "0400000011",
        })
        conn = sqlite3.connect(TEST_DB_PATH)
        stored = conn.execute(
            "SELECT password FROM patients WHERE email_address = ?", ("hash.check@example.com",)
        ).fetchone()[0]
        conn.close()
        assert stored != "PlainPassword1!"
        assert stored.startswith("scrypt:") or stored.startswith("pbkdf2:")

    def test_create_patient_missing_field_returns_400(self, client):
        test_client, module = client
        response = test_client.post("/patients", json={
            "first_name": "Incomplete",
        })
        assert response.status_code == 400

    def test_create_patient_duplicate_email_returns_409(self, client):
        test_client, module = client
        seed_one_patient(module, email="dupe@example.com")
        response = test_client.post("/patients", json={
            "first_name": "Dupe",
            "last_name": "Patient",
            "address": "9 Dupe St",
            "email_address": "dupe@example.com",
            "password": "SomePass123!",
            "phone_number": "0400000099",
            "emergency_contact_number": "0400000098",
        })
        assert response.status_code == 409


class TestUpdatePatient:
    def test_update_patient_returns_200(self, client):
        test_client, module = client
        patient_id = seed_one_patient(module)
        response = test_client.put(f"/patients/{patient_id}", json={"address": "New Address"})
        assert response.status_code == 200

    def test_update_patient_persists_change(self, client):
        test_client, module = client
        patient_id = seed_one_patient(module)
        test_client.put(f"/patients/{patient_id}", json={"address": "Updated Address"})
        response = test_client.get(f"/patients/{patient_id}")
        assert response.get_json()["address"] == "Updated Address"

    def test_update_nonexistent_patient_returns_404(self, client):
        test_client, module = client
        response = test_client.put("/patients/99999", json={"address": "Nowhere"})
        assert response.status_code == 404


class TestDeletePatient:
    def test_delete_patient_returns_200(self, client):
        test_client, module = client
        patient_id = seed_one_patient(module)
        response = test_client.delete(f"/patients/{patient_id}")
        assert response.status_code == 200

    def test_deleted_patient_no_longer_retrievable(self, client):
        test_client, module = client
        patient_id = seed_one_patient(module)
        test_client.delete(f"/patients/{patient_id}")
        response = test_client.get(f"/patients/{patient_id}")
        assert response.status_code == 404

    def test_delete_nonexistent_patient_returns_404(self, client):
        test_client, module = client
        response = test_client.delete("/patients/99999")
        assert response.status_code == 404


class TestVerifyCredentials:
    def test_verify_correct_credentials_returns_200(self, client):
        test_client, module = client
        seed_one_patient(module, email="verify.me@example.com", password="CorrectPass1!")
        response = test_client.post("/patients/verify", json={
            "email_address": "verify.me@example.com",
            "password": "CorrectPass1!",
        })
        assert response.status_code == 200

    def test_verify_correct_credentials_returns_role_and_id_not_password(self, client):
        test_client, module = client
        patient_id = seed_one_patient(module, email="verify.role@example.com", password="CorrectPass1!")
        response = test_client.post("/patients/verify", json={
            "email_address": "verify.role@example.com",
            "password": "CorrectPass1!",
        })
        data = response.get_json()
        assert data["patient_id"] == patient_id
        assert "password" not in data

    def test_verify_admin_email_returns_admin_role(self, client):
        test_client, module = client
        seed_one_patient(module, email="staff@admin.com", password="AdminPass1!")
        response = test_client.post("/patients/verify", json={
            "email_address": "staff@admin.com",
            "password": "AdminPass1!",
        })
        assert response.get_json()["role"] == "admin"

    def test_verify_non_admin_email_returns_patient_role(self, client):
        test_client, module = client
        seed_one_patient(module, email="regular@example.com", password="PatientPass1!")
        response = test_client.post("/patients/verify", json={
            "email_address": "regular@example.com",
            "password": "PatientPass1!",
        })
        assert response.get_json()["role"] == "patient"

    def test_verify_wrong_password_returns_401(self, client):
        test_client, module = client
        seed_one_patient(module, email="wrongpass@example.com", password="RightPass1!")
        response = test_client.post("/patients/verify", json={
            "email_address": "wrongpass@example.com",
            "password": "WrongPass1!",
        })
        assert response.status_code == 401

    def test_verify_nonexistent_email_returns_401(self, client):
        test_client, module = client
        response = test_client.post("/patients/verify", json={
            "email_address": "doesnotexist@example.com",
            "password": "Whatever1!",
        })
        assert response.status_code == 401