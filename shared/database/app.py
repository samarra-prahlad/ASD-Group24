import os
import sqlite3
from flask import Flask, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash

DB_DATA_DIR = os.environ.get("DB_DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
DB_PATH = os.path.join(DB_DATA_DIR, "shared.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    address TEXT NOT NULL,
    email_address TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    phone_number TEXT NOT NULL,
    emergency_contact_number TEXT NOT NULL
);
"""

ADMIN_EMAIL_SUFFIX = "@admin.com"

REQUIRED_FIELDS = [
    "first_name", "last_name", "address", "email_address",
    "password", "phone_number", "emergency_contact_number",
]

UPDATABLE_FIELDS = [
    "first_name", "last_name", "address", "email_address",
    "phone_number", "emergency_contact_number", "password",
]

app = Flask(__name__)


def get_connection():
    os.makedirs(DB_DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute(SCHEMA)
    conn.commit()
    conn.close()


def role_from_email(email):
    return "admin" if email.lower().endswith(ADMIN_EMAIL_SUFFIX) else "patient"


def patient_to_dict(row):
    return {
        "patient_id": row["patient_id"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "address": row["address"],
        "email_address": row["email_address"],
        "phone_number": row["phone_number"],
        "emergency_contact_number": row["emergency_contact_number"],
    }


@app.get("/patients")
def get_patients():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM patients").fetchall()
    conn.close()
    return jsonify([patient_to_dict(r) for r in rows])


@app.get("/patients/<int:patient_id>")
def get_patient(patient_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,)).fetchone()
    conn.close()
    if row is None:
        return jsonify({"error": "Patient not found"}), 404
    return jsonify(patient_to_dict(row))


@app.post("/patients")
def create_patient():
    data = request.get_json() or {}
    missing = [f for f in REQUIRED_FIELDS if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO patients
            (first_name, last_name, address, email_address, password, phone_number, emergency_contact_number)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["first_name"],
                data["last_name"],
                data["address"],
                data["email_address"],
                generate_password_hash(data["password"]),
                data["phone_number"],
                data["emergency_contact_number"],
            ),
        )
        conn.commit()
        new_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "Email address already registered"}), 409

    row = conn.execute("SELECT * FROM patients WHERE patient_id = ?", (new_id,)).fetchone()
    conn.close()
    return jsonify(patient_to_dict(row)), 201


@app.put("/patients/<int:patient_id>")
def update_patient(patient_id):
    data = request.get_json() or {}
    conn = get_connection()
    row = conn.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,)).fetchone()
    if row is None:
        conn.close()
        return jsonify({"error": "Patient not found"}), 404

    updates = {k: v for k, v in data.items() if k in UPDATABLE_FIELDS}
    if "password" in updates:
        updates["password"] = generate_password_hash(updates["password"])

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [patient_id]
        conn.execute(f"UPDATE patients SET {set_clause} WHERE patient_id = ?", values)
        conn.commit()

    row = conn.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,)).fetchone()
    conn.close()
    return jsonify(patient_to_dict(row)), 200


@app.delete("/patients/<int:patient_id>")
def delete_patient(patient_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,)).fetchone()
    if row is None:
        conn.close()
        return jsonify({"error": "Patient not found"}), 404

    conn.execute("DELETE FROM patients WHERE patient_id = ?", (patient_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Patient deleted"}), 200


@app.post("/patients/verify")
def verify_patient():
    data = request.get_json() or {}
    email = data.get("email_address")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "email_address and password are required"}), 400

    conn = get_connection()
    row = conn.execute("SELECT * FROM patients WHERE email_address = ?", (email,)).fetchone()
    conn.close()

    if row is None or not check_password_hash(row["password"], password):
        return jsonify({"error": "Invalid credentials"}), 401

    return jsonify({
        "patient_id": row["patient_id"],
        "first_name": row["first_name"],
        "role": role_from_email(row["email_address"]),
    }), 200


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=6000, debug=True)