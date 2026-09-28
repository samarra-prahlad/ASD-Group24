import os
import requests
from flask import Flask, jsonify, request, render_template, redirect
from flask_cors import CORS
from dotenv import load_dotenv
from openai import OpenAI
import re
from mcp_client import call_get_current_bed
from rag_client import call_answer_question

load_dotenv()

app = Flask(__name__)
CORS(app, supports_credentials=True)

DATABASE_SERVICE_URL = os.getenv("DATABASE_SERVICE_URL", "http://localhost:6006")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")

SHARED_ACCESS_API_URL = os.getenv("SHARED_ACCESS_API_URL", "http://localhost:5000")

MCP_ENABLED = os.getenv("MCP_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")
RAG_ENABLED = os.getenv("RAG_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")

client = OpenAI(
    base_url=OLLAMA_BASE_URL,
    api_key="ollama"
)


def load_prompt(filename):
    prompt_path = os.path.join(
        os.path.dirname(__file__),
        "prompts",
        filename
    )

    with open(prompt_path, "r", encoding="utf-8") as file:
        return file.read()   

@app.route("/auth/check")
def check_auth():
    token = request.cookies.get("session_token")

    if not token:
        return jsonify({
            "authenticated": False,
            "error": "Not logged in"
        }), 401

    try:
        response = requests.post(
            f"{SHARED_ACCESS_API_URL}/session/verify",
            json={"token": token},
            timeout=10
        )

    except requests.RequestException:
        return jsonify({
            "error": "Shared access service unavailable"
        }), 502

    if response.status_code != 200:
        return jsonify({
            "authenticated": False,
            "error": "Invalid session"
        }), 401

    session = response.json() or {}

    return jsonify({
        "authenticated": True,
        "role": session.get("role"),
        "patient_id": session.get("patient_id"),
        "first_name": session.get("first_name")
    }), 200

@app.route("/wards/<int:ward_id>")
def get_ward(ward_id):
    try:
        response = requests.get(
            f"{DATABASE_SERVICE_URL}/wards/{ward_id}",
            timeout=10
        )
    except requests.RequestException:
        return jsonify({"error": "Database service unavailable"}), 502

    return jsonify(response.json()), response.status_code

@app.route("/wards/<int:ward_id>/beds")
def get_beds(ward_id):
    try:
        response = requests.get(
            f"{DATABASE_SERVICE_URL}/wards/{ward_id}/beds",
            timeout=10
        )
    except requests.RequestException:
        return jsonify({"error": "Database service unavailable"}), 502

    return jsonify(response.json()), response.status_code

@app.route("/beds/<int:bed_id>/assign", methods=["PUT"])
def assign_patient_to_bed(bed_id):
    data = request.get_json() or {}

    patient_id = data.get("patient_id")

    if patient_id is None:
        return jsonify({"error": "patient_id is required"}), 400

    if not isinstance(patient_id, int):
        return jsonify({"error": "patient_id must be an integer"}), 400

    try:
        patient_response = requests.get(
            f"{SHARED_ACCESS_API_URL}/validate",
            params={"patient_id": patient_id},
            timeout=10
        )
    except requests.RequestException:
        return jsonify({"error": "Shared patient service unavailable"}), 502

    if patient_response.status_code == 404:
        return jsonify({"error": "Patient does not exist"}), 404

    if patient_response.status_code != 200:
        return jsonify({"error": "Unable to validate patient"}), patient_response.status_code

    
    try:
        bed_response = requests.put(
            f"{DATABASE_SERVICE_URL}/beds/{bed_id}/assign",
            json={"patient_id": patient_id},
            timeout=10
        )
    except requests.RequestException:
        return jsonify({"error": "Ward database service unavailable"}), 502

    return jsonify(bed_response.json()), bed_response.status_code

@app.get("/patients/<int:patient_id>/bed")
def get_patient_bed(patient_id):
    try:
        response = requests.get(
            f"{DATABASE_SERVICE_URL}/patients/{patient_id}/bed",
            timeout=10
        )
    except requests.RequestException:
        return jsonify({"error": "Ward database service unavailable"}), 502

    return jsonify(response.json()), response.status_code

@app.route("/beds/<int:bed_id>/release", methods=["PUT"])
def release_patient_from_bed(bed_id):
    try:
        bed_response = requests.put(
            f"{DATABASE_SERVICE_URL}/beds/{bed_id}/release",
            timeout=10
        )
    except requests.RequestException:
        return jsonify({
            "error": "Ward database service unavailable"
        }), 502

    return jsonify(bed_response.json()), bed_response.status_code

@app.get("/patients/<int:patient_id>/assignments")
def get_patient_assignments(patient_id):
    token = request.cookies.get("session_token")

    if not token:
        return jsonify({"error": "Not logged in"}), 401

    try:
        session_response = requests.post(
            f"{SHARED_ACCESS_API_URL}/session/verify",
            json={"token": token},
            timeout=10
        )
    except requests.RequestException:
        return jsonify({"error": "Shared access service unavailable"}), 502

    if session_response.status_code != 200:
        return jsonify({"error": "Invalid session"}), 401

    session = session_response.json()

    #Making sure a patient can only see their records but admins can see anyone's records. 
    if (
        session.get("role") == "patient" and session.get("patient_id") != patient_id
    ):
        return jsonify({
            "error": "You can only view your own records"
        }), 403

    try:
        db_response = requests.get(
            f"{DATABASE_SERVICE_URL}/patients/{patient_id}/assignments",
            timeout=10
        )
    except requests.RequestException:
        return jsonify({
            "error": "Ward database service unavailable"
        }), 502

    return jsonify(db_response.json()), db_response.status_code

@app.route("/ai/chat", methods=["POST"])
def ai_chat():
    data = request.get_json() or {}

    query = data.get("query")
    ward_id = data.get("ward_id")

    if not query:
        return jsonify({"error": "query is required"}), 400

    if ward_id is None:
        return jsonify({"error": "ward_id is required"}), 400
    
    try:
        ward_response = requests.get(
            f"{DATABASE_SERVICE_URL}/wards/{ward_id}",
            timeout=10
        )

        if ward_response.status_code != 200:
            return jsonify({"error": "Ward not found"}), 404

        beds_response = requests.get(
            f"{DATABASE_SERVICE_URL}/wards/{ward_id}/beds",
            timeout=10
        )

        if beds_response.status_code != 200:
            return jsonify({"error": "Unable to load beds"}), beds_response.status_code

    except requests.RequestException:
        return jsonify({"error": "Database service unavailable"}), 502

    ward = ward_response.json()
    beds = beds_response.json()

    loaded_system_prompt = load_prompt("implementation_system_prompt.txt")
    
    loaded_task_prompt = load_prompt("context_qa_task_prompt.txt")

    final_prompt = f"""
    {loaded_task_prompt}

    Current ward:
    {ward}

    Current beds:
    {beds}

    Question:
    {query}
    """

    try:
        response = client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": loaded_system_prompt
                },
                {
                    "role": "user",
                    "content": final_prompt
                }
            ],
            max_tokens=300,
            temperature=0.0
        )

        reply = response.choices[0].message.content

        return jsonify({
            "reply": reply
        }), 200

    except Exception as e:
        return jsonify({
            "error": "AI service unavailable"
        }), 502

def find_patient_id_in_question(question: str):
    match = re.search(r"\bpatient\s*(\d+)\b", question, re.IGNORECASE)

    if match:
        return int(match.group(1))

    return None

@app.route("/ask-mcp", methods=["POST"])
def ask_mcp():
    question = request.form.get("question", "").strip()

    if not question:
        return jsonify({
            "error": "Question is required"
        }), 400

    if not MCP_ENABLED:
        return jsonify({
            "error": "MCP is disabled"
        }), 503

    patient_id = find_patient_id_in_question(question)

    if patient_id is None:
        return jsonify({
            "error": "Could not identify a patient ID",
            "message": "Try asking: 'What bed is patient 12 in?'"
        }), 400

    try:
        bed_result = call_get_current_bed(patient_id)

    except Exception as exc:
        return jsonify({
            "error": "Could not reach MCP server",
            "details": str(exc)
        }), 503

    return jsonify(bed_result)

@app.route("/ask-rag", methods=["POST"])
def ask_rag():
    data = request.get_json() or {}

    question = data.get("question", "").strip()

    if not question:
        return jsonify({
            "error": "Question is required"
        }), 400

    if not RAG_ENABLED:
        return jsonify({"error": "RAG is disabled"}), 503

    try:
        result = call_answer_question(question)

    except Exception as exc:
        return jsonify({
            "error": "Could not reach RAG server",
            "details": str(exc)
        }), 503

    return jsonify(result), 200

#this was during testing to confirm the backend runs
@app.route("/health")
def health():
    return jsonify({"status": "backend running"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5006, debug=True)