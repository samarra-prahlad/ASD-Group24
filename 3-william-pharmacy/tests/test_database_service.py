"""
Tests for database_service.py

Strategy: each test gets its own throwaway SQLite file. We monkeypatch the
module's DATABASE global (rather than relying on the DATABASE_PATH env var,
since the module already imported it at collection time) so every test is
fully isolated and never touches /app/data/pharmacy.db.
"""
import sqlite3
import pytest

import importlib.util
import sys
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "database_service", Path(__file__).parent.parent / "database" / "app.py"
)
database_service = importlib.util.module_from_spec(_spec)
sys.modules["database_service"] = database_service
_spec.loader.exec_module(database_service)


SCHEMA = """
CREATE TABLE medications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    stock INTEGER NOT NULL DEFAULT 0,
    unit_price REAL NOT NULL
);

CREATE TABLE prescriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    medication_id INTEGER NOT NULL,
    dosage TEXT NOT NULL,
    prescribing_doctor TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (medication_id) REFERENCES medications(id)
);
"""


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """Point the app at a fresh temp SQLite file with the schema applied."""
    path = tmp_path / "pharmacy_test.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

    monkeypatch.setattr(database_service, "DATABASE", str(path))
    return str(path)


@pytest.fixture
def client(db_path):
    database_service.app.config["TESTING"] = True
    return database_service.app.test_client()


@pytest.fixture
def seeded_medication(db_path):
    """Insert one medication directly and return its id."""
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "INSERT INTO medications (name, stock, unit_price) VALUES (?, ?, ?)",
        ("Amoxicillin 500mg", 120, 0.35),
    )
    conn.commit()
    med_id = cur.lastrowid
    conn.close()
    return med_id


# ---------------------------------------------------------------------------
# GET /medications
# ---------------------------------------------------------------------------

def test_get_medications_empty(client):
    resp = client.get("/medications")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_get_medications_returns_seeded_row(client, seeded_medication):
    resp = client.get("/medications")
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body) == 1
    assert body[0]["id"] == seeded_medication
    assert body[0]["name"] == "Amoxicillin 500mg"
    assert body[0]["stock"] == 120
    assert body[0]["unit_price"] == 0.35


# ---------------------------------------------------------------------------
# GET /prescriptions/<patient_id>
# ---------------------------------------------------------------------------

def test_get_prescriptions_filters_by_patient(client, db_path, seeded_medication):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO prescriptions (patient_id, medication_id, dosage, prescribing_doctor, status)
           VALUES (?, ?, ?, ?, ?)""",
        (3, seeded_medication, "500mg twice daily", "Dr. Sarah Chen", "active"),
    )
    conn.execute(
        """INSERT INTO prescriptions (patient_id, medication_id, dosage, prescribing_doctor, status)
           VALUES (?, ?, ?, ?, ?)""",
        (4, seeded_medication, "200mg once daily", "Dr. James Patel", "active"),
    )
    conn.commit()
    conn.close()

    resp = client.get("/prescriptions/3")
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body) == 1
    assert body[0]["patient_id"] == 3


def test_get_prescriptions_no_match_returns_empty_list(client):
    resp = client.get("/prescriptions/999")
    assert resp.status_code == 200
    assert resp.get_json() == []


# ---------------------------------------------------------------------------
# POST /admin/medications/
# ---------------------------------------------------------------------------

def test_add_medication_success(client):
    resp = client.post(
        "/admin/medications/",
        json={"name": "Ibuprofen 200mg", "stock": 300, "unit_price": 0.10},
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["name"] == "Ibuprofen 200mg"
    assert body["id"] is not None

    # confirm it's actually persisted, not just echoed back
    listed = client.get("/medications").get_json()
    assert any(m["id"] == body["id"] for m in listed)


def test_add_medication_defaults_stock_to_zero(client):
    resp = client.post(
        "/admin/medications/",
        json={"name": "New Drug", "unit_price": 1.00},
    )
    assert resp.status_code == 201
    assert resp.get_json()["stock"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"stock": 10, "unit_price": 1.0},                       # missing name
        {"name": "X", "stock": 10},                              # missing unit_price
        {"name": "X", "stock": -5, "unit_price": 1.0},           # negative stock
        {"name": "X", "stock": "ten", "unit_price": 1.0},        # non-int stock
        {"name": "X", "stock": 5, "unit_price": -1.0},           # negative price
    ],
)
def test_add_medication_validation_errors_return_400(client, payload):
    resp = client.post("/admin/medications/", json=payload)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# PUT /admin/medications/<id>
# ---------------------------------------------------------------------------

def test_update_medication_success(client, seeded_medication):
    resp = client.put(
        f"/admin/medications/{seeded_medication}",
        json={"stock": 999},
    )
    assert resp.status_code == 200
    assert resp.get_json()["updated"] == 1

    updated = next(
        m for m in client.get("/medications").get_json()
        if m["id"] == seeded_medication
    )
    assert updated["stock"] == 999
    assert updated["name"] == "Amoxicillin 500mg"  # untouched fields preserved


def test_update_medication_no_fields_returns_400(client, seeded_medication):
    resp = client.put(f"/admin/medications/{seeded_medication}", json={})
    assert resp.status_code == 400


def test_update_medication_not_found_returns_404(client):
    resp = client.put("/admin/medications/9999", json={"stock": 1})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /admin/medications/<id>
# ---------------------------------------------------------------------------

def test_delete_medication_success(client, seeded_medication):
    resp = client.delete(f"/admin/medications/{seeded_medication}")
    assert resp.status_code == 200
    assert resp.get_json()["deleted"] == 1
    assert client.get("/medications").get_json() == []


def test_delete_medication_not_found_returns_404(client):
    resp = client.delete("/admin/medications/9999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /admin/prescriptions
# ---------------------------------------------------------------------------

def test_create_prescription_success(client, seeded_medication):
    resp = client.post(
        "/admin/prescriptions",
        json={
            "patient_id": 3,
            "medication_id": seeded_medication,
            "dosage": "500mg twice daily",
            "prescribing_doctor": "Dr. Sarah Chen",
        },
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["id"] is not None
    assert body["patient_id"] == 3
    assert body["dosage"] == "500mg twice daily"
    assert body["status"] == "active" 

    listed = client.get("/prescriptions/3").get_json()
    assert len(listed) == 1


def test_create_prescription_defaults_status_to_active_in_db(client, seeded_medication):
    """
    create_prescription defaults status to "active" when the client omits
    it, and that default is reflected both in the row inserted into the
    database and in the response body.
    """
    resp = client.post(
        "/admin/prescriptions",
        json={
            "patient_id": 3,
            "medication_id": seeded_medication,
            "dosage": "500mg twice daily",
            "prescribing_doctor": "Dr. Sarah Chen",
        },
    )
    assert resp.status_code == 201
    assert resp.get_json()["status"] == "active"  # now correctly present in the response

    listed = client.get("/prescriptions/3").get_json()
    assert listed[0]["status"] == "active"  # and the DB row matches


def test_create_prescription_missing_field_returns_400(client, seeded_medication):
    resp = client.post(
        "/admin/prescriptions",
        json={
            "patient_id": 3,
            "medication_id": seeded_medication,
            "dosage": "500mg twice daily",
            # prescribing_doctor missing
        },
    )
    assert resp.status_code == 400


def test_create_prescription_nonexistent_medication_returns_400(client):
    resp = client.post(
        "/admin/prescriptions",
        json={
            "patient_id": 3,
            "medication_id": 9999,
            "dosage": "500mg twice daily",
            "prescribing_doctor": "Dr. Sarah Chen",
        },
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# PUT /admin/prescriptions/<id>
# ---------------------------------------------------------------------------

def test_update_prescription_status(client, db_path, seeded_medication):
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        """INSERT INTO prescriptions (patient_id, medication_id, dosage, prescribing_doctor, status)
           VALUES (?, ?, ?, ?, ?)""",
        (3, seeded_medication, "500mg twice daily", "Dr. Sarah Chen", "active"),
    )
    conn.commit()
    rx_id = cur.lastrowid
    conn.close()

    resp = client.put(f"/admin/prescriptions/{rx_id}", json={"status": "completed"})
    assert resp.status_code == 200

    listed = client.get("/prescriptions/3").get_json()
    assert listed[0]["status"] == "completed"


def test_update_prescription_not_found_returns_404(client):
    resp = client.put("/admin/prescriptions/9999", json={"status": "completed"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /admin/prescriptions/<id>
# ---------------------------------------------------------------------------

def test_delete_prescription_success(client, db_path, seeded_medication):
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        """INSERT INTO prescriptions (patient_id, medication_id, dosage, prescribing_doctor, status)
           VALUES (?, ?, ?, ?, ?)""",
        (3, seeded_medication, "500mg twice daily", "Dr. Sarah Chen", "active"),
    )
    conn.commit()
    rx_id = cur.lastrowid
    conn.close()

    resp = client.delete(f"/admin/prescriptions/{rx_id}")
    assert resp.status_code == 200
    assert resp.get_json()["deleted"] == 1
    assert client.get("/prescriptions/3").get_json() == []


def test_delete_prescription_not_found_returns_404(client):
    resp = client.delete("/admin/prescriptions/9999")
    assert resp.status_code == 404
