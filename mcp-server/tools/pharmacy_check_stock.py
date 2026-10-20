from mcp_instance import mcp
import requests
import os

PHARMACY_BACKEND_URL = os.getenv("PHARMACY_BACKEND_URL", "http://localhost:5003")

def check_stock(medication_name: str) -> dict:
    """Check current stock."""
    if not medication_name:
        raise ValueError("medication_name is required")
    try:
        response = requests.get(f"{PHARMACY_BACKEND_URL}/medications", timeout=5)
        response.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to fetch stock from pharmacy backend: {e}")
    medications = response.json()
    match = next(
        (m for m in medications if medication_name.strip().lower() in m.get("name", "").lower()),
        None,
    )

    if not match:
        return {"error": f"No medication found matching '{medication_name}'"}

    return {
        "medication_id": match["id"],
        "name": match["name"],
        "stock": match["stock"],
        "in_stock": match["stock"] > 0,
    }


mcp.tool(name="pharmacy_check_stock")(check_stock)
