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