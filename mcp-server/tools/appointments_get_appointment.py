import os
import requests
from mcp_instance import mcp

# Same backend your Flask app talks to for appointment lookups.
# Override via env var so this works both locally and from inside a container.
APPOINTMENTS_BACKEND_URL = os.getenv(
    "APPOINTMENTS_BACKEND_URL", "http://appointments-backend:5001"
)


def get_appointment(appointment_id: int) -> dict:
    """Status/details of a single appointment."""
    try:
        response = requests.get(
            f"{APPOINTMENTS_BACKEND_URL}/appointments/{appointment_id}",
            timeout=5,
        )
    except requests.RequestException as exc:
        return {"error": "Appointments backend unavailable", "detail": str(exc)}

    if response.status_code == 404:
        return {"error": "Appointment not found"}

    if response.status_code != 200:
        return {
            "error": "Unable to retrieve appointment",
            "detail": response.text,
        }

    return response.json()


mcp.tool(name="appointments_get_appointment")(get_appointment)
