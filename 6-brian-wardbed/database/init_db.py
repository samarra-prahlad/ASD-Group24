import os
import sqlite3

DATABASE_PATH = os.path.join(os.path.dirname(__file__), "data", "ward.db")

def init_db():
    conn = sqlite3.connect(DATABASE_PATH)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS wards (
            ward_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ward_name TEXT NOT NULL UNIQUE,
            capacity INTEGER NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS beds (
            bed_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ward_id INTEGER NOT NULL,
            patient_id INTEGER,
            bed_number TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'available',

            FOREIGN KEY (ward_id) REFERENCES wards(ward_id),
            UNIQUE (ward_id, bed_number)
        )
    """)

    wards = [
        ("General", 10),
        ("Emergency", 8),
        ("Maternity", 6),
        ("Intensive Care", 5),
        ("Surgical", 8),
        ("Pediatric", 6),
    ]

    conn.executemany("""
        INSERT OR IGNORE INTO wards (ward_name, capacity)
        VALUES (?, ?)
    """, wards)

    ward_beds = [
    (1, "G", 10),
    (2, "E", 8),
    (3, "M", 6),
    (4, "ICU", 5),
    (5, "S", 8),
    (6, "P", 6)
    ]

    for ward_id, prefix, capacity in ward_beds:
        for number in range(1, capacity + 1):
            bed_number = f"{prefix}{number:02d}"

            conn.execute(
                """
                INSERT OR IGNORE INTO beds (
                    ward_id,
                    patient_id,
                    bed_number,
                    status
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    ward_id,
                    None,
                    bed_number,
                    "available"
                )
            )

    conn.commit()
    conn.close()

    print("Database initialized successfully.")

if __name__ == "__main__":
    init_db()