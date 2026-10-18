import os
import sqlite3

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
os.makedirs(DATA_DIR, exist_ok=True)
conn = sqlite3.connect(os.path.join(DATA_DIR, "labtests.db"))
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS lab_orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    test_type TEXT NOT NULL,
    ordered_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now'))
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS lab_results (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    result_value TEXT NOT NULL,
    reference_range TEXT NOT NULL,
    flagged INTEGER DEFAULT 0,
    ai_notes TEXT,
    recorded_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (order_id) REFERENCES lab_orders(order_id)
)
""")

# Only seed sample data if the table is empty — prevents duplicates on every restart
c.execute("SELECT COUNT(*) FROM lab_orders")
if c.fetchone()[0] == 0:
    sample_orders = [
        (1, 'Complete Blood Count', 'Dr. Nguyen', 'completed'),
        (2, 'Lipid Panel', 'Dr. Osei', 'completed'),
        (3, 'Thyroid Function Test', 'Dr. Nguyen', 'in_progress'),
        (4, 'Blood Glucose', 'Dr. Patel', 'completed'),
        (5, 'Liver Function Test', 'Dr. Osei', 'pending'),
        (6, 'Urinalysis', 'Dr. Patel', 'completed'),
        (7, 'Chest X-Ray', 'Dr. Nguyen', 'completed'),
        (8, 'Complete Blood Count', 'Dr. Osei', 'pending'),
        (9, 'HbA1c', 'Dr. Patel', 'completed'),
        (10, 'Electrolyte Panel', 'Dr. Nguyen', 'in_progress'),
    ]
    c.executemany(
        "INSERT INTO lab_orders (patient_id, test_type, ordered_by, status) VALUES (?, ?, ?, ?)",
        sample_orders
    )

    sample_results = [
    (1, 'WBC 11.2 x10^9/L', '4.0-11.0 x10^9/L', 1),
    (2, 'LDL 145 mg/dL', '<100 mg/dL', 1),
    (3, 'TSH 3.1 mIU/L', '0.4-4.0 mIU/L', 0),
    (4, 'Glucose 92 mg/dL', '70-100 mg/dL', 0),
    (5, 'ALT 65 U/L', '7-56 U/L', 1),
    (6, 'Protein: negative', 'negative', 0),
    (7, 'No acute findings', 'N/A', 0),
    (8, 'WBC 9.8 x10^9/L', '4.0-11.0 x10^9/L', 0),
    (9, 'HbA1c 5.4%', '4.0-5.6%', 0),
    (10, 'Sodium 148 mmol/L', '135-145 mmol/L', 1),
    ]

    c.executemany(
        "INSERT INTO lab_results (order_id, result_value, reference_range, flagged) VALUES (?, ?, ?, ?)",
        sample_results
    )
    print("Sample data inserted.")
else:
    print("Table already has data — skipping seed.")

conn.commit()
conn.close()