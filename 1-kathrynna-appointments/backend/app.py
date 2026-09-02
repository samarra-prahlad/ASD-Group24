from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import requests
from routes.ai_mode import ai_mode_bp

app = Flask(__name__)
CORS(app)
app.register_blueprint(ai_mode_bp, url_prefix="/ai")
DATABASE_SERVICE_URL = os.getenv("DATABASE_SERVICE_URL", "http://appointments-database:6001")
SHARED_ACCESS_API_URL = os.getenv("SHARED_ACCESS_API_URL", "http://shared-access-api:5000")

SLOT_MINUTES = 30
DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def parse_availability(availability_str):
    try:
        day_part, time_part = availability_str.strip().split(" ", 1)
        start_str, end_str = time_part.split("-")

        start_time = datetime.strptime(start_str.strip(), "%H:%M").time()
        end_time = datetime.strptime(end_str.strip(), "%H:%M").time()

        if "-" in day_part:
            start_day, end_day = day_part.split("-")
            start_idx = DAY_ABBR.index(start_day.strip())
            end_idx = DAY_ABBR.index(end_day.strip())

            if start_idx <= end_idx:
                days = DAY_ABBR[start_idx:end_idx + 1]
            else:
                days = DAY_ABBR[start_idx:] + DAY_ABBR[:end_idx + 1]
        else:
            days = [d.strip() for d in day_part.split(",")]

        return days, start_time, end_time

    except Exception:
        return None


def generate_slots(start_time, end_time, slot_minutes=SLOT_MINUTES):
    """Half-open slots: last slot starts no later than end_time - slot_minutes."""
    base_date = datetime(2000, 1, 1)
    current = datetime.combine(base_date, start_time)
    end_dt = datetime.combine(base_date, end_time)

    slots = []

    while current + timedelta(minutes=slot_minutes) <= end_dt:
        slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=slot_minutes)

    return slots


def available_slots_for_doctor(doctor, date_str):
    """Returns the list of open (unbooked) HH:MM slots for a doctor on a given date."""
    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return []

    parsed = parse_availability(doctor.get("availability", ""))

    if not parsed:
        return []

    days, start_time, end_time = parsed
    weekday_abbr = DAY_ABBR[selected_date.weekday()]

    if weekday_abbr not in days:
        return []

    all_slots = generate_slots(start_time, end_time)
    booked = set(doctor.get("booked_times", []))

    return [slot for slot in all_slots if slot not in booked]

@app.get("/")
def health():
    return jsonify({"service": "appointments-backend", "status": "running"})

def validate_patient(patient_id):
    """Ask the shared access API to confirm that the patient exists."""
    try:
        response = requests.get(
            f"{SHARED_ACCESS_API_URL}/validate?patient_id={patient_id}",
            timeout=5
        )
    except requests.RequestException as exc:
        return {"error": "Shared access API unavailable", "detail": str(exc)}, 503

    if response.status_code == 404:
        return {"valid": False, "error": "Patient not found"}, 404

    if response.status_code != 200:
        return {
            "error": "Unable to validate patient",
            "detail": response.text
        }, response.status_code

    return response.json(), 200

@app.get("/appointments")
def get_appointments():
    try:
        response = requests.get(f"{DATABASE_SERVICE_URL}/appointments", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "Appointments database unavailable", "detail": str(exc)}), 503

    return jsonify(response.json())

@app.get("/appointments/<int:appointment_id>")
def get_appointment(appointment_id):
    try:
        response = requests.get(
            f"{DATABASE_SERVICE_URL}/appointments/{appointment_id}",
            timeout=5
        )
    except requests.RequestException as exc:
        return jsonify({
            "error": "Appointments database unavailable",
            "detail": str(exc)
        }), 503

    if response.status_code == 404:
        return jsonify({"error": "Appointment not found"}), 404

    if response.status_code != 200:
        return jsonify({"error": "Unable to retrieve appointment"}), response.status_code

    return jsonify(response.json())

@app.get("/appointments/patient/<int:patient_id>")
def get_appointments_by_patient(patient_id):
    patient_result, patient_status = validate_patient(patient_id)

    if patient_status != 200:
        return jsonify({"error": f"Patient with ID {patient_id} not found"}), patient_status

    try:
        response = requests.get(
            f"{DATABASE_SERVICE_URL}/appointments/patient/{patient_id}",
            timeout=5
        )

        if response.status_code == 404:
            return jsonify({"error": f"No appointments found for patient {patient_id}"}), 404

        if response.status_code != 200:
            return jsonify({"error": "Unable to retrieve patient appointments"}), response.status_code

    except requests.RequestException as exc:
        return jsonify({
            "error": "Appointments database unavailable",
            "detail": str(exc)
        }), 503

    return jsonify(response.json())

@app.get("/appointments/doctor/<int:doctor_id>")
def get_appointments_by_doctor(doctor_id):
    try:
        response = requests.get(f"{DATABASE_SERVICE_URL}/appointments/doctor/{doctor_id}", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "Appointments database unavailable", "detail": str(exc)}), 503

    return jsonify(response.json())

@app.post("/appointments")
def create_appointment():
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    required_fields = ["patient_id", "doctor_id", "date", "time"]

    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    patient_id = data["patient_id"]
    doctor_id = data["doctor_id"]

    patient_result, patient_status = validate_patient(patient_id)

    if patient_status != 200:
        return jsonify({"error": f"Patient with ID {patient_id} not found"}), patient_status

    try:
        doctor_response = requests.get(
            f"{DATABASE_SERVICE_URL}/doctors/{doctor_id}",
            timeout=5
        )

        if doctor_response.status_code == 404:
            return jsonify({"error": f"Doctor with ID {doctor_id} not found"}), 404

        if doctor_response.status_code != 200:
            return jsonify({"error": "Unable to validate doctor"}), 503

        response = requests.post(
            f"{DATABASE_SERVICE_URL}/appointments",
            json=data,
            timeout=5
        )

        return jsonify(response.json()), response.status_code

    except requests.RequestException as exc:
        return jsonify({
            "error": "Unable to connect to appointments database",
            "detail": str(exc)
        }), 503


def render_appointment_card(appt, pending_change=None):
    appt_id = appt["id"]

    pending_banner = ""
    if pending_change:
        pending_banner = f"""
            <p style="color:#b45309;font-size:13px;margin-top:6px;">
                Change requested: {pending_change["requested_date"]} at {pending_change["requested_time"]}
                — awaiting admin approval.
            </p>
        """

    return f"""
        <div class="appointment-card" id="appointment-{appt_id}">
            <div class="appointment-view" id="appointment-view-{appt_id}">
                <div class="appointment-info">
                    <strong>{appt["doctor_name"]}</strong>
                    <span>{appt["doctor_specialty"]}</span>
                    <p>{appt["date"]} at {appt["time"]}</p>
                    <small>Status: {appt["status"]}</small>
                    {pending_banner}
                </div>
                <div class="appointment-actions">
                    <button type="button" class="secondary-button"
                        onclick="toggleEditAppointment({appt_id})" {"disabled" if pending_change else ""}>Edit</button>
                    <button type="button" class="delete-button"
                        hx-delete="/appointments/htmx/{appt_id}"
                        hx-target="#appointment-{appt_id}" hx-swap="outerHTML"
                        hx-confirm="Cancel this appointment?">Delete</button>
                </div>
            </div>
            <div class="appointment-edit is-hidden" id="appointment-edit-{appt_id}">
                <label>Date <input type="date" id="edit-date-{appt_id}" value="{appt["date"]}"></label>
                <label>Time <input type="time" id="edit-time-{appt_id}" value="{appt["time"]}"></label>
                <div class="appointment-actions">
                    <button type="button" class="primary-button"
                        hx-put="/appointments/htmx/{appt_id}" hx-swap="none"
                        hx-vals='js:{{"date": document.getElementById("edit-date-{appt_id}").value, "time": document.getElementById("edit-time-{appt_id}").value}}'
                        hx-on::after-request="handleSaveResult(event)">Request change</button>
                    <button type="button" class="secondary-button"
                        onclick="toggleEditAppointment({appt_id})">Cancel</button>
                </div>
            </div>
        </div>
    """


@app.put("/appointments/htmx/<int:appointment_id>")
def update_appointment_htmx(appointment_id):
    date = request.form.get("date")
    time = request.form.get("time")

    if not date or not time:
        return "<p>Please choose both a date and a time.</p>", 400

    try:
        existing = requests.get(f"{DATABASE_SERVICE_URL}/appointments/{appointment_id}", timeout=5)
        if existing.status_code != 200:
            return """<div class="availability-panel"><h3>Update failed</h3><p>This appointment could not be found.</p></div>""", 404

        response = requests.post(
            f"{DATABASE_SERVICE_URL}/appointment-changes",
            json={"appointment_id": appointment_id, "requested_date": date, "requested_time": time},
            timeout=5
        )

        if response.status_code != 201:
            return f"""<div class="availability-panel"><h3>Request not sent</h3><p>{response.json().get("error", "Unable to submit change request.")}</p></div>""", response.status_code

        updated = requests.get(f"{DATABASE_SERVICE_URL}/appointments/{appointment_id}", timeout=5).json()
        pending_change = {"requested_date": date, "requested_time": time}
        return render_appointment_card(updated, pending_change)

    except requests.RequestException as exc:
        return f"""<div class="availability-panel"><h3>Request failed</h3><p>Unable to connect: {exc}</p></div>""", 503


# Appointments by patient HTMX route
@app.get("/appointments/htmx/patient/<int:patient_id>")
def get_appointments_by_patient_htmx(patient_id):
    patient_result, patient_status = validate_patient(patient_id)
    if patient_status != 200:
        return f"""<div class="availability-panel"><h3>Patient not found</h3><p>No patient with ID {patient_id} exists.</p></div>""", patient_status

    try:
        response = requests.get(f"{DATABASE_SERVICE_URL}/appointments/patient/{patient_id}", timeout=5)
        response.raise_for_status()
        appointments = response.json()

        changes_resp = requests.get(f"{DATABASE_SERVICE_URL}/appointment-changes", params={"status": "pending"}, timeout=5)
        pending_by_appt = {}
        if changes_resp.status_code == 200:
            for c in changes_resp.json():
                pending_by_appt[c["appointment_id"]] = c

    except requests.RequestException as exc:
        return f"""<div class="availability-panel"><h3>Unable to load appointments</h3><p>{exc}</p></div>""", 503

    if not appointments:
        return """<div class="availability-panel"><p>No appointments found for this patient.</p></div>"""

    return "".join(render_appointment_card(appt, pending_by_appt.get(appt["id"])) for appt in appointments)


#admin routes
@app.get("/admin/appointments/htmx")
def admin_appointments_by_date_htmx():
    date = request.args.get("date")
    if not date:
        return "<p>Select a date to view appointments.</p>", 400

    try:
        response = requests.get(f"{DATABASE_SERVICE_URL}/appointments/date/{date}", timeout=5)
        response.raise_for_status()
        appointments = response.json()
    except requests.RequestException as exc:
        return f"<p>Unable to load appointments: {exc}</p>", 503

    if not appointments:
        return f"<div class='availability-panel'><p>No appointments scheduled for {date}.</p></div>"

    html = ""
    for appt in appointments:
        html += f"""
            <div class="appointment-card">
                <div class="appointment-info">
                    <strong>{appt["doctor_name"]}</strong>
                    <span>{appt["doctor_specialty"]}</span>
                    <p>{appt["time"]} — Patient #{appt["patient_id"]}</p>
                    <small>Status: {appt["status"]}</small>
                </div>
            </div>
        """
    return html


@app.get("/admin/changes/htmx")
def admin_pending_changes_htmx():
    try:
        response = requests.get(f"{DATABASE_SERVICE_URL}/appointment-changes", params={"status": "pending"}, timeout=5)
        response.raise_for_status()
        changes = response.json()
    except requests.RequestException as exc:
        return f"<p>Unable to load change requests: {exc}</p>", 503

    if not changes:
        return "<div class='availability-panel'><p>No pending change requests.</p></div>"

    html = ""
    for c in changes:
        html += f"""
            <div class="appointment-card" id="change-{c["id"]}">
                <div class="appointment-info">
                    <strong>{c["doctor_name"]}</strong>
                    <span>{c["doctor_specialty"]}</span>
                    <p>Patient #{c["patient_id"]} requests moving from
                        {c["current_date"]} {c["current_time"]} →
                        <strong>{c["requested_date"]} {c["requested_time"]}</strong></p>
                </div>
                <div class="appointment-actions">
                    <button type="button" class="primary-button"
                        hx-put="/admin/changes/htmx/{c["id"]}" hx-vals='{{"status": "approved"}}'
                        hx-target="#change-{c["id"]}" hx-swap="outerHTML">Approve</button>
                    <button type="button" class="delete-button"
                        hx-put="/admin/changes/htmx/{c["id"]}" hx-vals='{{"status": "rejected"}}'
                        hx-target="#change-{c["id"]}" hx-swap="outerHTML">Reject</button>
                </div>
            </div>
        """
    return html


@app.put("/admin/changes/htmx/<int:change_id>")
def admin_review_change_htmx(change_id):
    status = request.form.get("status")
    if status not in ("approved", "rejected"):
        return "<p>Invalid status.</p>", 400

    try:
        response = requests.put(f"{DATABASE_SERVICE_URL}/appointment-changes/{change_id}",
                                 json={"status": status}, timeout=5)
        if response.status_code != 200:
            return f"""<div class="availability-panel"><p>{response.json().get("error", "Could not update request.")}</p></div>""", response.status_code
        return f"""<div class="availability-panel confirmation"><p>Request {status}.</p></div>"""
    except requests.RequestException as exc:
        return f"<p>Unable to connect: {exc}</p>", 503

@app.delete("/appointments/<int:appointment_id>")
def delete_appointment(appointment_id):
    try:
        appointment_response = requests.get(
            f"{DATABASE_SERVICE_URL}/appointments/{appointment_id}",
            timeout=5
        )

        if appointment_response.status_code != 200:
            return jsonify(appointment_response.json()), appointment_response.status_code

        appointment = appointment_response.json()
        patient_id = appointment.get("patient_id")

        patient_result, patient_status = validate_patient(patient_id)

        if patient_status != 200:
            return jsonify({"error": f"Patient with ID {patient_id} not found"}), patient_status

        response = requests.delete(
            f"{DATABASE_SERVICE_URL}/appointments/{appointment_id}",
            timeout=5
        )

        return jsonify(response.json()), response.status_code

    except requests.RequestException as exc:
        return jsonify({
            "error": "Unable to connect to appointments database",
            "detail": str(exc)
        }), 503

@app.get("/doctors")
def get_doctors():
    try:
        response = requests.get(f"{DATABASE_SERVICE_URL}/doctors", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "Appointments database unavailable", "detail": str(exc)}), 503

    return jsonify(response.json())

@app.get("/doctors/<int:doctor_id>")
def get_doctor(doctor_id):
    try:
        response = requests.get(
            f"{DATABASE_SERVICE_URL}/doctors/{doctor_id}",
            timeout=5
        )
    except requests.RequestException as exc:
        return jsonify({
            "error": "Appointments database unavailable",
            "detail": str(exc)
        }), 503

    if response.status_code == 404:
        return jsonify({"error": f"Doctor ID {doctor_id} not found"}), 404

    if response.status_code != 200:
        return jsonify({"error": f"Unable to retrieve doctor ID {doctor_id}"}), response.status_code

    return jsonify(response.json())

@app.get("/availability")
def get_availability():
    specialty = request.args.get("specialty")
    date = request.args.get("date")

    if not specialty or not date:
        return jsonify({"error": "Both 'specialty' and 'date' are required"}), 400

    try:
        response = requests.get(
            f"{DATABASE_SERVICE_URL}/availability",
            params={"specialty": specialty, "date": date},
            timeout=5
        )

        return jsonify(response.json()), response.status_code
    except requests.RequestException as exc:
        return jsonify({
            "error": "Unable to connect to appointments database",
            "detail": str(exc)
        }), 503

@app.get("/doctors/htmx")
def get_doctors_htmx():
    try:
        response = requests.get(f"{DATABASE_SERVICE_URL}/doctors", timeout=5)
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"<p>Unable to load doctors: {exc}</p>", 503

    doctors = response.json()

    html = ""

    for doctor in doctors:
        html += f"""
        <div class="doctor-card">
            <strong>{doctor["name"]}</strong>
            <span>{doctor["specialty"]}</span>
            <small>{doctor["availability"]}</small>
        </div>
        """

    return html

@app.get("/availability/htmx")
def get_availability_htmx():
    specialty = request.args.get("specialty")
    date = request.args.get("date")

    if not specialty or not date:
        return "<p>Please select an appointment type and date.</p>", 400

    try:
        response = requests.get(
            f"{DATABASE_SERVICE_URL}/availability",
            params={"specialty": specialty, "date": date},
            timeout=5
        )

        if response.status_code != 200:
            return "<p>Unable to load availability.</p>", response.status_code

        data = response.json()

    except requests.RequestException:
        return "<p>Unable to connect to appointments database.</p>", 503

    doctors = data.get("doctors", [])

    if not doctors:
        return f"""
            <div class="availability-panel">
                <h3>No doctors available</h3>
                <p>No {specialty} doctors are available for {date}.</p>
            </div>
        """

    html = ""

    for doctor in doctors:

        open_slots = available_slots_for_doctor(doctor, date)

        html += f"""
            <div class="doctor-card">
                <strong>{doctor["doctor_name"]}</strong>
                <span>{doctor["specialty"]}</span>
                <small>{doctor["availability"]}</small>
                <div class="slot-group">
        """

        if open_slots:
            for slot in open_slots:
                doctor_name_js = doctor["doctor_name"].replace("'", "\\'")
                specialty_js = doctor["specialty"].replace("'", "\\'")
                html += f"""
                    <button
                        type="button"
                        class="slot-button"
                        onclick="selectSlot(this, {doctor["doctor_id"]}, '{doctor_name_js}', '{specialty_js}', '{date}', '{slot}')"
                    >{slot}</button>
                """
        else:
            html += "<p>No available times on this date.</p>"

        html += """
                </div>
            </div>
        """

    return html


def is_slot_booked(doctor_id, date, time, exclude_appointment_id=None):
    response = requests.get(
        f"{DATABASE_SERVICE_URL}/appointments/doctor/{doctor_id}",
        timeout=5
    )
    response.raise_for_status()

    for appt in response.json():
        if appt["date"] != date or appt["time"] != time:
            continue
        if exclude_appointment_id is not None and appt["id"] == exclude_appointment_id:
            continue
        return True

    return False


@app.post("/appointments/htmx")
def create_appointment_htmx():
    """
    Books a single slot picked from the /availability/htmx panel and
    returns an HTML confirmation fragment (or an HTML error fragment).
    htmx sends this as a normal form POST.
    """

    data = request.form

    doctor_id = data.get("doctor_id")
    date = data.get("date")
    time = data.get("time")
    patient_id = data.get("patient_id")

    if not doctor_id or not date or not time or not patient_id:
        return """
            <div class="availability-panel">
                <h3>Missing information</h3>
                <p>Please enter your patient ID and pick a time.</p>
            </div>
        """, 400

    try:
        patient_id_int = int(patient_id)
        doctor_id_int = int(doctor_id)
    except ValueError:
        return """
            <div class="availability-panel">
                <h3>Invalid input</h3>
                <p>Patient ID must be a number.</p>
            </div>
        """, 400

    patient_result, patient_status = validate_patient(patient_id_int)

    if patient_status != 200:
        return f"""
            <div class="availability-panel">
                <h3>Booking failed</h3>
                <p>Patient ID {patient_id_int} was not found. Double-check the ID and try again.</p>
            </div>
        """, patient_status

    try:
        doctor_response = requests.get(
            f"{DATABASE_SERVICE_URL}/doctors/{doctor_id_int}",
            timeout=5
        )

        if doctor_response.status_code != 200:
            return """
                <div class="availability-panel">
                    <h3>Booking failed</h3>
                    <p>That doctor could not be found.</p>
                </div>
            """, 404

        doctor = doctor_response.json()

        if is_slot_booked(doctor_id_int, date, time):
            return """
                <div class="availability-panel">
                    <h3>Booking failed</h3>
                    <p>
                        That slot was just taken by someone else.
                        Please go back and pick another time.
                    </p>
                </div>
            """, 409

        response = requests.post(
            f"{DATABASE_SERVICE_URL}/appointments",
            json={
                "patient_id": patient_id_int,
                "doctor_id": doctor_id_int,
                "date": date,
                "time": time
            },
            timeout=5
        )

        if response.status_code != 201:
            return """
                <div class="availability-panel">
                    <h3>Booking failed</h3>
                    <p>
                        That slot may have just been taken by someone else.
                        Please go back and pick another time.
                    </p>
                </div>
            """, response.status_code

        result = response.json()

        return f"""
            <div class="availability-panel confirmation">
                <h3>Booking confirmed</h3>
                <p>
                    You're booked with <strong>{doctor["name"]}</strong>
                    ({doctor["specialty"]}) on <strong>{date}</strong>
                    at <strong>{time}</strong>.
                </p>
                <p>Confirmation reference: #{result["appointment_id"]}</p>
                <a
                    class="nav-link"
                    href="appointments.html?patient_id={patient_id_int}"
                >View my appointments →</a>
            </div>
        """

    except requests.RequestException as exc:
        return f"""
            <div class="availability-panel">
                <h3>Booking failed</h3>
                <p>Unable to connect to the appointments database: {exc}</p>
            </div>
        """, 503


@app.delete("/appointments/htmx/<int:appointment_id>")
def delete_appointment_htmx(appointment_id):
    """Deletes an appointment. Returns nothing on success so htmx removes the card."""

    try:
        response = requests.delete(
            f"{DATABASE_SERVICE_URL}/appointments/{appointment_id}",
            timeout=5
        )

        if response.status_code != 200:
            return """
                <div class="availability-panel">
                    <h3>Delete failed</h3>
                    <p>Could not delete this appointment.</p>
                </div>
            """, response.status_code

        return "", 200

    except requests.RequestException as exc:
        return f"""
            <div class="availability-panel">
                <h3>Delete failed</h3>
                <p>Unable to connect to the appointments database: {exc}</p>
            </div>
        """, 503

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5001,
        debug=True
    )