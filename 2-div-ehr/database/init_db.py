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
        (3,  '2026-06-10', 'Type 2 Diabetes',    'Dr. Sarah Chen',   'Metformin 500mg twice daily',                                                       'Routine follow-up, A1C stable',                     'Penicillin (rash, moderate)'),
        (4,  '2026-07-02', 'Hypertension',       'Dr. James Patel',  'Lisinopril 10mg once daily',                                                        'Prescribed lifestyle changes, recheck in 3 months', 'Peanuts (anaphylaxis, severe)'),
        (3,  '2026-08-01', 'Diabetes follow-up', 'Dr. Sarah Chen',   'Continue Metformin 500mg twice daily; start Atorvastatin 20mg once daily at night', 'A1C improved, continue current dosage',             'Penicillin (rash, moderate)'),
        (5,  '2026-06-15', 'Seasonal Allergies', 'Dr. Emily Rossi',  'Cetirizine 10mg once daily as needed',                                              'Symptoms well controlled',                          'None reported'),
        (6,  '2026-05-22', 'Migraine',           'Dr. James Patel',  'Sumatriptan 50mg at onset of symptoms',                                             'Frequency reduced since last visit',                'Sulfa drugs (hives)'),
        (7,  '2026-07-18', 'Asthma',             'Dr. Sarah Chen',   'Salbutamol inhaler as needed, Fluticasone daily',                                   'Peak flow stable, no recent flare-ups',             'Dust mites (mild)'),
        (8,  '2026-08-05', 'Anxiety',            'Dr. Emily Rossi',  'Sertraline 50mg once daily',                                                        'Reports improved sleep and mood',                   'None reported'),
        (9,  '2026-04-30', 'Lower Back Pain',    'Dr. James Patel',  'Physiotherapy twice weekly, Ibuprofen 400mg as needed',                             'Mobility improving, continue physio',               'None reported'),
        (10, '2026-07-27', 'Eczema',             'Dr. Sarah Chen',   'Hydrocortisone cream 1% twice daily',                                               'Flare-up subsiding',                                'Latex (contact dermatitis)'),
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