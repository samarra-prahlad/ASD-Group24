import os
import sqlite3

DATA_DIR = "/app/data"
DATABASE_NAME = os.path.join(DATA_DIR, "appointments.db")

os.makedirs(DATA_DIR, exist_ok=True)

conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS doctors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    specialty TEXT NOT NULL,
    availability TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS appointments(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    doctor_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled',
    FOREIGN KEY (doctor_id) REFERENCES doctors (id),
    UNIQUE (doctor_id, date, time)
)
""")



sample_doctors = [
    (201, "Dr. John Smith", "Cardiology", "Mon-Fri 09:00-17:00"),
    (202, "Dr. Emily Johnson", "Dermatology", "Tue-Thu 10:00-16:30"),
    (203, "Dr. Michael Brown", "General Practice", "Mon-Wed 08:00-15:00"),
    (204, "Dr. Sarah Davis", "Pediatrics", "Mon-Fri 09:00-17:00"),
    (205, "Dr. William Wilson", "Psychiatry", "Tue-Fri 10:00-18:00"),
    (206, "Dr. Olivia Martinez", "General Practice", "Mon-Thu 09:00-16:00"),
    (207, "Dr. James Anderson", "Orthopedics", "Mon-Fri 08:30-17:00"),
    (208, "Dr. Isabella Thomas", "Physiotherapy", "Mon-Wed 09:00-15:30"),
    (209, "Dr. Benjamin Taylor", "Endocrinology", "Tue-Fri 10:00-17:00"),
    (210, "Dr. Sophia Moore", "Geriatrics", "Mon-Thu 08:00-14:30"),
    (211, "Dr. Grace Lee", "Neurology", "Mon-Fri 09:00-16:00"),
]

cursor.executemany(
    "INSERT OR IGNORE INTO doctors (id, name, specialty, availability) VALUES (?, ?, ?, ?)",
    sample_doctors,
)

# Sample Appointments
sample_appointments = [
    (101, 1, 201, "2026-08-15", "10:00", "scheduled"),
    (102, 2, 202, "2026-06-26", "11:30", "scheduled"),
    (103, 3, 203, "2026-09-17", "14:00", "scheduled"),
    (104, 2, 204, "2026-09-18", "09:30", "scheduled"),
    (105, 4, 205, "2026-09-15", "15:00", "scheduled"),
    (106, 4, 205, "2026-09-15", "14:00", "scheduled"),
    (107, 6, 205, "2026-09-16", "15:00", "scheduled"),
    (108, 7, 204, "2026-09-16", "16:00", "scheduled"),
    (109, 7, 202, "2026-09-15", "10:00", "scheduled"),
    (110, 6, 210, "2026-09-17", "12:00", "scheduled"),
    (111, 7, 210, "2026-09-17", "15:00", "scheduled"),
    (112, 1, 211, "2026-09-18", "14:00", "scheduled"),
    (113, 3, 211, "2026-09-18", "13:00", "scheduled"),
]

cursor.executemany(
    "INSERT OR IGNORE INTO appointments (id, patient_id, doctor_id, date, time, status) VALUES (?, ?, ?, ?, ?, ?)",
    sample_appointments,
)

conn.commit()
conn.close()

print("Appointments database initialized.")