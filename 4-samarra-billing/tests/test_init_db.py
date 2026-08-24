"""
Pytest suite for the Billing & Insurance database layer (init_db.py).

Run with:
    pytest tests/test_init_db.py -v
"""

import os
import sqlite3
import subprocess
import sys

import pytest

FEATURE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INIT_SCRIPT = os.path.join(FEATURE_ROOT, "database", "init_db.py")

# Local test runs write here instead of the container path (/app/data),
# which doesn't exist on a native macOS filesystem. Inside Docker, no one
# sets DB_DATA_DIR, so init_db.py still defaults to /app/data unchanged.
TEST_DATA_DIR = os.path.join(FEATURE_ROOT, "tests", ".test_data")
DATABASE_NAME = os.path.join(TEST_DATA_DIR, "billing.db")

VALID_STATUSES = {"pending", "paid", "partially_paid"}


@pytest.fixture(scope="module", autouse=True)
def fresh_database():
    """
    Wipe and rebuild billing.db by running init_db.py, once for this test module.
    Ensures tests run against a known, clean state rather than whatever
    happens to already be on disk.
    """
    os.makedirs(TEST_DATA_DIR, exist_ok=True)

    if os.path.exists(DATABASE_NAME):
        os.remove(DATABASE_NAME)

    env = os.environ.copy()
    env["DB_DATA_DIR"] = TEST_DATA_DIR

    result = subprocess.run(
        [sys.executable, INIT_SCRIPT],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f"init_db.py failed: {result.stderr}"

    yield

    # No teardown: leave the seeded db in place for the next tool in the
    # chain (app.py) to run against.


@pytest.fixture
def conn():
    """Fresh connection per test, with row_factory for dict-like access."""
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    yield connection
    connection.close()


# ---------------------------------------------------------------------------
# Database / table existence
# ---------------------------------------------------------------------------

class TestDatabaseSetup:

    def test_database_file_exists(self):
        assert os.path.exists(DATABASE_NAME)

    def test_insurance_providers_table_exists(self, conn):
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='insurance_providers'"
        ).fetchone()
        assert row is not None

    def test_invoices_table_exists(self, conn):
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='invoices'"
        ).fetchone()
        assert row is not None


# ---------------------------------------------------------------------------
# Schema / columns
# ---------------------------------------------------------------------------

class TestSchema:

    def test_insurance_providers_columns(self, conn):
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(insurance_providers)")}
        expected = {"id", "name", "plan_type", "coverage_percentage", "contact_number"}
        assert expected.issubset(columns)

    def test_invoices_columns(self, conn):
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(invoices)")}
        expected = {
            "id", "patient_id", "insurance_provider_id",
            "appointment_cost", "medication_cost", "bed_charges",
            "total_amount", "insurance_covered_amount", "patient_owed_amount",
            "status", "date",
        }
        assert expected.issubset(columns)

    def test_invoices_has_foreign_key_to_insurance_providers(self, conn):
        fks = conn.execute("PRAGMA foreign_key_list(invoices)").fetchall()
        assert any(fk["table"] == "insurance_providers" for fk in fks)


# ---------------------------------------------------------------------------
# Seed data population (spec requires >= 10 records per table)
# ---------------------------------------------------------------------------

class TestSeedData:

    def test_insurance_providers_minimum_record_count(self, conn):
        count = conn.execute("SELECT COUNT(*) AS c FROM insurance_providers").fetchone()["c"]
        assert count >= 10

    def test_invoices_minimum_record_count(self, conn):
        count = conn.execute("SELECT COUNT(*) AS c FROM invoices").fetchone()["c"]
        assert count >= 10

    def test_insurance_providers_have_no_null_required_fields(self, conn):
        rows = conn.execute(
            "SELECT * FROM insurance_providers WHERE name IS NULL OR plan_type IS NULL OR coverage_percentage IS NULL"
        ).fetchall()
        assert rows == []

    def test_invoices_have_no_null_required_fields(self, conn):
        rows = conn.execute(
            """SELECT * FROM invoices
               WHERE patient_id IS NULL
                  OR total_amount IS NULL
                  OR patient_owed_amount IS NULL
                  OR status IS NULL
                  OR date IS NULL"""
        ).fetchall()
        assert rows == []


# ---------------------------------------------------------------------------
# Data integrity / business rules
# ---------------------------------------------------------------------------

class TestDataIntegrity:

    def test_invoice_insurance_provider_ids_reference_real_providers(self, conn):
        invoices = conn.execute(
            "SELECT id, insurance_provider_id FROM invoices WHERE insurance_provider_id IS NOT NULL"
        ).fetchall()
        provider_ids = {row["id"] for row in conn.execute("SELECT id FROM insurance_providers")}

        orphaned = [inv["id"] for inv in invoices if inv["insurance_provider_id"] not in provider_ids]
        assert orphaned == [], f"Invoices with orphaned insurance_provider_id: {orphaned}"

    def test_total_amount_equals_sum_of_costs(self, conn):
        invoices = conn.execute(
            "SELECT id, appointment_cost, medication_cost, bed_charges, total_amount FROM invoices"
        ).fetchall()

        mismatches = []
        for inv in invoices:
            expected_total = round(inv["appointment_cost"] + inv["medication_cost"] + inv["bed_charges"], 2)
            if round(inv["total_amount"], 2) != expected_total:
                mismatches.append(inv["id"])

        assert mismatches == [], f"Invoices where total_amount != sum of costs: {mismatches}"

    def test_patient_owed_equals_total_minus_covered(self, conn):
        invoices = conn.execute(
            "SELECT id, total_amount, insurance_covered_amount, patient_owed_amount FROM invoices"
        ).fetchall()

        mismatches = []
        for inv in invoices:
            expected_owed = round(inv["total_amount"] - inv["insurance_covered_amount"], 2)
            if round(inv["patient_owed_amount"], 2) != expected_owed:
                mismatches.append(inv["id"])

        assert mismatches == [], f"Invoices where patient_owed_amount is inconsistent: {mismatches}"

    def test_status_values_are_valid(self, conn):
        statuses = {row["status"] for row in conn.execute("SELECT DISTINCT status FROM invoices")}
        assert statuses.issubset(VALID_STATUSES), f"Unexpected status values: {statuses - VALID_STATUSES}"

    def test_coverage_percentage_within_valid_range(self, conn):
        rows = conn.execute(
            "SELECT id, coverage_percentage FROM insurance_providers WHERE coverage_percentage < 0 OR coverage_percentage > 100"
        ).fetchall()
        assert rows == []

    def test_costs_are_non_negative(self, conn):
        rows = conn.execute(
            """SELECT id FROM invoices
               WHERE appointment_cost < 0 OR medication_cost < 0 OR bed_charges < 0
                  OR total_amount < 0 OR insurance_covered_amount < 0 OR patient_owed_amount < 0"""
        ).fetchall()
        assert rows == []


# ---------------------------------------------------------------------------
# Idempotency (re-running init_db.py should not duplicate seed data)
# ---------------------------------------------------------------------------

class TestIdempotency:

    def test_rerunning_init_script_does_not_duplicate_rows(self, conn):
        before_providers = conn.execute("SELECT COUNT(*) AS c FROM insurance_providers").fetchone()["c"]
        before_invoices = conn.execute("SELECT COUNT(*) AS c FROM invoices").fetchone()["c"]

        env = os.environ.copy()
        env["DB_DATA_DIR"] = TEST_DATA_DIR

        result = subprocess.run(
            [sys.executable, INIT_SCRIPT],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0, f"init_db.py failed on rerun: {result.stderr}"

        # reconnect since the script opened/closed its own connection to the same file
        conn2 = sqlite3.connect(DATABASE_NAME)
        after_providers = conn2.execute("SELECT COUNT(*) FROM insurance_providers").fetchone()[0]
        after_invoices = conn2.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        conn2.close()

        assert after_providers == before_providers
        assert after_invoices == before_invoices