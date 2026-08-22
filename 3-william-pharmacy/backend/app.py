from flask import Flask, jsonify
from flask_cors import CORS
import sqlite3

app = Flask(__name__)
CORS(app)

DATABASE = "/data/pharmacy.db"


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

    return jsonify([dict(row) for row in medications])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5103, debug=True)