import requests
from mcp_instance import mcp
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5006")

def get_current_bed(patient_id: int) -> dict:
    if patient_id is None:
        raise ValueError("patient_id is required")
    
    response = requests.get(
        f"{BACKEND_URL}/patients/{patient_id}/bed",
        timeout=5
    )

    if response.status_code == 404:
        return {
            "assigned": False,
            "patient_id": patient_id,
            "message": "Patient has no current bed assignment."
        }

    response.raise_for_status()

    data = response.json()

    return {
        "assigned": True,
        "patient_id": patient_id,
        "bed_id": data.get("bed_id"),
        "ward_id": data.get("ward_id"),
        "bed_number": data.get("bed_number")
    }


mcp.tool(name="wardbed_get_current_bed")(get_current_bed)
