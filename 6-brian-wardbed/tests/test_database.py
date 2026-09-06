import pytest
import os
import sqlite3
import tempfile
from database import app as database_app

#a small fake db to test the methods on in order to not change the actual db
#this fake db will change the db path to this one only and have the tets run normally
@pytest.fixture
def db_client():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    conn = sqlite3.connect(db_path)

    conn.executescript("""
        CREATE TABLE wards (
            ward_id INTEGER PRIMARY KEY,
            ward_name TEXT UNIQUE,
            capacity INTEGER
        );

        CREATE TABLE beds (
            bed_id INTEGER PRIMARY KEY,
            ward_id INTEGER,
            patient_id INTEGER,
            bed_number INTEGER,
            status TEXT DEFAULT 'available',
            UNIQUE(ward_id, bed_number)
        );
    """)

    conn.execute(
        "INSERT INTO wards (ward_id, ward_name, capacity) VALUES (?, ?, ?)",
        (1, "General", 2)
    )

    conn.execute(
        """
        INSERT INTO beds
        (bed_id, ward_id, patient_id, bed_number, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (1, 1, None, 1, "available")
    )

    beds = [
    (2, 1, 101, 2, "occupied"),
    (3, 1, 202, 3, "occupied")
    ]

    conn.executemany(
        """
        INSERT INTO beds
        (bed_id, ward_id, patient_id, bed_number, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        beds
    )

    conn.commit()
    conn.close()

    database_app.DATABASE_PATH = db_path
    database_app.app.config["TESTING"] = True

    with database_app.app.test_client() as client:
        yield client

    os.remove(db_path)

def test_get_ward(db_client):
    response = db_client.get("/wards/1")

    assert response.status_code == 200
    assert response.is_json

    data = response.get_json()

    assert data["ward_id"] == 1
    assert data["ward_name"] == "General"
    assert data["capacity"] == 2

def test_wrong_ward(db_client):
    response = db_client.get("/wards/999")

    assert response.status_code == 404

def test_get_beds(db_client):
    response = db_client.get("/wards/1/beds")

    assert response.status_code == 200
    assert response.is_json

    data = response.get_json()

    assert isinstance(data, list)

def test_assign_patient(db_client):
    response = db_client.put(
        "/beds/1/assign",
        json={"patient_id": 123}
    )

    assert response.status_code == 200

    response = db_client.get("/wards/1/beds")
    beds = response.get_json()

    bed = next(each_bed for each_bed in beds if each_bed["bed_id"] == 1)

    assert bed["patient_id"] == 123
    assert bed["status"] == "occupied"

def test_assign_missing_patient_id(db_client):
    response = db_client.put(
        "/beds/1/assign",
        json={}
    )

    assert response.status_code == 400

def test_assign_to_nonexistent_bed(db_client):
    response = db_client.put(
        "/beds/999/assign",
        json={"patient_id": 123}
    )

    assert response.status_code == 404

def test_assign_to_occupied_bed(db_client):
    response = db_client.put(
        "/beds/2/assign",
        json={"patient_id": 456}
    )

    assert response.status_code == 409

def test_release_patient(db_client):
    response = db_client.put("/beds/2/release")

    assert response.status_code == 200

    response = db_client.get("/wards/1/beds")
    beds = response.get_json()

    bed_2 = next(
        each_bed for each_bed in beds
        if each_bed["bed_id"] == 2
    )

    assert bed_2["patient_id"] is None
    assert bed_2["status"] == "available"

def test_release_empty_bed(db_client):
    response = db_client.put("/beds/1/release")

    assert response.status_code == 409

def test_release_nonexistent_bed(db_client):
    response = db_client.put("/beds/999/release")

    assert response.status_code == 404

def test_release_patient_only_changes_target_bed(db_client):
    response = db_client.put("/beds/2/release")

    assert response.status_code == 200

    response = db_client.get("/wards/1/beds")
    beds = response.get_json()

    bed_2 = next(
        each_bed for each_bed in beds
        if each_bed["bed_id"] == 2
    )

    bed_3 = next(
        each_bed for each_bed in beds
        if each_bed["bed_id"] == 3
    )

    assert bed_2["patient_id"] is None
    assert bed_2["status"] == "available"

    assert bed_3["patient_id"] == 202
    assert bed_3["status"] == "occupied"