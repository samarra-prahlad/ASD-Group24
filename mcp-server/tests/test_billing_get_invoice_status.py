import sqlite3

import pytest

from tools import billing_get_invoice_status
from tools.billing_get_invoice_status import get_invoice_status


def _create_test_db(path):
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE insurance_providers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            plan_type TEXT NOT NULL,
            coverage_percentage INTEGER NOT NULL,
            contact_number TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE invoices (
            id INTEGER PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            insurance_provider_id INTEGER,
            appointment_cost REAL NOT NULL DEFAULT 0,
            medication_cost REAL NOT NULL DEFAULT 0,
            bed_charges REAL NOT NULL DEFAULT 0,
            total_amount REAL NOT NULL,
            insurance_covered_amount REAL NOT NULL DEFAULT 0,
            patient_owed_amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            date TEXT NOT NULL
        )
    """)
    conn.execute(
        "INSERT INTO insurance_providers (id, name, plan_type, coverage_percentage, contact_number) "
        "VALUES (301, 'Medibank', 'Basic', 60, '13 23 31')"
    )
    conn.execute(
        "INSERT INTO invoices (id, patient_id, insurance_provider_id, appointment_cost, "
        "medication_cost, bed_charges, total_amount, insurance_covered_amount, "
        "patient_owed_amount, status, date) "
        "VALUES (1, 1, 301, 150.00, 45.00, 0.00, 195.00, 117.00, 78.00, 'pending', '2026-08-15')"
    )
    conn.commit()
    conn.close()


@pytest.fixture
def billing_db(tmp_path, monkeypatch):
    db_path = tmp_path / "billing.db"
    _create_test_db(db_path)
    monkeypatch.setattr(billing_get_invoice_status, "DATABASE_PATH", db_path)
    return db_path


def test_get_invoice_status_returns_matching_invoice(billing_db):
    result = get_invoice_status(1)

    assert result["invoice_id"] == 1
    assert result["patient_id"] == 1
    assert result["status"] == "pending"
    assert result["total_amount"] == 195.00
    assert result["insurance_covered_amount"] == 117.00
    assert result["patient_owed_amount"] == 78.00
    assert result["date"] == "2026-08-15"
    assert result["insurance_provider_name"] == "Medibank"


def test_get_invoice_status_returns_error_when_not_found(billing_db):
    result = get_invoice_status(999)

    assert result == {"error": "Invoice not found", "invoice_id": 999}


def test_get_invoice_status_returns_error_when_database_missing(tmp_path, monkeypatch):
    missing_path = tmp_path / "does_not_exist.db"
    monkeypatch.setattr(billing_get_invoice_status, "DATABASE_PATH", missing_path)

    result = get_invoice_status(1)

    assert result["error"] == "Billing database not found"