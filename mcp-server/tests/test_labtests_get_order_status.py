from unittest.mock import patch, MagicMock
from tools.labtests_get_order_status import get_order_status


@patch("tools.labtests_get_order_status.requests.get")
def test_get_order_status_returns_expected_shape(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "order_id": 1,
        "status": "pending",
        "test_type": "WBC",
        "ordered_by": "Dr. Test",
        "created_at": "2026-09-10T10:00:00",
    }
    mock_get.return_value = mock_response

    result = get_order_status(1)

    assert result == {
        "order_id": 1,
        "status": "pending",
        "test_type": "WBC",
        "ordered_by": "Dr. Test",
        "created_at": "2026-09-10T10:00:00",
    }


@patch("tools.labtests_get_order_status.requests.get")
def test_get_order_status_handles_missing_order(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_get.return_value = mock_response

    result = get_order_status(999999)

    assert result == {"error": "Order not found", "order_id": 999999}


@patch("tools.labtests_get_order_status.requests.get")
def test_get_order_status_handles_backend_unreachable(mock_get):
    import requests
    mock_get.side_effect = requests.RequestException("connection refused")

    result = get_order_status(1)

    assert result["error"] == "labtests backend unreachable"