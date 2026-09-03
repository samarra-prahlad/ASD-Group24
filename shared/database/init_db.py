import os
import sqlite3
from werkzeug.security import generate_password_hash

DB_DATA_DIR = os.environ.get("DB_DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
DB_PATH = os.path.join(DB_DATA_DIR, "shared.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    address TEXT NOT NULL,
    email_address TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    phone_number TEXT NOT NULL,
    emergency_contact_number TEXT NOT NULL
);
"""

# Plaintext passwords here — hashed before insertion.
# Emails ending in @admin.com are treated as admin role; everything else is patient.
SEED_PATIENTS = [
    {
        "first_name": "Grace",
        "last_name": "Hopper",
        "address": "1 Compiler Lane, Sydney NSW",
        "email_address": "grace.hopper@admin.com",
        "password": "AdminPass123!",
        "phone_number": "0400000001",
        "emergency_contact_number": "0400000101",
    },
    {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "address": "2 Analytical Ave, Sydney NSW",
        "email_address": "ada.lovelace@admin.com",
        "password": "AdminPass456!",
        "phone_number": "0400000002",
        "emergency_contact_number": "0400000102",
    },
    {
        "first_name": "John",
        "last_name": "Smith",
        "address": "10 Patient St, Sydney NSW",
        "email_address": "john.smith@example.com",
        "password": "PatientPass1!",
        "phone_number": "0400000003",
        "emergency_contact_number": "0400000103",
    },
    {
        "first_name": "Emily",
        "last_name": "Nguyen",
        "address": "11 Patient St, Sydney NSW",
        "email_address": "emily.nguyen@example.com",
        "password": "PatientPass2!",
        "phone_number": "0400000004",
        "emergency_contact_number": "0400000104",
    },
    {
        "first_name": "Liam",
        "last_name": "O'Brien",
        "address": "12 Patient St, Sydney NSW",
        "email_address": "liam.obrien@example.com",
        "password": "PatientPass3!",
        "phone_number": "0400000005",
        "emergency_contact_number": "0400000105",
    },
    {
        "first_name": "Sophia",
        "last_name": "Kim",
        "address": "13 Patient St, Sydney NSW",
        "email_address": "sophia.kim@example.com",
        "password": "PatientPass4!",
        "phone_number": "0400000006",
        "emergency_contact_number": "0400000106",
    },
    {
        "first_name": "Noah",
        "last_name": "Patel",
        "address": "14 Patient St, Sydney NSW",
        "email_address": "noah.patel@example.com",
        "password": "PatientPass5!",
        "phone_number": "0400000007",
        "emergency_contact_number": "0400000107",
    },
    {
        "first_name": "Olivia",
        "last_name": "Chen",
        "address": "15 Patient St, Sydney NSW",
        "email_address": "olivia.chen@example.com",
        "password": "PatientPass6!",
        "phone_number": "0400000008",
        "emergency_contact_number": "0400000108",
    },
    {
        "first_name": "Ethan",
        "last_name": "Brown",
        "address": "16 Patient St, Sydney NSW",
        "email_address": "ethan.brown@example.com",
        "password": "PatientPass7!",
        "phone_number": "0400000009",
        "emergency_contact_number": "0400000109",
    },
    {
        "first_name": "Mia",
        "last_name": "Wilson",
        "address": "17 Patient St, Sydney NSW",
        "email_address": "mia.wilson@example.com",
        "password": "PatientPass8!",
        "phone_number": "0400000010",
        "emergency_contact_number": "0400000110",
    },
]


def get_connection():
    os.makedirs(DB_DATA_DIR, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_connection()
    conn.execute(SCHEMA)

    cursor = conn.execute("SELECT COUNT(*) FROM patients")
    existing_count = cursor.fetchone()[0]

    if existing_count == 0:
        for patient in SEED_PATIENTS:
            conn.execute(
                """
                INSERT INTO patients
                (first_name, last_name, address, email_address, password,
                 phone_number, emergency_contact_number)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    patient["first_name"],
                    patient["last_name"],
                    patient["address"],
                    patient["email_address"],
                    generate_password_hash(patient["password"]),
                    patient["phone_number"],
                    patient["emergency_contact_number"],
                ),
            )

    conn.commit()
    conn.close()

init_db()

if __name__ == "__main__":
    init_db()