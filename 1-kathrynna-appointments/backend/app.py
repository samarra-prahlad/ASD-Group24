from flask import Flask, jsonify, request
import os
import requests

app = Flask(__name__)

DATABASE_SERVICE_URL = os.getenv("DATABASE_SERVICE_URL", "http://shared-database:6001")
SHARED_ACCESS_API_URL = os.getenv("SHARED_ACCESS_API_URL", "http://shared-access-api:5000")

# Check
@app.get("/")
def health():
    return jsonify({"service": "appointments-backend", "status": "running"})

def validate_patient(patient_id):
    """
    Ask the shared access API to confirm that the patient exists.
    """ 
    try:
        response = requests.get(f"{SHARED_ACCESS_API_URL}/validate?patient_id={patient_id}", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"error": "Shared access API unavailable", "detail": str(exc)}, 503

    if response.status_code == 404:
        return {"valid": False, "error": "Patient not found"}, 404

    return response.json(), 200

# Get all appointments
@app.get("/appointments")
def get_appointments():
    try:
        response = requests.get(f"{DATABASE_SERVICE_URL}/appointments", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "Appointments database unavailable", "detail": str(exc)}), 503

    return jsonify(response.json())

# get a single appointment 
@app.get("/appointments/<int:appointment_id>")
def get_appointment(appointment_id):
    try:
        response = requests.get(
            f"{DATABASE_SERVICE_URL}/appointments/{appointment_id}",
            timeout=5
        )
    except requests.RequestException as exc:
        return jsonify({
            "error": "Appointments database unavailable",
            "detail": str(exc)
        }), 503

    if response.status_code == 404:
        return jsonify({
            "error": "Appointment not found"
        }), 404

    if response.status_code != 200:
        return jsonify({
            "error": "Unable to retrieve appointment"
        }), response.status_code

    return jsonify(response.json())

# get appointments for a specific patient 
@app.get("/appointments/patient/<int:patient_id>")
def get_appointments_by_patient(patient_id):

    # Validate the patient through the shared backend
    patient_result, patient_status = validate_patient(patient_id)

    if patient_status != 200:
        return jsonify({
            "error": f"Patient with ID {patient_id} not found"
        }), patient_status

    try:
        response = requests.get(
            f"{DATABASE_SERVICE_URL}/appointments/patient/{patient_id}",
            timeout=5
        )

        if response.status_code == 404:
            return jsonify({
                "error": f"No appointments found for patient {patient_id}"
            }), 404

        if response.status_code != 200:
            return jsonify({
                "error": "Unable to retrieve patient appointments"
            }), response.status_code

    except requests.RequestException as exc:
        return jsonify({
            "error": "Appointments database unavailable",
            "detail": str(exc)
        }), 503

    return jsonify(response.json())

# get appointments for a specific doctor 
@app.get("/appointments/doctor/<int:doctor_id>")
def get_appointments_by_doctor(doctor_id):
    try:
        response = requests.get(f"{DATABASE_SERVICE_URL}/appointments/doctor/{doctor_id}", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "Appointments database unavailable", "detail": str(exc)}), 503

    return jsonify(response.json())

# create a new appointment 
@app.post("/appointments")
def create_appointment():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    required_fields = ["patient_id", "doctor_id", "date", "time"]

    for field in required_fields:
        if field not in data:
            return jsonify({
                "error": f"Missing required field: {field}"
            }), 400

    patient_id = data["patient_id"]
    doctor_id = data["doctor_id"]

    # Validate patient
    patient_result, patient_status = validate_patient(patient_id)

    if patient_status != 200:
        return jsonify({
            "error": f"Patient with ID {patient_id} not found"
        }), patient_status

    try:
        # Validate doctor
        doctor_response = requests.get(
            f"{DATABASE_SERVICE_URL}/doctors/{doctor_id}",
            timeout=5
        )

        if doctor_response.status_code == 404:
            return jsonify({
                "error": f"Doctor with ID {doctor_id} not found"
            }), 404

        if doctor_response.status_code != 200:
            return jsonify({
                "error": "Unable to validate doctor"
            }), 503

        # Create appointment
        response = requests.post(
            f"{DATABASE_SERVICE_URL}/appointments",
            json=data,
            timeout=5
        )

        return jsonify(response.json()), response.status_code

    except requests.RequestException as exc:
        return jsonify({
            "error": "Unable to connect to appointments database",
            "detail": str(exc)
        }), 503
    
# update appointments 
@app.put("/appointments/<int:appointment_id>")
def update_appointment(appointment_id):

    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Invalid JSON payload"
        }), 400

    try:

        # Find existing appointment
        appointment_response = requests.get(
            f"{DATABASE_SERVICE_URL}/appointments/{appointment_id}",
            timeout=5
        )

        if appointment_response.status_code != 200:
            return jsonify({
                "error": "Appointment not found"
            }), 404

        appointment_data = appointment_response.json()
        patient_id = appointment_data["patient_id"]

        # Validate patient through shared backend
        patient_result, patient_status = validate_patient(patient_id)

        if patient_status != 200:
            return jsonify({
                "error": f"Patient with ID {patient_id} not found"
            }), patient_status

        # Update appointment
        response = requests.put(
            f"{DATABASE_SERVICE_URL}/appointments/{appointment_id}",
            json=data,
            timeout=5
        )

        return jsonify(response.json()), response.status_code

    except requests.RequestException as exc:
        return jsonify({
            "error": "Unable to connect to appointments database",
            "detail": str(exc)
        }), 503

# delete appointment 
@app.delete("/appointments/<int:appointment_id>")
def delete_appointment(appointment_id):

    try:

        # Get appointment
        appointment_response = requests.get(
            f"{DATABASE_SERVICE_URL}/appointments/{appointment_id}",
            timeout=5
        )

        if appointment_response.status_code != 200:
            return jsonify(
                appointment_response.json()
            ), appointment_response.status_code

        appointment = appointment_response.json()
        patient_id = appointment.get("patient_id")

        # Validate patient through shared backend
        patient_result, patient_status = validate_patient(patient_id)

        if patient_status != 200:
            return jsonify({
                "error": f"Patient with ID {patient_id} not found"
            }), patient_status

        # Delete appointment
        response = requests.delete(
            f"{DATABASE_SERVICE_URL}/appointments/{appointment_id}",
            timeout=5
        )

        return jsonify(response.json()), response.status_code

    except requests.RequestException as exc:
        return jsonify({
            "error": "Unable to connect to appointments database",
            "detail": str(exc)
        }), 503
#get all doctors 
@app.get("/doctors")
def get_doctors():
    try:
        response = requests.get(f"{DATABASE_SERVICE_URL}/doctors", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "Appointments database unavailable", "detail": str(exc)}), 503

    return jsonify(response.json())

# get one doctor 
@app.get("/doctors/<int:doctor_id>")
def get_doctor(doctor_id):
    try:
        response = requests.get(
            f"{DATABASE_SERVICE_URL}/doctors/{doctor_id}",
            timeout=5
        )
    except requests.RequestException as exc:
        return jsonify({
            "error": "Appointments database unavailable",
            "detail": str(exc)
        }), 503

    if response.status_code == 404:
        return jsonify({
            "error": f"Doctor ID {doctor_id} not found"
        }), 404

    if response.status_code != 200:
        return jsonify({
            "error": f"Unable to retrieve doctor ID {doctor_id}"
        }), response.status_code

    return jsonify(response.json())

# run 
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5001,
        debug=True
    )