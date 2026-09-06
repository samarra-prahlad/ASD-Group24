import os
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from markupsafe import escape

app = Flask(__name__)
CORS(app)

DATABASE_SERVICE_URL = os.environ.get("DATABASE_SERVICE_URL", "http://billing-database:6004")
APPOINTMENTS_DATABASE_API_URL = os.environ.get("APPOINTMENTS_DATABASE_API_URL", "http://appointments-backend:5001")
PHARMACY_DATABASE_API_URL = os.environ.get("PHARMACY_DATABASE_API_URL", "http://pharmacy-backend:5003")
WARDBED_DATABASE_API_URL = os.environ.get("WARDBED_DATABASE_API_URL", "http://wardbed-backend:5006")
SHARED_ACCESS_API_URL = os.environ.get("SHARED_ACCESS_API_URL", "http://shared-backend:5000")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:0.5b")

AI_TIMEOUT = 30  # seconds - LLM responses are slower than normal service calls
REQUEST_TIMEOUT = 3  # seconds - fail fast to mock rather than hang if a teammate's service is down

AI_SYSTEM_PROMPT = (
    "You are a helpful billing assistant for a healthcare application. "
    "Answer questions about invoices, insurance coverage, and billing status "
    "concisely and in plain language. If you don't have enough information "
    "to answer, say so rather than guessing."
)


def proxy_get(url):
    """
    Forward a GET to another service and return (json_body, status_code).
    Returns a clean 503 instead of crashing if that service is unreachable.
    """
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        return response.json(), response.status_code
    except requests.exceptions.RequestException:
        return {"error": "billing-database is unreachable"}, 503


# ---------------------------------------------------------------------------
# Shared access control
#
# Calls shared-backend's /session/verify to find out who's making a request
# and what role they have. Billing enforces: admin = read/write on everyone's
# invoices, patient = read-only on their OWN invoices only (Billing is not
# the Appointments exception).
# ---------------------------------------------------------------------------

def verify_session(token):
    """
    Verifies a session token against shared-backend.
    Returns (session_dict, None) on success, or (None, error_kind) on failure,
    where error_kind is "missing", "unreachable", or "invalid".
    """
    if not token:
        return None, "missing"

    try:
        response = requests.post(
            f"{SHARED_ACCESS_API_URL}/session/verify",
            json={"token": token},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException:
        return None, "unreachable"

    if response.status_code != 200:
        return None, "invalid"

    return response.json(), None


def session_error_response(error):
    if error == "unreachable":
        return jsonify({"error": "Shared access service is unreachable"}), 503
    return jsonify({"error": "Invalid or missing session token"}), 401


# ---------------------------------------------------------------------------
# Cross-service cost lookups
#
# NOTE: As of writing, none of Appointments/Pharmacy/Ward & Bed's schemas
# expose a cost field (confirmed for Appointments - its doctors/appointments
# tables have no price data). These functions try the real API first, but
# the endpoint paths and response shapes below are GUESSES pending an actual
# contract with each teammate. The mock fallback values are flat placeholders
# so invoice generation is testable now - they are NOT real pricing and must
# be revisited once the real APIs (and cost fields) exist.
# ---------------------------------------------------------------------------

def get_appointment_cost(appointment_id):
    if appointment_id is None:
        return 0.0, "no_appointment"

    try:
        response = requests.get(
            f"{APPOINTMENTS_DATABASE_API_URL}/appointments/{appointment_id}",
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 200:
            data = response.json()
            if "cost" in data:
                return float(data["cost"]), "live"
    except requests.exceptions.RequestException:
        pass

    return 150.00, "mock"


def get_medication_cost(patient_id):
    if patient_id is None:
        return 0.0, "no_patient"

    try:
        response = requests.get(
            f"{PHARMACY_DATABASE_API_URL}/prescriptions/patient/{patient_id}",
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                total = sum(item.get("cost", 0) for item in data)
                return float(total), "live"
    except requests.exceptions.RequestException:
        pass

    return 0.00, "mock"


def get_bed_charges(patient_id):
    if patient_id is None:
        return 0.0, "no_patient"

    try:
        response = requests.get(
            f"{WARDBED_DATABASE_API_URL}/wardstays/patient/{patient_id}",
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                total = sum(item.get("charges", 0) for item in data)
                return float(total), "live"
    except requests.exceptions.RequestException:
        pass

    return 0.00, "mock"


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/")
def health():
    return jsonify({"service": "billing-backend", "status": "running"})


# ---------------------------------------------------------------------------
# Proxy plain CRUD reads to the database tier
#
# All read endpoints now require a valid session token. Admins can read
# everyone's invoices. Patients can only read their own - any invoice or
# patient_id belonging to someone else returns 403, regardless of what was
# requested in the URL.
# ---------------------------------------------------------------------------

@app.get("/invoices")
def get_invoices():
    token = request.args.get("token")
    session, error = verify_session(token)

    if session is None:
        return session_error_response(error)

    if session["role"] != "admin":
        return jsonify({"error": "Patients cannot list all invoices"}), 403

    body, status = proxy_get(f"{DATABASE_SERVICE_URL}/invoices")
    return jsonify(body), status


@app.get("/invoices/<int:invoice_id>")
def get_invoice(invoice_id):
    token = request.args.get("token")
    session, error = verify_session(token)

    if session is None:
        return session_error_response(error)

    body, status = proxy_get(f"{DATABASE_SERVICE_URL}/invoices/{invoice_id}")

    if status == 200 and session["role"] != "admin" and body.get("patient_id") != session["patient_id"]:
        return jsonify({"error": "You can only view your own invoices"}), 403

    return jsonify(body), status


@app.get("/invoices/patient/<int:patient_id>")
def get_invoices_by_patient(patient_id):
    token = request.args.get("token")
    session, error = verify_session(token)

    if session is None:
        return session_error_response(error)

    if session["role"] != "admin" and patient_id != session["patient_id"]:
        return jsonify({"error": "You can only view your own invoices"}), 403

    body, status = proxy_get(f"{DATABASE_SERVICE_URL}/invoices/patient/{patient_id}")
    return jsonify(body), status


@app.get("/insurance-providers")
def get_insurance_providers():
    body, status = proxy_get(f"{DATABASE_SERVICE_URL}/insurance-providers")
    return jsonify(body), status


# ---------------------------------------------------------------------------
# HTML fragment endpoint for the HTMX frontend
#
# hx-get expects HTML to swap into the DOM, not JSON, so this renders the
# same invoice data as an HTML table body. Requires a valid token. Patients
# always see only their own invoices - any ?patient_id in the request is
# ignored in favour of their session's own ID. Admins may filter by
# ?patient_id, or omit it to see everyone's.
# ---------------------------------------------------------------------------

def filter_and_sort_invoices(invoices, invoice_id=None, status=None, insurance=None, sort_by=None, sort_dir="asc"):
    """
    Applies search/filter/sort criteria to an already-fetched list of invoices.
    Done in Python since billing-database doesn't support these query params
    directly. Insurance matching is case-insensitive; "Self-pay" matches
    invoices with no insurance_provider_name.
    """
    result = invoices

    if invoice_id:
        result = [inv for inv in result if str(inv["id"]) == str(invoice_id)]

    if status:
        result = [inv for inv in result if inv.get("status", "").lower() == status.lower()]

    if insurance:
        if insurance.lower() == "self-pay":
            result = [inv for inv in result if not inv.get("insurance_provider_name")]
        else:
            result = [
                inv for inv in result
                if (inv.get("insurance_provider_name") or "").lower() == insurance.lower()
            ]

    if sort_by:
        reverse = sort_dir == "desc"
        result = sorted(result, key=lambda inv: inv.get(sort_by) or 0, reverse=reverse)

    return result


def render_invoice_rows(invoices, token, role="admin"):
    if not invoices:
        return "<tr><td colspan='8'>No invoices found.</td></tr>"

    rows = []
    for inv in invoices:
        provider_name = inv.get("insurance_provider_name") or "Self-pay"
        provider_id = inv.get("insurance_provider_id") or ""

        if role == "admin":
            action_cell = f'<button type="button" onclick="toggleEditInvoice({inv["id"]})">Edit</button>'
        elif inv["status"] != "paid":
            action_cell = f"""<button
                    type="button"
                    hx-post="/invoices/{inv['id']}/pay/html?token={token}"
                    hx-target="#invoice-pay-message-{inv['id']}"
                    hx-swap="innerHTML"
                    hx-confirm="Mark this invoice as paid?"
                >Pay</button>
                <div id="invoice-pay-message-{inv['id']}"></div>"""
        else:
            action_cell = "<span>Paid</span>"

        rows.append(f"""<tr id="invoice-row-{inv['id']}">
            <td>{inv['id']}</td>
            <td>{inv['patient_id']}</td>
            <td>{provider_name}</td>
            <td>${inv['total_amount']:.2f}</td>
            <td>${inv['insurance_covered_amount']:.2f}</td>
            <td>${inv['patient_owed_amount']:.2f}</td>
            <td>{inv['status']}</td>
            <td>{action_cell}</td>
        </tr>""")

        if role == "admin":
            rows.append(f"""<tr id="invoice-edit-{inv['id']}" class="edit-row is-hidden">
                <td colspan="8">
                    <form
                        hx-put="/invoices/{inv['id']}/html?token={token}"
                        hx-target="#invoice-edit-message-{inv['id']}"
                        hx-swap="innerHTML"
                    >
                        <label>Insurance Provider ID
                            <input type="number" name="insurance_provider_id" value="{provider_id}">
                        </label>
                        <label>Appointment Cost
                            <input type="number" step="0.01" name="appointment_cost" value="{inv['appointment_cost']}">
                        </label>
                        <label>Medication Cost
                            <input type="number" step="0.01" name="medication_cost" value="{inv['medication_cost']}">
                        </label>
                        <label>Bed Charges
                            <input type="number" step="0.01" name="bed_charges" value="{inv['bed_charges']}">
                        </label>
                        <label>Status
                            <select name="status">
                                <option value="pending" {"selected" if inv['status'] == "pending" else ""}>Pending</option>
                                <option value="paid" {"selected" if inv['status'] == "paid" else ""}>Paid</option>
                                <option value="partially_paid" {"selected" if inv['status'] == "partially_paid" else ""}>Partially paid</option>
                            </select>
                        </label>
                        <button type="submit">Save</button>
                        <button type="button" onclick="toggleEditInvoice({inv['id']})">Cancel</button>
                    </form>
                    <div id="invoice-edit-message-{inv['id']}"></div>
                </td>
            </tr>""")

    return "".join(rows)


@app.get("/invoices/html")
def get_invoices_html():
    token = request.args.get("token")
    session, error = verify_session(token)

    if session is None:
        return "<tr><td colspan='8'>Please log in again.</td></tr>", 401

    if session["role"] == "admin":
        patient_id = request.args.get("patient_id")
    else:
        patient_id = session["patient_id"]

    if patient_id:
        body, status = proxy_get(f"{DATABASE_SERVICE_URL}/invoices/patient/{patient_id}")
    else:
        body, status = proxy_get(f"{DATABASE_SERVICE_URL}/invoices")

    if status != 200:
        return "<tr><td colspan='8'>Error loading invoices.</td></tr>", status

    invoice_id = request.args.get("invoice_id")
    invoice_status = request.args.get("status")
    insurance = request.args.get("insurance")
    sort_by = request.args.get("sort_by")
    sort_dir = request.args.get("sort_dir", "asc")

    body = filter_and_sort_invoices(
        body,
        invoice_id=invoice_id,
        status=invoice_status,
        insurance=insurance,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    return render_invoice_rows(body, token, session["role"])


# ---------------------------------------------------------------------------
# Business logic: generate an invoice by pulling costs from other services
#
# Write operation - requires a valid admin session. Patients have read-only
# access to Billing (Billing is not the Appointments exception).
# ---------------------------------------------------------------------------

@app.post("/invoices/generate")
def generate_invoice():
    token = request.args.get("token")
    session, error = verify_session(token)

    if session is None:
        return session_error_response(error)

    if session["role"] != "admin":
        return jsonify({"error": "Patients have read-only access to Billing"}), 403

    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid input"}), 400

    if "patient_id" not in data:
        return jsonify({"error": "patient_id is required"}), 400

    patient_id = data["patient_id"]
    appointment_id = data.get("appointment_id")
    insurance_provider_id = data.get("insurance_provider_id")

    appointment_cost, appointment_source = get_appointment_cost(appointment_id)
    medication_cost, medication_source = get_medication_cost(patient_id)
    bed_charges, bed_source = get_bed_charges(patient_id)

    invoice_payload = {
        "patient_id": patient_id,
        "insurance_provider_id": insurance_provider_id,
        "appointment_cost": appointment_cost,
        "medication_cost": medication_cost,
        "bed_charges": bed_charges,
    }

    try:
        response = requests.post(
            f"{DATABASE_SERVICE_URL}/invoices", json=invoice_payload, timeout=REQUEST_TIMEOUT
        )
    except requests.exceptions.RequestException:
        return jsonify({"error": "billing-database is unreachable"}), 503

    if response.status_code != 201:
        return jsonify(response.json()), response.status_code

    result = response.json()
    result["cost_sources"] = {
        "appointment_cost": appointment_source,
        "medication_cost": medication_source,
        "bed_charges": bed_source,
    }

    return jsonify(result), 201


# ---------------------------------------------------------------------------
# POST /invoices/create/html - admin-only HTMX form endpoint for manually
# creating an invoice with directly-entered cost values (not derived via
# appointment_id like /invoices/generate). Returns an HTML fragment for the
# admin template rather than JSON. On success, fires an HX-Trigger header so
# the invoice table can listen and auto-refresh itself.
# ---------------------------------------------------------------------------

@app.post("/invoices/create/html")
def create_invoice_html():
    token = request.args.get("token")
    session, error = verify_session(token)

    if session is None:
        status = 503 if error == "unreachable" else 401
        return f"<div class='form-message form-error'>{escape('Invalid or missing session token.')}</div>", status

    if session["role"] != "admin":
        return "<div class='form-message form-error'>Patients cannot create invoices.</div>", 403

    patient_id = request.form.get("patient_id")

    if not patient_id:
        return "<div class='form-message form-error'>Patient ID is required.</div>", 400

    insurance_provider_id = request.form.get("insurance_provider_id") or None
    appointment_cost = request.form.get("appointment_cost", 0) or 0
    medication_cost = request.form.get("medication_cost", 0) or 0
    bed_charges = request.form.get("bed_charges", 0) or 0
    status_value = request.form.get("status", "pending")

    invoice_payload = {
        "patient_id": int(patient_id),
        "insurance_provider_id": int(insurance_provider_id) if insurance_provider_id else None,
        "appointment_cost": float(appointment_cost),
        "medication_cost": float(medication_cost),
        "bed_charges": float(bed_charges),
        "status": status_value,
    }

    try:
        response = requests.post(
            f"{DATABASE_SERVICE_URL}/invoices", json=invoice_payload, timeout=REQUEST_TIMEOUT
        )
    except requests.exceptions.RequestException:
        return "<div class='form-message form-error'>billing-database is unreachable.</div>", 503

    if response.status_code != 201:
        error_message = response.json().get("error", "Unable to create invoice.")
        return f"<div class='form-message form-error'>{escape(error_message)}</div>", response.status_code

    result = response.json()
    return (
        f"<div class='form-message form-success'>"
        f"Invoice #{result['invoice_id']} created successfully. "
        f"Total: ${result['total_amount']:.2f}"
        f"</div>",
        201,
        {"HX-Trigger": f'{{"invoicesChanged": null, "invoiceCreated": {{"id": {result["invoice_id"]}}}}}'},
    )


# ---------------------------------------------------------------------------
# PUT /invoices/<invoice_id>/html - admin-only HTMX form endpoint for editing
# an existing invoice's fields. Proxies to the database tier's existing
# PUT /invoices/<id>. Returns an HTML fragment rather than JSON. On success,
# fires an HX-Trigger header so the invoice table can listen and auto-refresh.
# ---------------------------------------------------------------------------

@app.put("/invoices/<int:invoice_id>/html")
def update_invoice_html(invoice_id):
    token = request.args.get("token")
    session, error = verify_session(token)

    if session is None:
        status = 503 if error == "unreachable" else 401
        return f"<div class='form-message form-error'>{escape('Invalid or missing session token.')}</div>", status

    if session["role"] != "admin":
        return "<div class='form-message form-error'>Patients cannot edit invoices.</div>", 403

    update_payload = {}

    if request.form.get("insurance_provider_id") is not None and request.form.get("insurance_provider_id") != "":
        update_payload["insurance_provider_id"] = int(request.form.get("insurance_provider_id"))
    if request.form.get("appointment_cost"):
        update_payload["appointment_cost"] = float(request.form.get("appointment_cost"))
    if request.form.get("medication_cost"):
        update_payload["medication_cost"] = float(request.form.get("medication_cost"))
    if request.form.get("bed_charges"):
        update_payload["bed_charges"] = float(request.form.get("bed_charges"))
    if request.form.get("status"):
        update_payload["status"] = request.form.get("status")
    if request.form.get("date"):
        update_payload["date"] = request.form.get("date")

    try:
        response = requests.put(
            f"{DATABASE_SERVICE_URL}/invoices/{invoice_id}", json=update_payload, timeout=REQUEST_TIMEOUT
        )
    except requests.exceptions.RequestException:
        return "<div class='form-message form-error'>billing-database is unreachable.</div>", 503

    if response.status_code != 200:
        error_message = response.json().get("error", "Unable to update invoice.")
        return f"<div class='form-message form-error'>{escape(error_message)}</div>", response.status_code

    result = response.json()
    return (
        f"<div class='form-message form-success'>"
        f"Invoice #{result['invoice_id']} updated successfully. "
        f"Total: ${result['total_amount']:.2f}"
        f"</div>",
        200,
        {"HX-Trigger": "invoicesChanged"},
    )


# ---------------------------------------------------------------------------
# GET /invoices/<invoice_id>/print - printable invoice page, opened in a new
# tab from the admin view after creating or editing an invoice. Admins can
# view any invoice; patients can only view their own (same rule as the
# existing GET /invoices/<id> JSON endpoint).
# ---------------------------------------------------------------------------

@app.get("/invoices/<int:invoice_id>/print")
def print_invoice(invoice_id):
    token = request.args.get("token")
    session, error = verify_session(token)

    if session is None:
        status = 503 if error == "unreachable" else 401
        return f"<p>{escape('Invalid or missing session token.')}</p>", status

    body, status = proxy_get(f"{DATABASE_SERVICE_URL}/invoices/{invoice_id}")

    if status != 200:
        error_message = body.get("error", "Unable to retrieve invoice.")
        return f"<p>{escape(error_message)}</p>", status

    if session["role"] != "admin" and body.get("patient_id") != session["patient_id"]:
        return "<p>You can only view your own invoices.</p>", 403

    provider_name = body.get("insurance_provider_name") or "Self-pay"

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Invoice #{body['id']}</title>
    <style>
        body {{ font-family: sans-serif; max-width: 600px; margin: 40px auto; }}
        h1 {{ border-bottom: 2px solid #333; padding-bottom: 8px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        td {{ padding: 8px 0; border-bottom: 1px solid #ddd; }}
        td:last-child {{ text-align: right; }}
        .total-row td {{ font-weight: bold; font-size: 1.2em; border-top: 2px solid #333; }}
    </style>
</head>
<body>
    <h1>Invoice #{body['id']}</h1>
    <p>Date: {body['date']}</p>
    <p>Patient ID: {body['patient_id']}</p>
    <p>Insurance: {provider_name}</p>
    <p>Status: {body['status']}</p>

    <table>
        <tr><td>Appointment Cost</td><td>${body['appointment_cost']:.2f}</td></tr>
        <tr><td>Medication Cost</td><td>${body['medication_cost']:.2f}</td></tr>
        <tr><td>Bed Charges</td><td>${body['bed_charges']:.2f}</td></tr>
        <tr><td>Insurance Covered</td><td>${body['insurance_covered_amount']:.2f}</td></tr>
        <tr class="total-row"><td>Amount Owed</td><td>${body['patient_owed_amount']:.2f}</td></tr>
    </table>

    <script>window.print();</script>
</body>
</html>""", 200


# ---------------------------------------------------------------------------
# POST /invoices/<invoice_id>/pay/html - patient-facing action to mark their
# own invoice as paid. Admins can also pay any invoice, using the same
# ownership rule as the other invoice routes.
# ---------------------------------------------------------------------------

@app.post("/invoices/<int:invoice_id>/pay/html")
def pay_invoice_html(invoice_id):
    token = request.args.get("token")
    session, error = verify_session(token)

    if session is None:
        status = 503 if error == "unreachable" else 401
        return f"<div class='form-message form-error'>{escape('Invalid or missing session token.')}</div>", status

    body, status = proxy_get(f"{DATABASE_SERVICE_URL}/invoices/{invoice_id}")

    if status != 200:
        error_message = body.get("error", "Unable to retrieve invoice.")
        return f"<div class='form-message form-error'>{escape(error_message)}</div>", status

    if session["role"] != "admin" and body.get("patient_id") != session["patient_id"]:
        return "<div class='form-message form-error'>You can only pay your own invoices.</div>", 403

    try:
        response = requests.put(
            f"{DATABASE_SERVICE_URL}/invoices/{invoice_id}",
            json={"status": "paid"},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException:
        return "<div class='form-message form-error'>billing-database is unreachable.</div>", 503

    if response.status_code != 200:
        error_message = response.json().get("error", "Unable to update invoice.")
        return f"<div class='form-message form-error'>{escape(error_message)}</div>", response.status_code

    result = response.json()
    return (
        f"<div class='form-message form-success'>"
        f"Invoice #{result['invoice_id']} marked as paid."
        f"</div>",
        200,
        {"HX-Trigger": "invoicesChanged"},
    )


# ---------------------------------------------------------------------------
# AI-Mode: Frontend -> Backend/API -> Ollama -> LLM
# ---------------------------------------------------------------------------

def call_ollama(user_message):
    """
    Sends the user's message to Ollama's OpenAI-compatible chat completions
    endpoint. Returns (reply_text, error_message) - exactly one is None.
    """
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/chat/completions",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": AI_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
            },
            timeout=AI_TIMEOUT,
        )
    except requests.exceptions.RequestException:
        return None, "AI service is unreachable"

    if response.status_code != 200:
        return None, "AI service returned an error"

    try:
        reply = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError):
        return None, "Unexpected AI response format"

    return reply, None


@app.post("/ai/chat")
def ai_chat():
    data = request.get_json()

    if not data or "message" not in data or not data["message"].strip():
        return jsonify({"error": "message is required"}), 400

    reply, error = call_ollama(data["message"])

    if error:
        return jsonify({"error": error}), 503

    return jsonify({"reply": reply})


@app.post("/ai/chat/html")
def ai_chat_html():
    """
    HTML fragment version for the HTMX chat widget. Appends a user bubble and
    an assistant bubble to the chat log on each request.
    """
    user_message = request.form.get("message", "").strip()

    if not user_message:
        return "<div class='chat-msg chat-error'>Please enter a message.</div>", 400

    reply, error = call_ollama(user_message)

    user_bubble = f"<div class='chat-msg chat-user'><strong>You:</strong> {escape(user_message)}</div>"

    if error:
        return f"{user_bubble}<div class='chat-msg chat-error'>{escape(error)}</div>", 503

    bot_bubble = f"<div class='chat-msg chat-bot'><strong>Assistant:</strong> {escape(reply)}</div>"
    return f"{user_bubble}{bot_bubble}"


# run application
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5004,
        debug=True
    )