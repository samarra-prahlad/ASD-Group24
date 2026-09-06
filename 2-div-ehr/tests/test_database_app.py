import os
import sys
import subprocess
import pytest

FEATURE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_DIR = os.path.join(FEATURE_ROOT, "database")
INIT_SCRIPT = os.path.join(DATABASE_DIR, "init_db.py")
TEST_DATA_DIR = os.path.join(FEATURE_ROOT, "tests", ".test_data")
DATABASE_NAME = os.path.join(TEST_DATA_DIR, "ehr.db")
os.environ["DATABASE_PATH"] = DATABASE_NAME

sys.path.insert(0, DATABASE_DIR)
import app as ehr_database_app 

KNOWN_SEEDED_PATIENT_ID = 3  # John Smith


@pytest.fixture(scope="module", autouse=True)
def fresh_database():
    os.makedirs(TEST_DATA_DIR, exist_ok=True)

    if os.path.exists(DATABASE_NAME):
        os.remove(DATABASE_NAME)

    env = os.environ.copy()
    env["DATABASE_PATH"] = DATABASE_NAME

    result = subprocess.run(
        [sys.executable, INIT_SCRIPT],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f"init_db.py failed: {result.stderr}"

    yield


@pytest.fixture
def client():
    ehr_database_app.app.config["TESTING"] = True
    with ehr_database_app.app.test_client() as test_client:
        yield test_client

class TestGetRecords:

    def test_get_records_for_seeded_patient_returns_records(self, client):
        response = client.get(f"/records/{KNOWN_SEEDED_PATIENT_ID}")
        assert response.status_code == 200
        records = response.get_json()
        assert len(records) > 0
        assert all(r["patient_id"] == KNOWN_SEEDED_PATIENT_ID for r in records)

    def test_get_records_for_unknown_patient_returns_empty_list(self, client):
        response = client.get("/records/999999")
        assert response.status_code == 200
        assert response.get_json() == []

    def test_records_include_all_expected_fields(self, client):
        response = client.get(f"/records/{KNOWN_SEEDED_PATIENT_ID}")
        record = response.get_json()[0]
        expected_fields = {
            "id", "patient_id", "visit_date", "diagnosis", "doctor_name",
            "treatment", "notes", "allergies", "created_at",
        }
        assert expected_fields.issubset(record.keys())

class TestRecordsWrite:

    def test_create_record_returns_201_with_id(self, client):
        response = client.post("/records", json={
            "patient_id": 6,
            "visit_date": "2026-08-20",
            "diagnosis": "Test Diagnosis",
            "doctor_name": "Dr. Test",
            "treatment": "Test Treatment",
            "notes": "Created by test suite",
            "allergies": "None",
        })
        assert response.status_code == 201
        assert "id" in response.get_json()

    def test_created_record_is_retrievable(self, client):
        create_resp = client.post("/records", json={
            "patient_id": 7,
            "visit_date": "2026-08-21",
            "diagnosis": "Retrievability Check",
            "doctor_name": "Dr. Test",
            "treatment": "N/A",
            "notes": "N/A",
            "allergies": "N/A",
        })
        new_id = create_resp.get_json()["id"]

        get_resp = client.get("/records/7")
        records = get_resp.get_json()
        assert any(r["id"] == new_id and r["diagnosis"] == "Retrievability Check" for r in records)

    def test_create_record_missing_patient_id_returns_400(self, client):
        response = client.post("/records", json={"diagnosis": "No patient attached"})
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_update_record_changes_fields(self, client):
        create_resp = client.post("/records", json={
            "patient_id": 8,
            "visit_date": "2026-08-22",
            "diagnosis": "Before Update",
            "doctor_name": "Dr. Test",
            "treatment": "N/A",
            "notes": "N/A",
            "allergies": "N/A",
        })
        record_id = create_resp.get_json()["id"]

        update_resp = client.put(f"/records/{record_id}", json={
            "visit_date": "2026-08-22",
            "diagnosis": "After Update",
            "doctor_name": "Dr. Test",
            "treatment": "N/A",
            "notes": "N/A",
            "allergies": "N/A",
        })
        assert update_resp.status_code == 200

        records = client.get("/records/8").get_json()
        updated = next(r for r in records if r["id"] == record_id)
        assert updated["diagnosis"] == "After Update"

    def test_delete_record_removes_it(self, client):
        create_resp = client.post("/records", json={
            "patient_id": 9,
            "visit_date": "2026-08-23",
            "diagnosis": "To Be Deleted",
            "doctor_name": "Dr. Test",
            "treatment": "N/A",
            "notes": "N/A",
            "allergies": "N/A",
        })
        record_id = create_resp.get_json()["id"]

        delete_resp = client.delete(f"/records/{record_id}")
        assert delete_resp.status_code == 200

        records = client.get("/records/9").get_json()
        assert not any(r["id"] == record_id for r in records)

class TestChangeRequests:

    def test_create_change_request_returns_201(self, client):
        response = client.post("/change_requests", json={
            "patient_id": 5,
            "request_type": "Update Allergies",
            "request_details": "Add shellfish allergy",
        })
        assert response.status_code == 201
        assert "id" in response.get_json()

    def test_create_change_request_missing_fields_returns_400(self, client):
        response = client.post("/change_requests", json={"request_details": "No type or patient"})
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_get_all_change_requests_includes_created_one(self, client):
        create_resp = client.post("/change_requests", json={
            "patient_id": 10,
            "request_type": "Update Notes",
            "request_details": "Please fix a typo",
        })
        new_id = create_resp.get_json()["id"]

        all_resp = client.get("/change_requests")
        assert any(r["id"] == new_id for r in all_resp.get_json())

    def test_get_change_requests_by_patient_returns_only_theirs(self, client):
        client.post("/change_requests", json={
            "patient_id": 5,
            "request_type": "Other",
            "request_details": "Patient 5's own request",
        })

        response = client.get("/change_requests/5")
        results = response.get_json()
        assert len(results) > 0
        assert all(r["patient_id"] == 5 for r in results)

    def test_new_change_request_defaults_to_pending(self, client):
        create_resp = client.post("/change_requests", json={
            "patient_id": 6,
            "request_type": "Other",
            "request_details": "Check default status",
        })
        new_id = create_resp.get_json()["id"]

        results = client.get("/change_requests/6").get_json()
        created = next(r for r in results if r["id"] == new_id)
        assert created["status"] == "pending"

    def test_update_change_request_status(self, client):
        create_resp = client.post("/change_requests", json={
            "patient_id": 6,
            "request_type": "Other",
            "request_details": "To be approved",
        })
        request_id = create_resp.get_json()["id"]

        update_resp = client.put(f"/change_requests/{request_id}", json={"status": "approved"})
        assert update_resp.status_code == 200

        results = client.get("/change_requests/6").get_json()
        updated = next(r for r in results if r["id"] == request_id)
        assert updated["status"] == "approved"

    def test_update_change_request_missing_status_returns_400(self, client):
        create_resp = client.post("/change_requests", json={
            "patient_id": 6,
            "request_type": "Other",
            "request_details": "Missing status on update",
        })
        request_id = create_resp.get_json()["id"]

        response = client.put(f"/change_requests/{request_id}", json={})
        assert response.status_code == 400
        assert "error" in response.get_json()