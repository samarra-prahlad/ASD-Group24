import os
import requests
from mcp_instance import mcp

LABTESTS_BACKEND_URL = os.getenv("LABTESTS_BACKEND_URL", "http://localhost:5005")


def get_order_status(order_id: int) -> dict:
    """Real-time status of a specific lab order."""
    try:
        r = requests.get(f"{LABTESTS_BACKEND_URL}/orders/{order_id}", timeout=5)
    except requests.RequestException as exc:
        return {"error": "labtests backend unreachable", "detail": str(exc)}

    if r.status_code == 404:
        return {"error": "Order not found", "order_id": order_id}
    if r.status_code != 200:
        return {"error": "Unexpected response from labtests backend", "status_code": r.status_code}

    order = r.json()
    return {
        "order_id": order["order_id"],
        "status": order["status"],
        "test_type": order["test_type"],
        "ordered_by": order["ordered_by"],
        "created_at": order["created_at"],
    }


mcp.tool(name="labtests_get_order_status")(get_order_status)