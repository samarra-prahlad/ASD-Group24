import requests

BASE_URL = "http://localhost:6001"

def test_health():
    response = requests.get(f"{BASE_URL}/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "appointments-database"
    assert data["status"] == "running"

def test_get_all_appointments():
    response = requests.get(f"{BASE_URL}/appointments")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

def test_get_single_appointment():
    response = requests.get(f"{BASE_URL}/appointments/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert "patient_id" in data
    assert "doctor_id" in data
    assert "date" in data
    assert "time" in data
    assert "status" in data

def test_get_nonexistent_appointment():
    response = requests.get(f"{BASE_URL}/appointments/9999")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"] == "Appointment not found"

def test_get_appointments_by_patient():
    response = requests.get(f"{BASE_URL}/appointments/patient/101")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    for appointment in data:
        assert appointment["patient_id"] == 101

def test_get_doctors():
    response = requests.get(f"{BASE_URL}/doctors")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

def test_get_single_doctor():
    response = requests.get(f"{BASE_URL}/doctors/201")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 201
    assert "name" in data
    assert "specialty" in data
    assert "availability" in data

def test_get_nonexistent_doctor():
    response = requests.get(f"{BASE_URL}/doctors/9999")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"] == "Doctor not found"

