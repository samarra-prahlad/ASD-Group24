import os

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

DATABASE_SERVICE_URL = os.getenv("DATABASE_SERVICE_URL", "http://shared-database:6000")


@app.get("/")
def health():
    return jsonify({"service": "shared-backend", "status": "running"})


@app.get("/validate")
def validate_patient():
    patient_id = request.args.get("patient_id", "").strip()

    if not patient_id:
        return jsonify({"error": "patient_id is required"}), 400

    try:
        response = requests.get(
            f"{DATABASE_SERVICE_URL}/users/{patient_id}", timeout=5
        )
    except requests.RequestException as exc:
        return jsonify({"error": "Shared database unavailable", "detail": str(exc)}), 503

    if response.status_code == 404:
        return jsonify({"valid": False, "error": "Patient not found"}), 404

    response.raise_for_status()
    user = response.json()

    return jsonify(
        {
            "valid": True,
            "user_id": user["id"],
            "name": user["name"],
            "role": user["role"],
        }
    )


@app.get("/users")
def list_users():
    try:
        response = requests.get(f"{DATABASE_SERVICE_URL}/users", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "Shared database unavailable", "detail": str(exc)}), 503

    return jsonify(response.json())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)