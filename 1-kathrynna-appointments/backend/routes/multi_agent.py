"""
Multi-agent appointment review (Release 2).

Appointments gathers appointment records (and pending change requests) as
evidence and sends them to the shared non-containerised Multi-Agent Server
(Planner -> Worker -> Reviewer). The agents' output is never used until an
admin approves, partially accepts, corrects or rejects it.

Admin-only: the session token is verified against shared-backend's
/session/verify. The frontend sends the token in the X-Session-Token header,
so it never appears in rendered HTML or in URLs.

Disabled by default (MULTI_AGENT_ENABLED=false) so the cloud deployment and
CI never depend on the local Multi-Agent Server. docker-compose sets it to
"true" for local runs.
"""
import os
import re

import requests
from flask import Blueprint, request
from markupsafe import escape

multi_agent_bp = Blueprint("multi_agent", __name__)

DATABASE_SERVICE_URL = os.getenv("DATABASE_SERVICE_URL", "http://appointments-database:6001")
SHARED_ACCESS_API_URL = os.getenv("SHARED_ACCESS_API_URL", "http://shared-backend:5000")
MULTI_AGENT_SERVER_URL = os.getenv("MULTI_AGENT_SERVER_URL", "http://host.docker.internal:7002")
MULTI_AGENT_ENABLED = os.getenv("MULTI_AGENT_ENABLED", "false").lower() == "true"
MULTI_AGENT_TIMEOUT = int(os.getenv("MULTI_AGENT_TIMEOUT", "300"))  # three LLM calls in a row
# The frontend's nginx proxies /api/* to this backend and strips the prefix.
FRONTEND_API_PREFIX = os.getenv("FRONTEND_API_PREFIX", "/api")
REQUEST_TIMEOUT = 5

DECISIONS = {
    "approve": "Approve",
    "partially_accept": "Partially accept",
    "correct": "Correct",
    "reject": "Reject",
}
RISK_BADGE_CLASSES = {"LOW": "confidence-high", "MEDIUM": "confidence-medium", "HIGH": "confidence-low"}
WORKFLOW_ID_PATTERN = re.compile(r"wf-[0-9a-f]{6,32}")
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

def html_error(message, status):
    return f"<div class='availability-panel agent-error'><p>{escape(message)}</p></div>", status


def get_token():
    return (
        request.headers.get("X-Session-Token")
        or request.form.get("token")
        or request.args.get("token")
    )


def require_admin():
    """Returns (session, None) for an admin, otherwise (None, html_error_response)."""
    token = get_token()
    if not token:
        return None, html_error("Invalid or missing session token.", 401)
    try:
        response = requests.post(
            f"{SHARED_ACCESS_API_URL}/session/verify",
            json={"token": token},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException:
        return None, html_error("Shared access service is unreachable.", 503)
    if response.status_code != 200:
        return None, html_error("Invalid or missing session token.", 401)
    session = response.json()
    if session.get("role") != "admin":
        return None, html_error("Only admins can run multi-agent workflows.", 403)
    return session, None


def reviewer_name(session):
    return f"{session.get('first_name') or 'admin'} (admin)"


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

def appointment_evidence(appointments):
    """Keeps only the fields the agents need (no free text or contact details)."""
    return [
        {
            "record_type": "appointment",
            "appointment_id": a.get("id"),
            "patient_id": a.get("patient_id"),
            "doctor_id": a.get("doctor_id"),
            "doctor_name": a.get("doctor_name"),
            "doctor_specialty": a.get("doctor_specialty"),
            "date": a.get("date"),
            "time": a.get("time"),
            "status": a.get("status"),
        }
        for a in appointments
        if isinstance(a, dict)
    ]


def change_request_evidence(changes):
    return [
        {
            "record_type": "change_request",
            "change_id": c.get("id"),
            "appointment_id": c.get("appointment_id"),
            "patient_id": c.get("patient_id"),
            "doctor_name": c.get("doctor_name"),
            "current_date": c.get("current_date"),
            "current_time": c.get("current_time"),
            "requested_date": c.get("requested_date"),
            "requested_time": c.get("requested_time"),
            "status": c.get("status", "pending"),
        }
        for c in changes
        if isinstance(c, dict)
    ]


def _db_get_list(path, params=None):
    """Returns a list, [] for 404, or None if the database could not be read."""
    try:
        response = requests.get(f"{DATABASE_SERVICE_URL}{path}", params=params, timeout=REQUEST_TIMEOUT)
    except requests.RequestException:
        return None
    if response.status_code == 404:
        return []
    if response.status_code != 200:
        return None
    try:
        body = response.json()
    except ValueError:
        return None
    return body if isinstance(body, list) else None


def gather_appointment_evidence(patient_id=None, date=None, include_changes=True):
    """Returns a list of evidence records, or None if appointments-database could not be read."""
    if patient_id is not None:
        appointments = _db_get_list(f"/appointments/patient/{patient_id}")
    elif date:
        appointments = _db_get_list(f"/appointments/date/{date}")
    else:
        appointments = _db_get_list("/appointments")
    if appointments is None:
        return None

    if patient_id is not None:
        appointments = [a for a in appointments if a.get("patient_id") == patient_id]
    evidence = appointment_evidence(appointments)

    if include_changes:
        changes = _db_get_list("/appointment-changes", params={"status": "pending"})
        if changes is None:
            return None
        if patient_id is not None:
            changes = [c for c in changes if c.get("patient_id") == patient_id]
        if date:
            changes = [c for c in changes if date in (c.get("current_date"), c.get("requested_date"))]
        evidence += change_request_evidence(changes)

    return evidence


# ---------------------------------------------------------------------------
# Multi-agent server calls
# ---------------------------------------------------------------------------

def multi_agent_post(path, payload, timeout):
    """POST to the multi-agent server. Returns (json_body, status) or (None, 503) if unreachable."""
    try:
        response = requests.post(f"{MULTI_AGENT_SERVER_URL}{path}", json=payload, timeout=timeout)
        return response.json(), response.status_code
    except (requests.RequestException, ValueError):
        return None, 503


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_agent_step(title, step):
    if not step:
        return ""
    model = escape(step.get("model") or "")
    failed = step.get("status") != "completed"
    if failed:
        body = f"<p class='agent-step-error'>Failed: {escape(step.get('error') or 'unknown error')}</p>"
    else:
        body = f"<pre class='agent-output'>{escape(step.get('output') or '')}</pre>"
    return (
        f"<div class='appointment-card agent-step{' agent-step-failed' if failed else ''}'>"
        f"<div class='appointment-info'><strong>{escape(title)}</strong><small>Model: {model}</small></div>"
        f"{body}</div>"
    )


def render_risk(reviewer_step):
    reviewer_step = reviewer_step or {}
    risk = reviewer_step.get("risk_level") or "UNKNOWN"
    recommendation = reviewer_step.get("recommendation") or "UNKNOWN"
    badge_class = RISK_BADGE_CLASSES.get(risk, "confidence-medium")
    grounding = reviewer_step.get("grounding") or {}
    grounding_html = ""
    if grounding:
        grounding_html = (
            f"<small>Evidence IDs cited: "
            f"{escape(str(grounding.get('evidence_ids_cited', 0)))} of "
            f"{escape(str(grounding.get('evidence_ids_available', 0)))}</small>"
        )
    notes = "".join(f"<li>{escape(note)}</li>" for note in reviewer_step.get("governance_notes", []))
    notes_html = f"<ul class='agent-governance'>{notes}</ul>" if notes else ""
    return (
        f"<div class='appointment-card agent-risk'><div class='appointment-info'>"
        f"<strong>Risk <span class='confidence-badge {badge_class}'>{escape(risk)}</span></strong>"
        f"<span>Reviewer recommends: {escape(recommendation)}</span>"
        f"{grounding_html}</div>{notes_html}</div>"
    )


# Button class per decision, reusing the appointments stylesheet.
DECISION_BUTTON_CLASSES = {
    "approve": "primary-button",
    "partially_accept": "secondary-button",
    "correct": "secondary-button",
    "reject": "delete-button",
}


def render_review_form(workflow_id):
    # workflow_id is validated against WORKFLOW_ID_PATTERN before this is called.
    buttons = "".join(
        f"<button type='submit' class='{DECISION_BUTTON_CLASSES[value]}' "
        f"name='decision' value='{value}'>{label}</button>"
        for value, label in DECISIONS.items()
    )
    return f"""<form id="agent-review-{workflow_id}" class="appointment-edit agent-review-form"
            hx-post="{FRONTEND_API_PREFIX}/multi-agent/workflow/{workflow_id}/review/html"
            hx-target="#agent-decision-{workflow_id}" hx-swap="innerHTML">
        <label>Reviewer notes (optional)<textarea name="notes" rows="2"></textarea></label>
        <label>Corrected output (required for Correct)<textarea name="correction" rows="4"></textarea></label>
        <div class="appointment-actions agent-review-buttons">{buttons}</div>
    </form>
    <div id="agent-decision-{workflow_id}"></div>"""


def render_workflow(workflow):
    workflow_id = workflow.get("workflow_id", "")
    steps = workflow.get("steps", {})
    status = workflow.get("status", "unknown")
    parts = [
        f"<div class='availability-panel agent-workflow' id='workflow-{escape(workflow_id)}'>",
        f"<h3>Workflow <code>{escape(workflow_id)}</code></h3>"
        f"<p>{escape(str(workflow.get('evidence_count', 0)))} evidence record(s) · "
        f"Status: <strong>{escape(status)}</strong></p>",
        render_agent_step("Planner", steps.get("planner")),
        render_agent_step("Worker", steps.get("worker")),
        render_agent_step("Reviewer", steps.get("reviewer")),
    ]
    if status == "awaiting_human_review" and WORKFLOW_ID_PATTERN.fullmatch(workflow_id):
        parts.append(render_risk(steps.get("reviewer")))
        parts.append(render_review_form(workflow_id))
    parts.append("</div>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@multi_agent_bp.post("/multi-agent/workflow/html")
def multi_agent_workflow_html():
    session, error_response = require_admin()
    if session is None:
        return error_response
    if not MULTI_AGENT_ENABLED:
        return html_error("Multi-agent workflows are disabled in this environment.", 503)

    user_request = request.form.get("user_request", "").strip()
    if not user_request:
        return html_error("Enter a request for the agents.", 400)
    if len(user_request) > 1000:
        return html_error("Request is too long (1000 characters max).", 400)

    patient_id = None
    patient_id_raw = request.form.get("patient_id", "").strip()
    if patient_id_raw:
        try:
            patient_id = int(patient_id_raw)
        except ValueError:
            return html_error("Patient ID must be a number.", 400)

    date = request.form.get("date", "").strip() or None
    if date and not DATE_PATTERN.fullmatch(date):
        return html_error("Date must be in YYYY-MM-DD format.", 400)

    # The form sends a hidden "off" plus "on" when the box is ticked; absent means include.
    include_values = request.form.getlist("include_changes")
    include_changes = not include_values or "on" in include_values

    evidence = gather_appointment_evidence(patient_id, date, include_changes)
    if evidence is None:
        return html_error("Could not load appointment evidence from appointments-database.", 503)

    scope = []
    if patient_id is not None:
        scope.append(f"Patient ID: {patient_id}")
    if date:
        scope.append(f"Date: {date}")
    if scope:
        user_request = f"{user_request} ({', '.join(scope)})"

    workflow, status = multi_agent_post("/workflow", {
        "feature": "appointments",
        "user_request": user_request,
        "evidence": evidence,
        "requested_by": reviewer_name(session),
    }, MULTI_AGENT_TIMEOUT)

    if workflow is None:
        return html_error("Multi-agent server is unavailable.", 503)
    if "workflow_id" not in workflow:
        return html_error(workflow.get("error", "Multi-agent server rejected the request."), status)

    http_status = 200 if status == 201 else 503
    return render_workflow(workflow), http_status, {"HX-Trigger": "multiAgentChanged"}


@multi_agent_bp.post("/multi-agent/workflow/<workflow_id>/review/html")
def multi_agent_review_html(workflow_id):
    session, error_response = require_admin()
    if session is None:
        return error_response
    if not WORKFLOW_ID_PATTERN.fullmatch(workflow_id):
        return html_error("Invalid workflow ID.", 400)

    decision = request.form.get("decision", "")
    if decision not in DECISIONS:
        return html_error("Choose approve, partially accept, correct or reject.", 400)
    correction = request.form.get("correction", "").strip()
    if decision == "correct" and not correction:
        return html_error("Enter the corrected output before choosing Correct.", 400)

    reviewer = reviewer_name(session)
    workflow, status = multi_agent_post(f"/workflow/{workflow_id}/review", {
        "decision": decision,
        "reviewer": reviewer,
        "notes": request.form.get("notes", "").strip(),
        "correction": correction or None,
    }, REQUEST_TIMEOUT * 3)

    if workflow is None:
        return html_error("Multi-agent server is unavailable.", 503)
    if status != 200:
        return html_error(workflow.get("error", "Review was not accepted."), status)

    final_output = workflow.get("final_output")
    final_html = (
        f"<pre class='agent-output'>{escape(final_output)}</pre>"
        if final_output else "<p>No output released (rejected).</p>"
    )
    html = (
        f"<div class='availability-panel confirmation agent-decision'>"
        f"<h3>Decision recorded: {escape(DECISIONS[decision])}</h3>"
        f"<p>By {escape(reviewer)} · Status: <strong>{escape(workflow.get('status', ''))}</strong></p>"
        f"<p><strong>Final output</strong></p>{final_html}</div>"
        # Remove the decision buttons so the same workflow cannot be reviewed twice.
        f"<div id='agent-review-{workflow_id}' hx-swap-oob='true'></div>"
    )
    return html, 200, {"HX-Trigger": "multiAgentChanged"}


@multi_agent_bp.get("/multi-agent/history/html")
def multi_agent_history_html():
    session, error_response = require_admin()
    if session is None:
        return error_response
    if not MULTI_AGENT_ENABLED:
        return "<p>Multi-agent workflows are disabled in this environment.</p>", 200

    try:
        response = requests.get(
            f"{MULTI_AGENT_SERVER_URL}/workflows",
            params={"feature": "appointments", "limit": 5},
            timeout=REQUEST_TIMEOUT,
        )
        workflows = response.json().get("workflows", [])
    except (requests.RequestException, ValueError, AttributeError):
        return "<p>Multi-agent server is unavailable.</p>", 200

    if not workflows:
        return "<p>No workflows yet.</p>", 200

    rows = []
    for wf in workflows:
        reviewer_step = (wf.get("steps") or {}).get("reviewer") or {}
        human = wf.get("human_review") or {}
        request_text = wf.get("user_request", "")
        if len(request_text) > 70:
            request_text = request_text[:70] + "…"
        rows.append(
            f"<tr><td><code>{escape(wf.get('workflow_id', ''))}</code></td>"
            f"<td>{escape(request_text)}</td>"
            f"<td>{escape(reviewer_step.get('risk_level') or '-')}</td>"
            f"<td>{escape(wf.get('status', ''))}</td>"
            f"<td>{escape(human.get('decision') or '-')}</td>"
            f"<td>{escape(human.get('reviewer') or '-')}</td></tr>"
        )
    return (
        "<table class='agent-history'><thead><tr><th>Workflow</th><th>Request</th>"
        "<th>Risk</th><th>Status</th><th>Decision</th><th>Reviewed by</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    ), 200