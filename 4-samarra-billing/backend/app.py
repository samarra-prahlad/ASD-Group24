from flask import Flask, jsonify, request
from flask_cors import CORS
from markupsafe import escape
import os
import requests

app = Flask(__name__)
CORS(app)

DATABASE_SERVICE_URL = os.environ.get("DATABASE_SERVICE_URL", "http://billing-database:6004")
APPOINTMENTS_DATABASE_API_URL = os.environ.get("APPOINTMENTS_DATABASE_API_URL", "http://appointments-backend:5001")
PHARMACY_DATABASE_API_URL = os.environ.get("PHARMACY_DATABASE_API_URL", "http://pharmacy-backend:5003")
WARDBED_DATABASE_API_URL = os.environ.get("WARDBED_DATABASE_API_URL", "http://wardbed-backend:5006")
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

    # Mock fallback: flat placeholder cost, not real pricing
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

    # Mock fallback: flat placeholder cost, not real pricing
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

    # Mock fallback: flat placeholder cost, not real pricing
    return 0.00, "mock"


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/")
def health():
    return jsonify({"service": "billing-backend", "status": "running"})


# ---------------------------------------------------------------------------
# Proxy plain CRUD reads to the database tier
# ---------------------------------------------------------------------------

@app.get("/invoices")
def get_invoices():
    body, status = proxy_get(f"{DATABASE_SERVICE_URL}/invoices")
    return jsonify(body), status


@app.get("/invoices/<int:invoice_id>")
def get_invoice(invoice_id):
    body, status = proxy_get(f"{DATABASE_SERVICE_URL}/invoices/{invoice_id}")
    return jsonify(body), status


@app.get("/invoices/patient/<int:patient_id>")
def get_invoices_by_patient(patient_id):
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
# same invoice data as an HTML table body. Optional ?patient_id=<id> filters
# to one patient's invoices (patient view); omitted, returns all (admin view).
# ---------------------------------------------------------------------------

def render_invoice_rows(invoices):
    if not invoices:
        return "<tr><td colspan='7'>No invoices found.</td></tr>"

    rows = []
    for inv in invoices:
        provider_name = inv.get("insurance_provider_name") or "Self-pay"
        rows.append(f"""<tr>
            <td>{inv['id']}</td>
            <td>{inv['patient_id']}</td>
            <td>{provider_name}</td>
            <td>${inv['total_amount']:.2f}</td>
            <td>${inv['insurance_covered_amount']:.2f}</td>
            <td>${inv['patient_owed_amount']:.2f}</td>
            <td>{inv['status']}</td>
        </tr>""")
    return "".join(rows)


@app.get("/invoices/html")
def get_invoices_html():
    patient_id = request.args.get("patient_id")

    if patient_id:
        body, status = proxy_get(f"{DATABASE_SERVICE_URL}/invoices/patient/{patient_id}")
    else:
        body, status = proxy_get(f"{DATABASE_SERVICE_URL}/invoices")

    if status != 200:
        return "<tr><td colspan='7'>Error loading invoices.</td></tr>", status

    return render_invoice_rows(body)


# ---------------------------------------------------------------------------
# Business logic: generate an invoice by pulling costs from other services
# ---------------------------------------------------------------------------

@app.post("/invoices/generate")
def generate_invoice():
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