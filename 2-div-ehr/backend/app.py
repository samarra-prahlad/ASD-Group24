import os
from pathlib import Path
from flask import Flask, jsonify, request
from flask_cors import CORS
from openai import OpenAI
import requests

from mcp_client import call_get_change_request_status
from rag_client import call_answer_question

app = Flask(__name__)
CORS(app)

DATABASE_SERVICE_URL = os.environ.get("DATABASE_SERVICE_URL", "http://ehr-database:6002")
SHARED_ACCESS_API_URL = os.environ.get("SHARED_ACCESS_API_URL", "http://shared-backend:5000")
SHARED_DB_URL = os.environ.get("SHARED_DB_URL", "http://shared-database:6000")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
PROMPT_DIR = Path(__file__).with_name("prompts")
MCP_ENABLED = os.getenv("MCP_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")
RAG_ENABLED = os.getenv("RAG_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")

client = OpenAI(
    base_url=OLLAMA_BASE_URL,
    api_key="ollama"
)


def load_prompt(filename):
    prompt_path = PROMPT_DIR / filename
    return prompt_path.read_text(encoding="utf-8").strip()

def check_session(token):
    if not token:
        return None, None, (jsonify({"error": "token is required"}), 400)

    try:
        resp = requests.post(
            f"{SHARED_ACCESS_API_URL}/session/verify",
            json={"token": token},
            timeout=5,
        )
    except requests.RequestException as exc:
        return None, None, (jsonify({"error": "Shared access service unavailable", "details": str(exc)}), 503)

    if resp.status_code != 200:
        return None, None, (jsonify({"error": "Invalid or expired session"}), 401)

    data = resp.json()
    return data.get("patient_id"), data.get("role"), None

@app.get("/")
def health():
    return jsonify({"service": "ehr-backend", "status": "running"})


@app.get("/whoami")
def whoami():
    token = request.args.get("token")
    patient_id, role, err = check_session(token)
    if err:
        return err
    return jsonify({"patient_id": patient_id, "role": role})


@app.get("/patients")
def get_patients():
    token = request.args.get("token")
    caller_id, role, err = check_session(token)
    if err:
        return err
    if role != "admin":
        return jsonify({"error": "Staff access required"}), 403

    try:
        resp = requests.get(f"{SHARED_DB_URL}/patients", timeout=5)
    except requests.RequestException as exc:
        return jsonify({"error": "Shared database service unavailable", "details": str(exc)}), 503

    return jsonify(resp.json()), resp.status_code


#---Medical_Records---

# READ
@app.get("/records/<int:patient_id>")
def get_records(patient_id):
    token = request.args.get("token")
    caller_id, role, err = check_session(token)
    if err:
        return err
    if role == "patient" and caller_id != patient_id:
        return jsonify({"error": "Patients can only access their own records"}), 403

    try:
        resp = requests.get(f"{DATABASE_SERVICE_URL}/records/{patient_id}", timeout=5)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "EHR Database unavailable", "details": str(exc)}), 503

    return jsonify(resp.json())


# CREATE
@app.post("/records")
def create_record():
    data = request.get_json()
    token = data.get("token")
    caller_id, role, err = check_session(token)
    if err:
        return err
    if role != "admin":
        return jsonify({"error": "Only staff can add medical records"}), 403

    try:
        resp = requests.post(f"{DATABASE_SERVICE_URL}/records", json=data, timeout=5)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "EHR Database unavailable", "details": str(exc)}), 503

    return jsonify(resp.json()), 201


# UPDATE
@app.put("/records/<int:record_id>")
def update_record(record_id):
    data = request.get_json()
    token = data.get("token")
    caller_id, role, err = check_session(token)
    if err:
        return err
    if role != "admin":
        return jsonify({"error": "Only staff can edit medical records"}), 403

    try:
        resp = requests.put(f"{DATABASE_SERVICE_URL}/records/{record_id}", json=data, timeout=5)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "EHR Database unavailable", "details": str(exc)}), 503

    return jsonify(resp.json())


# DELETE
@app.delete("/records/<int:record_id>")
def delete_record(record_id):
    token = request.args.get("token")
    caller_id, role, err = check_session(token)
    if err:
        return err
    if role != "admin":
        return jsonify({"error": "Only staff can delete medical records"}), 403

    try:
        resp = requests.delete(f"{DATABASE_SERVICE_URL}/records/{record_id}", timeout=5)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "EHR Database unavailable", "details": str(exc)}), 503

    return jsonify(resp.json())


#---Diagnosis---

@app.get("/diagnosis/<int:patient_id>")
def get_diagnosis(patient_id):
    try:
        resp = requests.get(f"{DATABASE_SERVICE_URL}/records/{patient_id}", timeout=5)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "EHR Database unavailable", "details": str(exc)}), 503

    records = resp.json()
    if not records:
        return jsonify({"diagnosis": None, "allergies": None}), 404

    latest = records[0]
    return jsonify({"diagnosis": latest.get("diagnosis"), "allergies": latest.get("allergies")})

#---Change_Requests---

# READ (all)
@app.get("/change_requests")
def get_all_change_requests():
    token = request.args.get("token")
    caller_id, role, err = check_session(token)
    if err:
        return err
    if role != "admin":
        return jsonify({"error": "Only staff can view change requests"}), 403

    try:
        resp = requests.get(f"{DATABASE_SERVICE_URL}/change_requests", timeout=5)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "EHR Database unavailable", "details": str(exc)}), 503

    return jsonify(resp.json())


# READ (by patient)
@app.get("/change_requests/<int:patient_id>")
def get_change_requests(patient_id):
    token = request.args.get("token")
    caller_id, role, err = check_session(token)
    if err:
        return err
    if role == "patient" and caller_id != patient_id:
        return jsonify({"error": "Patients can only access their own change requests"}), 403

    try:
        resp = requests.get(f"{DATABASE_SERVICE_URL}/change_requests/{patient_id}", timeout=5)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "EHR Database unavailable", "details": str(exc)}), 503

    return jsonify(resp.json())

@app.get("/change_requests/mcp-status/<int:request_id>")
def get_change_request_status_via_mcp(request_id):
    token = request.args.get("token")
    caller_id, role, err = check_session(token)
    if err:
        return err

    if not MCP_ENABLED:
        return jsonify({"error": "MCP is disabled"}), 503

    try:
        result = call_get_change_request_status(request_id)
    except Exception as exc:
        return jsonify({"error": "MCP server unavailable", "details": str(exc)}), 503

    if "error" in result:
        return jsonify(result), 404

    if role == "patient" and result.get("patient_id") != caller_id:
        return jsonify({"error": "Patients can only access their own change requests"}), 403

    return jsonify(result), 200

# CREATE
@app.post("/change_requests")
def create_change_request():
    data = request.get_json()
    token = data.get("token")
    caller_id, role, err = check_session(token)
    if err:
        return err
    if role == "patient" and caller_id != data.get("patient_id"):
        return jsonify({"error": "Patients can only submit requests for themselves"}), 403

    try:
        resp = requests.post(f"{DATABASE_SERVICE_URL}/change_requests", json=data, timeout=5)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "EHR Database unavailable", "details": str(exc)}), 503

    return jsonify(resp.json()), 201


# UPDATE
@app.put("/change_requests/<int:request_id>")
def update_change_request(request_id):
    data = request.get_json()
    token = data.get("token")
    caller_id, role, err = check_session(token)
    if err:
        return err
    if role != "admin":
        return jsonify({"error": "Only staff can review change requests"}), 403

    try:
        resp = requests.put(f"{DATABASE_SERVICE_URL}/change_requests/{request_id}", json=data, timeout=5)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "EHR Database unavailable", "details": str(exc)}), 503

    return jsonify(resp.json())


@app.delete("/change_requests/<int:request_id>")
def delete_change_request(request_id):
    token = request.args.get("token")
    caller_id, role, err = check_session(token)
    if err:
        return err
    if role != "admin":
        return jsonify({"error": "Only staff can delete change requests"}), 403

    try:
        resp = requests.delete(f"{DATABASE_SERVICE_URL}/change_requests/{request_id}", timeout=5)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "EHR Database unavailable", "details": str(exc)}), 503

    return jsonify(resp.json())

#---Patient history summarization---

@app.post("/summarize")
def summarize_history():
    data = request.get_json()
    token = data.get("token")
    patient_id = data.get("patient_id")
    question = data.get("question", "").strip()

    caller_id, role, err = check_session(token)
    if err:
        return err
    if role == "patient" and caller_id != patient_id:
        return jsonify({"error": "Patients can only view their own history"}), 403

    try:
        resp = requests.get(f"{DATABASE_SERVICE_URL}/records/{patient_id}", timeout=5)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": "EHR Database unavailable", "details": str(exc)}), 503

    records = resp.json()
    if not records:
        return jsonify({"reply": "No medical history found for this patient."})

    history_lines = [
        f"- {r.get('visit_date')}: {r.get('diagnosis')} "
        f"(treatment: {r.get('treatment')}, notes: {r.get('notes')}, allergies: {r.get('allergies')})"
        for r in records
    ]
    history_text = "\n".join(history_lines)

    default_question = "Summarize this patient's medical history in a few sentences."
    user_prompt = (
        f"Patient history:\n{history_text}\n\n"
        f"Question: {question or default_question}"
    )

    try:
        completion = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": load_prompt("summarize_system_prompt.txt")
                },
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=250,
            temperature=0.2,
        )
        answer = completion.choices[0].message.content
        return jsonify({"reply": answer})

    except Exception as exc:
        return jsonify({
            "error": "Local AI agent request failed. Check that Ollama is running and qwen2.5:0.5b is installed.",
            "detail": str(exc)
        }), 503

@app.post("/ask-rag")
def ask_rag():
    data = request.get_json(silent=True) or {}
    token = data.get("token")
    question = (data.get("question") or "").strip()

    caller_id, role, err = check_session(token)
    if err:
        return err

    if not question:
        return jsonify({"error": "question is required"}), 400

    if not RAG_ENABLED:
        return jsonify({"error": "RAG is disabled"}), 503

    try:
        result = call_answer_question(question)
    except Exception as exc:
        return jsonify({"error": "RAG server unavailable", "details": str(exc)}), 503

    return jsonify(result), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)