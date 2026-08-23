import os

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

DATABASE_SERVICE_URL = os.environ.get("DATABASE_SERVICE_URL", "http://ehr-database:6002")
SHARED_ACCESS_API_URL = os.environ.get("SHARED_ACCESS_API_URL", "http://shared-backend:5000")

def validate_user(user_id):
    try:
        response = requests.get(
            f"{SHARED_ACCESS_API_URL}/validate",
            params={"patient_id": user_id},
            timeout=5,
        )
    except requests.RequestException as exc:
        return None, (jsonify({"error": "Shared access service is unavailable", "details": str(exc)}), 503)

    if response.status_code == 404:
        return None, (jsonify({"error": "User not found"}), 404)

    response.raise_for_status()
    return response.json().get("role"), None


#---Medical_Records---

# READ
@app.get("/records/<int:patient_id>")
def get_records(patient_id):
    requester_id = request.args.get("requester_id")
    if not requester_id:
        return jsonify({"error": "requester_id is required"}), 400

    role, error_response = validate_user(requester_id)
    if error_response:
        return error_response
    if role == "patient" and int(requester_id) != patient_id:
        return jsonify({"error": "Patients can only access their own records"}), 403

    try:
        response = requests.get(f"{DATABASE_SERVICE_URL}/records/{patient_id}", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "EHR Database unavailable", "details": str(exc)}), 503

    return jsonify(response.json())

# CREATE
@app.post("/records")
def create_record():
    data = request.get_json()
    requester_id = data.get("requester_id")
    if not requester_id:
        return jsonify({"error": "requester_id is required"}), 400

    role, error_response = validate_user(requester_id)
    if error_response:
        return error_response
    if role not in ("doctor", "admin"):
        return jsonify({"error": "Only staff can add medical records"}), 403

    try:
        response = requests.post(f"{DATABASE_SERVICE_URL}/records", json=data, timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "EHR Database unavailable", "details": str(exc)}), 503

    return jsonify(response.json()), 201

# UPDATE
@app.put("/records/<int:record_id>")
def update_record(record_id):
    data = request.get_json()
    requester_id = data.get("requester_id")
    if not requester_id:
        return jsonify({"error": "requester_id is required"}), 400

    role, error_response = validate_user(requester_id)
    if error_response:
        return error_response
    if role not in ("doctor", "admin"):
        return jsonify({"error": "Only staff can edit medical records"}), 403

    try:
        response = requests.put(f"{DATABASE_SERVICE_URL}/records/{record_id}", json=data, timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "EHR Database unavailable", "details": str(exc)}), 503

    return jsonify(response.json())

# DELETE
@app.delete("/records/<int:record_id>")
def delete_record(record_id):
    requester_id = request.args.get("requester_id")
    if not requester_id:
        return jsonify({"error": "requester_id is required"}), 400

    role, error_response = validate_user(requester_id)
    if error_response:
        return error_response
    if role not in ("doctor", "admin"):
        return jsonify({"error": "Only staff can delete medical records"}), 403

    try:
        response = requests.delete(f"{DATABASE_SERVICE_URL}/records/{record_id}", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "EHR Database unavailable", "details": str(exc)}), 503

    return jsonify(response.json())

#---Diagnosis (this is what Pharmacy's backend calls)---

@app.get("/diagnosis/<int:patient_id>")
def get_diagnosis(patient_id):
    try:
        response = requests.get(f"{DATABASE_SERVICE_URL}/records/{patient_id}", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "EHR Database unavailable", "details": str(exc)}), 503

    records = response.json()
    if not records:
        return jsonify({"diagnosis": None, "allergies": None}), 404

    latest = records[0]
    return jsonify({"diagnosis": latest.get("diagnosis"), "allergies": latest.get("allergies")})

#---Change_Requests---

# READ (all)
@app.get("/change_requests")
def get_all_change_requests():
    requester_id = request.args.get("requester_id")
    if not requester_id:
        return jsonify({"error": "requester_id is required"}), 400

    role, error_response = validate_user(requester_id)
    if error_response:
        return error_response
    if role not in ("doctor", "admin"):
        return jsonify({"error": "Only staff can view change requests"}), 403

    try:
        response = requests.get(f"{DATABASE_SERVICE_URL}/change_requests", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "EHR Database unavailable", "details": str(exc)}), 503

    return jsonify(response.json())

# READ (by patient)
@app.get("/change_requests/<int:patient_id>")
def get_change_requests(patient_id):
    requester_id = request.args.get("requester_id")
    if not requester_id:
        return jsonify({"error": "requester_id is required"}), 400

    role, error_response = validate_user(requester_id)
    if error_response:
        return error_response
    if role == "patient" and int(requester_id) != patient_id:
        return jsonify({"error": "Patients can only access their own change requests"}), 403

    try:
        response = requests.get(f"{DATABASE_SERVICE_URL}/change_requests/{patient_id}", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "EHR Database unavailable", "details": str(exc)}), 503

    return jsonify(response.json())

# CREATE
@app.post("/change_requests")
def create_change_request():
    data = request.get_json()
    requester_id = data.get("requester_id")
    if not requester_id:
        return jsonify({"error": "requester_id is required"}), 400

    role, error_response = validate_user(requester_id)
    if error_response:
        return error_response
    if role == "patient" and int(requester_id) != data.get("patient_id"):
        return jsonify({"error": "Patients can only submit requests for themselves"}), 403

    try:
        response = requests.post(f"{DATABASE_SERVICE_URL}/change_requests", json=data, timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "EHR Database unavailable", "details": str(exc)}), 503

    return jsonify(response.json()), 201

# UPDATE
@app.put("/change_requests/<int:request_id>")
def update_change_request(request_id):
    data = request.get_json()
    requester_id = data.get("requester_id")
    if not requester_id:
        return jsonify({"error": "requester_id is required"}), 400

    role, error_response = validate_user(requester_id)
    if error_response:
        return error_response
    if role not in ("doctor", "admin"):
        return jsonify({"error": "Only staff can review change requests"}), 403

    try:
        response = requests.put(f"{DATABASE_SERVICE_URL}/change_requests/{request_id}", json=data, timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "EHR Database unavailable", "details": str(exc)}), 503

    return jsonify(response.json())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)