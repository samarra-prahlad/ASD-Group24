import os

import requests

SHARED_ACCESS_API_URL = os.getenv("SHARED_ACCESS_API_URL", "http://shared-backend:5000")


def check(label, method, url, **kwargs):
    try:
        response = requests.request(method, url, timeout=5, **kwargs)
        content_ok = bool(response.text and response.text.strip())
        return f"{label} -> HTTP {response.status_code}, content_ok={content_ok}"
    except Exception as exc:
        return f"{label} -> error: {exc}"


def observe_shared_access():
    result = check("shared-access-api", "GET", f"{SHARED_ACCESS_API_URL}/validate?patient_id=101")
    print(f"  Checked {result}")
    return result


def observe_all_services(plan):
    results = [observe_shared_access()]

    for service in plan["services"]:
        url = f"http://{service['name']}-backend:{service['backend_port']}/"
        result = check(f"{service['name']}-backend", "GET", url)
        print(f"  Checked {result}")
        results.append(result)

    return results