import os
import secrets
import requests
from flask_cors import CORS
from flask import Flask, jsonify, request, render_template, redirect, make_response

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BACKEND_DIR, "templates"))
CORS(app)

DATABASE_SERVICE_URL = os.environ.get("DATABASE_SERVICE_URL", "http://shared-database:6000")
REQUEST_TIMEOUT = 3  # seconds - fail fast rather than hang if the database service is down

REGISTER_REQUIRED_FIELDS = [
    "first_name", "last_name", "address", "email_address",
    "password", "phone_number", "emergency_contact_number",
]

# In-memory session store: token -> {patient_id, role, first_name}
# Resets if this container restarts - acceptable for this project's scope.
SESSIONS = {}


def create_session(patient_id, role, first_name):
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {"patient_id": patient_id, "role": role, "first_name": first_name}
    return token


# ---------------------------------------------------------------------------
# JSON API (used by other services / programmatic access)
# ---------------------------------------------------------------------------

@app.post("/register")
def register():
    data = request.get_json() or {}
    missing = [f for f in REGISTER_REQUIRED_FIELDS if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    try:
        response = requests.post(
            f"{DATABASE_SERVICE_URL}/patients",
            json=data,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException:
        return jsonify({"error": "Database service is unreachable"}), 503

    return jsonify(response.json()), response.status_code


@app.post("/login")
def login():
    data = request.get_json() or {}
    email = data.get("email_address")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "email_address and password are required"}), 400

    try:
        response = requests.post(
            f"{DATABASE_SERVICE_URL}/patients/verify",
            json={"email_address": email, "password": password},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException:
        return jsonify({"error": "Database service is unreachable"}), 503

    if response.status_code != 200:
        return jsonify(response.json()), response.status_code

    verified = response.json()
    token = create_session(verified["patient_id"], verified["role"], verified["first_name"])

    return jsonify({
        "token": token,
        "patient_id": verified["patient_id"],
        "role": verified["role"],
        "first_name": verified["first_name"],
    }), 200


@app.post("/session/verify")
def verify_session():
    data = request.get_json() or {}
    token = data.get("token")

    if not token:
        return jsonify({"error": "token is required"}), 400

    session = SESSIONS.get(token)
    if session is None:
        return jsonify({"valid": False, "error": "Invalid or expired session"}), 401

    return jsonify({
        "valid": True,
        "patient_id": session["patient_id"],
        "role": session["role"],
        "first_name": session["first_name"],
    }), 200



@app.post("/logout")
def logout():
    data = request.get_json() or {}
    token = data.get("token")
    SESSIONS.pop(token, None)
    return jsonify({"message": "Logged out"}), 200


def role_from_email(email):
    return "admin" if email.lower().endswith("@admin.com") else "patient"


@app.get("/validate")
def validate():
    """
    Used by the appointments gateway (port 5001) to confirm a patient ID
    exists before allowing booking/viewing/editing/cancelling actions.
    Expects: GET /validate?patient_id=<id>
    """
    patient_id = request.args.get("patient_id")
    if not patient_id:
        return jsonify({"error": "patient_id is required"}), 400

    try:
        response = requests.get(
            f"{DATABASE_SERVICE_URL}/patients/{patient_id}",
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException:
        return jsonify({"error": "Database service is unreachable"}), 503

    if response.status_code == 404:
        return jsonify({"valid": False, "error": "Patient not found"}), 404

    if response.status_code != 200:
        return jsonify({"error": "Unable to validate patient"}), response.status_code

    patient = response.json()
    return jsonify({
        "valid": True,
        "patient_id": patient["patient_id"],
        "role": role_from_email(patient["email_address"]),
    }), 200


# ---------------------------------------------------------------------------
# HTML pages (rendered directly by this backend - login/register/home)
# ---------------------------------------------------------------------------

@app.get("/login")
def login_page():
    return render_template("login.html", error=None)


@app.post("/login/html")
def login_html():
    email = request.form.get("email_address")
    password = request.form.get("password")

    if not email or not password:
        return render_template("login.html", error="Email and password are required."), 400

    try:
        response = requests.post(
            f"{DATABASE_SERVICE_URL}/patients/verify",
            json={"email_address": email, "password": password},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException:
        return render_template("login.html", error="Login service is unreachable. Try again shortly."), 503

    if response.status_code != 200:
        return render_template("login.html", error="Incorrect email or password."), 401

    verified = response.json()
    token = create_session(verified["patient_id"], verified["role"], verified["first_name"])

    resp = make_response(redirect("/home"))
    resp.set_cookie("session_token", token, httponly=True, path="/")
    return resp


@app.get("/register")
def register_page():
    return render_template("register.html", error=None)


@app.post("/register/html")
def register_html():
    data = request.form.to_dict()
    missing = [f for f in REGISTER_REQUIRED_FIELDS if not data.get(f)]
    if missing:
        return render_template("register.html", error=f"Missing required fields: {', '.join(missing)}"), 400

    try:
        response = requests.post(
            f"{DATABASE_SERVICE_URL}/patients",
            json=data,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException:
        return render_template("register.html", error="Registration service is unreachable. Try again shortly."), 503

    if response.status_code != 201:
        error_message = response.json().get("error", "Registration failed.")
        return render_template("register.html", error=error_message), response.status_code

    created = response.json()
    role = "admin" if created["email_address"].lower().endswith("@admin.com") else "patient"
    token = create_session(created["patient_id"], role, created["first_name"])

    resp = make_response(redirect("/home"))
    resp.set_cookie("session_token", token, httponly=True, path="/")
    return resp


@app.get("/home")
def home_page():
    token = request.cookies.get("session_token")
    session = SESSIONS.get(token) if token else None

    if session is None:
        return redirect("/login")

    template = "home_admin.html" if session["role"] == "admin" else "home_patient.html"
    return render_template(template, first_name=session["first_name"], token=token)


@app.get("/logout/html")
def logout_html():
    token = request.cookies.get("session_token")
    SESSIONS.pop(token, None)
    resp = make_response(redirect("/login"))
    resp.delete_cookie("session_token", path="/")
    return resp


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)