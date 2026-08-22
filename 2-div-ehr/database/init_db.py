import os
import sqlite3

database_path = os.environ.get(
"DATABASE_PATH",
"/app/data/ehr.db"
)

os.makedirs(os.path.dirname(database_path), exist_ok=True)

conn = sqlite3.connect(database_path)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS medical_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    visit_date TEXT,
    diagnosis TEXT,
    doctor_name TEXT,
    treatment TEXT,
    notes TEXT,
    allergies TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS change_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    request_type TEXT NOT NULL,
    request_details TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()

cursor.execute("SELECT COUNT(*) FROM medical_records")
if cursor.fetchone()[0] == 0:
    medical_records = [
        (101, '2026-06-10', 'Type 2 Diabetes',    'Dr. Sarah Chen',  'Metformin 500mg twice daily',                                                       'Routine follow-up, A1C stable',                     'Penicillin (rash, moderate)'),
        (102, '2026-07-02', 'Hypertension',       'Dr. James Patel', 'Lisinopril 10mg once daily',                                                        'Prescribed lifestyle changes, recheck in 3 months', 'Peanuts (anaphylaxis, severe)'),
        (101, '2026-08-01', 'Diabetes follow-up', 'Dr. Sarah Chen',  'Continue Metformin 500mg twice daily; start Atorvastatin 20mg once daily at night', 'A1C improved, continue current dosage',             'Penicillin (rash, moderate)'),
    ]
    cursor.executemany("""
    INSERT INTO medical_records (patient_id, visit_date, diagnosis, doctor_name, treatment, notes, allergies)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, medical_records)

    conn.commit()
    print (f"Inserted {len(medical_records)} medical records.")
else:
    print("Medical records already exist.")

conn.close()