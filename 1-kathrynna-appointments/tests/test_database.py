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

def test_get_appointments_by_doctor():
    response = requests.get(f"{BASE_URL}/appointments/doctor/201")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    for appointment in data:
        assert appointment["doctor_id"] == 201

def test_create_appointment():
    reponse = requests.post(f"{BASE_URL}/appointments", json={
        "patient_id": 101,
        "doctor_id": 202,
        "date": "2026-10-01",
        "time": "10:30"
    })

    assert reponse.status_code == 201
    data = reponse.json()

    assert data["message"] == "Appointment created successfully"
    assert "appointment_id" in data

    appointment_id = data["appointment_id"]

    requests.delete(f"{BASE_URL}/appointments/{appointment_id}")

def test_update_appointment():

    # Create an appointment first
    create_response = requests.post(
        f"{BASE_URL}/appointments",
        json={
            "patient_id": 101,
            "doctor_id": 201,
            "date": "2026-10-01",
            "time": "10:30",
            "status": "scheduled"
        }
    )

    assert create_response.status_code == 201

    appointment_id = create_response.json()["appointment_id"]

        # Update the appointment
    response = requests.put(
        f"{BASE_URL}/appointments/{appointment_id}",
        json={
            "date": "2026-10-02",
            "time": "11:00",
            "status": "confirmed"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["message"] == "Appointment updated"
    assert data["appointment_id"] == appointment_id

    # Verify the update
    get_response = requests.get(
        f"{BASE_URL}/appointments/{appointment_id}"
    )

    assert get_response.status_code == 200

    updated = get_response.json()

    assert updated["date"] == "2026-10-02"
    assert updated["time"] == "11:00"
    assert updated["status"] == "confirmed"

    # Clean up
    requests.delete(
        f"{BASE_URL}/appointments/{appointment_id}"
    )


def test_delete_appointment():

    # Create an appointment first
    create_response = requests.post(
        f"{BASE_URL}/appointments",
        json={
            "patient_id": 102,
            "doctor_id": 201,
            "date": "2026-10-05",
            "time": "13:00",
            "status": "scheduled"
        }
    )

    assert create_response.status_code == 201

    appointment_id = create_response.json()["appointment_id"]

    # Delete the appointment
    response = requests.delete(
        f"{BASE_URL}/appointments/{appointment_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["message"] == "Appointment deleted"
    assert data["appointment_id"] == appointment_id

    # Verify it was actually deleted
    get_response = requests.get(
        f"{BASE_URL}/appointments/{appointment_id}"
    )

    assert get_response.status_code == 404

def test_create_appointment_invalid_doctor():

    response = requests.post(
        f"{BASE_URL}/appointments",
        json={
            "patient_id": 101,
            "doctor_id": 9999,
            "date": "2026-10-01",
            "time": "10:30",
            "status": "scheduled"
        }
    )

    assert response.status_code == 404

    data = response.json()

    assert data["error"] == "Doctor not found"


def test_create_appointment_missing_field():

    response = requests.post(
        f"{BASE_URL}/appointments",
        json={
            "patient_id": 101,
            "doctor_id": 201,
            "date": "2026-10-01"
        }
    )

    assert response.status_code == 400

    data = response.json()

    assert "error" in data