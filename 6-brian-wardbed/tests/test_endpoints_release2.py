import pytest
from unittest.mock import patch, Mock

from backend.app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True

    with app.test_client() as client:
        yield client


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
    assert response.get_json()["message"] == "Patient 1 assigned successfully"


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
    assert response.get_json()["message"] == "Patient released successfully"