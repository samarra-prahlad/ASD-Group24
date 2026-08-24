import requests

BASE_URL = "http://localhost:6005"

def test_get_orders_returns_list():
    r = requests.get(f"{BASE_URL}/orders")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

def test_orders_have_expected_fields():
    r = requests.get(f"{BASE_URL}/orders")
    order = r.json()[0]
    assert "order_id" in order
    assert "patient_id" in order
    assert "status" in order

def test_get_results_for_order():
    r = requests.get(f"{BASE_URL}/results/1")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

def test_create_order():
    r = requests.post(f"{BASE_URL}/orders", json={
        "patient_id": 101,
        "test_type": "Cholesterol Panel",
        "ordered_by": "Dr. Test"
    })
    assert r.status_code == 201
    assert "order_id" in r.json()