"""Release 2: the Multi-Agent integration must be OFF by default.

With MULTI_AGENT_ENABLED unset (the default, and what the cloud and CI use),
the labtests backend must refuse the call without trying to reach the
Multi-Agent Server.
"""
import requests

BASE_URL = "http://localhost:5005"
TIMEOUT = 10


def test_multi_agent_analyze_is_disabled_by_default():
    r = requests.post(
        f"{BASE_URL}/multi-agent/analyze",
        json={"order_id": 1},
        timeout=TIMEOUT,
    )
    assert r.status_code == 503
    assert r.json()["status"] == "disabled"