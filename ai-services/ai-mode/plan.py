PLAN = {
    "goal": "Validate Group 24 healthcare microservices using a shared multi-agent workflow",
    "services": [
        {"name": "appointments", "backend_port": 5001},
        {"name": "ehr", "backend_port": 5002},
        {"name": "pharmacy", "backend_port": 5003},
        {"name": "billing", "backend_port": 5004},
        {"name": "labtests", "backend_port": 5005},
        {"name": "wardbed", "backend_port": 5006},
    ],
    "shared_access_check": "GET /validate on the shared access API",
}