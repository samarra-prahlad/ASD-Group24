import requests
import pytest
from unittest.mock import patch, Mock

from backend.app import app

@pytest.fixture
def client():
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client 

def test_get_ward(client):
    response = client.get("/wards/1")

    assert response.status_code == 200
    assert response.is_json

    data = response.get_json()

    assert isinstance(data, dict)

def test_get_invalid_ward(client):
    response = client.get("/wards/999")

    assert response.status_code == 404

def test_get_beds(client):
    response = client.get("/wards/1/beds")


    assert response.status_code == 200
    assert response.is_json

    data = response.get_json()

    assert isinstance(data, list)

def test_get_invalid_beds(client):
    response = client.get("/wards/999/beds")

    assert response.status_code == 404

#mocking in order to prevent actual changes in the db
def test_assign_patient_to_bed_success(client):
    mock_patient_response = Mock()
    mock_patient_response.status_code = 200

    mock_bed_response = Mock()
    mock_bed_response.status_code = 200
    mock_bed_response.json.return_value = {
        "message": "Patient 1 assigned successfully"
    }

    with patch(
        "backend.app.requests.get",
        return_value=mock_patient_response
    ), patch(
        "backend.app.requests.put",
        return_value=mock_bed_response
    ):

        response = client.put(
            "/beds/1/assign",
            json={"patient_id": 1}
        )

    assert response.status_code == 200
    assert response.is_json

    data = response.get_json()

    assert data["message"] == "Patient 1 assigned successfully"

def test_assign_patient_database_unavailable(client):
    mock_patient_response = Mock()
    mock_patient_response.status_code = 200

    with patch(
        "backend.app.requests.get",
        return_value=mock_patient_response
    ), patch(
        "backend.app.requests.put",
        side_effect=requests.RequestException
    ):
        response = client.put(
            "/beds/1/assign",
            json={"patient_id": 1}
        )

    assert response.status_code == 502
    assert response.get_json()["error"] == "Ward database service unavailable"


def test_assign_missing_patient_id(client):
    response = client.put(
        "/beds/1/assign",
        json={}
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "patient_id is required"

def test_assign_patient_id_not_integer(client):
    response = client.put(
        "/beds/1/assign",
        json={"patient_id": "abc"}
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "patient_id must be an integer"

def test_release_patient_success(client):
    mock_bed_response = Mock()
    mock_bed_response.status_code = 200
    mock_bed_response.json.return_value = {
        "message": "Patient released successfully"
    }

    with patch(
        "backend.app.requests.put",
        return_value=mock_bed_response
    ):
        response = client.put("/beds/1/release")

    assert response.status_code == 200
    assert response.is_json

    data = response.get_json()

    assert data["message"] == "Patient released successfully"


def test_release_patient_database_unavailable(client):
    with patch(
        "backend.app.requests.put",
        side_effect=requests.RequestException
    ):
        response = client.put("/beds/1/release")

    assert response.status_code == 502
    assert response.get_json()["error"] == "Ward database service unavailable"