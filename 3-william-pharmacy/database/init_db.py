import os
import sqlite3

database_path = os.environ.get(
    "DATABASE_PATH",
    "../database/pharmacy.db"
)

conn = sqlite3.connect(database_path)

cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS medications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        stock INTEGER NOT NULL DEFAULT 0,
        unit_price REAL NOT NULL
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS prescriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        medication_id INTEGER NOT NULL,
        dosage TEXT NOT NULL,
        prescribing_doctor TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (medication_id) REFERENCES medications(id)
    )
''')

conn.commit()

# Populate DB with data

cursor.execute('SELECT COUNT(*) FROM medications')
if cursor.fetchone()[0] == 0:
    medications = [
        ('Amoxicillin 500mg',      120, 0.35),
        ('Ibuprofen 200mg',        300, 0.10),
        ('Lisinopril 10mg',        150, 0.22),
        ('Metformin 500mg',        200, 0.15),
        ('Atorvastatin 20mg',      180, 0.40),
        ('Amlodipine 5mg',         140, 0.18),
        ('Omeprazole 20mg',        160, 0.25),
        ('Levothyroxine 50mcg',    100, 0.20),
        ('Albuterol Inhaler',       60, 12.50),
        ('Cetirizine 10mg',        250, 0.08),
    ]
    cursor.executemany(
        'INSERT INTO medications (name, stock, unit_price) VALUES (?, ?, ?)',
        medications
    )
    conn.commit()
    print(f"Inserted {len(medications)} medications.")
else:
    print("medications table already has data — skipping.")
 
cursor.execute('SELECT id FROM medications ORDER BY id')
med_ids = [row[0] for row in cursor.fetchall()]
 
cursor.execute('SELECT COUNT(*) FROM prescriptions')
if cursor.fetchone()[0] == 0:
    prescriptions = [
        (1001, med_ids[0], '500mg twice daily',        'Dr. Sarah Chen',      'active'),
        (1002, med_ids[1], '200mg every 6 hours',       'Dr. James Patel',     'active'),
        (1003, med_ids[2], '10mg once daily',           'Dr. Sarah Chen',      'active'),
        (1004, med_ids[3], '500mg twice daily',         'Dr. Maria Gonzalez',  'completed'),
        (1005, med_ids[4], '20mg once daily at night',  'Dr. James Patel',     'active'),
        (1006, med_ids[5], '5mg once daily',            'Dr. Ahmed Hassan',    'active'),
        (1007, med_ids[6], '20mg once daily',           'Dr. Maria Gonzalez',  'cancelled'),
        (1008, med_ids[7], '50mcg once daily',          'Dr. Sarah Chen',      'active'),
        (1009, med_ids[8], '2 puffs as needed',         'Dr. Ahmed Hassan',    'active'),
        (1010, med_ids[9], '10mg once daily',           'Dr. James Patel',     'completed'),
    ]
    cursor.executemany(
        '''INSERT INTO prescriptions (patient_id, medication_id, dosage, prescribing_doctor, status)
           VALUES (?, ?, ?, ?, ?)''',
        prescriptions
    )
    conn.commit()
    print(f"Inserted {len(prescriptions)} prescriptions.")
else:
    print("prescriptions table already has data — skipping.")
 
conn.close()