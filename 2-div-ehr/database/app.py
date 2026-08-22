import os
import sqlite3

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DATABASE_PATH = os.environ.get("DATABASE_PATH", "/app/data/ehr.db")

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/records/<int:patient_id>")
def get_records(patient_id):
    db = get_db()
    records = db.execute(
        "SELECT * FROM medical_records WHERE patient_id = ? ORDER BY visit_date DESC",
        (patient_id,)
    ).fetchall()
    db.close()
    return jsonify([dict(record) for record in records])


@app.post("/records")
def create_record():
    data = request.get_json()
    db = get_db()
    cursor = db.execute("""
        INSERT INTO medical_records (patient_id, visit_date, diagnosis, doctor_name, treatment, notes, allergies)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            data["patient_id"],
            data.get("visit_date"),
            data.get("diagnosis"),
            data.get("doctor_name"),
            data.get("treatment"),
            data.get("notes"),
            data.get("allergies"),
        )
    )
    db.commit()
    new_id = cursor.lastrowid
    db.close()
    return jsonify({"id": new_id}), 201

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6002, debug=True)

                       