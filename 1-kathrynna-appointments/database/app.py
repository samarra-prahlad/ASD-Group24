from flask import Flask, jsonify, request
import sqlite3

app = Flask(__name__)

DATABASE_NAME = "/app/data/appointments.db"

def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

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

# get appointments for a specific doctor
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

    #check if doctor exists
    doctor = conn.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,)).fetchone()

    if doctor is None:
        conn.close()
        return jsonify({"error": "Doctor not found"}), 404
    
    cursor = conn.execute("""
        INSERT INTO appointments (patient_id, doctor_id, date, time, status)
        VALUES (?, ?, ?, ?, ?)
    """, (patient_id, doctor_id, date, time, status))

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
    
    # Update fields
    patient_id = data.get("patient_id", appointment["patient_id"])
    doctor_id = data.get("doctor_id", appointment["doctor_id"])
    date = data.get("date", appointment["date"])
    time = data.get("time", appointment["time"])
    status = data.get("status", appointment["status"])

    # Check if doctor exists
    doctor = conn.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,)).fetchone()

    if doctor is None:
        conn.close()
        return jsonify({"error": "Doctor not found"}), 404

    conn.execute("""
        UPDATE appointments
        SET patient_id = ?, doctor_id = ?, date = ?, time = ?, status = ?
        WHERE id = ?
    """, (patient_id, doctor_id, date, time, status, appointment_id))

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

#run application 
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=6001,
        debug=True
    )