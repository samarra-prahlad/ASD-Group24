from flask import Flask, jsonify, request
import sqlite3
import os
from datetime import date

app = Flask(__name__)

DATA_DIR = os.environ.get("DB_DATA_DIR", "/app/data")
DATABASE_NAME = os.path.join(DATA_DIR, "billing.db")


def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def calculate_amounts(appointment_cost, medication_cost, bed_charges, coverage_percentage):
    """
    Server-side calculation so total_amount, insurance_covered_amount, and
    patient_owed_amount always stay consistent with the underlying costs -
    matches the invariants checked in tests/test_init_db.py.
    """
    total_amount = round(appointment_cost + medication_cost + bed_charges, 2)
    insurance_covered_amount = round(total_amount * (coverage_percentage / 100), 2)
    patient_owed_amount = round(total_amount - insurance_covered_amount, 2)
    return total_amount, insurance_covered_amount, patient_owed_amount


# Health check
@app.get("/")
def health():
    return jsonify({"service": "billing-database", "status": "running"})


# Get all invoices
@app.get("/invoices")
def get_invoices():
    conn = get_db_connection()

    invoices = conn.execute("""
        SELECT
            invoices.id,
            invoices.patient_id,
            invoices.insurance_provider_id,
            invoices.appointment_cost,
            invoices.medication_cost,
            invoices.bed_charges,
            invoices.total_amount,
            invoices.insurance_covered_amount,
            invoices.patient_owed_amount,
            invoices.status,
            invoices.date,
            insurance_providers.name AS insurance_provider_name,
            insurance_providers.plan_type AS insurance_plan_type
        FROM invoices
        LEFT JOIN insurance_providers
            ON invoices.insurance_provider_id = insurance_providers.id
        ORDER BY invoices.date DESC
    """).fetchall()

    conn.close()

    return jsonify([dict(row) for row in invoices])


# Get a single invoice
@app.get("/invoices/<int:invoice_id>")
def get_invoice(invoice_id):
    conn = get_db_connection()
    invoice = conn.execute("""
        SELECT
            invoices.id,
            invoices.patient_id,
            invoices.insurance_provider_id,
            invoices.appointment_cost,
            invoices.medication_cost,
            invoices.bed_charges,
            invoices.total_amount,
            invoices.insurance_covered_amount,
            invoices.patient_owed_amount,
            invoices.status,
            invoices.date,
            insurance_providers.name AS insurance_provider_name,
            insurance_providers.plan_type AS insurance_plan_type
        FROM invoices
        LEFT JOIN insurance_providers
            ON invoices.insurance_provider_id = insurance_providers.id
        WHERE invoices.id = ?
    """, (invoice_id,)).fetchone()

    conn.close()

    if invoice is None:
        return jsonify({"error": "Invoice not found"}), 404

    return jsonify(dict(invoice))


# Get invoices for a specific patient
@app.get("/invoices/patient/<int:patient_id>")
def get_invoices_by_patient(patient_id):
    conn = get_db_connection()
    invoices = conn.execute("""
        SELECT
            invoices.id,
            invoices.patient_id,
            invoices.insurance_provider_id,
            invoices.appointment_cost,
            invoices.medication_cost,
            invoices.bed_charges,
            invoices.total_amount,
            invoices.insurance_covered_amount,
            invoices.patient_owed_amount,
            invoices.status,
            invoices.date,
            insurance_providers.name AS insurance_provider_name,
            insurance_providers.plan_type AS insurance_plan_type
        FROM invoices
        LEFT JOIN insurance_providers
            ON invoices.insurance_provider_id = insurance_providers.id
        WHERE invoices.patient_id = ?
        ORDER BY invoices.date DESC
    """, (patient_id,)).fetchall()

    conn.close()

    return jsonify([dict(row) for row in invoices])


# Get invoices for a specific insurance provider
@app.get("/invoices/provider/<int:insurance_provider_id>")
def get_invoices_by_provider(insurance_provider_id):
    conn = get_db_connection()
    invoices = conn.execute("""
        SELECT
            invoices.id,
            invoices.patient_id,
            invoices.insurance_provider_id,
            insurance_providers.name AS insurance_provider_name,
            insurance_providers.plan_type AS insurance_plan_type,
            invoices.appointment_cost,
            invoices.medication_cost,
            invoices.bed_charges,
            invoices.total_amount,
            invoices.insurance_covered_amount,
            invoices.patient_owed_amount,
            invoices.status,
            invoices.date
        FROM invoices
        JOIN insurance_providers
            ON invoices.insurance_provider_id = insurance_providers.id
        WHERE invoices.insurance_provider_id = ?
        ORDER BY invoices.date DESC
    """, (insurance_provider_id,)).fetchall()

    conn.close()

    return jsonify([dict(row) for row in invoices])


# Create a new invoice
@app.post("/invoices")
def create_invoice():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid input"}), 400

    required_fields = ["patient_id"]

    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"{field} is required"}), 400

    patient_id = data["patient_id"]
    insurance_provider_id = data.get("insurance_provider_id")
    appointment_cost = data.get("appointment_cost", 0)
    medication_cost = data.get("medication_cost", 0)
    bed_charges = data.get("bed_charges", 0)
    status = data.get("status", "pending")
    invoice_date = data.get("date", date.today().isoformat())

    conn = get_db_connection()

    coverage_percentage = 0
    if insurance_provider_id is not None:
        provider = conn.execute(
            "SELECT * FROM insurance_providers WHERE id = ?", (insurance_provider_id,)
        ).fetchone()

        if provider is None:
            conn.close()
            return jsonify({"error": "Insurance provider not found"}), 404

        coverage_percentage = provider["coverage_percentage"]

    total_amount, insurance_covered_amount, patient_owed_amount = calculate_amounts(
        appointment_cost, medication_cost, bed_charges, coverage_percentage
    )

    cursor = conn.execute("""
        INSERT INTO invoices (
            patient_id, insurance_provider_id, appointment_cost, medication_cost,
            bed_charges, total_amount, insurance_covered_amount, patient_owed_amount,
            status, date
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        patient_id, insurance_provider_id, appointment_cost, medication_cost,
        bed_charges, total_amount, insurance_covered_amount, patient_owed_amount,
        status, invoice_date
    ))

    invoice_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Invoice created successfully",
        "invoice_id": invoice_id,
        "total_amount": total_amount,
        "insurance_covered_amount": insurance_covered_amount,
        "patient_owed_amount": patient_owed_amount
    }), 201


# Update an invoice
@app.put("/invoices/<int:invoice_id>")
def update_invoice(invoice_id):
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid input"}), 400

    conn = get_db_connection()
    invoice = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()

    if invoice is None:
        conn.close()
        return jsonify({"error": "Invoice not found"}), 404

    # Update fields, falling back to existing values
    patient_id = data.get("patient_id", invoice["patient_id"])
    insurance_provider_id = data.get("insurance_provider_id", invoice["insurance_provider_id"])
    appointment_cost = data.get("appointment_cost", invoice["appointment_cost"])
    medication_cost = data.get("medication_cost", invoice["medication_cost"])
    bed_charges = data.get("bed_charges", invoice["bed_charges"])
    status = data.get("status", invoice["status"])
    invoice_date = data.get("date", invoice["date"])

    coverage_percentage = 0
    if insurance_provider_id is not None:
        provider = conn.execute(
            "SELECT * FROM insurance_providers WHERE id = ?", (insurance_provider_id,)
        ).fetchone()

        if provider is None:
            conn.close()
            return jsonify({"error": "Insurance provider not found"}), 404

        coverage_percentage = provider["coverage_percentage"]

    total_amount, insurance_covered_amount, patient_owed_amount = calculate_amounts(
        appointment_cost, medication_cost, bed_charges, coverage_percentage
    )

    conn.execute("""
        UPDATE invoices
        SET patient_id = ?, insurance_provider_id = ?, appointment_cost = ?,
            medication_cost = ?, bed_charges = ?, total_amount = ?,
            insurance_covered_amount = ?, patient_owed_amount = ?, status = ?, date = ?
        WHERE id = ?
    """, (
        patient_id, insurance_provider_id, appointment_cost, medication_cost,
        bed_charges, total_amount, insurance_covered_amount, patient_owed_amount,
        status, invoice_date, invoice_id
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Invoice updated",
        "invoice_id": invoice_id,
        "total_amount": total_amount,
        "insurance_covered_amount": insurance_covered_amount,
        "patient_owed_amount": patient_owed_amount
    }), 200


# Delete an invoice
@app.delete("/invoices/<int:invoice_id>")
def delete_invoice(invoice_id):
    conn = get_db_connection()
    invoice = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()

    if invoice is None:
        conn.close()
        return jsonify({"error": "Invoice not found"}), 404

    conn.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": "Invoice deleted", "invoice_id": invoice_id})


# Get all insurance providers
@app.get("/insurance-providers")
def get_insurance_providers():
    conn = get_db_connection()

    providers = conn.execute("""SELECT * FROM insurance_providers ORDER BY name""").fetchall()

    conn.close()

    return jsonify([dict(row) for row in providers])


# Get a single insurance provider
@app.get("/insurance-providers/<int:provider_id>")
def get_insurance_provider(provider_id):
    conn = get_db_connection()
    provider = conn.execute(
        """SELECT * FROM insurance_providers WHERE id = ?""", (provider_id,)
    ).fetchone()
    conn.close()

    if provider is None:
        return jsonify({"error": "Insurance provider not found"}), 404

    return jsonify(dict(provider))


# run application
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=6004,
        debug=True
    )