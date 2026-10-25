import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(HERE, "..", "backend")
sys.path.insert(0, os.path.abspath(BACKEND_DIR))

import multi_agent_client as client  # noqa: E402

class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


def test_run_workflow_sends_pharmacy_feature_and_caps_evidence(monkeypatch):
    seen = {}

    def fake_post(url, json, timeout):
        seen.update(url=url, json=json, timeout=timeout)
        return FakeResponse({"workflow_id": "w1"}, 201)

    monkeypatch.setattr(client.requests, "post", fake_post)

    body, status = client.run_workflow("summarise", [{"id": i} for i in range(30)], "Admin")

    assert status == 201
    assert body == {"workflow_id": "w1"}
    assert seen["url"].endswith("/workflow")
    assert seen["json"]["feature"] == "pharmacy"
    assert seen["json"]["requested_by"] == "Admin"
    assert len(seen["json"]["evidence"]) == 20  # the server only uses 20


def test_submit_review_encodes_the_workflow_id(monkeypatch):
    seen = {}

    def fake_post(url, json, timeout):
        seen.update(url=url, json=json)
        return FakeResponse({"status": "ok"})

    monkeypatch.setattr(client.requests, "post", fake_post)

    client.submit_review("a/b ?x", "approve", "Admin")

    # a hostile id must not be able to change the path
    assert seen["url"].endswith("/workflow/a%2Fb%20%3Fx/review")


def test_submit_review_includes_correction_only_when_given(monkeypatch):
    bodies = []

    def fake_post(url, json, timeout):
        bodies.append(json)
        return FakeResponse({})

    monkeypatch.setattr(client.requests, "post", fake_post)

    client.submit_review("w1", "approve", "Admin", notes="ok")
    client.submit_review("w1", "correct", "Admin", correction="fix the dosage")

    assert "correction" not in bodies[0]
    assert bodies[1]["correction"] == "fix the dosage"
    assert bodies[1]["decision"] == "correct"