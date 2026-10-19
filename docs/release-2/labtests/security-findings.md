# Feature 5 (Lab Tests) - security findings and resolutions

Scans are configured in `5-max-labtests/.pre-commit-config.yaml` and run on every commit
(install once: `pre-commit install -c 5-max-labtests/.pre-commit-config.yaml`).

| Scan | Finding | Resolution |
|---|---|---|
| Ruff S201 (flask-debug-true) | `debug=True` in `backend/app.py` exposes the Werkzeug debugger | **Fixed.** Debug is now off unless `FLASK_DEBUG=true` is set. |
| Ruff S104 (bind all interfaces), 2 places | `host="0.0.0.0"` in the backend and database apps | **Documented.** Inline `# noqa: S104`. Containers must listen on all interfaces to be reachable through Docker networking. |
| Ruff S101 (assert) and S113 (request timeout) in `tests/` | pytest uses bare `assert`; tests call local services | **Documented.** Ignored for `tests/` only, in `5-max-labtests/ruff.toml`. Application code has no ignores other than S104 above. |
| pip-audit | flask 3.0.3, flask-cors 4.0.1 and requests 2.32.3 had known vulnerabilities | **Fixed.** Upgraded to flask 3.1.3, flask-cors 6.0.0 and requests 2.33.0. All tests pass after the upgrade. |
| detect-secrets | None found | Baseline `5-max-labtests/.secrets.baseline` records 0 secrets. |

Limitation: shared services (`shared/`) and other students' folders still pin the older versions.
They are outside Feature 5's scope and are reported to the team lead.