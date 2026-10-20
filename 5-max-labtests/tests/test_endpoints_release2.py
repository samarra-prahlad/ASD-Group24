"""Release 2 post-commit CI/CD endpoint tests for Feature 5 (Lab Tests).

Two endpoint functions of the labtests backend/API (port 5005) are tested:

  Endpoint 1: POST /orders        (create_order)
  Endpoint 2: GET  /orders/<id>   (get_order)

Neither endpoint needs Ollama, MCP or RAG, so they run reliably in CI
with MCP_RAG_ENABLED=false.
"""
import requests

BASE_URL = "http://localhost:5005"
TIMEOUT = 10


# ---------- Endpoint 1: POST /orders ----------

def test_post_orders_creates_order_for_valid_patient():
    r = requests.post(
        f"{BASE_URL}/orders",
        json={"patient_id": 1, "test_type": "Release 2 CI Test", "ordered_by": "Dr. CI"},
        timeout=TIMEOUT,
    )
    assert r.status_code == 201
    assert isinstance(r.json()["order_id"], int)


def test_post_orders_rejects_unknown_patient():
    r = requests.post(
        f"{BASE_URL}/orders",
        json={"patient_id": 999999, "test_type": "Release 2 CI Test", "ordered_by": "Dr. CI"},
        timeout=TIMEOUT,
    )
    assert r.status_code == 400
    assert r.json()["error"] == "Invalid patient_id"


# ---------- Endpoint 2: GET /orders/<id> ----------

def test_get_order_returns_the_order_that_was_created():
    created = requests.post(
        f"{BASE_URL}/orders",
        json={"patient_id": 1, "test_type": "Round Trip Panel", "ordered_by": "Dr. CI"},
        timeout=TIMEOUT,
    )
    order_id = created.json()["order_id"]

    r = requests.get(f"{BASE_URL}/orders/{order_id}", timeout=TIMEOUT)
    assert r.status_code == 200
    body = r.json()
    assert body["order_id"] == order_id
    assert body["patient_id"] == 1
    assert body["test_type"] == "Round Trip Panel"
    assert body["ordered_by"] == "Dr. CI"
    assert body["status"] == "pending"


def test_get_order_returns_404_for_missing_order():
    r = requests.get(f"{BASE_URL}/orders/999999", timeout=TIMEOUT)
    assert r.status_code == 404
    assert "error" in r.json()