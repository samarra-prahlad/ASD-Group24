import pytest
from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_health_returns_200(client):
    response = client.get('/health')
    assert response.status_code == 200


def test_health_returns_json_status_ok(client):
    response = client.get('/health')
    data = response.get_json()
    assert data == {"status": "ok"}