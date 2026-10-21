import os
from urllib.parse import quote

import requests

MULTI_AGENT_SERVER_URL = os.getenv("MULTI_AGENT_SERVER_URL", "http://localhost:7002")
# Defaults to off so a deployment that forgets the variable stays disabled.
# docker-compose sets it to "true" for local runs.
MULTI_AGENT_ENABLED = os.getenv("MULTI_AGENT_ENABLED", "false").strip().lower() == "true"
WORKFLOW_TIMEOUT_SECONDS = int(os.getenv("MULTI_AGENT_TIMEOUT_SECONDS", "300"))


def run_workflow(user_request: str, evidence: list, requested_by: str):
    resp = requests.post(
        f"{MULTI_AGENT_SERVER_URL}/workflow",
        json={
            "feature": "pharmacy",
            "user_request": user_request,
            "evidence": evidence[:20],
            "requested_by": requested_by,
        },
        timeout=WORKFLOW_TIMEOUT_SECONDS,
    )
    return resp.json(), resp.status_code


def submit_review(workflow_id: str, decision: str, reviewer: str, notes: str = "", correction: str | None = None):
    body = {"decision": decision, "reviewer": reviewer, "notes": notes}
    if correction:
        body["correction"] = correction
    resp = requests.post(
        f"{MULTI_AGENT_SERVER_URL}/workflow/{quote(workflow_id, safe='')}/review",
        json=body,
        timeout=10,
    )
    return resp.json(), resp.status_code