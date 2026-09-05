import os
import sqlite3
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

DATABASE_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "data", "ward.db"))

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

#this gets all the wards in the db
@app.get("/wards")
def get_wards():
    conn = get_db()

    wards = conn.execute("""
        SELECT ward_id, ward_name, capacity
        FROM wards
    """).fetchall()

    conn.close()

    return jsonify([dict(ward) for ward in wards])

@app.get("/wards/<int:ward_id>")
def get_ward(ward_id):
    conn = get_db()

    ward = conn.execute("""
        SELECT ward_id, ward_name, capacity
        FROM wards
        WHERE ward_id = ?
    """, (ward_id,)).fetchone()

    conn.close()

    if ward is None:
        return jsonify({"error": "Ward not found"}), 404

    return jsonify(dict(ward))

#this gets every bed in th specific ward
@app.get("/wards/<int:ward_id>/beds")
def get_beds_by_ward(ward_id):
    conn = get_db()

    ward = conn.execute("""
        SELECT ward_id
        FROM wards
        WHERE ward_id = ?
    """, (ward_id,)).fetchone()

    if ward is None:
        conn.close()
        return jsonify({"error": "Ward not found"}), 404

    beds = conn.execute("""
        SELECT bed_id, ward_id, patient_id, bed_number, status
        FROM beds
        WHERE ward_id = ?
    """, (ward_id,)).fetchall()

    conn.close()

    return jsonify([dict(bed) for bed in beds])

@app.put("/beds/<int:bed_id>/assign")
def assign_patient(bed_id):
    data = request.get_json()

    patient_id = data.get("patient_id")

    if patient_id is None:
        return jsonify({"error": "patient_id is required"}), 400

    conn = get_db()
    #bed validation
    bed = conn.execute("""
        SELECT bed_id, patient_id, status
        FROM beds
        WHERE bed_id = ?
    """, (bed_id,)).fetchone()

    if bed is None:
        conn.close()
        return jsonify({"error": "Bed not found"}), 404

    if bed["patient_id"] is not None:
        conn.close()
        return jsonify({"error": "Bed is already occupied"}), 409

    conn.execute("""
        UPDATE beds
        SET patient_id = ?, status = 'occupied'
        WHERE bed_id = ?
    """, (patient_id, bed_id))

    assignment = conn.execute("""
        INSERT INTO bed_assignments (
            bed_id,
            patient_id
        )
        VALUES (?, ?)
        RETURNING assignment_id, bed_id, patient_id, date_assigned, date_released
    """, (bed_id, patient_id)).fetchone()

    conn.commit()
    conn.close()

    raw_time = assignment["date_released"]

    readable_time = datetime.strptime(
        raw_time,
        "%Y-%m-%d %H:%M:%S"
    ).strftime("%d/%m/%Y %I:%M %p")

    return jsonify({
        "message": f"Patient {patient_id} has succesfully been assigned to bed {bed_id} at {readable_time}",
        "bed_id": bed_id,
        "patient_id": patient_id,
        "date_assigned" : assignment["date_assigned"]
    })

@app.put("/beds/<int:bed_id>/release")
def release_bed(bed_id):
    conn = get_db()

    bed = conn.execute("""
        SELECT bed_id, patient_id, status
        FROM beds
        WHERE bed_id = ?
    """, (bed_id,)).fetchone()

    if bed is None:
        conn.close()
        return jsonify({"error": "Bed not found"}), 404

    if bed["patient_id"] is None:
        conn.close()
        return jsonify({"error": "Bed is already available"}), 409

    patient_id = bed["patient_id"]

    conn.execute("""
        UPDATE beds
        SET patient_id = NULL,
            status = 'available'
        WHERE bed_id = ?
    """, (bed_id,))

    conn.execute("""
        UPDATE bed_assignments
        SET date_released = CURRENT_TIMESTAMP
        WHERE bed_id = ?
        AND patient_id = ?
        AND date_released IS NULL
    """, (bed_id, patient_id))

    conn.commit()
    conn.close()

    return jsonify({
        "message": f"Patient {patient_id} has successfully been removed from bed {bed_id}"
    })

@app.get("/patients/<int:patient_id>/assignments")
def get_patient_bed_history(patient_id):
    conn = get_db()

    assignments = conn.execute("""
        SELECT
            assignment_id,
            bed_id,
            patient_id,
            date_assigned,
            COALESCE(date_released, 'Currently occupied') AS date_released
        FROM bed_assignments
        WHERE patient_id = ?
        ORDER BY date_assigned DESC
    """, (patient_id,)).fetchall()

    conn.close()

    return jsonify([dict(row) for row in assignments]), 200


@app.get("/patients/<int:patient_id>/bed")
def get_patient_bed(patient_id):
    conn = get_db()

    bed = conn.execute("""
        SELECT bed_id, ward_id, patient_id, bed_number, status
        FROM beds
        WHERE patient_id = ?
    """, (patient_id,)).fetchone()

    conn.close()

    if bed is None:
        return jsonify({"error": "Patient is not assigned to a bed"}), 404

    return jsonify(dict(bed))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6006, debug=True)    