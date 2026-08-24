import os
import sqlite3

DATA_DIR = os.environ.get("DB_DATA_DIR", "/app/data")
DATABASE_NAME = os.path.join(DATA_DIR, "billing.db")

os.makedirs(DATA_DIR, exist_ok=True)

conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()

# Insurance providers table
cursor.execute("""
CREATE TABLE IF NOT EXISTS insurance_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    plan_type TEXT NOT NULL,
    coverage_percentage INTEGER NOT NULL,
    contact_number TEXT
)
""")

# Invoices table
cursor.execute("""
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    insurance_provider_id INTEGER,
    appointment_cost REAL NOT NULL DEFAULT 0,
    medication_cost REAL NOT NULL DEFAULT 0,
    bed_charges REAL NOT NULL DEFAULT 0,
    total_amount REAL NOT NULL,
    insurance_covered_amount REAL NOT NULL DEFAULT 0,
    patient_owed_amount REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    date TEXT NOT NULL,
    FOREIGN KEY (insurance_provider_id) REFERENCES insurance_providers (id)
)
""")

# Sample insurance providers
sample_insurance_providers = [
    (301, "Medibank", "Basic", 60, "13 23 31"),
    (302, "Medibank", "Premium", 85, "13 23 31"),
    (303, "Bupa", "Basic", 65, "13 41 35"),
    (304, "Bupa", "Premium", 90, "13 41 35"),
    (305, "HCF", "Standard", 70, "13 13 34"),
    (306, "NIB", "Basic", 60, "13 14 63"),
    (307, "NIB", "Premium", 80, "13 14 63"),
    (308, "Australian Unity", "Standard", 70, "13 29 39"),
    (309, "AHM", "Basic", 55, "13 42 46"),
    (310, "Medicare", "Public", 100, "13 20 11"),
]
cursor.executemany(
    "INSERT OR IGNORE INTO insurance_providers (id, name, plan_type, coverage_percentage, contact_number) VALUES (?, ?, ?, ?, ?)",
    sample_insurance_providers,
)

# Sample invoices
# total_amount = appointment_cost + medication_cost + bed_charges
# insurance_covered_amount = total_amount * (coverage_percentage / 100), rounded to 2dp
# patient_owed_amount = total_amount - insurance_covered_amount
sample_invoices = [
    (1, 101, 301, 150.00, 45.00, 0.00, 195.00, 117.00, 78.00, "pending", "2026-08-15"),
    (2, 102, 303, 120.00, 0.00, 0.00, 120.00, 78.00, 42.00, "paid", "2026-06-26"),
    (3, 101, 302, 150.00, 60.00, 800.00, 1010.00, 858.50, 151.50, "pending", "2026-09-17"),
    (4, 102, None, 180.00, 30.00, 0.00, 210.00, 0.00, 210.00, "pending", "2026-09-18"),
    (5, 101, 305, 150.00, 0.00, 400.00, 550.00, 385.00, 165.00, "partially_paid", "2026-09-19"),
    (6, 103, 304, 200.00, 90.00, 0.00, 290.00, 261.00, 29.00, "paid", "2026-07-02"),
    (7, 104, 306, 150.00, 25.00, 0.00, 175.00, 105.00, 70.00, "pending", "2026-07-05"),
    (8, 105, 310, 150.00, 15.00, 1200.00, 1365.00, 1365.00, 0.00, "paid", "2026-07-10"),
    (9, 103, 308, 120.00, 0.00, 0.00, 120.00, 84.00, 36.00, "pending", "2026-08-01"),
    (10, 106, 307, 150.00, 50.00, 600.00, 800.00, 640.00, 160.00, "partially_paid", "2026-08-12"),
    (11, 104, None, 90.00, 0.00, 0.00, 90.00, 0.00, 90.00, "pending", "2026-08-20"),
    (12, 106, 309, 150.00, 20.00, 0.00, 170.00, 93.50, 76.50, "paid", "2026-08-22"),
]
cursor.executemany(
    "INSERT OR IGNORE INTO invoices (id, patient_id, insurance_provider_id, appointment_cost, medication_cost, bed_charges, total_amount, insurance_covered_amount, patient_owed_amount, status, date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    sample_invoices,
)

conn.commit()
conn.close()

print("Billing database initialized.")