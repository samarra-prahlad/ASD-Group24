import requests

BASE_URL = "http://localhost:5001"

def test_health():
    response = requests.get(f"{BASE_URL}/")

    assert response.status_code == 200

    data = response.json()

    assert data["service"] == "appointments-backend"
    assert data["status"] == "running"

# testing getting appointments 
def test_get_all_appointments():
    response = requests.get(f"{BASE_URL}/appointments")

    assert response.status_code == 200
    assert isinstance(response.json(), list)

# testing getting a specific appointment 
def test_get_appointment():
    response = requests.get(f"{BASE_URL}/appointments/1")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == 1
    assert "patient_id" in data
    assert "doctor_id" in data
    assert "date" in data
    assert "time" in data
    assert "status" in data

# testing invalid appointments 
def test_get_invalid_appointment():
    response = requests.get(f"{BASE_URL}/appointments/99999")

    assert response.status_code == 404

# testing retreiving appointments for a patient 
def test_get_patient_appointments():
    response = requests.get(
        f"{BASE_URL}/appointments/patient/101"
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)

    for appointment in response.json():
        assert appointment["patient_id"] == 101

# testing invalid patient 
def test_invalid_patient():
    response = requests.get(
        f"{BASE_URL}/appointments/patient/99999"
    )

    assert response.status_code == 404

# Testing retreivng appointments for a doctor
def test_get_doctor_appointments():
    response = requests.get(
        f"{BASE_URL}/appointments/doctor/201"
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)

    for appointment in response.json():
        assert appointment["doctor_id"] == 201

# Testing get all doctors 
def test_get_all_doctors():
    response = requests.get(f"{BASE_URL}/doctors")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) > 0

# Testing getting a singular doctor
def test_get_single_doctor():
    response = requests.get(f"{BASE_URL}/doctors/201")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == 201
    assert "name" in data
    assert "specialty" in data
    assert "availability" in data

# Testing for invali doctor
def test_get_invalid_doctor():
    response = requests.get(f"{BASE_URL}/doctors/99999")

    assert response.status_code == 404

# Testing creating an appointment
def test_create_appointment():
    appointment = {
        "patient_id": 101,
        "doctor_id": 206,
        "date": "2026-11-01",
        "time": "10:30",
        "status": "scheduled"
    }

    response = requests.post(
        f"{BASE_URL}/appointments",
        json=appointment
    )

    assert response.status_code in [200, 201]

    data = response.json()

    assert "appointment_id" in data
    assert "message" in data
    appointment_id = data["appointment_id"]

    check_response = requests.get(
        f"{BASE_URL}/appointments/{appointment_id}"
    )

    assert check_response.status_code == 200

# Creating an appointment but patient is invalid 
def test_create_appointment_invalid_patient():
    appointment = {
        "patient_id": 99999,
        "doctor_id": 206,
        "date": "2026-11-01",
        "time": "10:30",
        "status": "scheduled"
    }

    response = requests.post(
        f"{BASE_URL}/appointments",
        json=appointment
    )

    assert response.status_code == 404

    data = response.json()

    assert "error" in data
    assert "Patient" in data["error"]

# Creating an appointment but doctor is invalid
def test_create_appointment_invalid_doctor():
    appointment = {
        "patient_id": 101,
        "doctor_id": 99999,
        "date": "2026-11-01",
        "time": "10:30",
        "status": "scheduled"
    }

    response = requests.post(
        f"{BASE_URL}/appointments",
        json=appointment
    )

    assert response.status_code == 404

    data = response.json()

    assert "error" in data
    assert "Doctor" in data["error"]

# CReating an appointment with a missing field
def test_create_appointment_missing_field():
    appointment = {
        "patient_id": 101,
        "doctor_id": 206,
        "date": "2026-11-01"
    }

    response = requests.post(
        f"{BASE_URL}/appointments",
        json=appointment
    )

    assert response.status_code == 400

    data = response.json()

    assert "error" in data
    assert "Missing required field" in data["error"]

# Testing updating an appointment
def test_update_appointment():
    appointment ={
        "patient_id": 101,
        "doctor_id": 206,
        "date": "2026-11-01",
        "time": "10:30",
        "status": "scheduled"
    }

    create_response = requests.post(
        f"{BASE_URL}/appointments",
        json=appointment
    )

    assert create_response.status_code in [200, 201]
    appointment_id = create_response.json()["appointment_id"]

    update_data = {
        "date": "2026-11-02",
        "time": "11:00",
        "status": "rescheduled"
    }

    response = requests.put(
        f"{BASE_URL}/appointments/{appointment_id}",
        json=update_data
    )

    assert response.status_code in [200, 201]
    check_response = requests.get(
        f"{BASE_URL}/appointments/{appointment_id}"
    )

    assert check_response.status_code == 200
    data = check_response.json()

    assert data["date"] == "2026-11-02"
    assert data["time"] == "11:00"

# Testing updating invalid appointment 
def test_update_appointment_invalid():
    update_data = {
        "date": "2026-11-02",
        "time": "11:00",
        "status": "rescheduled"
    }

    response = requests.put(
        f"{BASE_URL}/appointments/99999",
        json=update_data
    )

    assert response.status_code == 404

    data = response.json()

    assert "error" in data
    assert "Appointment" in data["error"]

# testing appoinment deletion 
def test_delete_appointment():
    appointment = {
        "patient_id": 101,
        "doctor_id": 206,
        "date": "2026-11-01",
        "time": "10:30",
        "status": "scheduled"
    }

    create_response = requests.post(
        f"{BASE_URL}/appointments",
        json=appointment
    )

    assert create_response.status_code in [200, 201]
    appointment_id = create_response.json()["appointment_id"]

    response = requests.delete(
        f"{BASE_URL}/appointments/{appointment_id}"
    )

    assert response.status_code in [200, 204]

    check_response = requests.get(
        f"{BASE_URL}/appointments/{appointment_id}"
    )

    assert check_response.status_code == 404

# Testing deleting an invalid appointment
def test_delete_invalid_appointment():
    response = requests.delete(
        f"{BASE_URL}/appointments/99999"
    )

    assert response.status_code == 404