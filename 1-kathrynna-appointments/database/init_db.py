import os
import sqlite3

DATA_DIR = "/app/data"
DATABASE_NAME = os.path.join(DATA_DIR, "appointments.db")

os.makedirs(DATA_DIR, exist_ok=True)

conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()

# Doctors table 
cursor.execute("""
CREATE TABLE IF NOT EXISTS doctors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    specialty TEXT NOT NULL,
    availability TEXT
)
""")

# Appointment table 
cursor.execute("""
CREATE TABLE IF NOT EXISTS appointments(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    doctor_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled',
    FOREIGN KEY (doctor_id) REFERENCES doctors (id)
)
""")

# Sample Doctors 
sample_doctors = [
    (201, "Dr. John Smith", "Cardiology", "Mon-Fri 09:00-17:00"),
    (202, "Dr. Emily Johnson", "Dermatology", "Tue-Thu 10:00-16:30"),
    (203, "Dr. Michael Brown", "General Practice", "Mon-Wed 08:00-15:00"),
    (204, "Dr. Sarah Davis", "Pediatrics", "Mon-Fri 09:00-17:00"),
    (205, "Dr. William Wilson", "Psychiatry", "Tue-Fri 10:00-18:00"),
]

cursor.executemany(
    "INSERT OR IGNORE INTO doctors (id, name, specialty, availability) VALUES (?, ?, ?, ?)",
    sample_doctors,
)

# Sample Appointments
sample_appointments = [
    (1, 101, 201, "2026-08-15", "10:00", "scheduled"),
    (2, 102, 202, "2026-06-26", "11:30", "scheduled"),
    (3, 101, 203, "2026-09-17", "14:00", "scheduled"),
    (4, 102, 204, "2026-09-18", "09:30", "scheduled"),
    (5, 101, 205, "2026-09-19", "15:00", "scheduled"),
]

cursor.executemany(
    "INSERT OR IGNORE INTO appointments (id, patient_id, doctor_id, date, time, status) VALUES (?, ?, ?, ?, ?, ?)",
    sample_appointments,
)

# save changes and close the connection
conn.commit()
conn.close()

print("Appointments database initialized.")