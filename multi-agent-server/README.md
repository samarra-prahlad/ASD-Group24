# Group 24 Shared Multi-Agent Server

A non-containerised Flask service (port **7002**) that coordinates three agents and gates every result on a human decision:

**Planner** (qwen2.5:0.5b) → **Worker** (qwen2.5:0.5b) → **Reviewer** (llama3.1:8b) → **Human approve / partially accept / correct / reject**

The models can be changed with the `PLANNER_MODEL`, `WORKER_MODEL`, `REVIEWER_MODEL` and `OLLAMA_BASE_URL` environment variables.

## Run
```
ollama pull qwen2.5:0.5b && ollama pull llama3.1:8b
cd multi-agent-server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py                 # server on http://0.0.0.0:7002
python workflow_runner.py     # terminal workflow + human decision
python -m pytest tests -q     # 23 tests, mocked LLM
```
Each agent can also run on its own: `python agents/planner_agent.py` (likewise `worker_agent.py` and `reviewer_agent.py`).

## API contract
| Method | Path | Body / query | Returns |
|---|---|---|---|
| GET | `/health` | – | status, agents, models |
| POST | `/workflow` | `{feature, user_request, evidence: [ {...} ], requested_by?}` | 201 + workflow `awaiting_human_review`, or 503 + `failed` |
| GET | `/workflow/<id>` | – | the workflow, or 404 |
| POST | `/workflow/<id>/review` | `{decision, reviewer, notes?, correction?}` | 200 updated workflow; 400 invalid; 404 unknown; 409 already reviewed |
| GET | `/workflows` | `?feature=billing&limit=20` | `{workflows: [...]}` newest first |

`decision` is one of `approve`, `partially_accept`, `correct` (requires `correction`) or `reject`.
`final_output` stays `null` until a human decides.

## How a feature backend uses it
Every backend in `docker-compose.yml` already has `MULTI_AGENT_ENABLED` and
`MULTI_AGENT_SERVER_URL=http://host.docker.internal:7002`.

Gather your evidence (your own records or tool results), then call the server. Never pass credentials or tokens.
```python
MULTI_AGENT_SERVER_URL = os.environ.get("MULTI_AGENT_SERVER_URL", "http://host.docker.internal:7002")
MULTI_AGENT_ENABLED = os.environ.get("MULTI_AGENT_ENABLED", "true").lower() == "true"

resp = requests.post(f"{MULTI_AGENT_SERVER_URL}/workflow", json={
    "feature": "pharmacy",                       # your feature name
    "user_request": "Summarise this patient's active prescriptions",
    "evidence": records,                         # list of dicts, max 20 used
    "requested_by": "admin",
}, timeout=300)
workflow = resp.json()
# workflow["steps"]["planner" | "worker" | "reviewer"]["output"]
# workflow["steps"]["reviewer"]["risk_level"]  -> LOW / MEDIUM / HIGH / UNKNOWN

requests.post(f"{MULTI_AGENT_SERVER_URL}/workflow/{workflow['workflow_id']}/review", json={
    "decision": "approve", "reviewer": "admin", "notes": "checked",
}, timeout=10)
```
In your UI, show the three agent outputs plus the risk level, with four buttons (Approve / Partially accept / Correct / Reject) that call the review endpoint.
Use a long timeout (the three agents take about 40–60 seconds), and escape agent output before putting it in HTML.

## Governance and audit
- `coordination_audit.jsonl` holds one event per step (`workflow_started`, `agent_started`/`agent_completed`/`agent_failed`, `awaiting_human_review`, `human_decision`).
- `workflow_history.jsonl` holds full workflow snapshots; history is reloaded on restart. Both files are git-ignored.
- The Reviewer's `RISK` and `RECOMMENDATION` are parsed. If evidence was supplied but the Worker cited no evidence IDs, risk is raised to MEDIUM automatically.
- A workflow can be reviewed only once (409 afterwards).
- Known limitation: the small models can misread evidence (for example, listing a paid invoice as outstanding) and the Reviewer may not catch it. That is why a human decision is mandatory.
