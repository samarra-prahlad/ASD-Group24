import os
import requests

MULTI_AGENT_SERVER_URL = os.getenv(
    "MULTI_AGENT_SERVER_URL",
    "http://host.docker.internal:7002"
)


def start_multi_agent_workflow(user_request, evidence=None, requested_by=None):
    response = requests.post(
        f"{MULTI_AGENT_SERVER_URL}/workflow",
        json={
            "user_request": user_request,
            "feature": "wardbed",
            "evidence": evidence or [],
            "requested_by": requested_by
        },
        timeout=600
    )

    response.raise_for_status()
    return response.json()


def review_multi_agent_workflow(
    workflow_id,
    decision,
    reviewer,
    notes="",
    correction=None
):
    response = requests.post(
        f"{MULTI_AGENT_SERVER_URL}/workflow/{workflow_id}/review",
        json={
            "decision": decision,
            "reviewer": reviewer,
            "notes": notes,
            "correction": correction
        },
        timeout=30
    )

    response.raise_for_status()
    return response.json()