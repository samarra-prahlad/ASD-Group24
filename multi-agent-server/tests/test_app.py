import pytest

from app import create_app
from coordinator import Coordinator
from tests.conftest import FakeLLM


@pytest.fixture
def client(coordinator):
    app = create_app(coordinator)
    app.config["TESTING"] = True
    return app.test_client()


def _start(client, evidence):
    return client.post("/workflow", json={"feature": "billing", "user_request": "Summarise", "evidence": evidence})


def test_health(client):
    body = client.get("/health").get_json()
    assert body["status"] == "ok"
    assert body["agents"] == ["planner", "worker", "reviewer"]


def test_workflow_requires_user_request(client):
    assert client.post("/workflow", json={"feature": "billing"}).status_code == 400


def test_workflow_rejects_bad_evidence(client):
    resp = client.post("/workflow", json={"user_request": "x", "evidence": "not a list"})
    assert resp.status_code == 400


def test_full_workflow_then_review(client, evidence):
    resp = _start(client, evidence)
    assert resp.status_code == 201
    wf_id = resp.get_json()["workflow_id"]

    assert client.get(f"/workflow/{wf_id}").get_json()["status"] == "awaiting_human_review"

    review = client.post(f"/workflow/{wf_id}/review", json={"decision": "approve", "reviewer": "samarra"})
    assert review.status_code == 200
    assert review.get_json()["status"] == "approved"

    again = client.post(f"/workflow/{wf_id}/review", json={"decision": "reject", "reviewer": "samarra"})
    assert again.status_code == 409


def test_review_validation_errors(client, evidence):
    wf_id = _start(client, evidence).get_json()["workflow_id"]
    assert client.post(f"/workflow/{wf_id}/review", json={"decision": "maybe", "reviewer": "s"}).status_code == 400
    assert client.post("/workflow/wf-missing/review", json={"decision": "approve", "reviewer": "s"}).status_code == 404
    assert client.get("/workflow/wf-missing").status_code == 404


def test_failed_workflow_returns_503(store, evidence):
    app = create_app(Coordinator(FakeLLM(fail_role="planner"), store))
    resp = app.test_client().post("/workflow", json={"user_request": "x", "evidence": evidence})
    assert resp.status_code == 503
    assert resp.get_json()["status"] == "failed"


def test_list_workflows_filters_by_feature(client, evidence):
    _start(client, evidence)
    client.post("/workflow", json={"feature": "pharmacy", "user_request": "x", "evidence": []})
    billing = client.get("/workflows?feature=billing").get_json()["workflows"]
    assert len(billing) == 1 and billing[0]["feature"] == "billing"
