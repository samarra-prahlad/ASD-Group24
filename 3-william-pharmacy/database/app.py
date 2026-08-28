import os

from flask import Flask, jsonify
from flask_cors import CORS
import sqlite3

app = Flask(__name__)
CORS(app)

DATABASE = os.environ.get(
    "DATABASE_PATH",
    "/app/data/pharmacy.db"
)


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/medications")
def get_medications():
    db = get_db()

    medications = db.execute(
        "SELECT * FROM medications"
    ).fetchall()

    db.close()
    print(f"Retrieved {len(medications)} medications from the database.")
    return jsonify([dict(row) for row in medications])

@app.get("/prescriptions/<patient_id>")
def get_prescriptions(patient_id):
    db = get_db()

    prescriptions = db.execute(
        "SELECT * FROM prescriptions WHERE patient_id = ?",
        (patient_id,)
    ).fetchall()

    db.close()
    print(f"Retrieved {len(prescriptions)} prescriptions from the database.")
    return jsonify([dict(row) for row in prescriptions])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6003, debug=True)