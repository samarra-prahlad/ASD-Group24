from flask import Flask, jsonify
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