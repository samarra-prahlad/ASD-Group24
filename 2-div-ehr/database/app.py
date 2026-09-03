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

#---Medical_Records---

# READ
@app.get("/records/<int:patient_id>")
def get_records(patient_id):
    db = get_db()
    records = db.execute(
        "SELECT * FROM medical_records WHERE patient_id = ? ORDER BY visit_date DESC",
        (patient_id,)
    ).fetchall()
    db.close()
    return jsonify([dict(record) for record in records])

# CREATE
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


# UPDATE
@app.put("/records/<int:record_id>")
def update_record(record_id):
    data = request.get_json()
    db = get_db()
    db.execute("""
        UPDATE medical_records
        SET visit_date = ?, diagnosis = ?, doctor_name = ?, treatment = ?, notes = ?, allergies = ?
        WHERE id = ?""",
        (
            data.get("visit_date"),
            data.get("diagnosis"),
            data.get("doctor_name"),
            data.get("treatment"),
            data.get("notes"),
            data.get("allergies"),
            record_id,
        )
    )
    db.commit()
    db.close()
    return jsonify({"message": "Record updated successfully"})

# DELETE
@app.delete("/records/<int:record_id>")
def delete_record(record_id):
    db = get_db()
    db.execute("DELETE FROM medical_records WHERE id = ?", (record_id,))
    db.commit()
    db.close()
    return jsonify({"message": "Record deleted successfully"})

#---Change_Requests---

# READ
@app.get("/change_requests")
def get_change_requests():
    db = get_db()
    requests = db.execute(
        "SELECT * FROM change_requests ORDER BY created_at DESC",
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in requests])

@app.get("/change_requests/<int:patient_id>")
def get_patient_change_requests(patient_id):
    db = get_db()
    requests = db.execute(
        "SELECT * FROM change_requests WHERE patient_id = ? ORDER BY created_at DESC",
        (patient_id,)
    ).fetchall()
    db.close()
    return jsonify([dict(r) for r in requests])

# CREATE
@app.post("/change_requests")
def create_change_request():
    data = request.get_json()
    db = get_db()
    cursor = db.execute("""
        INSERT INTO change_requests (patient_id, request_type, request_details)
        VALUES (?, ?, ?)""",
        (
            data["patient_id"],
            data["request_type"],
            data.get("request_details"),
        )
    )
    db.commit()
    new_id = cursor.lastrowid
    db.close()
    return jsonify({"id": new_id}), 201

# UPDATE
@app.put("/change_requests/<int:request_id>")
def update_change_request(request_id):
    data = request.get_json()
    db = get_db()
    db.execute("""
        UPDATE change_requests
        SET status = ?
        WHERE id = ?""",
        (data["status"], request_id)
    )
    db.commit()
    db.close()
    return jsonify({"message": "Change request updated successfully"})
            

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6002, debug=True)

                       