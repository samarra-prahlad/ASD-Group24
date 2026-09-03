import os
import sqlite3
import subprocess
import sys
import pytest

FEATURE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INIT_SCRIPT = os.path.join(FEATURE_ROOT, "database", "init_db.py")
TEST_DATA_DIR = os.path.join(FEATURE_ROOT, "tests", ".test_data")
DATABASE_NAME = os.path.join(TEST_DATA_DIR, "ehr.db")

EXPECTED_SEEDED_PATIENT_IDS = {3, 4, 5, 6, 7, 8, 9, 10}

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
def conn():
    """Fresh connection per test, with row_factory for dict-like access."""
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    yield connection
    connection.close()

class TestDatabaseSetup:

    def test_database_file_exists(self):
        assert os.path.exists(DATABASE_NAME)

    def test_medical_records_table_exists(self, conn):
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='medical_records'"
        ).fetchone()
        assert row is not None

    def test_change_requests_table_exists(self, conn):
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='change_requests'"
        ).fetchone()
        assert row is not None

class TestSchema:

    def test_medical_records_columns(self, conn):
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(medical_records)")}
        expected = {
            "id", "patient_id", "visit_date", "diagnosis", "doctor_name",
            "treatment", "notes", "allergies", "created_at",
        }
        assert expected.issubset(columns)

    def test_change_requests_columns(self, conn):
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(change_requests)")}
        expected = {
            "id", "patient_id", "request_type", "request_details",
            "status", "created_at",
        }
        assert expected.issubset(columns)

class TestSeedData:

    def test_medical_records_are_seeded(self, conn):
        count = conn.execute("SELECT COUNT(*) AS c FROM medical_records").fetchone()["c"]
        assert count > 0

    def test_change_requests_start_empty(self, conn):
        count = conn.execute("SELECT COUNT(*) AS c FROM change_requests").fetchone()["c"]
        assert count == 0

    def test_seeded_patient_ids_match_real_shared_database_patients(self, conn):
        seeded_ids = {row["patient_id"] for row in conn.execute("SELECT DISTINCT patient_id FROM medical_records")}
        assert seeded_ids == EXPECTED_SEEDED_PATIENT_IDS

    def test_admin_patient_ids_are_not_seeded(self, conn):
        rows = conn.execute(
            "SELECT * FROM medical_records WHERE patient_id IN (1, 2)"
        ).fetchall()
        assert rows == []

    def test_medical_records_have_no_null_required_fields(self, conn):
        rows = conn.execute(
            "SELECT * FROM medical_records WHERE patient_id IS NULL"
        ).fetchall()
        assert rows == []

    def test_every_seeded_record_has_a_diagnosis(self, conn):
        rows = conn.execute(
            "SELECT id FROM medical_records WHERE diagnosis IS NULL OR diagnosis = ''"
        ).fetchall()
        assert rows == []

class TestIdempotency:

    def test_rerunning_init_script_does_not_duplicate_rows(self, conn):
        before_count = conn.execute("SELECT COUNT(*) AS c FROM medical_records").fetchone()["c"]

        env = os.environ.copy()
        env["DATABASE_PATH"] = DATABASE_NAME

        result = subprocess.run(
            [sys.executable, INIT_SCRIPT],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0, f"init_db.py failed on rerun: {result.stderr}"
        assert "already exist" in result.stdout.lower()

        # reconnect since the script opened/closed its own connection to the same file
        conn2 = sqlite3.connect(DATABASE_NAME)
        after_count = conn2.execute("SELECT COUNT(*) FROM medical_records").fetchone()[0]
        conn2.close()

        assert after_count == before_count