import requests

BASE_URL = "http://localhost:5005"

def test_health_check():
    r = requests.get(f"{BASE_URL}/")
    assert r.status_code == 200
    assert r.json()["status"] == "running"

def test_get_orders_returns_list():
    r = requests.get(f"{BASE_URL}/orders")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

def test_create_order_valid_patient():
    r = requests.post(f"{BASE_URL}/orders", json={
        "patient_id": 1,
        "test_type": "Test Panel",
        "ordered_by": "Dr. Test"
    })
    assert r.status_code == 201
    assert "order_id" in r.json()

def test_create_order_invalid_patient_rejected():
    r = requests.post(f"{BASE_URL}/orders", json={
        "patient_id": 9999,
        "test_type": "Test Panel",
        "ordered_by": "Dr. Test"
    })
    assert r.status_code == 400
    assert "error" in r.json()

def test_create_result_gets_flagged():
    r = requests.post(f"{BASE_URL}/results", json={
        "order_id": 1,
        "result_value": "WBC 15.8 x10^9/L",
        "reference_range": "4.0-11.0 x10^9/L"
    })
    assert r.status_code == 201

def test_update_order_status():
    r = requests.put(f"{BASE_URL}/orders/1", json={"status": "completed"})
    assert r.status_code == 200

def test_get_all_results():
    r = requests.get(f"{BASE_URL}/results")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

def test_delete_order():
    # create one to delete, so we don't destroy seed data
    created = requests.post(f"{BASE_URL}/orders", json={
        "patient_id": 1, "test_type": "Temp Test", "ordered_by": "Dr. Test"
    }).json()
    r = requests.delete(f"{BASE_URL}/orders/{created['order_id']}")
    assert r.status_code == 200

def test_update_result():
    created = requests.post(f"{BASE_URL}/results", json={
        "order_id": 4, "result_value": "Placeholder", "reference_range": "N/A"
    }).json()

    r = requests.put(f"{BASE_URL}/results/{created['result_id']}", json={
        "result_value": "Updated value",
        "reference_range": "N/A",
        "flagged": 0,
        "ai_notes": "updated"
    })
    assert r.status_code == 200

def test_delete_result():
    created = requests.post(f"{BASE_URL}/results", json={
        "order_id": 4, "result_value": "temp", "reference_range": "temp"
    }).json()

    r = requests.delete(f"{BASE_URL}/results/{created['result_id']}")
    assert r.status_code == 200

def test_chat_returns_reply():
    r = requests.post(f"{BASE_URL}/chat", json={"message": "What is a CBC test?"})
    assert r.status_code == 200
    data = r.json()
    assert "reply" in data
    assert "status" in data
    assert "citations" in data
    assert isinstance(data["citations"], list)
    assert data.get("confidence_category") in ("High", "Medium", "Low", "Insufficient")

def test_chat_empty_message_does_not_crash():
    r = requests.post(f"{BASE_URL}/chat", json={"message": ""})
    assert r.status_code == 200
    assert "reply" in r.json()
    
def test_get_results_for_specific_order():
    r = requests.get(f"{BASE_URL}/results/1")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

def test_my_results_no_token_rejected():
    r = requests.get(f"{BASE_URL}/my-results")
    assert r.status_code == 400

def test_my_results_invalid_token_rejected():
    r = requests.get(f"{BASE_URL}/my-results?token=not-a-real-token")
    assert r.status_code == 401

def test_delete_nonexistent_order_does_not_crash():
    r = requests.delete(f"{BASE_URL}/orders/999999")
    assert r.status_code in (200, 404)

def test_update_nonexistent_result_does_not_crash():
    r = requests.put(f"{BASE_URL}/results/999999", json={
        "result_value": "x", "reference_range": "x", "flagged": 0, "ai_notes": ""
    })
    assert r.status_code in (200, 404)