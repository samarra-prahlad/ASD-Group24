import os

import requests

from mcp_instance import mcp

DATABASE_SERVICE_URL = os.environ.get("DATABASE_SERVICE_URL", "http://ehr-database:6002")


def get_change_request_status(request_id: int) -> dict:
    """Check whether a record change request has been processed."""
    try:
        resp = requests.get(
            f"{DATABASE_SERVICE_URL}/change_requests/by-id/{request_id}",
            timeout=5,
        )
    except requests.RequestException as exc:
        return {"error": "EHR database unavailable", "details": str(exc)}

    if resp.status_code == 404:
        return {"error": "Change request not found", "request_id": request_id}

    resp.raise_for_status()
    data = resp.json()

    return {
        "request_id": data["id"],
        "status": data["status"],
        "patient_id": data.get("patient_id"),
        "request_type": data.get("request_type"),
    }


mcp.tool(name="ehr_get_change_request_status")(get_change_request_status)