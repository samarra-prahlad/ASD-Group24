import os
import re
import asyncio
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

app = Flask(__name__)
CORS(app)

DATABASE_SERVICE_URL = os.getenv("DATABASE_SERVICE_URL", "http://labtests-database:6005")
SHARED_ACCESS_API_URL = os.getenv("SHARED_ACCESS_API_URL", "http://shared-backend:5000")
SHARED_DATABASE_URL = os.getenv("SHARED_DATABASE_URL", "http://shared-database:6000")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://host.docker.internal:7000/mcp")
RAG_SERVER_URL = os.getenv("RAG_SERVER_URL", "http://host.docker.internal:7001/mcp")

# MCP/RAG integration is retained in code but disabled by default, so cloud
# deployments (where the shared MCP/RAG servers and Ollama are not running)
# work without AI. Set to "true" in docker-compose for local demos.
MCP_RAG_ENABLED = os.getenv("MCP_RAG_ENABLED", "false").lower() == "true"

# Multi-Agent Server integration. Off by default, so cloud deployments and CI
# never depend on it. Set MULTI_AGENT_ENABLED=true to use it.
MULTI_AGENT_ENABLED = os.getenv("MULTI_AGENT_ENABLED", "false").lower() == "true"
MULTI_AGENT_SERVER_URL = os.getenv("MULTI_AGENT_SERVER_URL", "http://host.docker.internal:7002")
MULTI_AGENT_DECISIONS = ("approve", "partially_accept", "correct", "reject")


async def _call_tool(server_url, tool_name, arguments):
    """Generic MCP-protocol tool call, used for both the shared MCP server
    (port 7000) and the shared RAG server (port 7001) — both speak the same
    MCP client/session protocol, just expose different tools."""
    async with streamablehttp_client(server_url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            return result


def _extract_tool_result(result):
    """MCP tool results can come back as structuredContent (preferred) or as
    a text blob that needs JSON-parsing, depending on SDK/server version."""
    if getattr(result, "structuredContent", None):
        return result.structuredContent
    import json
    text = result.content[0].text
    return json.loads(text)

def load_prompt(filename):
    path = os.path.join(os.path.dirname(__file__), "prompts", filename)
    with open(path, "r") as f:
        return f.read()

@app.get("/")
def health():
    return jsonify({"service": "labtests-backend", "status": "running"})


@app.get("/orders")
def get_orders():
    r = requests.get(f"{DATABASE_SERVICE_URL}/orders", timeout=5)
    return jsonify(r.json())

@app.get("/orders/<int:order_id>")
def get_order(order_id):
    r = requests.get(f"{DATABASE_SERVICE_URL}/orders/{order_id}", timeout=5)
    return jsonify(r.json()), r.status_code


@app.get("/mcp/order-status/<int:order_id>")
def mcp_order_status(order_id):
    if not MCP_RAG_ENABLED:
        return jsonify({"error": "MCP/RAG disabled in this environment"}), 503
    try:
        result = asyncio.run(
            _call_tool(MCP_SERVER_URL, "labtests_get_order_status", {"order_id": order_id})
        )
        return jsonify(_extract_tool_result(result))
    except Exception as exc:
        return jsonify({"error": "MCP server unreachable", "detail": str(exc)}), 503

@app.post("/orders")
def create_order():
    data = request.get_json()
    patient_id = data.get("patient_id")

    try:
        v = requests.get(f"{SHARED_DATABASE_URL}/patients/{patient_id}", timeout=5)
        if v.status_code != 200:
            return jsonify({"error": "Invalid patient_id"}), 400
    except requests.RequestException as exc:
        return jsonify({"error": "Shared database unavailable", "detail": str(exc)}), 503

    r = requests.post(f"{DATABASE_SERVICE_URL}/orders", json=data, timeout=5)
    return jsonify(r.json()), r.status_code


@app.get("/results/<int:order_id>")
def get_results(order_id):
    r = requests.get(f"{DATABASE_SERVICE_URL}/results/{order_id}", timeout=5)
    return jsonify(r.json())


@app.post("/results")
def create_result():
    data = request.get_json()

    flagged, ai_notes = flag_result_with_ai(data["result_value"], data["reference_range"])
    data["flagged"] = flagged
    data["ai_notes"] = ai_notes

    r = requests.post(f"{DATABASE_SERVICE_URL}/results", json=data, timeout=5)
    return jsonify(r.json()), r.status_code

@app.put("/results/<int:result_id>")
def update_result(result_id):
    data = request.get_json()
    r = requests.put(f"{DATABASE_SERVICE_URL}/results/{result_id}", json=data, timeout=5)
    return jsonify(r.json()), r.status_code

@app.delete("/results/<int:result_id>")
def delete_result(result_id):
    r = requests.delete(f"{DATABASE_SERVICE_URL}/results/{result_id}", timeout=5)
    return jsonify(r.json()), r.status_code

def flag_result_with_ai(result_value, reference_range):
    prompt = load_prompt("flagging_prompt.txt").format(
        result_value=result_value, reference_range=reference_range
    )

    try:
        r = requests.post(
            f"{OLLAMA_BASE_URL}/chat/completions",
            json={
                "model": OLLAMA_MODEL,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=15,
        )
        text = r.json()["choices"][0]["message"]["content"].strip()
        upper_text = text.upper()

        verdict_match = re.search(r"VERDICT:\s*(YES|NO)", upper_text)
        if verdict_match:
            flagged = 1 if verdict_match.group(1) == "YES" else 0
        else:
            # model didn't follow the format — fall back to scanning for abnormality language
            abnormal_keywords = ["ABNORMAL", "OUTSIDE", "ELEVATED", "HIGH", "LOW", "NOT NORMAL", "FLAG"]
            flagged = 1 if any(kw in upper_text for kw in abnormal_keywords) else 0

        reason_match = re.search(r"REASON:\s*(.+)", text, re.IGNORECASE | re.DOTALL)
        ai_notes = reason_match.group(1).strip() if reason_match else text

        return flagged, ai_notes
    except Exception as exc:
        return 0, f"AI flagging unavailable: {exc}"


@app.post("/chat")
def chat():
    """
    Grounded chatbot: instead of sending the user's question straight to
    Ollama (which just guesses from its training data), this calls the
    shared RAG server's answer_question tool. That tool retrieves relevant
    chunks from our knowledge base (rag-server/knowledge/labtests/*.md),
    then asks Ollama to answer using only that retrieved context — and
    reports back which sources it used and how confident it is.
    """
    data = request.get_json()
    user_message = data.get("message", "")

    if not MCP_RAG_ENABLED:
        return jsonify({
            "reply": "MCP/RAG disabled in this environment.",
            "status": "disabled",
            "citations": [],
            "confidence_category": "Insufficient",
        })

    try:
        result = asyncio.run(
            _call_tool(RAG_SERVER_URL, "answer_question", {"query": user_message, "top_k": 5})
        )
        rag_response = _extract_tool_result(result)
    except Exception as exc:
        return jsonify({
            "reply": f"Chat unavailable: RAG server unreachable ({exc})",
            "status": "error",
            "citations": [],
            "confidence_category": "Insufficient",
        })

    return jsonify({
        "reply": rag_response.get("answer", "No answer returned."),
        "status": rag_response.get("status", "ok"),
        "citations": rag_response.get("citations", []),
        "confidence_category": rag_response.get("confidence_category", "Insufficient"),
        "retrieval_summary": rag_response.get("retrieval_summary", {}),
    })

@app.put("/orders/<int:order_id>")
def update_order(order_id):
    data = request.get_json()
    r = requests.put(f"{DATABASE_SERVICE_URL}/orders/{order_id}", json=data, timeout=5)
    return jsonify(r.json()), r.status_code

@app.delete("/orders/<int:order_id>")
def delete_order(order_id):
    r = requests.delete(f"{DATABASE_SERVICE_URL}/orders/{order_id}", timeout=5)
    return jsonify(r.json()), r.status_code

@app.get("/results")
def get_all_results():
    r = requests.get(f"{DATABASE_SERVICE_URL}/results", timeout=5)
    return jsonify(r.json())

@app.get("/my-results")
def get_my_results():
    token = request.args.get("token")
    if not token:
        return jsonify({"error": "token is required"}), 400

    # resolve token -> patient_id via shared session verify
    v = requests.post(f"{SHARED_ACCESS_API_URL}/session/verify", json={"token": token}, timeout=5)
    if v.status_code != 200 or not v.json().get("valid"):
        return jsonify({"error": "Invalid or expired session"}), 401
    patient_id = v.json()["patient_id"]

    # get this patient's orders, then their results
    orders_resp = requests.get(f"{DATABASE_SERVICE_URL}/orders", timeout=5)
    my_order_ids = [o["order_id"] for o in orders_resp.json() if o["patient_id"] == patient_id]

    all_results_resp = requests.get(f"{DATABASE_SERVICE_URL}/results", timeout=5)
    my_results = [r for r in all_results_resp.json() if r["order_id"] in my_order_ids]

    return jsonify(my_results)

MAX_EVIDENCE = 6


def _patient_lab_evidence(patient_id):
    """Collect a short, compact evidence list for one patient: their newest lab
    results first, then orders that have no result yet. Kept small because the
    agents use small models that struggle with long inputs."""
    orders = requests.get(f"{DATABASE_SERVICE_URL}/orders", timeout=5).json()
    my_orders = {o["order_id"]: o for o in orders if o["patient_id"] == patient_id}
    results = requests.get(f"{DATABASE_SERVICE_URL}/results", timeout=5).json()
    my_results = sorted(
        (r for r in results if r["order_id"] in my_orders),
        key=lambda r: r["result_id"],
        reverse=True,
    )

    evidence = []
    for r in my_results:
        evidence.append({
            "id": f"result-{r['result_id']}",
            "test": my_orders[r["order_id"]]["test_type"],
            "value": r["result_value"],
            "reference_range": r["reference_range"],
            "flagged": bool(r["flagged"]),
        })

    resulted_orders = {r["order_id"] for r in my_results}
    for order_id in sorted(my_orders, reverse=True):
        if order_id not in resulted_orders:
            evidence.append({
                "id": f"order-{order_id}",
                "test": my_orders[order_id]["test_type"],
                "status": my_orders[order_id]["status"],
            })
    return evidence[:MAX_EVIDENCE]


@app.post("/multi-agent/workflow")
def multi_agent_workflow():
    """Run the shared Multi-Agent Server (Planner, Worker, Reviewer) over one
    patient's lab records. Disabled unless MULTI_AGENT_ENABLED=true."""
    if not MULTI_AGENT_ENABLED:
        return jsonify({"status": "disabled",
                        "error": "Multi-Agent integration disabled in this environment"}), 503
    data = request.get_json(silent=True) or {}
    patient_id = data.get("patient_id")
    if not isinstance(patient_id, int) or isinstance(patient_id, bool):
        return jsonify({"error": "patient_id (integer) is required"}), 400
    user_request = str(data.get("user_request") or
                       "Summarise this patient's lab results and flag anything unusual")[:500]
    try:
        evidence = _patient_lab_evidence(patient_id)
        if not evidence:
            return jsonify({"error": "No lab orders or results found for this patient"}), 404
        r = requests.post(
            f"{MULTI_AGENT_SERVER_URL}/workflow",
            json={
                "feature": "labtests",
                "user_request": f"{user_request} (Patient ID: {patient_id})",
                "evidence": evidence,
                "requested_by": "labtests-staff",
            },
            timeout=300,
        )
        return jsonify(r.json()), r.status_code
    except (requests.RequestException, ValueError) as exc:
        return jsonify({"status": "error", "error": "Multi-Agent server unreachable",
                        "detail": str(exc)}), 503


@app.post("/multi-agent/workflow/<workflow_id>/review")
def multi_agent_review(workflow_id):
    """Send the human decision (approve / partially_accept / correct / reject)
    to the Multi-Agent Server. Disabled unless MULTI_AGENT_ENABLED=true."""
    if not MULTI_AGENT_ENABLED:
        return jsonify({"status": "disabled",
                        "error": "Multi-Agent integration disabled in this environment"}), 503
    if not re.fullmatch(r"wf-[0-9a-f]+", workflow_id):
        return jsonify({"error": "Invalid workflow id"}), 400
    data = request.get_json(silent=True) or {}
    decision = data.get("decision")
    if decision not in MULTI_AGENT_DECISIONS:
        return jsonify({"error": f"decision must be one of {', '.join(MULTI_AGENT_DECISIONS)}"}), 400
    body = {
        "decision": decision,
        "reviewer": str(data.get("reviewer") or "labtests-staff")[:100],
        "notes": str(data.get("notes") or "")[:1000],
    }
    if decision == "correct":
        correction = str(data.get("correction") or "").strip()
        if not correction:
            return jsonify({"error": "correction text is required for 'correct'"}), 400
        body["correction"] = correction
    try:
        r = requests.post(f"{MULTI_AGENT_SERVER_URL}/workflow/{workflow_id}/review",
                          json=body, timeout=10)
        return jsonify(r.json()), r.status_code
    except (requests.RequestException, ValueError) as exc:
        return jsonify({"status": "error", "error": "Multi-Agent server unreachable",
                        "detail": str(exc)}), 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")  # noqa: S104 - container must listen on all interfaces