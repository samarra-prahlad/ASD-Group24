import os
import sqlite3

DATA_DIR = "/app/data"
DATABASE_NAME = os.path.join(DATA_DIR, "access.db")

os.makedirs(DATA_DIR, exist_ok=True)

conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    dob TEXT,
    email TEXT UNIQUE,
    role TEXT NOT NULL DEFAULT 'patient',
    contact TEXT
)
""")

sample_users = [
    (101, "Alice Nguyen", "1990-04-12", "alice@example.com", "patient", "0400111222"),
    (102, "Ben Carter", "1985-09-03", "ben@example.com", "patient", "0400333444"),
    (201, "Dr. Sarah Chen", "1978-11-20", "sarah@example.com", "doctor", "0400555666")
]

cursor.executemany(
    "INSERT OR IGNORE INTO users (id, name, dob, email, role, contact) VALUES (?, ?, ?, ?, ?, ?)",
    sample_users,
)

conn.commit()
conn.close()

print("Shared access database initialized.")