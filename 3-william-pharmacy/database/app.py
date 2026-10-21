import os
from flask import Flask, abort, jsonify, request
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
    return jsonify([dict(row) for row in medications]), 200

@app.get("/prescriptions/<patient_id>")
def get_prescriptions(patient_id):
    db = get_db()

    prescriptions = db.execute(
        "SELECT * FROM prescriptions WHERE patient_id = ?",
        (patient_id,)
    ).fetchall()

    db.close()
    print(f"Retrieved {len(prescriptions)} prescriptions from the database.")
    return jsonify([dict(row) for row in prescriptions]), 200


# Admin endpoints
# create medications
@app.post("/admin/medications/")
def add_medication():
    data = request.get_json()
    name = data.get("name")
    stock = data.get("stock", 0)
    unit_price = data.get("unit_price")

    if not name or unit_price is None:
        abort(400, description="name and unit_price are required")
    if not isinstance(stock, int) or stock < 0:
        abort(400, description="stock must be a non-negative integer")
    if not isinstance(unit_price, (int, float)) or unit_price < 0:
        abort(400, description="unit_price must be a non-negative number")

    db = get_db()
    cur = db.execute(
        "INSERT INTO medications (name, stock, unit_price) VALUES (?, ?, ?)",
        (name, stock, unit_price)
    )
    db.commit()
    new_id = cur.lastrowid
    db.close()
    return jsonify({"id": new_id, "name": name, "stock": stock, "unit_price": unit_price}), 201

# update medications
@app.put("/admin/medications/<int:med_id>")
def update_medication(med_id):
    data = request.get_json()
    fields, values = [], []

    for col in ("name", "stock", "unit_price"):
        if col in data:
            fields.append(f"{col} = ?")
            values.append(data[col])

    if not fields:
        abort(400, description="No fields to update")

    values.append(med_id)
    db = get_db()
    cur = db.execute(
        f"UPDATE medications SET {', '.join(fields)} WHERE id = ?",
        values
    )
    db.commit()
    updated = cur.rowcount
    db.close()

    if updated == 0:
        abort(404, description="Medication not found")
    return jsonify({"updated": updated})

# delete medications
@app.delete("/admin/medications/<int:med_id>")
def delete_medication(med_id):
    db = get_db()
    cur = db.execute("DELETE FROM medications WHERE id = ?", (med_id,))
    db.commit()
    deleted = cur.rowcount
    db.close()

    if deleted == 0:
        abort(404, description="Medication not found")
    return jsonify({"deleted": deleted})


# create prescriptions
@app.post("/admin/prescriptions")
def create_prescription():
    data = request.get_json()
    required = ("patient_id", "medication_id", "dosage", "prescribing_doctor")
    if not all(k in data for k in required):
        abort(400, description=f"Required fields: {', '.join(required)}")

    db = get_db()
    med = db.execute(
        "SELECT id FROM medications WHERE id = ?", (data["medication_id"],)
    ).fetchone()
    if not med:
        db.close()
        abort(400, description="medication_id does not exist")

    status = data.get("status", "active")
    cur = db.execute(
        """INSERT INTO prescriptions (patient_id, medication_id, dosage, prescribing_doctor, status)
           VALUES (?, ?, ?, ?, ?)""",
        (
            data["patient_id"],
            data["medication_id"],
            data["dosage"],
            data["prescribing_doctor"],
            status,
        )
    )
    db.commit()
    new_id = cur.lastrowid
    db.close()
    return jsonify({"id": new_id, **data, "status": status}), 201

# update prescriptions
@app.put("/admin/prescriptions/<int:prescription_id>")
def update_prescription(prescription_id):
    data = request.get_json()
    fields, values = [], []

    for col in ("dosage", "prescribing_doctor", "status", "medication_id", "patient_id"):
        if col in data:
            fields.append(f"{col} = ?")
            values.append(data[col])

    if not fields:
        abort(400, description="No fields to update")

    values.append(prescription_id)
    db = get_db()
    cur = db.execute(
        f"UPDATE prescriptions SET {', '.join(fields)} WHERE id = ?",
        values
    )
    db.commit()
    updated = cur.rowcount
    db.close()

    if updated == 0:
        abort(404, description="Prescription not found")
    return jsonify({"updated": updated})

# delete prescriptions
@app.delete("/admin/prescriptions/<int:prescription_id>")
def delete_prescription(prescription_id):
    db = get_db()
    cur = db.execute("DELETE FROM prescriptions WHERE id = ?", (prescription_id,))
    db.commit()
    deleted = cur.rowcount
    db.close()

    if deleted == 0:
        abort(404, description="Prescription not found")
    return jsonify({"deleted": deleted})

if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=6003, debug=debug_mode) # noqa: S104 - container must listen on all interfaces