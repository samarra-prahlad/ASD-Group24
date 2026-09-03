import os
import requests
from flask import Flask, jsonify, request, render_template, redirect
from flask_cors import CORS

app = Flask(__name__)

DATABASE_SERVICE_URL = os.getenv("DATABASE_SERVICE_URL", "http://localhost:6006")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")

SHARED_ACCESS_API_URL = os.getenv("SHARED_ACCESS_API_URL", "http://shared-backend:5000")

@app.route("/ward/<int:ward_id>")
def ward_page(ward_id):
    token = request.cookies.get("session_token")

    if not token:
        return redirect("http://localhost:5000/login")

    try:
        response = requests.post(
            f"{SHARED_ACCESS_API_URL}/session/verify",
            json={"token": token},
            timeout=10
        )
    except requests.RequestException:
        return jsonify({"error": "Shared access service unavailable"}), 502

    if response.status_code != 200:
        return redirect("http://localhost:5000/login")

    session = response.json()

    if session.get("role") != "admin":
        return jsonify({"error": "Admin access required"}), 403

    return render_template(
        "ward_detail.html",
        ward_id=ward_id
    )

@app.route("/wards/<int:ward_id>")
def get_ward(ward_id):
    try:
        response = requests.get(
            f"{DATABASE_SERVICE_URL}/wards/{ward_id}",
            timeout=10
        )
    except requests.RequestException:
        return jsonify({"error": "Database service unavailable"}), 502

    return jsonify(response.json()), response.status_code

@app.route("/wards/<int:ward_id>/beds")
def get_beds(ward_id):
    try:
        response = requests.get(
            f"{DATABASE_SERVICE_URL}/wards/{ward_id}/beds",
            timeout=10
        )
    except requests.RequestException:
        return jsonify({"error": "Database service unavailable"}), 502

    return jsonify(response.json()), response.status_code

@app.route("/beds/<int:bed_id>/assign", methods=["PUT"])
def assign_patient_to_bed(bed_id):
    data = request.get_json() or {}

    patient_id = data.get("patient_id")

    if patient_id is None:
        return jsonify({"error": "patient_id is required"}), 400

    if not isinstance(patient_id, int):
        return jsonify({"error": "patient_id must be an integer"}), 400

    # Check patient exists
    try:
        patient_response = requests.get(
            f"{SHARED_ACCESS_API_URL}/validate",
            params={"patient_id": patient_id},
            timeout=10
        )
    except requests.RequestException:
        return jsonify({"error": "Shared patient service unavailable"}), 502

    if patient_response.status_code == 404:
        return jsonify({"error": "Patient does not exist"}), 404

    if patient_response.status_code != 200:
        return jsonify({"error": "Unable to validate patient"}), patient_response.status_code

    
    try:
        bed_response = requests.put(
            f"{DATABASE_SERVICE_URL}/beds/{bed_id}/assign",
            json={"patient_id": patient_id},
            timeout=10
        )
    except requests.RequestException:
        return jsonify({"error": "Ward database service unavailable"}), 502

    return jsonify(bed_response.json()), bed_response.status_code