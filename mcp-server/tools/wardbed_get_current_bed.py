import requests
from mcp_instance import mcp
import os

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:5006")

def get_current_bed(patient_id: int) -> dict:
    if patient_id is None:
        raise ValueError("patient_id is required")
    
    response = requests.get(f"{BACKEND_URL}/patients/{patient_id}/bed", timeout=5)

    return response.json()


mcp.tool(name="wardbed_get_current_bed")(get_current_bed)
