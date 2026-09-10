import pytest
from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_tools_endpoint_returns_200(client):
    response = client.get('/tools')
    assert response.status_code == 200


def test_tools_endpoint_returns_list(client):
    response = client.get('/tools')
    data = response.get_json()
    assert isinstance(data, list)


def test_registered_tool_has_required_fields(client):
    response = client.get('/tools')
    data = response.get_json()
    assert len(data) >= 1

    tool = data[0]
    assert "name" in tool
    assert "description" in tool
    assert "input_schema" in tool
    assert isinstance(tool["input_schema"], dict)