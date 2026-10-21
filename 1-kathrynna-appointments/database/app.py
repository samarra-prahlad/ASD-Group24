from flask import Flask, jsonify, request
import sqlite3

app = Flask(__name__)

import os
DATA_DIR = os.getenv("DATA_DIR", "/app/data")
DATABASE_NAME = os.path.join(DATA_DIR, "appointments.db")

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


#appointment change
def run_migrations():
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS appointment_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER NOT NULL,
            requested_date TEXT NOT NULL,
            requested_time TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TEXT,
            FOREIGN KEY (appointment_id) REFERENCES appointments(id)
        )
    """)
    conn.commit()
    conn.close()

run_migrations()



# Health check
@app.get("/")
def health():
    return jsonify({"service": "appointments-database", "status": "running"})

# Get all appointments
@app.get("/appointments")
def get_appointments():
    conn = get_db_connection()

    appointments = conn.execute("""
        SELECT
            appointments.id,
            appointments.patient_id,
            appointments.doctor_id,
            appointments.date,
            appointments.time,
            appointments.status,
            doctors.name AS doctor_name,
            doctors.specialty AS doctor_specialty
        FROM appointments
        LEFT JOIN doctors
            ON appointments.doctor_id = doctors.id
        ORDER BY appointments.date, appointments.time
    """).fetchall()

    conn.close()

    return jsonify([dict(row) for row in appointments])

# Get a single appointment
@app.get("/appointments/<int:appointment_id>")
def get_appointment(appointment_id):
    conn = get_db_connection()
    appointment = conn.execute("""
        SELECT
            appointments.id,
            appointments.patient_id,
            appointments.doctor_id,
            appointments.date,
            appointments.time,
            appointments.status,
            doctors.name AS doctor_name,
            doctors.specialty AS doctor_specialty
        FROM appointments
        LEFT JOIN doctors
            ON appointments.doctor_id = doctors.id
        WHERE appointments.id = ?
    """, (appointment_id,)).fetchone()

    conn.close()

    if appointment is None:
        return jsonify({"error": "Appointment not found"}), 404

    return jsonify(dict(appointment))

# Get appointments for a specific patient
@app.get("/appointments/patient/<int:patient_id>")
def get_appointments_by_patient(patient_id):
    conn = get_db_connection()
    appointments = conn.execute("""
        SELECT
            appointments.id,
            appointments.patient_id,
            appointments.doctor_id,
            appointments.date,
            appointments.time,
            appointments.status,
            doctors.name AS doctor_name,
            doctors.specialty AS doctor_specialty
        FROM appointments
        LEFT JOIN doctors
            ON appointments.doctor_id = doctors.id
        WHERE appointments.patient_id = ?
        ORDER BY appointments.date, appointments.time
    """, (patient_id,)).fetchall()

    conn.close()

    return jsonify([dict(row) for row in appointments])

# Get appointments for a specific doctor
@app.get("/appointments/doctor/<int:doctor_id>")
def get_appointments_by_doctor(doctor_id):

    conn = get_db_connection()
    appointments = conn.execute("""
        SELECT
            appointments.id,
            appointments.patient_id,
            appointments.doctor_id,
            doctors.name AS doctor_name,
            doctors.specialty AS doctor_specialty,
            appointments.date,
            appointments.time,
            appointments.status
        FROM appointments
        JOIN doctors
            ON appointments.doctor_id = doctors.id
        WHERE appointments.doctor_id = ?
        ORDER BY appointments.date, appointments.time
    """, (doctor_id,)).fetchall()

    conn.close()

    return jsonify([dict(row) for row in appointments])

#get appointments for a specific date (admin view)
@app.get("/appointments/date/<date>")
def get_appointments_by_date(date):
    conn = get_db_connection()
    appointments = conn.execute("""
        SELECT
            appointments.id,
            appointments.patient_id,
            appointments.doctor_id,
            appointments.date,
            appointments.time,
            appointments.status,
            doctors.name AS doctor_name,
            doctors.specialty AS doctor_specialty
        FROM appointments
        LEFT JOIN doctors
            ON appointments.doctor_id = doctors.id
        WHERE appointments.date = ?
        ORDER BY appointments.time
    """, (date,)).fetchall()
    conn.close()
    return jsonify([dict(row) for row in appointments])



# Create a new appointment
@app.post("/appointments")
def create_appointment():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid input"}), 400

    required_fields = ["patient_id", "doctor_id", "date", "time"]

    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"{field} is required"}), 400

    patient_id = data["patient_id"]
    doctor_id = data["doctor_id"]
    date = data["date"]
    time = data["time"]
    status = data.get("status", "scheduled")

    conn = get_db_connection()

    doctor = conn.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,)).fetchone()

    if doctor is None:
        conn.close()
        return jsonify({"error": "Doctor not found"}), 404

    try:
        cursor = conn.execute("""
            INSERT INTO appointments (patient_id, doctor_id, date, time, status)
            VALUES (?, ?, ?, ?, ?)
        """, (patient_id, doctor_id, date, time, status))
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "That slot has already been booked"}), 409

    appointment_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Appointment created successfully",
        "appointment_id": appointment_id
    }), 201

# Update an appointment
@app.put("/appointments/<int:appointment_id>")
def update_appointment(appointment_id):
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid input"}), 400

    conn = get_db_connection()
    appointment = conn.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone()

    if appointment is None:
        conn.close()
        return jsonify({"error": "Appointment not found"}), 404

    patient_id = data.get("patient_id", appointment["patient_id"])
    doctor_id = data.get("doctor_id", appointment["doctor_id"])
    date = data.get("date", appointment["date"])
    time = data.get("time", appointment["time"])
    status = data.get("status", appointment["status"])

    doctor = conn.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,)).fetchone()

    if doctor is None:
        conn.close()
        return jsonify({"error": "Doctor not found"}), 404

    try:
        conn.execute("""
            UPDATE appointments
            SET patient_id = ?, doctor_id = ?, date = ?, time = ?, status = ?
            WHERE id = ?
        """, (patient_id, doctor_id, date, time, status, appointment_id))
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "That slot has already been booked"}), 409

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Appointment updated",
        "appointment_id": appointment_id
    }), 200

# Delete an appointment
@app.delete("/appointments/<int:appointment_id>")
def delete_appointment(appointment_id):
    conn = get_db_connection()
    appointment = conn.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone()

    if appointment is None:
        conn.close()
        return jsonify({"error": "Appointment not found"}), 404

    conn.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": "Appointment deleted", "appointment_id": appointment_id})

# Get all doctors
@app.get("/doctors")
def get_doctors():
    conn = get_db_connection()
    doctors = conn.execute("""SELECT * FROM doctors ORDER BY name""").fetchall()
    conn.close()

    return jsonify([dict(row) for row in doctors])

# Get a single doctor
@app.get("/doctors/<int:doctor_id>")
def get_doctor(doctor_id):
    conn = get_db_connection()
    doctor = conn.execute("""SELECT * FROM doctors WHERE id = ?""", (doctor_id,)).fetchone()
    conn.close()

    if doctor is None:
        return jsonify({"error": "Doctor not found"}), 404

    return jsonify(dict(doctor))

# Get available doctors for a specialty and date
@app.get("/availability")
def get_availability():
    specialty = request.args.get("specialty")
    date = request.args.get("date")

    if not specialty or not date:
        return jsonify({
            "error": "Both 'specialty' and 'date' are required"
        }), 400

    conn = get_db_connection()

    doctors = conn.execute("""
        SELECT
            doctors.id,
            doctors.name,
            doctors.specialty,
            doctors.availability
        FROM doctors
        WHERE TRIM(doctors.specialty) = TRIM(?) COLLATE NOCASE
        ORDER BY doctors.name
    """, (specialty,)).fetchall()

    booked = conn.execute("""
        SELECT
            doctor_id,
            time
        FROM appointments
        WHERE date = ?
    """, (date,)).fetchall()

    conn.close()

    booked_slots = {
        (row["doctor_id"], row["time"])
        for row in booked
    }

    available = []

    for doctor in doctors:
        available.append({
            "doctor_id": doctor["id"],
            "doctor_name": doctor["name"],
            "specialty": doctor["specialty"],
            "availability": doctor["availability"],
            "booked_times": [
                time
                for doctor_id, time in booked_slots
                if doctor_id == doctor["id"]
            ]
        })

    return jsonify({
        "specialty": specialty,
        "date": date,
        "doctors": available
    })


#appointment change request endpoint (used by patient)
@app.post("/appointment-changes")
def create_appointment_change():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid input"}), 400

    appointment_id = data.get("appointment_id")
    requested_date = data.get("requested_date")
    requested_time = data.get("requested_time")

    if not appointment_id or not requested_date or not requested_time:
        return jsonify({"error": "appointment_id, requested_date and requested_time are required"}), 400

    conn = get_db_connection()
    appointment = conn.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
    if appointment is None:
        conn.close()
        return jsonify({"error": "Appointment not found"}), 404

    existing = conn.execute(
        "SELECT id FROM appointment_changes WHERE appointment_id = ? AND status = 'pending'",
        (appointment_id,)
    ).fetchone()
    if existing:
        conn.close()
        return jsonify({"error": "A change request is already pending for this appointment"}), 409

    cursor = conn.execute("""
        INSERT INTO appointment_changes (appointment_id, requested_date, requested_time, status)
        VALUES (?, ?, ?, 'pending')
    """, (appointment_id, requested_date, requested_time))
    change_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({"message": "Change request submitted", "change_id": change_id}), 201


#appointment change retrieval endpoint (used by admin queue)
@app.get("/appointment-changes")
def get_appointment_changes():
    status = request.args.get("status")
    conn = get_db_connection()

    query = """
        SELECT
            appointment_changes.id,
            appointment_changes.appointment_id,
            appointment_changes.requested_date,
            appointment_changes.requested_time,
            appointment_changes.status,
            appointment_changes.created_at,
            appointments.date AS current_date,
            appointments.time AS current_time,
            appointments.patient_id,
            doctors.name AS doctor_name,
            doctors.specialty AS doctor_specialty
        FROM appointment_changes
        JOIN appointments ON appointment_changes.appointment_id = appointments.id
        JOIN doctors ON appointments.doctor_id = doctors.id
    """
    params = ()
    if status:
        query += " WHERE appointment_changes.status = ?"
        params = (status,)
    query += " ORDER BY appointment_changes.created_at"

    changes = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(row) for row in changes])


#appintment change approval/rejection endpoint (used by admin queue)
@app.put("/appointment-changes/<int:change_id>")
def update_appointment_change(change_id):
    data = request.get_json()
    if not data or data.get("status") not in ("approved", "rejected"):
        return jsonify({"error": "status must be 'approved' or 'rejected'"}), 400

    new_status = data["status"]
    conn = get_db_connection()
    change = conn.execute("SELECT * FROM appointment_changes WHERE id = ?", (change_id,)).fetchone()

    if change is None:
        conn.close()
        return jsonify({"error": "Change request not found"}), 404
    if change["status"] != "pending":
        conn.close()
        return jsonify({"error": "This change request has already been reviewed"}), 409

    if new_status == "approved":
        conflict = conn.execute("""
            SELECT a.id FROM appointments a
            WHERE a.doctor_id = (SELECT doctor_id FROM appointments WHERE id = ?)
              AND a.date = ? AND a.time = ? AND a.id != ?
        """, (change["appointment_id"], change["requested_date"], change["requested_time"], change["appointment_id"])).fetchone()

        if conflict:
            conn.close()
            return jsonify({"error": "That slot has since been booked by someone else"}), 409

        try:
            conn.execute("UPDATE appointments SET date = ?, time = ? WHERE id = ?",
                          (change["requested_date"], change["requested_time"], change["appointment_id"]))
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({"error": "That slot has since been booked by someone else"}), 409

    conn.execute("UPDATE appointment_changes SET status = ?, reviewed_at = CURRENT_TIMESTAMP WHERE id = ?",
                 (new_status, change_id))
    conn.commit()
    conn.close()
    return jsonify({"message": f"Change request {new_status}"}), 200


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",  # nosec B104 - required inside the container
        port=6001,
        debug=os.getenv("FLASK_DEBUG") == "1",
    )