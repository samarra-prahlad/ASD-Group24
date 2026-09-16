from unittest.mock import patch, MagicMock

import requests

from tools.ehr_get_change_request_status import get_change_request_status


def fake_response(json_data, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    response.raise_for_status.side_effect = (
        None if status_code < 400
        else requests.exceptions.HTTPError(response=response)
    )
    return response


@patch("tools.ehr_get_change_request_status.requests.get")
def test_returns_status_for_existing_request(mock_get):
    mock_get.return_value = fake_response({
        "id": 2, "patient_id": 4, "request_type": "Update Treatment",
        "status": "approved", "created_at": "2026-09-10T10:00:00",
    }, 200)

    result = get_change_request_status(2)

    assert result == {
        "request_id": 2,
        "status": "approved",
        "patient_id": 4,
        "request_type": "Update Treatment",
    }


@patch("tools.ehr_get_change_request_status.requests.get")
def test_returns_error_for_unknown_request_id(mock_get):
    mock_get.return_value = fake_response({"error": "Change request not found"}, 404)

    result = get_change_request_status(999)

    assert result == {"error": "Change request not found", "request_id": 999}


@patch("tools.ehr_get_change_request_status.requests.get")
def test_returns_error_when_database_unavailable(mock_get):
    mock_get.side_effect = requests.exceptions.ConnectionError("refused")

    result = get_change_request_status(1)

    assert "error" in result